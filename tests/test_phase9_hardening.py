"""Tests for Phase 9 Enterprise Production Hardening and Anti-Ambiguity Remediation.

Validates:
1. SSE Transport Authentication Middleware (Bearer token, X-API-Key, ?apiKey=, and unauthenticated /health).
2. HMAC-SHA256 Cryptographic Plan Signing & Tamper Verification.
3. EC2 Memory Floor Guardrail (OOM Prevention).
4. EC2 & RDS Pricing Model Awareness (Reserved Instances / Savings Plans).
5. S3 Small-Object Economics Guardrail (<128 KB floor).
6. Safety Guardrail Quarantine Pattern for unmitigated high-risk actions.
7. Gemini Schema Dereferencer resolving $defs and $ref.
"""

from __future__ import annotations

import httpx
import pytest

from gemini_cost_arbiter.guardrails.risk_scorer import GuardrailEngine
from gemini_cost_arbiter.heuristics.ec2_rules import evaluate_ec2_instance
from gemini_cost_arbiter.heuristics.rds_rules import evaluate_rds_instance
from gemini_cost_arbiter.heuristics.s3_rules import evaluate_s3_bucket
from gemini_cost_arbiter.mcp.server_sse import create_sse_app
from gemini_cost_arbiter.models.remediation import (
    ActionType,
    CloudResourceType,
    RemediationActionItem,
    RemediationPlan,
)
from gemini_cost_arbiter.models.telemetry import EC2Metrics, RDSMetrics, S3Metrics
from gemini_cost_arbiter.reasoner.client import clean_gemini_schema


# ==============================================================================
# 1. SSE Transport Authentication Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_sse_auth_health_unauthenticated() -> None:
    """The /health endpoint must remain unauthenticated for container orchestrators."""
    app = create_sse_app(api_key="prod-secret-key-456")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "gemini-cost-arbiter-mcp"}


@pytest.mark.asyncio
async def test_sse_auth_missing_credentials_rejected() -> None:
    """When MCP_API_KEY is configured, missing auth must yield 401 Unauthorized."""
    app = create_sse_app(api_key="prod-secret-key-456")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # POST /messages without key
        res_post = await client.post("/messages", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        assert res_post.status_code == 401
        assert "Unauthorized" in res_post.text


@pytest.mark.asyncio
async def test_sse_auth_bearer_token_succeeds() -> None:
    """Authorization: Bearer <key> must successfully authenticate."""
    app = create_sse_app(api_key="prod-secret-key-456")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": "Bearer prod-secret-key-456"}
        res = await client.post("/messages", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}, headers=headers)
        assert res.status_code == 200
        assert res.json().get("result") is not None


@pytest.mark.asyncio
async def test_sse_auth_x_api_key_header_succeeds() -> None:
    """X-API-Key: <key> header must successfully authenticate."""
    app = create_sse_app(api_key="prod-secret-key-456")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        headers = {"X-API-Key": "prod-secret-key-456"}
        res = await client.post("/messages", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}, headers=headers)
        assert res.status_code == 200
        assert res.json().get("result") is not None


@pytest.mark.asyncio
async def test_sse_auth_query_parameter_succeeds() -> None:
    """?apiKey=<key> query parameter must successfully authenticate."""
    app = create_sse_app(api_key="prod-secret-key-456")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/messages?apiKey=prod-secret-key-456", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        assert res.status_code == 200
        assert res.json().get("result") is not None


# ==============================================================================
# 2. HMAC-SHA256 Cryptographic Plan Signing Tests
# ==============================================================================

