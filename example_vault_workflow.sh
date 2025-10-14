#!/bin/bash
###############################################################################
# Example Vault Alert Workflow with Anonymization Verification
#
# This script demonstrates how to integrate verify_anonymization.py into
# the weekly vault alert generation workflow.
#
# Usage: ./example_vault_workflow.sh [audience]
#   audience: advisors, c_suite, or global (default: all)
###############################################################################

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
TIMESTAMP=$(date +%Y%m%d)

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Determine which audiences to generate
AUDIENCE="${1:-all}"

if [ "$AUDIENCE" = "all" ]; then
    AUDIENCES=("advisors" "c_suite" "global")
else
    AUDIENCES=("$AUDIENCE")
fi

log_info "Starting vault alert generation for: ${AUDIENCES[*]}"

# Step 1: Generate HTML files
log_info "Generating HTML files..."

for aud in "${AUDIENCES[@]}"; do
    OUTPUT_FILE="${OUTPUT_DIR}/boss_format_${aud}_${TIMESTAMP}.html"

    log_info "Generating ${aud} alerts..."

    # Call the LangGraph generator
    python3 app/jobs/vault_alerts_generator.py \
        --audience "$aud" \
        --output "$OUTPUT_FILE"

    if [ $? -ne 0 ]; then
        log_error "Failed to generate ${aud} alerts"
        exit 1
    fi

    log_info "Generated: $OUTPUT_FILE"
done

# Step 2: Verify anonymization
log_info "Running anonymization verification..."

VERIFICATION_PASSED=true

for aud in "${AUDIENCES[@]}"; do
    OUTPUT_FILE="${OUTPUT_DIR}/boss_format_${aud}_${TIMESTAMP}.html"

    log_info "Verifying ${aud} file..."

    # Run verification in strict mode
    if python3 verify_anonymization.py --strict "$OUTPUT_FILE"; then
        log_info "✅ ${aud}: Verification PASSED"
    else
        log_error "❌ ${aud}: Verification FAILED"
        VERIFICATION_PASSED=false
    fi
done

# Step 3: Decision point
if [ "$VERIFICATION_PASSED" = true ]; then
    log_info "✅ All files passed verification!"

    # Optional: Deploy alerts
    # Uncomment to enable automatic deployment
    # log_info "Deploying alerts..."
    # python3 app/jobs/vault_alerts_scheduler.py

    log_info "Files ready for manual review and deployment:"
    for aud in "${AUDIENCES[@]}"; do
        echo "  - ${OUTPUT_DIR}/boss_format_${aud}_${TIMESTAMP}.html"
    done

    exit 0
else
    log_error "🚨 VERIFICATION FAILED - Alerts NOT deployed"
    log_error "Please review and fix the issues above before deploying."
    log_error "Run verification manually: python3 verify_anonymization.py ${OUTPUT_DIR}/*.html"

    exit 1
fi
