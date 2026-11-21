# Deterministic Build Prompt Playbook (`BUILD_PROMPTS.md`)

**Project:** `gemini-cost-arbiter-mcp`  
**Roadmap Source:** [`Enterprise_Blueprint.md`](Enterprise_Blueprint.md) | [`AUDIT_REMEDIATION_LOG.md`](AUDIT_REMEDIATION_LOG.md)  
**Usage:** Copy any fenced `BUILD-PROMPT-XX` block into a fresh autonomous coding session. Each prompt is 100% self-contained, begins with the mandatory **3-Line Session Bootstrap & Persona Header**, and ends with the **Auto-Commit & Fail-Closed Verification Gate**.

---

## `BUILD-PROMPT-01` — Governance Case Normalization & Playbook Foundation (`REM-001`)

```markdown
Act as a Principal AI Security Architect and Staff Python SRE executing Tier-1 production remediation on `gemini-cost-arbiter-mcp`.
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards, invariants, and 3-strike circuit breaker rules.
Execute ONLY this task (`BUILD-PROMPT-01`), follow all TDD, explicit `encoding="utf-8"` file I/O, no-self-mocking, and zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### Scope (`REM-001`)
1. Normalize `gemini.md` to uppercase `GEMINI.md` in the git index (`git mv gemini.md gemini.md.tmp && git mv gemini.md.tmp GEMINI.md`).
2. Ensure `PROJECT_MAP.md` and `BUILD_PROMPTS.md` are complete with zero placeholders.
3. Update `README.md` as a 100% hyperlinked Master Navigation Hub and fix `gemini.md` -> `GEMINI.md` in `README.md`.
4. Add `tests/test_governance_docs.py` verifying governance files and zero broken relative Markdown links in `README.md`.

### Auto-Commit & Fail-Closed Verification Gate
Run: `.venv\Scripts\python.exe -m pytest tests/test_governance_docs.py -v`
- On 100% pass: stage explicit modified/created files (`git add <explicit_files>`, never `git add -A`), commit with `chore(governance): normalize GEMINI.md and add PROJECT_MAP.md and BUILD_PROMPTS.md (REM-001)`, and report the short commit SHA in the 5-line Session Handover Block.
- On any failure: DO NOT run `git commit`; emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` with the exact error trace and halt.
```

---

## `BUILD-PROMPT-02` — CI/CD Quality Gates & Test Env Isolation (`REM-002`)

```markdown
Act as a Principal AI Security Architect and Staff Python SRE executing Tier-1 production remediation on `gemini-cost-arbiter-mcp`.
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards, invariants, and 3-strike circuit breaker rules.
Execute ONLY this task (`BUILD-PROMPT-02`), follow all TDD, explicit `encoding="utf-8"` file I/O, no-self-mocking, and zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### Scope (`REM-002`)
1. Add `pytest-cov>=6.0.0` and `pytest-timeout>=2.3.1` to `pyproject.toml` (`[project.optional-dependencies].test`) and `requirements.txt`; install dev/test tools into `.venv`.
2. Add `[tool.mypy]` (`python_version = "3.13"`, `strict = true`, `ignore_missing_imports = false`, `warn_return_any = true`) and `timeout = 10` (`timeout_method = "thread"`) to `pyproject.toml`.
3. Create `tests/conftest.py` with an `autouse=True` fixture setting `GEMINI_API_KEY="test-key"`, `OPENROUTER_API_KEY="mock_key"`, and `ENVIRONMENT="test"` via `monkeypatch.setenv` so local `.env` files never trigger live network calls.
4. Update `.github/workflows/test.yml` to install `.[dev,test]` and enforce `ruff check src tests`, `mypy src`, and `pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-fail-under=90`.

### Auto-Commit & Fail-Closed Verification Gate
Run: `.venv\Scripts\python.exe -m ruff check src tests ; .venv\Scripts\python.exe -m mypy src ; .venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-report=term:skip-covered`
- On 100% pass: stage explicit files (`git add <explicit_files>`), commit with `ci(gates): enforce ruff, mypy strict, pytest-timeout, and 90% coverage (REM-002)`, and report the short commit SHA.
- On any failure: DO NOT commit; emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` with the exact error trace and halt.
```

---

## `BUILD-PROMPT-03` — Strict Immutable Bounded Pydantic v2 Models (`REM-003`, `REM-004`)

