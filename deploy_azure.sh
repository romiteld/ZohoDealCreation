#!/bin/bash

# Azure Deployment Script for Well Intake API
# This script creates a deployment package and deploys to Azure

echo "=========================================="
echo "Azure Deployment for Well Intake API"
echo "Date: $(date)"
echo "=========================================="

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
RESOURCE_GROUP="TheWell-App-East"
APP_NAME="well-intake-api"
ZIP_FILE="deploy.zip"

echo -e "${YELLOW}Step 1: Cleaning previous deployment artifacts...${NC}"
rm -f $ZIP_FILE
rm -rf __pycache__ app/__pycache__ .pytest_cache

echo -e "${YELLOW}Step 2: Creating deployment package...${NC}"
# Create deployment with specific files and folders
zip -r $ZIP_FILE . \
    -x "zoho/*" \
    -x "*.pyc" \
    -x "__pycache__/*" \
    -x ".env*" \
    -x "*.git*" \
    -x "deploy.zip" \
    -x "test_*.py" \
    -x "server.log" \
    -x ".vscode/*" \
    -x ".idea/*" \
    -x "*.swp" \
    -x "*.swo" \
    -x "venv/*" \
    -x ".DS_Store" \
    -x "logs/*" \
    -x "temp/*" \
    -x "*.bak" \
    -x "*.tmp"

echo -e "${GREEN}Deployment package created: $ZIP_FILE ($(du -h $ZIP_FILE | cut -f1))${NC}"

echo -e "${YELLOW}Step 3: Deploying to Azure...${NC}"
az webapp deploy \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --src-path $ZIP_FILE \
    --type zip \
    --async false

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Deployment successful!${NC}"
    
    echo -e "${YELLOW}Step 4: Restarting app service...${NC}"
    az webapp restart --resource-group $RESOURCE_GROUP --name $APP_NAME
    
    echo -e "${YELLOW}Step 5: Waiting for app to start...${NC}"
    sleep 30
    
    echo -e "${YELLOW}Step 6: Checking health endpoint...${NC}"
    HEALTH_URL="https://${APP_NAME}.azurewebsites.net/health"
    
    for i in {1..10}; do
        echo -e "Attempt $i/10..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)
        
        if [ "$HTTP_CODE" = "200" ]; then
            echo -e "${GREEN}✓ Health check passed! App is running.${NC}"
            break
        else
            echo -e "${YELLOW}Health check returned: $HTTP_CODE. Waiting...${NC}"
            sleep 10
        fi
    done
    
    echo -e "${GREEN}=========================================="
    echo -e "Deployment Complete!"
    echo -e "App URL: https://${APP_NAME}.azurewebsites.net"
    echo -e "Health: https://${APP_NAME}.azurewebsites.net/health"
    echo -e "API Docs: https://${APP_NAME}.azurewebsites.net/docs"
    echo -e "==========================================${NC}"
    
    echo -e "${YELLOW}To view logs:${NC}"
    echo "az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
    
else
    echo -e "${RED}✗ Deployment failed!${NC}"
    echo -e "${YELLOW}Check logs with:${NC}"
    echo "az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
    exit 1
fi