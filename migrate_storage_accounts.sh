#!/bin/bash

# Azure Storage Account Migration Script
# Migrates storage accounts from MCPP to Azure Sponsorship
# Date: 2025-01-03

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Azure Storage Account Migration Script ===${NC}"
echo "Migrating from MCPP to Azure Sponsorship subscription"
echo ""

# Configuration
TARGET_SUBSCRIPTION="3fee2ac0-3a70-4343-a8b2-3a98da1c9682"
RESOURCE_GROUP="TheWell-Infra-East"
LOCATION="eastus"
DATE_SUFFIX="0903"

# Storage accounts to create
declare -A STORAGE_ACCOUNTS=(
    ["wellintakestorage${DATE_SUFFIX}"]="Standard_LRS"
    ["wellcontentstudio${DATE_SUFFIX}"]="Standard_LRS"
)

# Set the target subscription
echo -e "${YELLOW}Setting subscription to Azure Sponsorship...${NC}"
az account set --subscription $TARGET_SUBSCRIPTION

# Verify subscription
CURRENT_SUB=$(az account show --query name -o tsv)
echo -e "${GREEN}Current subscription: $CURRENT_SUB${NC}"
echo ""

# Create storage accounts
for STORAGE_NAME in "${!STORAGE_ACCOUNTS[@]}"; do
    SKU="${STORAGE_ACCOUNTS[$STORAGE_NAME]}"
    
    echo -e "${YELLOW}Creating storage account: $STORAGE_NAME${NC}"
    
    # Check if storage account already exists
    EXISTS=$(az storage account check-name-availability --name $STORAGE_NAME --query nameAvailable -o tsv)
    
    if [ "$EXISTS" = "false" ]; then
        echo -e "${YELLOW}Storage account $STORAGE_NAME already exists or name is not available${NC}"
        
        # Check if it exists in our resource group
        EXISTING_RG=$(az storage account show --name $STORAGE_NAME --query resourceGroup -o tsv 2>/dev/null || echo "")
        
        if [ -n "$EXISTING_RG" ]; then
            if [ "$EXISTING_RG" = "$RESOURCE_GROUP" ]; then
                echo -e "${GREEN}Storage account $STORAGE_NAME already exists in resource group $RESOURCE_GROUP${NC}"
            else
                echo -e "${RED}Storage account $STORAGE_NAME exists in different resource group: $EXISTING_RG${NC}"
                echo "Please choose a different name or delete the existing storage account"
                continue
            fi
        else
            echo -e "${RED}Storage account name $STORAGE_NAME is not available globally${NC}"
            continue
        fi
    else
        # Create the storage account
        az storage account create \
            --name $STORAGE_NAME \
            --resource-group $RESOURCE_GROUP \
            --location $LOCATION \
            --sku $SKU \
            --kind StorageV2 \
            --access-tier Hot \
            --https-only true \
            --min-tls-version TLS1_2 \
            --allow-blob-public-access false \
            --tags "Environment=Production" "MigratedFrom=MCPP" "MigrationDate=2025-01-03"
        
        echo -e "${GREEN}✓ Storage account $STORAGE_NAME created successfully${NC}"
    fi
    
    # Get storage account key for container operations
    STORAGE_KEY=$(az storage account keys list --account-name $STORAGE_NAME --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv)
    
    # Create common containers based on the storage account type
    if [[ "$STORAGE_NAME" == "wellintakestorage"* ]]; then
        echo "Creating containers for wellintakestorage..."
        
        # Create email-attachments container (from project requirements)
        az storage container create \
            --name "email-attachments" \
            --account-name $STORAGE_NAME \
            --account-key "$STORAGE_KEY" \
            --public-access off 2>/dev/null || echo "Container email-attachments already exists"
        
        echo -e "${GREEN}✓ Created email-attachments container${NC}"
    fi
    
    if [[ "$STORAGE_NAME" == "wellcontentstudio"* ]]; then
        echo "Creating containers for wellcontentstudio..."
        
        # Create containers for content studio function
        az storage container create \
            --name "content-input" \
            --account-name $STORAGE_NAME \
            --account-key "$STORAGE_KEY" \
            --public-access off 2>/dev/null || echo "Container content-input already exists"
        
        az storage container create \
            --name "content-output" \
            --account-name $STORAGE_NAME \
            --account-key "$STORAGE_KEY" \
            --public-access off 2>/dev/null || echo "Container content-output already exists"
        
        echo -e "${GREEN}✓ Created content containers${NC}"
    fi
    
    echo ""
done

echo -e "${GREEN}=== Migration Summary ===${NC}"
echo ""

# Display storage account endpoints
for STORAGE_NAME in "${!STORAGE_ACCOUNTS[@]}"; do
    echo -e "${YELLOW}Storage Account: $STORAGE_NAME${NC}"
    
    # Get connection string
    CONNECTION_STRING=$(az storage account show-connection-string \
        --name $STORAGE_NAME \
        --resource-group $RESOURCE_GROUP \
        --query connectionString -o tsv)
    
    # Get primary endpoints
    BLOB_ENDPOINT=$(az storage account show \
        --name $STORAGE_NAME \
        --resource-group $RESOURCE_GROUP \
        --query primaryEndpoints.blob -o tsv)
    
    echo "Blob Endpoint: $BLOB_ENDPOINT"
    echo "Connection String: $CONNECTION_STRING"
    echo ""
done

echo -e "${GREEN}=== Next Steps ===${NC}"
echo "1. Update connection strings in dependent services:"
echo "   - Well Intake API (.env.local): AZURE_STORAGE_CONNECTION_STRING"
echo "   - Well Content Repurpose Function: Update app settings"
echo ""
echo "2. Test the new storage accounts:"
echo "   - Upload a test file to verify access"
echo "   - Verify container permissions"
echo ""
echo "3. Migrate data from old storage accounts (if any exists)"
echo ""
echo "4. Update any firewall rules or network restrictions"
echo ""
echo -e "${GREEN}Migration preparation complete!${NC}"