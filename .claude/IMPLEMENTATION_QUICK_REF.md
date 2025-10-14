# Vault Alerts Zoho API Migration - Quick Reference

**Plan Version**: v3_final_with_user_approval
**Total Phases**: 9
**Estimated Time**: 9.25 hours
**Status Tracker**: `.claude/implementation_state.json`

## Phase Execution Order

```
1. Anonymizer Consolidation (60 min)      → DELETE duplicates, update imports
2. Feature Flag + Telemetry (30 min)      → NEW telemetry.py, USE_ZOHO_API flag
3. Async Zoho Client (120 min)           → httpx migration, 29-field mapping
4. VaultAlertsGenerator (75 min)         → Dual source support, cache v2
5. QueryEngine Lazy Init (30 min)        → Circuit breaker fix
6. Teams Bot Test (30 min)               → Invoke regression test
7. Boss Email Handler (45 min)           → NEW /admin endpoint
8. Comprehensive Testing (90 min)        → 6+ test scenarios
9. Documentation (45 min)                → Update guides, API docs
```

## Critical "DO NOT" List

⚠️ **NEVER CHANGE THESE**:

1. **RedisCacheManager API**: Use `disconnect()` NOT `close()`
2. **HTML Dictionary Keys**: Use `advisor_html` and `executive_html` (NOT `html_advisor`)
3. **Email Method**: `WeeklyDigestScheduler.send_email()` is SYNCHRONOUS (no `await`)
4. **LangGraph State**: MUTATE state dict, don't return new dict
5. **Circuit Breaker**: Use PUBLIC helpers only:
   - `_is_circuit_breaker_open()`
   - `_record_circuit_breaker_failure()`
   - DO NOT call `record_success()` (not exposed)
6. **Temperature**: Always `temperature=1` for GPT-5
7. **httpx Imports**: `from httpx import AsyncClient, Timeout, Limits, HTTPStatusError`

## File → Phase Mapping

### Phase 1 Files
- **DELETE**: `app/jobs/anonymizer.py` (entire file)
- **MODIFY**: `app/jobs/vault_alerts_generator.py` (delete lines 1020-1069)
- **MODIFY**: `generate_boss_format_langgraph.py` (delete lines 216-253)
- **UPDATE**: `tests/test_anonymizer.py` (change imports)
- **UPDATE**: `ANONYMIZER_QUICKSTART.md`, `ANONYMIZATION_TEST_SUMMARY.md`

### Phase 2 Files
- **CREATE**: `app/utils/telemetry.py`
- **MODIFY**: `app/config/feature_flags.py` (add USE_ZOHO_API)
- **MODIFY**: `.env.local` (add USE_ZOHO_API=false)

### Phase 3 Files
- **MODIFY**: `app/integrations.py` (add 7 new functions/methods)

### Phase 4 Files
- **MODIFY**: `app/jobs/vault_alerts_generator.py` (add lifecycle, update loader)

### Phase 5 Files
- **MODIFY**: `app/api/teams/query_engine.py` (add lazy init)

### Phase 6 Files
- **CREATE**: `tests/test_teams_invoke.py`

### Phase 7 Files
- **MODIFY**: `app/api/teams/routes.py` (add /admin/send_vault_alerts_to_bosses)

### Phase 8 Files
- **CREATE**: `tests/test_anonymizer_consolidated.py`
- **CREATE**: `tests/test_data_source_parity.py`

### Phase 9 Files
- **MODIFY**: `VAULT_ALERTS_GUIDE.md`, `ANONYMIZER_QUICKSTART.md`, `ANONYMIZATION_TEST_SUMMARY.md`
- **CREATE**: API endpoint documentation

## Test Commands by Phase

```bash
# Phase 1: Anonymizer
pytest tests/test_anonymizer_consolidated.py -v

# Phase 3: Zoho mapping
pytest tests/test_data_source_parity.py::test_zoho_field_mapping -v

# Phase 4: Data source parity
pytest tests/test_data_source_parity.py::test_data_source_parity -v

# Phase 6: Teams bot
pytest tests/test_teams_invoke.py -v

# Phase 8: Full suite
pytest tests/test_anonymizer_consolidated.py -v
pytest tests/test_data_source_parity.py -v
pytest tests/test_teams_invoke.py -v
pytest tests/ -k vault -v
pytest --cov=app --cov-report=term-missing

# Quick smoke test (all phases)
pytest tests/ -v --tb=short
```

## Schema Mapping Reference

**PostgreSQL Table**: `vault_candidates` (29 columns)
**Verification**: `PGPASSWORD='W3llDB2025Pass' psql -h well-intake-db-0903.postgres.database.azure.com -U adminuser -d wellintake -c "\d vault_candidates"`

**Zoho API Module**: `Leads` (displayed as "Candidates X Jobs")
**Custom View**: `_Vault Candidates` (ID: `6221978000090941003`)
**Field Mappings**: See `zoho api modules field mappings.md:60-139`

### Critical Field Mappings
```python
# Zoho API Name → PostgreSQL Column
'Candidate_Locator' → 'twav_number'
'Candidate_Name' → 'candidate_name'
'Title' → 'title'
'Employer' → 'firm'
'Book_Size_AUM' → 'aum'
'Production_L12Mo' → 'production'
'Desired_Comp' → 'compensation'
'When_Available' → 'availability'
'Headline' → 'headline'
# ... (29 total fields in map_to_vault_schema)
```

## Context Recovery Protocol

If Claude loses context mid-implementation:

```bash
# 1. Check current state
cat .claude/implementation_state.json | jq '.current_phase'

# 2. See what's completed
git diff main...HEAD --stat

# 3. Read last phase checkpoint
cat .claude/phase{N}_complete.md

# 4. Restore Claude with:
# "Continue vault alerts migration from phase {N}.
#  Read .claude/implementation_state.json and .claude/phase{N}_complete.md"
```

## Production Deployment Checklist

Before `docker build`:

- [ ] All `CandidateAnonymizer` imports removed (`rg "CandidateAnonymizer"` → 0 results)
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Coverage ≥85% (`pytest --cov=app`)
- [ ] `.env.local` has `USE_ZOHO_API=false` (start disabled)
- [ ] `implementation_state.json` shows all phases completed
- [ ] Git commit message references plan version: "v3_final_with_user_approval"

## Emergency Rollback

```bash
# If Zoho API causes issues in production
curl -X POST "https://well-intake-api.../api/teams/admin/toggle-feature" \
  -H "X-API-Key: $API_KEY" \
  -d '{"feature": "USE_ZOHO_API", "enabled": false}'

# Verify rollback
curl "https://well-intake-api.../health" | jq '.feature_flags.USE_ZOHO_API'
# Should return: false
```

## Boss Email Test Command

```bash
# Trigger boss email generation (2-3 hour workflow)
curl -X POST "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/admin/send_vault_alerts_to_bosses?from_date=2025-01-01" \
  -H "X-API-Key: $API_KEY"

# Expected response:
{
  "status": "success",
  "emails_sent": 3,
  "execution_time_ms": 9847234,
  "from_date": "2025-01-01"
}
```

## Key Environment Variables

```bash
# Required for Zoho API
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth-v2.azurewebsites.net
ZOHO_VAULT_VIEW_ID=6221978000090941003

# Required for telemetry
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...;...

# Required for Redis cache
AZURE_REDIS_CONNECTION_STRING=rediss://...

# Feature flags
USE_ZOHO_API=false  # Start disabled
PRIVACY_MODE=true
```

---

**Last Updated**: 2025-10-14
**Maintained By**: Claude (Vault Alerts Migration Project)