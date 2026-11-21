# Modular PromptOps Registry (`prompts/modular_prompt.md`)

**Project:** `gemini-cost-arbiter-mcp`  
**Default Model:** `DEFAULT_MODEL=gemini-3.8-flash-high` (`thinkingBudget=2048`, `maxOutputTokens=8192`)  
**Schema Sanitizer:** `clean_gemini_schema()` (dereferences `$defs`/`$ref`, collapses `anyOf`, excludes `execution_payload`, strips unsupported Protobuf keywords)  
**Prompt Injection Isolation:** Untrusted telemetry is NFKC-normalized, stripped of `<`/`>` breakout characters, compressed (`exclude_none=True, exclude_defaults=True`, `MAX_PROMPT_CHARS=32768`), and wrapped in `<untrusted_proposal_data>...</untrusted_proposal_data>`.

---

## 1. Tier-0 Master System Prompt

| Order | Artifact | Role & Responsibility | Token Budget |
|:---:|:---|:---|:---:|
| **0** | [`master_system_prompt.md`](master_system_prompt.md) | Global FinOps SRE persona, calibrated risk scoring (1–5), zero-hallucination axioms, anti-injection defense, and strict `RemediationPlan` JSON output contract | 800 |

---

## 2. Tier-1 Domain Cognitive Modules (`prompts/modules/`)

| Order | Module | Asset Coverage | Target Action Types | Token Budget |
|:---:|:---|:---|:---|:---:|
| **1** | [`01_ec2_compute_reasoning.md`](modules/01_ec2_compute_reasoning.md) | AWS EC2 Compute | `rightsize_instance`, `stop_instance`, `downsize` | 600 |
| **2** | [`02_rds_database_reasoning.md`](modules/02_rds_database_reasoning.md) | AWS RDS Relational Databases | `stop_db_instance`, `downsize` | 500 |
| **3** | [`03_s3_storage_tiering.md`](modules/03_s3_storage_tiering.md) | AWS S3 Object Storage | `transition_storage_tier` | 450 |
| **4** | [`04_ebs_eip_reclamation.md`](modules/04_ebs_eip_reclamation.md) | AWS EBS Volumes & Elastic IPs | `delete_unattached_volume`, `release_elastic_ip` | 400 |
| **5** | [`05_guardrails_rollback_iam.md`](modules/05_guardrails_rollback_iam.md) | Cross-Asset Guardrails & Governance | Rollbacks, zero-wildcard IAM, HMAC signing, quarantine | 650 |
| **6** | [`06_mcp_operational_runbooks.md`](modules/06_mcp_operational_runbooks.md) | MCP Agent Runbooks | `finops_waste_audit_runbook`, `remediation_rollback_procedure` | N/A |

---

## 3. Path-Safe Loading & Runtime Invariants

- All prompt artifacts under `PROMPTS_DIR` (`prompts/`) are loaded via `load_prompt_file()` with `Path.resolve().is_relative_to(prompts_dir.resolve())` and explicit `encoding="utf-8"`.
- Deterministic FinOps floors (EC2 RAM `> 65.0%` abort, S3 avg object size `< 128.0 KB` disqualify, `reserved`/`savings_plan` `$0.00` bill savings, and `projected_monthly_savings_usd <= current_monthly_spend_usd`) are enforced in Python via `GuardrailEngine.reconcile_with_telemetry()` regardless of LLM output.
