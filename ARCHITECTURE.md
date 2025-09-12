# Well Intake API - System Architecture

## 🏗️ High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        OA[Outlook Add-in<br/>JavaScript/Office.js]
        WEB[Web Interface<br/>HTML/CSS/JS]
        API_CLIENT[API Clients<br/>REST/WebSocket]
    end

    subgraph "CDN & Edge"
        CDN[Azure Front Door CDN<br/>Global Distribution]
        WAF[Web Application Firewall<br/>DDoS Protection]
    end

    subgraph "API Gateway"
        APIG[FastAPI Application<br/>Container Apps]
        WS[WebSocket Server<br/>Real-time Streaming]
        BATCH[Batch API<br/>Bulk Processing]
    end

    subgraph "Processing Layer"
        LG[LangGraph Workflow<br/>3-Node Pipeline]
        GPT[GPT-5 Model Tiers<br/>nano/mini/full]
        CACHE[Redis Cache<br/>90% Cost Reduction]
        QUEUE[Service Bus<br/>Batch Queue]
    end

    subgraph "Intelligence Layer"
        C3[C³ Cache<br/>Conformal Bounds]
        VOIT[VoIT Orchestrator<br/>Budget-Aware]
        SEARCH[AI Search<br/>Semantic Learning]
        VECTOR[pgvector<br/>Embeddings]
    end

    subgraph "Data Layer"
        PG[PostgreSQL<br/>400K Context]
        BLOB[Blob Storage<br/>Attachments]
        KV[Key Vault<br/>Secrets]
    end

    subgraph "Integration Layer"
        ZOHO[Zoho CRM<br/>API v8]
        OAUTH[OAuth Service<br/>Token Management]
        EMAIL[Email Services<br/>ACS/SendGrid]
    end

    subgraph "Monitoring"
        AI_INSIGHTS[Application Insights<br/>Metrics & Logs]
        COST[Cost Optimizer<br/>Budget Tracking]
    end

    OA --> CDN
    WEB --> CDN
    API_CLIENT --> CDN
    CDN --> WAF
    WAF --> APIG
    APIG --> LG
    APIG --> WS
    APIG --> BATCH
    LG --> GPT
    LG --> CACHE
    BATCH --> QUEUE
    GPT --> C3
    C3 --> VOIT
    LG --> SEARCH
    SEARCH --> VECTOR
    LG --> PG
    LG --> BLOB
    APIG --> KV
    LG --> ZOHO
    ZOHO --> OAUTH
    APIG --> EMAIL
    APIG --> AI_INSIGHTS
    GPT --> COST

    style OA fill:#4CAF50
    style LG fill:#2196F3
    style GPT fill:#FF9800
    style CACHE fill:#9C27B0
    style ZOHO fill:#F44336
```

## 🔄 LangGraph Email Processing Workflow

```mermaid
graph LR
    subgraph "LangGraph StateGraph"
        START[Email Input] --> EXTRACT[Extract Node<br/>GPT-5-mini<br/>Structured Output]
        EXTRACT --> RESEARCH[Research Node<br/>Firecrawl API<br/>Company Validation]
        RESEARCH --> VALIDATE[Validate Node<br/>Data Normalization<br/>JSON Standards]
        VALIDATE --> OUTPUT[ExtractedData<br/>Pydantic Model]
    end

    subgraph "Caching Layer"
        EXTRACT -.->|Check| REDIS[Redis Cache<br/>24-48hr TTL]
        REDIS -.->|Hit 90%| OUTPUT
        VALIDATE -.->|Store| REDIS
    end

    subgraph "Model Selection"
        CLASSIFIER[Email Classifier] --> NANO[GPT-5-nano<br/>$0.05/1M]
        CLASSIFIER --> MINI[GPT-5-mini<br/>$0.25/1M]
        CLASSIFIER --> FULL[GPT-5<br/>$1.25/1M]
    end

    style EXTRACT fill:#4CAF50
    style RESEARCH fill:#2196F3
    style VALIDATE fill:#FF9800
    style REDIS fill:#9C27B0
```

## 🚀 Request Flow Sequence

```mermaid
sequenceDiagram
    participant User as Outlook User
    participant Addin as Outlook Add-in
    participant CDN as Azure CDN
    participant API as FastAPI
    participant Cache as Redis Cache
    participant LG as LangGraph
    participant GPT as GPT-5
    participant Zoho as Zoho CRM
    participant DB as PostgreSQL

    User->>Addin: Select Email
    Addin->>CDN: POST /intake/email
    CDN->>API: Forward Request
    API->>Cache: Check Pattern Hash
    
    alt Cache Hit
        Cache-->>API: Return Cached Result
    else Cache Miss
        API->>LG: Process Email
        LG->>GPT: Extract (mini)
        GPT-->>LG: Structured Data
        LG->>GPT: Research Company
        GPT-->>LG: Validation
        LG-->>API: ExtractedData
        API->>Cache: Store Result
    end
    
    API->>DB: Check Duplicates
    API->>Zoho: Create/Update Deal
    Zoho-->>API: Deal ID
    API->>DB: Store Record
    API-->>Addin: Success + IDs
    Addin-->>User: Show Confirmation
