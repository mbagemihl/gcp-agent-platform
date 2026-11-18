"""Enterprise RFP Compliance & Pricing Agent orchestrated with Vertex AI Gemini & OpenTelemetry."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, AsyncIterator

from app.mcp_client import McpPricingClient
from app.prompts import SYSTEM_INSTRUCTION, build_analysis_prompt, evaluate_policy_risk
from app.rag_retriever import VertexRagRetriever
from app.telemetry import TraceSession

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = ("gemini-2.5-flash", "gemini-2.5-pro")


class EnterpriseRfpAgent:
    """Coordinates RAG policy retrieval, MCP tool calls, Gemini reasoning, and OpenTelemetry tracing."""

    def __init__(
        self,
        rag_retriever: VertexRagRetriever | None = None,
        mcp_client: McpPricingClient | None = None,
        project_id: str | None = None,
        region: str | None = None,
    ) -> None:
        self.rag_retriever = rag_retriever or VertexRagRetriever()
        self.mcp_client = mcp_client or McpPricingClient()
        self.project_id = (project_id or os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT", "")).strip()
        self.region = (region or os.getenv("GCP_REGION", "europe-west3")).strip()

    def _call_vertex_gemini(self, model_name: str, prompt: str) -> tuple[str, int, int, str]:
        """Call Vertex AI Gemini via google-genai SDK or fall back to deterministic local synthesis."""
        use_vertex = os.getenv("VERTEX_LLM_ENABLED", "auto").strip().lower()
        if use_vertex not in {"false", "0", "no"} and self.project_id:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(vertexai=True, project=self.project_id, location=self.region)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.2,
                    ),
                )
                text = (response.text or "").strip()
                usage = getattr(response, "usage_metadata", None)
                in_tokens = int(getattr(usage, "prompt_token_count", 0) or max(1, len(prompt) // 4))
                out_tokens = int(getattr(usage, "candidates_token_count", 0) or max(1, len(text) // 4))
                if text:
                    return text, in_tokens, out_tokens, "vertex_ai"
            except Exception as exc:
                logger.warning("Vertex AI Gemini call failed (%s); using local synthesis fallback.", exc)

        approx_in = max(120, len(prompt) // 4)
        return "", approx_in, 0, "local_fallback"

    @staticmethod
    def _build_local_fallback_response(
        rfp_title: str,
        user_query: str,
        rag_sources: list[dict[str, Any]],
        role_rates: list[dict[str, Any]],
        risk_assessment: dict[str, Any],
    ) -> str:
        """Produce structured German compliance evaluation when Vertex AI credentials are absent locally."""
        status = risk_assessment["status"]
        score = risk_assessment["risk_score"]
        blockers = risk_assessment["blockers"]
        warnings = risk_assessment["warnings"]

        verdict_map = {
            "GREEN": "GO – Machbar & vollständig richtlinienkonform",
            "YELLOW": "CONDITIONAL GO – Klärung / Security- oder Commercial-Waiver nötig",
            "RED": "NO-GO / BLOCKER – Verstößt gegen zwingende Enterprise-Richtlinien",
        }
        verdict = verdict_map.get(status, "REVIEW")

        blocker_lines = (
            "\n".join(f"- **{b['rule_id']}**: {b['description']} *(Treffer: {', '.join(b['matched_terms'])})*" for b in blockers)
            or "- Keine harten Blocker erkannt."
        )
        warning_lines = (
            "\n".join(f"- **{w['rule_id']}**: {w['description']}" for w in warnings)
            or "- Keine zusätzlichen Warnungen."
        )
        rate_lines = "\n".join(
            f"- **{r['matched_role']}**: {r['daily_rate_eur']} EUR/Tag · Verfügbarkeit: `{r['availability']}` "
            f"({r['available_fte']} FTE, Vorlauf: {r['lead_time_weeks']} Wochen)"
            for r in role_rates
        )
        source_lines = "\n".join(
            f"- `{s['title']}` (Relevanz: {s['score']:.2f}, Quelle: `{s['backend']}`)"
            for s in rag_sources
        )
        avg_rate = round(sum(r["daily_rate_eur"] for r in role_rates) / max(1, len(role_rates)))

        return (
            f"## RFP-Bewertung: {rfp_title}\n\n"
            f"**Empfehlung:** `{status}` – **{verdict}** (Risiko-Score: **{score}/100**)\n\n"
            f"**Anfrage:** {user_query}\n\n"
            f"### 1. Policy- & Compliance-Prüfung (Vertex AI RAG)\n"
            f"**Erkannte Blocker:**\n{blocker_lines}\n\n"
            f"**Hinweise / Warnungen:**\n{warning_lines}\n\n"
            f"**Herangezogene Richtlinien:**\n{source_lines}\n\n"
            f"### 2. Team- & Tagessatz-Kalkulation (MCP Pricing Server)\n"
            f"{rate_lines}\n\n"
            f"- **Durchschnittlicher Team-Tagessatz:** ~{avg_rate} EUR/Tag\n\n"
            f"### 3. Nächste Schritte\n"
            + (
                "- Angebotserstellung starten und identifizierte Lieferrollen im Ressourcen-Pool reservieren."
                if status == "GREEN"
                else "- Vor Angebotsabgabe zwingende Eskalation an Architecture Board / Legal / CISO durchführen."
            )
        )

    async def analyze_rfp_stream(
        self,
        rfp_title: str,
        rfp_text: str,
        user_query: str = "Bewerte Machbarkeit, Compliance-Risiken und benötigte Tagessätze.",
        model_name: str = "gemini-2.5-flash",
    ) -> AsyncIterator[dict[str, Any]]:
        """Run end-to-end RFP evaluation and yield live OpenTelemetry step events."""
        chosen_model = model_name if model_name in SUPPORTED_MODELS else "gemini-2.5-flash"
        session = TraceSession(model_name=chosen_model)
        mcp_calls: list[dict[str, Any]] = []

        # Step 1: Vertex AI RAG Policy Retrieval
        with session.record_step("rag_retrieval", "Vertex AI RAG: Enterprise Policies abrufen", {"top_k": 4}) as step:
            rag_sources = await self.rag_retriever.retrieve(f"{rfp_title}\n{rfp_text}\n{user_query}", top_k=4)
            step["details"]["sources_count"] = len(rag_sources)
            step["details"]["backend"] = rag_sources[0]["backend"] if rag_sources else "none"
            step["output"] = rag_sources
        yield {"type": "step_completed", "step": step}

        # Step 2: Deterministic Policy Risk Pre-Check
        with session.record_step("policy_risk_check", "Compliance- & Blocker-Regelprüfung") as step:
            risk_assessment = evaluate_policy_risk(rfp_text, rag_sources)
            step["details"]["risk_score"] = risk_assessment["risk_score"]
            step["details"]["status"] = risk_assessment["status"]
            step["output"] = risk_assessment
        yield {"type": "step_completed", "step": step}

        # Step 3: MCP Tool Calls - get_role_rates for required roles
        role_rates: list[dict[str, Any]] = []
        for role in risk_assessment["required_roles"]:
            req_payload = {"role": role}
            with session.record_step("mcp_tool_call", f"MCP Tool: get_role_rates({role})", {"tool": "get_role_rates"}) as step:
                rate_result = await self.mcp_client.get_role_rates(role)
                role_rates.append(rate_result)
                call_record = {
                    "tool": "get_role_rates",
                    "request": req_payload,
                    "response": rate_result,
                }
                mcp_calls.append(call_record)
                step["output"] = call_record
            yield {"type": "step_completed", "step": step}

        # Step 4: LLM Synthesis via Vertex AI Gemini
        prompt = build_analysis_prompt(
            rfp_title=rfp_title,
            rfp_text=rfp_text,
            user_query=user_query,
            rag_contexts=rag_sources,
            role_rates=role_rates,
            risk_assessment=risk_assessment,
        )
        with session.record_step("llm_generation", f"Vertex AI LLM: {chosen_model}", {"model": chosen_model}) as step:
            llm_text, in_tok, out_tok, llm_backend = await asyncio.to_thread(
                self._call_vertex_gemini,
                chosen_model,
                prompt,
            )
            if not llm_text:
                llm_text = self._build_local_fallback_response(
                    rfp_title=rfp_title,
                    user_query=user_query,
                    rag_sources=rag_sources,
                    role_rates=role_rates,
                    risk_assessment=risk_assessment,
                )
                out_tok = max(80, len(llm_text) // 4)

            session.add_tokens(in_tok, out_tok)
            step["details"]["backend"] = llm_backend
            step["details"]["input_tokens"] = in_tok
            step["details"]["output_tokens"] = out_tok
            step["output"] = {"backend": llm_backend, "preview": llm_text[:240]}
        yield {"type": "step_completed", "step": step}

        # Step 5: MCP Tool Call - Persist Compliance Report in Firestore
        summary_excerpt = llm_text.splitlines()[0] if llm_text else f"{risk_assessment['status']} ({risk_assessment['risk_score']}/100)"
        report_req = {
            "rfp_title": rfp_title,
            "risk_score": risk_assessment["risk_score"],
            "summary": summary_excerpt[:400],
        }
        with session.record_step(
            "mcp_tool_call",
            "MCP Tool: submit_compliance_report",
            {"tool": "submit_compliance_report"},
        ) as step:
            report_res = await self.mcp_client.submit_compliance_report(
                rfp_title=report_req["rfp_title"],
                risk_score=report_req["risk_score"],
                summary=report_req["summary"],
            )
            call_record = {
                "tool": "submit_compliance_report",
                "request": report_req,
                "response": report_res,
            }
            mcp_calls.append(call_record)
            step["output"] = call_record
        yield {"type": "step_completed", "step": step}

        yield {
            "type": "final_result",
            "rfp_title": rfp_title,
            "model": chosen_model,
            "trace_id": session.trace_id,
            "risk_score": risk_assessment["risk_score"],
            "status": risk_assessment["status"],
            "blockers": risk_assessment["blockers"],
            "warnings": risk_assessment["warnings"],
            "response_markdown": llm_text,
            "rag_sources": rag_sources,
            "mcp_calls": mcp_calls,
            "steps": session.steps,
            "token_usage": session.token_summary(),
        }

    async def analyze_rfp(
        self,
        rfp_title: str,
        rfp_text: str,
        user_query: str = "Bewerte Machbarkeit, Compliance-Risiken und benötigte Tagessätze.",
        model_name: str = "gemini-2.5-flash",
    ) -> dict[str, Any]:
        """Collect all streamed events and return the final consolidated analysis dictionary."""
        final_payload: dict[str, Any] = {}
        async for event in self.analyze_rfp_stream(
            rfp_title=rfp_title,
            rfp_text=rfp_text,
            user_query=user_query,
            model_name=model_name,
        ):
            if event.get("type") == "final_result":
                final_payload = event
        return final_payload
