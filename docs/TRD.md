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
* **Network & HTTP Clients:** `httpx>=0.28.0` with non-blocking connection pooling and keep-alive reuse.
* **MCP Web Transports:** `fastapi>=0.115.0`, `uvicorn>=0.30.0`, and `sse-starlette>=2.1.0`.
* **CLI Framework:** `click>=8.1.0` for standardized terminal entrypoints.
* **Test Harness:** `pytest>=8.3.0`, `pytest-asyncio>=0.25.0`, `respx>=0.22.0`.

---

## 2. Mathematical Formulations & FinOps Optimization Rules

### 2.1 EC2 Compute Waste & Rightsizing Formula
An EC2 instance $i$ is evaluated for rightsizing under the following multi-dimensional conditions:

$$\text{Underutilized}(i) = \left( \text{CPU}_{\text{avg}}(i) < 10.0\% \right) \land \left( \text{CPU}_{\text{p95}}(i) < 25.0\% \right)$$

$$\text{MemorySafe}(i) = \left( \text{RAM}_{\text{avg}}(i) \le 65.0\% \right)$$

* **OOM Prevention Guardrail:** If $\text{Underutilized}(i)$ holds but $\neg \text{MemorySafe}(i)$ ($\text{RAM}_{\text{avg}} > 65\%$), downsizing is **aborted** to prevent Out-Of-Memory application crashes.
* **Pricing Model & Real Catalog Rates Formula:**
  $$\text{Savings}_{\text{EC2}}(i) = \begin{cases} 0.00, & \text{if } \text{PricingModel}(i) \in \{\text{"reserved"}, \text{"savings\_plan"}\} \\ \min\left(\text{Spend}_{\text{monthly}}(i), \text{round}((\text{Rate}_{\text{curr}} - \text{Rate}_{\text{tgt}}) \times 730, 2)\right), & \text{if Catalog Rates Available} \\ \text{round}(\text{Spend}_{\text{monthly}}(i) \times 0.65, 2), & \text{fallback} \end{cases}$$
  Where $\text{Rate}_{\text{curr}}$ and $\text{Rate}_{\text{tgt}}$ are the standard AWS On-Demand hourly USD rates from `config/instance_mappings.json` and 730 is the standard operating hours per month.
* **Safety Risk Assignment:**
  $$\text{Risk}_{\text{EC2}}(i) = \begin{cases} 4, & \text{if } \text{Environment}(i) = \text{"production"} \\ 3, & \text{otherwise} \end{cases}$$

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

### 2.6 Cryptographic Full-Payload Plan Digest & HMAC-SHA256 Signature
To guarantee plan authenticity and prevent intermediary tampering across all metadata and execution payloads:
$$\text{Digest} = \text{SHA256}\left(\text{Canonical}(\text{Plan} \setminus \{\text{digest}, \text{signature}\})\right)$$

$$\text{Signature} = \text{HMAC-SHA256}\left( K_{\text{signing}}, \text{Canonical}(\text{Plan} \setminus \{\text{digest}, \text{signature}\}) \right)$$

Where $K_{\text{signing}}$ is the server-side `PLAN_SIGNING_SECRET`. In production mode (`ENVIRONMENT=production`), omitting `PLAN_SIGNING_SECRET` fails closed with a `RuntimeError` rather than falling back to an ephemeral secret.

### 2.7 Deterministic IAM & CLI Execution Synthesis (Zero-Hallucination)
To guarantee that downstream agent orchestrators never execute hallucinated or over-privileged AWS commands:
* `execution_payload["iam_policy"]`: Synthesized deterministically in Python with valid AWS IAM resource ARN formats:
  - EC2 instance: `arn:aws:ec2:*:*:instance/{res_id}`
  - EBS volume: `arn:aws:ec2:*:*:volume/{res_id}`
  - Elastic IP: `*` (with `ec2:DescribeAddresses`, `ec2:ReleaseAddress`)
  - RDS database: `arn:aws:rds:*:*:db:{res_id}`
  - S3 bucket: `arn:aws:s3:::{res_id}`
  - Actions are scoped specifically to `action.action_type`, and unknown resource types fail closed with `ValueError`.
