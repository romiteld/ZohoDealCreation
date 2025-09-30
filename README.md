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

**Well Intake** is an enterprise-grade AI-powered recruiting automation platform that transforms Outlook emails into enriched Zoho CRM records in under 3 seconds. Built on Azure Container Apps with intelligent cost optimization through the Candidate Vault Agent (VoIT + C³), the system combines:

### Executive Summary
- **50+ REST API endpoints** serving Outlook add-ins, webhooks, and admin consoles
- **LangGraph AI pipeline** (Extract → Research → Validate) with GPT-5 tiered model selection
- **90% cost reduction** through C³ probabilistic caching and VoIT adaptive reasoning
- **Sub-3s processing** with Redis caching, async IO, and streaming WebSocket/SSE
- **Multi-source ingestion**: Emails, Zoom transcripts, resumes, web scraping
- **Multi-channel publishing**: Email campaigns, CRM sync, portal cards, JD alignment
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

| Step | Command | Notes |
|------|---------|-------|
| 1 | `python -m venv .venv && source .venv/bin/activate` | Use Python 3.11 |
| 2 | `pip install -r requirements-dev.txt` | Installs FastAPI, LangGraph, tooling |
| 3 | `npm install --prefix addin` | Installs Outlook add-in dependencies |
| 4 | `cp app/.env.local.example app/.env.local` | Fill in secrets & API keys |
| 5 | `uvicorn app.main:app --reload` | Starts API locally |
| 6 | `npm run dev --prefix addin` | Runs add-in dev server |

