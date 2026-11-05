"""Pytest Integration and Unit Test Suite for Gemini Cloud-Cost Arbiter MCP.

Tests:
1. Multi-dimensional AWS telemetry schemas (EC2, RDS, S3, TelemetryBatch).
2. Safety Guardrails & Risk Scoring (1 to 5) with mandatory mitigation validation.
3. Deterministic Heuristic FinOps Engine.
4. Asynchronous Gemini 3.8 Flash High Reasoning Engine with mocked HTTP clients.
5. High-availability fallback from Gemini API outage to Heuristic Engine.
6. FinOps cumulative audit ledger.
7. Model Context Protocol (MCP) JSON-RPC 2.0 tool endpoints.
"""

import json
from unittest.mock import AsyncMock
import pytest
import httpx
from pydantic import ValidationError

from app.schemas import (
    ActionType,
    ArbiterConfig,
    CloudResourceType,
    EC2Metrics,
    FinOpsAuditSummary,
    RDSMetrics,
    RemediationActionItem,
    RemediationPlan,
    S3Metrics,
    TelemetryBatch,
    WasteAnalysisSummary,
)
from app.engine import GeminiCostArbiterEngine


@pytest.fixture
def arbiter_config() -> ArbiterConfig:
    """Fixture providing test configuration."""
    return ArbiterConfig(
        gemini_api_key="test-api-key-finops-12345",
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta",
        model_name="gemini-3.8-flash-high",
        thinking_budget=2048,
        max_acceptable_risk=5,
    )


@pytest.fixture
def arbiter_engine(arbiter_config: ArbiterConfig) -> GeminiCostArbiterEngine:
    """Fixture providing initialized engine."""
    return GeminiCostArbiterEngine(config=arbiter_config)


@pytest.fixture
def sample_telemetry_batch() -> TelemetryBatch:
    """Fixture providing realistic multi-dimensional AWS infrastructure telemetry."""
    return TelemetryBatch(
        ec2_instances=[
            EC2Metrics(
                resource_id="i-0123456789abcdef0",
                current_instance_type="m5.4xlarge",
                cpu_utilization_avg_pct=4.2,
                cpu_utilization_p95_pct=11.5,
                memory_utilization_avg_pct=18.0,
                monthly_spend_usd=550.0,
                environment="production",
                region="us-east-1",
            ),
            EC2Metrics(
                resource_id="i-0987654321fedcba0",
                current_instance_type="m5.large",
                cpu_utilization_avg_pct=65.0,
                cpu_utilization_p95_pct=88.0,
                memory_utilization_avg_pct=72.0,
                monthly_spend_usd=70.0,
                environment="production",
                region="us-east-1",
            ),
        ],
        rds_instances=[
            RDSMetrics(
                resource_id="prod-legacy-reports-db",
                current_instance_class="db.r5.2xlarge",
                cpu_utilization_avg_pct=2.1,
                memory_free_bytes=34359738368,
                storage_allocated_gb=500,
                storage_used_gb=85.0,
                active_connections_avg=0.0,  # Idle DB
                multi_az=True,
                monthly_spend_usd=720.0,
                environment="production",
                region="us-east-1",
            )
        ],
        s3_buckets=[
            S3Metrics(
                resource_id="corporate-analytics-archive",
                total_storage_gb=125000.0,
                object_count=1800000,
                current_storage_class="STANDARD",
                lifecycle_rules_configured=False,
                percentage_infrequently_accessed=85.0,
                monthly_spend_usd=2875.0,
                region="us-east-1",
            )
        ],
    )


# =============================================================================
# 1. Telemetry Ingestion Schema Tests
# =============================================================================


