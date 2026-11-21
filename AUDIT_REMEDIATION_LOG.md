# Forensic Audit & Remediation Log (`AUDIT_REMEDIATION_LOG.md`)

**Repository:** `gemini-cost-arbiter-mcp`  
**Audit Authority:** Principal AI Systems Architect, Lead SRE & Staff Security Engineer  
**Audit Date:** 2026-11-21 (Second-Pass Adversarial Red-Team & Zero-Hallucination Audit)  
**Audit Scope:** Full codebase (`src/gemini_cost_arbiter/**`, `app/**`, `tests/**`, `config/`, `prompts/`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/test.yml`, and `docs/*`)  
**Policy:** Zero-Hallucination Forensic Evidence (`file:line`), Zero Placeholders, Strictly Sequential `REM-001`–`REM-017`

---

## Executive Summary

| Severity | Total Tickets | Ticket IDs | Status | Primary Risk Domains |
|:---|:---:|:---|:---:|:---|
| **CRITICAL** | 5 | `REM-003` (`DONE`), `REM-004` (`DONE`), `REM-007` (`DONE`), `REM-012`, `REM-014` | `3 DONE / 2 OPEN` | Mutable/unbounded schemas (`extra="allow"`), CLI/rollback shell interpolation, placeholder signing secrets, missing SSE 10MB body limit (HTTP 413) & predictable session IDs |
| **HIGH** | 7 | `REM-002` (`DONE`), `REM-005` (`DONE`), `REM-008` (`DONE`), `REM-009` (`DONE`), `REM-011` (`DONE`), `REM-013`, `REM-015` | `5 DONE / 2 OPEN` | Missing CI `ruff`/`mypy`/`pytest-cov`/`pytest-timeout`, silent catalog fallback, LLM FinOps floor bypass, missing XML breakout & prompt compression, missing token/cost/cooldown circuit breakers, missing `risk==5`/HITL anti-replay gate, missing SQLite WAL + locking |
| **MEDIUM** | 3 | `REM-006` (`DONE`), `REM-010` (`DONE`), `REM-016` | `2 DONE / 1 OPEN` | Missing NFKC + `.strip().casefold()` & `prod`/`prd` tag detection, `clean_gemini_schema()` multi-branch `anyOf` drop, `prompts/` omitted from `Dockerfile` |
| **LOW** | 3 | `REM-001` (`DONE`), `REM-017` (`OPEN`), `REM-018` (`DONE`) | `2 DONE / 1 OPEN` | Case-sensitivity (`gemini.md` vs `GEMINI.md`), missing `PROJECT_MAP.md`/`BUILD_PROMPTS.md`, cross-file MCP URI & `modular_prompt.md` drift, multi-cloud docs/deploy standardization |
| **TOTAL** | **18** | **`REM-001` – `REM-018`** | **`12 DONE / 6 OPEN`** | Mapped 1-to-1 to `BUILD-PROMPT-01` through `BUILD-PROMPT-10` in [`Enterprise_Blueprint.md`](Enterprise_Blueprint.md) |

---

## Sequential Remediation Tickets

### REM-001: Governance Case Normalization (`GEMINI.md`) & Playbook Foundation (`PROJECT_MAP.md`, `BUILD_PROMPTS.md`)
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `LOW` | Governance & Cross-Platform Compatibility
- **Exact Evidence:** `gemini.md:1-221` (tracked in git as lowercase `gemini.md`); `README.md:439`; `PLAN.md:42`; `git ls-files` (lacks `PROJECT_MAP.md` and `BUILD_PROMPTS.md`)
- **Root Cause & Security/Reliability Impact:** On case-sensitive Linux filesystems (CI runners, Docker), tools looking for `GEMINI.md` miss lowercase `gemini.md`. Additionally, `PROJECT_MAP.md` and `BUILD_PROMPTS.md` (with mandatory 2-line session bootstrap headers and Auto-Commit & Fail-Closed Verification Gates) do not exist, and `README.md` is not yet a 100% hyperlinked Master Navigation Hub.
- **Exact Fix Specification:**
  1. Execute `git mv gemini.md gemini.md.tmp && git mv gemini.md.tmp GEMINI.md` so git tracks uppercase `GEMINI.md`.
  2. Author `PROJECT_MAP.md` indexing all modules, tests, configs, and docs, and `BUILD_PROMPTS.md` (`BUILD-PROMPT-01`–`10`) with the mandatory 2-line bootstrap header and Fail-Closed Verification Gate.
  3. Update `README.md` as a 100% hyperlinked Master Navigation Hub and update `gemini.md` references in `README.md:439` and `PLAN.md:42` to `GEMINI.md`.
- **TDD Verification Test:** `tests/test_governance_docs.py::test_governance_files_and_links_exist` asserting `Path("GEMINI.md").is_file()`, `Path("PROJECT_MAP.md").is_file()`, `Path("BUILD_PROMPTS.md").is_file()`, and zero broken relative Markdown links in `README.md`.

---

### REM-002: Enforce CI/CD Quality Gates (`ruff`, `mypy`, `pytest-timeout`, `pytest-cov >= 90%`) & Test Env Isolation
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `HIGH` | CI/CD & Anti-Test-Cheating Harness
- **Exact Evidence:** `.github/workflows/test.yml:26-38`; `pyproject.toml:48-56,65-83`; `requirements.txt:1-13`; `gemini.md:104` (references missing `tests/conftest.py`)
- **Root Cause & Security/Reliability Impact:** CI only executes `python -m pytest -v` without `ruff`, `mypy`, `pytest-timeout`, or `pytest-cov` (`--cov-fail-under=90`). `[tool.mypy]` is absent from `pyproject.toml`. Because `tests/conftest.py` does not exist, running `pytest` locally when `.env` contains non-test API keys causes tests instantiating `GeminiCostArbiterEngine()` without args (`tests/test_cli.py`, `tests/test_sse.py`) to attempt live HTTP calls and hang.
- **Exact Fix Specification:**
  1. Add `"pytest-cov>=6.0.0"`, `"pytest-timeout>=2.3.1"` to `[project.optional-dependencies].test` in `pyproject.toml` and `requirements.txt`.
  2. Add `[tool.mypy]` (`python_version = "3.13"`, `strict = true`, `ignore_missing_imports = false`, `warn_return_any = true`) and `timeout = 10` (`timeout_method = "thread"`) under `[tool.pytest.ini_options]` in `pyproject.toml`.
  3. Create `tests/conftest.py` with an `autouse=True` fixture setting `GEMINI_API_KEY="test-key"`, `OPENROUTER_API_KEY="mock_key"`, and `ENVIRONMENT="test"` via `monkeypatch.setenv`.
  4. Update `.github/workflows/test.yml` to install `.[dev,test]` and run `ruff check src tests`, `mypy src`, and `python -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-fail-under=90`.
- **TDD Verification Test:** All 55+ tests pass under `pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-fail-under=90` with exit code `0` even when `.env` is present.

---

### REM-003: Enforce `ConfigDict(extra="forbid", frozen=True)` & Remove `DynamicFallbackModel` Masking
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `CRITICAL` | Pydantic v2 Schema Strictness & Immutability
- **Exact Evidence:** `src/gemini_cost_arbiter/models/telemetry.py:23,52,73,96,113,127,145`; `src/gemini_cost_arbiter/models/remediation.py:31,78,101`; `src/gemini_cost_arbiter/models/audit.py:11`; `src/gemini_cost_arbiter/models/__init__.py:27-35`; `app/schemas.py:26-28`; `src/gemini_cost_arbiter/config.py:16`; `src/gemini_cost_arbiter/engine.py:181-183`
- **Root Cause & Security/Reliability Impact:** Every Pydantic model uses `extra="allow"` and mutable instances, allowing unvalidated fields, in-place mutation of signed models (`engine.py:182-183`), and silent env var typos (`config.py:16`). `models/__init__.py:33-35` and `app/schemas.py:26-28` define `__getattr__` returning `DynamicFallbackModel`, masking broken imports.
- **Exact Fix Specification:**
  1. Set `model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)` on all models in `models/telemetry.py`, `models/remediation.py`, and `models/audit.py`.
  2. Set `extra="forbid"` in `ArbiterConfig.model_config` (`config.py:16`).
  3. Remove `DynamicFallbackModel` and `__getattr__` from `models/__init__.py` and `app/schemas.py`.
  4. Update `engine.py:181-183` to use `a.model_copy(update={"reasoning_rationale": f"[DRY-RUN SIMULATION] {a.reasoning_rationale}"})`.
- **TDD Verification Test:** `tests/test_schema_strictness.py::test_models_forbid_extra_and_are_frozen` asserting `ValidationError` on unknown fields, `NaN`/`Inf` floats, and attribute mutation across `EC2Metrics`, `RemediationActionItem`, `RemediationPlan`, and `FinOpsAuditSummary`.

---

### REM-004: Bound All Resource IDs, Strings, Collections & Enforce `RemediationPlan` Savings Sum
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `CRITICAL` | Input Validation, DoS Defense & Anti-Hallucination Math
- **Exact Evidence:** `src/gemini_cost_arbiter/models/telemetry.py:25-37,54-67,75-90,98-107,115-121,131-134,147-151`; `src/gemini_cost_arbiter/models/remediation.py:33-48,75-95`
- **Root Cause & Security/Reliability Impact:** String fields (`resource_id`, `current_instance_type`, `environment`, `region`, `plan_id`, `reasoning_rationale`), `CloudTelemetry` numeric fields (`monthly_cost_usd`, `cpu_utilization_avg`, `memory_utilization_avg` at `telemetry.py:131-134`), and list/dict fields (`tags`, `ec2_instances`, `actions`, `system_mitigations`) lack length/regex/range bounds. Furthermore, `RemediationPlan` has no `@model_validator(mode="after")` verifying `total_projected_monthly_savings_usd == round(sum(a.projected_monthly_savings_usd for a in self.actions), 2)`.
- **Exact Fix Specification:**
  1. Constrain `resource_id` (`min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:/-]+$"`), `current_instance_type`/`current_instance_class` (`min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9.-]+$"`), `environment`/`region` (`min_length=1, max_length=64`), `reasoning_rationale` (`max_length=2048`), `target_configuration` (`min_length=1, max_length=128`), and `plan_id` (`min_length=1, max_length=64`).
  2. Bound `TelemetryBatch` lists (`max_length=500`), `tags` (`max_length=64`, key/value `max_length=128`), `actions` (`max_length=500`), and `system_mitigations` (`max_length=32`).
  3. Enforce `ge=0.0` on all USD spend/savings fields and `ge=0.0, le=100.0` on `CloudTelemetry` percentages (`telemetry.py:131-134`).
  4. Add `@model_validator(mode="after")` on `RemediationPlan` enforcing `abs(self.total_projected_monthly_savings_usd - round(sum(a.projected_monthly_savings_usd for a in self.actions), 2)) <= 0.01`.
- **TDD Verification Test:** `tests/test_schema_strictness.py::test_bounded_fields_and_plan_savings_invariant` asserting `ValidationError` on `resource_id="i-1; rm -rf /"`, `len(ec2_instances)==501`, and mismatched `total_projected_monthly_savings_usd`.

---

### REM-005: Fail-Closed Catalog Loading (`CatalogNotFoundError`) & Dynamic `CATALOG_PATH` Resolution
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `HIGH` | Deterministic Guardrails & Catalog Integrity
- **Exact Evidence:** `src/gemini_cost_arbiter/heuristics/ec2_rules.py:49-60,85,120-123`; `src/gemini_cost_arbiter/engine.py:562-564`
- **Root Cause & Security/Reliability Impact:** `load_instance_catalog()` uses a fragile relative `Path("config/instance_mappings.json")`, swallows all exceptions (`except Exception: pass`), and silently falls back to hardcoded maps. Unknown instance types silently default to `"t4g.xlarge"` (`ec2_rules.py:85`) and a flat `0.65` multiplier (`ec2_rules.py:121`). `engine.py:563` also uses a relative path and returns `"{}"` if missing.
- **Exact Fix Specification:**
  1. Define `CatalogNotFoundError(RuntimeError)` in `ec2_rules.py`.
  2. Resolve catalog path via `ArbiterConfig.catalog_path` (`CATALOG_PATH` env var) or `Path(__file__).resolve().parents[3] / "config" / "instance_mappings.json"`.
  3. Raise `CatalogNotFoundError` if the file is missing, unreadable, or invalid JSON; remove silent fallback defaults.
  4. Return `None` (with warning log) when `current_instance_type` is absent from `instance_downsize_map` or `instance_hourly_rates_usd`.
  5. Update `engine.py:562-564` to use the resolved catalog path and return JSON-RPC `-32603` on error.
- **TDD Verification Test:** `tests/test_catalog_and_normalization.py::test_missing_or_corrupted_catalog_fails_closed` asserting `pytest.raises(CatalogNotFoundError)` on missing/corrupted `CATALOG_PATH` and `None` for unknown instance types.

---

### REM-006: Unicode NFKC + `.strip().casefold()` Normalization & Production Tag Detection
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `MEDIUM` | Deterministic String Evaluation
- **Exact Evidence:** `src/gemini_cost_arbiter/heuristics/ec2_rules.py:71,81,85,88`; `src/gemini_cost_arbiter/heuristics/rds_rules.py:13,16`; `src/gemini_cost_arbiter/heuristics/ebs_rules.py:13`; `src/gemini_cost_arbiter/heuristics/s3_rules.py:19`; `src/gemini_cost_arbiter/guardrails/risk_scorer.py:63,100,103,128,131,183`
- **Root Cause & Security/Reliability Impact:** Comparisons use `.lower()`/`.upper()` without Unicode NFKC normalization or `.strip().casefold()`, and only match `"production"`—missing `"prod"`, `"prd"`, and `tags["Environment"]`/`tags["env"]`. Full-width Unicode or whitespace bypasses production risk scoring (`risk=4`) and RI/Savings Plan `$0` billing rules.
- **Exact Fix Specification:**
  1. Add `normalize_str(value: str) -> str` (`unicodedata.normalize("NFKC", value).strip().casefold()`) and `is_production_resource(environment: str, tags: Dict[str, str]) -> bool` matching `{"production", "prod", "prd"}` across `environment` and normalized tag keys `{"environment", "env", "stage"}`.
  2. Replace all `.lower()`/`.upper()` comparisons across `heuristics/*` and `guardrails/risk_scorer.py` with `normalize_str(...)`.
- **TDD Verification Test:** `tests/test_catalog_and_normalization.py::test_unicode_nfkc_and_prod_tag_detection` passing `environment=" Ｐｒｏｄｕｃｔｉｏｎ "` and `tags={"Env": "PRD"}` and asserting `safety_risk_score == 4`.

---

### REM-007: Eliminate Shell Injection (`shlex.quote()`) in CLI/Rollback & Remove `*` Wildcard IAM
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `CRITICAL` | Command Injection & Least-Privilege IAM
- **Exact Evidence:** `src/gemini_cost_arbiter/guardrails/risk_scorer.py:30-45,64-122,129-156`
- **Root Cause & Security/Reliability Impact:** `_generate_aws_cli` and `_generate_rollback_plan` interpolate `res_id` and `target_cfg` directly into shell strings without `shlex.quote()` or regex validation. `_generate_iam_policy` hardcodes `arn = "*"` for `EIP` (`risk_scorer.py:146`) and falls back to `"*"` if `res_id == "*"` (`risk_scorer.py:134,140,149,155`). `audit_and_enrich_action` accepts `bool` for `safety_risk_score` and treats `[""]` as non-empty mitigations.
- **Exact Fix Specification:**
  1. Validate `res_id` (`^[a-zA-Z0-9._:/-]+$`) and `target_cfg` (`^[a-zA-Z0-9._-]+$`), and wrap all interpolated CLI/rollback arguments in `shlex.quote(...)`.
  2. Reject `res_id == "*"` with `ValueError`; scope `EIP` `Resource` to `f"arn:aws:ec2:*:*:elastic-ip/{res_id}"` so zero `"*"` literals appear in any IAM `Action` or `Resource`.
  3. Enforce `type(score) is int and 1 <= score <= 5` and filter `mitigations = [m.strip() for m in raw_mitigations if isinstance(m, str) and m.strip()]` before quarantine checks.
- **TDD Verification Test:** `tests/test_guardrails_security.py::test_zero_wildcard_iam_and_cli_injection_blocked` asserting zero `"*"` in all 5 IAM policies, `ValueError` on `resource_id="i-1; cat /etc/passwd"`, and quarantine on `system_mitigations=["  "]` with `safety_risk_score=4`.

---

### REM-008: Reconcile LLM Outputs Against `TelemetryBatch` FinOps Floors & Cap Savings
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `HIGH` | FinOps Guardrail Integrity (LLM Path)
- **Exact Evidence:** `src/gemini_cost_arbiter/reasoner/client.py:230-233`; `src/gemini_cost_arbiter/reasoner/openrouter.py:97-100`; `src/gemini_cost_arbiter/guardrails/risk_scorer.py:28-57`
- **Root Cause & Security/Reliability Impact:** When `GEMINI_API_KEY` or `OPENROUTER_API_KEY` is active, LLM-proposed `RemediationActionItem`s only pass through `GuardrailEngine.audit_and_enrich_action(item)`, which does NOT cross-check `TelemetryBatch`. An LLM can hallucinate `projected_monthly_savings_usd > current_monthly_spend_usd`, downsize an EC2 instance with `memory_utilization_avg_pct > 65.0`, transition an S3 bucket with `< 128 KB` avg object size, or claim `> $0.00` savings on a `reserved`/`savings_plan` resource.
- **Exact Fix Specification:**
  1. Add `GuardrailEngine.reconcile_with_telemetry(actions: List[RemediationActionItem], batch: TelemetryBatch) -> List[RemediationActionItem]`.
  2. Clamp `projected_monthly_savings_usd <= current_monthly_spend_usd` and recompute `projected_monthly_spend_usd`.
  3. Drop/veto EC2 downsize actions where `memory_utilization_avg_pct > 65.0`, drop S3 Intelligent-Tiering actions where `avg_object_size_kb < 128.0`, and zero out savings (`0.0`) on `reserved`/`savings_plan` resources.
  4. Invoke `reconcile_with_telemetry` in `GeminiCostArbiterEngine.generate_remediation_plan()` for all LLM-generated plans.
- **TDD Verification Test:** `tests/test_guardrails_security.py::test_llm_plan_reconciled_against_finops_floors` feeding a mocked Gemini plan that proposes downsizing an 85% RAM EC2 instance and claiming `$999` savings on a `$100` RI, asserting the OOM downsize is blocked and RI savings are clamped to `$0.00`.

---

### REM-009: XML Breakout Stripping, Prompt Compression & Path-Safe Prompt Loader
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `HIGH` | Prompt Injection Defense, Context Bloat & Path Traversal
- **Exact Evidence:** `src/gemini_cost_arbiter/reasoner/prompt_compiler.py:10-64`; `prompts/master_system_prompt.md`; `prompts/modules/*.md`
- **Root Cause & Security/Reliability Impact:** `sanitize_string()` does not strip `<`/`>` XML breakout tags, and `compile_reasoner_prompt()` neither wraps telemetry in `<untrusted_proposal_data>` delimiters nor compresses defaults (`exclude_none=True, exclude_defaults=True`) or caps `MAX_PROMPT_CHARS`. `SYSTEM_PROMPT` is hardcoded instead of loaded from `prompts/` with `Path.resolve().is_relative_to(prompts_dir.resolve())`.
- **Exact Fix Specification:**
  1. Implement `load_prompt_file(relative_path: str, prompts_dir: Optional[Path] = None) -> str` enforcing `target.is_relative_to(base_dir.resolve())` and `encoding="utf-8"`.
  2. In `sanitize_string()`, NFKC-normalize and strip `<` and `>` characters before `INJECTION_PATTERN` replacement.
  3. In `compile_reasoner_prompt()`, dump with `exclude_none=True, exclude_defaults=True`, enforce `MAX_PROMPT_CHARS` (default `32768`), and wrap in `<untrusted_proposal_data>\n...\n</untrusted_proposal_data>`.
- **TDD Verification Test:** `tests/test_prompt_security.py::test_xml_breakout_compression_and_path_traversal` asserting `</untrusted_proposal_data>` is stripped, empty lists are omitted, and `load_prompt_file("../.env")` raises `ValueError`.

---

### REM-010: Harden `clean_gemini_schema()` for Multi-Branch `anyOf` & Align Docs
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `MEDIUM` | OpenAPI 3.0 `responseSchema` Sanitization
- **Exact Evidence:** `src/gemini_cost_arbiter/reasoner/client.py:66-104`; `gemini.md:219`; `prompts/README.md:41`
- **Root Cause & Security/Reliability Impact:** Multi-branch `anyOf` (e.g., `Union[str, int]`) fails `len(non_null) == 1` (`client.py:69`) and falls through to lines `84-104`, where `"anyOf"` is dropped by `ALLOWED_GEMINI_FIELDS`, leaving an empty `{}` schema that triggers Gemini HTTP 400.
- **Exact Fix Specification:**
  1. In `clean_gemini_schema()`, handle `len(non_null) > 1` by selecting the first non-null branch (preserving `nullable=True` if `null` was present) rather than emitting `{}`.
  2. Recursively strip `default`, `minimum`, `maximum`, `$schema`, `title`, and `additionalProperties`.
- **TDD Verification Test:** `tests/test_phase9_hardening.py::test_clean_gemini_schema_handles_multi_branch_anyof` asserting multi-branch `anyOf` never returns `{}`.

---

### REM-011: Token/Cost & Consecutive-Failure Circuit Breakers, `30s` Timeout, `<think>` Strip & OpenRouter Retries
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `HIGH` | Bounded Self-Healing, Fallback State Machine & Cost Control
- **Exact Evidence:** `src/gemini_cost_arbiter/reasoner/client.py:128,152,174-220,256-263`; `src/gemini_cost_arbiter/reasoner/openrouter.py:37,51-93`; `src/gemini_cost_arbiter/engine.py:150-175`; `src/gemini_cost_arbiter/config.py:30-58`
- **Root Cause & Security/Reliability Impact:** `client.py:152` hardcodes `"maxOutputTokens": 16384`; `client.py:128` and `openrouter.py:37` use `45.0s` timeouts; neither client enforces `MAX_SESSION_TOKEN_BUDGET` (`500000`), `DAILY_API_COST_LIMIT_USD` (`$10.00`), or a consecutive-failure cooldown circuit breaker (`3` consecutive errors -> fast-fail to heuristics). `client.py:256-263` lacks `<think>...</think>` stripping, `openrouter.py:72-75` lacks retry+jitter, and `engine.py` does not record `fallback_tier_used` telemetry.
- **Exact Fix Specification:**
  1. Add `max_output_tokens=8192`, `max_session_token_budget=500000`, `daily_api_cost_limit_usd=10.0`, and `circuit_breaker_failure_threshold=3` to `ArbiterConfig`.
  2. Enforce `httpx.Timeout(30.0, connect=10.0)` and `max_retries=2` with exponential backoff + jitter in both `GeminiReasonerClient` and `OpenRouterFallbackClient`.
  3. Implement `LLMQuotaCircuitBreaker` tracking session tokens, daily UTC USD spend, and consecutive failures; trip to `DeterministicHeuristicEngine` and log `fallback_tier_used`.
  4. Unify `_extract_json()` to strip `<think>...</think>` and markdown fences safely before `json.loads()`.
- **TDD Verification Test:** `tests/test_circuit_breaker.py::test_cost_and_consecutive_failure_circuit_breakers` asserting `DAILY_API_COST_LIMIT_USD` and 3 consecutive HTTP 503s trip immediate heuristic fallback without extra network calls.

---

### REM-012: Canonical JSON `ensure_ascii=False` & Reject Placeholder Signing Secrets
- **Severity & Category:** `CRITICAL` | Cryptographic Integrity & Secret Hygiene
- **Exact Evidence:** `src/gemini_cost_arbiter/guardrails/risk_scorer.py:176,181-192`; `src/gemini_cost_arbiter/config.py:123-132`
- **Root Cause & Security/Reliability Impact:** `attach_plan_digest()` omits `ensure_ascii=False` in `json.dumps(...)` (`risk_scorer.py:176`), causing canonicalization drift on non-ASCII tags. In `production`, `risk_scorer.py:182-184` only checks `if not signing_key_str:`, allowing `.env.example:8` placeholder `"your_32_byte_hmac_signing_secret_here"` or weak short secrets (`< 32` chars).
- **Exact Fix Specification:**
  1. Set `ensure_ascii=False` in `risk_scorer.py:176`.
  2. Reject known placeholders (`"your_32_byte_hmac_signing_secret_here"`, `"changeme"`, `"secret"`, `"test"`) and `len(signing_key_str.strip()) < 32` in `production` (`RuntimeError`).
  3. Use `plan.model_copy(update={"plan_digest": digest, "plan_signature": signature})`.
- **TDD Verification Test:** `tests/test_phase9_hardening.py::test_placeholder_signing_secret_rejected_in_production` asserting `RuntimeError` for placeholder/short secrets when `ENVIRONMENT=production`.

---

### REM-013: Enforce `risk == 5` Quarantine & Signed Anti-Replay HITL Approval Gate
- **Severity & Category:** `HIGH` | Human-in-the-Loop (HITL) Quarantine & Anti-Replay Security
- **Exact Evidence:** `src/gemini_cost_arbiter/models/remediation.py:53-60`; `src/gemini_cost_arbiter/guardrails/risk_scorer.py:39-47`; `src/gemini_cost_arbiter/engine.py:300-383`
- **Root Cause & Security/Reliability Impact:** Critical destructive actions (`safety_risk_score == 5`) are not automatically quarantined when mitigations are present, and `quarantined=True` items have no cryptographic HITL approval/release mechanism (`approve_quarantined_action` MCP tool or `/approve` endpoint) with canonical HMAC-SHA256, `issued_at`/`expires_at` (`<= 300s` TTL), and `nonce` deduplication.
- **Exact Fix Specification:**
  1. Automatically quarantine `safety_risk_score == 5` actions (`quarantined=True`, `quarantine_reason="Critical risk (5/5) requires signed HITL SRE approval"`) in `GuardrailEngine.audit_and_enrich_action`.
  2. Add `approve_quarantined_action` MCP tool (and `GuardrailEngine.verify_hitl_approval(...)`) validating canonical HMAC-SHA256 over `{plan_id, resource_id, issued_at, expires_at, nonce}`, rejecting `expires_at - issued_at > 300`, `now >= expires_at`, and replayed `nonce`s.
- **TDD Verification Test:** `tests/test_hitl_approval.py::test_risk_5_quarantined_and_anti_replay_approval` asserting `risk=5` is quarantined, valid signed approval releases it, and expired (`>= 300s`) or replayed `nonce` fails closed.

---

### REM-014: Enforce SSE Payload Body Limit (`MAX_PAYLOAD_BYTES` / HTTP 413), Random Session IDs & Placeholder Key Rejection
- **Severity & Category:** `CRITICAL` | SSE Transport Security & DoS Protection
- **Exact Evidence:** `src/gemini_cost_arbiter/mcp/server_sse.py:29,34,59-66,97,121-129`; `src/gemini_cost_arbiter/config.py:118-137`
- **Root Cause & Security/Reliability Impact:** `POST /messages` calls `await request.json()` (`server_sse.py:126`) without a `MAX_PAYLOAD_BYTES` (`10485760` / 10 MB) limit, enabling memory-exhaustion DoS. `GET /sse` uses predictable `str(id(request))` (`server_sse.py:97`) instead of `secrets.token_urlsafe(16)`. `_verify_auth` accepts placeholder `MCP_API_KEY` values in `production`, and `SensitiveQueryParamFilter` misses `api_key=`.
- **Exact Fix Specification:**
  1. Add `max_payload_bytes: int = Field(default=10485760, ge=1024, validation_alias="MAX_PAYLOAD_BYTES")` to `ArbiterConfig`.
  2. Check `Content-Length` and `len(await request.body()) > max_payload_bytes` in `handle_message_post`, returning HTTP `413 Payload Too Large`.
  3. Replace `str(id(request))` with `secrets.token_urlsafe(16)`, reject placeholder `MCP_API_KEY` in `production`, and update log redaction regex to `r"(?i)(api_?key)=[^&\s\"]+"`.
- **TDD Verification Test:** `tests/test_sse.py::test_sse_rejects_oversized_payload_413_and_uses_random_session` asserting HTTP 413 above `MAX_PAYLOAD_BYTES` and `len(session_id) >= 16`.

---

### REM-015: SQLite WAL Mode, `busy_timeout=5000`, `threading.RLock` + `filelock.FileLock` & Auto-Mkdir
- **Severity & Category:** `HIGH` | SQLite Concurrency & Cross-Platform Persistence
- **Exact Evidence:** `src/gemini_cost_arbiter/ledger/store.py:14,31,59,102,110,137`
- **Root Cause & Security/Reliability Impact:** `FinOpsLedger` claims thread safety (`store.py:14`) but has zero locks, does not enable `PRAGMA journal_mode=WAL` or `PRAGMA busy_timeout=5000`, does not create missing parent directories, and calls `json.dumps(plan_dict)` without `ensure_ascii=False`. Concurrent SSE/stdio access triggers `sqlite3.OperationalError: database is locked`.
- **Exact Fix Specification:**
  1. Add `filelock>=3.16.0` to `pyproject.toml` and `requirements.txt`.
  2. Add `self._thread_lock = threading.RLock()`, `Path(db_path).parent.mkdir(parents=True, exist_ok=True)`, and `self._file_lock = FileLock(f"{db_path}.lock", timeout=10.0)`.
  3. Configure `_connect()` with `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA synchronous=NORMAL;` and `ensure_ascii=False` in `json.dumps`.
- **TDD Verification Test:** `tests/test_sqlite_ledger.py::test_sqlite_wal_and_concurrent_writes` running 20 concurrent `record_plan()` threads, asserting `PRAGMA journal_mode` == `"wal"` and `total_batches_processed == 20`.

---

### REM-016: Docker Image `prompts/` Inclusion & `PROMPTS_DIR` Path Portability
- **Severity & Category:** `MEDIUM` | Containerization & Deployment Parity
- **Exact Evidence:** `Dockerfile:48-51`; `deploy/aws-free-tier/lambda-adapter/Dockerfile`
- **Root Cause & Security/Reliability Impact:** `Dockerfile:49-50` copies `config/` and `README.md` into `/app/` but omits `prompts/`. Once `prompt_compiler.py` loads `prompts/` (REM-009), containers will fail unless `prompts/` is copied and `PROMPTS_DIR` is resolved dynamically.
- **Exact Fix Specification:**
  1. Add `COPY prompts/ /app/prompts/` to `Dockerfile` (and `lambda-adapter/Dockerfile`).
  2. Add `prompts_dir: str = Field(default="prompts", validation_alias="PROMPTS_DIR")` to `ArbiterConfig` with fallback to repo-root `prompts/`.
- **TDD Verification Test:** `tests/test_prompt_security.py::test_prompts_directory_resolvable_from_arbitrary_cwd` verifying `load_prompt_file("master_system_prompt.md")` succeeds when `cwd` is `tmp_path`.

---

### REM-017: Cross-File Documentation, MCP `finops://` URI & `prompts/modular_prompt.md` Synchronization
- **Severity & Category:** `LOW` | Documentation Accuracy & PromptOps Registry
- **Exact Evidence:** `gemini.md:65-70,104,161,164,209-210,219`; `prompts/README.md:41`; `docs/ARCHITECTURE.md:48`; `prompts/` (missing `modular_prompt.md`)
- **Root Cause & Security/Reliability Impact:** `gemini.md:209-210` omits the `finops://` scheme (`engine.py:506,512`), `gemini.md:161,164` references nonexistent `telemetry_sample.json` instead of `sample_telemetry.json`, `gemini.md:219` and `prompts/README.md:41` omit `clean_gemini_schema()`, `docs/ARCHITECTURE.md:48` cites `52` tests instead of `55+`, and `prompts/modular_prompt.md` is missing.
- **Exact Fix Specification:**
  1. Create `prompts/modular_prompt.md` indexing `master_system_prompt.md` and `modules/01`–`modules/06`.
  2. Align `GEMINI.md`, `prompts/README.md`, `README.md`, and `docs/ARCHITECTURE.md` with `finops://` URIs, `sample_telemetry.json`, `clean_gemini_schema()`, `DEFAULT_MODEL`, and exact file trees/test counts.
- **TDD Verification Test:** `tests/test_governance_docs.py::test_mcp_resource_uris_and_prompts_registry_synced` asserting all `resources/list` URIs appear in `GEMINI.md` and `README.md`, and all `prompts/modules/*.md` files are indexed in `prompts/modular_prompt.md`.

---

### REM-018: Standardize `docs/` Tree & Add AWS, Azure, and Gemini Deployment Packages
- **Status:** `DONE` (2026-11-21)
- **Severity & Category:** `LOW` | Architecture Packaging & Multi-Cloud Deployment Standardization
- **Exact Evidence:** `docs/AWS_Deployment_Guide.md`, `deploy/aws-free-tier/`, `Repo_Baseline_AuditReport.md`
- **Root Cause & Security/Reliability Impact:** Deployment guides and artifacts were split inconsistently between `docs/AWS_Deployment_Guide.md` and `deploy/aws-free-tier/`, `Repo_Baseline_AuditReport.md` cluttered the repository root, and Azure / Google Cloud Run + Gemini MCP client deployment packages were absent.
- **Exact Fix Specification:**
  1. Consolidated `docs/AWS_Deployment_Guide.md` and `deploy/aws-free-tier/README.md` into `docs/DEPLOYMENT_AWS.md`, added `docs/DEPLOYMENT_AZURE.md` and `docs/DEPLOYMENT_GEMINI.md`, and moved `Repo_Baseline_AuditReport.md` to `docs/Repo_Baseline_AuditReport.md`.
  2. Migrated `deploy/aws-free-tier/` assets to `deploy/aws/` (`deploy-ec2.sh`, `docker-compose.prod.yml`, `lambda-adapter/Dockerfile`) and created `deploy/azure/` (`deploy-azure.sh`, `docker-compose.azure.yml`) and `deploy/gemini/` (`cloudbuild.yaml`, `service.yaml`, `mcp_configs.example.json`).
  3. Synchronized `README.md`, `PROJECT_MAP.md`, `GEMINI.md`, `Enterprise_Blueprint.md`, and `BUILD_PROMPTS.md`.
- **TDD Verification Test:** `tests/test_governance_docs.py::test_deployment_docs_and_packages_valid` asserting all three deployment docs, provider directories, and JSON/YAML manifests exist and parse cleanly.
