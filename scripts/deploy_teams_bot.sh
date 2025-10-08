#!/bin/bash
set -e

# Teams Bot Deployment Script
# Deploys Teams Bot service to Azure Container Apps

echo "============================================"
echo "Teams Bot Service Deployment"
echo "============================================"

# Configuration
RESOURCE_GROUP="TheWell-Infra-East"
ACR_NAME="wellintakeacr0903"
IMAGE_NAME="teams-bot"
CONTAINER_APP_NAME="teams-bot"
ENVIRONMENT_NAME="well-intake-env"

# Build image
echo "📦 Building Docker image..."
docker build -f teams_bot/Dockerfile -t ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest .

# Login to ACR
echo "🔐 Logging into Azure Container Registry..."
az acr login --name ${ACR_NAME}

# Push image
echo "⬆️  Pushing image to ACR..."
docker push ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest

# Check if Container App exists
if az containerapp show --name ${CONTAINER_APP_NAME} --resource-group ${RESOURCE_GROUP} &> /dev/null; then
    echo "🔄 Updating existing Container App..."

    # Update with new revision
    REVISION_SUFFIX="v$(date +%Y%m%d-%H%M%S)"
    az containerapp update \
        --name ${CONTAINER_APP_NAME} \
        --resource-group ${RESOURCE_GROUP} \
        --image ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest \
        --revision-suffix ${REVISION_SUFFIX}
else
    echo "🆕 Creating new Container App..."

    # Create new Container App
    az containerapp create \
        --name ${CONTAINER_APP_NAME} \
        --resource-group ${RESOURCE_GROUP} \
        --environment ${ENVIRONMENT_NAME} \
        --image ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest \
        --target-port 8001 \
        --ingress external \
        --min-replicas 1 \
        --max-replicas 3 \
        --cpu 0.5 \
        --memory 1.0Gi \
        --env-vars \
            SERVICE_NAME=teams-bot \
            PORT=8001 \
        --secrets \
            database-url=secretref:database-url \
            redis-connection=secretref:redis-connection \
            bot-app-id=secretref:bot-app-id \
            bot-app-password=secretref:bot-app-password \
            openai-api-key=secretref:openai-api-key \
            zoho-oauth-url=secretref:zoho-oauth-url \
            acs-connection=secretref:acs-connection \
            appinsights-connection=secretref:appinsights-connection
fi

# Get FQDN
FQDN=$(az containerapp show \
    --name ${CONTAINER_APP_NAME} \
    --resource-group ${RESOURCE_GROUP} \
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
