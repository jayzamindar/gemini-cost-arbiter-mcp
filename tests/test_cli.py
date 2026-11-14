"""CLI verification tests using Click CliRunner."""

import json
from pathlib import Path
from click.testing import CliRunner
from gemini_cost_arbiter.cli import main


def test_cli_version() -> None:
    """Verify version command."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.output


def test_cli_audit() -> None:
    """Verify audit command."""
    runner = CliRunner()
    result = runner.invoke(main, ["audit"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "total_batches_processed" in data
    assert "cumulative_waste_identified_usd" in data


def test_cli_analyze_and_plan(tmp_path: Path) -> None:
    """Verify analyze and plan commands with a temporary telemetry JSON file."""
    runner = CliRunner()
    telemetry = {
        "ec2_instances": [
            {
                "resource_id": "i-cli-test",
                "current_instance_type": "m5.4xlarge",
                "cpu_utilization_avg_pct": 3.0,
                "cpu_utilization_p95_pct": 8.0,
                "monthly_spend_usd": 500.0,
                "environment": "staging",
            }
        ],
        "rds_instances": [],
        "s3_buckets": [],
    }
    telemetry_file = tmp_path / "telemetry.json"
    telemetry_file.write_text(json.dumps(telemetry), encoding="utf-8")

    # Analyze
    analyze_result = runner.invoke(main, ["analyze", "-f", str(telemetry_file)])
    assert analyze_result.exit_code == 0
    analyze_data = json.loads(analyze_result.output)
    assert analyze_data["total_resources_evaluated"] == 1
    assert analyze_data["total_monthly_spend_usd"] == 500.0

    # Plan with max risk
    plan_result = runner.invoke(main, ["plan", "-f", str(telemetry_file), "-r", "4"])
    assert plan_result.exit_code == 0
    plan_data = json.loads(plan_result.output)
    assert len(plan_data["actions"]) == 1
    assert plan_data["actions"][0]["resource_id"] == "i-cli-test"
