#!/usr/bin/env python3
"""Idempotently provision, seed, inspect, or destroy a Vertex AI RAG Corpus from GCS policy files."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _get_access_token() -> str:
    """Obtain a GCP OAuth2 access token via google-auth or gcloud CLI fallback."""
    env_token = os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN", "").strip()
    if env_token:
        return env_token

    try:
        import google.auth
        from google.auth.transport.requests import Request

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(Request())
        if credentials.token:
            return credentials.token
    except Exception:
        pass

    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=True,
        capture_output=True,
        text=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("Failed to obtain GCP access token via google-auth or gcloud.")
    return token


def _http_json(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Execute an authenticated JSON HTTP request against GCP REST APIs."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {url}: {body}") from exc


def _poll_lro(region: str, operation_name: str, token: str, timeout_seconds: int = 300) -> dict[str, Any]:
    """Poll a Vertex AI long-running operation until completion or timeout."""
    base = f"https://{region}-aiplatform.googleapis.com/v1beta1"
    op_url = f"{base}/{operation_name.lstrip('/')}"
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        op = _http_json("GET", op_url, token)
        if op.get("done"):
            if "error" in op:
                raise RuntimeError(f"Vertex AI operation failed: {json.dumps(op['error'])}")
            return op
        time.sleep(3)

    raise TimeoutError(f"Timed out waiting for Vertex AI operation {operation_name}")


def _find_corpus_by_display_name(
    project_id: str,
    region: str,
    display_name: str,
    token: str,
) -> dict[str, Any] | None:
    """Return the matching ragCorpus resource dict if present, else None."""
    base = f"https://{region}-aiplatform.googleapis.com/v1beta1"
    parent = f"projects/{project_id}/locations/{region}"
    page_token = ""

    while True:
        query = f"?pageToken={urllib.parse.quote(page_token)}" if page_token else ""
        resp = _http_json("GET", f"{base}/{parent}/ragCorpora{query}", token)
        for corpus in resp.get("ragCorpora", []):
            if corpus.get("displayName") == display_name:
                return corpus
        page_token = resp.get("nextPageToken", "")
        if not page_token:
            return None


def _build_create_corpus_payload(
    project_id: str,
    region: str,
    display_name: str,
    embedding_model: str,
) -> dict[str, Any]:
    return {
        "displayName": display_name,
        "description": "Enterprise Cloud, Security, Licensing & Commercial Governance Policies",
        "ragVectorDbConfig": {
            "ragEmbeddingModelConfig": {
                "vertexPredictionEndpoint": {
                    "endpoint": (
                        f"projects/{project_id}/locations/{region}"
                        f"/publishers/google/models/{embedding_model}"
                    ),
                }
            }
        },
    }


def _create_corpus(
    project_id: str,
    region: str,
    display_name: str,
    embedding_model: str,
    token: str,
) -> dict[str, Any]:
    """Create a Vertex AI RAG Corpus and wait for provisioning to finish."""
    base = f"https://{region}-aiplatform.googleapis.com/v1beta1"
    parent = f"projects/{project_id}/locations/{region}"
    payload = _build_create_corpus_payload(project_id, region, display_name, embedding_model)

    op = _http_json("POST", f"{base}/{parent}/ragCorpora", token, payload=payload)
    if op.get("name") and not op.get("done"):
        op = _poll_lro(region, op["name"], token)

    response = op.get("response")
    if isinstance(response, dict) and response.get("name"):
        return response

    created = _find_corpus_by_display_name(project_id, region, display_name, token)
    if created is None:
        raise RuntimeError(f"Corpus '{display_name}' creation completed but lookup failed.")
    return created


def _ensure_rag_bucket_reader(bucket: str, project_number: str, token: str) -> bool:
    """Grant roles/storage.objectViewer on bucket to the Vertex RAG service agent idempotently."""
    if not bucket or not project_number:
        return False

    member = f"serviceAccount:service-{project_number}@gcp-sa-vertex-rag.iam.gserviceaccount.com"
    role = "roles/storage.objectViewer"
    iam_url = f"https://storage.googleapis.com/storage/v1/b/{urllib.parse.quote(bucket, safe='')}/iam"

    for attempt in range(6):
        policy = _http_json("GET", iam_url, token)
        bindings = policy.get("bindings", [])
        target_binding = next((b for b in bindings if b.get("role") == role), None)
        if target_binding and member in target_binding.get("members", []):
            return True

        if target_binding is not None:
            target_binding.setdefault("members", []).append(member)
        else:
            bindings.append({"role": role, "members": [member]})
        policy["bindings"] = bindings

        try:
            _http_json("PUT", iam_url, token, payload=policy)
            return True
        except RuntimeError as exc:
            if "does not exist" in str(exc) and attempt < 5:
                time.sleep(5)
                continue
            raise

    return False


def _list_gcs_policy_uris(bucket: str, prefix: str, token: str) -> list[str]:
    """List policy document gs:// URIs in the configured GCS bucket prefix."""
    cleaned_prefix = prefix.strip("/")
    prefix_param = f"{cleaned_prefix}/" if cleaned_prefix else ""
    url = (
        f"https://storage.googleapis.com/storage/v1/b/{urllib.parse.quote(bucket, safe='')}/o"
        f"?prefix={urllib.parse.quote(prefix_param, safe='')}"
    )
    resp = _http_json("GET", url, token)
    uris: list[str] = []
    for item in resp.get("items", []):
        name = item.get("name", "")
        if not name or name.endswith("/") or name.endswith(".gitkeep"):
            continue
        if name.lower().endswith((".md", ".pdf", ".txt")):
            uris.append(f"gs://{bucket}/{name}")
    return sorted(uris)