class TestTelemetryIngestion:
    """Test suite validating ingestion schemas and data constraints."""

    def test_valid_ec2_metrics(self) -> None:
        """Verify proper validation of EC2 telemetry."""
        ec2 = EC2Metrics(
            resource_id="i-test-instance-1",
            current_instance_type="c5.2xlarge",
            cpu_utilization_avg_pct=8.5,
            cpu_utilization_p95_pct=14.2,
            memory_utilization_avg_pct=22.0,
            monthly_spend_usd=245.0,
            environment="staging",
        )
        assert ec2.resource_id == "i-test-instance-1"
        assert ec2.cpu_utilization_avg_pct == 8.5
        assert ec2.monthly_spend_usd == 245.0

    def test_invalid_ec2_bounds(self) -> None:
        """Verify out-of-bound percentages are rejected."""
        with pytest.raises(ValidationError):
            EC2Metrics(
                resource_id="i-invalid",
                current_instance_type="m5.large",
                cpu_utilization_avg_pct=105.0,  # > 100%
                cpu_utilization_p95_pct=110.0,
                memory_utilization_avg_pct=50.0,
                monthly_spend_usd=100.0,
            )

        with pytest.raises(ValidationError):
            EC2Metrics(
                resource_id="i-invalid",
                current_instance_type="m5.large",
                cpu_utilization_avg_pct=-5.0,  # < 0%
                cpu_utilization_p95_pct=10.0,
                memory_utilization_avg_pct=50.0,
                monthly_spend_usd=100.0,
            )

    def test_valid_rds_metrics(self) -> None:
        """Verify RDS telemetry model constraints."""
        rds = RDSMetrics(
            resource_id="test-rds-db",
            current_instance_class="db.t4g.medium",
            cpu_utilization_avg_pct=12.0,
            memory_free_bytes=2147483648,
            storage_allocated_gb=100,
            storage_used_gb=40.0,
            active_connections_avg=4.5,
            monthly_spend_usd=65.0,
        )
        assert rds.storage_allocated_gb == 100
        assert rds.active_connections_avg == 4.5

    def test_valid_s3_metrics(self) -> None:
        """Verify S3 telemetry model constraints."""
        s3 = S3Metrics(
            resource_id="my-data-lake-raw",
            total_storage_gb=50000.0,
            object_count=500000,
            percentage_infrequently_accessed=90.0,
            monthly_spend_usd=1150.0,
        )
        assert s3.percentage_infrequently_accessed == 90.0
        assert s3.monthly_spend_usd == 1150.0

    def test_telemetry_batch_aggregations(self, sample_telemetry_batch: TelemetryBatch) -> None:
        """Verify batch counts and spend sums."""
        assert sample_telemetry_batch.total_resource_count == 4
        # 550 + 70 + 720 + 2875 = 4215.0
        assert sample_telemetry_batch.total_monthly_spend_usd == 4215.0


# =============================================================================
# 2. Safety Guardrails & Risk Scoring (1 to 5) Tests
# =============================================================================


