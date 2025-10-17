# The Well Recruiting Solutions - Complete Ecosystem Architecture

**Version:** 1.0
**Last Updated:** October 17, 2025
**Architecture Type:** Multi-Codebase Microservices with Shared Infrastructure

---

## 🏗️ System Overview

The Well Recruiting Solutions operates as a **3-codebase ecosystem** with shared Azure infrastructure, enabling intelligent recruiting workflows across email processing, content creation, and voice communications.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    THE WELL RECRUITING SOLUTIONS                             │
│                         Complete Ecosystem                                   │
└──────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
    │   WELL INTAKE   │      │ CONTENT STUDIO  │      │ VOICE PLATFORM  │
    │                 │      │                 │      │                 │
    │ Email → CRM     │◄────►│ AI Content Gen  │◄────►│ LiveKit Calls   │
    │ LangGraph AI    │      │ Social Media    │      │ Real-time Coach │
    │ Teams Bot       │      │ Image Creation  │      │ Screen Share AI │
    │                 │      │                 │      │                 │
    │ Status: LIVE ✅ │      │ Status: LIVE ✅ │      │ Status: DESIGN  │
    └────────┬────────┘      └────────┬────────┘      └────────┬────────┘
             │                        │                         │
             └────────────────────────┼─────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │    SHARED AZURE INFRASTRUCTURE      │
                    │                                     │
                    │  ┌──────────────────────────────┐  │
                    │  │ PostgreSQL (Central US)      │  │
                    │  │ • Well Intake tables         │  │
                    │  │ • Content Studio tables      │  │
                    │  │ • Shared user auth           │  │
                    │  └──────────────────────────────┘  │
                    │                                     │
                    │  ┌──────────────────────────────┐  │
                    │  │ Azure OpenAI (2 regions)     │  │
                    │  │ • GPT-5 (temp=1 always)      │  │
                    │  │ • East US + East US 2        │  │
                    │  └──────────────────────────────┘  │
                    │                                     │
                    │  ┌──────────────────────────────┐  │
                    │  │ Redis Cache (East US)        │  │
                    │  │ • Prompt caching (90% save)  │  │
                    │  │ • Session storage            │  │
                    │  └──────────────────────────────┘  │
                    │                                     │
                    │  ┌──────────────────────────────┐  │
                    │  │ Key Vault (2 instances)      │  │
                    │  │ • well-intake-kv             │  │
                    │  │ • well-youtube-kv            │  │
                    │  └──────────────────────────────┘  │
                    │                                     │
                    │  ┌──────────────────────────────┐  │
                    │  │ Blob Storage (4 accounts)    │  │
                    │  │ • Media, attachments, etc.   │  │
                    │  └──────────────────────────────┘  │
                    └─────────────────────────────────────┘
