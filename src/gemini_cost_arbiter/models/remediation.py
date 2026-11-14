"""Remediation and FinOps analytical output models with cryptographic digest."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from gemini_cost_arbiter.models.telemetry import CloudResourceType


class ActionType(str, Enum):
    """Categorized FinOps Remediation Action Types."""

    RIGHTSIZE_INSTANCE = "rightsize_instance"
    STOP_INSTANCE = "stop_instance"
    STOP_DB_INSTANCE = "stop_db_instance"
    TRANSITION_STORAGE_TIER = "transition_storage_tier"
    APPLY_LIFECYCLE_RULE = "apply_lifecycle_rule"
    DELETE_UNATTACHED_STORAGE = "delete_unattached_storage"
    DELETE_UNATTACHED_VOLUME = "delete_unattached_volume"
    RELEASE_ELASTIC_IP = "release_elastic_ip"
    TERMINATE = "TERMINATE"
    DOWNSIZE = "DOWNSIZE"
    IGNORE = "IGNORE"


class RemediationActionItem(BaseModel):
    """Risk-scored, actionable remediation proposal for an AWS resource."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(..., description="Target AWS resource identifier")
    resource_type: CloudResourceType = Field(..., description="Resource category: EC2, RDS, S3, EBS, EIP")
    action_type: ActionType = Field(..., description="Concrete remediation action type")
    target_configuration: str = Field(default="Optimized-Tier", description="Desired state or instance size")
    current_monthly_spend_usd: float = Field(..., description="Current cost in USD/month")
    projected_monthly_spend_usd: float = Field(..., description="Projected post-action cost in USD/month")
    projected_monthly_savings_usd: float = Field(..., description="Net monthly financial savings")
    safety_risk_score: int = Field(..., ge=1, le=5, description="Calibrated risk rating (1=lowest, 5=critical)")
    reasoning_rationale: str = Field(
        default="Automated SRE evaluation optimization profile suggestion.",
        description="Justification and trade-off analysis",
    )
    system_mitigations: List[str] = Field(
        default_factory=list,
        description="Mandatory automated safeguards for risk score >= 3",
    )
    execution_payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Deterministic automation parameters (AWS CLI, Terraform, rollback, IAM policy)",
    )
    quarantined: bool = Field(
        default=False,
        description="Flag indicating action is quarantined pending human SRE review/sign-off",
    )
    quarantine_reason: Optional[str] = Field(
        default=None,
        description="Detailed explanation of why this action was quarantined",
    )

    @model_validator(mode="after")
    def enforce_mitigations_for_high_risk(self) -> "RemediationActionItem":
        """Strictly enforce non-empty system mitigations or explicit quarantine for actions with risk >= 3."""
        if self.safety_risk_score >= 3 and not self.system_mitigations:
            if not self.quarantined:
                raise ValueError(
                    f"Action on '{self.resource_id}' has safety_risk_score={self.safety_risk_score} "
                    f"(>= 3) but contains no system_mitigations. Mandatory mitigations (e.g. automated snapshots, "
                    f"rollback plans) are required for safety compliance, or the action must be quarantined."
                )
        return self


class RemediationPlan(BaseModel):
    """Full remediation plan compiled for an infrastructure evaluation batch."""

    model_config = ConfigDict(extra="allow")

    plan_id: str = Field(..., description="Unique plan UUID")
    created_at: str = Field(..., description="ISO 8601 UTC timestamp")
    actions: List[RemediationActionItem] = Field(default_factory=list, description="Remediation items")
    total_current_monthly_spend_usd: float = Field(..., description="Sum of evaluated resource spend")
    total_projected_monthly_spend_usd: float = Field(..., description="Projected spend after mitigations")
    total_projected_monthly_savings_usd: float = Field(..., description="Total projected net monthly savings")
    average_risk_score: float = Field(default=1.0, description="Mean risk across all proposed actions")
    max_risk_score: int = Field(default=1, description="Peak risk among proposed actions")
    plan_digest: Optional[str] = Field(
        default=None,
        description="SHA-256 cryptographic digest ensuring plan payload integrity and tamper detection",
    )
    plan_signature: Optional[str] = Field(
        default=None,
        description="HMAC-SHA256 cryptographic signature verifying plan authenticity against tampering",
    )


class WasteAnalysisSummary(BaseModel):
    """Executive analytical summary of identified cloud waste."""

    model_config = ConfigDict(extra="allow")

    total_resources_evaluated: int = Field(..., description="Count of resources in batch")
    underutilized_resources_count: int = Field(..., description="Count of resources with detected waste")
    total_monthly_spend_usd: float = Field(..., description="Total batch spend")
    total_monthly_waste_usd: float = Field(..., description="Quantified recoverable spend")
    potential_savings_percentage: float = Field(..., description="Percentage of spend that can be saved")
    key_findings: List[str] = Field(default_factory=list, description="High-level architectural takeaways")
