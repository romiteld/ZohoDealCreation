#!/bin/bash

# Well Intake API - Enhanced Deployment Script with Cache Busting
# This script provides a convenient wrapper around the Python deployment system
# and maintains compatibility with existing deployment workflows

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_DEPLOY_SCRIPT="$SCRIPT_DIR/scripts/deploy_with_cache_bust.py"
ENVIRONMENT=${1:-"prod"}
ACTION=${2:-"deploy"}

# Function to print colored messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [environment] [action] [options]"
    echo ""
    echo "Arguments:"
    echo "  environment    Target environment: 'dev' or 'prod' (default: prod)"
    echo "  action         Action to perform: 'deploy', 'rollback', or 'status' (default: deploy)"
    echo ""
    echo "Examples:"
    echo "  $0                    # Deploy to production"
    echo "  $0 prod deploy        # Deploy to production (explicit)"
    echo "  $0 dev deploy         # Deploy to development"
    echo "  $0 prod rollback      # Rollback production to previous version"
    echo "  $0 prod status        # Check deployment status"
    echo ""
    echo "Advanced options (pass directly to Python script):"
    echo "  --force-version-bump  # Force version bump even if no changes detected"
    echo "  --rollback=REVISION   # Rollback to specific revision"
    echo ""
    echo "Examples with advanced options:"
    echo "  python scripts/deploy_with_cache_bust.py --environment=prod --force-version-bump"
    echo "  python scripts/deploy_with_cache_bust.py --environment=prod --rollback=well-intake-api--v1300120241201"
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install Python 3.8 or later."
        exit 1
    fi
    
    # Check virtual environment
    if [[ -z "$VIRTUAL_ENV" ]]; then
        log_warn "Virtual environment not activated. Attempting to activate..."
        if [[ -f "$SCRIPT_DIR/zoho/bin/activate" ]]; then
            source "$SCRIPT_DIR/zoho/bin/activate"
            log_info "Activated virtual environment: zoho"
        elif [[ -f "$SCRIPT_DIR/venv/bin/activate" ]]; then
            source "$SCRIPT_DIR/venv/bin/activate"
            log_info "Activated virtual environment: venv"
        else
            log_warn "No virtual environment found. Continuing with system Python."
        fi
    fi
    
    # Check deployment script exists
    if [[ ! -f "$PYTHON_DEPLOY_SCRIPT" ]]; then
        log_error "Deployment script not found: $PYTHON_DEPLOY_SCRIPT"
        exit 1
    fi
    
    # Check if script is executable
    if [[ ! -x "$PYTHON_DEPLOY_SCRIPT" ]]; then
        chmod +x "$PYTHON_DEPLOY_SCRIPT"
        log_info "Made deployment script executable"
    fi
    
    log_info "Prerequisites check passed"
}

# Function to validate environment
validate_environment() {
    if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
        log_error "Invalid environment: $ENVIRONMENT. Must be 'dev' or 'prod'."
        show_usage
        exit 1
    fi
}

# Function to get deployment status
get_deployment_status() {
    log_info "Checking deployment status for environment: $ENVIRONMENT"
    
    # Determine resource group based on environment
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        RESOURCE_GROUP="TheWell-Infra-East"
        CONTAINER_APP_NAME="well-intake-api"
    else
        RESOURCE_GROUP="TheWell-Dev-East"
        CONTAINER_APP_NAME="well-intake-api-dev"
    fi
    
    # Check if logged into Azure
    if ! az account show &> /dev/null; then
        log_error "Not logged into Azure. Please run 'az login' first."
        exit 1
    fi
    
    echo -e "\n${BLUE}Container App Status:${NC}"
    az containerapp show \
        --name "$CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query '{name:name,state:properties.provisioningState,replicas:properties.template.scale.minReplicas,fqdn:properties.configuration.ingress.fqdn}' \
        -o table
    
    echo -e "\n${BLUE}Active Revisions:${NC}"
    az containerapp revision list \
        --name "$CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query '[?properties.active==`true`].{Name:name,CreatedTime:properties.createdTime,Replicas:properties.replicas,TrafficWeight:properties.trafficWeight}' \
        -o table
    
    echo -e "\n${BLUE}Health Check:${NC}"
    APP_URL=$(az containerapp show \
        --name "$CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.configuration.ingress.fqdn' -o tsv)
    
    if [[ -n "$APP_URL" ]]; then
        HEALTH_URL="https://$APP_URL/health"
        echo "Checking: $HEALTH_URL"
        
        if HEALTH_RESPONSE=$(curl -s -w "%{http_code}" "$HEALTH_URL" -o /tmp/health_response); then
            HTTP_CODE="${HEALTH_RESPONSE: -3}"
            if [[ "$HTTP_CODE" == "200" ]]; then
                log_info "Health check passed (HTTP $HTTP_CODE)"
                echo "Response:"
                cat /tmp/health_response | python3 -m json.tool 2>/dev/null || cat /tmp/health_response
            else
                log_warn "Health check returned HTTP $HTTP_CODE"
                cat /tmp/health_response
            fi
        else
            log_error "Could not reach health endpoint"
        fi
        rm -f /tmp/health_response
    fi
}

# Function to execute deployment
execute_deployment() {
    log_info "Starting deployment to $ENVIRONMENT environment..."
    
    case "$ACTION" in
        "deploy")
            log_info "Executing full deployment with cache busting..."
            python3 "$PYTHON_DEPLOY_SCRIPT" --environment="$ENVIRONMENT"
            ;;
        "rollback")
            log_info "Executing rollback procedure..."
            if [[ -n "$3" ]]; then
                python3 "$PYTHON_DEPLOY_SCRIPT" --environment="$ENVIRONMENT" --rollback="$3"
            else
                python3 "$PYTHON_DEPLOY_SCRIPT" --environment="$ENVIRONMENT" --rollback
            fi
            ;;
        "status")
            get_deployment_status
            ;;
        *)
            log_error "Invalid action: $ACTION. Must be 'deploy', 'rollback', or 'status'."
            show_usage
            exit 1
            ;;
    esac
}

# Function to handle migration from old deployment script
check_legacy_deployment() {
    OLD_DEPLOY_SCRIPT="$SCRIPT_DIR/deployment/deploy_with_security.sh"
    
    if [[ -f "$OLD_DEPLOY_SCRIPT" ]] && [[ "$1" == "--legacy" ]]; then
        log_warn "Using legacy deployment script..."
        "$OLD_DEPLOY_SCRIPT"
        exit $?
    fi
}

# Main execution flow
main() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Well Intake API - Enhanced Deployment${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "Environment: ${YELLOW}$ENVIRONMENT${NC}"
    echo -e "Action: ${BLUE}$ACTION${NC}"
    echo -e "Script: ${BLUE}$PYTHON_DEPLOY_SCRIPT${NC}"
    echo -e "${GREEN}========================================${NC}\n"
    
    # Handle help and usage
    if [[ "$1" == "-h" || "$1" == "--help" ]]; then
        show_usage
        exit 0
    fi
    
    # Handle legacy deployment
    check_legacy_deployment "$@"
    
    # Validate inputs
    validate_environment
    
    # Check prerequisites
    check_prerequisites
    
    # Execute the requested action
    execute_deployment "$@"
    
    # Final status message
    if [[ $? -eq 0 ]]; then
        log_info "Operation completed successfully!"
    else
        log_error "Operation failed!"
        exit 1
    fi
}

# Handle script interruption
trap 'echo -e "\n${RED}Deployment interrupted by user${NC}"; exit 130' INT TERM

# Run main function with all arguments
main "$@"