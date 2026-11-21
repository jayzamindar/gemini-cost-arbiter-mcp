"""Asynchronous Google Gemini 3.8 Flash High Client with Thinking Budget and Schema Egress."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.guardrails.risk_scorer import GuardrailEngine
from gemini_cost_arbiter.models.remediation import RemediationActionItem, RemediationPlan
from gemini_cost_arbiter.models.telemetry import TelemetryBatch
from gemini_cost_arbiter.reasoner.prompt_compiler import SYSTEM_PROMPT, compile_reasoner_prompt

logger = logging.getLogger("gemini_cost_arbiter.reasoner")

ALLOWED_GEMINI_FIELDS = {
    "type",
    "format",
    "description",
    "nullable",
    "enum",
    "items",
    "properties",
    "required",
    "propertyOrdering",
}


def clean_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively dereference and sanitize Pydantic v2 JSON Schema for Gemini REST API compatibility.

    Enforces an explicit allowlist of valid google.ai.generativelanguage.v1beta.Schema fields,
    inlines all $ref pointers, collapses anyOf with null to nullable=True while preserving
    sibling metadata (such as description), excludes 'execution_payload' from LLM egress,
    and raises ValueError on unresolved or cyclic $ref pointers.
    """
    schema_copy = copy.deepcopy(schema)
    defs = schema_copy.pop("$defs", {})

    def _inline_refs(node: Any, seen_refs: set[str] | None = None) -> Any:
        if seen_refs is None:
            seen_refs = set()

        if isinstance(node, dict):
            # Detect and resolve $ref pointers
            if "$ref" in node:
                ref_val = node["$ref"]
                if ref_val in seen_refs:
                    raise ValueError(f"Cyclic $ref detected in schema: {ref_val}")
                ref_key = ref_val.split("/")[-1]
                if ref_key not in defs:
                    raise ValueError(f"Unresolved $ref in schema: {ref_val}")
                resolved = copy.deepcopy(defs[ref_key])
                return _inline_refs(resolved, seen_refs | {ref_val})

            # Detect Pydantic v2 Optional / Union patterns:
            # - {"anyOf": [{"type": "..."}, {"type": "null"}]} -> {"type": "...", "nullable": True}
            # - Multi-branch {"anyOf": [{"type": "string"}, {"type": "integer"}, ...]} -> select first non-null branch
            if "anyOf" in node and isinstance(node["anyOf"], list):
                non_null = [b for b in node["anyOf"] if isinstance(b, dict) and b.get("type") != "null"]
                has_null = any(isinstance(b, dict) and b.get("type") == "null" for b in node["anyOf"])
                if non_null:
                    collapsed = _inline_refs(copy.deepcopy(non_null[0]), seen_refs)
                    if not isinstance(collapsed, dict) or not collapsed:
                        collapsed = {"type": "string"}
                    if has_null:
                        collapsed["nullable"] = True
                    for k, v in node.items():
                        if k in ALLOWED_GEMINI_FIELDS and k not in (
                            "anyOf",
                            "type",
                            "nullable",
                            "properties",
                            "items",
                        ):
                            collapsed[k] = _inline_refs(v, seen_refs)
                    return collapsed
                if has_null:
                    collapsed = {"type": "string", "nullable": True}
                    for k, v in node.items():
                        if k in ALLOWED_GEMINI_FIELDS and k not in ("anyOf", "type", "nullable", "properties", "items"):
                            collapsed[k] = _inline_refs(v, seen_refs)
                    return collapsed

            cleaned: dict[str, Any] = {}
            for k, v in node.items():
                if k not in ALLOWED_GEMINI_FIELDS:
                    continue

                if k == "properties" and isinstance(v, dict):
                    cleaned_props = {}
                    for prop_name, prop_schema in v.items():
                        if prop_name == "execution_payload":
                            # Exclude execution_payload from LLM responseSchema as GuardrailEngine synthesizes it
                            continue
                        cleaned_props[prop_name] = _inline_refs(prop_schema, seen_refs)
                    cleaned["properties"] = cleaned_props
                elif k == "required" and isinstance(v, list):
                    cleaned["required"] = [r for r in v if r != "execution_payload"]
                elif k == "items":
                    cleaned["items"] = _inline_refs(v, seen_refs)
                else:
                    cleaned[k] = _inline_refs(v, seen_refs)

            return cleaned

        elif isinstance(node, list):
            return [_inline_refs(item, seen_refs) for item in node]
        return node

    return cast(dict[str, Any], _inline_refs(schema_copy))