def test_hmac_sha256_plan_signing_and_tamper_detection() -> None:
    """HMAC signature must verify authentic plans and reject tampered plans."""
    secret = "corporate-hsm-signing-key-999"
    action = RemediationActionItem(
        resource_id="i-test-123",
        resource_type=CloudResourceType.EC2,
        action_type=ActionType.RIGHTSIZE_INSTANCE,
        target_configuration="m5.large",
        current_monthly_spend_usd=500.0,
        projected_monthly_spend_usd=175.0,
        projected_monthly_savings_usd=325.0,
        safety_risk_score=3,
        system_mitigations=["Automated AMI Snapshot"],
    )
    plan = RemediationPlan(
        plan_id="plan-test-uuid",
        created_at="2026-11-13T00:00:00Z",
        actions=[action],
        total_current_monthly_spend_usd=500.0,
        total_projected_monthly_spend_usd=175.0,
        total_projected_monthly_savings_usd=325.0,
        average_risk_score=3.0,
        max_risk_score=3,
    )

    signed_plan = GuardrailEngine.attach_plan_digest(plan, secret=secret)
    assert signed_plan.plan_digest is not None
    assert signed_plan.plan_signature is not None
    assert GuardrailEngine.verify_plan_signature(signed_plan, secret=secret) is True

    # Tampering attack 1: modifying action spend
    tampered_dict = signed_plan.model_dump()
    tampered_dict["actions"][0]["projected_monthly_savings_usd"] = 9999.0
    tampered_plan = RemediationPlan(**tampered_dict)
    assert GuardrailEngine.verify_plan_signature(tampered_plan, secret=secret) is False

    # Tampering attack 2: modifying execution_payload (e.g. injecting malicious CLI command)
    tampered_cli_dict = signed_plan.model_dump()
    tampered_cli_dict["actions"][0]["execution_payload"]["aws_cli"] = "aws ec2 terminate-instances --instance-ids i-test-123"
    tampered_cli_plan = RemediationPlan(**tampered_cli_dict)
    assert GuardrailEngine.verify_plan_signature(tampered_cli_plan, secret=secret) is False

    # Tampering attack 3: modifying system_mitigations
    tampered_mitigations_dict = signed_plan.model_dump()
    tampered_mitigations_dict["actions"][0]["system_mitigations"] = ["Forged Attacker Snapshot Mitigation"]
    assert GuardrailEngine.verify_plan_signature(RemediationPlan(**tampered_mitigations_dict), secret=secret) is False

    # Tampering attack 4: modifying top-level plan totals
    tampered_totals_dict = signed_plan.model_dump()
    tampered_totals_dict["total_projected_monthly_savings_usd"] = 99999.0
    assert GuardrailEngine.verify_plan_signature(RemediationPlan(**tampered_totals_dict), secret=secret) is False

    # Fail-closed in production when PLAN_SIGNING_SECRET is missing
    import os
    orig_env = os.environ.get("ENVIRONMENT")
    orig_secret = os.environ.pop("PLAN_SIGNING_SECRET", None)
    try:
        os.environ["ENVIRONMENT"] = "production"
        with pytest.raises(RuntimeError, match="PLAN_SIGNING_SECRET must be configured in production"):
            GuardrailEngine.attach_plan_digest(plan, secret=None)
    finally:
        if orig_env is not None:
            os.environ["ENVIRONMENT"] = orig_env
        else:
            os.environ.pop("ENVIRONMENT", None)
        if orig_secret is not None:
            os.environ["PLAN_SIGNING_SECRET"] = orig_secret


# ==============================================================================
# 3. EC2 Memory Floor & Pricing Model Tests
# ==============================================================================

def test_ec2_memory_floor_prevents_oom_downsizing() -> None:
    """Chronic low CPU instance must NOT be downsized if RAM utilization > 65%."""
    # Low CPU (3%), but High Memory (82% RAM) -> MUST NOT DOWNSIZE
    ec2_high_ram = EC2Metrics(
        resource_id="i-memory-bound-redis",
        current_instance_type="m5.4xlarge",
        cpu_utilization_avg_pct=3.0,
        cpu_utilization_p95_pct=10.0,
        memory_utilization_avg_pct=82.0,
        monthly_spend_usd=550.0,
    )
    result = evaluate_ec2_instance(ec2_high_ram)
    assert result is None, "Heuristic must abort downsizing when memory utilization > 65% to avoid OOM crash"

    # Low CPU (3%), Low Memory (25% RAM) -> ALLOWS DOWNSIZING
    ec2_low_ram = EC2Metrics(
        resource_id="i-idle-web",
        current_instance_type="m5.4xlarge",
        cpu_utilization_avg_pct=3.0,
        cpu_utilization_p95_pct=10.0,
        memory_utilization_avg_pct=25.0,
        monthly_spend_usd=550.0,
    )
    result_low = evaluate_ec2_instance(ec2_low_ram)
    assert result_low is not None
    assert result_low.projected_monthly_savings_usd > 0.0


