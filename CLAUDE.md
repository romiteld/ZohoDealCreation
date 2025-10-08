# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Well Intake API** - An intelligent email processing system that automates CRM record creation in Zoho from recruitment emails. Uses LangGraph with GPT-5 for structured data extraction through a three-node workflow (Extract → Research → Validate). Deployed on Azure Container Apps with PostgreSQL for deduplication.

## Architecture

### Service Architecture (Phase 1)

The Well Intake API is transitioning to a microservices architecture with three independent services:

1. **Main API Service** (`app/`) - Email processing, LangGraph workflows, Zoho integration
   - Port: 8000
   - Container: `well-intake-api`
   - Endpoints: `/api/*`, `/health`, `/manifest.xml`

2. **Teams Bot Service** (`teams_bot/`) - Microsoft Teams integration
   - Port: 8001
   - Container: `teams-bot`
   - Endpoints: `/api/teams/*`, `/health`
   - Dependencies: Bot Framework, TalentWell Curator

3. **Vault Agent Service** (Future - Phase 2) - Weekly digest generation
   - Port: 8002
   - Container: `vault-agent`
   - Background job: Digest scheduler

**Shared Library** (`well_shared/`) - Common utilities used across all services:
- Database connection management (PostgreSQL)
- Redis cache manager
- Email delivery (Azure Communication Services)
- Evidence extraction utilities
- VoIT configuration and telemetry

### Core Stack
- **LangGraph v0.2.74** - Workflow orchestration (replaced CrewAI)
- **FastAPI** - Main API framework with REST endpoints
- **GPT-5 Model Tiers** - Intelligent selection (temperature=1 ALWAYS):
  - GPT-5-nano: $0.05/1M input (simple emails)
  - GPT-5-mini: $0.25/1M input (standard)
  - GPT-5: $1.25/1M input (complex)
- **Azure Cache for Redis** - Prompt/response caching (90% cost reduction)
- **Azure Container Apps** - Production deployment with auto-scaling
- **PostgreSQL with pgvector** - 400K context window support, embeddings
- **Azure Blob Storage** - Attachment storage
- **Azure Service Bus** - Batch email processing (50 emails/batch)
- **Azure AI Search** - Semantic pattern learning and company templates
- **Apollo.io Integration** - Contact enrichment via REST API
- **Azure Key Vault** - Secret management with rotation
- **Application Insights** - Custom metrics and cost tracking

### Key Components
- **Main API** (`app/main.py`): FastAPI with batch, streaming, and learning endpoints
- **LangGraph Manager** (`app/langgraph_manager.py`): Three-node StateGraph workflow
- **Database Enhancements** (`app/database_enhancements.py`): 400K context and vector search
- **Redis Cache Manager** (`well_shared/well_shared/cache/redis_manager.py`): Intelligent caching with 24hr TTL (migrated to well_shared)
- **Cache Strategies** (`app/cache_strategies.py`): Email classification and pattern recognition
- **Azure Cost Optimizer** (`app/azure_cost_optimizer.py`): Model tier selection and budget tracking
- **Service Bus Manager** (`app/service_bus_manager.py`): Batch queue management
- **Batch Processor** (`app/batch_processor.py`): Multi-email single-context processing
- **Azure AI Search Manager** (`app/azure_ai_search_manager.py`): Semantic search and learning
- **Learning Analytics** (`app/learning_analytics.py`): A/B testing and accuracy tracking
- **Power BI Integration** (`app/powerbi_integration.py`): Real-time analytics streaming to Power BI Premium
- **Monitoring** (`app/monitoring.py`): Application Insights integration
- **Security Config** (`app/security_config.py`): Key Vault and API key management
- **Business Rules** (`app/business_rules.py`): Deal name formatting, source determination
- **Integrations** (`app/integrations.py`): Zoho API v8, Azure services
- **Outlook Add-in** (`addin/`): Manifest with REST API integration

### Outlook Add-in Components
- **Manifest Files** (`addin/manifest.xml`, `addin/manifest.json`): Office add-in configuration
- **Task Pane** (`addin/taskpane.html`, `addin/taskpane.js`): Main UI and functionality
- **Commands** (`addin/commands.html`, `addin/commands.js`): Ribbon button handlers
- **Apollo Integration** (`addin/apollo.js`): REST API contact enrichment
- **App Logic** (`addin/app.js`): Core application functionality
- **Configuration** (`addin/config.js`): Environment and API settings
- **Static Assets** (`addin/icon-*.png`): Add-in icons and resources

