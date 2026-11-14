"""Runtime configuration contracts using Pydantic Settings."""

from __future__ import annotations

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ArbiterConfig(BaseSettings):
    """Centralized runtime configuration with environment variable precedence."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    # Google Gemini Configuration
    gemini_api_key: str = Field(
        default="test-gemini-key-placeholder",
        validation_alias="GEMINI_API_KEY",
        description="Google Gemini API authentication token.",
    )
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        validation_alias="GEMINI_BASE_URL",
        description="Base URL for Google Gemini API.",
    )
    model_name: str = Field(
        default="gemini-3.8-flash-high",
        validation_alias="DEFAULT_MODEL",
        description="Primary reasoning model identifier.",
    )
    thinking_budget: int = Field(
        default=2048,
        validation_alias="THINKING_BUDGET",
        ge=0,
        le=8192,
        description="Reasoning thinking budget in tokens for Gemini 3.8 Flash High.",
    )

    # Multi-Model Secondary Fallback (OpenRouter)
    openrouter_api_key: Optional[str] = Field(
        default=None,
        validation_alias="OPENROUTER_API_KEY",
        description="Optional OpenRouter API token for multi-model fallback.",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias="OPENROUTER_BASE_URL",
        description="Base URL for OpenRouter API.",
    )
    secondary_model: str = Field(
        default="qwen/qwen-2.5-coder-32b-instruct",
        validation_alias="SECONDARY_MODEL",
        description="Secondary fallback model identifier.",
    )

    # FinOps Guardrails & Risk Thresholds
    max_acceptable_risk: int = Field(
        default=5,
        ge=1,
        le=5,
        validation_alias="MAX_ACCEPTABLE_RISK",
        description="Maximum risk score (1-5) permitted in remediation plans.",
    )
    low_utilization_threshold_pct: float = Field(
        default=10.0,
        validation_alias="LOW_UTILIZATION_THRESHOLD_PCT",
        ge=0.0,
        le=100.0,
        description="Average CPU/usage threshold considered underutilized.",
    )
    moderate_utilization_threshold_pct: float = Field(
        default=40.0,
        validation_alias="MODERATE_UTILIZATION_THRESHOLD_PCT",
        ge=0.0,
        le=100.0,
        description="Moderate utilization ceiling.",
    )
    safety_auto_remediate_max_risk: int = Field(
        default=3,
        validation_alias="SAFETY_AUTO_REMEDIATE_MAX_RISK",
        ge=1,
        le=5,
        description="Max risk score eligible for autonomous remediation without human gate.",
    )

    # Persistence Backend
    db_path: Optional[str] = Field(
        default=None,
        validation_alias="DB_PATH",
        description="Optional SQLite database path for persistent audit ledger.",
    )

    # MCP Server Configuration
    mcp_server_name: str = Field(
        default="gemini-cost-arbiter-mcp",
        validation_alias="MCP_SERVER_NAME",
        description="Model Context Protocol server identifier.",
    )
    mcp_server_version: str = Field(
        default="1.0.0",
        validation_alias="MCP_SERVER_VERSION",
        description="Model Context Protocol server semver.",
    )
    mcp_host: str = Field(
        default="127.0.0.1",
        validation_alias="MCP_HOST",
        description="Binding host for SSE transport server.",
    )
    mcp_port: int = Field(
        default=8000,
        validation_alias="MCP_PORT",
        description="Binding port for SSE transport server.",
    )
    mcp_api_key: Optional[str] = Field(
        default=None,
        validation_alias="MCP_API_KEY",
        description="Optional API key requirement for SSE endpoints.",
    )
    plan_signing_secret: Optional[str] = Field(
        default=None,
        validation_alias="PLAN_SIGNING_SECRET",
        description="Cryptographic secret key used to HMAC-SHA256 sign remediation plans.",
    )
    environment: str = Field(
        default="development",
        validation_alias="ENVIRONMENT",
        description="Operational environment: production, staging, development, test.",
    )
    require_auth: bool = Field(
        default=False,
        validation_alias="REQUIRE_AUTH",
        description="Strictly mandate API key authentication on SSE transport (fails closed if unconfigured).",
    )
    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
        description="Application logging verbosity.",
    )