def test_ec2_and_rds_reserved_instance_pricing_model() -> None:
    """Downsizing or stopping resources on Reserved/Savings Plan yields $0.00 bill savings."""
    ec2_ri = EC2Metrics(
        resource_id="i-ri-workload",
        current_instance_type="m5.4xlarge",
        cpu_utilization_avg_pct=3.0,
        cpu_utilization_p95_pct=10.0,
        memory_utilization_avg_pct=20.0,
        monthly_spend_usd=550.0,
        pricing_model="reserved",
    )
    result_ec2 = evaluate_ec2_instance(ec2_ri)
    assert result_ec2 is not None
    assert result_ec2.projected_monthly_savings_usd == 0.0
    assert "RESERVED" in result_ec2.reasoning_rationale

    rds_ri = RDSMetrics(
        resource_id="rds-ri-db",
        active_connections_avg=0.0,
        monthly_spend_usd=400.0,
        pricing_model="savings_plan",
    )
    result_rds = evaluate_rds_instance(rds_ri)
    assert result_rds is not None
    assert result_rds.projected_monthly_savings_usd == 0.0
    assert "SAVINGS_PLAN" in result_rds.reasoning_rationale


# ==============================================================================
# 4. S3 Small-Object Economics Guardrail (<128 KB Floor)
# ==============================================================================

def test_s3_small_object_economics_guardrail() -> None:
    """S3 buckets with average object size < 128 KB must not be transitioned to Intelligent-Tiering."""
    # Bucket with 10 GB across 1,000,000 small log files (avg size = ~10.48 KB < 128 KB)
    s3_small_objects = S3Metrics(
        resource_id="bucket-micro-logs",
        total_storage_gb=10,
        object_count=1_000_000,
        percentage_infrequently_accessed=80.0,
        current_storage_class="STANDARD",
        monthly_spend_usd=50.0,
    )
    assert evaluate_s3_bucket(s3_small_objects) is None, "Must disqualify bucket with avg object size < 128 KB"

    # Bucket with 1,000 GB across 10,000 files (avg size = ~104.8 MB >= 128 KB)
    s3_large_objects = S3Metrics(
        resource_id="bucket-large-backups",
        total_storage_gb=1000,
        object_count=10_000,
        percentage_infrequently_accessed=80.0,
        current_storage_class="STANDARD",
        monthly_spend_usd=230.0,
    )
    result = evaluate_s3_bucket(s3_large_objects)
    assert result is not None
    assert result.target_configuration == "INTELLIGENT_TIERING"


# ==============================================================================
# 5. Safety Guardrail Quarantine Pattern
# ==============================================================================

def test_quarantine_pattern_for_unmitigated_high_risk() -> None:
    """Actions with risk >= 3 lacking explicit mitigations must be quarantined, not auto-patched."""
    raw_action = {
        "resource_id": "i-unmitigated-prod",
        "resource_type": "EC2",
        "action_type": "rightsize_instance",
        "current_monthly_spend_usd": 600.0,
        "projected_monthly_spend_usd": 200.0,
        "projected_monthly_savings_usd": 400.0,
        "safety_risk_score": 4,
        "system_mitigations": [],  # Reasoner omitted mitigations!
    }

    enriched = GuardrailEngine.audit_and_enrich_action(raw_action)
    assert enriched["quarantined"] is True
    assert "Quarantined pending manual SRE review" in enriched["quarantine_reason"]

    # Instantiating the Pydantic model with quarantined=True succeeds
    item = RemediationActionItem(**enriched)
    assert item.quarantined is True


