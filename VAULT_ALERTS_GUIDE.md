# Vault Candidate Alerts System - Complete Guide

## Overview
Automated system to generate weekly candidate alerts in boss's exact format using LangGraph 4-agent workflow with Azure OpenAI.

---

## 📁 Essential Files

### 1. Main Script
**File:** `generate_boss_format_langgraph.py`
**Purpose:** LangGraph 4-agent workflow for generating vault alerts
**Location:** `/home/romiteld/Development/Desktop_Apps/outlook/`

### 2. Database Schema
**Table:** `vault_candidates` in PostgreSQL
**Connection:** Azure Database for PostgreSQL Flexible Server
**Host:** `well-intake-db-0903.postgres.database.azure.com`

### 3. Environment Configuration
**File:** `.env.local`
**Required Variables:**
```bash
# Database
DATABASE_URL=postgresql://adminuser:W3llDB2025Pass@well-intake-db-0903.postgres.database.azure.com:5432/wellintake

# Azure OpenAI (eastus2 - 300 capacity)
AZURE_OPENAI_ENDPOINT=https://eastus2.api.cognitive.microsoft.com/
AZURE_OPENAI_KEY=a3dfd2487f074dd7aa46d61489a9b300
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Azure Redis Cache
AZURE_REDIS_CONNECTION_STRING=rediss://:password@wellintakecache0903.redis.cache.windows.net:6380
```

---

## 🗄️ Database Structure

### `vault_candidates` Table Schema

```sql
CREATE TABLE vault_candidates (
    id SERIAL PRIMARY KEY,

    -- Core Identity
    twav_number VARCHAR(50) UNIQUE NOT NULL,
    candidate_name VARCHAR(255),

    -- Job Details
    title VARCHAR(255),
    firm VARCHAR(255),
    years_experience TEXT,

    -- Financial Metrics
    aum TEXT,                          -- Assets Under Management
    production TEXT,                   -- Annual production
    compensation TEXT,                 -- Desired comp

    -- Location
    city VARCHAR(100),
    state VARCHAR(100),
    current_location TEXT,

    -- Credentials
    licenses TEXT,                     -- Series 7, 66, etc.
    professional_designations TEXT,    -- CFA, CFP, etc.

    -- Candidate Details
    headline TEXT,                     -- LinkedIn-style summary
    interviewer_notes TEXT,            -- Recruiter observations
    top_performance TEXT,              -- Rankings, awards
    candidate_experience TEXT,         -- Detailed background

    -- Availability
    availability TEXT,                 -- "2 weeks notice", "immediately"

    -- Media
    zoom_meeting_url TEXT,            -- Zoom interview recording

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Sample Data Query
```sql
-- View all vault candidates
SELECT
    twav_number,
    candidate_name,
    title,
    city || ', ' || state as location,
    availability,
    compensation
FROM vault_candidates
ORDER BY created_at DESC
LIMIT 10;
```

### Current Stats (as of 2025-10-11)
- **Total Candidates:** 146
- **Advisors:** 111 (76%)
- **Executives:** 35 (24%)

---

## 🤖 LangGraph 4-Agent Workflow

### Agent 1: Database Loader
**Purpose:** Load and filter candidates from PostgreSQL
**Duration:** ~2 seconds
**Output:**
- `all_candidates` (146 total)
- `advisor_candidates` (111)
- `executive_candidates` (35)

**Filtering Logic:**
```python
ADVISOR_KEYWORDS = [
    'financial advisor', 'wealth advisor', 'investment advisor',
    'portfolio manager', 'client advisor', 'senior advisor'
]