* `execution_payload["aws_cli"]`: Deterministically generated using sanitized resource IDs and target specifications from `config/instance_mappings.json`.
* `execution_payload["rollback"]`: Programmatically populated with exact recovery commands and CloudWatch alarm references.
* **Unconditional Overwrite Policy:** The `GuardrailEngine` unconditionally replaces any LLM-generated IAM policy or execution strings with these deterministic templates, discarding any hallucinated wildcard `*` permissions.

### 2.8 Gemini `responseSchema` OpenAPI 3.0 & Protobuf Compliance
To satisfy Google Gemini's strict REST API schema parser (`google.ai.generativelanguage.v1beta.Schema`):
* **Strict Field Allowlist:** `clean_gemini_schema()` strictly enforces an allowlist (`{"type", "format", "description", "nullable", "enum", "items", "properties", "required", "propertyOrdering"}`), dropping `minimum`, `maximum`, `$schema`, `$defs`, `title`, and `additionalProperties`.
* **Dereferencing `$defs` and `$ref`:** All JSON Schema references are inlined recursively into a self-contained OpenAPI 3.0 tree. Unresolved `$ref` pointers and cyclic references raise `ValueError`.
* **OpenAPI 3.1 `anyOf` Collapse:** Pydantic v2 `{"anyOf": [{"type": "T"}, {"type": "null"}]}` branches are collapsed to OpenAPI 3.0 `{"type": "T", "nullable": true}` while preserving sibling metadata (`description`).
* **Execution Payload Exclusion:** `execution_payload` is excluded from the LLM egress `responseSchema` to prevent unnecessary token consumption and schema bloat.
* **OpenRouter Fallback `<think>` Stripping:** `openrouter.py` strips `<think>...</think>` reasoning tokens and markdown code fences before JSON decoding.

---

## 3. Model Context Protocol (MCP) JSON-RPC 2.0 Specification

The engine conforms strictly to MCP Specification Version `2024-11-05`.

### 3.1 Tools Interface
1. **`analyze_infrastructure_waste`**: Ingests `TelemetryBatch` and returns `WasteAnalysisSummary`.
2. **`generate_remediation_plan`**: Ingests `TelemetryBatch`, `max_acceptable_risk`, and `dry_run` flag, returning validated `RemediationPlan` with SHA-256 digest, HMAC-SHA256 signature, and quarantine annotations.
3. **`get_finops_audit_summary`**: Returns `FinOpsAuditSummary` from the active persistent ledger.

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

### 3.4 Transport Security & Timing-Safe Authentication (SSE)
* When `MCP_API_KEY` is configured, `/sse` and `/messages` endpoints require valid authentication via:
  - `Authorization: Bearer <key>` header (RFC 6750)
  - `X-API-Key: <key>` header
  - `?apiKey=<key>` query parameter (standard for browser EventSource SSE)
* **Timing-Safe Evaluation:** All token comparisons are executed using `hmac.compare_digest()` to completely neutralize timing side-channel attacks.
* **Fail-Closed Protection:** In production mode (`ENVIRONMENT=production` or `REQUIRE_AUTH=true`), if `MCP_API_KEY` is unconfigured, requests to `/sse` and `/messages` immediately fail closed with HTTP 401 Unauthorized.
* **Query Parameter Plaintext Logging Redaction:** A dedicated `logging.Filter` (`SensitiveQueryParamFilter`) is attached to `uvicorn.access` to automatically redact `apiKey=[^&\s"]+` query parameters to `apiKey=***`, preventing credentials from leaking in server logs.
* **Unauthenticated Probes:** The `/health` probe remains unauthenticated for container orchestrators (Kubernetes, AWS Lambda Web Adapter, Docker Compose).

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

## 5. Storage Schema: SQLite Persistent Ledger

When invoked with `--db-path <path>`, the ledger persists across restarts via SQLite:

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

### 6.2 Turnkey AWS Free Tier Specs
* **EC2 Host Blueprint:** Automated setup on Amazon Linux 2023 or Ubuntu 24.04 targeting `t3.micro` / `t4g.small` with 512MB RAM bound compose specification.
* **Lambda Web Adapter Blueprint:** Container running AWS Lambda Web Adapter (`public.ecr.aws/awslabs/aws-lambda-adapter:0.8.4`) with Function URL for zero-server hosting.