# ==============================================================================
# 6. Gemini Schema Dereferencer
# ==============================================================================

def test_clean_gemini_schema_dereferences_defs_and_refs() -> None:
    """Schema flattener must inline $ref, remove $defs and titles for Gemini API compatibility."""
    raw_schema = RemediationPlan.model_json_schema()
    assert "$defs" in raw_schema

    cleaned = clean_gemini_schema(raw_schema)
    assert "$defs" not in cleaned
    assert "title" not in cleaned
    assert "additionalProperties" not in cleaned
    assert "$schema" not in cleaned

    # Check actions item properties
    actions_items = cleaned["properties"]["actions"]["items"]
    assert "$ref" not in actions_items
    assert "additionalProperties" not in actions_items
    assert "execution_payload" not in actions_items["properties"]
    assert "resource_id" in actions_items["properties"]
    assert "safety_risk_score" in actions_items["properties"]

    # Check that minimum and maximum constraints are stripped (Protobuf schema compatibility)
    assert "minimum" not in actions_items["properties"]["safety_risk_score"]
    assert "maximum" not in actions_items["properties"]["safety_risk_score"]

    # Check Optional field conversion from anyOf [{"type": "..."}, {"type": "null"}] to nullable=True
    # and verify sibling metadata (description) preservation
    quarantine_prop = actions_items["properties"]["quarantine_reason"]
    assert "anyOf" not in quarantine_prop
    assert quarantine_prop.get("nullable") is True
    assert quarantine_prop.get("type") == "string"
    assert quarantine_prop.get("description") is not None

    # Verify unresolved $ref raises ValueError
    with pytest.raises(ValueError, match="Unresolved \\$ref"):
        clean_gemini_schema({"$ref": "#/$defs/DoesNotExist"})

    # Verify cyclic $ref raises ValueError
    with pytest.raises(ValueError, match="Cyclic \\$ref"):
        clean_gemini_schema({"$defs": {"A": {"$ref": "#/$defs/A"}}, "$ref": "#/$defs/A"})


# ==============================================================================
# 7. Real AWS Pricing Catalog & Deterministic Overwrites & Fail-Closed Auth Tests
# ==============================================================================

def test_ec2_real_aws_pricing_catalog_lookup() -> None:
    """EC2 downsizing must calculate exact dollar savings from hourly rate delta * 730 hrs."""
    # m5.4xlarge ($0.768/hr) -> m5.xlarge ($0.192/hr)
    # Hourly delta: $0.576/hr * 730 hrs/month = $420.48/month savings
    ec2_item = EC2Metrics(
        resource_id="i-catalog-pricing-test",
        current_instance_type="m5.4xlarge",
        cpu_utilization_avg_pct=4.0,
        cpu_utilization_p95_pct=15.0,
        memory_utilization_avg_pct=30.0,
        monthly_spend_usd=600.0,
        pricing_model="on_demand",
    )
    result = evaluate_ec2_instance(ec2_item)
    assert result is not None
    assert result.target_configuration == "m5.xlarge"
    assert result.projected_monthly_savings_usd == 420.48
    assert result.projected_monthly_spend_usd == round(600.0 - 420.48, 2)
    assert "($0.768/hr) to m5.xlarge ($0.192/hr) saves ~$420.48/mo" in result.reasoning_rationale


