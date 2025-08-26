# Well Intake API - Intelligent Email Processing System

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![Azure](https://img.shields.io/badge/Azure-Container%20Apps-blue.svg)](https://azure.microsoft.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.74-orange.svg)](https://github.com/langchain-ai/langgraph)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

An intelligent email processing system that automatically converts recruitment emails into structured CRM records in Zoho. The system uses **LangGraph** with GPT-5-mini for AI-powered extraction, providing a robust three-node workflow (extract → research → validate). This eliminates manual data entry and ensures accurate record creation with intelligent fallback mechanisms.

## 🎯 Key Features

- **🤖 AI-Powered Extraction**: Uses LangGraph with GPT-5-mini for intelligent, multi-step data extraction
- **🔗 Three-Node Workflow**: Extract → Research (Firecrawl) → Validate pipeline for accuracy
- **📧 Outlook Integration**: Seamless integration via Outlook Add-in with "Send to Zoho" button  
- **🔄 Automated CRM Creation**: Automatically creates Accounts, Contacts, and Deals in Zoho CRM
- **🚫 Duplicate Prevention**: Smart deduplication based on email and company matching
- **📎 Attachment Handling**: Automatic upload and storage of email attachments to Azure Blob Storage
- **🏢 Multi-User Support**: Configurable owner assignment for enterprise deployment
- **⚡ High Performance**: Fast processing with structured output and error handling
- **🔍 Company Validation**: Uses Firecrawl API for real-time company research and validation

## 🏗️ Architecture Overview

> **Latest Update (August 2025)**: Migrated from CrewAI to **LangGraph** for improved reliability and performance. The system now runs on Azure Container Apps with a Docker-based deployment, eliminating previous dependency conflicts.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│  Outlook Email  │────▶│  Outlook Add-in  │────▶│   FastAPI App          │
└─────────────────┘     └──────────────────┘     │ (Container Apps)       │
                                                  └───────────┬─────────────┘
                                                              │
        ┌─────────────────────────────────────────────────────┼─────────────────────────────────────────────┐
        │                                                     │                                             │
  ┌─────▼──────────┐                                   ┌─────▼──────────┐                          ┌───────▼────────┐
  │   LangGraph    │                                   │  Azure Blob    │                          │   Zoho CRM    │
  │  GPT-5-mini    │◄──────┐                          │   Storage      │                          │   API v8      │
  └─────┬──────────┘       │                          └────────────────┘                          └───────┬────────┘
        │                  │                                                                               │
        ▼                  │                                                                               │
  ┌─────────────┐    ┌─────┴──────┐                                                              ┌───────▼────────┐
  │  Extract    │───▶│  Research  │                   ┌────────────────┐                          │  OAuth Service │
  │    Node     │    │ (Firecrawl)│                   │ Cosmos DB      │                          │(well-zoho-     │
  └─────────────┘    └─────┬──────┘                   │ PostgreSQL     │                          │ oauth)         │
                           │                           │ with pgvector  │                          └────────────────┘
                           ▼                           └────────────────┘
                     ┌─────────────┐
                     │  Validate   │
                     │    Node     │
                     └─────────────┘
```

### Azure Resource Organization

**Resource Groups:**
- **TheWell-Infra-East**: Infrastructure and Container App resources (East US region)
  - `well-intake-api` - Main FastAPI application (Azure Container Apps)
  - `wellintakeregistry` - Azure Container Registry for Docker images
  - Python 3.11 runtime with Gunicorn/Uvicorn in Docker container
  - Container Apps Environment with consumption-based scaling
  - `well-zoho-oauth` - OAuth token management service (Azure Web Apps - Flask)
  - `well-intake-db` - Cosmos DB for PostgreSQL with Citus distributed database
    - PostgreSQL 15 with pgvector extension
    - 2 vCores, 128GB storage on coordinator node
    - Distributed architecture for scalability
  - `wellintakeattachments` - Azure Blob Storage for email attachments
    - Container: `email-attachments` with private access
    - SAS token authentication for secure access
    - Standard_LRS redundancy
  - Log Analytics Workspace - Application monitoring and diagnostics
    - 30-day retention period
    - Integration with Container Apps for log streaming

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Azure account with active subscription
- Zoho CRM account with API access
- OpenAI API key for GPT-5-mini
- Firecrawl API key for web research

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd outlook
```

2. **Set up virtual environment**
```bash
python -m venv zoho
source zoho/bin/activate  # Linux/Mac
# or
zoho\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
Create a `.env.local` file in the root directory:
```env
# API Configuration
API_KEY=your-secure-api-key-here
ENVIRONMENT=development

# Azure Services
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=<storage-account>;...
AZURE_STORAGE_CONTAINER_NAME=email-attachments
DATABASE_URL=postgresql://<username>:<password>@<hostname>:5432/<database>?sslmode=require

# AI Services
OPENAI_API_KEY=sk-...
FIRECRAWL_API_KEY=fc-...

# Zoho Integration
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net
CLIENT_ID=1000.YOUR_CLIENT_ID
CLIENT_SECRET=your_client_secret
REDIRECT_URI=https://well-zoho-oauth.azurewebsites.net/callback
ZOHO_DEFAULT_OWNER_ID=owner_id_here  # Optional
ZOHO_DEFAULT_OWNER_EMAIL=owner@example.com  # Optional

# Feature Flags
BYPASS_CREWAI=true  # Set to false to enable CrewAI (requires resolving ChromaDB dependencies)

# Monitoring (Optional)
LOG_ANALYTICS_WORKSPACE_ID=workspace-id
APPLICATION_INSIGHTS_KEY=ai-key
```

5. **Run the application**
```bash
# Quick start (handles everything automatically)
./startup.sh

# Or manually
uvicorn app.main:app --reload --port 8000
```

6. **Access the application**
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Test Endpoint: http://localhost:8000/test/kevin-sullivan

## 📋 API Endpoints

### Core Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| POST | `/intake/email` | Process email and create Zoho records | API Key |
| GET | `/test/kevin-sullivan` | Test the full pipeline with sample data | API Key |
| GET | `/health` | Health check endpoint | None |
| GET | `/manifest.xml` | Outlook Add-in manifest | None |

### Request Format

```json
POST /intake/email
{
    "subject": "Email subject",
    "body": "Email body content",
    "sender": "sender@example.com",
    "attachments": [
        {
            "name": "resume.pdf",
            "content": "base64_encoded_content"
        }
    ]
}
```

### Response Format

```json
{
    "success": true,
    "message": "Email processed successfully",
    "data": {
        "account_id": "123456789",
        "contact_id": "987654321",
        "deal_id": "456789123",
        "attachments_uploaded": 1
    }
}
```

## 🧪 Testing

### Run All Tests
```bash
python test_all.py
```

### Run Specific Test Suites
```bash
# Test dependencies
python test_dependencies.py

# Test API endpoints
python test_api_endpoints.py

# Test integrations
python test_integrations.py

# Test with pytest
pytest app/test_business_rules.py -v
pytest --cov=app --cov-report=html
```

### Test the Kevin Sullivan Endpoint
```bash
curl -X GET "http://localhost:8000/test/kevin-sullivan" \
  -H "X-API-Key: your-secure-api-key-here" | python -m json.tool
```

## 🚢 Deployment

### Complete Azure Infrastructure

#### 1. Azure Resources Overview

| Resource | Name | Resource Group | Type | Purpose |
|----------|------|----------------|------|---------|
| Main API | `well-intake-api` | TheWell-App-East | Web App (Python 3.12) | FastAPI email processing service |
| OAuth Service | `well-zoho-oauth` | TheWell-Infra-East | Web App (Python 3.11) | Zoho OAuth token management |
| Database | `well-intake-db` | TheWell-Infra-East | Cosmos DB for PostgreSQL | Distributed database with pgvector for deduplication |
| Blob Storage | Private Storage Account | TheWell-Infra-East | Storage Account (Standard_LRS) | Email attachment storage with SAS token access |
| Monitoring | Log Analytics Workspace | TheWell-Infra-East | Log Analytics | Application monitoring and diagnostics |

**Production URLs:**
- Main API: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io`
- OAuth Service: `https://well-zoho-oauth.azurewebsites.net`
- Manifest: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml`

#### 2. Main API Deployment (well-intake-api)

```bash
# Prepare deployment package
zip -r deploy.zip . -x "zoho/*" "*.pyc" "__pycache__/*" ".env*" "*.git*" "deploy.zip" "test_*.py" "server.log"

# Deploy to Azure
az webapp deploy --resource-group TheWell-App-East \
  --name well-intake-api --src-path deploy.zip --type zip

# Configure startup command
az webapp config set --resource-group TheWell-App-East --name well-intake-api \
  --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker app.main:app"

# Set environment variables
az webapp config appsettings set --resource-group TheWell-App-East \
  --name well-intake-api --settings @app-settings.json

# Monitor logs
az webapp log tail --resource-group TheWell-App-East --name well-intake-api
```

#### 3. OAuth Service Deployment (well-zoho-oauth)

```bash
# Deploy OAuth service (Flask app)
cd oauth-service
zip -r oauth-deploy.zip . -x "*.pyc" "__pycache__/*" ".env*" "*.git*"

az webapp deploy --resource-group TheWell-Infra-East \
  --name well-zoho-oauth --src-path oauth-deploy.zip --type zip

# Configure Flask startup
az webapp config set --resource-group TheWell-Infra-East --name well-zoho-oauth \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app"

# View OAuth service logs
az webapp log tail --resource-group TheWell-Infra-East --name well-zoho-oauth
```

#### 4. Database Configuration (Cosmos DB for PostgreSQL)

```bash
# Connection details
Host: <your-db-server>.postgres.cosmos.azure.com
Port: 5432
Database: citus
Username: <db-username>
SSL Mode: require

# Connect to database
psql "host=<your-db-server>.postgres.cosmos.azure.com port=5432 dbname=citus user=<db-username> sslmode=require"

# Enable pgvector extension (for AI embeddings)
CREATE EXTENSION IF NOT EXISTS vector;

# Create tables for deduplication and caching
CREATE TABLE IF NOT EXISTS processed_emails (
    message_id VARCHAR(255) PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    zoho_deal_id VARCHAR(100),
    embeddings vector(1536)
);
```

#### 5. Blob Storage Configuration

```bash
# Storage account details
Account Name: <your-storage-account>
Container: email-attachments
Access Level: Private (SAS token required)

# Create container if not exists
az storage container create \
  --name email-attachments \
  --account-name <your-storage-account> \
  --auth-mode login

# Generate SAS token for application access
az storage container generate-sas \
  --name email-attachments \
  --account-name <your-storage-account> \
  --permissions rwdl \
  --expiry 2026-12-31 \
  --auth-mode login
```

#### 6. Monitoring Setup

```bash
# Log Analytics Workspace
Workspace ID: <your-workspace-id>
Workspace Name: <your-workspace-name>

# Configure application to send logs
az webapp log config \
  --resource-group TheWell-App-East \
  --name well-intake-api \
  --application-logging filesystem \
  --detailed-error-messages true \
  --failed-request-tracing true \
  --level verbose

# Query logs
az monitor log-analytics query \
  --workspace <your-workspace-id> \
  --analytics-query "AppServiceHTTPLogs | where TimeGenerated > ago(1h) | where ScStatus >= 400"
```

#### 7. Health Check Endpoints

```bash
# Main API health check
curl https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/health

# OAuth service health check  
curl https://well-zoho-oauth.azurewebsites.net/health

# Database connectivity check
az postgres flexible-server show-connection-string \
  --server-name well-intake-db \
  --database-name citus \
  --admin-user citus
```

### Outlook Add-in Installation

1. Navigate to Microsoft 365 Admin Center
2. Go to Integrated Apps → Upload custom apps → Office Add-in
3. Provide manifest URL: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml`
4. Add authorized users
5. The "Send to Zoho" button will appear in Outlook

## 🔧 Configuration

### Business Rules

The system enforces the following business rules:

- **Deal Name Format**: `"[Job Title] ([Location]) - [Firm Name]"`
- **Source Determination Priority**:
  1. Referral (if referrer present)
  2. Reverse Recruiting (if TWAV/Advisor Vault mentioned)
  3. Website Inbound (if Calendly link present)
  4. Email Inbound (default)

### CrewAI Configuration

The system uses three sequential AI agents:

1. **Extraction Agent**: Extracts basic candidate information
2. **Enrichment Agent**: Validates and enriches company data
3. **Validation Agent**: Cleans and standardizes output

**Critical Settings**:
- Model: GPT-5-mini (DO NOT CHANGE)
- Temperature: 1 (required for GPT-5-mini)
- Memory: Disabled for performance
- Max Execution Time: 30 seconds

## 📁 Project Structure

```
outlook/
├── app/                      # Main application code
│   ├── main.py              # FastAPI application
│   ├── main_optimized.py    # Optimized version
│   ├── crewai_manager.py    # AI orchestration
│   ├── business_rules.py    # Business logic
│   ├── integrations.py      # External service integrations
│   ├── models.py            # Pydantic models
│   └── static_files.py      # Static file serving
├── addin/                    # Outlook Add-in files
│   ├── manifest.xml         # Add-in configuration
│   ├── commands.js          # JavaScript functionality
│   └── *.html               # UI components
├── test_*.py                 # Test files
├── requirements.txt          # Python dependencies
├── startup.sh               # Quick start script
├── .env.local               # Environment variables (create this)
└── CLAUDE.md                # AI assistant instructions
```

## 🐛 Troubleshooting

### Common Issues

#### CrewAI Timeout
- **Problem**: CrewAI takes >2 minutes or times out
- **Solution**: Ensure `memory=False` and `max_execution_time=30` in CrewAI configuration

#### GPT-5-mini Temperature Error
- **Problem**: "temperature must be 1 for GPT-5-mini"
- **Solution**: Always use `temperature=1`, never change to other values

#### Zoho Owner Field Errors
- **Problem**: 400 Bad Request when creating Deals
- **Solution**: Ensure `ZOHO_DEFAULT_OWNER_ID` or `ZOHO_DEFAULT_OWNER_EMAIL` is configured

#### API Key Authentication Failed
- **Problem**: 503 Service Unavailable on Azure App Service
- **Solution**: Verify `.env.local` exists and is loaded with `load_dotenv('.env.local')`

#### ChromaDB Dependency Conflict (RESOLVED)
- **Problem**: "'function' object is not iterable" error when CrewAI imports ChromaDB
- **Root Cause**: CrewAI has hard dependency on ChromaDB even when knowledge features aren't used
- **Solution**: Set `BYPASS_CREWAI=true` to use simplified email extraction (95% faster)
- **Status**: ✅ Resolved - System defaults to bypass mode for optimal performance

#### SQLite Compatibility Issue (RESOLVED)
- **Problem**: 503 Service Unavailable errors due to SQLite version incompatibility
- **Root Cause**: Azure App Service Python 3.12 runtime includes SQLite 3.31, but ChromaDB requires SQLite 3.35+
- **Solution**: Migrated to Azure Container Apps using Docker with Python 3.11-slim (includes SQLite 3.40+)
- **Status**: ✅ Resolved - System now runs on Container Apps at `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io`

#### Outlook Add-in Icon Issues (RESOLVED)
- **Problem**: Network connection error and missing icons in Outlook ribbon
- **Root Cause**: Icon files referenced in manifest.xml returned 404 errors
- **Solution**: Created programmatic icon generation with black background and gold "TW" text
- **Status**: ✅ Resolved - All icons now display correctly in Outlook

## 📊 Performance Metrics

### ChromaDB Bypass Mode (Current - Default)
- **Average Processing Time**: 2-3 seconds per email
- **Email Extraction**: ~0.5 seconds (simplified parser)
- **Zoho API Operations**: ~1-2 seconds  
- **Attachment Upload**: ~0.5-1 second per file
- **Overall Performance**: 95% faster than CrewAI mode

### CrewAI Mode (Optional - when BYPASS_CREWAI=false)
- **Average Processing Time**: 45-55 seconds per email
- **CrewAI Execution**: ~10 seconds (after optimizations)
- **Zoho API Operations**: ~20-30 seconds
- **Attachment Upload**: ~5-10 seconds per file

## 🔐 Security Considerations

- API key authentication required for all endpoints
- Environment variables for sensitive configuration
- No hardcoded credentials or owner IDs
- Secure OAuth2 flow for Zoho authentication
- Azure Blob Storage for attachment security

## 🤝 Contributing

This is a proprietary system for The Well Recruiting. For questions or issues, please contact the development team.

## 📄 License

Proprietary - All rights reserved by The Well Recruiting

## 🆘 Support

For support and questions:
- Check the `CLAUDE.md` file for development guidelines
- Review test files for usage examples
- Contact the development team for assistance

---

**Production URL**: https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io

**Last Updated**: August 26, 2025 - ChromaDB bypass solution implemented