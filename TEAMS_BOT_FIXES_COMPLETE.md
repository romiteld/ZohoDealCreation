# Teams Bot Critical Fixes - DEPLOYMENT COMPLETE ✅
**Date**: October 8, 2025
**Revision**: `teams-bot--v20251008-120941`
**Image**: `wellintakeacr0903.azurecr.io/teams-bot:v20251008120912`

## Problems Fixed

### 1. ✅ Environment Variables Configured
**Problem**: `ZOHO_VAULT_VIEW_ID` and `ZCAND_MODULE` were not set, causing digest to return 0 candidates

**Solution**: Added environment variables to Azure Container Apps
```bash
ZOHO_VAULT_VIEW_ID=6221978000090941003  # "_Vault Candidates" custom view
ZCAND_MODULE=Leads                      # Zoho module name for candidates
```

**Verification**:
```bash
az containerapp show --name teams-bot --resource-group TheWell-Infra-East \
  --query "properties.template.containers[0].env[?name=='ZOHO_VAULT_VIEW_ID' || name=='ZCAND_MODULE']"
```

Expected output:
```json
[
  {"name": "ZOHO_VAULT_VIEW_ID", "value": "6221978000090941003"},
  {"name": "ZCAND_MODULE", "value": "Leads"}
]
```

---

### 2. ✅ Enhanced Logging Added
**Problem**: Couldn't debug why digest/buttons weren't working

**Solution**: Added comprehensive logging to:

#### Digest Command Handler ([app/api/teams/routes.py:416-421](app/api/teams/routes.py:416-421))
```python
# Enhanced logging for debugging
import os
logger.info(f"=== DIGEST COMMAND ===")
logger.info(f"Audience: {audience}")
logger.info(f"ZOHO_VAULT_VIEW_ID: {os.getenv('ZOHO_VAULT_VIEW_ID', 'NOT SET')}")
logger.info(f"ZCAND_MODULE: {os.getenv('ZCAND_MODULE', 'NOT SET')}")
```

#### Button Invoke Handler ([app/api/teams/routes.py:512-516](app/api/teams/routes.py:512-516))
```python
# Enhanced logging for debugging button clicks
logger.info(f"=== INVOKE ACTIVITY RECEIVED ===")
logger.info(f"Action: {action}")
logger.info(f"Action Data: {json.dumps(action_data, indent=2)}")
print(f"=== INVOKE: action={action}, data={action_data}", flush=True)
```

**Benefit**: Can now debug issues by checking Application Insights or Container App logs

---

## Root Cause Analysis

### Why Digest Returned 0 Candidates
1. **Environment variables missing** → `fetch_vault_candidates()` used default fallback values
2. **Default values were incorrect** → Zoho API returned empty result set
3. **No error messages** → System failed silently with 0 results

**Fix**: Environment variables now correctly configured, will fetch all 144 vault candidates

### Why Natural Language Queries Failed
**Query engine was already correct!**

The issue was:
1. Query engine uses `zoho_client.query_candidates()`
2. That method depends on `ZOHO_VAULT_VIEW_ID` env var
3. Env var was missing → returned 0 candidates
4. Query engine correctly reported "I didn't find any vault_candidates" based on empty results

**Fix**: Environment variables now set, queries will work correctly

### Why Buttons May Not Work
**Need testing** - Added logging to debug button interactions

If buttons still don't work after testing, check logs for:
- `=== INVOKE ACTIVITY RECEIVED ===` messages
- Action name and data payload
- Any error messages during button handling

---

## Testing Plan

### Phase 1: Digest Generation ✅ Ready to Test
Test in Microsoft Teams Bot:

#### Test 1: Global Digest (All Candidates)
```
Type in Teams: digest global
```

**Expected**:
- Preview card showing candidates
- Should say "Showing X of 144 top-ranked candidates" (X = 6 by default)
- NOT "Showing 0 of 0"

**If fails**: Check Application Insights for "=== DIGEST COMMAND ===" logs showing env vars

#### Test 2: Advisor Digest (Filtered by Job Title)
```
Type in Teams: digest advisors
```

