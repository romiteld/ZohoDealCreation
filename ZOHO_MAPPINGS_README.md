# Zoho CRM Field Mappings - Single Source of Truth

## Overview

**File:** `zoho_field_mappings.json`
**Generated:** 2025-10-15 (auto-generated from live Zoho CRM API v8)
**Total Modules:** 68 API-accessible modules
**Total Fields:** 1,518 fields across all modules

This is the **CANONICAL** source of truth for all Zoho CRM field mappings in The Well Intake API codebase.

## Quick Start

```python
import json

# Load mappings
with open('zoho_field_mappings.json', 'r') as f:
    mappings = json.load(f)

# Get vault candidates module info
vault_module = mappings['modules']['vault_candidates']
print(vault_module['module_name'])      # "Leads"
print(vault_module['custom_view_id'])   # "6221978000090941003"

# Get vault candidate fields
vault_fields = mappings['modules']['vault_candidates']['fields']
for field_name, field_info in vault_fields.items():
    print(f"{field_name}: {field_info['data_type']}")
```

## File Structure

```json
{
  "meta": {
    "generated_at": "ISO timestamp",
    "zoho_api_version": "v8",
    "total_modules": 68,
    "total_fields": 1518
  },
  "modules": {
    "vault_candidates": {
      "module_name": "Leads",
      "api_name": "Leads",
      "custom_view_id": "6221978000090941003",
      "custom_view_name": "_Vault Candidates",
      "filter_field": "Publish_to_Vault",
      "filter_value": true,
      "notes": "Vault candidates are stored in Leads module",
      "fields": {
        "Candidate_Locator": {
          "api_name": "Candidate_Locator",
          "data_type": "text",
          "custom_field": true,
          "description": "TWAV number identifier"
        }
      }
    }
  }
}
```

## Critical Vault Candidate Information

### Module Details
- **Module Name:** `Leads` (NOT "Candidates" module)
- **Custom View ID:** `6221978000090941003`
- **Custom View Name:** `_Vault Candidates`
- **Filter Field:** `Publish_to_Vault = true`
- **Total Records:** 164 vault candidates (as of 2025-10-15)

### API Endpoint
```
GET https://www.zohoapis.com/crm/v8/Leads?cvid=6221978000090941003&per_page=200
```

### Key Fields (17 total)
1. **Candidate_Locator** - TWAV number (e.g., "TWAV118373")
2. **Full_Name** - Candidate full name
3. **First_Name** - First name
4. **Last_Name** - Last name
5. **Current_Location** - City, State format
6. **Date_Published_to_Vault** - Publication date
7. **Publish_to_Vault** - Boolean filter field
8. **Pipeline_Stage** - Current stage
9. **Interview_Recording_Link** - Zoom recording URL
10. **Full_Interview_URL** - Complete interview URL
11. **Designation** - Role/title
12. **Mobility_Details** - Travel preferences
13. **Is_Mobile** - Yes/No mobility flag
14. **Owner** - Lookup to user (name, id, email)
15. **Created_Time** - ISO 8601 timestamp
16. **Modified_Time** - ISO 8601 timestamp
17. **Candidate_Type** - "Vault" for vault candidates

## Usage Examples

### Fetching Vault Candidates

```python
import requests
import json

# Load mappings to get correct module info
with open('zoho_field_mappings.json', 'r') as f:
    mappings = json.load(f)

vault_config = mappings['modules']['vault_candidates']

# Get OAuth token
oauth_response = requests.get("https://well-zoho-oauth-v2.azurewebsites.net/oauth/token")
token = oauth_response.json()['access_token']

# Fetch vault candidates using custom view
url = f"https://www.zohoapis.com/crm/v8/{vault_config['module_name']}"
params = {
    "cvid": vault_config['custom_view_id'],
    "per_page": 200,
    "page": 1
}
headers = {"Authorization": f"Bearer {token}"}

response = requests.get(url, headers=headers, params=params)
candidates = response.json().get('data', [])

print(f"Found {len(candidates)} vault candidates")
```

### Accessing Field Metadata

```python
import json

with open('zoho_field_mappings.json', 'r') as f:
    mappings = json.load(f)

# Get all Leads fields
leads_fields = mappings['modules']['Leads']['fields']

# Find custom fields
custom_fields = {
    name: info
    for name, info in leads_fields.items()
    if info.get('custom_field', False)
}

print(f"Leads module has {len(custom_fields)} custom fields")

# Get picklist values
candidate_type_field = leads_fields.get('Candidate_Type', {})
if 'pick_list_values' in candidate_type_field:
    print("Candidate Type options:")
    for option in candidate_type_field['pick_list_values']:
        print(f"  - {option['display_value']}")
```

### Validating Field Names

```python
import json

def validate_field_exists(module_name: str, field_name: str) -> bool:
    """Check if a field exists in a module."""
    with open('zoho_field_mappings.json', 'r') as f:
        mappings = json.load(f)

    module = mappings['modules'].get(module_name)
    if not module:
        return False

    return field_name in module.get('fields', {})

# Usage
if validate_field_exists('Leads', 'Candidate_Locator'):
    print("✅ Field exists")
else:
    print("❌ Field not found")
```

## Module Statistics

### Top 10 Modules by Field Count

1. **Leads** (Candidates) - 136 fields
2. **Contacts** - 94 fields
3. **Accounts** - 89 fields
4. **Deals** - 78 fields
5. **Products** - 52 fields
6. **Price_Books** - 48 fields
7. **Quotes** - 45 fields
8. **Sales_Orders** - 42 fields
9. **Purchase_Orders** - 40 fields
10. **Invoices** - 38 fields

### Custom Views by Module

