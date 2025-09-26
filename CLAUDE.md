# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Well Intake API** - An intelligent email processing system that automates CRM record creation in Zoho from recruitment emails. Uses LangGraph with GPT-5 for structured data extraction through a three-node workflow (Extract → Research → Validate). Deployed on Azure Container Apps with PostgreSQL for deduplication.

## Architecture

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
- **Redis Cache Manager** (`app/redis_cache_manager.py`): Intelligent caching with 24hr TTL
- **Cache Strategies** (`app/cache_strategies.py`): Email classification and pattern recognition
- **Azure Cost Optimizer** (`app/azure_cost_optimizer.py`): Model tier selection and budget tracking
- **Service Bus Manager** (`app/service_bus_manager.py`): Batch queue management
- **Batch Processor** (`app/batch_processor.py`): Multi-email single-context processing
- **Azure AI Search Manager** (`app/azure_ai_search_manager.py`): Semantic search and learning
- **Learning Analytics** (`app/learning_analytics.py`): A/B testing and accuracy tracking
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
pytest tests/zoom/              # Zoom integration tests

# Run pytest with coverage
pytest --cov=app --cov-report=html

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

### Deployment
```bash
# Full deployment (DB migrations, Docker build, Azure deploy)
./scripts/deploy.sh

# Quick Docker deployment (use --no-cache for fresh builds)
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:latest . --no-cache
az acr login --name wellintakeacr0903
docker push wellintakeacr0903.azurecr.io/well-intake-api:latest

# Force Container App to use new image with revision suffix
az containerapp update --name well-intake-api --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:latest \
  --revision-suffix "v$(date +%Y%m%d-%H%M%S)"

# Purge CDN cache after deployment
az afd endpoint purge --resource-group TheWell-Infra-East \
  --profile-name well-intake-frontdoor \
  --endpoint-name well-intake-api \
  --domains well-intake-api-dnajdub4azhjcgc3.z03.azurefd.net \
  --content-paths "/*"

# View logs
az containerapp logs show --name well-intake-api --resource-group TheWell-Infra-East --follow

# GitHub Actions deployment (preferred)
# Push to main branch triggers deploy-production.yml workflow
# Manual workflow dispatch available in GitHub Actions tab
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
```

## TalentWell Curator & Vault Agent System

### Overview
The **TalentWell Curator** is a sophisticated system for generating weekly candidate digests for financial advisors, with comprehensive **Zoom transcript processing** and evidence extraction. It integrates with the **Vault Agent** for C³/VoIT orchestration.

### Core Components

#### TalentWell Curator (`app/jobs/talentwell_curator.py`)
- **Weekly digest generation** for candidates with financial advisor focus
- **Comprehensive Zoom transcript processing** with VTT format support
- **Evidence-based bullet generation** (3-5 bullets minimum from real data sources)
- **Redis caching** with 4-week deduplication
- **AST template compilation** for HTML rendering
- **Subject line bandit optimization** for email campaigns

#### Vault Agent API (`app/api/vault_agent/routes.py`)
- `POST /api/vault-agent/ingest` - Normalize and store candidate records
- `POST /api/vault-agent/publish` - Apply C³+VoIT and publish to channels
- `GET /api/vault-agent/status` - Check feature flags and configuration
- **C³ cache integration** with conformal guarantees
- **VoIT orchestration** for quality/cost optimization

#### Evidence Extractor (`app/extract/evidence.py`)
**Refactored from tech to financial advisor patterns**:
```python
class BulletCategory(Enum):
    FINANCIAL_METRIC = "financial_metric"      # AUM, production, book size
    GROWTH_ACHIEVEMENT = "growth_achievement"  # Growth metrics
    CLIENT_METRIC = "client_metric"           # Client count, retention
    PERFORMANCE_RANKING = "performance_ranking" # Rankings
    LICENSES = "licenses"                     # Series 7/66, CFA, CFP
    EXPERIENCE = "experience"                 # Years in financial services
```

