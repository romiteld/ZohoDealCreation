#!/bin/bash

# Optimized Docker build and push script
# Uses buildx for better caching and multi-platform support

REGISTRY="wellintakeregistry.azurecr.io"
REPOSITORY="well-intake-api"
TAG="${1:-latest}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}Optimized Docker Build Script${NC}"
echo "Registry: $REGISTRY"
echo "Repository: $REPOSITORY"
echo "Tag: $TAG"
echo ""

# Login to Azure Container Registry
echo -e "${YELLOW}Logging into Azure Container Registry...${NC}"
az acr login --name wellintakeregistry

# Build with Docker buildx for better caching
echo -e "${YELLOW}Building Docker image with optimization...${NC}"

# Create builder if it doesn't exist
docker buildx create --name azurebuilder --use 2>/dev/null || docker buildx use azurebuilder

# Build and push with cache
docker buildx build \
    --platform linux/amd64 \
    --cache-from type=registry,ref=$REGISTRY/$REPOSITORY:buildcache \
    --cache-to type=registry,ref=$REGISTRY/$REPOSITORY:buildcache,mode=max \
    --tag $REGISTRY/$REPOSITORY:$TAG \
    --push \
    .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Build and push successful!${NC}"
    
    # Also update latest tag if not building latest
    if [ "$TAG" != "latest" ]; then
        echo -e "${YELLOW}Updating 'latest' tag...${NC}"
        docker buildx imagetools create \
            --tag $REGISTRY/$REPOSITORY:latest \
            $REGISTRY/$REPOSITORY:$TAG
    fi
    
    # Show image details
    echo ""
    echo -e "${BLUE}Image Details:${NC}"
    az acr repository show --name wellintakeregistry --image $REPOSITORY:$TAG --output table
    
    # Show image layers and size
    echo ""
    echo -e "${BLUE}Image Manifest:${NC}"
    az acr repository show-manifests --name wellintakeregistry --repository $REPOSITORY --detail --query "[?tags[?contains(@, '$TAG')]]" --output table
else
    echo -e "${RED}✗ Build failed!${NC}"
    exit 1
fi