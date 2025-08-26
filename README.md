# Well Intake API - Intelligent Email Processing System with Reverse Proxy

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![Azure](https://img.shields.io/badge/Azure-Container%20Apps-blue.svg)](https://azure.microsoft.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.74-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-red.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

An intelligent email processing system that automatically converts recruitment emails into structured CRM records in Zoho. The system uses **LangGraph** with GPT-5-mini for AI-powered extraction, providing a robust three-node workflow (extract → research → validate). Features a secure reverse proxy architecture for centralized authentication and enhanced security.

## 🎯 Key Features

- **🤖 AI-Powered Extraction**: Uses LangGraph with GPT-5-mini for intelligent, multi-step data extraction
- **🔐 Secure Reverse Proxy**: Centralized OAuth and API key management through dedicated proxy service
- **🔗 Three-Node Workflow**: Extract → Research (Firecrawl) → Validate pipeline for accuracy
- **📧 Outlook Integration**: Seamless integration via Outlook Add-in with "Send to Zoho" button  
- **🔄 Automated CRM Creation**: Automatically creates Accounts, Contacts, and Deals in Zoho CRM
- **🚫 Duplicate Prevention**: Smart deduplication based on email and company matching
- **📎 Attachment Handling**: Automatic upload and storage of email attachments to Azure Blob Storage
- **🏢 Multi-User Support**: Configurable owner assignment for enterprise deployment
- **⚡ High Performance**: Fast processing (2-3 seconds) with structured output and error handling
- **🔍 Company Validation**: Uses Firecrawl API for real-time company research and validation
- **🛡️ Enhanced Security**: Rate limiting, circuit breaker pattern, and automatic API key injection

## 🏗️ Architecture Overview

> **Latest Update (August 2025)**: 
> - Migrated from CrewAI to **LangGraph** for improved reliability and performance
> - Added **OAuth Reverse Proxy Service** for centralized authentication and security
> - System runs on Azure Container Apps with Docker-based deployment

### System Architecture

```
┌──────────────────┐
│  Outlook Email   │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│         Microsoft 365 Admin Center           │
│            (Integrated Apps)                  │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│      OAuth Reverse Proxy Service             │
│    (well-zoho-oauth.azurewebsites.net)       │
│                                               │
│  Features:                                    │
│  • Zoho OAuth token refresh & caching        │
│  • Automatic API key injection               │
│  • Rate limiting (100 req/min)               │
│  • Circuit breaker protection                │
│  • Request forwarding with headers           │
│  • CORS support                              │
└────────────────┬─────────────────────────────┘
                 │ Proxies all /api/* requests
                 │ Adds X-API-Key automatically
                 ▼
┌──────────────────────────────────────────────┐
│         Container Apps API                    │
│  (well-intake-api.azurecontainerapps.io)     │
│                                               │
│  ┌──────────────────────────────────────┐    │
│  │       LangGraph Workflow              │    │
│  │                                       │    │
│  │  ┌────────┐  ┌────────┐  ┌────────┐ │    │
│  │  │Extract │→ │Research│→ │Validate│ │    │
│  │  │ Node   │  │  Node  │  │  Node  │ │    │
│  │  └────────┘  └────────┘  └────────┘ │    │
│  └──────────────────────────────────────┘    │
└────────────────┬─────────────────────────────┘
                 │
    ┌────────────┼────────────┬───────────────┐
    │            │            │               │
┌───▼────┐  ┌───▼────┐  ┌───▼────┐    ┌─────▼─────┐
│OpenAI  │  │Firecrawl│  │Azure   │    │Zoho CRM   │
│GPT-5   │  │  API    │  │Blob    │    │API v8     │
│mini    │  │         │  │Storage │    │           │
└────────┘  └─────────┘  └────────┘    └───────────┘
```

### Azure Resource Organization

**Resource Groups:**
- **TheWell-Infra-East**: Infrastructure and application resources (East US region)
  
  **Core Services:**
  - `well-zoho-oauth` - **OAuth Reverse Proxy Service** (Azure App Service - Flask)
    - Handles all API routing with authentication
    - Manages Zoho OAuth token refresh
    - Implements security features (rate limiting, circuit breaker)
    - Single entry point for all API calls
    
  - `well-intake-api` - Main FastAPI application (Azure Container Apps)
    - LangGraph workflow engine with GPT-5-mini
    - Business logic and data processing
    - Protected behind reverse proxy
    
  - `wellintakeregistry` - Azure Container Registry
    - Docker image repository
    - Version control for deployments
    
  - `well-intake-db` - Cosmos DB for PostgreSQL
    - PostgreSQL 15 with pgvector extension
    - Distributed Citus architecture
    - Deduplication and data persistence
    
  - `wellintakeattachments` - Azure Blob Storage
    - Email attachment storage
    - Private container with SAS token auth

## 🚀 Production URLs

### Primary Service (Use These)
- **Service Root**: https://well-zoho-oauth.azurewebsites.net/
- **API Proxy**: https://well-zoho-oauth.azurewebsites.net/api/*
- **OAuth Token**: https://well-zoho-oauth.azurewebsites.net/oauth/token
- **Manifest**: https://well-zoho-oauth.azurewebsites.net/manifest.xml
- **Health Check**: https://well-zoho-oauth.azurewebsites.net/health

### Backend Services (Protected - Access via Proxy Only)
- Container Apps API: https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io
- Direct access requires API key authentication

## 📋 API Endpoints

### OAuth Proxy Service Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| GET | `/` | Service documentation | None |
| GET | `/health` | Service health with proxy status | None |
| GET/POST | `/oauth/token` | Get/refresh Zoho access token | None |
| ALL | `/api/*` | Proxy to Container Apps API | Automatic |
| GET | `/proxy/health` | Backend API health check | None |
| GET | `/manifest.xml` | Outlook Add-in manifest | None |

### Container Apps API Endpoints (via Proxy)

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| POST | `/api/intake/email` | Process email and create Zoho records | Handled by proxy |
| GET | `/api/test/kevin-sullivan` | Test pipeline with sample data | Handled by proxy |
| GET | `/api/health` | Backend health check | Handled by proxy |

### Request Format

```json
POST https://well-zoho-oauth.azurewebsites.net/api/intake/email
{
    "subject": "Email subject",
    "body": "Email body content",
    "sender_email": "sender@example.com",
    "sender_name": "Sender Name",
    "attachments": [
        {
            "filename": "resume.pdf",
            "content_base64": "base64_encoded_content",
            "content_type": "application/pdf"
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
        "attachments_uploaded": 1,
        "processing_time": 2.3
    }
}
```

## 🔧 Configuration

### Environment Variables (.env.local)

```env
# API Configuration
API_KEY=your-secure-api-key-here  # Handled by proxy automatically
USE_LANGGRAPH=true  # CRITICAL: Enables LangGraph workflow

# Azure Services
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
AZURE_CONTAINER_NAME=email-attachments
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require

# AI Services
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-5-mini  # DO NOT CHANGE
FIRECRAWL_API_KEY=fc-...

# Zoho Integration
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net
ZOHO_CLIENT_ID=1000.YOUR_CLIENT_ID
ZOHO_CLIENT_SECRET=your_client_secret
ZOHO_REFRESH_TOKEN=1000.refresh_token_here
ZOHO_DEFAULT_OWNER_EMAIL=owner@example.com

# Proxy Configuration (Optional)
MAIN_API_URL=https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io
PROXY_TIMEOUT=30
PROXY_RATE_LIMIT=100
```

## 🚀 Deployment

### Deploy OAuth Proxy Service

```bash
cd oauth_service
./deploy.sh  # Automated deployment script

# Or manually:
az webapp deployment source config-zip \
  --resource-group TheWell-Infra-East \
  --name well-zoho-oauth \
  --src oauth_proxy_deploy.zip
```

### Deploy Container Apps API

```bash
# Build and push Docker image
docker build -t wellintakeregistry.azurecr.io/well-intake-api:latest .
az acr login --name wellintakeregistry
docker push wellintakeregistry.azurecr.io/well-intake-api:latest

# Update Container App
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeregistry.azurecr.io/well-intake-api:latest
```

### Deploy Outlook Add-in

1. Access Microsoft 365 Admin Center
2. Navigate to Settings → Integrated Apps
3. Choose "Upload custom app"
4. Select "Office Add-in" as app type
5. Enter manifest URL: `https://well-zoho-oauth.azurewebsites.net/manifest.xml`
6. Complete deployment wizard

## 🧪 Testing

### Test OAuth Service
```bash
# Health check
curl https://well-zoho-oauth.azurewebsites.net/health

# OAuth token
curl https://well-zoho-oauth.azurewebsites.net/oauth/token

# Test proxy
curl https://well-zoho-oauth.azurewebsites.net/api/test/kevin-sullivan
```

### Test Complete Pipeline
```bash
cd oauth_service
python test_proxy.py  # Comprehensive proxy tests

cd ..
python test_langgraph.py  # Test LangGraph workflow
python test_api.py  # Test API endpoints
```

## 📊 Performance Metrics

- **Email Processing Time**: 2-3 seconds average
- **Token Refresh**: < 500ms (cached for 55 minutes)
- **Proxy Overhead**: < 50ms
- **Rate Limit**: 100 requests/minute per IP
- **Circuit Breaker**: Opens after 5 failures, 60s timeout
- **Attachment Limit**: 25MB per file
- **Concurrent Workers**: 2 (configurable)

## 🔍 Monitoring & Logs

### View Proxy Service Logs
```bash
az webapp log tail \
  --resource-group TheWell-Infra-East \
  --name well-zoho-oauth
```

### View Container Apps Logs
```bash
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --follow
```

## 🛡️ Security Features

1. **API Key Management**: Centralized in proxy service, never exposed to client
2. **OAuth Token Caching**: Reduces API calls and improves security
3. **Rate Limiting**: Prevents abuse with configurable limits
4. **Circuit Breaker**: Automatic failure detection and recovery
5. **Request Validation**: Input sanitization and validation
6. **CORS Support**: Controlled cross-origin access
7. **Azure Key Vault**: Integration ready for secret management
8. **SAS Token Auth**: Secure blob storage access

## 📈 Business Logic

### Deal Name Format
`"[Job Title] ([Location]) - [Firm Name]"`
- Missing values replaced with "Unknown"
- Applied consistently across all records

### Source Determination
1. Has referrer → "Referral" (with Source_Detail)
2. Contains "TWAV" → "Reverse Recruiting"
3. Has Calendly link → "Website Inbound"
4. Default → "Email Inbound"

### Deduplication Logic
- Checks existing accounts by email domain
- Matches contacts by email address
- Links new deals to existing accounts/contacts
- Prevents duplicate record creation

## 🚨 Troubleshooting

### Common Issues

**Issue**: 403 Forbidden on API calls
- **Solution**: Ensure proxy service is running and API_KEY is in .env.local

**Issue**: "temperature must be 1" error
- **Solution**: Always use temperature=1 for GPT-5-mini calls

**Issue**: Slow OAuth token refresh
- **Solution**: Check token cache, should be instant for cached tokens

**Issue**: Circuit breaker open
- **Solution**: Check backend health, wait 60s for automatic recovery

### Rollback Procedure
```bash
# List deployments
az webapp deployment list \
  --resource-group TheWell-Infra-East \
  --name well-zoho-oauth

# Rollback to previous version
az webapp deployment rollback \
  --resource-group TheWell-Infra-East \
  --name well-zoho-oauth
```

## 📝 Changelog

### v3.0.0 (August 26, 2025)
- ✨ Added OAuth Reverse Proxy Service for centralized authentication
- 🔐 Implemented automatic API key injection
- ⚡ Added rate limiting and circuit breaker protection
- 🔄 Enhanced Zoho OAuth token management with caching
- 📊 Improved monitoring and logging capabilities

### v2.0.0 (August 26, 2025)  
- 🚀 Migrated from CrewAI to LangGraph implementation
- ⚡ Reduced processing time from 45s to 2-3s
- 🐛 Fixed ChromaDB/SQLite dependency issues
- 🎯 Improved extraction accuracy with structured output

### v1.0.0 (August 2025)
- 🎉 Initial release with CrewAI implementation
- 📧 Outlook Add-in integration
- 🔗 Zoho CRM integration
- 📎 Azure Blob Storage for attachments

## 📞 Support

For issues or questions:
- Check the [Troubleshooting](#-troubleshooting) section
- Review logs in Azure Portal
- Contact the development team

## 📜 License

Proprietary - The Well Recruiting © 2025