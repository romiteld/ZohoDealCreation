#!/bin/bash

#######################################
# Deploy well-intake-functions to Azure
# Resource Group: TheWell-Infra-East
# Runtime: Python 3.11
#######################################

set -e  # Exit on error

# Configuration
RESOURCE_GROUP="TheWell-Infra-East"
LOCATION="eastus"
FUNCTION_APP_NAME="well-intake-functions"
STORAGE_ACCOUNT_NAME="wellintakefuncstorage"
APP_INSIGHTS_NAME="well-functions-insights"
PLAN_NAME="well-intake-functions-plan"
PYTHON_VERSION="3.11"

# Key Vault for secrets
KEY_VAULT_NAME="wellintakekeyvault"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting deployment of well-intake-functions...${NC}"

# Check if logged in to Azure
echo -e "${YELLOW}Checking Azure login...${NC}"
az account show > /dev/null 2>&1 || {
    echo -e "${RED}Not logged in to Azure. Please run 'az login' first.${NC}"
    exit 1
}

# Create resource group if it doesn't exist
echo -e "${YELLOW}Ensuring resource group exists...${NC}"
az group create \
    --name $RESOURCE_GROUP \
    --location $LOCATION \
    --output none 2>/dev/null || echo "Resource group already exists"

# Create storage account
echo -e "${YELLOW}Creating storage account: $STORAGE_ACCOUNT_NAME${NC}"
az storage account create \
    --name $STORAGE_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --sku Standard_LRS \
    --kind StorageV2 \
    --access-tier Hot \
    --https-only true \
    --min-tls-version TLS1_2 \
    --allow-blob-public-access false \
    --output none || echo "Storage account already exists"

# Get storage account connection string
STORAGE_CONNECTION_STRING=$(az storage account show-connection-string \
    --name $STORAGE_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --query connectionString \
    --output tsv)

# Create Application Insights if it doesn't exist
echo -e "${YELLOW}Creating Application Insights: $APP_INSIGHTS_NAME${NC}"
az monitor app-insights component create \
    --app $APP_INSIGHTS_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --kind web \
    --application-type web \
    --output none 2>/dev/null || echo "Application Insights already exists"

# Get Application Insights instrumentation key
APP_INSIGHTS_KEY=$(az monitor app-insights component show \
    --app $APP_INSIGHTS_NAME \
    --resource-group $RESOURCE_GROUP \
    --query instrumentationKey \
    --output tsv)

# Create Function App with consumption plan
echo -e "${YELLOW}Creating Function App: $FUNCTION_APP_NAME${NC}"
az functionapp create \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --consumption-plan-location $LOCATION \
    --runtime python \
    --runtime-version $PYTHON_VERSION \
    --functions-version 4 \
    --storage-account $STORAGE_ACCOUNT_NAME \
    --os-type Linux \
    --app-insights $APP_INSIGHTS_NAME \
    --app-insights-key "$APP_INSIGHTS_KEY" \
    --output none || echo "Function App already exists"

# Enable managed identity
echo -e "${YELLOW}Enabling managed identity...${NC}"
az functionapp identity assign \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --output none

# Get the principal ID of the managed identity
PRINCIPAL_ID=$(az functionapp identity show \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query principalId \
    --output tsv)

# Create Key Vault if it doesn't exist
echo -e "${YELLOW}Creating Key Vault: $KEY_VAULT_NAME${NC}"
az keyvault create \
    --name $KEY_VAULT_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --enable-soft-delete true \
    --retention-days 7 \
    --enable-purge-protection false \
    --output none 2>/dev/null || echo "Key Vault already exists"

# Grant access to Key Vault for the Function App's managed identity
echo -e "${YELLOW}Granting Key Vault access to Function App...${NC}"
az keyvault set-policy \
    --name $KEY_VAULT_NAME \
    --object-id $PRINCIPAL_ID \
    --secret-permissions get list \
    --output none

# Configure Function App settings
echo -e "${YELLOW}Configuring Function App settings...${NC}"

# Basic settings
az functionapp config appsettings set \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "AzureWebJobsStorage=$STORAGE_CONNECTION_STRING" \
        "FUNCTIONS_WORKER_RUNTIME=python" \
        "FUNCTIONS_EXTENSION_VERSION=~4" \
        "PYTHON_VERSION=$PYTHON_VERSION" \
        "APPINSIGHTS_INSTRUMENTATIONKEY=$APP_INSIGHTS_KEY" \
        "APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=$APP_INSIGHTS_KEY" \
        "AzureWebJobsFeatureFlags=EnableWorkerIndexing" \
    --output none

# Application-specific settings (using Key Vault references where appropriate)
az functionapp config appsettings set \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "OPENAI_API_KEY=@Microsoft.KeyVault(SecretUri=https://$KEY_VAULT_NAME.vault.azure.net/secrets/openai-api-key/)" \
        "DATABASE_URL=@Microsoft.KeyVault(SecretUri=https://$KEY_VAULT_NAME.vault.azure.net/secrets/database-url/)" \
        "ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net" \
        "API_BASE_URL=https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io" \
        "AZURE_CONTAINER_NAME=email-attachments" \
        "AZURE_STORAGE_CONNECTION_STRING=@Microsoft.KeyVault(SecretUri=https://$KEY_VAULT_NAME.vault.azure.net/secrets/storage-connection-string/)" \
    --output none

# Configure CORS if needed
echo -e "${YELLOW}Configuring CORS...${NC}"
az functionapp cors add \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --allowed-origins "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io" \
    --output none 2>/dev/null || true

# Enable HTTPS only
echo -e "${YELLOW}Enabling HTTPS only...${NC}"
az functionapp update \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --set httpsOnly=true \
    --output none

# Set up deployment slots (optional)
echo -e "${YELLOW}Creating staging deployment slot...${NC}"
az functionapp deployment slot create \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --slot staging \
    --configuration-source $FUNCTION_APP_NAME \
    --output none 2>/dev/null || echo "Staging slot already exists"

# Configure monitoring and alerts
echo -e "${YELLOW}Setting up monitoring alerts...${NC}"

# Create action group for alerts
az monitor action-group create \
    --name "FunctionAppAlerts" \
    --resource-group $RESOURCE_GROUP \
    --short-name "FuncAlerts" \
    --output none 2>/dev/null || true

# Create alert for function failures
az monitor metrics alert create \
    --name "well-intake-functions-failures" \
    --resource-group $RESOURCE_GROUP \
    --scopes "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME" \
    --condition "count FailedRequests > 10" \
    --window-size 5m \
    --evaluation-frequency 1m \
    --action "FunctionAppAlerts" \
    --description "Alert when function app has more than 10 failures in 5 minutes" \
    --output none 2>/dev/null || true

echo -e "${GREEN}✓ Function App infrastructure deployed successfully!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Add secrets to Key Vault:"
echo "   az keyvault secret set --vault-name $KEY_VAULT_NAME --name openai-api-key --value '<your-key>'"
echo "   az keyvault secret set --vault-name $KEY_VAULT_NAME --name database-url --value '<your-connection-string>'"
echo "   az keyvault secret set --vault-name $KEY_VAULT_NAME --name storage-connection-string --value '<your-storage-connection>'"
echo ""
echo "2. Deploy your function code:"
echo "   func azure functionapp publish $FUNCTION_APP_NAME --python"
echo "   OR"
echo "   az functionapp deployment source config-zip --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP --src <path-to-zip>"
echo ""
echo "3. Test the function:"
echo "   https://$FUNCTION_APP_NAME.azurewebsites.net/api/<function-name>"
echo ""
echo -e "${GREEN}Deployment complete!${NC}"