"""Domain tools for role pricing lookup and compliance report persistence."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

ROLE_CATALOG: dict[str, dict[str, Any]] = {
    "Cloud Architect": {
        "daily_rate_eur": 1450,
        "currency": "EUR",
        "availability": "Available",
        "available_fte": 1.5,
        "lead_time_weeks": 2,
        "seniority": "Principal",
    },
    "AI Engineer": {
        "daily_rate_eur": 1350,
        "currency": "EUR",
        "availability": "Limited",
        "available_fte": 1.0,
        "lead_time_weeks": 3,
        "seniority": "Senior",
    },
    "Security Architect": {
        "daily_rate_eur": 1500,
        "currency": "EUR",
        "availability": "Available",
        "available_fte": 1.0,
        "lead_time_weeks": 2,
        "seniority": "Principal",
    },
    "Data Engineer": {
        "daily_rate_eur": 1200,
        "currency": "EUR",
        "availability": "Available",
        "available_fte": 2.0,
        "lead_time_weeks": 1,
        "seniority": "Senior",
    },
    "Project Manager": {
        "daily_rate_eur": 1250,
        "currency": "EUR",
        "availability": "Available",
        "available_fte": 1.5,
        "lead_time_weeks": 1,
        "seniority": "Senior",
    },
    "DevSecOps Engineer": {
        "daily_rate_eur": 1300,
        "currency": "EUR",
        "availability": "Limited",
        "available_fte": 0.5,
        "lead_time_weeks": 4,
        "seniority": "Senior",
    },
}

DEFAULT_ROLE_FALLBACK: dict[str, Any] = {
    "daily_rate_eur": 1280,
    "currency": "EUR",
    "availability": "On Request",
    "available_fte": 0.5,
    "lead_time_weeks": 4,
    "seniority": "Senior",
}

_MEMORY_REPORTS: dict[str, dict[str, Any]] = {}


def _match_role_entry(role_query: str) -> tuple[str, dict[str, Any]]:
    """Find best matching role in ROLE_CATALOG using exact or token overlap matching."""
    normalized = role_query.strip().lower()
    for catalog_role, details in ROLE_CATALOG.items():
        if catalog_role.lower() == normalized:
            return catalog_role, details

    for catalog_role, details in ROLE_CATALOG.items():
        role_lower = catalog_role.lower()
        if normalized in role_lower or role_lower in normalized:
            return catalog_role, details

    query_tokens = set(normalized.split())
    best_match: tuple[int, str, dict[str, Any]] | None = None
    for catalog_role, details in ROLE_CATALOG.items():
        overlap = len(query_tokens & set(catalog_role.lower().split()))
        if overlap > 0 and (best_match is None or overlap > best_match[0]):
            best_match = (overlap, catalog_role, details)

    if best_match is not None:
        return best_match[1], best_match[2]

    return "General Enterprise Consultant (Fallback)", DEFAULT_ROLE_FALLBACK


def get_role_rates(role: str) -> dict[str, Any]:
    """Return daily consulting rates and team availability for a requested role.

    Pass ``role="all"`` to retrieve the default summary plus the full catalog.
    """
    cleaned = role.strip()
    if not cleaned:
        raise ValueError("role must not be empty")

    if cleaned.lower() == "all":
        return {
            "role": cleaned,
            "matched_role": "All Roles",
            **ROLE_CATALOG["Cloud Architect"],
            "catalog": ROLE_CATALOG,
        }

    matched_role, details = _match_role_entry(cleaned)
    return {
        "role": cleaned,
        "matched_role": matched_role,
        **details,
    }


def _classify_risk(risk_score: int) -> str:
    """Map numeric risk score (0-100) to GREEN, YELLOW, or RED traffic-light status."""
    if risk_score < 40:
        return "GREEN"
    if risk_score < 70:
        return "YELLOW"
    return "RED"


def _persist_to_firestore(report: dict[str, Any]) -> bool:
    """Attempt to store compliance report in Firestore if enabled and configured."""
    flag = os.getenv("FIRESTORE_ENABLED", "auto").strip().lower()
    if flag in {"false", "0", "no", "off"}:
        return False

    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    database_id = os.getenv("FIRESTORE_DATABASE", "(default)")
    collection_name = os.getenv("FIRESTORE_COLLECTION", "compliance_reports")

    if flag == "auto" and not project_id:
        return False

    try:
        from google.cloud import firestore  # lazy import keeps unit tests fast

        client = firestore.Client(project=project_id, database=database_id)
        client.collection(collection_name).document(report["report_id"]).set(report)
        return True
    except Exception as exc:
        if flag in {"true", "1", "yes", "on"}:
            logger.warning("Firestore persistence failed (%s); falling back to memory.", exc)
        return False


def submit_compliance_report(rfp_title: str, risk_score: int, summary: str) -> dict[str, Any]:
    """Persist an RFP compliance assessment report in Firestore (or in-memory fallback)."""
    title = rfp_title.strip()
    if not title:
        raise ValueError("rfp_title must not be empty")
    if not isinstance(risk_score, int) or isinstance(risk_score, bool) or not 0 <= risk_score <= 100:
        raise ValueError("risk_score must be an integer between 0 and 100")

    cleaned_summary = summary.strip()
    if not cleaned_summary:
        raise ValueError("summary must not be empty")

    report_id = f"rep-{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()
    status = _classify_risk(risk_score)

    document = {
        "report_id": report_id,
        "rfp_title": title,
        "risk_score": risk_score,
        "status": status,
        "summary": cleaned_summary,
        "created_at": created_at,
    }

    stored_in_firestore = _persist_to_firestore(document)
    backend = "firestore" if stored_in_firestore else "memory"
    if not stored_in_firestore:
        _MEMORY_REPORTS[report_id] = dict(document)

    return {
        **document,
        "storage_backend": backend,
    }


def list_memory_reports() -> list[dict[str, Any]]:
    """Return compliance reports held in the local in-memory store (useful for tests/debugging)."""
    return list(_MEMORY_REPORTS.values())