#### Zoom Client (`app/zoom_client.py`)
- **Server-to-Server OAuth** authentication
- **Meeting recording** and **transcript fetching**
- **VTT format transcript** processing
- **Automatic token refresh** with 1-hour expiry

### Data Flow Pipeline

#### Zoom Transcript Processing
1. **Fetch transcript**: `ZoomClient.fetch_zoom_transcript_for_meeting()`
2. **Evidence extraction**: Parse financial metrics using regex patterns
3. **Bullet generation**: Extract AUM, production, growth, clients from transcripts
4. **Confidence scoring**: 0.95 for transcript evidence, 0.9 for CRM fields

#### Financial Patterns Recognition
```python
# AUM/Book Size patterns from transcripts
'aum': [
    r'\$[\d,]+(?:\.\d+)?\s*(?:billion|B)\s*(?:AUM|aum|under management)',
    r'manages?[\s\w]*\$[\d,]+(?:\.\d+)?\s*[BMK]',
    r'(?:book|portfolio)[\s\w]*\$[\d,]+(?:\.\d+)?\s*[BMK]'
]

# Production patterns
'production': [
    r'\$[\d,]+(?:\.\d+)?\s*[BMK]?\s*(?:annual production|production)',
    r'(?:production|revenue)[:\s]+\$[\d,]+(?:\.\d+)?\s*[BMK]'
]

# Growth patterns
'growth': [
    r'(?:grew|growth)[\s\w]*(?:from )?[~]?\$[\d,]+[\s\w]*(?:to )[~]?\$[\d,]+',
    r'(?:increased?)[\s\w]*(?:AUM|assets)[\s\w]*(?:by )?\d+(?:\.\d+)?%'
]
```

### Environment Variables
```bash
# Vault Agent Features
FEATURE_C3=true              # Enable C³ cache
FEATURE_VOIT=true            # Enable VoIT orchestration
C3_DELTA=0.01               # Risk bound (1%)
C3_EPS=3                    # Edit tolerance (characters)
VOIT_BUDGET=5.0             # Processing budget
TARGET_QUALITY=0.9          # Target quality score

# Zoom Integration
ZOOM_ACCOUNT_ID=xyz
ZOOM_CLIENT_ID=xyz
ZOOM_CLIENT_SECRET=xyz
ZOOM_SECRET_TOKEN=xyz       # For webhook verification
ZOOM_VERIFICATION_TOKEN=xyz # For webhook verification
```

### DigestCard Format (Brandon's Requirements)
```python
@dataclass
class DigestCard:
    deal_id: str
    candidate_name: str
    job_title: str
    company: str
    location: str
    bullets: List[BulletPoint]           # 3-5 bullets from real data
    transcript_url: Optional[str]        # Zoom transcript URL
    evidence_score: float               # Average confidence score
```

### HTML Output Format
**Critical**: Must match Brandon's format with emojis:
- **‼️** for candidate name and title
- **🔔** for company and location
- **📍** for availability and compensation
- **Plain text HTML** (not fancy cards)
- **3-5 bullet points** extracted from transcripts, resumes, CRM data

### Essential Testing Commands
```bash
# Test TalentWell curator
python -m app.jobs.talentwell_curator --audience steve_perry --days 7

# Test Zoom transcript fetching
python -c "from app.zoom_client import ZoomClient; import asyncio; client = ZoomClient(); asyncio.run(client.fetch_meeting_recording('MEETING_ID'))"

# Test vault agent ingestion
curl -X POST "http://localhost:8000/api/vault-agent/ingest" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"source": "email", "payload": {...}}'

# Test evidence extraction
python tests/test_financial_advisor_extraction.py
```