```markdown
Act as a Principal AI Security Architect and Staff Python SRE executing Tier-1 production remediation on `gemini-cost-arbiter-mcp`.
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards, invariants, and 3-strike circuit breaker rules.
Execute ONLY this task (`BUILD-PROMPT-03`), follow all TDD, explicit `encoding="utf-8"` file I/O, no-self-mocking, and zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### Scope (`REM-003`, `REM-004`)
1. Enforce `model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)` across all models in `src/gemini_cost_arbiter/models/telemetry.py`, `remediation.py`, and `audit.py`, plus `extra="forbid"` on `ArbiterConfig` (`config.py`).
2. Remove `DynamicFallbackModel` and `__getattr__` from `src/gemini_cost_arbiter/models/__init__.py` and `app/schemas.py`.
3. Update `src/gemini_cost_arbiter/engine.py` dry-run annotation to use `a.model_copy(update=...)` instead of in-place mutation.
4. Bound `resource_id`, `current_instance_type`/`current_instance_class`, `environment`, `region`, `plan_id`, `reasoning_rationale`, `target_configuration`, `TelemetryBatch` lists (`max_length=500`), `tags` (`max_length=64`), `actions`, `system_mitigations`, `CloudTelemetry` metrics, and add `@model_validator(mode="after")` on `RemediationPlan` verifying `total_projected_monthly_savings_usd`.
5. Add `tests/test_schema_strictness.py` testing immutability, `extra="forbid"`, `NaN`/`Inf` rejection, field bounds, and savings sum invariants.

### Auto-Commit & Fail-Closed Verification Gate
Run: `.venv\Scripts\python.exe -m ruff check src tests ; .venv\Scripts\python.exe -m mypy src ; .venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-report=term:skip-covered`
- On 100% pass: stage explicit files, commit with `feat(models): enforce frozen extra=forbid schemas and bounded fields (REM-003, REM-004)`, and report the short commit SHA.
- On any failure: DO NOT commit; emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` and halt.
```

---

## `BUILD-PROMPT-04` — Fail-Closed Catalog & Unicode Normalization (`REM-005`, `REM-006`)

```markdown
Act as a Principal AI Security Architect and Staff Python SRE executing Tier-1 production remediation on `gemini-cost-arbiter-mcp`.
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards, invariants, and 3-strike circuit breaker rules.
Execute ONLY this task (`BUILD-PROMPT-04`), follow all TDD, explicit `encoding="utf-8"` file I/O, no-self-mocking, and zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### Scope (`REM-005`, `REM-006`)
1. Implement `CatalogNotFoundError` in `src/gemini_cost_arbiter/heuristics/ec2_rules.py`, resolve `CATALOG_PATH` dynamically, remove silent fallback maps/65% estimates, and return `None` for unknown instance types.
2. Update `engine.py` (`finops://config/instance-mappings`) to use the same resolved catalog path and return JSON-RPC `-32603` on error.
3. Add `normalize_str()` (`unicodedata.normalize("NFKC", val).strip().casefold()`) and `is_production_resource()` (`{"production", "prod", "prd"}` across `environment` and tags) across `heuristics/*` and `guardrails/risk_scorer.py`.
4. Add `tests/test_catalog_and_normalization.py` covering missing/corrupt catalogs, unknown instance types, and NFKC/tag normalization.

### Auto-Commit & Fail-Closed Verification Gate
Run: `.venv\Scripts\python.exe -m ruff check src tests ; .venv\Scripts\python.exe -m mypy src ; .venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-report=term:skip-covered`
- On 100% pass: stage explicit files, commit with `feat(heuristics): fail-closed catalog and NFKC normalization (REM-005, REM-006)`, and report the short commit SHA.
- On any failure: DO NOT commit; emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` and halt.
```

---

## `BUILD-PROMPT-05` — Guardrail Hardening & FinOps Reconciliation (`REM-007`, `REM-008`)

