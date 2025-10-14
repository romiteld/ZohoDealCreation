# Configuration Fix Required

## Issue Identified

The `ZOHO_DEFAULT_OWNER_EMAIL` is currently set to `daniel.romitelli@emailthewell.com`, which is incorrect. This should be set to an actual recruiter who owns candidates in Zoho CRM.

## Current Problem

```bash
# WRONG - In .env.local
ZOHO_DEFAULT_OWNER_EMAIL=daniel.romitelli@emailthewell.com
```

**Why this is wrong:**
- Daniel Romitelli is the Principal Technology Architect (programmer)
- He will never be the owner of any candidates or jobs in Zoho CRM
- This field is used as the default owner when creating new records via the email processing system
- Records created with this owner will not show up for actual recruiters

## Correct Configuration

The `ZOHO_DEFAULT_OWNER_EMAIL` should be set to **Steve Perry** (or another active recruiter):

```bash
# CORRECT - Set to actual recruiter
ZOHO_DEFAULT_OWNER_EMAIL=steve.perry@emailthewell.com
```

### Why Steve Perry?

- Steve is an active recruiter who owns candidates and deals in Zoho CRM
- All email-processed candidates will be assigned to him by default
- This ensures records flow into the correct recruitment workflow

## Access Control for Daniel Romitelli

**Daniel needs unlimited system access for testing/debugging**, which is handled through **Teams Bot role-based access** (NOT owner email):

### Current Teams Bot Access (app/api/teams/query_engine.py)

```python
# Line 97-98: All users currently have full access
intent["owner_filter"] = None  # No owner filtering
```

**This gives everyone unlimited access** - which is fine for now but should eventually be:

### Recommended Future Access Model

```python
# Executive users (unlimited access)
EXECUTIVE_EMAILS = [
    "steve@emailthewell.com",
    "brandon@emailthewell.com",
    "daniel.romitelli@emailthewell.com"  # Tech architect needs full access
]

# In QueryEngine.process_query():
if user_email in EXECUTIVE_EMAILS:
    intent["owner_filter"] = None  # Full access
else:
    intent["owner_filter"] = user_email  # Filtered to own records
```

## Action Items

### Immediate Fix (Production)

1. **Update .env.local**:
   ```bash
   ZOHO_DEFAULT_OWNER_EMAIL=steve.perry@emailthewell.com
   ```

2. **Update Azure Container Apps** (production):
   ```bash
   az containerapp update --name well-intake-api \
     --resource-group TheWell-Infra-East \
     --set-env-vars ZOHO_DEFAULT_OWNER_EMAIL=steve.perry@emailthewell.com
   ```

3. **Verify OAuth Service** (well-zoho-oauth-v2):
   - Check if OAuth service also uses this variable
   - Update if needed

### Future Enhancement

1. **Implement Executive Access List** in QueryEngine:
   - Add `EXECUTIVE_EMAILS` constant
   - Check user_email against list before applying owner filter
   - Ensures Daniel has unlimited query access for debugging

2. **Document Access Tiers**:
   - Executive: Full access (Steve, Brandon, Daniel)
   - Recruiter: Filtered to own records (owner_email = user_email)
   - Admin: API access only (via API_KEY)

## Testing After Fix

```bash
# 1. Verify owner email is set correctly
curl http://localhost:8000/health | jq .zoho_owner_email

# 2. Test email processing creates record with correct owner
# Send test email → Check Zoho CRM → Verify owner is Steve Perry

# 3. Test Teams Bot query access (Daniel should have full access)
# In Teams: "@Well Bot show me all vault candidates"
# Should return all candidates regardless of owner
```

## Documentation Updates Needed

1. **CLAUDE.md** - Update environment variable documentation:
   ```markdown
   ZOHO_DEFAULT_OWNER_EMAIL=steve.perry@emailthewell.com  # Default owner for email-processed records
   ```

2. **ZOHO_API_MIGRATION.md** - Add access control section:
   ```markdown
   ## Access Control

   - **ZOHO_DEFAULT_OWNER_EMAIL**: Default owner for new records (should be active recruiter)
   - **Teams Bot Access**: All users currently have full query access
   - **Future**: Executive vs regular user tiering planned
   ```

## Related Files

- `.env.local` - Local environment configuration
- `app/api/teams/query_engine.py:97-98` - Owner filter logic
- `app/api/teams/routes.py:1673-1675` - Boss email recipients
- `app/integrations.py` - ZohoApiClient using default owner

## Priority

**HIGH** - This affects data ownership and record routing in production. Should be fixed before processing more emails.
