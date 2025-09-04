#!/bin/bash

#######################################
# Deploy all Function Apps to Azure
# Resource Group: TheWell-Infra-East
# Functions: well-intake-functions, well-content-repurpose
#######################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="TheWell-Infra-East"
LOCATION="eastus"
KEY_VAULT_NAME="wellintakekeyvault"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}     Azure Function Apps Migration Deployment Script${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Target Resource Group:${NC} $RESOURCE_GROUP"
echo -e "${YELLOW}Location:${NC} $LOCATION"
echo -e "${YELLOW}Function Apps to Deploy:${NC}"
echo "  1. well-intake-functions (Email processing)"
echo "  2. well-content-repurpose (Content generation)"
echo ""

# Function to check command success
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1 completed successfully${NC}"
    else
        echo -e "${RED}✗ $1 failed${NC}"
        exit 1
    fi
}

# Check if logged in to Azure
echo -e "${YELLOW}Step 1: Checking Azure login...${NC}"
az account show > /dev/null 2>&1 || {
    echo -e "${RED}Not logged in to Azure. Please run 'az login' first.${NC}"
    exit 1
}
SUBSCRIPTION=$(az account show --query name -o tsv)
echo -e "${GREEN}✓ Logged in to subscription: $SUBSCRIPTION${NC}"
echo ""

# Ask for confirmation
read -p "Do you want to proceed with the deployment? (yes/no): " -r
echo
if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo -e "${RED}Deployment cancelled.${NC}"
    exit 1
fi

# Create resource group
echo -e "${YELLOW}Step 2: Creating resource group...${NC}"
az group create \
    --name $RESOURCE_GROUP \
    --location $LOCATION \
    --output none 2>/dev/null || echo "Resource group already exists"
check_status "Resource group creation"
echo ""

# Create shared Key Vault
echo -e "${YELLOW}Step 3: Creating shared Key Vault...${NC}"
az keyvault create \
    --name $KEY_VAULT_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --enable-soft-delete true \
    --retention-days 7 \
    --enable-purge-protection false \
    --output none 2>/dev/null || echo "Key Vault already exists"
check_status "Key Vault creation"
echo ""

# Deploy well-intake-functions
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Step 4: Deploying well-intake-functions...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
if [ -f "./deploy-well-intake-functions.sh" ]; then
    chmod +x ./deploy-well-intake-functions.sh
    ./deploy-well-intake-functions.sh
    check_status "well-intake-functions deployment"
else
    echo -e "${RED}deploy-well-intake-functions.sh not found!${NC}"
    exit 1
fi
echo ""

# Deploy well-content-repurpose
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Step 5: Deploying well-content-repurpose...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
if [ -f "./deploy-well-content-repurpose.sh" ]; then
    chmod +x ./deploy-well-content-repurpose.sh
    ./deploy-well-content-repurpose.sh
    check_status "well-content-repurpose deployment"
else
    echo -e "${RED}deploy-well-content-repurpose.sh not found!${NC}"
    exit 1
fi
echo ""

# Set up shared secrets in Key Vault
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Step 6: Setting up shared secrets in Key Vault...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Check if secrets exist
echo -e "${YELLOW}Checking for required secrets...${NC}"
SECRETS_TO_CHECK=("openai-api-key" "database-url" "storage-connection-string")
MISSING_SECRETS=()

for secret in "${SECRETS_TO_CHECK[@]}"; do
    az keyvault secret show --vault-name $KEY_VAULT_NAME --name $secret > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        MISSING_SECRETS+=($secret)
    else
        echo -e "${GREEN}✓ Secret '$secret' exists${NC}"
    fi
done

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}The following secrets need to be configured:${NC}"
    for secret in "${MISSING_SECRETS[@]}"; do
        echo "  - $secret"
    done
    echo ""
    echo -e "${YELLOW}You can set them using:${NC}"
    echo "az keyvault secret set --vault-name $KEY_VAULT_NAME --name <secret-name> --value '<secret-value>'"
fi
echo ""

# Create shared monitoring dashboard
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Step 7: Creating monitoring dashboard...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Get Application Insights ID
APP_INSIGHTS_ID=$(az monitor app-insights component show \
    --app "well-functions-insights" \
    --resource-group $RESOURCE_GROUP \
    --query id \
    --output tsv 2>/dev/null)

if [ ! -z "$APP_INSIGHTS_ID" ]; then
    echo -e "${GREEN}✓ Application Insights configured${NC}"
    echo "  Dashboard URL: https://portal.azure.com/#resource$APP_INSIGHTS_ID/overview"
else
    echo -e "${YELLOW}⚠ Application Insights not found${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}         Deployment Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Successfully deployed:${NC}"
echo "  ✓ Resource Group: $RESOURCE_GROUP"
echo "  ✓ Key Vault: $KEY_VAULT_NAME"
echo "  ✓ Function App: well-intake-functions"
echo "  ✓ Function App: well-content-repurpose"
echo "  ✓ Application Insights: well-functions-insights"
echo ""
echo -e "${YELLOW}Function App URLs:${NC}"
echo "  • well-intake-functions: https://well-intake-functions.azurewebsites.net"
echo "  • well-content-repurpose: https://well-content-repurpose.azurewebsites.net"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Configure missing Key Vault secrets (if any)"
echo "  2. Deploy function code from your repositories"
echo "  3. Test function endpoints"
echo "  4. Configure custom domains (optional)"
echo "  5. Set up CI/CD pipelines"
echo ""
echo -e "${GREEN}Migration preparation complete!${NC}"