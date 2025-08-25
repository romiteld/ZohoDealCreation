#!/bin/bash
# Automated Azure Deployment Script for Well Intake API
# Handles the complete deployment process with error checking

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="TheWell-App-East"
APP_NAME="well-intake-api"
REGION="canadacentral"

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Azure App Service Deployment Script${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Function to check if Azure CLI is installed
check_azure_cli() {
    if ! command -v az &> /dev/null; then
        echo -e "${RED}Error: Azure CLI is not installed${NC}"
        echo "Please install Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi
    echo -e "${GREEN}✓ Azure CLI found${NC}"
}

# Function to check Azure login
check_azure_login() {
    echo "Checking Azure login status..."
    if ! az account show &> /dev/null; then
        echo -e "${YELLOW}Not logged in to Azure${NC}"
        echo "Please login:"
        az login
    else
        ACCOUNT=$(az account show --query name -o tsv)
        echo -e "${GREEN}✓ Logged in to Azure account: $ACCOUNT${NC}"
    fi
}

# Function to verify resource group and app
verify_resources() {
    echo "Verifying Azure resources..."
    
    # Check resource group
    if az group show --name "$RESOURCE_GROUP" &> /dev/null; then
        echo -e "${GREEN}✓ Resource group '$RESOURCE_GROUP' found${NC}"
    else
        echo -e "${RED}Error: Resource group '$RESOURCE_GROUP' not found${NC}"
        exit 1
    fi
    
    # Check web app
    if az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
        echo -e "${GREEN}✓ Web app '$APP_NAME' found${NC}"
    else
        echo -e "${RED}Error: Web app '$APP_NAME' not found${NC}"
        exit 1
    fi
}

# Function to prepare deployment package
prepare_package() {
    echo ""
    echo "Preparing deployment package..."
    
    # Run the Python setup script
    if [ -f "azure_deploy_setup.py" ]; then
        python3 azure_deploy_setup.py
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Deployment package created${NC}"
        else
            echo -e "${RED}Error: Failed to create deployment package${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Error: azure_deploy_setup.py not found${NC}"
        exit 1
    fi
}

# Function to configure app settings
configure_app_settings() {
    echo ""
    echo "Configuring app settings..."
    
    # Set Python-specific settings
    az webapp config appsettings set \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_NAME" \
        --settings \
        WEBSITES_PORT=8000 \
        SCM_DO_BUILD_DURING_DEPLOYMENT=true \
        PYTHON_ENABLE_WORKER_EXTENSIONS=1 \
        WEBSITE_RUN_FROM_PACKAGE=0 \
        WEBSITES_CONTAINER_START_TIME_LIMIT=1800 \
        --output none
    
    echo -e "${GREEN}✓ App settings configured${NC}"
}

# Function to deploy the package
deploy_package() {
    echo ""
    echo "Deploying package to Azure..."
    
    if [ ! -f "deploy.zip" ]; then
        echo -e "${RED}Error: deploy.zip not found${NC}"
        exit 1
    fi
    
    # Get the current state for rollback
    echo "Saving current deployment state..."
    DEPLOYMENT_ID=$(date +%Y%m%d%H%M%S)
    
    # Deploy the ZIP package
    echo "Uploading deployment package..."
    az webapp deploy \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_NAME" \
        --src-path deploy.zip \
        --type zip \
        --timeout 600
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Package deployed successfully${NC}"
    else
        echo -e "${RED}Error: Deployment failed${NC}"
        exit 1
    fi
}

# Function to set startup command
set_startup_command() {
    echo ""
    echo "Setting startup command..."
    
    az webapp config set \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_NAME" \
        --startup-file "bash startup.sh" \
        --output none
    
    echo -e "${GREEN}✓ Startup command configured${NC}"
}

# Function to restart the app
restart_app() {
    echo ""
    echo "Restarting application..."
    
    az webapp restart \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_NAME"
    
    echo -e "${GREEN}✓ Application restarted${NC}"
}

# Function to verify deployment
verify_deployment() {
    echo ""
    echo "Verifying deployment..."
    echo "Waiting for application to start (this may take 2-3 minutes)..."
    
    # Wait for app to be ready
    sleep 30
    
    # Check health endpoint
    HEALTH_URL="https://${APP_NAME}.azurewebsites.net/health"
    echo "Checking health endpoint: $HEALTH_URL"
    
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || echo "000")
    
    if [ "$HTTP_STATUS" = "200" ]; then
        echo -e "${GREEN}✓ Application is healthy (HTTP $HTTP_STATUS)${NC}"
        echo -e "${GREEN}✓ Deployment successful!${NC}"
    elif [ "$HTTP_STATUS" = "000" ]; then
        echo -e "${YELLOW}⚠ Could not reach application (network error)${NC}"
        echo "The application may still be starting. Check logs with:"
        echo "  az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
    else
        echo -e "${YELLOW}⚠ Application returned HTTP $HTTP_STATUS${NC}"
        echo "Check application logs for details:"
        echo "  az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
    fi
}

# Function to show logs
show_logs() {
    echo ""
    echo -e "${YELLOW}To monitor deployment logs, run:${NC}"
    echo "  az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
    echo ""
    echo -e "${YELLOW}To download logs, run:${NC}"
    echo "  az webapp log download --resource-group $RESOURCE_GROUP --name $APP_NAME --log-file logs.zip"
    echo ""
    echo -e "${YELLOW}To SSH into the container, run:${NC}"
    echo "  az webapp ssh --resource-group $RESOURCE_GROUP --name $APP_NAME"
}

# Main deployment flow
main() {
    echo "Starting Azure deployment process..."
    echo ""
    
    # Pre-deployment checks
    check_azure_cli
    check_azure_login
    verify_resources
    
    # Prepare and deploy
    prepare_package
    configure_app_settings
    deploy_package
    set_startup_command
    restart_app
    
    # Verify
    verify_deployment
    show_logs
    
    echo ""
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}Deployment Complete!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo ""
    echo "Application URL: https://${APP_NAME}.azurewebsites.net"
    echo "API Documentation: https://${APP_NAME}.azurewebsites.net/docs"
    echo "Health Check: https://${APP_NAME}.azurewebsites.net/health"
    echo ""
}

# Handle script arguments
case "${1:-}" in
    --rollback)
        echo "Rolling back to previous deployment..."
        az webapp deployment rollback \
            --resource-group "$RESOURCE_GROUP" \
            --name "$APP_NAME"
        echo -e "${GREEN}✓ Rollback initiated${NC}"
        ;;
    --logs)
        echo "Showing application logs..."
        az webapp log tail \
            --resource-group "$RESOURCE_GROUP" \
            --name "$APP_NAME"
        ;;
    --status)
        echo "Checking application status..."
        az webapp show \
            --resource-group "$RESOURCE_GROUP" \
            --name "$APP_NAME" \
            --query "{Status:state, URL:defaultHostName, Runtime:runtimeAvailability}" \
            -o table
        ;;
    --help)
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  (no option)  Deploy the application"
        echo "  --rollback   Rollback to previous deployment"
        echo "  --logs       Show application logs"
        echo "  --status     Check application status"
        echo "  --help       Show this help message"
        ;;
    *)
        main
        ;;
esac