def test_deterministic_iam_and_cli_overwrites_llm_hallucinations() -> None:
    """GuardrailEngine must unconditionally overwrite any LLM-hallucinated IAM policies or CLI commands."""
    hallucinated_action = {
        "resource_id": "i-prod-compute-1",
        "resource_type": "EC2",
        "action_type": "rightsize_instance",
        "target_configuration": "m5.xlarge",
        "current_monthly_spend_usd": 600.0,
        "projected_monthly_spend_usd": 179.52,
        "projected_monthly_savings_usd": 420.48,
        "safety_risk_score": 4,
        "system_mitigations": ["Pre-migration snapshot", "Scheduled maintenance window"],
        "execution_payload": {
            # Hallucinated wildcard permissions and malicious/unsafe CLI command
            "iam_policy": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}],
            },
            "aws_cli": "rm -rf / --no-preserve-root",
            "rollback": "do nothing",
        },
    }

    sanitized = GuardrailEngine.audit_and_enrich_action(hallucinated_action)
    payload = sanitized["execution_payload"]

    # Must NOT contain wildcard Action "*"
    assert payload["iam_policy"]["Statement"][0]["Action"] != "*"
    assert "ec2:*" not in payload["iam_policy"]["Statement"][0]["Action"]
    assert "ec2:ModifyInstanceAttribute" in payload["iam_policy"]["Statement"][0]["Action"]
    assert payload["iam_policy"]["Statement"][0]["Resource"] == "arn:aws:ec2:*:*:instance/i-prod-compute-1"

    # Must NOT contain hallucinated CLI command
    assert payload["aws_cli"] != "rm -rf / --no-preserve-root"
    assert payload["aws_cli"] == "aws ec2 modify-instance-attribute --instance-id i-prod-compute-1 --instance-type m5.xlarge"

    # Must contain deterministic rollback plan
    assert payload["rollback"]["strategy"] == "revert_instance_type"
    assert "modify-instance-attribute" in payload["rollback"]["command"]


def test_valid_aws_arn_formats_and_scoped_iam_actions() -> None:
    """Validate all 5 AWS resource ARN formats and action scoping in synthesized IAM policies."""
    # 1. EC2 Instance
    ec2_policy = GuardrailEngine._generate_iam_policy({
        "resource_type": "EC2",
        "action_type": "rightsize_instance",
        "resource_id": "i-0123456789abcdef0",
    })
    assert ec2_policy["Statement"][0]["Resource"] == "arn:aws:ec2:*:*:instance/i-0123456789abcdef0"
    assert "ec2:ModifyInstanceAttribute" in ec2_policy["Statement"][0]["Action"]
    assert "ec2:StopInstances" not in ec2_policy["Statement"][0]["Action"]

    # 1b. EC2 Stop Instance
    ec2_stop = GuardrailEngine._generate_iam_policy({
        "resource_type": "EC2",
        "action_type": "stop_instance",
        "resource_id": "i-stop-123",
    })
    assert ec2_stop["Statement"][0]["Resource"] == "arn:aws:ec2:*:*:instance/i-stop-123"
    assert "ec2:StopInstances" in ec2_stop["Statement"][0]["Action"]

    # 2. EBS Volume
    ebs_policy = GuardrailEngine._generate_iam_policy({
        "resource_type": "EBS",
        "action_type": "delete_unattached_volume",
        "resource_id": "vol-0abcdef1234567890",
    })
    assert ebs_policy["Statement"][0]["Resource"] == "arn:aws:ec2:*:*:volume/vol-0abcdef1234567890"
    assert "ec2:DeleteVolume" in ebs_policy["Statement"][0]["Action"]

    # 3. Elastic IP
    eip_policy = GuardrailEngine._generate_iam_policy({
        "resource_type": "EIP",
        "action_type": "release_elastic_ip",
        "resource_id": "eipalloc-01234567",
    })
    assert eip_policy["Statement"][0]["Resource"] == "*"
    assert eip_policy["Statement"][0]["Action"] == ["ec2:DescribeAddresses", "ec2:ReleaseAddress"]

    # 4. RDS Database
    rds_policy = GuardrailEngine._generate_iam_policy({
        "resource_type": "RDS",
        "action_type": "stop_db_instance",
        "resource_id": "prod-postgres-db",
    })
    assert rds_policy["Statement"][0]["Resource"] == "arn:aws:rds:*:*:db:prod-postgres-db"
    assert "rds:StopDBInstance" in rds_policy["Statement"][0]["Action"]

    # 5. S3 Bucket
    s3_policy = GuardrailEngine._generate_iam_policy({
        "resource_type": "S3",
        "action_type": "transition_storage_tier",
        "resource_id": "corporate-cold-data",
    })
    assert s3_policy["Statement"][0]["Resource"] == "arn:aws:s3:::corporate-cold-data"
    assert "s3:PutLifecycleConfiguration" in s3_policy["Statement"][0]["Action"]

    # 6. Unknown resource type must raise ValueError (fail-closed)
    with pytest.raises(ValueError, match="Unknown or unsupported cloud resource type"):
        GuardrailEngine._generate_iam_policy({
            "resource_type": "KUBERNETES_CLUSTER",
            "action_type": "scale_down",
            "resource_id": "k8s-prod",
        })


