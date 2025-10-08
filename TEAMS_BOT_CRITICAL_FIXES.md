# Teams Bot Critical Fixes - October 8, 2025

## Problems Identified

### 1. **CRITICAL: Missing Environment Variables in Azure Container Apps**
**Impact**: Digest generation returns 0 candidates, should return 144
**Root Cause**: `ZOHO_VAULT_VIEW_ID` and `ZCAND_MODULE` not configured in Azure

#### Evidence:
```bash
# Local environment check shows:
ZOHO_VAULT_VIEW_ID: NOT SET
ZCAND_MODULE: NOT SET
```

#### Fix Required:
Add to Azure Container Apps environment variables:
```bash
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars \
    "ZOHO_VAULT_VIEW_ID=6221978000090941003" \
    "ZCAND_MODULE=Leads"
```

**Location in Code**: `app/integrations.py:1620-1626`
```python
# Use Leads module (displayed as Candidates in Zoho)
module_name = os.getenv("ZCAND_MODULE", "Leads")
vault_view_id = os.getenv("ZOHO_VAULT_VIEW_ID", "6221978000090941003")

# Fetch using custom view (supports up to 2000 records with simple pagination)
params = {
    "cvid": vault_view_id,  # Use custom view to filter server-side
    ...
}
```

---

### 2. **Natural Language Query Engine: Wrong Table Name**
**Impact**: All queries fail with "I didn't find any vault_candidates matching your query"
**Root Cause**: Query engine uses table name `vault_candidates` instead of Zoho module name `Leads`

#### Evidence from Screenshots:
- "how many deals last month" → "I didn't find any deals matching your query"
- "how many candidates are in the vault" → "I didn't find any vault_candidates matching your query"

#### Issue Location: `app/api/teams/query_engine.py:156-170`
```python
async def _build_query(self, intent: Dict[str, Any]) -> Tuple[List[Dict], List]:
    table = intent.get("table", "vault_candidates")  # ❌ WRONG TABLE NAME
    zoho_client = ZohoApiClient()

    # Route to appropriate query method based on table
    if table == "deals":
        # Works correctly for deals
        ...
    elif table == "vault_candidates":  # ❌ WRONG - should be checking intent type
        # Tries to use PostgreSQL table name instead of Zoho API
        ...
```

**Problem**: Query engine was designed for PostgreSQL database queries but now needs to query Zoho CRM API instead.

#### Fix Required:
Rewrite query engine to use ZohoClient methods:
- `vault_candidates` queries → `zoho_client.fetch_vault_candidates()`
- `deals` queries → `zoho_client.search_deals()`
- Count queries → use `len()` on results

---

### 3. **Adaptive Card Button Actions Not Triggering**
**Impact**: Clicking "Generate Digest" or "My Preferences" buttons does nothing
**Root Cause**: Invoke activity handler may not be properly routing button actions

#### Code Location: `app/api/teams/routes.py:483-595` (handle_invoke_activity)

Need to verify:
1. Are invoke activities being received?
2. Is action routing working correctly?
3. Are InvokeResponse objects being sent properly?

#### Check invoke handler logs:
```python
async def handle_invoke_activity(turn_context: TurnContext, db: asyncpg.Connection):
    """Handle invoke activities from adaptive card buttons."""
    value = turn_context.activity.value
    action = value.get("action") if value else None

    logger.info(f"Invoke activity received - Action: {action}")  # ← Add this log
```

---

## Deployment Plan

### Phase 1: Environment Variables (Immediate - 5 minutes)
```bash
# 1. Add missing environment variables to Azure Container Apps
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars \
    "ZOHO_VAULT_VIEW_ID=6221978000090941003" \
    "ZCAND_MODULE=Leads"

# 2. Verify variables are set
az containerapp show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "properties.template.containers[0].env"

# 3. Restart container to apply changes
az containerapp revision restart \
  --name teams-bot \
  --resource-group TheWell-Infra-East
```

### Phase 2: Query Engine Rewrite (30-45 minutes)
Rewrite `app/api/teams/query_engine.py` to use Zoho API instead of database:

**Before (Database-centric):**
```python
# Build SQL query and execute against PostgreSQL
table = intent.get("table", "vault_candidates")
if table == "vault_candidates":
    # Build SQL query...
```

**After (Zoho API-centric):**
```python
# Use ZohoClient methods to fetch from Zoho CRM
zoho_client = ZohoApiClient()

if intent_type == "count_candidates":
    candidates = await zoho_client.fetch_vault_candidates(limit=2000)
    count = len(candidates)
    return {"text": f"There are {count} candidates in the vault"}

elif intent_type == "count_deals":
    # Build date filters
    from_date = entities.get("from_date")
    to_date = entities.get("to_date")
    deals = await zoho_client.search_deals(...)
    return {"text": f"Found {len(deals)} deals"}
```

### Phase 3: Button Invoke Handler (15-20 minutes)
Add comprehensive logging and error handling to invoke handler:

```python
async def handle_invoke_activity(turn_context: TurnContext, db: asyncpg.Connection):
    """Handle invoke activities from adaptive card buttons."""
    try:
        value = turn_context.activity.value
        action = value.get("action") if value else None

        # Enhanced logging
        logger.info(f"=== INVOKE ACTIVITY RECEIVED ===")
        logger.info(f"Action: {action}")
        logger.info(f"Value: {json.dumps(value, indent=2)}")

        if action == "generate_digest_preview":
            # Process digest generation...
            logger.info("Processing digest generation from button click")
        elif action == "show_preferences":
            # Show preferences...
            logger.info("Showing preferences from button click")
        else:
            logger.warning(f"Unhandled action: {action}")
    except Exception as e:
        logger.error(f"Error in invoke handler: {e}", exc_info=True)
```

---

## Testing Checklist

After deployment, test in order:

### 1. Environment Variables
```bash
# SSH into container and verify
echo $ZOHO_VAULT_VIEW_ID  # Should show: 6221978000090941003
echo $ZCAND_MODULE        # Should show: Leads
```

### 2. Digest Generation
In Teams Bot, type:
- `digest global` → Should show candidates
- `digest advisors` → Should show financial advisors
- `digest c_suite` → Should show executives

**Expected**: Preview card with candidate cards, not "Showing 0 of 0"

### 3. Natural Language Queries
In Teams Bot, type:
- "how many candidates are in the vault" → Should return count (e.g., 144)
- "how many deals last month" → Should return deal count
- "show me my deals from Q4" → Should list deals (for recruiters: filtered by owner)

**Expected**: Actual counts and data, not "I didn't find any..."

### 4. Button Interactions
Click buttons on help card:
- "Generate Digest" → Should show digest preview
- "My Preferences" → Should show preferences form

**Expected**: Cards appear, not silent failure

---

## Root Cause Summary

1. **Environment variables missing** → Digest uses wrong/missing view ID
2. **Query engine architectural mismatch** → Designed for PostgreSQL, now needs Zoho API
3. **Button handler may need logging** → Can't debug without visibility

## Files to Modify

1. `app/api/teams/query_engine.py` - Complete rewrite of `_build_query()` method
2. `app/api/teams/routes.py` - Add logging to `handle_invoke_activity()`
3. Azure Container Apps configuration - Add environment variables

## Estimated Time
- Phase 1 (Env vars): 5 minutes
- Phase 2 (Query engine): 45 minutes
- Phase 3 (Button handler): 20 minutes
- Testing: 15 minutes

**Total: ~1.5 hours**