```markdown
Act as a Principal AI Security Architect and Staff Python SRE executing Tier-1 production remediation on `gemini-cost-arbiter-mcp`.
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards, invariants, and 3-strike circuit breaker rules.
Execute ONLY this task (`BUILD-PROMPT-05`), follow all TDD, explicit `encoding="utf-8"` file I/O, no-self-mocking, and zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### Scope (`REM-007`, `REM-008`)
1. Validate `res_id`/`target_cfg` and apply `shlex.quote()` in `GuardrailEngine._generate_aws_cli()` and `_generate_rollback_plan()`.
2. Remove `"*"` from EIP and fallback IAM policies (`_generate_iam_policy`), rejecting `res_id == "*"` with `ValueError`.
3. Reject `bool` `safety_risk_score` and filter whitespace-only `system_mitigations` before quarantine evaluation.
4. Implement `GuardrailEngine.reconcile_with_telemetry(actions, batch)` enforcing `projected_monthly_savings_usd <= current_monthly_spend_usd`, EC2 >65% RAM veto, S3 <128 KB veto, and RI/Savings Plan `$0.00` savings on LLM plans.
5. Add TDD tests in `tests/test_guardrails_security.py`.

### Auto-Commit & Fail-Closed Verification Gate
Run: `.venv\Scripts\python.exe -m ruff check src tests ; .venv\Scripts\python.exe -m mypy src ; .venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-report=term:skip-covered`
- On 100% pass: stage explicit files, commit with `fix(guardrails): shlex CLI hardening, zero-wildcard IAM, and LLM reconciliation (REM-007, REM-008)`, and report the short commit SHA.
- On any failure: DO NOT commit; emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` and halt.
```

---

## `BUILD-PROMPT-06` — Prompt Defense, Compression & Schema Sanitization (`REM-009`, `REM-010`)

```markdown
Act as a Principal AI Security Architect and Staff Python SRE executing Tier-1 production remediation on `gemini-cost-arbiter-mcp`.
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards, invariants, and 3-strike circuit breaker rules.
Execute ONLY this task (`BUILD-PROMPT-06`), follow all TDD, explicit `encoding="utf-8"` file I/O, no-self-mocking, and zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### Scope (`REM-009`, `REM-010`)
1. Strip `<`/`>` XML breakout tags in `sanitize_string()`, compress `TelemetryBatch` (`exclude_none=True, exclude_defaults=True`, `MAX_PROMPT_CHARS=32768`), and wrap telemetry in `<untrusted_proposal_data>...</untrusted_proposal_data>`.
2. Implement `load_prompt_file()` enforcing `Path.resolve().is_relative_to(prompts_dir.resolve())` and `encoding="utf-8"`.
3. Harden `clean_gemini_schema()` in `reasoner/client.py` to handle multi-branch `anyOf` without emitting `{}`.
4. Add `tests/test_prompt_security.py` and expand `tests/test_phase9_hardening.py`.

### Auto-Commit & Fail-Closed Verification Gate
Run: `.venv\Scripts\python.exe -m ruff check src tests ; .venv\Scripts\python.exe -m mypy src ; .venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-report=term:skip-covered`
- On 100% pass: stage explicit files, commit with `fix(reasoner): prompt breakout defense, compression, and schema anyOf fix (REM-009, REM-010)`, and report the short commit SHA.
- On any failure: DO NOT commit; emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` and halt.
```

---

## `BUILD-PROMPT-07` — Circuit Breakers & Fallback Resilience (`REM-011`)

```markdown
Act as a Principal AI Security Architect and Staff Python SRE executing Tier-1 production remediation on `gemini-cost-arbiter-mcp`.
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards, invariants, and 3-strike circuit breaker rules.
Execute ONLY this task (`BUILD-PROMPT-07`), follow all TDD, explicit `encoding="utf-8"` file I/O, no-self-mocking, and zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### Scope (`REM-011`)
1. Add `max_output_tokens=8192`, `max_session_token_budget=500000`, `daily_api_cost_limit_usd=10.0`, and `circuit_breaker_failure_threshold=3` to `ArbiterConfig`.
2. Enforce `httpx.Timeout(30.0, connect=10.0)` and `max_retries=2` with exponential backoff + jitter in both `GeminiReasonerClient` and `OpenRouterFallbackClient`.
3. Implement `LLMQuotaCircuitBreaker`, unify `<think>...</think>` + fence stripping in `_extract_json()`, and emit `fallback_tier_used` telemetry in `GeminiCostArbiterEngine`.
4. Add `tests/test_circuit_breaker.py`.

### Auto-Commit & Fail-Closed Verification Gate
Run: `.venv\Scripts\python.exe -m ruff check src tests ; .venv\Scripts\python.exe -m mypy src ; .venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-report=term:skip-covered`
- On 100% pass: stage explicit files, commit with `feat(resilience): add token/cost/cooldown circuit breakers and 30s timeouts (REM-011)`, and report the short commit SHA.
- On any failure: DO NOT commit; emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` and halt.
```

---

## `BUILD-PROMPT-08` — Crypto Canonicalization, HITL & SSE Hardening (`REM-012`, `REM-013`, `REM-014`)

```markdown
Act as a Principal AI Security Architect and Staff Python SRE executing Tier-1 production remediation on `gemini-cost-arbiter-mcp`.
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards, invariants, and 3-strike circuit breaker rules.
Execute ONLY this task (`BUILD-PROMPT-08`), follow all TDD, explicit `encoding="utf-8"` file I/O, no-self-mocking, and zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### Scope (`REM-012`, `REM-013`, `REM-014`)
1. Enforce `ensure_ascii=False` in `attach_plan_digest()` and reject placeholder/short (`< 32` chars) `PLAN_SIGNING_SECRET` in `production`.
2. Auto-quarantine `safety_risk_score == 5` actions and implement `approve_quarantined_action` MCP tool with canonical HMAC-SHA256, `<= 300s` TTL (`issued_at`/`expires_at`), and `nonce` anti-replay deduplication.
3. Enforce `MAX_PAYLOAD_BYTES` (`10485760` / HTTP 413) in `server_sse.py`, replace `str(id(request))` with `secrets.token_urlsafe(16)`, reject placeholder `MCP_API_KEY` in `production`, and redact `api_key`/`apiKey` case-insensitively.
4. Add `tests/test_hitl_approval.py` and expand `tests/test_sse.py` and `tests/test_phase9_hardening.py`.