class GeminiReasonerClient:
    """Client for Google Gemini 3.8 Flash High with thinking budget and constrained schema egress."""

    def __init__(self, config: ArbiterConfig, http_client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._custom_client = http_client
        self._internal_client: httpx.AsyncClient | None = None
        self.last_usage_metadata: dict[str, Any] = {}

    async def get_client(self) -> httpx.AsyncClient:
        """Retrieve active HTTP client."""
        if self._custom_client is not None:
            return self._custom_client
        if self._internal_client is None or self._internal_client.is_closed:
            self._internal_client = httpx.AsyncClient(
                timeout=httpx.Timeout(45.0, connect=10.0),
                headers={"Content-Type": "application/json"},
            )
        return self._internal_client

    async def aclose(self) -> None:
        """Close managed network client."""
        if self._internal_client is not None and not self._internal_client.is_closed:
            await self._internal_client.aclose()
            self._internal_client = None

    async def generate_plan(self, batch: TelemetryBatch) -> RemediationPlan | None:
        """Dispatch telemetry evaluation to Gemini 3.8 Flash High with exponential retry."""
        client = await self.get_client()
        url = f"{self.config.gemini_base_url}/models/{self.config.model_name}:generateContent"
        params = {"key": self.config.gemini_api_key}

        user_content = compile_reasoner_prompt(batch)

        raw_schema = RemediationPlan.model_json_schema()
        cleaned_schema = clean_gemini_schema(raw_schema)

        generation_config: dict[str, Any] = {
            "temperature": 0.1,
            "maxOutputTokens": 16384,
            "responseMimeType": "application/json",
            "responseSchema": cleaned_schema,
        }

        # Inject Thinking Budget for Gemini 3.8 Flash High if configured
        if self.config.thinking_budget > 0:
            generation_config["thinkingConfig"] = {"thinkingBudget": self.config.thinking_budget}

        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "generationConfig": generation_config,
        }

        # Exponential backoff retry loop for transient HTTP 429 and 503 errors
        max_retries = 2
        backoff_base = 1.0
        response: httpx.Response | None = None

        for attempt in range(max_retries + 1):
            try:
                response = await client.post(url, params=params, json=payload)
                status = getattr(response, "status_code", 200)

                if status in (429, 503) and attempt < max_retries:
                    jitter = random.uniform(0.1, 0.5)
                    delay = (backoff_base * (2**attempt)) + jitter
                    logger.warning(
                        "Upstream Gemini API returned HTTP %s (attempt %s/%s). Retrying in %.2fs...",
                        status,
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                if status >= 400:
                    response.raise_for_status()
                break
            except (httpx.ConnectError, httpx.TimeoutException) as net_err:
                if attempt < max_retries:
                    await asyncio.sleep(backoff_base * (2**attempt))
                    continue
                raise net_err

        if response is None:
            return None

        data = response.json()

        # Capture usage token telemetry if available
        if "usageMetadata" in data:
            self.last_usage_metadata = data["usageMetadata"]

        candidates = data.get("candidates", [])
        if not candidates:
            return None

        parts = candidates[0].get("content", {}).get("parts", [])
        raw_text = "".join(p.get("text", "") for p in parts if "text" in p)
        if not raw_text:
            return None

        clean_json = self._extract_json(raw_text)
        parsed = json.loads(clean_json)

        # Parse and enrich actions via GuardrailEngine
        actions: list[RemediationActionItem] = []
        raw_actions = (
            parsed.get("actions", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
        )

        for item in raw_actions:
            if isinstance(item, dict):
                enriched = GuardrailEngine.audit_and_enrich_action(item)
                actions.append(RemediationActionItem(**enriched))

        current_spend = batch.total_monthly_spend_usd
        projected_savings = round(sum(a.projected_monthly_savings_usd for a in actions), 2)
        projected_spend = round(max(0.0, current_spend - projected_savings), 2)
        avg_risk = round(sum(a.safety_risk_score for a in actions) / len(actions), 2) if actions else 1.0
        max_risk = max([a.safety_risk_score for a in actions], default=1)

        raw_plan = RemediationPlan(
            plan_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC).isoformat(),
            actions=actions,
            total_current_monthly_spend_usd=current_spend,
            total_projected_monthly_spend_usd=projected_spend,
            total_projected_monthly_savings_usd=projected_savings,
            average_risk_score=avg_risk,
            max_risk_score=max_risk,
        )

        # Calculate cryptographic digest and HMAC signature
        return GuardrailEngine.attach_plan_digest(raw_plan, secret=self.config.plan_signing_secret)

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip markdown code fence if present."""
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```", 1)[1].split("```", 1)[0]
        return cleaned.strip()
