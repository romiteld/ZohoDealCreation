#!/bin/bash

# Manual Deployment Script - Alternative to GitHub Actions
# This script can be run locally when GitHub Actions are not configured

set -e

echo "🚀 Well Intake API - Manual Deployment Script"
echo "============================================="

# Configuration
REGISTRY="wellintakeacr0903.azurecr.io"
IMAGE_NAME="well-intake-api"
CONTAINER_APP="well-intake-api"
RESOURCE_GROUP="TheWell-Infra-East"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v az &> /dev/null; then
    print_error "Azure CLI not found. Please install it first."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    print_error "Docker not found. Please install it first."
    exit 1
fi

print_status "Prerequisites checked"

# Azure login check
echo ""
echo "🔐 Checking Azure authentication..."
if ! az account show &> /dev/null; then
    print_warning "Not logged in to Azure. Please login:"
    az login
fi
print_status "Azure authenticated"

# Generate version
VERSION="2.0.0.$(date +%Y%m%d).$(date +%H%M%S)"
SHORT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "manual")
IMAGE_TAG="${VERSION}-${SHORT_SHA}"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
LATEST_IMAGE="${REGISTRY}/${IMAGE_NAME}:latest"

echo ""
echo "📦 Build Information:"
echo "  Version: ${VERSION}"
echo "  Git SHA: ${SHORT_SHA}"
echo "  Image: ${FULL_IMAGE}"

# Build Docker image
echo ""
echo "🔨 Building Docker image..."
docker build -t ${FULL_IMAGE} -t ${LATEST_IMAGE} \
    --build-arg VERSION=${VERSION} \
    --build-arg COMMIT_SHA=${SHORT_SHA} \
    --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
    .

if [ $? -eq 0 ]; then
    print_status "Docker image built successfully"
else
    print_error "Docker build failed"
    exit 1
fi

# Login to ACR
echo ""
echo "🔐 Logging in to Azure Container Registry..."
az acr login --name wellintakeacr0903

if [ $? -eq 0 ]; then
    print_status "Logged in to ACR"
else
    print_error "ACR login failed"
    exit 1
fi

# Push image
echo ""
echo "📤 Pushing Docker image to registry..."
docker push ${FULL_IMAGE}
docker push ${LATEST_IMAGE}

if [ $? -eq 0 ]; then
    print_status "Image pushed successfully"
else
    print_error "Image push failed"
    exit 1
fi

# Deploy to Container Apps
echo ""
echo "🚀 Deploying to Azure Container Apps..."
az containerapp update \
    --name ${CONTAINER_APP} \
    --resource-group ${RESOURCE_GROUP} \
    --image ${FULL_IMAGE} \
    --output none

if [ $? -eq 0 ]; then
    print_status "Deployment successful"
else
    print_error "Deployment failed"
    exit 1
fi

# Wait for deployment
echo ""
echo "⏳ Waiting for deployment to stabilize (30 seconds)..."
sleep 30

# Health check
echo ""
echo "🏥 Running health check..."
API_URL="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
if curl -f "${API_URL}/health" -s -o /dev/null; then
    print_status "Health check passed"
else
    print_warning "Health check failed or API key required"
fi

# Get deployment info
echo ""
echo "📊 Deployment Summary:"
echo "=================================="
echo "  Container App: ${CONTAINER_APP}"
echo "  Resource Group: ${RESOURCE_GROUP}"
echo "  Image: ${FULL_IMAGE}"
echo "  API URL: ${API_URL}"
echo "  Timestamp: $(date)"
echo "=================================="

print_status "Deployment completed successfully!"

echo ""
echo "📝 Next steps:"
echo "  1. Test the API: curl ${API_URL}/health"
echo "  2. Check logs: az containerapp logs show --name ${CONTAINER_APP} --resource-group ${RESOURCE_GROUP} --follow"
echo "  3. View in portal: https://portal.azure.com"

# Optional: Clear Redis cache
echo ""
read -p "Do you want to clear Redis cache? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 Clearing Redis cache..."
    curl -X POST "${API_URL}/cache/invalidate" \
        -H "X-API-Key: e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384" \
        -s -o /dev/null
    print_status "Cache cleared"
fi