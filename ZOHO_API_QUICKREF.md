# Zoho API Quick Reference

## Feature Flag Toggle

```bash
# Use PostgreSQL (default, safe)
export USE_ZOHO_API=false

# Use Zoho API (new, requires testing)
export USE_ZOHO_API=true
```

## Key Files

| File | Purpose | Key Functions |
|------|---------|---------------|
| `app/integrations.py` | Zoho API client | `ZohoApiClient`, `map_to_vault_schema()` |
| `app/jobs/vault_alerts_generator.py` | Dual source logic | `_agent_database_loader()` |
| `app/utils/anonymizer.py` | Canonical anonymizer | `anonymize_candidate_data()` |
| `app/config/feature_flags.py` | Feature flags | `USE_ZOHO_API` |
| `app/utils/telemetry.py` | Telemetry client | `TelemetryClient` |

## Schema Mapping (29 Fields)

| PostgreSQL | Zoho API | Type |
|-----------|----------|------|
| `twav_number` | `Candidate_Locator` | String |
| `firm` | `Employer` | String |
| `aum` | `Book_Size_AUM` | Float |
| `production` | `Production_L12Mo` | Float |
| `compensation` | `Desired_Comp` | String |
| `city` | `Current_Location` (parsed) | String |
| `state` | `Current_Location` (parsed) | String |
| `transferable_book` | `Transferable_Book_of_Business` | String |
| `licenses` | `Licenses_and_Exams` | String |
| `availability` | `When_Available` | String |

**Full mapping**: See `ZOHO_API_MIGRATION.md` or `app/integrations.py:1243-1274`

## Common Commands

### Testing
```bash
# Schema mapping test
pytest tests/test_data_source_parity.py::test_zoho_field_mapping -v

# Data source parity test
pytest tests/test_data_source_parity.py::test_data_source_parity -v

# Anonymizer test
pytest tests/test_anonymizer_consolidated.py -v

# All vault tests
pytest tests/ -k vault -v
```

### Development
```bash
# Run with Zoho API enabled
USE_ZOHO_API=true uvicorn app.main:app --reload --port 8000

# Test boss email endpoint
curl -X POST "http://localhost:8000/api/teams/admin/send_vault_alerts_to_bosses?from_date=2025-01-01" \
  -H "X-API-Key: $API_KEY"
```

### Production
```bash
# Enable Zoho API in production
az containerapp update --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --set-env-vars USE_ZOHO_API=true

# Disable (rollback)
az containerapp update --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --set-env-vars USE_ZOHO_API=false
```

## Data Flow

### PostgreSQL Path (USE_ZOHO_API=false)
```
PostgreSQL Query → vault_candidates table → Anonymization → HTML
```

### Zoho API Path (USE_ZOHO_API=true)
```
Zoho API Query → Schema Mapping → Redis Cache (24h) → Anonymization → HTML
```

## Cache Keys

| Purpose | Key Format | TTL |
|---------|-----------|-----|
| Vault candidates | `vault:zoho:v2:{date_range_days}` | 24 hours |
| Bullet points | `vault:bullets:{twav}` | 24 hours |

## Environment Variables

```bash
# Required
USE_ZOHO_API=false                                          # Feature flag
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth-v2.azurewebsites.net
ZOHO_VAULT_VIEW_ID=6221978000090941003                     # Custom view

# Optional (with defaults)
AZURE_REDIS_CONNECTION_STRING=rediss://...                 # For caching
```

## Monitoring

### Application Insights Queries

```kusto
// Zoho API usage
customEvents
| where name == "zoho_api_call"
| summarize Count=count(), AvgDuration=avg(todouble(customDimensions.duration_ms)) by bin(timestamp, 1h)

// Data source distribution
customEvents
| where name == "vault_alerts_generated"
| extend DataSource = tostring(customDimensions.data_source)
| summarize Count=count() by DataSource

// Cache hit rate
customEvents
| where name == "vault_alerts_generated"
| where customDimensions.data_source == "zoho_cache"
| summarize CacheHits=count() by bin(timestamp, 1h)
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Empty fields | Wrong Zoho field names | Verify `map_to_vault_schema()` |
| Slow queries | Cache miss or blocking HTTP | Check Redis, verify async client |
| Filter not working | Filter on unmapped field | Use mapped field names |
| Telemetry flooding | Excessive `flush()` calls | Remove flush, use batch interval |

## Key Constraints

- **Always use**: `temperature=1` for GPT-5
- **Redis method**: `disconnect()` NOT `close()`
- **HTML keys**: `advisor_html` and `executive_html`
- **Email method**: `send_email()` is synchronous
- **State mutation**: LangGraph expects state mutation
- **Imports**: `from httpx import AsyncClient, Timeout, Limits, HTTPStatusError`

## Code References

| Function | File | Line | Purpose |
|----------|------|------|---------|
| `map_to_vault_schema()` | `app/integrations.py` | 1243-1274 | Schema mapping |
| `_agent_database_loader()` | `app/jobs/vault_alerts_generator.py` | ~420 | Dual source toggle |
| `anonymize_candidate_data()` | `app/utils/anonymizer.py` | ~20 | Canonical anonymizer |
| `send_vault_alerts_to_bosses()` | `app/api/teams/routes.py` | ~1850 | Boss email endpoint |

## Documentation

- **Full Guide**: `ZOHO_API_MIGRATION.md`
- **Project Docs**: `CLAUDE.md`
- **Implementation State**: `.claude/implementation_state.json`
- **Phase 9 Summary**: `.claude/phase9_complete.md`

## Quick Start

```bash
# 1. Clone and setup
git checkout feature/comprehensive-tests
source zoho/bin/activate

# 2. Configure
export USE_ZOHO_API=true
export ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth-v2.azurewebsites.net

# 3. Test
pytest tests/test_data_source_parity.py -v

# 4. Run
uvicorn app.main:app --reload --port 8000
```

## Support

- **Questions**: See `ZOHO_API_MIGRATION.md` for detailed explanations
- **Issues**: Check Troubleshooting section above
- **Monitoring**: Application Insights → Custom Events → `zoho_api_call`
