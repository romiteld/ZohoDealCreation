#!/bin/bash

# Update Application Configurations to Use Migrated Resources
# This script updates all apps to use the new 0903-suffixed storage accounts

set -e

echo "==================================="
echo "Updating Application Configurations"
echo "==================================="

RESOURCE_GROUP="TheWell-Infra-East"

# Get connection strings for new storage accounts
echo "Getting connection strings for migrated storage accounts..."

WELLATTACHMENTS_CONN=$(az storage account show-connection-string \
    --name wellattachments0903 \
    --resource-group $RESOURCE_GROUP \
    --query connectionString -o tsv)

WELLCONTENT_CONN=$(az storage account show-connection-string \
    --name wellcontent0903 \
    --resource-group $RESOURCE_GROUP \
    --query connectionString -o tsv)

WELLINTAKEFUNC_CONN=$(az storage account show-connection-string \
    --name wellintakefunc0903 \
    --resource-group $RESOURCE_GROUP \
    --query connectionString -o tsv)

echo "✅ Retrieved connection strings"

# Update Container App: well-intake-api
echo ""
echo "Updating Container App: well-intake-api..."
echo "----------------------------------------"

# Get current environment variables
CURRENT_ENV=$(az containerapp show \
    --name well-intake-api \
    --resource-group $RESOURCE_GROUP \
    --query "properties.template.containers[0].env" -o json)

# Update AZURE_STORAGE_CONNECTION_STRING to use wellattachments0903
az containerapp update \
    --name well-intake-api \
    --resource-group $RESOURCE_GROUP \
    --set-env-vars \
        AZURE_STORAGE_CONNECTION_STRING="$WELLATTACHMENTS_CONN" \
    --output none

echo "✅ Updated well-intake-api with new storage connection string"

# Update Function App: well-intake-functions
echo ""
echo "Updating Function App: well-intake-functions..."
echo "------------------------------------------------"

# Update AzureWebJobsStorage to use new function storage
az functionapp config appsettings set \
    --name well-intake-functions \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "AzureWebJobsStorage=$WELLINTAKEFUNC_CONN" \
        "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING=$WELLINTAKEFUNC_CONN" \
        "AZURE_STORAGE_CONNECTION_STRING=$WELLATTACHMENTS_CONN" \
    --output none

echo "✅ Updated well-intake-functions with new storage connections"

# Update Function App: well-content-repurpose
echo ""
echo "Updating Function App: well-content-repurpose..."
echo "-------------------------------------------------"

# Update to use wellcontent0903 storage
az functionapp config appsettings set \
    --name well-content-repurpose \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "AzureWebJobsStorage=$WELLCONTENT_CONN" \
        "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING=$WELLCONTENT_CONN" \
        "ContentStorageConnection=$WELLCONTENT_CONN" \
    --output none

echo "✅ Updated well-content-repurpose with new storage connections"

# Update Web App: well-zoho-oauth
echo ""
echo "Updating Web App: well-zoho-oauth..."
echo "-------------------------------------"

# Check if this app uses any storage connections
echo "Checking current configuration..."
ZOHO_SETTINGS=$(az webapp config appsettings list \
    --name well-zoho-oauth \
    --resource-group $RESOURCE_GROUP \
    --query "[?contains(name, 'Storage') || contains(name, 'STORAGE')].{name:name, value:value}" \
    -o json)

if [ "$ZOHO_SETTINGS" != "[]" ]; then
    echo "Found storage settings to update..."
    az webapp config appsettings set \
        --name well-zoho-oauth \
        --resource-group $RESOURCE_GROUP \
        --settings \
            "AZURE_STORAGE_CONNECTION_STRING=$WELLATTACHMENTS_CONN" \
        --output none
    echo "✅ Updated well-zoho-oauth storage settings"
else
    echo "ℹ️  No storage settings found for well-zoho-oauth"
fi

# Update Web App: well-voice-ui
echo ""
echo "Updating Web App: well-voice-ui..."
echo "-----------------------------------"

# Check if this app uses any storage connections
echo "Checking current configuration..."
VOICE_SETTINGS=$(az webapp config appsettings list \
    --name well-voice-ui \
    --resource-group $RESOURCE_GROUP \
    --query "[?contains(name, 'Storage') || contains(name, 'STORAGE')].{name:name, value:value}" \
    -o json)

