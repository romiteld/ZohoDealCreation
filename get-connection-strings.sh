#!/bin/bash

# Script to get all connection strings for the new migrated resources
# Date: 2025-09-03

set -e

RESOURCE_GROUP="TheWell-Infra-East"

echo "================================================"
echo "Connection Strings for Migrated Resources"
echo "================================================"
echo ""

# PostgreSQL
echo "# PostgreSQL Database"
echo "DATABASE_URL=postgresql://welldbadmin:W3llRecruit2025DB!@well-intake-db-0903.postgres.database.azure.com:5432/wellintake?sslmode=require"
echo ""

# Redis Cache
echo "# Redis Cache"
REDIS_KEY=$(az redis list-keys --name wellintakecache0903 --resource-group $RESOURCE_GROUP --query primaryKey -o tsv 2>/dev/null || echo "[FAILED_TO_GET_KEY]")
echo "AZURE_REDIS_CONNECTION_STRING=rediss://:${REDIS_KEY}@wellintakecache0903.redis.cache.windows.net:6380"
echo ""

# Storage Accounts
echo "# Storage Account (Attachments)"
STORAGE_KEY=$(az storage account keys list --account-name wellattachments0903 --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv 2>/dev/null || echo "[FAILED_TO_GET_KEY]")
echo "AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;EndpointSuffix=core.windows.net;AccountName=wellattachments0903;AccountKey=${STORAGE_KEY}"
echo "AZURE_CONTAINER_NAME=email-attachments"
echo ""

echo "# Storage Account (Functions)"
FUNC_STORAGE_KEY=$(az storage account keys list --account-name wellintakefunc0903 --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv 2>/dev/null || echo "[FAILED_TO_GET_KEY]")
echo "AZURE_FUNC_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;EndpointSuffix=core.windows.net;AccountName=wellintakefunc0903;AccountKey=${FUNC_STORAGE_KEY}"
echo ""

# Service Bus
echo "# Service Bus"
SERVICE_BUS_CONNECTION_STRING=$(az servicebus namespace authorization-rule keys list \
  --namespace-name wellintakebus0903 \
  --resource-group $RESOURCE_GROUP \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv 2>/dev/null || echo "[FAILED_TO_GET_CONNECTION_STRING]")
echo "AZURE_SERVICE_BUS_CONNECTION_STRING=${SERVICE_BUS_CONNECTION_STRING}"
echo "AZURE_SERVICE_BUS_QUEUE_NAME=email-processing"
echo ""

# SignalR
echo "# SignalR"
SIGNALR_CONNECTION_STRING=$(az signalr key list \
  --name wellintakesignalr0903 \
  --resource-group $RESOURCE_GROUP \
  --query primaryConnectionString -o tsv 2>/dev/null || echo "[FAILED_TO_GET_CONNECTION_STRING]")
echo "AZURE_SIGNALR_CONNECTION_STRING=${SIGNALR_CONNECTION_STRING}"
echo ""

# AI Search
echo "# AI Search"
AI_SEARCH_KEY=$(az search admin-key show \
  --service-name wellintakesearch0903 \
  --resource-group $RESOURCE_GROUP \
  --query primaryKey -o tsv 2>/dev/null || echo "[FAILED_TO_GET_KEY]")
echo "AZURE_AI_SEARCH_ENDPOINT=https://wellintakesearch0903.search.windows.net"
echo "AZURE_AI_SEARCH_KEY=${AI_SEARCH_KEY}"
echo "AZURE_AI_SEARCH_INDEX_NAME=well-intake-patterns"
echo ""

# Application Insights
echo "# Application Insights"
APP_INSIGHTS_CONNECTION_STRING=$(az monitor app-insights component show \
  --app wellintakeinsights0903 \
  --resource-group $RESOURCE_GROUP \
  --query connectionString -o tsv 2>/dev/null || echo "[FAILED_TO_GET_CONNECTION_STRING]")

APP_INSIGHTS_INSTRUMENTATION_KEY=$(az monitor app-insights component show \
  --app wellintakeinsights0903 \
  --resource-group $RESOURCE_GROUP \
  --query instrumentationKey -o tsv 2>/dev/null || echo "[FAILED_TO_GET_KEY]")

echo "APPLICATIONINSIGHTS_CONNECTION_STRING=${APP_INSIGHTS_CONNECTION_STRING}"
echo "APPINSIGHTS_INSTRUMENTATIONKEY=${APP_INSIGHTS_INSTRUMENTATION_KEY}"
echo ""

echo "================================================"
echo "Summary of Resources:"
echo "================================================"
echo "✅ PostgreSQL: well-intake-db-0903.postgres.database.azure.com"
echo "✅ Redis: wellintakecache0903.redis.cache.windows.net"
echo "✅ Storage (Attachments): wellattachments0903.blob.core.windows.net"
echo "✅ Storage (Functions): wellintakefunc0903.blob.core.windows.net"
echo "✅ Service Bus: wellintakebus0903.servicebus.windows.net"
echo "✅ SignalR: wellintakesignalr0903.service.signalr.net"
echo "✅ AI Search: wellintakesearch0903.search.windows.net"
echo "✅ App Insights: wellintakeinsights0903"
echo ""