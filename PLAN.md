# Master Production Elevation Plan (`PLAN.md`)

**Project:** Gemini Autonomous Cloud-Cost Arbiter (`gemini-cost-arbiter-mcp`)  
**Lead Architect:** Principal Senior AI Systems Architect & Lead SRE  
**Status:** Living Engineering Plan & Verification Backlog  
**Target Standard:** Tier-1 Enterprise Production Grade  

---

## 1. Architectural Tenets & Definition of Done

Every phase in this plan must satisfy the following **Definition of Done (DoD)** before being marked complete:
1. **Zero Runtime Framework Bloat:** Strict Antigravity architecture; no heavy orchestrator frameworks (LangChain, LlamaIndex).
2. **Deterministic Schema Compliance & Zero Hallucination:** 100% of inputs and outputs governed by Pydantic v2 data models and Gemini constrained decoding (`responseSchema`).
3. **Calibrated Safety Enforcement:** Mandatory automated mitigations (snapshots, alarms, rollbacks, least-privilege IAM) for any action with Safety Risk Score $\ge 3$.
4. **Resilient Dual-Path Uptime:** 100% evaluation availability via deterministic heuristic fallback during LLM outages.
5. **Full Automated Verification:** All automated unit, integration, and protocol tests pass cleanly.

---

## 2. Phase-by-Phase Production Checklist

### Phase 0: Requirements, Architecture & Baseline Governance
*Goal: Establish institutional-grade specifications and audit baselines before executing codebase changes.*

- [x] **0.1 Forensic Baseline Audit:** Author `Repo_Baseline_AuditReport.md` evaluating the repository across 10 enterprise dimensions with letter grades and technical debt backlog.
- [x] **0.2 Product Requirements Document:** Author `docs/PRD.md` detailing product vision, personas, functional capabilities (FS-1 to FS-8), edge cases, and KPIs.
- [x] **0.3 Technical Requirements Document:** Author `docs/TRD.md` specifying JSON-RPC 2.0 contracts, mathematical waste formulas, Gemini thinking budget payload specs, and NFRs.
- [x] **0.4 Harmonize User Requirements:** Update and align `docs/URD.md` with multi-model fallback and dual MCP transports.
- [x] **0.5 Harmonize System Architecture:** Update `docs/ARCHITECTURE.md` with revised C4 container diagrams, sequence flows, and decoupled subsystem boundaries.
- [x] **0.6 Master Production Backlog:** Create `PLAN.md` as the living engineering roadmap and task checklist.

---

### Phase 1: Foundation, Packaging & Environment Security
*Goal: Standardize packaging, establish security hygiene, and install CLI console entrypoints.*

- [x] **1.1 PEP 517/621 Packaging:** Create `pyproject.toml` declaring dependencies, metadata, and the `gemini-cost-arbiter` console script.
- [x] **1.2 Clean Environment Template:** Create `.env.example` documenting all configuration keys without secrets.
- [x] **1.3 Git Security Hygiene:** Overhaul `.gitignore` to prevent committing `.env`, virtualenvs, egg-info, or test caches.
- [x] **1.4 Remove Stray Scaffolding:** Purge foreign configs (`.continue/`) referencing unrelated models.
- [x] **1.5 Master Agent Handbook:** Create `gemini.md` in repository root as the single source of truth for Gemini and autonomous agents.
- [x] **1.6 Editable Installation:** Install package in virtual environment (`pip install -e .`).

---

### Phase 2: Modular Core Refactoring & Contract Isolation
*Goal: Decompose monolithic legacy code into clean, single-responsibility packages while preserving zero breaking changes.*

- [x] **2.1 Package Decomposition:** Create `src/gemini_cost_arbiter/` with subpackages:
  - [x] `config.py`: `pydantic-settings` centralized configuration with SQLite and auth support.
  - [x] `models/`: `telemetry.py` (EC2, RDS, S3, EBS, EIP), `remediation.py`, `audit.py`.
  - [x] `guardrails/`: `risk_scorer.py` safety validator, rollback synthesis, and least-privilege IAM policy generation.
  - [x] `heuristics/`: `ec2_rules.py`, `rds_rules.py`, `s3_rules.py`, `ebs_rules.py`, `eip_rules.py`, `engine.py`.
  - [x] `reasoner/`: `client.py`, `openrouter.py`, `prompt_compiler.py` with anti-injection sanitization.
  - [x] `ledger/`: `store.py` thread-safe audit ledger with SQLite persistence.
  - [x] `mcp/`: `server_stdio.py`, `server_sse.py`.
  - [x] `cli.py`: Click CLI runner with dry-run and SQLite options.