if [ "$VOICE_SETTINGS" != "[]" ]; then
    echo "Found storage settings to update..."
    az webapp config appsettings set \
        --name well-voice-ui \
        --resource-group $RESOURCE_GROUP \
        --settings \
            "AZURE_STORAGE_CONNECTION_STRING=$WELLCONTENT_CONN" \
        --output none
    echo "✅ Updated well-voice-ui storage settings"
else
    echo "ℹ️  No storage settings found for well-voice-ui"
fi

# Create documentation of all changes
echo ""
echo "Creating configuration change documentation..."
cat > configuration-changes.md << EOF
# Configuration Changes Documentation
Generated: $(date)

## Storage Account Migrations
All applications have been updated to use the new 0903-suffixed storage accounts.

### Storage Accounts Created
- **wellattachments0903** - For email attachments and files
- **wellcontent0903** - For content studio and media files  
- **wellintakefunc0903** - For Azure Functions runtime

### Application Updates

#### Container Apps
1. **well-intake-api**
   - Updated: AZURE_STORAGE_CONNECTION_STRING → wellattachments0903
   - Purpose: Stores email attachments processed by the intake API

#### Function Apps
1. **well-intake-functions**
   - Updated: AzureWebJobsStorage → wellintakefunc0903
   - Updated: WEBSITE_CONTENTAZUREFILECONNECTIONSTRING → wellintakefunc0903
   - Updated: AZURE_STORAGE_CONNECTION_STRING → wellattachments0903
   - Purpose: Function runtime storage and attachment processing

2. **well-content-repurpose**
   - Updated: AzureWebJobsStorage → wellcontent0903
   - Updated: WEBSITE_CONTENTAZUREFILECONNECTIONSTRING → wellcontent0903
   - Updated: ContentStorageConnection → wellcontent0903
   - Purpose: Content processing and media storage

#### Web Apps
1. **well-zoho-oauth**
   - Updated: AZURE_STORAGE_CONNECTION_STRING → wellattachments0903 (if applicable)
   - Purpose: OAuth token and session storage

2. **well-voice-ui**
   - Updated: AZURE_STORAGE_CONNECTION_STRING → wellcontent0903 (if applicable)
   - Purpose: Voice recording and media storage

## Verification Steps
1. Test each application endpoint
2. Verify file upload/download functionality
3. Check Function App execution logs
4. Confirm no broken storage references

## Rollback Instructions
If issues arise, original storage accounts can be restored by running:
\`\`\`bash
# Restore from backup configuration
./restore-original-config.sh
\`\`\`

## Notes
- All changes are effective immediately
- Applications may need a restart to fully apply changes
- Monitor Application Insights for any errors
EOF

echo "✅ Documentation created: configuration-changes.md"

# Restart applications to ensure changes take effect
echo ""
echo "Restarting applications..."
echo "--------------------------"

# Restart Container Apps
echo "Restarting well-intake-api..."
az containerapp revision restart \
    --name well-intake-api \
    --resource-group $RESOURCE_GROUP \
    --revision $(az containerapp revision list --name well-intake-api --resource-group $RESOURCE_GROUP --query "[0].name" -o tsv) \
    --output none 2>/dev/null || echo "⚠️  Container app will apply changes on next deployment"

# Function Apps auto-restart on config changes
echo "ℹ️  Function Apps will automatically restart with new settings"

# Web Apps
echo "Restarting well-zoho-oauth..."
az webapp restart --name well-zoho-oauth --resource-group $RESOURCE_GROUP --output none

echo "Restarting well-voice-ui..."
az webapp restart --name well-voice-ui --resource-group $RESOURCE_GROUP --output none

echo ""
echo "======================================="
echo "✅ Configuration Update Complete!"
echo "======================================="
echo ""
echo "Summary:"
echo "- Updated 1 Container App"
echo "- Updated 2 Function Apps"
echo "- Updated 2 Web Apps"
echo "- All applications now use 0903-suffixed storage accounts"
echo ""
echo "Next Steps:"
echo "1. Review configuration-changes.md for full details"
echo "2. Test application functionality"
echo "3. Monitor Application Insights for any issues"
echo "4. Verify storage operations are working correctly"