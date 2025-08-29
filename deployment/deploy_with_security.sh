#!/bin/bash

# Well Intake API - Enterprise Deployment Script with Security & Monitoring
# This script handles zero-downtime deployment with security enhancements

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="TheWell-Infra-East"
LOCATION="eastus"
REGISTRY_NAME="wellintakeregistry"
CONTAINER_APP_NAME="well-intake-api"
KEY_VAULT_NAME="well-intake-kv"
APP_INSIGHTS_NAME="well-intake-insights"
REDIS_NAME="well-intake-redis"
IMAGE_TAG=${1:-"latest"}

# Function to print colored messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Please install it first."
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install it first."
        exit 1
    fi
    
    # Check Azure login
    if ! az account show &> /dev/null; then
        log_error "Not logged into Azure. Please run 'az login' first."
        exit 1
    fi
    
    log_info "Prerequisites check passed."
}

# Create or update Key Vault
setup_key_vault() {
    log_info "Setting up Azure Key Vault..."
    
    # Check if Key Vault exists
    if az keyvault show --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
        log_info "Key Vault already exists."
    else
        log_info "Creating Key Vault..."
        az keyvault create \
            --name $KEY_VAULT_NAME \
            --resource-group $RESOURCE_GROUP \
            --location $LOCATION \
            --enable-rbac-authorization false \
            --enabled-for-deployment true \
            --enabled-for-disk-encryption true \
            --enabled-for-template-deployment true \
            --sku standard
    fi
    
    # Store secrets from .env.local
    if [ -f ".env.local" ]; then
        log_info "Migrating secrets to Key Vault..."
        
        # Read .env.local and store secrets
        while IFS='=' read -r key value; do
            # Skip comments and empty lines
            if [[ ! "$key" =~ ^# ]] && [ -n "$key" ]; then
                # Convert underscore to hyphen for Key Vault naming
                secret_name=$(echo "$key" | tr '_' '-' | tr '[:upper:]' '[:lower:]')
                
                # Store secret in Key Vault
                az keyvault secret set \
                    --vault-name $KEY_VAULT_NAME \
                    --name "$secret_name" \
                    --value "$value" \
                    --output none 2>/dev/null || true
            fi
        done < .env.local
        
        log_info "Secrets migrated to Key Vault."
    else
        log_warn ".env.local not found. Skipping secret migration."
    fi
}

# Setup Application Insights
setup_monitoring() {
    log_info "Setting up Application Insights..."
    
    # Check if Application Insights exists
    if az monitor app-insights component show \
        --app $APP_INSIGHTS_NAME \
        --resource-group $RESOURCE_GROUP &> /dev/null; then
        log_info "Application Insights already exists."
    else
        log_info "Creating Application Insights..."
        
        # Create Log Analytics Workspace first
        workspace_id=$(az monitor log-analytics workspace create \
            --resource-group $RESOURCE_GROUP \
            --workspace-name "${APP_INSIGHTS_NAME}-workspace" \
            --location $LOCATION \
            --query id -o tsv)
        
        # Create Application Insights
        az monitor app-insights component create \
            --app $APP_INSIGHTS_NAME \
            --location $LOCATION \
            --resource-group $RESOURCE_GROUP \
            --workspace $workspace_id \
            --application-type web
    fi
    
    # Get connection string
    APP_INSIGHTS_CONNECTION=$(az monitor app-insights component show \
        --app $APP_INSIGHTS_NAME \
        --resource-group $RESOURCE_GROUP \
        --query connectionString -o tsv)
    
    # Store in Key Vault
    az keyvault secret set \
        --vault-name $KEY_VAULT_NAME \
        --name "appinsights-connection-string" \
        --value "$APP_INSIGHTS_CONNECTION" \
        --output none
    
    log_info "Application Insights configured."
}

# Setup Redis Cache
setup_redis() {
    log_info "Setting up Azure Cache for Redis..."
    
    # Check if Redis exists
    if az redis show --name $REDIS_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
        log_info "Redis cache already exists."
    else
        log_info "Creating Redis cache (this may take 15-20 minutes)..."
        
        az redis create \
            --name $REDIS_NAME \
            --resource-group $RESOURCE_GROUP \
            --location $LOCATION \
            --sku Standard \
            --vm-size c1 \
            --enable-non-ssl-port false \
            --minimum-tls-version 1.2
    fi
    
    # Get Redis connection string
    REDIS_KEY=$(az redis list-keys \
        --name $REDIS_NAME \
        --resource-group $RESOURCE_GROUP \
        --query primaryKey -o tsv)
    
    REDIS_CONNECTION="${REDIS_NAME}.redis.cache.windows.net:6380,password=${REDIS_KEY},ssl=True,abortConnect=False"
    
    # Store in Key Vault
    az keyvault secret set \
        --vault-name $KEY_VAULT_NAME \
        --name "redis-connection-string" \
        --value "$REDIS_CONNECTION" \
        --output none
    
    log_info "Redis cache configured."
}

# Build and push Docker image
build_and_push_image() {
    log_info "Building Docker image..."
    
    # Build the image
    docker build -t ${REGISTRY_NAME}.azurecr.io/${CONTAINER_APP_NAME}:${IMAGE_TAG} .
    
    # Login to ACR
    log_info "Logging into Azure Container Registry..."
    az acr login --name $REGISTRY_NAME
    
    # Push the image
    log_info "Pushing image to registry..."
    docker push ${REGISTRY_NAME}.azurecr.io/${CONTAINER_APP_NAME}:${IMAGE_TAG}
    
    log_info "Docker image pushed successfully."
}

# Deploy to Container Apps with zero downtime
deploy_container_app() {
    log_info "Deploying to Azure Container Apps..."
    
    # Check if Container App exists
    if az containerapp show \
        --name $CONTAINER_APP_NAME \
        --resource-group $RESOURCE_GROUP &> /dev/null; then
        
        log_info "Updating existing Container App with zero-downtime deployment..."
        
        # Create a new revision
        az containerapp update \
            --name $CONTAINER_APP_NAME \
            --resource-group $RESOURCE_GROUP \
            --image ${REGISTRY_NAME}.azurecr.io/${CONTAINER_APP_NAME}:${IMAGE_TAG} \
            --revision-suffix "v$(date +%Y%m%d%H%M%S)" \
            --min-replicas 2 \
            --max-replicas 10 \
            --scale-rule-name cpu-scaling \
            --scale-rule-type cpu \
            --scale-rule-metadata type=utilization value=70 \
            --cpu 2 \
            --memory 4Gi \
            --set-env-vars \
                USE_MANAGED_IDENTITY=true \
                KEY_VAULT_URL=https://${KEY_VAULT_NAME}.vault.azure.net/ \
                ENVIRONMENT=production \
                USE_LANGGRAPH=true \
                OPENAI_MODEL=gpt-4o-mini
        
        # Wait for the new revision to be ready
        log_info "Waiting for new revision to be ready..."
        sleep 30
        
        # Gradually shift traffic to new revision
        log_info "Shifting traffic to new revision..."
        
        # Get the latest revision name
        NEW_REVISION=$(az containerapp revision list \
            --name $CONTAINER_APP_NAME \
            --resource-group $RESOURCE_GROUP \
            --query "[0].name" -o tsv)
        
        # Set traffic split (canary deployment)
        az containerapp ingress traffic set \
            --name $CONTAINER_APP_NAME \
            --resource-group $RESOURCE_GROUP \
            --revision-weight $NEW_REVISION=100
        
    else
        log_error "Container App does not exist. Please create it first."
        exit 1
    fi
    
    log_info "Container App deployed successfully."
}

# Setup alerts
setup_alerts() {
    log_info "Setting up monitoring alerts..."
    
    # Get App Insights ID
    APP_INSIGHTS_ID=$(az monitor app-insights component show \
        --app $APP_INSIGHTS_NAME \
        --resource-group $RESOURCE_GROUP \
        --query id -o tsv)
    
    # Create alert for high error rate
    az monitor metrics alert create \
        --name "HighErrorRate" \
        --resource-group $RESOURCE_GROUP \
        --scopes $APP_INSIGHTS_ID \
        --condition "avg exceptions/count > 5" \
        --window-size 5m \
        --evaluation-frequency 1m \
        --severity 2 \
        --description "Email processing error rate is high"
    
    # Create alert for high latency
    az monitor metrics alert create \
        --name "HighLatency" \
        --resource-group $RESOURCE_GROUP \
        --scopes $APP_INSIGHTS_ID \
        --condition "avg requests/duration > 5000" \
        --window-size 5m \
        --evaluation-frequency 1m \
        --severity 3 \
        --description "API latency is high"
    
    # Create alert for high cost
    az monitor metrics alert create \
        --name "HighGPTCost" \
        --resource-group $RESOURCE_GROUP \
        --scopes $APP_INSIGHTS_ID \
        --condition "sum customMetrics/gpt_cost_usd > 100" \
        --window-size 1440m \
        --evaluation-frequency 60m \
        --severity 3 \
        --description "Daily GPT cost exceeds $100"
    
    log_info "Alerts configured."
}

# Run health check
health_check() {
    log_info "Running health check..."
    
    # Get the app URL
    APP_URL=$(az containerapp show \
        --name $CONTAINER_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --query properties.configuration.ingress.fqdn -o tsv)
    
    # Check health endpoint
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://${APP_URL}/health)
    
    if [ "$HEALTH_STATUS" == "200" ]; then
        log_info "Health check passed! Application is running."
        
        # Get detailed health info
        curl -s https://${APP_URL}/health | python -m json.tool
    else
        log_error "Health check failed with status: $HEALTH_STATUS"
        
        # Get recent logs
        log_warn "Recent application logs:"
        az containerapp logs show \
            --name $CONTAINER_APP_NAME \
            --resource-group $RESOURCE_GROUP \
            --tail 50
        
        exit 1
    fi
}

# Cleanup old revisions
cleanup_old_revisions() {
    log_info "Cleaning up old revisions..."
    
    # Get all revisions except the latest 3
    OLD_REVISIONS=$(az containerapp revision list \
        --name $CONTAINER_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --query "[3:].name" -o tsv)
    
    for revision in $OLD_REVISIONS; do
        log_info "Deactivating revision: $revision"
        az containerapp revision deactivate \
            --name $CONTAINER_APP_NAME \
            --resource-group $RESOURCE_GROUP \
            --revision $revision || true
    done
    
    log_info "Cleanup completed."
}

# Main deployment flow
main() {
    log_info "Starting Well Intake API deployment with security and monitoring..."
    
    # Check prerequisites
    check_prerequisites
    
    # Setup infrastructure
    setup_key_vault
    setup_monitoring
    setup_redis
    
    # Build and deploy
    build_and_push_image
    deploy_container_app
    
    # Configure monitoring
    setup_alerts
    
    # Validate deployment
    health_check
    
    # Cleanup
    cleanup_old_revisions
    
    log_info "Deployment completed successfully!"
    
    # Print summary
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Deployment Summary:${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "Container App: ${CONTAINER_APP_NAME}"
    echo -e "Resource Group: ${RESOURCE_GROUP}"
    echo -e "Image Tag: ${IMAGE_TAG}"
    echo -e "Key Vault: ${KEY_VAULT_NAME}"
    echo -e "App Insights: ${APP_INSIGHTS_NAME}"
    echo -e "Redis Cache: ${REDIS_NAME}"
    
    APP_URL=$(az containerapp show \
        --name $CONTAINER_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --query properties.configuration.ingress.fqdn -o tsv)
    
    echo -e "Application URL: https://${APP_URL}"
    echo -e "${GREEN}========================================${NC}"
}

# Run main function
main