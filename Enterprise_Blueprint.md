# Enterprise Production Blueprint (`Enterprise_Blueprint.md`)

**Project:** Gemini Autonomous Cloud-Cost Arbiter (`gemini-cost-arbiter-mcp`)  
**Runtime:** Python 3.13+ (`asyncio`)  
**AI & Fallback Stack:** Google Gemini (`DEFAULT_MODEL` via REST `v1beta` with `thinkingConfig` & `clean_gemini_schema()`) + OpenRouter Secondary Fallback + Deterministic SRE Heuristic Engine  
**Transports & Persistence:** MCP JSON-RPC 2.0 (`stdio` & FastAPI/Starlette `SSE`) + SQLite WAL Ledger (`filelock` + `threading.RLock`)  
**Governance:** [`GEMINI.md`](GEMINI.md) + [`AUDIT_REMEDIATION_LOG.md`](AUDIT_REMEDIATION_LOG.md)  
**Target Standard:** Tier-1 Enterprise Production Grade

---

## 1. Architectural Tenets & Definition of Done (DoD)

Every remediation ticket and feature build MUST satisfy all 10 tenets below before being marked `COMPLETE`:

1. **Zero Runtime Framework Bloat:** Strict Antigravity decoupled architecture—no LangChain, LlamaIndex, or opaque agent orchestrators.
2. **Strict Immutable Pydantic v2 Contracts:** Every domain model in `src/gemini_cost_arbiter/models/` enforces `ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)` with bounded strings (`min_length`, `max_length`, `pattern`), bounded numeric ranges (`ge`, `le`), bounded collection sizes, and `@model_validator` mathematical consistency (`total_projected_monthly_savings_usd` == sum of action savings). No `DynamicFallbackModel` or `__getattr__` masking.
3. **Fail-Closed Pricing Catalog & Unicode Normalization:** `config/instance_mappings.json` is resolved dynamically via `CATALOG_PATH` and fails closed with `CatalogNotFoundError` if missing or corrupted. All string comparisons (`environment`, `pricing_model`, `resource_type`, `current_instance_type`) are normalized via Unicode `NFKC` + `.strip().casefold()`, with production detection covering `{"production", "prod", "prd"}` across `environment` and tags.
4. **Calibrated FinOps Domain Guardrails & LLM Reconciliation:**
   - EC2 >65% RAM aborts downsizing; S3 <128 KB avg object size disqualifies Intelligent-Tiering; Reserved Instance / Savings Plan commitments yield `$0.00` bill savings; `projected_monthly_savings_usd <= current_monthly_spend_usd` is enforced deterministically on both heuristic and LLM plans.
   - Risk Score $\ge 3$ with empty/whitespace `system_mitigations` AND all `safety_risk_score == 5` actions are quarantined (`quarantined=True`) and gated behind signed anti-replay HITL approval (`issued_at`/`expires_at` $\le 300\text{s}$, `nonce` deduplication).
   - `GuardrailEngine` unconditionally overwrites `aws_cli`, `rollback`, and `iam_policy` with `shlex.quote()`-hardened commands and zero-`*` wildcard IAM statements.
