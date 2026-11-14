"""OpenTelemetry distributed tracing instrumentation helper for FinOps operations."""

from __future__ import annotations

import contextlib
from typing import Any, Dict, Generator, Optional

try:
    from opentelemetry import trace

    TRACER: Optional[trace.Tracer] = trace.get_tracer("gemini-cost-arbiter-mcp", "1.0.0")
except ImportError:
    TRACER = None


@contextlib.contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[None, None, None]:
    """Context manager wrapping execution block in an OpenTelemetry trace span."""
    if TRACER is None:
        yield
        return

    with TRACER.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        yield