class TestSafetyGuardrails:
    """Test suite validating Safety Risk Scoring (1 to 5) and mitigation rules."""

    def test_low_risk_action_without_mitigations_allowed(self) -> None:
        """Score 1 and 2 actions are allowed without mitigations."""
        item = RemediationActionItem(
            resource_id="my-bucket",
            resource_type=CloudResourceType.S3,
            action_type=ActionType.TRANSITION_STORAGE_TIER,
            target_configuration="INTELLIGENT_TIERING",
            current_monthly_spend_usd=500.0,
            projected_monthly_spend_usd=250.0,
            projected_monthly_savings_usd=250.0,
            safety_risk_score=1,
            reasoning_rationale="Safe transparent tiering transition.",
            system_mitigations=[],
        )
        assert item.safety_risk_score == 1
        assert len(item.system_mitigations) == 0

    def test_high_risk_action_requires_system_mitigations(self) -> None:
        """Score >= 3 actions MUST have non-empty system_mitigations or fail validation."""
        with pytest.raises(ValidationError) as excinfo:
            RemediationActionItem(
                resource_id="i-prod-web-server",
                resource_type=CloudResourceType.EC2,
                action_type=ActionType.RIGHTSIZE_INSTANCE,
                target_configuration="m5.large",
                current_monthly_spend_usd=400.0,
                projected_monthly_spend_usd=100.0,
                projected_monthly_savings_usd=300.0,
                safety_risk_score=4,
                reasoning_rationale="Downsizing production compute instance.",
                system_mitigations=[],  # FORBIDDEN: Empty on score >= 3
            )
        assert "contains no system_mitigations" in str(excinfo.value)

    def test_high_risk_action_with_mitigations_succeeds(self) -> None:
        """Score >= 3 actions succeed when mitigations are provided."""
        item = RemediationActionItem(
            resource_id="i-prod-web-server",
            resource_type=CloudResourceType.EC2,
            action_type=ActionType.RIGHTSIZE_INSTANCE,
            target_configuration="m5.large",
            current_monthly_spend_usd=400.0,
            projected_monthly_spend_usd=100.0,
            projected_monthly_savings_usd=300.0,
            safety_risk_score=4,
            reasoning_rationale="Downsizing production compute instance.",
            system_mitigations=[
                "Create pre-execution AMI snapshot",
                "Execute during Sunday 02:00 UTC maintenance window",
            ],
        )
        assert item.safety_risk_score == 4
        assert len(item.system_mitigations) == 2

    def test_invalid_risk_score_bounds(self) -> None:
        """Scores < 1 or > 5 must raise ValidationError."""
        with pytest.raises(ValidationError):
            RemediationActionItem(
                resource_id="res",
                resource_type=CloudResourceType.S3,
                action_type=ActionType.APPLY_LIFECYCLE_RULE,
                target_configuration="GLACIER",
                current_monthly_spend_usd=10.0,
                projected_monthly_spend_usd=2.0,
                projected_monthly_savings_usd=8.0,
                safety_risk_score=0,  # Below 1
                reasoning_rationale="Invalid score test.",
            )

        with pytest.raises(ValidationError):
            RemediationActionItem(
                resource_id="res",
                resource_type=CloudResourceType.S3,
                action_type=ActionType.APPLY_LIFECYCLE_RULE,
                target_configuration="GLACIER",
                current_monthly_spend_usd=10.0,
                projected_monthly_spend_usd=2.0,
                projected_monthly_savings_usd=8.0,
                safety_risk_score=6,  # Above 5
                reasoning_rationale="Invalid score test.",
            )


# =============================================================================
# 3. Deterministic Heuristic Engine Tests
# =============================================================================


class TestDeterministicHeuristicEngine:
    """Test suite validating deterministic FinOps logic and waste detection."""

    def test_heuristic_evaluation_of_sample_fleet(
        self,
        arbiter_engine: GeminiCostArbiterEngine,
        sample_telemetry_batch: TelemetryBatch,
    ) -> None:
        """Verify detection of underutilized EC2, idle RDS, and cold S3."""
        plan = arbiter_engine._evaluate_heuristics(sample_telemetry_batch)

        assert len(plan.actions) == 3
        action_types = [a.action_type for a in plan.actions]
        assert ActionType.RIGHTSIZE_INSTANCE in action_types
        assert ActionType.STOP_INSTANCE in action_types
        assert ActionType.TRANSITION_STORAGE_TIER in action_types

        # Verify savings calculation
        assert plan.total_projected_monthly_savings_usd > 2000.0
        assert plan.total_projected_monthly_spend_usd < plan.total_current_monthly_spend_usd

        # Verify mitigations exist on high risk actions
        for action in plan.actions:
            if action.safety_risk_score >= 3:
                assert len(action.system_mitigations) > 0

    @pytest.mark.asyncio
    async def test_risk_filter_threshold(
        self,
        arbiter_engine: GeminiCostArbiterEngine,
        sample_telemetry_batch: TelemetryBatch,
    ) -> None:
        """Verify that max_acceptable_risk filters out high risk operations."""
        plan = await arbiter_engine.generate_remediation_plan(
            sample_telemetry_batch,
            max_acceptable_risk=2,
        )
        assert len(plan.actions) == 1
        assert plan.actions[0].resource_type == CloudResourceType.S3
        assert plan.actions[0].safety_risk_score == 1


# =============================================================================
# 4. Asynchronous Gemini 3.8 Flash High Engine & Mocked Network Tests
# =============================================================================


