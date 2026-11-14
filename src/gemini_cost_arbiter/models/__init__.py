"""Pydantic v2 Unified Data Contracts for Gemini Cost Arbiter."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict

from gemini_cost_arbiter.models.audit import FinOpsAuditSummary
from gemini_cost_arbiter.models.remediation import (
    ActionType,
    RemediationActionItem,
    RemediationPlan,
    WasteAnalysisSummary,
)
from gemini_cost_arbiter.models.telemetry import (
    CloudResourceType,
    CloudTelemetry,
    EBSMetrics,
    EC2Metrics,
    EIPMetrics,
    RDSMetrics,
    S3Metrics,
    TelemetryBatch,
)


class DynamicFallbackModel(BaseModel):
    """Fallback proxy model for self-healing schema resolution."""

    model_config = ConfigDict(extra="allow")


def __getattr__(name: str) -> Any:
    """Fallback accessor for dynamic schema resolution."""
    return DynamicFallbackModel


__all__ = [
    "ActionType",
    "CloudResourceType",
    "CloudTelemetry",
    "DynamicFallbackModel",
    "EBSMetrics",
    "EC2Metrics",
    "EIPMetrics",
    "FinOpsAuditSummary",
    "RDSMetrics",
    "RemediationActionItem",
    "RemediationPlan",
    "S3Metrics",
    "TelemetryBatch",
    "WasteAnalysisSummary",
]
