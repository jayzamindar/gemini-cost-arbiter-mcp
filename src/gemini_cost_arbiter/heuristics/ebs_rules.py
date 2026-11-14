"""Deterministic heuristics for detached and orphan AWS EBS volumes."""

from __future__ import annotations

from typing import List, Optional
from gemini_cost_arbiter.models.remediation import ActionType, RemediationActionItem
from gemini_cost_arbiter.models.telemetry import CloudResourceType, EBSMetrics


def evaluate_ebs_volume(ebs: EBSMetrics) -> Optional[RemediationActionItem]:
    """Evaluate EBS volume for orphan/detached storage waste."""
    if not ebs.is_attached and ebs.days_unattached >= 30:
        is_prod = ebs.environment.lower() == "production"
        # If it has a verified snapshot, risk is low (2); if no snapshot, moderate (3) requiring snapshot mitigation
        risk = 3 if (not ebs.has_snapshot or is_prod) else 2
        savings = round(ebs.monthly_spend_usd, 2)
        post_spend = 0.0

        mitigations: List[str] = []
        if risk >= 3:
            mitigations.extend([
                f"Create pre-deletion EBS snapshot ('snap-pre-delete-{ebs.resource_id}')",
                "Verify volume tags do not indicate static disaster recovery state",
                "Retain automated snapshot for 90 days before final expiration",
            ])

        return RemediationActionItem(
            resource_id=ebs.resource_id,
            resource_type=CloudResourceType.EBS,
            action_type=ActionType.DELETE_UNATTACHED_VOLUME,
            target_configuration="DELETED_STATE_WITH_SNAPSHOT",
            current_monthly_spend_usd=ebs.monthly_spend_usd,
            projected_monthly_spend_usd=post_spend,
            projected_monthly_savings_usd=savings,
            safety_risk_score=risk,
            reasoning_rationale=(
                f"EBS volume '{ebs.resource_id}' ({ebs.size_gb}GB {ebs.volume_type}) has been detached for "
                f"{ebs.days_unattached} days without compute association. Deleting orphan volume saves 100% recurring cost."
            ),
            system_mitigations=mitigations,
            execution_payload={
                "aws_cli": f"aws ec2 delete-volume --volume-id {ebs.resource_id}",
                "terraform": {
                    "resource": "aws_ebs_volume",
                    "action": "destroy",
                },
                "rollback": {
                    "strategy": "restore_from_snapshot",
                    "command": f"aws ec2 create-volume --snapshot-id snap-pre-delete-{ebs.resource_id} --availability-zone {ebs.region}a",
                },
            },
        )
    return None
