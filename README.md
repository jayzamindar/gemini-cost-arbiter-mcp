# 🛸 Gemini Autonomous Cloud-Cost Arbiter (`gemini-cost-arbiter-mcp`)

[![Continuous Integration](https://github.com/jayzamindar/gemini-cost-arbiter-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/jayzamindar/gemini-cost-arbiter-mcp/actions)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-JSON--RPC%202.0-orange.svg)](https://modelcontextprotocol.io/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.10%2B-green.svg)](https://docs.pydantic.dev/)
[![Docker Image Size](https://img.shields.io/badge/docker-65.5MB-brightgreen.svg)](#-docker-packaging--local-execution)
[![AWS Free Tier](https://img.shields.io/badge/AWS-100%25%20Free%20Tier-success.svg)](deploy/aws-free-tier/)
[![Tests Passing](https://img.shields.io/badge/tests-55%2F55%20passing-brightgreen.svg)](#3-run-the-automated-test-suite)

An enterprise-grade FinOps intelligence engine and **Model Context Protocol (MCP)** server. The arbiter continuously ingests multi-dimensional cloud utilization telemetry across AWS enterprise infrastructure (**EC2 compute, RDS databases, S3 storage, detached EBS volumes, and unassociated Elastic IPs**), detects systemic capacity and financial waste, and leverages **Google Gemini 3.8 Flash High** with configurable reasoning thinking budgets (and secondary multi-model fallback) to synthesize deterministic, schema-governed remediation execution payloads.

---

## 💡 Problem & Business Impact

### The Enterprise Cloud FinOps Dilemma
Modern engineering organizations routinely waste **30% to 55% of their total AWS infrastructure budget** on unmonitored over-provisioning and zombie resources:
* **Severely Oversized Compute:** Production instances running at `< 5%` average CPU utilization while incurring high 16-core hourly on-demand rates ($500–$2,000+/month per node).
* **Orphaned Storage & Idle Leaks:** Unattached EBS volumes persisting indefinitely after EC2 termination, unassociated Elastic IPs accumulating hourly AWS idle penalty fees, and terabytes of inactive objects trapped in high-cost S3 Standard storage.
* **Alert Fatigue & Operational Paralysis:** Existing monitoring tools (CloudWatch, AWS Cost Explorer) flag millions of dollars in potential waste, but SRE teams lack the engineering bandwidth to manually author change requests, verify memory thresholds, and write surgical rollback runbooks.

### The Danger of Unguarded AI Agents
Delegating infrastructure remediation directly to autonomous AI agents or unconstrained LLMs introduces existential production risks:
* **Hallucinated IAM Overprivilege:** LLMs frequently hallucinate broad wildcard policies (`"Action": "*", "Resource": "*"`), violating Zero Trust security principles.
* **Catastrophic Outages (OOM & State Loss):** Naive rightsizing algorithms downsize instances solely based on low CPU, causing immediate Out-Of-Memory (OOM) crashes on memory-intensive caches and database workloads.
* **Irreversible Termination:** Unguarded models terminate live instances or delete storage without automated pre-change snapshots or canary health probes.

### The Solution: Deterministic Guardrails Meet Deep Cognitive Reasoning
The **Gemini Autonomous Cloud-Cost Arbiter (`gemini-cost-arbiter-mcp`)** solves this challenge by strictly decoupling AI cognitive analysis from execution authority:
1. **Gemini 3.8 Flash High with Thinking Budget:** Conducts multi-dimensional telemetry reasoning, balancing workload peaks, IOPS ceilings, and storage lifecycle economics.
2. **Deterministic Python Guardrails:** The reasoner never directly touches cloud infrastructure or synthesizes executable privileges. Execution commands (`aws_cli`, `rollback`) and least-privilege IAM statements are deterministically compiled in Python, strictly eliminating wildcard permissions.
3. **Calibrated Safety Risk Scoring (1–5) & Quarantine:** High-risk actions ($\ge 3$) strictly require automated pre-change snapshots and rollback procedures. If mitigations are absent, the action is automatically quarantined (`quarantined=True`) pending human SRE sign-off.
4. **Cryptographic Integrity:** Every generated remediation plan is sealed with a full-payload HMAC-SHA256 signature (`plan_signature`), preventing tampering in transit across agent networks.
5. **Zero-Downtime Reliability:** An internal deterministic SRE heuristic engine serves as an automatic offline fallback, ensuring 100% availability even during external LLM outages or API rate limits.

---

## 🏗️ System Architecture Flow

```text
  AWS Infrastructure Telemetry
  (EC2 Compute, RDS Databases, S3 Storage, Orphan EBS, Idle EIPs)
                       │
                       ▼
  ┌─────────────────────────────────────────┐
  │       Prompt Injection Sanitizer        │  ◄── Strips regex injection attacks & prompt leaks
  └────────────────────┬────────────────────┘
                       │
                       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                   Dual-Engine Reasoning Core                    │
  │  ┌───────────────────────────┐      ┌────────────────────────┐  │
  │  │   Gemini 3.8 Flash High   │ ───► │  OpenRouter Fallback   │  │
  │  │   (Thinking Budget: 2048) │ 429  │  (Qwen 2.5 Coder 32B)  │  │
  │  └─────────────┬─────────────┘      └────────────┬───────────┘  │
  │                │                                 │              │
  │                └────────────────┬────────────────┘              │
  │                                 ▼ API Outage / Rate Limit       │
  │                  ┌─────────────────────────────┐                │
  │                  │  Deterministic SRE Engine   │                │
  │                  │  (100% Offline Rule Sets)   │                │
  │                  └──────────────┬──────────────┘                │
  └─────────────────────────────────┼───────────────────────────────┘
                                    │ Structured Pydantic Output
                                    ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                Deterministic Security Guardrails                │
  │  • Real AWS Pricing Catalog Differential: (Rate * 730 hrs)      │
  │  • FinOps Memory Floor Protection: RAM > 65% aborts downsize    │
  │  • S3 Intelligent-Tiering Floor: Objects < 128 KB excluded      │
  │  • Least-Privilege IAM Policy Synthesis: Zero wildcard '*'      │
  │  • Deterministic AWS CLI & Automated Rollback Script Gen        │
  │  • Calibrated Safety Scoring (1-5) & Quarantine Gate (>= 3)     │
  │  • Cryptographic HMAC-SHA256 Canonical Plan Digest & Signature  │
  └─────────────────────────────────┬───────────────────────────────┘
                                    │ Sealed Remediation Plan
                                    ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                        Egress & Transports                      │
  │  • Model Context Protocol (MCP) stdio Transport (Local Agents)  │
  │  • Model Context Protocol (MCP) SSE Transport (FastAPI, Docker) │
  │  • Persistent SQLite FinOps Audit Ledger (Survives Restarts)    │
  └─────────────────────────────────────────────────────────────────┘
```

---

## 🔬 Concrete Example: Telemetry Input ➔ Guardrailed Output

### 1. Ingested Telemetry (AWS CloudWatch Sample)
An underutilized production `m5.4xlarge` EC2 instance averaging `3.2%` CPU utilization:

```json
{
  "instance_id": "i-0a8b9c7d6e5f4a3b2",
  "instance_type": "m5.4xlarge",
  "cpu_utilization_avg": 3.2,
  "cpu_utilization_max": 8.4,
  "memory_utilization_avg": 28.4,
  "current_monthly_spend_usd": 560.64,
  "tags": {
    "Environment": "Production",
    "Service": "order-processing",
    "Owner": "checkout-team"
  }
}
```

### 2. Validated Remediation Output (`RemediationActionItem`)
The engine reasons over the memory floor (`28.4% < 65%`), looks up standard AWS on-demand rates (`$0.768` ➔ `$0.192`/hr), calculates exact catalog savings (`$420.48/mo`), assigns `safety_risk_score: 4` (Production), mandates system mitigations, and deterministically generates scoped IAM and CLI payloads:

```json
{
  "resource_id": "i-0a8b9c7d6e5f4a3b2",
  "resource_type": "EC2",
  "action_type": "rightsize_instance",
  "target_configuration": "m5.xlarge",
  "current_monthly_spend_usd": 560.64,
  "projected_monthly_spend_usd": 140.16,
  "projected_monthly_savings_usd": 420.48,
  "safety_risk_score": 4,
  "quarantined": false,
  "reasoning_rationale": "Sustained CPU average of 3.2% (peak 8.4%) and memory average of 28.4% indicates substantial over-provisioning. Memory floor is well below the 65% safety ceiling. Downsizing to m5.xlarge maintains adequate headroom while reducing compute overhead by 75.0%.",
  "system_mitigations": [
    "Create pre-execution AMI backup snapshot",
    "Execute change during approved off-peak maintenance window",
    "Execute automated canary health check probe post-resize",
    "Verify CloudWatch error rate and latency metrics"
  ],
  "execution_payload": {
    "aws_cli": "aws ec2 modify-instance-attribute --instance-id i-0a8b9c7d6e5f4a3b2 --instance-type m5.xlarge",
    "rollback": {
      "strategy": "revert_instance_type",
      "command": "aws ec2 modify-instance-attribute --instance-id i-0a8b9c7d6e5f4a3b2 --instance-type m5.4xlarge"
    },
    "iam_policy": {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "ArbiterRemediationEC2",
          "Effect": "Allow",
          "Action": [
            "ec2:DescribeInstances",
            "ec2:ModifyInstanceAttribute"
          ],
          "Resource": "arn:aws:ec2:*:*:instance/i-0a8b9c7d6e5f4a3b2"
        }
      ]
    }
  }
}
```

### 3. Cryptographic Sealing (`RemediationPlan`)
Top-level plan fields include canonical HMAC-SHA256 signatures ensuring execution commands cannot be tampered with in transit:
```json
{
  "plan_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "plan_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "plan_signature": "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069"
}
```

---

## ⚡ Key Architectural Capabilities

* **Decoupled Architecture (Antigravity Principles):** Zero runtime framework bloat (no LangChain or LlamaIndex runtime locks).
* **Dual-Engine Fault Isolation:** Primary AI reasoning path with automatic fallback to an internal **Deterministic SRE Heuristic Engine** for 100% service uptime during LLM outages or rate limits.
* **Gemini 3.8 Flash High with Thinking Budget:** Configurable algorithmic reasoning (`thinkingBudget: 1024-4096 tokens`) for deep trade-off analysis across workload peaks, IOPS throttling risks, and storage tier economics.
* **Multi-Model Secondary Fallback:** Support for secondary LLM inference (e.g. Qwen 2.5 Coder 32B via OpenRouter) when primary API quotas are exhausted.
* **Strict Zero-Hallucination Contracts:** 100% of LLM outputs constrained at token-generation time into Pydantic v2 models via Gemini native structured schema validation (`responseSchema`).
* **Real AWS Pricing Catalog Lookup:** EC2 right-sizing projected monthly savings are computed from standard AWS On-Demand hourly rate differentials multiplied by 730 operating hours/month from `config/instance_mappings.json` (replacing flat percentage multipliers).
* **Deterministic IAM & CLI Execution Synthesis:** Execution payloads (`iam_policy`, `aws_cli`, `rollback`) are deterministically synthesized in Python and unconditionally overwrite any LLM-hallucinated permissions, strictly eliminating wildcard `*` privileges.
* **Calibrated Safety Guardrails & Quarantine Pattern:** Actions are scored from 1 (negligible) to 5 (critical). Any action with Safety Score $\ge 3$ strictly requires automated system mitigations; if the reasoner omits mitigations, the action is quarantined (`quarantined=True`) pending human SRE review rather than auto-patched with generic templates.
* **FinOps Domain Guardrails:** EC2 memory floor (>65% RAM aborts downsizing to prevent OOM); S3 <128KB object size floor prevents Intelligent-Tiering fee traps; Reserved Instance and Savings Plan commitments are respected ($0 bill savings).
* **Timing-Safe Auth & Fail-Closed Protection:** SSE transport protected via constant-time `hmac.compare_digest()` authentication across Bearer tokens, `X-API-Key`, and `?apiKey=` query params, failing closed (HTTP 401) when unconfigured in production.
* **Cryptographic HMAC-SHA256 Plan Signing:** Deterministic SHA-256 digest and HMAC-SHA256 signature (`plan_signature`) computed over remediation actions using `PLAN_SIGNING_SECRET` to detect downstream tampering.
* **Stateful Audit Ledger Persistence:** Thread-safe in-memory metrics backed by durable SQLite storage (`--db-path`) restoring cumulative savings across server restarts.
* **Dual MCP Transports:** Full support for standard input/output (`stdio`) for local IDEs and desktop agents (Claude Desktop, Cursor, Antigravity) and Server-Sent Events (`SSE`) via FastAPI for containerized or network-hosted deployments.
* **Hierarchical PromptOps:** Modular prompt documents version-controlled under `prompts/` (Master System Prompt + 6 Domain Cognitive Modules).
* **Turnkey AWS Free Tier Packaging:** Zero-cost deployment blueprints for EC2 Free Tier (`t3.micro`/`t4g.small`) and AWS Lambda Serverless Containers.

---

## 🤖 Multi-Model AI Engineering & Adversarial Verification

To ensure enterprise-grade resilience and eliminate hidden edge-case vulnerabilities, `gemini-cost-arbiter-mcp` was developed and validated using a multi-model engineering and adversarial verification methodology:

### 1. Primary Builder & Reasoning Engine: Google Gemini 3.8 Flash High
* **Plan & Action Modes:** Formulated system architecture, Pydantic v2 domain schemas, the PromptOps hierarchy, and MCP protocol integration.
* **Constrained Egress:** Leveraged native Gemini `responseSchema` to guarantee schema compliance directly at token-generation time, preventing malformed JSON responses.
* **Thinking Budget:** Configured algorithmic reasoning tokens (`thinkingBudget: 2048`) to conduct multi-step trade-off analysis on complex infrastructure telemetry.

### 2. Adversarial Multi-Model Verification Panel
The system was cross-evaluated across frontier reasoning and code-specialized models (**DeepSeek R1**, **Qwen 2.5 Coder**, **Llama**, and **Cohere North**) to discover edge cases that single-model development overlooks:
* **Google C++ Protobuf `responseSchema` Allowlist Sanitization:** Discovered that the Gemini REST API compiles schemas into C++ Protobuf descriptors (`google.ai.generativelanguage.v1beta.Schema`), rejecting standard JSON-Schema draft-07 keywords (`minimum`, `maximum`, `$schema`, `title`, and uncollapsed `anyOf` with `null`). Built an explicit allowlist sanitizer in `clean_gemini_schema()` to guarantee zero HTTP 400 Bad Request errors.
* **AWS IAM ARN Specification Hardening:** Identified invalid shortcut ARNs (e.g. `arn:aws:ec2:*:i-xxx`) and replaced them with standard AWS IAM ARNs (`arn:aws:ec2:*:*:instance/{id}`, `arn:aws:rds:*:*:db:{id}`, `arn:aws:s3:::{id}`).
* **Full-Payload Cryptographic Sealing:** Audited HMAC signing coverage to ensure the entire canonical plan payload (including `execution_payload`, `system_mitigations`, and top-level totals) is cryptographically signed, preventing command tampering.
* **Fallback Fence & `<think>` Token Sanitization:** Handled reasoning model fence artifacts (such as DeepSeek `<think>` tokens) in secondary fallback responses to prevent unparsed tokens from entering downstream schema parsers.

---

## 🔌 Plug-and-Play MCP Client Configuration

Connect `gemini-cost-arbiter-mcp` to your favorite MCP client in seconds:

### Claude Desktop (`claude_desktop_config.json`)
Add the following block to your configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "gemini-cost-arbiter": {
      "command": "python",
      "args": [
        "-m",
        "gemini_cost_arbiter",
        "run-mcp",
        "--transport",
        "stdio",
        "--db-path",
        "./data/finops.db"
      ],
      "env": {
        "GEMINI_API_KEY": "your_gemini_api_key_here",
        "PLAN_SIGNING_SECRET": "your_secure_signing_secret_here"
      }
    }
  }
}
```

### Cursor IDE (`.cursor/mcp.json` or Settings ➔ MCP)
```json
{
  "mcpServers": {
    "gemini-cost-arbiter": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/gemini-cost-arbiter-mcp",
        "run",
        "gemini-cost-arbiter",
        "run-mcp",
        "--transport",
        "stdio",
        "--db-path",
        "./data/finops.db"
      ],
      "env": {
        "GEMINI_API_KEY": "your_gemini_api_key_here",
        "PLAN_SIGNING_SECRET": "your_secure_signing_secret_here"
      }
    }
  }
}
```

---

## 🚀 Quick Start & Installation

### 1. Prerequisites & Environment Setup
Verify that your machine has Python 3.13+ installed locally:

```bash
# Clone the repository
git clone https://github.com/jayzamindar/gemini-cost-arbiter-mcp.git
cd gemini-cost-arbiter-mcp

# Initialize virtual environment
python -m venv .venv

# Activate on Windows PowerShell:
.venv\Scripts\activate
# Activate on Linux/macOS:
source .venv/bin/activate

# Install in editable mode with development & testing dependencies
pip install setuptools
pip install -e ".[dev,test]"
```

### 2. Configure Credentials
Copy `.env.example` to `.env` and configure your credentials:

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=your_gemini_api_token_here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
DEFAULT_MODEL=gemini-3.8-flash-high
THINKING_BUDGET=2048

# Optional secondary fallback (OpenRouter)
OPENROUTER_API_KEY=your_optional_openrouter_api_key_here

# Persistent SQLite FinOps ledger path
DB_PATH=./data/finops.db

# Cryptographic Plan Signing Secret
PLAN_SIGNING_SECRET=your_secure_random_hex_key_here
```

### 3. Run the Automated Test Suite
Execute the **55-test** verification suite validating schema integrity, contract boundaries, MCP handshakes, CLI runners, security guardrails, SQLite persistence, real AWS pricing rates, deterministic templating, timing-safe fail-closed auth, and fallback loops:

```bash
python -m pytest -v
```

---

## 🖥️ Command Line Interface (CLI)

The package installs the `gemini-cost-arbiter` executable:

```bash
# View all available CLI commands
gemini-cost-arbiter --help

# 1. Run MCP Server in Standard I/O mode (for Claude Desktop / Cursor / Antigravity)
gemini-cost-arbiter run-mcp --transport stdio --db-path ./data/finops.db

# 2. Run MCP Server in SSE mode (for remote gateways or Docker)
gemini-cost-arbiter run-mcp --transport sse --host 0.0.0.0 --port 8000 --db-path ./data/finops.db

# 3. Analyze a telemetry JSON file directly
gemini-cost-arbiter analyze -f path/to/telemetry.json

# 4. Generate a remediation plan with risk filtering and simulation dry-run
gemini-cost-arbiter plan -f path/to/telemetry.json --max-risk 3 --dry-run

# 5. Display cumulative FinOps audit ledger metrics
gemini-cost-arbiter audit --db-path ./data/finops.db
```

---

## 🐳 Docker Packaging & Local Execution

The project includes an enterprise-hardened, multi-stage, non-root Dockerfile resulting in an ultra-lean **65.5 MB** runtime image:

```bash
# Build multi-stage production image
docker build -t gemini-cost-arbiter-mcp:latest .

# Run with local volume persistence for SQLite ledger
docker run -d --rm -p 8000:8000 \
    -v $(pwd)/data:/app/data \
    -e GEMINI_API_KEY=your_api_key \
    --name arbiter-server \
    gemini-cost-arbiter-mcp:latest

# Validate live health probe
curl http://localhost:8000/health
# Output: {"status":"healthy","service":"gemini-cost-arbiter-mcp"}

# Or launch via Docker Compose:
docker compose up -d
```

---

## ☁️ Zero-Cost AWS Free Tier Deployment

Turnkey blueprints for deploying the server at **$0.00/month** on AWS Free Tier are located in [deploy/aws-free-tier/](deploy/aws-free-tier/):
* **Option 1 (EC2 Free Tier Host):** Automated setup script [deploy-ec2.sh](deploy/aws-free-tier/deploy-ec2.sh) for `t3.micro` or `t4g.small` instances with memory-capped Docker Compose ([docker-compose.prod.yml](deploy/aws-free-tier/docker-compose.prod.yml)).
* **Option 2 (Serverless Lambda Container):** Serverless container via [lambda-adapter/Dockerfile](deploy/aws-free-tier/lambda-adapter/Dockerfile) using the AWS Lambda Web Adapter with direct Function URL (1M free requests/month).

See [deploy/aws-free-tier/README.md](deploy/aws-free-tier/README.md) for step-by-step instructions.

---

## 🛡️ Remediation Safety Risk Scoring Matrix

| Score | Level | Description | Example Actions | Mandatory Mitigations Required |
|:---:|:---|:---|:---|:---|
| **1** | Negligible | Metadata or automated storage tiering; completely non-disruptive | S3 Intelligent-Tiering transition, Lifecycle rule application | None |
| **2** | Low | Reversible cleanup with existing snapshot validation | Delete unattached EBS volume older than 30 days (with snapshot), release idle EIP | Verify volume age, verify tag != prod |
| **3** | Moderate | Modifying compute/database state on non-production tiers | Dev/Staging EC2 right-sizing, Dev RDS stop, EBS delete without snapshot | Automated pre-change backup, scheduled window, rollback script |
| **4** | High | Production compute resizing or database cluster changes | Prod EC2 downsizing, RDS instance class change | Pre-execution AMI snapshot, canary probe, automated rollback script, least-privilege IAM |
| **5** | Critical | Irreversible termination or permanent storage drop | Terminating instances, deleting RDS database instances | Dual-approval gate, forensic snapshot, 7-day retention grace |

---

## 🔌 Model Context Protocol (MCP) Interface Catalog

The server implements standard JSON-RPC 2.0 communication over `stdio` and `SSE`:

### 1. Tools Catalog (`tools/list`, `tools/call`)
| Tool Name | Parameters | Returns | Description |
|:---|:---|:---|:---|
| `analyze_infrastructure_waste` | `telemetry: TelemetryBatch` | `WasteAnalysisSummary` | Scans all resources, calculates monthly dollar waste, and identifies top optimization candidates across EC2, RDS, S3, EBS, and EIP. |
| `generate_remediation_plan` | `telemetry: TelemetryBatch`, `max_acceptable_risk: Optional[int]`, `dry_run: bool` | `RemediationPlan` | Produces an actionable, risk-scored remediation plan complete with execution commands, automated rollbacks, least-privilege IAM policies, and SHA-256 digest. |
| `get_finops_audit_summary` | None | `FinOpsAuditSummary` | Returns cumulative financial savings, total resources analyzed, and aggregated ledger statistics. |

### 2. Prompts Catalog (`prompts/list`, `prompts/get`)
* `finops_waste_audit_runbook`: Standardized SRE runbook guiding autonomous agents through structured waste inspection.
* `remediation_rollback_procedure`: Emergency rollback runbook with snapshot and CloudWatch verification steps.

### 3. Resources Catalog (`resources/list`, `resources/read`)
* `finops://audit/ledger`: Real-time read-only JSON stream of cumulative FinOps savings metrics.
* `finops://policies/risk-matrix`: Live read-only safety scoring guidelines and mandatory mitigation rules.
* `finops://config/instance-mappings`: Active AWS EC2 rightsizing and Graviton modernization catalog.

---

## 📁 Repository Structure

```
gemini-cost-arbiter-mcp/
├── .dockerignore                    # Docker build context exclusions
├── .env.example                     # Environment template without secrets
├── .gitignore                       # Production git ignore rules
├── .github/workflows/test.yml       # Multi-version CI workflow (Python 3.13, 3.14)
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
├── Dockerfile                       # Multi-stage, non-root, security-hardened container (65.5MB)
├── docker-compose.yml               # Local compose stack with persistent SQLite volume
├── gemini.md                        # Master AI Agent & Gemini development guide
├── PLAN.md                          # Master step-by-step production elevation checklist
├── Repo_Baseline_AuditReport.md     # 10-dimension forensic baseline audit report (Grade: 100/100)
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
├── src/gemini_cost_arbiter/         # Modular production package
│   ├── cli.py                       # Click CLI interface (run-mcp, analyze, plan, audit)
│   ├── config.py                    # Pydantic Settings configuration (SQLite, auth)
│   ├── observability.py             # OpenTelemetry distributed tracing helper
│   ├── models/                      # Pydantic v2 data models (EC2, RDS, S3, EBS, EIP, Plan)
│   ├── reasoner/                    # Gemini 3.8 Flash High client (thinking budget) & OpenRouter
│   ├── heuristics/                  # Deterministic SRE fallback engine (EC2, RDS, S3, EBS, EIP)
│   ├── guardrails/                  # Safety score validation, rollbacks, and least-privilege IAM
│   ├── ledger/                      # Stateful FinOps audit tracking with SQLite persistence
│   └── mcp/                         # MCP protocol dispatcher & servers (stdio and SSE)
├── app/                             # Zero-breaking-change backward compatibility shims
└── tests/                           # 55-test verification suite (100% passing)
```

---

## 📄 License
Licensed under the Apache License, Version 2.0.
