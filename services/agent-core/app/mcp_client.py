"""HTTP client for mcp-pricing-server with Cloud Run OIDC Identity Token support."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class McpPricingClient:
    """Async client calling mcp-pricing-server endpoints with optional GCP ID token auth."""

    def __init__(self, base_url: str | None = None, use_id_token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("MCP_PRICING_SERVER_URL", "http://localhost:8081")).rstrip("/")
        self.use_id_token_mode = (use_id_token or os.getenv("MCP_USE_ID_TOKEN", "auto")).strip().lower()

    def _should_fetch_id_token(self) -> bool:
        if self.use_id_token_mode in {"true", "1", "yes"}:
            return True
        if self.use_id_token_mode in {"false", "0", "no"}:
            return False
        return self.base_url.startswith("https://") and "localhost" not in self.base_url

    def _build_auth_headers(self) -> dict[str, str]:
        if not self._should_fetch_id_token():
            return {}
        try:
            from google.auth.transport.requests import Request as AuthRequest
            from google.oauth2 import id_token

            token = id_token.fetch_id_token(AuthRequest(), self.base_url)
            return {"Authorization": f"Bearer {token}"}
        except Exception as exc:
            logger.warning("Could not fetch GCP ID token for audience %s (%s)", self.base_url, exc)
            return {}

    async def get_role_rates(self, role: str) -> dict[str, Any]:
        """Invoke get_role_rates tool on mcp-pricing-server."""
        headers = self._build_auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/api/tools/get_role_rates",
                json={"role": role},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def submit_compliance_report(self, rfp_title: str, risk_score: int, summary: str) -> dict[str, Any]:
        """Invoke submit_compliance_report tool on mcp-pricing-server."""
        headers = self._build_auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/api/tools/submit_compliance_report",
                json={"rfp_title": rfp_title, "risk_score": risk_score, "summary": summary},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
