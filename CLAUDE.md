# CLAUDE.md

Guidance for Claude Code working with the Well Intake API codebase.

## Project Overview

**Well Intake API** - Intelligent email processing system automating CRM record creation in Zoho from recruitment emails. Uses LangGraph with GPT-5 for structured data extraction (Extract → Research → Validate). Deployed on Azure Container Apps with PostgreSQL.

## Quick Start

```bash
# Setup
python3 -m venv zoho && source zoho/bin/activate
pip install -r requirements.txt requirements-dev.txt
cp .env.example .env.local  # Edit with credentials
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Test
pytest tests/test_file.py -v
pytest --cov=app --cov-report=term-missing

# Shared library (well_shared/)
cd well_shared && pip install -e .  # Editable mode for dev
```

## Architecture

### Services
1. **Main API** (`app/`) - Email processing, LangGraph, Zoho - Port 8000, Container: `well-intake-api`
2. **Teams Bot** (`teams_bot/`) - MS Teams integration - Port 8001, Container: `teams-bot`
3. **Vault Agent** (Future) - Weekly digest generation - Port 8002

### Core Stack
- **LangGraph v0.2.74** - Workflow orchestration
- **FastAPI** - REST endpoints
- **GPT-5 Models** (temperature=1 ALWAYS): nano ($0.05/1M), mini ($0.25/1M), full ($1.25/1M)
- **Azure Redis** - Prompt caching (90% cost reduction)
- **PostgreSQL + pgvector** - 400K context, embeddings
- **Azure Container Apps** - Auto-scaling deployment
- **Apollo.io** - Contact enrichment
- **Firecrawl v2** - Company research

### Key Components
- `app/main.py` - FastAPI endpoints
- `app/langgraph_manager.py` - 3-node StateGraph workflow
- `well_shared/cache/redis_manager.py` - Caching (24hr TTL)
- `app/jobs/talentwell_curator.py` - Weekly digests, Zoom transcripts
- `app/api/teams/routes.py` - Teams Bot handlers
- `addin/taskpane.js` - Outlook Add-in UI

### LangGraph Workflow
```python
class EmailProcessingState(TypedDict):
    email_content: str
    extraction_result: Optional[Dict]  # GPT-5-mini structured output
    company_research: Optional[Dict]   # Firecrawl + Apollo.io
    final_output: Optional[ExtractedData]
```

### Teams Bot Commands
- `help` - Command documentation
- `digest [audience]` - Generate candidate digest (advisors/c_suite/global)
- `preferences` - Settings & weekly email subscriptions
- `analytics` - Usage stats
- Natural language queries - Ask about deals, candidates, meetings

## Essential Commands

### Development
```bash
# Activate environment
source zoho/bin/activate

# Run servers
uvicorn app.main:app --reload --port 8000           # Main API
uvicorn teams_bot.app.main:app --reload --port 8001 # Teams Bot

# Test
pytest tests/apollo/              # Apollo integration
pytest tests/talentwell/          # TalentWell curator
pytest -k "test_pattern" -v       # Pattern matching
```

### Deployment
```bash
# Build and deploy
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:latest .
az acr login --name wellintakeacr0903
docker push wellintakeacr0903.azurecr.io/well-intake-api:latest
az containerapp update --name well-intake-api --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:latest \
  --revision-suffix "v$(date +%Y%m%d-%H%M%S)"

# View logs
az containerapp logs show --name well-intake-api --resource-group TheWell-Infra-East --follow

# Database migrations (production)
curl -X POST "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/admin/run-migration?migration_name=XXX.sql" \
  -H "X-API-Key: your-api-key"
```

### Outlook Add-in
```bash
npm run validate:all    # Validate manifests
npm run package         # Package for distribution
npm run serve           # Local testing (localhost:8080)
```

## Authentication

**Dual Architecture:**
- **Client API** (well-zoho-oauth-v2.azurewebsites.net) - No API key required, Flask OAuth proxy
- **Backend API** (Container Apps) - Requires `X-API-Key` header

**Flow:** Client → OAuth Proxy → Backend (with injected credentials) → Response

## Critical Constraints

⚠️ **NEVER CHANGE:**
- AI Model: `gpt-5` with `temperature=1`
- Owner: Use `ZOHO_DEFAULT_OWNER_EMAIL` env var (never hardcode IDs)
- Zoho: Use API v8 endpoints
- Field Names: `Source` (not `Lead_Source`), `Source_Detail` for referrers
- Pipeline: Always "Sales Pipeline"
- Manifest ID: `d2422753-f7f6-4a4a-9e1e-7512f37a50e5`