```

## 🧠 Intelligent Features

### C³ (Conformal Counterfactual Cache)
```mermaid
graph TD
    INPUT[Email Input] --> EMBED[Generate Embedding]
    EMBED --> SIMILAR[Find Similar<br/>Cosine Distance]
    SIMILAR --> RISK[Risk Assessment<br/>δ = 0.01]
    RISK --> DECIDE{Risk < δ?}
    DECIDE -->|Yes| CACHE_HIT[Use Cached]
    DECIDE -->|No| PROCESS[Process New]
    PROCESS --> STORE[Store Result]
    
    style RISK fill:#FF5722
    style CACHE_HIT fill:#4CAF50
```

### VoIT (Value-of-Insight Tree)
```mermaid
graph TD
    TASK[Processing Task] --> BUDGET[Budget: 5.0 units]
    BUDGET --> QUALITY[Target: 0.9 quality]
    QUALITY --> SELECT{Select Model}
    SELECT -->|Simple| NANO[nano: 0.5 units]
    SELECT -->|Standard| MINI[mini: 1.0 units]
    SELECT -->|Complex| FULL[full: 2.5 units]
    
    NANO --> EVAL[Evaluate Quality]
    MINI --> EVAL
    FULL --> EVAL
    EVAL --> ADJUST{Quality >= 0.9?}
    ADJUST -->|No| UPGRADE[Upgrade Model]
    ADJUST -->|Yes| COMPLETE[Complete]
    
    style BUDGET fill:#2196F3
    style QUALITY fill:#4CAF50
```

## 📊 Data Models

### Email Processing State
```python
class EmailProcessingState(TypedDict):
    email_content: str
    sender_domain: str
    extraction_result: Optional[Dict]
    company_research: Optional[Dict]
    validation_result: Optional[Dict]
    final_output: Optional[ExtractedData]
    cache_key: Optional[str]
    model_tier: Literal["nano", "mini", "full"]
    processing_time_ms: float
    cost_estimate: float
```

### Extracted Data Schema
```python
class ExtractedData(BaseModel):
    # Candidate Information
    candidate_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    linkedin_url: Optional[str]
    
    # Position Details
    job_title: Optional[str]
    location: Optional[str]
    company_name: Optional[str]
    industry: Optional[str]
    
    # Referral Information
    referrer_name: Optional[str]
    referrer_email: Optional[str]
    source: Optional[str]
    source_detail: Optional[str]
    
    # Additional Context
    notes: Optional[str]
    website: Optional[str]
```

## 🔐 Security Architecture

```mermaid
graph TB
    subgraph "Security Layers"
        WAF[Web Application Firewall]
        APIGW[API Gateway<br/>Rate Limiting]
        AUTH[API Key Auth<br/>Header Validation]
        KV[Azure Key Vault<br/>Secret Rotation]
        RBAC[Role-Based Access<br/>Zoho Permissions]
    end

    subgraph "Data Protection"
        TLS[TLS 1.3<br/>In Transit]
        ENCRYPT[AES-256<br/>At Rest]
        PII[PII Masking<br/>Logs & Telemetry]
    end

    WAF --> APIGW
    APIGW --> AUTH
    AUTH --> KV
    KV --> RBAC
    
    style WAF fill:#F44336
    style KV fill:#4CAF50
    style ENCRYPT fill:#2196F3