def _build_import_payload(gcs_uris: list[str], chunk_size: int, chunk_overlap: int) -> dict[str, Any]:
    return {
        "importRagFilesConfig": {
            "gcsSource": {"uris": gcs_uris},
            "ragFileChunkingConfig": {
                "fixedLengthChunking": {
                    "chunkSize": chunk_size,
                    "chunkOverlap": chunk_overlap,
                }
            },
        }
    }


def _import_rag_files(
    region: str,
    corpus_name: str,
    gcs_uris: list[str],
    chunk_size: int,
    chunk_overlap: int,
    token: str,
) -> dict[str, Any]:
    """Import policy files from GCS into the Vertex AI RAG Corpus and wait for indexing."""
    base = f"https://{region}-aiplatform.googleapis.com/v1beta1"
    payload = _build_import_payload(gcs_uris, chunk_size, chunk_overlap)
    op = _http_json("POST", f"{base}/{corpus_name}:importRagFiles", token, payload=payload)
    if op.get("name") and not op.get("done"):
        op = _poll_lro(region, op["name"], token, timeout_seconds=600)
    return op


def _list_rag_files(region: str, corpus_name: str, token: str) -> list[dict[str, Any]]:
    """List indexed RAG files inside a corpus to inspect their indexing status."""
    base = f"https://{region}-aiplatform.googleapis.com/v1beta1"
    files: list[dict[str, Any]] = []
    page_token = ""

    while True:
        query = f"?pageToken={urllib.parse.quote(page_token)}" if page_token else ""
        resp = _http_json("GET", f"{base}/{corpus_name}/ragFiles{query}", token)
        files.extend(resp.get("ragFiles", []))
        page_token = resp.get("nextPageToken", "")
        if not page_token:
            return files


