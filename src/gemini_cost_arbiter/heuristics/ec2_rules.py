"""Deterministic EC2 right-sizing and waste heuristics with fail-closed AWS pricing catalog lookup."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, cast

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.heuristics.normalization import is_production_resource, normalize_str
from gemini_cost_arbiter.models.remediation import ActionType, RemediationActionItem
from gemini_cost_arbiter.models.telemetry import CloudResourceType, EC2Metrics

logger = logging.getLogger("gemini_cost_arbiter.heuristics.ec2")

DEFAULT_CATALOG_RELATIVE_PATH = "config/instance_mappings.json"


class CatalogNotFoundError(RuntimeError):
    """Raised when the EC2 instance mapping and pricing catalog is missing, unreadable, or invalid."""


def resolve_catalog_path() -> Path:
    """Resolve the instance catalog path dynamically via CATALOG_PATH / ArbiterConfig or repo root."""
    env_override = os.environ.get("CATALOG_PATH")
    if env_override is not None:
        stripped = env_override.strip()
        if not stripped:
            raise CatalogNotFoundError("CATALOG_PATH environment variable is empty.")
        return Path(stripped)

    cfg = ArbiterConfig()
    candidate = Path(cfg.catalog_path)
    if candidate.exists():
        return candidate
    if cfg.catalog_path == DEFAULT_CATALOG_RELATIVE_PATH:
        return Path(__file__).resolve().parents[3] / DEFAULT_CATALOG_RELATIVE_PATH
    return candidate


def load_instance_catalog() -> dict[str, Any]:
    """Load and validate the externalized instance mapping and pricing catalog (fail-closed)."""
    config_path = resolve_catalog_path()
    if not config_path.is_file():
        raise CatalogNotFoundError(f"Instance mappings catalog not found at '{config_path}'.")

    try:
        raw_text = config_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogNotFoundError(f"Failed to load instance mappings catalog at '{config_path}': {exc}") from exc

    if not isinstance(data, dict):
        raise CatalogNotFoundError(f"Invalid catalog format at '{config_path}': expected JSON object.")

    downsize_map = data.get("instance_downsize_map")
    hourly_rates = data.get("instance_hourly_rates_usd")
    if not isinstance(downsize_map, dict) or not isinstance(hourly_rates, dict):
        raise CatalogNotFoundError(
            f"Invalid catalog structure at '{config_path}': missing 'instance_downsize_map' or 'instance_hourly_rates_usd'."
        )

    return cast(dict[str, Any], data)


def load_instance_mappings() -> dict[str, str]:
    """Load normalized instance downsize mappings from the catalog."""
    raw_map = cast(dict[str, str], load_instance_catalog()["instance_downsize_map"])
    return {normalize_str(k): normalize_str(v) for k, v in raw_map.items()}


def get_instance_hourly_rate(instance_type: str) -> float | None:
    """Lookup real standard AWS On-Demand hourly rate for an instance size."""
    raw_rates = cast(dict[str, float], load_instance_catalog()["instance_hourly_rates_usd"])
    rates = {normalize_str(k): float(v) for k, v in raw_rates.items()}
    return rates.get(normalize_str(instance_type))


def evaluate_ec2_instance(ec2: EC2Metrics) -> RemediationActionItem | None:
    """Evaluate EC2 instance for underutilization waste using real AWS pricing lookups."""
    # Memory Floor Guardrail: Abort downsizing if memory utilization is high to prevent OOM crash
    if ec2.memory_utilization_avg_pct > 65.0:
        return None

    if ec2.cpu_utilization_avg_pct < 10.0 and ec2.cpu_utilization_p95_pct < 25.0:
        is_prod = is_production_resource(ec2.environment, ec2.tags)
        risk = 4 if is_prod else 3

        mapping = load_instance_mappings()
        norm_instance_type = normalize_str(ec2.current_instance_type)
        target_spec = mapping.get(norm_instance_type)
        if target_spec is None:
            logger.warning(
                "Unknown EC2 instance type '%s' for resource '%s'; aborting downsizing.",
                ec2.current_instance_type,
                ec2.resource_id,
            )
            return None

        # Pricing Model Awareness: If instance is covered by RI or Savings Plan, bill savings is $0.00
        pricing_norm = normalize_str(getattr(ec2, "pricing_model", "on_demand"))
        is_prepaid = pricing_norm in {"reserved", "savings_plan"}
        if is_prepaid:
            savings = 0.0
            post_spend = ec2.monthly_spend_usd
            rationale_suffix = (
                f" (NOTE: Instance is covered by {pricing_norm.upper()} commitment; "
                f"net AWS billing savings are $0.00 until commitment expiration)."
            )
        else:
            # Real AWS Pricing Lookup (fail closed if rates are missing from catalog)
            curr_rate = get_instance_hourly_rate(ec2.current_instance_type)
            tgt_rate = get_instance_hourly_rate(target_spec)

            if curr_rate is None or tgt_rate is None or curr_rate <= tgt_rate:
                logger.warning(
                    "Missing or non-beneficial catalog hourly rate for '%s' -> '%s' on resource '%s'; aborting downsizing.",
                    ec2.current_instance_type,
                    target_spec,
                    ec2.resource_id,
                )
                return None

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
