"""Unit and API tests for mcp-pricing-server tools."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.server import app
from app.tools import _MEMORY_REPORTS, get_role_rates, submit_compliance_report


@pytest.fixture(autouse=True)
def _force_memory_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests never hit live GCP Firestore and start with clean state."""
    monkeypatch.setenv("FIRESTORE_ENABLED", "false")
    _MEMORY_REPORTS.clear()


def test_get_role_rates_exact_and_fuzzy_match() -> None:
    exact = get_role_rates("Cloud Architect")
    assert exact["matched_role"] == "Cloud Architect"
    assert exact["daily_rate_eur"] == 1450
    assert exact["currency"] == "EUR"

    fuzzy = get_role_rates("ai engineer")
    assert fuzzy["matched_role"] == "AI Engineer"
    assert fuzzy["daily_rate_eur"] == 1350

    partial = get_role_rates("Security")
    assert partial["matched_role"] == "Security Architect"


def test_get_role_rates_unknown_and_all() -> None:
    unknown = get_role_rates("Quantum Wizard")
    assert "Fallback" in unknown["matched_role"]
    assert unknown["daily_rate_eur"] > 0

    all_roles = get_role_rates("all")
    assert "catalog" in all_roles
    assert "Cloud Architect" in all_roles["catalog"]


def test_submit_compliance_report_status_classification() -> None:
    green = submit_compliance_report("GCP Migration RFP", 18, "Fully compliant with Cloud-First policy.")
    assert green["status"] == "GREEN"
    assert green["storage_backend"] == "memory"
    assert green["report_id"].startswith("rep-")

    yellow = submit_compliance_report("Hybrid Analytics RFP", 55, "Requires security waiver review.")
    assert yellow["status"] == "YELLOW"

    red = submit_compliance_report("Air-Gapped AGPL RFP", 92, "Blocked by on-prem and AGPL constraints.")
    assert red["status"] == "RED"
    assert len(_MEMORY_REPORTS) == 3


def test_submit_compliance_report_rejects_invalid_score() -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        submit_compliance_report("Invalid RFP", 150, "Score out of range.")

    with pytest.raises(ValueError, match="between 0 and 100"):
        submit_compliance_report("Invalid Bool", True, "Boolean should fail.")  # type: ignore[arg-type]


def test_http_endpoints() -> None:
    client = TestClient(app)

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    tools_resp = client.get("/api/tools")
    assert tools_resp.status_code == 200
    tool_names = {t["name"] for t in tools_resp.json()["tools"]}
    assert tool_names == {"get_role_rates", "submit_compliance_report"}

    rate_resp = client.post("/api/tools/get_role_rates", json={"role": "Data Engineer"})
    assert rate_resp.status_code == 200
    assert rate_resp.json()["daily_rate_eur"] == 1200

    report_resp = client.post(
        "/api/tools/submit_compliance_report",
        json={"rfp_title": "HTTP Test RFP", "risk_score": 25, "summary": "Low risk."},
    )
    assert report_resp.status_code == 200
    assert report_resp.json()["status"] == "GREEN"
