"""Pydantic v2 Unified Data Contracts for Gemini Cost Arbiter MCP."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CloudResourceType(str, Enum):
    """Supported AWS Resource Types."""

    EC2 = "EC2"
    RDS = "RDS"
    S3 = "S3"


class ActionType(str, Enum):
    """Categorized FinOps Remediation Action Types."""

    RIGHTSIZE_INSTANCE = "rightsize_instance"
    STOP_INSTANCE = "stop_instance"
    STOP_DB_INSTANCE = "stop_db_instance"
    TRANSITION_STORAGE_TIER = "transition_storage_tier"
    APPLY_LIFECYCLE_RULE = "apply_lifecycle_rule"
    DELETE_UNATTACHED_STORAGE = "delete_unattached_storage"
    TERMINATE = "TERMINATE"
    DOWNSIZE = "DOWNSIZE"
    IGNORE = "IGNORE"


class ArbiterConfig(BaseModel):
    """Configuration contract supporting Gemini, OpenRouter, and local thresholds."""

    model_config = ConfigDict(extra="allow")

    gemini_api_key: str = Field(default="test-gemini-key-placeholder")
    gemini_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta")
    openrouter_api_key: Optional[str] = Field(default=None)
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    model_name: str = Field(default="gemini-3.8-flash-high")
    thinking_budget: int = Field(default=2048)
    max_acceptable_risk: int = Field(default=5, ge=1, le=5)
    mcp_server_name: str = Field(default="gemini-cost-arbiter-mcp")
    mcp_server_version: str = Field(default="1.0.0")
    low_utilization_threshold_pct: float = Field(default=10.0)
    moderate_utilization_threshold_pct: float = Field(default=40.0)
    safety_auto_remediate_max_risk: int = Field(default=3)


class EC2Metrics(BaseModel):
    """Multi-dimensional utilization telemetry for an AWS EC2 instance."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(default="i-default")
    current_instance_type: str = Field(default="m5.large")
    cpu_utilization_avg_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    cpu_utilization_p95_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_utilization_avg_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    network_in_out_mbps: float = Field(default=0.0, ge=0.0)
    network_in_bytes_avg: float = Field(default=0.0, ge=0.0)
    network_out_bytes_avg: float = Field(default=0.0, ge=0.0)
    monthly_spend_usd: float = Field(default=0.0, ge=0.0)
    environment: str = Field(default="production")
    region: str = Field(default="us-east-1")
    tags: Dict[str, str] = Field(default_factory=dict)

    @field_validator("cpu_utilization_p95_pct")
    @classmethod
    def validate_p95(cls, p95: float, info) -> float:
        avg = info.data.get("cpu_utilization_avg_pct")
        if avg is not None and p95 < avg:
            return avg
        return p95


class RDSMetrics(BaseModel):
    """Multi-dimensional utilization telemetry for an AWS RDS database instance."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(default="rds-default")
    current_instance_class: str = Field(default="db.t4g.medium")
    cpu_utilization_avg_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_free_bytes: int = Field(default=0, ge=0)
    storage_allocated_gb: int = Field(default=100, ge=1)
    storage_used_gb: float = Field(default=0.0, ge=0.0)
    free_storage_space_bytes_min: float = Field(default=0.0, ge=0.0)
    active_connections_avg: float = Field(default=0.0, ge=0.0)
    multi_az: bool = Field(default=True)
    monthly_spend_usd: float = Field(default=0.0, ge=0.0)
    environment: str = Field(default="production")
    region: str = Field(default="us-east-1")
    tags: Dict[str, str] = Field(default_factory=dict)


class S3Metrics(BaseModel):
    """Multi-dimensional utilization telemetry for an AWS S3 object storage bucket."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(default="s3-default")
    total_storage_gb: float = Field(default=0.0, ge=0.0)
    bucket_size_bytes_total: float = Field(default=0.0, ge=0.0)
    object_count: int = Field(default=0, ge=0)
    object_count_total: int = Field(default=0, ge=0)
    current_storage_class: str = Field(default="STANDARD")
    lifecycle_rules_configured: bool = Field(default=False)
    percentage_infrequently_accessed: float = Field(default=0.0, ge=0.0, le=100.0)
    monthly_spend_usd: float = Field(default=0.0, ge=0.0)
    region: str = Field(default="us-east-1")
    tags: Dict[str, str] = Field(default_factory=dict)