```

---

## 📂 Codebase Inventory

### 1. Well Intake API
**Location:** `/home/romiteld/Development/Desktop_Apps/outlook`
**Git Status:** Main branch, 43 files pending commit, active development

**Purpose:** Intelligent email processing and CRM automation

**Core Technologies:**
- FastAPI (Python) - REST API framework
- LangGraph v0.2.74 - AI workflow orchestration
- GPT-5 models (nano, mini, full) - Always temperature=1
- PostgreSQL + pgvector - 400K context storage
- Azure Redis - Prompt caching (24hr TTL)
- Zoho CRM API v8 - Direct integration

**Key Components:**
```
outlook/
├── app/
│   ├── main.py                    # FastAPI endpoints
│   ├── langgraph_manager.py       # 3-node StateGraph workflow
│   ├── integrations.py            # Zoho, Apollo, Firecrawl
│   ├── api/teams/                 # Teams Bot (natural language queries)
│   ├── jobs/talentwell_curator.py # Weekly digest generator
│   └── workers/                   # Service Bus background workers
├── teams_bot/                     # MS Teams integration (separate container)
├── resume_generator/              # Resume generation service
├── well_shared/                   # Shared Python library
├── addin/                         # Outlook Add-in (Office.js)
└── migrations/                    # Alembic database migrations
```

**Deployment:**
- **Main API:** `well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io`
- **Teams Bot:** `teams-bot` Container App
- **Resume Gen:** `resume-generator` Container App
- **Workers:** teams-digest-worker, teams-nlp-worker, vault-marketability-worker
- **OAuth Proxy:** `well-zoho-oauth-v2.azurewebsites.net` (Flask)

**Database Schema:**
- Core: emails, extracted_data, deals, candidates, meetings
- Teams: teams_user_preferences, conversation_state, weekly_digest_deliveries
- Jobs: talentwell_digest_runs, bullet_cache

### 2. Content Studio
**Location:** `/home/romiteld/Development/Web/wealth`
**Git Status:** Production branch, deployed to Vercel + Azure

**Purpose:** AI-powered content creation and social media management

**Core Technologies:**
- React 19 + TypeScript - Modern frontend
- Node.js 20 + Express.js - Backend API
- Azure Container Apps - Hosting
- FAL AI (Imagen4, Flux Pro) - Image generation
- OpenAI GPT-5-mini - Content generation
- Vercel - Frontend CDN

**Key Components:**
```
wealth/
├── apps/
│   ├── web/                       # React frontend (Vercel)
│   │   ├── src/components/studio/ # Feature components
│   │   ├── src/lib/api/           # API client layer
│   │   └── src/config/            # MSAL auth config
│   │
│   └── api/                       # Express backend (Azure Container Apps)
│       ├── server.js              # Main entry point
│       ├── src/routes/            # 33+ API endpoints
│       ├── src/services/          # Business logic
│       └── Dockerfile             # Container config
│
├── packages/types/                # Shared TypeScript types
├── infra/                         # Infrastructure scripts
└── docs/                          # Architecture documentation
```

**Deployment:**
- **Frontend:** `studio.thewell.solutions` (Vercel global CDN)
- **Backend:** `well-content-studio-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io`
- **Functions:** well-linkedin-publisher, well-youtube-publisher, well-scheduled-publisher

**Database Schema:**
- Content: campaigns, wealth_* tables, brand_protection_log
- Social: published_content, social_media_accounts
- AI: content_vault, ai_chat_history

**API Endpoints (33+):**
```
Authentication:     /api/azure-auth/*
AI & Content:       /api/ai, /api/ai-image, /api/ai-marketing
Content Mgmt:       /api/campaigns, /api/vault-agent, /api/talentwell
Research:           /api/research, /api/research-enhanced
Social Media:       /api/social-integration (LinkedIn, YouTube, Twitter)
Media:              /api/upload, /api/brand, /api/images
Repurposing:        /api/repurpose, /api/generate-documents
Integration:        /intake (Outlook Add-in)
```

### 3. Voice Platform (Recruiting Voice Platform)
**Location:** `/home/romiteld/Development/Desktop_Apps/recruiting-voice-platform`
**Git Status:** Design phase, not yet deployed

**Purpose:** JustCall replacement with real-time AI coaching for recruiting calls

**Core Technologies (Planned):**
- LiveKit Cloud - Real-time voice/video/screen share
- Next.js 14 + TypeScript - Frontend
- FastAPI (Python) - Backend agents
- Azure Speech Services - Transcription & translation
- GPT-5 - Real-time AI coaching
- Azure Computer Vision - Screen share analysis

**Architecture (Patent-Level):**
```
recruiting-voice-platform/
├── docs/
│   ├── PRD.txt                         # Complete product requirements
│   ├── architecture_diagram.png        # System architecture
│   ├── voice_platform_flow.png         # Call flow diagram
│   └── ai_processing_pipeline.png      # AI analysis pipeline
├── frontend/                           # Next.js 14 app (planned)
├── backend/                            # FastAPI agents (planned)
├── mobile/                             # React Native (future)
└── database/                           # Schema design (planned)
```

**Innovations:**
1. **Real-Time AI Advisor** - Coaches recruiters DURING calls with live suggestions
2. **Multi-Modal Analysis** - Voice + video + screen share → comprehensive insights
3. **Zero-Touch CRM** - Automatic deal creation, notes, follow-ups from conversation
4. **Context Engine** - Pulls LinkedIn, past calls, company research into view
5. **Compliance AI** - Automatic PII detection, question compliance checking
6. **Universal Platform** - One system for phone, Teams, Zoom, web calls

**Deployment Plan:**
- Frontend: Vercel (Next.js)
- Backend: Azure Container Apps (FastAPI agents)
- Database: Extend shared PostgreSQL
- LiveKit: Cloud instance ($50-500/month based on usage)
- Integration: Teams Bot for call scheduling

**Database Schema (Designed):**
```sql
-- Voice platform tables (to be added to shared DB)
CREATE TABLE recruiting_calls (
    id UUID PRIMARY KEY,
    room_name VARCHAR(255),
    recruiter_id UUID REFERENCES users(id),
    candidate_phone VARCHAR(50),
    audio_url TEXT,
    video_url TEXT,
    transcript JSONB,
    ai_summary TEXT,
    engagement_score INTEGER,
    extracted_crm_data JSONB,
    zoho_deal_id VARCHAR(255)
);

CREATE TABLE call_insights (
    id UUID PRIMARY KEY,
    call_id UUID REFERENCES recruiting_calls(id),
    insight_type VARCHAR(50), -- 'suggestion', 'warning', 'opportunity'
    content TEXT,
    confidence FLOAT,
    shown_to_recruiter BOOLEAN
);

CREATE TABLE screen_share_analysis (
    id UUID PRIMARY KEY,
    call_id UUID REFERENCES recruiting_calls(id),
    content_type VARCHAR(100), -- 'resume', 'portfolio', 'linkedin'
    extracted_text TEXT,
    detected_elements JSONB,
    insights TEXT[]
);
```

---

## 🔗 Integration Architecture

### Shared Database Strategy

**PostgreSQL:** `well-intake-db-0903.postgres.database.azure.com:5432`
- **Location:** Central US (for geographic distribution)
- **Engine:** PostgreSQL 13 Flexible Server
- **Storage:** 32 GB with auto-growth
- **Connection Pool:** max 10, min 2 (optimized for container apps)

**Schema Ownership:**
```sql
-- Well Intake schemas
CREATE SCHEMA intake;     -- emails, langgraph state, crm data
CREATE SCHEMA teams;      -- bot conversations, user preferences

-- Content Studio schemas
CREATE SCHEMA content;    -- campaigns, social media, vault

-- Voice Platform schemas (future)
CREATE SCHEMA voice;      -- calls, insights, recordings

-- Shared schemas
CREATE SCHEMA public;     -- users, roles, shared auth
CREATE SCHEMA analytics;  -- cross-system reporting
```

**Migration Strategy:**
- Well Intake: Alembic migrations
- Content Studio: Prisma/Knex migrations
- Voice Platform: Alembic migrations (when deployed)
- Coordination: Manual merge of migration files before deployment

### Cross-System Data Flow

**Scenario 1: Email → Content Creation**
```
1. Well Intake processes recruitment email
2. Extracts candidate info → Zoho CRM
3. Teams Bot notifies Content Studio via API
4. Content Studio generates LinkedIn post about placement
5. Publishes to social media
```

**Scenario 2: Call → CRM → Digest**
```
1. Voice Platform captures recruiting call (future)
2. AI extracts deal data → PostgreSQL
3. Zoho sync updates CRM
4. TalentWell curator includes in weekly digest
5. Email sent to executives
```

**Scenario 3: Note-Taking Integration (Planned)**
```
1. Steve takes notes in note-taking app
2. AI analyzes note content → tags candidates/deals
3. Links to Well Intake records automatically
4. Searchable via Teams Bot natural language
5. Surfaces in Content Studio for marketing ideas
```

### API Integration Points

**Well Intake → Content Studio:**
- Endpoint: `POST /api/vault-agent/candidate-published`
- Auth: Shared JWT from Key Vault
- Payload: Candidate data for content generation

**Content Studio → Well Intake:**
- Endpoint: `POST /api/teams/admin/trigger-digest`
- Auth: X-API-Key header
- Payload: Digest generation request

**Voice Platform → Well Intake (Future):**
- Endpoint: `POST /api/crm/auto-populate`
- Auth: Managed Identity
- Payload: Extracted CRM data from call transcript

### Shared Services

**1. Azure OpenAI (2 Deployments)**
```
Primary: well-intake-aoai (East US)
- Model: gpt-5 (all variants)
- Usage: Well Intake LangGraph, Teams Bot NLP
- Temperature: Always 1 (per project requirement)

Secondary: well-intake-aoai-eus2 (East US 2)
- Model: gpt-5-mini
- Usage: Content Studio AI chat, content generation
- Temperature: 0.7 for creative, 0.1 for structured output
```

**2. Redis Cache (Shared)**
```
Host: wellintakecache0903.redis.cache.windows.net:6380
Schema Namespaces:
- intake:*     → Well Intake prompt cache
- content:*    → Content Studio session cache
- vault:*      → TalentWell bullet cache
- voice:*      → Voice Platform future use
```

**3. Key Vault (2 Instances)**
```
well-intake-kv:
- Intake API keys (OpenAI, Zoho, Apollo, Firecrawl)
- Database credentials
- Service Bus connection strings

well-youtube-kv:
- Social media OAuth tokens
- FAL AI key
- Publishing API credentials
```

**4. Application Insights**
```
wellintakeinsights0903:
- Telemetry from all Container Apps
- Custom events for business metrics
- Distributed tracing across services
```

---

## 🚀 Deployment Architecture

### Azure Resources (45+ Total)

**Container Apps (7):**
1. `well-intake-api` - Main email processing
2. `teams-bot` - MS Teams integration
3. `resume-generator` - Resume PDF generation
4. `well-content-studio-api` - Content creation backend
5. `teams-digest-worker` - Weekly digest generation (KEDA scaled)
6. `teams-nlp-worker` - Natural language query processing (KEDA scaled)
7. `vault-marketability-worker` - Candidate scoring (Service Bus triggered)

**App Services/Functions (5):**
1. `well-zoho-oauth-v2` - OAuth proxy (Flask)
2. `well-linkedin-publisher` - LinkedIn automation (Node.js)
3. `well-youtube-publisher` - YouTube uploads (Node.js)
4. `well-scheduled-publisher` - Content scheduling (Node.js)
5. `weekly-digest-scheduler` - Container App Job (KEDA cron)

**Data Services:**
- PostgreSQL Flexible Server (Central US)
- Redis Cache (East US)
- 4× Storage Accounts (wellintakestorage0903, wellattachments0903, wellcontent0903, wellintakefunc0903)
- Azure AI Search (wellintakesearch0903)
- 2× Azure OpenAI accounts

**Networking & CDN:**
- Azure Front Door (well-intake-frontdoor)
- Azure Maps (well-geocode-acc)
- Azure Communication Services (email domain: emailthewell.com)

**Monitoring & Security:**
- 3× Application Insights
- 2× Key Vaults
- 2× Service Bus namespaces
- 2× Metric Alerts (DLQ monitoring)

### Container App Scaling Configuration

```yaml
# well-intake-api
scale:
  minReplicas: 1
  maxReplicas: 10
  rules:
    - name: http-scaling
      http:
        concurrentRequests: 50

# teams-digest-worker (KEDA)
scale:
  minReplicas: 0
  maxReplicas: 5
  rules:
    - name: azure-servicebus
      type: azure-servicebus
      metadata:
        queueName: digest-queue
        messageCount: '5'

# teams-nlp-worker (KEDA)
scale:
  minReplicas: 0
  maxReplicas: 3
  rules:
    - name: azure-servicebus
      type: azure-servicebus
      metadata:
        queueName: nlp-query-queue
        messageCount: '2'
```

### CI/CD Pipeline

**Well Intake:**
```bash
# GitHub Actions: .github/workflows/azure-deploy.yml
Trigger: Push to main
Steps:
  1. Run tests (pytest)
  2. Build Docker image
  3. Push to wellintakeacr0903.azurecr.io
  4. Update Container Apps with new revision
  5. Run health checks
  6. Notify via Teams webhook
```

**Content Studio:**
```bash
# Frontend (Vercel): Auto-deploy on push to main
# Backend (Azure): .github/workflows/deploy.yml
Trigger: Push to main
Steps:
  1. npm run test
  2. Docker build apps/api
  3. Push to wellintakeacr0903.azurecr.io
  4. Update well-content-studio-api
  5. Verify /api/health endpoint
```

---

## 🔮 Future Architecture (6-12 Months)

### Phase 1: Note-Taking Integration (Month 1-2)
```
Well Intake API Extension:
├── New routes: /api/notes/*
├── AI tagging with GPT-5
├── Auto-link to candidates/deals
├── Shared PostgreSQL schema
└── Teams Bot integration for search

Estimated Effort: 2-3 weeks
Cost Impact: $0 (uses existing infrastructure)
```

### Phase 2: Voice Platform Deployment (Month 3-4)
```
New Infrastructure:
├── LiveKit Cloud ($50-500/month)
├── SIP Trunk Provider ($100-300/month)
├── Additional Container App: well-voice-platform
├── Database: Extend shared PostgreSQL
└── Integration: Teams Bot + CRM automation

Estimated Effort: 6-8 weeks
Cost Impact: $150-800/month (usage-based)
```

### Phase 3: Unified Analytics Dashboard (Month 5-6)
```
Power BI / Tableau Integration:
├── Cross-system metrics
├── Email → Placement conversion rates
├── Content → Engagement analytics
├── Voice → Call effectiveness scores
└── Real-time KPI monitoring

Estimated Effort: 4 weeks
Cost Impact: $20-50/month (Power BI Pro licenses)
```

---

## 📊 System Metrics & Monitoring

### Current Performance (Well Intake + Content Studio)

**Well Intake API:**
- Avg Response Time: 450ms (email processing)
- LangGraph Execution: 2-8 seconds (3-node workflow)
- Daily Email Volume: ~50-200 emails
- Cache Hit Rate: 90% (Redis prompt caching)
- Uptime: 99.8% (last 30 days)

**Content Studio:**
- Frontend Load Time: 1.2s (Vercel CDN)
- Backend API Latency: 200ms avg
- AI Image Generation: 15-45 seconds (FAL AI)
- Content Creation: 5-10 seconds (GPT-5-mini streaming)
- Uptime: 99.9% (last 30 days)

**Shared Database:**
- Connection Pool: 6/10 avg utilization
- Query Performance: p95 < 100ms
- Storage Used: 8.2 GB / 32 GB
- Backup Retention: 7 days

### Health Check Endpoints

```bash
# Well Intake
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
# → {"status": "healthy", "database": "connected", "redis": "connected"}

# Content Studio
curl https://well-content-studio-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/health
# → {"status": "ok", "uptime": 172800, "database": "connected"}

# Teams Bot
curl https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
# → {"status": "healthy", "workers": "operational"}
```

---

## 🔐 Security & Compliance

**Shared Security Model:**
- Azure AD SSO (@emailthewell.com tenant)
- Key Vault for all secrets (no .env.local in production)
- Managed Identities for service-to-service auth
- TLS 1.2+ enforcement across all services
- Private endpoints for database access
- RBAC with least-privilege principles

**Compliance Frameworks:**
- SOC 2 Type II ready (audit logging, access controls)
- GDPR compliant (data encryption, retention policies, PII anonymization)
- HIPAA capable (encryption standards, BAA available)

**Audit Logging:**
- Application Insights telemetry (all apps)
- Azure Monitor logs (infrastructure)
- Key Vault access audit trail
- Service Bus dead-letter queue monitoring

---

## 📚 Development Workflow

### Local Development Setup

**Well Intake:**
```bash
cd /home/romiteld/Development/Desktop_Apps/outlook
source zoho/bin/activate
cp .env.example .env.local  # Edit with dev credentials
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Content Studio:**
```bash
cd /home/romiteld/Development/Web/wealth
npm run install:all
# Terminal 1: npm run web  (frontend → localhost:3000)
# Terminal 2: npm run api  (backend → localhost:3001)
```

**Voice Platform (Future):**
```bash
cd /home/romiteld/Development/Desktop_Apps/recruiting-voice-platform
npm install
npm run dev  # Next.js dev server
```

### Git Workflow

**Well Intake:**
- Main branch: `main` (auto-deploy to production)
- Feature branches: `feature/*`
- Current status: 43 uncommitted files (vault alert work)

**Content Studio:**
- Main branch: `main` (auto-deploy via Vercel + GitHub Actions)
- Staging: Preview URLs for PRs

**Cross-Codebase Changes:**
1. Database schema changes → Coordinate migrations
2. Shared API contracts → Version endpoints
3. Breaking changes → Deploy backend first, then consumers

---

## 🎯 Architectural Principles

1. **Shared Infrastructure, Isolated Logic**
   - Common services (DB, Redis, Key Vault)
   - Independent deployments per codebase
   - No tight coupling between apps

2. **AI-First Design**
   - GPT-5 models for all intelligence
   - Prompt caching for cost efficiency (90% savings)
   - Temperature=1 for Well Intake (per requirement)

3. **Async Where Possible**
   - Service Bus for background jobs
   - KEDA scaling for workers (min=0)
   - Streaming responses for AI chat

4. **Security by Default**
   - Key Vault for all secrets
   - Managed Identities over API keys
   - Private networking where feasible

5. **Observable & Debuggable**
   - Structured logging (Application Insights)
   - Distributed tracing across services
   - Health checks on all APIs

---

## 📖 Related Documentation

- `CLAUDE.md` - Well Intake development guide
- `/Development/Web/wealth/README.md` - Content Studio documentation
- `/Development/Desktop_Apps/recruiting-voice-platform/docs/PRD.txt` - Voice Platform PRD
- `SECURITY_AUDIT_REPORT.md` - Security assessment (this repo)
- `AZURE_COST_OPTIMIZATION.md` - Cost analysis (to be created)

---

**Architecture Version:** 1.0
**Last Validated:** October 17, 2025
**Next Review:** November 17, 2025
**Maintained By:** Daniel Romitelli <daniel.romitelli@emailthewell.com>