### Teams Bot Integration Components
- **Webhook Endpoint** (`app/api/teams/routes.py`): Bot Framework activity handlers (message, invoke, conversationUpdate)
- **Adaptive Cards** (`app/api/teams/adaptive_cards.py`): Interactive UI cards (welcome, help, digest preview, preferences, error)
- **Database Schema** (`migrations/005_teams_integration_tables.sql`): 4 tables + 2 analytics views
- **Subscription Schema** (`migrations/006_weekly_digest_subscriptions.sql`): Weekly email digest subscriptions with tracking
- **Weekly Digest Scheduler** (`app/jobs/weekly_digest_scheduler.py`): Hourly background job for automated digest delivery
- **VoIT Configuration** (`app/config/voit_config.py`): Shared model tier selection and cost tracking
- **TalentWell Curator** (`app/jobs/talentwell_curator.py`): Score-based ranking, retry logic, sentiment analysis

**Teams Bot Commands:**
- `help` - Display formatted help card with command documentation
- `digest [audience]` - Generate candidate digest preview (audiences: advisors, c_suite, global)
- `digest <email>` - Test mode - route digest to specific email for validation
- `preferences` - View/edit default audience, frequency, notification settings, and weekly digest subscriptions
- `analytics` - View usage statistics and recent activity
- Natural language queries - Ask questions about deals, candidates, meetings (executive access: full data, recruiters: filtered by owner)

**Candidate Filtering Logic:**
- Filters by **job title keywords** (not owner email)
- `advisors` → Financial/Wealth/Investment Advisor keywords
- `c_suite` → CEO, CFO, VP, Director, Executive keywords
- `global` → All candidates (no filter)

## Project Structure

### Directory Organization
- `app/` - Main API service (email processing, LangGraph workflows)
  - Entry points: `app/main.py`, `app/langgraph_manager.py`
- `teams_bot/` - Teams Bot service (Microsoft Teams integration)
  - Entry point: `teams_bot/app/main.py`
  - Dockerfile: `teams_bot/Dockerfile`
  - Dependencies: `teams_bot/requirements.txt`
- `well_shared/` - Shared library for all services
  - Package: `well_shared/well_shared/`
  - Modules: database, cache, mail, evidence, config
- `addin/` - Outlook Add-in frontend (JavaScript, HTML, manifest)
  - Primary file: `addin/taskpane.js`
- `oauth_service/` - Flask OAuth proxy for Zoho token brokering
- `tests/` - pytest suites with integration and browser test harnesses
  - `tests/integration/` - End-to-end tests
  - `tests/smoke/` - Staging smoke tests per service
  - `tests/fixtures/` - Shared test fixtures
- `docs/` - Architecture Decision Records (ADRs) and technical docs
- `scripts/` - Deployment scripts, database utilities, automation
- `migrations/` - Alembic database migration files
- `static/` & `templates/` - Shared UI resources and Jinja2 templates

### Naming Conventions
- **Python**: PEP 8, 4 spaces, `snake_case`, type hints where practical
- **JavaScript**: 2-space indentation, `camelCase`, avoid hyphens in filenames
- **Config/Prompts**: lowercase with hyphens (e.g., `app/prompts/deal_summary.txt`)
- **Test files**: `test_<feature>.py` pattern

### Code Quality Standards
- **Formatting**: Use `black`, `isort`, `ruff` for Python; `npm run lint` for JavaScript
- **Coverage**: Target ≥85% on business-critical modules using `pytest --cov=app --cov-report=term-missing`
- **Type Safety**: Add type hints to new Python functions; validate with `mypy`

## Essential Commands

### Outlook Add-in Development
```bash
# Validate manifest files
npm run validate          # Validate manifest.xml
npm run validate:json     # Validate manifest.json
npm run validate:all      # Validate both manifests

# Convert between manifest formats
npm run convert           # Convert XML to JSON

# Package add-in for distribution
npm run package           # Package both formats
npm run package:json      # Package JSON manifest only
npm run package:xml       # Package XML manifest only

# Serve add-in locally for testing
npm run serve             # Serve on http://localhost:8080

# Run all validation tests
npm run test

# Full deployment workflow
npm run deploy            # Validate and package
```

### Local Development
```bash
# Activate virtual environment
source zoho/bin/activate  # Linux/Mac
zoho\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies

# Run development server
uvicorn app.main:app --reload --port 8000

# Test LangGraph workflow
python test_langgraph.py

# Test container deployment
python test_container_deployment.py
```

