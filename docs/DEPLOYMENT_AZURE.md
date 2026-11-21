# Azure Production Deployment Guide (`docs/DEPLOYMENT_AZURE.md`)

**Target Environment:** Microsoft Azure — Azure Container Registry (ACR) + Azure Container Apps (ACA) / Azure Container Instances (ACI)  
**Governance:** [`GEMINI.md`](../GEMINI.md) | [`Enterprise_Blueprint.md`](../Enterprise_Blueprint.md)  
**Assets:** [`deploy/azure/deploy-azure.sh`](../deploy/azure/deploy-azure.sh), [`deploy/azure/docker-compose.azure.yml`](../deploy/azure/docker-compose.azure.yml)

---

## 1. Architecture Overview

- **Registry:** Azure Container Registry (`acr`) hosting the non-root `python:3.13-slim` container built from [`Dockerfile`](../Dockerfile).
- **Compute:** Azure Container Apps (`az containerapp`) with external HTTPS ingress on target port `8000` and `/health` readiness/liveness probes.
- **Secrets:** Azure Key Vault (`az keyvault secret`) injected into Container App secrets (`gemini-api-key`, `mcp-api-key`, `plan-signing-secret`)—zero plaintext secrets in manifests.
- **Persistence:** Azure Files volume mounted at `/app/data` for `DB_PATH=/app/data/finops.db` (SQLite WAL mode).

---

## 2. Step-by-Step Deployment

### Step 1: Provision Resource Group, ACR & Key Vault

```bash
RESOURCE_GROUP="rg-gemini-cost-arbiter"
LOCATION="eastus"
ACR_NAME="acrcostarbiter01"
KV_NAME="kv-cost-arbiter-01"

az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled true
az keyvault create --name "$KV_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION"

az keyvault secret set --vault-name "$KV_NAME" --name "gemini-api-key" --value "<YOUR_GEMINI_API_KEY>"
az keyvault secret set --vault-name "$KV_NAME" --name "mcp-api-key" --value "$(openssl rand -hex 32)"
az keyvault secret set --vault-name "$KV_NAME" --name "plan-signing-secret" --value "$(openssl rand -hex 32)"
```

### Step 2: Build, Push & Deploy via Turnkey Script

```bash
chmod +x deploy/azure/deploy-azure.sh
RESOURCE_GROUP="rg-gemini-cost-arbiter" \
ACR_NAME="acrcostarbiter01" \
KV_NAME="kv-cost-arbiter-01" \
./deploy/azure/deploy-azure.sh
```

### Step 3: Local Azure Compose Parity & Health Probe

```bash
docker compose -f deploy/azure/docker-compose.azure.yml up -d
curl -f http://localhost:8000/health
# Expected: {"status":"healthy","service":"gemini-cost-arbiter-mcp"}
```