## Environment Variables

```bash
# Core
API_KEY=your-key
USE_LANGGRAPH=true
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-5

# Azure
DATABASE_URL=postgresql://...
AZURE_REDIS_CONNECTION_STRING=rediss://...
AZURE_OPENAI_ENDPOINT=https://eastus2.api.cognitive.microsoft.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini

# Zoho
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net
ZOHO_DEFAULT_OWNER_EMAIL=daniel.romitelli@emailthewell.com
ZOHO_VAULT_VIEW_ID=6221978000090941003

# Zoom
ZOOM_ACCOUNT_ID=xyz
ZOOM_CLIENT_ID=xyz
ZOOM_CLIENT_SECRET=xyz

# Email
EMAIL_PROVIDER=azure_communication_services
ACS_EMAIL_CONNECTION_STRING=endpoint=https://...
```

## Feature Flags

Defaults in `app/config/feature_flags.py`, override in `.env.local`:

- `PRIVACY_MODE=true` - Company anonymization, strict compensation format
- `FEATURE_GROWTH_EXTRACTION=true` - Extract growth metrics from transcripts
- `FEATURE_LLM_SENTIMENT=true` - GPT-5 sentiment scoring (±15% boost/penalty)
- `FEATURE_ASYNC_ZOHO=false` - ⚠️ DO NOT ENABLE (needs refactor)

## Common Patterns

### Add Endpoint
```bash
# 1. Define route: app/main.py or app/api/teams/routes.py
# 2. Add logic: app/<feature>.py
# 3. Update models: app/models.py (Pydantic)
# 4. Test: pytest tests/test_<feature>.py -v
# 5. Auto docs: http://localhost:8000/docs
```

### Add Migration
```bash
alembic revision -m "description"
# Edit migrations/versions/<hash>_description.py
alembic upgrade head
alembic downgrade -1  # Test rollback
```

### Modify Shared Library
```bash
# Edit: well_shared/well_shared/<module>.py
cd well_shared && pip install -e .
pytest tests/ -k "shared" -v
```

## Production URLs

- API: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io
- Health: /health
- Manifest: /manifest.xml

## Common Issues

- **"temperature must be 1"** → Always use `temperature=1` for GPT-5
- **403 Forbidden** → Check `API_KEY` in `.env.local`
- **Container not updating** → Force revision with `--revision-suffix "v$(date +%Y%m%d-%H%M%S)"`
- **Docker WSL2 permissions** → `sudo usermod -aG docker $USER && newgrp docker`

## Recent Updates (2025-10)

### Vault Alert System
- **generate_boss_format_langgraph.py** - 4-agent LangGraph workflow for weekly candidate alerts
- Format: `‼️ [Alert Type] 🔔 [Location] 📍 [Availability/Compensation]` + 5-6 bullets
- NO candidate names, NO firm names in output
- CSS: `page-break-inside: avoid` prevents card splitting
- Database: 146 vault candidates in `vault_candidates` table
- Redis: 24hr bullet caching with `vault:bullets:{twav}` keys

### Zoom Integration
- **app/zoom_client.py** - Production client with Server-to-Server OAuth
- Methods: `list_recordings(from_date, to_date)`, `fetch_zoom_transcript_for_meeting(meeting_id)`
- Utility scripts: zoom_list_recordings.py, zoom_get_transcript.py, zoom_search_candidate.py
- Retry logic: Exponential backoff with jitter for 5xx errors

### Weekly Email Digests
- Subscription system via Teams Bot preferences
- Azure Communication Services for delivery
- Database: `teams_user_preferences`, `weekly_digest_deliveries`, `subscription_confirmations`
- Scheduler: `app/jobs/weekly_digest_scheduler.py` (hourly background job)

### Teams Bot Natural Language
- GPT-5-mini intent classification → SQL query builder
- Executive access (steve@, brandon@, daniel.romitelli@): Full data
- Regular recruiters: Filtered by `owner_email`
- Supports: deals, deal_notes, meetings, vault_candidates tables

## Git Guidelines

```bash
# Commit format: Imperative mood, ≤65 chars
✅ "Fix city/state preservation in data cleaning"
❌ "Fixed bugs"

# Before PR
pytest --cov=app --cov-report=term-missing  # ≥85% coverage
npm run lint --prefix addin
npm run validate:all

# Security
Never commit secrets → Use .env.local + Azure Key Vault
Rotate tokens after exposure
```

## Code Quality

```bash
# Format
black app/ && isort app/

# Lint
flake8 app/ && pylint app/ && mypy app/

# Security
bandit -r app/ && safety check
```