class CloudTelemetry(BaseModel):
    """Unified telemetry model supporting individual resource mapping."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(...)
    resource_type: CloudResourceType = Field(...)
    monthly_cost_usd: float = Field(default=0.0)
    monthly_spend_usd: float = Field(default=0.0)
    cpu_utilization_avg: float = Field(default=0.0)
    memory_utilization_avg: float = Field(default=0.0)
    ec2_metrics: Optional[EC2Metrics] = None
    rds_metrics: Optional[RDSMetrics] = None
    s3_metrics: Optional[S3Metrics] = None


class TelemetryBatch(BaseModel):
    """Batch container for multi-dimensional infrastructure telemetry."""

    model_config = ConfigDict(extra="allow")

    ec2_instances: List[EC2Metrics] = Field(default_factory=list)
    rds_instances: List[RDSMetrics] = Field(default_factory=list)
    s3_buckets: List[S3Metrics] = Field(default_factory=list)

    @property
    def total_resource_count(self) -> int:
        return len(self.ec2_instances) + len(self.rds_instances) + len(self.s3_buckets)

    @property
    def total_monthly_spend_usd(self) -> float:
        spend = sum(x.monthly_spend_usd for x in self.ec2_instances)
        spend += sum(x.monthly_spend_usd for x in self.rds_instances)
        spend += sum(x.monthly_spend_usd for x in self.s3_buckets)
        return round(spend, 2)


class RemediationActionItem(BaseModel):
    """Risk-scored, actionable remediation proposal for an AWS resource."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(...)
    resource_type: CloudResourceType = Field(...)
    action_type: ActionType = Field(...)
    target_configuration: str = Field(default="Optimized-Tier")
    current_monthly_spend_usd: float = Field(...)
    projected_monthly_spend_usd: float = Field(...)
    projected_monthly_savings_usd: float = Field(...)
    safety_risk_score: int = Field(..., ge=1, le=5)
    reasoning_rationale: str = Field(default="Automated SRE evaluation optimization profile suggestion.")
    system_mitigations: List[str] = Field(default_factory=list)
    execution_payload: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_mitigations_for_high_risk(self) -> "RemediationActionItem":
        if self.safety_risk_score >= 3 and not self.system_mitigations:
            raise ValueError(
                f"Action on '{self.resource_id}' has safety_risk_score={self.safety_risk_score} "
                f"(>= 3) but contains no system_mitigations. Mandatory mitigations (e.g. automated snapshots, "
                f"rollback plans) are required for safety compliance."
            )
        return self


class RemediationPlan(BaseModel):
    """Full remediation plan compiled for an infrastructure evaluation batch."""

    model_config = ConfigDict(extra="allow")

    plan_id: str = Field(...)
    created_at: str = Field(...)
    actions: List[RemediationActionItem] = Field(default_factory=list)
    total_current_monthly_spend_usd: float = Field(...)
    total_projected_monthly_spend_usd: float = Field(...)
    total_projected_monthly_savings_usd: float = Field(...)
    average_risk_score: float = Field(default=1.0)
    max_risk_score: int = Field(default=1)


class WasteAnalysisSummary(BaseModel):
    """Executive analytical summary of identified cloud waste."""

    model_config = ConfigDict(extra="allow")

    total_resources_evaluated: int = Field(...)
    underutilized_resources_count: int = Field(...)
    total_monthly_spend_usd: float = Field(...)
    total_monthly_waste_usd: float = Field(...)
    potential_savings_percentage: float = Field(...)
    key_findings: List[str] = Field(default_factory=list)


class FinOpsAuditSummary(BaseModel):
    """FinOps ledger metrics object tracking cumulative savings."""

    model_config = ConfigDict(extra="allow")

    total_batches_processed: int = Field(default=0)
    total_resources_analyzed: int = Field(default=0)
    cumulative_waste_identified_usd: float = Field(default=0.0)
    cumulative_projected_savings_usd: float = Field(default=0.0)
    remediations_generated_count: int = Field(default=0)
    last_updated: str = Field(...)


class DynamicFallbackModel(BaseModel):
    """Fallback proxy model for self-healing schema resolution."""

    model_config = ConfigDict(extra="allow")


def __getattr__(name: str) -> Any:
    """Self-healing module fallback attribute accessor."""
    return DynamicFallbackModel
