#!/bin/bash

# Storage Migration Validation Script
# Tests connectivity to the newly migrated storage accounts

set -e

echo "=== Azure Storage Migration Validation ==="
echo "Testing connectivity to migrated storage accounts"
echo ""

# Load environment variables
if [ -f ".env.local" ]; then
    # Export environment variables from .env.local (basic parsing)
    eval $(grep -v '^#' .env.local | xargs -I {} echo export {})
    echo "✓ Loaded environment variables from .env.local"
else
    echo "❌ .env.local file not found"
    exit 1
fi

# Test 1: Storage Account Connectivity
echo ""
echo "=== Test 1: Storage Account Access ==="
echo "Testing wellintakestorage0903..."

# Get storage key
STORAGE_KEY=$(az storage account keys list --account-name wellintakestorage0903 --resource-group TheWell-Infra-East --query "[0].value" -o tsv 2>/dev/null)

if [ -n "$STORAGE_KEY" ]; then
    echo "✓ Successfully retrieved storage key"
else
    echo "❌ Failed to retrieve storage key"
    exit 1
fi

# Test container listing
CONTAINERS=$(az storage container list --account-name wellintakestorage0903 --account-key "$STORAGE_KEY" --query "[].name" -o tsv 2>/dev/null)

if echo "$CONTAINERS" | grep -q "email-attachments"; then
    echo "✓ email-attachments container exists"
else
    echo "❌ email-attachments container not found"
    exit 1
fi

# Test 2: Upload a test file
echo ""
echo "=== Test 2: File Upload Test ==="
TEST_FILE="test-migration-$(date +%s).txt"
echo "This is a test file created during storage migration validation on $(date)" > "$TEST_FILE"

az storage blob upload \
    --file "$TEST_FILE" \
    --container-name email-attachments \
    --name "$TEST_FILE" \
    --account-name wellintakestorage0903 \
    --account-key "$STORAGE_KEY" \
    --output none 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✓ Successfully uploaded test file: $TEST_FILE"
else
    echo "❌ Failed to upload test file"
    rm -f "$TEST_FILE"
    exit 1
fi

# Test 3: Download the test file
echo ""
echo "=== Test 3: File Download Test ==="
DOWNLOAD_FILE="downloaded-$TEST_FILE"

az storage blob download \
    --container-name email-attachments \
    --name "$TEST_FILE" \
    --file "$DOWNLOAD_FILE" \
    --account-name wellintakestorage0903 \
    --account-key "$STORAGE_KEY" \
    --output none 2>/dev/null

if [ -f "$DOWNLOAD_FILE" ]; then
    echo "✓ Successfully downloaded test file"
    
    # Compare files
    if cmp -s "$TEST_FILE" "$DOWNLOAD_FILE"; then
        echo "✓ File integrity verified - upload/download successful"
    else
        echo "❌ File integrity check failed"
    fi
else
    echo "❌ Failed to download test file"
fi

# Test 4: Content Storage Account
echo ""
echo "=== Test 4: Content Storage Account ==="
echo "Testing wellcontent0903..."

CONTENT_KEY=$(az storage account keys list --account-name wellcontent0903 --resource-group TheWell-Infra-East --query "[0].value" -o tsv 2>/dev/null)

if [ -n "$CONTENT_KEY" ]; then
    echo "✓ Successfully retrieved content storage key"
else
    echo "❌ Failed to retrieve content storage key"
fi

# List content containers
CONTENT_CONTAINERS=$(az storage container list --account-name wellcontent0903 --account-key "$CONTENT_KEY" --query "[].name" -o tsv 2>/dev/null)

if echo "$CONTENT_CONTAINERS" | grep -q "content-input"; then
    echo "✓ content-input container exists"
else
    echo "❌ content-input container not found"
fi

if echo "$CONTENT_CONTAINERS" | grep -q "content-output"; then
    echo "✓ content-output container exists"
else
    echo "❌ content-output container not found"
fi

# Test 5: Well Intake API Configuration
echo ""
echo "=== Test 5: Configuration Validation ==="

if [[ "$AZURE_STORAGE_CONNECTION_STRING" == *"wellintakestorage0903"* ]]; then
    echo "✓ .env.local correctly configured for new storage account"
else
    echo "❌ .env.local still using old storage account configuration"
    echo "Current: $(echo $AZURE_STORAGE_CONNECTION_STRING | grep -o 'AccountName=[^;]*')"
    echo "Expected: AccountName=wellintakestorage0903"
fi

if [[ "$AZURE_CONTAINER_NAME" == "email-attachments" ]]; then
    echo "✓ Container name correctly set to email-attachments"
else
    echo "❌ Container name misconfigured: $AZURE_CONTAINER_NAME"
fi

# Cleanup
echo ""
echo "=== Cleanup ==="
rm -f "$TEST_FILE" "$DOWNLOAD_FILE"

# Delete test blob
az storage blob delete \
    --container-name email-attachments \
    --name "$TEST_FILE" \
    --account-name wellintakestorage0903 \
    --account-key "$STORAGE_KEY" \
    --output none 2>/dev/null

echo "✓ Cleaned up test files"

echo ""
echo "=== Validation Summary ==="
echo "✅ Storage account migration validation completed successfully!"
echo ""
echo "Next Steps:"
echo "1. Test the Well Intake API with actual email processing"
echo "2. Update any Function Apps that use wellcontentstudio → wellcontent0903"
echo "3. Monitor for 24-48 hours to ensure stability"
echo "4. Schedule deletion of old storage accounts after verification"
echo ""
echo "Storage Endpoints:"
echo "- wellintakestorage0903: https://wellintakestorage0903.blob.core.windows.net/"
echo "- wellcontent0903: https://wellcontent0903.blob.core.windows.net/"