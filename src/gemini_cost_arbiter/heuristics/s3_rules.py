"""Deterministic S3 storage tiering and lifecycle heuristics."""

from __future__ import annotations

from gemini_cost_arbiter.models.remediation import ActionType, RemediationActionItem
from gemini_cost_arbiter.models.telemetry import CloudResourceType, S3Metrics


def evaluate_s3_bucket(s3: S3Metrics) -> RemediationActionItem | None:
    """Evaluate S3 bucket for cold storage optimization opportunities with small-object guardrail."""
    # Small-Object Economics Guardrail: S3 Intelligent-Tiering ignores objects < 128 KB
    # and charges $0.0025 per 1,000 objects/month. Buckets with small avg object size cost MORE.
    if s3.object_count > 0:
        avg_object_size_kb = (s3.total_storage_gb * 1024.0 * 1024.0) / s3.object_count
        if avg_object_size_kb < 128.0:
            return None

    if s3.percentage_infrequently_accessed > 50.0 and s3.current_storage_class.upper() == "STANDARD":
        savings = round(s3.monthly_spend_usd * 0.55, 2)
        post_spend = round(s3.monthly_spend_usd - savings, 2)

        return RemediationActionItem(
            resource_id=s3.resource_id,
            resource_type=CloudResourceType.S3,
            action_type=ActionType.TRANSITION_STORAGE_TIER,
            target_configuration="INTELLIGENT_TIERING",
            current_monthly_spend_usd=s3.monthly_spend_usd,
            projected_monthly_spend_usd=post_spend,
            projected_monthly_savings_usd=savings,
            safety_risk_score=1,
            reasoning_rationale=(
                f"S3 bucket '{s3.resource_id}' contains {s3.percentage_infrequently_accessed:.1f}% "
                f"infrequently accessed data stored on STANDARD class without lifecycle automation. "
                f"Enabling INTELLIGENT_TIERING eliminates cold object premiums with zero retrieval fees."
            ),
            system_mitigations=[],
            execution_payload={
                "terraform": {
                    "resource": "aws_s3_bucket_lifecycle_configuration",
                    "bucket": s3.resource_id,
                },
                "rollback": {
                    "strategy": "revert_storage_class",
                    "command": f"aws s3 cp s3://{s3.resource_id}/ s3://{s3.resource_id}/ --storage-class STANDARD --recursive",
                },
            },
        )
    return None
