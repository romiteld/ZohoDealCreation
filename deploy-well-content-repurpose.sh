#!/bin/bash

#######################################
# Deploy well-content-repurpose to Azure
# Resource Group: TheWell-Infra-East
# Runtime: Python 3.11
#######################################

set -e  # Exit on error

# Configuration
RESOURCE_GROUP="TheWell-Infra-East"
LOCATION="eastus"
FUNCTION_APP_NAME="well-content-repurpose"
STORAGE_ACCOUNT_NAME="wellcontentstorage"
APP_INSIGHTS_NAME="well-functions-insights"  # Shared with well-intake-functions
PLAN_NAME="well-content-plan"
PYTHON_VERSION="3.11"

# Key Vault for secrets
KEY_VAULT_NAME="wellintakekeyvault"  # Shared Key Vault

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting deployment of well-content-repurpose...${NC}"

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

# Create storage account for content function
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

# Create content container in storage account
echo -e "${YELLOW}Creating blob container for content...${NC}"
az storage container create \
    --name "content-repository" \
    --account-name $STORAGE_ACCOUNT_NAME \
    --auth-mode login \
    --output none 2>/dev/null || echo "Container already exists"

az storage container create \
    --name "generated-content" \
    --account-name $STORAGE_ACCOUNT_NAME \
    --auth-mode login \
    --output none 2>/dev/null || echo "Container already exists"

# Get Application Insights key (already created by well-intake-functions)
echo -e "${YELLOW}Getting Application Insights configuration...${NC}"
APP_INSIGHTS_KEY=$(az monitor app-insights component show \
    --app $APP_INSIGHTS_NAME \
    --resource-group $RESOURCE_GROUP \
    --query instrumentationKey \
    --output tsv 2>/dev/null) || {
    # Create Application Insights if it doesn't exist
    echo -e "${YELLOW}Creating Application Insights: $APP_INSIGHTS_NAME${NC}"
    az monitor app-insights component create \
        --app $APP_INSIGHTS_NAME \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --kind web \
        --application-type web \
        --output none
    
    APP_INSIGHTS_KEY=$(az monitor app-insights component show \
        --app $APP_INSIGHTS_NAME \
        --resource-group $RESOURCE_GROUP \
        --query instrumentationKey \
        --output tsv)
}

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

# Grant access to Key Vault for the Function App's managed identity
echo -e "${YELLOW}Granting Key Vault access to Function App...${NC}"
az keyvault set-policy \
    --name $KEY_VAULT_NAME \
    --object-id $PRINCIPAL_ID \
    --secret-permissions get list \
    --output none 2>/dev/null || true

# Grant access to storage account for managed identity
echo -e "${YELLOW}Granting storage account access to Function App...${NC}"
STORAGE_ACCOUNT_ID=$(az storage account show \
    --name $STORAGE_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --query id \
    --output tsv)

az role assignment create \
    --role "Storage Blob Data Contributor" \
    --assignee $PRINCIPAL_ID \
    --scope $STORAGE_ACCOUNT_ID \
    --output none 2>/dev/null || true

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

# Application-specific settings for content generation
az functionapp config appsettings set \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "OPENAI_API_KEY=@Microsoft.KeyVault(SecretUri=https://$KEY_VAULT_NAME.vault.azure.net/secrets/openai-api-key/)" \
        "DATABASE_URL=@Microsoft.KeyVault(SecretUri=https://$KEY_VAULT_NAME.vault.azure.net/secrets/database-url/)" \
        "CONTENT_STORAGE_CONNECTION=$STORAGE_CONNECTION_STRING" \
        "CONTENT_CONTAINER_NAME=content-repository" \
        "GENERATED_CONTENT_CONTAINER=generated-content" \
        "MAX_CONTENT_SIZE_MB=50" \
        "SUPPORTED_FORMATS=pdf,docx,txt,md,html" \
        "CONTENT_GENERATION_MODEL=gpt-4" \
        "CONTENT_TEMPERATURE=0.7" \
    --output none

# Configure CORS for content API access
echo -e "${YELLOW}Configuring CORS...${NC}"
az functionapp cors add \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --allowed-origins "*" \
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

# Configure additional function-specific settings
echo -e "${YELLOW}Configuring content processing settings...${NC}"
az functionapp config appsettings set \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "CONTENT_PROCESSING_QUEUE=content-processing" \
        "CONTENT_OUTPUT_QUEUE=content-output" \
        "MAX_CONCURRENT_JOBS=10" \
        "JOB_TIMEOUT_MINUTES=30" \
        "RETRY_COUNT=3" \
        "RETRY_INTERVAL_SECONDS=60" \
    --output none

# Create queues for content processing
echo -e "${YELLOW}Creating storage queues for content processing...${NC}"
az storage queue create \
    --name "content-processing" \
    --account-name $STORAGE_ACCOUNT_NAME \
    --auth-mode login \
    --output none 2>/dev/null || echo "Queue already exists"

az storage queue create \
    --name "content-output" \
    --account-name $STORAGE_ACCOUNT_NAME \
    --auth-mode login \
    --output none 2>/dev/null || echo "Queue already exists"

# Configure monitoring and alerts specific to content generation
echo -e "${YELLOW}Setting up content-specific monitoring alerts...${NC}"

# Create alert for long-running content generation
az monitor metrics alert create \
    --name "content-generation-duration" \
    --resource-group $RESOURCE_GROUP \
    --scopes "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME" \
    --condition "avg FunctionExecutionTime > 300000" \
    --window-size 15m \
    --evaluation-frequency 5m \
    --action "FunctionAppAlerts" \
    --description "Alert when content generation takes more than 5 minutes on average" \
    --output none 2>/dev/null || true

# Create alert for high queue depth
az monitor metrics alert create \
    --name "content-queue-depth" \
    --resource-group $RESOURCE_GROUP \
    --scopes "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME/queueServices/default" \
    --condition "avg QueueMessageCount > 100" \
    --window-size 5m \
    --evaluation-frequency 1m \
    --action "FunctionAppAlerts" \
    --description "Alert when content processing queue has more than 100 messages" \
    --output none 2>/dev/null || true

echo -e "${GREEN}✓ Content Repurpose Function App infrastructure deployed successfully!${NC}"
echo ""
echo -e "${YELLOW}Function App Details:${NC}"
echo "  Name: $FUNCTION_APP_NAME"
echo "  URL: https://$FUNCTION_APP_NAME.azurewebsites.net"
echo "  Storage: $STORAGE_ACCOUNT_NAME"
echo "  Containers: content-repository, generated-content"
echo "  Queues: content-processing, content-output"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Deploy your function code:"
echo "   cd <your-function-project-directory>"
echo "   func azure functionapp publish $FUNCTION_APP_NAME --python"
echo ""
echo "2. Verify Key Vault secrets are set:"
echo "   - openai-api-key"
echo "   - database-url"
echo ""
echo "3. Test the function endpoints:"
echo "   - HTTP Trigger: https://$FUNCTION_APP_NAME.azurewebsites.net/api/<function-name>"
echo "   - Queue Trigger: Add message to 'content-processing' queue"
echo ""
echo "4. Monitor function execution:"
echo "   - Application Insights: $APP_INSIGHTS_NAME"
echo "   - Function App Logs: az functionapp log tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo -e "${GREEN}Deployment complete!${NC}"