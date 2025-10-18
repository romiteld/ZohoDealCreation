#!/bin/bash

#######################################
# Teams Bot Rollback Script
# Version: 1.0.0
# Description: Quick rollback to previous Teams Bot revision
# Usage: ./rollback_teams_bot.sh [revision_name]
#######################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SUBSCRIPTION_ID="3fee2ac0-3a70-4343-a8b2-3a98da1c9682"
RESOURCE_GROUP="TheWell-Infra-East"
CONTAINER_APP_NAME="teams-bot"

print_status() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo "========================================"
echo "Teams Bot Emergency Rollback"
echo "========================================"
echo

# Set Azure subscription
az account set --subscription "$SUBSCRIPTION_ID"

# Get current revision
CURRENT_REVISION=$(az containerapp show \
    -n "$CONTAINER_APP_NAME" \
    -g "$RESOURCE_GROUP" \
    --query "properties.latestRevisionName" -o tsv)

print_status "Current revision: $CURRENT_REVISION"

# List available revisions
print_status "Available revisions:"
az containerapp revision list \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?properties.active].{Name:name, Created:properties.createdTime, Traffic:properties.trafficWeight}" \
    --output table

# Determine target revision
if [ -n "$1" ]; then
    TARGET_REVISION="$1"
    print_status "Using specified revision: $TARGET_REVISION"
elif [ -f /tmp/previous_revision.txt ]; then
    TARGET_REVISION=$(cat /tmp/previous_revision.txt)
    print_status "Using saved previous revision: $TARGET_REVISION"
else
    # Get the previous active revision
    TARGET_REVISION=$(az containerapp revision list \
        --name "$CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "[?properties.active && name!='$CURRENT_REVISION'].name | [0]" \
        -o tsv)

    if [ -z "$TARGET_REVISION" ]; then
        print_error "No previous revision found for rollback"
        exit 1
    fi
    print_status "Using previous active revision: $TARGET_REVISION"
fi

# Confirm rollback
print_warning "This will rollback from $CURRENT_REVISION to $TARGET_REVISION"
read -p "Are you sure you want to continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Rollback cancelled"
    exit 0
fi

# Perform rollback
print_status "Initiating rollback..."

az containerapp ingress traffic set \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --revision-weight "$TARGET_REVISION=100" \
    --output none

print_status "Traffic routed to: $TARGET_REVISION"

# Verify rollback
sleep 10

APP_URL=$(az containerapp show \
    -n "$CONTAINER_APP_NAME" \
    -g "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" -o tsv)

print_status "Verifying rollback..."

# Check health
HEALTH_CHECK=$(curl -s -w "\n%{http_code}" "https://$APP_URL/health" | tail -1)

if [[ "$HEALTH_CHECK" == "200" ]]; then
    print_status "Health check passed ✅"
else
    print_error "Health check failed (HTTP $HEALTH_CHECK)"
fi

# Deactivate problematic revision (optional)
print_warning "Do you want to deactivate the problematic revision $CURRENT_REVISION?"
read -p "Deactivate? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    az containerapp revision deactivate \
        --name "$CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --revision "$CURRENT_REVISION" \
        --output none
    print_status "Revision $CURRENT_REVISION deactivated"
fi

echo
echo "========================================"
print_status "🔄 ROLLBACK COMPLETE! 🔄"
echo "========================================"
echo
print_status "Active revision: $TARGET_REVISION"
print_status "Service URL: https://$APP_URL"
echo
print_status "Next steps:"
echo "  1. Investigate the issue with $CURRENT_REVISION"
echo "  2. Review logs: az containerapp logs show -n $CONTAINER_APP_NAME -g $RESOURCE_GROUP --revision $CURRENT_REVISION"
echo "  3. Fix the issue and redeploy"
echo