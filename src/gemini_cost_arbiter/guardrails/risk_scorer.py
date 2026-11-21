"""Safety Guardrail & Risk Scoring Engine.

Enforces calibrated safety scores (1 to 5), least-privilege IAM policy generation,
automated rollback synthesis, quarantine patterns, and HMAC-SHA256 cryptographic plan signing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import shlex
from typing import Any

from gemini_cost_arbiter.heuristics.normalization import PRODUCTION_VALUES, normalize_str
from gemini_cost_arbiter.models.remediation import ActionType, RemediationActionItem, RemediationPlan
from gemini_cost_arbiter.models.telemetry import CloudResourceType, TelemetryBatch

logger = logging.getLogger("gemini_cost_arbiter.guardrails")

# Ephemeral startup secret generated if PLAN_SIGNING_SECRET is omitted from environment
_EPHEMERAL_MACHINE_SECRET = secrets.token_hex(32)

_RES_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._:/-]+$")
_TARGET_CFG_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")
_PREPAID_PRICING_MODELS: frozenset[str] = frozenset({"reserved", "savings_plan"})


def _validate_resource_id(res_id: Any) -> str:
    """Validate AWS resource_id against safe character allowlist and reject wildcards."""
    if not isinstance(res_id, str) or res_id == "*" or not _RES_ID_PATTERN.fullmatch(res_id):
        raise ValueError(f"Invalid resource_id {res_id!r}: must match ^[a-zA-Z0-9._:/-]+$ and must not be '*'.")
    return res_id


def _validate_target_config(target_cfg: Any) -> str:
    """Validate target_configuration against safe character allowlist."""
    if not isinstance(target_cfg, str) or not _TARGET_CFG_PATTERN.fullmatch(target_cfg):
        raise ValueError(f"Invalid target_configuration {target_cfg!r}: must match ^[a-zA-Z0-9._-]+$.")
    return target_cfg


class GuardrailEngine:
    """Enterprise safety evaluator ensuring compliant, least-privilege remediation payloads."""

    @staticmethod
    def audit_and_enrich_action(action_data: dict[str, Any]) -> dict[str, Any]:
        """Validate safety risk bounds, enforce quarantine for missing mitigations, and synthesize rollbacks and IAM."""
        score = action_data.get("safety_risk_score", 1)
        if type(score) is not int or score < 1 or score > 5:
            raise ValueError(f"Safety risk score {score!r} must be an integer within bounds [1, 5].")

        raw_mitigations = action_data.get("system_mitigations", [])
        if raw_mitigations is None:
            raw_mitigations = []
        mitigations: list[str] = [m.strip() for m in raw_mitigations if isinstance(m, str) and m.strip()]
        action_data["system_mitigations"] = mitigations

        resource_id = action_data.get("resource_id", "unknown-resource")

        # Quarantine Pattern: Never silently auto-inject generic templates for high-risk actions.
        # If the reasoner omitted mitigations on score >= 3, quarantine the action for human SRE sign-off.
        if score >= 3 and not mitigations:
            action_data["quarantined"] = True
            action_data["quarantine_reason"] = (
                f"Action on '{resource_id}' has safety_risk_score={score} (>= 3) "
                f"but reasoner omitted required system mitigations. Quarantined pending manual SRE review."
            )
        else:
            action_data.setdefault("quarantined", False)
            action_data.setdefault("quarantine_reason", None)

        # Unconditionally synthesize and overwrite execution payload with deterministic Python templates
        # (Zero-Hallucination: Strips and replaces any LLM-hallucinated IAM policies, CLI strings, or rollbacks)
        payload = dict(action_data.get("execution_payload", {}))
        payload["rollback"] = GuardrailEngine._generate_rollback_plan(action_data)
        payload["iam_policy"] = GuardrailEngine._generate_iam_policy(action_data)
        payload["aws_cli"] = GuardrailEngine._generate_aws_cli(action_data)
        action_data["execution_payload"] = payload

        return action_data

    @staticmethod
    def _generate_rollback_plan(action_data: dict[str, Any]) -> dict[str, Any]:
        """Synthesize deterministic rollback payload based on resource type and action."""
        raw_type = action_data.get("resource_type", "")
        res_type = normalize_str(raw_type.value if hasattr(raw_type, "value") else str(raw_type)).replace(
            "cloudresourcetype.", ""
        )
        res_id = _validate_resource_id(action_data.get("resource_id"))
        quoted_id = shlex.quote(res_id)

        if "ec2" in res_type:
            return {
                "strategy": "revert_instance_type",
                "command": (
                    f"aws ec2 modify-instance-attribute --instance-id {quoted_id}"
                    f" --instance-type ${{ORIGINAL_INSTANCE_TYPE}}"
                ),
                "health_check_alarm": f"arn:aws:cloudwatch:us-east-1:123456789012:alarm:{res_id}-StatusCheckFailed",
            }
        elif "rds" in res_type:
            return {
                "strategy": "restore_from_snapshot",
                "command": f"aws rds start-db-instance --db-instance-identifier {quoted_id}",
                "snapshot_target": f"snapshot-pre-action-{res_id}",
            }
        elif "s3" in res_type:
            quoted_s3_uri = shlex.quote(f"s3://{res_id}/")
            return {
                "strategy": "revert_storage_class",
                "command": f"aws s3 cp {quoted_s3_uri} {quoted_s3_uri} --storage-class STANDARD --recursive",
            }
        elif "ebs" in res_type:
            quoted_snap = shlex.quote(f"snap-pre-delete-{res_id}")
            return {
                "strategy": "restore_from_snapshot",
                "command": f"aws ec2 create-volume --snapshot-id {quoted_snap} --availability-zone us-east-1a",
            }
        elif "eip" in res_type:
            return {
                "strategy": "allocate_new_eip",
                "command": "aws ec2 allocate-address --domain vpc",
                "note": "Original static IP cannot be guaranteed once released back to the AWS pool.",
            }
        return {"strategy": "manual_sre_intervention", "action": "inspect_system_logs"}

    @staticmethod
    def _generate_aws_cli(action_data: dict[str, Any]) -> str:
        """Deterministically generate exact AWS CLI execution command for remediation."""
        raw_type = action_data.get("resource_type", "")
        res_type = normalize_str(raw_type.value if hasattr(raw_type, "value") else str(raw_type)).replace(
            "cloudresourcetype.", ""
        )
        res_id = _validate_resource_id(action_data.get("resource_id"))
        quoted_id = shlex.quote(res_id)
        raw_action = action_data.get("action_type", "")
        action_name = normalize_str(raw_action.value if hasattr(raw_action, "value") else str(raw_action))
        raw_target = action_data.get("target_configuration")
        validated_target = _validate_target_config(raw_target) if raw_target is not None else None

        if "ec2" in res_type:
            if "stop" in action_name:
                return f"aws ec2 stop-instances --instance-ids {quoted_id}"
            target = validated_target if validated_target is not None else "t3.medium"
            return f"aws ec2 modify-instance-attribute --instance-id {quoted_id} --instance-type {shlex.quote(target)}"
        elif "rds" in res_type:
            if "stop" in action_name:
                return f"aws rds stop-db-instance --db-instance-identifier {quoted_id}"
            target = validated_target if validated_target is not None else "db.t3.medium"
            return (
                f"aws rds modify-db-instance --db-instance-identifier {quoted_id}"
                f" --db-instance-class {shlex.quote(target)} --apply-immediately"
            )
        elif "s3" in res_type:
            return (
                f"aws s3api put-bucket-lifecycle-configuration --bucket {quoted_id}"
                f" --lifecycle-configuration file://lifecycle.json"
            )
        elif "ebs" in res_type:
            return f"aws ec2 delete-volume --volume-id {quoted_id}"
        elif "eip" in res_type:
            return f"aws ec2 release-address --allocation-id {quoted_id}"
        return f"aws ec2 describe-instances --instance-ids {quoted_id}"

    @staticmethod
    def _generate_iam_policy(action_data: dict[str, Any]) -> dict[str, Any]:
        """Generate exact least-privilege AWS IAM statement required for execution and rollback."""
        raw_type = action_data.get("resource_type", "")
        res_type = normalize_str(raw_type.value if hasattr(raw_type, "value") else str(raw_type)).replace(
            "cloudresourcetype.", ""
        )
        res_id = _validate_resource_id(action_data.get("resource_id"))
        raw_action = action_data.get("action_type", "")
        action_name = normalize_str(raw_action.value if hasattr(raw_action, "value") else str(raw_action))

        if res_type == "ec2":
            arn = f"arn:aws:ec2:*:*:instance/{res_id}"
            if "stop" in action_name:
                allowed_actions = ["ec2:DescribeInstances", "ec2:StopInstances"]
            else:
                allowed_actions = ["ec2:DescribeInstances", "ec2:ModifyInstanceAttribute"]
        elif res_type == "ebs":
            arn = f"arn:aws:ec2:*:*:volume/{res_id}"
            if "delete" in action_name or "terminate" in action_name:
                allowed_actions = ["ec2:DescribeVolumes", "ec2:DeleteVolume"]
            else:
                allowed_actions = ["ec2:DescribeVolumes", "ec2:ModifyVolume"]
        elif res_type == "eip":
            arn = f"arn:aws:ec2:*:*:elastic-ip/{res_id}"
            allowed_actions = ["ec2:DescribeAddresses", "ec2:ReleaseAddress"]
        elif res_type == "rds":
            arn = f"arn:aws:rds:*:*:db:{res_id}"
            if "stop" in action_name:
                allowed_actions = ["rds:DescribeDBInstances", "rds:StopDBInstance", "rds:StartDBInstance"]
            else:
                allowed_actions = ["rds:DescribeDBInstances", "rds:ModifyDBInstance"]
        elif res_type == "s3":
            arn = f"arn:aws:s3:::{res_id}"
            allowed_actions = ["s3:GetLifecycleConfiguration", "s3:PutLifecycleConfiguration"]
        else:
            raise ValueError(f"Unknown or unsupported cloud resource type for IAM policy generation: '{res_type}'")

        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": f"FinOpsArbiterExecution{res_type.upper()}",
                    "Effect": "Allow",
                    "Action": allowed_actions,
                    "Resource": arn,
                }
            ],
        }

    @staticmethod
    def reconcile_with_telemetry(
        actions: list[RemediationActionItem],
        batch: TelemetryBatch,
    ) -> list[RemediationActionItem]:
        """Reconcile proposed actions against TelemetryBatch FinOps floors and spend caps."""
        ec2_map = {m.resource_id: m for m in batch.ec2_instances}
        rds_map = {m.resource_id: m for m in batch.rds_instances}
        s3_map = {m.resource_id: m for m in batch.s3_buckets}
        ebs_map = {m.resource_id: m for m in batch.ebs_volumes}
        eip_map = {m.resource_id: m for m in batch.elastic_ips}

        reconciled: list[RemediationActionItem] = []
        for action in actions:
            current_spend = action.current_monthly_spend_usd
            is_prepaid = False

            if action.resource_type == CloudResourceType.EC2:
                ec2 = ec2_map.get(action.resource_id)
                if ec2 is not None:
                    if (
                        action.action_type in {ActionType.RIGHTSIZE_INSTANCE, ActionType.DOWNSIZE}
                        and ec2.memory_utilization_avg_pct > 65.0
                    ):
                        logger.warning(
                            "Vetoing EC2 downsize on '%s': memory_utilization_avg_pct=%.1f%% (> 65.0%%).",
                            action.resource_id,
                            ec2.memory_utilization_avg_pct,
                        )
                        continue
                    current_spend = ec2.monthly_spend_usd
                    is_prepaid = normalize_str(ec2.pricing_model) in _PREPAID_PRICING_MODELS

            elif action.resource_type == CloudResourceType.RDS:
                rds = rds_map.get(action.resource_id)
                if rds is not None:
                    current_spend = rds.monthly_spend_usd
                    is_prepaid = normalize_str(rds.pricing_model) in _PREPAID_PRICING_MODELS

            elif action.resource_type == CloudResourceType.S3:
                s3 = s3_map.get(action.resource_id)
                if s3 is not None:
                    current_spend = s3.monthly_spend_usd
                    avg_kb: float | None = None
                    if s3.object_count > 0:
                        avg_kb = (s3.total_storage_gb * 1024.0 * 1024.0) / s3.object_count
                    elif s3.object_count_total > 0:
                        avg_kb = (s3.bucket_size_bytes_total / 1024.0) / s3.object_count_total
                    if (
                        avg_kb is not None
                        and avg_kb < 128.0
                        and action.action_type in {ActionType.TRANSITION_STORAGE_TIER, ActionType.APPLY_LIFECYCLE_RULE}
                    ):
                        logger.warning(
                            "Vetoing S3 tiering on '%s': avg_object_size_kb=%.2f KB (< 128.0 KB).",
                            action.resource_id,
                            avg_kb,
                        )
                        continue

            elif action.resource_type == CloudResourceType.EBS:
                ebs = ebs_map.get(action.resource_id)
                if ebs is not None:
                    current_spend = ebs.monthly_spend_usd

            elif action.resource_type == CloudResourceType.EIP:
                eip = eip_map.get(action.resource_id)
                if eip is not None:
                    current_spend = eip.monthly_spend_usd

            if is_prepaid:
                clamped_savings = 0.0
            else:
                clamped_savings = round(min(max(0.0, action.projected_monthly_savings_usd), current_spend), 2)

            projected_spend = round(max(0.0, current_spend - clamped_savings), 2)
            reconciled.append(
                action.model_copy(
                    update={
                        "current_monthly_spend_usd": current_spend,
                        "projected_monthly_savings_usd": clamped_savings,
                        "projected_monthly_spend_usd": projected_spend,
                    }
                )
            )

        return reconciled

    @staticmethod
    def attach_plan_digest(plan: RemediationPlan, secret: str | None = None) -> RemediationPlan:
        """Calculate and attach SHA-256 digest and HMAC-SHA256 signature to the full canonical plan."""
        plan_data = plan.model_dump(mode="json", exclude={"plan_digest", "plan_signature"})
        canonical_json = json.dumps(plan_data, sort_keys=True, separators=(",", ":"))
        raw_bytes = canonical_json.encode("utf-8")
        digest = hashlib.sha256(raw_bytes).hexdigest()

        # Keyed HMAC-SHA256 signing with fail-closed production check
        signing_key_str = secret or os.environ.get("PLAN_SIGNING_SECRET")
        if not signing_key_str:
            if normalize_str(os.environ.get("ENVIRONMENT", "")) in PRODUCTION_VALUES:
                raise RuntimeError("PLAN_SIGNING_SECRET must be configured in production environment.")
            signing_key_str = _EPHEMERAL_MACHINE_SECRET

        signature = hmac.new(signing_key_str.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

        plan_dict = plan.model_dump()
        plan_dict["plan_digest"] = digest
        plan_dict["plan_signature"] = signature
        return RemediationPlan(**plan_dict)

    @staticmethod
    def verify_plan_signature(plan: RemediationPlan, secret: str | None = None) -> bool:
        """Verify both SHA-256 digest and HMAC-SHA256 signature of a remediation plan against tampering."""
        if not plan.plan_signature or not plan.plan_digest:
            return False
        try:
            recalculated = GuardrailEngine.attach_plan_digest(plan, secret=secret)
        except Exception:
            return False

        digest_matches = hmac.compare_digest(plan.plan_digest, recalculated.plan_digest or "")
        sig_matches = hmac.compare_digest(plan.plan_signature, recalculated.plan_signature or "")
        return digest_matches and sig_matches

    @staticmethod
    def filter_by_risk(
        actions: list[RemediationActionItem],
        max_acceptable_risk: int | None = None,
    ) -> list[RemediationActionItem]:
        """Filter out any actions exceeding the maximum acceptable risk threshold."""
        threshold = max_acceptable_risk if max_acceptable_risk is not None else 5
        return [a for a in actions if a.safety_risk_score <= threshold]
