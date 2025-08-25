# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Well Intake API** - An intelligent email processing system that automates CRM record creation in Zoho from recruitment emails. Uses CrewAI with GPT-5-mini for data extraction, PostgreSQL for deduplication, and Azure services for infrastructure.

## Current Status (Updated: 2025-08-25)

✅ **WORKING**: Full pipeline operational
- **Migrated to Azure Container Apps** - Resolved SQLite compatibility issues
- **Icon rendering fixed** - All Outlook Add-in icons now display correctly
- Zoho Deal creation fixed with correct field mappings
- Progress notifications implemented in Outlook add-in
- Deployed to Azure Container Apps at `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io`
- OAuth service running at `https://well-zoho-oauth.azurewebsites.net`

## Critical Constraints

⚠️ **NEVER CHANGE THE AI MODEL** - The system uses GPT-5-mini exclusively. Do not change to GPT-4, GPT-3.5, or any other model.
⚠️ **NEVER HARDCODE OWNER IDS** - Owner field must be configurable via environment variables for multi-user production deployment.
⚠️ **PRESERVE OPTIMIZED VERSIONS** - The codebase contains both standard and optimized versions of key files (_optimized suffix). Do not merge or remove optimized versions without explicit instruction.

## Architecture

### Core Components
- **Main API** (`app/main.py`): FastAPI serving `/intake/email` and `/test/kevin-sullivan` endpoints
- **OAuth Service** (`app.py`): Flask app for Zoho OAuth token management at `https://well-zoho-oauth.azurewebsites.net`
- **CrewAI Manager** (`app/crewai_manager.py`): Three-agent pipeline using GPT-5-mini with optimized settings
- **Business Rules Engine** (`app/business_rules.py`): Enforces formatting rules for deal names, contact cleaning, and source determination
- **Integrations** (`app/integrations.py`): PostgreSQL client with pgvector, Azure Blob Storage, Zoho CRM API v8
- **Outlook Add-in** (`addin/`): Manifest.xml and JavaScript for Outlook integration

### External Dependencies
- **Azure Services**: Cosmos DB for PostgreSQL (distributed Citus), Blob Storage, Container Apps, Container Registry
- **AI Services**: OpenAI GPT-5-mini via CrewAI (temperature=1 required)
- **CRM**: Zoho CRM API v8 (not v6 as old comments suggest)
- **Web Research**: Firecrawl API for company validation
- **Container Runtime**: Docker with Python 3.11-slim base image

## Essential Commands

### Virtual Environment Setup
```bash
# Create and activate the zoho virtual environment
python -m venv zoho
source zoho/bin/activate  # Linux/Mac
# or
zoho\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Quick start with automated setup
./startup.sh  # Handles venv activation, dependency install, and server launch

# Manual FastAPI development server
uvicorn app.main:app --reload --port 8000

# Production deployment (Azure Container Apps)
gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker app.main:app

# OAuth service (Flask)
python app.py

# Docker Commands for Container Apps
docker build -t wellintakeregistry.azurecr.io/well-intake-api:v8 .
docker push wellintakeregistry.azurecr.io/well-intake-api:v8
```

### Testing Commands
```bash
# Verify all dependencies work correctly
python test_dependencies.py

# Test API endpoints
python test_api.py
python test_api_endpoints.py

# Test integrations (Zoho, Azure)
python test_integrations.py

# Run all tests
python test_all.py

# Test startup configuration
python test_startup.py
```

### Utility Commands
```bash
# Validate Outlook Add-in manifest
python validate_manifest.py

# Migrate to optimized versions
python migrate_to_optimized.py

# Restart Azure App Service (legacy)
./restart_app.sh

# Create Outlook Add-in icons
python create_icons.py
```

## Environment Configuration

Create `.env.local` in the root directory with:
```bash
# API Configuration
API_KEY=your_api_key_here
ENVIRONMENT=development

# Azure Services
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
AZURE_STORAGE_CONTAINER_NAME=email-attachments
DATABASE_URL=postgresql://...

# AI Services
OPENAI_API_KEY=sk-...
FIRECRAWL_API_KEY=fc-...

# Zoho Integration
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net
CLIENT_ID=1000.YOUR_CLIENT_ID_HERE
CLIENT_SECRET=your_client_secret_here
REDIRECT_URI=https://well-zoho-oauth.azurewebsites.net/callback

# Monitoring
LOG_ANALYTICS_WORKSPACE_ID=workspace-id
APPLICATION_INSIGHTS_KEY=ai-key
```

## Key Business Logic

### Deal Name Formatting
Format: `"[Job Title] ([Location]) - [Firm Name]"`
- Uses "Unknown" as placeholder for missing values
- Applied via `format_deal_name()` in business_rules.py