### Data Sources Integration
1. **Zoom Transcripts**: Primary source for financial metrics and achievements
2. **CRM Fields**: `book_size_aum`, `production_12mo`, `professional_designations`
3. **Resume Data**: Education, certifications, prior experience
4. **Email Content**: Additional context and referrer information

### Critical Business Rules
- **No fake data**: Only extract bullets from verifiable sources
- **Minimum 3 bullets**: Extract from transcripts, resumes, CRM if insufficient
- **Financial focus**: Prioritize AUM, production, growth, client metrics
- **Evidence linking**: Each bullet must trace back to source (transcript line, CRM field)
- **Confidence scoring**: Transcript evidence = 0.95, CRM = 0.9, inferred = 0.7

## Critical Constraints

⚠️ **NEVER CHANGE** - System requirements that must not be modified:
- **AI Model**: Always use `gpt-5` with `temperature=1`
- **Owner Assignment**: Use `ZOHO_DEFAULT_OWNER_EMAIL` environment variable, never hardcode IDs
- **Zoho API**: Use v8 endpoints (not v6)
- **Field Names**: Use `Source` (not `Lead_Source`), `Source_Detail` for referrer names

### Outlook Add-in Constraints
⚠️ **Office Add-in Specific Requirements**:
- **Manifest ID**: Never change the add-in ID `d2422753-f7f6-4a4a-9e1e-7512f37a50e5`
- **CDN URLs**: Always use Azure Front Door CDN URLs for production manifests
- **CSP Headers**: All external domains must be included in Content Security Policy
- **HTTPS Only**: All add-in resources must be served over HTTPS
- **Versioning**: Auto-increment manifest version on deployment (handled by CI/CD)
- **Icon Requirements**: Must provide 16px, 32px, and 80px PNG icons
- **App Domains**: All API endpoints must be listed in `<AppDomains>` section

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

# Zoho
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net
ZOHO_DEFAULT_OWNER_EMAIL=daniel.romitelli@emailthewell.com

