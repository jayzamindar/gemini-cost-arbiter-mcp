# PromptOps Engineering Architecture & Catalog

## 1. Overview & Best Practice Tenets
In enterprise-grade Autonomous AI Systems, prompts are **not casual string concatenations**; they are **version-controlled, schema-bound software artifacts**. 

The **Gemini Autonomous Cloud-Cost Arbiter (`gemini-cost-arbiter-mcp`)** follows the **Hierarchical PromptOps Architecture**:

```
prompts/
├── README.md                               # PromptOps Catalog & Governance Guide (This file)
├── modular_prompt.md                       # Unified PromptOps Registry indexing Tier-0 & Modules 01-06
├── master_system_prompt.md                 # Tier-0 Master System Prompt & Global Ontology
└── modules/                                # Specialized FinOps Cognitive Modules
    ├── 01_ec2_compute_reasoning.md         # EC2 CPU p95/avg, RAM, and Graviton modernization
    ├── 02_rds_database_reasoning.md        # RDS connection pooling, Multi-AZ & Aurora rightsizing
    ├── 03_s3_storage_tiering.md            # S3 Intelligent-Tiering & Glacier lifecycle policies
    ├── 04_ebs_eip_reclamation.md           # Unattached EBS volumes and unassociated Elastic IPs
    ├── 05_guardrails_rollback_iam.md       # Calibrated risk scoring, rollbacks & least-privilege IAM
    └── 06_mcp_operational_runbooks.md      # MCP prompt templates for autonomous SRE agents
```

---

## 2. Prompt Hierarchy & Responsibility Matrix

| Artifact | Scope & Responsibility | Target Model | Max Token Budget | Temperature |
|:---|:---|:---|:---:|:---:|
| `master_system_prompt.md` | Global SRE persona, FinOps domain axioms, anti-hallucination rules, safety thresholds | Gemini 3.8 Flash High / Qwen 2.5 Coder 32B | 800 tokens | 0.1 |
| `01_ec2_compute_reasoning.md` | Rules for compute underutilization, Graviton architecture, burstable T3/T4g credits | Gemini 3.8 Flash High | 600 tokens | 0.1 |
| `02_rds_database_reasoning.md` | Idle database detection, connection metrics, Multi-AZ failover risk evaluation | Gemini 3.8 Flash High | 500 tokens | 0.1 |
| `03_s3_storage_tiering.md` | Storage class lifecycle analysis, retrieval overhead calculations, Glacier archives | Gemini 3.8 Flash High | 450 tokens | 0.1 |
| `04_ebs_eip_reclamation.md` | Detached volume retention rules (30d threshold), idle Elastic IP cost leaks | Gemini 3.8 Flash High | 400 tokens | 0.1 |
| `05_guardrails_rollback_iam.md` | Generation of deterministic rollback commands and least-privilege IAM statements | Gemini 3.8 Flash High | 650 tokens | 0.1 |
| `06_mcp_operational_runbooks.md` | Standard SRE runbooks exposed via MCP `prompts/list` and `prompts/get` | Autonomous MCP Client / IDE | N/A (Runbook) | N/A |

---

## 3. Strict Anti-Hallucination Protocol (The 3 Pillars)

To guarantee 100% zero-hallucination compliance across all prompt evaluations (`DEFAULT_MODEL=gemini-3.8-flash-high`):
1. **Schema-Constrained Decoding (`clean_gemini_schema()`):** Prompts are coupled with `generationConfig.responseSchema = clean_gemini_schema(RemediationPlan.model_json_schema())`, which dereferences `$defs`/`$ref`, collapses `anyOf` unions, excludes `execution_payload`, and strips unsupported JSON-Schema keywords for Gemini C++ Protobuf compliance.
2. **Catalog-Anchored Reality:** The prompt instructs the model to only recommend AWS instance types present in `config/instance_mappings.json` (indexed via [`modular_prompt.md`](modular_prompt.md)).
3. **Deterministic Python Arithmetic:** Mathematical calculations (spending, percentage savings, and cost deltas) are validated and reconciled by Python business logic (`GuardrailEngine.reconcile_with_telemetry()`)—never blindly trusted to LLM token prediction.
