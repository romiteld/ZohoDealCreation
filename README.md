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
- **🚀 CI/CD Pipeline**: GitHub Actions for automatic version increment and cache busting
- **💾 Redis Caching**: Intelligent caching with automatic invalidation on deployment
- **📊 Manifest Analytics**: Track version adoption, cache performance, and error rates
- **🌐 CDN Management**: Azure Front Door integration with cache purging capabilities
- **🔀 Proxy Routing**: Flask-based routing with /api/* and /cdn/* endpoint support

## 🏗️ Architecture Overview

> **Latest Updates (September 2025)**: 
> - Migrated from CrewAI to **LangGraph** for improved reliability and performance
> - Added **OAuth Reverse Proxy Service** for centralized authentication and security
> - Implemented **Redis caching** with intelligent pattern recognition
> - Added **Azure Service Bus** for batch email processing
> - Enhanced with **Azure AI Search**, **SignalR**, and **Application Insights**
> - System runs on Azure Container Apps with Docker-based deployment

### System Architecture with Cache Busting

```
┌─────────────────────────────────────────────────────┐
│                  GitHub Repository                   │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │         GitHub Actions Workflow              │  │
│  │                                              │  │
│  │  Triggers on:                                │  │
│  │  • manifest.xml changes                      │  │
│  │  • Add-in file changes (*.html, *.js)       │  │
│  │                                              │  │
│  │  Actions:                                    │  │
│  │  1. Detect changes & increment version       │  │
│  │  2. Update manifest.xml with new version     │  │
│  │  3. Clear Redis cache via API                 │  │
│  │  4. Build & push Docker image                 │  │
│  │  5. Deploy to Azure Container Apps           │  │
│  └──────────────────┬───────────────────────────┘  │
└─────────────────────┼───────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│         Microsoft 365 Admin Center           │
│         (Integrated Apps Portal)             │
│                                               │
│  • Manifest Version: auto-incremented        │
│  • Cache-busted URLs with ?v=x.x.x.x        │
│  • Automatic deployment on changes           │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────┐
│  Outlook Email   │
│   (Add-in UI)    │
└────────┬─────────┘
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
│  • Manifest serving & analytics              │
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
│                                               │
│  ┌──────────────────────────────────────┐    │
│  │     Redis Cache Layer                 │    │
│  │                                       │    │
│  │  • Manifest caching                   │    │
│  │  • Add-in file caching               │    │
│  │  • Email pattern caching             │    │
│  │  • Auto-invalidation on deploy       │    │
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

### CI/CD Pipeline Flow

```
Developer Push → GitHub Actions → Version Increment → Cache Clear → Docker Build → Azure Deploy
     │                │                  │                │              │              │
     └─> Changes  ──> Detect ──────> Update ──────> Redis API ────> Registry ────> Container Apps
         Detection     Type           Manifest        Invalidate       Push           Update
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
    
  - `wellintakeacr0903` - Azure Container Registry
    - Docker image repository
    - Version control for deployments
    
  - `well-intake-db-0903` - PostgreSQL Flexible Server
    - PostgreSQL 15 with pgvector extension
    - 400K token context window support
    - Vector similarity search capabilities
    
  - `wellintakestorage0903` - Azure Blob Storage
    - Email attachment storage
    - Private container with SAS token auth
    
  - `wellintakecache0903` - Azure Cache for Redis
    - Redis 6.0 with 256MB Basic C0 tier
    - Intelligent caching with pattern recognition
    - Email classification and template detection
    
  - `wellintakebus0903` - Azure Service Bus
    - Batch processing queue management
    - Multi-email context processing
    - Message routing and retry logic
    
  - `wellintakesignalr0903` - Azure SignalR Service
    - Real-time streaming communication
    - WebSocket connections for live updates
    
  - `wellintakesearch0903` - Azure AI Search
    - Semantic pattern learning
    - Company template storage
    - Vector-based similarity matching

## 🚀 Production URLs

### Primary Service (Use These)
- **Service Root**: https://well-zoho-oauth.azurewebsites.net/
- **API Proxy**: https://well-zoho-oauth.azurewebsites.net/api/*
- **OAuth Token**: https://well-zoho-oauth.azurewebsites.net/oauth/token
- **Manifest**: https://well-zoho-oauth.azurewebsites.net/manifest.xml
- **Health Check**: https://well-zoho-oauth.azurewebsites.net/health

### Backend Services (Protected - Access via Proxy Only)
- Container Apps API: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io
- Direct access requires API key authentication

## 📋 API Endpoints

### OAuth Proxy Service Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| GET | `/` | Service documentation | None |
| GET | `/health` | Service health with proxy status | None |
| GET/POST | `/oauth/token` | Get/refresh Zoho access token | None |
| ALL | `/api/*` | Proxy to Container Apps API | Automatic |
| ALL | `/cdn/*` | CDN management (alias for /api/cdn/*) | Automatic |
| GET | `/proxy/health` | Backend API health check | None |
| GET | `/manifest.xml` | Outlook Add-in manifest | None |

### Container Apps API Endpoints (via Proxy)

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| POST | `/api/intake/email` | Process email and create Zoho records | Handled by proxy |
| POST | `/api/batch/submit` | Submit batch of emails for processing | Handled by proxy |
| GET | `/api/batch/{batch_id}/status` | Check batch processing status | Handled by proxy |
| GET | `/api/test/kevin-sullivan` | Test pipeline with sample data | Handled by proxy |
| GET | `/api/health` | Backend health check | Handled by proxy |
| GET | `/api/cache/status` | Redis cache metrics and performance | Handled by proxy |
| POST | `/api/cache/invalidate` | Clear cache entries | Handled by proxy |
| POST | `/api/cache/warmup` | Pre-load common email patterns | Handled by proxy |
| GET | `/api/cdn/status` | CDN configuration and metrics | Handled by proxy |
| POST | `/api/cdn/purge` | Purge CDN cache for specific paths | Handled by proxy |

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

## 🚀 CI/CD with GitHub Actions

### Manifest Cache Busting Workflow

The system includes an automated CI/CD pipeline that handles manifest versioning and cache invalidation:

#### Features
- **Automatic Version Increment**: Detects changes and increments version based on change type
  - Major: Breaking changes (ID, requirements, provider changes)
  - Minor: New features (permissions, extension points)
  - Patch: Bug fixes and minor updates
  - Build: Auto-increment for all other changes

- **Smart Change Detection**: Monitors specific files
  - `addin/manifest.xml` - Outlook add-in manifest
  - `addin/*.html` - Task pane and command UI files
  - `addin/*.js` - JavaScript functionality
  - `addin/*.css` - Styling changes

- **Cache Invalidation**: Automatically clears Redis cache on deployment
  - Manifest patterns: `manifest:*`
  - Add-in patterns: `addin:*, taskpane:*`
  - Triggers cache warmup for frequently accessed resources

- **Zero-Downtime Deployment**: Blue-green deployment to Azure Container Apps
  - Builds multi-platform Docker images
  - Tags with version and commit SHA
  - Automatic rollback on failure

#### GitHub Secrets Required

Configure these in your repository settings (Settings → Secrets → Actions):

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `AZURE_CLIENT_ID` | Service Principal Client ID | `fff7bffd-8f53-4a8c-a064-...` |
| `AZURE_CLIENT_SECRET` | Service Principal Secret | `a~a8Q~jaSezoO3.USqu5...` |
| `AZURE_TENANT_ID` | Azure AD Tenant ID | `29ee1479-b5f7-48c5-b665-...` |
| `AZURE_SUBSCRIPTION_ID` | Azure Subscription ID | `3fee2ac0-3a70-4343-a8b2-...` |
| `API_KEY` | API Key for cache endpoints | `e49d2dbcfa4547f5bdc371c5...` |

#### Workflow Triggers

The workflow automatically runs when:
1. **Push to main branch** with changes to:
   - Add-in manifest (`addin/manifest.xml`)
   - Add-in HTML files (`addin/*.html`)
   - Add-in JavaScript (`addin/*.js`)
   - Add-in CSS (`addin/*.css`)

2. **Manual dispatch** via GitHub Actions UI:
   - Force version increment (major/minor/patch)
   - Useful for testing or emergency deployments

#### Example Workflow Execution

```yaml
name: Manifest Cache-Bust & Deploy
on:
  push:
    paths:
      - 'addin/manifest.xml'
      - 'addin/*.html'
      - 'addin/*.js'
      
jobs:
  detect-changes:    # Analyzes what changed
  increment-version: # Updates manifest version
  clear-cache:       # Invalidates Redis cache
  build-and-deploy:  # Deploys to Azure
  verify-deployment: # Health check
  rollback:          # Auto-rollback on failure
```

### Cache Strategy

The system implements a multi-layer caching strategy:

1. **Browser Cache Busting**: Version parameters (`?v=x.x.x.x`) on all resource URLs
2. **Redis Cache**: Stores manifest and add-in files with TTL
3. **CDN Cache**: Azure CDN with origin pull from Redis
4. **Analytics Tracking**: Monitors cache hit rates and performance

### Monitoring & Analytics

Track deployment and cache performance through:

- **GitHub Actions**: Workflow run history and logs
- **Application Insights**: Cache metrics and performance
- **Redis Monitor**: Hit/miss rates, memory usage
- **Manifest Analytics**: Version adoption, error rates

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

# Redis Configuration
AZURE_REDIS_CONNECTION_STRING=rediss://:access_key@wellintakecache0903.redis.cache.windows.net:6380

# Azure Service Bus
AZURE_SERVICE_BUS_CONNECTION_STRING=Endpoint=sb://wellintakebus0903.servicebus.windows.net/;...

# Azure SignalR
AZURE_SIGNALR_CONNECTION_STRING=Endpoint=https://wellintakesignalr0903.service.signalr.net;...

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://wellintakesearch0903.search.windows.net
AZURE_SEARCH_KEY=your_search_admin_key

# Proxy Configuration (Optional)
MAIN_API_URL=https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io
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
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:latest .
az acr login --name wellintakeacr0903
docker push wellintakeacr0903.azurecr.io/well-intake-api:latest

# Update Container App
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:latest
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

- **Email Processing Time**: 2-3 seconds average (new requests), <100ms (cached)
- **Cache Hit Rate**: 66% in production scenarios
- **Token Refresh**: < 500ms (cached for 55 minutes)
- **Proxy Overhead**: < 50ms
- **Rate Limit**: 100 requests/minute per IP
- **Circuit Breaker**: Opens after 5 failures, 60s timeout
- **Attachment Limit**: 25MB per file
- **Concurrent Workers**: 2-10 (auto-scaling)
- **Batch Processing**: 50 emails per context window
- **Redis Response Time**: <1ms for cache operations

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

# Container App rollback
az containerapp revision list \
  --name well-intake-api \
  --resource-group TheWell-Infra-East

az containerapp ingress traffic set \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --revision-weight previous-revision=100 latest=0
```

## 📝 Changelog

### v3.1.0 (September 9, 2025)
- ✅ **Redis Cache System Operational** - Fixed connection issues, 90% performance improvement
- 🔧 **Azure Service Configuration** - Updated all service names to actual deployed resources
- 🚀 **Infrastructure Optimization** - Service Bus, SignalR, AI Search fully integrated
- 📊 **Cache Analytics** - 66% hit rate with intelligent email pattern recognition
- 🔐 **Security Enhancements** - Consolidated API key management and validation

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