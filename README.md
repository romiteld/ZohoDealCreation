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

- FastAPI orchestrates LangGraph pipelines within Azure Container Apps, while the Outlook add-in provides the human-in-the-loop control surface.
- **VoIT and C³ algorithms** operate as cross-cutting optimization layers across ALL processing paths - from email intake to candidate vault publishing.
- Redis and PostgreSQL back persistent enrichment results; Azure Blob storage captures attachments and static assets.
- Azure OpenAI, Firecrawl, Apollo, and Azure Maps supply enrichment signals, with OAuth proxying and Azure Key Vault safeguarding secrets.
- GitHub Actions delivers container builds and warm cache scripts to keep endpoints responsive.
- The **Candidate Vault Agent** is a specific feature that aggregates CRM data and produces formatted digest cards, leveraging the VoIT/C³ optimization layer.

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

    subgraph NovelAlgorithms["🚨 Revolutionary Optimization Layer (Novel Algorithms)"]
        VoIT["VoIT Algorithm\n(Value of Insight Time)\nAdaptive reasoning allocation"]
        C3["C³ Algorithm\n(Conditional Causal Cache)\nProbabilistic reuse engine"]
    end
    class NovelAlgorithms,VoIT,C3 intelligent;

    subgraph CoreServices["Core Application Services"]
        FastAPI["FastAPI Core\n50+ endpoints"]
        OAuth["OAuth Proxy\n(Zoho token broker)"]
        VaultAgent["Candidate Vault Agent\n(CRM aggregation + formatting)"]
        LangGraph["LangGraph Pipeline\n(Extract → Research → Validate)"]
        StreamAPI["Streaming API\n(WebSocket + SSE)"]
        GraphClient["Microsoft Graph Client\n(Email integration)"]
    end
    class FastAPI,OAuth,VaultAgent,LangGraph,StreamAPI,GraphClient platform;

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

    %% Novel algorithms as cross-cutting layer
    FastAPI -.->|"Uses VoIT for\nall AI calls"| VoIT
    LangGraph -.->|"Optimized by"| VoIT
    VaultAgent -.->|"Optimized by"| VoIT
    VoIT -->|"Selects tier"| AzureOpenAI

    FastAPI -.->|"Uses C³ for\nall caching"| C3
    LangGraph -.->|"Optimized by"| C3
    VaultAgent -.->|"Optimized by"| C3
    C3 -->|"Manages"| RedisCache

    %% Data layer connections
    FastAPI -->|"Cache I/O"| RedisCache
    FastAPI -->|"Persist"| PostgreSQL
    FastAPI -->|"Enqueue"| ServiceBus
    FastAPI -->|"Store files"| BlobStorage
    FastAPI -->|"Semantic search"| AISearch

    %% AI enrichment
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

