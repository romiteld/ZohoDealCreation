# Root Directory Cleanup Plan - Well Intake API

**Created:** October 17, 2025
**Priority:** Medium
**Estimated Effort:** 30 minutes
**Risk Level:** Low (no production code affected)

---

## 🎯 Objective

Reduce root directory clutter by 40-50% through systematic archival of development artifacts, test scripts, and older vault alert iterations while preserving the most recent working files.

---

## 📊 Current State Analysis

**Root Directory File Count:** 50+ files
- Production scripts: ~15
- HTML previews: ~20 (vault alerts, debug, test)
- Python test scripts: ~15
- Markdown docs: ~10
- Other: ~10

**Problem Areas:**
1. Multiple iterations of same files (boss_format_*.html from Oct 11, 15, 16)
2. Test/debug scripts from vault alert development (send_*.py, test_*.py)
3. Temporary HTML files from debugging sessions
4. Outdated documentation

**Git Status:**
```bash
$ git status --short | head -5
M .claude/settings.local.json
M .gitignore
?? Makefile
?? PERFORMANCE_ANALYSIS_REPORT.md
?? advisorexample1.png
# ... 43 more untracked files
```

---

## 📁 Files Identified for Archiving

### Category 1: Vault Alert Iterations (Keep Most Recent Only)

**KEEP (Oct 16, 2024 - Most Recent):**
- ✅ `boss_format_advisors_20251016_192620.html`
- ✅ `boss_format_executives_20251016_192620.html`
- ✅ `app/templates/email/candidate_vault.html` (template)

**ARCHIVE (Older Iterations):**
```
archive/vault_alerts_iterations/
├── boss_format_advisors_20251011_095703.html
├── boss_format_advisors_20251015_180232.html
├── boss_format_executives_20251011_095703.html
├── boss_format_executives_20251015_180232.html
├── debug_advisor.html
├── debug_advisor_CLEANED.html
├── debug_executive.html
├── debug_executive_CLEANED.html
├── test_anonymization_clean.html
├── test_anonymization_sample.html
├── test_format_VERIFY.html
└── test_sample.html
```
**Count:** 12 files → archived

### Category 2: Development Test Scripts

**ARCHIVE:**
```
archive/test_scripts_oct2024/
├── send_boss_email_now.py
├── send_cleaned_vault_alerts.py
├── send_vault_alerts_no_validation.py
├── send_fixes_update_email.py
├── send_progress_email_to_steve.py
├── send_voice_platform_report.py
├── send_deliverability_report.py
├── generate_boss_format_langgraph.py
├── generate_test_email_for_approval.py
├── generate_top_20_vault_style.py
├── find_top_marketable_candidates.py
├── test_anonymization_e2e.py
├── test_anonymization_fixes.py
├── test_anonymizer.py
├── test_safe_get_fix.py
├── test_validation_only.py
├── test_graph_connection.py
├── test_nlp_queries_e2e.py
├── test_role_lookup.py
├── test_service_bus.py
├── test_teams_queries.py
├── test_zoho_search.sh
├── clear_all_vault_cache.py
├── clear_bullet_cache.py
└── clear_vault_cache.py
```
**Count:** 25 files → archived

### Category 3: Top 20/Top 10 Preview Files

**ARCHIVE:**
```
archive/top_candidates_previews/
├── top_20_with_note.html
├── top_20_vault_style.html
├── top_10_marketable_preview.html
├── top_10_marketable_candidates_email.py
└── send_top_20_emails.py
```
**Count:** 5 files → archived

### Category 4: Utility/Debug Scripts (Keep Selective)

**KEEP (Still Useful):**
- ✅ `run_talentwell_with_real_twav.py` (production utility)
- ✅ `deploy.sh` (deployment script)
- ✅ `run_tests.sh` (test automation)
- ✅ `run_all_tests.py` (test runner)

**ARCHIVE:**
```
archive/utility_scripts/
├── debug_morgan_stanley.py
├── fetch_missing_zoho_data.py
├── find_zoho_contact.py
├── create_zoho_sync_metadata.py
├── create_zoho_user_mapping.py
├── extract_rich_bullets.py
├── load_vault_candidates_to_db.py
├── validate_fa_extraction.py
├── monitor_boss_email.sh
├── check_generation_status.sh
├── cleanup_root_folder.sh
├── example_vault_workflow.sh
├── get-connection-strings.sh
└── update-container-env.sh
```
**Count:** 14 files → archived

### Category 5: Documentation/Reports (Archive Old)