- **Leads:** 44 custom views (includes `_Vault Candidates`)
- **Deals:** 38 custom views
- **Contacts:** 31 custom views
- **Accounts:** 22 custom views
- **Activities:** 15 custom views
- **Tasks:** 9 custom views

## Regenerating Mappings

To update the mappings from live Zoho API:

```bash
python3 generate_zoho_mappings.py
```

This will:
1. Fetch all modules from Zoho CRM
2. For each module, fetch all fields with metadata
3. Fetch all custom views for key modules
4. Include picklist values and lookup relationships
5. Generate updated `zoho_field_mappings.json`

**Runtime:** ~30-45 seconds

## Common Patterns

### Working with Lookup Fields

```python
# Owner field is a lookup
owner_field = mappings['modules']['Leads']['fields']['Owner']
print(owner_field['data_type'])  # "lookup"
print(owner_field.get('lookup', {}).get('module'))  # Module it looks up to

# Access owner info from API response
candidate = {
    "Owner": {
        "name": "Steve Perry",
        "id": "6221978000000291003",
        "email": "steve.perry@emailthewell.com"
    }
}
owner_email = candidate['Owner']['email']
```

### Working with Picklist Fields

```python
# Get all valid options for a picklist
mobility_field = mappings['modules']['Leads']['fields']['Is_Mobile']
valid_options = [
    opt['display_value']
    for opt in mobility_field.get('pick_list_values', [])
]
print(valid_options)  # ['Yes', 'No']
```

### Date/DateTime Formatting

```python
from datetime import datetime

# Zoho uses ISO 8601 format for datetime fields
created_time = mappings['modules']['Leads']['fields']['Created_Time']
print(created_time['data_type'])  # "datetime"

# Format for Zoho API
now = datetime.utcnow().isoformat() + 'Z'

# Parse from Zoho API
zoho_timestamp = "2025-10-15T12:34:56Z"
parsed = datetime.fromisoformat(zoho_timestamp.replace('Z', '+00:00'))
```

## OAuth Service

### Getting Access Token

```bash
curl "https://well-zoho-oauth-v2.azurewebsites.net/oauth/token"
```

**Response:**
```json
{
  "access_token": "1000.abc123...",
  "api_domain": "https://www.zohoapis.com",
  "cached": true,
  "expires_at": "2025-10-15T13:45:00Z"
}
```

### Using in Code

```python
import requests

def get_zoho_headers():
    """Get Zoho API headers with OAuth token."""
    response = requests.get(
        "https://well-zoho-oauth-v2.azurewebsites.net/oauth/token"
    )
    token = response.json()['access_token']
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

headers = get_zoho_headers()
# Use headers in Zoho API requests
```

## Field Types Reference

### Standard Field Types
- **text** - Single line text (max 255 chars)
- **textarea** - Multi-line text
- **email** - Email address validation
- **phone** - Phone number
- **website** - URL validation
- **picklist** - Single select dropdown
- **multiselectpicklist** - Multiple select
- **lookup** - Reference to another module
- **boolean** - True/False
- **integer** - Whole numbers
- **bigint** - Large integers
- **double** - Decimal numbers
- **currency** - Money values
- **date** - Date only (YYYY-MM-DD)
- **datetime** - Date and time (ISO 8601)

### Special Field Types
- **autonumber** - Auto-generated sequence
- **ownerlookup** - User lookup
- **userlookup** - User reference
- **profileimage** - Image upload
- **fileupload** - File attachment

## Important Notes

### ⚠️ Critical Rules

1. **Module Name:** Vault candidates are in **Leads** module, NOT "Candidates"
2. **Custom View:** Always use `cvid=6221978000090941003` for vault queries
3. **Filter Field:** `Publish_to_Vault` (boolean) controls vault membership
4. **API Version:** Always use `/crm/v8/` endpoints
5. **OAuth Service:** Use `https://well-zoho-oauth-v2.azurewebsites.net/oauth/token`

### Best Practices

- Always validate field names against this mapping file before API calls
- Use custom view ID for vault queries (not search criteria)
- Cache OAuth tokens (they're cached by the service for 50 minutes)
- Paginate large result sets (max 200 per page)
- Check `more_records` in API response for pagination

## Troubleshooting

### "INVALID_MODULE" Error
```
{"code":"INVALID_MODULE","message":"the module name given seems to be invalid"}
```
**Solution:** Check module name in mappings. Vault = "Leads", not "Candidates"

### "INVALID_DATA" Error
```
{"code":"INVALID_DATA","message":"the given data is invalid"}
```
**Solution:** Validate field names and types match mappings exactly

### Empty Results
```json
{"data": [], "info": {"more_records": false}}
```
**Solutions:**
1. Check custom view ID is correct: `6221978000090941003`
2. Verify records exist with `Publish_to_Vault = true`
3. Check OAuth token is valid

### 401 Unauthorized
**Solutions:**
1. Verify OAuth service URL: `/oauth/token` (not `/api/token`)
2. Check token hasn't expired
3. Verify credentials in environment variables

## Related Files

- `zoho_field_mappings.json` - Main mapping file (THIS IS THE SOURCE OF TRUTH)
- `generate_zoho_mappings.py` - Script to regenerate mappings
- `ZOHO_MAPPINGS_SUMMARY.txt` - Quick reference statistics
- `app/integrations.py` - OAuth token retrieval implementation
- `app/workers/vault_marketability_worker.py` - Vault query implementation

## Support

For questions about Zoho field mappings:
1. Check this README first
2. Verify field exists in `zoho_field_mappings.json`
3. Test with Zoho API directly if needed
4. Regenerate mappings if Zoho schema changed

---

**Last Updated:** 2025-10-15
**Zoho API Version:** v8
**Total Modules:** 68
**Total Fields:** 1,518
