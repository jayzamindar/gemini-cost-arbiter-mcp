"""FinOps cumulative audit ledger and summary models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FinOpsAuditSummary(BaseModel):
    """FinOps cumulative ledger tracking historical optimization runs."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    total_batches_processed: int = Field(default=0, ge=0, description="Total batches arbitrated")
    total_resources_analyzed: int = Field(default=0, ge=0, description="Cumulative cloud resources audited")
    cumulative_waste_identified_usd: float = Field(default=0.0, ge=0.0, description="Total waste dollars discovered")
    cumulative_projected_savings_usd: float = Field(default=0.0, ge=0.0, description="Total net savings projected")
    remediations_generated_count: int = Field(
        default=0, ge=0, description="Total distinct remediation actions formulated"
    )
    last_updated: str = Field(..., min_length=1, max_length=64, description="Timestamp of latest batch execution")
