# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Well Intake API** - An intelligent email processing system that automates CRM record creation in Zoho from recruitment emails. Uses LangGraph with GPT-5 for structured data extraction through a three-node workflow (Extract → Research → Validate). Deployed on Azure Container Apps with PostgreSQL for deduplication.

## Architecture

### Core Stack
- **LangGraph v0.2.74** - Workflow orchestration (replaced CrewAI)
- **FastAPI** - Main API framework with WebSocket support
- **GPT-5 Model Tiers** - Intelligent selection (temperature=1 ALWAYS):
  - GPT-5-nano: $0.05/1M input (simple emails)
  - GPT-5-mini: $0.25/1M input (standard)
  - GPT-5: $1.25/1M input (complex)
- **Azure Cache for Redis** - Prompt/response caching (90% cost reduction)
- **Azure Container Apps** - Production deployment with auto-scaling
- **PostgreSQL with pgvector** - 400K context window support, embeddings
- **Azure Blob Storage** - Attachment storage
- **Azure Service Bus** - Batch email processing (50 emails/batch)
- **Azure SignalR/WebSocket** - Real-time streaming responses
- **Azure AI Search** - Semantic pattern learning
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
- **SignalR Manager** (`app/signalr_manager.py`): WebSocket streaming infrastructure
- **Streaming Endpoints** (`app/streaming_endpoints.py`): Real-time API endpoints
- **Azure AI Search Manager** (`app/azure_ai_search_manager.py`): Semantic search and learning
- **Learning Analytics** (`app/learning_analytics.py`): A/B testing and accuracy tracking
- **Monitoring** (`app/monitoring.py`): Application Insights integration
- **Security Config** (`app/security_config.py`): Key Vault and API key management
- **Business Rules** (`app/business_rules.py`): Deal name formatting, source determination
- **Integrations** (`app/integrations.py`): Zoho API v8, Azure services
- **Outlook Add-in** (`addin/`): Manifest with WebSocket support

## Essential Commands

### Local Development
```bash
# Activate virtual environment
source zoho/bin/activate  # Linux/Mac
zoho\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000

# Test LangGraph workflow
python test_langgraph.py

# Test container deployment
python test_container_deployment.py
```

### Deployment
```bash
# Full deployment (DB migrations, Docker build, Azure deploy)
./deploy.sh

# Quick Docker deployment
docker build -t wellintakeregistry.azurecr.io/well-intake-api:latest .
az acr login --name wellintakeregistry
docker push wellintakeregistry.azurecr.io/well-intake-api:latest
az containerapp update --name well-intake-api --resource-group TheWell-Infra-East --image wellintakeregistry.azurecr.io/well-intake-api:latest

# View logs
az containerapp logs show --name well-intake-api --resource-group TheWell-Infra-East --follow
```

### Testing
```bash
# Test Kevin Sullivan sample
curl -X GET "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/test/kevin-sullivan" \
  -H "X-API-Key: your-api-key" | python -m json.tool

# Health check
curl https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/health
```

## Critical Constraints

⚠️ **NEVER CHANGE** - System requirements that must not be modified:
- **AI Model**: Always use `gpt-5` with `temperature=1`
- **Owner Assignment**: Use `ZOHO_DEFAULT_OWNER_EMAIL` environment variable, never hardcode IDs
- **Zoho API**: Use v8 endpoints (not v6)
- **Field Names**: Use `Source` (not `Lead_Source`), `Source_Detail` for referrer names

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
2. **Research Node**: Firecrawl API for company validation (5s timeout)
3. **Validate Node**: Data normalization and JSON standardization

### Error Handling
- Fallback to `SimplifiedEmailExtractor` on errors
- Maintains partial data through pipeline
- Always returns valid `ExtractedData` object

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
- **Azure SignalR/WebSocket**: Real-time streaming (first token <200ms)
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

### 2025-08-26: LangGraph Migration
✅ **LangGraph Implementation**
- Replaced CrewAI with LangGraph v0.2.74
- Eliminated ChromaDB/SQLite issues
- Reduced processing: 45s → 2-3s
- Docker image v10 on Container Apps