# Root Folder Cleanup Plan

**Date:** October 15, 2025

## Summary

This cleanup removes **~103 old/outdated files** from the root directory while preserving all essential files for development, deployment, and reference.

---

## 🚀 How to Run Cleanup

```bash
# Review what will be removed
cat cleanup_root_folder.sh

# Run cleanup (creates backup first)
./cleanup_root_folder.sh

# Test that everything still works
pytest tests/
docker build -f teams_bot/Dockerfile .

# If all good, delete backup
rm -rf removed_files_backup_*
```

---

## ✅ Files Being KEPT

### Project Configuration (Essential)
- `.dockerignore`
- `.env.local` ⚠️ Active configuration
- `.gitignore`
- `.pre-commit-config.yaml`
- `Dockerfile`
- `gunicorn.conf.py`
- `package.json` / `package-lock.json`
- `pytest.ini`
- `requirements.txt` / `requirements-dev.txt`

### Active Documentation
- `CLAUDE.md` - Project instructions for AI assistants
- `README.md` - Main project documentation
- `VAULT_ALERTS_GUIDE.md` ⭐ **You explicitly wanted this** (digest development reference)
- `ANONYMIZATION_RULES.md` - Active anonymization logic
- `ZOHO_API_VERIFICATION.md` - Current API verification

### JSON Files ⭐ **You explicitly wanted all JSONs**
- `zoho_custom_views.json`
- `zoho_deals_fields.json`
- `zoho_lead_fields.json`
- `zoho_leads_all_fields_complete.json`
- `zoho_leads_custom_views.json`
- `zoho_leads_fields.json`
- `zoho_notes_fields.json`
- `zoho_payment_findings.json`
- `zoho_payment_modules.json`
- `zoho_sample_vault_candidate.json`
- `zoho_vault_candidates_detailed.json`
- `teams-app-manifest.json`

### DNS & Email Deliverability ⭐ **You explicitly wanted these**
- `verify_azure_dns.sh`
- `verify_dmarc_fix.sh`
- `email_deliverability_report.html`
- `email_deliverability_report_updated.html`
- `send_deliverability_report.py`

### Current Deployment
- `talentwell-teams-app-v1.0.3.zip` - Latest Teams app package

### Active Utilities
- `startup.sh` - Local development server
- `test_nlp_queries_e2e.py` - Current E2E test suite
- `zoom_get_transcript.py` - Utility for Zoom transcripts
- `zoom_list_recordings.py` - Utility for Zoom recordings
- `zoom_search_candidate.py` - Utility for finding candidates

---

## 🗑️ Files Being REMOVED

### Old/Outdated Documentation (22 files)
**Why:** Historical documents for completed tasks/migrations

