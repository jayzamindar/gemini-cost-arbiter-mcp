"""Deterministic EC2 right-sizing and waste heuristics with real AWS pricing catalog lookup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from gemini_cost_arbiter.models.remediation import ActionType, RemediationActionItem
from gemini_cost_arbiter.models.telemetry import CloudResourceType, EC2Metrics

DEFAULT_INSTANCE_DOWNSIZE_MAP: dict[str, str] = {
    "m5.8xlarge": "m5.4xlarge",
    "m5.4xlarge": "m5.xlarge",
    "m5.2xlarge": "m5.large",
    "m5.xlarge": "m5.large",
    "c5.9xlarge": "c5.4xlarge",
    "c5.4xlarge": "c5.xlarge",
    "c5.2xlarge": "c5.large",
    "r5.4xlarge": "r5.xlarge",
    "t3.2xlarge": "t3.large",
    "t3.xlarge": "t3.medium",
}

DEFAULT_HOURLY_RATES: dict[str, float] = {
    "m5.8xlarge": 1.536,
    "m5.4xlarge": 0.768,
    "m5.2xlarge": 0.384,
    "m5.xlarge": 0.192,
    "m5.large": 0.096,
    "c5.4xlarge": 0.680,
    "c5.2xlarge": 0.340,
    "c5.xlarge": 0.170,
    "c5.large": 0.085,
    "r5.4xlarge": 1.008,
    "r5.2xlarge": 0.504,
    "r5.xlarge": 0.252,
    "r5.large": 0.126,
    "t3.2xlarge": 0.3328,
    "t3.xlarge": 0.1664,
    "t3.large": 0.0832,
    "t3.medium": 0.0416,
    "t4g.xlarge": 0.1344,
    "t4g.large": 0.0672,
    "t4g.medium": 0.0336,
    "t4g.small": 0.0168,
}


def load_instance_catalog() -> dict[str, Any]:
    """Load externalized instance mapping and pricing catalog from config/instance_mappings.json."""
    config_path = Path("config/instance_mappings.json")
    if config_path.exists():
        try:
            return cast(dict[str, Any], json.loads(config_path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return {
        "instance_downsize_map": DEFAULT_INSTANCE_DOWNSIZE_MAP,
        "instance_hourly_rates_usd": DEFAULT_HOURLY_RATES,
    }


def load_instance_mappings() -> dict[str, str]:
    """Load instance downsize mappings from catalog."""
    return cast(
        dict[str, str],
        load_instance_catalog().get("instance_downsize_map", DEFAULT_INSTANCE_DOWNSIZE_MAP),
    )


def get_instance_hourly_rate(instance_type: str) -> float | None:
    """Lookup real standard AWS On-Demand hourly rate for an instance size."""
    rates = cast(
        dict[str, float],
        load_instance_catalog().get("instance_hourly_rates_usd", DEFAULT_HOURLY_RATES),
    )
    return rates.get(instance_type.lower())


def evaluate_ec2_instance(ec2: EC2Metrics) -> RemediationActionItem | None:
    """Evaluate EC2 instance for underutilization waste using real AWS pricing lookups."""
    # Memory Floor Guardrail: Abort downsizing if memory utilization is high to prevent OOM crash
    if ec2.memory_utilization_avg_pct > 65.0:
        return None

    if ec2.cpu_utilization_avg_pct < 10.0 and ec2.cpu_utilization_p95_pct < 25.0:
        is_prod = ec2.environment.lower() == "production"
        risk = 4 if is_prod else 3

        mapping = load_instance_mappings()
        target_spec = mapping.get(ec2.current_instance_type.lower(), "t4g.xlarge")

        # Pricing Model Awareness: If instance is covered by RI or Savings Plan, bill savings is $0.00
        is_prepaid = getattr(ec2, "pricing_model", "on_demand").lower() in ["reserved", "savings_plan"]
        if is_prepaid:
            savings = 0.0
            post_spend = ec2.monthly_spend_usd
            rationale_suffix = (
                f" (NOTE: Instance is covered by {ec2.pricing_model.upper()} commitment; "
                f"net AWS billing savings are $0.00 until commitment expiration)."
            )
        else:
            # Real AWS Pricing Lookup (replacing flat percentage multipliers)
            curr_rate = get_instance_hourly_rate(ec2.current_instance_type)
            tgt_rate = get_instance_hourly_rate(target_spec)

            if curr_rate is not None and tgt_rate is not None and curr_rate > tgt_rate:
                hourly_delta = curr_rate - tgt_rate
                catalog_monthly_savings = round(hourly_delta * 730.0, 2)
                savings = (
                    min(ec2.monthly_spend_usd, catalog_monthly_savings)
                    if ec2.monthly_spend_usd > 0
                    else catalog_monthly_savings
                )
                post_spend = round(max(0.0, ec2.monthly_spend_usd - savings), 2)
                savings_pct = round((savings / ec2.monthly_spend_usd) * 100, 1) if ec2.monthly_spend_usd > 0 else 50.0
                rationale_suffix = (
                    f" Rightsizing from {ec2.current_instance_type} (${curr_rate:.3f}/hr) to "
                    f"{target_spec} (${tgt_rate:.3f}/hr) saves ~${savings:.2f}/mo ({savings_pct}% reduction)."
                )
            else:
                # Fallback to standard 65% estimate if unlisted in catalog
                savings = round(ec2.monthly_spend_usd * 0.65, 2)
                post_spend = round(ec2.monthly_spend_usd - savings, 2)
                rationale_suffix = (
                    f" Rightsizing from {ec2.current_instance_type} to {target_spec} saves ~65% monthly spend."
                )

        mitigations: list[str] = [
            f"Create pre-migration AMI snapshot ('ami-backup-{ec2.resource_id}')",
            "Schedule execution during off-peak maintenance window",
            "Automated rollback script via AWS CLI instance modification hook",
        ]

        return RemediationActionItem(
            resource_id=ec2.resource_id,
            resource_type=CloudResourceType.EC2,
            action_type=ActionType.RIGHTSIZE_INSTANCE,
            target_configuration=target_spec,
            current_monthly_spend_usd=ec2.monthly_spend_usd,
            projected_monthly_spend_usd=post_spend,
            projected_monthly_savings_usd=savings,
            safety_risk_score=risk,
            reasoning_rationale=(
                f"Instance '{ec2.resource_id}' is chronically underutilized with "
                f"{ec2.cpu_utilization_avg_pct:.1f}% avg CPU and {ec2.cpu_utilization_p95_pct:.1f}% p95 CPU."
                f"{rationale_suffix}"
            ),
            system_mitigations=mitigations,
            execution_payload={
                "aws_cli": f"aws ec2 modify-instance-attribute --instance-id {ec2.resource_id} --instance-type {target_spec}",
                "terraform": {
                    "resource": "aws_instance",
                    "instance_type": target_spec,
                },
                "rollback": {
                    "strategy": "revert_instance_type",
                    "command": f"aws ec2 modify-instance-attribute --instance-id {ec2.resource_id} --instance-type {ec2.current_instance_type}",
                },
            },
        )
    return None
