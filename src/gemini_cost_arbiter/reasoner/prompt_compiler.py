"""Prompt compiler optimizing FinOps telemetry payloads with anti-injection sanitization."""

from __future__ import annotations

import json
import re
from typing import Any, Dict
from gemini_cost_arbiter.models.telemetry import TelemetryBatch

SYSTEM_PROMPT = """You are an elite FinOps SRE Cloud-Cost Arbiter.
Your objective is to ingest raw AWS infrastructure utilization telemetry (EC2, RDS, S3, EBS, EIP),
detect compute, memory, and storage waste, and synthesize deterministic, risk-scored
remediation execution payloads.

Rules:
1. Every proposed action must be classified with a Safety Risk Score from 1 (lowest) to 5 (critical).
2. If safety_risk_score >= 3, system_mitigations must NOT be empty (must include pre-execution snapshots and rollback instructions).
3. Quantify projected dollar savings accurately based on current monthly spend.
4. Output must strictly conform to the provided JSON schema.
5. Strictly adhere to verified AWS instance types (never hallucinate non-existent instance sizes or pricing).
"""

# Patterns commonly used in prompt injection attempts inside telemetry metadata
INJECTION_PATTERN = re.compile(
    r"(ignore\s+(previous|all)\s+instructions|system\s+prompt|delete\s+(all|database|databases|instance|instances|storage)|drop\s+database|<script|;\s*rm\s+-rf)",
    re.IGNORECASE,
)


def sanitize_string(value: str, max_length: int = 128) -> str:
    """Sanitize freeform string inputs to prevent prompt injection and token overflow."""
    if not isinstance(value, str):
        return str(value)
    # Strip dangerous control characters and null bytes
    cleaned = "".join(ch for ch in value if ch.isprintable())
    # Defang injection keywords
    cleaned = INJECTION_PATTERN.sub("[SANITIZED_INJECTION_PATTERN]", cleaned)
    return cleaned[:max_length]


def sanitize_telemetry_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize telemetry metadata and tags before prompt compilation."""
    sanitized: Dict[str, Any] = {}
    for key, value in data.items():
        clean_key = sanitize_string(key, max_length=64)
        if isinstance(value, str):
            sanitized[clean_key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[clean_key] = sanitize_telemetry_dict(value)
        elif isinstance(value, list):
            sanitized[clean_key] = [
                sanitize_telemetry_dict(v) if isinstance(v, dict) else (sanitize_string(v) if isinstance(v, str) else v)
                for v in value
            ]
        else:
            sanitized[clean_key] = value
    return sanitized


def compile_reasoner_prompt(batch: TelemetryBatch) -> str:
    """Compile batch into condensed, sanitized JSON context with zero token bloat."""
    raw_dict = batch.model_dump()
    sanitized = sanitize_telemetry_dict(raw_dict)
    return json.dumps(sanitized, separators=(",", ":"))
