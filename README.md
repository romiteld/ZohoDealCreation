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
2. [Quick Start](#quick-start)
3. [Key Capabilities](#key-capabilities)
4. [Architecture](#architecture)
5. [Development Guide](#development-guide)
6. [Testing](#testing)
7. [CI/CD & Operations](#cicd--operations)
8. [Directory Layout](#directory-layout)
9. [Support](#support)

---

## Overview

Well Intake automates the journey from recruiting email to CRM record. The system combines FastAPI services, Outlook add-ins, Azure Container Apps, Redis caching, and LangGraph-based AI pipelines to extract, enrich, validate, and submit deal data into Zoho CRM. The platform focuses on:

- **Accuracy** – multi-stage extraction with enrichment (Firecrawl v2, Apollo.io) and duplicate detection.
- **Speed** – sub-3s processing through caching, async IO, and streamed workflows.
- **Operator Control** – human-in-the-loop Outlook taskpane with edit-before-send flows and preview/test modes.
- **Observability & Safety** – structured logging, health endpoints, cache warmers, and emergency rollback tooling.


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


## Architecture

- FastAPI orchestrates LangGraph pipelines within Azure Container Apps, while the Outlook add-in provides the human-in-the-loop control surface.
- Redis and PostgreSQL back persistent enrichment results; Azure Blob storage captures attachments and static assets.
- Azure OpenAI, Firecrawl, Apollo, and Azure Maps supply enrichment signals, with OAuth proxying and Azure Key Vault safeguarding secrets.
- GitHub Actions delivers container builds and warm cache scripts to keep endpoints responsive.

> **Diagram legend** - blue: operators, dark gray: platform services, amber: data stores, violet: third-party integrations, green: observability & ops.

### System Context (C4 Level 1)

```mermaid
flowchart LR
    classDef actor fill:#E3F2FD,stroke:#1E40AF,color:#0B1F4B,stroke-width:1px;
    classDef platform fill:#F8FAFC,stroke:#0F172A,color:#0F172A,stroke-width:1px;
    classDef datastore fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:1px;
    classDef external fill:#FCE7F3,stroke:#C026D3,color:#701A75,stroke-width:1px;
    classDef ops fill:#DCFCE7,stroke:#15803D,color:#064E3B,stroke-width:1px;

    subgraph Operator["Operator Workspace"]
        Outlook["Outlook Taskpane Add-in\n(JavaScript + Office.js)"]
    end
    class Outlook actor;

    subgraph Platform["Well Intake Platform\n(Azure Container Apps)"]
        OAuth["OAuth Proxy\n(Flask ingress, token broker)"]
        API["FastAPI Core\n(LangGraph orchestration)"]
        Cache["Redis Cache"]
        DB["PostgreSQL + pgvector"]
        Blob["Azure Blob Storage\n(Attachments, manifests)"]
        Jobs["Async Jobs & Scripts\n(Cache warmers, enrichers)"]
    end
    class OAuth,API,Jobs platform;
    class Cache,DB,Blob datastore;

    subgraph AIProviders["AI & Enrichment Providers"]
        OpenAI["Azure OpenAI\n(GPT-5 models)"]
        Firecrawl["Firecrawl API"]
        Apollo["Apollo.io API"]
        Maps["Azure Maps"]
    end
    class OpenAI,Firecrawl,Apollo,Maps external;

    CRM["Zoho CRM"]
    class CRM external;

    Insights["Application Insights / Logging Sink"]
    class Insights ops;

    Vault["Azure Key Vault"]
    class Vault external;

    Outlook -->|"OAuth 2.0 + REST"| OAuth
    OAuth -->|"Session hand-off\n(Forward auth headers)"| API
    API -->|"Cache lookups"| Cache
    API -->|"Persist deals + embeddings"| DB
    API -->|"Upload attachments"| Blob
    API -->|"Create/update records"| CRM
    API -->|"LLM prompts"| OpenAI
    API -->|"Company research"| Firecrawl
    API -->|"Contact enrichment"| Apollo
    API -->|"Geocode addresses"| Maps
    API -->|"Structured telemetry"| Insights
    OAuth -->|"Secret fetch"| Vault
    API -->|"Secret fetch"| Vault
    Jobs -->|"Backfill / cache warm"| API
    Outlook -->|"Static assets"| Blob
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

### Container Responsibilities (C4 Level 2)

```mermaid
flowchart TB
    classDef container fill:#FFFFFF,stroke:#0F172A,color:#111827,stroke-width:1px;
    classDef ext fill:#F3E8FF,stroke:#7C3AED,color:#4C1D95,stroke-width:1px;
    classDef data fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:1px;

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
        Router["API Routers\n(/intake, /cache, /health)"]
        LangGraph["LangGraph Orchestrator"]
        Services["Domain Services\n(normalizers, dedupe)"]
        Integrations["Integration Clients\n(Zoho, Firecrawl, Apollo, Maps)"]
        Background["Background Tasks\n(cache warmers, backfills)"]
        Telemetry["Telemetry\n(logging, metrics)"]
    end
    class FastAPI,Router,LangGraph,Services,Integrations,Background,Telemetry container;

    subgraph DataPlane["Data Plane"]
        RedisNode["Redis"]
        Postgres["PostgreSQL + pgvector"]
        BlobStore["Azure Blob\n(attachments, manifests)"]
    end
    class DataPlane,RedisNode,Postgres,BlobStore data;

    subgraph External["External Systems"]
        ZohoAPI["Zoho CRM"]
        OpenAIAPI["Azure OpenAI"]
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
    classDef comp fill:#EFF6FF,stroke:#1D4ED8,color:#0B1F4B,stroke-width:1px;
    classDef boundary stroke:#0F172A,stroke-width:1.5px,fill:#FFFFFF,color:#111827;

    subgraph Boundary["FastAPI Service"]
        subgraph RouterLayer["Router Layer"]
            Public["Public Routers\n(intake, attachments)"]
            Internal["Internal Routers\n(cache, warmup, health)"]
        end
        subgraph WorkflowLayer["Workflow & Domain"]
            GraphMgr["LangGraph Manager\n(orchestrates extract -> enrich -> validate)"]
            Rules["Business Rules\n(deal naming, dedupe, gating)"]
            Normalizers["Normalizers\n(email -> CRM schema)"]
            Confidence["Confidence Engine\n(scoring + human overrides)"]
        end
        subgraph IntegrationLayer["Integration Adapters"]
            ZohoClient["Zoho Client"]
            FirecrawlClient["Firecrawl Client"]
            ApolloClient["Apollo Client"]
            MapsClient["Azure Maps Client"]
            OpenAIClient["Azure OpenAI Client"]
        end
        subgraph PersistenceLayer["Persistence & Cache"]
            Repo["Repository Layer\n(SQLModel + pgvector)"]
            CacheMgr["Cache Manager\n(Redis IO, TTL policy)"]
            BlobSvc["Attachment Service\n(Blob uploads + metadata)"]
        end
        subgraph ObservabilityLayer["Observability"]
            Logging["Structured Logging"]
            Metrics["Metrics Exporters"]
            Alerts["Alert Hooks\n(health + SLA)"]
        end
    end
    class Boundary,RouterLayer,WorkflowLayer,IntegrationLayer,PersistenceLayer,ObservabilityLayer boundary;
    class Public,Internal,GraphMgr,Rules,Normalizers,Confidence,ZohoClient,FirecrawlClient,ApolloClient,MapsClient,OpenAIClient,Repo,CacheMgr,BlobSvc,Logging,Metrics,Alerts comp;

    Public --> GraphMgr
    Internal --> CacheMgr
    GraphMgr --> Rules
    GraphMgr --> Normalizers
    GraphMgr --> Confidence
    Rules --> Repo
    Normalizers --> Repo
    Confidence --> CacheMgr
    CacheMgr --> Repo
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
```

### Data & Integration Catalogue

| Category | Surface | Purpose | Notes |
|----------|---------|---------|-------|
| Platform Data | PostgreSQL (`deals`, `contacts`, `attachments`, `embeddings`) | Source of truth for CRM pushes, replay safety, vector search | `pgvector` drives similarity matching & deduping |
| Platform Data | Redis (`intake:*`, `manifest:*`) | Sub-second previews, duplicate suppression, manifest caching | TTL tuned for 2–12h depending on stage |
| Platform Data | Azure Blob (`attachments/`, `manifests/`) | Attachment storage, Outlook static file hosting | Versioned with cache-busting to avoid stale manifests |
| Integrations | Zoho CRM REST APIs | Account/Contact/Deal creation, idempotent updates | OAuth tokens managed by proxy, backoff on 429s |
| Integrations | Azure OpenAI (`gpt-5`, `gpt-4o-mini`) | Field extraction, validation, summarization | Prompt templates live in `app/prompts/` |
| Integrations | Firecrawl API | Company research, website parsing | Batched to minimize request volume |
| Integrations | Apollo.io API | Contact enrichment, phone/email validation | Smart throttling with daily quota guardrails |
| Integrations | Azure Maps | Geocoding, timezone inference | Optional feature flag via `ENABLE_AZURE_MAPS` |
| Observability | Application Insights | Centralized telemetry, trace correlation | Configured through deployment pipeline |

### Deployment & Operations Snapshot

- GitHub Actions builds the Outlook add-in, Docker images, and runs manifest cache-bust workflows prior to promoting new revisions to Azure Container Apps.
- Cache warmers populate Redis and blob metadata immediately post-deploy to keep first-run latency low.
- Emergency rollback scripts shift traffic to the previous container revision and invalidate Redis keys to maintain consistency.


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

For the Outlook add-in, set `API_BASE_URL` and `API_KEY` in `addin/config.js` or `.env` depending on deployment target.

> Detailed geocoding setup lives in [`docs/geo/azure_maps.md`](docs/geo/azure_maps.md).

### Useful Commands

```bash
# Run FastAPI with autoreload
uvicorn app.main:app --reload --port 8000

# Run background batch pipeline
python run_all_tests.py --mode batch

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
├── docs/                  # Reference material & ADRs
├── migrations/            # Alembic migrations (pgvector, schema updates)
├── oauth_service/         # OAuth proxy microservice
├── scripts/               # Deployment & maintenance scripts
├── static/                # CDN-ready assets
├── tests/                 # Pytest suites (unit + integration)
└── README.md              # You are here
```


## Support

- **Incident response & rollback**: use the Emergency Rollback workflow or `scripts/restart_app.sh`.
- **Cache issues**: run `scripts/manifest_warmup.py` or hit `/cache/invalidate` followed by `/cache/warmup`.
- **Credential rotation**: update the OAuth proxy secrets and refresh tokens in Azure Key Vault and `.env` templates.
- **Questions / improvements**: open an issue or ping the platform team.

---

_CLAUDE.md contains assistant configuration details and should remain in the repository._

