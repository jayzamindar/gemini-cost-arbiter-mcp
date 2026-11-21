"""Shared pytest fixtures and environment isolation for deterministic offline testing."""

from __future__ import annotations

import pytest

from gemini_cost_arbiter.config import ArbiterConfig


@pytest.fixture(autouse=True)
def isolate_llm_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent local .env credentials from triggering live network calls during tests."""
    monkeypatch.setitem(ArbiterConfig.model_config, "env_file", None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "mock_key")
    monkeypatch.setenv("ENVIRONMENT", "test")