**KEEP (Current/Active):**
- ✅ `CLAUDE.md`, `README.md`, `AGENTS.md`
- ✅ `IMPLEMENTATION_STATUS.md`, `KEDA_CONFIGURATION.md`
- ✅ `ZOHO_MAPPINGS_README.md` (canonical reference)

**ARCHIVE:**
```
archive/old_documentation/
├── ANONYMIZATION_QUICK_REFERENCE.md
├── ANONYMIZATION_TEST_SUMMARY.md
├── ANONYMIZATION_VERIFICATION_README.md
├── ANONYMIZER_QUICKSTART.md
├── AZURE_SERVICE_BUS_CONFIG.md
├── BOSS_APPROVAL_EMAIL.md
├── BOSS_APPROVAL_EMAIL_SEND_NOW.md
├── CLEANUP_PLAN.md
├── CONFIGURATION_FIX_NEEDED.md
├── DEPLOYMENT_VERIFICATION.md
├── INSTALLATION_CHECKLIST.md
├── PHASE1_COMPLETION_SUMMARY.md
├── PHASE2_COMPLETION_SUMMARY.md
├── SECURITY_REMEDIATION_SUMMARY.md
├── SERVICE_BUS_DELIVERABLES.md
├── VERIFICATION_GUIDE.md
├── ZOHO_API_MIGRATION.md
├── ZOHO_API_QUICKREF.md
├── anonymization_test_report.txt
├── verification_report.txt
├── generation_log.txt
└── duplicates_report_2025_10_13.csv
```
**Count:** 22 files → archived

### Category 6: Image/Asset Files

**ARCHIVE:**
```
archive/screenshots_assets/
├── advisorexample1.png
├── advisorexample2.png
├── advisorexample3.png
├── top20.png
├── team.png
├── cb-base64-string.txt
├── cb-bg-css.txt
└── cb-image-tag.txt
```
**Count:** 8 files → archived

### Category 7: Data Files (Archive Old Exports)

**ARCHIVE:**
```
archive/data_exports/
├── Candidates_2025_10_07.csv
├── Candidates_2025_10_09.csv
├── Deals_2025_10_07.csv
├── Jobs_2025_10_07.csv
├── zoho_custom_views.json
├── zoho_deals_fields.json
├── zoho_lead_fields.json
├── zoho_leads_all_fields_complete.json
├── zoho_leads_custom_views.json
├── zoho_leads_fields.json
├── zoho_notes_fields.json
├── zoho_payment_findings.json
├── zoho_payment_modules.json
├── zoho_sample_vault_candidate.json
└── zoho_vault_candidates_detailed.json
```
**Count:** 15 files → archived

**KEEP (Canonical Reference):**
- ✅ `zoho_field_mappings.json` (954 KB - single source of truth)

---

## 🎯 Archive Directory Structure

```
/home/romiteld/Development/Desktop_Apps/outlook/
├── archive/
│   ├── README.md                        # Archive index with dates
│   ├── vault_alerts_iterations/         # 12 files
│   ├── test_scripts_oct2024/            # 25 files
│   ├── top_candidates_previews/         # 5 files
│   ├── utility_scripts/                 # 14 files
│   ├── old_documentation/               # 22 files
│   ├── screenshots_assets/              # 8 files
│   └── data_exports/                    # 15 files
│
└── [Root directory - 50% cleaner]
```

**Total Files to Archive:** 101 files
**Estimated Root Reduction:** 45-50%

---

## 🚀 Execution Plan

### Phase 1: Create Archive Structure (2 minutes)

```bash
cd /home/romiteld/Development/Desktop_Apps/outlook

# Create archive directories
mkdir -p archive/{vault_alerts_iterations,test_scripts_oct2024,top_candidates_previews,utility_scripts,old_documentation,screenshots_assets,data_exports}

# Create archive index
cat > archive/README.md << 'EOF'
# Archive Directory

This directory contains development artifacts, test scripts, and older iterations of files that are no longer actively used but preserved for reference.

## Archive Date
October 17, 2025

## Contents
- `vault_alerts_iterations/` - Older HTML previews (Oct 11, Oct 15) - keep Oct 16 in root
- `test_scripts_oct2024/` - Development test scripts from vault alert work
- `top_candidates_previews/` - Top 10/Top 20 candidate preview files
- `utility_scripts/` - One-time utility scripts no longer needed
- `old_documentation/` - Superseded documentation files
- `screenshots_assets/` - Screenshots and CSS snippets
- `data_exports/` - Older Zoho data exports (Oct 7-9)

## Retrieval
All files retain full git history. To restore a file:
```bash
git log --all --full-history -- archive/path/to/file
```

## Maintenance
Review quarterly (Jan, Apr, Jul, Oct) for permanent deletion of files older than 1 year.
EOF
```

