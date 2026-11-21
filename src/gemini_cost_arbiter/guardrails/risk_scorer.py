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
import secrets
from typing import Any

from gemini_cost_arbiter.heuristics.normalization import PRODUCTION_VALUES, normalize_str
from gemini_cost_arbiter.models.remediation import RemediationActionItem, RemediationPlan

logger = logging.getLogger("gemini_cost_arbiter.guardrails")

# Ephemeral startup secret generated if PLAN_SIGNING_SECRET is omitted from environment
_EPHEMERAL_MACHINE_SECRET = secrets.token_hex(32)


class GuardrailEngine:
    """Enterprise safety evaluator ensuring compliant, least-privilege remediation payloads."""

    @staticmethod
    def audit_and_enrich_action(action_data: dict[str, Any]) -> dict[str, Any]:
        """Validate safety risk bounds, enforce quarantine for missing mitigations, and synthesize rollbacks and IAM."""
        score = action_data.get("safety_risk_score", 1)
        if score < 1 or score > 5:
            raise ValueError(f"Safety risk score {score} must be within bounds [1, 5].")

        mitigations: list[str] = list(action_data.get("system_mitigations", []))
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
        res_id = action_data.get("resource_id", "res")

        if "ec2" in res_type:
            return {
                "strategy": "revert_instance_type",
                "command": f"aws ec2 modify-instance-attribute --instance-id {res_id} --instance-type ${{ORIGINAL_INSTANCE_TYPE}}",
                "health_check_alarm": f"arn:aws:cloudwatch:us-east-1:123456789012:alarm:{res_id}-StatusCheckFailed",
            }
        elif "rds" in res_type:
            return {
                "strategy": "restore_from_snapshot",
                "command": f"aws rds start-db-instance --db-instance-identifier {res_id}",
                "snapshot_target": f"snapshot-pre-action-{res_id}",
            }
        elif "s3" in res_type:
            return {
                "strategy": "revert_storage_class",
                "command": f"aws s3 cp s3://{res_id}/ s3://{res_id}/ --storage-class STANDARD --recursive",
            }
        elif "ebs" in res_type:
            return {
                "strategy": "restore_from_snapshot",
                "command": f"aws ec2 create-volume --snapshot-id snap-pre-delete-{res_id} --availability-zone us-east-1a",
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
        res_id = action_data.get("resource_id", "res")
        raw_action = action_data.get("action_type", "")
        action_name = normalize_str(raw_action.value if hasattr(raw_action, "value") else str(raw_action))
        target_cfg = action_data.get("target_configuration")

        if "ec2" in res_type:
            if "stop" in action_name:
                return f"aws ec2 stop-instances --instance-ids {res_id}"
            target = target_cfg or "t3.medium"
            return f"aws ec2 modify-instance-attribute --instance-id {res_id} --instance-type {target}"
        elif "rds" in res_type:
            if "stop" in action_name:
                return f"aws rds stop-db-instance --db-instance-identifier {res_id}"
            target = target_cfg or "db.t3.medium"
            return f"aws rds modify-db-instance --db-instance-identifier {res_id} --db-instance-class {target} --apply-immediately"
        elif "s3" in res_type:
            return f"aws s3api put-bucket-lifecycle-configuration --bucket {res_id} --lifecycle-configuration file://lifecycle.json"
        elif "ebs" in res_type:
            return f"aws ec2 delete-volume --volume-id {res_id}"
        elif "eip" in res_type:
            return f"aws ec2 release-address --allocation-id {res_id}"
        return f"aws ec2 describe-instances --instance-ids {res_id}"

    @staticmethod
    def _generate_iam_policy(action_data: dict[str, Any]) -> dict[str, Any]:
        """Generate exact least-privilege AWS IAM statement required for execution and rollback."""
        raw_type = action_data.get("resource_type", "")
        res_type = normalize_str(raw_type.value if hasattr(raw_type, "value") else str(raw_type)).replace(
            "cloudresourcetype.", ""
        )
        res_id = action_data.get("resource_id", "*")
        raw_action = action_data.get("action_type", "")
        action_name = normalize_str(raw_action.value if hasattr(raw_action, "value") else str(raw_action))

        if res_type == "ec2":
            arn = f"arn:aws:ec2:*:*:instance/{res_id}" if res_id != "*" else "*"
            if "stop" in action_name:
                allowed_actions = ["ec2:DescribeInstances", "ec2:StopInstances"]
            else:
                allowed_actions = ["ec2:DescribeInstances", "ec2:ModifyInstanceAttribute"]
        elif res_type == "ebs":
            arn = f"arn:aws:ec2:*:*:volume/{res_id}" if res_id != "*" else "*"
            if "delete" in action_name or "terminate" in action_name:
                allowed_actions = ["ec2:DescribeVolumes", "ec2:DeleteVolume"]
            else:
                allowed_actions = ["ec2:DescribeVolumes", "ec2:ModifyVolume"]
        elif res_type == "eip":
            arn = "*"
            allowed_actions = ["ec2:DescribeAddresses", "ec2:ReleaseAddress"]
        elif res_type == "rds":
            arn = f"arn:aws:rds:*:*:db:{res_id}" if res_id != "*" else "*"
            if "stop" in action_name:
                allowed_actions = ["rds:DescribeDBInstances", "rds:StopDBInstance", "rds:StartDBInstance"]
            else:
                allowed_actions = ["rds:DescribeDBInstances", "rds:ModifyDBInstance"]
        elif res_type == "s3":
            arn = f"arn:aws:s3:::{res_id}" if res_id != "*" else "*"
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
