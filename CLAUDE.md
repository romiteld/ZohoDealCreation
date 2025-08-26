# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Well Intake API** - An intelligent email processing system that automates CRM record creation in Zoho from recruitment emails. Uses LangGraph with GPT-5-mini for structured data extraction through a three-node workflow (Extract → Research → Validate). Deployed on Azure Container Apps with PostgreSQL for deduplication.

## Current Status (Updated: 2025-08-26)

✅ **PRODUCTION READY**: LangGraph implementation fully operational
- **LangGraph v0.2.74** replacing CrewAI - Eliminates ChromaDB/SQLite dependency issues
- **Container Apps Deployment** - Running at `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io`
- **OAuth Service** - Active at `https://well-zoho-oauth.azurewebsites.net`
- Zoho Deal creation with correct v8 API field mappings
- Outlook Add-in with progress notifications
- Fast processing: ~2-3 seconds per email

## Critical Constraints

⚠️ **NEVER CHANGE THE AI MODEL** - System uses GPT-5-mini exclusively with temperature=1
⚠️ **NEVER HARDCODE OWNER IDS** - Use `ZOHO_DEFAULT_OWNER_EMAIL` environment variable
⚠️ **ALWAYS TEST BEFORE DESTRUCTIVE OPERATIONS** - Run server and API tests before cleanup

## Architecture

### Core Components
- **Main API** (`app/main.py`): FastAPI application with `/intake/email` endpoint
- **LangGraph Manager** (`app/langgraph_manager.py`): Three-node workflow using StateGraph
  - Extract Node: GPT-5-mini with structured output (Pydantic models)
  - Research Node: Firecrawl API for company validation
  - Validate Node: Data normalization and JSON standardization
- **Business Rules** (`app/business_rules.py`): Deal name formatting, source determination
- **Integrations** (`app/integrations.py`): Zoho API v8, Azure Blob Storage, PostgreSQL
- **Outlook Add-in** (`addin/`): Manifest and JavaScript for email forwarding

### External Services
- **Azure Container Apps**: Main deployment platform
- **Azure Container Registry**: `wellintakeregistry.azurecr.io`
- **Cosmos DB PostgreSQL**: With pgvector for embeddings
- **Azure Blob Storage**: Email attachment storage
- **OpenAI API**: GPT-5-mini via AsyncOpenAI client
- **Firecrawl API**: Company research and validation

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

# Quick test
python test_langgraph.py
```

### Docker & Deployment
```bash
# Build Docker image
docker build -t wellintakeregistry.azurecr.io/well-intake-api:latest .

# Push to Azure Container Registry
az acr login --name wellintakeregistry
docker push wellintakeregistry.azurecr.io/well-intake-api:latest

# Deploy to Container Apps
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeregistry.azurecr.io/well-intake-api:latest

# View logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --follow
```

### Testing
```bash
# Test LangGraph workflow
python test_langgraph.py

# Test API endpoints
python test_api.py

# Test Kevin Sullivan sample
curl -X GET "http://localhost:8000/test/kevin-sullivan" \
  -H "X-API-Key: your-api-key" | python -m json.tool
```

## Environment Configuration

Required `.env.local` file:
```bash
# Core Settings
API_KEY=your-secure-api-key
USE_LANGGRAPH=true  # CRITICAL: Enables LangGraph workflow

# OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-5-mini  # DO NOT CHANGE

# Azure Resources
DATABASE_URL=postgresql://...
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_CONTAINER_NAME=email-attachments

# Zoho Integration
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net
ZOHO_DEFAULT_OWNER_EMAIL=daniel.romitelli@emailthewell.com

# APIs
FIRECRAWL_API_KEY=fc-...
SERPER_API_KEY=...  # Optional, for legacy CrewAI
```

## LangGraph Workflow Details

### State Management
```python
class EmailProcessingState(TypedDict):
    email_content: str
    sender_domain: str
    extraction_result: Optional[Dict]
    company_research: Optional[Dict]
    validation_result: Optional[Dict]
    final_output: Optional[ExtractedData]
```

### Node Functions
1. **extract_information**: Uses GPT-5-mini with structured output
2. **research_company**: Calls Firecrawl API with sender domain
3. **validate_and_structure**: Normalizes data, handles nulls

### Error Handling
- Each node has try-catch with fallback to `SimplifiedEmailExtractor`
- Maintains extracted data even if research fails
- Always returns valid `ExtractedData` object

## Business Logic

### Deal Name Format
`"[Job Title] ([Location]) - [Firm Name]"`
- "Unknown" for missing values
- Applied in `business_rules.py::format_deal_name()`

### Source Determination
1. Referrer present → "Referral"
2. "TWAV" mentioned → "Reverse Recruiting"
3. Calendly link → "Website Inbound"
4. Default → "Email Inbound"

## API Workflow

1. Receive email at `/intake/email` with API key auth
2. Upload attachments to Azure Blob Storage
3. Process with LangGraph workflow (2-3 seconds)
4. Apply business rules formatting
5. Check PostgreSQL for duplicates
6. Create/update Zoho records (Account → Contact → Deal)
7. Store in PostgreSQL for future deduplication
8. Return Zoho record IDs

## Zoho Integration

- **API Version**: v8 (not v6)
- **OAuth**: Separate Flask service for token refresh
- **Field Mappings**:
  - `Source` (not `Lead_Source`)
  - `Source_Detail` for referrer names
  - `Deal_Name` with formatted pattern
- **Owner Assignment**: Via environment variable, not hardcoded

## Testing Strategy

### Kevin Sullivan Test
Expected extraction:
- Candidate: "Kevin Sullivan"
- Job Title: "Senior Financial Advisor"
- Location: "Fort Wayne area"
- Processing time: 2-3 seconds

### Duplicate Testing
Run same email twice - second run should:
- Find existing Account/Contact
- Create new Deal linked to existing records
- Return "found existing records" message

## Production URLs

- **API**: https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io
- **Health**: https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/health
- **Manifest**: https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml
- **OAuth**: https://well-zoho-oauth.azurewebsites.net

## Known Issues & Solutions

### Temperature Error with GPT-5-mini
- **Issue**: "temperature must be 1"
- **Solution**: Always use `temperature=1` in OpenAI calls

### API Key Authentication
- **Issue**: 403 Forbidden
- **Solution**: Ensure `.env.local` loaded with `load_dotenv('.env.local')`

### Firecrawl Timeout
- **Issue**: Company research times out
- **Solution**: 5-second timeout with graceful fallback

## Recent Changes (2025-08-26)

### ✅ LangGraph Migration Complete
- Replaced CrewAI with LangGraph v0.2.74
- Eliminated ChromaDB/SQLite dependency issues
- Reduced processing time from 45s to 2-3s
- Cleaned up 19 deprecated files
- Docker image v10 deployed to Container Apps

### File Cleanup Performed
- Removed all CrewAI-related files
- Deleted migration scripts and SQLite fixes
- Cleaned LogFiles directory
- Removed deprecated OAuth implementations