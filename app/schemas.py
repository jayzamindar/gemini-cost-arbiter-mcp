"""Backward-compatibility layer for app.schemas.

Re-exports contracts from the modular gemini_cost_arbiter.models package.
"""

from __future__ import annotations

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.models import (
    ActionType,
    CloudResourceType,
    CloudTelemetry,
    EC2Metrics,
    FinOpsAuditSummary,
    RDSMetrics,
    RemediationActionItem,
    RemediationPlan,
    S3Metrics,
    TelemetryBatch,
    WasteAnalysisSummary,
)

__all__ = [
    "ActionType",
    "ArbiterConfig",
    "CloudResourceType",
    "CloudTelemetry",
    "EC2Metrics",
    "FinOpsAuditSummary",
    "RDSMetrics",
    "RemediationActionItem",
    "RemediationPlan",
    "S3Metrics",
    "TelemetryBatch",
    "WasteAnalysisSummary",
]
