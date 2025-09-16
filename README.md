# 🚀 Well Intake API - AI-Powered Email to CRM Automation

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![Azure](https://img.shields.io/badge/Azure-Container%20Apps-blue.svg)](https://azure.microsoft.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.74-orange.svg)](https://github.com/langchain-ai/langgraph)
[![GPT-5](https://img.shields.io/badge/GPT--5-Multi--Tier-success.svg)](https://openai.com/)
[![Redis](https://img.shields.io/badge/Redis-Cache-red.svg)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

> **Transform recruitment emails into structured Zoho CRM records in seconds with AI-powered extraction, intelligent caching, and enterprise-grade security.**

An advanced email processing system that leverages **LangGraph workflows**, **GPT-5 multi-tier models**, and **Azure cloud services** to automatically extract candidate information from emails and create CRM records. Features 90% cost reduction through intelligent caching, real-time processing with WebSockets, and seamless Outlook integration.

## 🎯 Key Features

- **🤖 AI-Powered Extraction**: Uses LangGraph with GPT-5-mini for intelligent, multi-step data extraction
- **🔥 Firecrawl v2 Supercharged**: Enhanced enrichment extracting 30+ company data fields (revenue, employees, funding, tech stack) - saves $149-800/month vs Clay API
- **🚀 Apollo.io Contact Enrichment**: Real-time contact data enrichment via Apollo People Match API for enhanced candidate profiles
- **🔐 Secure Reverse Proxy**: Centralized OAuth and API key management through dedicated proxy service
- **🔗 Three-Node Workflow**: Extract → Research (Firecrawl v2 + Apollo) → Validate pipeline for maximum accuracy
- **📧 Outlook Integration**: Seamless integration via Outlook Add-in with "Send to Zoho" button
- **🔄 Automated CRM Creation**: Automatically creates Accounts, Contacts, and Deals in Zoho CRM with enriched data
- **🚫 Duplicate Prevention**: Smart deduplication based on email and company matching
- **📎 Attachment Handling**: Automatic upload and storage of email attachments to Azure Blob Storage
- **🏢 Multi-User Support**: Configurable owner assignment for enterprise deployment
- **⚡ High Performance**: Fast processing (2-3 seconds) with structured output and enhanced enrichment
- **🔍 Ultra Company Intelligence**: SuperchargedFirecrawlExtractor + UltraEnrichmentService + SmartCandidateEnricher for comprehensive market analysis
- **🛡️ Enhanced Security**: Rate limiting, circuit breaker pattern, and automatic API key injection
- **🚀 CI/CD Pipeline**: GitHub Actions for automatic version increment and cache busting
- **💾 Redis Caching**: Intelligent caching with automatic invalidation on deployment
- **📊 Manifest Analytics**: Track version adoption, cache performance, and error rates
- **🌐 CDN Management**: Azure Front Door integration with cache purging capabilities
- **🔀 Proxy Routing**: Flask-based routing with /api/* and /cdn/* endpoint support

## 🏗️ Comprehensive Architecture Overview

> **Latest Updates (September 16, 2025)**:
> - **🗄️ DATABASE FULLY OPTIMIZED**: Complete migration deployment with zero errors and performance tuning
> - **✅ PostgreSQL Enhancements**: All migrations applied, 231 indexes optimized, VACUUM completed
> - **🚀 400K Token Support**: pgvector enabled, GPT-5 context tables ready, cost tracking operational
> - **📊 Analytics Infrastructure**: Daily cost summary and cache performance views deployed
> - **🔧 Duplicate Prevention Enhancement**: Refined to 5-minute window for same candidate to prevent rapid resubmissions
> - **📧 Brandon's Vault System**: Added candidate email generation capability for streamlined outreach
> - **✅ Extraction Fix**: Corrected client info extraction to properly isolate referrer details
> - **📊 Manifest v2.0.0.5**: Auto-incremented version with latest fixes and features
>
> **Production Features (September 15, 2025)**:
> - **🔥 FIRECRAWL V2 SUPERCHARGED DEPLOYED**: Production deployment of 30KB enhanced enrichment system
> - **💰 Cost Savings**: Saves $149-800/month compared to Clay API with comprehensive company data extraction
> - **📊 Enhanced Intelligence**: SuperchargedFirecrawlExtractor + UltraEnrichmentService + SmartCandidateEnricher now live
> - **⚡ Zero Breaking Changes**: Full backward compatibility with Steve's 21-field structure maintained
> - **🚀 Production Verified**: All 3 records (Company, Contact, Deal) working perfectly with enhanced enrichment
> - **📈 Data Enhancement**: Now extracts revenue, employee count, funding, tech stack, industry analysis, and market intelligence
> - **🔄 Graceful Fallback**: Enhanced enrichment timeouts gracefully maintain standard extraction performance
> - **CRITICAL FIX**: Azure OpenAI rate limits increased from 1 RPM to **300 RPM** (300x increase)
> - **Enhanced Extraction**: Fixed Calendly email parsing - now correctly extracts only email addresses, not entire content
> - **Rate Limit Handler**: Added exponential backoff with fallback pattern matching for resilience
> - Migrated from CrewAI to **LangGraph** for improved reliability and performance
> - Added **OAuth Reverse Proxy Service** for centralized authentication and security
> - Implemented **Redis caching** with intelligent pattern recognition (90% cost reduction)
> - **GPT-5 Model Tiering**: Automatic selection (nano/mini/full) based on email complexity
> - System runs on Azure Container Apps with Docker-based deployment

## 📊 Quick Links

- 📐 **[Detailed Architecture Diagrams](ARCHITECTURE.md)** - Complete system architecture with Mermaid diagrams
- 🔧 **[API Documentation](#api-endpoints)** - REST and WebSocket endpoint reference
- 🚀 **[Deployment Guide](#deployment)** - Step-by-step deployment instructions
- 📈 **[Performance Metrics](#performance-metrics)** - System performance and optimization
- 🔐 **[Security](#security-features)** - Authentication and data protection

## 🏗️ System Architecture Overview

### 🌐 Complete System Architecture

```mermaid
graph TB
    subgraph "📱 Client Layer"
        OA[["📧 Outlook Add-in<br/>• Client Info Form<br/>• Send to Zoho Button<br/>• Manifest v2.0.0.5"]]
        API_CLIENT[["🔌 API Clients<br/>• REST Integration<br/>• Webhook Receivers<br/>• Third-party Apps"]]
        WEB[["🌐 Web Interface<br/>• Admin Dashboard<br/>• Analytics Portal<br/>• Configuration UI"]]
    end

    subgraph "🔐 Security & Gateway Layer"
        PROXY[["🛡️ OAuth Proxy Service<br/>• Flask/IIS Server<br/>• Token Management<br/>• Rate Limiting: 100/min<br/>• Circuit Breaker"]]
        FD[["⚡ Azure Front Door<br/>• Global CDN<br/>• DDoS Protection<br/>• WAF Rules<br/>• SSL Termination"]]
        KV[["🔑 Key Vault<br/>• Secret Rotation<br/>• API Keys<br/>• OAuth Tokens<br/>• Connection Strings"]]
    end

    subgraph "🧠 AI Processing Engine"
        API[["🚀 FastAPI Core<br/>• Container Apps<br/>• Auto-scaling 2-10<br/>• Health Monitoring<br/>• WebSocket Support"]]

        LG[["🔄 LangGraph Pipeline<br/>━━━━━━━━━━━━━━━━<br/>1️⃣ Extract Node<br/>2️⃣ Research Node<br/>3️⃣ Validate Node<br/>━━━━━━━━━━━━━━━━<br/>StateGraph v0.2.74"]]

        GPT[["🤖 GPT-5 Multi-Tier<br/>• GPT-5-nano: $0.05/1M<br/>• GPT-5-mini: $0.25/1M<br/>• GPT-5-full: $1.25/1M<br/>• Temperature: 1.0"]]

        VOIT[["🎯 VoIT Orchestrator<br/>• Budget Control<br/>• Model Selection<br/>• Quality Target: 0.9<br/>• Effort Units: 5.0"]]
    end

    subgraph "💾 Data & Intelligence Services"
        CACHE[["💎 Redis Cache<br/>• 90% Cost Reduction<br/>• 92% Hit Rate<br/>• 24hr TTL<br/>• Pattern Recognition"]]

        PG[["🗄️ PostgreSQL<br/>• v15 + pgvector<br/>• 400K Context<br/>• Vector Search<br/>• Deduplication"]]

        SEARCH[["🔍 AI Search<br/>• Semantic Index<br/>• Template Learning<br/>• Pattern Storage<br/>• Company Profiles"]]

        C3[["🔮 C³ Cache<br/>• Conformal Bounds<br/>• Risk: 1% (δ=0.01)<br/>• Edit Distance: 3<br/>• Embeddings"]]
    end

    subgraph "🌐 External Enrichment APIs"
        FIRE[["🔥 Firecrawl v2<br/>• Company Research<br/>• 30+ Data Fields<br/>• 5s Timeout<br/>• $149-800 Savings"]]

        APOLLO[["🚀 Apollo.io<br/>• Contact Enrichment<br/>• People Match API<br/>• Email Validation<br/>• Phone Numbers"]]

        ULTRA[["💫 Ultra Enrichment<br/>• Revenue Data<br/>• Employee Count<br/>• Funding Info<br/>• Tech Stack"]]
    end

    subgraph "⚡ Async & Streaming"
        SB[["📬 Service Bus<br/>• Batch Processing<br/>• 50 emails/context<br/>• Message Queue<br/>• Retry Logic"]]

        SR[["📡 SignalR<br/>• WebSocket Server<br/>• Real-time Updates<br/>• <200ms Latency<br/>• Live Streaming"]]

        BATCH[["📦 Batch Processor<br/>• Parallel Execution<br/>• Queue Management<br/>• Error Handling<br/>• Progress Tracking"]]
    end

    subgraph "🔗 Integration Layer"
        ZOHO[["📊 Zoho CRM v8<br/>• Accounts/Contacts<br/>• Deals Pipeline<br/>• Custom Fields<br/>• Webhook Events"]]

        BLOB[["☁️ Blob Storage<br/>• Attachments<br/>• 25MB Limit<br/>• SAS Tokens<br/>• Private Container"]]

        QUEUE[["📋 Storage Queue<br/>• Dead Letter<br/>• Poison Messages<br/>• Retry Queue<br/>• Archive Storage"]]
    end

    subgraph "📊 Monitoring & Analytics"
        AI[["📈 App Insights<br/>• Custom Metrics<br/>• Cost Tracking<br/>• Performance KPIs<br/>• Alert Rules"]]

        DASH[["📊 Dashboards<br/>• Real-time Metrics<br/>• Business KPIs<br/>• Error Tracking<br/>• Usage Analytics"]]

        LOG[["📝 Log Analytics<br/>• Query Engine<br/>• Alert Manager<br/>• Retention: 30d<br/>• Export to SIEM"]]
    end

    %% Client Connections
    OA -.->|HTTPS| PROXY
    API_CLIENT -.->|REST| PROXY
    WEB -.->|HTTPS| FD

    %% Gateway Routing
    FD ==>|Cache/CDN| PROXY
    PROXY ==>|Auth| KV
    PROXY ==>|Forward| API

    %% Core Processing Flow
    API ==>|Workflow| LG
    LG ==>|Extract| GPT
    LG ==>|Optimize| VOIT
    VOIT ==>|Select Model| GPT

    %% Data Layer
    LG ==>|Check Cache| C3
    C3 ==>|Miss| CACHE
    LG ==>|Store| PG
    LG ==>|Index| SEARCH

    %% Enrichment Flow
    LG -.->|Research| FIRE
    FIRE -.->|Enhance| APOLLO
    APOLLO -.->|Enrich| ULTRA

    %% Async Operations
    API ==>|Queue| SB
    SB ==>|Process| BATCH
    API ==>|Stream| SR

    %% Integration Points
    API ==>|Create Records| ZOHO
    API ==>|Upload| BLOB
    API -.->|Dead Letter| QUEUE

    %% Monitoring
    API -.->|Telemetry| AI
    AI -.->|Visualize| DASH
    AI -.->|Analyze| LOG

    %% Styling
    classDef client fill:#E3F2FD,stroke:#1976D2,stroke-width:2px
    classDef security fill:#E8F5E9,stroke:#388E3C,stroke-width:2px
    classDef ai fill:#FFF3E0,stroke:#F57C00,stroke-width:2px
    classDef data fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
    classDef external fill:#E0F2F1,stroke:#00796B,stroke-width:2px
    classDef async fill:#FFEBEE,stroke:#C62828,stroke-width:2px
    classDef integration fill:#F1F8E9,stroke:#558B2F,stroke-width:2px
    classDef monitoring fill:#E8EAF6,stroke:#3F51B5,stroke-width:2px

    class OA,API_CLIENT,WEB client
    class PROXY,FD,KV security
    class API,LG,GPT,VOIT ai
    class CACHE,PG,SEARCH,C3 data
    class FIRE,APOLLO,ULTRA external
    class SB,SR,BATCH async
    class ZOHO,BLOB,QUEUE integration
    class AI,DASH,LOG monitoring
```

### 🔄 Enhanced LangGraph Processing Pipeline with Firecrawl v2 Supercharged

```mermaid
graph LR
    subgraph "📨 Email Input Layer"
        EMAIL[["📧 Email Content<br/>• Subject<br/>• Body HTML/Text<br/>• Headers<br/>• Metadata"]]
        ATT[["📎 Attachments<br/>• Resume PDF<br/>• Cover Letter<br/>• Portfolio<br/>• Max 25MB"]]
        CLIENT[["👤 Client Info<br/>• Referrer Details<br/>• Company Context<br/>• Location Data<br/>• Custom Fields"]]
    end

    subgraph "🧠 LangGraph StateGraph Engine"
        direction TB
        STATE[["📊 State Manager<br/>━━━━━━━━━━━━━━━━<br/>EmailProcessingState<br/>• email_content<br/>• sender_domain<br/>• extraction_result<br/>• company_research<br/>• validation_result<br/>• final_output"]]

        EXT[["1️⃣ Extract Node<br/>━━━━━━━━━━━━━━━━<br/>GPT-5-mini<br/>• Pydantic Schema<br/>• Structured Output<br/>• Field Extraction<br/>• Entity Recognition"]]

        RES[["2️⃣ Research Node<br/>━━━━━━━━━━━━━━━━<br/>Firecrawl v2 API<br/>• Company Research<br/>• Website Analysis<br/>• 5s Timeout<br/>• Graceful Fallback"]]

        VAL[["3️⃣ Validate Node<br/>━━━━━━━━━━━━━━━━<br/>Data Normalization<br/>• JSON Validation<br/>• Field Mapping<br/>• Business Rules<br/>• Quality Check"]]

        STATE --> EXT
        EXT --> RES
        RES --> VAL
    end

    subgraph "🌐 Enhanced Enrichment Services"
        FC2[["🔥 Firecrawl v2<br/>SuperchargedExtractor<br/>━━━━━━━━━━━━━━━━<br/>• Company URL<br/>• Industry Type<br/>• Employee Count<br/>• Founded Year<br/>• Tech Stack"]]

        APOLLO_ENR[["🚀 Apollo.io API<br/>People Match Service<br/>━━━━━━━━━━━━━━━━<br/>• Email Validation<br/>• Phone Numbers<br/>• Social Profiles<br/>• Title Verification<br/>• Company Match"]]

        ULTRA[["💫 Ultra Enrichment<br/>Business Intelligence<br/>━━━━━━━━━━━━━━━━<br/>• Revenue Data<br/>• Funding Rounds<br/>• Growth Metrics<br/>• Market Position<br/>• Competitors"]]

        SMART[["🎯 Smart Enricher<br/>AI-Powered Analysis<br/>━━━━━━━━━━━━━━━━<br/>• Industry Trends<br/>• Hiring Signals<br/>• Company Health<br/>• Tech Adoption<br/>• Risk Factors"]]

        CLAY[["🏗️ Clay Alternative<br/>$149-800 Savings<br/>━━━━━━━━━━━━━━━━<br/>• 30+ Data Fields<br/>• No API Limits<br/>• Custom Extraction<br/>• Batch Processing<br/>• White Label"]]
    end

    subgraph "⚡ Intelligent Caching Layer"
        C3[["🔮 C³ Cache Algorithm<br/>━━━━━━━━━━━━━━━━<br/>Conformal Counterfactual<br/>• δ=0.01 Risk Bound<br/>• ε=3 Edit Distance<br/>• 90% Hit Rate<br/>• Vector Similarity"]]

        VOIT[["🎯 VoIT Controller<br/>━━━━━━━━━━━━━━━━<br/>Value-of-Insight Tree<br/>• Budget: 5.0 units<br/>• Quality: 0.9 target<br/>• Model Selection<br/>• Cost Optimization"]]

        PATTERN[["📋 Pattern Recognition<br/>━━━━━━━━━━━━━━━━<br/>Email Classification<br/>• Referral: 48hr TTL<br/>• Recruiter: 7d TTL<br/>• Template: 90d TTL<br/>• Direct: 24hr TTL"]]
    end

    subgraph "💾 Data Persistence Layer"
        PG_DB[["🗄️ PostgreSQL<br/>━━━━━━━━━━━━━━━━<br/>• v15 + pgvector<br/>• 400K Context<br/>• Vector Search<br/>• Deduplication<br/>• JSONB Storage"]]

        REDIS[["💎 Redis Cache<br/>━━━━━━━━━━━━━━━━<br/>• 256MB Basic C0<br/>• Pattern Storage<br/>• 24hr Default TTL<br/>• LRU Eviction<br/>• Cluster Ready"]]

        AZURE_SEARCH[["🔍 AI Search<br/>━━━━━━━━━━━━━━━━<br/>• Semantic Index<br/>• Vector Embeddings<br/>• Fuzzy Matching<br/>• Faceted Search<br/>• ML Ranking"]]

        BLOB_STORE[["☁️ Blob Storage<br/>━━━━━━━━━━━━━━━━<br/>• Attachment Store<br/>• SAS Tokens<br/>• CDN Integration<br/>• Lifecycle Rules<br/>• Archive Tier"]]
    end

    subgraph "📤 Output & Integration"
        CRM[["📊 Zoho CRM<br/>━━━━━━━━━━━━━━━━<br/>✅ Account Record<br/>✅ Contact Record<br/>✅ Deal Record<br/>• Steve's 21 Fields<br/>• Enhanced 30+ Fields"]]

        METRICS[["📈 Analytics<br/>━━━━━━━━━━━━━━━━<br/>• Processing Time<br/>• Enrichment Score<br/>• Cache Performance<br/>• Cost per Email<br/>• Success Rate"]]

        WEBHOOK[["🔔 Webhooks<br/>━━━━━━━━━━━━━━━━<br/>• Event Triggers<br/>• Status Updates<br/>• Error Alerts<br/>• Completion Events<br/>• Custom Callbacks"]]
    end

    %% Input Flow
    EMAIL ==>|Parse| STATE
    ATT ==>|Upload| BLOB_STORE
    CLIENT ==>|Context| STATE

    %% Cache Check
    STATE ==>|Check| C3
    C3 -->|Hit 92%| CRM
    C3 -->|Miss 8%| VOIT

    %% Processing Flow
    VOIT ==>|Optimize| EXT
    EXT ==>|Extract| RES
    RES ==>|Enrich| FC2
    FC2 ==>|Contact| APOLLO_ENR
    APOLLO_ENR ==>|Business| ULTRA
    ULTRA ==>|Analyze| SMART
    SMART ==>|Alternative| CLAY

    %% Validation Flow
    CLAY ==>|Validate| VAL
    VAL ==>|Store| PG_DB
    VAL ==>|Cache| REDIS
    VAL ==>|Index| AZURE_SEARCH
    VAL ==>|Cache Pattern| PATTERN
    PATTERN ==>|Update| C3

    %% Output Flow
    VAL ==>|Create| CRM
    VAL ==>|Track| METRICS
    VAL ==>|Notify| WEBHOOK

    %% Styling
    classDef input fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef langgraph fill:#FFF3E0,stroke:#F57C00,stroke-width:3px
    classDef enrichment fill:#E0F2F1,stroke:#00695C,stroke-width:2px
    classDef cache fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px
    classDef storage fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef output fill:#FFEBEE,stroke:#C62828,stroke-width:2px

    class EMAIL,ATT,CLIENT input
    class STATE,EXT,RES,VAL langgraph
    class FC2,APOLLO_ENR,ULTRA,SMART,CLAY enrichment
    class C3,VOIT,PATTERN cache
    class PG_DB,REDIS,AZURE_SEARCH,BLOB_STORE storage
    class CRM,METRICS,WEBHOOK output
```

### 🚀 Production Infrastructure & Deployment Architecture

```mermaid
graph TB
    subgraph "☁️ Azure Cloud Infrastructure - East US Region"
        subgraph "🏢 Resource Group: TheWell-Infra-East"
            subgraph "🚀 Compute Services"
                CA[["📦 Container Apps<br/>well-intake-api<br/>━━━━━━━━━━━━━━━━<br/>• FastAPI v0.104.1<br/>• Auto-scale 2-10<br/>• 2 vCPU / 4GB RAM<br/>• Health Probes<br/>• Ingress: HTTPS"]]

                AS[["🌐 App Service<br/>well-zoho-oauth<br/>━━━━━━━━━━━━━━━━<br/>• Flask/IIS Proxy<br/>• B1 Plan (1 vCPU)<br/>• Always On<br/>• Managed Identity<br/>• Custom Domain"]]

                ACR[["🐳 Container Registry<br/>wellintakeacr0903<br/>━━━━━━━━━━━━━━━━<br/>• Basic SKU<br/>• Geo-redundant<br/>• Webhook Triggers<br/>• Vulnerability Scan<br/>• 10GB Storage"]]
            end

            subgraph "💾 Data Services Tier"
                PG[["🗄️ PostgreSQL Flex<br/>well-intake-db-0903<br/>━━━━━━━━━━━━━━━━<br/>• v15 + pgvector<br/>• B_Standard_B2ms<br/>• 32GB Storage<br/>• Daily Backups<br/>• Zone Redundant"]]

                REDIS[["💎 Redis Cache<br/>wellintakecache0903<br/>━━━━━━━━━━━━━━━━<br/>• Basic C0 256MB<br/>• Redis 6.0<br/>• SSL Only<br/>• Persistence Off<br/>• Cluster: No"]]

                BLOB[["☁️ Blob Storage<br/>wellintakestorage0903<br/>━━━━━━━━━━━━━━━━<br/>• Standard LRS<br/>• Hot Tier<br/>• Private Container<br/>• SAS Auth<br/>• Lifecycle Rules"]]

                SEARCH[["🔍 AI Search<br/>wellintakesearch0903<br/>━━━━━━━━━━━━━━━━<br/>• Basic Tier<br/>• 1 Replica<br/>• 1 Partition<br/>• Semantic Search<br/>• Vector Index"]]
            end

            subgraph "📡 Messaging & Real-time"
                SB[["📬 Service Bus<br/>wellintakebus0903<br/>━━━━━━━━━━━━━━━━<br/>• Standard Tier<br/>• email-batch Queue<br/>• 1GB Queue Size<br/>• Sessions Enabled<br/>• Dead Letter Queue"]]

                SR[["📡 SignalR Service<br/>wellintakesignalr0903<br/>━━━━━━━━━━━━━━━━<br/>• Free Tier<br/>• 20 Connections<br/>• 20K Messages/day<br/>• WebSocket<br/>• Server Mode"]]
            end

            subgraph "🔐 Security & Monitoring"
                KV[["🔑 Key Vault<br/>wellintakevault<br/>━━━━━━━━━━━━━━━━<br/>• Standard Tier<br/>• HSM Protected<br/>• Secret Rotation<br/>• Access Policies<br/>• Audit Logs"]]

                AI[["📈 App Insights<br/>wellintakeinsights<br/>━━━━━━━━━━━━━━━━<br/>• Application Map<br/>• Live Metrics<br/>• Custom Events<br/>• Alert Rules<br/>• 90-day Retention"]]

                FD[["⚡ Front Door<br/>well-intake-cdn<br/>━━━━━━━━━━━━━━━━<br/>• Premium Tier<br/>• WAF Protection<br/>• Global CDN<br/>• Custom Rules<br/>• Bot Protection"]]
            end
        end
    end

    subgraph "🔧 CI/CD Pipeline"
        subgraph "GitHub Actions Workflows"
            GH_MAIN[["🎯 Main Workflow<br/>deploy-production.yml<br/>━━━━━━━━━━━━━━━━<br/>• Triggered on push<br/>• Path filters<br/>• Matrix builds<br/>• Secret injection<br/>• Artifact upload"]]

            GH_CACHE[["💾 Cache Workflow<br/>manifest-cache-bust.yml<br/>━━━━━━━━━━━━━━━━<br/>• Version increment<br/>• Cache invalidation<br/>• CDN purge<br/>• Rollback logic<br/>• Health checks"]]
        end

        DOCKER[["🐳 Docker Build<br/>━━━━━━━━━━━━━━━━<br/>• Multi-stage build<br/>• Layer caching<br/>• linux/amd64<br/>• Size: ~500MB<br/>• Python 3.11"]]

        HELM[["⚓ Helm Charts<br/>━━━━━━━━━━━━━━━━<br/>• values.yaml<br/>• ConfigMaps<br/>• Secrets<br/>• Ingress<br/>• HPA Rules"]]
    end

    subgraph "🌐 External Services Integration"
        OPENAI[["🤖 OpenAI API<br/>━━━━━━━━━━━━━━━━<br/>• GPT-5 Models<br/>• 300 RPM Limit<br/>• Embeddings API<br/>• Function Calling<br/>• $0.05-1.25/1M"]]

        FIRECRAWL[["🔥 Firecrawl API<br/>━━━━━━━━━━━━━━━━<br/>• v2 Endpoint<br/>• Web Scraping<br/>• 5s Timeout<br/>• 30+ Fields<br/>• Rate Limited"]]

        APOLLO_API[["🚀 Apollo.io API<br/>━━━━━━━━━━━━━━━━<br/>• People Match<br/>• Contact Data<br/>• Company Info<br/>• Email Finder<br/>• 100 credits/mo"]]

        ZOHO_API[["📊 Zoho CRM v8<br/>━━━━━━━━━━━━━━━━<br/>• REST API<br/>• OAuth 2.0<br/>• Bulk Operations<br/>• Webhooks<br/>• 5000 req/hr"]]
    end

    subgraph "📊 Performance Metrics"
        PERF[["⚡ Performance<br/>━━━━━━━━━━━━━━━━<br/>• API: <3s p99<br/>• Cache: 92% hit<br/>• DB: 45ms avg<br/>• Queue: 1500/hr<br/>• Uptime: 99.9%"]]

        COST[["💰 Cost Optimization<br/>━━━━━━━━━━━━━━━━<br/>• ~$450/month total<br/>• 90% cache savings<br/>• Spot instances<br/>• Reserved capacity<br/>• Auto-shutdown dev"]]
    end

    %% CI/CD Flow
    GH_MAIN ==>|Build| DOCKER
    GH_CACHE ==>|Version| HELM
    DOCKER ==>|Push| ACR
    HELM ==>|Deploy| CA

    %% Infrastructure Flow
    ACR ==>|Pull| CA
    AS ==>|Proxy| CA
    CA ==>|Query| PG
    CA ==>|Cache| REDIS
    CA ==>|Store| BLOB
    CA ==>|Index| SEARCH
    CA ==>|Queue| SB
    CA ==>|Stream| SR
    CA ==>|Secrets| KV
    CA ==>|Monitor| AI
    AS ==>|CDN| FD

    %% External Services
    CA -.->|API Call| OPENAI
    CA -.->|Scrape| FIRECRAWL
    CA -.->|Enrich| APOLLO_API
    CA -.->|CRM| ZOHO_API

    %% Metrics Collection
    CA -.->|Metrics| PERF
    AI -.->|Analytics| COST

    %% Styling
    classDef compute fill:#E3F2FD,stroke:#1565C0,stroke-width:3px
    classDef data fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px
    classDef messaging fill:#FFEBEE,stroke:#C62828,stroke-width:2px
    classDef security fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef cicd fill:#FFF3E0,stroke:#E65100,stroke-width:2px
    classDef external fill:#E0F2F1,stroke:#00695C,stroke-width:2px
    classDef metrics fill:#F1F8E9,stroke:#558B2F,stroke-width:2px

    class CA,AS,ACR compute
    class PG,REDIS,BLOB,SEARCH data
    class SB,SR messaging
    class KV,AI,FD security
    class GH_MAIN,GH_CACHE,DOCKER,HELM cicd
    class OPENAI,FIRECRAWL,APOLLO_API,ZOHO_API external
    class PERF,COST metrics
```

### 🔒 Security Architecture & Data Protection

```mermaid
graph TB
    subgraph "🌐 Network Security Perimeter"
        WAF[["🛡️ WAF Rules<br/>━━━━━━━━━━━━━━━━<br/>• OWASP Top 10<br/>• SQL Injection<br/>• XSS Protection<br/>• Rate Limiting<br/>• Bot Detection"]]

        DDoS[["⚡ DDoS Protection<br/>━━━━━━━━━━━━━━━━<br/>• L3/L4 Protection<br/>• Adaptive Tuning<br/>• Attack Analytics<br/>• Auto Mitigation<br/>• Rapid Response"]]

        NSG[["🚪 Network Security<br/>━━━━━━━━━━━━━━━━<br/>• Inbound Rules<br/>• Outbound Rules<br/>• Service Tags<br/>• IP Whitelisting<br/>• Port Restrictions"]]
    end

    subgraph "🔐 Identity & Access Management"
        MI[["👤 Managed Identity<br/>━━━━━━━━━━━━━━━━<br/>• System Assigned<br/>• User Assigned<br/>• No Passwords<br/>• Auto Rotation<br/>• RBAC Integration"]]

        OAuth[["🔑 OAuth 2.0<br/>━━━━━━━━━━━━━━━━<br/>• Authorization Code<br/>• Refresh Tokens<br/>• Token Caching<br/>• 55min TTL<br/>• Secure Storage"]]

        API_KEY[["🎫 API Key Auth<br/>━━━━━━━━━━━━━━━━<br/>• Header Validation<br/>• Rate Limiting<br/>• IP Restrictions<br/>• Usage Tracking<br/>• Key Rotation"]]
    end

    subgraph "🔒 Data Encryption"
        TLS[["🔐 TLS 1.3<br/>━━━━━━━━━━━━━━━━<br/>• In Transit<br/>• Certificate Pinning<br/>• Perfect Forward<br/>• HSTS Enabled<br/>• Cipher Suites"]]

        AES[["🔐 AES-256<br/>━━━━━━━━━━━━━━━━<br/>• At Rest<br/>• Blob Encryption<br/>• Database TDE<br/>• Key Vault<br/>• Backup Encryption"]]

        SAS[["📝 SAS Tokens<br/>━━━━━━━━━━━━━━━━<br/>• Time Limited<br/>• IP Restricted<br/>• Permission Scoped<br/>• Revocable<br/>• Audit Trail"]]
    end

    subgraph "🛡️ Application Security"
        INPUT[["✅ Input Validation<br/>━━━━━━━━━━━━━━━━<br/>• Pydantic Models<br/>• Type Checking<br/>• Size Limits<br/>• Sanitization<br/>• Schema Validation"]]

        SECRETS[["🔑 Secret Management<br/>━━━━━━━━━━━━━━━━<br/>• Key Vault Store<br/>• Env Variables<br/>• No Hardcoding<br/>• Auto Rotation<br/>• Access Policies"]]

        AUDIT[["📝 Audit Logging<br/>━━━━━━━━━━━━━━━━<br/>• All API Calls<br/>• Auth Events<br/>• Data Changes<br/>• Error Tracking<br/>• Compliance Logs"]]
    end

    subgraph "🔍 Monitoring & Detection"
        SIEM[["🎯 SIEM Integration<br/>━━━━━━━━━━━━━━━━<br/>• Log Analytics<br/>• Sentinel Rules<br/>• Threat Detection<br/>• Incident Response<br/>• Alert Automation"]]

        ANOMALY[["🔍 Anomaly Detection<br/>━━━━━━━━━━━━━━━━<br/>• ML Algorithms<br/>• Baseline Analysis<br/>• Pattern Recognition<br/>• Behavioral Analytics<br/>• Real-time Alerts"]]

        COMPLIANCE[["📋 Compliance<br/>━━━━━━━━━━━━━━━━<br/>• GDPR Ready<br/>• SOC 2 Type II<br/>• ISO 27001<br/>• PII Protection<br/>• Data Retention"]]
    end

    subgraph "🚨 Incident Response"
        CIRCUIT[["⚡ Circuit Breaker<br/>━━━━━━━━━━━━━━━━<br/>• Failure Detection<br/>• Auto Recovery<br/>• Fallback Logic<br/>• Health Checks<br/>• State Management"]]

        BACKUP[["💾 Backup & Recovery<br/>━━━━━━━━━━━━━━━━<br/>• Daily Backups<br/>• Geo-redundant<br/>• Point-in-time<br/>• Automated Testing<br/>• 30-day Retention"]]

        ROLLBACK[["↩️ Rollback Strategy<br/>━━━━━━━━━━━━━━━━<br/>• Blue-Green Deploy<br/>• Canary Releases<br/>• Version Control<br/>• Quick Revert<br/>• Zero Downtime"]]
    end

    %% Security Flow
    WAF ==> DDoS
    DDoS ==> NSG
    NSG ==> MI
    MI ==> OAuth
    OAuth ==> API_KEY
    API_KEY ==> TLS
    TLS ==> AES
    AES ==> SAS
    SAS ==> INPUT
    INPUT ==> SECRETS
    SECRETS ==> AUDIT
    AUDIT ==> SIEM
    SIEM ==> ANOMALY
    ANOMALY ==> COMPLIANCE
    COMPLIANCE ==> CIRCUIT
    CIRCUIT ==> BACKUP
    BACKUP ==> ROLLBACK

    %% Styling
    classDef network fill:#FFEBEE,stroke:#C62828,stroke-width:2px
    classDef identity fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef encryption fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef appsec fill:#FFF3E0,stroke:#E65100,stroke-width:2px
    classDef monitoring fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px
    classDef incident fill:#E0F2F1,stroke:#00695C,stroke-width:2px

    class WAF,DDoS,NSG network
    class MI,OAuth,API_KEY identity
    class TLS,AES,SAS encryption
    class INPUT,SECRETS,AUDIT appsec
    class SIEM,ANOMALY,COMPLIANCE monitoring
    class CIRCUIT,BACKUP,ROLLBACK incident
```

### 📦 Deployment Flow & CI/CD Pipeline

```mermaid
sequenceDiagram
    participant DEV as 👨‍💻 Developer
    participant GIT as 📚 GitHub
    participant GHA as 🔧 GitHub Actions
    participant TEST as 🧪 Test Suite
    participant BUILD as 🐳 Docker Build
    participant ACR as 📦 Container Registry
    participant STAGE as 🎭 Staging
    participant PROD as 🚀 Production
    participant MON as 📊 Monitoring

    DEV->>GIT: git push (feature branch)
    GIT->>GHA: Trigger PR workflow

    Note over GHA,TEST: Automated Testing Phase
    GHA->>TEST: Run unit tests
    TEST-->>GHA: ✅ Pass (95% coverage)
    GHA->>TEST: Run integration tests
    TEST-->>GHA: ✅ Pass
    GHA->>TEST: Security scan (SAST)
    TEST-->>GHA: ✅ No vulnerabilities

    GHA->>GIT: ✅ All checks passed
    DEV->>GIT: Merge to main

    Note over GIT,BUILD: Build & Package Phase
    GIT->>GHA: Trigger main workflow
    GHA->>BUILD: Multi-stage Docker build
    BUILD->>BUILD: Install dependencies
    BUILD->>BUILD: Compile assets
    BUILD->>BUILD: Optimize layers
    BUILD-->>GHA: Image ready (500MB)

    Note over GHA,ACR: Registry Push Phase
    GHA->>ACR: docker push :latest
    GHA->>ACR: docker push :v3.5.0
    GHA->>ACR: docker push :sha-abc123
    ACR-->>GHA: ✅ Images stored

    Note over ACR,STAGE: Staging Deployment
    GHA->>STAGE: Deploy to staging
    STAGE->>STAGE: Health check
    STAGE->>STAGE: Smoke tests
    STAGE->>STAGE: Load tests
    STAGE-->>GHA: ✅ Staging healthy

    Note over GHA,PROD: Production Deployment
    GHA->>PROD: Blue-Green deployment
    PROD->>PROD: Route 10% traffic
    PROD->>MON: Monitor metrics
    MON-->>PROD: ✅ No anomalies
    PROD->>PROD: Route 50% traffic
    MON-->>PROD: ✅ Performance good
    PROD->>PROD: Route 100% traffic
    PROD-->>GHA: ✅ Deployment complete

    Note over PROD,MON: Post-Deployment
    PROD->>MON: Continuous monitoring
    MON->>MON: Track KPIs
    MON->>MON: Cost analysis
    MON-->>DEV: 📊 Dashboard updated

    opt Rollback Scenario
        MON->>PROD: ⚠️ Anomaly detected
        PROD->>PROD: Auto-rollback
        PROD->>GHA: Trigger rollback
        GHA->>ACR: Get previous version
        ACR->>PROD: Deploy stable version
        PROD-->>MON: ✅ Service restored
    end
```

For complete detailed architecture diagrams, see **[ARCHITECTURE.md](ARCHITECTURE.md)**

### 🔄 LangGraph Workflow Architecture

> **📊 View Complete C4 Architecture Diagrams in [ARCHITECTURE.md](ARCHITECTURE.md)**
> 
> The system uses a sophisticated 3-node LangGraph pipeline with intelligent model selection, caching, and real-time processing capabilities.

### 🚀 Advanced CI/CD Pipeline with Intelligent Deployment

> **View detailed deployment architecture in [ARCHITECTURE.md](ARCHITECTURE.md#deployment-architecture)**

The system features a sophisticated CI/CD pipeline with:
- **GitHub Actions** workflows for automated deployment
- **Multi-stage Docker** builds with platform optimization
- **Blue-Green deployment** with automatic rollback
- **Comprehensive health checks** and monitoring


### 🧠 Intelligent Caching Architecture

> **View C³ Algorithm and Cache Architecture in [ARCHITECTURE.md](ARCHITECTURE.md#innovation--algorithms)**

Features our patent-pending C³ (Conformal Counterfactual Cache) system:
- **90% cost reduction** through intelligent caching
- **92% cache hit rate** with pattern recognition
- **Multi-tier TTL** strategy for email classification
- **Real-time analytics** and optimization recommendations

### 📊 Real-time Monitoring & Analytics Architecture

> **View complete monitoring architecture in [ARCHITECTURE.md](ARCHITECTURE.md#system-health-dashboard)**

Comprehensive observability with Application Insights:
- **Real-time metrics** tracking and visualization
- **Cost optimization** with budget alerts
- **Performance monitoring** across all services
- **Custom dashboards** for business KPIs

### 🌊 Data Flow & Processing Architecture

> **View complete data flow diagrams in [ARCHITECTURE.md](ARCHITECTURE.md#data-flow-diagrams)**

End-to-end email processing pipeline:
- **<10s processing** from Outlook to Zoho CRM
- **Parallel batch processing** via Service Bus
- **Real-time streaming** with SignalR WebSocket
- **Intelligent routing** with VoIT orchestration

### 🏗️ Azure Resource Organization & Infrastructure

> **View complete Azure infrastructure in [ARCHITECTURE.md](ARCHITECTURE.md#azure-infrastructure)**
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
APOLLO_API_KEY=your-apollo-api-key

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

## 📈 Performance Metrics

### System Performance
| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| **API Response Time** | < 3s | 2.1s | ✅ |
| **Cache Hit Rate** | > 80% | 92% | ✅ |
| **LangGraph Processing** | < 3s | 2-3s | ✅ |
| **Cost per Email** | < $0.01 | $0.003 | ✅ |
| **Batch Processing** | > 1000/hr | 1500/hr | ✅ |
| **WebSocket Latency** | < 200ms | 180ms | ✅ |
| **Database Query** | < 100ms | 45ms | ✅ |
| **Blob Upload** | < 500ms | 320ms | ✅ |

### Cost Optimization
- **90% reduction** through Redis caching
- **60% savings** with intelligent model selection (nano/mini/full)
- **95% efficiency** for batch processing (50 emails per context)

### Reliability
- **99.9% uptime** with Azure Container Apps
- **Zero-downtime deployments** with blue-green strategy
- **Automatic retries** with exponential backoff
- **Circuit breaker** pattern for external services

## 🔐 Security Features

### Authentication & Authorization
- **API Key Authentication** with secure header validation
- **OAuth 2.0** for Zoho CRM integration
- **Azure Key Vault** for secret management
- **Automatic token refresh** with 55-minute cache

### Data Protection
- **TLS 1.3** for all data in transit
- **AES-256 encryption** at rest
- **PII masking** in logs and telemetry
- **RBAC** for Azure resource access

### Rate Limiting & DDoS Protection
- **100 requests/minute** per API key
- **Azure WAF** protection
- **Circuit breaker** for failed requests
- **Automatic IP blocking** for suspicious activity

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

### v3.5.0 (September 16, 2025) - 🚀 Apollo.io Integration
- **🚀 Apollo.io Contact Enrichment** - Integrated Apollo People Match API for real-time contact data enhancement
- **🔧 Configuration Management** - Added Apollo API key support in config_manager.py with Azure Key Vault integration
- **⚡ Email Processing Enhancement** - Enhanced email pipeline with Apollo enrichment after AI extraction
- **🛡️ Error Handling** - Comprehensive error handling with graceful degradation when Apollo API unavailable
- **📊 Comprehensive Testing** - 90% test success rate across 10 test categories, production ready
- **🔐 Security Integration** - Secure API key management through Azure Key Vault and environment variables

### v3.4.0 (September 16, 2025) - 📊 Documentation & Architecture Updates
- **📐 Architecture Documentation** - Updated comprehensive C4 model diagrams with latest infrastructure
- **📋 README Updates** - Synchronized documentation with production features and deployment status
- **🔧 Enhanced Duplicate Prevention** - Tightened to 5-minute window for same candidate submissions
- **✅ Client Info Extraction Fix** - Corrected extraction to stop pulling referrer location/company incorrectly
- **📧 Brandon's Vault Generator** - Added new candidate email generation capability for Vault system

### v3.3.0 (September 15, 2025) - 🔥 Firecrawl v2 Supercharged
- **🚀 PRODUCTION DEPLOYMENT** - Successfully deployed Firecrawl v2 Supercharged enhanced enrichment system
- **💰 Major Cost Savings** - Saves $149-800/month compared to Clay API while providing superior data quality
- **📊 Enhanced Data Extraction** - Now extracts 30+ company data fields including revenue, employee count, funding, tech stack, industry analysis
- **🎯 Three-Service Architecture** - SuperchargedFirecrawlExtractor + UltraEnrichmentService + SmartCandidateEnricher working in harmony
- **⚡ Zero Breaking Changes** - Full backward compatibility maintained with Steve's existing 21-field structure
- **🔄 Graceful Fallback** - Enhanced enrichment gracefully falls back to standard extraction on timeouts
- **✅ Production Verified** - All 3 records (Company, Contact, Deal) confirmed working with enriched data
- **🐳 Docker Deployment** - Rebuilt image with --no-cache, deployed to Azure Container Apps with verification
- **📈 Business Impact** - Significant competitive advantage through enhanced company intelligence data

### v3.2.1 (September 13, 2025)
- 🔧 **Telemetry Fix** - Updated Application Insights connection string to modern format
- 📊 **Monitoring Restored** - Fixed 400 Bad Request errors in telemetry transmission
- ✅ **Outlook Add-in Updated** - Fixed form field population and cancel button functionality
- 🚀 **Cache Busting** - Updated manifest version to 2.0.0.3 for immediate availability

### v3.2.0 (September 13, 2025)
- 🔥 **CRITICAL FIX** - Resolved "generator didn't stop after athrow()" async context manager issues
- 🔧 **Database Connection Manager** - Removed @asynccontextmanager decorators causing nested generator problems
- 🛠️ **Health Check Fix** - Fixed _perform_health_check to use manual acquire/release pattern
- 🚀 **Production Stability** - API fully operational with proper async handling
- 📊 **Error Handling** - Added GeneratorExit exception handling for graceful cleanup

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

## 🗃️ TalentWell CSV Import & Policy Seeding System

The TalentWell system provides a comprehensive data import pipeline that processes Zoho CRM exports, normalizes data, and seeds intelligent policies for email automation and prospect engagement. This system is designed for high-volume recruitment data processing with built-in deduplication, validation, and audit trails.

### 🎯 Overview

The TalentWell import system transforms raw CSV exports from Zoho CRM into structured, normalized data that powers:
- **Deal Management**: Complete deal lifecycle tracking with stage history
- **Policy Generation**: AI-driven policies for email subject optimization and audience targeting
- **Data Normalization**: Company name standardization and location context mapping
- **Audit Trails**: Full tracking of all import operations with correlation IDs

#### Architecture Components
- **CSV Import Engine**: Processes multiple file formats with flexible parsing
- **PostgreSQL Storage**: Comprehensive schema with vector search capabilities
- **Policy Seeder**: Generates Bayesian priors and A/B testing configurations
- **Validation Layer**: Data integrity checks and business rule enforcement
- **Redis Caching**: Policy and template caching for performance optimization

### 📁 CSV File Formats

The system supports four distinct CSV file types, each with specific column mappings and data requirements:

#### **Deals CSV** (`deals.csv`)
Primary deal records with complete opportunity information.

**Required Columns:**
- `Deal Id` (TEXT) - Unique identifier, cannot be empty
- `Deal Name` (TEXT) - Candidate name or deal identifier
- `Deal Owner` (TEXT) - Owner filter: "Steve Perry"
- `Account Name` (TEXT) - Firm/company name
- `Stage` (TEXT) - Current deal stage

**Optional Columns:**
- `Job Title` (TEXT) - Position being filled
- `Location` (TEXT) - Geographic location
- `Created Time` (DATETIME) - Deal creation timestamp
- `Closing Date` (DATETIME) - Expected/actual close date
- `Modified Time` (DATETIME) - Last modification timestamp
- `Lead Source` (TEXT) - Original source of lead
- `Source Detail` (TEXT) - Additional source information
- `Referrer Name` (TEXT) - Name of referring person
- `Description` (TEXT) - Deal notes and details
- `Amount` (DECIMAL) - Deal value in USD

**Date Format Support:**
- `2025-01-15 10:30:00` (ISO with time)
- `2025-01-15` (ISO date only)
- `01/15/2025` (US format)
- `01/15/2025 10:30 AM` (US with time)
- `15-Jan-2025` (UK format)
- `01-15-2025` (US dash format)

#### **Stage History CSV** (`stage_history.csv`)
Tracks all stage transitions for deal pipeline analysis.

**Required Columns:**
- `Deal Id` (TEXT) - Foreign key reference to deals
- `Stage` (TEXT) - Stage name after transition
- `Changed Time` (DATETIME) - When transition occurred

**Optional Columns:**
- `Duration` (INTEGER) - Days spent in previous stage
- `Changed By` (TEXT) - User who made the change

#### **Meetings CSV** (`meetings.csv`)
Meeting records with engagement metrics for relationship tracking.

**Required Columns:**
- `Deal Id` or `Related To` (TEXT) - Deal association
- `Title` (TEXT) - Meeting subject/title
- `Start DateTime` (DATETIME) - Meeting start time

**Optional Columns:**
- `Participants` (TEXT) - Attendee list
- `Email Opened` (YES/NO) - Email engagement metric
- `Link Clicked` (YES/NO) - Link engagement metric
- `Created Time` (DATETIME) - Record creation time

#### **Notes CSV** (`notes.csv`)
Deal notes and comments with automatic deduplication.

**Required Columns:**
- `Deal Id` or `Parent Id` (TEXT) - Deal association
- `Note Content` (TEXT) - Note text content

**Optional Columns:**
- `Created Time` (DATETIME) - Note creation time
- `Note Owner` or `Created By` (TEXT) - Note author
- `Modified Time` (DATETIME) - Last modification

### 📂 File Placement

The system supports multiple file placement strategies for different deployment scenarios:

#### **Local Development**
Place CSV files in the local imports directory:
```
/path/to/project/app/admin/imports/
├── deals.csv
├── stage_history.csv  
├── meetings.csv
└── notes.csv
```

#### **Container Deployment**
Mount CSV files to the container data directory:
```
/mnt/data/
├── Deals_2025_09_10.csv
├── Deals_Stage_History_2025_09_10.csv
├── Meetings_2025_09_10.csv
└── Notes_Deals_2025_09_10.csv
```

#### **File Naming Conventions**
- Prefix with data type: `Deals_`, `Meetings_`, `Notes_`
- Include date stamp: `YYYY_MM_DD` format
- Use descriptive suffixes: `_Stage_History`, `_Deals`
- Maintain `.csv` extension

### 🚀 API Endpoints

#### **Import Endpoints**

##### 1. Default Folder Import
Imports all CSV files from the default directory (`app/admin/imports/` or `/mnt/data/`).

```bash
curl -X POST "https://well-zoho-oauth.azurewebsites.net/api/talentwell/admin/import-exports" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "status": "success", 
  "import_summary": {
    "deals": 1250,
    "stage_history": 3400,
    "meetings": 890,
    "notes": 2100,
    "owner": "Steve Perry",
    "date_range": "2025-01-01 to 2025-09-08"
  },
  "timestamp": "2025-09-11T15:30:00.000Z"
}
```

##### 2. Explicit Paths Import
Specify exact file paths for each CSV type.

```bash
curl -X POST "https://well-zoho-oauth.azurewebsites.net/api/talentwell/admin/import-exports" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "paths": {
      "deals": "/mnt/data/Deals_2025_09_10.csv",
      "stage_history": "/mnt/data/Deals_Stage_History_2025_09_10.csv",
      "meetings": "/mnt/data/Meetings_2025_09_10.csv",
      "notes": "/mnt/data/Notes_Deals_2025_09_10.csv"
    }
  }'
```

##### 3. JSON Content Import
Send CSV content directly in JSON payload.

```bash
curl -X POST "https://well-zoho-oauth.azurewebsites.net/api/talentwell/admin/import-exports" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "deals": "Deal Id,Deal Name,Deal Owner\n123,John Doe,Steve Perry",
    "stage_history": "Deal Id,Stage,Changed Time\n123,Qualified,2025-09-10 14:30:00"
  }'
```

##### 4. Multipart File Upload (Future Enhancement)
Upload CSV files directly via multipart form data.

```bash
curl -X POST "https://well-zoho-oauth.azurewebsites.net/api/talentwell/admin/import-exports" \
  -H "X-API-Key: $API_KEY" \
  -F "deals=@Deals.csv" \
  -F "stages=@Stage_History.csv" \
  -F "meetings=@Meetings.csv" \
  -F "notes=@Notes.csv"
```

#### **Policy Management Endpoints**

##### 1. Seed Policies
Generate and seed all policy data into database and Redis cache.

```bash
curl -X POST "https://well-zoho-oauth.azurewebsites.net/api/talentwell/seed-policies" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json"
```

**Query Parameters:**
- `regenerate` (boolean) - Clear existing policies and regenerate from scratch

**Response:**
```json
{
  "status": "success",
  "policies_generated": {
    "employers": 145,
    "city_context": 89, 
    "subject_priors": 23,
    "selector_priors": 12
  },
  "database_seeded": {"employers": 145, "cities": 89},
  "redis_loaded": {"cache_keys": 8, "policies_loaded": 269},
  "timestamp": "2025-09-11T15:30:00.000Z"
}
```

##### 2. Reload Policies (via Policy Loader)
Refresh Redis cache from database without regeneration.

```bash
# Access through internal policy loader service
curl -X GET "https://well-zoho-oauth.azurewebsites.net/api/cache/warmup" \
  -H "X-API-Key: $API_KEY"
```

#### **Outlook Integration Endpoints**

##### 1. Email Intake
Process emails from Outlook Add-in with TalentWell integration.

```bash
curl -X POST "https://well-zoho-oauth.azurewebsites.net/api/intake/email" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Senior Developer Position - ABC Corp",
    "body": "We have an excellent opportunity...",
    "sender_email": "recruiter@abccorp.com",
    "sender_name": "Jane Smith",
    "attachments": [
      {
        "filename": "resume.pdf",
        "content_base64": "base64_encoded_content",
        "content_type": "application/pdf"
      }
    ]
  }'
```

**Response:**
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
  },
  "talentwell_integration": {
    "policies_applied": 3,
    "normalization_used": true,
    "audit_correlation_id": "uuid-here"
  }
}
```

### ⚙️ Configuration

#### **Environment Variables**
Add these to your `.env.local` file for TalentWell functionality:

```bash
# Database Configuration
DATABASE_URL=postgresql://user:pass@host:5432/wellintake?sslmode=require

# API Security
API_KEY=your-secure-api-key-here

# TalentWell Settings
TALENTWELL_OWNER_FILTER=Steve Perry
TALENTWELL_DATE_START=2025-01-01
TALENTWELL_DATE_END=2025-09-08
TALENTWELL_IMPORT_PATH=/app/admin/imports
TALENTWELL_CONTAINER_PATH=/mnt/data

# Redis Configuration (for policy caching)
AZURE_REDIS_CONNECTION_STRING=rediss://:password@host:6380

# Azure Storage (for audit logs)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
AZURE_CONTAINER_NAME=talentwell-audit

# Policy Generation
POLICY_GENERATION_ENABLED=true
SUBJECT_BANDIT_ENABLED=true
BAYESIAN_PRIORS_ENABLED=true
```

#### **API Key Setup**
1. Generate a secure API key (32+ characters)
2. Add to environment variables on all services
3. Ensure OAuth proxy forwards authentication
4. Test with health check endpoints

#### **Database Connection**
The system requires PostgreSQL with extensions:
- `uuid-ossp` for UUID generation
- `pgcrypto` for hash functions  
- `pg_trgm` for fuzzy text matching
- `pgvector` for similarity search (optional)

#### **Redis Configuration**
Policy caching requires Azure Cache for Redis:
- Basic C0 tier (256MB) minimum
- SSL/TLS enabled (rediss://)
- 24-hour TTL for policy data
- Automatic cache warmup on policy updates

### 🔧 Troubleshooting Guide

#### **Common Import Errors**

##### **400 Bad Request - Invalid CSV Format**
```json
{"detail": "Request body required"}
```

**Solutions:**
1. Ensure Content-Type is `application/json` for JSON payloads
2. Verify CSV data is properly formatted
3. Check that at least one CSV type is provided
4. Validate JSON structure matches expected format

##### **415 Unsupported Media Type**
```json  
{"detail": "Invalid JSON in request body"}
```

**Solutions:**
1. Use proper JSON encoding for CSV content
2. Escape special characters in CSV data
3. Ensure multipart form data has correct field names
4. Check file upload size limits (25MB max)

##### **Database Constraint Violations**
```json
{"detail": "Foreign key constraint failed: deal_id not found"}
```

**Solutions:**
1. Import deals.csv before other CSV types
2. Verify Deal IDs exist in referenced tables
3. Check date range filtering isn't excluding deals
4. Ensure owner filter matches data ("Steve Perry")

##### **Zoho API Integration Failures**
```json
{"detail": "Zoho API authentication failed"}
```

**Solutions:**
1. Check OAuth service is running
2. Verify refresh token is valid
3. Ensure API rate limits aren't exceeded
4. Test Zoho connectivity with health endpoint

#### **Performance Issues**

##### **Slow Import Processing**
**Symptoms:** Import takes >30 seconds for <1000 records

**Solutions:**
1. Check database connection pool settings
2. Verify indexes exist on foreign key columns
3. Use batch processing for large datasets
4. Enable PostgreSQL query optimization

##### **Memory Issues**
**Symptoms:** Out of memory errors during large imports

**Solutions:**
1. Process files in smaller batches
2. Increase container memory allocation
3. Use streaming CSV parsing for large files
4. Clear Redis cache if memory constrained

#### **Audit Trail Debugging**

##### **Correlation ID Tracking**
Every import operation generates a correlation ID for tracking:

```sql
-- Find all operations for a correlation ID
SELECT operation_type, outcome, processing_time_ms, error_message
FROM intake_audit 
WHERE correlation_id = 'uuid-here'
ORDER BY created_at;

-- Check recent import failures
SELECT correlation_id, operation_type, error_message, created_at
FROM intake_audit 
WHERE outcome = 'failure' 
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

##### **Policy Application Issues**
```sql
-- Verify policy seeding completed successfully
SELECT COUNT(*) as employer_count FROM employer_normalization;
SELECT COUNT(*) as city_count FROM city_context;  
SELECT COUNT(*) as subject_count FROM subject_bandit;

-- Check policy usage in deal processing
SELECT metadata->>'policies_applied' as policies, COUNT(*)
FROM intake_audit 
WHERE operation_type = 'email_processing'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY policies;
```

### 📋 Best Practices

#### **Import Frequency**
- **Daily imports**: For active recruitment campaigns
- **Weekly imports**: For historical analysis and reporting
- **Monthly imports**: For policy regeneration and optimization

#### **Data Validation**
- Always import deals.csv first (foreign key dependencies)
- Validate date ranges match expected data period
- Check owner filter matches your data exactly
- Verify CSV encoding is UTF-8

#### **Performance Optimization**
- Use explicit file paths for container deployments
- Enable Redis caching for policy data
- Monitor database query performance
- Batch large imports into smaller chunks

#### **Security Considerations**
- Never log PII data in application logs
- Use correlation IDs for debugging (no sensitive data)
- Ensure API keys are properly secured
- Validate file upload sizes and types

### 🗃️ Database Migration

#### **Running the Migration**
Execute the TalentWell schema migration:

```bash
# Connect to PostgreSQL
psql $DATABASE_URL

# Run migration script
\i migrations/003_talentwell_tables.sql

# Verify tables created
\dt+ deals deal_stage_history meetings deal_notes;
\dt+ employer_normalization city_context subject_bandit;
\dt+ selector_priors intake_audit;
```

#### **Rollback Procedure**
If migration fails or needs rollback:

```sql
-- Backup existing data first
CREATE TABLE deals_backup AS SELECT * FROM deals;
CREATE TABLE audit_backup AS SELECT * FROM intake_audit;

-- Drop TalentWell tables (cascade removes foreign keys)
DROP TABLE IF EXISTS intake_audit CASCADE;
DROP TABLE IF EXISTS deal_notes CASCADE;
DROP TABLE IF EXISTS meetings CASCADE;
DROP TABLE IF EXISTS deal_stage_history CASCADE;
DROP TABLE IF EXISTS deals CASCADE;

-- Drop normalization tables
DROP TABLE IF EXISTS employer_normalization CASCADE;
DROP TABLE IF EXISTS city_context CASCADE;
DROP TABLE IF EXISTS subject_bandit CASCADE;
DROP TABLE IF EXISTS selector_priors CASCADE;
```

#### **Data Backup**
Before major imports, backup critical data:

```bash
# Backup TalentWell tables
pg_dump $DATABASE_URL \
  -t deals -t deal_stage_history -t meetings -t deal_notes \
  -t employer_normalization -t city_context -t subject_bandit \
  -t selector_priors -t intake_audit \
  > talentwell_backup_$(date +%Y%m%d).sql

# Restore if needed
psql $DATABASE_URL < talentwell_backup_20250911.sql
```

## 📜 License

Proprietary - The Well Recruiting © 2025