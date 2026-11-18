"""FastMCP + FastAPI HTTP/SSE server for pricing rates and compliance report persistence."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from app.tools import get_role_rates, submit_compliance_report

mcp = FastMCP("mcp-pricing-server")


@mcp.tool()
def tool_get_role_rates(role: str) -> dict[str, Any]:
    """Retrieve daily consulting rates (EUR) and current availability for a delivery role."""
    return get_role_rates(role)


@mcp.tool()
def tool_submit_compliance_report(rfp_title: str, risk_score: int, summary: str) -> dict[str, Any]:
    """Store a finalized RFP compliance risk assessment report in Firestore."""
    return submit_compliance_report(rfp_title=rfp_title, risk_score=risk_score, summary=summary)


class RoleRateRequest(BaseModel):
    role: str = Field(..., min_length=1, description="Consulting role name or 'all'")


class ComplianceReportRequest(BaseModel):
    rfp_title: str = Field(..., min_length=1, description="Title of the analyzed RFP")
    risk_score: int = Field(..., ge=0, le=100, description="Risk score from 0 to 100")
    summary: str = Field(..., min_length=1, description="Executive compliance summary")


def _build_mcp_subapp() -> Any:
    """Create ASGI sub-app for FastMCP across 2.x/3.x versions."""
    if hasattr(mcp, "http_app"):
        return mcp.http_app(path="/")
    if hasattr(mcp, "sse_app"):
        return mcp.sse_app()
    return None


mcp_subapp = _build_mcp_subapp()
app_lifespan = getattr(mcp_subapp, "lifespan", None)

app = FastAPI(
    title="MCP Pricing & Compliance Server",
    version="1.0.0",
    lifespan=app_lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness and readiness probe endpoint."""
    return {"status": "ok", "service": "mcp-pricing-server"}


@app.get("/api/tools")
def list_tools() -> dict[str, Any]:
    """Describe available MCP tools exposed by this service."""
    return {
        "server": "mcp-pricing-server",
        "tools": [
            {
                "name": "get_role_rates",
                "description": "Retrieve daily consulting rates (EUR) and availability for a role.",
                "parameters": {"role": "string"},
            },
            {
                "name": "submit_compliance_report",
                "description": "Persist an RFP compliance report in Firestore.",
                "parameters": {"rfp_title": "string", "risk_score": "integer (0-100)", "summary": "string"},
            },
        ],
    }


@app.post("/api/tools/get_role_rates")
def invoke_get_role_rates(payload: RoleRateRequest) -> dict[str, Any]:
    """HTTP tool invocation endpoint for get_role_rates."""
    try:
        return get_role_rates(payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tools/submit_compliance_report")
def invoke_submit_compliance_report(payload: ComplianceReportRequest) -> dict[str, Any]:
    """HTTP tool invocation endpoint for submit_compliance_report."""
    try:
        return submit_compliance_report(
            rfp_title=payload.rfp_title,
            risk_score=payload.risk_score,
            summary=payload.summary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if mcp_subapp is not None:
    app.mount("/mcp", mcp_subapp)