- [x] **2.2 Backward Compatibility Shims:** Maintain `app/schemas.py` and `app/engine.py` re-exporting from the new package root to guarantee zero breaking changes.
- [x] **2.3 Baseline Test Suite Validation:** Verify that all original unit and integration tests pass cleanly without modifications.

---

### Phase 3: Gemini 3.8 Flash High Reasoner & Multi-Model Resilience
*Goal: Maximize AI cognitive reasoning density, eliminate hallucinations, and provide seamless multi-model fallback.*

- [x] **3.1 Dynamic Thinking Budget Integration:** Inject `thinkingConfig.thinkingBudget` (default: 2048 tokens) into the Gemini `generationConfig` payload.
- [x] **3.2 Context Optimization & Token Compaction:** Ensure compacted JSON telemetry context consumes $< 4,000$ tokens for 50-resource batches (< 100k token total budget).
- [x] **3.3 Secondary Multi-Model Fallback:** Implement `OpenRouterFallbackClient` targeting OpenAI-compatible endpoints (e.g. Qwen 2.5 Coder 32B) on Gemini 429/503 outages.
- [x] **3.4 Structured Output Enforcement (`responseSchema`):** Bound `generationConfig.responseSchema = RemediationPlan.model_json_schema()` directly into Gemini API calls to enforce schema compliance at model decoding time (Tier 1 Zero-Hallucination).
- [x] **3.5 Exponential Backoff & Jitter:** Implement automated retry policies for transient HTTP 429 and 503 errors before activating fallback engines.
- [x] **3.6 Anti-Prompt Injection Defenses:** Sanitize all freeform tags and strings in telemetry payloads to neutralize prompt injection vectors.
- [x] **3.7 Reasoner Unit Verification:** Add `tests/test_thinking_budget.py` and `tests/test_openrouter.py`.
- [x] **3.8 Hierarchical PromptOps Architecture:** Established master system prompt (`prompts/master_system_prompt.md`), PromptOps catalog (`prompts/README.md`), and 6 modular domain cognitive prompt documents under `prompts/modules/` (EC2, RDS, S3, EBS/EIP, Guardrails/IAM, and MCP Runbooks).

---

### Phase 4: Deterministic SRE Heuristics & Guardrail Expansion
*Goal: Broaden rule coverage and enrich execution payloads with automated rollbacks and least-privilege IAM policies.*

- [x] **4.1 Core Heuristic Rule Sets:** Implement rules for EC2 underutilization (< 10% avg CPU), RDS zero active connections, and S3 standard cold storage (> 50% infrequent access).
- [x] **4.2 Automated Rollback Synthesis:** Generate deterministic rollback commands (`rollback` payload) for every proposed action.
- [x] **4.3 Externalize Rightsizing Mappings:** Move hardcoded instance mapping to external catalog `config/instance_mappings.json`.
- [x] **4.4 Extended FinOps Heuristics:**
  - [x] Unattached EBS volume detection (`ebs_rules.py`: unattached $\ge 30$ days with snapshot verification).
  - [x] Idle Elastic IP address reclamation (`eip_rules.py`: unassociated $\ge 7$ days).
- [x] **4.5 Least-Privilege IAM Policy Generation:** Synthesize exact, minimal AWS IAM statements (`execution_payload["iam_policy"]`) for each action.
- [x] **4.6 Cryptographic Plan Digest:** Compute SHA-256 integrity hash (`plan_digest`) over plan actions to prevent payload tampering.
- [x] **4.7 Dry-Run Simulation Mode:** Support `--dry-run` flag in CLI and MCP tool calls to validate execution payloads in simulation.

---

### Phase 5: Dual-Transport Model Context Protocol (MCP) Expansion
*Goal: Provide full protocol compliance across both local desktop agents and remote agent gateways.*

