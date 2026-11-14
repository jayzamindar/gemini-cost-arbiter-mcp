"""Secondary multi-model fallback client using OpenRouter."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.guardrails.risk_scorer import GuardrailEngine
from gemini_cost_arbiter.models.remediation import RemediationActionItem, RemediationPlan
from gemini_cost_arbiter.models.telemetry import TelemetryBatch
from gemini_cost_arbiter.reasoner.prompt_compiler import SYSTEM_PROMPT, compile_reasoner_prompt

logger = logging.getLogger("gemini_cost_arbiter.openrouter")


class OpenRouterFallbackClient:
    """Secondary fallback LLM client (e.g. Qwen 2.5 Coder via OpenRouter)."""

    def __init__(self, config: ArbiterConfig, http_client: Optional[httpx.AsyncClient] = None) -> None:
        self.config = config
        self._custom_client = http_client
        self._internal_client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Retrieve active HTTP client."""
        if self._custom_client is not None:
            return self._custom_client
        if self._internal_client is None or self._internal_client.is_closed:
            self._internal_client = httpx.AsyncClient(
                timeout=httpx.Timeout(45.0, connect=10.0),
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

    async def generate_plan(self, batch: TelemetryBatch) -> Optional[RemediationPlan]:
        """Dispatch evaluation to OpenRouter OpenAI-compatible endpoint."""
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
            "response_format": {"type": "json_object"},
        }

        response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"OpenRouter HTTP {response.status_code}")

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return None

        raw_text = choices[0].get("message", {}).get("content", "")
        if not raw_text:
            return None

        # Strip <think>...</think> reasoning blocks (e.g. DeepSeek R1 / Qwen 2.5) and markdown code fences
        cleaned_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_text)
        if fence_match:
            cleaned_text = fence_match.group(1).strip()
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        parsed = json.loads(cleaned_text)
        actions: List[RemediationActionItem] = []
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
            created_at=datetime.now(timezone.utc).isoformat(),
            actions=actions,
            total_current_monthly_spend_usd=current_spend,
            total_projected_monthly_spend_usd=projected_spend,
            total_projected_monthly_savings_usd=projected_savings,
            average_risk_score=avg_risk,
            max_risk_score=max_risk,
        )