def _delete_corpus(region: str, corpus_name: str, token: str) -> None:
    """Force-delete a Vertex AI RAG Corpus and wait for the operation to finish."""
    base = f"https://{region}-aiplatform.googleapis.com/v1beta1"
    op = _http_json("DELETE", f"{base}/{corpus_name}?force=true", token)
    if op.get("name") and not op.get("done"):
        _poll_lro(region, op["name"], token)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage & seed Vertex AI RAG Corpus from GCS policies.")
    parser.add_argument("--action", choices=("seed", "status", "destroy"), default="seed")
    parser.add_argument("--project-id", default=os.getenv("GCP_PROJECT_ID", ""))
    parser.add_argument("--project-number", default=os.getenv("GCP_PROJECT_NUMBER", ""))
    parser.add_argument("--region", default=os.getenv("GCP_REGION", "europe-west3"))
    parser.add_argument("--corpus-display-name", default="enterprise-agent-policies")
    parser.add_argument("--embedding-model", default="text-embedding-005")
    parser.add_argument("--gcs-bucket", default="")
    parser.add_argument("--gcs-prefix", default="policies")
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true", help="Print planned API requests without calling GCP.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.project_id:
        print("ERROR: --project-id (or GCP_PROJECT_ID env var) is required.", file=sys.stderr)
        return 2

    if args.dry_run:
        plan: dict[str, Any] = {
            "dry_run": True,
            "action": args.action,
            "project_id": args.project_id,
            "region": args.region,
            "corpus_display_name": args.corpus_display_name,
        }
        if args.action == "seed":
            sample_uris = [f"gs://{args.gcs_bucket}/{args.gcs_prefix.strip('/')}/*"] if args.gcs_bucket else []
            plan["create_corpus_payload"] = _build_create_corpus_payload(
                args.project_id, args.region, args.corpus_display_name, args.embedding_model
            )
            plan["import_files_payload"] = _build_import_payload(sample_uris, args.chunk_size, args.chunk_overlap)
        elif args.action == "destroy":
            plan["delete_endpoint"] = (
                f"https://{args.region}-aiplatform.googleapis.com/v1beta1/"
                f"projects/{args.project_id}/locations/{args.region}/ragCorpora/<CORPUS_ID>?force=true"
            )
        print(json.dumps(plan, indent=2))
        return 0

    token = _get_access_token()

    if args.action == "destroy":
        corpus = _find_corpus_by_display_name(args.project_id, args.region, args.corpus_display_name, token)
        if corpus is None:
            print(json.dumps({"action": "destroy", "status": "already_absent", "display_name": args.corpus_display_name}))
            return 0
        _delete_corpus(args.region, corpus["name"], token)
        print(json.dumps({"action": "destroy", "status": "deleted", "corpus_name": corpus["name"]}))
        return 0

    if args.action == "status":
        corpus = _find_corpus_by_display_name(args.project_id, args.region, args.corpus_display_name, token)
        if corpus is None:
            print(json.dumps({"action": "status", "status": "not_found", "display_name": args.corpus_display_name}))
            return 1
        rag_files = _list_rag_files(args.region, corpus["name"], token)
        summary = [
            {
                "name": f.get("name"),
                "displayName": f.get("displayName"),
                "fileStatus": f.get("fileStatus", {}),
            }
            for f in rag_files
        ]
        print(json.dumps({"action": "status", "corpus": corpus["name"], "files_count": len(rag_files), "files": summary}, indent=2))
        return 0

    # action == "seed"
    corpus = _find_corpus_by_display_name(args.project_id, args.region, args.corpus_display_name, token)
    created_now = False
    if corpus is None:
        corpus = _create_corpus(
            args.project_id,
            args.region,
            args.corpus_display_name,
            args.embedding_model,
            token,
        )
        created_now = True

    corpus_name = corpus["name"]
    project_number = args.project_number.strip()
    if not project_number and corpus_name.startswith("projects/"):
        candidate = corpus_name.split("/")[1]
        if candidate.isdigit():
            project_number = candidate

    if args.gcs_bucket and project_number:
        _ensure_rag_bucket_reader(args.gcs_bucket, project_number, token)

    uris = _list_gcs_policy_uris(args.gcs_bucket, args.gcs_prefix, token) if args.gcs_bucket else []
    if not uris:
        print(
            json.dumps(
                {
                    "action": "seed",
                    "corpus_name": corpus_name,
                    "created": created_now,
                    "imported_uris": [],
                    "message": "Corpus ready; no .md/.pdf/.txt policy objects found in GCS prefix yet.",
                },
                indent=2,
            )
        )
        return 0

    _import_rag_files(args.region, corpus_name, uris, args.chunk_size, args.chunk_overlap, token)
    rag_files = _list_rag_files(args.region, corpus_name, token)
    print(
        json.dumps(
            {
                "action": "seed",
                "corpus_name": corpus_name,
                "created": created_now,
                "imported_uris": uris,
                "indexed_files_count": len(rag_files),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