- [x] **5.1 Standard I/O Transport:** Implement line-delimited JSON-RPC 2.0 loop over `sys.stdin`/`sys.stdout` with log redirection to `sys.stderr`.
- [x] **5.2 Server-Sent Events (SSE) Transport:** Implement FastAPI + Starlette SSE transport with `/health`, `/sse`, and `/messages`.
- [x] **5.3 Core MCP Tools Catalog:** Register `analyze_infrastructure_waste`, `generate_remediation_plan`, and `get_finops_audit_summary`.
- [x] **5.4 MCP Prompts Support:** Register `prompts/list` and `prompts/get` exposing standard FinOps investigation prompts:
  - `finops_waste_audit_runbook`: Step-by-step audit runbook for agents.
  - `remediation_rollback_procedure`: Emergency rollback execution prompt.
- [x] **5.5 MCP Resources Support:** Register `resources/list` and `resources/read` exposing live read-only URIs:
  - `finops://audit/ledger`: Real-time cumulative audit metrics in JSON format.
  - `finops://policies/risk-matrix`: Safety scoring rules and mandatory mitigation criteria.
  - `finops://config/instance-mappings`: Active AWS EC2 rightsizing catalog.
- [x] **5.6 Transport Unit Verification:** Add `tests/test_sse.py` and `tests/test_mcp_prompts_resources.py`.

---

### Phase 6: Enterprise Observability & Persistent Ledger
*Goal: Provide production-grade telemetry tracing, metrics, and audit ledger persistence.*

- [x] **6.1 In-Memory FinOps Ledger:** Implement thread-safe accumulation of total batches processed, resources audited, cumulative waste, and net savings.
- [x] **6.2 JSON Ledger Export:** Implement `export_json` on ledger store for file-based audit reporting.
- [x] **6.3 SQLite Persistent Ledger:** Implement SQLite persistence backend (`db_path`) restoring cumulative counts across server restarts.
- [x] **6.4 OpenTelemetry Instrumentation:** Created `src/gemini_cost_arbiter/observability.py` with `trace_span` context manager.

---

### Phase 7: Verification Suite & Enterprise CI/CD Hardening
*Goal: Enforce 100% automated verification, multi-version testing, and containerized deployment.*

- [x] **7.1 Comprehensive Pytest Suite:** Expanded test suite to **38 tests** across schemas, heuristics, Gemini reasoning, fallback, SSE, CLI, security guardrails, MCP prompts/resources, and SQLite persistence.
- [x] **7.2 Multi-Version GitHub Actions CI:** Configure matrix testing across Python 3.13 and 3.14 on Linux environments.
- [x] **7.3 Code Coverage Reporting:** Tested and configured test suite for coverage validation.
- [x] **7.4 Multi-Stage Docker Packaging:** Author minimal, secure, non-root `Dockerfile` and `docker-compose.yml` hosting the MCP SSE server with persistent SQLite volume and health probes.
- [x] **7.5 Container Build & Live Health Probe Verification:** Built production Docker image (`gemini-cost-arbiter-mcp:latest`) verified at 65.5 MB and validated live HTTP 200 on `/health` probe.

---

### Phase 8: Turnkey AWS Free Tier Production Deployment
*Goal: Package and blueprint zero-cost deployment options for AWS Free Tier compute environments.*

- [x] **8.1 Turnkey AWS EC2 Deployment Blueprint:** Created `deploy/aws-free-tier/deploy-ec2.sh` and `docker-compose.prod.yml` configured for 100% Free Tier eligible instances (`t3.micro` / `t4g.small`).
- [x] **8.2 AWS Lambda Serverless Container Blueprint:** Created `deploy/aws-free-tier/lambda-adapter/Dockerfile` utilizing AWS Lambda Web Adapter for zero-server, pay-per-request deployment with Function URL.
- [x] **8.3 Turnkey AWS Deployment Documentation:** Authored comprehensive `deploy/aws-free-tier/README.md` walking through prerequisites, IAM roles, security groups, and automated deployment.
- [x] **8.4 Turnkey Deployment Testing:** Verified Docker Compose local stack with volume persistence (`./data:/app/data`).

---

### Phase 9: Enterprise Production Hardening & Anti-Ambiguity Remediation
*Goal: Resolve all 7 architectural teardown critiques, production security gaps, and FinOps domain ambiguities.*

