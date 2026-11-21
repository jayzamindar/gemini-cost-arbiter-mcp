# Technical Requirements Document (TRD)

**Project:** Gemini Autonomous Cloud-Cost Arbiter (`gemini-cost-arbiter-mcp`)  
**Version:** 1.2.0  
**Status:** Approved / Tier-1 Enterprise Production Blueprint  
**Authors:** Principal Senior AI Systems Architect & Lead Software Engineer  
**Target Audience:** SREs, Systems Architects, Backend Engineers, Agent Developers  

---

## 1. System Technology Stack & Architectural Constraints

```
+-----------------------------------------------------------------------------------+
|                        gemini-cost-arbiter-mcp Architecture                       |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Transports: stdio (JSON-RPC 2.0 loop) | SSE / HTTP (FastAPI & Starlette)     |  |
|  +-----------------------------------------------------------------------------+  |
|                                        |                                          |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  | Engine Orchestrator: GeminiCostArbiterEngine (Python 3.13+ / asyncio)       |  |
|  +-----------------------------------------------------------------------------+  |
|          |                                   |                       |            |
|          v                                   v                       v            |
|  +-------------------+             +-------------------+   +-------------------+  |
|  | Gemini 3.8 Flash  |             | Deterministic SRE |   | Safety Guardrails |  |
|  | High Reasoner     |             | Heuristic Engine  |   | & Risk Scorer     |  |
|  | (Thinking Budget) |             | (Zero-LLM Uptime) |   | (Scale 1 to 5)    |  |
|  +-------------------+             +-------------------+   +-------------------+  |
|          |                                   |                       |            |
|          v                                   v                       v            |
|  +-----------------------------------------------------------------------------+  |
|  | Contracts & Storage: Pydantic v2 Models | SQLite & In-Memory Audit Ledger   |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### 1.1 Core Runtime & Dependencies
* **Language Runtime:** Python 3.13+ (fully operational on Python 3.14). Native asynchronous execution via `asyncio`.
* **Data Validation & Parsing:** `pydantic>=2.10.0` and `pydantic-settings>=2.7.0` for strict runtime schema enforcement.
* **Network & HTTP Clients:** `httpx>=0.28.0` with `Timeout(30.0, connect=10.0)`, `max_retries=2` (exponential backoff + jitter), and `LLMQuotaCircuitBreaker` (`MAX_SESSION_TOKEN_BUDGET=500000`, `DAILY_API_COST_LIMIT_USD=10.00`, `circuit_breaker_failure_threshold=3`).
* **MCP Web Transports:** `fastapi>=0.115.0`, `uvicorn>=0.30.0`, and `sse-starlette>=2.1.0`.
* **CLI & Persistence:** `click>=8.1.0` and `filelock>=3.16.0` for concurrent SQLite WAL locking.
* **Quality & Test Harness:** `ruff`, `mypy` (`strict = true`), `pytest>=8.3.0`, `pytest-asyncio>=0.25.0`, `pytest-cov>=6.0.0` (`>= 90%` gate), `pytest-timeout>=2.3.1` (`10s`), `respx>=0.22.0`.

### 1.2 Immutable Pydantic v2 Contracts & `ArbiterConfig`
* **Model Strictness:** All domain models under `src/gemini_cost_arbiter/models/` enforce `ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)`, bounded strings (`resource_id` `^[a-zA-Z0-9._:/-]+$`, `1..128` chars; `current_instance_type` `^[a-zA-Z0-9.-]+$`, `2..64` chars), bounded collections (`max_length=500` on `TelemetryBatch` lists and `actions`, `max_length=64` on `tags`), and `@model_validator(mode="after")` on `RemediationPlan` (`verify_savings_sum`, tolerance `<= 0.01`).
* **Runtime Settings (`ArbiterConfig`, `extra="forbid"`):** `DEFAULT_MODEL=gemini-3.8-flash-high`, `SECONDARY_MODEL=qwen/qwen-2.5-coder-32b-instruct`, `THINKING_BUDGET=2048`, `MAX_OUTPUT_TOKENS=8192`, `MAX_SESSION_TOKEN_BUDGET=500000`, `DAILY_API_COST_LIMIT_USD=10.00`, `CIRCUIT_BREAKER_FAILURE_THRESHOLD=3`, `MAX_PAYLOAD_BYTES=10485760`, `CATALOG_PATH=config/instance_mappings.json`, `PROMPTS_DIR=prompts`, `DB_PATH`, `PLAN_SIGNING_SECRET`, `MCP_API_KEY`.

---

## 2. Mathematical Formulations & FinOps Optimization Rules

### 2.1 EC2 Compute Waste & Rightsizing Formula
An EC2 instance $i$ is evaluated for rightsizing under the following multi-dimensional conditions:

$$\text{Underutilized}(i) = \left( \text{CPU}_{\text{avg}}(i) < 10.0\% \right) \land \left( \text{CPU}_{\text{p95}}(i) < 25.0\% \right)$$

$$\text{MemorySafe}(i) = \left( \text{RAM}_{\text{avg}}(i) \le 65.0\% \right)$$

* **OOM Prevention Guardrail:** If $\text{Underutilized}(i)$ holds but $\neg \text{MemorySafe}(i)$ ($\text{RAM}_{\text{avg}} > 65\%$), downsizing is **aborted** to prevent Out-Of-Memory application crashes.
* **Pricing Model & Fail-Closed Catalog Rates Formula:**
  $$\text{Savings}_{\text{EC2}}(i) = \begin{cases} 0.00, & \text{if } \text{PricingModel}(i) \in \{\text{"reserved"}, \text{"savings\_plan"}\} \\ \min\left(\text{Spend}_{\text{monthly}}(i), \text{round}((\text{Rate}_{\text{curr}} - \text{Rate}_{\text{tgt}}) \times 730, 2)\right), & \text{if Catalog Rates Available} \\ \text{None (abort/skip)}, & \text{if instance type absent from catalog} \end{cases}$$
  Where $\text{Rate}_{\text{curr}}$ and $\text{Rate}_{\text{tgt}}$ are the standard AWS On-Demand hourly USD rates from `config/instance_mappings.json` (resolved via `CATALOG_PATH`; missing/corrupted catalogs fail closed with `CatalogNotFoundError`) and 730 is the standard operating hours per month.
* **Unicode NFKC Normalization & Safety Risk Assignment:**
  All string comparisons (`environment`, `pricing_model`, `resource_type`, `current_instance_type`, `tags`) normalize via `unicodedata.normalize("NFKC", val).strip().casefold()`. Production detection (`is_production_resource()`) matches `{"production", "prod", "prd"}` across `environment` and tag keys `{"environment", "env", "stage"}`.
  $$\text{Risk}_{\text{EC2}}(i) = \begin{cases} 4, & \text{if } \text{is\_production\_resource}(i) \\ 3, & \text{otherwise} \end{cases}$$

### 2.2 RDS Database Idle Connection Formula
An RDS database instance $d$ is classified as an idle zombie instance if:
$$\text{Connections}_{\text{avg}}(d) == 0.0$$

When verified:
* **Target Action:** `STOP_DB_INSTANCE`
* **Pricing Model Floor:**
  $$\text{Savings}_{\text{RDS}}(d) = \begin{cases} 0.00, & \text{if } \text{PricingModel}(d) \in \{\text{"reserved"}, \text{"savings\_plan"}\} \\ \text{round}(\text{Spend}_{\text{monthly}}(d) \times 0.85, 2), & \text{otherwise} \end{cases}$$
* **Safety Risk Assignment:**
  $$\text{Risk}_{\text{RDS}}(d) = \begin{cases} 5, & \text{if } \text{Environment}(d) = \text{"production"} \\ 3, & \text{otherwise} \end{cases}$$

### 2.3 S3 Storage Cold Tiering & Small-Object Floor Formula
An S3 bucket $b$ is eligible for intelligent tiering optimization if and only if both access and object size thresholds hold:
$$\text{InfrequentAccessPct}(b) > 50.0\% \quad \land \quad \text{StorageClass}(b) = \text{"STANDARD"}$$

$$\text{AvgObjectSizeKB}(b) = \frac{\text{TotalStorageBytes}(b)}{1024 \times \max(\text{ObjectCount}(b), 1)} \ge 128.0\text{ KB}$$

* **Small-Object Monitoring Fee Trap:** If $\text{AvgObjectSizeKB}(b) < 128.0$, `INTELLIGENT_TIERING` is **disqualified** because the \$0.0025 per 1,000 objects monitoring charge exceeds standard storage savings.
* **Projected Monthly Savings:**
  $$\text{Savings}_{\text{S3}}(b) = \text{round}(\text{Spend}_{\text{monthly}}(b) \times 0.40, 2)$$
* **Safety Risk Assignment:** $\text{Risk}_{\text{S3}}(b) = 1$ (Negligible risk; completely non-disruptive).

### 2.4 EBS Block Storage Detached Volume Formula
An EBS volume $v$ is classified as orphan storage waste if:
$$\text{IsAttached}(v) = \text{False} \quad \land \quad \text{DaysDetached}(v) \ge 30$$

When verified:
* **Target Action:** `TERMINATE`
* **Projected Monthly Savings:**
  $$\text{Savings}_{\text{EBS}}(v) = \text{round}(\text{Spend}_{\text{monthly}}(v) \times 1.00, 2)$$
* **Safety Risk Assignment:**
  $$\text{Risk}_{\text{EBS}}(v) = \begin{cases} 2, & \text{if } \text{HasSnapshot}(v) = \text{True} \\ 3, & \text{otherwise} \end{cases}$$

### 2.5 Elastic IP Idle Reclamation Formula
An Elastic IP address $e$ is classified as idle IP waste if:
$$\text{IsAssociated}(e) = \text{False} \quad \land \quad \text{DaysIdle}(e) \ge 7$$

When verified:
* **Target Action:** `RELEASE_ADDRESS`
* **Projected Monthly Savings:**
  $$\text{Savings}_{\text{EIP}}(e) = \text{round}(\text{Spend}_{\text{monthly}}(e) \times 1.00, 2)$$
* **Safety Risk Assignment:** $\text{Risk}_{\text{EIP}}(e) = 2$ (Low risk; reversible address release).

### 2.6 Canonical Full-Payload Plan Signing & HITL Anti-Replay Verification
To guarantee plan authenticity and prevent intermediary tampering across all metadata and execution payloads:
$$\text{Canonical}(X) = \text{json.dumps}(X, \text{sort\_keys=True}, \text{separators}=("," , ":"), \text{ensure\_ascii=False}).\text{encode}(\text{"utf-8"})$$
$$\text{Digest} = \text{SHA256}\left(\text{Canonical}(\text{Plan} \setminus \{\text{plan\_digest}, \text{plan\_signature}\})\right)$$
$$\text{Signature} = \text{HMAC-SHA256}\left( K_{\text{signing}}, \text{Canonical}(\text{Plan} \setminus \{\text{plan\_digest}, \text{plan\_signature}\}) \right)$$

Where $K_{\text{signing}}$ is `PLAN_SIGNING_SECRET`. In `production`, missing, short (`< 32` chars), or known placeholder secrets fail closed with `RuntimeError`.
* **Critical Risk (`5/5`) Quarantine & HITL Anti-Replay Gate:** All `safety_risk_score == 5` actions and all `safety_risk_score >= 3` actions lacking non-empty `system_mitigations` are quarantined (`quarantined=True`). Release via `GuardrailEngine.verify_hitl_approval(...)` validates canonical HMAC-SHA256 over `{plan_id, resource_id, issued_at, expires_at, nonce}`, rejecting `expires_at - issued_at > 300`, `now >= expires_at`, and replayed `nonce`s (`RLock`-protected).

### 2.7 Deterministic IAM & CLI Execution Synthesis (Zero-Hallucination)
To guarantee that downstream agent orchestrators never execute hallucinated or over-privileged AWS commands:
* `execution_payload["iam_policy"]`: Synthesized deterministically in Python with **zero `"*"` wildcards** and standard AWS IAM resource ARN formats:
  - EC2 instance: `arn:aws:ec2:*:*:instance/{res_id}`
  - EBS volume: `arn:aws:ec2:*:*:volume/{res_id}`
  - Elastic IP: `arn:aws:ec2:*:*:elastic-ip/{res_id}` (with `ec2:DescribeAddresses`, `ec2:ReleaseAddress`)
  - RDS database: `arn:aws:rds:*:*:db:{res_id}`
  - S3 bucket: `arn:aws:s3:::{res_id}`
  - Actions are scoped specifically to `action.action_type`, and unknown resource types or `res_id == "*"` fail closed with `ValueError`.
* `execution_payload["aws_cli"]`: Deterministically generated using regex-validated (`^[a-zA-Z0-9._:/-]+$` / `^[a-zA-Z0-9._-]+$`) and `shlex.quote()`-escaped arguments.
* `execution_payload["rollback"]`: Programmatically populated with `shlex.quote()`-escaped recovery commands and CloudWatch alarm references.
* **Unconditional Overwrite & LLM FinOps Reconciliation:** `GuardrailEngine.audit_and_enrich_action` unconditionally replaces LLM-generated IAM/CLI/rollback fields, and `GuardrailEngine.reconcile_with_telemetry` vetoes EC2 downsizes $> 65\%$ RAM, S3 tiering $< 128\text{ KB}$, zeroes RI/Savings Plan savings, and caps savings at `current_monthly_spend_usd`.

### 2.8 Gemini `responseSchema` Compliance & Prompt Injection Defense
To satisfy Google Gemini's strict REST API schema parser (`google.ai.generativelanguage.v1beta.Schema`) and defend against untrusted telemetry payloads:
* **Strict Field Allowlist:** `clean_gemini_schema()` strictly enforces an allowlist (`{"type", "format", "description", "nullable", "enum", "items", "properties", "required", "propertyOrdering"}`), dropping `minimum`, `maximum`, `$schema`, `$defs`, `title`, and `additionalProperties`.
* **Dereferencing `$defs`/`$ref` & Multi-Branch `anyOf` Collapse:** All JSON Schema references are inlined recursively. Nullable `anyOf` collapses to `{"type": "T", "nullable": true}`; multi-branch `anyOf` selects the first non-null branch (preserving `nullable=True` if `null` was present) rather than emitting `{}`.
* **Execution Payload Exclusion:** `execution_payload` is excluded from the LLM egress `responseSchema`.
* **Prompt Defense & Compression:** `sanitize_string()` NFKC-normalizes and strips `<`/`>` XML breakout characters; `compile_reasoner_prompt()` dumps with `exclude_none=True, exclude_defaults=True`, caps at `MAX_PROMPT_CHARS=32768`, and wraps telemetry in `<untrusted_proposal_data>...</untrusted_proposal_data>`. `load_prompt_file()` enforces `Path.resolve().is_relative_to(prompts_dir.resolve())`.
* **Unified `<think>` Stripping:** Both `GeminiReasonerClient` and `OpenRouterFallbackClient` strip `<think>...</think>` blocks and markdown fences before JSON parsing.

---

## 3. Model Context Protocol (MCP) JSON-RPC 2.0 Specification

The engine conforms strictly to MCP Specification Version `2024-11-05`.

### 3.1 Tools Interface (4 MCP Tools)
1. **`analyze_infrastructure_waste`**: Ingests `TelemetryBatch` and returns `WasteAnalysisSummary`.
2. **`generate_remediation_plan`**: Ingests `TelemetryBatch`, `max_acceptable_risk`, and `dry_run` flag, returning validated `RemediationPlan` with SHA-256 digest, HMAC-SHA256 signature, and quarantine annotations.
3. **`get_finops_audit_summary`**: Returns `FinOpsAuditSummary` from the active persistent ledger.
4. **`approve_quarantined_action`**: Verifies a signed, time-bounded (`<= 300s` TTL) anti-replay HITL approval (`plan_id`, `resource_id`, `issued_at`, `expires_at`, `nonce`, `signature`) to release a quarantined action.

### 3.2 Prompts Interface
* `prompts/list`: Returns registered runbooks:
  - `finops_waste_audit_runbook`
  - `remediation_rollback_procedure`
* `prompts/get`: Returns the prompt text and argument bindings for interactive agent execution.

### 3.3 Resources Interface
* `resources/list`: Returns registered read-only resource URIs:
  - `finops://audit/ledger`
  - `finops://policies/risk-matrix`
  - `finops://config/instance-mappings`