- `ANONYMIZATION_QUICK_REFERENCE.md` - Duplicate of ANONYMIZATION_RULES.md
- `ANONYMIZATION_TEST_SUMMARY.md` - Old test results
- `ANONYMIZATION_VERIFICATION_README.md` - Duplicate
- `ANONYMIZER_QUICKSTART.md` - Duplicate
- `AGENTS.md` - Not being used
- `AZURE_SERVICE_BUS_CONFIG.md` - Service Bus already configured
- `BOSS_APPROVAL_EMAIL.md` - Old documentation
- `BOSS_APPROVAL_EMAIL_SEND_NOW.md` - Old
- `CONFIGURATION_FIX_NEEDED.md` - Issues fixed
- `DEPLOYMENT_VERIFICATION.md` - Old deployment docs
- `FIXES_2025-10-15.md` - Historical (today's fixes)
- `IMPLEMENTATION_STATUS.md` - Outdated status
- `INSTALLATION_CHECKLIST.md` - One-time use
- `KEDA_CONFIGURATION.md` - KEDA already deployed
- `PHASE1_COMPLETION_SUMMARY.md` - Historical
- `PHASE2_COMPLETION_SUMMARY.md` - Historical
- `POWERBI_SETUP.md` - Not actively used
- `SECURITY_REMEDIATION_SUMMARY.md` - Historical
- `SERVICE_BUS_DELIVERABLES.md` - Historical
- `VERIFICATION_GUIDE.md` - Old
- `ZOHO_API_MIGRATION.md` - Migration complete
- `ZOHO_API_QUICKREF.md` - Duplicate of ZOHO_API_VERIFICATION.md

### Old Test Files (15 files)
**Why:** One-time verification tests, superseded by current test suite

- `test_anonymization_e2e.py` - Old test
- `test_anonymization_clean.html` - Test output
- `test_anonymization_sample.html` - Test output
- `test_anonymizer.py` - Old test
- `test_format_VERIFY.html` - Verification output
- `test_production_endpoint.py` - One-time verification
- `test_production_query.py` - One-time verification
- `test_role_lookup.py` - One-time verification
- `test_sample.html` - Test output
- `test_service_bus.py` - One-time verification
- `test_teams_queries.py` - Superseded by test_nlp_queries_e2e.py
- `test_validation_only.py` - One-time verification
- `test_vault_adapter.py` - One-time verification
- `anonymization_test_report.txt` - Old report
- `verification_report.txt` - Old report

### One-Time Use Scripts (24 files)
**Why:** Migration/setup scripts that have already been run

- `ai_bullet_generator.py` - Integrated into main code
- `clear_bullet_cache.py` - One-time cache clear
- `clear_vault_cache.py` - One-time cache clear
- `create_zoho_sync_metadata.py` - One-time sync
- `create_zoho_user_mapping.py` - One-time mapping
- `extract_rich_bullets.py` - One-time extraction
- `fetch_missing_zoho_data.py` - One-time backfill
- `find_zoho_contact.py` - One-time lookup
- `generate_boss_format_langgraph.py` - Integrated into app/jobs/
- `generate_test_email_for_approval.py` - One-time test
- `load_vault_candidates_to_db.py` - One-time data load
- `run_all_tests.py` - Use `pytest` directly
- `run_talentwell_with_real_twav.py` - One-time test
- `run_teams_migration.py` - Migration complete
- `send_boss_approval_email.py` - One-time send
- `send_boss_approval_realtime.py` - One-time send
- `tone_utils.py` - Not imported anywhere
- `validate_fa_extraction.py` - One-time validation
- `validate_manifest.py` - One-time validation
- `verify_anonymization.py` - One-time verification
- `verify_deployed_code.py` - One-time verification
- `verify_final.py` - One-time verification

### Old Data/Export Files (8 files)
**Why:** Old snapshots, no longer needed

- `Candidates_2025_10_07.csv` - Old export
- `Candidates_2025_10_09.csv` - Old export
- `Deals_2025_10_07.csv` - Old export
- `Jobs_2025_10_07.csv` - Old export
- `duplicates_report_2025_10_13.csv` - Old report
- `boss_format_advisors_20251011_095703.html` - Test output
- `boss_format_executives_20251011_095703.html` - Test output
- `generation_log.txt` - Old logs

### Old Packages (1 file)
**Why:** Superseded by v1.0.3

- `TalentWell-Assistant-v1.0.2.zip` - Old Teams app package

### Backup/Temp Files (6 files)
**Why:** Old backups, no longer needed

- `.env.local.backup` - Old backup
- `.env.sandbox` - Not used
- `cb-base64-string.txt` - Temp file
- `cb-bg-css.txt` - Temp file
- `cb-image-tag.txt` - Temp file
- `email_to_brandon_calendly_fix.txt` - Temp note

### Junk Files (6 files)
**Why:** Likely created by failed commands or typos

- `Black` - Error artifact
- `Excel` - Error artifact
- `Recruiter` - Error artifact
- `Steve` - Error artifact
- `The` (2 copies) - Error artifacts
- `Transparent` - Error artifact

### Old Shell Scripts (7 files)
**Why:** One-time use or superseded by Azure CLI

- `check_generation_status.sh` - One-time check
- `deploy.sh` - Use Azure CLI instead
- `example_vault_workflow.sh` - Example only
- `get-connection-strings.sh` - One-time retrieval
- `monitor_boss_email.sh` - One-time monitoring
- `run_tests.sh` - Use `pytest` directly
- `update-container-env.sh` - One-time update

### Old Deployment Files (3 files)
**Why:** Old deployment methods, no longer used

- `weekly-digest-job.yaml` - Using Service Bus now
- `.deployment` - Old deployment config
- `.coverage` - Regenerated on test runs

---

## 🔒 Safety Features

1. **Backup First**: All files moved to `removed_files_backup_YYYYMMDD_HHMMSS/`
2. **Safe Removal**: Uses `mv` not `rm`, easy to restore
3. **Explicit Preservation**: Never touches JSON, VAULT_ALERTS_GUIDE, DNS/email files
4. **Review Before Delete**: You can inspect backup before permanent deletion

---

## 📊 Impact

**Before Cleanup:** ~180 files in root directory
**After Cleanup:** ~77 essential files
**Reduction:** 57% fewer files, easier to navigate

---

## 🧪 Testing After Cleanup

```bash
# Verify environment still works
cat .env.local | grep -q "DATABASE_URL" && echo "✅ .env.local intact"

# Verify Docker builds
docker build -f teams_bot/Dockerfile . && echo "✅ Docker build successful"

# Verify tests run
pytest test_nlp_queries_e2e.py -v && echo "✅ Tests passing"

# Verify JSON files present
ls zoho_*.json | wc -l  # Should show 11 files
```

---

## ⚠️ Important Notes

1. **Don't delete `.env.local`** - Contains active credentials
2. **Keep all JSON files** - Schema definitions for Zoho API
3. **Keep VAULT_ALERTS_GUIDE.md** - Reference for digest generation
4. **Keep DNS/email deliverability files** - Active monitoring tools

---

## 🎯 Result

A clean, maintainable root directory with only:
- Active configuration files
- Essential documentation
- Current deployment packages
- Useful utility scripts
- Reference JSON schemas
