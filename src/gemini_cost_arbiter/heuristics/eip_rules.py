"""Deterministic heuristics for idle and unassociated AWS Elastic IP addresses."""

from __future__ import annotations

from typing import Optional
from gemini_cost_arbiter.models.remediation import ActionType, RemediationActionItem
from gemini_cost_arbiter.models.telemetry import CloudResourceType, EIPMetrics


def evaluate_elastic_ip(eip: EIPMetrics) -> Optional[RemediationActionItem]:
    """Evaluate Elastic IP for unassociated idle allocation charges."""
    if not eip.is_associated and eip.days_idle >= 7:
        savings = round(eip.monthly_spend_usd, 2)

        return RemediationActionItem(
            resource_id=eip.resource_id,
            resource_type=CloudResourceType.EIP,
            action_type=ActionType.RELEASE_ELASTIC_IP,
            target_configuration="RELEASED",
            current_monthly_spend_usd=eip.monthly_spend_usd,
            projected_monthly_spend_usd=0.0,
            projected_monthly_savings_usd=savings,
            safety_risk_score=2,
            reasoning_rationale=(
                f"Elastic IP '{eip.public_ip}' (Allocation: {eip.resource_id}) has been unassociated for "
                f"{eip.days_idle} days, incurring continuous AWS idle IPv4 charges. Releasing stops waste."
            ),
            system_mitigations=[],
            execution_payload={
                "aws_cli": f"aws ec2 release-address --allocation-id {eip.resource_id}",
                "terraform": {
                    "resource": "aws_eip",
                    "action": "destroy",
                },
                "rollback": {
                    "strategy": "allocate_new_eip",
                    "command": "aws ec2 allocate-address --domain vpc",
                    "note": "Original static IP cannot be guaranteed once released back to the AWS pool.",
                },
            },
        )
    return None
