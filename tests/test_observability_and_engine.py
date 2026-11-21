"""Unit tests for observability.trace_span and GeminiCostArbiterEngine uncovered branches."""

from __future__ import annotations

import io
import json
import sys
from unittest.mock import MagicMock

import pytest

from gemini_cost_arbiter import observability
from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.engine import GeminiCostArbiterEngine
from gemini_cost_arbiter.models.telemetry import (
    CloudResourceType,
    CloudTelemetry,
    EBSMetrics,
    EC2Metrics,
    EIPMetrics,
    RDSMetrics,
    S3Metrics,
)


def test_trace_span_with_and_without_tracer(monkeypatch: pytest.MonkeyPatch) -> None:
    """trace_span must set attributes when TRACER is active and yield cleanly when TRACER is None."""
    mock_span = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_span
    mock_cm.__exit__.return_value = False
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value = mock_cm

    monkeypatch.setattr(observability, "TRACER", mock_tracer)
    with observability.trace_span("test_op", {"resource_id": "i-123", "count": 2}):
        pass
    mock_tracer.start_as_current_span.assert_called_once_with("test_op")
    mock_span.set_attribute.assert_any_call("resource_id", "i-123")
    mock_span.set_attribute.assert_any_call("count", "2")

    monkeypatch.setattr(observability, "TRACER", None)
    entered = False
    with observability.trace_span("noop_op"):
        entered = True
    assert entered is True


@pytest.mark.asyncio
async def test_engine_helpers_coercion_and_mcp_edge_branches(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    """Cover _coerce_to_batch list[CloudTelemetry], lifecycle helpers, and MCP edge methods."""
    engine = GeminiCostArbiterEngine(config=ArbiterConfig(db_path=str(tmp_path / "engine_cov.db")))

    # Lifecycle & properties
    client = await engine.get_http_client()
    assert client is not None
    assert engine.audit_ledger == []
    engine.reset_audit_ledger()

    # Coerce list[CloudTelemetry] covering all 5 resource types
    items = [
        CloudTelemetry(
            resource_id="i-ec2-1",
            resource_type=CloudResourceType.EC2,
            monthly_cost_usd=100.0,
            ec2_metrics=EC2Metrics(resource_id="i-ec2-1", monthly_spend_usd=100.0),
        ),
        CloudTelemetry(
            resource_id="rds-1",
            resource_type=CloudResourceType.RDS,
            monthly_cost_usd=200.0,
            rds_metrics=RDSMetrics(resource_id="rds-1", monthly_spend_usd=200.0),
        ),
        CloudTelemetry(
            resource_id="s3-1",
            resource_type=CloudResourceType.S3,
            monthly_cost_usd=50.0,
            s3_metrics=S3Metrics(resource_id="s3-1", monthly_spend_usd=50.0),
        ),
        CloudTelemetry(
            resource_id="vol-1",
            resource_type=CloudResourceType.EBS,
            monthly_cost_usd=10.0,
            ebs_metrics=EBSMetrics(resource_id="vol-1", monthly_spend_usd=10.0),
        ),
        CloudTelemetry(
            resource_id="eipalloc-1",
            resource_type=CloudResourceType.EIP,
            monthly_cost_usd=3.6,
            eip_metrics=EIPMetrics(resource_id="eipalloc-1", monthly_spend_usd=3.6),
        ),
    ]
    batch = engine._coerce_to_batch(items)
    assert batch.total_resource_count == 5

    # Unknown telemetry type returns empty batch -> nominal efficiency boundaries
    empty_summary = await engine.analyze_infrastructure_waste("unexpected-type")
    assert empty_summary.total_resources_evaluated == 0
    assert "nominal efficiency boundaries" in empty_summary.key_findings[0]

    # MCP edge methods: notifications/initialized, ping, unknown method, unknown tool
    assert await engine.handle_mcp_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    ping_resp = await engine.handle_mcp_message({"jsonrpc": "2.0", "id": 10, "method": "ping"})
    assert ping_resp == {"jsonrpc": "2.0", "id": 10, "result": {}}

    unknown_method = await engine.handle_mcp_message({"jsonrpc": "2.0", "id": 11, "method": "foo/bar"})
    assert unknown_method is not None and unknown_method["error"]["code"] == -32601

    unknown_tool = await engine.handle_mcp_message(
        {"jsonrpc": "2.0", "id": 12, "method": "tools/call", "params": {"name": "nonexistent_tool", "arguments": {}}}
    )
    assert unknown_tool is not None and unknown_tool["error"]["code"] == -32601

    # Stdio server loop: blank line, bad JSON (-32700), ping, EOF
    fake_stdin = io.StringIO("\nnot-json\n" + json.dumps({"jsonrpc": "2.0", "id": 99, "method": "ping"}) + "\n")
    fake_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    await engine.run_stdio_server()
    lines = [json.loads(line) for line in fake_stdout.getvalue().strip().splitlines()]
    assert lines[0]["error"]["code"] == -32700
    assert lines[1] == {"jsonrpc": "2.0", "id": 99, "result": {}}
