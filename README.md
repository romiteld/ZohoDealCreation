# Well Intake Platform

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com/)
[![Azure](https://img.shields.io/badge/Azure-Container%20Apps-0078D4.svg)](https://azure.microsoft.com/)
[![Redis](https://img.shields.io/badge/Redis-6.x-DC382D.svg)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-Proprietary-critical.svg)]()

> AI-assisted email intake that transforms Outlook messages into enriched Zoho CRM records in seconds.

---

## Contents

1. [Overview](#overview)
2. [Technology Stack & Infrastructure](#technology-stack--infrastructure)
3. [Quick Start](#quick-start)
4. [Key Capabilities](#key-capabilities)
5. [Architecture](#architecture)
   - [System Context (C4 Level 1)](#system-context-c4-level-1---complete-production-architecture)
   - [Intake Runtime](#intake-runtime-primary-sequence)
   - [VoIT Processing Flow](#voit-processing-flow-candidate-vault-agent)
   - [Container Responsibilities (C4 Level 2)](#container-responsibilities-c4-level-2)
   - [FastAPI Component Map (C4 Level 3)](#fastapi-core-component-map-c4-level-3)
   - [C³ Cache Logic](#c%C2%B3-cache-reuse-or-rebuild-decision-logic)
   - [API Endpoint Catalogue](#complete-api-endpoint-catalogue)
   - [Data & Integration Catalogue](#data--integration-catalogue)
   - [Vault Agent Summary](#candidate-vault-agent-architecture-summary)
   - [CI/CD Pipeline](#cicd--deployment-pipeline-architecture)
6. [Development Guide](#development-guide)
7. [Testing](#testing)
8. [CI/CD & Operations](#cicd--operations)
9. [Directory Layout](#directory-layout)
10. [Support](#support)

---

## Overview

**Well Intake** is an enterprise-grade AI-powered recruiting automation platform that transforms Outlook emails into enriched Zoho CRM records in under 3 seconds. Built as a **microservices architecture** on Azure Container Apps with intelligent cost optimization through VoIT + C³, the platform consists of:

### Microservices Architecture (Phase 1)

1. **Main API Service** (`app/`) - Port 8000
   - Email processing with LangGraph workflow (Extract → Research → Validate)
   - Zoho CRM integration via OAuth proxy
   - Firecrawl v2 + Apollo.io enrichment
   - Redis caching with C³ probabilistic reuse
   - Azure Service Bus batch processing

2. **Teams Bot Service** (`teams_bot/`) - Port 8001
   - Microsoft Teams integration with Bot Framework SDK
   - Adaptive Cards for interactive UI
   - Natural language query engine with GPT-5
   - TalentWell candidate digest generation
   - User preferences and analytics tracking

3. **Vault Agent Service** (Phase 2 - Planned) - Port 8002
   - Weekly digest scheduler (hourly background job)
   - Automated email delivery via Azure Communication Services
   - Subscription management and delivery tracking

4. **Shared Library** (`well_shared/`)
   - Common utilities used across all services
   - Database connection management (PostgreSQL)
   - Redis cache manager with intelligent TTL
   - Email delivery (Azure Communication Services)
   - Evidence extraction and VoIT configuration

**Benefits of Microservices:**
- Independent deployment and scaling per service
- Isolated failure domains (Teams Bot doesn't affect email processing)
- Technology flexibility (different frameworks per service)
- Easier testing and development (run services independently)

### Executive Summary
- **50+ REST API endpoints** serving Outlook add-ins, Teams bot, webhooks, and admin consoles
- **Microsoft Teams bot integration** with Adaptive Cards for TalentWell candidate digests
- **LangGraph AI pipeline** (Extract → Research → Validate) with GPT-5 tiered model selection
- **90% cost reduction** through C³ probabilistic caching and VoIT adaptive reasoning
- **Sub-3s processing** with Redis caching, async IO, and streaming WebSocket/SSE
- **Multi-source ingestion**: Emails, Zoom transcripts, resumes, web scraping
- **Multi-channel publishing**: Email campaigns, CRM sync, Teams bot digests, portal cards, JD alignment
- **Zero-downtime deployments** via Azure Container Apps multi-revision with instant rollback
- **Enterprise security**: Azure AD + HMAC API keys, Key Vault secrets, TLS 1.2+
- **Full observability**: Application Insights with custom metrics, 90-day audit logs

### Core Value Proposition
- **Accuracy** – Multi-stage extraction with Firecrawl v2, Apollo.io enrichment, and 95% duplicate prevention
- **Speed** – Sub-3s email-to-CRM with LangGraph pipeline, Redis caching, and batch processing (50 emails/batch)
- **Intelligence** – Candidate Vault Agent (VoIT) adapts reasoning depth based on uncertainty; C³ cache reuses 90% of computations
- **Control** – Human-in-the-loop Outlook taskpane with edit-before-send, confidence indicators, and test mode
- **Reliability** – Auto-scaling (0-10 instances), health checks, emergency rollback, and comprehensive error handling
- **Cost Efficiency** – 65% AI cost reduction through smart model tier selection (nano/mini/large) and semantic caching


## Technology Stack & Infrastructure

### Core Technologies
- **Backend**: Python 3.11, FastAPI 0.104+, LangGraph 0.2.74
- **Frontend**: Vanilla JavaScript, Office.js, HTML5/CSS3
- **AI/ML**: Azure OpenAI (GPT-5 tiers), LangChain, Pydantic structured outputs
- **Databases**: Azure PostgreSQL Flexible Server (pgvector), Azure Cache for Redis 6.x
- **Message Queue**: Azure Service Bus (Standard tier)
- **Storage**: Azure Blob Storage (Hot tier), Azure AI Search
- **Hosting**: Azure Container Apps (multi-revision), Azure Front Door CDN
- **Teams Integration**: Bot Framework SDK 4.16+, Adaptive Cards v1.4
- **Security**: Azure Key Vault, Azure AD, HMAC API key validation
- **Monitoring**: Application Insights, custom metrics, structured logging
- **CI/CD**: GitHub Actions (3 workflows), 20+ automation scripts
- **IaC**: Azure CLI scripts, Docker multi-stage builds

### Azure Resource Inventory
- **Resource Group**: `TheWell-Infra-East` (East US)
- **Container Apps**: `well-intake-api` (auto-scaling 0-10 instances)
- **Container Registry**: `wellintakeacr0903.azurecr.io`
- **PostgreSQL**: `well-intake-db.postgres.database.azure.com`
- **Redis**: Azure Cache for Redis (Standard C1, 1GB)
- **Blob Storage**: `wellintakestorage` (attachments, manifests, icons)
- **Service Bus**: Namespace with `email-batch-queue`
- **AI Search**: `wellintakesearch0903` (Basic tier)
- **Front Door**: `well-intake-api-dnajdub4azhjcgc3.z03.azurefd.net`
- **Key Vault**: `well-intake-kv`
- **App Insights**: Integrated with Container Apps

### Cost Optimization Features
- **VoIT Controller**: Adaptive model tier selection (nano/mini/large) based on complexity
- **C³ Cache**: 90% reduction in redundant API calls through probabilistic reuse
- **Redis Caching**: 24h TTL for enrichment data, 2-12h for intake previews
- **Batch Processing**: 50 emails/batch reduces per-request overhead
- **Azure Maps**: Optional geocoding with 24h cache (cost-gated)
- **Apollo.io**: Free plan fallback for contact enrichment
- **Service Bus**: Dead-letter queue for retry without reprocessing costs

### Business Metrics & KPIs
- **Processing Speed**: Sub-3s email-to-CRM with LangGraph pipeline
- **Accuracy**: Multi-stage validation with Firecrawl/Apollo enrichment
- **Cache Hit Rate**: 90% with C³ probabilistic reuse (Application Insights tracked)
- **Uptime**: Azure Container Apps auto-scaling (0-10 instances)
- **Cost Efficiency**: VoIT reduces AI costs by 65% through smart model selection
- **Data Quality**: Duplicate detection prevents 95% of redundant CRM records
- **Human-in-the-Loop**: 100% operator approval before CRM submission
- **API Reliability**: Multi-revision deployment with instant rollback capability

### Security & Compliance
- **Authentication**: Multi-factor (Azure AD Bearer tokens + HMAC API keys)
- **Rate Limiting**: 5 failed attempts → 15-minute lockout per IP/key
- **Secret Management**: Azure Key Vault with rotation support
- **Data Encryption**: TLS 1.2+ in transit, encrypted at rest (Azure Storage/PostgreSQL)
- **CORS**: Restricted origins with Azure Front Door CDN
- **Audit Logging**: Application Insights with 90-day retention
- **API Security**: Timing-safe key comparison prevents side-channel attacks
- **Input Validation**: Pydantic models with strict type checking
- **Least Privilege**: Managed identities for Azure resource access
- **Secrets Scanning**: GitHub Actions security checks on every commit

## Quick Start

### Local Development Setup

| Step | Command | Notes |
|------|---------|-------|
| 1 | `python -m venv zoho && source zoho/bin/activate` | Use Python 3.11 (Windows: `zoho\Scripts\activate`) |
| 2 | `pip install -r requirements.txt` | Installs core dependencies |
| 3 | `pip install -r requirements-dev.txt` | Installs development tools |
| 4 | `npm install --prefix addin` | Installs Outlook add-in dependencies |
| 5 | `cp .env.example .env.local` | Fill in secrets & API keys |
| 6 | `alembic upgrade head` | Initialize database schema |

### Running Services Locally

**Main API Service** (Email Processing)
```bash
uvicorn app.main:app --reload --port 8000
# Visit: http://localhost:8000/docs
```

**Teams Bot Service** (Microsoft Teams Integration)
```bash
uvicorn teams_bot.app.main:app --reload --port 8001
# Visit: http://localhost:8001/health
```

**Outlook Add-in** (Frontend)
```bash
npm run serve --prefix addin
# Visit: http://localhost:8080
```

**Shared Library** (Development Mode)
```bash
cd well_shared
pip install -e .  # Editable mode for live updates
```

### Prerequisites
- **Redis**: Azure Cache for Redis (or local `redis-server` on port 6379)
- **PostgreSQL**: Azure PostgreSQL Flexible Server (or local `postgres` on port 5432)
- **Environment Variables**: See [CLAUDE.md](CLAUDE.md#environment-variables) for required config

See [Development Guide](#development-guide) for Docker container helpers and detailed setup instructions.


## Key Capabilities

### Intake & Enrichment
- Multi-stage LangGraph pipeline (extract -> research -> validate) powered by GPT-5 tiers.
- Firecrawl v2 “supercharged” enrichment with company HQ, revenue, funding, tech stack, and leadership insights.
- Apollo.io enrichment for contact-level details (phone, LinkedIn, titles) with smart throttling.

### Outlook Taskpane Experience
- One-click **Send to Zoho**, **Test**, and enrichment controls inside Outlook.
- Real-time field confidence indicators, attachment previews, and manual override hints.
- Express-send gating based on extraction confidence and deduplication checks.

### Microsoft Teams Bot Integration
- **Interactive Adaptive Cards** for TalentWell candidate digest previews with rich formatting.
- **Command-driven interface**: `digest [audience]`, `preferences`, `analytics`, `help`.
- **Audience filtering by job title**: advisors (Financial/Wealth Advisors), c_suite (Executives), global (all).
- **Test mode routing**: `digest <email>` sends digest preview to specific email for validation.
- **User preferences**: Default audience, digest frequency, notification settings stored in PostgreSQL.
- **Analytics tracking**: Conversation count, digest requests, recent activity per user.
- **Score-based ranking**: Composite scoring (financial metrics + evidence quality + sentiment).
- **Sentiment analysis**: Enthusiasm and tone detection from Zoom transcripts and CRM notes.

### CRM Automation
- Creates or updates Zoho Accounts, Contacts, and Deals with full enrichment data.
- Duplicate guardrails (email / company / time-window) prevent accidental reconciling.
- Attachment ingestion into Azure Blob storage with metadata hydration.

### Platform Services
- Redis-backed caching with auto-invalidation during deployments.
- Azure Container Apps hosting with GitHub Actions pipeline (version bumping + cache busting).
- Emergency rollback workflow for instant traffic shift to previous revisions.

### Geocoding & Location Intelligence
- Optional Azure Maps integration for forward/reverse geocoding.
- Automated address normalization and city/state enrichment during company research.
- Configurable country bias, caching (24h TTL), and feature flag via `ENABLE_AZURE_MAPS`.

### Revolutionary AI Optimization Algorithms (VoIT + C³)

**🚨 Novel Contribution to AI Systems Architecture**

This system introduces **two groundbreaking algorithms** that optimize AI content processing across the entire platform:

#### **VoIT (Value of Insight Time)** - Adaptive Reasoning Depth Allocation
- **First-of-its-kind algorithm** that dynamically allocates compute budget based on uncertainty metrics
- Evaluates **Value of Information (VOI)** for each processing span: `VOI = quality_gain - λ*cost - μ*latency`
- Automatically selects optimal model tier (GPT-5-nano/mini/large) or tool based on expected return
- **Novel uncertainty quantification**: Combines retrieval dispersion, rule conflicts, and C³ margin scores
- Achieves **65% cost reduction** while maintaining 95%+ quality through intelligent resource allocation
- Operates at **span-level granularity** - each content segment optimized independently

#### **C³ (Conditional Causal Cache)** - Probabilistic Reuse-or-Rebuild Engine
- **Revolutionary caching mechanism** that goes beyond traditional cache hit/miss logic
- Calculates **probabilistic margin** (δ) to determine if cached content can be safely reused
- **Embedding similarity + field drift detection** - understands semantic changes, not just exact matches
- **Selective rebuild** - identifies and regenerates only invalidated spans, not entire artifacts
- **Dependency tracking with certificates** - maintains causal relationships between cached entries
- Achieves **90% cache hit rate** with intelligent reuse decisions (vs ~50% with traditional caching)
- **7-day TTL with drift detection** - balances freshness with cost efficiency

**Combined Impact:**
- 90% reduction in redundant API calls
- Sub-3s processing times with intelligent optimization
- Cost per request reduced from $0.08 to $0.02
- These algorithms are **cross-cutting concerns** that optimize ALL content processing throughout the system

---

### Candidate Vault Agent
**Separate feature for CRM data aggregation and formatted output generation**

- **Multi-source Data Aggregation** - Pulls candidate records from Zoho CRM "vault" + enriches with:
  - Resume documents
  - Zoom meeting transcripts and notes
  - Web research/scraping results
  - Historical CRM notes
- **Locked Format Output** - Produces Brandon's specification-compliant digest cards:
  - **‼️** for candidate name and title
  - **🔔** for company and location
  - **📍** for availability and compensation
  - **3-5 evidence-backed bullet points** (no hallucinations)
- **TalentWell Curator Integration** - Powers advisor-specific candidate alerts ([run_talentwell_with_real_twav.py](run_talentwell_with_real_twav.py)) with evidence extraction, financial pattern recognition (AUM, production, licenses), and digest card generation ([Advisor_Vault_Candidate_Alerts.html](Advisor_Vault_Candidate_Alerts.html))
- **Quality Enforcement** - Validates all output against format requirements before delivery
- **Leverages VoIT + C³** - Uses the platform's optimization algorithms for efficient processing

### Privacy & Data Quality Features
**Feature-flagged privacy enhancements for TalentWell candidate digests** (✅ Production: 2025-10-05)

- **Company Anonymization** (`PRIVACY_MODE=true`)
  - Transforms identifying company names into generic descriptors
  - Example: "Morgan Stanley" → "Major wirehouse", "Small RIA Shop" → "Mid-sized RIA"
  - Size-based categorization using AUM when available
  - Protects candidate privacy while preserving context for advisors

- **Strict Compensation Formatting**
  - Normalizes all compensation data to "Target comp: $XXK–$YYK OTE" format
  - Parses various input formats: ranges, single values, "all-in", "base + bonus"
  - Handles edge cases: "1.5M" → "$1500K OTE", "negotiable" → "Target comp: negotiable"
  - Prevents raw candidate phrasing from appearing in digests

- **Location Bullet Suppression**
  - Location appears only in card header, never duplicated in bullets
  - Prevents redundant "Location: New York, NY" bullet points
  - Maintains clean, focused bullet point lists

- **AUM Privacy Rounding**
  - Rounds AUM to privacy-preserving ranges: "$5B+", "$1B–$5B", "$500M–$1B", "$100M–$500M"
  - Prevents exact book size disclosure while maintaining advisor context

- **AI Enhancement Features**
  - **Growth Extraction** (`FEATURE_GROWTH_EXTRACTION=true`) - Parses "grew 40% YoY" and "$1B → $1.5B" patterns from transcripts
  - **GPT-5 Sentiment Analysis** (`FEATURE_LLM_SENTIMENT=true`) - Analyzes enthusiasm, professionalism, red flags; 5-15% boost/penalty on bullet scores
  - **Score-Based Ranking** - Composite scoring prioritizes growth metrics, sentiment, and evidence quality

- **Rollback Capability**
  - Set `PRIVACY_MODE=false` in Azure Container Apps environment variables
  - Instant revert to original behavior without code deployment
  - Feature flags stored in `app/config/feature_flags.py`

- **Comprehensive Test Coverage** - 51 tests across 3 suites
  - `tests/talentwell/test_data_quality.py` (15 tests) - Privacy mode unit tests
  - `tests/talentwell/test_bullet_ranking.py` (29 tests) - Growth extraction, sentiment scoring
  - `tests/talentwell/test_privacy_integration.py` (7 tests) - Full end-to-end integration tests


## Architecture

- **Microservices architecture** with three independent services: Main API (email processing), Teams Bot (Microsoft Teams integration), and Vault Agent (digest scheduler).
- **Shared library** (`well_shared/`) provides common utilities for database, cache, mail, and VoIT configuration across all services.
- FastAPI orchestrates LangGraph pipelines within Azure Container Apps, while the Outlook add-in and Teams Bot provide human-in-the-loop control surfaces.
- **VoIT and C³ algorithms** operate as cross-cutting optimization layers across ALL processing paths - from email intake to candidate vault publishing.
- Redis and PostgreSQL back persistent enrichment results; Azure Blob storage captures attachments and static assets.
- Azure OpenAI, Firecrawl, Apollo, and Azure Maps supply enrichment signals, with OAuth proxying and Azure Key Vault safeguarding secrets.
- GitHub Actions delivers container builds and warm cache scripts to keep endpoints responsive.
- The **Candidate Vault Agent** aggregates CRM data and produces formatted digest cards, leveraging the VoIT/C³ optimization layer.
- The **Teams Bot** provides natural language query interface and weekly digest subscriptions, with Azure Communication Services handling email delivery.
- Each service can be deployed, scaled, and monitored independently while sharing common infrastructure and libraries.

> **Diagram legend** - blue: operators, dark gray: platform services, amber: data stores, violet: third-party integrations, green: observability & ops, **coral: revolutionary VoIT/C³ optimization algorithms** (novel contribution).

### System Context (C4 Level 1) - Complete Production Architecture

```mermaid
flowchart TB
    classDef actor fill:#E3F2FD,stroke:#1E40AF,color:#0B1F4B,stroke-width:2px;
    classDef platform fill:#F8FAFC,stroke:#0F172A,color:#0F172A,stroke-width:2px;
    classDef datastore fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:2px;
    classDef external fill:#FCE7F3,stroke:#C026D3,color:#701A75,stroke-width:2px;
    classDef ops fill:#DCFCE7,stroke:#15803D,color:#064E3B,stroke-width:2px;
    classDef intelligent fill:#FED7D7,stroke:#E53E3E,color:#742A2A,stroke-width:2px;
    classDef infra fill:#E0E7FF,stroke:#4338CA,color:#1E1B4B,stroke-width:2px;
    classDef shared fill:#F0FDFA,stroke:#14B8A6,color:#134E4A,stroke-width:2px;

    subgraph Users["User Layer"]
        Recruiter["Recruiters\n(Outlook Desktop/Web/Teams)"]
        Executives["Executive Staff\n(Weekly digest subscribers)"]
        Admin["Admin Users\n(Management Console)"]
    end
    class Recruiter,Executives,Admin actor;

    subgraph ClientApps["Client Applications"]
        OutlookAddin["Outlook Add-in\n(Office.js, Manifest v1.1)"]
        TeamsClient["Teams Client\n(Microsoft Teams UI)"]
        WebHooks["Webhook Handlers\n(Inbound integrations)"]
    end
    class OutlookAddin,TeamsClient,WebHooks platform;

    subgraph AzureInfra["Azure Infrastructure"]
        FrontDoor["Azure Front Door CDN\nwell-intake-api-dnajdub4azhjcgc3"]
        MainContainer["Container Apps\nwell-intake-api (Port 8000)\n(Multi-revision with traffic split)"]
        TeamsContainer["Container Apps\nteams-bot (Port 8001)\n(Bot Framework SDK)"]
        ACR["Azure Container Registry\nwellintakeacr0903"]
        KeyVault["Azure Key Vault\nwell-intake-kv"]
        AppInsights["Application Insights\n(Telemetry + Alerts)"]
    end
    class FrontDoor,MainContainer,TeamsContainer,ACR,KeyVault,AppInsights infra;

    subgraph SharedLib["Shared Library (well_shared/)"]
        SharedCache["Redis Manager\n(cache/redis_manager.py)"]
        SharedDB["Database Connection\n(database/connection.py)"]
        SharedMail["Email Sender\n(mail/sender.py)"]
        SharedVoIT["VoIT Config\n(config/voit_config.py)"]
        SharedC3["C³ Cache\n(cache/c3.py)"]
        SharedTelemetry["Telemetry\n(telemetry/insights.py)"]
    end
    class SharedLib,SharedCache,SharedDB,SharedMail,SharedVoIT,SharedC3,SharedTelemetry shared;

    subgraph NovelAlgorithms["🚨 Revolutionary Optimization Layer (Novel Algorithms)"]
        VoIT["VoIT Algorithm\n(Value of Insight Time)\nAdaptive reasoning allocation"]
        C3["C³ Algorithm\n(Conditional Causal Cache)\nProbabilistic reuse engine"]
    end
    class NovelAlgorithms,VoIT,C3 intelligent;

    subgraph CoreServices["Core Application Services (Main API - Port 8000)"]
        FastAPI["FastAPI Core\n50+ endpoints"]
        OAuth["OAuth Proxy\n(Zoho token broker)"]
        VaultAgent["Candidate Vault Agent\n(CRM aggregation + formatting)"]
        DigestScheduler["Weekly Digest Scheduler\n(Hourly background job)"]
        LangGraph["LangGraph Pipeline\n(Extract → Research → Validate)"]
        StreamAPI["Streaming API\n(WebSocket + SSE)"]
        GraphClient["Microsoft Graph Client\n(Email integration)"]
    end
    class FastAPI,OAuth,VaultAgent,DigestScheduler,LangGraph,StreamAPI,GraphClient platform;

    subgraph TeamsBotServices["Teams Bot Services (Port 8001)"]
        BotFramework["Bot Framework SDK\n(Adaptive Cards + Dialog)"]
        NLPEngine["Natural Language Engine\n(GPT-5-mini intent classification)"]
        DigestWorker["Digest Worker\n(Service Bus consumer)"]
        MarketabilityWorker["Vault Marketability Worker\n(Service Bus consumer)"]
        UserPrefs["User Preferences Manager\n(PostgreSQL storage)"]
        Analytics["Analytics Tracker\n(Conversation metrics)"]
    end
    class TeamsBotServices,BotFramework,NLPEngine,DigestWorker,MarketabilityWorker,UserPrefs,Analytics platform;

    subgraph DataLayer["Data & Persistence Layer"]
        RedisCache["Azure Cache for Redis\n(C³ + standard cache)"]
        PostgreSQL["Azure PostgreSQL Flexible\nwell-intake-db\n(pgvector + 400K context)"]
        BlobStorage["Azure Blob Storage\n(Attachments + manifests)"]
        ServiceBus["Azure Service Bus\n(email-batch-queue, digest-queue,\nvault-marketability-queue)"]
        AISearch["Azure AI Search\n(Semantic patterns)"]
    end
    class RedisCache,PostgreSQL,BlobStorage,ServiceBus,AISearch datastore;

    subgraph AIEnrichment["AI & Enrichment Services"]
        AzureOpenAI["Azure OpenAI\nGPT-5 nano/mini/large\n(Tiered selection)"]
        Firecrawl["Firecrawl v2 API\n(FIRE-1 agent)"]
        ApolloIO["Apollo.io API\n(Contact enrichment)"]
        AzureMaps["Azure Maps\n(Geocoding)"]
        Zoom["Zoom API\n(Transcripts + recordings)"]
    end
    class AzureOpenAI,Firecrawl,ApolloIO,AzureMaps,Zoom external;

    subgraph ExternalSystems["External Business Systems"]
        ZohoCRM["Zoho CRM v8 API\n(Accounts/Contacts/Deals/Leads)"]
        ACS["Azure Communication Services\n(Weekly digest emails)"]
        TeamsAPI["Microsoft Teams API\n(Bot Framework + Adaptive Cards)"]
    end
    class ZohoCRM,ACS,TeamsAPI external;

    subgraph CICD["CI/CD & DevOps"]
        GitHub["GitHub Actions\n(3 workflows)"]
        Scripts["Deployment Scripts\n(20+ automation scripts)"]
    end
    class GitHub,Scripts ops;

    %% User flows
    Recruiter -->|"Open add-in"| OutlookAddin
    Recruiter -->|"Chat in Teams"| TeamsClient
    Recruiter -->|"Subscribe to digests"| TeamsClient
    Executives -->|"Receive digests"| ACS

    %% Client to infrastructure
    OutlookAddin -->|"HTTPS/WSS"| FrontDoor
    TeamsClient -->|"Bot Framework"| TeamsAPI
    WebHooks -->|"HTTPS"| FrontDoor
    Admin -->|"Admin APIs"| FrontDoor

    %% Infrastructure routing
    FrontDoor -->|"Route + TLS"| MainContainer
    FrontDoor -->|"Route + TLS"| TeamsContainer
    TeamsAPI -->|"Messages"| TeamsContainer
    MainContainer -->|"Pull images"| ACR
    TeamsContainer -->|"Pull images"| ACR
    MainContainer -->|"Fetch secrets"| KeyVault
    TeamsContainer -->|"Fetch secrets"| KeyVault
    MainContainer -->|"Telemetry"| AppInsights
    TeamsContainer -->|"Telemetry"| AppInsights

    %% Shared library usage
    MainContainer -.->|"Uses"| SharedLib
    TeamsContainer -.->|"Uses"| SharedLib
    SharedCache -->|"Connects to"| RedisCache
    SharedDB -->|"Connects to"| PostgreSQL
    SharedMail -->|"Sends via"| ACS
    SharedVoIT -->|"Configures"| VoIT
    SharedC3 -->|"Implements"| C3
    SharedTelemetry -->|"Reports to"| AppInsights

    %% Core service interactions (Main API)
    MainContainer -->|"Host"| FastAPI
    FastAPI -->|"Delegate"| OAuth
    FastAPI -->|"Orchestrate"| LangGraph
    FastAPI -->|"Stream"| StreamAPI
    FastAPI -->|"Vault ops"| VaultAgent
    FastAPI -->|"Schedule digests"| DigestScheduler
    FastAPI -->|"Read emails"| GraphClient

    %% Teams Bot service interactions
    TeamsContainer -->|"Host"| BotFramework
    BotFramework -->|"Process NLP"| NLPEngine
    BotFramework -->|"Manage prefs"| UserPrefs
    BotFramework -->|"Track usage"| Analytics
    DigestWorker -->|"Consume queue"| ServiceBus
    MarketabilityWorker -->|"Consume queue"| ServiceBus

    %% Novel algorithms as cross-cutting layer
    FastAPI -.->|"Uses VoIT for\nall AI calls"| VoIT
    LangGraph -.->|"Optimized by"| VoIT
    VaultAgent -.->|"Optimized by"| VoIT
    NLPEngine -.->|"Optimized by"| VoIT
    DigestWorker -.->|"Optimized by"| VoIT
    VoIT -->|"Selects tier"| AzureOpenAI

    FastAPI -.->|"Uses C³ for\nall caching"| C3
    LangGraph -.->|"Optimized by"| C3
    VaultAgent -.->|"Optimized by"| C3
    DigestWorker -.->|"Optimized by"| C3
    C3 -->|"Manages"| RedisCache

    %% Data layer connections (Main API)
    FastAPI -->|"Cache I/O"| RedisCache
    FastAPI -->|"Persist"| PostgreSQL
    FastAPI -->|"Enqueue"| ServiceBus
    FastAPI -->|"Store files"| BlobStorage
    FastAPI -->|"Semantic search"| AISearch

    %% Data layer connections (Teams Bot)
    BotFramework -->|"Cache I/O"| RedisCache
    UserPrefs -->|"Store prefs"| PostgreSQL
    Analytics -->|"Store metrics"| PostgreSQL
    DigestWorker -->|"Query data"| PostgreSQL
    MarketabilityWorker -->|"Query vault"| ZohoCRM

    %% AI enrichment
    LangGraph -->|"Research"| Firecrawl
    FastAPI -->|"Enrich"| ApolloIO
    FastAPI -->|"Geocode"| AzureMaps
    VaultAgent -->|"Transcripts"| Zoom
    NLPEngine -->|"Intent classification"| AzureOpenAI
    DigestWorker -->|"Generate content"| AzureOpenAI

    %% External systems
    FastAPI -->|"Create records"| ZohoCRM
    BotFramework -->|"Send cards"| TeamsAPI
    OAuth -->|"Token refresh"| ZohoCRM
    VaultAgent -->|"Query candidates"| ZohoCRM
    DigestScheduler -->|"Send emails"| ACS
    DigestWorker -->|"Send emails"| ACS

    %% CI/CD
    GitHub -->|"Build + Push"| ACR
    GitHub -->|"Deploy"| MainContainer
    GitHub -->|"Deploy"| TeamsContainer
    Scripts -->|"Warmup"| FastAPI
    Scripts -->|"Warmup"| BotFramework
    Scripts -->|"Migrations"| PostgreSQL
```

### Intake Runtime (Primary Sequence)

```mermaid
sequenceDiagram
    participant User as Recruiter / Operator
    participant Addin as Outlook Add-in
    participant Proxy as OAuth Proxy
    participant API as FastAPI Core
    participant Redis as Redis Cache
    participant LLM as Azure OpenAI
    participant Enrich as Firecrawl / Apollo / Azure Maps
    participant PG as PostgreSQL
    participant Blob as Azure Blob
    participant Zoho as Zoho CRM

    User->>Addin: Confirm extracted values in taskpane
    Addin->>Proxy: HTTPS POST /intake (JWT + payload)
    Proxy->>API: Forward request with signed platform token
    API->>Redis: Check cached enrichment bundle
    Redis-->>API: Cache miss (first run)
    API->>LLM: Prompt LangGraph extraction + validation
    API->>Enrich: Fetch company, contact, and geocode data
    Enrich-->>API: Enrichment payloads (batched)
    API->>Blob: Upload attachments & taskpane notes
    API->>PG: Persist normalized deal package (JSONB + vectors)
    API->>Redis: Cache response for preview / retries
    API->>Zoho: Create/update Account, Contact, Deal
    Zoho-->>API: Confirm CRM operations
    API-->>Addin: Success payload with confidence scores
    Addin-->>User: Render confirmation banner + deep links
```

### VoIT + C³ Processing Flow (Universal Content Optimization)
**Applies to ALL content processing: email intake, vault agent, batch processing, etc.**

```mermaid
sequenceDiagram
    participant Client as Client/Curator
    participant Vault as Vault Agent API
    participant C3 as C³ Cache
    participant VoIT as VoIT Controller
    participant LLM as Azure OpenAI
    participant Tools as External Tools
    participant Redis as Redis Store

    Client->>Vault: POST /ingest (source, payload)
    Vault->>Vault: Normalize to canonical format
    Vault->>Vault: Generate embedding
    Vault->>Redis: Store canonical record
    Redis-->>Vault: VAULT-{uuid} locator
    Vault-->>Client: {locator, status: "ingested"}

    Client->>Vault: POST /publish (locator, channels)
    Vault->>Redis: Fetch canonical record
    Redis-->>Vault: Canonical data + embedding

    alt C³ Enabled
        Vault->>C3: Check cache (embed, fields)
        C3->>C3: Calculate margin (δ-bound)

        alt Cache Hit (margin > δ)
            C3-->>Vault: Reuse cached artifact
            Note over Vault: Skip VoIT processing
        else Selective Rebuild
            C3-->>Vault: Invalidated spans list
            Note over Vault: Process only stale spans
        end
    end

    alt VoIT Enabled
        Vault->>VoIT: Submit artifact_ctx with spans
        VoIT->>VoIT: Sort by uncertainty metrics

        loop For each span (budget > 0)
            VoIT->>VoIT: Evaluate actions (reuse/mini/tool/deep)
            VoIT->>VoIT: Calculate VOI = qgain - λ*cost - μ*latency

            alt Action: small LLM
                VoIT->>LLM: Call gpt-5-mini
                LLM-->>VoIT: Processed text (cost=1.0)
            else Action: tool
                VoIT->>Tools: Call Firecrawl/Apollo
                Tools-->>VoIT: Enriched text (cost=1.8)
            else Action: deep LLM
                VoIT->>LLM: Call gpt-5
                LLM-->>VoIT: High-quality text (cost=3.5)
            else Action: reuse
                VoIT->>VoIT: Use cached text (cost=0.01)
            end

            VoIT->>VoIT: Update span quality + budget
        end

        VoIT->>VoIT: Assemble final artifact
        VoIT-->>Vault: Assembled artifact + quality scores
    end

    alt C³ Enabled
        Vault->>C3: Save new cache entry
        C3->>Redis: Store with dependency cert
    end

    Vault->>Vault: Generate channel outputs
    Vault-->>Client: {published, results, cache_status}
```

### Service Bus Async Processing Flow
**Azure Service Bus message queues for batch processing and async workflows**

```mermaid
sequenceDiagram
    participant Client as API Client/Scheduler
    participant MainAPI as Main API (Port 8000)
    participant ServiceBus as Azure Service Bus
    participant EmailQueue as email-batch-queue
    participant DigestQueue as digest-queue
    participant VaultQueue as vault-marketability-queue
    participant DeadLetter as Dead Letter Queue
    participant TeamsWorker as Teams Bot Worker
    participant VaultWorker as Vault Worker (Main API)
    participant KEDA as KEDA Scaler
    participant PostgreSQL as PostgreSQL
    participant Redis as Redis Cache
    participant ZohoCRM as Zoho CRM

    Note over Client,ZohoCRM: Email Batch Processing Flow

    Client->>MainAPI: POST /batch/submit<br/>{emails: [50 emails]}
    MainAPI->>PostgreSQL: Create batch_job record<br/>status: pending
    PostgreSQL-->>MainAPI: batch_id: abc-123

    loop For each email in batch
        MainAPI->>EmailQueue: Send message<br/>{email_id, batch_id}
    end

    MainAPI-->>Client: 202 Accepted<br/>{batch_id: "abc-123"}

    Note over ServiceBus,KEDA: KEDA Auto-Scaling

    KEDA->>EmailQueue: Poll queue depth
    EmailQueue-->>KEDA: 50 messages pending
    KEDA->>MainAPI: Scale to 3 replicas

    Note over VaultWorker: Batch Worker Processing

    loop Process messages (batch=10)
        VaultWorker->>EmailQueue: Receive 10 messages<br/>(PeekLock mode)
        EmailQueue-->>VaultWorker: Message batch

        loop For each message
            VaultWorker->>VaultWorker: Extract + enrich email

            alt Success
                VaultWorker->>ZohoCRM: Create CRM records
                VaultWorker->>PostgreSQL: Update batch_item<br/>status: success
                VaultWorker->>EmailQueue: Complete message
            else Transient Error
                VaultWorker->>VaultWorker: Retry (3 attempts)
                alt Max retries exceeded
                    VaultWorker->>EmailQueue: Abandon message
                    EmailQueue->>DeadLetter: Move to dead letter
                    VaultWorker->>PostgreSQL: Update batch_item<br/>status: failed, error_details
                end
            end
        end
    end

    VaultWorker->>PostgreSQL: Update batch_job<br/>status: completed
    VaultWorker->>Redis: Invalidate cache keys

    Note over Client,ZohoCRM: Teams Digest Generation Flow

    Client->>TeamsWorker: Chat message: "digest advisors"
    TeamsWorker->>TeamsWorker: Parse intent (GPT-5-mini)
    TeamsWorker->>DigestQueue: Send message<br/>{user_id, audience: "advisors"}
    TeamsWorker-->>Client: "Generating digest..."

    TeamsWorker->>DigestQueue: Receive message
    DigestQueue-->>TeamsWorker: {user_id, audience}

    TeamsWorker->>Redis: Check cache<br/>key: vault:digest:advisors

    alt Cache miss
        TeamsWorker->>ZohoCRM: Query vault candidates<br/>(Leads module, custom view)
        ZohoCRM-->>TeamsWorker: 164 vault records
        TeamsWorker->>TeamsWorker: Apply VoIT/C³ optimization
        TeamsWorker->>TeamsWorker: Generate digest cards
        TeamsWorker->>Redis: Cache digest (24h TTL)
    else Cache hit
        Redis-->>TeamsWorker: Cached digest
    end

    TeamsWorker->>Client: Send Adaptive Card<br/>(Microsoft Teams API)
    TeamsWorker->>PostgreSQL: Record delivery<br/>weekly_digest_deliveries
    TeamsWorker->>DigestQueue: Complete message

    Note over Client,ZohoCRM: Vault Marketability Worker Flow

    Client->>TeamsWorker: "Give me 10 most marketable candidates"
    TeamsWorker->>VaultQueue: Send message<br/>{user_id, query_text}
    TeamsWorker-->>Client: "Analyzing vault..."

    VaultWorker->>VaultQueue: Receive message
    VaultQueue-->>VaultWorker: {user_id, query_text}

    VaultWorker->>ZohoCRM: Query all vault candidates<br/>(GET /crm/v8/Leads?cvid=6221978000090941003)
    ZohoCRM-->>VaultWorker: 164 candidates

    VaultWorker->>VaultWorker: Score candidates<br/>(MarketabilityScorer algorithm)
    VaultWorker->>VaultWorker: Rank by composite score<br/>(financial + evidence + sentiment)
    VaultWorker->>VaultWorker: Take top 10
    VaultWorker->>VaultWorker: Anonymize data (PRIVACY_MODE)

    VaultWorker->>Client: Send ranked results<br/>(Adaptive Card with 10 candidates)
    VaultWorker->>PostgreSQL: Record analytics
    VaultWorker->>VaultQueue: Complete message

    Note over DeadLetter: Dead Letter Queue Processing

    Client->>MainAPI: POST /batch/deadletter/process
    MainAPI->>DeadLetter: Receive failed messages
    DeadLetter-->>MainAPI: {failed_messages: []}

    loop For each failed message
        MainAPI->>MainAPI: Analyze error

        alt Retriable error
            MainAPI->>EmailQueue: Re-enqueue message
            MainAPI->>DeadLetter: Complete DLQ message
        else Permanent error
            MainAPI->>PostgreSQL: Log permanent failure
            MainAPI->>DeadLetter: Complete DLQ message
        end
    end

    MainAPI-->>Client: {reprocessed: 15, skipped: 3}

    Note over KEDA: Auto-scaling Down

    KEDA->>EmailQueue: Poll queue depth
    EmailQueue-->>KEDA: 0 messages pending
    KEDA->>MainAPI: Scale to 0 replicas<br/>(idle workers terminated)
```

### Container Responsibilities (C4 Level 2)

```mermaid
flowchart TB
    classDef container fill:#FFFFFF,stroke:#0F172A,color:#111827,stroke-width:2px;
    classDef ext fill:#F3E8FF,stroke:#7C3AED,color:#4C1D95,stroke-width:2px;
    classDef data fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:2px;
    classDef intelligent fill:#FED7D7,stroke:#E53E3E,color:#742A2A,stroke-width:2px;

    subgraph AddIn["Outlook Taskpane"]
        UI["Taskpane UI\n(Vanilla JS + Office.js)"]
        Commands["Command Surface\n(Ribbon buttons)"]
        Manifest["Manifest + Assets"]
    end
    class AddIn,UI,Commands,Manifest container;

    subgraph Proxy["OAuth Proxy"]
        FlaskApp["Flask App"]
        TokenSvc["Token Broker\n(Zoho + internal)"]
        Policy["Policy Guardrails\n(IP allow list, rate limits)"]
    end
    class Proxy,FlaskApp,TokenSvc,Policy container;

    subgraph NovelOptimization["🚨 Novel Optimization Algorithms (Cross-Cutting)"]
        VoITLayer["VoIT Layer\n(Budget allocation, VOI calc, tier selection)"]
        C3Layer["C³ Layer\n(Probabilistic reuse, margin calc)"]
    end
    class NovelOptimization,VoITLayer,C3Layer intelligent;

    subgraph FastAPI["FastAPI Core"]
        Router["API Routers\n(/intake, /cache, /health, /vault-agent)"]
        LangGraph["LangGraph Orchestrator"]
        VaultRouter["Vault Agent Router\n(/ingest, /publish, /status)"]
        Services["Domain Services\n(normalizers, dedupe)"]
        Integrations["Integration Clients\n(Zoho, Firecrawl, Apollo, Maps)"]
        Background["Background Tasks\n(cache warmers, backfills)"]
        Telemetry["Telemetry\n(logging, metrics)"]
    end
    class FastAPI,Router,LangGraph,Services,Integrations,Background,Telemetry,VaultRouter container;

    subgraph VaultAgent["Candidate Vault Agent (CRM Formatter)"]
        Aggregator["Data Aggregator\n(Zoho vault + enrichment)"]
        Formatter["Digest Formatter\n(Brandon's locked format)"]
        Validator["Format Validator\n(Emoji + bullet rules)"]
    end
    class VaultAgent,Aggregator,Formatter,Validator container;

    subgraph TeamsBotContainer["Teams Bot Service (Port 8001)"]
        BotSDK["Bot Framework SDK\n(Activity handlers, Dialog state)"]
        NLPEngine["Natural Language Engine\n(Intent classification, GPT-5-mini)"]
        CommandHandler["Command Handlers\n(/digest, /preferences, /analytics, /help)"]
        DigestWorker["Digest Worker\n(Service Bus consumer)"]
        MarketWorker["Marketability Worker\n(Vault candidate ranking)"]
        UserPrefs["User Preferences Manager\n(PostgreSQL + Teams state)"]
        Analytics["Analytics Tracker\n(Conversation metrics)"]
        ProactiveMsg["Proactive Messaging\n(Weekly digest delivery)"]
    end
    class TeamsBotContainer,BotSDK,NLPEngine,CommandHandler,DigestWorker,MarketWorker,UserPrefs,Analytics,ProactiveMsg container;

    subgraph DataPlane["Data Plane"]
        RedisNode["Redis\n(C³ entries + standard cache)"]
        Postgres["PostgreSQL + pgvector\n(Embeddings + canonical records)"]
        BlobStore["Azure Blob\n(attachments, manifests)"]
    end
    class DataPlane,RedisNode,Postgres,BlobStore data;

    subgraph External["External Systems"]
        ZohoAPI["Zoho CRM"]
        OpenAIAPI["Azure OpenAI\n(GPT-5 nano/mini/large)"]
        FirecrawlAPI["Firecrawl"]
        ApolloAPI["Apollo.io"]
        MapsAPI["Azure Maps"]
        KeyVault["Azure Key Vault"]
        Insights["Application Insights"]
    end
    class External,ZohoAPI,OpenAIAPI,FirecrawlAPI,ApolloAPI,MapsAPI,KeyVault,Insights ext;

    UI --> FlaskApp
    Commands --> FlaskApp
    Manifest --> BlobStore
    FlaskApp --> Policy
    Policy --> TokenSvc
    TokenSvc --> Router
    Router --> LangGraph
    Router --> VaultRouter

    %% Novel algorithms as cross-cutting layers
    LangGraph -.->|"Uses"| VoITLayer
    LangGraph -.->|"Uses"| C3Layer
    VaultRouter -.->|"Uses"| VoITLayer
    VaultRouter -.->|"Uses"| C3Layer
    Integrations -.->|"Uses"| VoITLayer
    Services -.->|"Uses"| C3Layer

    VoITLayer -->|"Selects tier"| OpenAIAPI
    C3Layer -->|"Manages"| RedisNode

    %% Vault Agent specific
    VaultRouter --> Aggregator
    Aggregator --> Formatter
    Formatter --> Validator
    Aggregator --> ZohoAPI
    Aggregator --> Postgres

    LangGraph --> Services
    Services --> Integrations
    Services --> Postgres
    Integrations --> ZohoAPI
    Integrations --> FirecrawlAPI
    Integrations --> ApolloAPI
    Integrations --> MapsAPI
    Background --> RedisNode
    Background --> BlobStore
    TokenSvc --> KeyVault
    TokenSvc --> ZohoAPI
    Router --> Telemetry
    Telemetry --> Insights

    %% Teams Bot connections
    BotSDK --> NLPEngine
    BotSDK --> CommandHandler
    NLPEngine -.->|"Uses"| VoITLayer
    CommandHandler --> DigestWorker
    CommandHandler --> UserPrefs
    DigestWorker -.->|"Uses"| VoITLayer
    DigestWorker -.->|"Uses"| C3Layer
    DigestWorker --> ZohoAPI
    MarketWorker -.->|"Uses"| VoITLayer
    MarketWorker --> ZohoAPI
    UserPrefs --> Postgres
    Analytics --> Postgres
    ProactiveMsg --> UserPrefs
    ProactiveMsg --> DigestWorker
    DigestWorker --> RedisNode
    MarketWorker --> RedisNode
    NLPEngine --> Postgres
    NLPEngine --> RedisNode
```

### Teams Bot Service Architecture (C4 Level 2)
**Dedicated container service for Microsoft Teams integration**

```mermaid
flowchart TB
    classDef container fill:#FFFFFF,stroke:#0F172A,color:#111827,stroke-width:2px;
    classDef ext fill:#F3E8FF,stroke:#7C3AED,color:#4C1D95,stroke-width:2px;
    classDef data fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:2px;
    classDef intelligent fill:#FED7D7,stroke:#E53E3E,color:#742A2A,stroke-width:2px;
    classDef shared fill:#F0FDFA,stroke:#14B8A6,color:#134E4A,stroke-width:2px;

    subgraph TeamsClient["Microsoft Teams Client"]
        UserChat["User Chat Interface"]
        BotConversation["Bot Conversation Thread"]
        AdaptiveCardsUI["Adaptive Cards Renderer"]
    end
    class TeamsClient,UserChat,BotConversation,AdaptiveCardsUI ext;

    subgraph TeamsBotContainer["Teams Bot Container (Port 8001)\nteams_bot/app/"]
        direction TB

        subgraph APILayer["API Layer (teams_bot/app/api/)"]
            HealthEndpoint["health_check.py\n(Health probe)"]
            TeamsRoutes["teams/routes.py\n(Bot endpoints)"]
        end

        subgraph BotCore["Bot Framework Layer"]
            BotFramework["Bot Framework SDK\n(Activity handler)"]
            DialogManager["Dialog Manager\n(Conversation state)"]
            AdaptiveCardsBuilder["Adaptive Cards Builder\n(Dynamic card generation)"]
        end

        subgraph NLPLayer["Natural Language Processing"]
            IntentClassifier["Intent Classifier\n(GPT-5-mini)\nclassify user intent"]
            QueryBuilder["SQL Query Builder\n(Dynamic query generation)"]
            ResponseFormatter["Response Formatter\n(Natural language output)"]
        end

        subgraph CommandHandlers["Command Handlers"]
            DigestCmd["Digest Command\n(/digest [audience])"]
            PrefsCmd["Preferences Command\n(/preferences)"]
            AnalyticsCmd["Analytics Command\n(/analytics)"]
            HelpCmd["Help Command\n(/help)"]
        end

        subgraph Workers["Service Bus Workers (teams_bot/app/workers/)"]
            DigestWorker["digest_worker.py\n(Consume digest-queue)"]
            MarketabilityWorker["nlp_worker.py\n(Consume vault-marketability-queue)"]
        end

        subgraph Services["Business Services (teams_bot/app/services/)"]
            ProactiveMsg["proactive_messaging.py\n(Send cards without user prompt)"]
            MessageBus["message_bus.py\n(Service Bus integration)"]
            CircuitBreaker["circuit_breaker.py\n(Fault tolerance)"]
        end

        subgraph DataLayer["Data Access"]
            UserPrefsRepo["User Preferences Repository\n(PostgreSQL)"]
            AnalyticsRepo["Analytics Repository\n(Conversation metrics)"]
            DeliveryRepo["Digest Delivery Repository\n(Tracking)"]
        end
    end
    class TeamsRoutes,HealthEndpoint,BotFramework,DialogManager,AdaptiveCardsBuilder,IntentClassifier,QueryBuilder,ResponseFormatter,DigestCmd,PrefsCmd,AnalyticsCmd,HelpCmd,DigestWorker,MarketabilityWorker,ProactiveMsg,MessageBus,CircuitBreaker,UserPrefsRepo,AnalyticsRepo,DeliveryRepo container;

    subgraph SharedLibrary["Shared Library (well_shared/)"]
        SharedRedis["cache/redis_manager.py"]
        SharedDB["database/connection.py"]
        SharedMail["mail/sender.py"]
        SharedVoIT["config/voit_config.py"]
        SharedC3["cache/c3.py"]
    end
    class SharedLibrary,SharedRedis,SharedDB,SharedMail,SharedVoIT,SharedC3 shared;

    subgraph OptimizationLayer["Optimization Algorithms"]
        VoITOpt["VoIT Algorithm\n(Adaptive model selection)"]
        C3Opt["C³ Algorithm\n(Probabilistic caching)"]
    end
    class OptimizationLayer,VoITOpt,C3Opt intelligent;

    subgraph ExternalDeps["External Dependencies"]
        TeamsAPI["Microsoft Teams API\n(Bot Framework + Cards)"]
        PostgreSQL["Azure PostgreSQL\n(User prefs, analytics)"]
        RedisCache["Azure Redis\n(Cache + sessions)"]
        ServiceBusQueue["Azure Service Bus\n(digest-queue,\nvault-marketability-queue)"]
        MainAPI["Main API\n(well-intake-api)\nPort 8000"]
        ZohoCRM["Zoho CRM\n(Vault candidates)"]
        AzureOpenAI["Azure OpenAI\n(Intent classification)"]
        ACS["Azure Communication Services\n(Email delivery)"]
    end
    class TeamsAPI,PostgreSQL,RedisCache,ServiceBusQueue,MainAPI,ZohoCRM,AzureOpenAI,ACS ext;

    %% User interaction flows
    UserChat -->|"Send message"| TeamsAPI
    TeamsAPI -->|"Activity events"| BotFramework
    BotFramework -->|"Parse intent"| IntentClassifier

    %% Command routing
    IntentClassifier -->|"/digest"| DigestCmd
    IntentClassifier -->|"/preferences"| PrefsCmd
    IntentClassifier -->|"/analytics"| AnalyticsCmd
    IntentClassifier -->|"/help"| HelpCmd
    IntentClassifier -->|"Natural language"| QueryBuilder

    %% Natural language processing
    QueryBuilder -->|"SQL query"| UserPrefsRepo
    QueryBuilder -->|"SQL query"| AnalyticsRepo
    QueryBuilder -.->|"Uses VoIT"| VoITOpt
    VoITOpt -->|"Select model"| AzureOpenAI
    AzureOpenAI -->|"Results"| ResponseFormatter
    ResponseFormatter -->|"Format response"| BotFramework

    %% Command execution
    DigestCmd -->|"Enqueue request"| MessageBus
    MessageBus -->|"Send message"| ServiceBusQueue
    PrefsCmd -->|"Read/Write"| UserPrefsRepo
    AnalyticsCmd -->|"Query"| AnalyticsRepo
    HelpCmd -->|"Static response"| BotFramework

    %% Worker processing
    DigestWorker -->|"Consume"| ServiceBusQueue
    MarketabilityWorker -->|"Consume"| ServiceBusQueue
    DigestWorker -->|"Query vault"| ZohoCRM
    DigestWorker -.->|"Uses VoIT/C³"| VoITOpt
    DigestWorker -.->|"Uses C³"| C3Opt
    DigestWorker -->|"Generate digest"| AdaptiveCardsBuilder
    MarketabilityWorker -->|"Query vault"| ZohoCRM
    MarketabilityWorker -.->|"Uses VoIT"| VoITOpt
    MarketabilityWorker -->|"Rank candidates"| ResponseFormatter

    %% Adaptive Cards generation
    AdaptiveCardsBuilder -->|"Build card JSON"| BotFramework
    BotFramework -->|"Send activity"| TeamsAPI
    TeamsAPI -->|"Render cards"| AdaptiveCardsUI

    %% Proactive messaging
    ProactiveMsg -->|"Send without prompt"| TeamsAPI
    ProactiveMsg -->|"Track delivery"| DeliveryRepo

    %% Shared library usage
    UserPrefsRepo -.->|"Uses"| SharedDB
    AnalyticsRepo -.->|"Uses"| SharedDB
    IntentClassifier -.->|"Uses"| SharedRedis
    DigestWorker -.->|"Uses"| SharedMail
    MarketabilityWorker -.->|"Uses"| SharedRedis

    %% Data layer connections
    UserPrefsRepo -->|"Store/Retrieve"| PostgreSQL
    AnalyticsRepo -->|"Store/Retrieve"| PostgreSQL
    DeliveryRepo -->|"Store/Retrieve"| PostgreSQL
    IntentClassifier -->|"Cache I/O"| RedisCache
    DigestWorker -->|"Cache I/O"| RedisCache
    SharedDB -->|"Connect"| PostgreSQL
    SharedRedis -->|"Connect"| RedisCache
    SharedMail -->|"Send"| ACS

    %% Cross-service communication
    DigestCmd -->|"Fallback API call"| MainAPI
    MarketabilityWorker -->|"Fallback API call"| MainAPI

    %% Circuit breaker
    MessageBus -.->|"Protected by"| CircuitBreaker
    ProactiveMsg -.->|"Protected by"| CircuitBreaker

    %% Health probes
    HealthEndpoint -->|"Check"| PostgreSQL
    HealthEndpoint -->|"Check"| RedisCache
    HealthEndpoint -->|"Check"| ServiceBusQueue
```

### Shared Library Architecture (C4 Level 3)
**Common utilities library consumed by all services (well_shared/)**

```mermaid
flowchart TB
    classDef service fill:#E0E7FF,stroke:#4338CA,color:#1E1B4B,stroke-width:2px;
    classDef module fill:#DCFCE7,stroke:#059669,color:#064E3B,stroke-width:2px;
    classDef external fill:#FCE7F3,stroke:#C026D3,color:#701A75,stroke-width:2px;
    classDef config fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:2px;

    subgraph Consumers["Service Consumers"]
        MainAPI["Main API Service\n(well-intake-api)\nPort 8000"]
        TeamsBot["Teams Bot Service\n(teams-bot)\nPort 8001"]
        VaultAgent["Vault Agent Service\n(Future)\nPort 8002"]
    end
    class Consumers,MainAPI,TeamsBot,VaultAgent service;

    subgraph SharedLibrary["well_shared/ Package"]
        direction TB

        subgraph CacheModules["cache/ - Caching Abstractions"]
            RedisManager["redis_manager.py\n• Connection pooling\n• Key namespacing (intake:*, vault:*)\n• Batch operations (mget, mset)\n• Health checks\n• TTL management (2h-7d)\n• Automatic reconnection"]

            C3Module["c3.py\n• C³ Algorithm implementation\n• Probabilistic margin calculation\n• Embedding similarity (δ-bound)\n• Selective rebuild logic\n• Dependency certificates\n• Entry serialization"]

            VoITCache["voit.py\n• VoIT span caching\n• Uncertainty metrics storage\n• Action history tracking\n• Budget persistence\n• Quality score caching"]
        end

        subgraph DatabaseModules["database/ - Database Abstractions"]
            Connection["connection.py\n• Async SQLAlchemy sessions\n• Connection pooling (10-20 conns)\n• Retry logic with exponential backoff\n• Transaction management\n• Health checks\n• pgvector support"]
        end

        subgraph MailModules["mail/ - Email Delivery"]
            Sender["sender.py\n• Azure Communication Services\n• Email templating\n• Attachment handling\n• Delivery tracking\n• Retry logic (3 attempts)\n• Rate limiting\n• Batch send support"]
        end

        subgraph EvidenceModules["evidence/ - Evidence Extraction"]
            Extractor["extractor.py\n• Bullet point generation\n• Financial pattern detection\n• Source attribution\n• Confidence scoring\n• Hallucination prevention\n• Evidence linking"]
        end

        subgraph TelemetryModules["telemetry/ - Observability"]
            Insights["insights.py\n• Application Insights client\n• Structured logging\n• Custom metrics (VOI, cache hit)\n• Trace correlation\n• Exception tracking\n• Performance profiling\n• Batch telemetry (15s interval)"]
        end

        subgraph ConfigModules["config/ - Configuration Management"]
            VoITConfig["voit_config.py\n• Model tier costs (nano/mini/large)\n• Budget defaults (5.0 units)\n• Quality targets (0.9)\n• Cost weights (λ=0.3, μ=0.2)\n• Uncertainty thresholds\n• Action costs (reuse=0.01, tool=1.8, deep=3.5)"]
        end

        subgraph ZohoModules["zoho/ - Zoho Utilities"]
            ZohoCommon["__init__.py\n• Shared Zoho constants\n• Field mappings reference\n• Common schemas\n• Error handling patterns"]
        end
    end
    class CacheModules,DatabaseModules,MailModules,EvidenceModules,TelemetryModules,ConfigModules,ZohoModules module;
    class RedisManager,C3Module,VoITCache,Connection,Sender,Extractor,Insights,VoITConfig,ZohoCommon module;

    subgraph ExternalServices["External Dependencies"]
        AzureRedis["Azure Cache for Redis\n(Standard C1, 1GB)"]
        PostgreSQL["Azure PostgreSQL Flexible\n(pgvector, 400K context)"]
        ACS["Azure Communication Services\n(Email delivery)"]
        AppInsights["Application Insights\n(Telemetry sink)"]
    end
    class ExternalServices,AzureRedis,PostgreSQL,ACS,AppInsights external;

    subgraph SetupConfig["Package Configuration"]
        SetupPy["setup.py\n• Package metadata\n• Dependencies\n• Entry points\n• Version: 0.1.0"]

        RequirementsTxt["requirements.txt\n• redis>=4.5.0\n• sqlalchemy>=2.0.0\n• azure-communication-email\n• azure-monitor-opentelemetry"]
    end
    class SetupConfig,SetupPy,RequirementsTxt config;

    %% Service consumption
    MainAPI -.->|"pip install -e well_shared/\n(Editable mode for dev)"| SharedLibrary
    TeamsBot -.->|"pip install -e well_shared/\n(Editable mode for dev)"| SharedLibrary
    VaultAgent -.->|"pip install -e well_shared/\n(Editable mode for dev)"| SharedLibrary

    %% Cache module connections
    MainAPI -->|"Import & use"| RedisManager
    MainAPI -->|"Import & use"| C3Module
    MainAPI -->|"Import & use"| VoITCache
    TeamsBot -->|"Import & use"| RedisManager
    TeamsBot -->|"Import & use"| C3Module
    VaultAgent -->|"Import & use"| RedisManager
    VaultAgent -->|"Import & use"| C3Module
    VaultAgent -->|"Import & use"| VoITCache

    %% Database module connections
    MainAPI -->|"Import & use"| Connection
    TeamsBot -->|"Import & use"| Connection
    VaultAgent -->|"Import & use"| Connection

    %% Mail module connections
    MainAPI -->|"Import & use"| Sender
    TeamsBot -->|"Import & use"| Sender
    VaultAgent -->|"Import & use"| Sender

    %% Evidence module connections
    MainAPI -->|"Import & use"| Extractor
    VaultAgent -->|"Import & use"| Extractor

    %% Telemetry module connections
    MainAPI -->|"Import & use"| Insights
    TeamsBot -->|"Import & use"| Insights
    VaultAgent -->|"Import & use"| Insights

    %% Config module connections
    MainAPI -->|"Import & use"| VoITConfig
    TeamsBot -->|"Import & use"| VoITConfig
    VaultAgent -->|"Import & use"| VoITConfig

    %% Zoho module connections
    MainAPI -->|"Import & use"| ZohoCommon
    TeamsBot -->|"Import & use"| ZohoCommon
    VaultAgent -->|"Import & use"| ZohoCommon

    %% External service connections
    RedisManager -->|"Connect via\nredis.asyncio"| AzureRedis
    C3Module -->|"Store entries"| AzureRedis
    VoITCache -->|"Cache spans"| AzureRedis
    Connection -->|"Async sessions\nsqlalchemy.ext.asyncio"| PostgreSQL
    Sender -->|"Send emails\nazure.communication.email"| ACS
    Insights -->|"Send telemetry\nazure.monitor.opentelemetry"| AppInsights

    %% Setup configuration
    SetupPy -.->|"Defines dependencies"| RequirementsTxt
    SharedLibrary -.->|"Installed via"| SetupPy

    %% Usage notes
    note1["Usage Pattern:\n1. Install in editable mode: cd well_shared && pip install -e .\n2. Import in services: from well_shared.cache import redis_manager\n3. Changes to well_shared/ immediately available to all services\n4. Single source of truth for common utilities"]
    class note1 config;
```

### FastAPI Core Component Map (C4 Level 3)

```mermaid
flowchart LR
    classDef comp fill:#EFF6FF,stroke:#1D4ED8,color:#0B1F4B,stroke-width:2px;
    classDef boundary stroke:#0F172A,stroke-width:2px,fill:#FFFFFF,color:#111827;
    classDef intelligent fill:#FED7D7,stroke:#E53E3E,color:#742A2A,stroke-width:2px;

    subgraph Boundary["FastAPI Service"]
        subgraph RouterLayer["Router Layer"]
            Public["Public Routers\n(intake, attachments)"]
            Internal["Internal Routers\n(cache, warmup, health)"]
            VaultRoutes["Vault Agent Routes\n(/ingest, /publish, /status)"]
        end
        subgraph IntelligentLayer["Intelligent Optimization"]
            VoITController["VoIT Controller\n(VOI calculation, budget allocation)"]
            C3Manager["C³ Cache Manager\n(reuse-or-rebuild, margin calc)"]
            SpanProcessor["Span Processor\n(uncertainty metrics, action selection)"]
        end
        subgraph WorkflowLayer["Workflow & Domain"]
            GraphMgr["LangGraph Manager\n(orchestrates extract -> enrich -> validate)"]
            Rules["Business Rules\n(deal naming, dedupe, gating)"]
            Normalizers["Normalizers\n(email -> CRM schema, canonical format)"]
            Confidence["Confidence Engine\n(scoring + human overrides)"]
        end
        subgraph IntegrationLayer["Integration Adapters"]
            ZohoClient["Zoho Client"]
            FirecrawlClient["Firecrawl Client"]
            ApolloClient["Apollo Client"]
            MapsClient["Azure Maps Client"]
            OpenAIClient["Azure OpenAI Client\n(GPT-5 nano/mini/large)"]
        end
        subgraph PersistenceLayer["Persistence & Cache"]
            Repo["Repository Layer\n(SQLModel + pgvector)"]
            CacheMgr["Cache Manager\n(Redis IO, TTL policy)"]
            C3Storage["C³ Storage\n(entry serialization, Redis ops)"]
            BlobSvc["Attachment Service\n(Blob uploads + metadata)"]
        end
        subgraph ObservabilityLayer["Observability"]
            Logging["Structured Logging"]
            Metrics["Metrics Exporters\n(VOI, cache hit rate, quality)"]
            Alerts["Alert Hooks\n(health + SLA)"]
        end
    end
    class Boundary,RouterLayer,WorkflowLayer,IntegrationLayer,PersistenceLayer,ObservabilityLayer,IntelligentLayer boundary;
    class Public,Internal,GraphMgr,Rules,Normalizers,Confidence,ZohoClient,FirecrawlClient,ApolloClient,MapsClient,OpenAIClient,Repo,CacheMgr,BlobSvc,Logging,Metrics,Alerts comp;
    class VaultRoutes,VoITController,C3Manager,SpanProcessor,C3Storage intelligent;

    Public --> GraphMgr
    Internal --> CacheMgr
    VaultRoutes --> Normalizers
    VaultRoutes --> C3Manager
    C3Manager --> C3Storage
    C3Manager --> VoITController
    VoITController --> SpanProcessor
    SpanProcessor --> OpenAIClient
    SpanProcessor --> FirecrawlClient
    SpanProcessor --> ApolloClient
    GraphMgr --> Rules
    GraphMgr --> Normalizers
    GraphMgr --> Confidence
    Rules --> Repo
    Normalizers --> Repo
    Confidence --> CacheMgr
    CacheMgr --> Repo
    C3Storage --> CacheMgr
    Repo --> ZohoClient
    ZohoClient --> Repo
    GraphMgr --> OpenAIClient
    GraphMgr --> FirecrawlClient
    GraphMgr --> ApolloClient
    GraphMgr --> MapsClient
    BlobSvc --> Repo
    BlobSvc --> CacheMgr
    Logging --> Metrics
    Metrics --> Alerts
    Public --> Logging
    Public --> Metrics
    VaultRoutes --> Logging
    VaultRoutes --> Metrics
```

### C³ Cache Reuse-or-Rebuild Decision Logic

```mermaid
flowchart TD
    Start([Inbound Publish Request]) --> LoadCache{C³ Entry<br/>Exists?}

    LoadCache -->|No| FullBuild[Full Build Path]
    LoadCache -->|Yes| CalcMargin["Calculate Margin<br/>δ = 1 - P(risk)"]

    CalcMargin --> CompareEmbed[Compare Embedding<br/>Similarity]
    CompareEmbed --> CheckFields{Field<br/>Drift?}

    CheckFields -->|High drift| SelectiveRebuild[Selective Rebuild]
    CheckFields -->|Low drift| CheckMargin{"Margin ><br/>δ-bound?"}

    CheckMargin -->|Yes| CacheHit[✓ Reuse Cached Artifact]
    CheckMargin -->|No| SelectiveRebuild

    SelectiveRebuild --> IdentifySpans[Identify Invalidated Spans]
    IdentifySpans --> VoITProcess[VoIT Span Processing]

    FullBuild --> CreateSpans[Create Span Context]
    CreateSpans --> VoITProcess

    VoITProcess --> SortSpans["Sort by Uncertainty<br/>retrieval_dispersion +<br/>rule_conflicts + c3_margin"]

    SortSpans --> BudgetLoop{"Budget > 0 &<br/>Quality < Target?"}

    BudgetLoop -->|Yes| EvalActions["Evaluate Actions:<br/>1. Reuse cached<br/>2. Small LLM<br/>3. Tool call<br/>4. Deep LLM"]

    EvalActions --> CalcVOI["Calculate VOI:<br/>qgain - λ*cost - μ*latency"]
    CalcVOI --> SelectAction[Select Max VOI Action]
    SelectAction --> ApplyAction[Apply Action]
    ApplyAction --> UpdateQuality[Update Span Quality<br/>Deduct Budget]
    UpdateQuality --> BudgetLoop

    BudgetLoop -->|No| Assemble[Assemble Artifact]
    CacheHit --> GenerateOutput[Generate Channel Outputs]
    Assemble --> SaveC3[Save to C³ Cache]
    SaveC3 --> GenerateOutput

    GenerateOutput --> Return([Return Results])

    style CacheHit fill:#90EE90,stroke:#006400,stroke-width:3px
    style SelectiveRebuild fill:#FFD700,stroke:#B8860B,stroke-width:3px
    style FullBuild fill:#FFA07A,stroke:#8B0000,stroke-width:3px
    style VoITProcess fill:#FFB6C1,stroke:#C71585,stroke-width:3px
```

### Zoom Integration Sequence
**Server-to-Server OAuth 2.0 flow with meeting transcript extraction**

```mermaid
sequenceDiagram
    participant User as Recruiter/TalentWell Curator
    participant App as Main API/TalentWell Curator
    participant ZoomClient as zoom_client.py
    participant ZoomAuth as Zoom OAuth Server
    participant ZoomAPI as Zoom REST API v2
    participant Redis as Redis Cache
    participant PostgreSQL as PostgreSQL
    participant VaultAgent as Vault Agent

    Note over User,VaultAgent: OAuth 2.0 Server-to-Server Authentication

    App->>ZoomClient: Request access token
    ZoomClient->>Redis: Check cached token<br/>key: zoom:token

    alt Token cached and valid
        Redis-->>ZoomClient: Return cached token
    else Token expired or missing
        ZoomClient->>ZoomAuth: POST /oauth/token<br/>grant_type: account_credentials<br/>account_id: {ZOOM_ACCOUNT_ID}<br/>client_id: {ZOOM_CLIENT_ID}<br/>client_secret: {ZOOM_CLIENT_SECRET}
        ZoomAuth-->>ZoomClient: {access_token, expires_in: 3600}
        ZoomClient->>Redis: Cache token (59 min TTL)
        Redis-->>ZoomClient: OK
    end

    Note over User,VaultAgent: List Meeting Recordings

    User->>App: Request: "Get recordings from last month"
    App->>ZoomClient: list_recordings(from_date, to_date)
    ZoomClient->>ZoomClient: Prepare auth headers<br/>Authorization: Bearer {token}

    ZoomClient->>ZoomAPI: GET /users/me/recordings<br/>from={from_date}&to={to_date}<br/>&page_size=30
    ZoomAPI-->>ZoomClient: {meetings: [{uuid, topic, start_time,<br/>duration, recording_count}], next_page_token}

    loop Has more pages
        ZoomClient->>ZoomAPI: GET /users/me/recordings<br/>next_page_token={token}
        ZoomAPI-->>ZoomClient: {meetings: [...], next_page_token}
    end

    ZoomClient-->>App: List of 150 meetings
    App-->>User: Display meetings list

    Note over User,VaultAgent: Fetch Transcript for Specific Meeting

    User->>App: Select meeting: "Candidate John Doe - Advisory Role"
    App->>ZoomClient: fetch_zoom_transcript_for_meeting(meeting_id)

    ZoomClient->>Redis: Check transcript cache<br/>key: zoom:transcript:{meeting_id}

    alt Transcript cached
        Redis-->>ZoomClient: Cached transcript JSON
        ZoomClient-->>App: Transcript data
    else Transcript not cached
        ZoomClient->>ZoomAPI: GET /meetings/{meeting_id}/recordings
        ZoomAPI-->>ZoomClient: {recording_files: [{id, file_type,<br/>download_url, recording_type}]}

        ZoomClient->>ZoomClient: Find VTT transcript file<br/>(file_type: "TRANSCRIPT",<br/>recording_type: "audio_transcript")

        alt VTT transcript found
            ZoomClient->>ZoomAPI: GET {download_url}<br/>Authorization: Bearer {token}
            ZoomAPI-->>ZoomClient: VTT file content

            ZoomClient->>ZoomClient: Parse VTT to JSON<br/>{segments: [{start_time, text, speaker}]}
            ZoomClient->>Redis: Cache transcript (7d TTL)
            Redis-->>ZoomClient: OK
        else No transcript available
            ZoomClient-->>App: {error: "No transcript found"}
            App-->>User: "Transcript not available for this meeting"
        end

        alt Retry on transient errors
            Note over ZoomClient: 5xx errors or network issues
            ZoomClient->>ZoomClient: Exponential backoff<br/>(1s, 2s, 4s)<br/>+ jitter (±200ms)
            ZoomClient->>ZoomAPI: Retry request (max 3 attempts)
        end
    end

    ZoomClient-->>App: {transcript: {segments: [...],<br/>duration_minutes, participant_count}}

    Note over User,VaultAgent: Integrate with TalentWell Curator

    App->>App: Extract candidate information<br/>from transcript text
    App->>App: Analyze sentiment and enthusiasm<br/>(FEATURE_LLM_SENTIMENT=true)
    App->>App: Extract financial metrics<br/>(AUM, production, growth)<br/>(FEATURE_GROWTH_EXTRACTION=true)

    App->>VaultAgent: POST /ingest<br/>{source: "transcript",<br/>payload: {candidate_data,<br/>transcript_text, sentiment_score}}
    VaultAgent->>PostgreSQL: Store canonical record<br/>vault_records table
    PostgreSQL-->>VaultAgent: vault_locator: VAULT-{uuid}

    VaultAgent-->>App: {locator, status: "ingested"}

    App->>App: Generate digest bullet points<br/>(evidence_extractor.py)
    App->>App: Validate DigestCard format<br/>(‼️ 🔔 📍 + 3-5 bullets)

    App-->>User: Display candidate digest card<br/>with Zoom transcript evidence

    Note over User,VaultAgent: Candidate Search Workflow

    User->>App: "Search transcripts for candidate: John Doe"
    App->>ZoomClient: search_candidate_in_transcripts("John Doe")

    ZoomClient->>ZoomClient: Call list_recordings() for date range

    loop For each meeting
        ZoomClient->>Redis: Get cached transcript
        alt Cached
            Redis-->>ZoomClient: Transcript
        else Not cached
            ZoomClient->>ZoomAPI: Fetch and parse transcript
            ZoomClient->>Redis: Cache result
        end

        ZoomClient->>ZoomClient: Search transcript text for "John Doe"

        alt Candidate found in transcript
            ZoomClient->>ZoomClient: Add meeting to results<br/>{meeting_id, topic, date,<br/>matched_segments}
        end
    end

    ZoomClient-->>App: {matches: [{meeting_id, topic,<br/>transcript_excerpt}]}
    App-->>User: Display 3 meetings with candidate mentions

    Note over ZoomClient,Redis: Error Handling

    alt OAuth token expired mid-request
        ZoomAPI-->>ZoomClient: 401 Unauthorized
        ZoomClient->>ZoomAuth: Refresh token
        ZoomAuth-->>ZoomClient: New access token
        ZoomClient->>Redis: Update cached token
        ZoomClient->>ZoomAPI: Retry original request
    end

    alt Rate limit exceeded
        ZoomAPI-->>ZoomClient: 429 Too Many Requests<br/>Retry-After: 60
        ZoomClient->>ZoomClient: Sleep 60 seconds
        ZoomClient->>ZoomAPI: Retry request
    end

    alt Meeting not found
        ZoomAPI-->>ZoomClient: 404 Not Found
        ZoomClient-->>App: {error: "Meeting not found"}
        App-->>User: "Meeting has been deleted or ID is invalid"
    end
```

### Weekly Digest Subscription Flow
**Automated email delivery system with user preferences and delivery tracking**

```mermaid
sequenceDiagram
    participant User as Executive/Advisor
    participant Teams as Microsoft Teams
    participant TeamsBot as Teams Bot Service
    participant Scheduler as Weekly Digest Scheduler<br/>(Hourly background job)
    participant PostgreSQL as PostgreSQL
    participant VaultAgent as Vault Agent/Curator
    participant ZohoCRM as Zoho CRM
    participant Redis as Redis Cache
    participant ACS as Azure Communication Services
    participant Email as User Email Inbox

    Note over User,Email: User Subscription Management

    User->>Teams: Send message: "/preferences"
    Teams->>TeamsBot: Activity: message received
    TeamsBot->>PostgreSQL: SELECT * FROM teams_user_preferences<br/>WHERE user_id = '{user_id}'

    alt User preferences exist
        PostgreSQL-->>TeamsBot: {default_audience, digest_enabled,<br/>weekly_email_enabled, email_address}
        TeamsBot->>TeamsBot: Build preferences card<br/>(Adaptive Card)
        TeamsBot->>Teams: Send preferences card<br/>with toggle controls
        Teams-->>User: Display preferences<br/>✅ Weekly digest: ON<br/>📧 Email: steve@emailthewell.com<br/>🎯 Audience: advisors
    else No preferences found
        TeamsBot->>PostgreSQL: INSERT INTO teams_user_preferences<br/>(user_id, digest_enabled=true,<br/>weekly_email_enabled=false)
        PostgreSQL-->>TeamsBot: Preferences created
        TeamsBot->>Teams: Send welcome card<br/>"Set up your preferences"
        Teams-->>User: Display setup wizard
    end

    User->>Teams: Toggle: "Enable weekly email ✅"
    Teams->>TeamsBot: Activity: adaptive card action
    TeamsBot->>PostgreSQL: UPDATE teams_user_preferences<br/>SET weekly_email_enabled = true<br/>WHERE user_id = '{user_id}'
    PostgreSQL-->>TeamsBot: Updated

    TeamsBot->>PostgreSQL: INSERT INTO subscription_confirmations<br/>(user_id, email, status='pending')
    PostgreSQL-->>TeamsBot: confirmation_id

    TeamsBot->>ACS: Send confirmation email<br/>Subject: "Confirm your TalentWell digest subscription"<br/>Body: "Click link to confirm"
    ACS-->>Email: Deliver confirmation email

    User->>Email: Click confirmation link
    Email->>TeamsBot: GET /api/teams/confirm-subscription?token={token}
    TeamsBot->>PostgreSQL: UPDATE subscription_confirmations<br/>SET status='confirmed', confirmed_at=NOW()
    PostgreSQL-->>TeamsBot: Confirmed

    TeamsBot->>Teams: Send card: "✅ Subscription confirmed!"
    Teams-->>User: Confirmation notification

    Note over Scheduler,ACS: Hourly Digest Scheduler Job

    Scheduler->>Scheduler: Check current time<br/>(runs every hour via CRON)

    alt Monday 9:00 AM EST
        Scheduler->>PostgreSQL: SELECT * FROM teams_user_preferences<br/>WHERE weekly_email_enabled = true<br/>AND subscription_status = 'confirmed'
        PostgreSQL-->>Scheduler: 25 subscribed users

        loop For each subscribed user
            Scheduler->>PostgreSQL: Check last delivery<br/>SELECT * FROM weekly_digest_deliveries<br/>WHERE user_id = '{user_id}'<br/>AND delivered_at > NOW() - INTERVAL '7 days'

            alt Already sent this week
                Scheduler->>Scheduler: Skip user (already delivered)
            else Not sent this week
                Scheduler->>PostgreSQL: Get user preferences<br/>default_audience, email_address
                PostgreSQL-->>Scheduler: {audience: "advisors",<br/>email: "steve@emailthewell.com"}

                Scheduler->>Redis: Check digest cache<br/>key: vault:digest:advisors:weekly

                alt Cache hit (generated today)
                    Redis-->>Scheduler: Cached HTML digest
                else Cache miss
                    Scheduler->>VaultAgent: Request digest generation<br/>POST /api/vault-agent/publish<br/>{audience: "advisors",<br/>channels: ["email_campaign"]}

                    VaultAgent->>ZohoCRM: Query vault candidates<br/>GET /crm/v8/Leads?cvid=6221978000090941003<br/>(Custom view: _Vault Candidates)
                    ZohoCRM-->>VaultAgent: 164 vault candidates

                    VaultAgent->>VaultAgent: Apply audience filter<br/>(filter by job_title: advisors)
                    VaultAgent->>VaultAgent: Score and rank candidates<br/>(financial metrics + sentiment)
                    VaultAgent->>VaultAgent: Apply VoIT/C³ optimization
                    VaultAgent->>VaultAgent: Generate digest cards<br/>(‼️ 🔔 📍 format + 3-5 bullets)
                    VaultAgent->>VaultAgent: Apply privacy mode<br/>(anonymize companies, round AUM)

                    VaultAgent-->>Scheduler: {html_digest, candidate_count: 12}
                    Scheduler->>Redis: Cache digest (24h TTL)
                end

                Scheduler->>ACS: Send digest email<br/>To: steve@emailthewell.com<br/>Subject: "TalentWell Weekly Digest - Advisors"<br/>Body: HTML digest with 12 candidates<br/>From: notifications@emailthewell.com
                ACS-->>Email: Deliver digest email

                Scheduler->>PostgreSQL: INSERT INTO weekly_digest_deliveries<br/>(user_id, audience, candidate_count=12,<br/>status='sent', delivered_at=NOW())
                PostgreSQL-->>Scheduler: Delivery recorded
            end
        end

        Scheduler->>Scheduler: Log completion<br/>"Delivered 25 digests"
    else Not Monday 9:00 AM
        Scheduler->>Scheduler: Skip (not delivery time)
    end

    Note over User,Email: User Receives and Views Digest

    User->>Email: Open digest email
    Email->>Email: Render HTML digest<br/>(12 candidate cards)
    Email-->>User: Display formatted digest

    User->>User: Review candidates<br/>(anonymized companies,<br/>rounded AUM, strict compensation)

    User->>Teams: Send message: "I want more details on candidate #3"
    Teams->>TeamsBot: Natural language query
    TeamsBot->>TeamsBot: Parse intent (GPT-5-mini)
    TeamsBot->>PostgreSQL: Query recent digest deliveries<br/>for this user
    PostgreSQL-->>TeamsBot: {digest_id, candidates_json}
    TeamsBot->>TeamsBot: Extract candidate #3 data
    TeamsBot->>ZohoCRM: Fetch full candidate record<br/>(using candidate_locator)
    ZohoCRM-->>TeamsBot: Full CRM record
    TeamsBot->>Teams: Send detailed candidate card<br/>(Adaptive Card with full info)
    Teams-->>User: Display candidate details

    Note over User,Email: Unsubscribe Flow

    User->>Email: Click "Unsubscribe" link<br/>(included in every digest)
    Email->>TeamsBot: GET /api/teams/unsubscribe?token={token}
    TeamsBot->>PostgreSQL: UPDATE teams_user_preferences<br/>SET weekly_email_enabled = false<br/>WHERE user_id = '{user_id}'
    PostgreSQL-->>TeamsBot: Updated

    TeamsBot->>PostgreSQL: INSERT INTO weekly_digest_deliveries<br/>(user_id, status='unsubscribed')
    PostgreSQL-->>TeamsBot: Logged

    TeamsBot-->>User: Display confirmation page<br/>"You've been unsubscribed"

    User->>Teams: Send message: "/preferences"
    Teams->>TeamsBot: Activity: message
    TeamsBot->>PostgreSQL: Get preferences
    PostgreSQL-->>TeamsBot: {weekly_email_enabled: false}
    TeamsBot->>Teams: Send card:<br/>"❌ Weekly digest: OFF"
    Teams-->>User: Confirm unsubscribed status

    Note over Scheduler,PostgreSQL: Delivery Analytics & Monitoring

    Scheduler->>PostgreSQL: Query delivery metrics<br/>SELECT COUNT(*), AVG(candidate_count)<br/>FROM weekly_digest_deliveries<br/>WHERE delivered_at > NOW() - INTERVAL '30 days'<br/>GROUP BY audience
    PostgreSQL-->>Scheduler: {advisors: {deliveries: 100,<br/>avg_candidates: 15},<br/>c_suite: {deliveries: 20,<br/>avg_candidates: 8}}

    Scheduler->>Scheduler: Log metrics to<br/>Application Insights<br/>(delivery_count, open_rate estimates)
```

### End-to-End Data Flow (C4 Level 1 Supplement)
**Complete data journey visualization across all processing paths**

```mermaid
flowchart TB
    classDef source fill:#E3F2FD,stroke:#1E40AF,color:#0B1F4B,stroke-width:2px;
    classDef process fill:#F3E8FF,stroke:#7C3AED,color:#4C1D95,stroke-width:2px;
    classDef optimize fill:#FED7D7,stroke:#E53E3E,color:#742A2A,stroke-width:3px;
    classDef enrich fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:2px;
    classDef store fill:#DCFCE7,stroke:#059669,color:#064E3B,stroke-width:2px;
    classDef output fill:#FCE7F3,stroke:#C026D3,color:#701A75,stroke-width:2px;

    subgraph DataSources["Data Sources (Ingestion Layer)"]
        Email["Outlook Email\n(Recruiter submissions)"]
        ZoomMeeting["Zoom Meetings\n(Candidate interviews)"]
        Resume["Resume Uploads\n(PDF/DOCX attachments)"]
        WebScrape["Web Research\n(Firecrawl v2 scraping)"]
        TeamsChat["Teams Chat Messages\n(Natural language queries)"]
    end
    class DataSources,Email,ZoomMeeting,Resume,WebScrape,TeamsChat source;

    subgraph IngestionLayer["Ingestion & Extraction Layer"]
        direction TB

        EmailParser["Email Parser\n(LangGraph pipeline)\nExtract → Research → Validate"]
        ZoomParser["Zoom Transcript Parser\n(VTT → JSON segments)"]
        ResumeParser["Resume Parser\n(PDF text extraction)"]
        WebParser["Web Content Parser\n(FIRE-1 agent structured extraction)"]
        NLPParser["NLP Intent Classifier\n(GPT-5-mini query understanding)"]
    end
    class IngestionLayer,EmailParser,ZoomParser,ResumeParser,WebParser,NLPParser process;

    subgraph OptimizationLayer["🚨 VoIT + C³ Optimization Layer (Cross-Cutting)"]
        direction LR

        VoITEngine["VoIT Engine\n• Uncertainty quantification\n• VOI calculation\n• Model tier selection (nano/mini/large)\n• Budget allocation\n• Quality tracking"]

        C3Engine["C³ Engine\n• Probabilistic margin (δ-bound)\n• Embedding similarity\n• Selective rebuild\n• Dependency certificates\n• 90% cache hit rate"]
    end
    class OptimizationLayer,VoITEngine,C3Engine optimize;

    subgraph EnrichmentLayer["Enrichment Layer"]
        direction TB

        ApolloEnrich["Apollo.io Enrichment\n(Contact phone, LinkedIn,<br/>job titles, company data)"]
        FirecrawlEnrich["Firecrawl v2 Research\n(Company HQ, revenue,<br/>funding, tech stack)"]
        AzureMapsEnrich["Azure Maps Geocoding\n(Address normalization,<br/>city/state inference)"]
        GPTEnrich["GPT-5 Analysis\n(Sentiment, growth metrics,<br/>financial patterns)"]
    end
    class EnrichmentLayer,ApolloEnrich,FirecrawlEnrich,AzureMapsEnrich,GPTEnrich enrich;

    subgraph NormalizationLayer["Normalization & Canonicalization"]
        direction TB

        EmailNormalizer["Email → Canonical\n(ExtractedData → DealModel)"]
        ZoomNormalizer["Transcript → Canonical\n(VaultRecord with sentiment)"]
        ResumeNormalizer["Resume → Canonical\n(Contact + Experience)"]
        WebNormalizer["Web Data → Canonical\n(Company metadata)"]
    end
    class NormalizationLayer,EmailNormalizer,ZoomNormalizer,ResumeNormalizer,WebNormalizer process;

    subgraph StorageLayer["Persistence & Cache Layer"]
        direction TB

        PostgresDB["PostgreSQL Database\n• deals, contacts, attachments\n• vault_records (canonical)\n• teams_user_preferences\n• weekly_digest_deliveries\n• batch_jobs, learning_events"]

        RedisCache["Redis Cache\n• intake:* (2-12h TTL)\n• vault:* (7d TTL)\n• c3:* (7d TTL with drift)\n• apollo:*, firecrawl:* (24h)"]

        BlobStorage["Azure Blob Storage\n• Email attachments\n• Manifests & icons\n• Resume files"]

        Embeddings["pgvector Embeddings\n• Semantic similarity\n• Deduplication\n• 400K context window"]
    end
    class StorageLayer,PostgresDB,RedisCache,BlobStorage,Embeddings store;

    subgraph OutputLayer["Output & Distribution Layer"]
        direction TB

        ZohoCRM["Zoho CRM Records\n(Accounts, Contacts, Deals, Leads)"]
        TeamsCards["Teams Adaptive Cards\n(Digest previews, query results)"]
        EmailDigests["Weekly Email Digests\n(Azure Communication Services)"]
        VaultPublish["Vault Publications\n(HTML cards, portal listings)"]
    end
    class OutputLayer,ZohoCRM,TeamsCards,EmailDigests,VaultPublish output;

    %% Data flow connections - Email path
    Email --> EmailParser
    EmailParser -.->|"Optimized by"| VoITEngine
    EmailParser -.->|"Cached by"| C3Engine
    EmailParser --> ApolloEnrich
    EmailParser --> FirecrawlEnrich
    EmailParser --> AzureMapsEnrich
    ApolloEnrich --> EmailNormalizer
    FirecrawlEnrich --> EmailNormalizer
    AzureMapsEnrich --> EmailNormalizer
    EmailNormalizer --> PostgresDB
    EmailNormalizer --> RedisCache
    EmailNormalizer --> Embeddings
    PostgresDB --> ZohoCRM
    RedisCache --> ZohoCRM

    %% Data flow connections - Zoom path
    ZoomMeeting --> ZoomParser
    ZoomParser --> GPTEnrich
    GPTEnrich --> ZoomNormalizer
    ZoomNormalizer -.->|"Optimized by"| VoITEngine
    ZoomNormalizer -.->|"Cached by"| C3Engine
    ZoomNormalizer --> PostgresDB
    ZoomNormalizer --> RedisCache
    PostgresDB --> VaultPublish
    RedisCache --> EmailDigests

    %% Data flow connections - Resume path
    Resume --> ResumeParser
    ResumeParser --> BlobStorage
    ResumeParser --> ResumeNormalizer
    ResumeNormalizer --> PostgresDB
    PostgresDB --> ZohoCRM

    %% Data flow connections - Web research path
    WebScrape --> WebParser
    WebParser -.->|"Optimized by"| VoITEngine
    WebParser --> WebNormalizer
    WebNormalizer --> RedisCache
    RedisCache --> FirecrawlEnrich

    %% Data flow connections - Teams natural language path
    TeamsChat --> NLPParser
    NLPParser -.->|"Optimized by"| VoITEngine
    NLPParser --> PostgresDB
    PostgresDB --> TeamsCards

    %% VoIT/C³ optimization points
    VoITEngine --> ApolloEnrich
    VoITEngine --> FirecrawlEnrich
    VoITEngine --> GPTEnrich
    C3Engine --> RedisCache

    %% Output generation
    PostgresDB --> VaultPublish
    Embeddings --> VaultPublish
    VaultPublish --> EmailDigests
    VaultPublish --> TeamsCards

    %% Data transformations annotations
    EmailParser -.->|"Structured extraction\n(Pydantic schemas)"| EmailNormalizer
    ZoomParser -.->|"VTT → JSON\n(segment parsing)"| ZoomNormalizer
    EmailNormalizer -.->|"DealModel\n(SQLModel ORM)"| PostgresDB
    ZoomNormalizer -.->|"VaultRecord\n(canonical format)"| PostgresDB
    PostgresDB -.->|"Custom view query\n(cvid=6221978000090941003)"| VaultPublish
    VaultPublish -.->|"DigestCard format\n(‼️ 🔔 📍 + 3-5 bullets)"| EmailDigests
    VaultPublish -.->|"Privacy mode\n(anonymize, round AUM)"| EmailDigests

    %% Performance annotations
    note1["VoIT Optimization Points:\n• Model selection (nano/mini/large)\n• Tool vs. LLM decision\n• Budget allocation\n• 65% cost reduction"]
    class note1 optimize;

    note2["C³ Cache Hit Scenarios:\n• Email deduplication (90% hit rate)\n• Transcript reuse (semantic similarity)\n• Company research (24h freshness)\n• Vault digest generation (daily cache)"]
    class note2 optimize;

    note3["Data Quality Controls:\n• Confidence scoring (>0.7 threshold)\n• Duplicate detection (embedding similarity)\n• Evidence linking (no hallucinations)\n• Format validation (DigestCard rules)"]
    class note3 store;
```

### Complete API Endpoint Catalogue

| Category | Endpoint | Method | Purpose | Auth Required |
|----------|----------|--------|---------|---------------|
| **Core Intake** | `/intake/email` | POST | Primary email processing endpoint - LangGraph pipeline | API Key or Bearer |
| | `/intake/email/status/{id}` | GET | Check extraction status | API Key |
| | `/test/kevin-sullivan` | GET | Test endpoint with sample data | API Key |
| **Batch Processing** | `/batch/submit` | POST | Submit batch of emails for processing | API Key |
| | `/batch/process` | POST | Process batch with Service Bus | API Key |
| | `/batch/status/{batch_id}` | GET | Get batch processing status | API Key |
| | `/batch/status` | GET | Get all batch statuses | API Key |
| | `/batch/queue/status` | GET | Get Service Bus queue metrics | API Key |
| | `/batch/queue/process` | POST | Process queue items | API Key |
| | `/batch/deadletter/process` | POST | Reprocess dead letter messages | API Key |
| **Vault Agent** | `/api/vault-agent/ingest` | POST | Ingest canonical records (email/resume/transcript) | API Key |
| | `/api/vault-agent/publish` | POST | Multi-channel publishing with VoIT/C³ | API Key |
| | `/api/vault-agent/status` | GET | Get feature flags and config | API Key |
| **Apollo Enrichment** | `/api/apollo/enrich` | POST | Enrich contact with Apollo.io | API Key |
| | `/api/apollo/enrich-batch` | POST | Batch enrich multiple contacts | API Key |
| | `/api/apollo/search` | POST | Search Apollo.io database | API Key |
| **Streaming** | `/stream/email` | POST | Stream processing with SSE | API Key |
| | `/stream/status/{extraction_id}` | GET | Stream status updates via SSE | API Key |
| | `/ws/email-processing` | WS | WebSocket real-time processing | API Key |
| **Cache Management** | `/cache/status` | GET | Get cache health and metrics | API Key |
| | `/cache/invalidate` | POST | Invalidate cache keys | API Key |
| | `/cache/warmup` | POST | Warm cache with common queries | API Key |
| | `/cache/alerts` | GET | Get cache health alerts | API Key |
| | `/cache/metrics/report` | GET | Detailed cache metrics | API Key |
| | `/cache/monitoring/start` | POST | Start cache monitoring | API Key |
| | `/cache/health/detailed` | GET | Detailed cache health check | API Key |
| **Manifest Management** | `/manifest.xml` | GET | Outlook add-in manifest (XML) | Public |
| | `/manifest.json` | GET | Outlook add-in manifest (JSON) | Public |
| | `/manifest/cache/status` | GET | Manifest cache status | API Key |
| | `/manifest/cache/invalidate` | POST | Invalidate manifest cache | API Key |
| | `/manifest/cache/warmup` | POST | Warm manifest cache | API Key |
| | `/manifest/template/update` | PUT | Update manifest template | API Key |
| | `/manifest/warmup/status` | GET | Get warmup status | Public |
| | `/manifest/analytics` | GET | Manifest usage analytics | API Key |
| | `/manifest/monitoring/alerts` | GET | Manifest monitoring alerts | API Key |
| **CDN Management** | `/api/cdn/purge` | POST | Purge Azure Front Door cache | API Key |
| | `/api/cdn/status` | GET | Get CDN cache status | API Key |
| **Static Assets** | `/commands.js` | GET | Add-in command handlers | Public |
| | `/commands.html` | GET | Add-in command UI | Public |
| | `/config.js` | GET | Add-in configuration | Public |
| | `/placeholder.html` | GET | Add-in placeholder page | Public |
| | `/icon-{size}.png` | GET | Add-in icons (16/32/64/80/128) | Public |
| **Learning & Analytics** | `/learning/analytics/{field}` | GET | Get field-level learning analytics | API Key |
| | `/learning/variants` | GET | Get A/B test variants | API Key |
| | `/learning/insights` | GET | Get AI learning insights | API Key |
| **AI Search** | `/ai-search/patterns/search` | GET | Search semantic patterns | API Key |
| | `/ai-search/templates/{domain}` | GET | Get company templates | API Key |
| | `/ai-search/patterns/index` | POST | Index new patterns | API Key |
| | `/ai-search/status` | GET | Get AI Search status | API Key |
| **Admin** | `/admin/policies` | GET/POST | Manage processing policies | API Key |
| | `/admin/policies/{id}` | GET/PUT/DELETE | CRUD policy operations | API Key |
| | `/admin/import-v2/*` | Various | Import/export v2 operations | API Key |
| **Authentication** | `/auth/validate` | POST | Validate auth token | Public |
| | `/auth/user-info` | GET | Get user information | Bearer |
| | `/auth/login` | GET | Microsoft login redirect | Public |
| **Health & Monitoring** | `/health` | GET | Basic health check | Public |
| | `/health/database` | GET | Database health check | API Key |
| | `/` | GET | API root with version info | Public |

### Data & Integration Catalogue

| Category | Surface | Purpose | Notes |
|----------|---------|---------|-------|
| Platform Data | PostgreSQL (`deals`, `contacts`, `attachments`, `embeddings`, `vault_records`, `learning_events`, `correction_logs`) | Source of truth for CRM pushes, replay safety, vector search, canonical records, AI learning data | `pgvector` drives similarity matching & deduping; 400K context window support |
| Platform Data | Redis (`intake:*`, `manifest:*`, `c3:*`, `vault:*`, `apollo:*`, `firecrawl:*`) | Sub-second previews, duplicate suppression, C³ cache entries, vault canonical records, enrichment cache | TTL tuned for 2–12h (intake) to 7 days (vault); 90% cost reduction |
| Platform Data | Azure Blob (`attachments/`, `manifests/`, `icons/`) | Attachment storage, Outlook static file hosting, add-in assets | Versioned with cache-busting to avoid stale manifests |
| Platform Data | Azure Service Bus (`email-batch-queue`, `email-deadletter`) | Batch email processing queues, failed message handling | 50 emails/batch with atomic processing |
| Integrations | Zoho CRM REST APIs (v8) | Account/Contact/Deal creation, idempotent updates, deduplication checks | OAuth tokens managed by proxy, backoff on 429s, search with parentheses |
| Integrations | Azure OpenAI (`gpt-5-nano`, `gpt-5-mini`, `gpt-5`) | Field extraction, validation, summarization, VoIT span processing | Prompt templates live in `app/prompts/`; VoIT selects model tier by uncertainty; temperature=1 always |
| Integrations | Firecrawl API (v2 FIRE-1) | Company research, website parsing, VoIT tool enrichment, structured data extraction | Batched to minimize request volume; used in VoIT "tool" action; 5s timeout |
| Integrations | Apollo.io API | Contact enrichment, phone/email validation, VoIT contact data, company search | Smart throttling with daily quota guardrails, free plan fallback |
| Integrations | Azure Maps | Geocoding, timezone inference, address normalization | Optional feature flag via `ENABLE_AZURE_MAPS`; 24h TTL cache |
| Integrations | Zoom API | Meeting recordings, transcripts, AI summaries, participant data | Used by TalentWell Curator; OAuth authentication |
| Integrations | Microsoft Graph API | Outlook email reading, calendar access, user profile data | Azure AD authentication with delegated permissions |
| Observability | Application Insights | Centralized telemetry, trace correlation, VoIT metrics (VOI, quality, cache hit rate), cost tracking | Configured through deployment pipeline; custom metrics for business KPIs |
| Vault Agent | `/api/vault-agent/ingest` | Normalize multi-source payloads (email/resume/transcript/zoom) to canonical format | Generates embeddings, stores in Redis with 7-day TTL; supports `source`: "email", "resume", "transcript", "web" |
| Vault Agent | `/api/vault-agent/publish` | Multi-channel publishing with C³/VoIT optimization | Channels: `email_campaign`, `zoho_crm`, `portal_card`, `jd_alignment` |
| Vault Agent | `/api/vault-agent/status` | Feature flag status and configuration inspection | Returns C³/VoIT enabled state, δ-bound, budget, quality targets |

### Candidate Vault Agent Architecture (CRM Data Formatting System)
**Pulls from Zoho CRM vault + enriches with multi-source data → produces locked-format digest cards**

```mermaid
graph TB
    subgraph Sources["Data Sources (Aggregated from CRM Vault)"]
        ZohoCRM["Zoho CRM Records<br/>'Vault' candidates"]
        Resume[Resume Attachments<br/>Stored in CRM]
        Transcript[Zoom Transcripts<br/>Meeting recordings]
        ZoomNotes[Zoom AI Notes<br/>Meeting summaries]
        CRMNotes[Historical CRM Notes<br/>Recruiter observations]
        Web[Web Research<br/>Firecrawl enrichment]
    end

    subgraph Aggregation["Data Aggregation Layer"]
        Fetch[Fetch Vault Candidates<br/>from Zoho]
        Enrich["Enrich with Attachments<br/>+ Transcripts + Notes"]
        Extract["Evidence Extraction<br/>Financial patterns (AUM, prod)"]
    end

    subgraph Optimization["🚨 VoIT + C³ Optimization (Cross-Cutting)"]
        C3Check{"C³ Cache Check<br/>Probabilistic reuse"}
        VoITProc[VoIT Processing<br/>Adaptive depth allocation]
    end

    subgraph Formatting["Locked Format Generation"]
        Template["Brandon's Template<br/>‼️ 🔔 📍 + 3-5 bullets"]
        Validate[Format Validator<br/>Emoji + bullet rules]
        Evidence[Evidence Linking<br/>No hallucinations allowed]
    end

    subgraph Output["Digest Card Output"]
        EmailDigest[Email Campaign<br/>Advisor-specific alerts]
        HTMLCard[HTML Digest Cards<br/>Advisor_Vault_Candidate_Alerts.html]
    end

    subgraph Storage["Persistence"]
        Redis[("Redis<br/>7d TTL")]
        PG[("PostgreSQL<br/>Canonical Records")]
    end

    ZohoCRM --> Fetch
    Resume --> Enrich
    Transcript --> Enrich
    ZoomNotes --> Enrich
    CRMNotes --> Enrich
    Web --> Enrich

    Fetch --> Enrich
    Enrich --> Extract
    Extract --> C3Check

    C3Check -->|Cache Hit| Template
    C3Check -->|Cache Miss| VoITProc
    VoITProc --> Template

    Template --> Validate
    Validate --> Evidence
    Evidence --> EmailDigest
    Evidence --> HTMLCard

    Extract --> Redis
    Extract --> PG

    classDef source fill:#E3F2FD,stroke:#1E40AF,stroke-width:2px
    classDef aggr fill:#F3E8FF,stroke:#7C3AED,stroke-width:2px
    classDef optimize fill:#FED7D7,stroke:#E53E3E,stroke-width:3px
    classDef format fill:#FEF3C7,stroke:#D97706,stroke-width:2px
    classDef output fill:#DCFCE7,stroke:#15803D,stroke-width:2px
    classDef storage fill:#F8FAFC,stroke:#0F172A,stroke-width:2px

    class ZohoCRM,Resume,Transcript,ZoomNotes,CRMNotes,Web source
    class Fetch,Enrich,Extract aggr
    class C3Check,VoITProc optimize
    class Template,Validate,Evidence format
    class EmailDigest,HTMLCard output
    class Redis,PG storage
```

### CI/CD & Deployment Pipeline Architecture

```mermaid
flowchart TB
    classDef repo fill:#F3E8FF,stroke:#7C3AED,stroke-width:2px
    classDef build fill:#DBEAFE,stroke:#2563EB,stroke-width:2px
    classDef test fill:#FEF3C7,stroke:#D97706,stroke-width:2px
    classDef deploy fill:#DCFCE7,stroke:#15803D,stroke-width:2px
    classDef prod fill:#FED7D7,stroke:#E53E3E,stroke-width:2px

    subgraph DevWorkflow["Developer Workflow"]
        Dev["Developer\nCommit"]
        PR["Pull Request\nReview"]
    end
    class Dev,PR repo

    subgraph GitHubActions["GitHub Actions (3 Workflows)"]
        Manifest["manifest-cache-bust.yml\n(Addin changes)"]
        Deploy["deploy-production.yml\n(Main branch)"]
        Emergency["emergency-rollback.yml\n(Manual trigger)"]
    end
    class Manifest,Deploy,Emergency build

    subgraph BuildStage["Build & Test Stage"]
        Validate["Validate Manifests\n(XML + JSON)"]
        Docker["Docker Multi-stage Build\n(Optimized layers)"]
        Security["Security Scan\n(Bandit + Safety)"]
        UnitTest["Unit Tests\n(pytest)"]
    end
    class Validate,Docker,Security,UnitTest test

    subgraph Registry["Container Registry"]
        ACR["wellintakeacr0903.azurecr.io\nwell-intake-api:latest\nwell-intake-api:v{timestamp}"]
    end
    class ACR deploy

    subgraph AzureDeploy["Azure Deployment"]
        ContainerUpdate["Container App Update\n(New revision with suffix)"]
        TrafficSplit["Traffic Split\n(Blue-green deployment)"]
        HealthCheck["Health Check\n(/health endpoint)"]
    end
    class ContainerUpdate,TrafficSplit,HealthCheck deploy

    subgraph PostDeploy["Post-Deployment"]
        CDNPurge["Azure Front Door Purge\n(Cache invalidation)"]
        CacheWarm["Cache Warmup\n(Manifest + Redis)"]
        DBMigrate["Database Migrations\n(Alembic)"]
        Verify["Smoke Tests\n(Kevin Sullivan endpoint)"]
    end
    class CDNPurge,CacheWarm,DBMigrate,Verify deploy

    subgraph Production["Production Environment"]
        LiveTraffic["Live Traffic\n(Azure Front Door)"]
        Monitoring["Monitoring\n(App Insights)"]
        Rollback["Emergency Rollback\n(Previous revision)"]
    end
    class LiveTraffic,Monitoring,Rollback prod

    %% Workflow
    Dev -->|"Push to branch"| PR
    PR -->|"Merge to main"| Deploy
    Dev -->|"Addin changes"| Manifest

    Deploy --> Validate
    Manifest --> Validate

    Validate --> Docker
    Docker --> Security
    Security --> UnitTest
    UnitTest -->|"All pass"| ACR

    ACR -->|"Pull image"| ContainerUpdate
    ContainerUpdate --> TrafficSplit
    TrafficSplit --> HealthCheck

    HealthCheck -->|"Success"| CDNPurge
    CDNPurge --> CacheWarm
    CacheWarm --> DBMigrate
    DBMigrate --> Verify

    Verify -->|"Pass"| LiveTraffic
    LiveTraffic --> Monitoring
    Monitoring -->|"Issues detected"| Emergency
    Emergency --> Rollback
    Rollback --> LiveTraffic

    HealthCheck -->|"Fail"| Rollback
```

### Deployment Scripts Inventory

| Script | Purpose | Trigger | Runtime |
|--------|---------|---------|---------|
| `deploy.sh` | Full deployment (build + push + migrate + deploy) | Manual | ~5-8 min |
| `deploy_with_cache_bust.py` | Deploy with manifest version bump + CDN purge | GitHub Actions | ~6-10 min |
| `manifest_warmup.py` | Warm manifest cache across all endpoints | Post-deploy | ~2-3 min |
| `initialize_database.py` | Create tables, indexes, pgvector extension | First deploy | ~1-2 min |
| `docker-build-optimized.sh` | Multi-stage Docker build with layer caching | CI/CD | ~3-5 min |
| `restart_app.sh` | Quick restart without rebuild | Emergency | ~30 sec |
| `test_deployment_pipeline.py` | End-to-end deployment validation | CI/CD | ~5 min |
| `update_manifest_version.py` | Auto-increment manifest version | Pre-deploy | ~5 sec |

### Database Schema & ER Diagram

```mermaid
erDiagram
    DEALS ||--o{ ATTACHMENTS : "has"
    DEALS ||--o{ EMBEDDINGS : "indexed_by"
    DEALS ||--o{ CORRECTION_LOGS : "tracks"
    CONTACTS ||--o{ DEALS : "owns"
    CONTACTS ||--o{ EMBEDDINGS : "indexed_by"
    VAULT_RECORDS ||--o{ EMBEDDINGS : "indexed_by"
    VAULT_RECORDS ||--o{ LEARNING_EVENTS : "generates"
    BATCH_JOBS ||--o{ BATCH_ITEMS : "contains"

    DEALS {
        uuid id PK
        string zoho_deal_id UK
        string company_name
        string contact_name
        string contact_email UK
        string contact_phone
        string job_title
        string location
        string deal_name
        string source
        string source_detail
        string pipeline
        decimal amount
        string stage
        jsonb extracted_data
        jsonb enrichment_data
        timestamp created_at
        timestamp updated_at
        string processing_status
        jsonb confidence_scores
    }

    CONTACTS {
        uuid id PK
        string zoho_contact_id UK
        string first_name
        string last_name
        string email UK
        string phone
        string title
        string company
        string city
        string state
        jsonb apollo_data
        timestamp last_enriched_at
        timestamp created_at
    }

    ATTACHMENTS {
        uuid id PK
        uuid deal_id FK
        string blob_url UK
        string filename
        string content_type
        bigint size_bytes
        string storage_path
        jsonb metadata
        timestamp uploaded_at
    }

    EMBEDDINGS {
        uuid id PK
        string entity_type "deal|contact|vault_record"
        uuid entity_id FK
        vector embedding "pgvector(1536)"
        string embedding_model "text-embedding-ada-002"
        jsonb metadata
        timestamp created_at
    }

    VAULT_RECORDS {
        uuid id PK
        string vault_locator UK "VAULT-{uuid}"
        string source "email|resume|transcript|web"
        jsonb canonical_payload
        vector embedding "pgvector(1536)"
        jsonb c3_cache_metadata
        timestamp ingested_at
        timestamp last_published_at
        int publish_count
        string status "ingested|published|failed"
    }

    LEARNING_EVENTS {
        uuid id PK
        uuid vault_record_id FK
        string event_type "field_correction|pattern_detected|quality_score"
        string field_name
        jsonb before_value
        jsonb after_value
        decimal confidence_delta
        jsonb context
        timestamp recorded_at
    }

    CORRECTION_LOGS {
        uuid id PK
        uuid deal_id FK
        string field_name
        string original_value
        string corrected_value
        string correction_source "user|apollo|firecrawl|azure_maps"
        jsonb correction_metadata
        timestamp corrected_at
    }

    BATCH_JOBS {
        uuid id PK
        string batch_id UK
        int total_emails
        int processed_count
        int success_count
        int error_count
        jsonb metadata
        string status "pending|processing|completed|failed"
        timestamp created_at
        timestamp started_at
        timestamp completed_at
    }

    BATCH_ITEMS {
        uuid id PK
        uuid batch_job_id FK
        string email_subject
        string sender_email
        jsonb extraction_result
        string status "pending|success|failed"
        jsonb error_details
        timestamp processed_at
    }

    POLICIES {
        uuid id PK
        string policy_name UK
        string policy_type "gating|enrichment|validation"
        jsonb rules
        boolean enabled
        int priority
        timestamp created_at
        timestamp updated_at
    }

    CACHE_METRICS {
        uuid id PK
        string cache_type "c3|redis|manifest"
        string operation "hit|miss|eviction|invalidation"
        string key_pattern
        bigint count
        decimal hit_rate
        timestamp recorded_at
    }
```

### Security Architecture Diagram

```mermaid
flowchart TB
    classDef threat fill:#FFE5E5,stroke:#DC2626,stroke-width:2px
    classDef defense fill:#D1FAE5,stroke:#059669,stroke-width:2px
    classDef boundary fill:#DBEAFE,stroke:#2563EB,stroke-width:3px

    subgraph Internet["Public Internet"]
        Attacker["Threat Actors"]
        User["Legitimate Users"]
    end
    class Attacker threat
    class User defense

    subgraph EdgeDefense["Edge Defense Layer"]
        AFD["Azure Front Door CDN\n- DDoS Protection\n- WAF Rules\n- Geo-filtering\n- Rate limiting"]
        TLS["TLS 1.2+ Termination\n- Certificate rotation\n- HSTS headers"]
    end
    class EdgeDefense,AFD,TLS boundary

    subgraph AuthLayer["Authentication Layer"]
        APIKey["HMAC API Key Validation\n- Timing-safe comparison\n- Key rotation support"]
        AzureAD["Azure AD OAuth 2.0\n- Bearer token validation\n- Delegated permissions"]
        RateLimit["Rate Limiter\n- 5 failed attempts\n- 15-minute lockout\n- IP + key tracking"]
    end
    class AuthLayer,APIKey,AzureAD,RateLimit defense

    subgraph AppSecurity["Application Security"]
        CORS["CORS Policy\n- Restricted origins\n- Credential validation"]
        Input["Input Validation\n- Pydantic schemas\n- SQL injection prevention\n- XSS sanitization"]
        Secrets["Secret Management\n- Azure Key Vault\n- No hardcoded credentials\n- Rotation hooks"]
    end
    class AppSecurity,CORS,Input,Secrets defense

    subgraph DataSecurity["Data Security"]
        EncryptTransit["Encryption in Transit\n- TLS 1.2+\n- Redis TLS\n- PostgreSQL TLS"]
        EncryptRest["Encryption at Rest\n- Azure Storage encryption\n- PostgreSQL encryption\n- Blob storage encryption"]
        KeyVault["Azure Key Vault\n- Zoho tokens\n- API keys\n- Connection strings\n- Azure Maps key"]
    end
    class DataSecurity,EncryptTransit,EncryptRest,KeyVault defense

    subgraph NetworkSecurity["Network Security"]
        VNet["Virtual Network\n- Private endpoints\n- Subnet isolation"]
        NSG["Network Security Groups\n- Ingress/egress rules\n- Service tags"]
        ManagedIdentity["Managed Identities\n- Passwordless auth\n- Least privilege"]
    end
    class NetworkSecurity,VNet,NSG,ManagedIdentity defense

    subgraph Monitoring["Security Monitoring"]
        AuditLogs["Audit Logs\n- 90-day retention\n- Immutable storage"]
        AppInsights["Application Insights\n- Security events\n- Anomaly detection"]
        Alerts["Security Alerts\n- Failed auth spikes\n- Unusual API patterns\n- Secret access tracking"]
    end
    class Monitoring,AuditLogs,AppInsights,Alerts defense

    %% Threat flows
    Attacker -->|"Attack attempts"| AFD
    User -->|"HTTPS requests"| AFD

    %% Defense flows
    AFD -->|"Pass WAF"| TLS
    TLS -->|"Validate"| APIKey
    TLS -->|"Validate"| AzureAD
    APIKey --> RateLimit
    AzureAD --> RateLimit
    RateLimit -->|"Pass"| CORS
    CORS --> Input
    Input --> Secrets
    Secrets --> KeyVault

    %% Data protection
    Input --> EncryptTransit
    EncryptTransit --> EncryptRest
    KeyVault --> EncryptRest

    %% Network isolation
    CORS --> VNet
    VNet --> NSG
    NSG --> ManagedIdentity

    %% Monitoring
    APIKey --> AuditLogs
    AzureAD --> AuditLogs
    RateLimit --> AppInsights
    Secrets --> AppInsights
    KeyVault --> Alerts
    AuditLogs --> Alerts

    %% Blocked threats
    AFD -.->|"Block"| Attacker
    RateLimit -.->|"Block"| Attacker
```

### Authentication & Authorization Flow

```mermaid
sequenceDiagram
    participant User as User/Outlook Add-in
    participant AFD as Azure Front Door
    participant API as FastAPI Core
    participant KeyVault as Azure Key Vault
    participant AzureAD as Azure AD
    participant RateLimiter as Rate Limiter
    participant Secrets as Secret Store

    Note over User,Secrets: Authentication Flow

    alt API Key Authentication
        User->>AFD: POST /intake/email<br/>X-API-Key: hmac-key
        AFD->>API: Forward with X-Forwarded-For
        API->>RateLimiter: Check IP + key limits
        RateLimiter-->>API: Within limits
        API->>KeyVault: Fetch valid API keys
        KeyVault-->>API: Return key list
        API->>API: Timing-safe key comparison
        API-->>User: 200 OK with data
    end

    Note over User,Secrets: OAuth 2.0 Flow

    alt Azure AD Bearer Token
        User->>AzureAD: POST /auth/login (redirect)
        AzureAD-->>User: Authorization code
        User->>API: GET /auth/callback?code=xyz
        API->>AzureAD: Exchange code for token
        AzureAD-->>API: Access token + refresh token
        API->>Secrets: Store refresh token
        API-->>User: Set session cookie

        User->>AFD: POST /intake/email<br/>Authorization: Bearer {token}
        AFD->>API: Forward request
        API->>AzureAD: Validate token signature
        AzureAD-->>API: Token valid + claims
        API->>API: Check user permissions
        API-->>User: 200 OK with data
    end

    Note over User,Secrets: Rate Limiting

    alt Failed Authentication
        User->>AFD: POST /intake/email<br/>X-API-Key: invalid-key
        AFD->>API: Forward request
        API->>RateLimiter: Record failed attempt
        RateLimiter->>RateLimiter: Increment counter (IP + key)
        RateLimiter-->>API: Attempt 5/5
        API-->>User: 429 Rate Limited<br/>Retry-After: 900s

        Note over RateLimiter: 15-minute lockout activated

        User->>AFD: POST /intake/email<br/>X-API-Key: valid-key
        AFD->>API: Forward request
        API->>RateLimiter: Check lockout status
        RateLimiter-->>API: IP locked until {timestamp}
        API-->>User: 429 Rate Limited<br/>Retry-After: 780s
    end

    Note over User,Secrets: Secret Rotation

    API->>KeyVault: Get Zoho refresh token
    KeyVault-->>API: Return token (version 3)
    API->>API: Use token for Zoho API

    Note over KeyVault: Admin rotates secret

    KeyVault->>KeyVault: Create new version 4
    API->>KeyVault: Get latest secret
    KeyVault-->>API: Return token (version 4)
```

### Network Architecture Diagram

```mermaid
flowchart TB
    classDef internet fill:#FEE2E2,stroke:#DC2626,stroke-width:2px
    classDef edge fill:#DBEAFE,stroke:#2563EB,stroke-width:2px
    classDef compute fill:#DCFCE7,stroke:#059669,stroke-width:2px
    classDef data fill:#FEF3C7,stroke:#D97706,stroke-width:2px
    classDef mgmt fill:#F3E8FF,stroke:#7C3AED,stroke-width:2px

    subgraph Internet["Public Internet"]
        Client["Outlook Clients\n(Desktop/Web/Mobile)"]
        WebHook["External Webhooks"]
        Admin["Admin Console"]
    end
    class Internet,Client,WebHook,Admin internet

    subgraph EdgeLayer["Edge Network Layer"]
        AFD["Azure Front Door CDN\nwell-intake-api-dnajdub4azhjcgc3.z03.azurefd.net\n- Global anycast\n- TLS termination\n- WAF + DDoS\n- Cache rules"]
        DNS["Azure DNS\n- Custom domain\n- Health probes\n- Geo-routing"]
    end
    class EdgeLayer,AFD,DNS edge

    subgraph VNet["Azure Virtual Network (East US)\n10.0.0.0/16"]
        subgraph AppSubnet["Container Apps Subnet\n10.0.1.0/24"]
            ContainerEnv["Container Apps Environment\nwell-intake-env"]
            ContainerApp["Container App\nwell-intake-api\n(0-10 instances)"]
        end

        subgraph DataSubnet["Data Subnet\n10.0.2.0/24"]
            RedisPrivate["Redis Private Endpoint\n10.0.2.4"]
            PGPrivate["PostgreSQL Private Endpoint\n10.0.2.5"]
            BlobPrivate["Blob Storage Private Endpoint\n10.0.2.6"]
        end

        subgraph MgmtSubnet["Management Subnet\n10.0.3.0/24"]
            KeyVaultPrivate["Key Vault Private Endpoint\n10.0.3.4"]
            AppInsightsPrivate["App Insights Private Link"]
        end

        NSG["Network Security Groups\n- Inbound: 443 from AFD\n- Outbound: 443, 5432, 6380\n- Deny all else"]
    end
    class VNet,AppSubnet,DataSubnet,MgmtSubnet compute
    class RedisPrivate,PGPrivate,BlobPrivate data
    class KeyVaultPrivate,AppInsightsPrivate,NSG mgmt

    subgraph AzureBackbone["Azure Backbone Network"]
        ServiceBus["Service Bus\nwell-intake-bus"]
        AISearch["AI Search\nwellintakesearch0903"]
        ACR["Container Registry\nwellintakeacr0903"]
    end
    class AzureBackbone,ServiceBus,AISearch,ACR data

    subgraph ExternalAPIs["External APIs (Internet)"]
        OpenAI["Azure OpenAI\n(East US)"]
        Firecrawl["Firecrawl API\n(Public)"]
        Apollo["Apollo.io API\n(Public)"]
        Zoho["Zoho CRM API\n(Public)"]
        AzureMaps["Azure Maps\n(Global)"]
    end
    class ExternalAPIs,OpenAI,Firecrawl,Apollo,Zoho,AzureMaps internet

    %% Ingress flows
    Client -->|"HTTPS:443"| AFD
    WebHook -->|"HTTPS:443"| AFD
    Admin -->|"HTTPS:443"| AFD
    DNS -.->|"Health probe"| AFD

    %% Edge to VNet
    AFD -->|"HTTPS:443<br/>Service Tag: AzureFrontDoor"| ContainerApp
    ContainerApp --> NSG

    %% Internal VNet flows
    ContainerApp -->|"TLS:6380<br/>Private Link"| RedisPrivate
    ContainerApp -->|"TLS:5432<br/>Private Link"| PGPrivate
    ContainerApp -->|"HTTPS:443<br/>Private Link"| BlobPrivate
    ContainerApp -->|"HTTPS:443<br/>Private Link"| KeyVaultPrivate
    ContainerApp -->|"HTTPS:443"| AppInsightsPrivate

    %% Azure backbone
    ContainerApp -->|"AMQP:5671<br/>Service Endpoint"| ServiceBus
    ContainerApp -->|"HTTPS:443<br/>Service Endpoint"| AISearch
    ContainerEnv -->|"Pull images<br/>Managed Identity"| ACR

    %% External API calls
    ContainerApp -->|"HTTPS:443<br/>NAT Gateway"| OpenAI
    ContainerApp -->|"HTTPS:443<br/>NAT Gateway"| Firecrawl
    ContainerApp -->|"HTTPS:443<br/>NAT Gateway"| Apollo
    ContainerApp -->|"HTTPS:443<br/>NAT Gateway"| Zoho
    ContainerApp -->|"HTTPS:443<br/>NAT Gateway"| AzureMaps

    %% Network labels
    RedisPrivate -.->|"10.0.1.0/24"| ContainerApp
    PGPrivate -.->|"10.0.1.0/24"| ContainerApp
```

### Performance & Caching Strategy Architecture

```mermaid
flowchart TB
    classDef request fill:#DBEAFE,stroke:#2563EB,stroke-width:2px
    classDef cache fill:#FEF3C7,stroke:#D97706,stroke-width:2px
    classDef compute fill:#DCFCE7,stroke:#059669,stroke-width:2px
    classDef intelligent fill:#FED7D7,stroke:#E53E3E,stroke-width:2px

    subgraph RequestPath["Request Path"]
        InboundReq["Inbound Request"]
        CacheKey["Generate Cache Key\n(email hash + fields)"]
    end
    class RequestPath,InboundReq,CacheKey request

    subgraph CDNLayer["CDN Layer (Azure Front Door)"]
        CDNCache["CDN Cache\n- Static assets (manifest, icons)\n- Cache-Control headers\n- Purge on deploy"]
        CDNHit{CDN Hit?}
        CDNReturn["Return Cached Asset\n(0ms)"]
    end
    class CDNLayer,CDNCache,CDNHit,CDNReturn cache

    subgraph RedisLayer["Redis Cache Layer"]
        IntakeCache["Intake Cache\n- Key: intake:{email_hash}\n- TTL: 2-12h\n- Stores: extracted_data"]
        EnrichCache["Enrichment Cache\n- Key: apollo:{email}\n- Key: firecrawl:{domain}\n- TTL: 24h"]
        C3Cache["C³ Cache\n- Key: c3:{embed_hash}\n- TTL: 7d\n- Stores: artifacts + margins"]
        VaultCache["Vault Cache\n- Key: vault:{locator}\n- TTL: 7d\n- Stores: canonical_records"]
        RedisHit{Cache Hit?}
        RedisReturn["Return Cached Data\n(10-50ms)"]
    end
    class RedisLayer,IntakeCache,EnrichCache,C3Cache,VaultCache,RedisHit,RedisReturn cache

    subgraph C3Intelligence["C³ Intelligent Cache"]
        CalcMargin["Calculate Margin\nδ = 1 - P(risk)"]
        CheckDrift{Embedding\nSimilarity >\nThreshold?}
        ReuseDecision{Margin >\nδ-bound?}
        SelectiveRebuild["Selective Rebuild\n(Invalidated spans only)"]
    end
    class C3Intelligence,CalcMargin,CheckDrift,ReuseDecision,SelectiveRebuild intelligent

    subgraph ComputeLayer["Compute Layer"]
        ModelSelect["VoIT Model Selection\n- nano ($0.05/1M)\n- mini ($0.25/1M)\n- large ($1.25/1M)"]
        LangGraph["LangGraph Pipeline\n- Extract\n- Research (5s timeout)\n- Validate"]
        Enrichment["Enrichment APIs\n- Firecrawl v2\n- Apollo.io\n- Azure Maps"]
        WriteCache["Write to Cache\n(All layers)"]
    end
    class ComputeLayer,ModelSelect,LangGraph,Enrichment,WriteCache compute

    subgraph Metrics["Performance Metrics"]
        CacheHitRate["Cache Hit Rate: 90%\n(Application Insights)"]
        P50["P50 Latency: 150ms"]
        P95["P95 Latency: 2.8s"]
        P99["P99 Latency: 4.2s"]
        CostSavings["Cost Savings: 65%\n(VoIT + C³)"]
    end
    class Metrics cache

    %% Flow
    InboundReq --> CacheKey
    CacheKey --> CDNHit
    CDNHit -->|Yes| CDNReturn
    CDNHit -->|No| RedisHit

    RedisHit -->|Yes| RedisReturn
    RedisHit -->|No| CalcMargin

    CalcMargin --> CheckDrift
    CheckDrift -->|High similarity| ReuseDecision
    CheckDrift -->|Low similarity| ModelSelect

    ReuseDecision -->|Yes| RedisReturn
    ReuseDecision -->|No| SelectiveRebuild

    SelectiveRebuild --> ModelSelect
    ModelSelect --> LangGraph
    LangGraph --> Enrichment
    Enrichment --> WriteCache

    WriteCache --> IntakeCache
    WriteCache --> EnrichCache
    WriteCache --> C3Cache
    WriteCache --> VaultCache

    WriteCache --> RedisReturn

    %% Metrics connections
    CDNReturn -.-> CacheHitRate
    RedisReturn -.-> CacheHitRate
    RedisReturn -.-> P50
    WriteCache -.-> P95
    Enrichment -.-> P99
    C3Cache -.-> CostSavings
    ModelSelect -.-> CostSavings
```

### Threat Model & Attack Surface Analysis

```mermaid
flowchart TB
    classDef threat fill:#FFE5E5,stroke:#DC2626,stroke-width:3px
    classDef mitigation fill:#D1FAE5,stroke:#059669,stroke-width:2px
    classDef monitoring fill:#FEF3C7,stroke:#D97706,stroke-width:2px

    subgraph AttackSurface["Attack Surface"]
        direction TB
        A1["A1: API Key Theft/Leakage"]
        A2["A2: DDoS Attack"]
        A3["A3: SQL Injection"]
        A4["A4: Secret Exposure"]
        A5["A5: Man-in-the-Middle"]
        A6["A6: Cache Poisoning"]
        A7["A7: Unauthorized Data Access"]
        A8["A8: Resource Exhaustion"]
        A9["A9: Supply Chain Attack"]
        A10["A10: Session Hijacking"]
    end
    class A1,A2,A3,A4,A5,A6,A7,A8,A9,A10 threat

    subgraph Mitigations["Security Controls"]
        direction TB

        subgraph AuthControls["Authentication Controls"]
            M1["HMAC Key Validation\n- Timing-safe comparison\n- Key rotation"]
            M2["Azure AD OAuth 2.0\n- Token validation\n- Refresh flow"]
            M3["Rate Limiting\n- 5 attempts/15min\n- IP + key tracking"]
        end

        subgraph NetworkControls["Network Controls"]
            M4["Azure Front Door WAF\n- DDoS protection\n- Geo-filtering"]
            M5["TLS 1.2+ Enforcement\n- Certificate pinning\n- HSTS headers"]
            M6["VNet Isolation\n- Private endpoints\n- NSG rules"]
        end

        subgraph DataControls["Data Controls"]
            M7["Input Validation\n- Pydantic schemas\n- Parameterized queries"]
            M8["Azure Key Vault\n- Secret rotation\n- Access policies"]
            M9["Encryption at Rest\n- Storage encryption\n- DB encryption"]
        end

        subgraph AppControls["Application Controls"]
            M10["CORS Restrictions\n- Origin validation\n- Credential checks"]
            M11["Cache Isolation\n- Key namespacing\n- TTL enforcement"]
            M12["Resource Limits\n- Request timeouts\n- Payload size caps"]
        end

        subgraph SupplyChainControls["Supply Chain Controls"]
            M13["Dependency Scanning\n- Safety checks\n- Bandit scans"]
            M14["Image Scanning\n- Trivy scans\n- ACR quarantine"]
            M15["Least Privilege\n- Managed identities\n- RBAC"]
        end
    end
    class AuthControls,NetworkControls,DataControls,AppControls,SupplyChainControls mitigation

    subgraph Detection["Detection & Monitoring"]
        direction TB
        D1["Application Insights\n- Security events\n- Anomaly detection"]
        D2["Audit Logs\n- 90-day retention\n- Immutable storage"]
        D3["Alerts\n- Failed auth spikes\n- Unusual patterns"]
        D4["Health Probes\n- Continuous validation\n- Auto-remediation"]
    end
    class Detection,D1,D2,D3,D4 monitoring

    %% Threat to Mitigation mappings
    A1 --> M1
    A1 --> M2
    A1 --> M3

    A2 --> M4
    A2 --> M12

    A3 --> M7

    A4 --> M8
    A4 --> M15

    A5 --> M5
    A5 --> M6

    A6 --> M11

    A7 --> M2
    A7 --> M15

    A8 --> M12
    A8 --> M4

    A9 --> M13
    A9 --> M14

    A10 --> M2
    A10 --> M10

    %% Monitoring connections
    M1 --> D1
    M2 --> D1
    M3 --> D3
    M4 --> D2
    M8 --> D2
    M13 --> D4
    M14 --> D4
```

### Monitoring & Observability Architecture

```mermaid
flowchart TB
    classDef source fill:#E0E7FF,stroke:#4338CA,stroke-width:2px
    classDef collect fill:#FEF3C7,stroke:#D97706,stroke-width:2px
    classDef analyze fill:#DCFCE7,stroke:#059669,stroke-width:2px
    classDef alert fill:#FED7D7,stroke:#E53E3E,stroke-width:2px

    subgraph DataSources["Telemetry Sources"]
        direction TB
        App["FastAPI Application\n- Structured logging\n- Custom metrics\n- Trace context"]
        Container["Container Apps\n- stdout/stderr\n- Resource metrics\n- HTTP access logs"]
        Azure["Azure Resources\n- Redis metrics\n- PostgreSQL metrics\n- Blob metrics\n- Service Bus metrics"]
        Security["Security Events\n- Auth failures\n- Rate limit hits\n- Key Vault access"]
    end
    class DataSources,App,Container,Azure,Security source

    subgraph Collection["Collection Layer"]
        direction TB
        AppInsights["Application Insights\n- OpenTelemetry SDK\n- Auto-instrumentation\n- Sampling (10%)"]
        LogAnalytics["Log Analytics Workspace\n- Kusto queries\n- 90-day retention\n- Cross-resource queries"]
        Metrics["Azure Monitor Metrics\n- 1-minute granularity\n- Aggregation\n- Alerts"]
    end
    class Collection,AppInsights,LogAnalytics,Metrics collect

    subgraph Analysis["Analysis & Dashboards"]
        direction TB

        subgraph Dashboards["Monitoring Dashboards"]
            OpsDash["Operations Dashboard\n- Request rate\n- Error rate\n- Latency (P50/P95/P99)\n- Instance count"]
            CostDash["Cost Dashboard\n- AI token usage\n- VoIT model selection\n- Cache hit rate\n- Cost per request"]
            SecurityDash["Security Dashboard\n- Auth attempts\n- Rate limit violations\n- Secret access\n- IP patterns"]
            VaultDash["Vault Agent Dashboard\n- VOI calculations\n- C³ hit rate\n- Quality scores\n- Budget tracking"]
        end

        subgraph Queries["Custom Queries"]
            TraceQuery["Distributed Traces\n- End-to-end flows\n- Span correlation\n- Bottleneck detection"]
            ErrorQuery["Error Analysis\n- Exception types\n- Stack traces\n- Frequency trends"]
            PerformQuery["Performance Analysis\n- Cache effectiveness\n- API latency\n- Resource utilization"]
        end
    end
    class Analysis,Dashboards,Queries,OpsDash,CostDash,SecurityDash,VaultDash,TraceQuery,ErrorQuery,PerformQuery analyze

    subgraph Alerting["Alerting & Response"]
        direction TB

        subgraph Alerts["Alert Rules"]
            HealthAlert["Health Alerts\n- Endpoint downtime\n- Database connection failures\n- Redis unavailability"]
            PerformAlert["Performance Alerts\n- P95 latency > 5s\n- Error rate > 5%\n- Cache hit rate < 80%"]
            SecurityAlert["Security Alerts\n- Failed auth > 10/min\n- Unusual IP patterns\n- Secret rotation needed"]
            CostAlert["Cost Alerts\n- Daily budget exceeded\n- Unusual token usage\n- VoIT budget overrun"]
        end

        subgraph Actions["Alert Actions"]
            Email["Email Notifications"]
            Teams["Microsoft Teams Webhook"]
            AutoRemediate["Auto-remediation\n- Scale out\n- Cache invalidation\n- Emergency rollback"]
        end
    end
    class Alerting,Alerts,Actions,HealthAlert,PerformAlert,SecurityAlert,CostAlert,Email,Teams,AutoRemediate alert

    subgraph KPIs["Business KPIs"]
        direction LR
        K1["Processing Speed\nTarget: <3s"]
        K2["Cache Hit Rate\nTarget: 90%"]
        K3["Uptime\nTarget: 99.9%"]
        K4["Cost per Request\nTarget: $0.02"]
        K5["Data Quality\nTarget: 95% accuracy"]
    end
    class KPIs analyze

    %% Data flow
    App --> AppInsights
    Container --> AppInsights
    Azure --> Metrics
    Security --> AppInsights

    AppInsights --> LogAnalytics
    Metrics --> LogAnalytics

    LogAnalytics --> OpsDash
    LogAnalytics --> CostDash
    LogAnalytics --> SecurityDash
    LogAnalytics --> VaultDash

    LogAnalytics --> TraceQuery
    LogAnalytics --> ErrorQuery
    LogAnalytics --> PerformQuery

    OpsDash --> HealthAlert
    CostDash --> CostAlert
    SecurityDash --> SecurityAlert
    VaultDash --> PerformAlert

    HealthAlert --> Email
    PerformAlert --> Teams
    SecurityAlert --> Email
    CostAlert --> Teams

    HealthAlert --> AutoRemediate
    PerformAlert --> AutoRemediate

    %% KPI connections
    OpsDash -.-> K1
    CostDash -.-> K4
    VaultDash -.-> K2
    HealthAlert -.-> K3
    ErrorQuery -.-> K5
```

### Complete Codebase Component Map (File-Level Architecture)

```mermaid
flowchart TB
    classDef frontend fill:#E0E7FF,stroke:#4338CA,stroke-width:2px
    classDef core fill:#DCFCE7,stroke:#059669,stroke-width:2px
    classDef vault fill:#FED7D7,stroke:#E53E3E,stroke-width:3px
    classDef integration fill:#FCE7F3,stroke:#C026D3,stroke-width:2px
    classDef data fill:#FEF3C7,stroke:#D97706,stroke-width:2px
    classDef infra fill:#F3E8FF,stroke:#7C3AED,stroke-width:2px
    classDef test fill:#FEE2E2,stroke:#DC2626,stroke-width:2px

    subgraph OutlookAddin["📱 Outlook Add-in (addin/)"]
        direction TB
        ManifestXML["manifest.xml\n(Office Add-in config)"]
        ManifestJSON["manifest.json\n(Unified manifest)"]
        TaskpaneHTML["taskpane.html\n(Main UI)"]
        TaskpaneJS["taskpane.js\n(Form logic + API calls)"]
        CommandsHTML["commands.html\n(Ribbon handlers)"]
        CommandsJS["commands.js\n(Button actions)"]
        ConfigJS["config.js\n(Environment settings)"]
        ApolloJS["apollo.js\n(Contact enrichment)"]
        AppJS["app.js\n(Core logic)"]
        Icons["icon-*.png\n(16/32/64/80/128px)"]
    end
    class OutlookAddin,ManifestXML,ManifestJSON,TaskpaneHTML,TaskpaneJS,CommandsHTML,CommandsJS,ConfigJS,ApolloJS,AppJS,Icons frontend

    subgraph FastAPICore["🚀 FastAPI Core (app/)"]
        direction TB
        MainPy["main.py\n(FastAPI app + routers)"]
        ConfigPy["config.py\n(Settings + env vars)"]
        DatabasePy["database.py\n(SQLModel + async session)"]
        SecurityPy["security_config.py\n(API key + Azure Key Vault)"]
        LoggingPy["logging_config.py\n(Structured logging)"]
        MonitoringPy["monitoring.py\n(App Insights integration)"]
    end
    class FastAPICore,MainPy,ConfigPy,DatabasePy,SecurityPy,LoggingPy,MonitoringPy core

    subgraph NovelAlgorithms["🚨 Revolutionary Optimization (app/orchestrator/ + app/cache/)"]
        direction TB

        subgraph VoITSystem["VoIT Algorithm (Cross-Cutting)"]
            VoITController["voit_controller.py\n(VOI calculation + budget)"]
            SpanProcessor["span_processor.py\n(Uncertainty metrics + actions)"]
            ActionSelector["action_selector.py\n(Cost tier selection)"]
        end

        subgraph C3System["C³ Algorithm (Cross-Cutting)"]
            C3Manager["c3_manager.py\n(Reuse-or-rebuild logic)"]
            C3Storage["c3_storage.py\n(Redis serialization)"]
            CacheMetrics["cache_metrics.py\n(Hit/miss tracking)"]
        end

        RedisManager["redis_cache_manager.py\n(Standard cache operations)"]
    end
    class NovelAlgorithms,VoITSystem,C3System vault
    class VoITController,SpanProcessor,ActionSelector,C3Manager,C3Storage,CacheMetrics,RedisManager vault

    subgraph VaultAgentFeature["📋 Candidate Vault Agent (app/api/vault_agent/ + app/jobs/)"]
        direction TB

        subgraph VaultAPI["API Layer"]
            VaultRoutes["routes.py\n(/ingest, /publish, /status)"]
            VaultModels["models.py\n(Pydantic schemas)"]
        end

        subgraph VaultAggregation["Data Aggregation"]
            Normalizer["normalizer.py\n(Canonical format)"]
            Aggregator["aggregator.py\n(Zoho vault + enrichments)"]
        end

        subgraph VaultJobs["Background Jobs"]
            TalentWellCurator["talentwell_curator.py\n(Advisor alerts)"]
            BatchProcessor["batch_processor.py\n(Multi-email)"]
        end

        subgraph VaultExtract["Evidence Extraction"]
            EvidenceExtractor["evidence_extractor.py\n(Bullet points)"]
            FinancialPatterns["financial_patterns.py\n(AUM/production/licenses)"]
        end

        subgraph VaultValidation["Format Validation"]
            CardValidator["card_validator.py\n(DigestCard format ‼️🔔📍)"]
            QualityMetrics["quality_metrics.py\n(Scoring)"]
        end

        subgraph PrivacyFeatures["Privacy & AI Features (NEW)"]
            FeatureFlags["feature_flags.py\n(PRIVACY_MODE, GROWTH, SENTIMENT)"]
            PrivacyMethods["talentwell_curator.py\n(_anonymize_company, _standardize_compensation,\n_extract_growth_metrics, _analyze_sentiment)"]
        end
    end
    class VaultAgentFeature,VaultAPI,VaultAggregation,VaultJobs,VaultExtract,VaultValidation,PrivacyFeatures core
    class VaultRoutes,VaultModels,Normalizer,Aggregator,TalentWellCurator,BatchProcessor,EvidenceExtractor,FinancialPatterns,CardValidator,QualityMetrics,FeatureFlags,PrivacyMethods core

    subgraph LangGraphPipeline["🤖 LangGraph Pipeline (app/)"]
        direction TB
        LangGraphMgr["langgraph_manager.py\n(Extract → Research → Validate)"]
        SimplifiedExtractor["simplified_extractor.py\n(Fallback extraction)"]
        BusinessRules["business_rules.py\n(Deal naming + source)"]
        ConfidenceEngine["confidence_engine.py\n(Scoring + gating)"]
    end
    class LangGraphPipeline,LangGraphMgr,SimplifiedExtractor,BusinessRules,ConfidenceEngine core

    subgraph Integrations["🔌 External Integrations (app/)"]
        direction TB

        subgraph ZohoIntegration["Zoho CRM"]
            ZohoClient["integrations.py\n(Zoho v8 API client)"]
            ZohoOAuth["oauth_client.py\n(Token management)"]
        end

        subgraph AIIntegrations["AI Services"]
            OpenAIClient["openai_client.py\n(GPT-5 tiers)"]
            FirecrawlV2["firecrawl_v2_fire_agent.py\n(FIRE-1 enrichment)"]
            ApolloClient["apollo_client.py\n(Contact enrichment)"]
        end

        subgraph AzureIntegrations["Azure Services"]
            MapsClient["azure_maps_client.py\n(Geocoding)"]
            BlobClient["blob_client.py\n(Attachment storage)"]
            ServiceBusClient["service_bus_manager.py\n(Batch queues)"]
            AISearchClient["azure_ai_search_manager.py\n(Semantic patterns)"]
        end

        subgraph ZoomIntegration["Zoom"]
            ZoomClient["zoom_client.py\n(Transcripts + recordings)"]
        end
    end
    class Integrations,ZohoIntegration,AIIntegrations,AzureIntegrations,ZoomIntegration,ZohoClient,ZohoOAuth,OpenAIClient,FirecrawlV2,ApolloClient,MapsClient,BlobClient,ServiceBusClient,AISearchClient,ZoomClient integration

    subgraph DataModels["📊 Data Models (app/models/)"]
        direction TB
        ExtractedData["extracted_data.py\n(Pydantic schemas)"]
        DealModel["deal.py\n(SQLModel ORM)"]
        ContactModel["contact.py\n(SQLModel ORM)"]
        VaultRecord["vault_record.py\n(Canonical record)"]
        LearningEvent["learning_event.py\n(AI feedback)"]
        CorrectionLog["correction_log.py\n(Field changes)"]
        BatchJob["batch_job.py\n(Batch tracking)"]
    end
    class DataModels,ExtractedData,DealModel,ContactModel,VaultRecord,LearningEvent,CorrectionLog,BatchJob data

    subgraph Database["🗄️ Database Layer"]
        direction TB
        PostgreSQL["PostgreSQL\n(pgvector + 400K context)"]
        Alembic["migrations/\n(Alembic migrations)"]
        InitDB["initialize_database.py\n(Schema setup)"]
    end
    class Database,PostgreSQL,Alembic,InitDB data

    subgraph CacheLayer["⚡ Cache Layer"]
        direction TB
        RedisDB["Azure Cache for Redis\n(Standard C1, 1GB)"]
        CacheStrategies["cache_strategies.py\n(Email classification)"]
        CostOptimizer["azure_cost_optimizer.py\n(Model selection)"]
    end
    class CacheLayer,RedisDB,CacheStrategies,CostOptimizer data

    subgraph Infrastructure["☁️ Infrastructure & DevOps"]
        direction TB

        subgraph Docker["Docker"]
            Dockerfile["Dockerfile\n(Multi-stage build)"]
            DockerCompose["docker-compose.yml\n(Local dev)"]
        end

        subgraph Scripts["scripts/"]
            DeployScript["deploy.sh\n(Full deployment)"]
            WarmupScript["manifest_warmup.py\n(Cache warming)"]
            MigrationScript["run_migrations.sh\n(DB updates)"]
        end

        subgraph GitHub["GitHub Actions (.github/workflows/)"]
            ManifestWorkflow["manifest-cache-bust.yml\n(Add-in deploy)"]
            DeployWorkflow["deploy-production.yml\n(Main deploy)"]
            RollbackWorkflow["emergency-rollback.yml\n(Instant rollback)"]
        end
    end
    class Infrastructure,Docker,Scripts,GitHub,Dockerfile,DockerCompose,DeployScript,WarmupScript,MigrationScript,ManifestWorkflow,DeployWorkflow,RollbackWorkflow infra

    subgraph Testing["🧪 Testing (tests/)"]
        direction TB

        subgraph TestCategories["Test Suites"]
            ApolloTests["apollo/\n(Apollo.io integration)"]
            FirecrawlTests["firecrawl/\n(Firecrawl v2)"]
            IntegrationTests["integration/\n(End-to-end)"]
            ProductionTests["production/\n(Smoke tests)"]
            ZoomTests["zoom/\n(Transcript tests)"]
        end

        TestRunner["run_all_tests.py\n(Organized test runner)"]
        PytestConfig["pytest.ini\n(Configuration)"]
    end
    class Testing,TestCategories,ApolloTests,FirecrawlTests,IntegrationTests,ProductionTests,ZoomTests,TestRunner,PytestConfig test

    subgraph Documentation["📚 Documentation (docs/)"]
        direction TB
        CLAUDE["CLAUDE.md\n(AI assistant config)"]
        AGENTS["AGENTS.md\n(Architecture docs)"]
        GeoDoc["geo/azure_maps.md\n(Geocoding setup)"]
    end
    class Documentation,CLAUDE,AGENTS,GeoDoc infra

    subgraph Runners["▶️ Application Runners"]
        direction TB
        TalentWellRunner["run_talentwell_with_real_twav.py\n(Curator executor)"]
        DigestHTML["Advisor_Vault_Candidate_Alerts.html\n(Output template)"]
    end
    class Runners,TalentWellRunner,DigestHTML vault

    subgraph SharedLibrary["📦 Shared Library (well_shared/)"]
        direction TB

        subgraph SharedCache["cache/"]
            SharedRedisManager["redis_manager.py\n(Connection pooling, batch ops)"]
            SharedC3["c3.py\n(C³ implementation)"]
            SharedVoIT["voit.py\n(VoIT span caching)"]
        end

        subgraph SharedDatabase["database/"]
            SharedConnection["connection.py\n(Async SQLAlchemy sessions)"]
        end

        subgraph SharedMail["mail/"]
            SharedSender["sender.py\n(Azure Communication Services)"]
        end

        subgraph SharedEvidence["evidence/"]
            SharedExtractor["extractor.py\n(Bullet generation)"]
        end

        subgraph SharedTelemetry["telemetry/"]
            SharedInsights["insights.py\n(Application Insights batching)"]
        end

        subgraph SharedConfig["config/"]
            SharedVoITConfig["voit_config.py\n(Model tier costs, budgets)"]
        end

        subgraph SharedZoho["zoho/"]
            SharedZohoCommon["__init__.py\n(Shared Zoho constants)"]
        end

        SharedSetup["setup.py\n(Package metadata, v0.1.0)"]
        SharedRequirements["requirements.txt\n(Dependency specs)"]
    end
    class SharedLibrary,SharedCache,SharedDatabase,SharedMail,SharedEvidence,SharedTelemetry,SharedConfig,SharedZoho core
    class SharedRedisManager,SharedC3,SharedVoIT,SharedConnection,SharedSender,SharedExtractor,SharedInsights,SharedVoITConfig,SharedZohoCommon,SharedSetup,SharedRequirements core

    subgraph TeamsBotService["💬 Teams Bot Service (teams_bot/)"]
        direction TB

        subgraph TeamsBotApp["teams_bot/app/"]
            TeamsBotMain["main.py\n(FastAPI app, Port 8001)"]
            TeamsBotConfig["config.py\n(Bot settings)"]
        end

        subgraph TeamsBotAPI["teams_bot/app/api/"]
            TeamsBotHealthCheck["health_check.py\n(Health endpoints)"]

            subgraph TeamsBotTeamsRoutes["teams/"]
                TeamsBotRoutes["routes.py\n(Bot endpoints)"]
                TeamsBotDialogFlow["dialog_flow.py\n(Conversation flow)"]
                TeamsBotAdaptiveCards["adaptive_cards.py\n(Card templates)"]
            end
        end

        subgraph TeamsBotServices["teams_bot/app/services/"]
            TeamsBotNLP["nlp_query_service.py\n(Intent classification, GPT-5-mini)"]
            TeamsBotProactive["proactive_messaging.py\n(Weekly digest delivery)"]
            TeamsBotMessageBus["message_bus.py\n(Service Bus integration)"]
            TeamsBotCircuitBreaker["circuit_breaker.py\n(Fault tolerance)"]
        end

        subgraph TeamsBotWorkers["teams_bot/app/workers/"]
            TeamsBotDigestWorker["digest_worker.py\n(Service Bus consumer)"]
            TeamsBotNLPWorker["nlp_worker.py\n(Vault marketability)"]
        end

        subgraph TeamsBotModels["teams_bot/app/models/"]
            TeamsBotUserPrefs["user_preferences.py\n(PostgreSQL ORM)"]
            TeamsBotDigestDelivery["digest_delivery.py\n(Tracking)"]
            TeamsBotAnalytics["analytics.py\n(Conversation metrics)"]
        end

        TeamsBotRequirements["requirements.txt\n(Bot Framework SDK, httpx)"]
        TeamsBotDockerfile["Dockerfile\n(Multi-stage build)"]
    end
    class TeamsBotService,TeamsBotApp,TeamsBotAPI,TeamsBotServices,TeamsBotWorkers,TeamsBotModels core
    class TeamsBotMain,TeamsBotConfig,TeamsBotHealthCheck,TeamsBotTeamsRoutes,TeamsBotRoutes,TeamsBotDialogFlow,TeamsBotAdaptiveCards,TeamsBotNLP,TeamsBotProactive,TeamsBotMessageBus,TeamsBotCircuitBreaker,TeamsBotDigestWorker,TeamsBotNLPWorker,TeamsBotUserPrefs,TeamsBotDigestDelivery,TeamsBotAnalytics,TeamsBotRequirements,TeamsBotDockerfile core

    %% Frontend connections
    TaskpaneJS --> MainPy
    ApolloJS --> ApolloClient
    ManifestXML --> BlobClient
    ConfigJS --> SecurityPy

    %% Core connections
    MainPy --> VaultRoutes
    MainPy --> LangGraphMgr
    MainPy --> ZohoClient
    SecurityPy --> ZohoOAuth
    DatabasePy --> PostgreSQL
    MonitoringPy --> LoggingPy

    %% Novel algorithms (cross-cutting) connections
    VoITController --> SpanProcessor
    SpanProcessor --> ActionSelector
    ActionSelector --> OpenAIClient
    C3Manager --> C3Storage
    C3Storage --> RedisManager
    C3Manager --> CacheMetrics

    %% VoIT/C³ used by all processing paths
    LangGraphMgr -.->|"Uses"| VoITController
    LangGraphMgr -.->|"Uses"| C3Manager
    VaultRoutes -.->|"Uses"| VoITController
    VaultRoutes -.->|"Uses"| C3Manager
    BatchProcessor -.->|"Uses"| VoITController
    BatchProcessor -.->|"Uses"| C3Manager

    %% Vault Agent feature connections
    VaultRoutes --> Normalizer
    VaultRoutes --> Aggregator
    Aggregator --> ZohoClient
    Normalizer --> VaultRecord
    TalentWellCurator --> EvidenceExtractor
    EvidenceExtractor --> FinancialPatterns
    TalentWellCurator --> CardValidator
    CardValidator --> QualityMetrics
    TalentWellCurator --> FeatureFlags
    TalentWellCurator --> PrivacyMethods

    %% LangGraph connections
    LangGraphMgr --> BusinessRules
    LangGraphMgr --> ConfidenceEngine
    LangGraphMgr --> SimplifiedExtractor
    LangGraphMgr --> FirecrawlV2
    LangGraphMgr --> ApolloClient
    LangGraphMgr --> MapsClient

    %% Integration connections
    ZohoClient --> ZohoOAuth
    FirecrawlV2 --> RedisManager
    ApolloClient --> RedisManager
    BlobClient --> ManifestXML
    ServiceBusClient --> BatchProcessor
    AISearchClient --> RedisManager
    ZoomClient --> TalentWellCurator

    %% Data model connections
    ExtractedData --> DealModel
    ExtractedData --> ContactModel
    VaultRecord --> LearningEvent
    DealModel --> CorrectionLog
    BatchJob --> DatabasePy

    %% Cache connections
    C3Storage --> RedisDB
    RedisManager --> RedisDB
    CacheStrategies --> RedisManager
    CostOptimizer --> VoITController

    %% Database connections
    DealModel --> PostgreSQL
    ContactModel --> PostgreSQL
    VaultRecord --> PostgreSQL
    LearningEvent --> PostgreSQL
    Alembic --> PostgreSQL
    InitDB --> PostgreSQL

    %% Infrastructure connections
    Dockerfile --> MainPy
    DeployScript --> ManifestWorkflow
    WarmupScript --> DeployWorkflow
    MigrationScript --> Alembic

    %% Testing connections
    TestRunner --> ApolloTests
    TestRunner --> FirecrawlTests
    TestRunner --> IntegrationTests
    ApolloTests --> ApolloClient
    FirecrawlTests --> FirecrawlV2
    IntegrationTests --> MainPy
    ProductionTests --> MainPy
    ZoomTests --> ZoomClient

    %% Documentation connections
    CLAUDE --> MainPy
    AGENTS --> VaultRoutes
    GeoDoc --> MapsClient

    %% Runner connections
    TalentWellRunner --> TalentWellCurator
    TalentWellRunner --> DigestHTML

    %% Shared Library connections (consumed by all services)
    MainPy -.->|"pip install -e"| SharedSetup
    TeamsBotMain -.->|"pip install -e"| SharedSetup
    DatabasePy --> SharedConnection
    RedisManager --> SharedRedisManager
    C3Manager --> SharedC3
    VoITController --> SharedVoIT
    MonitoringPy --> SharedInsights
    TalentWellCurator --> SharedExtractor
    SharedConnection --> PostgreSQL
    SharedRedisManager --> RedisDB
    SharedSender --> BlobClient
    SharedInsights --> LoggingPy

    %% Teams Bot Service connections
    TeamsBotMain --> TeamsBotRoutes
    TeamsBotMain --> TeamsBotHealthCheck
    TeamsBotRoutes --> TeamsBotNLP
    TeamsBotRoutes --> TeamsBotDialogFlow
    TeamsBotRoutes --> TeamsBotAdaptiveCards
    TeamsBotNLP -.->|"Uses"| VoITController
    TeamsBotNLP --> SharedConnection
    TeamsBotNLP --> ZohoClient
    TeamsBotDialogFlow --> TeamsBotUserPrefs
    TeamsBotProactive --> TeamsBotDigestWorker
    TeamsBotProactive --> SharedSender
    TeamsBotMessageBus --> ServiceBusClient
    TeamsBotDigestWorker -.->|"Uses"| VoITController
    TeamsBotDigestWorker -.->|"Uses"| C3Manager
    TeamsBotDigestWorker --> ZohoClient
    TeamsBotDigestWorker --> SharedRedisManager
    TeamsBotNLPWorker -.->|"Uses"| VoITController
    TeamsBotNLPWorker --> ZohoClient
    TeamsBotUserPrefs --> PostgreSQL
    TeamsBotDigestDelivery --> PostgreSQL
    TeamsBotAnalytics --> PostgreSQL
    TeamsBotCircuitBreaker --> TeamsBotMessageBus
```

### VoIT + C³ Revolutionary Algorithms - Detailed Implementation
**🚨 Novel contribution: These algorithms optimize ALL content processing system-wide**

```mermaid
flowchart LR
    classDef novel fill:#FED7D7,stroke:#E53E3E,stroke-width:4px
    classDef cache fill:#FEF3C7,stroke:#D97706,stroke-width:2px
    classDef feature fill:#E0E7FF,stroke:#4338CA,stroke-width:2px
    classDef jobs fill:#DCFCE7,stroke:#059669,stroke-width:2px
    classDef extract fill:#FCE7F3,stroke:#C026D3,stroke-width:2px
    classDef validate fill:#F3E8FF,stroke:#7C3AED,stroke-width:2px

    subgraph NovelVoIT["🚨 VoIT Algorithm (app/orchestrator/) - REVOLUTIONARY"]
        VoITCtrl["voit_controller.py\n• VOI calculation: qgain - λ*cost - μ*latency\n• Budget allocation\n• Model tier selection (nano/mini/large)\n• Quality tracking\n• FIRST-OF-ITS-KIND"]

        SpanProc["span_processor.py\n• Uncertainty metrics calculation\n• Action evaluation (4 tiers)\n• Span sorting by uncertainty\n• Cost tracking\n• NOVEL UNCERTAINTY QUANTIFICATION"]

        ActionSelector["action_selector.py\n• Reuse cached (cost=0.01)\n• Small LLM (cost=1.0)\n• Tool call (cost=1.8)\n• Deep LLM (cost=3.5)\n• ADAPTIVE TIER SELECTION"]
    end
    class NovelVoIT,VoITCtrl,SpanProc,ActionSelector novel

    subgraph NovelC3["🚨 C³ Algorithm (app/cache/) - REVOLUTIONARY"]
        C3Mgr["c3_manager.py\n• Probabilistic margin calc (δ-bound)\n• Embedding similarity + drift detection\n• Reuse-or-rebuild logic\n• Dependency tracking with certificates\n• BEYOND TRADITIONAL CACHE HIT/MISS"]

        C3Store["c3_storage.py\n• Entry serialization\n• Redis operations\n• TTL management (7d)\n• Certificate storage\n• CAUSAL DEPENDENCY TRACKING"]

        CacheMetrics["cache_metrics.py\n• Hit/miss tracking (90% vs 50% trad)\n• Cost savings calculation\n• Performance metrics\n• Alert triggers"]
    end
    class NovelC3,C3Mgr,C3Store,CacheMetrics novel

    subgraph StandardCache["Standard Redis Operations"]
        RedisMgr["redis_cache_manager.py\n• Key namespacing\n• Batch operations\n• Health checks\n• Standard TTL management"]
    end
    class StandardCache,RedisMgr cache

    subgraph VaultAgentFeature["📋 Candidate Vault Agent Feature (Uses VoIT/C³)"]
        VaultAPI["vault_agent/routes.py\n• /ingest - Multi-source aggregation\n• /publish - Digest generation\n• /status - Feature flags"]

        Normalizer["normalizer.py\n• Zoho vault → canonical\n• Resume → canonical\n• Transcript → canonical\n• Web → canonical"]
    end
    class VaultAgentFeature,VaultAPI,Normalizer feature

    subgraph VaultJobs["Background Jobs (Use VoIT/C³)"]
        TWCurator["talentwell_curator.py\n• Advisor-specific alerts\n• Evidence extraction\n• Digest generation (‼️🔔📍 format)"]

        BatchProc["batch_processor.py\n• 50 emails/batch\n• Service Bus integration\n• Dead-letter handling"]
    end
    class VaultJobs,TWCurator,BatchProc jobs

    subgraph ExtractLayer["Evidence Extraction"]
        EvidExtract["evidence_extractor.py\n• Bullet point generation\n• Transcript analysis\n• CRM data mining"]

        FinPattern["financial_patterns.py\n• AUM detection (regex)\n• Production patterns\n• License extraction"]
    end
    class ExtractLayer,EvidExtract,FinPattern extract

    subgraph ValidateLayer["Format Validation"]
        CardValid["card_validator.py\n• DigestCard format (‼️🔔📍)\n• Bullet count (3-5)\n• No fake data enforcement"]

        QualityMetrics["quality_metrics.py\n• Retrieval dispersion\n• Rule conflicts\n• C³ margin\n• Overall quality score"]
    end
    class ValidateLayer,CardValid,QualityMetrics validate

    %% VoIT/C³ internal connections
    VoITCtrl --> SpanProc
    SpanProc --> ActionSelector
    ActionSelector --> C3Mgr
    C3Mgr --> C3Store
    C3Store --> RedisMgr
    C3Mgr --> CacheMetrics

    %% Features use VoIT/C³
    VaultAPI -.->|"Optimized by"| VoITCtrl
    VaultAPI -.->|"Cached by"| C3Mgr
    Normalizer -.->|"Optimized by"| VoITCtrl
    TWCurator -.->|"Optimized by"| VoITCtrl
    TWCurator -.->|"Cached by"| C3Mgr
    BatchProc -.->|"Optimized by"| VoITCtrl
    BatchProc -.->|"Cached by"| C3Mgr

    %% Feature-specific connections
    VaultAPI --> Normalizer
    TWCurator --> EvidExtract
    EvidExtract --> FinPattern
    TWCurator --> CardValid
    CardValid --> QualityMetrics
    SpanProc --> QualityMetrics
```

### Deployment & Operations Snapshot

- GitHub Actions builds the Outlook add-in, Docker images, and runs manifest cache-bust workflows prior to promoting new revisions to Azure Container Apps.
- Multi-revision deployment with traffic split enables blue-green deployments and instant rollback.
- Cache warmers populate Redis and blob metadata immediately post-deploy to keep first-run latency low.
- Emergency rollback scripts shift traffic to the previous container revision and invalidate Redis keys to maintain consistency.
- Vault Agent feature flags (`FEATURE_C3`, `FEATURE_VOIT`) enable gradual rollout and A/B testing of intelligent optimization.
- Health checks validate `/health` and `/health/database` endpoints before routing traffic.
- CDN purge ensures manifest changes propagate to all Outlook clients within minutes.


## Development Guide

### Environment
- Python 3.11+
- Node.js 18+ for the add-in
- Redis 6.x (local container recommended)
- PostgreSQL 15 with `pgvector` extension

Use the provided helper scripts:

```bash
# Launch local infra with Docker Compose (Redis + PostgreSQL)
./scripts/startup.sh

# Seed sample data / fixtures
python app/admin/seed_policies.py
```

### Configuration

`app/.env.local.example` documents the required variables. Key items:

- `OPENAI_API_KEY` / `AZURE_OPENAI_ENDPOINT`
- `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`
- `FIRECRAWL_API_KEY`, `APOLLO_API_KEY`
- `REDIS_URL`, `DATABASE_URL`
- Optional geocoding: `ENABLE_AZURE_MAPS`, `AZURE_MAPS_KEY` (or Key Vault secret), `AZURE_MAPS_DEFAULT_COUNTRY`
- Candidate Vault Agent features:
  - `FEATURE_C3=true` - Enable C³ probabilistic caching
  - `FEATURE_VOIT=true` - Enable VoIT adaptive reasoning
  - `C3_DELTA=0.01` - Risk bound for cache reuse (1% default)
  - `VOIT_BUDGET=5.0` - Processing budget in cost units
  - `TARGET_QUALITY=0.9` - Target quality score for span processing
  - `VOIT_LAM=0.3` - Cost weight (λ) in VOI calculation
  - `VOIT_MU=0.2` - Latency weight (μ) in VOI calculation

For the Outlook add-in, set `API_BASE_URL` and `API_KEY` in `addin/config.js` or `.env` depending on deployment target.

> Detailed geocoding setup lives in [`docs/geo/azure_maps.md`](docs/geo/azure_maps.md).

### Useful Commands

```bash
# Run FastAPI with autoreload
uvicorn app.main:app --reload --port 8000

# Run background batch pipeline
python run_all_tests.py --mode batch

# Run TalentWell Curator with Vault Agent
python run_talentwell_with_real_twav.py  # Generates advisor candidate alerts

# Test Vault Agent endpoints
curl -X GET "http://localhost:8000/api/vault-agent/status" -H "X-API-Key: your-key"
curl -X POST "http://localhost:8000/api/vault-agent/ingest" \
  -H "X-API-Key: your-key" -H "Content-Type: application/json" \
  -d '{"source": "email", "payload": {...}}'

# Start taskpane in development mode
npm run dev --prefix addin

# Lint add-in code
npm run lint --prefix addin
```


## Testing

### Test Organization
The test suite is organized by feature area with comprehensive coverage across unit, integration, and end-to-end tests.

```bash
# Run all tests
pytest

# Run specific test suites by directory
pytest tests/apollo/             # Apollo.io integration tests
pytest tests/firecrawl/          # Firecrawl v2 integration tests
pytest tests/integration/        # End-to-end integration tests
pytest tests/production/         # Production environment smoke tests
pytest tests/talentwell/         # TalentWell curator, privacy, AI features
pytest tests/zoom/              # Zoom API integration tests

# Run add-in endpoint tests
pytest tests/test_addin_endpoints.py

# Coverage reporting
pytest --cov=app --cov-report=term-missing
pytest --cov=app --cov-report=html  # HTML report in htmlcov/
```

### TalentWell Test Suite
Privacy and AI enhancement features have comprehensive test coverage (51 tests):

```bash
# Run all TalentWell tests
pytest tests/talentwell/ -v

# Privacy mode and data quality (15 tests)
pytest tests/talentwell/test_data_quality.py -v
# Tests: company anonymization, strict compensation formatting,
#        location bullet suppression, rollback behavior

# Growth extraction and sentiment scoring (29 tests)
pytest tests/talentwell/test_bullet_ranking.py -v
# Tests: percentage patterns ("grew 40% YoY"), dollar ranges ("$1B → $1.5B"),
#        edge cases, sentiment analysis, score-based ranking

# End-to-end integration tests (7 tests)
pytest tests/talentwell/test_privacy_integration.py -v
# Tests: full digest generation with privacy mode, rollback behavior,
#        growth + privacy interaction, compensation edge cases, AUM rounding

# Coverage for TalentWell curator
pytest --cov=app.jobs.talentwell_curator --cov-report=term-missing
```

### Test Patterns & Best Practices
- **Monkeypatching** - Feature flags are tested using `monkeypatch.setattr(curator_module, "PRIVACY_MODE", True)`
- **AsyncMock** - Zoho client and Redis dependencies mocked with `AsyncMock()`
- **Fixtures** - Shared fixtures in `tests/fixtures/` for sample deals, transcripts, CRM data
- **Parameterized Tests** - Edge cases tested with `@pytest.mark.parametrize`
- **Integration Tests** - Full end-to-end scenarios with mocked external dependencies

### Manual Testing
- **Outlook Add-in** - Load add-in with Office 365 developer tenant, test Send/Test flows
- **Teams Bot** - Test commands in Teams: `digest`, `preferences`, `analytics`, `help`
- **Smoke Tests** - Automated smoke test script: `./run_tests.sh`

### CI/CD Testing
GitHub Actions workflows run tests automatically on:
- Pull requests to `main` branch
- Manifest changes (triggers `manifest-cache-bust.yml`)
- Manual workflow dispatch

Include `pytest --cov=app --cov-report=term-missing` for coverage when assessing dead code before deletion.


## CI/CD & Operations

- **Manifest Cache Busting Workflow** (`.github/workflows/manifest-cache-bust.yml`)
  - Auto-detects add-in changes, bumps manifest version, clears caches, builds Docker image, deploys to Azure Container Apps.
  - Skips deployment gracefully when Azure secrets are missing; generates PRs for protected branches.

- **Emergency Rollback** (`emergency-rollback.yml`)
  - Traffic shift back to previous Azure Container Apps revision with post-rollback health checks.

- **Cache Warmers & Health**
  - `/health`, `/cache/status`, `/cache/warmup`, `/cache/invalidate` endpoints available.

- **Logging & Monitoring**
  - Structured JSON logging via `app/logging_config.py`.
  - Application Insights integration configured in Azure deployment scripts.


## Directory Layout

```
.
├── addin/                 # Outlook taskpane (TypeScript, HTML, CSS)
├── app/                   # FastAPI service, LangGraph orchestration, integrations
│   ├── api/
│   │   └── vault_agent/   # Vault Agent REST endpoints (/ingest, /publish, /status)
│   ├── cache/             # Cache implementations (C³, Redis)
│   ├── orchestrator/      # VoIT controller and span processing
│   ├── jobs/              # Background jobs (TalentWell Curator)
│   ├── extract/           # Evidence extraction and bullet point generation
│   ├── validation/        # TalentWell card validators
│   └── mail/              # Email sending helpers
├── docs/                  # Reference material & ADRs
├── migrations/            # Alembic migrations (pgvector, schema updates)
├── oauth_service/         # OAuth proxy microservice
├── scripts/               # Deployment & maintenance scripts
├── static/                # CDN-ready assets
├── tests/                 # Pytest suites (unit + integration)
├── run_talentwell_with_real_twav.py  # TalentWell Curator runner
├── Advisor_Vault_Candidate_Alerts.html  # Example digest output
└── README.md              # You are here
```


## Support

- **Incident response & rollback**: use the Emergency Rollback workflow or `scripts/restart_app.sh`.
- **Cache issues**: run `scripts/manifest_warmup.py` or hit `/cache/invalidate` followed by `/cache/warmup`.
- **Credential rotation**: update the OAuth proxy secrets and refresh tokens in Azure Key Vault and `.env` templates.
- **Questions / improvements**: open an issue or ping the platform team.

---

## License

**Proprietary and Confidential**

Copyright © 2025 The Well Recruiting Solutions. All rights reserved.

This software and associated documentation files (the "Software") are the proprietary property of The Well Recruiting Solutions. Unauthorized copying, distribution, modification, or use of this Software, via any medium, is strictly prohibited without the express written permission of The Well Recruiting Solutions.

