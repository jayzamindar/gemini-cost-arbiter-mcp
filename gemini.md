# GEMINI.md: Autonomous Cloud-Cost Arbiter (`gemini-cost-arbiter-mcp`)

## 1. Project Overview & Architectural Vision
The **Gemini Autonomous Cloud-Cost Arbiter (`gemini-cost-arbiter-mcp`)** is an enterprise-grade FinOps intelligence engine and Model Context Protocol (MCP) server. It continuously ingests multi-dimensional cloud utilization telemetry across AWS infrastructure (EC2 compute, RDS databases, S3 storage, EBS block storage, Elastic IPs), identifies systemic resource waste, and leverages **Google Gemini 3.8 Flash High** with configurable thinking budgets (and secondary multi-model fallback) to synthesize deterministic, schema-governed remediation execution payloads.

### Architectural Tenets (Antigravity Principles)
1. **Decoupled Architecture:** Zero runtime framework bloat (no heavy orchestrators like LangChain or LlamaIndex).
2. **Dual-Engine Fault Isolation:** Primary AI reasoning path with seamless automatic fallback to an internal **Deterministic SRE Heuristic Engine** for 100% service uptime during LLM outages or rate limits.
3. **Calibrated Safety Risk Scoring (Scale 1 to 5) & Quarantine Pattern:** Every proposed action is classified by operational risk; any action with Risk Score $\ge 3$ strictly requires non-empty automated system mitigations (pre-change snapshots, canary probes, rollback runbooks, and least-privilege IAM statements). If the reasoner omits mitigations, the action is quarantined (`quarantined=True`) pending human review.
4. **Deterministic IAM & CLI Execution Synthesis:** Execution payloads (`iam_policy`, `aws_cli`, `rollback`) are deterministically synthesized in Python and unconditionally overwrite any LLM-hallucinated permissions, strictly eliminating wildcard `*` privileges.
5. **Real AWS Pricing Catalog Lookup:** EC2 right-sizing projected monthly savings are computed from standard AWS On-Demand hourly rate differentials multiplied by 730 operating hours/month looked up from `config/instance_mappings.json`.
6. **FinOps Domain Guardrails:** EC2 memory floor (>65% RAM aborts downsizing to prevent OOM); S3 <128KB object size floor prevents Intelligent-Tiering fee traps; Reserved Instance and Savings Plan commitments are respected ($0 bill savings).
7. **Timing-Safe Auth & Fail-Closed Protection:** Constant-time `hmac.compare_digest()` authentication across Bearer tokens, `X-API-Key`, and `?apiKey=` query params; fails closed (HTTP 401) when unconfigured in production.
8. **Strict Zero-Hallucination Contracts:** Outputs are constrained at token-generation time into predictable Pydantic v2 data models via Gemini native structured schema validation (`responseSchema`).
9. **Dual MCP Transport:** Full support for standard input/output (`stdio`) for local IDEs and agents (Claude Desktop, Cursor, Antigravity) and Server-Sent Events (`SSE`) for containerized or remote agent gateways.
10. **Multi-Asset FinOps Coverage:** First-class telemetry evaluation for EC2 instances, RDS databases, S3 object storage, detached EBS volumes, and unassociated Elastic IPs.

---

## 2. Repository Layout & Target Directory Tree