### Auto-Commit & Fail-Closed Verification Gate
Run: `.venv\Scripts\python.exe -m ruff check src tests ; .venv\Scripts\python.exe -m mypy src ; .venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-fail-under=90`
- On 100% pass: stage explicit files, commit with `feat(security): canonical signing, HITL anti-replay gate, and SSE 413 limit (REM-012..014)`, and report the short commit SHA.
- On any failure: DO NOT commit; emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` and halt.
```

---

## `BUILD-PROMPT-09` — SQLite WAL Concurrency & Docker Parity (`REM-015`, `REM-016`)

```markdown
Act as a Principal AI Security Architect and Staff Python SRE executing Tier-1 production remediation on `gemini-cost-arbiter-mcp`.
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards, invariants, and 3-strike circuit breaker rules.
Execute ONLY this task (`BUILD-PROMPT-09`), follow all TDD, explicit `encoding="utf-8"` file I/O, no-self-mocking, and zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### Scope (`REM-015`, `REM-016`)
1. Add `filelock>=3.16.0` to `pyproject.toml` and `requirements.txt`.
2. Update `FinOpsLedger` (`ledger/store.py`) to enable `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `threading.RLock`, `filelock.FileLock`, auto-create parent directories, and `ensure_ascii=False` in JSON serialization.
3. Copy `prompts/` into `/app/prompts/` in `Dockerfile` (and `deploy/aws/lambda-adapter/Dockerfile`), support `PROMPTS_DIR` in `ArbiterConfig`, and verify parity with `docs/DEPLOYMENT_AWS.md`, `docs/DEPLOYMENT_AZURE.md`, and `docs/DEPLOYMENT_GEMINI.md`.
4. Add concurrent write tests in `tests/test_sqlite_ledger.py` and cwd-portability tests in `tests/test_prompt_security.py`.

### Auto-Commit & Fail-Closed Verification Gate
Run: `.venv\Scripts\python.exe -m ruff check src tests ; .venv\Scripts\python.exe -m mypy src ; .venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-fail-under=90`
- On 100% pass: stage explicit files, commit with `feat(persistence): SQLite WAL concurrency, filelock, and Docker prompts parity (REM-015, REM-016)`, and report the short commit SHA.
- On any failure: DO NOT commit; emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` and halt.
```

---

## `BUILD-PROMPT-10` — Docs Sync, Prompt Registry & Final Release Gate (`REM-017`)

```markdown
Act as a Principal AI Security Architect and Staff Python SRE executing Tier-1 production remediation on `gemini-cost-arbiter-mcp`.
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards, invariants, and 3-strike circuit breaker rules.
Execute ONLY this task (`BUILD-PROMPT-10`), follow all TDD, explicit `encoding="utf-8"` file I/O, no-self-mocking, and zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### Scope (`REM-017`)
1. Create `prompts/modular_prompt.md` indexing `master_system_prompt.md` and `prompts/modules/01..06`.
2. Synchronize `README.md`, `prompts/README.md`, `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT_AWS.md`, `docs/DEPLOYMENT_AZURE.md`, `docs/DEPLOYMENT_GEMINI.md`, and `GEMINI.md` (`finops://` URIs, `sample_telemetry.json`, `clean_gemini_schema()`, `DEFAULT_MODEL`, accurate test counts).
3. Expand `tests/test_governance_docs.py` to assert 100% URI and prompt registry parity and run the Stage 2 CLI & coverage verification suite.

### Auto-Commit & Fail-Closed Verification Gate
Run: `.venv\Scripts\python.exe -m ruff check src tests ; .venv\Scripts\python.exe -m mypy src ; .venv\Scripts\python.exe -m pytest -q --tb=short --timeout=10 --cov=src/gemini_cost_arbiter --cov-fail-under=90`
- On 100% pass: stage explicit files, commit with `docs(sync): add prompts/modular_prompt.md and finalize release verification (REM-017)`, and report the short commit SHA.
- On any failure: DO NOT commit; emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` and halt.
```