### Phase 2: Move Files (10 minutes)

```bash
# Category 1: Vault alert iterations
mv boss_format_advisors_20251011_095703.html archive/vault_alerts_iterations/
mv boss_format_advisors_20251015_180232.html archive/vault_alerts_iterations/
mv boss_format_executives_20251011_095703.html archive/vault_alerts_iterations/
mv boss_format_executives_20251015_180232.html archive/vault_alerts_iterations/
mv debug_*.html archive/vault_alerts_iterations/
mv test_anonymization_*.html archive/vault_alerts_iterations/
mv test_format_VERIFY.html archive/vault_alerts_iterations/
mv test_sample.html archive/vault_alerts_iterations/

# Category 2: Test scripts
mv send_boss_email_now.py archive/test_scripts_oct2024/
mv send_cleaned_vault_alerts.py archive/test_scripts_oct2024/
mv send_vault_alerts_no_validation.py archive/test_scripts_oct2024/
mv send_fixes_update_email.py archive/test_scripts_oct2024/
mv send_progress_email_to_steve.py archive/test_scripts_oct2024/
mv send_voice_platform_report.py archive/test_scripts_oct2024/
mv send_deliverability_report.py archive/test_scripts_oct2024/
mv generate_*.py archive/test_scripts_oct2024/
mv find_top_marketable_candidates.py archive/test_scripts_oct2024/
mv test_*.py archive/test_scripts_oct2024/
mv test_zoho_search.sh archive/test_scripts_oct2024/
mv clear_all_vault_cache.py archive/test_scripts_oct2024/
mv clear_bullet_cache.py archive/test_scripts_oct2024/
mv clear_vault_cache.py archive/test_scripts_oct2024/

# Category 3: Top candidates previews
mv top_20_with_note.html archive/top_candidates_previews/
mv top_20_vault_style.html archive/top_candidates_previews/
mv top_10_marketable_preview.html archive/top_candidates_previews/
mv top_10_marketable_candidates_email.py archive/top_candidates_previews/
mv send_top_20_emails.py archive/top_candidates_previews/

# Category 4: Utility scripts
mv debug_morgan_stanley.py archive/utility_scripts/
mv fetch_missing_zoho_data.py archive/utility_scripts/
mv find_zoho_contact.py archive/utility_scripts/
mv create_zoho_*.py archive/utility_scripts/
mv extract_rich_bullets.py archive/utility_scripts/
mv load_vault_candidates_to_db.py archive/utility_scripts/
mv validate_fa_extraction.py archive/utility_scripts/
mv monitor_boss_email.sh archive/utility_scripts/
mv check_generation_status.sh archive/utility_scripts/
mv cleanup_root_folder.sh archive/utility_scripts/
mv example_vault_workflow.sh archive/utility_scripts/
mv get-connection-strings.sh archive/utility_scripts/
mv update-container-env.sh archive/utility_scripts/

# Category 5: Old documentation
mv ANONYMIZATION_*.md archive/old_documentation/
mv AZURE_SERVICE_BUS_CONFIG.md archive/old_documentation/
mv BOSS_APPROVAL_EMAIL*.md archive/old_documentation/
mv CLEANUP_PLAN.md archive/old_documentation/
mv CONFIGURATION_FIX_NEEDED.md archive/old_documentation/
mv DEPLOYMENT_VERIFICATION.md archive/old_documentation/
mv INSTALLATION_CHECKLIST.md archive/old_documentation/
mv PHASE*.md archive/old_documentation/
mv SECURITY_REMEDIATION_SUMMARY.md archive/old_documentation/
mv SERVICE_BUS_DELIVERABLES.md archive/old_documentation/
mv VERIFICATION_GUIDE.md archive/old_documentation/
mv ZOHO_API_MIGRATION.md archive/old_documentation/
mv ZOHO_API_QUICKREF.md archive/old_documentation/
mv *_report.txt archive/old_documentation/
mv generation_log.txt archive/old_documentation/
mv duplicates_report_*.csv archive/old_documentation/

# Category 6: Images/assets
mv advisorexample*.png archive/screenshots_assets/
mv top20.png team.png archive/screenshots_assets/
mv cb-*.txt archive/screenshots_assets/

# Category 7: Data exports
mv Candidates_*.csv Deals_*.csv Jobs_*.csv archive/data_exports/
mv zoho_custom_views.json archive/data_exports/
mv zoho_deals_fields.json archive/data_exports/
mv zoho_lead_fields.json archive/data_exports/
mv zoho_leads_*.json archive/data_exports/
mv zoho_notes_fields.json archive/data_exports/
mv zoho_payment_*.json archive/data_exports/
mv zoho_sample_vault_candidate.json archive/data_exports/
mv zoho_vault_candidates_detailed.json archive/data_exports/
```

