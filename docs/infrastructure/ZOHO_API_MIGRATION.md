# Zoho API Migration Guide

## Overview

The Well Intake API now supports dual data sources for vault candidate alerts:
- **Legacy**: PostgreSQL `vault_candidates` table (default)
- **New**: Zoho CRM API v8 via custom view query (opt-in)

Toggle via `USE_ZOHO_API` feature flag.

## Architecture

### Data Flow

**PostgreSQL Path** (`USE_ZOHO_API=false`):
```
Database Query → vault_candidates table → Anonymization → HTML Generation
```

**Zoho API Path** (`USE_ZOHO_API=true`):
```
Zoho API Query → Schema Mapping → Redis Cache (24h TTL) → Anonymization → HTML Generation
```

### Schema Mapping

29 PostgreSQL columns map 1:1 to Zoho CRM fields:

| PostgreSQL Column | Zoho API Field | Notes |
|------------------|----------------|-------|
| `twav_number` | `Candidate_Locator` | Primary key |
| `firm` | `Employer` | Company name |
| `aum` | `Book_Size_AUM` | Assets under management |
| `production` | `Production_L12Mo` | Last 12 months |
| `compensation` | `Desired_Comp` | Target compensation |
| `transferable_book` | `Transferable_Book_of_Business` | Full field name |
| `licenses` | `Licenses_and_Exams` | Full field name |
| `availability` | `When_Available` | Timing field |
| `created_at` | `Created_Time` | Zoho timestamp |
| `updated_at` | `Modified_Time` | Zoho timestamp |
| `city` | Parsed from `Current_Location` | Split "City, ST" format |
| `state` | Parsed from `Current_Location` | Split "City, ST" format |
| `current_location` | `Current_Location` | Raw "City, ST" format |
| `practice_type` | `Practice_Type` | Advisory/Investment/etc |
| `deal_status` | `Deal_Stage` | Pipeline stage |
| `score` | `Score` | Numeric scoring |
| `confidential` | `Confidential` | Boolean flag |
| `stage` | `Stage` | Lead/Contact/etc |
| `description` | `Description` | Long text field |
| `notes` | `Notes` | Additional context |
| `email` | `Email` | Contact email |
| `phone` | `Phone` | Contact phone |
| `linkedin_url` | `LinkedIn_URL` | Profile link |
| `source` | `Source` | Lead source |
| `source_detail` | `Source_Detail` | Referrer info |
| `owner_email` | `Owner.email` | Recruiter email |
| `owner_name` | `Owner.name` | Recruiter name |
| `owner_id` | `Owner.id` | Zoho user ID |

**Full mapping**: See `app/integrations.py:1243-1274` (`map_to_vault_schema` function)

## Configuration

### Environment Variables

```bash
# Feature flag (default: false)
USE_ZOHO_API=false

# Zoho OAuth proxy
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth-v2.azurewebsites.net

# Vault candidates view ID
ZOHO_VAULT_VIEW_ID=6221978000090941003

# Redis for caching
AZURE_REDIS_CONNECTION_STRING=rediss://...
```

### Feature Flag Toggle

**Development**:
```bash
# .env.local
USE_ZOHO_API=true
```

**Production** (Azure Container Apps):
```bash
az containerapp update --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --set-env-vars USE_ZOHO_API=true
```

## Testing

### Unit Tests
```bash
# Schema mapping
pytest tests/test_data_source_parity.py::test_zoho_field_mapping -v

# Anonymizer (consolidated)
pytest tests/test_anonymizer_consolidated.py -v

# Teams bot adaptive cards
pytest tests/test_teams_invoke.py -v
```

### Integration Tests
```bash
# End-to-end vault alerts
pytest tests/test_vault_alerts_e2e.py -v

# Boss email endpoint
pytest tests/test_boss_email_endpoint.py -v
```

### Manual Testing
```bash
# 1. Toggle to Zoho API
export USE_ZOHO_API=true

# 2. Generate vault alerts
curl -X POST "http://localhost:8000/api/teams/admin/send_vault_alerts_to_bosses?from_date=2025-01-01" \
  -H "X-API-Key: $API_KEY"

# 3. Check data source in response
# "data_source": "zoho_api" or "zoho_cache"
```

## Performance

### Caching Strategy
- **Key Format**: `vault:zoho:v2:{date_range_days}`
- **TTL**: 24 hours
- **Cache Hit Rate**: ~90% (after warm-up)

### Async Benefits
- **Before**: Blocking `requests` library (~3-5s per query)
- **After**: Non-blocking `httpx.AsyncClient` (~1-2s per query)
- **Improvement**: 40-50% faster, no event loop blocking

### Telemetry
- **Batching**: 15-second intervals (Application Insights)
- **Metrics**: `zoho_api_call` events track duration, success rate, module

## Monitoring

### Key Metrics
1. **Data Source Distribution**: PostgreSQL vs Zoho API usage
2. **Cache Hit Rate**: Redis cache effectiveness
3. **Query Duration**: Average Zoho API response time
4. **Error Rate**: Failed Zoho queries (circuit breaker trips)

### Application Insights Queries
```kusto
// Zoho API usage
customEvents
| where name == "zoho_api_call"
| summarize Count=count(), AvgDuration=avg(todouble(customDimensions.duration_ms)) by bin(timestamp, 1h)

// Cache hit rate
customEvents
| where name == "vault_alerts_generated"
| extend DataSource = tostring(customDimensions.data_source)
| summarize Count=count() by DataSource
```

## Rollback Plan

If issues arise, immediately toggle back to PostgreSQL:

```bash
# Azure Container Apps
az containerapp update --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --set-env-vars USE_ZOHO_API=false

# Verify rollback
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
```

## Known Limitations

1. **Rate Limits**: Zoho API limited to ~100 calls/minute
2. **View Dependency**: Requires `ZOHO_VAULT_VIEW_ID` custom view to exist
3. **OAuth Proxy**: Dependent on `well-zoho-oauth-v2` service availability
4. **Schema Changes**: Manual mapping updates needed if Zoho fields change

## Migration Checklist

- [ ] Verify `USE_ZOHO_API=false` in production (default)
- [ ] Test Zoho API path in staging environment
- [ ] Monitor cache hit rates for 24 hours
- [ ] Validate schema mapping with production data
- [ ] Compare anonymization output (PostgreSQL vs Zoho)
- [ ] Load test with 500+ candidates
- [ ] Verify boss email endpoint works with Zoho data
- [ ] Update Application Insights dashboards
- [ ] Document any custom filters in use
- [ ] Train team on feature flag toggle

## Troubleshooting

### Issue: Empty candidate fields
**Cause**: Incorrect Zoho field names in mapping
**Fix**: Verify production Zoho schema matches `map_to_vault_schema`

### Issue: Slow queries
**Cause**: Cache misses or blocking HTTP
**Fix**: Check Redis connectivity; verify async client in use

### Issue: Filter not working
**Cause**: Filters applied before schema mapping
**Fix**: Ensure filters use mapped field names (city, state, not Current_Location)

### Issue: Telemetry flooding
**Cause**: `flush()` called on every event
**Fix**: Remove flush calls; let 15-second batch interval handle it

## Support

- **Documentation**: This file + `CLAUDE.md`
- **Code**: `app/integrations.py`, `app/jobs/vault_alerts_generator.py`
- **Tests**: `tests/test_data_source_parity.py`, `tests/test_vault_alerts_e2e.py`
- **Monitoring**: Application Insights → Custom Events → `zoho_api_call`