# APIs
FIRECRAWL_API_KEY=fc-...
```

## API Workflow

1. Receive email at `/intake/email`
2. **Check Redis cache for similar email patterns**
3. Upload attachments to Azure Blob
4. Process with LangGraph (2-3 seconds) or use cached result
5. **Cache extraction results for future use**
6. Apply business rules
7. Check PostgreSQL for duplicates
8. Create/update Zoho records
9. Store in PostgreSQL
10. Return Zoho IDs

## Redis Caching (NEW)

### Configuration
Add to `.env.local`:
```bash
AZURE_REDIS_CONNECTION_STRING=rediss://:password@hostname:port
```

### Cost Benefits
- **GPT-5-mini**: $0.25/1M tokens (new requests)
- **Cached inputs**: $0.025/1M tokens (90% savings)
- **Response time**: <100ms for cached vs 2-3s for new

### Cache Endpoints
- `GET /cache/status` - View metrics and optimization recommendations
- `POST /cache/invalidate` - Clear cache entries (optional pattern)
- `POST /cache/warmup` - Pre-load common email patterns

### Caching Strategy
- **24-hour TTL** for standard emails
- **48-hour TTL** for referral emails
- **7-day TTL** for recruiter templates
- **90-day TTL** for common patterns

### Email Classification
Automatically classifies and optimizes caching for:
- Referral emails (highest cache priority)
- Recruiter outreach (template detection)
- Direct applications
- Follow-up emails
- Batch recruitment

## Common Issues

### "temperature must be 1" Error
Always use `temperature=1` for GPT-5-mini calls

### 403 Forbidden
Ensure API_KEY in `.env.local` and load with `load_dotenv('.env.local')`

### Firecrawl Timeout
5-second timeout with graceful fallback to extraction-only

### Slow Processing
Check LangGraph is enabled: `USE_LANGGRAPH=true`

## Production URLs

- **API**: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io
- **Health**: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
- **Manifest**: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/manifest.xml
- **Add-in Files**: Both root (`/`) and `/addin/` paths serve static files:
  - `/manifest.xml` or `/addin/manifest.xml`
  - `/commands.js` or `/addin/commands.js`
  - `/taskpane.js` or `/addin/taskpane.js`
  - `/commands.html` or `/addin/commands.html`
  - `/taskpane.html` or `/addin/taskpane.html`

## Recent Updates

### 2025-09-09: CDN Proxy Routing Fix
✅ **Fixed Flask Proxy CDN Management Routes**
- **Issue**: CDN endpoints returning 404 through proxy despite working directly on backend
- **Root Cause**: Conflict between IIS web.config URL rewrites and Flask routing
- **Solution**: Removed IIS `/api/*` rewrite rule, let Flask handle all API routing
- **New Routes**:
  - `/api/cdn/*` → Backend `/api/cdn/*` (CDN management)
  - `/cdn/*` → Backend `/api/cdn/*` (Alias route for convenience)
- **Endpoints Now Working**:
  - `GET /api/cdn/status` - CDN configuration and metrics
  - `POST /api/cdn/purge` - Purge specific paths from CDN cache
  - `GET /cdn/status` - Alias for CDN status
  - `POST /cdn/purge` - Alias for CDN purge

### 2025-08-29: GPT-5-mini 400K Context Optimization
✅ **Complete Azure Infrastructure Enhancement**
- **PostgreSQL with pgvector**: 400K context window support, similarity search
- **Azure Cache for Redis**: 90% cost reduction with intelligent caching
- **Azure Service Bus**: Batch processing (50 emails per GPT-5 context)
- **Azure AI Search**: Semantic pattern learning and company templates
- **Model Tiering**: Automatic GPT-5-nano/mini/full selection based on complexity
- **Enterprise Security**: Key Vault integration, API key rotation, rate limiting
- **Application Insights**: Custom metrics, cost tracking, performance monitoring

### Performance Improvements
- **Speed**: 20x faster batch processing, <1s for cached patterns
- **Cost**: 60-95% reduction through caching and intelligent model selection  
- **Scale**: Process thousands of emails/hour with Service Bus
- **Reliability**: Zero-downtime deployments, automatic retries

### 2025-09-09: C³ and VoIT Features
✅ **Conformal Counterfactual Cache (C³) and Value-of-Insight Tree (VoIT)**
- **C³ Cache**: Risk-bounded caching with conformal guarantees
  - `C3_DELTA=0.01`: 1% stale-risk tolerance  
  - `C3_EPS=3`: Edit distance tolerance in characters
  - Stores embeddings in Redis, computes cosine distance locally
  - Automatic calibration via conformal quantiles
- **VoIT Orchestration**: Budget-aware reasoning depth controller
  - `VOIT_BUDGET=5.0`: Effort units for processing
  - `TARGET_QUALITY=0.9`: Target quality score
  - Dynamically selects between GPT-5-nano/mini/full
  - Optimizes quality vs cost vs latency tradeoff
- **Vault Agent API**: Canonical record management
  - `POST /api/vault-agent/ingest`: Normalize and store records
  - `POST /api/vault-agent/publish`: Apply C³+VoIT and publish to channels
  - `GET /api/vault-agent/status`: Check feature flags and config

### Environment Variables (Azure Container Apps)
```bash
# C³ Configuration
FEATURE_C3=true         # Enable C³ cache
FEATURE_VOIT=true       # Enable VoIT orchestration
C3_DELTA=0.01          # Risk bound (1%)
C3_EPS=3               # Edit tolerance (characters)
VOIT_BUDGET=5.0        # Processing budget
TARGET_QUALITY=0.9     # Target quality score
```

Target significant cost reductions through intelligent caching and adaptive reasoning.

### 2025-09-16: Apollo WebSocket Removal & Static File Routes
✅ **Simplified Architecture**
- Removed all WebSocket/SignalR dependencies from backend
- Apollo integration now uses REST API exclusively
- Added `/addin/` endpoint aliases for all static files
- Cleaned up Container App URLs (migrated from salmonsmoke to wittyocean)
- Updated CSP headers to remove WebSocket connections
- Both root (`/`) and `/addin/` paths now serve Outlook Add-in files

### 2025-08-26: LangGraph Migration
✅ **LangGraph Implementation**
- Replaced CrewAI with LangGraph v0.2.74
- Eliminated ChromaDB/SQLite issues
- Reduced processing: 45s → 2-3s
- Docker image v10 on Container Apps

### 2025-09-17: Firecrawl v2 Web Search Client Complete Implementation
✅ **Full Firecrawl v2 Integration with Web Search Client**
- **Web Search Client Button**: Added to Outlook Add-in taskpane with progress indicator
- **Progress Tracking**: 5-step progress indicator (Web Crawl → Data Extract → Company Intel → Contact Enrich → AI Analysis)
- **API Endpoint Fix**: Corrected Firecrawl API from `/v2` to `/v1` endpoint
- **Enhanced Data Extraction**: Regex-based parsing of company phone, email, address, LinkedIn from scraped content
- **Graceful Fallbacks**: Switched from Extract API to Scrape API to work within token limitations
- **Container Deployment**: Successfully deployed as revision `complete-20250917-053434`
- **Key Components**:
  - `app/firecrawl_v2_fire_agent.py`: Core FIRE-1 agent with company research capabilities
  - `app/firecrawl_v2_adapter.py`: LangGraph interface adapter for workflow integration
  - `addin/taskpane.js`: Frontend integration with progress indicator and form population
  - `/api/firecrawl/enrich`: Backend REST endpoint for company enrichment

### 2025-09-17: Frontend Data Mapping Architecture Fix
✅ **Critical Frontend Bug Fixes**
- **Issue**: Frontend ignored structured backend data from Firecrawl/Apollo research
- **Root Cause**: Outlook Add-in mapping only used legacy flat fields, not new structured records
- **Solution**: Enhanced `taskpane.js` data mapper to use `ExtractedData` structured format
- **Key Changes**:
  - Fixed ternary operator precedence bug in location parsing (single cities no longer duplicate to state)
  - Added mapping for `contact_record.city/state` from backend research
  - Added mapping for `company_record.phone/website/detail` from Firecrawl/Apollo enrichment
  - Form population now prefers structured backend data over text parsing
- **Data Flow**: LangGraph Research → Structured Records → Frontend Mapping → Form Population
- **Impact**: Firecrawl v2 and Apollo.io research data now properly displays in Outlook Add-in forms

### 2025-09-26: TalentWell Curator & Financial Advisor Processing
✅ **Complete Financial Advisor Pipeline Implementation**
- **Evidence Extraction Refactoring**: Converted from tech patterns (Python/Java/AWS) to financial advisor patterns (AUM/production/licenses)
- **TalentWell Curator System**: Full weekly digest generation with Zoom transcript processing
- **Vault Agent Integration**: C³/VoIT orchestration for candidate record management
- **Financial Pattern Recognition**: Comprehensive regex patterns for AUM, production, growth, client metrics
- **Zoom Server-to-Server OAuth**: Complete integration for transcript fetching and processing
- **Brandon's HTML Format**: Emoji-based candidate cards (‼️🔔📍) with 3-5 bullet points from real data sources
- **Key Components**:
  - `app/jobs/talentwell_curator.py`: Core digest generation with evidence extraction
  - `app/extract/evidence.py`: Financial advisor-specific pattern recognition
  - `app/api/vault_agent/routes.py`: C³ cache and VoIT orchestration endpoints
  - `app/zoom_client.py`: Complete Zoom API integration with VTT transcript support
- **Critical Requirements**: No fake data, minimum 3 bullets from transcripts/resumes/CRM, financial metrics priority