### Testing
```bash
# Run all organized tests
python run_all_tests.py

# Run specific test categories by directory
pytest tests/apollo/             # Apollo.io integration tests
pytest tests/firecrawl/          # Firecrawl integration tests
pytest tests/integration/        # End-to-end integration tests
pytest tests/production/         # Production environment tests
pytest tests/zoom/               # Zoom integration tests
pytest tests/talentwell/         # TalentWell curator, privacy, and AI tests

# Run TalentWell-specific tests
pytest tests/talentwell/test_data_quality.py      # Privacy mode, compensation, location
pytest tests/talentwell/test_bullet_ranking.py    # Growth extraction, sentiment scoring
pytest tests/talentwell/test_privacy_integration.py  # Full end-to-end privacy tests

# Run pytest with coverage
pytest --cov=app --cov-report=html
pytest --cov=app.jobs.talentwell_curator --cov-report=term-missing  # Curator coverage

# Run specific service tests
pytest -m redis                  # Redis cache tests
pytest -m postgresql             # Database tests
pytest -m container_app          # Container App tests

# Run single test file
pytest tests/test_specific_file.py

# Run with specific verbosity and stop on first failure
pytest -v --maxfail=1

# Test specific Apollo functionality
python tests/apollo/test_apollo_quick.py
python tests/apollo/test_apollo_deep_integration.py

# Test specific Firecrawl functionality
python tests/firecrawl/test_firecrawl_sdk.py
python tests/firecrawl/test_firecrawl_v2_fire.py
```

### Code Quality
```bash
# Format code
black app/                    # Auto-format Python code
isort app/                    # Sort imports

# Lint code
flake8 app/                   # Style checking
pylint app/                   # Code analysis
mypy app/                     # Type checking

# Security checks
bandit -r app/                # Security vulnerability scan
safety check                  # Dependency vulnerability scan
```

### Database Operations
```bash
# Run migrations
alembic upgrade head          # Apply all migrations
alembic revision --autogenerate -m "Description"  # Create new migration

# Run migration via API endpoint (for production)
curl -X POST "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/admin/run-migration?migration_name=006_weekly_digest_subscriptions.sql" \
  -H "X-API-Key: your-api-key"

# Database maintenance
python scripts/cleanup_old_records.py   # Clean old records
python scripts/vacuum_database.py       # Optimize database
```

### Power BI Integration
```bash
# Generate dataset schemas for Power BI workspace
python -c "
from app.powerbi_integration import powerbi
import json
schemas = powerbi.create_datasets_schema()
print(json.dumps(schemas, indent=2))
"

# Environment variables (add to .env)
POWERBI_WORKSPACE_ID=your-workspace-id
POWERBI_API_KEY=your-premium-api-key
ENABLE_POWERBI_STREAMING=true
POWERBI_BATCH_SIZE=100  # Optional, default 100
```

**Datasets**:
- **extraction_metrics**: Per-email extraction quality and model performance
- **ab_test_results**: Prompt variant A/B testing outcomes
- **cost_optimization**: Model tier usage, token counts, budget tracking
- **field_accuracy**: Field-level correction rates and template effectiveness
- **learning_patterns**: Pattern recognition, template usage, improvement trends
- **deal_processing**: Individual deal tracking from email → Zoho with full traceability

**Usage in Code**:
```python
from app.powerbi_integration import powerbi, DealProcessingRow

# Log deal processing
deal_row = DealProcessingRow(
    deal_id=deal["id"],
    extraction_id=extraction_id,
    timestamp=datetime.utcnow(),
    deal_name=deal["Deal_Name"],
    company_name=company,
    contact_name=contact,
    email_domain=domain,
    source=source,
    processing_stage="Create",
    success=True,
    processing_time_ms=duration_ms,
    extraction_confidence=0.95,
    fields_corrected=2,
    used_template=True,
    used_firecrawl=True,
    used_apollo=False,
    model_used="gpt-5-mini",
    tokens_input=1500,
    tokens_output=800,
    cost_usd=0.0012,
    owner_email="recruiter@emailthewell.com"
)
powerbi.log_deal_processing(deal_row)
```

### Deployment

#### Multi-Service Deployment (Phase 1)
```bash
# Deploy Teams Bot service
./scripts/deploy_teams_bot.sh

# Deploy Main API service (existing)
./scripts/deploy.sh

# Deployment gate (validate staging before production)
python scripts/deployment_gate.py --service teams-bot
python scripts/deployment_gate.py --service main-api
python scripts/deployment_gate.py --all  # Validate all services
```

#### Service-Specific Deployment
```bash
# Teams Bot Service
docker build -f teams_bot/Dockerfile -t wellintakeacr0903.azurecr.io/teams-bot:latest .
az acr login --name wellintakeacr0903
docker push wellintakeacr0903.azurecr.io/teams-bot:latest
az containerapp update --name teams-bot --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/teams-bot:latest \
  --revision-suffix "v$(date +%Y%m%d-%H%M%S)"

# Main API Service
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:latest .
az acr login --name wellintakeacr0903
docker push wellintakeacr0903.azurecr.io/well-intake-api:latest
az containerapp update --name well-intake-api --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:latest \
  --revision-suffix "v$(date +%Y%m%d-%H%M%S)"

# View service logs
az containerapp logs show --name teams-bot --resource-group TheWell-Infra-East --follow
az containerapp logs show --name well-intake-api --resource-group TheWell-Infra-East --follow
```

