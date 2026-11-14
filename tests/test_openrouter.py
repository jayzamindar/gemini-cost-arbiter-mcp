"""Tests validating secondary multi-model fallback via OpenRouter."""

import json
import pytest
import respx
import httpx
from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.engine import GeminiCostArbiterEngine
from gemini_cost_arbiter.models.telemetry import EC2Metrics, TelemetryBatch


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_secondary_fallback_flow() -> None:
    """Verify that when Gemini returns 503, OpenRouter handles the reasoning request."""
    config = ArbiterConfig(
        gemini_api_key="valid-test-key",
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta",
        openrouter_api_key="valid-openrouter-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        secondary_model="qwen/qwen-2.5-coder-32b-instruct",
    )
    engine = GeminiCostArbiterEngine(config=config)

    # Gemini 503 Outage
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-high:generateContent").mock(
        return_value=httpx.Response(503, text="Service Unavailable")
    )

    # OpenRouter Success
    mocked_openrouter_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "actions": [
                            {
                                "resource_id": "i-fallback-test",
                                "resource_type": "EC2",
                                "action_type": "rightsize_instance",
                                "target_configuration": "t4g.large",
                                "current_monthly_spend_usd": 250.0,
                                "projected_monthly_spend_usd": 75.0,
                                "projected_monthly_savings_usd": 175.0,
                                "safety_risk_score": 3,
                                "reasoning_rationale": "OpenRouter Qwen 2.5 Coder identified idle instance.",
                                "system_mitigations": ["Automated snapshot before resizing"],
                            }
                        ]
                    })
                }
            }
        ]
    }

    openrouter_route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=mocked_openrouter_response)
    )

    batch = TelemetryBatch(
        ec2_instances=[
            EC2Metrics(
                resource_id="i-fallback-test",
                current_instance_type="m5.xlarge",
                cpu_utilization_avg_pct=6.0,
                monthly_spend_usd=250.0,
            )
        ]
    )

    plan = await engine.generate_remediation_plan(batch)
    assert openrouter_route.called
    assert len(plan.actions) == 1
    assert plan.actions[0].resource_id == "i-fallback-test"
    assert "OpenRouter Qwen 2.5 Coder" in plan.actions[0].reasoning_rationale
