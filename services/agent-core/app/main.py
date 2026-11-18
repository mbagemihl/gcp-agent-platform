"""FastAPI HTTP and NDJSON streaming API for agent-core."""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent import EnterpriseRfpAgent

app = FastAPI(title="Enterprise Agent Core", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = EnterpriseRfpAgent()


class AnalyzeRequest(BaseModel):
    rfp_title: str = Field(..., min_length=1, description="Title of the RFP")
    rfp_text: str = Field(..., min_length=1, description="Full RFP content to analyze")
    user_query: str = Field(
        default="Bewerte Machbarkeit, Compliance-Risiken und benötigte Tagessätze.",
        min_length=1,
    )
    model_name: str = Field(default="gemini-2.5-flash")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness and readiness probe endpoint."""
    return {"status": "ok", "service": "agent-core"}


@app.post("/api/analyze")
async def analyze_rfp(payload: AnalyzeRequest) -> dict:
    """Run RFP analysis and return the complete structured JSON payload."""
    try:
        return await agent.analyze_rfp(
            rfp_title=payload.rfp_title,
            rfp_text=payload.rfp_text,
            user_query=payload.user_query,
            model_name=payload.model_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}") from exc


@app.post("/api/analyze/stream")
async def analyze_rfp_stream(payload: AnalyzeRequest) -> StreamingResponse:
    """Stream real-time OpenTelemetry steps and final result as NDJSON lines."""

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in agent.analyze_rfp_stream(
                rfp_title=payload.rfp_title,
                rfp_text=payload.rfp_text,
                user_query=payload.user_query,
                model_name=payload.model_name,
            ):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "error", "detail": str(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
