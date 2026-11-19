"""Vertex AI RAG Corpus retriever with local policy fallback for offline/local runs."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BUILTIN_POLICIES: list[dict[str, str]] = [
    {
        "title": "01_cloud_strategy_policy.md",
        "source": "builtin://policies/01_cloud_strategy_policy.md",
        "text": (
            "Enterprise Cloud-First Policy: All new workloads and customer engagements must target "
            "managed Google Cloud Platform (GCP) services such as Cloud Run, GKE, Vertex AI, and Firestore. "
            "Strictly on-premises or air-gapped deployments without Cloud connectivity are not supported "
            "and represent a hard delivery blocker unless formally approved by the CTO board."
        ),
    },
    {
        "title": "02_security_gdpr_policy.md",
        "source": "builtin://policies/02_security_gdpr_policy.md",
        "text": (
            "Security & GDPR Compliance Policy: Production deployments handling EU customer data must "
            "run in EU regions (e.g., europe-west3), enforce encryption at rest and in transit (TLS 1.2+), "
            "enable Cloud Audit Logging, and adhere to ISO 27001 / Zero Trust IAM principles without shared root access."
        ),
    },
    {
        "title": "03_oss_licensing_policy.md",
        "source": "builtin://policies/03_oss_licensing_policy.md",
        "text": (
            "Open-Source & IP Licensing Policy: Approved permissive licenses include Apache-2.0, MIT, and BSD-3-Clause. "
            "Viral copyleft licenses such as AGPL-3.0 or GPLv3 for custom client deliverables are strictly prohibited "
            "due to intellectual property contamination risks."
        ),
    },
    {
        "title": "04_commercial_governance_policy.md",
        "source": "builtin://policies/04_commercial_governance_policy.md",
        "text": (
            "Commercial & Liability Policy: Standard consulting agreements cap total liability at 1x contract value. "
            "Unlimited liability clauses or uncapped SLA liquidated damages constitute a commercial red flag and "
            "require executive escalation (No-Go without cap)."
        ),
    },
]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9äöüß]{3,}", text.lower()))


class VertexRagRetriever:
    """Queries a Vertex AI RAG Corpus or falls back to local/built-in policy documents."""

    def __init__(
        self,
        corpus_name: str | None = None,
        region: str | None = None,
        policy_dir: str | None = None,
        corpus_display_name: str | None = None,
    ) -> None:
        self.corpus_name = (
            corpus_name if corpus_name is not None else os.getenv("VERTEX_RAG_CORPUS", "")
        ).strip()
        self.corpus_display_name = (
            corpus_display_name
            if corpus_display_name is not None
            else os.getenv("VERTEX_RAG_CORPUS_DISPLAY_NAME", "")
        ).strip()
        self.region = (
            region or os.getenv("VERTEX_RAG_REGION") or os.getenv("GCP_REGION", "europe-west3")
        ).strip()
        self.policy_dir = policy_dir or os.getenv("POLICY_SEED_DIR", "")
        self.project_id = (
            os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT", "")
        ).strip()

    def _load_local_policies(self) -> list[dict[str, str]]:
        """Load markdown policy files from disk if available, otherwise return built-in snippets."""
        candidates: list[Path] = []
        if self.policy_dir:
            candidates.append(Path(self.policy_dir))
        for parent in Path(__file__).resolve().parents:
            candidates.append(parent / "seed-data" / "policies")

        loaded: list[dict[str, str]] = []
        for directory in candidates:
            if not directory.is_dir():
                continue
            for md_file in sorted(directory.glob("*.md")):
                content = md_file.read_text(encoding="utf-8").strip()
                if content:
                    loaded.append(
                        {
                            "title": md_file.name,
                            "source": f"file://{md_file.name}",
                            "text": content,
                        }
                    )
            if loaded:
                return loaded

        return list(BUILTIN_POLICIES)

    async def _resolve_corpus_name(self, token: str) -> str:
        """Resolve Vertex AI RAG Corpus resource name by display name and cache it."""
        if self.corpus_name:
            return self.corpus_name
        if not self.corpus_display_name or not self.project_id:
            return ""

        base = f"https://{self.region}-aiplatform.googleapis.com/v1beta1"
        parent = f"projects/{self.project_id}/locations/{self.region}"
        headers = {"Authorization": f"Bearer {token}"}
        page_token = ""

        async with httpx.AsyncClient(timeout=15.0) as client:
            while True:
                params = {"pageToken": page_token} if page_token else None
                resp = await client.get(f"{base}/{parent}/ragCorpora", params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                for corpus in data.get("ragCorpora", []):
                    if corpus.get("displayName") == self.corpus_display_name and corpus.get("name"):
                        self.corpus_name = corpus["name"]
                        return self.corpus_name
                page_token = data.get("nextPageToken", "")
                if not page_token:
                    return ""

    async def _query_vertex_rag_api(self, query_text: str, top_k: int) -> list[dict[str, Any]]:
        """Call Vertex AI RAG retrieveContexts REST API using ADC credentials."""
        import google.auth
        from google.auth.transport.requests import Request as AuthRequest

        credentials, detected_project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(AuthRequest())
        if not self.project_id and detected_project:
            self.project_id = detected_project

        corpus_name = await self._resolve_corpus_name(credentials.token)
        if not corpus_name:
            return []

        project_part = corpus_name.split("/")[1] if corpus_name.startswith("projects/") else self.project_id
        parent = f"projects/{project_part}/locations/{self.region}"
        url = f"https://{self.region}-aiplatform.googleapis.com/v1beta1/{parent}:retrieveContexts"

        payload = {
            "vertexRagStore": {
                "ragResources": [{"ragCorpus": corpus_name}],
            },
            "query": {
                "text": query_text[:2000],
                "similarityTopK": top_k,
            },
        }
        headers = {"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        contexts = data.get("contexts", {}).get("contexts", [])
        results: list[dict[str, Any]] = []
        for idx, ctx in enumerate(contexts[:top_k]):
            source_uri = ctx.get("sourceUri") or ctx.get("sourceDisplayName") or f"rag-context-{idx + 1}"
            title = source_uri.rsplit("/", 1)[-1]
            results.append(
                {
                    "title": title,
                    "source": source_uri,
                    "score": round(float(ctx.get("score", 0.85)), 4),
                    "text": (ctx.get("text") or "")[:600],
                    "backend": "vertex_rag",
                }
            )
        return results

    def _query_local_fallback(self, query_text: str, top_k: int) -> list[dict[str, Any]]:
        """Rank local policy documents by keyword overlap against the query."""
        policies = self._load_local_policies()
        query_tokens = _tokenize(query_text)
        scored: list[dict[str, Any]] = []

        for policy in policies:
            doc_tokens = _tokenize(f"{policy['title']} {policy['text']}")
            overlap = len(query_tokens & doc_tokens)
            score = round(min(0.99, 0.45 + overlap * 0.06), 4) if query_tokens else 0.75
            scored.append(
                {
                    "title": policy["title"],
                    "source": policy["source"],
                    "score": score,
                    "text": policy["text"][:600],
                    "backend": "local_fallback",
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    async def retrieve(self, query_text: str, top_k: int = 4) -> list[dict[str, Any]]:
        """Retrieve the top-k matching enterprise policy passages for an RFP query."""
        if self.corpus_name or self.corpus_display_name:
            try:
                results = await self._query_vertex_rag_api(query_text, top_k=top_k)
                if results:
                    return results
            except Exception as exc:
                logger.warning("Vertex RAG lookup failed (%s); falling back to local policy store.", exc)

        return self._query_local_fallback(query_text, top_k=top_k)