5. **Zero-Trust Prompt Injection, Compression & Path Traversal Defense:** Untrusted telemetry strings are NFKC-normalized, stripped of `<`/`>` XML breakout characters, length-capped, compressed (`exclude_none=True, exclude_defaults=True`, `MAX_PROMPT_CHARS`), and wrapped in `<untrusted_proposal_data>...</untrusted_proposal_data>`. Prompt loaders enforce `Path.resolve().is_relative_to(prompts_dir.resolve())`.
6. **Protobuf-Compliant `clean_gemini_schema()` Egress:** All LLM `responseSchema` payloads are dereferenced (`$defs`/`$ref`), `anyOf` nullables/unions collapsed cleanly, `execution_payload` excluded, and unsupported JSON-Schema keywords (`minimum`, `maximum`, `$schema`, `title`, `additionalProperties`) stripped.
7. **Bounded Self-Healing, Fallback & Multi-Layer Circuit Breakers:** Gemini and OpenRouter clients enforce `30s` timeouts, `max_retries=2` with exponential backoff + jitter, strip `<think>...</think>` and markdown fences, cap `MAX_OUTPUT_TOKENS` (`8192`), and trip `DAILY_API_COST_LIMIT_USD` (`$10.00`), `MAX_SESSION_TOKEN_BUDGET` (`500000`), and consecutive-failure cooldowns directly to the Deterministic SRE Heuristic Engine with `fallback_tier_used` telemetry.
8. **Cryptographic Canonical Integrity & Fail-Closed Auth:** `plan_digest` (SHA-256), `plan_signature` (HMAC-SHA256), and HITL approval tokens are computed over canonical JSON (`sort_keys=True, separators=(",", ":"), ensure_ascii=False`). `PLAN_SIGNING_SECRET` and `MCP_API_KEY` fail closed in `production` when unset, short (`< 32` chars for signing), or set to placeholder strings. SSE enforces `hmac.compare_digest()`, `MAX_PAYLOAD_BYTES` (`10485760` / HTTP 413), and `secrets.token_urlsafe(16)` session IDs.
9. **Concurrent SQLite WAL Persistence & UTF-8 I/O:** `FinOpsLedger` uses `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `threading.RLock`, and `filelock.FileLock`, with explicit `encoding="utf-8"` on all file I/O.
10. **Anti-Test-Cheating & Mandatory Verification Gates:** Every PR and build prompt must pass `ruff check src tests`, `mypy src`, and `pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-fail-under=90` with isolated test env fixtures (`tests/conftest.py`), and `README.md` must remain a 100% hyperlinked Master Navigation Hub.

---

## 2. Phase-by-Phase Production & Remediation Roadmap

### Baseline Implementation Milestones (Consolidated from legacy `PLAN.md`)
All initial foundation milestones (Phases 0–10 of the legacy `PLAN.md`) are **COMPLETE** and preserved here for architectural lineage:
- **Phases 0–2 (Specs, Packaging & Modular Core):** Authored `docs/PRD.md`, `docs/TRD.md`, `docs/URD.md`, `docs/ARCHITECTURE.md`, and `Repo_Baseline_AuditReport.md`; configured `pyproject.toml` (`gemini-cost-arbiter` CLI); decomposed core into `src/gemini_cost_arbiter/` (`config`, `models`, `reasoner`, `heuristics`, `guardrails`, `ledger`, `mcp`, `observability`, `cli`) with zero-breaking-change shims in `app/`.
- **Phases 3–6 (AI Reasoner, Heuristics, Dual MCP & Ledger):** Integrated Gemini `thinkingConfig` + `responseSchema`, `OpenRouterFallbackClient`, `prompts/` Tier-0 + 6 domain modules, `config/instance_mappings.json`, EC2/RDS/S3/EBS/EIP heuristics, MCP JSON-RPC 2.0 (`stdio` + FastAPI `SSE`, 3 tools, 2 prompts, 3 `finops://` resources), OpenTelemetry `trace_span`, and SQLite persistence.
- **Phases 7–10 (Docker, AWS Free Tier & Phase 9 Hardening):** Built non-root multi-stage `Dockerfile` (65.5 MB) and `deploy/aws-free-tier/` (EC2 & Lambda Web Adapter); hardened SSE auth (`hmac.compare_digest`, fail-closed prod), HMAC-SHA256 full-payload plan signing, EC2 >65% RAM floor, RI/SP `$0` savings, S3 <128 KB floor, quarantine gate, `clean_gemini_schema()` `$defs`/`$ref`/`anyOf` sanitization, deterministic IAM/CLI overwrites, and `SensitiveQueryParamFilter` (55/55 baseline tests passing; `docs/AWS_Deployment_Guide.md` & `docs/Production_Readiness_Report.md` delivered).

### Active Enterprise Remediation Roadmap (`BUILD-PROMPT-01` – `BUILD-PROMPT-10`)

