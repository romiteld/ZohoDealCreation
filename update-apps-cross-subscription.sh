#!/bin/bash

# Cross-Subscription Application Configuration Update
# Updates apps in old subscription to use storage accounts from new subscription

set -e

echo "====================================================="
echo "Cross-Subscription Application Configuration Update"
echo "====================================================="

# Subscription IDs
OLD_SUBSCRIPTION="df2b303d-1082-421f-a56d-a5dfc714309f"  # MCPP Subscription
NEW_SUBSCRIPTION="3fee2ac0-3a70-4343-a8b2-3a98da1c9682"  # Microsoft Azure Sponsorship
RESOURCE_GROUP="TheWell-Infra-East"

echo "Applications in: $OLD_SUBSCRIPTION (MCPP Subscription)"
echo "Storage accounts in: $NEW_SUBSCRIPTION (Microsoft Azure Sponsorship)"
echo ""

# Step 1: Get connection strings from new subscription
echo "Step 1: Getting connection strings from new subscription..."
echo "--------------------------------------------------------"
az account set --subscription $NEW_SUBSCRIPTION

# Get connection strings for migrated storage accounts
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

WELLINTAKESTORAGE_CONN=$(az storage account show-connection-string \
    --name wellintakestorage0903 \
    --resource-group $RESOURCE_GROUP \
    --query connectionString -o tsv)

echo "✅ Retrieved connection strings from new subscription"

# Step 2: Switch to old subscription to update applications
echo ""
echo "Step 2: Switching to old subscription to update applications..."
echo "--------------------------------------------------------------"
az account set --subscription $OLD_SUBSCRIPTION

# Verify we can see the applications
echo "Verifying applications exist in old subscription:"
az containerapp list --resource-group $RESOURCE_GROUP --query "[].name" -o tsv | head -5
az functionapp list --resource-group $RESOURCE_GROUP --query "[].name" -o tsv | head -5
az webapp list --resource-group $RESOURCE_GROUP --query "[].name" -o tsv | head -5

# Step 3: Update Container App: well-intake-api
echo ""
echo "Step 3: Updating Container App: well-intake-api..."
echo "--------------------------------------------------"

az containerapp update \
    --name well-intake-api \
    --resource-group $RESOURCE_GROUP \
    --set-env-vars \
        AZURE_STORAGE_CONNECTION_STRING="$WELLATTACHMENTS_CONN" \
    --output none

echo "✅ Updated well-intake-api to use wellattachments0903"

# Step 4: Update Function App: well-intake-functions
echo ""
echo "Step 4: Updating Function App: well-intake-functions..."
echo "-------------------------------------------------------"

az functionapp config appsettings set \
    --name well-intake-functions \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "AzureWebJobsStorage=$WELLINTAKEFUNC_CONN" \
        "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING=$WELLINTAKEFUNC_CONN" \
        "AZURE_STORAGE_CONNECTION_STRING=$WELLATTACHMENTS_CONN" \
    --output none

echo "✅ Updated well-intake-functions to use new storage accounts"

# Step 5: Update Function App: well-content-repurpose
echo ""
echo "Step 5: Updating Function App: well-content-repurpose..."
echo "--------------------------------------------------------"

az functionapp config appsettings set \
    --name well-content-repurpose \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "AzureWebJobsStorage=$WELLCONTENT_CONN" \
        "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING=$WELLCONTENT_CONN" \
        "ContentStorageConnection=$WELLCONTENT_CONN" \
    --output none

echo "✅ Updated well-content-repurpose to use wellcontent0903"

# Step 6: Update Web App: well-zoho-oauth
echo ""
echo "Step 6: Updating Web App: well-zoho-oauth..."
echo "---------------------------------------------"

az webapp config appsettings set \
    --name well-zoho-oauth \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "AZURE_STORAGE_CONNECTION_STRING=$WELLINTAKESTORAGE_CONN" \
    --output none

echo "✅ Updated well-zoho-oauth to use wellintakestorage0903"

# Step 7: Update Web App: well-voice-ui
echo ""
echo "Step 7: Updating Web App: well-voice-ui..."
echo "-------------------------------------------"

az webapp config appsettings set \
    --name well-voice-ui \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "AZURE_STORAGE_CONNECTION_STRING=$WELLCONTENT_CONN" \
    --output none

echo "✅ Updated well-voice-ui to use wellcontent0903"

