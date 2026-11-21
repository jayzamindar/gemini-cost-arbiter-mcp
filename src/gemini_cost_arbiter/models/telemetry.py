"""Multi-dimensional AWS telemetry schemas (EC2, RDS, S3, EBS, EIP)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

ResourceIdStr = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:/-]+$")]
InstanceTypeStr = Annotated[str, Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9.-]+$")]
BoundedLabelStr = Annotated[str, Field(min_length=1, max_length=64)]
TagKeyStr = Annotated[str, Field(min_length=1, max_length=128)]
TagValueStr = Annotated[str, Field(max_length=128)]
TagsMap = Annotated[dict[TagKeyStr, TagValueStr], Field(default_factory=dict, max_length=64)]


class CloudResourceType(StrEnum):
    """Supported AWS Resource Types."""

    EC2 = "EC2"
    RDS = "RDS"
    S3 = "S3"
    EBS = "EBS"
    EIP = "EIP"


class EC2Metrics(BaseModel):
    """Multi-dimensional utilization telemetry for an AWS EC2 compute instance."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    resource_id: ResourceIdStr = Field(
        default="i-default",
        description="EC2 instance identifier (e.g., i-0123456789abcdef0)",
    )
    current_instance_type: InstanceTypeStr = Field(
        default="m5.large",
        description="Current instance size/family",
    )
    cpu_utilization_avg_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Rolling average CPU utilization")
    cpu_utilization_p95_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="95th percentile peak CPU utilization",
    )
    memory_utilization_avg_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Average memory utilization")
    network_in_out_mbps: float = Field(default=0.0, ge=0.0, description="Combined bandwidth in Mbps")
    network_in_bytes_avg: float = Field(default=0.0, ge=0.0)
    network_out_bytes_avg: float = Field(default=0.0, ge=0.0)
    monthly_spend_usd: float = Field(default=0.0, ge=0.0, description="Current recurring monthly expenditure")
    pricing_model: BoundedLabelStr = Field(
        default="on_demand",
        description="Pricing commitment: on_demand, reserved, savings_plan, spot",
    )
    environment: BoundedLabelStr = Field(
        default="production",
        description="Lifecycle stage: production, staging, development",
    )
    region: BoundedLabelStr = Field(default="us-east-1", description="AWS operational region")
    tags: TagsMap = Field(default_factory=dict, description="Resource allocation tags")

    @field_validator("cpu_utilization_p95_pct")
    @classmethod
    def validate_p95(cls, p95: float, info: ValidationInfo) -> float:
        """Ensure p95 metric is at least equal to average."""
        avg = info.data.get("cpu_utilization_avg_pct")
        if isinstance(avg, (int, float)) and p95 < float(avg):
            return float(avg)
        return p95


class RDSMetrics(BaseModel):
    """Multi-dimensional utilization telemetry for an AWS RDS database instance."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    resource_id: ResourceIdStr = Field(default="rds-default", description="DB instance identifier")
    current_instance_class: InstanceTypeStr = Field(default="db.t4g.medium", description="RDS instance class")
    cpu_utilization_avg_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Average database CPU load")
    memory_free_bytes: int = Field(default=0, ge=0, description="Free buffer/RAM bytes")
    storage_allocated_gb: int = Field(default=100, ge=1, description="Allocated disk storage in GB")
    storage_used_gb: float = Field(default=0.0, ge=0.0, description="Actually utilized disk storage in GB")
    free_storage_space_bytes_min: float = Field(default=0.0, ge=0.0)
    active_connections_avg: float = Field(default=0.0, ge=0.0, description="Average active client connections")
    multi_az: bool = Field(default=True, description="Multi-AZ redundancy topology flag")
    monthly_spend_usd: float = Field(default=0.0, ge=0.0, description="Monthly database expenditure")
    pricing_model: BoundedLabelStr = Field(
        default="on_demand",
        description="Pricing commitment: on_demand, reserved, savings_plan, spot",
    )
    environment: BoundedLabelStr = Field(default="production")
    region: BoundedLabelStr = Field(default="us-east-1")
    tags: TagsMap = Field(default_factory=dict)


class S3Metrics(BaseModel):
    """Multi-dimensional utilization telemetry for an AWS S3 object storage bucket."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    resource_id: ResourceIdStr = Field(default="s3-default", description="Bucket name")
    total_storage_gb: float = Field(default=0.0, ge=0.0, description="Total storage consumed in GB")
    bucket_size_bytes_total: float = Field(default=0.0, ge=0.0)
    object_count: int = Field(default=0, ge=0, description="Total object count")
    object_count_total: int = Field(default=0, ge=0)
    current_storage_class: BoundedLabelStr = Field(default="STANDARD", description="Primary storage class")
    lifecycle_rules_configured: bool = Field(default=False, description="Whether lifecycle policies are present")
    percentage_infrequently_accessed: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of objects unread in > 90 days",
    )
    monthly_spend_usd: float = Field(default=0.0, ge=0.0, description="Monthly storage expenditure")
    region: BoundedLabelStr = Field(default="us-east-1")
    tags: TagsMap = Field(default_factory=dict)


