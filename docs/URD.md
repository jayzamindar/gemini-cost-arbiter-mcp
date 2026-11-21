# User Requirements Document (URD)

**Project:** Gemini Autonomous Cloud-Cost Arbiter (`gemini-cost-arbiter-mcp`)  
**Version:** 1.2.0  
**Status:** Approved / Tier-1 Enterprise Production Grade Hardened  
**Audience:** FinOps Stakeholders, Cloud Platform SREs, AI Agent Engineers  

---

### 1. Executive Summary & System Objective
The **Gemini Autonomous Cloud-Cost Arbiter (`gemini-cost-arbiter-mcp`)** is an automated, asynchronous FinOps intelligence engine. It continuously ingests multi-dimensional cloud utilization telemetry across AWS enterprise infrastructure (**EC2 compute, RDS databases, S3 object storage, detached EBS block storage, and unassociated Elastic IPs**), identifies systemic compute, memory, and storage waste, and leverages **Google Gemini 3.8 Flash High** reasoning (with configurable thinking budgets and multi-model secondary fallback) to synthesize deterministic, schema-validated remediation execution payloads for Model Context Protocol (MCP) clients and downstream infrastructure-as-code automation.

---

### 2. User & System Personas & RACI Matrix
* **FinOps Infrastructure Lead:** Needs automated identification of zombie and underutilized resources across compute, database, and storage assets with exact dollar waste calculations, cumulative ROI tracking, and monthly savings projections.
* **Cloud Platform SRE:** Requires deterministic, schema-governed execution payloads that adhere to strict safety guardrails without manual spreadsheet triage, complete with automated pre-change snapshots, rollback scripts, least-privilege AWS IAM policies, and **Human-in-the-Loop (HITL) cryptographic sign-off (`approve_quarantined_action`)** for quarantined critical (`safety_risk_score == 5`) or unmitigated high-risk (`>= 3`) actions.
* **Autonomous LLM Agents / MCP Clients:** Require standardized tool schemas to inspect cloud waste, query cost-arbitration decisions, trigger validated remediation plans, access standardized runbooks, and read live resources over standard JSON-RPC 2.0 transports (`stdio` and `SSE`).

| Activity | FinOps Lead | Cloud Platform SRE | Autonomous MCP Client | `GuardrailEngine` |
|:---|:---:|:---:|:---:|:---:|
| Ingest Telemetry & Analyze Waste | Informed | Consulted | **Responsible** | Accountable |
| Generate Signed Remediation Plan | Informed | Consulted | **Responsible** | **Accountable** |
| Quarantine `risk == 5` / Unmitigated `>= 3` | Informed | Informed | Informed | **Responsible / Accountable** |
| Issue Signed HITL Approval (`<= 300s` TTL) | Consulted | **Accountable / Approver** | **Responsible** (submits token) | **Verifies HMAC + Nonce** |
| Review Audit Ledger (`audit` / `finops://audit/ledger`) | **Accountable** | Consulted | **Responsible** | Informed |

---

### 3. Functional Requirements (FR)

#### FR-1: Multi-Dimensional Telemetry Ingestion
* **FR-1.1 (EC2 Compute):** Ingest raw telemetry for AWS EC2 instances: `cpu_utilization_avg_pct`, `cpu_utilization_p95_pct`, `memory_utilization_avg_pct`, `network_in_out_mbps`, `current_instance_type`, and `monthly_spend_usd`.
* **FR-1.2 (RDS Databases):** Ingest telemetry for AWS RDS instances: `cpu_utilization_avg_pct`, `memory_free_bytes`, `storage_allocated_gb`, `storage_used_gb`, `active_connections_avg`, `multi_az`, `current_instance_class`, and `monthly_spend_usd`.
* **FR-1.3 (S3 Storage):** Ingest telemetry for AWS S3 storage buckets: `total_storage_gb`, `object_count`, `current_storage_class`, `lifecycle_rules_configured`, `percentage_infrequently_accessed`, and `monthly_spend_usd`.
* **FR-1.4 (EBS Block Storage):** Ingest telemetry for AWS EBS volumes: `volume_id`, `volume_size_gb`, `volume_type`, `is_attached`, `days_detached`, `has_snapshot`, and `monthly_spend_usd`.
* **FR-1.5 (Elastic IP Addresses):** Ingest telemetry for AWS Elastic IPs: `allocation_id`, `public_ip`, `is_associated`, `days_idle`, and `monthly_spend_usd`.
* **FR-1.6 (Heterogeneous Batch Normalization):** Support both single-resource evaluation and batch telemetry ingestion (`TelemetryBatch`).

