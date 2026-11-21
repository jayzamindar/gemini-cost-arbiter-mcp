# Repository Index & Architecture Map (`PROJECT_MAP.md`)

**Project:** `gemini-cost-arbiter-mcp`  
**Package Root:** `src/gemini_cost_arbiter/`  
**Governance:** [`GEMINI.md`](GEMINI.md) | [`Enterprise_Blueprint.md`](Enterprise_Blueprint.md) | [`AUDIT_REMEDIATION_LOG.md`](AUDIT_REMEDIATION_LOG.md) | [`BUILD_PROMPTS.md`](BUILD_PROMPTS.md)

---

## 1. Core Python Package (`src/gemini_cost_arbiter/`)

| Module / Subpackage | Purpose & Responsibility | Key Symbols |
|:---|:---|:---|
| `src/gemini_cost_arbiter/__init__.py` | Package metadata and public exports | `__version__` |
| `src/gemini_cost_arbiter/__main__.py` | Module entrypoint (`python -m gemini_cost_arbiter`) | `main` |
| `src/gemini_cost_arbiter/cli.py` | Click CLI (`run-mcp`, `analyze`, `plan`, `audit`) | `main`, `run_mcp`, `analyze`, `plan`, `audit` |
| `src/gemini_cost_arbiter/config.py` | Pydantic Settings runtime configuration | `ArbiterConfig` |
| `src/gemini_cost_arbiter/engine.py` | Core orchestrator & MCP JSON-RPC 2.0 dispatcher | `GeminiCostArbiterEngine` |
| `src/gemini_cost_arbiter/observability.py` | OpenTelemetry distributed trace span helper | `trace_span` |
| `src/gemini_cost_arbiter/models/__init__.py` | Unified Pydantic v2 data contract exports | `TelemetryBatch`, `RemediationPlan`, `FinOpsAuditSummary` |
| `src/gemini_cost_arbiter/models/telemetry.py` | Multi-dimensional AWS telemetry schemas | `EC2Metrics`, `RDSMetrics`, `S3Metrics`, `EBSMetrics`, `EIPMetrics`, `CloudTelemetry`, `TelemetryBatch` |
| `src/gemini_cost_arbiter/models/remediation.py` | Action, plan, risk, and summary schemas | `ActionType`, `RemediationActionItem`, `RemediationPlan`, `WasteAnalysisSummary` |
| `src/gemini_cost_arbiter/models/audit.py` | Cumulative FinOps audit ledger model | `FinOpsAuditSummary` |
| `src/gemini_cost_arbiter/reasoner/client.py` | Gemini REST `v1beta` client & `responseSchema` sanitizer | `GeminiReasonerClient`, `clean_gemini_schema`, `ALLOWED_GEMINI_FIELDS` |
| `src/gemini_cost_arbiter/reasoner/openrouter.py` | Secondary OpenRouter fallback LLM client | `OpenRouterFallbackClient` |
| `src/gemini_cost_arbiter/reasoner/prompt_compiler.py` | Telemetry sanitizer & prompt compiler | `SYSTEM_PROMPT`, `sanitize_string`, `sanitize_telemetry_dict`, `compile_reasoner_prompt` |
| `src/gemini_cost_arbiter/heuristics/engine.py` | Offline deterministic SRE heuristic orchestrator | `DeterministicHeuristicEngine` |
| `src/gemini_cost_arbiter/heuristics/ec2_rules.py` | EC2 underutilization, >65% RAM floor, catalog pricing | `evaluate_ec2_instance`, `load_instance_catalog`, `get_instance_hourly_rate` |
| `src/gemini_cost_arbiter/heuristics/rds_rules.py` | RDS zero-connection idle & RI/Savings Plan checks | `evaluate_rds_instance` |
| `src/gemini_cost_arbiter/heuristics/s3_rules.py` | S3 cold tiering & <128 KB small-object floor | `evaluate_s3_bucket` |
| `src/gemini_cost_arbiter/heuristics/ebs_rules.py` | Detached orphan EBS volume (>30d) reclamation | `evaluate_ebs_volume` |
| `src/gemini_cost_arbiter/heuristics/eip_rules.py` | Unassociated Elastic IP (>7d) reclamation | `evaluate_elastic_ip` |
| `src/gemini_cost_arbiter/guardrails/risk_scorer.py` | Quarantine gate, deterministic CLI/rollback/IAM, HMAC-SHA256 | `GuardrailEngine` |
| `src/gemini_cost_arbiter/ledger/store.py` | Cumulative FinOps audit ledger & SQLite persistence | `FinOpsLedger` |
| `src/gemini_cost_arbiter/mcp/server_stdio.py` | Standard I/O MCP JSON-RPC 2.0 transport runner | `run_stdio`, `main` |
| `src/gemini_cost_arbiter/mcp/server_sse.py` | FastAPI + Starlette SSE/HTTP MCP transport server | `create_sse_app`, `run_sse`, `SensitiveQueryParamFilter` |

---

## 2. Backward-Compatibility Shims (`app/`)

| File | Purpose |
|:---|:---|
| `app/__init__.py` | Legacy package marker |
| `app/engine.py` | Re-exports `GeminiCostArbiterEngine` from `gemini_cost_arbiter.engine` |
| `app/schemas.py` | Re-exports Pydantic v2 contracts from `gemini_cost_arbiter.models` & `config` |