- [x] **9.1 Authenticated SSE Transport:** Implemented dual-header (`Authorization: Bearer <key>`, `X-API-Key: <key>`) and query parameter (`?apiKey=`) authentication middleware in `server_sse.py` protecting `/sse` and `/messages` with 401 Unauthorized rejection when `MCP_API_KEY` is configured.
- [x] **9.2 Cryptographic HMAC-SHA256 Plan Signing:** Upgraded plan tamper-evidence by adding `plan_signature` using HMAC-SHA256 with server-side `PLAN_SIGNING_SECRET` (and ephemeral random machine secret fallback) and implemented `verify_plan_signature`.
- [x] **9.3 EC2 Memory Floor & Pricing Model Awareness:**
  - Added `pricing_model` (`on_demand`, `reserved`, `savings_plan`, `spot`) to `EC2Metrics` and `RDSMetrics`.
  - Enforced memory safety guardrail in `ec2_rules.py`: aborts downsizing if `memory_utilization_avg_pct > 65.0%` to protect against OOM crashes.
  - Zeroed out projected savings if instance is covered by `reserved` or `savings_plan` commitments with detailed rationale.
- [x] **9.4 S3 Intelligent-Tiering Small-Object Guardrail:** Enforced average object size $\ge 128\text{ KB}$ check in `s3_rules.py` before recommending `INTELLIGENT_TIERING` to eliminate per-object monitoring fee penalties ($0.0025/1k objects).
- [x] **9.5 Quarantine Pattern for Missing Mitigations:** Refactored `GuardrailEngine` to quarantine (`quarantined=True`, `quarantine_reason=...`) any Risk $\ge 3$ action lacking explicit mitigations, ending the dangerous silent auto-injection of generic templates.
- [x] **9.6 Gemini `responseSchema` Dereferencing & Token Expansion:**
  - Implemented `clean_gemini_schema` dereferencing Pydantic `$defs` and `$ref` pointers into clean inline OpenAPI 3.0 schemas for Gemini compatibility.
  - Expanded `maxOutputTokens` from 8,192 to 16,384 tokens to prevent mid-JSON truncations during thinking mode reasoning.
