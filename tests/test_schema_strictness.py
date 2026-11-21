"""Strictness, immutability, bounds, and invariant tests for Pydantic v2 models (REM-003, REM-004)."""

from __future__ import annotations

import importlib
import math

import pytest
from pydantic import ValidationError

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.engine import GeminiCostArbiterEngine
from gemini_cost_arbiter.models import (
    ActionType,
    CloudResourceType,
    CloudTelemetry,
    EBSMetrics,
    EC2Metrics,
    EIPMetrics,
    FinOpsAuditSummary,
    RDSMetrics,
    RemediationActionItem,
    RemediationPlan,
    S3Metrics,
    TelemetryBatch,
    WasteAnalysisSummary,
)


def test_models_forbid_extra_and_are_frozen() -> None:
    """All core models must forbid extra fields, reject NaN/Inf, and be immutable (frozen)."""
    with pytest.raises(ValidationError):
        EC2Metrics(resource_id="i-12345", unknown_field="nope")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        RDSMetrics(resource_id="db-1", unknown_field="nope")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        S3Metrics(resource_id="bucket-1", unknown_field="nope")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        EBSMetrics(resource_id="vol-1", unknown_field="nope")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        EIPMetrics(resource_id="eipalloc-1", unknown_field="nope")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        CloudTelemetry(
            resource_id="i-1",
            resource_type=CloudResourceType.EC2,
            unknown_field="nope",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        TelemetryBatch(unknown_field=[])  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        RemediationActionItem(
            resource_id="i-1",
            resource_type=CloudResourceType.EC2,
            action_type=ActionType.RIGHTSIZE_INSTANCE,
            current_monthly_spend_usd=100.0,
            projected_monthly_spend_usd=50.0,
            projected_monthly_savings_usd=50.0,
            safety_risk_score=1,
            unknown_field="nope",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        RemediationPlan(
            plan_id="plan-1",
            created_at="2026-01-01T00:00:00Z",
            total_current_monthly_spend_usd=0.0,
            total_projected_monthly_spend_usd=0.0,
            total_projected_monthly_savings_usd=0.0,
            unknown_field="nope",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        WasteAnalysisSummary(
            total_resources_evaluated=1,
            underutilized_resources_count=0,
            total_monthly_spend_usd=10.0,
            total_monthly_waste_usd=0.0,
            potential_savings_percentage=0.0,
            unknown_field="nope",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        FinOpsAuditSummary(last_updated="2026-01-01T00:00:00Z", unknown_field="nope")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        ArbiterConfig(nonexistent_setting="bad")  # type: ignore[call-arg]

    # NaN / Inf rejection
    for bad_float in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValidationError):
            EC2Metrics(resource_id="i-nan", monthly_spend_usd=bad_float)
        with pytest.raises(ValidationError):
            RemediationActionItem(
                resource_id="i-nan",
                resource_type=CloudResourceType.EC2,
                action_type=ActionType.RIGHTSIZE_INSTANCE,
                current_monthly_spend_usd=bad_float,
                projected_monthly_spend_usd=0.0,
                projected_monthly_savings_usd=0.0,
                safety_risk_score=1,
            )
        with pytest.raises(ValidationError):
            FinOpsAuditSummary(last_updated="2026-01-01T00:00:00Z", cumulative_waste_identified_usd=bad_float)

    # Frozen immutability checks
    ec2 = EC2Metrics(resource_id="i-frozen")
    with pytest.raises(ValidationError):
        ec2.monthly_spend_usd = 999.0  # type: ignore[misc]

    action = RemediationActionItem(
        resource_id="i-frozen",
        resource_type=CloudResourceType.EC2,
        action_type=ActionType.RIGHTSIZE_INSTANCE,
        current_monthly_spend_usd=100.0,
        projected_monthly_spend_usd=60.0,
        projected_monthly_savings_usd=40.0,
        safety_risk_score=1,
    )
    with pytest.raises(ValidationError):
        action.reasoning_rationale = "mutated"  # type: ignore[misc]

    plan = RemediationPlan(
        plan_id="plan-frozen",
        created_at="2026-01-01T00:00:00Z",
        actions=[action],
        total_current_monthly_spend_usd=100.0,
        total_projected_monthly_spend_usd=60.0,
        total_projected_monthly_savings_usd=40.0,
    )
    with pytest.raises(ValidationError):
        plan.plan_digest = "tampered"  # type: ignore[misc]

    audit = FinOpsAuditSummary(last_updated="2026-01-01T00:00:00Z")
    with pytest.raises(ValidationError):
        audit.total_batches_processed = 42  # type: ignore[misc]


def test_dynamic_fallback_model_removed() -> None:
    """DynamicFallbackModel and __getattr__ masking must not exist in models or app.schemas."""
    models_pkg = importlib.import_module("gemini_cost_arbiter.models")
    schemas_mod = importlib.import_module("app.schemas")

    assert not hasattr(models_pkg, "DynamicFallbackModel")
    assert not hasattr(schemas_mod, "DynamicFallbackModel")

    with pytest.raises(AttributeError):
        _ = models_pkg.NonExistentSchemaClass  # type: ignore[attr-defined]

    with pytest.raises(AttributeError):
        _ = schemas_mod.NonExistentSchemaClass  # type: ignore[attr-defined]


def test_bounded_fields_and_plan_savings_invariant() -> None:
    """String patterns/lengths, collection bounds, numeric ranges, and savings sum must be enforced."""
    # Injection / invalid resource_id
    with pytest.raises(ValidationError):
        EC2Metrics(resource_id="i-1; rm -rf /")

    with pytest.raises(ValidationError):
        EC2Metrics(resource_id="")

    with pytest.raises(ValidationError):
        EC2Metrics(resource_id="i-" + "a" * 127)

    # Instance type / class bounds
    with pytest.raises(ValidationError):
        EC2Metrics(current_instance_type="x")

    with pytest.raises(ValidationError):
        RDSMetrics(current_instance_class="db.t4g.medium; DROP TABLE")

    # Tag count and key/value length bounds
    too_many_tags = {f"k{i}": "v" for i in range(65)}
    with pytest.raises(ValidationError):
        EC2Metrics(tags=too_many_tags)

    with pytest.raises(ValidationError):
        EC2Metrics(tags={"k" * 129: "v"})

    with pytest.raises(ValidationError):
        EC2Metrics(tags={"k": "v" * 129})

    # TelemetryBatch max_length=500
    with pytest.raises(ValidationError):
        TelemetryBatch(ec2_instances=[EC2Metrics(resource_id=f"i-{i}") for i in range(501)])

    # CloudTelemetry numeric bounds
    with pytest.raises(ValidationError):
        CloudTelemetry(resource_id="i-1", resource_type=CloudResourceType.EC2, monthly_cost_usd=-1.0)

    with pytest.raises(ValidationError):
        CloudTelemetry(resource_id="i-1", resource_type=CloudResourceType.EC2, cpu_utilization_avg=101.0)

    # system_mitigations max_length=32
    with pytest.raises(ValidationError):
        RemediationActionItem(
            resource_id="i-1",
            resource_type=CloudResourceType.EC2,
            action_type=ActionType.RIGHTSIZE_INSTANCE,
            current_monthly_spend_usd=100.0,
            projected_monthly_spend_usd=50.0,
            projected_monthly_savings_usd=50.0,
            safety_risk_score=3,
            system_mitigations=[f"mitigation-{i}" for i in range(33)],
        )

    # RemediationPlan savings sum invariant
    action = RemediationActionItem(
        resource_id="i-1",
        resource_type=CloudResourceType.EC2,
        action_type=ActionType.RIGHTSIZE_INSTANCE,
        current_monthly_spend_usd=100.0,
        projected_monthly_spend_usd=60.0,
        projected_monthly_savings_usd=40.0,
        safety_risk_score=1,
    )
    with pytest.raises(ValidationError):
        RemediationPlan(
            plan_id="plan-bad-sum",
            created_at="2026-01-01T00:00:00Z",
            actions=[action],
            total_current_monthly_spend_usd=100.0,
            total_projected_monthly_spend_usd=60.0,
            total_projected_monthly_savings_usd=99.99,
        )

    # Valid RemediationPlan within 0.01 tolerance
    valid_plan = RemediationPlan(
        plan_id="plan-ok",
        created_at="2026-01-01T00:00:00Z",
        actions=[action],
        total_current_monthly_spend_usd=100.0,
        total_projected_monthly_spend_usd=60.0,
        total_projected_monthly_savings_usd=40.0,
    )
    assert valid_plan.total_projected_monthly_savings_usd == 40.0


async def test_dry_run_does_not_mutate_frozen_actions() -> None:
    """Engine dry_run=True must annotate frozen actions using model_copy() without ValidationError."""
    engine = GeminiCostArbiterEngine()
    batch = TelemetryBatch(
        ec2_instances=[
            EC2Metrics(
                resource_id="i-dryrun01",
                current_instance_type="m5.large",
                cpu_utilization_avg_pct=3.0,
                cpu_utilization_p95_pct=6.0,
                memory_utilization_avg_pct=20.0,
                monthly_spend_usd=70.0,
                environment="development",
            )
        ]
    )
    plan = await engine.generate_remediation_plan(batch, dry_run=True)
    assert len(plan.actions) >= 1
    assert all(a.reasoning_rationale.startswith("[DRY-RUN SIMULATION] ") for a in plan.actions)
