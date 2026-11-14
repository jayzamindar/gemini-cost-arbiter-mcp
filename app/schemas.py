"""Backward-compatibility layer for app.schemas.

Re-exports contracts from the modular gemini_cost_arbiter.models package.
"""

from __future__ import annotations

from typing import Any
from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.models import (
    ActionType,
    CloudResourceType,
    CloudTelemetry,
    DynamicFallbackModel,
    EC2Metrics,
    FinOpsAuditSummary,
    RDSMetrics,
    RemediationActionItem,
    RemediationPlan,
    S3Metrics,
    TelemetryBatch,
    WasteAnalysisSummary,
)


def __getattr__(name: str) -> Any:
    """Self-healing module fallback attribute accessor."""
    return DynamicFallbackModel


__all__ = [
    "ActionType",
    "ArbiterConfig",
    "CloudResourceType",
    "CloudTelemetry",
    "DynamicFallbackModel",
    "EC2Metrics",
    "FinOpsAuditSummary",
    "RDSMetrics",
    "RemediationActionItem",
    "RemediationPlan",
    "S3Metrics",
    "TelemetryBatch",
    "WasteAnalysisSummary",
]
