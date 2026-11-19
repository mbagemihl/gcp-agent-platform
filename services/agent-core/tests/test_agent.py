"""Unit and API tests for agent-core prompt logic, telemetry, RAG fallback, and pipeline."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent import EnterpriseRfpAgent, resolve_model_name
from app.main import app
from app.prompts import build_analysis_prompt, evaluate_policy_risk
from app.rag_retriever import VertexRagRetriever
from app.telemetry import TraceSession, estimate_token_cost_usd


class FakeMcpClient:
    """In-memory mock of McpPricingClient for isolated agent unit tests."""

    async def get_role_rates(self, role: str) -> dict[str, Any]:
        return {
            "role": role,
            "matched_role": role,
            "daily_rate_eur": 1400,
            "currency": "EUR",
            "availability": "Available",
            "available_fte": 1.5,
            "lead_time_weeks": 2,
            "seniority": "Senior",
        }

    async def submit_compliance_report(self, rfp_title: str, risk_score: int, summary: str) -> dict[str, Any]:
        status = "GREEN" if risk_score < 40 else ("YELLOW" if risk_score < 70 else "RED")
        return {
            "report_id": "rep-test123",
            "rfp_title": rfp_title,
            "risk_score": risk_score,
            "status": status,
            "summary": summary,
            "storage_backend": "memory",
        }


def test_evaluate_policy_risk_green_vs_red() -> None:
    green_rfp = (
        "Wir suchen einen Partner für eine Google Cloud Platform (GCP) Migration mit Cloud Run, "
        "Vertex AI, ISO 27001 und Apache-2.0 Open-Source-Komponenten in europe-west3."
    )
    green_res = evaluate_policy_risk(green_rfp)
    assert green_res["status"] == "GREEN"
    assert green_res["risk_score"] < 40
    assert green_res["blockers"] == []
    assert "Cloud Architect" in green_res["required_roles"]

    red_rfp = (
        "Das System muss strictly on-prem / air-gapped betrieben werden (kein Cloud-Zugriff). "
        "Zudem wird eine Auslieferung unter AGPL-3.0 sowie unbegrenzte Haftung gefordert."
    )
    red_res = evaluate_policy_risk(red_rfp)
    assert red_res["status"] == "RED"
    assert red_res["risk_score"] >= 70
    blocker_ids = {b["rule_id"] for b in red_res["blockers"]}
    assert blocker_ids == {"CLOUD_FIRST_AIRGAP", "OSS_VIRAL_LICENSE", "UNLIMITED_LIABILITY"}


def test_build_analysis_prompt_includes_rag_and_rates() -> None:
    prompt = build_analysis_prompt(
        rfp_title="Smart Analytics GCP",
        rfp_text="Build a Vertex AI pipeline on GCP.",
        user_query="Check risk and rates.",
        rag_contexts=[{"title": "cloud.md", "score": 0.91, "text": "Cloud-first on GCP."}],
        role_rates=[
            {
                "matched_role": "AI Engineer",
                "daily_rate_eur": 1350,
                "availability": "Limited",
                "available_fte": 1.0,
                "lead_time_weeks": 3,
            }
        ],
    )
    assert "Smart Analytics GCP" in prompt
    assert "cloud.md" in prompt
    assert "1350 EUR/day" in prompt


def test_trace_session_and_cost_estimation() -> None:
    session = TraceSession(model_name="gemini-2.5-flash")
    with session.record_step("rag_retrieval", "Fetch Policies", {"top_k": 4}) as step:
        step["output"] = ["p1"]
    session.add_tokens(1000, 500)

    assert len(session.steps) == 1
    assert session.steps[0]["trace_id"]
    assert session.steps[0]["latency_ms"] >= 0
    summary = session.token_summary()
    assert summary["total_tokens"] == 1500
    assert summary["estimated_cost_usd"] == estimate_token_cost_usd("gemini-2.5-flash", 1000, 500)


def test_rag_retriever_and_full_agent_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERTEX_LLM_ENABLED", "false")
    retriever = VertexRagRetriever(corpus_name="")
    policies = asyncio.run(retriever.retrieve("AGPL licensing and GCP Cloud Run", top_k=3))
    assert len(policies) == 3
    assert all(p["backend"] == "local_fallback" for p in policies)

    test_agent = EnterpriseRfpAgent(rag_retriever=retriever, mcp_client=FakeMcpClient())  # type: ignore[arg-type]
    result = asyncio.run(
        test_agent.analyze_rfp(
            rfp_title="Test Cloud Run RFP",
            rfp_text="GCP Cloud Run + Vertex AI RAG Platform with Apache-2.0.",
            user_query="Ist das Projekt machbar?",
            model_name="gemini-2.5-flash",
        )
    )
    assert result["model"] == "gemini-3.8-flash"
    assert resolve_model_name("gemini-2.5-pro") == "gemini-3.1-pro-preview"
    assert resolve_model_name("gemini-3.8-flash") == "gemini-3.8-flash"
    assert result["status"] == "GREEN"
    assert result["risk_score"] < 40
    assert len(result["steps"]) >= 4
    trace_ids = {step["trace_id"] for step in result["steps"]}
    assert trace_ids == {result["trace_id"]}
    assert any(call["tool"] == "submit_compliance_report" for call in result["mcp_calls"])
    assert result["token_usage"]["total_tokens"] > 0


def test_fastapi_endpoints_with_mocked_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    monkeypatch.setenv("VERTEX_LLM_ENABLED", "false")
    monkeypatch.setattr(
        main_module,
        "agent",
        EnterpriseRfpAgent(rag_retriever=VertexRagRetriever(corpus_name=""), mcp_client=FakeMcpClient()),  # type: ignore[arg-type]
    )

    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"

    resp = client.post(
        "/api/analyze",
        json={
            "rfp_title": "Red Blocker RFP",
            "rfp_text": "Strict on-prem only deployment with AGPL and unlimited liability.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RED"
    assert data["risk_score"] >= 70


def test_rag_retriever_display_name_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERTEX_RAG_CORPUS", "")
    monkeypatch.setenv("VERTEX_RAG_CORPUS_DISPLAY_NAME", "enterprise-agent-policies")
    monkeypatch.setenv("VERTEX_RAG_REGION", "europe-west3")
    monkeypatch.setenv("GCP_PROJECT_ID", "gcp-agent-platform-2026")

    retriever = VertexRagRetriever()
    assert retriever.corpus_display_name == "enterprise-agent-policies"
    assert retriever.region == "europe-west3"

    async def _fail_api(_query: str, top_k: int) -> list[dict[str, Any]]:
        raise RuntimeError("offline in unit test")

    monkeypatch.setattr(retriever, "_query_vertex_rag_api", _fail_api)
    results = asyncio.run(retriever.retrieve("GCP Cloud Run", top_k=2))
    assert len(results) == 2
    assert all(item["backend"] == "local_fallback" for item in results)
