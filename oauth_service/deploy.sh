#!/bin/bash

# OAuth Service Reverse Proxy Deployment Script
# Deploys to Azure App Service: well-zoho-oauth

set -e

echo "================================================"
echo "OAuth Service Reverse Proxy Deployment"
echo "================================================"

# Configuration
RESOURCE_GROUP="TheWell-Infra-East"
APP_NAME="well-zoho-oauth"
DEPLOYMENT_DIR="oauth_proxy_deploy"

# Clean up any previous deployment directory
if [ -d "$DEPLOYMENT_DIR" ]; then
    echo "Cleaning up previous deployment directory..."
    rm -rf "$DEPLOYMENT_DIR"
fi

# Create deployment directory
echo "Creating deployment package..."
mkdir -p "$DEPLOYMENT_DIR"

# Copy application files
echo "Copying application files..."
cp oauth_app_with_proxy.py "$DEPLOYMENT_DIR/"
cp requirements.txt "$DEPLOYMENT_DIR/"
cp startup.txt "$DEPLOYMENT_DIR/"

# Copy .env.local from parent directory if it exists
if [ -f "../.env.local" ]; then
    echo "Copying .env.local from parent directory..."
    cp ../.env.local "$DEPLOYMENT_DIR/"
elif [ -f ".env.local" ]; then
    echo "Copying .env.local from current directory..."
    cp .env.local "$DEPLOYMENT_DIR/"
else
    echo "WARNING: .env.local not found! The service will need environment variables configured in Azure."
fi

# Create deployment zip
cd "$DEPLOYMENT_DIR"
echo "Creating deployment ZIP package..."
zip -r ../oauth_proxy_deploy.zip . -x "*.pyc" -x "__pycache__/*"
cd ..

echo "Deployment package created: oauth_proxy_deploy.zip"

# Deploy to Azure (requires Azure CLI)
if command -v az &> /dev/null; then
    echo ""
    echo "Deploying to Azure App Service..."
    
    # Deploy the ZIP package
    az webapp deployment source config-zip \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_NAME" \
        --src oauth_proxy_deploy.zip
    
    # Set Python version
    echo "Configuring Python version..."
    az webapp config set \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_NAME" \
        --linux-fx-version "PYTHON|3.11"
    
    # Set startup command
    echo "Setting startup command..."
    az webapp config set \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_NAME" \
        --startup-file "startup.txt"
    
    # Restart the app
    echo "Restarting App Service..."
    az webapp restart \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_NAME"
    
    echo ""
    echo "================================================"
    echo "Deployment completed successfully!"
    echo "Service URL: https://${APP_NAME}.azurewebsites.net"
    echo "================================================"
    
    # Test the deployment
    echo ""
    echo "Testing deployment..."
    sleep 10  # Wait for app to start
    
    HEALTH_URL="https://${APP_NAME}.azurewebsites.net/health"
    echo "Checking health endpoint: $HEALTH_URL"
    curl -s "$HEALTH_URL" | python -m json.tool || echo "Health check failed - app may still be starting"
    
else
    echo ""
    echo "Azure CLI not found. Please deploy manually using:"
    echo "  1. Upload oauth_proxy_deploy.zip to Azure App Service"
    echo "  2. Configure environment variables from .env.local"
    echo "  3. Set startup command to: gunicorn --bind=0.0.0.0 --timeout 600 oauth_app_with_proxy:app"
fi

# Clean up
echo ""
echo "Cleaning up temporary files..."
rm -rf "$DEPLOYMENT_DIR"

echo "Deployment script completed!"