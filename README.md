### 🛸 Engineered via Antigravity Principles
* **Decoupled Architecture:** Zero runtime framework dependencies (no heavy AI orchestrators like LangChain or LlamaIndex). Minimizes context payload bloat and prevents third-party dependency locks.
* **Dual-Engine Fault Isolation:** Built with an inline resilience wrapper. If external API rates are exhausted or standard 503 gateway dropped packets are encountered, the engine smoothly falls back to an internal **Deterministic SRE Heuristic Engine**, preserving infrastructure validation workflows with 100% availability.
* **Strict Runtime Contracts:** Stochastic LLM outputs are forced into predictable JSON objects via strict Pydantic parsing. If any response violates field typings or bounds, the data payload is caught and handled safely before execution.

---

## 💻 Core Functional Capabilities

1. **Multi-Asset Waste Discovery:** Ingests granular metadata models for computing layers (`EC2Metrics`), state data engines (`RDSMetrics`), and object file storage systems (`S3Metrics`).
2. **Dynamic Risk-Filtered Planning:** Generates actionable remediation items bound to strict safety metrics (Scores 1-5). Supports runtime thresholding filters (`risk_filter`) to drop destructive actions from automated cycles.
3. **Stateful Audit Logging:** Tracks optimization trends across active execution cycles via an in-memory transactional ledger tracking real-time compound dollar savings.
4. **Model Context Protocol Routing:** Implements standard JSON-RPC 2.0 RPC request processing matching the modern standard for AI-agent tool discovery (`tools/list` and `tools/call`).

---

## ⚡ Quick Start & Core Testing Instructions

### 1. Prerequisites & Environment Setup
Verify that your machine has Python 3.13+ installed locally:

```bash
# Clone the repository
git clone https://github.com
cd gemini-cost-arbiter-mcp

# Initialize virtual isolation boundary
python -m venv .venv
source .venv/bin/activate  # On Windows PowerShell: .venv\Scripts\activate

# Install strictly locked production dependencies
pip install -r requirements.txt
```

### 2. Configure Credentials
Create a `.env` file in the root workspace directory to bind your upstream execution connections:

```env
OPENROUTER_API_KEY=your_openrouter_api_token_here
GEMINI_API_KEY=your_optional_gemini_token_here
```

### 3. Run the 21-Test Verification Suite
The repository includes a comprehensive unit and integration suite validating schema integrity, contract boundaries, MCP handshakes, and fallback loops. Run this command inside your terminal:

```bash
python -m pytest -v tests/test_arbiter.py
```

---

## 🤖 AI Lifecycle Prompt Registry

To maintain auditability and demonstrate advanced AI-assisted software engineering practices to hiring managers, the system layout keeps its underlying prompt blueprints mapped into `prompts/code_generation.txt`. 

### System Core Generation Prompt
```text
System Paradigm: Antigravity Architecture, Python 3.13+, AsyncIO, Pydantic v2.
Role: Senior AI SRE Specialist & Elite Portfolio Tutor.
Objective: Build a highly decoupled, asynchronous Model Context Protocol (MCP) server gateway that intercepts infrastructure telemetry, converts payloads into JSON arrays, maps them to an OpenAI-compatible completion loop running Qwen 2.5 Coder via OpenRouter, and enforces a strict structural Pydantic validation wrapper output contract with zero boilerplate code. Include a fallback deterministic heuristic safety calculation loop to prevent system drops if API quotas break.
```

---

## 🚀 Enterprise CI/CD Pipeline Configuration

The pipeline validates software changes automatically on every repository merge action, ensuring that all 21 tests pass successfully before release.

Create a workflow file at `.github/workflows/test.yml` with this definition:

```yaml
name: Continuous Integration Suite

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  validate-and-test:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout Source Code Repository
      uses: actions/checkout@v4

    - name: Configure Python 3.13 Runtime
      uses: actions/setup-python@v5
      with:
        python-version: '3.13'
        cache: 'pip'

    - name: Install Architecture Dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Execute Full 21-Test Automated Integration Suite
      env:
        OPENROUTER_API_KEY: "mock_ci_token_bypass"
      run: |
        python -m pytest -v tests/test_arbiter.py
```