### Phase 3: Update .gitignore (5 minutes)

```bash
# Add to .gitignore to prevent future clutter
cat >> .gitignore << 'EOF'

# Prevent future HTML preview clutter
*_preview.html
*_debug.html
boss_format_*.html
top_*_*.html
test_*.html

# Prevent test script proliferation
send_*.py
test_*.py

# But explicitly track essential files
!tests/**/*.py
!run_tests.sh
!run_all_tests.py

# Temporary files
*.tmp
*.temp
nul

# Archive directory itself is tracked
!archive/
EOF
```

### Phase 4: Git Commit (3 minutes)

```bash
# Stage the archive
git add archive/

# Commit with descriptive message
git commit -m "Archive development artifacts and older vault alert iterations

- Archive 101 files to reduce root directory clutter by 50%
- Categories: vault alerts (12), test scripts (25), previews (5),
  utilities (14), old docs (22), assets (8), data exports (15)
- Keep only Oct 16, 2024 vault alerts (most recent)
- Update .gitignore to prevent future clutter
- All files retain full git history for retrieval if needed

Ref: ROOT_CLEANUP_PLAN.md"

# Push to remote
git push origin main
```

### Phase 5: Verification (5 minutes)

```bash
# Verify root directory is cleaner
ls -1 | wc -l  # Should be ~50% fewer files

# Verify archive structure
tree archive/ -L 2

# Verify git history preserved
git log --all --full-history -- archive/vault_alerts_iterations/boss_format_advisors_20251011_095703.html

# Verify ignored files work
touch test_new_preview.html
git status  # Should not show untracked file
rm test_new_preview.html
```

---

## ✅ Expected Outcomes

**Before Cleanup:**
```bash
$ ls -1 | wc -l
107  # Approximate count
```

**After Cleanup:**
```bash
$ ls -1 | wc -l
55   # ~50% reduction

$ ls -1 archive/
README.md
vault_alerts_iterations/
test_scripts_oct2024/
top_candidates_previews/
utility_scripts/
old_documentation/
screenshots_assets/
data_exports/

$ git status
On branch upgrade/safe-dependency-updates-2025-10
Changes to be committed:
  new file:   archive/README.md
  new file:   archive/vault_alerts_iterations/...
  ... (101 new files in archive)
  modified:   .gitignore
```

---

## 🔄 Maintenance Guidelines

### Quarterly Review (Every 3 Months)
1. Review archive directories
2. Delete files older than 1 year if confirmed obsolete
3. Update archive README with deletion log

### Ongoing Discipline
**Before committing new files to root:**
- Ask: "Is this a production file or temporary artifact?"
- If temporary → Name it with prefix that's in .gitignore
- If preview → Use standardized naming (test_*, *_preview.html)
- If utility → Place in `scripts/` directory instead

**Git Pre-Commit Hook (Optional):**
```bash
# .git/hooks/pre-commit
#!/bin/bash
# Warn if adding HTML files to root (except manifest.xml)
if git diff --cached --name-only | grep -E '^[^/]+\.html$' | grep -v manifest.xml; then
    echo "⚠️  Warning: Adding HTML file to root directory"
    echo "Consider if this should be in archive/ or tests/ instead"
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
```

---

## 📋 Rollback Procedure (If Needed)

If any archived file is needed urgently:

```bash
# Option 1: Copy back to root
cp archive/vault_alerts_iterations/boss_format_advisors_20251015_180232.html .

# Option 2: Restore with git history
git checkout HEAD~1 -- boss_format_advisors_20251015_180232.html

# Option 3: Full rollback (not recommended)
git revert <commit-hash-of-archive>
```

---

## 🎯 Success Metrics

- ✅ Root directory file count reduced by ≥40%
- ✅ All archived files retain git history
- ✅ .gitignore prevents future clutter
- ✅ Essential production files remain in root
- ✅ Archive structure documented and searchable
- ✅ Zero production impact (no code changes)

---

**Plan Status:** Ready for Execution
**Risk Assessment:** Low (read-only operations, full git history preserved)
**Estimated Duration:** 30 minutes
**Recommended Execution Time:** Off-hours or during next maintenance window
