#!/bin/bash

# Web Apps Deployment Script for TheWell-Infra-East
# This script deploys well-zoho-oauth and well-voice-ui web apps

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SUBSCRIPTION_ID="3fee2ac0-3a70-4343-a8b2-3a98da1c9682"
RESOURCE_GROUP="TheWell-Infra-East"
LOCATION="eastus"
APP_PLAN_NAME="TheWell-WebApps-Plan"
APP_PLAN_SKU="B1"  # Change to S1 for production

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if resource exists
resource_exists() {
    local resource_type=$1
    local name=$2
    local rg=$3
    
    if az $resource_type show --name $name --resource-group $rg &>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Main deployment
main() {
    print_status "Starting Web Apps deployment to TheWell-Infra-East..."
    
    # Set subscription
    print_status "Setting Azure subscription..."
    az account set --subscription "$SUBSCRIPTION_ID"
    
    # Verify resource group exists
    print_status "Verifying resource group exists..."
    if ! az group show --name "$RESOURCE_GROUP" &>/dev/null; then
        print_error "Resource group $RESOURCE_GROUP does not exist!"
        exit 1
    fi
    
    # Create App Service Plan if it doesn't exist
    print_status "Checking App Service Plan..."
    if resource_exists "appservice plan" "$APP_PLAN_NAME" "$RESOURCE_GROUP"; then
        print_warning "App Service Plan $APP_PLAN_NAME already exists, skipping creation..."
    else
        print_status "Creating App Service Plan: $APP_PLAN_NAME..."
        az appservice plan create \
            --name "$APP_PLAN_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --location "$LOCATION" \
            --sku "$APP_PLAN_SKU" \
            --is-linux
        print_status "App Service Plan created successfully!"
    fi
    
    # Deploy well-zoho-oauth
    print_status "Deploying well-zoho-oauth..."
    deploy_zoho_oauth
    
    # Deploy well-voice-ui
    print_status "Deploying well-voice-ui..."
    deploy_voice_ui
    
    # Create Application Insights
    print_status "Setting up Application Insights..."
    setup_application_insights
    
    print_status "Deployment completed successfully!"
    print_status "Web Apps URLs:"
    echo "  - well-zoho-oauth: https://well-zoho-oauth.azurewebsites.net"
    echo "  - well-voice-ui: https://well-voice-ui.azurewebsites.net"
}

deploy_zoho_oauth() {
    local APP_NAME="well-zoho-oauth"
    
    if resource_exists "webapp" "$APP_NAME" "$RESOURCE_GROUP"; then
        print_warning "Web App $APP_NAME already exists, updating configuration..."
    else
        print_status "Creating Web App: $APP_NAME..."
        az webapp create \
            --name "$APP_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --plan "$APP_PLAN_NAME" \
            --runtime "NODE:18-lts"
    fi
    
    print_status "Configuring $APP_NAME settings..."
    
    # Configure app settings
    az webapp config appsettings set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --settings \
            NODE_ENV="production" \
            PORT="8080" \
            ZOHO_OAUTH_SERVICE_URL="https://well-zoho-oauth.azurewebsites.net" \
            WEBSITE_NODE_DEFAULT_VERSION="~18"
    
    # Enable HTTPS only
    az webapp update \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --https-only true
    
    # Enable Always On (for B1 tier and above)
    az webapp config set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --always-on true \
        --use-32bit-worker-process false
    
    # Configure CORS
    az webapp cors add \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --allowed-origins "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io" \
        --allowed-origins "https://well-voice-ui.azurewebsites.net"
    
    # Enable diagnostic logs
    az webapp log config \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --application-logging filesystem \
        --level information \
        --web-server-logging filesystem
    
    print_status "$APP_NAME deployed successfully!"
}

deploy_voice_ui() {
    local APP_NAME="well-voice-ui"
    
    if resource_exists "webapp" "$APP_NAME" "$RESOURCE_GROUP"; then
        print_warning "Web App $APP_NAME already exists, updating configuration..."
    else
        print_status "Creating Web App: $APP_NAME..."
        az webapp create \
            --name "$APP_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --plan "$APP_PLAN_NAME" \
            --runtime "NODE:18-lts"
    fi
    
    print_status "Configuring $APP_NAME settings..."
    
    # Configure app settings
    az webapp config appsettings set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --settings \
            NODE_ENV="production" \
            REACT_APP_API_URL="https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io" \
            REACT_APP_OAUTH_URL="https://well-zoho-oauth.azurewebsites.net" \
            WEBSITE_NODE_DEFAULT_VERSION="~18"
    
    # Enable HTTPS only
    az webapp update \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --https-only true
    
    # Enable WebSockets for real-time features
    az webapp config set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --web-sockets-enabled true \
        --always-on true \
        --use-32bit-worker-process false
    
    # Configure CORS for all origins (typical for UI apps)
    az webapp cors add \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --allowed-origins "*"
    
    # Configure for SPA routing
    az webapp config set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --startup-file "pm2 serve /home/site/wwwroot --no-daemon --spa"
    
    # Enable diagnostic logs
    az webapp log config \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --application-logging filesystem \
        --level information \
        --web-server-logging filesystem
    
    print_status "$APP_NAME deployed successfully!"
}

setup_application_insights() {
    local INSIGHTS_NAME="TheWell-AppInsights"
    
    # Check if Application Insights exists
    if az monitor app-insights component show \
        --app "$INSIGHTS_NAME" \
        --resource-group "$RESOURCE_GROUP" &>/dev/null; then
        print_warning "Application Insights $INSIGHTS_NAME already exists..."
    else
        print_status "Creating Application Insights: $INSIGHTS_NAME..."
        az monitor app-insights component create \
            --app "$INSIGHTS_NAME" \
            --location "$LOCATION" \
            --resource-group "$RESOURCE_GROUP" \
            --application-type web \
            --kind web
    fi
    
    # Get instrumentation key
    INSTRUMENTATION_KEY=$(az monitor app-insights component show \
        --app "$INSIGHTS_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query instrumentationKey -o tsv)
    
    # Connect to well-zoho-oauth
    print_status "Connecting Application Insights to well-zoho-oauth..."
    az webapp config appsettings set \
        --name "well-zoho-oauth" \
        --resource-group "$RESOURCE_GROUP" \
        --settings \
            APPINSIGHTS_INSTRUMENTATIONKEY="$INSTRUMENTATION_KEY" \
            APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=$INSTRUMENTATION_KEY"
    
    # Connect to well-voice-ui
    print_status "Connecting Application Insights to well-voice-ui..."
    az webapp config appsettings set \
        --name "well-voice-ui" \
        --resource-group "$RESOURCE_GROUP" \
        --settings \
            APPINSIGHTS_INSTRUMENTATIONKEY="$INSTRUMENTATION_KEY" \
            APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=$INSTRUMENTATION_KEY"
    
    print_status "Application Insights configured successfully!"
}

# Function to deploy code (example for ZIP deployment)
deploy_code() {
    local APP_NAME=$1
    local SOURCE_PATH=$2
    
    if [ ! -d "$SOURCE_PATH" ]; then
        print_warning "Source path $SOURCE_PATH does not exist, skipping code deployment..."
        return
    fi
    
    print_status "Deploying code to $APP_NAME from $SOURCE_PATH..."
    
    # Create deployment package
    cd "$SOURCE_PATH"
    zip -r "../${APP_NAME}.zip" . -x "*.git*" -x "node_modules/*" -x ".env*"
    
    # Deploy
    az webapp deployment source config-zip \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --src "../${APP_NAME}.zip"
    
    # Clean up
    rm "../${APP_NAME}.zip"
    
    print_status "Code deployed to $APP_NAME successfully!"
}

# Function to test web apps
test_deployment() {
    print_status "Testing deployments..."
    
    # Test well-zoho-oauth
    print_status "Testing well-zoho-oauth..."
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://well-zoho-oauth.azurewebsites.net/)
    if [ "$RESPONSE" -eq 200 ] || [ "$RESPONSE" -eq 404 ]; then
        print_status "well-zoho-oauth is responding (HTTP $RESPONSE)"
    else
        print_warning "well-zoho-oauth returned HTTP $RESPONSE"
    fi
    
    # Test well-voice-ui
    print_status "Testing well-voice-ui..."
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://well-voice-ui.azurewebsites.net/)
    if [ "$RESPONSE" -eq 200 ] || [ "$RESPONSE" -eq 404 ]; then
        print_status "well-voice-ui is responding (HTTP $RESPONSE)"
    else
        print_warning "well-voice-ui returned HTTP $RESPONSE"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --deploy-code)
            DEPLOY_CODE=true
            shift
            ;;
        --test)
            TEST_ONLY=true
            shift
            ;;
        --sku)
            APP_PLAN_SKU="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --deploy-code    Deploy code from local directories"
            echo "  --test          Only test existing deployments"
            echo "  --sku SKU       App Service Plan SKU (default: B1)"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main or test based on arguments
if [ "$TEST_ONLY" = true ]; then
    test_deployment
else
    main
    test_deployment
    
    # Optionally deploy code
    if [ "$DEPLOY_CODE" = true ]; then
        print_status "Deploying code packages..."
        # Update these paths to your actual source code locations
        # deploy_code "well-zoho-oauth" "/path/to/well-zoho-oauth"
        # deploy_code "well-voice-ui" "/path/to/well-voice-ui"
        print_warning "Please update the source paths in the script to deploy code"
    fi
fi