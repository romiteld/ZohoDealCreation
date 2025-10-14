#!/bin/bash
# Deploy Teams Bot Workers to Azure Container Apps
# Usage: ./scripts/deploy-workers.sh [digest|nlp|all]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="TheWell-Infra-East"
ACR_NAME="wellintakeacr0903"
ACR_LOGIN_SERVER="$ACR_NAME.azurecr.io"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Teams Bot Workers Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Determine which worker to deploy
WORKER_TYPE="${1:-all}"

# Login to ACR
echo -e "${YELLOW}Logging into Azure Container Registry...${NC}"
az acr login --name $ACR_NAME

build_and_push_digest_worker() {
    echo ""
    echo -e "${YELLOW}Building Digest Worker...${NC}"

    docker build -t $ACR_LOGIN_SERVER/teams-digest-worker:latest \
        -t $ACR_LOGIN_SERVER/teams-digest-worker:$TIMESTAMP \
        -f teams_bot/Dockerfile.digest-worker .

    echo -e "${YELLOW}Pushing Digest Worker to ACR...${NC}"
    docker push $ACR_LOGIN_SERVER/teams-digest-worker:latest
    docker push $ACR_LOGIN_SERVER/teams-digest-worker:$TIMESTAMP

    echo -e "${GREEN}✅ Digest Worker image pushed${NC}"
}

build_and_push_nlp_worker() {
    echo ""
    echo -e "${YELLOW}Building NLP Worker...${NC}"

    docker build -t $ACR_LOGIN_SERVER/teams-nlp-worker:latest \
        -t $ACR_LOGIN_SERVER/teams-nlp-worker:$TIMESTAMP \
        -f teams_bot/Dockerfile.nlp-worker .

    echo -e "${YELLOW}Pushing NLP Worker to ACR...${NC}"
    docker push $ACR_LOGIN_SERVER/teams-nlp-worker:latest
    docker push $ACR_LOGIN_SERVER/teams-nlp-worker:$TIMESTAMP

    echo -e "${GREEN}✅ NLP Worker image pushed${NC}"
}

update_digest_worker_container_app() {
    echo ""
    echo -e "${YELLOW}Updating Digest Worker Container App...${NC}"

    az containerapp update \
        --name teams-digest-worker \
        --resource-group $RESOURCE_GROUP \
        --image $ACR_LOGIN_SERVER/teams-digest-worker:latest \
        --revision-suffix "v$TIMESTAMP" \
        --output table

    echo -e "${GREEN}✅ Digest Worker Container App updated${NC}"
}

update_nlp_worker_container_app() {
    echo ""
    echo -e "${YELLOW}Updating NLP Worker Container App...${NC}"

    az containerapp update \
        --name teams-nlp-worker \
        --resource-group $RESOURCE_GROUP \
        --image $ACR_LOGIN_SERVER/teams-nlp-worker:latest \
        --revision-suffix "v$TIMESTAMP" \
        --output table

    echo -e "${GREEN}✅ NLP Worker Container App updated${NC}"
}

# Execute based on worker type
case $WORKER_TYPE in
    digest)
        build_and_push_digest_worker
        update_digest_worker_container_app
        ;;
    nlp)
        build_and_push_nlp_worker
        update_nlp_worker_container_app
        ;;
    all)
        build_and_push_digest_worker
        build_and_push_nlp_worker
        update_digest_worker_container_app
        update_nlp_worker_container_app
        ;;
    *)
        echo -e "${RED}Invalid worker type: $WORKER_TYPE${NC}"
        echo "Usage: $0 [digest|nlp|all]"
        exit 1
        ;;
esac

# Display replica status
echo ""
echo -e "${YELLOW}Checking Digest Worker replicas...${NC}"
az containerapp replica list \
    --name teams-digest-worker \
    --resource-group $RESOURCE_GROUP \
    --query "[].{Name:name, Status:properties.runningState}" \
    --output table || echo "No replicas (scale-to-zero active)"

echo ""
echo -e "${YELLOW}Checking NLP Worker replicas...${NC}"
az containerapp replica list \
    --name teams-nlp-worker \
    --resource-group $RESOURCE_GROUP \
    --query "[].{Name:name, Status:properties.runningState}" \
    --output table || echo "No replicas (scale-to-zero active)"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Deployed images:"
echo "  - Digest Worker: $ACR_LOGIN_SERVER/teams-digest-worker:$TIMESTAMP"
echo "  - NLP Worker: $ACR_LOGIN_SERVER/teams-nlp-worker:$TIMESTAMP"
echo ""
echo "Monitor logs:"
echo "  az containerapp logs show --name teams-digest-worker --resource-group $RESOURCE_GROUP --follow"
echo "  az containerapp logs show --name teams-nlp-worker --resource-group $RESOURCE_GROUP --follow"
echo ""
echo "Check Service Bus queue depth:"
echo "  az servicebus queue show --name teams-digest-requests --namespace-name wellintakebus-standard --query countDetails.activeMessageCount"
echo "  az servicebus queue show --name teams-nlp-queries --namespace-name wellintakebus-standard --query countDetails.activeMessageCount"