@pytest.mark.asyncio
async def test_openrouter_strips_think_tags_and_markdown_fences() -> None:
    """OpenRouterFallbackClient must strip <think>...</think> reasoning blocks and markdown code fences."""
    import respx
    from gemini_cost_arbiter.config import ArbiterConfig
    from gemini_cost_arbiter.models.telemetry import TelemetryBatch, EC2Metrics
    from gemini_cost_arbiter.reasoner.openrouter import OpenRouterFallbackClient

    config = ArbiterConfig(
        openrouter_api_key="valid-test-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        secondary_model="deepseek/deepseek-r1",
    )
    client = OpenRouterFallbackClient(config=config)

    # Simulated DeepSeek R1 / Qwen 2.5 response with <think> tag and markdown fence
    raw_content = (
        "<think>\n"
        "Here is my internal chain of thought analysis.\n"
        "The EC2 instance is severely underutilized at 3% CPU.\n"
        "</think>\n"
        "```json\n"
        "{\n"
        '  "actions": [\n'
        "    {\n"
        '      "resource_id": "i-deepseek-test",\n'
        '      "resource_type": "EC2",\n'
        '      "action_type": "rightsize_instance",\n'
        '      "target_configuration": "t4g.small",\n'
        '      "current_monthly_spend_usd": 150.0,\n'
        '      "projected_monthly_spend_usd": 35.0,\n'
        '      "projected_monthly_savings_usd": 115.0,\n'
        '      "safety_risk_score": 2,\n'
        '      "reasoning_rationale": "DeepSeek R1 identified underutilization."\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "```"
    )

    with respx.mock:
        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"content": raw_content}}]
            })
        )
        batch = TelemetryBatch(ec2_instances=[EC2Metrics(resource_id="i-deepseek-test", monthly_spend_usd=150.0)])
        plan = await client.generate_plan(batch)
        assert plan is not None
        assert len(plan.actions) == 1
        assert plan.actions[0].resource_id == "i-deepseek-test"
        assert plan.actions[0].projected_monthly_savings_usd == 115.0


def test_sse_access_log_filter_redacts_api_key() -> None:
    """SensitiveQueryParamFilter must redact apiKey query parameter values to apiKey=*** in access logs."""
    import logging
    from gemini_cost_arbiter.mcp.server_sse import SensitiveQueryParamFilter

    filter_instance = SensitiveQueryParamFilter()
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="server.py",
        lineno=10,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:45678", "GET", "/sse?apiKey=super_secret_token_abc123&env=prod", "1.1", 200),
        exc_info=None,
    )
    filter_instance.filter(record)
    formatted = record.getMessage()
    assert "super_secret_token_abc123" not in formatted
    assert "apiKey=***" in formatted


@pytest.mark.asyncio
async def test_sse_auth_fail_closed_in_production() -> None:
    """In production mode, unconfigured MCP_API_KEY must fail closed (401 Unauthorized)."""
    from gemini_cost_arbiter.config import ArbiterConfig
    from gemini_cost_arbiter.engine import GeminiCostArbiterEngine

    # Server configured in production without an API key
    prod_engine = GeminiCostArbiterEngine(config=ArbiterConfig(environment="production", mcp_api_key=None))
    app = create_sse_app(engine=prod_engine)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Health probe remains 200 for container orchestrators
        res_health = await client.get("/health")
        assert res_health.status_code == 200

        # /messages must fail closed with 401 Unauthorized
        res_messages = await client.post("/messages", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        assert res_messages.status_code == 401
        assert "unconfigured in production" in res_messages.text

