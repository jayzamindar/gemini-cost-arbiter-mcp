"""Tests validating Gemini 3.8 Flash High thinking budget payload serialization."""

import json

import httpx
import pytest
import respx

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.models.telemetry import EC2Metrics, TelemetryBatch
from gemini_cost_arbiter.reasoner.client import GeminiReasonerClient


@pytest.mark.asyncio
@respx.mock
async def test_gemini_thinking_budget_in_payload() -> None:
    """Verify that thinkingConfig is injected into generationConfig."""
    config = ArbiterConfig(
        gemini_api_key="valid-test-key",
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta",
        model_name="gemini-3.8-flash-high",
        thinking_budget=3072,
    )
    client = GeminiReasonerClient(config=config)

    mocked_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "actions": [
                                        {
                                            "resource_id": "i-test",
                                            "resource_type": "EC2",
                                            "action_type": "rightsize_instance",
                                            "target_configuration": "t4g.xlarge",
                                            "current_monthly_spend_usd": 300.0,
                                            "projected_monthly_spend_usd": 100.0,
                                            "projected_monthly_savings_usd": 200.0,
                                            "safety_risk_score": 3,
                                            "reasoning_rationale": "Rightsizing underutilized instance.",
                                            "system_mitigations": ["Pre-execution AMI snapshot"],
                                        }
                                    ]
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-high:generateContent"
    ).mock(return_value=httpx.Response(200, json=mocked_response))

    batch = TelemetryBatch(
        ec2_instances=[
            EC2Metrics(
                resource_id="i-test",
                current_instance_type="m5.2xlarge",
                cpu_utilization_avg_pct=5.0,
                monthly_spend_usd=300.0,
            )
        ]
    )

    plan = await client.generate_plan(batch)
    assert plan is not None
    assert len(plan.actions) == 1
    assert plan.actions[0].resource_id == "i-test"

    # Verify request payload contained thinkingConfig
    assert route.called
    sent_request = route.calls.last.request
    sent_payload = json.loads(sent_request.content)
    assert "generationConfig" in sent_payload
    assert "thinkingConfig" in sent_payload["generationConfig"]
    assert sent_payload["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 3072
