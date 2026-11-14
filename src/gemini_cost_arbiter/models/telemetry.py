"""Multi-dimensional AWS telemetry schemas (EC2, RDS, S3, EBS, EIP)."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CloudResourceType(str, Enum):
    """Supported AWS Resource Types."""

    EC2 = "EC2"
    RDS = "RDS"
    S3 = "S3"
    EBS = "EBS"
    EIP = "EIP"


class EC2Metrics(BaseModel):
    """Multi-dimensional utilization telemetry for an AWS EC2 compute instance."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(default="i-default", description="EC2 instance identifier (e.g., i-0123456789abcdef0)")
    current_instance_type: str = Field(default="m5.large", description="Current instance size/family")
    cpu_utilization_avg_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Rolling average CPU utilization")
    cpu_utilization_p95_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="95th percentile peak CPU utilization")
    memory_utilization_avg_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Average memory utilization")
    network_in_out_mbps: float = Field(default=0.0, ge=0.0, description="Combined bandwidth in Mbps")
    network_in_bytes_avg: float = Field(default=0.0, ge=0.0)
    network_out_bytes_avg: float = Field(default=0.0, ge=0.0)
    monthly_spend_usd: float = Field(default=0.0, ge=0.0, description="Current recurring monthly expenditure")
    pricing_model: str = Field(default="on_demand", description="Pricing commitment: on_demand, reserved, savings_plan, spot")
    environment: str = Field(default="production", description="Lifecycle stage: production, staging, development")
    region: str = Field(default="us-east-1", description="AWS operational region")
    tags: Dict[str, str] = Field(default_factory=dict, description="Resource allocation tags")

    @field_validator("cpu_utilization_p95_pct")
    @classmethod
    def validate_p95(cls, p95: float, info) -> float:
        """Ensure p95 metric is at least equal to average."""
        avg = info.data.get("cpu_utilization_avg_pct")
        if avg is not None and p95 < avg:
            return avg
        return p95


class RDSMetrics(BaseModel):
    """Multi-dimensional utilization telemetry for an AWS RDS database instance."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(default="rds-default", description="DB instance identifier")
    current_instance_class: str = Field(default="db.t4g.medium", description="RDS instance class")
    cpu_utilization_avg_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Average database CPU load")
    memory_free_bytes: int = Field(default=0, ge=0, description="Free buffer/RAM bytes")
    storage_allocated_gb: int = Field(default=100, ge=1, description="Allocated disk storage in GB")
    storage_used_gb: float = Field(default=0.0, ge=0.0, description="Actually utilized disk storage in GB")
    free_storage_space_bytes_min: float = Field(default=0.0, ge=0.0)
    active_connections_avg: float = Field(default=0.0, ge=0.0, description="Average active client connections")
    multi_az: bool = Field(default=True, description="Multi-AZ redundancy topology flag")
    monthly_spend_usd: float = Field(default=0.0, ge=0.0, description="Monthly database expenditure")
    pricing_model: str = Field(default="on_demand", description="Pricing commitment: on_demand, reserved, savings_plan, spot")
    environment: str = Field(default="production")
    region: str = Field(default="us-east-1")
    tags: Dict[str, str] = Field(default_factory=dict)


class S3Metrics(BaseModel):
    """Multi-dimensional utilization telemetry for an AWS S3 object storage bucket."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(default="s3-default", description="Bucket name")
    total_storage_gb: float = Field(default=0.0, ge=0.0, description="Total storage consumed in GB")
    bucket_size_bytes_total: float = Field(default=0.0, ge=0.0)
    object_count: int = Field(default=0, ge=0, description="Total object count")
    object_count_total: int = Field(default=0, ge=0)
    current_storage_class: str = Field(default="STANDARD", description="Primary storage class")
    lifecycle_rules_configured: bool = Field(default=False, description="Whether lifecycle policies are present")
    percentage_infrequently_accessed: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of objects unread in > 90 days",
    )
    monthly_spend_usd: float = Field(default=0.0, ge=0.0, description="Monthly storage expenditure")
    region: str = Field(default="us-east-1")
    tags: Dict[str, str] = Field(default_factory=dict)


class EBSMetrics(BaseModel):
    """Utilization telemetry for an AWS Elastic Block Store (EBS) volume."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(default="vol-default", description="EBS volume identifier")
    size_gb: int = Field(default=100, ge=1, description="Volume size in GB")
    volume_type: str = Field(default="gp3", description="EBS volume type (gp3, gp2, io2, etc.)")
    is_attached: bool = Field(default=False, description="Whether volume is attached to an instance")
    days_unattached: int = Field(default=0, ge=0, description="Days detached from compute")
    has_snapshot: bool = Field(default=False, description="Whether at least one snapshot exists")
    monthly_spend_usd: float = Field(default=0.0, ge=0.0, description="Recurring monthly spend for this volume")
    environment: str = Field(default="production")
    region: str = Field(default="us-east-1")
    tags: Dict[str, str] = Field(default_factory=dict)


class EIPMetrics(BaseModel):
    """Utilization telemetry for an unassociated AWS Elastic IP (EIP) address."""

    model_config = ConfigDict(extra="allow")

    resource_id: str = Field(default="eipalloc-default", description="EIP Allocation ID")
    public_ip: str = Field(default="198.51.100.1", description="Allocated public IPv4 address")
    is_associated: bool = Field(default=False, description="Whether mapped to an active ENI/instance")
    days_idle: int = Field(default=0, ge=0, description="Consecutive days unassociated")
    monthly_spend_usd: float = Field(default=3.60, ge=0.0, description="AWS idle IPv4 address charge (~$0.005/hr)")
    region: str = Field(default="us-east-1")
    tags: Dict[str, str] = Field(default_factory=dict)


class CloudTelemetry(BaseModel):
    """Unified telemetry model supporting generic resource mapping."""

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
    ebs_metrics: Optional[EBSMetrics] = None
    eip_metrics: Optional[EIPMetrics] = None


class TelemetryBatch(BaseModel):
    """Batch container for multi-dimensional infrastructure telemetry."""

    model_config = ConfigDict(extra="allow")

    ec2_instances: List[EC2Metrics] = Field(default_factory=list)
    rds_instances: List[RDSMetrics] = Field(default_factory=list)
    s3_buckets: List[S3Metrics] = Field(default_factory=list)
    ebs_volumes: List[EBSMetrics] = Field(default_factory=list)
    elastic_ips: List[EIPMetrics] = Field(default_factory=list)

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
