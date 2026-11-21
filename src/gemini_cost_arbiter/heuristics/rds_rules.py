"""Deterministic RDS database waste heuristics."""

from __future__ import annotations

from gemini_cost_arbiter.models.remediation import ActionType, RemediationActionItem
from gemini_cost_arbiter.models.telemetry import CloudResourceType, RDSMetrics


def evaluate_rds_instance(rds: RDSMetrics) -> RemediationActionItem | None:
    """Evaluate RDS instance for zero-connection idle state."""
    if rds.active_connections_avg == 0.0:
        is_prod = rds.environment.lower() == "production"
        risk = 5 if is_prod else 3

        is_prepaid = getattr(rds, "pricing_model", "on_demand").lower() in ["reserved", "savings_plan"]
        if is_prepaid:
            savings = 0.0
            post_spend = rds.monthly_spend_usd
            rationale_suffix = (
                f" (NOTE: Database is covered by {rds.pricing_model.upper()} commitment; "
                f"stopping instance yields $0.00 in real AWS bill savings until commitment expiration)."
            )
        else:
            savings = round(rds.monthly_spend_usd * 0.85, 2)
            post_spend = round(rds.monthly_spend_usd - savings, 2)
            rationale_suffix = " Stopping idle database with prior snapshot eliminates running compute costs."

        mitigations: list[str] = [
            f"Execute manual RDS final snapshot ('snapshot-pre-stop-{rds.resource_id}')",
            "Verify no client applications or lambdas have active DNS bindings",
            "Retain automated backups for 30 days prior to stopping",
        ]

        return RemediationActionItem(
            resource_id=rds.resource_id,
            resource_type=CloudResourceType.RDS,
            action_type=ActionType.STOP_INSTANCE,
            target_configuration="STOPPED_STATE_WITH_SNAPSHOT",
            current_monthly_spend_usd=rds.monthly_spend_usd,
            projected_monthly_spend_usd=post_spend,
            projected_monthly_savings_usd=savings,
            safety_risk_score=risk,
            reasoning_rationale=(
                f"RDS DB instance '{rds.resource_id}' has 0 active client connections over observation window."
                f"{rationale_suffix}"
            ),
            system_mitigations=mitigations,
            execution_payload={
                "aws_cli": f"aws rds stop-db-instance --db-instance-identifier {rds.resource_id}",
                "rollback": {
                    "strategy": "restart_db_instance",
                    "command": f"aws rds start-db-instance --db-instance-identifier {rds.resource_id}",
                },
            },
        )
    return None
