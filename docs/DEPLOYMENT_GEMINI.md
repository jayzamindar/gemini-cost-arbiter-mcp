# Google Cloud Run & Gemini MCP Packaging Guide (`docs/DEPLOYMENT_GEMINI.md`)

**Target Environment:** Google Cloud Run (SSE Transport) + Google AI Studio / Gemini API + Local/Remote MCP Clients  
**Governance:** [`GEMINI.md`](../GEMINI.md) | [`Enterprise_Blueprint.md`](../Enterprise_Blueprint.md)  
**Assets:** [`deploy/gemini/cloudbuild.yaml`](../deploy/gemini/cloudbuild.yaml), [`deploy/gemini/service.yaml`](../deploy/gemini/service.yaml), [`deploy/gemini/mcp_configs.example.json`](../deploy/gemini/mcp_configs.example.json)

---

## 1. Google AI Studio / Gemini API Configuration

1. Obtain an API key from Google AI Studio and export `GEMINI_API_KEY`.
2. Configure runtime defaults per [`GEMINI.md`](../GEMINI.md):
   - `DEFAULT_MODEL=gemini-3.8-flash-high`
   - `THINKING_BUDGET=2048`
   - `MAX_OUTPUT_TOKENS=8192`
   - `MAX_SESSION_TOKEN_BUDGET=500000`
   - `DAILY_API_COST_LIMIT_USD=10.00`
3. Verify locally with `sample_telemetry.json`:

```bash
gemini-cost-arbiter analyze -f sample_telemetry.json
gemini-cost-arbiter plan -f sample_telemetry.json --max-risk 3 --dry-run
```

---

## 2. Google Cloud Run SSE Deployment

### Step 1: Store Secrets in Secret Manager

```bash
printf "%s" "<YOUR_GEMINI_API_KEY>" | gcloud secrets create gemini-api-key --data-file=-
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create mcp-api-key --data-file=-
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create plan-signing-secret --data-file=-
```

### Step 2: Build with Cloud Build & Deploy Declarative Service

```bash
gcloud builds submit --config deploy/gemini/cloudbuild.yaml .
gcloud run services replace deploy/gemini/service.yaml --region us-central1
```

### Step 3: Verify Cloud Run Health Endpoint

```bash
SERVICE_URL=$(gcloud run services describe gemini-cost-arbiter-mcp --region us-central1 --format="value(status.url)")
curl -f "${SERVICE_URL}/health"
```

---

## 3. Plug-and-Play MCP Client Packaging

Ready-to-copy client configurations for **Antigravity**, **Gemini CLI**, **Claude Desktop**, and **Cursor** (`stdio` and `SSE`) are provided in [`deploy/gemini/mcp_configs.example.json`](../deploy/gemini/mcp_configs.example.json).