#### FR-2: AI Arbiter Reasoner (Gemini 3.8 Flash High) & Multi-Model Resilience
* **FR-2.1:** Telemetry must be evaluated directly without human preprocessing, relying on the high-cognitive reasoning capabilities of Gemini 3.8 Flash High to detect subtle patterns of waste.
* **FR-2.2:** The reasoner shall apply configurable reasoning thinking budgets (e.g. 1024 to 4096 tokens) to evaluate trade-offs between performance degradation risks, cost optimization, and operational reliability.
* **FR-2.3:** The engine shall maintain an asynchronous non-blocking connection pool via `httpx.AsyncClient` targeting the Google Gemini API (`generativelanguage.googleapis.com/v1beta`).
* **FR-2.4:** The system shall support secondary multi-model fallback to OpenRouter (e.g. Qwen 2.5 Coder 32B) when primary Gemini API quotas are exhausted or rate-limited.
* **FR-2.5 (Hierarchical PromptOps):** System prompts must follow a structured hierarchy: a Tier-0 Master System Prompt (`prompts/master_system_prompt.md`) coupled with 6 domain cognitive modules (`prompts/modules/`).

#### FR-3: Structured Egress Contracts & Zero-Hallucination Guarantees
* **FR-3.1:** All outputs generated by the AI reasoning model must parse strictly into immutable, bounded Pydantic v2 data models (`RemediationPlan`, `RemediationActionItem`, `WasteAnalysisSummary`) with `ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)`.
* **FR-3.2 (Constrained Decoding):** LLM calls must inject `generationConfig.responseSchema = clean_gemini_schema(RemediationPlan.model_json_schema())` directly into Gemini API calls to dereference `$defs`/`$ref`, collapse `anyOf` unions, exclude `execution_payload`, and strip unsupported JSON-Schema keywords.
* **FR-3.3 (Fail-Closed Ground-Truth Catalog):** Target instance types must be verified against `config/instance_mappings.json` resolved via `CATALOG_PATH`. Missing or invalid catalogs raise `CatalogNotFoundError` (fail closed), and unknown instance types return `None` rather than silent fallback defaults.
* **FR-3.4 (Deterministic Rollbacks, `shlex.quote()` CLI & Zero-Wildcard IAM):** Execution payloads must provide machine-readable action parameters (`aws_cli`), automated rollback commands (`rollback`), and least-privilege AWS IAM statements (`iam_policy`) with zero `"*"` wildcards. All CLI/rollback arguments are regex-validated and `shlex.quote()`-escaped in Python, unconditionally overwriting any LLM-generated strings.
* **FR-3.5 (Canonical HMAC-SHA256 Plan Signing):** The plan must include a SHA-256 integrity hash (`plan_digest`) and an HMAC-SHA256 signature (`plan_signature`) computed over canonical JSON (`sort_keys=True, separators=(",", ":"), ensure_ascii=False`). In `production`, missing, short (`< 32` chars), or placeholder `PLAN_SIGNING_SECRET` values fail closed with `RuntimeError`.
* **FR-3.6 (Dry-Run Simulation & CLI Workflows):** The CLI (`src/gemini_cost_arbiter/cli.py`) must provide `analyze -f sample_telemetry.json`, `plan -f sample_telemetry.json --max-risk 3 --dry-run`, `audit --db-path ./data/finops.db`, and `run-mcp --transport stdio|sse`.
* **FR-3.7 (Real AWS Pricing Catalog Lookup):** EC2 right-sizing projected savings must be computed from standard AWS On-Demand hourly rate differentials multiplied by 730 hours/month looked up directly from `config/instance_mappings.json`, replacing flat percentage multipliers.