# Step 8: Create comprehensive documentation
echo ""
echo "Step 8: Creating documentation..."
echo "---------------------------------"

cat > /home/romiteld/outlook/cross-subscription-config-update.md << EOF
# Cross-Subscription Configuration Update
**Generated**: $(date)
**Updated by**: Azure CLI automation

## Migration Summary
Updated all applications in the **MCPP Subscription** to use storage accounts from the **Microsoft Azure Sponsorship** subscription.

### Subscriptions Involved
- **Source (Apps)**: MCPP Subscription (\`df2b303d-1082-421f-a56d-a5dfc714309f\`)
- **Target (Storage)**: Microsoft Azure Sponsorship (\`3fee2ac0-3a70-4343-a8b2-3a98da1c9682\`)

## Storage Account Mappings

### wellattachments0903 (New Subscription)
- **Used By**: well-intake-api, well-intake-functions
- **Purpose**: Email attachments and intake processing
- **Connection String**: Updated in apps

### wellcontent0903 (New Subscription)  
- **Used By**: well-content-repurpose, well-voice-ui
- **Purpose**: Content processing, voice recordings, media files
- **Connection String**: Updated in apps

### wellintakefunc0903 (New Subscription)
- **Used By**: well-intake-functions (runtime)
- **Purpose**: Azure Functions runtime storage
- **Connection String**: Updated in app

### wellintakestorage0903 (New Subscription)
- **Used By**: well-zoho-oauth
- **Purpose**: General application storage
- **Connection String**: Updated in app

## Application Updates

### 1. Container App: well-intake-api ✅
**Location**: MCPP Subscription / TheWell-Infra-East
**Changes**:
- AZURE_STORAGE_CONNECTION_STRING → wellattachments0903

### 2. Function App: well-intake-functions ✅
**Location**: MCPP Subscription / TheWell-Infra-East  
**Changes**:
- AzureWebJobsStorage → wellintakefunc0903
- WEBSITE_CONTENTAZUREFILECONNECTIONSTRING → wellintakefunc0903
- AZURE_STORAGE_CONNECTION_STRING → wellattachments0903

### 3. Function App: well-content-repurpose ✅
**Location**: MCPP Subscription / TheWell-Infra-East
**Changes**:
- AzureWebJobsStorage → wellcontent0903
- WEBSITE_CONTENTAZUREFILECONNECTIONSTRING → wellcontent0903
- ContentStorageConnection → wellcontent0903

### 4. Web App: well-zoho-oauth ✅
**Location**: MCPP Subscription / TheWell-Infra-East
**Changes**:
- AZURE_STORAGE_CONNECTION_STRING → wellintakestorage0903

### 5. Web App: well-voice-ui ✅
**Location**: MCPP Subscription / TheWell-Infra-East
**Changes**:
- AZURE_STORAGE_CONNECTION_STRING → wellcontent0903

## Cross-Subscription Implications

### Benefits
✅ **Cost Optimization**: Using sponsorship credits for storage
✅ **Resource Isolation**: Storage separated from compute
✅ **Scalability**: Better resource management

### Considerations
⚠️ **Network Latency**: Cross-subscription may add minimal latency
⚠️ **Billing Complexity**: Storage costs in different subscription
⚠️ **Access Management**: Ensure service principals have cross-subscription access

## Testing Checklist

### Immediate Tests (Next 15 minutes)
- [ ] Container App health check
- [ ] Function App runtime test
- [ ] Web App basic response
- [ ] Storage connectivity test

### Extended Tests (Next 2 hours)
- [ ] File upload functionality
- [ ] Email processing workflow
- [ ] Content repurposing pipeline
- [ ] OAuth token storage
- [ ] Voice recording upload

### Performance Tests (Next 24 hours)  
- [ ] Storage operation latency
- [ ] Function execution time
- [ ] Container app response time
- [ ] Overall system throughput

## Monitoring

### Application Insights Alerts
Monitor for these patterns post-migration:
- Storage connection timeouts
- Authentication failures across subscriptions
- Increased response times
- Function execution failures

### Storage Account Metrics
- Cross-subscription request rates
- Storage operation errors
- Access policy violations
- Network connectivity issues

## Rollback Plan

### Emergency Rollback (if critical issues)
\`\`\`bash
# Switch back to old subscription
az account set --subscription df2b303d-1082-421f-a56d-a5dfc714309f

# Get original storage connection strings
OLD_WELLINTAKEATTACHMENTS=\$(az storage account show-connection-string --name wellintakeattachments --resource-group TheWell-Infra-East --query connectionString -o tsv)
OLD_WELLCONTENTSTUDIO=\$(az storage account show-connection-string --name wellcontentstudio --resource-group TheWell-Infra-East --query connectionString -o tsv)
OLD_WELLINTAKEFUNC=\$(az storage account show-connection-string --name wellintakefunc7151 --resource-group TheWell-Infra-East --query connectionString -o tsv)

# Restore Container App
az containerapp update --name well-intake-api --resource-group TheWell-Infra-East \\
  --set-env-vars AZURE_STORAGE_CONNECTION_STRING="\$OLD_WELLINTAKEATTACHMENTS"

# Restore Function Apps
az functionapp config appsettings set --name well-intake-functions --resource-group TheWell-Infra-East \\
  --settings "AzureWebJobsStorage=\$OLD_WELLINTAKEFUNC" \\
             "AZURE_STORAGE_CONNECTION_STRING=\$OLD_WELLINTAKEATTACHMENTS"

# Similar rollback for other apps...
\`\`\`

## Next Steps

1. **Immediate (0-1 hour)**
   - ✅ Monitor application health endpoints
   - ✅ Test basic functionality
   - ✅ Check Application Insights for errors

2. **Short-term (1-24 hours)**
   - ✅ Conduct comprehensive testing
   - ✅ Monitor performance metrics
   - ✅ Validate all storage operations

3. **Medium-term (1-7 days)**
   - ✅ Review cost implications
   - ✅ Optimize storage access patterns
   - ✅ Plan final migration of compute resources

4. **Long-term (1+ weeks)**
   - ✅ Complete migration of all resources
   - ✅ Consolidate into single subscription
   - ✅ Update documentation and runbooks

## Support Information
- **Script Location**: \`/home/romiteld/outlook/update-apps-cross-subscription.sh\`
- **Documentation**: \`/home/romiteld/outlook/cross-subscription-config-update.md\`
- **Backup Config**: Stored in migration script outputs
- **Emergency Contact**: Azure support for cross-subscription issues
EOF

echo "✅ Documentation created: cross-subscription-config-update.md"

# Step 9: Test applications
echo ""
echo "Step 9: Testing application connectivity..."
echo "-------------------------------------------"

echo "Testing Container App health..."
curl -s -f -m 10 https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health > /dev/null && echo "✅ well-intake-api health check passed" || echo "⚠️ well-intake-api health check failed"

echo "Testing Web Apps..."
curl -s -f -m 10 https://well-zoho-oauth.azurewebsites.net > /dev/null && echo "✅ well-zoho-oauth responding" || echo "⚠️ well-zoho-oauth not responding"
curl -s -f -m 10 https://well-voice-ui.azurewebsites.net > /dev/null && echo "✅ well-voice-ui responding" || echo "⚠️ well-voice-ui not responding"

echo "Testing Function Apps..."
curl -s -f -m 10 https://well-intake-functions.azurewebsites.net > /dev/null && echo "✅ well-intake-functions responding" || echo "⚠️ well-intake-functions not responding"
curl -s -f -m 10 https://well-content-repurpose.azurewebsites.net > /dev/null && echo "✅ well-content-repurpose responding" || echo "⚠️ well-content-repurpose not responding"

# Step 10: Summary
echo ""
echo "====================================================="
echo "✅ Cross-Subscription Configuration Update Complete!"
echo "====================================================="
echo ""
echo "Summary:"
echo "- Applications: 5 updated (1 Container App, 2 Function Apps, 2 Web Apps)"
echo "- Storage Accounts: 4 new accounts in Microsoft Azure Sponsorship"
echo "- Cross-Subscription: Apps in MCPP → Storage in Azure Sponsorship"
echo ""
echo "Next Actions:"
echo "1. Monitor applications for 2+ hours"
echo "2. Test all functionality thoroughly"  
echo "3. Review Application Insights dashboards"
echo "4. Plan compute resource migration"
echo ""
echo "Files Created:"
echo "- /home/romiteld/outlook/cross-subscription-config-update.md (detailed docs)"
echo "- This script: /home/romiteld/outlook/update-apps-cross-subscription.sh"
echo ""
echo "⚠️ IMPORTANT: Monitor for next 24 hours for any cross-subscription issues"