```
gemini-cost-arbiter-mcp/
├── .dockerignore                    # Docker build context exclusions
├── .env.example                     # Environment template without secrets
├── .gitignore                       # Standardized git ignore rules
├── .github/
│   └── workflows/
│       └── test.yml                 # CI/CD: matrix testing (Python 3.13, 3.14)
├── config/
│   └── instance_mappings.json       # AWS EC2 rightsizing & Graviton modernization lookup catalog
├── deploy/
│   └── aws-free-tier/               # Turnkey AWS Free Tier deployment blueprints
│       ├── README.md                # Zero-cost AWS setup guide
│       ├── deploy-ec2.sh            # Automated EC2 t3.micro / t4g.small setup script
│       ├── docker-compose.prod.yml  # Production compose file with memory bounds (512M)
│       └── lambda-adapter/
│           └── Dockerfile           # Serverless container with AWS Lambda Web Adapter
├── docs/
│   ├── ARCHITECTURE.md              # System Architecture Document (C4 models & sequence flows)
│   ├── AWS_Deployment_Guide.md      # Turnkey AWS deployment guide (EC2, Lambda, IAM, SSM)
│   ├── PRD.md                       # Product Requirements Document
│   ├── Production_Readiness_Report.md # SRE Production Readiness Review (PRR) 8-pillar audit
│   ├── TRD.md                       # Technical Requirements Document
│   └── URD.md                       # User Requirements Document
├── Dockerfile                       # Multi-stage, non-root, security-hardened container
├── docker-compose.yml               # Local compose stack with persistent SQLite volume
├── gemini.md                        # Master project guide for Gemini & AI agents
├── PLAN.md                          # Master step-by-step production elevation checklist
├── Repo_Baseline_AuditReport.md     # 10-dimension forensic baseline audit report
├── prompts/
│   ├── README.md                    # PromptOps catalog & engineering guide
│   ├── master_system_prompt.md      # Tier-0 Master System Prompt & Global Ontology
│   ├── code_generation.txt          # Engineering prompt history
│   └── modules/                     # Specialized FinOps Cognitive Modules
│       ├── 01_ec2_compute_reasoning.md
│       ├── 02_rds_database_reasoning.md
│       ├── 03_s3_storage_tiering.md
│       ├── 04_ebs_eip_reclamation.md
│       ├── 05_guardrails_rollback_iam.md
│       └── 06_mcp_operational_runbooks.md
├── pyproject.toml                   # PEP 517/621 packaging, entrypoints, and test configuration
├── README.md                        # Project documentation and quickstart
├── src/
│   └── gemini_cost_arbiter/         # Modular core package
│       ├── __init__.py              # Package metadata and public exports
│       ├── __main__.py              # Allows `python -m gemini_cost_arbiter`
│       ├── cli.py                   # Click-based CLI entrypoints (analyze, plan, audit, run-mcp)
│       ├── config.py                # Pydantic-settings runtime configuration
│       ├── observability.py         # OpenTelemetry distributed tracing helper
│       ├── models/                  # Pydantic v2 data models
│       │   ├── __init__.py
│       │   ├── telemetry.py         # EC2, RDS, S3, EBS, EIP, and TelemetryBatch schemas
│       │   ├── remediation.py       # Actions, Plans, and Risk bounds with SHA-256 plan digest
│       │   └── audit.py             # FinOps ledger models
│       ├── reasoner/                # Upstream AI Reasoning
│       │   ├── __init__.py
│       │   ├── client.py            # Gemini 3.8 Flash High client (thinking budget & responseSchema)
│       │   ├── openrouter.py        # Multi-model secondary fallback client
│       │   └── prompt_compiler.py   # High-density token optimizer & prompt injection sanitizer
│       ├── heuristics/              # Rule-based fallback engine
│       │   ├── __init__.py
│       │   ├── ec2_rules.py         # EC2 underutilization heuristics (catalog loaded)
│       │   ├── rds_rules.py         # RDS idle connection heuristics
│       │   ├── s3_rules.py          # S3 infrequent access tiering heuristics
│       │   ├── ebs_rules.py         # Detached orphan EBS volume heuristics
│       │   └── eip_rules.py         # Unassociated Elastic IP heuristics
│       ├── guardrails/              # Safety policies
│       │   ├── __init__.py
│       │   └── risk_scorer.py       # Safety score validator, rollback builder, IAM policy generator
│       ├── ledger/                  # Stateful audit tracking
│       │   ├── __init__.py
│       │   └── store.py             # Cumulative savings ledger with SQLite persistence
│       └── mcp/                     # Model Context Protocol
│           ├── __init__.py
│           ├── server_stdio.py      # stdio JSON-RPC 2.0 loop
│           └── server_sse.py        # FastAPI/Starlette SSE transport server
├── app/                             # Backward-compatibility shim layer
│   ├── __init__.py
│   ├── engine.py                    # Re-exports GeminiCostArbiterEngine
│   └── schemas.py                   # Re-exports all Pydantic contracts
└── tests/                           # Modular test suite (55 tests, 100% passing)
    ├── __init__.py
    ├── conftest.py                  # Pytest fixtures and sample telemetry
    ├── test_arbiter.py              # Ingestion schemas & MCP baseline tests
    ├── test_cli.py                  # CLI command execution tests
    ├── test_guardrails_security.py  # Anti-injection, IAM policy, SHA-256 digest, EBS/EIP tests
    ├── test_mcp_prompts_resources.py# MCP Prompts & Resources lifecycle tests
    ├── test_openrouter.py           # Secondary fallback client tests
    ├── test_phase9_hardening.py     # SSE auth, HMAC-SHA256, memory floor, S3 <128KB, quarantine tests
    ├── test_sqlite_ledger.py        # SQLite persistence across restarts tests
    ├── test_sse.py                  # FastAPI SSE transport tests
    └── test_thinking_budget.py      # Gemini thinking budget payload tests
```

---

## 3. Core Developer & Operational Commands