EXECUTIVE_KEYWORDS = [
    'ceo', 'cfo', 'coo', 'cio', 'president', 'founder',
    'managing director', 'partner', 'head of'
]
```

**Code Location:** Lines 112-162 in `generate_boss_format_langgraph.py`

---

### Agent 2: GPT-5 Bullet Generator
**Purpose:** Generate 5-6 compelling bullets per candidate using Azure OpenAI
**Duration:** ~3 minutes (146 candidates × 2 seconds each)
**Model:** `gpt-5-mini` (Azure deployment)
**Temperature:** 1 (REQUIRED - do not change)

**Bullet Generation Rules:**
1. Write 5-6 bullets (NOT 4)
2. Start with BIGGEST achievements (AUM, production, growth)
3. Include credentials and licenses
4. Add personality/values bullet
5. LAST bullet MUST be: "Available [timing]; desired comp [amount]"
6. Use active verbs and specific numbers

**Cache Strategy:**
- Redis key: `bullets_boss_format:{twav_number}`
- TTL: 24 hours
- Cache hit rate: ~100% on subsequent runs

**Prompt Template:** Lines 245-290 in `generate_boss_format_langgraph.py`

**Example Output:**
```json
{
  "bullets": [
    "Managed $500M high-net-worth book at Vanguard; top 5% performer nationally",
    "30-year investment management career; built relationships across pensions, foundations, endowments",
    "CFA charterholder; Series 7 and 63 licenses",
    "Values-driven communicator; former educator who translates complex topics for mixed audiences",
    "Values: integrity, teamwork, humility",
    "Available on Two Weeks notice; desired comp $200k - $250k OTE"
  ]
}
```

**Code Location:** Lines 164-326 in `generate_boss_format_langgraph.py`

---

### Agent 3: HTML Renderer
**Purpose:** Render HTML reports in boss's EXACT format
**Duration:** ~1 second
**Output:** 2 HTML files

**Boss's Format (from screenshot):**
```
‼️ [Alert Type] 🔔
📍 Location: [City, State] (Is not mobile; Open to Remote or Hybrid)
• [5-6 bullet points]
• Available [timing]; desired comp $X
Ref code: TWAVXXXXX
```

**Alert Type Detection:**
- CEO / President Candidate Alert
- CIO / CGO Candidate Alert
- CFO Candidate Alert
- Managing Director / Partner Candidate Alert
- Vice President Candidate Alert
- Director / Executive Candidate Alert
- Head of Department Candidate Alert
- Advisor Candidate Alert (default)

**CSS Features:**
- `page-break-inside: avoid` - Prevents cards from splitting across pages
- `break-inside: avoid` - Modern CSS alternative
- Clean white cards with shadow
- Print-optimized layout

**Code Location:** Lines 328-467 in `generate_boss_format_langgraph.py`

---

### Agent 4: Quality Verifier
**Purpose:** Validate report quality metrics
**Duration:** ~1 second

**Quality Checks:**
1. **Locations Valid:** All candidates have city/state (target: 100%)
2. **Bullets Count:** Each candidate has 5-6 bullets (target: 100%)
3. **Ref Code Format:** All TWAVs start with "TWAV" (target: 100%)

**Output Example:**
```
✅ Quality Metrics:
   Total Candidates: 146
   Locations Valid: 146/146 (100.0%)
   5-6 Bullets Per Card: 146/146 (100.0%)
   Ref Code Format: 146/146 (100.0%)
```

**Code Location:** Lines 469-508 in `generate_boss_format_langgraph.py`

---

## 🚀 How to Run

### Basic Usage
```bash
# Activate virtual environment
source zoho/bin/activate

# Generate reports (takes ~3 minutes)
python3 generate_boss_format_langgraph.py
```

### Expected Output
```
================================================================================
ADVISOR VAULT ALERTS - BOSS'S EXACT FORMAT
================================================================================

🚀 Starting LangGraph workflow...

Agent 1: Database Loader        ✅ Complete (2s)
Agent 2: GPT-5 Bullet Generator 🔄 Processing (3m)
Agent 3: HTML Renderer          ⏳ Waiting
Agent 4: Quality Verifier       ⏳ Waiting

