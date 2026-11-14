"""Asynchronous Cloud-Cost Arbiter Engine with Full MCP Protocol Support.

Coordinates AI reasoning, multi-model fallback, deterministic heuristics,
safety guardrails, cryptographic plan digests, and persistent FinOps ledgers.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from pydantic import ValidationError

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.guardrails.risk_scorer import GuardrailEngine
from gemini_cost_arbiter.heuristics.engine import DeterministicHeuristicEngine
from gemini_cost_arbiter.ledger.store import FinOpsLedger
from gemini_cost_arbiter.models.audit import FinOpsAuditSummary
from gemini_cost_arbiter.models.remediation import RemediationPlan, WasteAnalysisSummary
from gemini_cost_arbiter.models.telemetry import (
    CloudResourceType,
    CloudTelemetry,
    EBSMetrics,
    EC2Metrics,
    EIPMetrics,
    RDSMetrics,
    S3Metrics,
    TelemetryBatch,
)
from gemini_cost_arbiter.reasoner.client import GeminiReasonerClient
from gemini_cost_arbiter.reasoner.openrouter import OpenRouterFallbackClient

logger = logging.getLogger("gemini_cost_arbiter")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class GeminiCostArbiterEngine:
    """FinOps Intelligence and Cloud-Cost Arbitration Engine."""

    def __init__(
        self,
        config: Optional[ArbiterConfig] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize engine with runtime configuration and optional HTTP client."""
        self.config = config or ArbiterConfig(**kwargs)
        self._custom_client = http_client

        # Subsystems
        self.gemini_client = GeminiReasonerClient(self.config, http_client=http_client)
        self.openrouter_client = OpenRouterFallbackClient(self.config, http_client=http_client)
        self.heuristic_engine = DeterministicHeuristicEngine()
        self.guardrails = GuardrailEngine()
        self.ledger = FinOpsLedger(db_path=self.config.db_path)

        # Backward compatibility properties
        self.gemini_base_url = self.config.gemini_base_url
        self.gemini_api_key = self.config.gemini_api_key
        self.openrouter_base_url = self.config.openrouter_base_url
        self.openrouter_api_key = self.config.openrouter_api_key
        self.model_name = self.config.model_name

    @property
    def audit_ledger(self) -> List[Dict[str, Any]]:
        """Access audit ledger entries."""
        return self.ledger.entries

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or initialize active HTTP client."""
        return await self.gemini_client.get_client()

    async def aclose(self) -> None:
        """Close managed network client resources."""
        await self.gemini_client.aclose()
        await self.openrouter_client.aclose()

    def reset_audit_ledger(self) -> None:
        """Reset internal FinOps audit ledger."""
        self.ledger.reset()

    def get_finops_audit_summary(self) -> FinOpsAuditSummary:
        """Retrieve structured FinOps audit summary."""
        return self.ledger.get_summary()

    # -------------------------------------------------------------------------
    # Core Analysis & Plan Generation
    # -------------------------------------------------------------------------

    async def analyze_infrastructure_waste(self, telemetry: Any) -> WasteAnalysisSummary:
        """Analyze cloud telemetry to detect resource waste and quantify savings potential."""
        batch = self._coerce_to_batch(telemetry)
        plan = await self.generate_remediation_plan(batch)

        total_resources = batch.total_resource_count
        total_spend = batch.total_monthly_spend_usd
        total_waste = plan.total_projected_monthly_savings_usd
        underutilized_count = len(plan.actions)
        savings_pct = (total_waste / total_spend * 100.0) if total_spend > 0.0 else 0.0

        findings: List[str] = []
        for action in plan.actions:
            findings.append(
                f"[{action.resource_type.value}] {action.resource_id}: {action.reasoning_rationale} "
                f"(Projected Savings: ${action.projected_monthly_savings_usd:.2f}/mo, Risk: {action.safety_risk_score}/5)"
            )

        if not findings:
            findings.append("All analyzed infrastructure resources are operating within nominal efficiency boundaries.")

        return WasteAnalysisSummary(
            total_resources_evaluated=total_resources,
            underutilized_resources_count=underutilized_count,
            total_monthly_spend_usd=total_spend,
            total_monthly_waste_usd=round(total_waste, 2),
            potential_savings_percentage=round(savings_pct, 2),
            key_findings=findings,
        )

    async def generate_remediation_plan(
        self,
        telemetry: Any,
        max_acceptable_risk: Optional[int] = None,
        risk_filter: Optional[int] = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> RemediationPlan:
        """Compile a deterministic, risk-scored remediation plan."""
        batch = self._coerce_to_batch(telemetry)
        effective_risk_threshold = (
            risk_filter
            if risk_filter is not None
            else (max_acceptable_risk if max_acceptable_risk is not None else self.config.max_acceptable_risk)
        )

        plan: Optional[RemediationPlan] = None

        # 1. Attempt Primary Gemini AI Reasoning
        should_try_gemini = self._custom_client is not None or (
            self.gemini_api_key and not self.gemini_api_key.startswith("test-")
        )

        if should_try_gemini:
            try:
                plan = await self.gemini_client.generate_plan(batch)
            except Exception as exc:
                logger.warning("Primary Gemini reasoning failed (%s); attempting secondary fallback.", exc)

        # 2. Attempt Secondary Fallback (OpenRouter) if Gemini failed or unconfigured
        should_try_openrouter = self._custom_client is not None or (
            self.openrouter_api_key
            and not self.openrouter_api_key.startswith("mock_")
            and not self.openrouter_api_key.startswith("test-")
        )

        if plan is None and should_try_openrouter:
            try:
                plan = await self.openrouter_client.generate_plan(batch)
            except Exception as exc:
                logger.warning("Secondary OpenRouter fallback failed (%s); invoking deterministic heuristics.", exc)

        # 3. Deterministic Heuristic Engine Fallback
        if plan is None:
            plan = self._evaluate_heuristics(batch)

        # 4. Enforce Safety Guardrail Risk Filter
        filtered_actions = self.guardrails.filter_by_risk(plan.actions, max_acceptable_risk=effective_risk_threshold)

        # If dry-run requested, annotate rationale
        if dry_run:
            for a in filtered_actions:
                a.reasoning_rationale = f"[DRY-RUN SIMULATION] {a.reasoning_rationale}"

        current_spend = batch.total_monthly_spend_usd
        projected_savings = round(sum(a.projected_monthly_savings_usd for a in filtered_actions), 2)
        projected_spend = round(max(0.0, current_spend - projected_savings), 2)
        avg_risk = (
            round(sum(a.safety_risk_score for a in filtered_actions) / len(filtered_actions), 2)
            if filtered_actions
            else 1.0
        )
        max_risk = max([a.safety_risk_score for a in filtered_actions], default=1)

        raw_plan = RemediationPlan(
            plan_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            actions=filtered_actions,
            total_current_monthly_spend_usd=current_spend,
            total_projected_monthly_spend_usd=projected_spend,
            total_projected_monthly_savings_usd=projected_savings,
            average_risk_score=avg_risk,
            max_risk_score=max_risk,
        )

        # Attach SHA-256 plan digest and HMAC signature for tamper prevention
        final_plan = self.guardrails.attach_plan_digest(raw_plan, secret=self.config.plan_signing_secret)

        # Update Ledger
        self.ledger.record_plan(final_plan.model_dump(), batch.total_resource_count)
        return final_plan

    def _evaluate_heuristics(self, batch: TelemetryBatch) -> RemediationPlan:
        """Run deterministic heuristic engine."""
        return self.heuristic_engine.evaluate(batch)

    def _coerce_to_batch(self, telemetry: Any) -> TelemetryBatch:
        """Normalize varied input schemas into a strict TelemetryBatch."""
        if isinstance(telemetry, TelemetryBatch):
            return telemetry
        if isinstance(telemetry, dict):
            return TelemetryBatch.model_validate(telemetry)
        if isinstance(telemetry, list):
            ec2_list: List[EC2Metrics] = []
            rds_list: List[RDSMetrics] = []
            s3_list: List[S3Metrics] = []
            ebs_list: List[EBSMetrics] = []
            eip_list: List[EIPMetrics] = []
            for item in telemetry:
                if isinstance(item, CloudTelemetry):
                    if item.resource_type == CloudResourceType.EC2:
                        ec2_list.append(
                            item.ec2_metrics
                            or EC2Metrics(resource_id=item.resource_id, monthly_spend_usd=item.monthly_cost_usd)
                        )
                    elif item.resource_type == CloudResourceType.RDS:
                        rds_list.append(
                            item.rds_metrics
                            or RDSMetrics(resource_id=item.resource_id, monthly_spend_usd=item.monthly_cost_usd)
                        )
                    elif item.resource_type == CloudResourceType.S3:
                        s3_list.append(
                            item.s3_metrics
                            or S3Metrics(resource_id=item.resource_id, monthly_spend_usd=item.monthly_cost_usd)
                        )
                    elif item.resource_type == CloudResourceType.EBS:
                        ebs_list.append(
                            item.ebs_metrics
                            or EBSMetrics(resource_id=item.resource_id, monthly_spend_usd=item.monthly_cost_usd)
                        )
                    elif item.resource_type == CloudResourceType.EIP:
                        eip_list.append(
                            item.eip_metrics
                            or EIPMetrics(resource_id=item.resource_id, monthly_spend_usd=item.monthly_cost_usd)
                        )
            return TelemetryBatch(
                ec2_instances=ec2_list,
                rds_instances=rds_list,
                s3_buckets=s3_list,
                ebs_volumes=ebs_list,
                elastic_ips=eip_list,
            )
        return TelemetryBatch()

    # -------------------------------------------------------------------------
    # Model Context Protocol (MCP) JSON-RPC 2.0 Dispatcher
    # -------------------------------------------------------------------------

    async def handle_mcp_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process inbound JSON-RPC 2.0 message according to MCP specification."""
        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        if method == "notifications/initialized":
            return None

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "prompts": {"listChanged": False},
                    },
                    "serverInfo": {
                        "name": self.config.mcp_server_name,
                        "version": self.config.mcp_server_version,
                    },
                },
            }

        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        # MCP Tools
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "analyze_infrastructure_waste",
                            "description": "Ingest multi-dimensional AWS telemetry (EC2, RDS, S3, EBS, EIP) and return quantified cloud waste metrics.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"telemetry": {"type": "object", "description": "TelemetryBatch payload"}},
                                "required": ["telemetry"],
                            },
                        },
                        {
                            "name": "generate_remediation_plan",
                            "description": "Evaluate cloud telemetry and produce a deterministic, risk-scored remediation plan with mitigations, rollbacks, and IAM policies.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "telemetry": {"type": "object", "description": "TelemetryBatch payload"},
                                    "max_acceptable_risk": {"type": "integer", "minimum": 1, "maximum": 5},
                                    "dry_run": {"type": "boolean", "default": False},
                                },
                                "required": ["telemetry"],
                            },
                        },
                        {
                            "name": "get_finops_audit_summary",
                            "description": "Retrieve cumulative FinOps audit metrics and historical savings across all evaluated batches.",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                    ]
                },
            }

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            try:
                if tool_name == "analyze_infrastructure_waste":
                    telemetry_raw = arguments.get("telemetry", {})
                    summary = await self.analyze_infrastructure_waste(telemetry_raw)
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": summary.model_dump_json(indent=2)}]
                        },
                    }

                elif tool_name == "generate_remediation_plan":
                    telemetry_raw = arguments.get("telemetry", {})
                    max_risk = arguments.get("max_acceptable_risk")
                    dry_run = bool(arguments.get("dry_run", False))
                    plan = await self.generate_remediation_plan(
                        telemetry_raw, max_acceptable_risk=max_risk, dry_run=dry_run
                    )
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": plan.model_dump_json(indent=2)}]
                        },
                    }

                elif tool_name == "get_finops_audit_summary":
                    audit = self.get_finops_audit_summary()
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": audit.model_dump_json(indent=2)}]
                        },
                    }

                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
                    }
            except (ValidationError, ValueError) as val_err:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32602, "message": f"Invalid tool arguments: {val_err}"},
                }
            except Exception as err:
                logger.exception("Error executing MCP tool: %s", err)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32603, "message": f"Internal execution error: {err}"},
                }

        # MCP Prompts
        if method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "prompts": [
                        {
                            "name": "finops_waste_audit_runbook",
                            "description": "Standardized SRE runbook for auditing multi-dimensional cloud waste and rightsizing opportunities.",
                            "arguments": [
                                {
                                    "name": "environment",
                                    "description": "Deployment environment (production, staging, development)",
                                    "required": False,
                                }
                            ],
                        },
                        {
                            "name": "remediation_rollback_procedure",
                            "description": "Step-by-step verification and emergency rollback runbook for applied cost optimizations.",
                            "arguments": [
                                {
                                    "name": "plan_id",
                                    "description": "Target RemediationPlan UUID to inspect",
                                    "required": True,
                                }
                            ],
                        },
                    ]
                },
            }

        if method == "prompts/get":
            prompt_name = params.get("name")
            args = params.get("arguments", {})

            if prompt_name == "finops_waste_audit_runbook":
                env = args.get("environment", "all")
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "description": "FinOps Waste Audit Runbook",
                        "messages": [
                            {
                                "role": "user",
                                "content": {
                                    "type": "text",
                                    "text": (
                                        f"Please execute a comprehensive cloud waste audit for target environment: '{env}'.\n"
                                        "1. Inspect EC2 compute with average CPU < 10% and peak p95 < 25%.\n"
                                        "2. Flag RDS databases with 0 active client connections.\n"
                                        "3. Identify S3 Standard buckets with > 50% infrequent access.\n"
                                        "4. Identify detached EBS volumes (>30 days) and unassociated Elastic IPs.\n"
                                        "Call 'generate_remediation_plan' with max_acceptable_risk=3."
                                    ),
                                },
                            }
                        ],
                    },
                }

            elif prompt_name == "remediation_rollback_procedure":
                plan_id = args.get("plan_id", "latest")
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "description": "Remediation Rollback Procedure",
                        "messages": [
                            {
                                "role": "user",
                                "content": {
                                    "type": "text",
                                    "text": (
                                        f"Executing emergency rollback verification for plan '{plan_id}'.\n"
                                        "1. Verify CloudWatch status check alarms for target instances.\n"
                                        "2. For EC2: execute the generated 'rollback' payload command.\n"
                                        "3. For RDS: verify pre-action snapshot integrity before restarting.\n"
                                        "4. Log the rollback event to the FinOps ledger."
                                    ),
                                },
                            }
                        ],
                    },
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Prompt '{prompt_name}' not found"},
                }

        # MCP Resources
        if method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "resources": [
                        {
                            "uri": "finops://audit/ledger",
                            "name": "FinOps Audit Ledger",
                            "description": "Live cumulative optimization metrics, total savings, and evaluated resource counts.",
                            "mimeType": "application/json",
                        },
                        {
                            "uri": "finops://policies/risk-matrix",
                            "name": "Remediation Safety Risk Matrix",
                            "description": "Calibrated 1-to-5 safety scoring guidelines and mandatory mitigation rules.",
                            "mimeType": "application/json",
                        },
                        {
                            "uri": "finops://config/instance-mappings",
                            "name": "AWS EC2 Rightsizing Lookup Catalog",
                            "description": "Active instance family downsizing and Graviton modernization mappings.",
                            "mimeType": "application/json",
                        },
                    ]
                },
            }

        if method == "resources/read":
            uri = params.get("uri")

            if uri == "finops://audit/ledger":
                summary = self.get_finops_audit_summary()
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": summary.model_dump_json(indent=2),
                            }
                        ]
                    },
                }

            elif uri == "finops://policies/risk-matrix":
                matrix = {
                    "1": "Negligible: Non-disruptive metadata or storage tiering (S3 Intelligent-Tiering).",
                    "2": "Low: Reversible storage cleanup (unattached EBS > 30d, unassociated EIP).",
                    "3": "Moderate: Non-prod compute/database state modifications (pre-change backup required).",
                    "4": "High: Production compute resize, RDS cluster modifications (canary + rollback required).",
                    "5": "Critical: Permanent termination or deletion (dual-approval gate required).",
                }
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps(matrix, indent=2),
                            }
                        ]
                    },
                }

            elif uri == "finops://config/instance-mappings":
                config_path = Path("config/instance_mappings.json")
                text_content = config_path.read_text(encoding="utf-8") if config_path.exists() else "{}"
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": text_content,
                            }
                        ]
                    },
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32602, "message": f"Resource URI '{uri}' not found"},
                }

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }

    async def run_stdio_server(self) -> None:
        """Run standard I/O JSON-RPC 2.0 loop for Model Context Protocol clients."""
        import asyncio

        logger.info("Starting Gemini Cloud-Cost Arbiter MCP Server (Model: %s)", self.model_name)
        loop = asyncio.get_running_loop()

        while True:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                try:
                    req_dict = json.loads(line)
                except json.JSONDecodeError as decode_err:
                    error_resp = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"Parse error: {decode_err}"},
                    }
                    sys.stdout.write(json.dumps(error_resp) + "\n")
                    sys.stdout.flush()
                    continue

                response = await self.handle_mcp_message(req_dict)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Unexpected error in stdio server loop: %s", e)

        await self.aclose()
