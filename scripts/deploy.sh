#!/bin/bash

##############################################################################
# COMPREHENSIVE DEPLOYMENT SCRIPT FOR WELL INTAKE API
# This script handles:
# 1. Database migrations (PostgreSQL with pgvector)
# 2. Azure Blob Storage setup
# 3. Docker image building and pushing
# 4. Azure Container Apps deployment
# 5. Manifest version update
##############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="TheWell-Infra-East"
CONTAINER_APP_NAME="well-intake-api"
REGISTRY_NAME="wellintakeregistry"
IMAGE_NAME="well-intake-api"
STORAGE_ACCOUNT="wellintakestorage"  # Update with your storage account name
CONTAINER_NAME="email-attachments"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  WELL INTAKE API - FULL DEPLOYMENT SCRIPT${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"
if ! command_exists az; then
    echo -e "${RED}Azure CLI is not installed. Please install it first.${NC}"
    exit 1
fi

if ! command_exists docker; then
    echo -e "${RED}Docker is not installed. Please install it first.${NC}"
    exit 1
fi

if ! command_exists python3; then
    echo -e "${RED}Python 3 is not installed. Please install it first.${NC}"
    exit 1
fi

# 1. DATABASE MIGRATIONS
echo -e "\n${YELLOW}Step 1: Database Migrations${NC}"
echo "Creating correction learning tables if they don't exist..."

cat > /tmp/db_migration.sql << 'EOF'
-- Create correction learning table for AI improvements
CREATE TABLE IF NOT EXISTS ai_corrections (
    id SERIAL PRIMARY KEY,
    email_domain VARCHAR(255),
    email_snippet TEXT,
    original_extraction JSONB,
    user_corrections JSONB,
    correction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_count INT DEFAULT 0,
    success_rate FLOAT DEFAULT 0.0
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_ai_corrections_domain 
ON ai_corrections(email_domain);

CREATE INDEX IF NOT EXISTS idx_ai_corrections_timestamp 
ON ai_corrections(correction_timestamp DESC);

-- Create learning patterns table
CREATE TABLE IF NOT EXISTS learning_patterns (
    id SERIAL PRIMARY KEY,
    pattern_type VARCHAR(100),
    pattern_key VARCHAR(255),
    pattern_value TEXT,
    confidence FLOAT DEFAULT 0.5,
    usage_count INT DEFAULT 0,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for pattern lookups
CREATE INDEX IF NOT EXISTS idx_learning_patterns_type_key 
ON learning_patterns(pattern_type, pattern_key);

-- Create email processing history table with embeddings
CREATE TABLE IF NOT EXISTS email_processing_history (
    id SERIAL PRIMARY KEY,
    email_hash VARCHAR(64) UNIQUE,
    sender_email VARCHAR(255),
    sender_domain VARCHAR(255),
    subject TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    extraction_result JSONB,
    zoho_deal_id VARCHAR(100),
    zoho_account_id VARCHAR(100),
    zoho_contact_id VARCHAR(100),
    attachments JSONB,
    processing_time_ms INT,
    ai_model VARCHAR(50) DEFAULT 'gpt-4-mini',
    success BOOLEAN DEFAULT true,
    error_message TEXT
);

-- Add vector extension if not exists (for future semantic search)
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column for semantic search (optional)
ALTER TABLE email_processing_history 
ADD COLUMN IF NOT EXISTS content_embedding vector(1536);

-- Create index for embeddings
CREATE INDEX IF NOT EXISTS idx_email_embeddings 
ON email_processing_history 
USING ivfflat (content_embedding vector_cosine_ops)
WITH (lists = 100);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO citus;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO citus;
EOF

echo "Applying database migrations..."
if [ -f .env.local ]; then
    source .env.local
    
    # Extract connection details from DATABASE_URL
    if [ ! -z "$DATABASE_URL" ]; then
        # Parse DATABASE_URL
        DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
        DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
        DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
        DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
        DB_PASS=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
        
        export PGPASSWORD=$DB_PASS
        psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f /tmp/db_migration.sql
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Database migrations completed successfully${NC}"
        else
            echo -e "${YELLOW}⚠ Database migration failed - continuing anyway${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ DATABASE_URL not found in .env.local - skipping DB migration${NC}"
    fi
else
    echo -e "${YELLOW}⚠ .env.local not found - skipping DB migration${NC}"
fi

# 2. AZURE BLOB STORAGE SETUP
echo -e "\n${YELLOW}Step 2: Azure Blob Storage Setup${NC}"
echo "Checking/creating blob container..."

# Login to Azure if needed
az account show &>/dev/null || az login

# Create storage container if it doesn't exist
if az storage container show --name $CONTAINER_NAME --account-name $STORAGE_ACCOUNT &>/dev/null; then
    echo -e "${GREEN}✓ Blob container '$CONTAINER_NAME' already exists${NC}"
else
    echo "Creating blob container '$CONTAINER_NAME'..."
    az storage container create \
        --name $CONTAINER_NAME \
        --account-name $STORAGE_ACCOUNT \
        --public-access off
    echo -e "${GREEN}✓ Blob container created${NC}"
fi

# Set CORS rules for the container (if needed for browser uploads)
echo "Setting CORS rules for blob storage..."
az storage cors add \
    --services b \
    --methods GET POST PUT DELETE OPTIONS \
    --origins "https://outlook.office.com" "https://outlook.office365.com" \
    --allowed-headers "*" \
    --exposed-headers "*" \
    --max-age 3600 \
    --account-name $STORAGE_ACCOUNT 2>/dev/null || true

echo -e "${GREEN}✓ Blob storage configuration complete${NC}"

# 3. UPDATE MANIFEST VERSION
echo -e "\n${YELLOW}Step 3: Updating Manifest Version${NC}"
if [ -f update_manifest_version.py ]; then
    python3 update_manifest_version.py
else
    echo -e "${YELLOW}⚠ Manifest updater not found - skipping version update${NC}"
fi

# 4. BUILD DOCKER IMAGE
echo -e "\n${YELLOW}Step 4: Building Docker Image${NC}"
echo "Building Docker image with latest code..."

# Get current git commit hash for tagging
GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
IMAGE_TAG="${GIT_HASH}-$(date +%Y%m%d-%H%M%S)"

docker build -t $REGISTRY_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG .
docker tag $REGISTRY_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG $REGISTRY_NAME.azurecr.io/$IMAGE_NAME:latest

echo -e "${GREEN}✓ Docker image built successfully${NC}"

# 5. PUSH TO AZURE CONTAINER REGISTRY
echo -e "\n${YELLOW}Step 5: Pushing to Azure Container Registry${NC}"
echo "Logging into Azure Container Registry..."

az acr login --name $REGISTRY_NAME

echo "Pushing Docker image..."
docker push $REGISTRY_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG
docker push $REGISTRY_NAME.azurecr.io/$IMAGE_NAME:latest

echo -e "${GREEN}✓ Docker image pushed successfully${NC}"

# 6. UPDATE CONTAINER APP
echo -e "\n${YELLOW}Step 6: Updating Container App${NC}"
echo "Deploying to Azure Container Apps..."

# Update with new image
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --image $REGISTRY_NAME.azurecr.io/$IMAGE_NAME:latest

echo -e "${GREEN}✓ Container App updated successfully${NC}"

# 7. VERIFY DEPLOYMENT
echo -e "\n${YELLOW}Step 7: Verifying Deployment${NC}"
echo "Waiting for deployment to stabilize (30 seconds)..."
sleep 30

# Check health endpoint
HEALTH_URL="https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/health"
echo "Checking health endpoint..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
    
    # Get detailed health info
    curl -s $HEALTH_URL | python3 -m json.tool
else
    echo -e "${RED}✗ Health check failed with status: $HTTP_STATUS${NC}"
fi

# 8. RUN TESTS
echo -e "\n${YELLOW}Step 8: Running Deployment Tests${NC}"
if [ -f test_container_deployment.py ]; then
    python3 test_container_deployment.py || true
else
    echo -e "${YELLOW}⚠ Test script not found - skipping tests${NC}"
fi

# 9. SHOW DEPLOYMENT SUMMARY
echo -e "\n${BLUE}================================================${NC}"
echo -e "${BLUE}  DEPLOYMENT COMPLETE${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${GREEN}Deployment Summary:${NC}"
echo "• Image Tag: $IMAGE_TAG"
echo "• Container App: $CONTAINER_APP_NAME"
echo "• URL: https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io"
echo "• Manifest: https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/manifest.xml"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Clear browser cache in Outlook Web"
echo "2. Remove and re-add the add-in using the manifest URL above"
echo "3. Test the 'Send to Zoho' button with a sample email"
echo "4. Monitor logs with:"
echo "   az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow"
echo ""
echo -e "${GREEN}Deployment completed at $(date)${NC}"

# Clean up temp files
rm -f /tmp/db_migration.sql

exit 0