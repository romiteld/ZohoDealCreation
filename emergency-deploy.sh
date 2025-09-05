#!/bin/bash

echo "========================================="
echo "EMERGENCY DEPLOYMENT - Well Intake API"
echo "========================================="
echo ""

# Load environment variables
if [ -f .env.local ]; then
    set -a
    source .env.local
    set +a
    echo "✓ Environment variables loaded"
fi

echo ""
echo "Step 1: Building Docker image..."
echo "---------------------------------"
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:emergency-$(date +%Y%m%d-%H%M%S) -t wellintakeacr0903.azurecr.io/well-intake-api:latest .
if [ $? -eq 0 ]; then
    echo "✓ Docker image built successfully"
else
    echo "✗ Docker build failed!"
    exit 1
fi

echo ""
echo "Step 2: Logging into Azure Container Registry..."
echo "-------------------------------------------------"
az acr login --name wellintakeacr0903
if [ $? -eq 0 ]; then
    echo "✓ Logged into ACR successfully"
else
    echo "✗ ACR login failed!"
    exit 1
fi

echo ""
echo "Step 3: Pushing Docker image..."
echo "--------------------------------"
docker push wellintakeacr0903.azurecr.io/well-intake-api:latest
if [ $? -eq 0 ]; then
    echo "✓ Docker image pushed successfully"
else
    echo "✗ Docker push failed!"
    exit 1
fi

echo ""
echo "Step 4: Updating Container App environment variables..."
echo "-------------------------------------------------------"
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
  --output none

if [ $? -eq 0 ]; then
    echo "✓ Environment variables updated"
else
    echo "✗ Environment variable update failed!"
    exit 1
fi

echo ""
echo "Step 5: Deploying new container image..."
echo "----------------------------------------"
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:latest \
  --output none

if [ $? -eq 0 ]; then
    echo "✓ Container App updated with new image"
else
    echo "✗ Container App update failed!"
    exit 1
fi

echo ""
echo "Step 6: Waiting for deployment to stabilize..."
echo "----------------------------------------------"
sleep 10

echo ""
echo "Step 7: Testing endpoints..."
echo "----------------------------"
echo "Testing Front Door health endpoint..."
curl -s https://well-intake-api-dnajdub4azhjcgc3.z03.azurefd.net/health | python3 -m json.tool | head -10
echo ""
echo "Testing manifest endpoint..."
curl -s -I https://well-intake-api-dnajdub4azhjcgc3.z03.azurefd.net/manifest.xml | head -5

echo ""
echo "========================================="
echo "DEPLOYMENT COMPLETE!"
echo "========================================="
echo ""
echo "Add-in URLs:"
echo "- Manifest: https://well-intake-api-dnajdub4azhjcgc3.z03.azurefd.net/manifest.xml"
echo "- Health: https://well-intake-api-dnajdub4azhjcgc3.z03.azurefd.net/health"
echo ""
echo "Next steps:"
echo "1. Clear Outlook cache (File > Options > Add-ins > Manage COM Add-ins)"
echo "2. Remove and re-add the add-in in Outlook"
echo "3. Test the 'Send to Zoho' button on an email"
echo ""
echo "If DNS is configured later, update manifest.xml to use addin.emailthewell.com"