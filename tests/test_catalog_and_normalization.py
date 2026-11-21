"""Tests for fail-closed catalog loading (REM-005) and Unicode NFKC/tag normalization (REM-006)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gemini_cost_arbiter.engine import GeminiCostArbiterEngine
from gemini_cost_arbiter.guardrails.risk_scorer import GuardrailEngine
from gemini_cost_arbiter.heuristics.ebs_rules import evaluate_ebs_volume
from gemini_cost_arbiter.heuristics.ec2_rules import (
    CatalogNotFoundError,
    evaluate_ec2_instance,
    get_instance_hourly_rate,
    load_instance_catalog,
)
from gemini_cost_arbiter.heuristics.engine import DeterministicHeuristicEngine
from gemini_cost_arbiter.heuristics.normalization import is_production_resource, normalize_str
from gemini_cost_arbiter.heuristics.rds_rules import evaluate_rds_instance
from gemini_cost_arbiter.heuristics.s3_rules import evaluate_s3_bucket
from gemini_cost_arbiter.models.telemetry import EBSMetrics, EC2Metrics, RDSMetrics, S3Metrics, TelemetryBatch


def test_missing_or_corrupted_catalog_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing, empty, or corrupted CATALOG_PATH must raise CatalogNotFoundError without silent fallbacks."""
    missing_path = tmp_path / "does_not_exist.json"
    monkeypatch.setenv("CATALOG_PATH", str(missing_path))
    with pytest.raises(CatalogNotFoundError, match="not found"):
        load_instance_catalog()

    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("CATALOG_PATH", str(corrupt_path))
    with pytest.raises(CatalogNotFoundError, match="Failed to load"):
        load_instance_catalog()

    incomplete_path = tmp_path / "incomplete.json"
    incomplete_path.write_text(json.dumps({"version": "1.0"}), encoding="utf-8")
    monkeypatch.setenv("CATALOG_PATH", str(incomplete_path))
    with pytest.raises(CatalogNotFoundError, match="Invalid catalog structure"):
        load_instance_catalog()

    monkeypatch.setenv("CATALOG_PATH", "   ")
    with pytest.raises(CatalogNotFoundError, match="empty"):
        load_instance_catalog()


