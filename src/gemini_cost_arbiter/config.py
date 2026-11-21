"""Runtime configuration contracts using Pydantic Settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ArbiterConfig(BaseSettings):
    """Centralized runtime configuration with environment variable precedence."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        populate_by_name=True,
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
    max_output_tokens: int = Field(
        default=8192,
        validation_alias="MAX_OUTPUT_TOKENS",
        ge=256,
        le=65536,
        description="Maximum output tokens per LLM completion.",
    )
    max_session_token_budget: int = Field(
        default=500000,
        validation_alias="MAX_SESSION_TOKEN_BUDGET",
        ge=1000,
        description="Maximum cumulative token budget per session before tripping circuit breaker.",
    )
    daily_api_cost_limit_usd: float = Field(
        default=10.0,
        validation_alias="DAILY_API_COST_LIMIT_USD",
        ge=0.01,
        description="Daily UTC API spend ceiling in USD before tripping circuit breaker.",
    )
    circuit_breaker_failure_threshold: int = Field(
        default=3,
        validation_alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        ge=1,
        le=20,
        description="Consecutive LLM failures required to trip the cooldown circuit breaker.",
    )

    # Multi-Model Secondary Fallback (OpenRouter)
    openrouter_api_key: str | None = Field(
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

    # Persistence & Catalog Configuration
    db_path: str | None = Field(
        default=None,
        validation_alias="DB_PATH",
        description="Optional SQLite database path for persistent audit ledger.",
    )
    catalog_path: str = Field(
        default="config/instance_mappings.json",
        validation_alias="CATALOG_PATH",
        description="Path to AWS EC2 instance downsize and pricing catalog JSON.",
    )
    prompts_dir: str = Field(
        default="prompts",
        validation_alias="PROMPTS_DIR",
        description="Path to PromptOps directory containing master and modular system prompts.",
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
    mcp_api_key: str | None = Field(
        default=None,
        validation_alias="MCP_API_KEY",
        description="Optional API key requirement for SSE endpoints.",
    )
    max_payload_bytes: int = Field(
        default=10485760,
        ge=1024,
        validation_alias="MAX_PAYLOAD_BYTES",
        description="Maximum inbound HTTP/SSE JSON-RPC request body size in bytes (10 MB default).",
    )
    plan_signing_secret: str | None = Field(
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