| Build Prompt | Phase | Target Tickets | Scope & Acceptance Criteria |
|:---|:---|:---|:---|
| **`BUILD-PROMPT-01`** | Phase 1: Governance & Playbook Foundation | `REM-001` | Rename `gemini.md` -> `GEMINI.md` in git index; author `PROJECT_MAP.md` & `BUILD_PROMPTS.md`; make `README.md` a 100% hyperlinked hub. |
| **`BUILD-PROMPT-02`** | Phase 2: CI/CD & Anti-Test-Cheating Harness | `REM-002` | Add `ruff`, `mypy` strict config, `pytest-timeout`, `pytest-cov >= 90%`, `tests/conftest.py` env isolation, and update `.github/workflows/test.yml`. |
| **`BUILD-PROMPT-03`** | Phase 3: Strict Immutable Pydantic v2 Models | `REM-003`, `REM-004` | Enforce `ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)`, remove `DynamicFallbackModel`, bound all IDs/strings/collections/spends, add `RemediationPlan` savings sum validator, update `engine.py` dry-run to `model_copy()`. |
| **`BUILD-PROMPT-04`** | Phase 4: Fail-Closed Catalog & Normalization | `REM-005`, `REM-006` | Implement `CatalogNotFoundError`, dynamic `CATALOG_PATH` resolution, abort on unknown instance types, apply Unicode `NFKC` + `.strip().casefold()`, and detect `prod`/`production`/`prd` tags. |
| **`BUILD-PROMPT-05`** | Phase 5: Guardrail Hardening & FinOps Reconciliation | `REM-007`, `REM-008` | Add regex + `shlex.quote()` in CLI/rollback builders, eliminate `*` in EIP/fallback IAM policies, reject `bool` risk scores & whitespace mitigations, and reconcile LLM plans against `TelemetryBatch` FinOps floors & spend caps. |
| **`BUILD-PROMPT-06`** | Phase 6: Prompt Defense, Compression & Schema Sanitization | `REM-009`, `REM-010` | Strip `<`/`>` breakout chars, wrap telemetry in `<untrusted_proposal_data>`, compress prompts (`exclude_none`/`exclude_defaults`/`MAX_PROMPT_CHARS`), add path-safe prompt loader (`is_relative_to`), harden `clean_gemini_schema()` multi-branch `anyOf`. |
| **`BUILD-PROMPT-07`** | Phase 7: Circuit Breakers & Fallback Resilience | `REM-011` | Add `MAX_OUTPUT_TOKENS` (`8192`), `MAX_SESSION_TOKEN_BUDGET` (`500000`), `DAILY_API_COST_LIMIT_USD` (`$10.00`), consecutive-failure cooldown, `30s` timeout, `<think>` stripping in Gemini client, retry+jitter in OpenRouter, and `fallback_tier_used` logging. |
| **`BUILD-PROMPT-08`** | Phase 8: Crypto Canonicalization, HITL & SSE Hardening | `REM-012`, `REM-013`, `REM-014` | Enforce `ensure_ascii=False` in canonical signing, reject placeholder secrets in production, quarantine `risk == 5` with signed anti-replay HITL approval (`<= 300s` TTL + `nonce`), add `MAX_PAYLOAD_BYTES` HTTP 413 check, `secrets.token_urlsafe(16)` session IDs, and case-insensitive log redaction. |
| **`BUILD-PROMPT-09`** | Phase 9: SQLite WAL Concurrency & Docker Parity | `REM-015`, `REM-016` | Enable SQLite WAL + `busy_timeout=5000` + `RLock` + `filelock`, auto-create parent dirs, copy `prompts/` into `Dockerfile`, and support `PROMPTS_DIR`. |
| **`BUILD-PROMPT-10`** | Phase 10: Docs Sync & Prompt Registry | `REM-017` | Create `prompts/modular_prompt.md`, align `finops://` URIs, `sample_telemetry.json`, `clean_gemini_schema()`, and test counts across all docs. |

---

## 3. Verification Commands Quick Reference

### Stage 1: Quiet Fast Verification Gate (Run After Every Edit)
```powershell
.venv\Scripts\python.exe -m ruff check src tests ; `
.venv\Scripts\python.exe -m mypy src ; `
.venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10
```

### Stage 2: Full Coverage, CLI & Container Verification Chain
```powershell
# 1. Full Test Suite with >= 90% Coverage Enforcement
.venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-fail-under=90

# 2. CLI Functional Smoke Checks
.venv\Scripts\python.exe -m gemini_cost_arbiter --version
.venv\Scripts\python.exe -m gemini_cost_arbiter analyze -f sample_telemetry.json
.venv\Scripts\python.exe -m gemini_cost_arbiter plan -f sample_telemetry.json --max-risk 3 --dry-run
.venv\Scripts\python.exe -m gemini_cost_arbiter audit

# 3. Docker Production Build & Health Check
docker build -t gemini-cost-arbiter-mcp:latest .
docker compose up -d
curl -f http://localhost:8000/health
```