class TestGeminiAIReasoningEngine:
    """Test suite validating async Gemini 3.8 Flash High reasoning and fallback."""

    @pytest.mark.asyncio
    async def test_successful_gemini_reasoning_flow(
        self,
        arbiter_config: ArbiterConfig,
        sample_telemetry_batch: TelemetryBatch,
    ) -> None:
        """Verify happy-path AI reasoning call with structured JSON egress."""
        mocked_gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "actions": [
                                            {
                                                "resource_id": "i-0123456789abcdef0",
                                                "resource_type": "EC2",
                                                "action_type": "rightsize_instance",
                                                "target_configuration": "t4g.xlarge",
                                                "current_monthly_spend_usd": 550.0,
                                                "projected_monthly_spend_usd": 150.0,
                                                "projected_monthly_savings_usd": 400.0,
                                                "safety_risk_score": 4,
                                                "reasoning_rationale": "High memory headroom and low CPU average justify ARM Graviton rightsize.",
                                                "system_mitigations": [
                                                    "Pre-cutover AMI snapshot",
                                                    "Canary traffic test",
                                                ],
                                                "execution_payload": {
                                                    "command": "aws ec2 modify-instance-attribute"
                                                },
                                            }
                                        ]
                                    }
                                )
                            }
                        ]
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 240,
                "candidatesTokenCount": 180,
                "thinkingTokenCount": 512,
            },
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = httpx.Response(200, json=mocked_gemini_response)
        mock_client.post.return_value = mock_response

        engine = GeminiCostArbiterEngine(config=arbiter_config, http_client=mock_client)
        plan = await engine.generate_remediation_plan(sample_telemetry_batch)

        assert len(plan.actions) == 1
        action = plan.actions[0]
        assert action.resource_id == "i-0123456789abcdef0"
        assert action.target_configuration == "t4g.xlarge"
        assert action.projected_monthly_savings_usd == 400.0
        assert action.safety_risk_score == 4
        assert len(action.system_mitigations) == 2

    @pytest.mark.asyncio
    async def test_resilient_fallback_on_gemini_503_error(
        self,
        arbiter_config: ArbiterConfig,
        sample_telemetry_batch: TelemetryBatch,
    ) -> None:
        """Verify seamless fallback to Deterministic Heuristic Engine during API outages."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = httpx.Response(503, text="Service Unavailable")
        mock_client.post.return_value = mock_response

        engine = GeminiCostArbiterEngine(config=arbiter_config, http_client=mock_client)
        plan = await engine.generate_remediation_plan(sample_telemetry_batch)

        assert len(plan.actions) > 0
        assert plan.total_projected_monthly_savings_usd > 0.0

    @pytest.mark.asyncio
    async def test_waste_analysis_summary(
        self,
        arbiter_engine: GeminiCostArbiterEngine,
        sample_telemetry_batch: TelemetryBatch,
    ) -> None:
        """Verify analyze_infrastructure_waste output structure."""
        summary = await arbiter_engine.analyze_infrastructure_waste(sample_telemetry_batch)

        assert summary.total_resources_evaluated == 4
        assert summary.underutilized_resources_count > 0
        assert summary.total_monthly_waste_usd > 0.0
        assert summary.potential_savings_percentage > 0.0
        assert len(summary.key_findings) > 0


# =============================================================================
# 5. FinOps Cumulative Audit Ledger Tests
# =============================================================================


class TestFinOpsAuditLedger:
    """Test suite validating cumulative metrics tracking."""

    @pytest.mark.asyncio
    async def test_ledger_accumulation_and_reset(
        self,
        arbiter_engine: GeminiCostArbiterEngine,
        sample_telemetry_batch: TelemetryBatch,
    ) -> None:
        """Verify that multiple evaluations accumulate statistics in the audit ledger."""
        arbiter_engine.reset_audit_ledger()
        initial_audit = arbiter_engine.get_finops_audit_summary()
        assert initial_audit.total_batches_processed == 0

        # Process first batch
        await arbiter_engine.generate_remediation_plan(sample_telemetry_batch)
        audit_1 = arbiter_engine.get_finops_audit_summary()
        assert audit_1.total_batches_processed == 1
        assert audit_1.total_resources_analyzed == 4
        assert audit_1.cumulative_projected_savings_usd > 0.0

        # Process second batch
        await arbiter_engine.generate_remediation_plan(sample_telemetry_batch)
        audit_2 = arbiter_engine.get_finops_audit_summary()
        assert audit_2.total_batches_processed == 2
        assert audit_2.total_resources_analyzed == 8
        assert audit_2.cumulative_projected_savings_usd == round(
            audit_1.cumulative_projected_savings_usd * 2, 2
        )

        # Reset
        arbiter_engine.reset_audit_ledger()
        audit_reset = arbiter_engine.get_finops_audit_summary()
        assert audit_reset.total_batches_processed == 0
        assert audit_reset.cumulative_projected_savings_usd == 0.0


# =============================================================================
# 6. Model Context Protocol (MCP) JSON-RPC 2.0 Tests
# =============================================================================


class TestModelContextProtocol:
    """Test suite validating JSON-RPC 2.0 MCP tools dispatcher."""

    @pytest.mark.asyncio
    async def test_mcp_initialize(self, arbiter_engine: GeminiCostArbiterEngine) -> None:
        """Verify MCP initialize handshake."""
        msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
        resp = await arbiter_engine.handle_mcp_message(msg)
        assert resp is not None
        assert resp["jsonrpc"] == "2.0"
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert resp["result"]["serverInfo"]["name"] == arbiter_engine.config.mcp_server_name

    @pytest.mark.asyncio
    async def test_mcp_tools_list(self, arbiter_engine: GeminiCostArbiterEngine) -> None:
        """Verify all 3 tools are exposed with valid input schemas."""
        msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        resp = await arbiter_engine.handle_mcp_message(msg)
        assert resp is not None
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "analyze_infrastructure_waste" in tool_names
        assert "generate_remediation_plan" in tool_names
        assert "get_finops_audit_summary" in tool_names

    @pytest.mark.asyncio
    async def test_mcp_call_analyze_waste(
        self,
        arbiter_engine: GeminiCostArbiterEngine,
        sample_telemetry_batch: TelemetryBatch,
    ) -> None:
        """Verify MCP tools/call for analyze_infrastructure_waste."""
        msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "analyze_infrastructure_waste",
                "arguments": {
                    "telemetry": sample_telemetry_batch.model_dump(),
                },
            },
        }
        resp = await arbiter_engine.handle_mcp_message(msg)
        assert resp is not None
        content = resp["result"]["content"][0]["text"]
        parsed = json.loads(content)
        assert parsed["total_resources_evaluated"] == 4
        assert parsed["total_monthly_waste_usd"] > 0.0

    @pytest.mark.asyncio
    async def test_mcp_call_generate_plan(
        self,
        arbiter_engine: GeminiCostArbiterEngine,
        sample_telemetry_batch: TelemetryBatch,
    ) -> None:
        """Verify MCP tools/call for generate_remediation_plan."""
        msg = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "generate_remediation_plan",
                "arguments": {
                    "telemetry": sample_telemetry_batch.model_dump(),
                    "max_acceptable_risk": 5,
                },
            },
        }
        resp = await arbiter_engine.handle_mcp_message(msg)
        assert resp is not None
        content = resp["result"]["content"][0]["text"]
        parsed = json.loads(content)
        assert "plan_id" in parsed
        assert len(parsed["actions"]) > 0

    @pytest.mark.asyncio
    async def test_mcp_call_audit_summary(
        self, arbiter_engine: GeminiCostArbiterEngine
    ) -> None:
        """Verify MCP tools/call for get_finops_audit_summary."""
        msg = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "get_finops_audit_summary", "arguments": {}},
        }
        resp = await arbiter_engine.handle_mcp_message(msg)
        assert resp is not None
        content = resp["result"]["content"][0]["text"]
        parsed = json.loads(content)
        assert "cumulative_waste_identified_usd" in parsed

    @pytest.mark.asyncio
    async def test_mcp_unknown_tool(self, arbiter_engine: GeminiCostArbiterEngine) -> None:
        """Verify unknown tool returns -32601."""
        msg = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "non_existent_tool", "arguments": {}},
        }
        resp = await arbiter_engine.handle_mcp_message(msg)
        assert resp is not None
        assert resp["error"]["code"] == -32601
