#!/bin/bash

# Azure Resource Cleanup Script - MCPP Subscription
# This script will DELETE ALL resources in the old MCPP subscription
# After migration to Azure Sponsorship subscription is complete

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Subscription details
OLD_SUBSCRIPTION="df2b303d-1082-421f-a56d-a5dfc714309f"
OLD_RG="TheWell-Infra-East"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  MCPP SUBSCRIPTION CLEANUP SCRIPT${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${YELLOW}WARNING: This will DELETE ALL resources in:${NC}"
echo -e "${YELLOW}Subscription: MCPP Subscription (${OLD_SUBSCRIPTION})${NC}"
echo -e "${YELLOW}Resource Group: ${OLD_RG}${NC}"
echo ""

# Verify we're in the right subscription
echo -e "${BLUE}Setting subscription context...${NC}"
az account set --subscription "$OLD_SUBSCRIPTION"

# Show what will be deleted
echo -e "${BLUE}Resources that will be DELETED:${NC}"
az resource list --resource-group "$OLD_RG" --query "[].{Name:name,Type:type}" -o table

echo ""
echo -e "${RED}⚠️  FINAL CONFIRMATION REQUIRED ⚠️${NC}"
echo -e "${RED}This action is IRREVERSIBLE!${NC}"
echo -e "${RED}All data in these resources will be PERMANENTLY LOST!${NC}"
echo ""
read -p "Are you absolutely sure you want to DELETE all resources? Type 'DELETE-ALL-RESOURCES' to proceed: " confirmation

if [ "$confirmation" != "DELETE-ALL-RESOURCES" ]; then
    echo -e "${GREEN}Deletion cancelled. Resources preserved.${NC}"
    exit 0
fi

echo ""
echo -e "${RED}Starting resource deletion...${NC}"

# Create backup log
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BACKUP_DIR="./cleanup-backup-$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

echo -e "${BLUE}Creating final backup of resource configurations...${NC}"

# Export resource list for final record
az resource list --resource-group "$OLD_RG" --query "[].{Name:name,Type:type,Location:location,Id:id}" -o json > "$BACKUP_DIR/deleted-resources.json"

# Delete resources in safe order
echo -e "${BLUE}Phase 1: Deleting Web Apps and Function Apps...${NC}"
az functionapp delete --name well-intake-functions --resource-group "$OLD_RG" --yes || echo "Function app already gone"
az functionapp delete --name well-content-repurpose --resource-group "$OLD_RG" --yes || echo "Function app already gone"
az webapp delete --name well-voice-ui --resource-group "$OLD_RG" || echo "Web app already gone"
az webapp delete --name well-zoho-oauth --resource-group "$OLD_RG" || echo "Web app already gone"

echo -e "${BLUE}Phase 2: Deleting Container Apps and Environment...${NC}"
az containerapp delete --name well-intake-api --resource-group "$OLD_RG" --yes || echo "Container app already gone"
az containerapp env delete --name well-intake-env-v2 --resource-group "$OLD_RG" --yes || echo "Container env already gone"

echo -e "${BLUE}Phase 3: Deleting Databases and Caches...${NC}"
az postgres flexible-server delete --name well-intake-db --resource-group "$OLD_RG" --yes || echo "Database already gone"
az redis delete --name well-intake-cache-v2 --resource-group "$OLD_RG" --yes || echo "Redis already gone"

echo -e "${BLUE}Phase 4: Deleting Storage Accounts...${NC}"
az storage account delete --name wellintakeattachments --resource-group "$OLD_RG" --yes || echo "Storage already gone"
az storage account delete --name wellintakefunc7151 --resource-group "$OLD_RG" --yes || echo "Storage already gone"
az storage account delete --name wellintakestorage --resource-group "$OLD_RG" --yes || echo "Storage already gone"
az storage account delete --name wellcontentstudio --resource-group "$OLD_RG" --yes || echo "Storage already gone"
az storage account delete --name wellcontentstudio0903 --resource-group "$OLD_RG" --yes || echo "Storage already gone"

echo -e "${BLUE}Phase 5: Deleting Services and Infrastructure...${NC}"
az search service delete --name well-intake-search --resource-group "$OLD_RG" --yes || echo "Search already gone"
az servicebus namespace delete --name well-intake-servicebus --resource-group "$OLD_RG" || echo "Service Bus already gone"
az signalr delete --name well-intake-signalr --resource-group "$OLD_RG" || echo "SignalR already gone"
az acr delete --name wellintakeregistry --resource-group "$OLD_RG" --yes || echo "Registry already gone"

echo -e "${BLUE}Phase 6: Deleting Cognitive Services...${NC}"
az cognitiveservices account delete --name well-speech-service --resource-group "$OLD_RG" || echo "Cognitive service already gone"

echo -e "${BLUE}Phase 7: Deleting App Service Plans...${NC}"
az appservice plan delete --name EastUSPlan --resource-group "$OLD_RG" --yes || echo "Plan already gone"
az appservice plan delete --name daniel.romitelli_asp_3999 --resource-group "$OLD_RG" --yes || echo "Plan already gone"
az appservice plan delete --name EastUSLinuxDynamicPlan --resource-group "$OLD_RG" --yes || echo "Plan already gone"

echo -e "${BLUE}Phase 8: Deleting Network Resources...${NC}"
az network vnet delete --name vnet-1 --resource-group "$OLD_RG" || echo "VNet already gone"
az network nsg delete --name nsg-1 --resource-group "$OLD_RG" || echo "NSG already gone"

echo -e "${BLUE}Phase 9: Deleting Monitoring Resources...${NC}"
az monitor log-analytics workspace delete --workspace-name well-intake-logs --resource-group "$OLD_RG" --yes || echo "Log Analytics already gone"
az monitor log-analytics workspace delete --workspace-name workspace-heellnfraasthGOy --resource-group "$OLD_RG" --yes || echo "Log Analytics already gone"

echo -e "${BLUE}Phase 10: Final cleanup - Delete entire resource group...${NC}"
az group delete --name "$OLD_RG" --yes --no-wait

echo ""
echo -e "${GREEN}✅ Resource deletion initiated!${NC}"
echo -e "${GREEN}Resource group deletion is running in background.${NC}"
echo -e "${GREEN}Backup created in: $BACKUP_DIR${NC}"
echo ""
echo -e "${BLUE}To check deletion status:${NC}"
echo -e "${BLUE}az group show --name $OLD_RG --subscription $OLD_SUBSCRIPTION${NC}"
echo ""
echo -e "${GREEN}Cleanup complete! All MCPP resources scheduled for deletion.${NC}"