### Source Determination Priority
1. If referrer present → "Referral" + referrer name
2. If "TWAV"/"Advisor Vault" in text → "Reverse Recruiting" + "TWAV Platform"
3. If "Calendly" link → "Website Inbound" + "Calendly scheduling"
4. Default → "Email Inbound" + "Direct email contact"

### Company Identification Priority
1. Explicit mention in email body/signature
2. Firecrawl web research using sender domain
3. Domain fallback (inferred from email domain)

## CrewAI Agent Configuration

Three sequential agents process each email:
1. **Extraction Agent**: Extracts candidate_name, job_title, location, company_guess, referrer
2. **Enrichment Agent**: Validates company using Firecrawl research  
3. **Validation Agent**: Cleans and standardizes final JSON output

### Critical CrewAI Settings (Performance Optimized)
```python
# Model configuration - DO NOT CHANGE
model="gpt-5-mini"
temperature=1  # Required for GPT-5-mini, lower values cause errors

# Performance settings - DO NOT CHANGE  
memory=False  # Disabled to prevent 5-10s delays per task
max_execution_time=30  # Prevents timeouts
verbose=True  # Boolean only, not integer

# Result parsing
# Handle CrewOutput object with hasattr(result, 'raw')
# Extract JSON with regex: re.search(r'\{.*\}', result_str, re.DOTALL)
```

## API Workflow

1. **Receive email** from Outlook Add-in at `/intake/email`
2. **Validate** API key authentication
3. **Upload attachments** to Azure Blob Storage
4. **Process with CrewAI** for data extraction
5. **Apply business rules** for formatting
6. **Check Zoho** for duplicate contacts/accounts
7. **Create/update** Zoho records (Account → Contact → Deal)
8. **Return response** with created record IDs

## Zoho Integration Details

- **API Version**: v8 (current production version)
- **OAuth Flow**: Managed by separate Flask app (`app.py`)
- **Record Creation Order**: Account → Contact → Deal → Attachments
- **Owner**: Configurable via `ZOHO_DEFAULT_OWNER_ID` or `ZOHO_DEFAULT_OWNER_EMAIL` environment variables
- **Default Stage**: "Qualification"
- **Deduplication**: Reuses existing Accounts/Contacts based on email matching

## Development Considerations

### When modifying email processing:
- Test with `test_dependencies.py` first to ensure all packages work
- CrewAI agents may need prompt adjustments in `crewai_manager.py`
- Business rules are centralized in `business_rules.py`

### When updating Zoho integration:
- OAuth tokens expire - use the Flask OAuth service to refresh
- Check for existing records before creating to prevent duplicates
- Maintain creation order: Account → Contact → Deal

### When working with Azure resources:
- Blob Storage container: `email-attachments`
- Database: PostgreSQL-compatible Cosmos DB
- Use connection strings from `.env.local`

## Testing Approach

### Kevin Sullivan Test Endpoint
Use `/test/kevin-sullivan` endpoint to verify the full pipeline:
```bash
curl -X GET "http://localhost:8000/test/kevin-sullivan" \
  -H "X-API-Key: your-secure-api-key-here" | python -m json.tool
```

Expected behavior:
- Extracts: "Kevin Sullivan", "Senior Financial Advisor", "Fort Wayne area"
- Creates Zoho records with proper deduplication
- Completes in ~45-55 seconds (CrewAI takes ~10s after optimizations)

### Test Coverage Areas
- Email parsing with various formats
- Duplicate prevention logic (run test twice to verify)
- Business rule application (Deal naming format)
- Zoho API error handling
- Attachment upload to Azure Blob

### Running Individual Tests
```bash
# Test specific functionality
pytest app/test_business_rules.py::test_format_deal_name
pytest app/test_integrations.py::test_zoho_connection -v

# Run tests with coverage
pytest --cov=app --cov-report=html
```

## Monitoring

- Logs stream to Azure Log Analytics workspace
- Application Insights for performance metrics
- Custom metrics: emails_processed, zoho_records_created, ai_extraction_confidence

## Recent Fixes (2025-08-25)

### ✅ Zoho Deal Creation Fixed
- **Issue**: Deals were failing to create due to incorrect field mappings
- **Fix**: Updated field names to match Zoho API v8 requirements:
  - Using "Source" instead of "Lead_Source"
  - Proper source values: "Email Inbound", "Referral", "Website Inbound", "Reverse Recruiting"
  - Added "Source_Detail" field for referrer names
  - Enhanced error logging to show full Zoho API responses

### ✅ Progress Notifications Added
- **Issue**: Users had no feedback when clicking "Send to Zoho"
- **Fix**: Added step-by-step progress indicators:
  - "📧 Reading email content..."
  - "📎 Processing X attachment(s)..."
  - "🤖 Analyzing email with AI..."
  - "📊 Creating Zoho CRM records..."
  - Success message shows Deal name
  - Error messages include specific details