* `resources/read`: Streams JSON or Markdown payloads for the requested URI.

### 3.4 Transport Security, Body Limits & Timing-Safe Authentication (SSE)
* When `MCP_API_KEY` is configured, `/sse` and `/messages` endpoints require valid authentication via `Authorization: Bearer <key>`, `X-API-Key: <key>`, or `?apiKey=<key>`/`?api_key=<key>` using constant-time `hmac.compare_digest()`.
* **Fail-Closed Protection:** In `production`, unconfigured or placeholder `MCP_API_KEY` values fail closed with HTTP `401 Unauthorized`.
* **DoS & Session Hardening:** `POST /messages` enforces `MAX_PAYLOAD_BYTES=10485760` (10 MB / HTTP `413 Payload Too Large`); `GET /sse` allocates cryptographically random `secrets.token_urlsafe(16)` session IDs.
* **Case-Insensitive Log Redaction:** `SensitiveQueryParamFilter` on `uvicorn.access` redacts `r"(?i)(api_?key)=[^&\s\"]+"` to `\1=***`.
* **Unauthenticated Probes:** `/health` remains unauthenticated for container orchestrators.

---

## 4. Hierarchical PromptOps Architecture

Prompts are version-controlled under `prompts/` and decoupled into two operational tiers:
1. **Tier-0 Master System Prompt (`prompts/master_system_prompt.md`):**
   - Establishes global SRE persona, zero-hallucination non-negotiables, calibrated risk bounds (1-5), and anti-injection regex sanitization.
