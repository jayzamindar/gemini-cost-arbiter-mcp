"""Tests for LLM quota/cost/cooldown circuit breakers, 30s timeouts, retries, and JSON extraction."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.engine import GeminiCostArbiterEngine
from gemini_cost_arbiter.models.telemetry import EC2Metrics, TelemetryBatch
from gemini_cost_arbiter.reasoner.circuit_breaker import LLMQuotaCircuitBreaker, extract_json
from gemini_cost_arbiter.reasoner.client import GeminiReasonerClient
from gemini_cost_arbiter.reasoner.openrouter import OpenRouterFallbackClient


def _sample_batch() -> TelemetryBatch:
    return TelemetryBatch(
        ec2_instances=[
            EC2Metrics(
                resource_id="i-cb-test",
                current_instance_type="m5.xlarge",
                cpu_utilization_avg_pct=4.5,
                memory_utilization_avg_pct=15.0,
                monthly_spend_usd=200.0,
            )
        ]
    )


def test_config_and_timeout_defaults() -> None:
    """Verify REM-011 ArbiterConfig defaults and 30s client timeouts."""
    config = ArbiterConfig(
        gemini_api_key="valid-gemini-key",
        openrouter_api_key="valid-openrouter-key",
    )
    assert config.max_output_tokens == 8192
    assert config.max_session_token_budget == 500000
    assert config.daily_api_cost_limit_usd == 10.0
    assert config.circuit_breaker_failure_threshold == 3


@pytest.mark.asyncio
async def test_clients_enforce_30s_timeout() -> None:
    """Both Gemini and OpenRouter clients must enforce 30s read / 10s connect timeouts."""
    config = ArbiterConfig(gemini_api_key="valid-gemini-key", openrouter_api_key="valid-openrouter-key")
    gemini = GeminiReasonerClient(config=config)
    openrouter = OpenRouterFallbackClient(config=config)
    try:
        g_client = await gemini.get_client()
        o_client = await openrouter.get_client()
        assert g_client.timeout == httpx.Timeout(30.0, connect=10.0)
        assert o_client.timeout == httpx.Timeout(30.0, connect=10.0)
    finally:
        await gemini.aclose()
        await openrouter.aclose()


def test_unified_extract_json_strips_think_and_fences() -> None:
    """extract_json() and both clients' _extract_json() strip <think> blocks and markdown fences."""
    raw = '<think>\nReasoning trace with {"noise": 1}\n</think>\n```json\n{"actions": []}\n```'
    assert json.loads(extract_json(raw)) == {"actions": []}
    assert json.loads(GeminiReasonerClient._extract_json(raw)) == {"actions": []}
    assert json.loads(OpenRouterFallbackClient._extract_json(raw)) == {"actions": []}


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_retries_with_backoff_and_max_tokens() -> None:
    """OpenRouterFallbackClient retries transient 503s up to max_retries=2 and sends max_tokens."""
    config = ArbiterConfig(
        openrouter_api_key="valid-openrouter-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        max_output_tokens=4096,
    )
    client = OpenRouterFallbackClient(config=config)
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(503, text="Busy"),
            httpx.Response(503, text="Busy"),
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '<think>ok</think>{"actions": []}'}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                },
            ),
        ]
    )

    with patch("gemini_cost_arbiter.reasoner.openrouter.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        plan = await client.generate_plan(_sample_batch())

    assert plan is not None
    assert route.call_count == 3
    assert sleep_mock.await_count == 2
    sent_payload = json.loads(route.calls.last.request.content)
    assert sent_payload["max_tokens"] == 4096
    assert client.last_usage_metadata["total_tokens"] == 150


@pytest.mark.asyncio
@respx.mock
async def test_cost_and_consecutive_failure_circuit_breakers(caplog: pytest.LogCaptureFixture) -> None:
    """DAILY_API_COST_LIMIT_USD and 3 consecutive HTTP 503s trip immediate heuristic fallback."""
    caplog.set_level(logging.INFO, logger="gemini_cost_arbiter")
    config = ArbiterConfig(
        gemini_api_key="valid-gemini-key",
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta",
        openrouter_api_key=None,
        daily_api_cost_limit_usd=0.05,
        max_session_token_budget=500000,
        circuit_breaker_failure_threshold=3,
    )
    engine = GeminiCostArbiterEngine(config=config)
    gemini_route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-high:generateContent"
    ).mock(return_value=httpx.Response(503, text="Service Unavailable"))

    batch = _sample_batch()

    # 3 consecutive failures (each fails after max_retries=2) trip the consecutive-failure cooldown
    with patch("gemini_cost_arbiter.reasoner.client.asyncio.sleep", new_callable=AsyncMock):
        for _ in range(3):
            plan = await engine.generate_remediation_plan(batch)
            assert plan is not None
            assert engine.last_fallback_tier_used == "heuristics"

    calls_at_trip = gemini_route.call_count
    assert calls_at_trip == 9  # 3 calls * (1 initial + 2 retries)
    assert engine.circuit_breaker.trip_reason() == "consecutive_failure_cooldown"

    # Subsequent call must bypass Gemini completely (zero extra network calls)
    plan_after_trip = await engine.generate_remediation_plan(batch)
    assert plan_after_trip is not None
    assert gemini_route.call_count == calls_at_trip
    assert engine.last_fallback_tier_used == "heuristics"
    assert "fallback_tier_used=heuristics" in caplog.text

    # Now test DAILY_API_COST_LIMIT_USD tripping
    engine2 = GeminiCostArbiterEngine(config=config)
    engine2.circuit_breaker.record_success(tokens_used=1000, estimated_cost_usd=0.06)
    assert engine2.circuit_breaker.trip_reason() == "daily_api_cost_limit_exceeded"
    plan_cost_tripped = await engine2.generate_remediation_plan(batch)
    assert plan_cost_tripped is not None
    assert gemini_route.call_count == calls_at_trip  # Zero network calls
    assert engine2.last_fallback_tier_used == "heuristics"