### ✅ Container Apps Migration Completed
- **Issue**: 503 Service Unavailable errors due to SQLite version incompatibility with ChromaDB
- **Fix**: Migrated from Azure App Service to Container Apps using Docker
  - Created Dockerfile with Python 3.11-slim base image
  - Added static directory for icon files
  - Updated to use Azure Container Registry (wellintakeregistry.azurecr.io)
  - Container Apps URL: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io`

### ✅ Outlook Add-in Icons Fixed
- **Issue**: Network connection error and missing icons in Outlook ribbon
- **Fix**: Created programmatic icon generation and serving
  - Generated 16x16, 32x32, and 80x80 PNG icons with black background and gold "TW" text
  - Added icon serving routes to FastAPI with proper path validation
  - Updated Dockerfile to include static directory
  - All manifest.xml icon URLs now return 200 status

## Known Issues & Solutions

### CrewAI Performance
- **Problem**: CrewAI times out or takes >2 minutes
- **Solution**: Ensure `memory=False` and `max_execution_time=30` are set

### GPT-5-mini Temperature Error
- **Problem**: "temperature must be 1 for GPT-5-mini"
- **Solution**: Always use `temperature=1`, never use 0.3 or other values

### API Key Authentication
- **Problem**: 403 Invalid API Key
- **Solution**: Ensure `.env.local` is loaded explicitly with `load_dotenv('.env.local')`

## Azure Deployment

### Production URLs (Current - Container Apps)
- **API Endpoint**: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io`
- **Manifest URL**: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml`
- **Commands JS**: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/commands.js`
- **Health Check**: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/health`
- **Icons**: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/icon-{16,32,80}.png`

### Azure Resources (Current Architecture)
- **Container App**: `well-intake-api` (East US region)
- **Container Registry**: `wellintakeregistry.azurecr.io`
- **Resource Group**: `TheWell-Infra-East`
- **Environment**: Container Apps Environment with consumption-based scaling
- **Runtime**: Python 3.11 in Docker container with Gunicorn/Uvicorn
- **OAuth Service**: `well-zoho-oauth` (Azure Web Apps - Flask)
- **Database**: Cosmos DB for PostgreSQL with pgvector extension
- **Blob Storage**: `wellintakeattachments` for email attachments

### Container Apps Deployment Commands
```bash
# Build and push Docker image
docker build -t wellintakeregistry.azurecr.io/well-intake-api:v8 .
docker push wellintakeregistry.azurecr.io/well-intake-api:v8

# Update Container App with new image
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeregistry.azurecr.io/well-intake-api:v8

# View Container App logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --follow

# Scale Container App (if needed)
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --min-replicas 1 \
  --max-replicas 3
```

### Legacy App Service (Deprecated)
- **Web App**: `well-intake-api` (Canada Central) - No longer used
- **Resource Group**: `TheWell-App-East` - Kept for OAuth service only

### Outlook Add-in Installation
1. **Microsoft 365 Admin Center**:
   - Navigate to Integrated Apps → Upload custom apps → Office Add-in
   - Provide URL: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml`
   
2. **User Authorization**:
   - Add authorized users (yourself, Steve, Brandon)
   - Add-in appears in Outlook with "Send to Zoho" button
   
3. **Multi-User Support**:
   - No hardcoded owner IDs
   - Configure via `ZOHO_DEFAULT_OWNER_ID` or `ZOHO_DEFAULT_OWNER_EMAIL` environment variables
   - System handles multiple authorized users dynamically

## File Structure Notes

### Optimized vs Standard Files
The codebase maintains two versions of critical files:
- `app/main.py` - Standard implementation
- `app/main_optimized.py` - Performance-optimized version
- `app/crewai_manager.py` - Standard CrewAI configuration  
- `app/crewai_manager_optimized.py` - Optimized with reduced latency
- `app/integrations.py` - Standard integrations
- `app/integrations_optimized.py` - Optimized with connection pooling

Use `migrate_to_optimized.py` to switch between versions.

### Static File Serving
The application serves static files for the Outlook Add-in:
- `/manifest.xml` - Add-in manifest configuration
- `/commands.js` - JavaScript for add-in functionality
- `/commands.html`, `/taskpane.html` - UI components
- `/icon-{16,32,80}.png` - Add-in icons with black background and gold "TW" text
These are handled by `app/main.py` routes and the static directory.

### Docker Configuration
The application uses a Docker container for deployment:
- **Base Image**: python:3.11-slim
- **Dependencies**: PostgreSQL client, libpq-dev, PIL for icon generation
- **Port**: 8000 (exposed)
- **Health Check**: HTTP request to /health endpoint every 30 seconds
- **Startup Command**: Gunicorn with Uvicorn workers for async support