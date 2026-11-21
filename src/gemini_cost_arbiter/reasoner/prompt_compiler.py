"""Prompt compiler optimizing FinOps telemetry payloads with anti-injection sanitization."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from gemini_cost_arbiter.models.telemetry import TelemetryBatch

MAX_PROMPT_CHARS = 32768

_FALLBACK_SYSTEM_PROMPT = """You are an elite FinOps SRE Cloud-Cost Arbiter.
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


def _resolve_prompts_dir(prompts_dir: Path | None = None) -> Path:
    """Resolve the prompts directory via explicit arg, PROMPTS_DIR env, cwd, or repo root."""
    if prompts_dir is not None:
        return prompts_dir
    env_dir = os.environ.get("PROMPTS_DIR")
    if env_dir is not None and env_dir.strip():
        return Path(env_dir.strip())
    cwd_prompts = Path("prompts")
    if cwd_prompts.is_dir():
        return cwd_prompts
    return Path(__file__).resolve().parents[3] / "prompts"


def load_prompt_file(relative_path: str, prompts_dir: Path | None = None) -> str:
    """Load a prompt file safely, enforcing path traversal containment and UTF-8 encoding."""
    if not isinstance(relative_path, str) or not relative_path.strip() or "\x00" in relative_path:
        raise ValueError("Invalid prompt file path.")
    if Path(relative_path).is_absolute():
        raise ValueError(f"Absolute prompt path not permitted: '{relative_path}'")

    base_dir = _resolve_prompts_dir(prompts_dir).resolve()
    target = (base_dir / relative_path).resolve()
    if not target.is_relative_to(base_dir):
        raise ValueError(f"Path traversal blocked: '{relative_path}' escapes '{base_dir}'.")
    if not target.is_file():
        raise FileNotFoundError(f"Prompt file not found: '{target}'")
    return target.read_text(encoding="utf-8")


def _load_default_system_prompt() -> str:
    try:
        return load_prompt_file("master_system_prompt.md")
    except (FileNotFoundError, OSError):
        return _FALLBACK_SYSTEM_PROMPT


SYSTEM_PROMPT = _load_default_system_prompt()

# Patterns commonly used in prompt injection attempts inside telemetry metadata
INJECTION_PATTERN = re.compile(
    r"(ignore\s+(previous|all)\s+instructions|system\s+prompt|delete\s+(all|database|databases|instance|instances|storage)|drop\s+database|<script|;\s*rm\s+-rf)",
    re.IGNORECASE,
)


def sanitize_string(value: str, max_length: int = 128) -> str:
    """Sanitize freeform string inputs to prevent prompt injection, XML breakout, and token overflow."""
    if not isinstance(value, str):
        value = str(value)
    # NFKC-normalize and strip dangerous control characters / null bytes
    normalized = unicodedata.normalize("NFKC", value)
    cleaned = "".join(ch for ch in normalized if ch.isprintable())
    # Strip XML breakout characters before injection pattern defanging
    cleaned = cleaned.replace("<", "").replace(">", "")
    # Defang injection keywords
    cleaned = INJECTION_PATTERN.sub("[SANITIZED_INJECTION_PATTERN]", cleaned)
    return cleaned[:max_length]


def sanitize_telemetry_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize telemetry metadata and tags before prompt compilation."""
    sanitized: dict[str, Any] = {}
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


def compile_reasoner_prompt(batch: TelemetryBatch, max_chars: int = MAX_PROMPT_CHARS) -> str:
    """Compile batch into condensed, sanitized JSON context wrapped in untrusted data delimiters."""
    raw_dict = batch.model_dump(exclude_none=True, exclude_defaults=True)
    sanitized = sanitize_telemetry_dict(raw_dict)
    compact_json = json.dumps(sanitized, separators=(",", ":"), ensure_ascii=False)

    prefix = "<untrusted_proposal_data>\n"
    suffix = "\n</untrusted_proposal_data>"
    available = max(0, max_chars - len(prefix) - len(suffix))
    if len(compact_json) > available:
        marker = "...[TRUNCATED]"
        if available > len(marker):
            compact_json = compact_json[: available - len(marker)] + marker
        else:
            compact_json = compact_json[:available]

    return f"{prefix}{compact_json}{suffix}"