#### CDN and Cache Management
```bash
# Purge CDN cache after deployment
az afd endpoint purge --resource-group TheWell-Infra-East \
  --profile-name well-intake-frontdoor \
  --endpoint-name well-intake-api \
  --domains well-intake-api-dnajdub4azhjcgc3.z03.azurefd.net \
  --content-paths "/*"

# Alternative: Use API endpoint for CDN purge
curl -X POST "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/cdn/purge" \
  -H "Content-Type: application/json" -d '{"paths": ["/*"]}'
```

#### GitHub Actions (Automated)
```bash
# Workflows: manifest-cache-bust.yml (active), deploy-production.yml (disabled)
# Manual workflow dispatch available in GitHub Actions tab
```

### CI/CD Workflows

**Active Workflows:**
```bash
# Manifest Cache-Bust & Deploy (.github/workflows/manifest-cache-bust.yml)
# Triggers: Changes to addin/manifest.xml, *.html, *.js, *.css
# Actions:
# 1. Auto-increments manifest version (MAJOR.MINOR.PATCH.BUILD)
# 2. Clears Redis cache and warms with new version
# 3. Builds and deploys Docker image to Azure Container Apps
# 4. Runs health checks and smoke tests
# 5. Automatic rollback on failure

# Manual trigger with custom version increment:
# GitHub Actions > Manifest Cache-Bust & Deploy > Run workflow

# Required GitHub Secrets:
# AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, API_KEY
```

**Disabled Workflows:**
- `deploy-production.yml` - Full production deployment
- `deploy-simple.yml` - Simplified deployment flow

**Emergency Rollback:**
```bash
# Use emergency-rollback.yml workflow for critical issues
# GitHub Actions > Emergency Rollback > Run workflow > Select revision
```

### API Testing
```bash
# Test Kevin Sullivan sample
curl -X GET "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/test/kevin-sullivan" \
  -H "X-API-Key: your-api-key" | python -m json.tool

# Health check
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health

# Test cache status
curl -X GET "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/cache/status" \
  -H "X-API-Key: your-api-key"

# Test VoIT status
curl -X GET "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/vault-agent/status" \
  -H "X-API-Key: your-api-key"

# Test TalentWell curator
python -m app.jobs.talentwell_curator --audience steve_perry --days 7

# Test Zoom transcript fetching
python -c "from app.zoom_client import ZoomClient; import asyncio; client = ZoomClient(); asyncio.run(client.fetch_meeting_recording('MEETING_ID'))"
```

## Authentication & OAuth Architecture

### OAuth Proxy Service
The system uses a **dual-authentication architecture** to protect credentials and simplify client integration:

**Client-Facing API** (well-zoho-oauth-v2.azurewebsites.net):
- **No API key required** for Outlook Add-in clients
- Flask App Service acts as OAuth proxy
- Automatic credential injection for backend requests
- Token management with 55-minute Redis cache TTL
- Rate limiting: 100 req/min per IP

**Backend API** (well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io):
- Requires `X-API-Key` header for direct access
- Only OAuth proxy has backend API key
- Clients never see or store API keys
- Container Apps environment with auto-scaling

**Authentication Flow:**
1. Client sends request to OAuth proxy (no auth required)
2. Proxy retrieves cached OAuth token from Redis (or refreshes from Zoho)
3. Proxy injects API key and forwards request to backend API
4. Backend processes with LangGraph and returns results
5. Proxy forwards response to client

**Key Vault Integration:**
- Managed Identity for Container Apps
- No stored credentials in code or config files
- Automatic token rotation by Azure platform
- `ZOHO_DEFAULT_OWNER_EMAIL` used for owner assignment (never hardcode IDs)

## LangGraph Workflow

### State Definition
```python
class EmailProcessingState(TypedDict):
    email_content: str
    sender_domain: str
    extraction_result: Optional[Dict]
    company_research: Optional[Dict]
    validation_result: Optional[Dict]
    final_output: Optional[ExtractedData]
```

### Three-Node Pipeline
1. **Extract Node**: GPT-5-mini with Pydantic structured output
2. **Research Node**: Firecrawl v2 Fire Agent + Apollo.io for company enrichment (5s timeout)
3. **Validate Node**: Data normalization and structured record creation

