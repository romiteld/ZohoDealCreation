#!/bin/bash

# Azure Container Registry cleanup script
# Keeps only the latest 3 production tags and removes old test/development tags

REGISTRY="wellintakeregistry"
REPOSITORY="well-intake-api"

# Tags to always keep
KEEP_TAGS=("v8-microsoft-pattern" "latest" "v6-nested-overrides")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Azure Container Registry Cleanup Script${NC}"
echo "Registry: $REGISTRY"
echo "Repository: $REPOSITORY"
echo ""

# Get all tags
echo -e "${YELLOW}Fetching all tags...${NC}"
ALL_TAGS=$(az acr repository show-tags --name $REGISTRY --repository $REPOSITORY --output tsv)

# Count total tags
TOTAL_TAGS=$(echo "$ALL_TAGS" | wc -l)
echo "Total tags found: $TOTAL_TAGS"
echo ""

# Tags to delete
DELETE_TAGS=()

# Process each tag
while IFS= read -r tag; do
    # Check if tag should be kept
    KEEP=false
    for keep_tag in "${KEEP_TAGS[@]}"; do
        if [[ "$tag" == "$keep_tag" ]]; then
            KEEP=true
            break
        fi
    done
    
    if [ "$KEEP" = false ]; then
        DELETE_TAGS+=("$tag")
    fi
done <<< "$ALL_TAGS"

# Display tags to be deleted
echo -e "${YELLOW}Tags to be deleted (${#DELETE_TAGS[@]} tags):${NC}"
for tag in "${DELETE_TAGS[@]}"; do
    echo "  - $tag"
done
echo ""

# Display tags to keep
echo -e "${GREEN}Tags to keep:${NC}"
for tag in "${KEEP_TAGS[@]}"; do
    echo "  ✓ $tag"
done
echo ""

# Ask for confirmation
read -p "Do you want to proceed with deletion? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deleting old tags...${NC}"
    
    for tag in "${DELETE_TAGS[@]}"; do
        echo -n "Deleting $tag... "
        if az acr repository delete --name $REGISTRY --image $REPOSITORY:$tag --yes 2>/dev/null; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗${NC}"
        fi
    done
    
    echo ""
    echo -e "${GREEN}Cleanup complete!${NC}"
    
    # Show remaining tags
    echo ""
    echo -e "${GREEN}Remaining tags:${NC}"
    az acr repository show-tags --name $REGISTRY --repository $REPOSITORY --output table
else
    echo -e "${YELLOW}Cleanup cancelled.${NC}"
fi

# Show registry size information
echo ""
echo -e "${GREEN}Registry Usage Information:${NC}"
az acr show-usage --name $REGISTRY --output table