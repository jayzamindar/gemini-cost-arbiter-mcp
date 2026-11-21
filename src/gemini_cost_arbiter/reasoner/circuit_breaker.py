"""LLM quota, cost, and consecutive-failure circuit breakers plus JSON extraction."""

from __future__ import annotations

import re
import threading
import time
from datetime import UTC, date, datetime


def extract_json(text: str) -> str:
    """Strip <think>...</think> reasoning blocks and markdown code fences before JSON parsing."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, flags=re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return cleaned


class LLMQuotaCircuitBreaker:
    """Thread-safe circuit breaker enforcing token budgets, daily UTC USD spend, and failure cooldowns."""

    def __init__(
        self,
        max_session_token_budget: int = 500000,
        daily_api_cost_limit_usd: float = 10.0,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.max_session_token_budget = max_session_token_budget
        self.daily_api_cost_limit_usd = daily_api_cost_limit_usd
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

        self._lock = threading.RLock()
        self.session_tokens_used: int = 0
        self.daily_cost_usd: float = 0.0
        self._cost_date: date = datetime.now(UTC).date()
        self.consecutive_failures: int = 0
        self._cooldown_until: float | None = None

    def _rollover_daily_cost_if_needed(self) -> None:
        """Reset daily USD spend counter when the UTC calendar date advances."""
        today = datetime.now(UTC).date()
        if today != self._cost_date:
            self.daily_cost_usd = 0.0
            self._cost_date = today

    def trip_reason(self) -> str | None:
        """Return the active circuit-breaker trip reason, or None if requests are permitted."""
        with self._lock:
            self._rollover_daily_cost_if_needed()
            if self.session_tokens_used >= self.max_session_token_budget:
                return "session_token_budget_exceeded"
            if self.daily_cost_usd >= self.daily_api_cost_limit_usd:
                return "daily_api_cost_limit_exceeded"
            if self._cooldown_until is not None:
                if time.monotonic() < self._cooldown_until:
                    return "consecutive_failure_cooldown"
                self._cooldown_until = None
                self.consecutive_failures = 0
            return None

    def allow_request(self) -> bool:
        """Return True if LLM calls are permitted under all quota and failure thresholds."""
        return self.trip_reason() is None

    def record_success(self, tokens_used: int = 0, estimated_cost_usd: float = 0.0) -> None:
        """Record a successful LLM call, resetting consecutive failures and updating quotas."""
        with self._lock:
            self._rollover_daily_cost_if_needed()
            self.consecutive_failures = 0
            self._cooldown_until = None
            if tokens_used > 0:
                self.session_tokens_used += tokens_used
            if estimated_cost_usd > 0.0:
                self.daily_cost_usd = round(self.daily_cost_usd + estimated_cost_usd, 6)

    def record_failure(self) -> None:
        """Record a failed LLM call and trip the cooldown timer when threshold is reached."""
        with self._lock:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.failure_threshold:
                self._cooldown_until = time.monotonic() + self.cooldown_seconds

    @staticmethod
    def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate USD cost using conservative Flash-tier per-million token rates."""
        input_cost = (max(0, prompt_tokens) / 1_000_000.0) * 0.15
        output_cost = (max(0, completion_tokens) / 1_000_000.0) * 0.60
        return round(input_cost + output_cost, 6)
