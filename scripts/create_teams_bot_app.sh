#!/bin/bash
set -e

# Create Teams Bot Container App with Key Vault secret references

RESOURCE_GROUP="TheWell-Infra-East"
ENVIRONMENT="well-intake-env"
APP_NAME="teams-bot"
IMAGE="wellintakeacr0903.azurecr.io/teams-bot:latest"
KEYVAULT="https://well-intake-kv.vault.azure.net"

echo "Creating Teams Bot Container App..."

# Create with system-assigned managed identity
az containerapp create \
  --name "${APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --environment "${ENVIRONMENT}" \
  --image "${IMAGE}" \
  --target-port 8001 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --registry-server wellintakeacr0903.azurecr.io \
  --system-assigned \
  --secrets \
    database-url="keyvaultref:${KEYVAULT}/secrets/database-url" \
    redis-connection="keyvaultref:${KEYVAULT}/secrets/redis-connection-string" \
    openai-api-key="keyvaultref:${KEYVAULT}/secrets/openai-api-key" \
    bot-app-password="keyvaultref:${KEYVAULT}/secrets/teams-bot-app-password" \
  --env-vars \
    SERVICE_NAME=teams-bot \
    PORT=8001 \
    DATABASE_URL=secretref:database-url \
    AZURE_REDIS_CONNECTION_STRING=secretref:redis-connection \
    OPENAI_API_KEY=secretref:openai-api-key \
    OPENAI_MODEL=gpt-5-mini \
    TEAMS_BOT_APP_ID=34d9338f-ba4e-4a68-9a22-b01892afba83 \
    TEAMS_BOT_APP_PASSWORD=secretref:bot-app-password \
    TEAMS_BOT_TENANT_ID=29ee1479-b5f7-48c5-b665-7de9a8a9033e \
    ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth-v2.azurewebsites.net \
    ZOHO_DEFAULT_OWNER_EMAIL=daniel.romitelli@emailthewell.com \
    ZOHO_VAULT_VIEW_ID=6221978000090941003 \
    ACS_EMAIL_CONNECTION_STRING="endpoint=https://well-communication-services.unitedstates.communication.azure.com/;accesskey=FPOJad6EvdZwIeEjBTMykP7dn4B1M6NBNbuKqnuVWu6M3s8Rn4FMJQQJ99BIACULyCpW8ypnAAAAAZCS8yrU" \
    SMTP_FROM_EMAIL=noreply@emailthewell.com \
    SMTP_FROM_NAME="TalentWell Vault" \
    APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=3f58ffbc-d4c1-42ae-bce5-1e0c7ecd9cd7;IngestionEndpoint=https://eastus-8.in.applicationinsights.azure.com/;LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/;ApplicationId=4906f571-0dab-442c-9728-9dd5abaf013a" \
    PRIVACY_MODE=true \
    FEATURE_GROWTH_EXTRACTION=true \
    FEATURE_LLM_SENTIMENT=true \
    FEATURE_C3=true \
    FEATURE_VOIT=true \
    C3_DELTA=0.01 \
    VOIT_BUDGET=5.0 \
    TARGET_QUALITY=0.9

echo "Teams Bot Container App created successfully!"

# Get FQDN
FQDN=$(az containerapp show \
  --name "${APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

echo ""
echo "✅ Deployment complete!"
echo "🌐 Teams Bot URL: https://${FQDN}"
echo "🔍 Health check: https://${FQDN}/health"
echo ""
echo "Next steps:"
echo "1. Update Bot Framework messaging endpoint: https://${FQDN}/api/teams/messages"
echo "2. Run smoke tests: pytest tests/smoke/test_teams_bot_smoke.py --env=staging"
echo "3. Validate deployment: python scripts/deployment_gate.py --service teams-bot"