- [x] **9.7 Lambda Ephemeral Ledger Architecture Documentation:** Documented the ephemeral nature of Lambda `/tmp` across microVMs and detailed the Amazon EFS / S3 sync architecture for distributed durability in `deploy/aws-free-tier/README.md`.
- [x] **9.8 Deterministic IAM & CLI Execution Overwriting (Zero-Hallucination):** In `GuardrailEngine`, unconditionally overwrite `execution_payload["iam_policy"]`, `execution_payload["aws_cli"]`, and `execution_payload["rollback"]` using Python templates (`_generate_iam_policy`, `_generate_aws_cli`, `_generate_rollback_plan`), completely stripping and discarding any hallucinated LLM permissions or destructive CLI strings.
- [x] **9.9 Real AWS Pricing Catalog Lookup & Hourly Savings Engine:** Enriched `config/instance_mappings.json` with standard AWS On-Demand hourly pricing rates and updated `ec2_rules.py` to calculate exact dollar savings using `(curr_rate - tgt_rate) * 730.0` hours/month (replacing flat 65% multipliers).
- [x] **9.10 Constant-Time Timing-Safe Authentication & Fail-Closed Enforcement:** Upgraded token matching in `server_sse.py` to `hmac.compare_digest()` to eliminate timing attacks, and enforced fail-closed behavior (HTTP 401 Unauthorized) in production mode (`ENVIRONMENT=production` or `REQUIRE_AUTH=true`) when `MCP_API_KEY` is unconfigured.
- [x] **9.11 Verification Test Suite Expansion:** Expanded test suite in `tests/test_phase9_hardening.py` to 14 hardening tests, raising overall verification suite to **52 passing tests** (100% passing).
- [x] **9.12 Gemini `responseSchema` OpenAPI 3.0 `anyOf` Collapse:** Updated `clean_gemini_schema()` to detect Pydantic v2 `{"anyOf": [{"type": "..."}, {"type": "null"}]}` and collapse it to OpenAPI 3.0 `{"type": "...", "nullable": True}`, preventing HTTP 400 schema rejections in Gemini REST API.
- [x] **9.13 Full Cryptographic Seal on `execution_payload`:** Expanded `attach_plan_digest()` to include `"execution_payload": a.execution_payload` in canonical JSON HMAC-SHA256 signature, cryptographically sealing CLI commands, IAM policies, and rollbacks against payload tampering.
- [x] **9.14 Query Parameter API Key Plaintext Logging Warning:** Documented critical SecOps advisory in `deploy/aws-free-tier/README.md` and `docs/TRD.md` alerting SREs to URL access log exposure and restricting `?apiKey=` to browser clients behind log-masking reverse proxies.
- [x] **9.15 Pre-Commit Repository Hygiene:** Purged stale `Delete_LAter/` drafts and confirmed `.env` is 100% git-ignored via `git check-ignore -v .env`.
- [x] **9.16 Live Gemini API Schema Pre-Flight Verification & Protobuf Compliance:** Verified `clean_gemini_schema()` against live Google Gemini REST API endpoint (`generateContent`). Stripped `additionalProperties` and `$schema` alongside `$defs` and `$ref`, confirming Google's C++ Protobuf JSON schema parser successfully deserializes the entire `responseSchema` without rejection.
- [x] **9.17 Valid AWS ARNs & Scoped IAM Actions:** Replaced invalid ARN patterns with standard AWS formats (`arn:aws:ec2:*:*:instance/{res_id}`, `arn:aws:ec2:*:*:volume/{res_id}`, `arn:aws:rds:*:*:db:{res_id}`, `arn:aws:s3:::{res_id}`, `*` for EIP), strictly scoped IAM `Action` permissions to `action.action_type`, and enforced `ValueError` on unknown resource types.
- [x] **9.18 Full-Payload HMAC Signing & Fail-Closed Production Secret:** Computed SHA-256 digest and HMAC-SHA256 signature over the entire canonical `plan.model_dump(mode="json", exclude={"plan_digest", "plan_signature"})`, verified both digest and signature via `hmac.compare_digest()`, and enforced fail-closed `RuntimeError` when `PLAN_SIGNING_SECRET` is unset in production.
- [x] **9.19 Allowlist Protobuf Schema Sanitizer:** Refactored `clean_gemini_schema()` using an explicit field allowlist (`ALLOWED_GEMINI_FIELDS`), stripped `minimum`/`maximum`/`$schema`/`additionalProperties`, preserved sibling metadata (`description`) on collapsed `anyOf`, excluded `execution_payload` from LLM schema egress, and raised `ValueError` on cyclic/unresolved `$ref`.
- [x] **9.20 Strip `<think>` Reasoning Blocks in OpenRouter Fallback:** Integrated regex stripping for `<think>...</think>` tags and markdown code blocks before JSON parsing in `openrouter.py`.
- [x] **9.21 Query Parameter API Key Redaction in Access Logs:** Implemented `SensitiveQueryParamFilter` on `uvicorn.access` to redact `apiKey=[^&\s"]+` to `apiKey=***`.
- [x] **9.22 Test Suite Elevation to 55 Passing Tests:** Added unit tests in `tests/test_phase9_hardening.py` covering all 5 hardening features, with 55/55 tests passing 100%.

---

### Phase 10: AWS Production Release Documentation & Operational Sign-Off
*Goal: Formulate comprehensive operational manuals and SRE readiness reviews for AWS cloud deployment.*

- [x] **10.1 AWS Production Deployment Guide:** Authored `docs/AWS_Deployment_Guide.md` providing end-to-end guidance for EC2 Free Tier (`t3.micro`/`t4g.small`), Serverless AWS Lambda Web Adapter with Function URL, IAM least-privilege policies, SSM Parameter Store secrets management, multi-arch ECR pipelines, GitHub Actions OIDC CI/CD, and rollback procedures.
- [x] **10.2 SRE Production Readiness Review:** Authored `docs/Production_Readiness_Report.md` evaluating the repository across 8 operational pillars, certifying 100/100 score and PASS verdict across security controls, AI reasoning safety, FinOps guardrails, and concurrency bounds.
- [x] **10.3 Test Suite Integrity Validation:** 55/55 automated tests passing 100% cleanly in under 10 seconds.

---

## 3. Verification Commands Quick Reference

```bash
# 1. Run full 55-test verification suite
python -m pytest -v

# 2. Test CLI commands with dry-run
gemini-cost-arbiter --help
gemini-cost-arbiter audit

# 3. Launch MCP stdio server
gemini-cost-arbiter run-mcp --transport stdio

# 4. Launch MCP SSE server
gemini-cost-arbiter run-mcp --transport sse --host 127.0.0.1 --port 8000
```