### Research Node Architecture
- **Firecrawl v2 Integration**: `app/firecrawl_v2_fire_agent.py` with FIRE-1 agent using Scrape API
- **Apollo.io Enrichment**: Contact/company data from REST API
- **Web Search Client**: Frontend button in Outlook Add-in with progress indicator
- **Dynamic Import**: Falls back gracefully if Firecrawl modules missing
- **Company Research**: Enriches `CompanyRecord` with phone, website, location data via regex parsing
- **Contact Research**: Populates `ContactRecord.city/state` from company location
- **API Endpoint**: `/api/firecrawl/enrich` for direct company domain enrichment

### Error Handling
- Fallback to `SimplifiedEmailExtractor` on errors
- Maintains partial data through pipeline
- Always returns valid `ExtractedData` object with structured records

## Data Flow Architecture

### Backend → Frontend Data Mapping
```javascript
// Backend returns ExtractedData with structured records:
{
  company_record: { company_name, phone, website, detail },
  contact_record: { first_name, last_name, email, phone, city, state },
  deal_record: { source, deal_name, description_of_reqs }
}

// Frontend maps to form fields (taskpane.js:633-647):
extractedData = {
  // Structured data preferred over legacy flat fields
  contactCity: getString(contact.city),           // From Firecrawl research
  contactState: getString(contact.state),         // From Firecrawl research
  companyPhone: getString(company.phone),         // From Apollo/Firecrawl
  companyWebsite: getString(company.website),     // From Apollo/Firecrawl
  companyOwner: getString(company.detail),        // From referrer data
  // Legacy flat fields as fallbacks
  location: getString(extracted?.location)
}
```

### Critical Frontend Form Population Logic
- **Structured Data First**: `taskpane.js:1013-1026` prefers backend research data
- **Fallback Parsing**: Only parses `location` string if structured fields empty
- **Precedence Fixed**: No longer duplicates city into state for single-location strings

## Business Rules

### Deal Name Format
Pattern: `"[Job Title] ([Location]) - [Firm Name]"`
- Missing values → "Unknown"
- Applied in `business_rules.py::format_deal_name()`

### Source Determination
1. Has referrer → "Referral" + Source_Detail
2. Contains "TWAV" → "Reverse Recruiting"
3. Has Calendly → "Website Inbound"
4. Default → "Email Inbound"

## Critical Constraints

⚠️ **NEVER CHANGE** - System requirements that must not be modified:
- **AI Model**: Always use `gpt-5` with `temperature=1`
- **Owner Assignment**: Use `ZOHO_DEFAULT_OWNER_EMAIL` environment variable, never hardcode IDs
- **Zoho API**: Use v8 endpoints (not v6)
- **Field Names**: Use `Source` (not `Lead_Source`), `Source_Detail` for referrer names
- **Pipeline**: Always lock to "Sales Pipeline" only

### Outlook Add-in Constraints
⚠️ **Office Add-in Specific Requirements**:
- **Manifest ID**: Never change the add-in ID `d2422753-f7f6-4a4a-9e1e-7512f37a50e5`
- **CDN URLs**: Always use Azure Front Door CDN URLs for production manifests
- **CSP Headers**: All external domains must be included in Content Security Policy
- **HTTPS Only**: All add-in resources must be served over HTTPS
- **Versioning**: Auto-increment manifest version on deployment (handled by CI/CD)
- **Icon Requirements**: Must provide 16px, 32px, and 80px PNG icons
- **App Domains**: All API endpoints must be listed in `<AppDomains>` section

### Teams Adaptive Cards Design Constraints
⚠️ **Microsoft Teams Adaptive Card Best Practices**:
- **Text Wrapping**: Always set `"wrap": true` on TextBlock elements to prevent truncation on mobile
- **Column Layouts**: Use `"width": "stretch"` for flexible content, `"width": "auto"` for buttons
- **Visual Hierarchy**: Use Container elements with `"separator": true` for section breaks
- **Mobile First**: Design for narrow screens (≤450px), will scale up to desktop
- **Action Limits**: Maximum 6 primary actions, use Action.ShowCard for sub-actions
- **FactSet**: Use for key-value pairs instead of bullet lists for cleaner presentation
- **Spacing**: Use `"spacing": "Medium"` between major sections, `"Small"` for related items
- **Plain Text**: Teams doesn't support markdown in plain text responses, use TextBlock formatting instead

## Environment Variables

