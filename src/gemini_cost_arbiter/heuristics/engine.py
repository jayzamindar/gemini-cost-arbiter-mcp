"""Deterministic Heuristic SRE Engine.

Acts as high-availability fallback when upstream AI APIs are degraded or unavailable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from gemini_cost_arbiter.heuristics.ebs_rules import evaluate_ebs_volume
from gemini_cost_arbiter.heuristics.ec2_rules import evaluate_ec2_instance
from gemini_cost_arbiter.heuristics.eip_rules import evaluate_elastic_ip
from gemini_cost_arbiter.heuristics.rds_rules import evaluate_rds_instance
from gemini_cost_arbiter.heuristics.s3_rules import evaluate_s3_bucket
from gemini_cost_arbiter.models.remediation import RemediationActionItem, RemediationPlan
from gemini_cost_arbiter.models.telemetry import TelemetryBatch


class DeterministicHeuristicEngine:
    """Evaluates telemetry with deterministic FinOps rules."""

    @staticmethod
    def evaluate(batch: TelemetryBatch) -> RemediationPlan:
        """Run all heuristic rules against a telemetry batch."""
        actions: List[RemediationActionItem] = []

        # 1. EC2 Evaluation
        for ec2 in batch.ec2_instances:
            item = evaluate_ec2_instance(ec2)
            if item is not None:
                actions.append(item)

        # 2. RDS Evaluation
        for rds in batch.rds_instances:
            item = evaluate_rds_instance(rds)
            if item is not None:
                actions.append(item)

        # 3. S3 Evaluation
        for s3 in batch.s3_buckets:
            item = evaluate_s3_bucket(s3)
            if item is not None:
                actions.append(item)

        # 4. EBS Evaluation
        for ebs in batch.ebs_volumes:
            item = evaluate_ebs_volume(ebs)
            if item is not None:
                actions.append(item)

        # 5. EIP Evaluation
        for eip in batch.elastic_ips:
            item = evaluate_elastic_ip(eip)
            if item is not None:
                actions.append(item)

        current_spend = batch.total_monthly_spend_usd
        projected_savings = round(sum(a.projected_monthly_savings_usd for a in actions), 2)
        projected_spend = round(max(0.0, current_spend - projected_savings), 2)
        avg_risk = round(sum(a.safety_risk_score for a in actions) / len(actions), 2) if actions else 1.0
        max_risk = max([a.safety_risk_score for a in actions], default=1)

        return RemediationPlan(
            plan_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            actions=actions,
            total_current_monthly_spend_usd=current_spend,
            total_projected_monthly_spend_usd=projected_spend,
            total_projected_monthly_savings_usd=projected_savings,
            average_risk_score=avg_risk,
            max_risk_score=max_risk,
        )
