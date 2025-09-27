# Bulletproof Policy Seeding System v2

A comprehensive policy management system for the recruitment platform that generates and maintains critical business rules and configurations.

## Overview

The Policy Seeding System v2 manages four key types of policies:

1. **Employer Normalization**: Classifies firms as "National firm" or "Independent firm"
2. **City Context**: Maps cities to metro areas (e.g., "Brooklyn" → "NYC Metro") 
3. **Subject Bandit**: Multi-armed bandit priors for email subject line optimization
4. **Selector Priors**: C³ and TTL parameters for candidate selection algorithms

## Architecture

- **Database Layer**: PostgreSQL tables store canonical policy data
- **Cache Layer**: Redis provides fast access with no TTL for static policies
- **Dual Storage**: All policies stored in both PostgreSQL and Redis
- **API Layer**: FastAPI endpoints for management and querying

## Usage

### Command Line Interface

```bash
# Seed all policies (default)
python app/admin/seed_policies_v2.py

# Reload policies from database to Redis
python app/admin/seed_policies_v2.py reload

# Clear Redis policy cache
python app/admin/seed_policies_v2.py clear
```

### FastAPI Endpoints

All endpoints require `X-API-Key` header for authentication:

#### Seed Policies
```bash
POST /api/admin/policies/seed
Content-Type: application/json

{
  "clear_existing": true,
  "seed_employers": true,
  "seed_cities": true,
  "seed_subjects": true,
  "seed_selectors": true
}
```

#### Reload from Database
```bash
POST /api/admin/policies/reload
```

#### Query Specific Policy
```bash
POST /api/admin/policies/query

{
  "policy_type": "employer",
  "key": "morgan stanley"
}
```

#### Get Policy Statistics
```bash
GET /api/admin/policies/stats
```

#### Clear Redis Cache
```bash
DELETE /api/admin/policies/clear
```

## Policy Types

### 1. Employer Normalization

Maps company names to firm types based on national firm indicators.

**Database**: `policy_employers` table  
**Redis**: `policy:employers:{company_name}` → firm_type  
**Example**: `policy:employers:morgan stanley` → `"National firm"`

**National Firms**: LPL, Raymond James, Ameriprise, Edward Jones, Wells Fargo, Morgan Stanley, Merrill Lynch, UBS, Charles Schwab, Fidelity, Vanguard, Northwestern Mutual, MassMutual, Prudential, Goldman Sachs, JPMorgan, Bank of America, Citigroup, Deutsche Bank, Credit Suisse, Barclays, RBC, TD Ameritrade, E*Trade, Franklin Templeton

### 2. City Context

Maps cities to their metro areas for geographical analysis.

**Database**: `policy_city_context` table  
**Redis**: `geo:metro:{city}` → metro_area  
**Example**: `geo:metro:manhattan` → `"NYC Metro"`

**Major Metro Areas**: 
- NYC Metro (Manhattan, Brooklyn, Queens, etc.)
- LA Metro (Los Angeles, Beverly Hills, Santa Monica, etc.)
- Chicago Metro, SF Bay Area, Boston Metro, DC Metro, etc.

### 3. Subject Bandit Priors

Multi-armed bandit parameters for email subject line testing.

**Database**: `policy_subject_priors` table  
**Redis**: `bandit:subjects:global:{variant}` → JSON with alpha/beta  
**Example**: `bandit:subjects:global:v1` → `{"template": "🎯 Weekly Talent Update - {date}", "alpha": 3, "beta": 1}`

**Variants**:
- v1: '🎯 Weekly Talent Update - {date}'
- v2: 'Your Curated Candidates - {date}'
- v3: '📊 TalentWell Weekly Digest'
- v4: 'Steve - New Talent Matches Available'
- v5: 'Weekly Recruiting Pipeline Update'

### 4. Selector Priors

C³ tau parameters and TTL alpha/beta values for candidate selection.

**Database**: `policy_selector_priors` table  
**Redis**: 
- `c3:tau:{selector}` → tau_delta value
- `ttl:{selector}` → JSON with alpha/beta

**Selectors**:
- mobility: (0.30, 5, 3) - High volatility
- compensation: (0.28, 5, 3) - High volatility  
- location: (0.35, 4, 3) - Very high volatility
- licenses: (0.55, 2, 6) - Low volatility
- achievements: (0.40, 3, 4) - Medium volatility

## Data Flow

1. **Seeding**: Policies generated from imported deals/meetings data
2. **Storage**: Canonical data in PostgreSQL tables
3. **Caching**: Fast Redis access with no expiration
4. **Retrieval**: Applications read from Redis first, fallback to PostgreSQL
5. **Updates**: Database updates trigger Redis refresh

## Database Tables

```sql
-- Employer classifications
CREATE TABLE policy_employers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT UNIQUE NOT NULL,
    firm_type TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- City to metro mappings  
CREATE TABLE policy_city_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city TEXT UNIQUE NOT NULL,
    metro_area TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Subject line bandit priors
CREATE TABLE policy_subject_priors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audience TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    text_template TEXT NOT NULL,
    alpha INTEGER DEFAULT 1,
    beta INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(audience, variant_id)
);

-- Selector algorithm parameters
CREATE TABLE policy_selector_priors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    selector TEXT UNIQUE NOT NULL,
    tau_delta NUMERIC NOT NULL,
    bdat_alpha INTEGER NOT NULL,
    bdat_beta INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Environment Variables

Required in `.env.local`:

```bash
# PostgreSQL (required)
DATABASE_URL=postgresql://user:pass@host:port/db

# Redis (optional, falls back to DB-only mode)
AZURE_REDIS_CONNECTION_STRING=rediss://:password@hostname:port

# API Authentication (required for endpoints)
API_KEY=your-secure-api-key
ADMIN_API_KEY=your-admin-key  # Optional separate admin key
```

## Error Handling

- **PostgreSQL Failures**: System fails fast with clear error messages
- **Redis Failures**: Continues in database-only mode with warnings
- **Partial Failures**: Returns counts of successful operations
- **Validation**: Input validation on all API endpoints
- **Authentication**: Secure API key validation with rate limiting

## Performance

- **Redis Lookup**: <1ms for cached policies
- **Database Fallback**: ~10ms for uncached queries
- **Bulk Seeding**: ~5 seconds for full policy refresh
- **Memory Usage**: ~1MB for complete policy cache
- **Storage**: ~50KB database storage for all policies

## Testing

```bash
# Run comprehensive tests
python test_policies.py

# Test specific functionality
python -c "
import asyncio
from app.admin.seed_policies_v2 import PolicySeeder

async def test():
    seeder = PolicySeeder()
    await seeder.initialize()
    result = await seeder.seed_all()
    print(f'Seeded: {result}')
    await seeder.close()

asyncio.run(test())
"
```

## Monitoring

- **Metrics**: Track seeding operations, Redis hits/misses
- **Health**: Database and Redis connection status
- **Alerting**: Failed seeding operations and cache misses
- **Logs**: Structured logging with operation details

## Best Practices

1. **Regular Seeding**: Run daily to capture new firms/cities from deals
2. **Cache Warming**: Reload Redis after database schema changes
3. **Validation**: Always verify policy counts after operations
4. **Backup**: Database tables are source of truth, Redis is cache
5. **Testing**: Validate policies with known test cases before deployment