class EBSMetrics(BaseModel):
    """Utilization telemetry for an AWS Elastic Block Store (EBS) volume."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    resource_id: ResourceIdStr = Field(default="vol-default", description="EBS volume identifier")
    size_gb: int = Field(default=100, ge=1, description="Volume size in GB")
    volume_type: BoundedLabelStr = Field(default="gp3", description="EBS volume type (gp3, gp2, io2, etc.)")
    is_attached: bool = Field(default=False, description="Whether volume is attached to an instance")
    days_unattached: int = Field(default=0, ge=0, description="Days detached from compute")
    has_snapshot: bool = Field(default=False, description="Whether at least one snapshot exists")
    monthly_spend_usd: float = Field(default=0.0, ge=0.0, description="Recurring monthly spend for this volume")
    environment: BoundedLabelStr = Field(default="production")
    region: BoundedLabelStr = Field(default="us-east-1")
    tags: TagsMap = Field(default_factory=dict)


class EIPMetrics(BaseModel):
    """Utilization telemetry for an unassociated AWS Elastic IP (EIP) address."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    resource_id: ResourceIdStr = Field(default="eipalloc-default", description="EIP Allocation ID")
    public_ip: BoundedLabelStr = Field(default="198.51.100.1", description="Allocated public IPv4 address")
    is_associated: bool = Field(default=False, description="Whether mapped to an active ENI/instance")
    days_idle: int = Field(default=0, ge=0, description="Consecutive days unassociated")
    monthly_spend_usd: float = Field(default=3.60, ge=0.0, description="AWS idle IPv4 address charge (~$0.005/hr)")
    region: BoundedLabelStr = Field(default="us-east-1")
    tags: TagsMap = Field(default_factory=dict)


class CloudTelemetry(BaseModel):
    """Unified telemetry model supporting generic resource mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    resource_id: ResourceIdStr = Field(...)
    resource_type: CloudResourceType = Field(...)
    monthly_cost_usd: float = Field(default=0.0, ge=0.0)
    monthly_spend_usd: float = Field(default=0.0, ge=0.0)
    cpu_utilization_avg: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_utilization_avg: float = Field(default=0.0, ge=0.0, le=100.0)
    ec2_metrics: EC2Metrics | None = None
    rds_metrics: RDSMetrics | None = None
    s3_metrics: S3Metrics | None = None
    ebs_metrics: EBSMetrics | None = None
    eip_metrics: EIPMetrics | None = None


class TelemetryBatch(BaseModel):
    """Batch container for multi-dimensional infrastructure telemetry."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    ec2_instances: list[EC2Metrics] = Field(default_factory=list, max_length=500)
    rds_instances: list[RDSMetrics] = Field(default_factory=list, max_length=500)
    s3_buckets: list[S3Metrics] = Field(default_factory=list, max_length=500)
    ebs_volumes: list[EBSMetrics] = Field(default_factory=list, max_length=500)
    elastic_ips: list[EIPMetrics] = Field(default_factory=list, max_length=500)

    @property
    def total_resource_count(self) -> int:
        """Total number of cloud assets in batch."""
        return (
            len(self.ec2_instances)
            + len(self.rds_instances)
            + len(self.s3_buckets)
            + len(self.ebs_volumes)
            + len(self.elastic_ips)
        )

    @property
    def total_monthly_spend_usd(self) -> float:
        """Total current monthly expenditure across all resources."""
        spend = sum(x.monthly_spend_usd for x in self.ec2_instances)
        spend += sum(x.monthly_spend_usd for x in self.rds_instances)
        spend += sum(x.monthly_spend_usd for x in self.s3_buckets)
        spend += sum(x.monthly_spend_usd for x in self.ebs_volumes)
        spend += sum(x.monthly_spend_usd for x in self.elastic_ips)
        return round(spend, 2)
