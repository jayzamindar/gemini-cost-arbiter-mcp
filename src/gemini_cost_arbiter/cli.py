"""Click-based Command Line Interface for Gemini Cost Arbiter MCP."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional
import click

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.engine import GeminiCostArbiterEngine
from gemini_cost_arbiter.models.telemetry import TelemetryBatch


@click.group()
@click.version_option(version="1.0.0", prog_name="gemini-cost-arbiter")
def main() -> None:
    """Gemini Autonomous Cloud-Cost Arbiter & FinOps MCP Server."""
    pass


@main.command("run-mcp")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"], case_sensitive=False),
    default="stdio",
    show_default=True,
    help="MCP transport protocol to host.",
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Host address for SSE transport.")
@click.option("--port", default=8000, show_default=True, type=int, help="Port for SSE transport.")
@click.option("--db-path", default=None, help="Optional SQLite database path for persistent ledger.")
def run_mcp(transport: str, host: str, port: int, db_path: Optional[str]) -> None:
    """Start the Model Context Protocol (MCP) server."""
    config = ArbiterConfig(db_path=db_path) if db_path else ArbiterConfig()
    engine = GeminiCostArbiterEngine(config=config)

    if transport.lower() == "stdio":
        click.echo("Starting Gemini Cost Arbiter MCP Server in stdio mode...", err=True)
        try:
            asyncio.run(engine.run_stdio_server())
        except KeyboardInterrupt:
            pass
    else:
        from gemini_cost_arbiter.mcp.server_sse import run_sse

        click.echo(f"Starting Gemini Cost Arbiter MCP Server in SSE mode on http://{host}:{port}/sse ...", err=True)
        run_sse(host=host, port=port, engine=engine)


@main.command("analyze")
@click.option(
    "--telemetry-file",
    "-f",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Path to JSON file containing telemetry batch.",
)
def analyze(telemetry_file: Path) -> None:
    """Analyze telemetry file and print waste breakdown."""
    content = telemetry_file.read_text(encoding="utf-8")
    data = json.loads(content)
    batch = TelemetryBatch.model_validate(data)

    engine = GeminiCostArbiterEngine()
    summary = asyncio.run(engine.analyze_infrastructure_waste(batch))
    click.echo(summary.model_dump_json(indent=2))


@main.command("plan")
@click.option(
    "--telemetry-file",
    "-f",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Path to JSON file containing telemetry batch.",
)
@click.option(
    "--max-risk",
    "-r",
    type=click.IntRange(1, 5),
    default=5,
    show_default=True,
    help="Filter out actions exceeding this safety risk score.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Execute in simulation mode without proposing mutating commands.",
)
@click.option("--db-path", default=None, help="Optional SQLite database path for persistent ledger.")
def plan(telemetry_file: Path, max_risk: int, dry_run: bool, db_path: Optional[str]) -> None:
    """Synthesize a risk-scored remediation plan from telemetry."""
    content = telemetry_file.read_text(encoding="utf-8")
    data = json.loads(content)
    batch = TelemetryBatch.model_validate(data)

    config = ArbiterConfig(db_path=db_path) if db_path else ArbiterConfig()
    engine = GeminiCostArbiterEngine(config=config)
    plan_result = asyncio.run(
        engine.generate_remediation_plan(batch, max_acceptable_risk=max_risk, dry_run=dry_run)
    )
    click.echo(plan_result.model_dump_json(indent=2))


@main.command("audit")
@click.option("--db-path", default=None, help="Optional SQLite database path to read ledger from.")
def audit(db_path: Optional[str]) -> None:
    """Display cumulative FinOps audit ledger metrics."""
    config = ArbiterConfig(db_path=db_path) if db_path else ArbiterConfig()
    engine = GeminiCostArbiterEngine(config=config)
    summary = engine.get_finops_audit_summary()
    click.echo(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