@pytest.mark.asyncio
@respx.mock
async def test_session_token_budget_trips_circuit_breaker() -> None:
    """MAX_SESSION_TOKEN_BUDGET trips immediate heuristic fallback with zero network calls."""
    config = ArbiterConfig(
        gemini_api_key="valid-gemini-key",
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta",
        max_session_token_budget=1000,
    )
    engine = GeminiCostArbiterEngine(config=config)
    gemini_route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-high:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": '{"actions": []}'}]}}],
                "usageMetadata": {"promptTokenCount": 700, "candidatesTokenCount": 400, "totalTokenCount": 1100},
            },
        )
    )

    batch = _sample_batch()
    await engine.generate_remediation_plan(batch)
    assert engine.last_fallback_tier_used == "gemini"
    assert gemini_route.call_count == 1
    assert engine.circuit_breaker.trip_reason() == "session_token_budget_exceeded"

    await engine.generate_remediation_plan(batch)
    assert engine.last_fallback_tier_used == "heuristics"
    assert gemini_route.call_count == 1


def test_circuit_breaker_utc_rollover_and_cooldown_expiry() -> None:
    """Daily spend resets on UTC date rollover and cooldown resets after expiry."""
    cb = LLMQuotaCircuitBreaker(
        max_session_token_budget=500000,
        daily_api_cost_limit_usd=1.0,
        failure_threshold=2,
        cooldown_seconds=0.01,
    )
    cb.record_success(tokens_used=100, estimated_cost_usd=1.5)
    assert cb.trip_reason() == "daily_api_cost_limit_exceeded"

    # Simulate previous UTC day
    cb._cost_date = (datetime.now(UTC) - timedelta(days=1)).date()
    assert cb.allow_request() is True
    assert cb.daily_cost_usd == 0.0

    # Simulate failure cooldown expiry
    cb.record_failure()
    cb.record_failure()
    assert cb.trip_reason() == "consecutive_failure_cooldown"
    cb._cooldown_until = 0.0
    assert cb.allow_request() is True
    assert cb.consecutive_failures == 0


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_timeout_retry_and_engine_fallback_telemetry() -> None:
    """OpenRouter retries TimeoutException with jitter and records failure/success on engine."""
    config = ArbiterConfig(
        gemini_api_key="test-gemini-key",  # bypassed
        openrouter_api_key="valid-openrouter-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        circuit_breaker_failure_threshold=2,
    )
    engine = GeminiCostArbiterEngine(config=config)
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("Read timed out")
    )

    with patch("gemini_cost_arbiter.reasoner.openrouter.asyncio.sleep", new_callable=AsyncMock):
        plan = await engine.generate_remediation_plan(_sample_batch())

    assert plan is not None
    assert route.call_count == 3
    assert engine.last_fallback_tier_used == "heuristics"
    assert engine.circuit_breaker.consecutive_failures == 1