2. **Modular Domain Cognitive Modules (`prompts/modules/`):**
   - `01_ec2_compute_reasoning.md`: CPU avg/p95 and Graviton modernization.
   - `02_rds_database_reasoning.md`: Zombie database detection and Multi-AZ downsizing.
   - `03_s3_storage_tiering.md`: Intelligent-Tiering and Glacier lifecycle transitions.
   - `04_ebs_eip_reclamation.md`: Orphan EBS volumes and idle Elastic IPs.
   - `05_guardrails_rollback_iam.md`: Automated rollbacks and least-privilege IAM statements.
   - `06_mcp_operational_runbooks.md`: SRE agent runbooks for audits and emergency rollbacks.

---

## 5. Storage Schema: Concurrent SQLite WAL Persistent Ledger

When invoked with `--db-path <path>` (`DB_PATH`), `FinOpsLedger` auto-creates parent directories, serializes writes via `threading.RLock` and `filelock.FileLock`, and enables `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA synchronous=NORMAL;` with `ensure_ascii=False` JSON serialization:

```sql
CREATE TABLE IF NOT EXISTS finops_ledger (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    total_batches_analyzed INTEGER NOT NULL DEFAULT 0,
    total_resources_audited INTEGER NOT NULL DEFAULT 0,
    cumulative_waste_detected_usd REAL NOT NULL DEFAULT 0.0,
    cumulative_projected_savings_usd REAL NOT NULL DEFAULT 0.0,
    total_remediations_generated INTEGER NOT NULL DEFAULT 0,
    last_updated_timestamp TEXT NOT NULL
);
```