Required in `.env.local`:
```bash
# Core
API_KEY=your-secure-api-key
USE_LANGGRAPH=true  # CRITICAL: Enables LangGraph

# OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-5  # DO NOT CHANGE

# Azure
DATABASE_URL=postgresql://...
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_CONTAINER_NAME=email-attachments
AZURE_REDIS_CONNECTION_STRING=rediss://:password@hostname:port

# Zoho
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net
ZOHO_DEFAULT_OWNER_EMAIL=daniel.romitelli@emailthewell.com
ZOHO_VAULT_VIEW_ID=6221978000090941003  # Custom view "_Vault Candidates" (filters Publish_to_Vault=true server-side)

# APIs
FIRECRAWL_API_KEY=fc-...
APOLLO_API_KEY=...

# Zoom Integration
ZOOM_ACCOUNT_ID=xyz
ZOOM_CLIENT_ID=xyz
ZOOM_CLIENT_SECRET=xyz

# Weekly Digest Subscriptions (Added 2025-10-07)
EMAIL_PROVIDER=azure_communication_services
ACS_EMAIL_CONNECTION_STRING=endpoint=https://...  # Azure Communication Services for email delivery
SMTP_FROM_EMAIL=noreply@emailthewell.com
SMTP_FROM_NAME=TalentWell Vault

# Vault Agent Features
FEATURE_C3=true              # Enable C³ cache
FEATURE_VOIT=true            # Enable VoIT orchestration
C3_DELTA=0.01               # Risk bound (1%)
VOIT_BUDGET=5.0             # Processing budget
TARGET_QUALITY=0.9          # Target quality score
```

## Feature Flags

Feature flags allow gradual rollout of new functionality. Defaults live in `app/config/feature_flags.py` and can be overridden in `.env.local`.

### Privacy Features (Approved – 2025-10-05)

#### `PRIVACY_MODE` (default: `true`)
- Company anonymization (`"Morgan Stanley" → "Major wirehouse"`)
- Strict compensation normalization (`Target comp: $XXK–$YYK OTE`)
- Location bullet suppression to avoid duplicating header fields
- Rollback: set `PRIVACY_MODE=false` and restart the Container App

### AI Features

#### `FEATURE_GROWTH_EXTRACTION` (default: `true`)
- Extracts growth metrics such as "grew book 40% YoY" or "top 5% performer"
- High-priority category (0.95 weight) in bullet ranking

#### `FEATURE_LLM_SENTIMENT` (default: `true`)
- Enables GPT-5 sentiment analysis for bullet scoring (0.85–1.15 multiplier)
- Uses GPT-5-mini for accurate sentiment, enthusiasm, and professionalism detection
- Falls back to keyword-based heuristics if GPT-5 fails
- Positive sentiment = 5–15% boost, negative sentiment = 5–15% penalty
- Enabled 2025-10-05

### Performance Features

#### `FEATURE_ASYNC_ZOHO` (default: `false`)
⚠️ **Do not enable** – async client is blocked until Zoho call sites are refactored
- See `docs/decisions/talentwell-privacy-rollout.md` for status

### UX Features (Phase 3 – not implemented)
- `FEATURE_AUDIENCE_FILTERING`
- `FEATURE_CANDIDATE_SCORING`

## TalentWell Curator System

### Overview
The **TalentWell Curator** generates weekly candidate digests for financial advisors with Zoom transcript processing and evidence extraction.

### Financial Patterns Recognition
```python
# AUM/Book Size patterns from transcripts
'aum': [
    r'\$[\d,]+(?:\.\d+)?\s*(?:billion|B)\s*(?:AUM|aum|under management)',
    r'manages?[\s\w]*\$[\d,]+(?:\.\d+)?\s*[BMK]'
]

# Production patterns
'production': [
    r'\$[\d,]+(?:\.\d+)?\s*[BMK]?\s*(?:annual production|production)',
    r'(?:production|revenue)[:\s]+\$[\d,]+(?:\.\d+)?\s*[BMK]'
]
```

### DigestCard Format Requirements
- **‼️** for candidate name and title
- **🔔** for company and location
- **📍** for availability and compensation
- **3-5 bullet points** extracted from transcripts, resumes, CRM data
- **No fake data**: Only extract bullets from verifiable sources

## Production URLs

- **API**: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io
- **Health**: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
- **Manifest**: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/manifest.xml
- **Add-in Files**: Both root (`/`) and `/addin/` paths serve static files

## Common Issues & Solutions

### "temperature must be 1" Error
Always use `temperature=1` for GPT-5-mini calls

### 403 Forbidden
Ensure API_KEY in `.env.local` and load with `load_dotenv('.env.local')`

### Firecrawl Timeout
5-second timeout with graceful fallback to extraction-only

### Slow Processing
Check LangGraph is enabled: `USE_LANGGRAPH=true`

### Docker Permission Issues in WSL2
```bash
sudo usermod -aG docker $USER
newgrp docker  # Or restart terminal
```

### Container App Not Updating
Force revision with unique suffix:
```bash
az containerapp update --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:latest \
  --revision-suffix "v$(date +%Y%m%d-%H%M%S)"
```