---

## 3. Verification & Test Suite (`tests/`)

| Test File | Coverage Scope |
|:---|:---|
| `tests/test_arbiter.py` | Ingestion schemas, risk guardrails, heuristics, mocked Gemini, ledger, MCP JSON-RPC 2.0 |
| `tests/test_cli.py` | Click CLI commands (`--version`, `analyze`, `plan`, `audit`) |
| `tests/test_governance_docs.py` | Governance file presence, `README.md` link integrity, `BUILD_PROMPTS.md` contract checks |
| `tests/test_guardrails_security.py` | Prompt injection sanitization, IAM scoping, SHA-256 digest, EBS/EIP rules, dry-run |
| `tests/test_mcp_prompts_resources.py` | MCP `prompts/list`, `prompts/get`, `resources/list`, `resources/read` |
| `tests/test_openrouter.py` | Secondary OpenRouter fallback on Gemini HTTP 503 |
| `tests/test_phase9_hardening.py` | SSE auth, HMAC-SHA256 signing, EC2 RAM floor, RI/SP, S3 <128KB, quarantine, `clean_gemini_schema()` |
| `tests/test_sqlite_ledger.py` | SQLite persistence across restarts |
| `tests/test_sse.py` | FastAPI SSE `/health` and `/messages` handshake/tools |
| `tests/test_thinking_budget.py` | Gemini `thinkingConfig.thinkingBudget` payload serialization |

---

## 4. Configuration, Prompts, Packaging & Deployment

| Path | Purpose |
|:---|:---|
| `config/instance_mappings.json` | AWS EC2 rightsizing, Graviton modernization, and On-Demand hourly rate catalog |
| `prompts/README.md` | PromptOps architecture catalog |
| `prompts/master_system_prompt.md` | Tier-0 Master System Prompt & Global Ontology |
| `prompts/code_generation.txt` | Legacy architectural design prompt history |
| `prompts/modules/01_ec2_compute_reasoning.md` | EC2 compute & Graviton reasoning module |
| `prompts/modules/02_rds_database_reasoning.md` | RDS database idle & Multi-AZ reasoning module |
| `prompts/modules/03_s3_storage_tiering.md` | S3 Intelligent-Tiering & Glacier module |
| `prompts/modules/04_ebs_eip_reclamation.md` | EBS & EIP reclamation module |
| `prompts/modules/05_guardrails_rollback_iam.md` | Risk scoring, rollback & IAM synthesis module |
| `prompts/modules/06_mcp_operational_runbooks.md` | MCP SRE operational runbooks module |
| `pyproject.toml` | PEP 517/621 packaging, dependencies, pytest & ruff configuration |
| `requirements.txt` | Pinned runtime & test dependencies |
| `Dockerfile` | Multi-stage non-root (`appuser`) production container |
| `docker-compose.yml` | Local SSE stack with persistent `./data` volume |
| `.github/workflows/test.yml` | GitHub Actions CI matrix (Python 3.13, 3.14) |
| `deploy/aws-free-tier/README.md` | Zero-cost AWS Free Tier deployment guide |
| `deploy/aws-free-tier/deploy-ec2.sh` | Automated EC2 Free Tier setup script |
| `deploy/aws-free-tier/docker-compose.prod.yml` | Production compose override with 512M memory cap |
| `deploy/aws-free-tier/lambda-adapter/Dockerfile` | Serverless AWS Lambda Web Adapter container |
| `sample_telemetry.json` | Sample multi-resource telemetry batch for CLI smoke tests |

---

## 5. Governance & Specification Documents (`docs/` & Root)

| Document | Role |
|:---|:---|
| [`GEMINI.md`](GEMINI.md) | Supreme operational constitution, `[PROJECT_CONFIGURATION]`, 13 invariants, 3-strike breaker |
| [`Enterprise_Blueprint.md`](Enterprise_Blueprint.md) | 10 Architectural Tenets (DoD), `BUILD-PROMPT-01..10` roadmap, verification chains |
| [`AUDIT_REMEDIATION_LOG.md`](AUDIT_REMEDIATION_LOG.md) | Forensic audit tickets (`REM-001`–`REM-017`) with `file:line` evidence & TDD specs |
| [`PROJECT_MAP.md`](PROJECT_MAP.md) | Repository index & module map (this file) |
| [`BUILD_PROMPTS.md`](BUILD_PROMPTS.md) | Self-contained `BUILD-PROMPT-01..10` execution playbook |
| [`PLAN.md`](PLAN.md) | Historical baseline production elevation checklist |
| [`Repo_Baseline_AuditReport.md`](Repo_Baseline_AuditReport.md) | Initial 10-dimension baseline audit report |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System Architecture Document (C4 & sequence flows) |
| [`docs/TRD.md`](docs/TRD.md) | Technical Requirements Document |
| [`docs/PRD.md`](docs/PRD.md) | Product Requirements Document |
| [`docs/URD.md`](docs/URD.md) | User Requirements Document |
| [`docs/AWS_Deployment_Guide.md`](docs/AWS_Deployment_Guide.md) | AWS EC2, Lambda, IAM, and SSM deployment guide |
| [`docs/Production_Readiness_Report.md`](docs/Production_Readiness_Report.md) | 8-pillar SRE Production Readiness Review |
