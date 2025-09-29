#!/bin/bash
# Script to update Azure Container App environment variables

# Load environment variables from .env.local
if [ -f .env.local ]; then
    export $(cat .env.local | grep -v '^#' | xargs)
fi

echo "Updating Azure Container App environment variables..."

# Update all environment variables at once
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --set-env-vars \
    "API_KEY=$API_KEY" \
    "DATABASE_URL=$DATABASE_URL" \
    "AZURE_REDIS_CONNECTION_STRING=$AZURE_REDIS_CONNECTION_STRING" \
    "AZURE_SERVICE_BUS_CONNECTION_STRING=$AZURE_SERVICE_BUS_CONNECTION_STRING" \
    "AZURE_SIGNALR_CONNECTION_STRING=$AZURE_SIGNALR_CONNECTION_STRING" \
    "APPLICATIONINSIGHTS_CONNECTION_STRING=$APPLICATIONINSIGHTS_CONNECTION_STRING" \
    "AZURE_SEARCH_ENDPOINT=$AZURE_SEARCH_ENDPOINT" \
    "AZURE_SEARCH_KEY=$AZURE_SEARCH_KEY" \
    "AZURE_STORAGE_CONNECTION_STRING=$AZURE_STORAGE_CONNECTION_STRING" \
    "AZURE_CONTAINER_NAME=$AZURE_CONTAINER_NAME" \
    "OPENAI_API_KEY=$OPENAI_API_KEY" \
    "OPENAI_MODEL=$OPENAI_MODEL" \
    "FIRECRAWL_API_KEY=$FIRECRAWL_API_KEY" \
    "ZOHO_OAUTH_SERVICE_URL=$ZOHO_OAUTH_SERVICE_URL" \
    "ZOHO_CLIENT_ID=$ZOHO_CLIENT_ID" \
    "ZOHO_CLIENT_SECRET=$ZOHO_CLIENT_SECRET" \
    "ZOHO_REFRESH_TOKEN=$ZOHO_REFRESH_TOKEN" \
    "ZOHO_DEFAULT_OWNER_EMAIL=$ZOHO_DEFAULT_OWNER_EMAIL" \
    "USE_LANGGRAPH=true" \
    "LOG_LEVEL=INFO" \
    "ENABLE_AZURE_MAPS=true" \
    "AZURE_MAPS_BASE_URL=https://atlas.microsoft.com" \
    "AZURE_MAPS_API_VERSION=1.0" \
    "AZURE_MAPS_KEY_SECRET_NAME=AzureMapsKey" \
    "AZURE_MAPS_DEFAULT_COUNTRY=US" \
    "AZURE_MAPS_CACHE_TTL_SEC=86400" \
  --output json

echo "Environment variables updated successfully!"