## Future Enhancements

### Teams Bot Channel/Group Chat Support (Planned)
**Current Limitation**: Bot only works in 1:1 personal chats. Cannot @mention in channels or group chats.

**To Add Channel Support:**
1. Update bot manifest (`migrations/005_teams_integration_tables.sql`) to include team/channel scope
2. Modify `handle_message_activity()` in `app/api/teams/routes.py` to handle channel messages
3. Leverage existing `remove_mention_text()` helper for @mention parsing
4. Add channel-specific permission checks (public vs private channels)
5. Test @mention triggering in:
   - Team channels
   - Group chats
   - Private channels

**Implementation Files:**
- Bot manifest configuration
- `app/api/teams/routes.py:355-430` (message handler)
- `app/api/teams/adaptive_cards.py` (response cards)

**Use Cases:**
- @TalentWell digest advisors in #recruiting channel
- @TalentWell analytics in team standup
- Quick candidate queries without leaving channel context

## Recent Critical Fixes

### Vault Candidates Pagination & CSS Inlining (2025-10-07)
- **Issue**: Two critical bugs in weekly digest system
  1. Only 40 of 144 vault candidates returned due to single-page API fetch
  2. Email digests showing raw CSS code instead of styled HTML
- **Fixes**:
  1. **Pagination**: Use Zoho Custom View (`cvid` parameter) for server-side filtering
     - Added `ZOHO_VAULT_VIEW_ID` environment variable
     - View "_Vault Candidates" (ID: `6221978000090941003`) filters `Publish_to_Vault=true`
     - Now returns all 144 vault candidates in single request
  2. **CSS Inlining**: Migrated from `premailer` to `css-inline` library (14x faster)
     - Single inlining point in `TalentWellCurator._render_digest()`
     - Removed duplicate inlining from scheduler and send methods
     - Added Application Insights telemetry for CSS failures
     - `css_inlining_failures` metric tracks failures for ops visibility
- **Dependencies**: Removed `premailer==3.10.0` and `cssutils==2.11.1`, added `css-inline==0.14.2`
- **Files**: [app/integrations.py:1620](app/integrations.py:1620), [app/jobs/talentwell_curator.py:1454](app/jobs/talentwell_curator.py:1454), [app/mail/send.py:18](app/mail/send.py:18), [requirements.txt](requirements.txt)
- **Deployment**: Requires `pip install --upgrade` to get css-inline library

### Weekly Digest Email Subscription System (2025-10-07)
- **Feature**: Complete email subscription system for Teams Bot users
- **Implementation**:
  - Database schema: `teams_user_preferences` extended with subscription fields
  - Created `weekly_digest_deliveries` tracking table
  - Created `subscription_confirmations` audit table
  - Background scheduler: `app/jobs/weekly_digest_scheduler.py` (hourly job)
  - Azure Communication Services for email delivery
  - UI integration in Teams Bot preferences card
- **Subscription Fields**:
  - `subscription_active` - Toggle on/off
  - `delivery_email` - Where to send digests
  - `max_candidates_per_digest` - Customizable limit (1-20)
  - `last_digest_sent_at` - Delivery tracking
  - `next_digest_scheduled_at` - Automatic scheduling via database triggers
- **Files**: `migrations/006_weekly_digest_subscriptions.sql`, `app/jobs/weekly_digest_scheduler.py`, `app/api/teams/adaptive_cards.py`, `app/api/teams/routes.py`
- **Migration**: Applied successfully via `/api/teams/admin/run-migration` endpoint
- **Next Steps**: Set up scheduled job (Azure Container Apps Job or Azure Function) to run hourly digest processing

### Teams Bot Query Engine Fixes (2025-10-05)
- **Issue**: Three errors preventing digest generation and natural language queries
- **Fixes**:
  1. Changed `note_text` → `note_content` column references in query engine
  2. Added `max_cards` parameter to `TalentWellCurator.run_weekly_digest()`
  3. Fixed SQL variable scope with initialization and error handling
- **Files**: `app/api/teams/query_engine.py`, `app/jobs/talentwell_curator.py`
- **Commit**: `249fb36`

### TalentWell Privacy & AI Enhancement Rollout (2025-10-05)
- **Privacy Mode Enabled**: Company anonymization, strict compensation formatting, location bullet suppression
- **Implementation**:
  - Company names → generic descriptors ("Major wirehouse", "Large RIA")
  - Compensation → "Target comp: $XXK–$YYK OTE" format
  - Location only in header, filtered from bullets
- **AI Enhancements**:
  - Growth extraction: Parses "grew 40% YoY" and "$1B → $1.5B" patterns
  - GPT-5 sentiment analysis: 5–15% boost/penalty based on enthusiasm, professionalism, red flags
