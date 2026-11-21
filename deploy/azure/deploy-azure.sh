#!/usr/bin/env bash
# ==============================================================================
# Turnkey Azure Container Apps Deployment Script for gemini-cost-arbiter-mcp
# ==============================================================================
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-rg-gemini-cost-arbiter}"
LOCATION="${LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-acrcostarbiter01}"
KV_NAME="${KV_NAME:-kv-cost-arbiter-01}"
ENV_NAME="${ENV_NAME:-cae-cost-arbiter}"
APP_NAME="${APP_NAME:-gemini-cost-arbiter-mcp}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

IMAGE_URI="${ACR_NAME}.azurecr.io/${APP_NAME}:${IMAGE_TAG}"

echo "[+] Building and pushing image to ACR: ${IMAGE_URI}"
az acr build --registry "${ACR_NAME}" --image "${APP_NAME}:${IMAGE_TAG}" .

echo "[+] Ensuring Container Apps environment exists..."
az containerapp env create \
  --name "${ENV_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --location "${LOCATION}" \
  --output none

echo "[+] Fetching secrets from Azure Key Vault: ${KV_NAME}"
GEMINI_API_KEY=$(az keyvault secret show --vault-name "${KV_NAME}" --name "gemini-api-key" --query value -o tsv)
MCP_API_KEY=$(az keyvault secret show --vault-name "${KV_NAME}" --name "mcp-api-key" --query value -o tsv)
PLAN_SIGNING_SECRET=$(az keyvault secret show --vault-name "${KV_NAME}" --name "plan-signing-secret" --query value -o tsv)

echo "[+] Deploying Azure Container App: ${APP_NAME}"
az containerapp create \
  --name "${APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --environment "${ENV_NAME}" \
  --image "${IMAGE_URI}" \
  --target-port 8000 \
  --ingress external \
  --cpu 0.5 --memory 1.0Gi \
  --secrets \
    gemini-api-key="${GEMINI_API_KEY}" \
    mcp-api-key="${MCP_API_KEY}" \
    plan-signing-secret="${PLAN_SIGNING_SECRET}" \
  --env-vars \
    ENVIRONMENT=production \
    REQUIRE_AUTH=true \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    MAX_PAYLOAD_BYTES=10485760 \
    DEFAULT_MODEL=gemini-3.8-flash-high \
    THINKING_BUDGET=2048 \
    MAX_OUTPUT_TOKENS=8192 \
    DB_PATH=/app/data/finops.db \
    GEMINI_API_KEY=secretref:gemini-api-key \
    MCP_API_KEY=secretref:mcp-api-key \
    PLAN_SIGNING_SECRET=secretref:plan-signing-secret

echo "[+] Deployment complete. Verify /health endpoint via FQDN."