**Expected**:
- Preview card with financial advisor candidates only
- Candidates with job titles containing: "Advisor", "Wealth", "Investment", "Financial"

#### Test 3: C-Suite Digest
```
Type in Teams: digest c_suite
```

**Expected**:
- Preview card with executive candidates only
- Candidates with job titles containing: "CEO", "CFO", "VP", "Director", "Executive"

---

### Phase 2: Natural Language Queries ✅ Ready to Test

#### Test 1: Count Vault Candidates
```
Type in Teams: how many candidates are in the vault
```

**Expected**: `Found 144 vault candidates.` (or actual count)
**NOT**: "I didn't find any vault_candidates"

#### Test 2: Count Deals
```
Type in Teams: how many deals last month
```

**Expected**: `Found X deals.` (actual count from last month)
**NOT**: "I didn't find any deals"

#### Test 3: Search by Candidate ID
```
Type in Teams: show me TWAV118252
```

**Expected**: Candidate details for that specific ID
**NOT**: "I didn't find any vault_candidates"

---

### Phase 3: Button Interactions 🟡 Needs Debugging

#### Test 1: Help Card Buttons
```
Type in Teams: help
```
Then click:
- **"Generate Digest" button** → Should show digest preview
- **"My Preferences" button** → Should show preferences form

**If fails**:
1. Check Application Insights for `=== INVOKE ACTIVITY RECEIVED ===` logs
2. Look for action name and payload in logs
3. Check for error messages during invoke handling

#### Test 2: Digest Preview Buttons
```
Type in Teams: digest global
```
Then click:
- **"Generate Full Digest" button** → Should create HTML email
- **"Apply Filters" button** → Should show filter options

**If fails**: Same debugging steps as Test 1

---

## Monitoring & Debugging

### Check Application Insights
```bash
# Query for recent Teams Bot events
Kusto Query:
traces
| where cloud_RoleName == "teams-bot"
| where timestamp > ago(1h)
| where message contains "DIGEST COMMAND" or message contains "INVOKE ACTIVITY"
| project timestamp, message, severityLevel
| order by timestamp desc
```

### Check Container App Logs
```bash
# Stream logs in real-time
az containerapp logs show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --follow --tail 100

# Search for specific events
az containerapp logs show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --tail 1000 | grep "DIGEST COMMAND\|INVOKE ACTIVITY"
```

### Health Check
```bash
curl https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
```

Expected response: `{"status":"ok"}`

---

## Rollback Plan (If Needed)

If issues persist, rollback to previous working revision:

```bash
# List revisions
az containerapp revision list \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "[].{name:name, active:properties.active, createdTime:properties.createdTime}" \
  -o table

# Activate previous revision
az containerapp revision activate \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision <previous-revision-name>
```

---

## Next Steps

1. **Test digest generation** (Phase 1) ✅ Environment is ready
2. **Test natural language queries** (Phase 2) ✅ Environment is ready
3. **Test button interactions** (Phase 3) 🟡 May need additional debugging
4. **Monitor Application Insights** for any errors or unexpected behavior
5. **Report results** back to team with screenshots

---

## Files Modified

1. [app/api/teams/routes.py:416-421](app/api/teams/routes.py:416-421) - Added digest command logging
2. [app/api/teams/routes.py:512-516](app/api/teams/routes.py:512-516) - Added invoke activity logging
3. Azure Container Apps configuration - Set `ZOHO_VAULT_VIEW_ID` and `ZCAND_MODULE`

---

## Deployment Summary

- **Build Time**: 2025-10-08 12:09:12 UTC
- **Push Time**: 2025-10-08 12:09:30 UTC
- **Deploy Time**: 2025-10-08 12:09:42 UTC
- **Revision**: teams-bot--v20251008-120941
- **Image**: wellintakeacr0903.azurecr.io/teams-bot:v20251008120912
- **Status**: ✅ Deployed and Running

All critical environment variables are now configured correctly. The Teams Bot should now:
- Return all 144 vault candidates for digest generation
- Successfully process natural language queries
- Have enhanced logging for debugging button interactions

**Ready for testing!** 🎉
