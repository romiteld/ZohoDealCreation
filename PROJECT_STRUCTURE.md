# Well Intake API - Project Structure

```
outlook/
├── README.md                              # Main project documentation
├── CLAUDE.md                             # Claude Code instructions
├── requirements.txt                       # Python dependencies
├── Dockerfile                            # Container configuration
├── gunicorn.conf.py                      # WSGI server configuration
├── .env.local.template                   # Environment variables template
├── .gitignore                            # Git ignore rules
│
├── app/                                  # Core application code
│   ├── __init__.py                       # Package initialization
│   ├── main.py                           # FastAPI application entry point
│   ├── models.py                         # Data models and schemas
│   ├── langgraph_manager.py              # LangGraph workflow orchestration
│   ├── integrations.py                   # Zoho CRM integration
│   ├── business_rules.py                 # Business logic and rules
│   ├── firecrawl_research.py             # Company research integration
│   ├── database_enhancements.py          # PostgreSQL with vector support
│   ├── redis_cache_manager.py            # Redis caching layer
│   ├── cache_strategies.py               # Intelligent caching patterns
│   ├── azure_cost_optimizer.py           # GPT model tier selection
│   ├── batch_processor.py                # Multi-email processing
│   ├── service_bus_manager.py            # Azure Service Bus integration
│   ├── signalr_manager.py                # WebSocket streaming support
│   ├── streaming_endpoints.py            # Real-time API endpoints
│   ├── azure_ai_search_manager.py        # Semantic search and learning
│   ├── learning_analytics.py             # A/B testing and accuracy tracking
│   ├── monitoring.py                     # Application Insights integration
│   ├── security_config.py                # Azure Key Vault and security
│   ├── correction_learning.py            # ML-based correction system
│   ├── azure_ad_auth.py                  # Azure Active Directory auth
│   ├── microsoft_graph_client.py         # Microsoft Graph API client
│   └── realtime_queue_manager.py         # Real-time queue processing
│
├── addin/                                # Outlook Add-in
│   ├── manifest.xml                      # Office Add-in manifest
│   └── (static files for add-in UI)
│
├── scripts/                              # Utility and deployment scripts
│   ├── deploy.sh                         # Main deployment script
│   ├── startup.sh                        # Container startup script
│   ├── restart_app.sh                    # Application restart script
│   ├── azure_cli_outlook_commands.sh     # Azure CLI commands
│   ├── troubleshoot_addin.sh            # Add-in troubleshooting
│   ├── run_migration.py                  # Database migration runner
│   ├── initialize_database.py            # Database initialization
│   ├── update_manifest_version.py        # Manifest version updater
│   ├── check_extensions.py               # Database extensions checker
│   ├── check_zoho_now.py                # Zoho API status checker
│   ├── zoho_data_export.py              # Data export utility
│   ├── zoho_pattern_learner.py          # Pattern learning script
│   └── zoho_smart_export.py             # Smart export utility
│
├── tests/                                # Test suite
│   ├── test_batch_processing.py          # Batch processing tests
│   ├── test_container_deployment.py      # Container deployment tests
│   ├── test_addin_endpoints.py          # Add-in endpoint tests
│   ├── test_streaming.py                # Streaming functionality tests
│   ├── test_cost_tracking.py            # Cost optimization tests
│   ├── test_redis_cache.py              # Redis cache tests
│   ├── test_database_enhancements.py    # Database feature tests
│   └── test_langgraph.py                # LangGraph workflow tests
│
├── deployment/                           # Deployment configurations
│   ├── container_apps_config.yaml       # Azure Container Apps config
│   └── deploy_with_security.sh          # Secure deployment script
│
├── docs/                                # Documentation archive
│   ├── BATCH_PROCESSING_SUMMARY.md      # Batch processing documentation
│   ├── DATABASE_ENHANCEMENTS.md         # Database features documentation
│   ├── LEARNING_SYSTEM_GUIDE.md         # Learning system documentation
│   ├── MANIFEST_REFRESH_GUIDE.md        # Add-in manifest guide
│   ├── MANIFEST_UPDATE_GUIDE.md         # Manifest update procedures
│   ├── PRODUCTION_READINESS.md          # Production deployment guide
│   ├── PROXY_FIX_SUMMARY.md            # Proxy configuration fixes
│   ├── SECURITY_AND_MONITORING.md       # Security implementation guide
│   ├── SERVICE_BUS_SETUP.md            # Service Bus configuration
│   ├── STREAMING_IMPLEMENTATION.md      # Streaming features guide
│   ├── URL_UPDATE_SUMMARY.md           # URL update procedures
│   └── CLEANUP_RECOMMENDATIONS.md       # Cleanup guidelines
│
├── archive/                             # Archived components
│   └── voice-ui/                        # Voice interface (archived)
│       ├── server.js                    # Express server
│       ├── package.json                 # Node.js dependencies
│       └── public/                      # Static assets
│
├── migrations/                          # Database migrations
├── oauth_service/                       # OAuth service components
├── static/                             # Static assets
└── zoho/                               # Python virtual environment (ignored)
```

## Architecture Overview

### Core Components
- **FastAPI Application** (`app/main.py`): Main API server with WebSocket support
- **LangGraph Workflow** (`app/langgraph_manager.py`): Three-node email processing pipeline
- **Redis Cache Layer** (`app/redis_cache_manager.py`): 90% cost reduction through intelligent caching
- **Azure Integrations**: Container Apps, Service Bus, SignalR, AI Search, Key Vault
- **Outlook Add-in** (`addin/`): Office 365 integration with manifest

### Key Features
- **GPT-5 Model Tiering**: Automatic selection of nano/mini/full models based on complexity
- **400K Context Window**: PostgreSQL with pgvector for large email batch processing
- **Real-time Streaming**: WebSocket support for live processing updates
- **Enterprise Security**: Azure AD authentication, Key Vault secret management
- **ML Learning System**: Pattern recognition and accuracy improvement

### Deployment
- **Production**: Azure Container Apps with auto-scaling
- **Database**: PostgreSQL with vector extensions
- **Cache**: Azure Cache for Redis with 24-48 hour TTL
- **Storage**: Azure Blob Storage for attachments
- **Monitoring**: Application Insights with custom metrics

This structure provides clear separation of concerns, maintainable code organization, and production-ready deployment capabilities.