#### FR-4: Safety Guardrails & Risk Scoring (1 to 5)
* **FR-4.1:** Every proposed remediation action must be classified with a deterministic Safety Risk Score ranging from **1** (lowest operational risk) to **5** (highest operational risk):
  * **Level 1 (Zero / Negligible Risk):** Reversible, non-disruptive changes (S3 Intelligent-Tiering transition, lifecycle rules).
  * **Level 2 (Low Risk):** Reversible cleanup with verified snapshot presence (delete unattached EBS volumes older than 30 days with snapshot, release idle Elastic IP).
  * **Level 3 (Moderate Risk):** Modifying compute/database state on non-production tiers (Dev/Staging EC2 downsizing, Dev RDS stop, EBS delete without snapshot).
  * **Level 4 (High Risk):** Modifying production compute (Prod EC2 downsizing, RDS instance class change).
  * **Level 5 (Critical Risk):** Permanent termination or irreversible data drop (terminating instances, deleting RDS database instances).
* **FR-4.2 (Mandatory Mitigations):** Any action with a risk score of **3 or higher** MUST include non-empty `system_mitigations` (automated pre-action AMI/EBS snapshot, rollback runbook, maintenance window scheduling).
* **FR-4.3:** The system must provide a `max_acceptable_risk` threshold filter to prune or flag actions that exceed the client's current risk policy.
* **FR-4.4 (Quarantine & HITL Anti-Replay Gate):** Any action with `safety_risk_score == 5` is unconditionally quarantined (`quarantined=True`, `quarantine_reason="Critical risk (5/5) requires signed HITL SRE approval"`). Additionally, any action with `safety_risk_score >= 3` lacking non-empty `system_mitigations` is quarantined. Quarantined actions require cryptographic SRE release via `approve_quarantined_action` (`<= 300s` TTL + single-use `nonce` anti-replay protection).
* **FR-4.5 (EC2 Memory Floor & Pricing Model Guardrails):** EC2 instances with average memory utilization > 65% are disqualified from downsizing to prevent Out-Of-Memory (OOM) crashes. Instances covered by Reserved Instance (RI) or Savings Plan commitments are tagged with $0.00 net billing savings.
* **FR-4.6 (S3 Small-Object Economics Guardrail):** S3 buckets with average object size < 128 KB are disqualified from Intelligent-Tiering to protect customers against net cost increases from the per-object monitoring fee.

#### FR-5: Model Context Protocol (MCP) Integration & Transports
* **FR-5.1 (Tools Catalog):** Expose 4 standard MCP tools:
  * `analyze_infrastructure_waste`: Ingests telemetry and returns waste breakdown, projected savings, and candidate remediation opportunities.
  * `generate_remediation_plan`: Generates structured, risk-scored remediation action items with concrete system mitigations and execution payloads.
  * `get_finops_audit_summary`: Returns cumulative cloud waste detected, total projected monthly savings, and breakdown by AWS resource type.
  * `approve_quarantined_action`: Verifies a signed, time-bounded (`<= 300s` TTL) anti-replay HITL SRE approval token (`{plan_id, resource_id, issued_at, expires_at, nonce}`) to release a quarantined action.
* **FR-5.2 (Prompts Catalog):** Expose standardized MCP prompts:
  * `finops_waste_audit_runbook`: Standardized SRE runbook for systematic waste inspection.
  * `remediation_rollback_procedure`: Emergency rollback execution prompt.
* **FR-5.3 (Resources Catalog):** Expose live read-only MCP resources:
  * `finops://audit/ledger`: Real-time cumulative audit metrics in JSON format.
  * `finops://policies/risk-matrix`: Safety scoring rules and mandatory mitigation criteria.
  * `finops://config/instance-mappings`: Active AWS EC2 rightsizing catalog.
* **FR-5.4 (Dual Transports & DoS Protection):** MCP communication adheres to JSON-RPC 2.0 over `stdio` and `SSE`. The SSE transport enforces `MAX_PAYLOAD_BYTES` (`10485760` / HTTP `413 Payload Too Large`) and generates `secrets.token_urlsafe(16)` session IDs.
* **FR-5.5 (Timing-Safe Authentication & Fail-Closed Protection):** The SSE transport enforces constant-time `hmac.compare_digest()` token comparison across Bearer tokens, `X-API-Key` headers, and query parameters (`?apiKey=` / `?api_key=`), redacts `apiKey`/`api_key` case-insensitively in access logs, and fails closed (HTTP 401) in production when `MCP_API_KEY` is unconfigured or a placeholder.