Files generated:
✅ boss_format_advisors_20251011_095703.html (157KB - 111 candidates)
✅ boss_format_executives_20251011_095703.html (53KB - 35 candidates)
```

---

## 🧪 Testing the System

### 1. Test Database Connection
```bash
PGPASSWORD='W3llDB2025Pass' psql \
  -h well-intake-db-0903.postgres.database.azure.com \
  -U adminuser \
  -d wellintake \
  -c "SELECT COUNT(*) as total_candidates FROM vault_candidates;"
```

**Expected Output:** `146`

### 2. Test Redis Cache Connection
```bash
python3 -c "
import asyncio
import os
from dotenv import load_dotenv
load_dotenv('.env.local')
import redis.asyncio as redis

async def test_redis():
    client = redis.from_url(os.getenv('AZURE_REDIS_CONNECTION_STRING'), decode_responses=True)
    await client.ping()
    print('✅ Redis connected')
    await client.close()

asyncio.run(test_redis())
"
```

**Expected Output:** `✅ Redis connected`

### 3. Test Azure OpenAI Connection
```bash
python3 -c "
import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv('.env.local')

client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)

response = client.chat.completions.create(
    model=os.getenv('AZURE_OPENAI_DEPLOYMENT'),
    messages=[{'role': 'user', 'content': 'Say hello'}],
    max_tokens=10
)

print('✅ Azure OpenAI connected:', response.choices[0].message.content)
"
```

**Expected Output:** `✅ Azure OpenAI connected: Hello! How can I assist you today?`

### 4. Test Agent 1 Only (Database Loader)
```bash
python3 -c "
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

async def test_agent1():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows = await conn.fetch('SELECT twav_number, candidate_name, title FROM vault_candidates LIMIT 5')

    print('✅ Agent 1: Database Loader')
    for row in rows:
        print(f'  - {row[\"twav_number\"]}: {row[\"candidate_name\"]} ({row[\"title\"]})')

    await conn.close()

asyncio.run(test_agent1())
"
```

### 5. Test Bullet Generation (Agent 2 - Single Candidate)
```bash
python3 -c "
import asyncio
import os
from openai import AzureOpenAI
from dotenv import load_dotenv
import json

load_dotenv('.env.local')

client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)

prompt = '''Write 5-6 compelling bullet points for a financial advisor candidate alert.

Candidate data:
Title: Financial Advisor
Years Experience: 10 years
AUM: \$250M
Licenses: Series 7, 66
Availability: 2 weeks notice
Compensation: \$150K-\$200K

Return ONLY valid JSON with 5-6 bullets:
{\"bullets\": [\"bullet 1\", \"bullet 2\", \"bullet 3\", \"bullet 4\", \"bullet 5\", \"Available on 2 weeks notice; desired comp \$150K-\$200K\"]}'''

response = client.chat.completions.create(
    model=os.getenv('AZURE_OPENAI_DEPLOYMENT'),
    messages=[
        {'role': 'system', 'content': 'You are an expert financial recruiter writing compelling bullet points.'},
        {'role': 'user', 'content': prompt}
    ],
    temperature=1,
    response_format={'type': 'json_object'}
)

result = json.loads(response.choices[0].message.content)
bullets = result.get('bullets', [])

print('✅ Agent 2: Bullet Generator')
for i, bullet in enumerate(bullets, 1):
    # Strip leading bullet chars
    bullet = bullet.lstrip('• ').lstrip('- ').strip()
    print(f'  {i}. {bullet}')
"
```

---

## 🔧 Advanced Operations

### Clear Redis Cache (Force Regeneration)
```bash
python3 -c "
import asyncio
import os
from dotenv import load_dotenv
load_dotenv('.env.local')
import redis.asyncio as redis

async def clear_cache():
    client = redis.from_url(os.getenv('AZURE_REDIS_CONNECTION_STRING'), decode_responses=True)
    keys = await client.keys('bullets_boss_format:*')
    if keys:
        await client.delete(*keys)
        print(f'✅ Cleared {len(keys)} cached bullet entries')
    else:
        print('No cached bullets found')
    await client.aclose()

