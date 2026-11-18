"""OpenTelemetry instrumentation for Cloud Trace export and live UI JSON step streaming."""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)

# Pricing in USD per 1M tokens (approximate list rates for telemetry UI estimation)
MODEL_PRICING_PER_1M: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
}

_TRACER_INITIALIZED = False


def configure_tracer(service_name: str = "agent-core") -> trace.Tracer:
    """Initialize global OpenTelemetry TracerProvider with optional GCP Cloud Trace exporter."""
    global _TRACER_INITIALIZED
    if not _TRACER_INITIALIZED:
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        enable_cloud_trace = os.getenv("ENABLE_CLOUD_TRACE", "false").strip().lower() in {"true", "1", "yes"}
        project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        if enable_cloud_trace and project_id:
            try:
                from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

                exporter = CloudTraceSpanExporter(project_id=project_id)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                logger.info("Cloud Trace exporter enabled for project %s", project_id)
            except Exception as exc:
                logger.warning("Could not initialize Cloud Trace exporter (%s); continuing locally.", exc)

        trace.set_tracer_provider(provider)
        _TRACER_INITIALIZED = True

    return trace.get_tracer(service_name)


def estimate_token_cost_usd(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate token cost in USD for supported Gemini 2.5 models."""
    rates = MODEL_PRICING_PER_1M.get(model_name, MODEL_PRICING_PER_1M["gemini-2.5-flash"])
    cost = (max(0, input_tokens) / 1_000_000) * rates["input"] + (max(0, output_tokens) / 1_000_000) * rates["output"]
    return round(cost, 6)


@dataclass
class TraceSession:
    """Tracks OpenTelemetry spans, latencies, and token usage for a single RFP analysis run."""

    model_name: str
    tracer: trace.Tracer = field(default_factory=configure_tracer)
    trace_id: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    @contextmanager
    def record_step(
        self,
        step_type: str,
        label: str,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Execute a block inside an OpenTelemetry span and capture structured step telemetry."""
        start = time.perf_counter()
        step_data: dict[str, Any] = {
            "step_type": step_type,
            "label": label,
            "status": "ok",
            "details": dict(attributes or {}),
        }

        with self.tracer.start_as_current_span(f"agent.{step_type}") as span:
            span_ctx = span.get_span_context()
            trace_hex = f"{span_ctx.trace_id:032x}" if span_ctx.trace_id else ""
            span_hex = f"{span_ctx.span_id:016x}" if span_ctx.span_id else ""
            if not self.trace_id and trace_hex:
                self.trace_id = trace_hex

            for key, value in (attributes or {}).items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"agent.{key}", value)

            try:
                yield step_data
                span.set_status(Status(StatusCode.OK))
            except Exception as exc:
                step_data["status"] = "error"
                step_data["error"] = str(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            finally:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                span.set_attribute("agent.latency_ms", elapsed_ms)
                step_data["trace_id"] = trace_hex
                step_data["span_id"] = span_hex
                step_data["latency_ms"] = elapsed_ms
                self.steps.append(step_data)

    def add_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Accumulate LLM input/output token counts for cost calculation."""
        self.input_tokens += max(0, int(input_tokens))
        self.output_tokens += max(0, int(output_tokens))

    def token_summary(self) -> dict[str, Any]:
        """Return token usage totals and estimated USD cost."""
        total = self.input_tokens + self.output_tokens
        return {
            "model": self.model_name,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": total,
            "estimated_cost_usd": estimate_token_cost_usd(
                self.model_name,
                self.input_tokens,
                self.output_tokens,
            ),
        }
