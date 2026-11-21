"""Secondary multi-model fallback client using OpenRouter."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.guardrails.risk_scorer import GuardrailEngine
from gemini_cost_arbiter.models.remediation import RemediationActionItem, RemediationPlan
from gemini_cost_arbiter.models.telemetry import TelemetryBatch
from gemini_cost_arbiter.reasoner.circuit_breaker import extract_json
from gemini_cost_arbiter.reasoner.prompt_compiler import SYSTEM_PROMPT, compile_reasoner_prompt

logger = logging.getLogger("gemini_cost_arbiter.openrouter")


class OpenRouterFallbackClient:
    """Secondary fallback LLM client (e.g. Qwen 2.5 Coder via OpenRouter)."""

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
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.openrouter_api_key or ''}",
                },
            )
        return self._internal_client

    async def aclose(self) -> None:
        """Close managed network client."""
        if self._internal_client is not None and not self._internal_client.is_closed:
            await self._internal_client.aclose()
            self._internal_client = None

    async def generate_plan(self, batch: TelemetryBatch) -> RemediationPlan | None:
        """Dispatch evaluation to OpenRouter OpenAI-compatible endpoint with bounded retry."""
        if not self.config.openrouter_api_key:
            return None

        client = await self.get_client()
        url = f"{self.config.openrouter_base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.config.openrouter_api_key}"}

        user_content = compile_reasoner_prompt(batch)

        payload = {
            "model": self.config.secondary_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Telemetry JSON:\n{user_content}"},
            ],
            "temperature": 0.1,
            "max_tokens": self.config.max_output_tokens,
            "response_format": {"type": "json_object"},
        }

        max_retries = 2
        backoff_base = 1.0
        response: httpx.Response | None = None

        for attempt in range(max_retries + 1):
            try:
                response = await client.post(url, headers=headers, json=payload)
                status = getattr(response, "status_code", 200)

                if status in (429, 503) and attempt < max_retries:
                    jitter = random.uniform(0.1, 0.5)
                    delay = (backoff_base * (2**attempt)) + jitter
                    logger.warning(
                        "Upstream OpenRouter API returned HTTP %s (attempt %s/%s). Retrying in %.2fs...",
                        status,
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                if status >= 400:
                    raise RuntimeError(f"OpenRouter HTTP {status}")
                break
            except (httpx.ConnectError, httpx.TimeoutException) as net_err:
                if attempt < max_retries:
                    jitter = random.uniform(0.1, 0.5)
                    delay = (backoff_base * (2**attempt)) + jitter
                    await asyncio.sleep(delay)
                    continue
                raise net_err

        if response is None:
            return None

        data = response.json()
        if isinstance(data.get("usage"), dict):
            self.last_usage_metadata = data["usage"]

        choices = data.get("choices", [])
        if not choices:
            return None

        raw_text = choices[0].get("message", {}).get("content", "")
        if not raw_text:
            return None

        cleaned_text = self._extract_json(raw_text)
        parsed = json.loads(cleaned_text)
        actions: list[RemediationActionItem] = []
        raw_actions = parsed.get("actions", []) if isinstance(parsed, dict) else []

        for item in raw_actions:
            if isinstance(item, dict):
                enriched = GuardrailEngine.audit_and_enrich_action(item)
                actions.append(RemediationActionItem(**enriched))

        current_spend = batch.total_monthly_spend_usd
        projected_savings = round(sum(a.projected_monthly_savings_usd for a in actions), 2)
        projected_spend = round(max(0.0, current_spend - projected_savings), 2)
        avg_risk = round(sum(a.safety_risk_score for a in actions) / len(actions), 2) if actions else 1.0
        max_risk = max([a.safety_risk_score for a in actions], default=1)

        return RemediationPlan(
            plan_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC).isoformat(),
            actions=actions,
            total_current_monthly_spend_usd=current_spend,
            total_projected_monthly_spend_usd=projected_spend,
            total_projected_monthly_savings_usd=projected_savings,
            average_risk_score=avg_risk,
            max_risk_score=max_risk,
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip <think>...</think> blocks and markdown code fences if present."""
        return extract_json(text)