asyncio.run(clear_cache())
"
```

### Query Specific Candidate by TWAV
```sql
SELECT
    twav_number,
    candidate_name,
    title,
    firm,
    city || ', ' || state as location,
    aum,
    production,
    licenses,
    professional_designations,
    availability,
    compensation,
    interviewer_notes
FROM vault_candidates
WHERE twav_number = 'TWAV117830';
```

### Update Candidate Data
```sql
-- Update compensation
UPDATE vault_candidates
SET compensation = '$200K-$250K OTE',
    updated_at = NOW()
WHERE twav_number = 'TWAV117830';

-- Update location
UPDATE vault_candidates
SET city = 'Phoenix',
    state = 'AZ',
    current_location = 'Phoenix, AZ',
    updated_at = NOW()
WHERE twav_number = 'TWAV117830';
```

### Add New Candidate
```sql
INSERT INTO vault_candidates (
    twav_number,
    candidate_name,
    title,
    firm,
    city,
    state,
    current_location,
    years_experience,
    aum,
    production,
    licenses,
    professional_designations,
    headline,
    interviewer_notes,
    availability,
    compensation,
    zoom_meeting_url
) VALUES (
    'TWAV999999',
    'John Smith',
    'Senior Financial Advisor',
    'Wealth Management LLC',
    'Dallas',
    'TX',
    'Dallas, TX',
    '15 years',
    '$300M',
    '$2M annually',
    'Series 7, 66, Life & Health',
    'CFP, CFA Level II',
    'Top-performing advisor specializing in high-net-worth clients',
    'Strong communicator, values integrity and client service',
    'Immediately',
    '$175K-$225K base + bonus',
    'https://zoom.us/rec/abc123'
);
```

---

## 📊 Monitoring & Analytics

### Check Generation History
```bash
# List all generated reports
ls -lht boss_format_*.html | head -10

# Count total reports
ls -1 boss_format_*.html 2>/dev/null | wc -l
```

### Redis Cache Statistics
```bash
python3 -c "
import asyncio
import os
from dotenv import load_dotenv
load_dotenv('.env.local')
import redis.asyncio as redis

async def cache_stats():
    client = redis.from_url(os.getenv('AZURE_REDIS_CONNECTION_STRING'), decode_responses=True)

    keys = await client.keys('bullets_boss_format:*')
    print(f'📊 Redis Cache Statistics')
    print(f'   Cached Candidates: {len(keys)}')
    print(f'   Cache Key Pattern: bullets_boss_format:TWAVXXXXXX')
    print(f'   TTL: 24 hours')

    await client.aclose()

asyncio.run(cache_stats())
"
```

### Database Statistics
```sql
-- Candidate breakdown
SELECT
    CASE
        WHEN title ILIKE '%ceo%' OR title ILIKE '%president%' OR title ILIKE '%founder%' THEN 'Executive'
        ELSE 'Advisor'
    END as category,
    COUNT(*) as count
FROM vault_candidates
GROUP BY category;

-- Candidates by location
SELECT
    state,
    COUNT(*) as count
FROM vault_candidates
WHERE state IS NOT NULL
GROUP BY state
ORDER BY count DESC
LIMIT 10;

-- Recently added candidates
SELECT
    twav_number,
    candidate_name,
    title,
    created_at
FROM vault_candidates
ORDER BY created_at DESC
LIMIT 10;
```

---

## 🐛 Troubleshooting

### Issue: "No module named 'langgraph'"
**Solution:**
```bash
pip install langgraph
```

### Issue: "Connection refused" (PostgreSQL)
**Check:**
1. Database URL is correct in `.env.local`
2. Firewall allows connections from your IP
3. Database is running

**Test:**
```bash
PGPASSWORD='W3llDB2025Pass' psql \
  -h well-intake-db-0903.postgres.database.azure.com \
  -U adminuser \
  -d wellintake \
  -c "SELECT 1;"