---

## 6. Container Packaging & Turnkey Free Tier Deployment Specs

### 6.1 Multi-Stage Dockerfile Runtime
* **Base Image:** `python:3.13-slim`
* **Security Hardening:** Non-root system user (`appuser`, UID/GID 10001). Compilers (`gcc`, `build-essential`) isolated strictly to builder stage.
* **Image Size:** Verified at **65.5 MB**.
* **Health Probe:** Validates HTTP 200 on `/health` endpoint every 30s.

### 6.2 Multi-Cloud & Gemini Deployment Specs
* **AWS Free Tier (`deploy/aws/`):** EC2 setup on Amazon Linux 2023 / Ubuntu 24.04 (`t3.micro` / `t4g.small`, 512 MB RAM cap) and AWS Lambda Web Adapter (`public.ecr.aws/awslabs/aws-lambda-adapter:0.8.4`) with `prompts/` included in image.
* **Microsoft Azure (`deploy/azure/`):** Azure Container Registry + Azure Container Apps (`deploy-azure.sh`, `docker-compose.azure.yml`).
* **Google Cloud Run & Gemini MCP (`deploy/gemini/`):** Cloud Build (`cloudbuild.yaml`), Cloud Run service manifest (`service.yaml`), and `mcp_configs.example.json`.