- **Feature Flags**: `PRIVACY_MODE=true`, `FEATURE_GROWTH_EXTRACTION=true`, `FEATURE_LLM_SENTIMENT=true`
- **Files**: `app/config/feature_flags.py`, `app/jobs/talentwell_curator.py`, `docs/decisions/talentwell-privacy-rollout.md`
- **Testing**: `tests/talentwell/test_data_quality.py`, `tests/talentwell/test_bullet_ranking.py`, `tests/talentwell/test_privacy_integration.py`
- **Rollback**: Set `PRIVACY_MODE=false` in Azure Container Apps environment variables

### Teams Bot Natural Language Query Engine (2025-10-05)
- **Feature**: Dual-mode operation with natural language query processing
- **Access Control**:
  - **Executive users** (steve@, brandon@, daniel.romitelli@): Full access to all business data
  - **Regular recruiters**: Filtered by `owner_email` to their own Zoho records only
- **Implementation**:
  - New query engine: `app/api/teams/query_engine.py`
  - GPT-5-mini intent classification with entity extraction (temperature=1)
  - SQL query builder with automatic owner filtering
  - Supports: deals, deal_notes, meetings tables
  - **CRITICAL**: `extract_user_email()` helper extracts real email from `additional_properties`, not `aad_object_id` GUID
- **Query Examples**:
  - "How many interviews last week?" → Executive sees all, recruiter sees only theirs
  - "Show me my deals from Q4" → Filtered by owner_email
  - "What's the status of John Smith?" → Search candidate name
- **Commands Still Work**: All existing commands (help, digest, preferences, analytics) work for everyone
- **Files**: `app/api/teams/routes.py:69-99,321-457`, `app/api/teams/query_engine.py`, `app/api/teams/adaptive_cards.py:208-247`

### Teams Bot Improvements (2025-10-04)
- **Issue**: Analytics command showed "unsupported card" error in Teams
- **Solution**: Changed from markdown to plain text formatting in `app/api/teams/routes.py:753-768`
- **Issue**: Filtering by owner email instead of candidate type
- **Solution**: Implemented job title keyword filtering in `app/integrations.py:1535-1656`
- **Issue**: Help card had poor visual presentation
- **Solution**: Redesigned using Microsoft Adaptive Cards best practices with containers, separators, FactSet

### City/State Preservation Fix (2025-09-27)
- **Issue**: City/state fields were being stripped during data cleaning
- **Solution**: Added modern fields to `field_limits` in `langgraph_manager.py:1333`
- **Files**: `app/langgraph_manager.py`, `addin/taskpane.js`

### Pipeline Lock Fix (2025-09-27)
- **Issue**: Pipeline dropdown allowed wrong values
- **Solution**: Changed to readonly input locked to "Sales Pipeline"
- **File**: `addin/taskpane.html:644`

### Referrer Contamination Fix (2025-09-27)
- **Issue**: Internal emails triggering referral source
- **Solution**: Filter metadata emails in `business_rules.py:68`
- **Domains**: `@emailthewell.com`, `@thewell.com`

### Zoho Deduplication Fix (2025-09-27)
- **Issue**: Search queries failing without parentheses
- **Solution**: Added parentheses to search criteria in `integrations.py`
- **Pattern**: `(Website:equals:{website})`

## Git & Pull Request Guidelines

### Commit Messages
- **Format**: Imperative mood, ≤65 characters (e.g., "Add redis cache guard")
- **Body**: Add detailed explanations when touching multiple services
- **Examples**:
  - ✅ "Fix city/state preservation in data cleaning"
  - ✅ "Add OAuth proxy architecture documentation"
  - ❌ "Fixed bugs" (too vague)
  - ❌ "Updated files" (not descriptive)

### Pull Request Requirements
1. **Summary**: Describe behavior changes and motivation
2. **Impact**: List affected endpoints, manifests, or components
3. **Testing**: Document validation steps (`pytest`, `npm run lint`, etc.)
4. **Screenshots**: Attach UI changes (taskpane, forms) as GIFs/images
5. **Configuration**: Flag any `.env` changes or manual deployment tasks
6. **Links**: Reference Azure Boards/Jira tickets if applicable

### Validation Checklist
```bash
# Before submitting PR:
pytest --cov=app --cov-report=term-missing  # ≥85% coverage required
npm run lint --prefix addin                 # No linting errors
npm run validate:all                        # Manifests valid
./run_tests.sh                              # CI automation passes
```

### Security Notes
- **Never commit secrets** - Use `.env.local` templates and Azure Key Vault
- **Rotate tokens** after accidental exposure via `oauth_service` configs
- **Refresh cache** after manifest/key changes using cache-bust deployment