```

### Issue: "Connection refused" (Redis)
**Check:**
1. Redis connection string is correct
2. Redis cache is running in Azure

**Test:**
```bash
redis-cli -h wellintakecache0903.redis.cache.windows.net -p 6380 -a <password> --tls PING
```

### Issue: Double Bullets in HTML
**Cause:** GPT-5-mini adding "• " prefix to bullets
**Fix:** Line 308 strips leading bullet characters:
```python
bullets = [bullet.lstrip('• ').lstrip('- ').strip() for bullet in bullets]
```

### Issue: Cards Split Across Pages
**Fix:** CSS added at line 410-411:
```css
page-break-inside: avoid;
break-inside: avoid;
```

### Issue: Wrong Alert Types
**Check:** `get_alert_type()` function at lines 75-110
**Logic:** Checks job titles for keywords (CEO, President, VP, Director, etc.)

---

## 📝 Output Files

### File Naming Convention
```
boss_format_advisors_YYYYMMDD_HHMMSS.html
boss_format_executives_YYYYMMDD_HHMMSS.html
```

### File Sizes (Typical)
- Advisors: ~155-160KB (111 candidates)
- Executives: ~52-55KB (35 candidates)

### HTML Structure
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Advisor Vault Candidate Alerts - Financial Advisors</title>
    <style>/* CSS for cards and print layout */</style>
</head>
<body>
    <h1>📊 Advisor Vault Candidate Alerts - Financial Advisors</h1>
    <div class="stats">
        <p><strong>Generated:</strong> 2025-10-11 09:57 AM</p>
        <p><strong>Total Candidates:</strong> 111</p>
    </div>

    <div class="candidates">
        <!-- Candidate cards -->
        <div class="candidate-card">
            <h2>‼️ Advisor Candidate Alert 🔔</h2>
            <p><strong>📍 Location: Milwaukee, WI</strong> (Is not mobile; <strong>Open to Remote</strong> or Hybrid)</p>
            <ul>
                <li>Bullet 1</li>
                <li>Bullet 2</li>
                ...
                <li>Available on 2 weeks notice; desired comp $150K-$200K</li>
            </ul>
            <p>Ref code: TWAV101658</p>
        </div>
    </div>
</body>
</html>
```

---

## 🔄 Weekly Automation (Future)

### Setup Cron Job
```bash
# Edit crontab
crontab -e

# Run every Monday at 8 AM
0 8 * * 1 cd /home/romiteld/Development/Desktop_Apps/outlook && source zoho/bin/activate && python3 generate_boss_format_langgraph.py
```

### Email Delivery (Future Enhancement)
- Use Azure Communication Services
- Automatically email HTML reports to stakeholders
- See `app/api/monitoring_routes.py` for webhook implementation

---

## 📚 Related Files

1. **`app/jobs/talentwell_curator.py`** - Weekly digest generation for Teams Bot
2. **`app/integrations.py`** - Zoho API integration with vault candidates
3. **`migrations/005_teams_integration_tables.sql`** - Database schema for vault candidates
4. **`app/api/monitoring_routes.py`** - Real-time monitoring endpoints (NEW)
5. **`well_shared/cache/redis_manager.py`** - Redis cache management utilities

---

## 🎯 Success Criteria

✅ All 4 agents complete successfully
✅ Quality metrics show 100% across all checks
✅ HTML format matches boss's screenshot exactly
✅ No double bullets in output
✅ Cards don't split across pages
✅ Cache hit rate ~100% on subsequent runs
✅ Generation time ~3 minutes (first run) or ~5 seconds (cached)

---

## 📞 Support

**Files to Check When Debugging:**
1. `.env.local` - Environment variables
2. `generate_boss_format_langgraph.py` - Main script
3. Database connection string
4. Redis connection string
5. Azure OpenAI deployment name

**Key Metrics to Monitor:**
- Cache hit rate (target: 100% after first run)
- Quality metrics (target: 100% for all checks)
- Generation time (target: <3 minutes)
- Database connection health
- Redis connection health

---

*Last Updated: 2025-10-11*
*Generated by: Claude Code Assistant*