#### FR-6: Stateful Audit Ledger & Persistence
* **FR-6.1:** Maintain cumulative metrics across active execution batches: total batches processed, total resources audited, cumulative dollar waste discovered, and net savings projected.
* **FR-6.2 (Concurrent SQLite WAL Persistence):** Support persistent storage via `--db-path` using SQLite WAL mode (`PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`), `threading.RLock`, and `filelock.FileLock` so ledger state survives restarts under concurrent access.

---

### 4. Non-Functional Constraints (NFR)

| Constraint ID | Category | Requirement Specification |
|:---|:---|:---|
| **NFR-1** | Runtime & Language | Python 3.13+ (operational on Python 3.14). Native asynchronous execution via `asyncio`. |
| **NFR-2** | Zero Boilerplate | Strict Antigravity engineering paradigms: zero heavy orchestrator frameworks, 100% strict `mypy src` type annotations, `ruff` clean. |
| **NFR-3** | Context & Cost Budget | Token-efficient prompt compression (`MAX_PROMPT_CHARS = 32768`, `MAX_OUTPUT_TOKENS = 8192`), `MAX_SESSION_TOKEN_BUDGET = 500000`, `DAILY_API_COST_LIMIT_USD = $10.00`. |
| **NFR-4** | Determinism & Robustness | `LLMQuotaCircuitBreaker` (3-failure cooldown, `30s` timeout, `max_retries=2`) falling back to the deterministic SRE heuristic engine for 100% availability. |
| **NFR-5** | Testing Integrity | `94/94` automated `pytest` tests passing with `93.42%` coverage (`>= 90%` gate), `mypy --strict` clean, `ruff` clean (Python 3.13 & 3.14). |
| **NFR-6** | Packaging & Size | Multi-stage Docker container executing as non-root user (`appuser`, UID 10001) with image content size $\le 100\text{ MB}$ (verified at 65.5 MB). |
| **NFR-7** | Turnkey Deployment | Multi-cloud deployment blueprints for AWS Free Tier (`deploy/aws/`), Azure Container Apps (`deploy/azure/`), and Google Cloud Run / Gemini MCP (`deploy/gemini/`). |

---

### 5. Remediation Safety Risk Scoring Matrix

```
+------------------------------------------------------------------------------------------------------+
| Score | Risk Level | Description                 | Applicable Actions        | Mandatory Mitigations |
+-------+------------+-----------------------------+---------------------------+-----------------------+
|   1   | Negligible | Non-disruptive, metadata    | S3 lifecycle policy,      | None required         |
|       |            | or automated tiering        | Intelligent-Tiering       |                       |
+-------+------------+-----------------------------+---------------------------+-----------------------+
|   2   | Low        | Reversible cleanup with     | Delete unattached EBS >30d| Verify age > 30 days, |
|       |            | prior snapshot check        | (with snap), release EIP  | verify tag != prod    |
+-------+------------+-----------------------------+---------------------------+-----------------------+
|   3   | Moderate   | Stoppable compute changes   | EC2/RDS right-sizing in   | Pre-change backup,    |
|       |            | on non-critical tiers       | Dev/Staging, EBS no snap  | maintenance window    |
+-------+------------+-----------------------------+---------------------------+-----------------------+
|   4   | High       | Production compute resize,  | Production EC2 rightsize, | Automated snapshot,   |
|       |            | database storage shrink     | RDS instance class change | Canary health check,  |
|       |            |                             |                           | Rollback automation   |
+-------+------------+-----------------------------+---------------------------+-----------------------+
|   5   | Critical   | Destructive termination or  | EC2 instance termination, | Dual-approval gate,   |
|       |            | volume deletion             | RDS permanent delete      | Forensic AMI backup,  |
|       |            |                             |                           | 7-day soft-delete     |
+------------------------------------------------------------------------------------------------------+
```

---

### 6. Acceptance Criteria
1. Given raw EC2 telemetry showing 3% average CPU on an `m5.4xlarge` costing $550/month, the engine proposes rightsizing to `m5.xlarge` or `t4g.xlarge`, calculates savings exceeding $400/month, assigns safety score 3 (or 4 if production), and supplies automated snapshot mitigations and rollback plans.
2. Given unattached EBS volume telemetry older than 30 days, the engine detects orphan waste, synthesizes pre-delete snapshot mitigations, and generates least-privilege IAM statements.
3. Given unassociated Elastic IP telemetry idle for $\ge 7$ days, the engine proposes releasing the address, calculates $100\%$ savings, and assigns Risk Score 2.
