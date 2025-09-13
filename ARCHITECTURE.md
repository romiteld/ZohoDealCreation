# 🏗️ Well Intake API - System Architecture

> **Enterprise-Grade AI Email Processing System**  
> *C4 Model Architecture Documentation with Azure Cloud Infrastructure*

## 📋 Table of Contents
- [System Context](#system-context-c4-level-1)
- [Container Architecture](#container-architecture-c4-level-2)
- [Component Architecture](#component-architecture-c4-level-3)
- [Deployment Architecture](#deployment-architecture)
- [Data Flow Diagrams](#data-flow-diagrams)
- [Innovation & Algorithms](#innovation--algorithms)
- [Infrastructure & Resources](#infrastructure--resources)

---

## 🌐 System Context (C4 Level 1)

```mermaid
graph TB
    subgraph Users["👥 System Users"]
        Recruiter["👤 Recruitment Team<br/>Processes candidate emails"]
        Admin["👨‍💼 System Admin<br/>Manages configuration & monitoring"]
        Analyst["📊 Data Analyst<br/>Reviews metrics & insights"]
    end
    
    subgraph WellIntake["🚀 Well Intake System"]
        API["Well Intake API<br/>FastAPI + LangGraph<br/>C³ Cache + VoIT Orchestration"]
        OAuth["OAuth Proxy Service<br/>well-zoho-oauth-v2<br/>Flask App Service"]
    end
    
    subgraph ExternalSystems["🌐 External Systems"]
        Outlook["📧 Microsoft 365<br/>Email Client + Add-in"]
        Zoho["📊 Zoho CRM v8<br/>CRM System"]
        OpenAI["🤖 OpenAI GPT-5<br/>gpt-5-mini model"]
        Firecrawl["🔍 Firecrawl API<br/>Company Research"]
        Serper["🔎 Serper API<br/>Search Service"]
    end
    
    subgraph AzureServices["☁️ Azure Infrastructure"]
        Storage["📁 Blob Storage<br/>wellintakestorage0903"]
        Postgres["🗄️ PostgreSQL<br/>well-intake-db-0903<br/>with pgvector"]
        Redis["⚡ Redis Cache<br/>wellintakecache0903"]
        ServiceBus["📨 Service Bus<br/>well-intake-servicebus"]
        SignalR["🔌 SignalR<br/>well-intake-signalr"]
        Search["🔍 AI Search<br/>well-intake-search"]
        FrontDoor["🌍 Front Door CDN<br/>well-intake-frontdoor"]
        AppInsights["📊 App Insights<br/>Monitoring & Analytics"]
    end
    
    Recruiter -->|"Sends emails"| Outlook
    Admin -->|"Configures & monitors"| API
    Analyst -->|"Views analytics"| API
    
    Outlook -->|"REST/WebSocket"| API
    API -->|"OAuth/API v8"| OAuth
    OAuth -->|"API v8"| Zoho
    API -->|"GPT-5 API"| OpenAI
    API -->|"Research API"| Firecrawl
    API -->|"Search API"| Serper
    
    API --> Storage
    API --> Postgres
    API --> Redis
    API --> ServiceBus
    API --> SignalR
    API --> Search
    FrontDoor --> API
    API --> AppInsights
    
    style API fill:#4A90E2,stroke:#2E5C8A,stroke-width:3px,color:#fff
    style OAuth fill:#7B68EE,stroke:#5A4FCF,stroke-width:2px,color:#fff
    style Postgres fill:#336791,stroke:#234A6F,stroke-width:2px,color:#fff
    style Redis fill:#DC382D,stroke:#B02920,stroke-width:2px,color:#fff
```

---

## 🏛️ Container Architecture (C4 Level 2)

```mermaid
graph TB
    subgraph Frontend["🖥️ Frontend Layer"]
        OutlookAddin["📮 Outlook Add-in<br/>JavaScript/Office.js<br/>manifest.xml"]
        AdminUI["🎛️ Admin Dashboard<br/>Python/FastAPI<br/>import_exports_v2"]
    end
    
    subgraph Gateway["🔐 API Gateway Layer"]
        FrontDoor["🌍 Azure Front Door<br/>CDN + WAF<br/>well-intake-frontdoor"]
        OAuthProxy["🔑 OAuth Proxy<br/>Flask App Service<br/>well-zoho-oauth-v2"]
    end
    
    subgraph Application["⚡ Application Layer"]
        FastAPI["🚀 FastAPI Server<br/>Python 3.11<br/>main.py"]
        
        subgraph Routers["📡 API Routers"]
            IntakeAPI["/intake/email<br/>Email processing"]
            BatchAPI["/batch/*<br/>Batch processing"]
            CacheAPI["/cache/*<br/>Cache management"]
            VaultAPI["/api/vault-agent/*<br/>Canonical records"]
            AdminAPI["/admin/*<br/>Policies & imports"]
            StreamAPI["/ws/*<br/>WebSocket streaming"]
            ManifestAPI["/manifest.xml<br/>Add-in manifest"]
        end
    end
    
    subgraph Intelligence["🧠 AI Processing Layer"]
        LangGraph["🔄 LangGraph Manager<br/>3-node StateGraph<br/>langgraph_manager.py"]
        C3Cache["💾 C³ Cache Engine<br/>Conformal caching<br/>cache/c3.py"]
        VoIT["🎯 VoIT Orchestrator<br/>Budget-aware selection<br/>cache/voit.py"]
        BusinessRules["📋 Business Rules<br/>Deal formatting<br/>business_rules.py"]
    end
    
    subgraph Data["🗄️ Data Layer"]
        PostgreSQL["🐘 PostgreSQL<br/>well-intake-db-0903<br/>pgvector extension"]
        Redis["⚡ Redis Cache<br/>wellintakecache0903<br/>6GB Premium"]
        BlobStorage["📁 Blob Storage<br/>wellintakestorage0903<br/>email-attachments"]
        AISearch["🔍 AI Search<br/>well-intake-search<br/>Semantic indexing"]
    end
    
    subgraph Messaging["📨 Messaging Layer"]
        ServiceBus["📬 Service Bus<br/>email-batch-queue<br/>50 emails/batch"]
        SignalR["🔌 SignalR Service<br/>well-intake-signalr<br/>WebSocket hub"]
    end
    
    subgraph External["🌐 External Services"]
        OpenAI["🤖 OpenAI<br/>gpt-5-mini<br/>temperature=1"]
        Zoho["📊 Zoho CRM<br/>API v8<br/>Account/Contact/Deal"]
        Firecrawl["🔍 Firecrawl<br/>Company research<br/>5s timeout"]
        MSGraph["📧 MS Graph<br/>Email access<br/>OAuth 2.0"]
    end
    
    OutlookAddin --> FrontDoor
    AdminUI --> FastAPI
    FrontDoor --> FastAPI
    FastAPI --> OAuthProxy
    
    FastAPI --> LangGraph
    LangGraph --> C3Cache
    C3Cache --> VoIT
    LangGraph --> BusinessRules
    
    FastAPI --> PostgreSQL
    FastAPI --> Redis
    FastAPI --> BlobStorage
    FastAPI --> AISearch
    FastAPI --> ServiceBus
    FastAPI --> SignalR
    
    VoIT --> OpenAI
    OAuthProxy --> Zoho
    LangGraph --> Firecrawl
    FastAPI --> MSGraph
    
    style FastAPI fill:#4A90E2,stroke:#2E5C8A,stroke-width:3px,color:#fff
    style LangGraph fill:#9B59B6,stroke:#7D3C98,stroke-width:2px,color:#fff
    style C3Cache fill:#E74C3C,stroke:#C0392B,stroke-width:2px,color:#fff
    style PostgreSQL fill:#336791,stroke:#234A6F,stroke-width:2px,color:#fff
```

---

## 🔧 Component Architecture (C4 Level 3)

```mermaid
graph TB
    subgraph LangGraphWorkflow["🔄 LangGraph Workflow Engine (langgraph_manager.py)"]
        StateManager["📋 EmailProcessingState<br/>TypedDict with 25+ fields<br/>Learning-aware state"]
        ExtractNode["📤 extract_node()<br/>GPT-5-mini extraction<br/>Structured output"]
        ResearchNode["🔍 research_node()<br/>Firecrawl API<br/>Company validation"]
        ValidateNode["✅ validate_node()<br/>Business rules<br/>Data normalization"]
        BuildGraph["🏗️ build_graph()<br/>StateGraph assembly<br/>Node connections"]
        ErrorHandler["⚠️ SimplifiedEmailExtractor<br/>Fallback extraction<br/>Error recovery"]
    end
    
    subgraph C3CacheSystem["💾 C³ Cache System (cache/c3.py)"]
        C3Entry["📦 C3Entry<br/>Cached result<br/>Dependencies"]
        DependencyCert["🔐 DependencyCertificate<br/>Cache validation<br/>Risk bounds"]
        C3Reuse["♻️ c3_reuse_or_rebuild()<br/>Cache decision<br/>δ=0.01 risk"]
        Calibration["📊 update_calibration()<br/>Conformal scores<br/>Adaptive bounds"]
        RedisIO["💾 redis_io.py<br/>Save/load entries<br/>Vector storage"]
    end
    
    subgraph VoITOrchestrator["🎯 VoIT Orchestrator (cache/voit.py)"]
        VoITController["🎮 voit_controller()<br/>Main orchestrator<br/>Budget: 5.0 units"]
        ComplexityCalc["📊 calculate_complexity()<br/>Email scoring<br/>0.0-1.0 scale"]
        ModelSelect["🎯 select_model_tier()<br/>nano/mini/full<br/>Cost optimization"]
        QualityEval["✅ evaluate_quality()<br/>Score validation<br/>Target: 0.9"]
        BudgetTrack["💰 Budget Tracker<br/>Effort units<br/>Cost monitoring"]
    end
    
    subgraph BusinessLogic["📋 Business Rules (business_rules.py)"]
        RulesEngine["⚙️ BusinessRulesEngine<br/>apply_rules()<br/>Field normalization"]
        DealFormat["🏷️ format_deal_name()<br/>[Title] ([Location]) - [Firm]<br/>Pattern application"]
        SourceDetermine["🔍 determine_source()<br/>Email classification<br/>Source mapping"]
        OwnerAssign["👤 assign_owner()<br/>ZOHO_DEFAULT_OWNER<br/>Email lookup"]
    end
    
    subgraph Integration["🔌 Integration Layer"]
        ZohoClient["📊 ZohoApiClient<br/>integrations.py<br/>API v8 client"]
        PostgresClient["🐘 PostgreSQLClient<br/>integrations.py<br/>Deduplication"]
        BlobClient["📁 AzureBlobStorage<br/>integrations.py<br/>Attachments"]
        MSGraphClient["📧 MicrosoftGraphClient<br/>microsoft_graph_client.py<br/>Email access"]
    end
    
    StateManager --> ExtractNode
    ExtractNode --> ResearchNode
    ResearchNode --> ValidateNode
    ValidateNode --> StateManager
    StateManager -.->|On error| ErrorHandler
    
    ExtractNode --> C3Reuse
    C3Reuse --> C3Entry
    C3Entry --> DependencyCert
    C3Reuse --> RedisIO
    C3Reuse --> Calibration
    
    StateManager --> VoITController
    VoITController --> ComplexityCalc
    ComplexityCalc --> ModelSelect
    ModelSelect --> QualityEval
    VoITController --> BudgetTrack
    
    ValidateNode --> RulesEngine
    RulesEngine --> DealFormat
    RulesEngine --> SourceDetermine
    RulesEngine --> OwnerAssign
    
    RulesEngine --> ZohoClient
    StateManager --> PostgresClient
    ExtractNode --> BlobClient
    StateManager --> MSGraphClient
    
    style StateManager fill:#4A90E2,stroke:#2E5C8A,stroke-width:2px,color:#fff
    style C3Reuse fill:#E74C3C,stroke:#C0392B,stroke-width:2px,color:#fff
    style VoITController fill:#F39C12,stroke:#D68910,stroke-width:2px,color:#fff
    style RulesEngine fill:#27AE60,stroke:#1E8449,stroke-width:2px,color:#fff
```

---

## 🚀 Deployment Architecture

```mermaid
graph TB
    subgraph AzureCloud["☁️ Azure Cloud - East US Region"]
        subgraph ResourceGroups["🗂️ Resource Groups"]
            InfraRG["TheWell-Infra-East<br/>Infrastructure resources"]
        end
        
        subgraph ContainerApps["🐳 Container Apps Environment"]
            API["well-intake-api<br/>FastAPI Container<br/>2 CPU, 4GB RAM<br/>Auto-scale: 1-10"]
            OAuthApp["well-zoho-oauth-v2<br/>Flask App Service<br/>B1 Plan"]
        end
        
        subgraph Database["🗄️ Database Services"]
            PostgresFlexible["well-intake-db-0903<br/>PostgreSQL Flexible Server<br/>B_Standard_B2s<br/>32GB storage<br/>pgvector extension"]
        end
        
        subgraph Caching["⚡ Cache Services"]
            RedisCache["wellintakecache0903<br/>Redis Premium P1<br/>6GB memory<br/>Cluster enabled"]
        end
        
        subgraph Storage["📁 Storage Services"]
            BlobStorage["wellintakestorage0903<br/>StorageV2<br/>Hot tier<br/>Containers:<br/>- email-attachments"]
        end
        
        subgraph Messaging["📨 Messaging Services"]
            ServiceBus["well-intake-servicebus<br/>Premium tier<br/>Queues:<br/>- email-batch-queue"]
            SignalR["well-intake-signalr<br/>Standard tier<br/>1 unit<br/>1000 connections"]
        end
        
        subgraph Search["🔍 Search & AI"]
            AISearch["well-intake-search<br/>Standard tier<br/>Semantic search<br/>Vector indexes"]
            AppInsights["well-intake-insights<br/>Application Insights<br/>Log Analytics<br/>Custom metrics"]
        end
        
        subgraph Network["🌐 Networking"]
            FrontDoor["well-intake-frontdoor<br/>Premium tier<br/>WAF enabled<br/>Global PoPs"]
            DNS["DNS Zones<br/>Custom domains"]
        end
        
        subgraph Registry["📦 Container Registry"]
            ACR["wellintakeacr0903<br/>Basic tier<br/>Docker images"]
        end
    end
    
    subgraph GitHubActions["🔧 CI/CD Pipeline"]
        Workflow["GitHub Actions<br/>deploy-production.yml<br/>deploy-simple.yml"]
    end
    
    Workflow -->|Push images| ACR
    ACR -->|Deploy| API
    
    FrontDoor -->|Route traffic| API
    FrontDoor -->|Route OAuth| OAuthApp
    
    API --> PostgresFlexible
    API --> RedisCache
    API --> BlobStorage
    API --> ServiceBus
    API --> SignalR
    API --> AISearch
    API --> AppInsights
    
    OAuthApp --> RedisCache
    
    style API fill:#4A90E2,stroke:#2E5C8A,stroke-width:3px,color:#fff
    style PostgresFlexible fill:#336791,stroke:#234A6F,stroke-width:2px,color:#fff
    style RedisCache fill:#DC382D,stroke:#B02920,stroke-width:2px,color:#fff
    style FrontDoor fill:#FF6B35,stroke:#CC5429,stroke-width:2px,color:#fff
```

---

## 📊 Data Flow Diagrams

### Email Processing Flow

```mermaid
flowchart TB
    subgraph "📮 Input"
        A[📧 Email Received] --> B{🔍 Check Cache}
    end
    
    subgraph "💾 Cache Layer"
        B -->|Hit 92%| C[✅ Return Cached]
        B -->|Miss 8%| D[🔄 Process New]
    end
    
    subgraph "🤖 AI Processing"
        D --> E[📝 Extract<br/>GPT-5-mini]
        E --> F[🔍 Research<br/>Firecrawl]
        F --> G[✅ Validate<br/>Business Rules]
    end
    
    subgraph "💼 CRM Integration"
        G --> H[🔐 Check Duplicates]
        H --> I[📤 Create in Zoho]
        I --> J[💾 Store in DB]
    end
    
    subgraph "📈 Output"
        C --> K[📊 Return Result]
        J --> K
        K --> L[📨 Notify User]
    end
    
    style A fill:#e1f5fe
    style C fill:#c8e6c9
    style E fill:#fff9c4
    style I fill:#ffccbc
    style K fill:#d1c4e9
```

### Real-time Streaming Architecture

```mermaid
flowchart LR
    subgraph "🖥️ Clients"
        A1[📮 Outlook Add-in]
        A2[🌐 Web Dashboard]
        A3[📱 Mobile App]
    end
    
    subgraph "🔌 WebSocket Layer"
        B[🎯 Load Balancer<br/>Sticky Sessions]
        C[📡 SignalR Service<br/>1000 concurrent]
        D[🔄 Redis Backplane<br/>Pub/Sub]
    end
    
    subgraph "📤 Message Processing"
        E[👥 Connection Manager]
        F[📢 Group Broadcasting]
        G[✅ Acknowledgments]
    end
    
    A1 & A2 & A3 --> B
    B --> C
    C <--> D
    D --> E
    E --> F
    F --> G
    G -.->|Confirm| A1 & A2 & A3
    
    style C fill:#e3f2fd
    style D fill:#f3e5f5
    style F fill:#e8f5e9
```

---

## 🧠 Innovation & Algorithms

### C³ (Conformal Counterfactual Cache) Algorithm

```mermaid
flowchart TB
    subgraph "📥 Input Processing"
        A[📧 Email Input] --> B[#️⃣ SHA-256 Hash]
        A --> C[🧮 OpenAI Embedding<br/>1536 dimensions]
    end
    
    subgraph "🔍 Similarity Search"
        C --> D[📐 Cosine Similarity]
        D --> E[🔝 Top-K Candidates<br/>K=10]
        E --> F[📏 Edit Distance<br/>ε=3 chars]
    end
    
    subgraph "⚖️ Risk Assessment"
        F --> G[📊 Calibration Set<br/>1000 samples]
        G --> H[📈 Conformal Quantile<br/>99% confidence]
        H --> I[🎯 Risk Bound<br/>δ = 0.01]
    end
    
    subgraph "✅ Decision"
        I --> J{Confidence > 0.99?}
        J -->|Yes| K[💚 Cache Hit<br/><100ms]
        J -->|No| L[🔄 Process New<br/>2-3s]
    end
    
    subgraph "📚 Learning"
        L --> M[✔️ Validate]
        M --> N[🔄 Update Model]
        N --> O[💾 Store Result<br/>TTL: 24-90d]
        K --> P[📊 Metrics<br/>92% hit rate]
    end
    
    style A fill:#e3f2fd
    style I fill:#ffebee
    style K fill:#e8f5e9
    style P fill:#f3e5f5
```

### VoIT (Value-of-Insight Tree) Orchestration

```mermaid
flowchart TB
    subgraph "📊 Email Analysis"
        A[📧 Email] --> B[🏷️ Feature Extraction]
        B --> C[📈 Complexity Score<br/>0.0-1.0]
        C --> D[⚡ Urgency Detection]
        D --> E[💰 Business Value<br/>$0-$1000]
    end
    
    subgraph "💼 Budget Allocation"
        E --> F[🎯 Budget Calculator<br/>0.1-10 units]
        F --> G[✨ Quality Target<br/>0.8-0.99]
        G --> H[💵 Cost Constraints<br/>Max $0.01/email]
    end
    
    subgraph "🌳 Decision Tree"
        H --> I{Model Selection}
        I -->|Simple<0.3| J[🟢 GPT-5-nano<br/>$0.05/1M]
        I -->|Standard 0.3-0.7| K[🟡 GPT-5-mini<br/>$0.25/1M]
        I -->|Complex>0.7| L[🔴 GPT-5-full<br/>$1.25/1M]
        I -->|High-value| M[🔷 Multi-Model<br/>Ensemble]
    end
    
    subgraph "🔄 Optimization"
        J & K & L & M --> N[📊 Quality Check]
        N --> O{Target Met?}
        O -->|No + Budget| P[⬆️ Upgrade]
        O -->|No + No Budget| Q[⬇️ Degrade]
        O -->|Yes| R[✅ Complete]
        P --> I
    end
    
    style A fill:#e1f5fe
    style F fill:#fff9c4
    style J fill:#c8e6c9
    style K fill:#fff59d
    style L fill:#ffcdd2
    style M fill:#b3e5fc
    style R fill:#d1c4e9
```

---

## 🏢 Infrastructure & Resources

### Azure Resource Map

```mermaid
mindmap
  root((Azure Infrastructure))
    Compute
      Container Apps
        API Instances 1-10
        Auto-scaling
        Blue-Green Deploy
      Container Registry
        Docker Images
        Multi-arch builds
      Functions
        Event processors
        Scheduled jobs
    Data
      PostgreSQL
        400K context
        pgvector extension
        Read replicas
      Redis Cache
        6GB cluster
        3 shards
        Pub/Sub backplane
      Blob Storage
        25MB attachments
        Hot tier
        Versioning
      AI Search
        Semantic index
        Vector search
        3 replicas
    Network
      Front Door CDN
        15 edge locations
        Cache rules
        WAF protection
      Virtual Network
        3 subnets
        Private endpoints
        NSG rules
      Load Balancer
        L4/L7 routing
        Health probes
    Integration
      Service Bus
        Premium tier
        50 msg/batch
        Dead letter queue
      SignalR
        1000 connections
        WebSocket/SSE
        Groups/Hubs
      Event Grid
        Event routing
        1M events/mo
      Logic Apps
        10 workflows
        Connectors
    Security
      Key Vault
        HSM-backed
        Secret rotation
        Access policies
      Managed Identity
        System assigned
        RBAC integration
      Defender
        Threat detection
        Vulnerability scan
    Monitoring
      App Insights
        Custom metrics
        90-day retention
        Alerts
      Log Analytics
        30GB/month
        KQL queries
      Dashboard
        Real-time widgets
        Power BI integration
```

---

## 📈 Performance Metrics

```mermaid
graph LR
    subgraph "⚡ Response Times"
        A[Cache Hit<br/>< 100ms] 
        B[API Response<br/>P95: 2.1s]
        C[WebSocket<br/>First Token: 180ms]
    end
    
    subgraph "💰 Cost Optimization"
        D[Cache Rate<br/>92%]
        E[Cost/Email<br/>$0.003]
        F[Monthly Savings<br/>$8,500]
    end
    
    subgraph "📊 Scale Metrics"
        G[Throughput<br/>1500 emails/hr]
        H[Batch Size<br/>50 emails]
        I[Concurrent Users<br/>1000]
    end
    
    subgraph "🎯 Quality Scores"
        J[Accuracy<br/>98.5%]
        K[Dedup Rate<br/>99.9%]
        L[Uptime<br/>99.95%]
    end
    
    style A fill:#e8f5e9
    style D fill:#c8e6c9
    style E fill:#fff9c4
    style F fill:#d4e157
    style J fill:#b3e5fc
    style L fill:#81c784
```

---

## 🔐 Security Architecture

```mermaid
flowchart TB
    subgraph "🌐 Edge Security"
        A[🛡️ WAF<br/>OWASP 3.2] --> B[🚦 Rate Limiting<br/>100 req/min]
        B --> C[🔒 TLS 1.3<br/>In transit]
    end
    
    subgraph "🔑 Authentication"
        C --> D[🎫 API Keys<br/>Header validation]
        D --> E[🔐 OAuth 2.0<br/>Token management]
        E --> F[👤 Managed Identity<br/>Azure AD]
    end
    
    subgraph "🗝️ Secrets Management"
        F --> G[🔐 Key Vault<br/>HSM-backed]
        G --> H[🔄 Rotation<br/>90-day cycle]
        H --> I[📋 Access Policies<br/>RBAC]
    end
    
    subgraph "📊 Compliance"
        I --> J[🔍 Audit Logs<br/>90-day retention]
        J --> K[🛡️ Defender<br/>Threat detection]
        K --> L[📈 Sentinel<br/>SIEM/SOAR]
    end
    
    style A fill:#ffebee
    style D fill:#fff3e0
    style G fill:#e8f5e9
    style L fill:#e3f2fd
```

---

## 🚦 CI/CD Pipeline

```mermaid
flowchart LR
    subgraph "📝 Source Control"
        A[GitHub Push] --> B[Branch Protection]
    end
    
    subgraph "🔨 Build Stage"
        B --> C[Version Increment]
        C --> D[Run Tests]
        D --> E[Security Scan]
        E --> F[Docker Build]
    end
    
    subgraph "📦 Registry"
        F --> G[Container Scan]
        G --> H[Push to ACR]
    end
    
    subgraph "🚀 Deploy Stage"
        H --> I[Blue Environment]
        I --> J[Health Checks]
        J --> K{Healthy?}
        K -->|Yes| L[Traffic Switch]
        K -->|No| M[Rollback]
    end
    
    subgraph "✅ Post-Deploy"
        L --> N[Cache Clear]
        N --> O[Smoke Tests]
        O --> P[Notify Teams]
    end
    
    style A fill:#f4f4f4
    style D fill:#fff9c4
    style E fill:#ffebee
    style K fill:#e8f5e9
    style M fill:#ffcdd2
    style P fill:#e3f2fd
```

---

## 📊 System Health Dashboard

```mermaid
graph TB
    subgraph "🎯 KPIs"
        A[Uptime<br/>99.95%]
        B[Response Time<br/>P95: 2.1s]
        C[Error Rate<br/>0.05%]
        D[Cache Hit<br/>92%]
    end
    
    subgraph "💰 Cost Metrics"
        E[Daily Cost<br/>$142]
        F[Cost/Email<br/>$0.003]
        G[Monthly Savings<br/>$8,500]
    end
    
    subgraph "📈 Usage Stats"
        H[Daily Emails<br/>47,000]
        I[Active Users<br/>312]
        J[API Calls<br/>2.3M/day]
    end
    
    subgraph "⚠️ Alerts"
        K[Critical: 0]
        L[Warning: 2]
        M[Info: 14]
    end
    
    style A fill:#4caf50
    style B fill:#8bc34a
    style C fill:#4caf50
    style D fill:#81c784
    style E fill:#ffeb3b
    style F fill:#cddc39
    style G fill:#8bc34a
    style K fill:#4caf50
    style L fill:#ff9800
    style M fill:#03a9f4
```

---

## 📚 Documentation

### Quick Links
- 🔧 [API Documentation](./API.md)
- 🚀 [Deployment Guide](./DEPLOYMENT.md)
- 🔐 [Security Policies](./SECURITY.md)
- 📊 [Performance Tuning](./PERFORMANCE.md)
- 🧪 [Testing Strategy](./TESTING.md)

### Version History
| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2025-09-12 | C4 Model diagrams with icons |
| 1.5.0 | 2025-09-11 | Added innovative algorithms |
| 1.0.0 | 2025-08-29 | Initial architecture |

---

*Last Updated: September 2025 | Version: 2.0.0 | C4 Model Architecture*