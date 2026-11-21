"""OpenTelemetry distributed tracing instrumentation helper for FinOps operations."""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from typing import Any

try:
    from opentelemetry import trace

    TRACER: trace.Tracer | None = trace.get_tracer("gemini-cost-arbiter-mcp", "1.0.0")
except ImportError:
    TRACER = None


@contextlib.contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Generator[None]:
    """Context manager wrapping execution block in an OpenTelemetry trace span."""
    if TRACER is None:
        yield
        return

    with TRACER.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        yield