Make sure Redis and PostgreSQL are available (see [Development Guide](#development-guide) for container helpers).


## Key Capabilities

### Intake & Enrichment
- Multi-stage LangGraph pipeline (extract -> research -> validate) powered by GPT-5 tiers.
- Firecrawl v2 “supercharged” enrichment with company HQ, revenue, funding, tech stack, and leadership insights.
- Apollo.io enrichment for contact-level details (phone, LinkedIn, titles) with smart throttling.

### Outlook Taskpane Experience
- One-click **Send to Zoho**, **Test**, and enrichment controls inside Outlook.
- Real-time field confidence indicators, attachment previews, and manual override hints.
- Express-send gating based on extraction confidence and deduplication checks.

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

### Candidate Vault Agent (VoIT)
- **Value of Insight Time (VoIT)** - Adaptive reasoning depth allocation across processing spans.
- **C³ Cache (Conditional Causal Cache)** - Probabilistic reuse-or-rebuild decisions with dependency tracking.
- **Span-level Optimization** - Allocates compute budget (LLM tiers, tools) based on uncertainty metrics.
- **Multi-source Ingestion** - Normalizes emails, Zoom transcripts/notes, candidate resumes, and web scraping into canonical records.
- **Multi-channel Publishing** - Canonical records for email campaigns, CRM sync, portal cards, and JD alignment.
- **Cost Efficiency** - Reduces redundant API calls through semantic caching and selective rebuilds.
- **TalentWell Curator Integration** - Powers advisor-specific candidate alerts ([run_talentwell_with_real_twav.py](run_talentwell_with_real_twav.py)) with evidence extraction, financial pattern recognition (AUM, production, licenses), and digest card generation ([Advisor_Vault_Candidate_Alerts.html](Advisor_Vault_Candidate_Alerts.html)).


## Architecture

- FastAPI orchestrates LangGraph pipelines within Azure Container Apps, while the Outlook add-in provides the human-in-the-loop control surface.
- The **Candidate Vault Agent** (VoIT) manages adaptive reasoning depth allocation and C³ probabilistic caching for cost-optimized processing.
- Redis and PostgreSQL back persistent enrichment results; Azure Blob storage captures attachments and static assets.
- Azure OpenAI, Firecrawl, Apollo, and Azure Maps supply enrichment signals, with OAuth proxying and Azure Key Vault safeguarding secrets.
- GitHub Actions delivers container builds and warm cache scripts to keep endpoints responsive.

> **Diagram legend** - blue: operators, dark gray: platform services, amber: data stores, violet: third-party integrations, green: observability & ops, coral: intelligent optimization.

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

    subgraph Users["User Layer"]
        Recruiter["Recruiters\n(Outlook Desktop/Web)"]
        Advisor["Financial Advisors\n(Email Recipients)"]
        Admin["Admin Users\n(Management Console)"]
    end
    class Recruiter,Advisor,Admin actor;

    subgraph ClientApps["Client Applications"]
        OutlookAddin["Outlook Add-in\n(Office.js, Manifest v1.1)"]
        WebHooks["Webhook Handlers\n(Inbound integrations)"]
    end
    class OutlookAddin,WebHooks platform;

    subgraph AzureInfra["Azure Infrastructure"]
        FrontDoor["Azure Front Door CDN\nwell-intake-api-dnajdub4azhjcgc3"]
        ContainerApp["Container Apps\nwell-intake-api\n(Multi-revision with traffic split)"]
        ACR["Azure Container Registry\nwellintakeacr0903"]
        KeyVault["Azure Key Vault\nwell-intake-kv"]
        AppInsights["Application Insights\n(Telemetry + Alerts)"]
    end
    class FrontDoor,ContainerApp,ACR,KeyVault,AppInsights infra;

    subgraph CoreServices["Core Application Services"]
        FastAPI["FastAPI Core\n50+ endpoints"]
        OAuth["OAuth Proxy\n(Zoho token broker)"]
        VaultAgent["Candidate Vault Agent\n(VoIT + C³)"]
        LangGraph["LangGraph Pipeline\n(Extract → Research → Validate)"]
        StreamAPI["Streaming API\n(WebSocket + SSE)"]
        GraphClient["Microsoft Graph Client\n(Email integration)"]
    end
    class FastAPI,OAuth,LangGraph,StreamAPI,GraphClient platform;
    class VaultAgent intelligent;

    subgraph DataLayer["Data & Persistence Layer"]
        RedisCache["Azure Cache for Redis\n(C³ + standard cache)"]
        PostgreSQL["Azure PostgreSQL Flexible\nwell-intake-db\n(pgvector + 400K context)"]
        BlobStorage["Azure Blob Storage\n(Attachments + manifests)"]
        ServiceBus["Azure Service Bus\n(Batch queues)"]
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
        ZohoCRM["Zoho CRM v8 API\n(Accounts/Contacts/Deals)"]
        EmailProviders["Email Providers\n(SendGrid/Azure Comm)"]
    end
    class ZohoCRM,EmailProviders external;

    subgraph CICD["CI/CD & DevOps"]
        GitHub["GitHub Actions\n(3 workflows)"]
        Scripts["Deployment Scripts\n(20+ automation scripts)"]
    end
    class GitHub,Scripts ops;

    %% User flows
    Recruiter -->|"Open add-in"| OutlookAddin
    Advisor -->|"Receive digests"| EmailProviders

    %% Client to infrastructure
    OutlookAddin -->|"HTTPS/WSS"| FrontDoor
    WebHooks -->|"HTTPS"| FrontDoor
    Admin -->|"Admin APIs"| FrontDoor

    %% Infrastructure routing
    FrontDoor -->|"Route + TLS"| ContainerApp
    ContainerApp -->|"Pull images"| ACR
    ContainerApp -->|"Fetch secrets"| KeyVault
    ContainerApp -->|"Telemetry"| AppInsights

    %% Core service interactions
    ContainerApp -->|"Host"| FastAPI
    FastAPI -->|"Delegate"| OAuth
    FastAPI -->|"Orchestrate"| LangGraph
    FastAPI -->|"Stream"| StreamAPI
    FastAPI -->|"Vault ops"| VaultAgent
    FastAPI -->|"Read emails"| GraphClient

    %% Data layer connections
    FastAPI -->|"Cache I/O"| RedisCache
    VaultAgent -->|"C³ cache"| RedisCache
    FastAPI -->|"Persist"| PostgreSQL
    FastAPI -->|"Enqueue"| ServiceBus
    FastAPI -->|"Store files"| BlobStorage
    FastAPI -->|"Semantic search"| AISearch

    %% AI enrichment
    LangGraph -->|"LLM calls"| AzureOpenAI
    VaultAgent -->|"Model selection"| AzureOpenAI
    LangGraph -->|"Research"| Firecrawl
    FastAPI -->|"Enrich"| ApolloIO
    FastAPI -->|"Geocode"| AzureMaps
    VaultAgent -->|"Transcripts"| Zoom

    %% External systems
    FastAPI -->|"Create records"| ZohoCRM
    OAuth -->|"Token refresh"| ZohoCRM
    VaultAgent -->|"Send digests"| EmailProviders

    %% CI/CD
    GitHub -->|"Build + Push"| ACR
    GitHub -->|"Deploy"| ContainerApp
    Scripts -->|"Warmup"| FastAPI
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

### VoIT Processing Flow (Candidate Vault Agent)

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

    subgraph FastAPI["FastAPI Core"]
        Router["API Routers\n(/intake, /cache, /health, /vault-agent)"]
        LangGraph["LangGraph Orchestrator"]
        VaultRouter["Vault Agent Router\n(/ingest, /publish, /status)"]
        Services["Domain Services\n(normalizers, dedupe)"]
        Integrations["Integration Clients\n(Zoho, Firecrawl, Apollo, Maps)"]
        Background["Background Tasks\n(cache warmers, backfills)"]
        Telemetry["Telemetry\n(logging, metrics)"]
    end
    class FastAPI,Router,LangGraph,Services,Integrations,Background,Telemetry container;
    class VaultRouter intelligent;

    subgraph VaultAgent["Candidate Vault Agent"]
        VoITCtrl["VoIT Controller\n(Budget allocation, VOI calc)"]
        C3Cache["C³ Cache Manager\n(Reuse-or-rebuild logic)"]
        Normalizer["Payload Normalizer\n(Canonical format)"]
    end
    class VaultAgent,VoITCtrl,C3Cache,Normalizer intelligent;

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
    VaultRouter --> Normalizer
    Normalizer --> C3Cache
    C3Cache --> VoITCtrl
    VoITCtrl --> OpenAIAPI
    VoITCtrl --> FirecrawlAPI
    C3Cache --> RedisNode
    VaultRouter --> Postgres
    LangGraph --> Services
    Services --> Integrations
    Services --> Postgres
    Services --> RedisNode
    Integrations --> ZohoAPI
    Integrations --> OpenAIAPI
    Integrations --> FirecrawlAPI
    Integrations --> ApolloAPI
    Integrations --> MapsAPI
    Background --> RedisNode
    Background --> BlobStore
    TokenSvc --> KeyVault
    TokenSvc --> ZohoAPI
    Router --> Telemetry
    Telemetry --> Insights
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
    Start([Inbound Publish Request]) --> LoadCache{C³ Entry\nExists?}

    LoadCache -->|No| FullBuild[Full Build Path]
    LoadCache -->|Yes| CalcMargin[Calculate Margin\nδ = 1 - P(risk)]

    CalcMargin --> CompareEmbed[Compare Embedding\nSimilarity]
    CompareEmbed --> CheckFields{Field\nDrift?}

    CheckFields -->|High drift| SelectiveRebuild[Selective Rebuild]
    CheckFields -->|Low drift| CheckMargin{Margin >\nδ-bound?}

    CheckMargin -->|Yes| CacheHit[✓ Reuse Cached Artifact]
    CheckMargin -->|No| SelectiveRebuild

    SelectiveRebuild --> IdentifySpans[Identify Invalidated Spans]
    IdentifySpans --> VoITProcess[VoIT Span Processing]

    FullBuild --> CreateSpans[Create Span Context]
    CreateSpans --> VoITProcess

    VoITProcess --> SortSpans[Sort by Uncertainty\nretrieval_dispersion +\nrule_conflicts + c3_margin]

    SortSpans --> BudgetLoop{Budget > 0 &\nQuality < Target?}

    BudgetLoop -->|Yes| EvalActions[Evaluate Actions:\n1. Reuse cached\n2. Small LLM\n3. Tool call\n4. Deep LLM]

    EvalActions --> CalcVOI[Calculate VOI:\nqgain - λ*cost - μ*latency]
    CalcVOI --> SelectAction[Select Max VOI Action]
    SelectAction --> ApplyAction[Apply Action]
    ApplyAction --> UpdateQuality[Update Span Quality\nDeduct Budget]
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

### Candidate Vault Agent Architecture Summary

```mermaid
graph TB
    subgraph Sources["Data Sources"]
        Email[Email Intake\nOutlook Add-in]
        Resume[Resume Upload\nATS Integration]
        Transcript[Zoom Transcripts\nMeeting Recordings]
        ZoomNotes[Zoom Notes\nAI Summaries]
        Web[Web Scraping\nFirecrawl]
    end

    subgraph Ingest["Ingestion Layer"]
        Normalize[Payload Normalizer]
        Embed[Embedding Generator]
        Canon[Canonical Record Store]
    end

    subgraph Intelligence["Intelligent Processing Layer"]
        C3Gate{C³ Cache Gate}
        VoIT[VoIT Controller]
        Spans[Span Processor]
    end

    subgraph Actions["Processing Actions"]
        Reuse[Reuse Cached\ncost=0.01]
        Mini[GPT-5-mini\ncost=1.0]
        Tool[Firecrawl/Apollo\ncost=1.8]
        Deep[GPT-5\ncost=3.5]
    end

    subgraph Outputs["Multi-Channel Publishing"]
        EmailCamp[Email Campaign\nDigest Cards]
        ZohoCRM[Zoho CRM\nCandidate Records]
        Portal[Portal Cards\nAdvisor Dashboard]
        JDAlign[JD Alignment\nMatch Scores]
    end

    subgraph Storage["Persistence"]
        Redis[(Redis\nC³ Entries\n7d TTL)]
        PG[(PostgreSQL\nCanonical Records\nEmbeddings)]
    end

    Email --> Normalize
    Resume --> Normalize
    Transcript --> Normalize
    ZoomNotes --> Normalize
    Web --> Normalize

    Normalize --> Embed
    Embed --> Canon
    Canon --> Redis
    Canon --> C3Gate

    C3Gate -->|Cache Hit\nmargin > δ| Outputs
    C3Gate -->|Cache Miss\nOR Selective Rebuild| VoIT

    VoIT --> Spans
    Spans -->|Sort by\nUncertainty| Actions

    Reuse -->|VOI Max| VoIT
    Mini -->|VOI Max| VoIT
    Tool -->|VOI Max| VoIT
    Deep -->|VOI Max| VoIT

    VoIT -->|Budget Exhausted\nOR Quality Met| Outputs
    VoIT --> Redis

    Outputs --> EmailCamp
    Outputs --> ZohoCRM
    Outputs --> Portal
    Outputs --> JDAlign

    Canon --> PG

    classDef source fill:#E3F2FD,stroke:#1E40AF,stroke-width:2px
    classDef ingest fill:#F3E8FF,stroke:#7C3AED,stroke-width:2px
    classDef intelligent fill:#FED7D7,stroke:#E53E3E,stroke-width:3px
    classDef action fill:#FEF3C7,stroke:#D97706,stroke-width:2px
    classDef output fill:#DCFCE7,stroke:#15803D,stroke-width:2px
    classDef storage fill:#F8FAFC,stroke:#0F172A,stroke-width:2px

    class Email,Resume,Transcript,ZoomNotes,Web source
    class Normalize,Embed,Canon ingest
    class C3Gate,VoIT,Spans intelligent
    class Reuse,Mini,Tool,Deep action
    class EmailCamp,ZohoCRM,Portal,JDAlign output
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

- **Python unit/integration tests**: `pytest`
- **Selective suites**: `pytest tests/test_addin_endpoints.py`
- **Smoke test script**: `./run_tests.sh`
- **Front-end** (manual) – load the Outlook add-in with Office 365 developer tenant and exercise Test/Send flows.

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

_CLAUDE.md contains assistant configuration details and should remain in the repository._