### Environment Setup
```bash
# Initialize virtual environment
python -m venv .venv
# Windows PowerShell
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# Install package in editable mode with development & testing dependencies
pip install setuptools
pip install -e ".[dev,test]"
```

### Running the Test Suite
```bash
# Run full automated test suite with verbose output
python -m pytest -v

# Run with coverage report
python -m pytest -v --cov=gemini_cost_arbiter tests/
```

### Starting the MCP Server
```bash
# 1. Standard Input/Output (stdio) Transport (for Claude Desktop, Antigravity, Cursor)
gemini-cost-arbiter run-mcp --transport stdio

# Alternatively with persistent SQLite database:
gemini-cost-arbiter run-mcp --transport stdio --db-path ./data/finops.db

# 2. Server-Sent Events (SSE) Transport (for remote gateways or Docker)
gemini-cost-arbiter run-mcp --transport sse --host 0.0.0.0 --port 8000 --db-path ./data/finops.db
```

### CLI Utilities
```bash
# View CLI help
gemini-cost-arbiter --help

# Run one-off waste analysis against a JSON telemetry file
gemini-cost-arbiter analyze -f telemetry_sample.json

# Generate risk-scored remediation plan (with simulation dry-run flag)
gemini-cost-arbiter plan -f telemetry_sample.json --max-risk 3 --dry-run

# View cumulative FinOps audit ledger
gemini-cost-arbiter audit --db-path ./data/finops.db
```

### Docker Container Operations
```bash
# Build production multi-stage image
docker build -t gemini-cost-arbiter-mcp:latest .

# Launch local stack with volume-mounted SQLite persistence
docker compose up -d

# Verify container health
curl http://localhost:8000/health
```

---

## 4. Remediation Safety Risk Scoring Matrix

| Score | Level | Description | Example Actions | Mandatory Mitigations Required |
|:---:|:---|:---|:---|:---|
| **1** | Negligible | Metadata or automated storage tiering; completely non-disruptive | S3 Intelligent-Tiering transition, Lifecycle rule application | None |
| **2** | Low | Reversible cleanup with existing snapshot validation | Delete unattached EBS volume older than 30 days (with snapshot), release idle EIP | Verify volume age, verify tag != prod |
| **3** | Moderate | Modifying compute/database state on non-production tiers | Dev/Staging EC2 right-sizing, Dev RDS stop, EBS delete without snapshot | Automated pre-change backup, scheduled window, rollback script |
| **4** | High | Production compute resizing or database cluster changes | Prod EC2 downsizing, RDS instance class change | Pre-execution AMI snapshot, canary probe, automated rollback script, least-privilege IAM |
| **5** | Critical | Irreversible termination or permanent storage drop | Terminating instances, deleting RDS database instances | Dual-approval gate, forensic snapshot, 7-day retention grace |

---

## 5. Model Context Protocol (MCP) Interface Catalog

### 5.1 MCP Tools
1. **`analyze_infrastructure_waste`**: Ingests multi-dimensional telemetry (EC2, RDS, S3, EBS, EIP) and quantifies dollar waste and savings percentage.
2. **`generate_remediation_plan`**: Produces concrete action items with execution payloads (`aws_cli`, `terraform`), automated rollback payloads, least-privilege IAM statements, and SHA-256 digest.
3. **`get_finops_audit_summary`**: Returns cumulative financial metrics across evaluated batches.

### 5.2 MCP Prompts
1. **`finops_waste_audit_runbook`**: Standardized SRE runbook guiding autonomous agents through structured waste inspection.
2. **`remediation_rollback_procedure`**: Emergency rollback runbook with snapshot and CloudWatch verification steps.

### 5.3 MCP Resources
1. **`finops://audit/ledger`**: Real-time read-only JSON stream of cumulative FinOps savings metrics.
2. **`policies/risk-matrix`**: Live read-only safety scoring guidelines and mandatory mitigation rules.
3. **`config/instance-mappings`**: Active AWS EC2 rightsizing and Graviton modernization catalog.

---

## 6. Gemini 3.8 Flash High Integration Specifics
When calling Google Gemini:
* **Endpoint:** `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-high:generateContent`
* **Authentication:** API key passed via query parameter or `x-goog-api-key` header.
* **Thinking Budget:** Configured via `thinkingConfig.thinkingBudget` (default: 2048 tokens).
* **Constrained Output Egress:** Guaranteed schema compliance via `generationConfig.responseMimeType = "application/json"` and `generationConfig.responseSchema = RemediationPlan.model_json_schema()`.
* **Resilience:** Wrapped in exponential backoff retry with jitter for HTTP 429 / 503 before switching to deterministic heuristics.
* **Anti-Injection:** Freeform telemetry tags are sanitized against regex injection patterns before prompt compilation.
