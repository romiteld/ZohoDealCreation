#!/bin/bash

# Root Folder Cleanup Script
# This script removes old/outdated files while preserving:
# - All JSON files
# - VAULT_ALERTS_GUIDE.md
# - DNS & email deliverability files
# - Essential project configuration

set -e  # Exit on error

ROOT_DIR="/home/romiteld/Development/Desktop_Apps/outlook"
cd "$ROOT_DIR"

echo "========================================"
echo "Root Folder Cleanup"
echo "========================================"
echo ""
echo "This will remove 103 old/outdated files"
echo "Press Ctrl+C to cancel, Enter to continue..."
read

# Create backup directory with timestamp
BACKUP_DIR="./removed_files_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "Creating backup in: $BACKUP_DIR"
echo ""

# Function to safely remove file (move to backup)
safe_remove() {
    local file="$1"
    if [ -f "$file" ]; then
        mv "$file" "$BACKUP_DIR/"
        echo "✓ Removed: $file"
    fi
}

echo "Removing old documentation..."
safe_remove "ANONYMIZATION_QUICK_REFERENCE.md"
safe_remove "ANONYMIZATION_TEST_SUMMARY.md"
safe_remove "ANONYMIZATION_VERIFICATION_README.md"
safe_remove "ANONYMIZER_QUICKSTART.md"
safe_remove "AGENTS.md"
safe_remove "AZURE_SERVICE_BUS_CONFIG.md"
safe_remove "BOSS_APPROVAL_EMAIL.md"
safe_remove "BOSS_APPROVAL_EMAIL_SEND_NOW.md"
safe_remove "CONFIGURATION_FIX_NEEDED.md"
safe_remove "DEPLOYMENT_VERIFICATION.md"
safe_remove "FIXES_2025-10-15.md"
safe_remove "IMPLEMENTATION_STATUS.md"
safe_remove "INSTALLATION_CHECKLIST.md"
safe_remove "KEDA_CONFIGURATION.md"
safe_remove "PHASE1_COMPLETION_SUMMARY.md"
safe_remove "PHASE2_COMPLETION_SUMMARY.md"
safe_remove "POWERBI_SETUP.md"
safe_remove "SECURITY_REMEDIATION_SUMMARY.md"
safe_remove "SERVICE_BUS_DELIVERABLES.md"
safe_remove "VERIFICATION_GUIDE.md"
safe_remove "ZOHO_API_MIGRATION.md"
safe_remove "ZOHO_API_QUICKREF.md"

echo ""
echo "Removing old test files..."
safe_remove "test_anonymization_e2e.py"
safe_remove "test_anonymization_clean.html"
safe_remove "test_anonymization_sample.html"
safe_remove "test_anonymizer.py"
safe_remove "test_format_VERIFY.html"
safe_remove "test_production_endpoint.py"
safe_remove "test_production_query.py"
safe_remove "test_role_lookup.py"
safe_remove "test_sample.html"
safe_remove "test_service_bus.py"
safe_remove "test_teams_queries.py"
safe_remove "test_validation_only.py"
safe_remove "test_vault_adapter.py"
safe_remove "anonymization_test_report.txt"
safe_remove "verification_report.txt"

echo ""
echo "Removing one-time use scripts..."
safe_remove "ai_bullet_generator.py"
safe_remove "clear_bullet_cache.py"
safe_remove "clear_vault_cache.py"
safe_remove "create_zoho_sync_metadata.py"
safe_remove "create_zoho_user_mapping.py"
safe_remove "extract_rich_bullets.py"
safe_remove "fetch_missing_zoho_data.py"
safe_remove "find_zoho_contact.py"
safe_remove "generate_boss_format_langgraph.py"
safe_remove "generate_test_email_for_approval.py"
safe_remove "load_vault_candidates_to_db.py"
safe_remove "run_all_tests.py"
safe_remove "run_talentwell_with_real_twav.py"
safe_remove "run_teams_migration.py"
safe_remove "send_boss_approval_email.py"
safe_remove "send_boss_approval_realtime.py"
safe_remove "tone_utils.py"
safe_remove "validate_fa_extraction.py"
safe_remove "validate_manifest.py"
safe_remove "verify_anonymization.py"
safe_remove "verify_deployed_code.py"
safe_remove "verify_final.py"

echo ""
echo "Removing old data exports..."
safe_remove "Candidates_2025_10_07.csv"
safe_remove "Candidates_2025_10_09.csv"
safe_remove "Deals_2025_10_07.csv"
safe_remove "Jobs_2025_10_07.csv"
safe_remove "duplicates_report_2025_10_13.csv"
safe_remove "boss_format_advisors_20251011_095703.html"
safe_remove "boss_format_executives_20251011_095703.html"
safe_remove "generation_log.txt"

echo ""
echo "Removing old packages..."
safe_remove "TalentWell-Assistant-v1.0.2.zip"

echo ""
echo "Removing backup/temp files..."
safe_remove ".env.local.backup"
safe_remove ".env.sandbox"
safe_remove "cb-base64-string.txt"
safe_remove "cb-bg-css.txt"
safe_remove "cb-image-tag.txt"
safe_remove "email_to_brandon_calendly_fix.txt"

echo ""
echo "Removing junk files..."
safe_remove "Black"
safe_remove "Excel"
safe_remove "Recruiter"
safe_remove "Steve"
safe_remove "The"
safe_remove "Transparent"

echo ""
echo "Removing old shell scripts..."
safe_remove "check_generation_status.sh"
safe_remove "deploy.sh"
safe_remove "example_vault_workflow.sh"
safe_remove "get-connection-strings.sh"
safe_remove "monitor_boss_email.sh"
safe_remove "run_tests.sh"
safe_remove "update-container-env.sh"

echo ""
echo "Removing old deployment files..."
safe_remove "weekly-digest-job.yaml"
safe_remove ".deployment"
safe_remove ".coverage"

echo ""
echo "========================================"
echo "✅ Cleanup Complete!"
echo "========================================"
echo ""
echo "Files backed up to: $BACKUP_DIR"
echo ""
echo "If everything works fine after testing, you can delete the backup:"
echo "  rm -rf $BACKUP_DIR"
echo ""

# Count files in backup
file_count=$(ls -1 "$BACKUP_DIR" 2>/dev/null | wc -l)
echo "Removed $file_count files"