```

## 🎯 Performance Metrics

| Component | Metric | Target | Current |
|-----------|--------|--------|---------|
| **API Response** | P95 Latency | < 3s | 2.1s |
| **Cache Hit Rate** | Success % | > 80% | 92% |
| **LangGraph Pipeline** | Processing Time | < 3s | 2-3s |
| **GPT-5 Calls** | Cost per Email | < $0.01 | $0.003 |
| **Batch Processing** | Emails/Hour | > 1000 | 1500 |
| **WebSocket** | First Token | < 200ms | 180ms |
| **Database** | Query Time | < 100ms | 45ms |
| **Blob Storage** | Upload Time | < 500ms | 320ms |

## 🚦 Deployment Pipeline

```mermaid
graph LR
    subgraph "Development"
        DEV[Local Dev<br/>Python 3.11]
        TEST[Unit Tests<br/>pytest]
    end

    subgraph "CI/CD"
        GH[GitHub<br/>Push to main]
        BUILD[Docker Build<br/>Multi-stage]
        ACR[Azure Container<br/>Registry]
    end

    subgraph "Production"
        ACA[Container Apps<br/>Auto-scaling]
        SLOT[Blue-Green<br/>Deployment]
        MONITOR[Health Checks<br/>Monitoring]
    end

    DEV --> TEST
    TEST --> GH
    GH --> BUILD
    BUILD --> ACR
    ACR --> ACA
    ACA --> SLOT
    SLOT --> MONITOR

    style GH fill:#333
    style BUILD fill:#2196F3
    style ACA fill:#4CAF50
```

## 📈 Scaling Strategy

### Horizontal Scaling
- **Container Apps**: 1-10 replicas based on CPU/Memory
- **Redis Cache**: 6GB with clustering support
- **PostgreSQL**: Read replicas for query distribution
- **Service Bus**: Partitioned queues for parallel processing

### Vertical Scaling
- **GPT-5 Tiers**: Dynamic model selection based on complexity
- **Batch Size**: 1-50 emails per context window
- **Cache TTL**: 24hr-90day based on pattern stability
- **Context Window**: Up to 400K tokens with pgvector

## 🔧 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Office.js, JavaScript | Outlook integration |
| **CDN** | Azure Front Door | Global distribution |
| **API** | FastAPI, Python 3.11 | REST & WebSocket APIs |
| **Workflow** | LangGraph 0.2.74 | Orchestration pipeline |
| **AI** | GPT-5 (nano/mini/full) | Text extraction |
| **Cache** | Azure Redis 6.0 | Response caching |
| **Database** | PostgreSQL 15 + pgvector | Data persistence |
| **Queue** | Azure Service Bus | Batch processing |
| **Storage** | Azure Blob Storage | File attachments |
| **Search** | Azure AI Search | Semantic indexing |
| **Monitoring** | Application Insights | Telemetry & metrics |
| **Security** | Azure Key Vault | Secret management |
| **Container** | Docker, Container Apps | Deployment platform |

## 🌍 Environment Configuration

```bash
# Core Services
API_KEY=<secure-api-key>
DATABASE_URL=postgresql://...@.postgres.database.azure.com:5432/wellintake
AZURE_REDIS_CONNECTION_STRING=rediss://...@.redis.cache.windows.net:6380

# AI Configuration
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-5-mini
USE_LANGGRAPH=true

# Feature Flags
FEATURE_C3=true         # Conformal cache
FEATURE_VOIT=true       # Budget orchestration
C3_DELTA=0.01          # 1% risk tolerance
VOIT_BUDGET=5.0        # Processing units

# Integration
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net
FIRECRAWL_API_KEY=fc-...
```

## 📞 API Endpoints

### Core Endpoints
- `POST /intake/email` - Process single email
- `POST /intake/batch` - Process multiple emails
- `GET /health` - Health check
- `GET /cache/status` - Cache metrics

### WebSocket Endpoints
- `WS /ws/process` - Real-time processing
- `WS /ws/status` - Live status updates

### Admin Endpoints
- `POST /cache/invalidate` - Clear cache
- `POST /cache/warmup` - Preload patterns
- `GET /metrics` - Performance metrics

### Manifest Endpoints
- `GET /manifest.xml` - Outlook add-in manifest
- `GET /cdn/status` - CDN configuration
- `POST /cdn/purge` - Purge CDN cache

## 🔍 Monitoring & Observability

```mermaid
graph TB
    subgraph "Metrics Collection"
        APP[Application<br/>Custom Metrics]
        INFRA[Infrastructure<br/>System Metrics]
        BIZ[Business<br/>KPIs]
    end

    subgraph "Processing"
        AI[Application Insights<br/>Aggregation]
        LA[Log Analytics<br/>Queries]
        ALERT[Alert Rules<br/>Thresholds]
    end

    subgraph "Visualization"
        DASH[Azure Dashboard<br/>Real-time]
        REPORT[Power BI<br/>Analytics]
        SLACK[Slack/Teams<br/>Notifications]
    end

    APP --> AI
    INFRA --> AI
    BIZ --> AI
    AI --> LA
    LA --> ALERT
    LA --> DASH
    LA --> REPORT
    ALERT --> SLACK

    style AI fill:#2196F3
    style DASH fill:#4CAF50
    style ALERT fill:#FF5722
```

---

*Last Updated: September 2025 | Version: 1.4.0*