def test_unknown_instance_type_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown EC2 instance types must return None instead of falling back to t4g.xlarge or 65% estimates."""
    ec2_unknown = EC2Metrics(
        resource_id="i-unknown-type-1",
        current_instance_type="z99.hypergiant",
        cpu_utilization_avg_pct=2.0,
        cpu_utilization_p95_pct=5.0,
        memory_utilization_avg_pct=15.0,
        monthly_spend_usd=900.0,
    )
    assert evaluate_ec2_instance(ec2_unknown) is None
    assert get_instance_hourly_rate("z99.hypergiant") is None

    # Even if an instance is in instance_downsize_map, missing hourly rate must fail closed (return None)
    partial_catalog = tmp_path / "partial_catalog.json"
    partial_catalog.write_text(
        json.dumps(
            {
                "instance_downsize_map": {"m5.4xlarge": "m5.xlarge"},
                "instance_hourly_rates_usd": {"m5.4xlarge": 0.768},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CATALOG_PATH", str(partial_catalog))
    ec2_missing_target_rate = EC2Metrics(
        resource_id="i-missing-target-rate",
        current_instance_type="m5.4xlarge",
        cpu_utilization_avg_pct=2.0,
        cpu_utilization_p95_pct=5.0,
        memory_utilization_avg_pct=15.0,
        monthly_spend_usd=550.0,
    )
    assert evaluate_ec2_instance(ec2_missing_target_rate) is None


def test_catalog_resolves_from_arbitrary_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default catalog path must resolve relative to package root even when cwd is outside repo."""
    monkeypatch.delenv("CATALOG_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    catalog = load_instance_catalog()
    assert "instance_downsize_map" in catalog
    assert "instance_hourly_rates_usd" in catalog


@pytest.mark.asyncio
async def test_mcp_instance_mappings_resource_uses_catalog_and_errors_on_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """finops://config/instance-mappings must use resolved catalog path and return JSON-RPC -32603 on error."""
    engine = GeminiCostArbiterEngine()
    missing_path = tmp_path / "missing_catalog.json"
    monkeypatch.setenv("CATALOG_PATH", str(missing_path))

    resp = await engine.handle_mcp_message(
        {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "resources/read",
            "params": {"uri": "finops://config/instance-mappings"},
        }
    )
    assert resp is not None
    assert resp["id"] == 99
    assert resp["error"]["code"] == -32603


def test_unicode_nfkc_and_prod_tag_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFKC normalization and prod/prd/production tag detection must apply across heuristics and guardrails."""
    assert normalize_str(" Ｐｒｏｄｕｃｔｉｏｎ ") == "production"
    assert is_production_resource(" Ｐｒｏｄｕｃｔｉｏｎ ") is True
    assert is_production_resource("staging", {"Env": "PRD"}) is True
    assert is_production_resource("dev", {"Stage": " ＰＲＯＤ "}) is True
    assert is_production_resource("dev", {"Owner": "prod"}) is False

    # EC2 with full-width Unicode environment & PRD tag -> risk == 4
    ec2_unicode_prod = EC2Metrics(
        resource_id="i-unicode-prod-1",
        current_instance_type="m5.4xlarge",
        cpu_utilization_avg_pct=3.0,
        cpu_utilization_p95_pct=8.0,
        memory_utilization_avg_pct=20.0,
        monthly_spend_usd=550.0,
        environment=" Ｐｒｏｄｕｃｔｉｏｎ ",
        tags={"Env": "PRD"},
        pricing_model=" ＲＥＳＥＲＶＥＤ ",
    )
    ec2_action = evaluate_ec2_instance(ec2_unicode_prod)
    assert ec2_action is not None
    assert ec2_action.safety_risk_score == 4
    assert ec2_action.projected_monthly_savings_usd == 0.0

    # RDS with tag-only PRD detection -> risk == 5
    rds_tag_prod = RDSMetrics(
        resource_id="rds-tag-prd",
        active_connections_avg=0.0,
        monthly_spend_usd=400.0,
        environment="staging",
        tags={"Environment": "PRD"},
    )
    rds_action = evaluate_rds_instance(rds_tag_prod)
    assert rds_action is not None
    assert rds_action.safety_risk_score == 5

    # EBS with tag-only prod detection -> risk == 3 even with snapshot
    ebs_tag_prod = EBSMetrics(
        resource_id="vol-tag-prod",
        size_gb=100,
        is_attached=False,
        days_unattached=45,
        has_snapshot=True,
        monthly_spend_usd=10.0,
        environment="dev",
        tags={"env": "prod"},
    )
    ebs_action = evaluate_ebs_volume(ebs_tag_prod)
    assert ebs_action is not None
    assert ebs_action.safety_risk_score == 3

    # S3 with full-width storage class
    s3_unicode = S3Metrics(
        resource_id="bucket-unicode-std",
        total_storage_gb=1000.0,
        object_count=1000,
        current_storage_class=" ＳＴＡＮＤＡＲＤ ",
        percentage_infrequently_accessed=75.0,
        monthly_spend_usd=100.0,
    )
    s3_action = evaluate_s3_bucket(s3_unicode)
    assert s3_action is not None

    # GuardrailEngine NFKC normalization for resource_type and ENVIRONMENT
    enriched = GuardrailEngine.audit_and_enrich_action(
        {
            "resource_id": "i-nfkc-1",
            "resource_type": " ＥＣ２ ",
            "action_type": "rightsize_instance",
            "target_configuration": "m5.xlarge",
            "safety_risk_score": 2,
            "system_mitigations": ["Snapshot"],
        }
    )
    assert "ec2:ModifyInstanceAttribute" in enriched["execution_payload"]["iam_policy"]["Statement"][0]["Action"]

    monkeypatch.setenv("ENVIRONMENT", " ＰＲＯＤ ")
    monkeypatch.delenv("PLAN_SIGNING_SECRET", raising=False)
    empty_plan = DeterministicHeuristicEngine.evaluate(TelemetryBatch())
    with pytest.raises(RuntimeError, match="PLAN_SIGNING_SECRET"):
        GuardrailEngine.attach_plan_digest(empty_plan, secret=None)
