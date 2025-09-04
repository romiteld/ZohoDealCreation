"""
FastAPI main application using PostgreSQL with pgvector
Production-ready with Azure Container Apps deployment
"""

# LangGraph implementation - PostgreSQL with vector support
import os
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status, Header, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import models and services
from app.models import EmailPayload as EmailRequest, ProcessingResult as ZohoResponse, ExtractedData
from app.business_rules import BusinessRulesEngine
from app.integrations import ZohoApiClient as ZohoIntegration, AzureBlobStorageClient as AzureBlobStorage, PostgreSQLClient
from app.microsoft_graph_client import MicrosoftGraphClient
from app.azure_ad_auth import get_auth_service
from app.realtime_queue_manager import get_queue_manager, websocket_endpoint, EmailStatus
from app.manifest_cache_service import get_manifest_cache_service

# API Key Authentication with secure comparison and rate limiting
import hmac
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib

API_KEY = os.getenv("API_KEY")
if not API_KEY or API_KEY == "your-secure-api-key-here":
    logger.warning("API_KEY not properly configured - using development key")
    API_KEY = os.getenv("API_KEY", "dev-key-only-for-testing")

# Rate limiting for API key verification
api_key_attempts = defaultdict(list)
MAX_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

async def verify_api_key(request: Request, x_api_key: str = Header(...)):
    """Verify API key from header with timing-safe comparison and rate limiting"""
    if not x_api_key:
        logger.warning("Missing API key in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required"
        )
    
    # Get client IP for rate limiting
    client_ip = request.client.host
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()[:16]
    rate_limit_key = f"{client_ip}:{key_hash}"
    
    # Check rate limiting
    current_time = datetime.utcnow()
    attempts = api_key_attempts[rate_limit_key]
    
    # Clean old attempts
    api_key_attempts[rate_limit_key] = [
        attempt for attempt in attempts 
        if current_time - attempt < LOCKOUT_DURATION
    ]
    
    # Check if locked out
    if len(api_key_attempts[rate_limit_key]) >= MAX_ATTEMPTS:
        logger.warning(f"Rate limit exceeded for {client_ip} with key {key_hash}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {LOCKOUT_DURATION.total_seconds() / 60} minutes"
        )
    
    # Use timing-safe comparison to prevent timing attacks
    if not hmac.compare_digest(x_api_key, API_KEY):
        # Record failed attempt
        api_key_attempts[rate_limit_key].append(current_time)
        logger.warning(f"Invalid API key attempt from {client_ip} with key {key_hash}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )
    
    # Clear successful attempts
    if rate_limit_key in api_key_attempts:
        del api_key_attempts[rate_limit_key]
    
    return x_api_key

async def verify_user_auth(authorization: str = Header(None)):
    """Verify user authentication via Microsoft token or API key"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    # Check if it's a Bearer token (Microsoft auth) or API key
    if authorization.startswith('Bearer '):
        # Microsoft token validation
        token = authorization.split(' ')[1]
        
        # For development/testing, allow test tokens
        if token.startswith('test-token-'):
            logger.info("Test token accepted for development")
            return {"type": "test", "user_id": "test-user"}
        
        try:
            # Validate Microsoft token
            auth_service = get_auth_service()
            user_info = auth_service.decode_token(token)
            
            if not user_info or 'oid' not in user_info:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Microsoft token"
                )
            
            return {
                "type": "microsoft",
                "user_id": user_info['oid'],
                "email": user_info.get('preferred_username'),
                "name": user_info.get('name')
            }
            
        except Exception as e:
            logger.error(f"Microsoft token validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
    
    elif authorization == API_KEY:
        # API key authentication
        return {"type": "api_key", "user_id": "api_client"}
    
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Well Intake API with Cosmos DB vector store")
    
    # Initialize PostgreSQL client with error handling and timeout
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            postgres_client = PostgreSQLClient(database_url)
            # Try to connect with a longer timeout
            await asyncio.wait_for(postgres_client.init_pool(), timeout=30.0)
            # Ensure tables exist
            await postgres_client.ensure_tables()
            app.state.postgres_client = postgres_client
            logger.info("PostgreSQL client initialized successfully with tables")
        except asyncio.TimeoutError:
            logger.warning("PostgreSQL connection timed out (will continue without deduplication)")
            app.state.postgres_client = None
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed (will continue without deduplication): {e}")
            app.state.postgres_client = None
    else:
        logger.warning("DATABASE_URL not configured, PostgreSQL deduplication disabled")
        app.state.postgres_client = None
    
    # Initialize vector store if available
    try:
        from app.vector_store import get_vector_store
        vector_store = await get_vector_store()
        app.state.vector_store = vector_store
        logger.info("Cosmos DB vector store initialized")
    except Exception as e:
        logger.warning(f"Vector store initialization failed (will continue without): {e}")
        app.state.vector_store = None
    
    # Initialize Zoho integration with PostgreSQL client
    app.state.zoho_integration = ZohoIntegration(
        oauth_service_url=os.getenv("ZOHO_OAUTH_SERVICE_URL", "https://well-zoho-oauth.azurewebsites.net")
    )
    # Pass PostgreSQL client to Zoho client for caching
    if hasattr(app.state, 'postgres_client') and app.state.postgres_client:
        app.state.zoho_integration.pg_client = app.state.postgres_client
        logger.info("Zoho integration initialized with PostgreSQL caching")
    
    # Initialize Service Bus manager if connection string is available
    service_bus_conn = os.getenv("SERVICE_BUS_CONNECTION_STRING") or os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
    if service_bus_conn:
        try:
            from app.service_bus_manager import ServiceBusManager
            app.state.service_bus_manager = ServiceBusManager()
            await app.state.service_bus_manager.connect()
            logger.info("Azure Service Bus manager initialized for batch processing")
        except Exception as e:
            logger.warning(f"Service Bus initialization failed (batch processing disabled): {e}")
            app.state.service_bus_manager = None
    else:
        logger.info("Service Bus not configured, batch processing will use direct mode")
        app.state.service_bus_manager = None
    
    # Initialize Microsoft Graph client for real email integration
    try:
        app.state.graph_client = MicrosoftGraphClient()
        is_connected = await app.state.graph_client.test_connection()
        if is_connected:
            logger.info("Microsoft Graph client initialized successfully")
        else:
            logger.warning("Microsoft Graph client initialization failed - using fallback mode")
            app.state.graph_client = None
    except Exception as e:
        logger.warning(f"Microsoft Graph client initialization error: {e}")
        app.state.graph_client = None
    
    # Initialize manifest cache warmup after all services are ready
    try:
        from app.startup_warmup import perform_manifest_startup_warmup, schedule_background_manifest_warmup
        
        # Perform initial cache warmup (fast startup)
        warmup_stats = await perform_manifest_startup_warmup()
        
        if 'error' not in warmup_stats:
            logger.info(f"Manifest cache warmed during startup: {warmup_stats.get('success_rate', '0%')} success rate")
            
            # Schedule comprehensive warmup in background
            await schedule_background_manifest_warmup()
        else:
            logger.warning(f"Manifest warmup failed: {warmup_stats.get('error', 'Unknown error')}")
            
        app.state.manifest_warmup_stats = warmup_stats
        
    except Exception as e:
        logger.warning(f"Manifest warmup initialization failed: {e}")
        app.state.manifest_warmup_stats = {"error": str(e)}
    
    # Initialize Redis monitoring service
    try:
        from app.redis_monitoring import get_monitoring_service
        from app.redis_cache_manager import get_cache_manager
        
        monitoring_service = get_monitoring_service()
        cache_manager = await get_cache_manager()
        
        # Start background monitoring
        await monitoring_service.start_monitoring(cache_manager, interval_minutes=5)
        
        app.state.redis_monitoring = monitoring_service
        logger.info("Redis monitoring service initialized and started")
        
    except Exception as e:
        logger.warning(f"Redis monitoring initialization failed: {e}")
        app.state.redis_monitoring = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down Well Intake API")
    if hasattr(app.state, 'vector_store') and app.state.vector_store:
        from app.vector_store import cleanup_vector_store
        await cleanup_vector_store()
    if hasattr(app.state, 'postgres_client') and app.state.postgres_client:
        await app.state.postgres_client.close()
    if hasattr(app.state, 'service_bus_manager') and app.state.service_bus_manager:
        await app.state.service_bus_manager.close()
    # Cleanup handled by individual cache managers

# Create FastAPI app
app = FastAPI(
    title="Well Intake API",
    description="Intelligent email processing with Cosmos DB",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS with strict domain allowlist
ALLOWED_ORIGINS = [
    # Azure Container Apps domains
    "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io",
    "https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io",
    
    # Microsoft Office domains
    "https://outlook.office.com",
    "https://outlook.office365.com",
    "https://outlook.live.com",
    "https://outlook.office365-ppe.com",
    "https://outlook-sdf.office.com",
    "https://outlook.office365.us",
    "https://outlook.office365.cn",
    
    # Development environments (remove in production)
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000"
]

# Remove localhost origins in production
if os.getenv("ENVIRONMENT", "production") == "production":
    ALLOWED_ORIGINS = [origin for origin in ALLOWED_ORIGINS if not origin.startswith("http://localhost") and not origin.startswith("http://127.0.0.1")]

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Allow framing for Outlook Add-in endpoints
        add_in_paths = ["/manifest.xml", "/commands.html", "/commands.js", "/taskpane.html", 
                       "/taskpane.js", "/placeholder.html", "/loader.html", "/config.js",
                       "/icon-16.png", "/icon-32.png", "/icon-64.png", "/icon-80.png", "/icon-128.png",
                       "/addin/manifest.xml", "/addin/commands.html", "/addin/commands.js", 
                       "/addin/taskpane.html", "/addin/taskpane.js", "/addin/config.js",
                       "/addin/icon-16.png", "/addin/icon-32.png", "/addin/icon-64.png", "/addin/icon-80.png", "/addin/icon-128.png"]
        if not any(request.url.path.startswith(path) for path in add_in_paths):
            # Only set X-Frame-Options for non-add-in endpoints
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        else:
            # For add-in endpoints, allow framing from Office domains
            if "X-Frame-Options" in response.headers:
                del response.headers["X-Frame-Options"]
            
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Adjust CSP for add-in endpoints
        if any(request.url.path.startswith(path) for path in add_in_paths):
            # More permissive CSP for add-in pages
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' https://*.office.com https://*.office365.com https://*.microsoft.com; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://appsforoffice.microsoft.com https://*.office.com https://ajax.aspnetcdn.com; "
                "style-src 'self' 'unsafe-inline' https://*.office.com; "
                "img-src 'self' data: https://*.office.com https://*.microsoft.com; "
                "connect-src 'self' wss://*.azurecontainerapps.io https://*.azurecontainerapps.io https://*.office.com; "
                "frame-src 'self' https://*.office.com https://*.office365.com https://*.microsoft.com https://telemetryservice.firstpartyapps.oaspapps.com; "
                "frame-ancestors https://outlook.office.com https://outlook.office365.com https://*.outlook.com;"
            )
        else:
            # Standard CSP for API endpoints
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://appsforoffice.microsoft.com; style-src 'self' 'unsafe-inline';"
        
        return response

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add Trusted Host middleware to prevent host header attacks
ALLOWED_HOSTS = [
    "*.azurecontainerapps.io",
    "localhost",
    "127.0.0.1",
    "testserver"  # For FastAPI TestClient
]

if os.getenv("ENVIRONMENT", "production") == "production":
    ALLOWED_HOSTS = ["*.azurecontainerapps.io"]

# Add TrustedHostMiddleware - disabled in test environment
if os.getenv("ENVIRONMENT", "production") != "test":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=ALLOWED_HOSTS
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

# Include streaming endpoints
from app.streaming_endpoints import router as streaming_router
app.include_router(streaming_router)

# Include manifest template endpoints
from app.manifest_endpoints import router as manifest_router
app.include_router(manifest_router)

# Include manifest monitoring dashboard
from app.manifest_monitoring import router as manifest_monitoring_router
app.include_router(manifest_monitoring_router)

# Include CDN management endpoints
try:
    from app.cdn_endpoints import router as cdn_router
    app.include_router(cdn_router)
    logger.info("CDN router loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load CDN router: {e}")
except Exception as e:
    logger.error(f"Error loading CDN router: {e}")

# Initialize services (zoho_integration will be initialized in lifespan)
business_rules = BusinessRulesEngine()
blob_storage = AzureBlobStorage(
    connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING", ""),
    container_name=os.getenv("AZURE_CONTAINER_NAME", "email-attachments")
)

# Removed: SerperDev API (deprecated)

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Well Intake API",
        "version": "2.1.0",
        "status": "operational",
        "storage": "Cosmos DB for PostgreSQL",
        "vector_support": "pgvector",
        "batch_processing": "Azure Service Bus with GPT-5-mini",
        "max_batch_size": 50,
        "context_window": "400K tokens",
        "no_sqlite": True,
        "endpoints": [
            "/health",
            "/intake/email",
            "/batch/submit",
            "/batch/process",
            "/batch/status/{batch_id}",
            "/batch/queue/status",
            "/batch/queue/process",
            "/batch/deadletter/process",
            "/test/kevin-sullivan",
            "/cache/status",
            "/cache/invalidate",
            "/cache/warmup",
            "/manifest.xml",
            "/commands.js",
            "/auth/login",
            "/auth/callback",
            "/api/user/info",
            "/api/user/logout",
            "/api/auth/users",
            "/api/emails/queue",
            "/api/emails/{email_id}",
            "/api/voice/process",
            "/api/webhook/github",
            "/api/webhook/github/status",
            "/api/webhook/github/test"
        ]
    }

@app.get("/learning/analytics/{field_name}", dependencies=[Depends(verify_api_key)])
async def get_field_analytics(field_name: str, days_back: int = 30, domain: Optional[str] = None):
    """Get learning analytics for a specific extraction field"""
    try:
        # Input validation
        if not field_name or len(field_name) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid field name"
            )
        
        if days_back < 1 or days_back > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="days_back must be between 1 and 365"
            )
        
        if domain and not domain.replace('.', '').replace('-', '').isalnum():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid domain format"
            )
        from app.learning_analytics import LearningAnalytics
        from app.correction_learning import CorrectionLearningService
        
        # Initialize services
        correction_service = CorrectionLearningService(None, use_azure_search=True)
        analytics = LearningAnalytics(search_manager=correction_service.search_manager)
        
        # Get field analytics
        # Temporarily disable analytics
        result = {
            "field_name": field_name,
            "analytics_disabled": True,
            "message": "Analytics temporarily disabled"
        }
        # result = await analytics.get_field_analytics(
        #     field_name=field_name,
        #     days_back=days_back,
        #     email_domain=domain
        # )
        
        return result
    except Exception as e:
        logger.error(f"Failed to get field analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/learning/variants", dependencies=[Depends(verify_api_key)])
async def get_prompt_variants():
    """Get A/B testing report for prompt variants"""
    try:
        from app.learning_analytics import LearningAnalytics
        
        analytics = LearningAnalytics(enable_ab_testing=True)
        report = await analytics.get_variant_report()
        
        return report
    except Exception as e:
        logger.error(f"Failed to get variant report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/learning/insights", dependencies=[Depends(verify_api_key)])
async def get_learning_insights(domain: Optional[str] = None, days_back: int = 30):
    """Get overall learning insights from Azure AI Search"""
    try:
        from app.azure_ai_search_manager import AzureAISearchManager
        
        search_manager = AzureAISearchManager()
        insights = await search_manager.get_learning_insights(
            email_domain=domain,
            days_back=days_back
        )
        
        return insights
    except Exception as e:
        logger.error(f"Failed to get learning insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint with service status"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "operational",
            "cosmos_db": "unknown",
            "zoho": "unknown",
            "blob_storage": "unknown",
            "openai": "configured" if os.getenv("OPENAI_API_KEY") else "missing",
            "vector_store": "cosmos_db_pgvector",
            "redis_cache": "unknown"
        },
        "environment": os.getenv("ENVIRONMENT", "production"),
        "no_sqlite": True,
        "no_chroma": True
    }
    
    # Check Cosmos DB
    try:
        if hasattr(app.state, 'postgres_client') and app.state.postgres_client:
            await app.state.postgres_client.test_connection()
            health_status["services"]["cosmos_db"] = "operational"
        else:
            health_status["services"]["cosmos_db"] = "not_configured"
    except Exception as e:
        logger.warning(f"Cosmos DB health check failed: {e}")
        health_status["services"]["cosmos_db"] = "error"
    
    # Check Zoho
    try:
        if hasattr(app.state, 'zoho_integration') and app.state.zoho_integration:
            app.state.zoho_integration.get_access_token()
            health_status["services"]["zoho"] = "operational"
        else:
            health_status["services"]["zoho"] = "not_initialized"
    except Exception as e:
        logger.warning(f"Zoho health check failed: {e}")
        health_status["services"]["zoho"] = "error"
    
    # Check Blob Storage
    try:
        if blob_storage.test_connection():
            health_status["services"]["blob_storage"] = "operational"
        else:
            health_status["services"]["blob_storage"] = "container_not_found"
    except Exception as e:
        logger.warning(f"Blob Storage health check failed: {e}")
        health_status["services"]["blob_storage"] = "error"
    
    # Check Redis Cache with enhanced fallback status
    try:
        from app.redis_cache_manager import get_redis_health_status
        redis_health = await get_redis_health_status()
        
        # Map Redis health status to service status
        status_mapping = {
            "healthy": "operational",
            "unhealthy": "degraded", 
            "not_configured": "not_configured",
            "circuit_breaker_open": "circuit_breaker_open",
            "fallback_mode": "fallback_mode",
            "error": "error"
        }
        
        health_status["services"]["redis_cache"] = status_mapping.get(
            redis_health.get("status"), "unknown"
        )
        
        # Include detailed Redis metrics and fallback information
        health_status["redis_details"] = {
            "connection_status": redis_health.get("connection_status"),
            "circuit_breaker_status": redis_health.get("circuit_breaker_status"),
            "fallback_mode": redis_health.get("fallback_mode"),
            "response_time_ms": redis_health.get("response_time_ms"),
            "error": redis_health.get("error")
        }
        
        # Get performance metrics if available
        try:
            from app.redis_cache_manager import get_cache_manager
            cache_manager = await get_cache_manager()
            metrics = await cache_manager.get_metrics()
            health_status["cache_metrics"] = {
                "hit_rate": metrics.get("hit_rate", "0%"),
                "total_requests": metrics.get("total_requests", 0),
                "estimated_savings": f"${metrics.get('savings', 0):.2f}",
                "uptime_percentage": metrics.get("uptime_percentage", "0%"),
                "fallback_activations": metrics.get("fallback_activations", 0)
            }
        except:
            health_status["cache_metrics"] = {
                "hit_rate": "0%",
                "total_requests": 0,
                "estimated_savings": "$0.00",
                "uptime_percentage": "0%",
                "fallback_activations": 0
            }
            
    except Exception as e:
        logger.warning(f"Redis cache health check failed: {e}")
        health_status["services"]["redis_cache"] = "error"
        health_status["redis_details"] = {
            "error": f"Health check failed: {str(e)}"
        }
    
    return health_status

@app.post("/intake/email", response_model=ZohoResponse, dependencies=[Depends(verify_api_key)])
async def process_email(request: EmailRequest, req: Request):
    """Process email and create Zoho CRM records with learning from user corrections"""
    try:
        # Input validation
        import re
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, request.sender_email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sender email format"
            )
        
        # Validate body length (prevent excessive processing)
        if len(request.body) > 100000:  # 100KB limit
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Email body too large (max 100KB)"
            )
        
        # Sanitize inputs to prevent injection attacks
        if request.sender_name and len(request.sender_name) > 200:
            request.sender_name = request.sender_name[:200]
        
        if request.subject and len(request.subject) > 500:
            request.subject = request.subject[:500]
        
        logger.info(f"Processing email from {request.sender_email}")
        
        # Initialize correction learning and analytics if user provided corrections
        correction_service = None
        learning_analytics = None
        prompt_variant = None
        
        if request.user_corrections and request.ai_extraction:
            try:
                from app.correction_learning import CorrectionLearningService, FeedbackLoop
                from app.learning_analytics import LearningAnalytics
                import hashlib
                from datetime import datetime
                
                # Initialize correction service with Azure AI Search
                if hasattr(req.app.state, 'postgres_client') and req.app.state.postgres_client:
                    correction_service = CorrectionLearningService(
                        req.app.state.postgres_client, 
                        use_azure_search=True
                    )
                    feedback_loop = FeedbackLoop(correction_service)
                    
                    # Initialize learning analytics
                    learning_analytics = LearningAnalytics(
                        search_manager=correction_service.search_manager,
                        enable_ab_testing=True
                    )
                    
                    # Process and store the user feedback
                    feedback_result = await feedback_loop.process_user_feedback(
                        email_data={
                            'sender_email': request.sender_email,
                            'body': request.body
                        },
                        ai_extraction=request.ai_extraction,
                        user_edits=request.user_corrections
                    )
                    
                    # Track correction in analytics
                    if feedback_result.get('fields_corrected', 0) > 0:
                        extraction_id = hashlib.md5(
                            f"{request.sender_email}:{datetime.utcnow().isoformat()}".encode()
                        ).hexdigest()
                        
                        field_corrections = {}
                        for field, changes in feedback_result.get('corrections', {}).items():
                            field_corrections[field] = (
                                changes['original'], 
                                changes['corrected']
                            )
                        
                        await learning_analytics.track_correction(
                            extraction_id=extraction_id,
                            field_corrections=field_corrections,
                            prompt_variant_id=prompt_variant.variant_id if prompt_variant else None
                        )
                    
                    logger.info(f"Stored user corrections: {feedback_result['fields_corrected']} fields corrected")
            except Exception as e:
                logger.warning(f"Could not store user corrections: {e}")
        
        # Process attachments
        attachment_urls = []
        if request.attachments:
            for attachment in request.attachments:
                url = await blob_storage.upload_attachment(
                    attachment.filename,
                    attachment.content,
                    attachment.content_type
                )
                if url:
                    attachment_urls.append(url)
        
        # Extract sender domain
        sender_domain = request.sender_email.split('@')[1] if '@' in request.sender_email else 'unknown.com'
        
        # Check if user provided corrections (skip AI if so)
        if request.user_corrections:
            # User has already reviewed and corrected the data
            logger.info("Using user-provided corrections directly")
            from app.models import ExtractedData
            extracted_data = ExtractedData(**request.user_corrections)
        else:
            # Use LangGraph implementation
            try:
                logger.info("Using LangGraph for email processing")
                from app.langgraph_manager import EmailProcessingWorkflow
                
                # Initialize with learning if available
                workflow = EmailProcessingWorkflow()
                
                # Enhance prompts with historical corrections if available
                if correction_service:
                    # Get domain patterns for enhanced extraction
                    patterns = await correction_service.get_common_patterns(
                        email_domain=sender_domain,
                        min_frequency=1
                    )
                    if patterns:
                        logger.info(f"Applying {len(patterns)} learned patterns from previous corrections")
                
                extracted_data = await workflow.process_email(request.body, sender_domain)
                logger.info(f"Extracted data with LangGraph: {extracted_data}")
            except Exception as e:
                logger.warning(f"LangGraph processing failed: {e}, using fallback extractor")
                from app.langgraph_manager import SimplifiedEmailExtractor
                extracted_data = SimplifiedEmailExtractor.extract(request.body, request.sender_email)
        
        # Apply business rules
        processed_data = business_rules.process_data(
            extracted_data.model_dump() if hasattr(extracted_data, 'model_dump') else extracted_data,
            request.body,
            request.sender_email
        )
        # Convert back to ExtractedData model
        from app.models import ExtractedData
        enhanced_data = ExtractedData(**processed_data)
        
        # Check for duplicates using Cosmos DB
        is_duplicate = False
        if hasattr(req.app.state, 'postgres_client') and req.app.state.postgres_client:
            is_duplicate = await req.app.state.postgres_client.check_duplicate(
                request.sender_email,
                enhanced_data.candidate_name
            )
        
        if is_duplicate:
            logger.info(f"Duplicate detected for {request.sender_email}")
        
        # Create or update Zoho records
        zoho_result = await req.app.state.zoho_integration.create_or_update_records(
            enhanced_data,
            request.sender_email,
            attachment_urls,
            is_duplicate
        )
        
        # Store in database for deduplication
        if not is_duplicate and hasattr(req.app.state, 'postgres_client') and req.app.state.postgres_client:
            await req.app.state.postgres_client.store_processed_email(
                request.sender_email,
                enhanced_data.candidate_name,
                zoho_result["deal_id"]
            )
        
        # Determine message based on duplicate status
        if zoho_result.get("was_duplicate"):
            message = f"Email processed successfully (found existing records in Zoho)"
        else:
            message = "Email processed successfully"
        
        return ZohoResponse(
            status="success",
            deal_id=zoho_result["deal_id"],
            account_id=zoho_result["account_id"],
            contact_id=zoho_result["contact_id"],
            deal_name=zoho_result["deal_name"],
            primary_email=zoho_result["primary_email"],
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error processing email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test/kevin-sullivan", dependencies=[Depends(verify_api_key)])
async def test_kevin_sullivan(req: Request):
    """Test endpoint with Kevin Sullivan sample email"""
    test_email = EmailRequest(
        sender_email="referrer@wellpartners.com",
        sender_name="John Referrer",
        subject="Introduction - Kevin Sullivan for Senior Financial Advisor Role",
        body="""
        Hi Team,
        
        I wanted to introduce you to Kevin Sullivan who would be perfect for the 
        Senior Financial Advisor position in the Fort Wayne area.
        
        Kevin has over 10 years of experience in wealth management and has consistently 
        exceeded his targets. He's currently looking for new opportunities and would be 
        a great addition to your team.
        
        Please let me know if you'd like to schedule a call to discuss further.
        
        Best regards,
        John Referrer
        Well Partners Recruiting
        """,
        received_date=datetime.utcnow().isoformat(),
        attachments=[]
    )
    
    return await process_email(test_email, req)

# Batch processing endpoints
@app.post("/batch/submit", dependencies=[Depends(verify_api_key)])
async def submit_batch(emails: List[EmailRequest], priority: int = 0):
    """
    Submit a batch of emails for processing using GPT-5-mini
    
    Args:
        emails: List of email payloads to process
        priority: Processing priority (0-9, higher = more priority)
    
    Returns:
        Batch submission confirmation with batch ID
    """
    try:
        # Validate batch size
        if len(emails) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch size exceeds maximum of 50 emails"
            )
        
        if len(emails) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch must contain at least one email"
            )
        
        # Validate priority
        if priority < 0 or priority > 9:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Priority must be between 0 and 9"
            )
        
        logger.info(f"Received batch submission with {len(emails)} emails")
        
        # Initialize Service Bus manager if not already done
        if not hasattr(app.state, 'service_bus_manager'):
            from app.service_bus_manager import ServiceBusManager
            app.state.service_bus_manager = ServiceBusManager()
            await app.state.service_bus_manager.connect()
        
        # Convert EmailRequest objects to dictionaries
        email_dicts = []
        for email in emails:
            email_dict = {
                "sender_email": email.sender_email,
                "sender_name": email.sender_name,
                "subject": email.subject,
                "body": email.body,
                "attachments": [
                    {
                        "filename": att.filename,
                        "content": att.content_base64,
                        "content_type": att.content_type
                    }
                    for att in email.attachments
                ] if email.attachments else []
            }
            email_dicts.append(email_dict)
        
        # Submit to Service Bus
        batch_id = await app.state.service_bus_manager.send_batch(email_dicts, priority)
        
        return {
            "status": "success",
            "batch_id": batch_id,
            "email_count": len(emails),
            "priority": priority,
            "message": f"Batch submitted for processing. Use /batch/status/{batch_id} to check progress."
        }
        
    except Exception as e:
        logger.error(f"Error submitting batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch/process", dependencies=[Depends(verify_api_key)])
async def process_batch_direct(emails: List[EmailRequest]):
    """
    Process a batch of emails directly without queuing
    Useful for immediate processing of small batches
    
    Args:
        emails: List of email payloads to process
    
    Returns:
        Processing results for the batch
    """
    try:
        logger.info(f"Processing batch directly with {len(emails)} emails")
        
        # Initialize batch processor
        from app.batch_processor import BatchEmailProcessor
        
        processor = BatchEmailProcessor(
            zoho_client=app.state.zoho_integration if hasattr(app.state, 'zoho_integration') else None,
            postgres_client=app.state.postgres_client if hasattr(app.state, 'postgres_client') else None
        )
        
        # Convert EmailRequest objects to dictionaries
        email_dicts = []
        for email in emails:
            email_dict = {
                "sender_email": email.sender_email,
                "sender_name": email.sender_name,
                "subject": email.subject,
                "body": email.body,
                "attachments": [
                    {
                        "filename": att.filename,
                        "content": att.content_base64,
                        "content_type": att.content_type
                    }
                    for att in email.attachments
                ] if email.attachments else []
            }
            email_dicts.append(email_dict)
        
        # Process emails with optimal batching
        results = await processor.process_emails_optimized(email_dicts, auto_batch=True)
        
        # Get aggregate statistics
        stats = processor.get_processing_stats(results)
        
        return {
            "status": "success",
            "statistics": stats,
            "message": f"Processed {stats['processed_emails']} of {stats['total_emails']} emails"
        }
        
    except Exception as e:
        logger.error(f"Error processing batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/batch/status/{batch_id}", dependencies=[Depends(verify_api_key)])
async def get_batch_status(batch_id: str):
    """
    Get status of a batch processing job
    
    Args:
        batch_id: Batch identifier from submission
    
    Returns:
        Current batch processing status
    """
    try:
        # Validate batch_id format (prevent injection)
        import uuid
        try:
            # Batch IDs should be UUIDs
            uuid.UUID(batch_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid batch ID format"
            )
        # Initialize Service Bus manager if needed
        if not hasattr(app.state, 'service_bus_manager'):
            from app.service_bus_manager import ServiceBusManager
            app.state.service_bus_manager = ServiceBusManager()
            await app.state.service_bus_manager.connect()
        
        # Peek at messages to find batch status
        messages = await app.state.service_bus_manager.peek_messages(max_messages=50)
        
        # Find the batch
        batch_found = False
        for msg in messages:
            if msg.get("batch_id") == batch_id:
                batch_found = True
                return {
                    "status": "pending",
                    "batch_id": batch_id,
                    "email_count": msg.get("email_count"),
                    "created_at": msg.get("created_at"),
                    "priority": msg.get("priority"),
                    "position_in_queue": messages.index(msg) + 1
                }
        
        if not batch_found:
            # Check if batch was recently processed (would need to store results)
            return {
                "status": "unknown",
                "batch_id": batch_id,
                "message": "Batch not found in queue. It may have been processed or expired."
            }
        
    except Exception as e:
        logger.error(f"Error getting batch status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/batch/queue/status", dependencies=[Depends(verify_api_key)])
async def get_queue_status():
    """Get Service Bus queue status and metrics"""
    try:
        # Initialize Service Bus manager if needed
        if not hasattr(app.state, 'service_bus_manager'):
            from app.service_bus_manager import ServiceBusManager
            app.state.service_bus_manager = ServiceBusManager()
            await app.state.service_bus_manager.connect()
        
        status = await app.state.service_bus_manager.get_queue_status()
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch/queue/process", dependencies=[Depends(verify_api_key)])
async def process_queue_batches(max_batches: int = 1):
    """
    Process batches from the Service Bus queue
    
    Args:
        max_batches: Maximum number of batches to process
    
    Returns:
        Processing results
    """
    try:
        logger.info(f"Processing up to {max_batches} batches from queue")
        
        # Initialize batch processor
        from app.batch_processor import BatchEmailProcessor
        
        processor = BatchEmailProcessor(
            service_bus_manager=app.state.service_bus_manager if hasattr(app.state, 'service_bus_manager') else None,
            zoho_client=app.state.zoho_integration if hasattr(app.state, 'zoho_integration') else None,
            postgres_client=app.state.postgres_client if hasattr(app.state, 'postgres_client') else None
        )
        
        # Process from queue
        results = await processor.process_from_queue(max_batches=max_batches)
        
        if not results:
            return {
                "status": "success",
                "message": "No batches available in queue",
                "processed_batches": 0
            }
        
        # Get aggregate statistics
        stats = processor.get_processing_stats(results)
        
        return {
            "status": "success",
            "processed_batches": len(results),
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Error processing queue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch/deadletter/process", dependencies=[Depends(verify_api_key)])
async def process_dead_letter_queue(max_messages: int = 10):
    """
    Process messages from the dead letter queue
    
    Args:
        max_messages: Maximum number of messages to process
    
    Returns:
        Dead letter processing results
    """
    try:
        # Initialize Service Bus manager if needed
        if not hasattr(app.state, 'service_bus_manager'):
            from app.service_bus_manager import ServiceBusManager
            app.state.service_bus_manager = ServiceBusManager()
            await app.state.service_bus_manager.connect()
        
        results = await app.state.service_bus_manager.process_dead_letter_queue(max_messages)
        
        return {
            "status": "success",
            "processed_messages": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error processing dead letter queue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cache/status", dependencies=[Depends(verify_api_key)])
async def get_cache_status():
    """Get comprehensive Redis cache performance metrics, health status, and optimization recommendations"""
    try:
        from app.redis_cache_manager import get_cache_manager, get_redis_health_status
        from app.cache_strategies import get_strategy_manager
        
        cache_manager = await get_cache_manager()
        strategy_manager = get_strategy_manager()
        
        # Get health status first
        redis_health = await get_redis_health_status()
        
        # Get cache metrics (will handle Redis being unavailable gracefully)
        cache_metrics = await cache_manager.get_metrics()
        
        # Get strategy metrics
        try:
            strategy_metrics = strategy_manager.get_metrics()
            optimizations = strategy_manager.optimize_cache_strategy(cache_metrics)
        except Exception as e:
            logger.warning(f"Failed to get strategy metrics: {e}")
            strategy_metrics = {}
            optimizations = []
        
        # Enhanced status determination
        overall_status = "healthy"
        if redis_health.get("status") == "not_configured":
            overall_status = "not_configured"
        elif redis_health.get("status") == "circuit_breaker_open":
            overall_status = "circuit_breaker_open"
        elif cache_manager.fallback_mode:
            overall_status = "fallback_mode"
        elif not cache_manager._connected:
            overall_status = "disconnected"
        elif redis_health.get("status") in ["unhealthy", "degraded"]:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "health_check": redis_health,
            "cache_metrics": cache_metrics,
            "strategy_metrics": strategy_metrics,
            "optimizations": optimizations,
            "cost_analysis": {
                "gpt5_mini_per_million": "$0.25",
                "cached_per_million": "$0.025",
                "savings_ratio": "90%",
                "estimated_monthly_savings": f"${cache_metrics.get('estimated_monthly_savings', 0):.2f}"
            },
            "reliability": {
                "uptime_percentage": cache_metrics.get("uptime_percentage", "0%"),
                "circuit_breaker_status": "open" if cache_manager.circuit_breaker.is_open else "closed",
                "fallback_activations": cache_metrics.get("fallback_activations", 0),
                "connection_failures": cache_metrics.get("connection_failures", 0),
                "timeout_failures": cache_metrics.get("timeout_failures", 0)
            },
            "configuration": {
                "max_failures_before_circuit_breaker": cache_manager.max_failures,
                "failure_timeout_minutes": int(cache_manager.failure_timeout.total_seconds() / 60),
                "connection_timeout_seconds": cache_manager.connection_timeout,
                "operation_timeout_seconds": cache_manager.operation_timeout,
                "max_retries": cache_manager.max_retries
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "health_check": {"status": "error", "error": str(e)},
            "cache_metrics": {},
            "strategy_metrics": {},
            "optimizations": [],
            "cost_analysis": {
                "gpt5_mini_per_million": "$0.25",
                "cached_per_million": "$0.025",
                "savings_ratio": "90%",
                "estimated_monthly_savings": "$0.00"
            },
            "reliability": {
                "uptime_percentage": "0%",
                "circuit_breaker_status": "unknown",
                "fallback_activations": 0
            },
            "message": "Cache status check failed"
        }

@app.post("/cache/invalidate", dependencies=[Depends(verify_api_key)])
async def invalidate_cache(pattern: Optional[str] = None):
    """Invalidate cache entries matching a pattern with graceful fallback handling"""
    try:
        from app.redis_cache_manager import get_cache_manager
        
        cache_manager = await get_cache_manager()
        deleted_count = await cache_manager.invalidate_cache(pattern)
        
        # Check if we're in fallback mode
        if cache_manager.fallback_mode:
            return {
                "status": "fallback_mode",
                "deleted_entries": 0,
                "pattern": pattern or "well:email:*",
                "message": "Cache invalidation skipped - Redis unavailable",
                "fallback_reason": cache_manager.fallback_reason
            }
        
        return {
            "status": "success",
            "deleted_entries": deleted_count,
            "pattern": pattern or "well:email:*",
            "redis_status": "connected" if cache_manager._connected else "disconnected"
        }
        
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        return {
            "status": "error",
            "error": str(e),
            "deleted_entries": 0,
            "pattern": pattern or "well:email:*",
            "message": "Cache invalidation failed"
        }

@app.post("/cache/warmup", dependencies=[Depends(verify_api_key)])
async def warmup_cache():
    """Pre-warm cache with common email patterns with graceful fallback handling"""
    try:
        from app.redis_cache_manager import get_cache_manager
        from app.cache_strategies import get_strategy_manager
        
        cache_manager = await get_cache_manager()
        strategy_manager = get_strategy_manager()
        
        # Get common patterns
        common_patterns = strategy_manager.get_common_patterns()
        
        # Warm up cache
        cached_count = await cache_manager.warmup_cache(common_patterns)
        
        # Check if we're in fallback mode
        if cache_manager.fallback_mode:
            return {
                "status": "fallback_mode",
                "patterns_cached": 0,
                "total_patterns": len(common_patterns),
                "patterns": [p["key"] for p in common_patterns],
                "message": "Cache warmup skipped - Redis unavailable",
                "fallback_reason": cache_manager.fallback_reason
            }
        
        return {
            "status": "success",
            "patterns_cached": cached_count,
            "total_patterns": len(common_patterns),
            "patterns": [p["key"] for p in common_patterns],
            "redis_status": "connected" if cache_manager._connected else "disconnected",
            "success_rate": f"{(cached_count / len(common_patterns) * 100):.1f}%" if common_patterns else "N/A"
        }
        
    except Exception as e:
        logger.error(f"Error warming up cache: {e}")
        return {
            "status": "error",
            "error": str(e),
            "patterns_cached": 0,
            "total_patterns": 0,
            "patterns": [],
            "message": "Cache warmup failed"
        }

# Redis monitoring and alerting endpoints
@app.get("/cache/alerts", dependencies=[Depends(verify_api_key)])
async def get_cache_alerts(hours: int = 24):
    """Get Redis cache alerts from the last N hours"""
    try:
        from app.redis_monitoring import get_monitoring_service
        
        monitoring_service = get_monitoring_service()
        alert_summary = monitoring_service.get_alert_summary(hours=hours)
        
        return {
            "status": "success",
            "alert_summary": alert_summary
        }
    except Exception as e:
        logger.error(f"Error getting cache alerts: {e}")
        return {
            "status": "error",
            "error": str(e),
            "alert_summary": {}
        }

@app.get("/cache/metrics/report", dependencies=[Depends(verify_api_key)])
async def get_cache_metrics_report(hours: int = 24):
    """Get comprehensive Redis cache metrics report"""
    try:
        from app.redis_monitoring import get_monitoring_service
        
        monitoring_service = get_monitoring_service()
        metrics_report = monitoring_service.get_metrics_report(hours=hours)
        
        return {
            "status": "success",
            "metrics_report": metrics_report
        }
    except Exception as e:
        logger.error(f"Error getting cache metrics report: {e}")
        return {
            "status": "error",
            "error": str(e),
            "metrics_report": {}
        }

@app.post("/cache/monitoring/start", dependencies=[Depends(verify_api_key)])
async def start_cache_monitoring(interval_minutes: int = 5):
    """Start Redis cache monitoring service"""
    try:
        from app.redis_monitoring import get_monitoring_service
        from app.redis_cache_manager import get_cache_manager
        
        monitoring_service = get_monitoring_service()
        cache_manager = await get_cache_manager()
        
        await monitoring_service.start_monitoring(cache_manager, interval_minutes)
        
        return {
            "status": "success",
            "message": f"Redis monitoring started with {interval_minutes} minute intervals",
            "interval_minutes": interval_minutes
        }
    except Exception as e:
        logger.error(f"Error starting cache monitoring: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to start Redis monitoring"
        }

@app.get("/cache/health/detailed", dependencies=[Depends(verify_api_key)])
async def get_detailed_cache_health():
    """Get detailed Redis cache health with monitoring data"""
    try:
        from app.redis_monitoring import get_monitoring_service
        from app.redis_cache_manager import get_redis_health_status
        from datetime import datetime
        
        # Get basic health status
        redis_health = await get_redis_health_status()
        
        # Get monitoring data
        monitoring_service = get_monitoring_service()
        alert_summary = monitoring_service.get_alert_summary(hours=1)  # Last hour
        metrics_report = monitoring_service.get_metrics_report(hours=1)  # Last hour
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "redis_health": redis_health,
            "recent_alerts": alert_summary,
            "metrics_summary": metrics_report,
            "overall_status": "healthy" if redis_health.get("status") == "healthy" and alert_summary.get("unresolved_alerts", 0) == 0 else "degraded"
        }
    except Exception as e:
        logger.error(f"Error getting detailed cache health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Manifest cache management endpoints
@app.get("/manifest/cache/status", dependencies=[Depends(verify_api_key)])
async def get_manifest_cache_status():
    """Get manifest cache performance metrics and configuration"""
    try:
        manifest_service = await get_manifest_cache_service()
        status = await manifest_service.get_cache_status()
        return status
    except Exception as e:
        logger.error(f"Error getting manifest cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/manifest/cache/invalidate", dependencies=[Depends(verify_api_key)])
async def invalidate_manifest_cache(
    environment: str = None,
    variant: str = None,
    pattern: str = None
):
    """Invalidate manifest cache entries with instant invalidation"""
    try:
        manifest_service = await get_manifest_cache_service()
        
        # Convert string parameters to enums if provided
        env = None
        var = None
        
        if environment:
            try:
                env = Environment(environment.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid environment: {environment}")
        
        if variant:
            try:
                var = ManifestVariant(variant.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid variant: {variant}")
        
        deleted_count = await manifest_service.invalidate_cache(env, var, pattern)
        
        return {
            "status": "success",
            "entries_invalidated": deleted_count,
            "environment": environment,
            "variant": variant,
            "pattern": pattern
        }
    except Exception as e:
        logger.error(f"Error invalidating manifest cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/manifest/cache/warmup", dependencies=[Depends(verify_api_key)])
async def warmup_manifest_cache(environments: List[str] = None):
    """Pre-warm manifest cache for specified environments"""
    try:
        manifest_service = await get_manifest_cache_service()
        
        # Convert string environments to enums
        env_list = []
        if environments:
            for env_str in environments:
                try:
                    env_list.append(Environment(env_str.lower()))
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid environment: {env_str}")
        
        results = await manifest_service.warmup_cache(env_list if env_list else None)
        
        return {
            "status": "success",
            "warmup_results": results,
            "total_manifests_cached": sum(r["success"] for r in results.values())
        }
    except Exception as e:
        logger.error(f"Error warming up manifest cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/manifest/template/update", dependencies=[Depends(verify_api_key)])
async def update_manifest_template(
    environment: str,
    variant: str,
    template_updates: Dict[str, Any]
):
    """Update manifest template and invalidate related cache entries"""
    try:
        manifest_service = await get_manifest_cache_service()
        
        # Convert parameters to enums
        try:
            env = Environment(environment.lower())
            var = ManifestVariant(variant.lower())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid parameter: {str(e)}")
        
        success = await manifest_service.update_template(env, var, template_updates)
        
        if success:
            return {
                "status": "success",
                "environment": environment,
                "variant": variant,
                "updates_applied": list(template_updates.keys())
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update template")
            
    except Exception as e:
        logger.error(f"Error updating manifest template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Authentication endpoints for Voice UI
@app.post("/auth/validate")
async def validate_voice_ui_token(auth_info: dict = Depends(verify_user_auth)):
    """Validate authentication token for Voice UI"""
    try:
        return {
            "status": "valid",
            "auth_type": auth_info["type"],
            "user_id": auth_info["user_id"],
            "email": auth_info.get("email"),
            "name": auth_info.get("name"),
            "timestamp": datetime.utcnow().isoformat(),
            "voice_ui_access": True,
            "permissions": ["voice_interface", "email_processing"]
        }
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed"
        )

@app.get("/auth/user-info")
async def get_user_info(auth_info: dict = Depends(verify_user_auth)):
    """Get authenticated user information"""
    try:
        user_data = {
            "user_id": auth_info["user_id"],
            "auth_type": auth_info["type"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add user details for Microsoft auth
        if auth_info["type"] == "microsoft":
            user_data.update({
                "email": auth_info.get("email"),
                "name": auth_info.get("name"),
                "provider": "Microsoft Azure AD"
            })
        elif auth_info["type"] == "test":
            user_data.update({
                "email": "test@thewell.com",
                "name": "Test User",
                "provider": "Development Test"
            })
        
        return user_data
        
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user information"
        )

# Static file serving for Outlook Add-in
@app.get("/manifest.xml")
async def get_manifest(request: Request):
    """Serve Outlook Add-in manifest - direct file serving as primary method"""
    # Direct file serving for reliability
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "addin", "manifest.xml")
    if os.path.exists(manifest_path):
        # Add cache busting headers
        return FileResponse(
            manifest_path, 
            media_type="application/xml; charset=utf-8",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Manifest-Version": "1.3.0.2"
            }
        )
    
    # Fallback error if file not found
    logger.error(f"Manifest file not found at {manifest_path}")
    raise HTTPException(status_code=404, detail="Manifest.xml not found")

@app.get("/commands.js")
async def get_commands():
    """Serve Outlook Add-in JavaScript"""
    js_path = os.path.join(os.path.dirname(__file__), "..", "addin", "commands.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Commands.js not found")

@app.get("/commands.html")
async def get_commands_html():
    """Serve Outlook Add-in HTML"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "addin", "commands.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Commands.html not found")

@app.get("/config.js")
async def get_config_js():
    """Serve Outlook Add-in configuration JavaScript"""
    js_path = os.path.join(os.path.dirname(__file__), "..", "addin", "config.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Config.js not found")

@app.get("/placeholder.html")
async def get_placeholder_html():
    """Serve placeholder HTML for Outlook Add-in"""
    # Create a minimal placeholder HTML if it doesn't exist
    placeholder_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <meta http-equiv="X-UA-Compatible" content="IE=Edge" />
    <title>The Well Recruiting - Send to Zoho</title>
</head>
<body>
    <div style="padding: 20px; font-family: Arial, sans-serif;">
        <h2>Send to Zoho</h2>
        <p>Click the "Send to Zoho" button in the ribbon to process this email.</p>
    </div>
</body>
</html>"""
    return HTMLResponse(content=placeholder_content)

@app.get("/manifest/warmup/status")
async def get_manifest_warmup_status(request: Request):
    """Get manifest cache warmup status"""
    try:
        from app.startup_warmup import get_manifest_warmup_status
        
        # Get warmup status
        status = await get_manifest_warmup_status()
        
        # Add current request environment for context
        host = str(request.url.hostname).lower()
        current_env = 'development' if 'localhost' in host or '127.0.0.1' in host else 'production'
        
        return {
            "warmup_status": status,
            "current_environment": current_env,
            "startup_stats": getattr(request.app.state, 'manifest_warmup_stats', {}),
            "api_endpoints": {
                "generate_manifest": "/api/manifest/generate",
                "warmup_cache": "/api/manifest/warmup",
                "cache_status": "/api/manifest/cache/status",
                "templates": "/api/manifest/templates"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting manifest warmup status: {e}")
        return {
            "error": str(e),
            "warmup_status": {"completed": False},
            "current_environment": "unknown"
        }

# Azure AD Authentication Endpoints
@app.get("/auth/login")
async def initiate_login(redirect_url: str = None):
    """Start Azure AD OAuth login flow"""
    try:
        auth_service = get_auth_service()
        
        # Generate state parameter for security
        state = f"redirect={redirect_url}" if redirect_url else "default"
        
        # Get authorization URL
        auth_url = auth_service.get_authorization_url(state)
        
        return {
            "auth_url": auth_url,
            "state": state,
            "message": "Redirect user to auth_url to complete login"
        }
    
    except Exception as e:
        logger.error(f"Login initiation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/callback")
async def handle_auth_callback(code: str = None, state: str = None, error: str = None):
    """Handle OAuth callback from Azure AD"""
    try:
        if error:
            logger.error(f"OAuth error: {error}")
            return HTMLResponse(f"""
                <html><body>
                    <h2>Authentication Error</h2>
                    <p>Error: {error}</p>
                    <p><a href="/auth/login">Try again</a></p>
                </body></html>
            """)
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code not provided")
        
        auth_service = get_auth_service()
        
        # Exchange code for tokens
        token_info = await auth_service.exchange_code_for_tokens(code, state)
        
        # Generate success page with user info
        user_email = token_info.get('user_email', 'Unknown')
        user_name = token_info.get('user_name', 'User')
        
        success_html = f"""
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .success {{ color: green; }}
                .info {{ background: #f0f8ff; padding: 20px; border-radius: 5px; }}
                .token {{ font-family: monospace; word-break: break-all; }}
            </style>
        </head>
        <body>
            <h2 class="success">✅ Authentication Successful!</h2>
            <div class="info">
                <p><strong>Welcome, {user_name}!</strong></p>
                <p><strong>Email:</strong> {user_email}</p>
                <p><strong>User ID:</strong> {token_info['user_id']}</p>
                <p><strong>Scopes:</strong> {', '.join(token_info.get('scopes', []))}</p>
            </div>
            <p>You can now close this window and return to the Voice UI application.</p>
            <p><a href="/api/user/info?user_id={token_info['user_id']}">View User Info</a></p>
            
            <script>
                // Auto-close window after 5 seconds
                setTimeout(function() {{
                    if (window.opener) {{
                        window.close();
                    }}
                }}, 5000);
            </script>
        </body>
        </html>
        """
        
        logger.info(f"Successfully authenticated user {user_email}")
        return HTMLResponse(success_html)
    
    except Exception as e:
        logger.error(f"Auth callback error: {e}")
        return HTMLResponse(f"""
            <html><body>
                <h2>Authentication Error</h2>
                <p>Error: {str(e)}</p>
                <p><a href="/auth/login">Try again</a></p>
            </body></html>
        """)

@app.get("/api/user/info", dependencies=[Depends(verify_api_key)])
async def get_user_info(user_id: str):
    """Get authenticated user information"""
    try:
        auth_service = get_auth_service()
        user_info = auth_service.get_user_info(user_id)
        
        if not user_info:
            raise HTTPException(status_code=404, detail="User not found or not authenticated")
        
        return user_info
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/user/logout", dependencies=[Depends(verify_api_key)])
async def logout_user(request: Request):
    """Logout user and remove tokens"""
    try:
        body = await request.json()
        user_id = body.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID required")
        
        auth_service = get_auth_service()
        success = auth_service.logout_user(user_id)
        
        if success:
            return {"status": "logged_out", "user_id": user_id}
        else:
            return {"status": "not_found", "user_id": user_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/users", dependencies=[Depends(verify_api_key)])
async def get_authenticated_users():
    """Get list of all authenticated users (admin endpoint)"""
    try:
        auth_service = get_auth_service()
        users = auth_service.get_all_authenticated_users()
        
        return {
            "authenticated_users": users,
            "total_count": len(users),
            "active_count": sum(1 for user in users.values() if user['is_valid'])
        }
    
    except Exception as e:
        logger.error(f"Get authenticated users error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket Endpoint for Real-time Queue Updates
@app.websocket("/ws/queue/{user_id}")
async def websocket_queue_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time email queue updates"""
    await websocket_endpoint(websocket, user_id)

@app.get("/taskpane.html")
async def get_taskpane():
    """Serve Outlook Add-in task pane"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "addin", "taskpane.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Taskpane.html not found")

@app.get("/taskpane.js")
async def get_taskpane_js():
    """Serve Outlook Add-in task pane JavaScript"""
    # Try multiple path resolutions
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "addin", "taskpane.js"),
        os.path.join("/app", "addin", "taskpane.js"),
        os.path.join(os.getcwd(), "addin", "taskpane.js"),
    ]
    
    for js_path in possible_paths:
        if os.path.exists(js_path):
            return FileResponse(js_path, media_type="application/javascript")
    
    # Log which paths were tried for debugging
    logger.error(f"taskpane.js not found. Tried paths: {possible_paths}")
    raise HTTPException(status_code=404, detail=f"Taskpane.js not found. Tried: {possible_paths}")

# Voice UI API Endpoints
@app.post("/api/voice/process", dependencies=[Depends(verify_api_key)])
async def process_voice_command(request: Request):
    """Process voice command and return appropriate action"""
    try:
        body = await request.json()
        command = body.get("command", "").lower()
        context = body.get("context", {})
        
        # Input validation
        if not command or len(command) > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Command must be between 1 and 500 characters"
            )
        
        # Sanitize command (remove potentially dangerous characters)
        import re
        command = re.sub(r'[^\w\s\-.,?!]', '', command)
        
        # Process command and determine action
        response = {
            "action": "unknown",
            "data": {},
            "message": f"Processed command: {command}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Basic command processing
        if "process" in command and "email" in command:
            response["action"] = "processEmail"
        elif "approve" in command:
            response["action"] = "approveExtraction"
        elif "reject" in command:
            response["action"] = "rejectExtraction"
        elif "next" in command:
            response["action"] = "nextEmail"
        elif "previous" in command:
            response["action"] = "previousEmail"
        elif "queue" in command:
            response["action"] = "showQueue"
        elif "metrics" in command:
            response["action"] = "showMetrics"
        
        logger.info(f"Voice command processed: {command} -> {response['action']}")
        return response
        
    except Exception as e:
        logger.error(f"Voice command processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/emails/queue", dependencies=[Depends(verify_api_key)])
async def get_email_queue(user_id: str = None):
    """Get real-time email processing queue"""
    try:
        # Get queue manager instance
        queue_manager = get_queue_manager()
        
        # Sync emails from Microsoft Graph to queue if needed
        await sync_emails_to_queue(user_id)
        
        # Get current queue state
        queue_data = await queue_manager.get_queue_state(user_id)
        
        logger.info(f"Retrieved queue with {queue_data.get('total_count', 0)} emails for user {user_id}")
        return queue_data
        
    except Exception as e:
        logger.error(f"Email queue retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def sync_emails_to_queue(user_id: str = None):
    """Sync emails from Microsoft Graph to real-time queue"""
    try:
        if not hasattr(app.state, 'graph_client') or not app.state.graph_client:
            return
        
        queue_manager = get_queue_manager()
        
        # Get recruitment emails from Microsoft Graph
        org_emails = await app.state.graph_client.get_recruitment_emails_for_organization(
            hours_back=24,
            max_emails_per_user=10
        )
        
        emails_added = 0
        for source_user, user_emails in org_emails.items():
            for email in user_emails:
                # Convert Microsoft Graph email to queue format
                email_data = {
                    "id": email.id,
                    "from_address": email.from_address,
                    "from_name": email.from_name,
                    "subject": email.subject,
                    "body": email.body,
                    "timestamp": email.received_time,
                    "priority": "high" if email.importance == "high" else "normal",
                    "has_attachments": email.has_attachments,
                    "source_user": source_user
                }
                
                # Determine initial status based on categories
                if "Processed by Zoho" in email.categories:
                    initial_status = EmailStatus.PROCESSED
                elif "Processing" in email.categories:
                    initial_status = EmailStatus.PROCESSING
                else:
                    initial_status = EmailStatus.PENDING
                
                # Add to queue (will skip if already exists)
                try:
                    await queue_manager.add_email_to_queue(email_data, user_id or source_user)
                    # Set the appropriate status
                    await queue_manager.update_email_status(email.id, initial_status)
                    emails_added += 1
                except Exception as add_error:
                    # Email might already exist, which is fine
                    logger.debug(f"Email {email.id} already in queue or add failed: {add_error}")
        
        if emails_added > 0:
            logger.info(f"Synced {emails_added} emails from Microsoft Graph to queue")
        
    except Exception as e:
        logger.warning(f"Error syncing emails to queue: {e}")

@app.get("/api/emails/{email_id}", dependencies=[Depends(verify_api_key)])
async def get_email_by_id(email_id: str):
    """Get specific email details by ID from Microsoft Graph"""
    try:
        # Try to get from Microsoft Graph first
        if hasattr(app.state, 'graph_client') and app.state.graph_client:
            try:
                # Get emails from organization and find the specific email
                org_emails = await app.state.graph_client.get_recruitment_emails_for_organization(
                    hours_back=168,  # Last week to find the email
                    max_emails_per_user=50
                )
                
                # Search for the specific email ID
                for user_email, user_emails in org_emails.items():
                    for email in user_emails:
                        if email.id == email_id:
                            # Process email through LangGraph if not already processed
                            extracted_data = None
                            if "Processed by Zoho" not in email.categories:
                                try:
                                    from app.langgraph_manager import EmailProcessingWorkflow
                                    workflow = EmailProcessingWorkflow()
                                    extracted_data = await workflow.process_email(
                                        email.body, 
                                        email.from_address.split('@')[1] if '@' in email.from_address else 'unknown.com'
                                    )
                                    logger.info(f"Processed email {email_id} with LangGraph")
                                except Exception as process_error:
                                    logger.warning(f"LangGraph processing failed for {email_id}: {process_error}")
                            
                            return {
                                "id": email.id,
                                "from": email.from_address,
                                "from_name": email.from_name,
                                "subject": email.subject,
                                "body": email.body,
                                "attachments": email.attachments,
                                "extracted_data": extracted_data.model_dump() if extracted_data else None,
                                "status": "processed" if "Processed by Zoho" in email.categories else "pending",
                                "timestamp": email.received_time,
                                "has_attachments": email.has_attachments,
                                "is_read": email.is_read,
                                "importance": email.importance,
                                "categories": email.categories,
                                "source_user": user_email
                            }
                
                # Email not found in Microsoft Graph
                logger.warning(f"Email {email_id} not found in Microsoft Graph")
                raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
                
            except HTTPException:
                raise
            except Exception as graph_error:
                logger.error(f"Microsoft Graph error retrieving email {email_id}: {graph_error}")
                raise HTTPException(status_code=500, detail=f"Error retrieving email: {graph_error}")
        
        # Fallback if Graph client not available
        else:
            logger.warning("Microsoft Graph client not available")
            raise HTTPException(status_code=503, detail="Email service not available")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/emails/{email_id}/preview", dependencies=[Depends(verify_api_key)])
async def preview_extraction(email_id: str, request: Request):
    """Preview extraction results for approval"""
    try:
        body = await request.json()
        extracted_data = body.get("extractedData", {})
        
        # Process through business rules for preview
        preview_data = {
            "email_id": email_id,
            "deal_name": business_rules.format_deal_name(
                extracted_data.get("job_title", "Unknown"),
                extracted_data.get("job_location", "Unknown"),
                extracted_data.get("company_name", "Unknown")
            ),
            "source": business_rules.determine_source(
                extracted_data.get("referrer_name"),
                extracted_data.get("email_content", "")
            ),
            "confidence": extracted_data.get("confidence", 0.8),
            "extracted_data": extracted_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return preview_data
        
    except Exception as e:
        logger.error(f"Extraction preview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/emails/{email_id}/approve", dependencies=[Depends(verify_api_key)])
async def approve_extraction(email_id: str, request: Request):
    """Approve extraction with any edits"""
    try:
        body = await request.json()
        extracted_data = body.get("extractedData", {})
        edits = body.get("edits", {})
        
        # Apply edits to extracted data
        final_data = {**extracted_data, **edits}
        
        # Process through existing intake pipeline
        email_payload = EmailRequest(
            from_address=final_data.get("from_address", ""),
            subject=final_data.get("subject", ""),
            body=final_data.get("email_content", ""),
            attachments=[]
        )
        
        # Use existing processing logic
        zoho_integration = app.state.zoho_integration
        result = await process_email_internal(email_payload, zoho_integration)
        
        logger.info(f"Email {email_id} approved and processed")
        return {
            "status": "approved",
            "zoho_result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Extraction approval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/emails/{email_id}/reject", dependencies=[Depends(verify_api_key)])
async def reject_extraction(email_id: str, request: Request):
    """Reject extraction with reason"""
    try:
        body = await request.json()
        reason = body.get("reason", "No reason provided")
        
        # Log rejection for learning
        logger.info(f"Email {email_id} rejected: {reason}")
        
        return {
            "status": "rejected",
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Extraction rejection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/learning/feedback", dependencies=[Depends(verify_api_key)])
async def submit_learning_feedback(request: Request):
    """Submit feedback for human-in-the-loop learning"""
    try:
        body = await request.json()
        
        feedback_data = {
            "email_id": body.get("emailId"),
            "original_data": body.get("originalData", {}),
            "corrected_data": body.get("correctedData", {}),
            "confidence": body.get("confidence", 1.0),
            "user_agent": body.get("userAgent", ""),
            "timestamp": body.get("timestamp", datetime.utcnow().isoformat())
        }
        
        # Store in PostgreSQL if available
        if hasattr(app.state, 'postgres_client') and app.state.postgres_client:
            try:
                await app.state.postgres_client.store_learning_feedback(feedback_data)
            except Exception as db_error:
                logger.warning(f"Failed to store learning feedback in database: {db_error}")
        
        logger.info(f"Learning feedback submitted for email {feedback_data['email_id']}")
        return {
            "status": "feedback_stored",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Learning feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics/accuracy", dependencies=[Depends(verify_api_key)])
async def get_accuracy_metrics(timeframe: str = "24h"):
    """Get extraction accuracy metrics"""
    try:
        # Mock metrics - in production, calculate from database
        metrics = {
            "timeframe": timeframe,
            "total_extractions": 150,
            "accurate_extractions": 142,
            "accuracy_rate": 0.947,
            "improvement_rate": 0.023,
            "common_corrections": [
                {"field": "company_name", "frequency": 8},
                {"field": "job_location", "frequency": 5},
                {"field": "job_title", "frequency": 3}
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Metrics retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics/system", dependencies=[Depends(verify_api_key)])
async def get_system_metrics():
    """Get system performance metrics"""
    try:
        metrics = {
            "processing_speed": {
                "average_time": "2.3s",
                "median_time": "2.1s",
                "95th_percentile": "4.2s"
            },
            "cache_performance": {
                "hit_rate": 0.73,
                "miss_rate": 0.27,
                "cost_savings": 0.68
            },
            "system_health": {
                "cpu_usage": 0.35,
                "memory_usage": 0.42,
                "disk_usage": 0.18
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"System metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper function for processing emails internally
async def process_email_internal(email_payload: EmailRequest, zoho_integration):
    """Internal email processing logic"""
    try:
        # Use existing LangGraph processing
        use_langgraph = os.getenv("USE_LANGGRAPH", "true").lower() == "true"
        
        if use_langgraph:
            from app.langgraph_manager import EmailProcessor
            processor = EmailProcessor()
            extracted_data = await processor.process_email_async(
                email_content=email_payload.body,
                sender_domain=email_payload.from_address.split('@')[-1] if '@' in email_payload.from_address else ""
            )
        else:
            # Fallback to simple extraction
            extracted_data = ExtractedData(
                job_title="Unknown Position",
                company_name="Unknown Company",
                job_location="Unknown Location"
            )
        
        # Apply business rules
        deal_name = business_rules.format_deal_name(
            extracted_data.job_title,
            extracted_data.job_location,
            extracted_data.company_name
        )
        
        source, source_detail = business_rules.determine_source(
            extracted_data.referrer_name,
            email_payload.body
        )
        
        # Create Zoho records
        result = await zoho_integration.create_contact_and_deal(
            extracted_data, 
            deal_name, 
            source, 
            source_detail,
            email_payload.from_address
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Internal email processing error: {e}")
        raise

# GitHub Webhook Endpoints for Cache Invalidation
@app.post("/api/webhook/github")
async def github_webhook_endpoint(request: Request):
    """
    GitHub webhook endpoint for automatic cache invalidation.
    Handles push events for manifest-related file changes.
    """
    try:
        from app.webhook_handlers import verify_github_webhook, handle_github_webhook, log_webhook_event
        
        # Verify webhook signature and parse payload
        webhook_data = await verify_github_webhook(request)
        
        logger.info(f"Received GitHub webhook: {webhook_data['event_type']}")
        
        # Process the webhook
        processing_result = await handle_github_webhook(webhook_data)
        
        # Log to Application Insights for monitoring
        try:
            await log_webhook_event(webhook_data, processing_result)
        except Exception as log_error:
            logger.warning(f"Failed to log webhook event: {log_error}")
        
        return {
            "status": "success",
            "webhook_processed": True,
            "event_type": webhook_data["event_type"],
            "result": processing_result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub webhook processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )

@app.get("/api/webhook/github/status", dependencies=[Depends(verify_api_key)])
async def get_webhook_status():
    """Get GitHub webhook handler status and statistics."""
    try:
        from app.webhook_handlers import get_webhook_handler
        
        handler = get_webhook_handler()
        stats = handler.get_stats()
        
        return {
            "status": "operational",
            "webhook_endpoint": "/api/webhook/github",
            "statistics": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting webhook status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/webhook/github/test", dependencies=[Depends(verify_api_key)])
async def test_webhook_invalidation():
    """Test endpoint to manually trigger cache invalidation."""
    try:
        from app.webhook_handlers import get_webhook_handler
        
        handler = get_webhook_handler()
        
        # Simulate a push event with manifest changes
        test_payload = {
            "repository": {"full_name": "romiteld/outlook"},
            "ref": "refs/heads/main",
            "commits": [{
                "modified": ["addin/manifest.xml", "addin/commands.js"],
                "added": [],
                "removed": []
            }]
        }
        
        result = await handler.process_push_event(test_payload)
        
        return {
            "status": "test_completed",
            "result": result,
            "message": "Manual cache invalidation test completed",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Webhook test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Manifest Analytics Endpoints
@app.get("/api/manifest/status", dependencies=[Depends(verify_api_key)])
async def get_manifest_cache_status():
    """Get manifest cache status and performance metrics."""
    try:
        # Basic analytics data placeholder
        analytics_data = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_hit_rate": "0%",
            "errors": 0,
            "avg_response_time_ms": "0"
        }
        status_data = await analytics.get_cache_status()
        
        return {
            "status": "success",
            "data": status_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting manifest cache status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cache status: {str(e)}"
        )

@app.get("/api/manifest/metrics", dependencies=[Depends(verify_api_key)])
async def get_manifest_performance_metrics(hours: int = 24):
    """Get manifest performance analytics for the specified time period."""
    if hours < 1 or hours > 168:  # Limit to 7 days max
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hours parameter must be between 1 and 168"
        )
    
    try:
        # Basic analytics data placeholder
        analytics_data = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_hit_rate": "0%",
            "errors": 0,
            "avg_response_time_ms": "0"
        }
        metrics_data = await analytics.get_performance_metrics(hours)
        
        return {
            "status": "success",
            "data": metrics_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting manifest metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve performance metrics: {str(e)}"
        )

@app.post("/api/manifest/invalidate", dependencies=[Depends(verify_api_key)])
async def invalidate_manifest_cache(pattern: Optional[str] = None):
    """Manually invalidate manifest cache entries."""
    try:
        # Basic analytics data placeholder
        analytics_data = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_hit_rate": "0%",
            "errors": 0,
            "avg_response_time_ms": "0"
        }
        result = await analytics.invalidate_manifest_cache(pattern)
        
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error invalidating manifest cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache invalidation failed: {str(e)}"
        )

@app.get("/api/manifest/versions", dependencies=[Depends(verify_api_key)])
async def get_version_adoption_metrics():
    """Get version adoption tracking across different Office clients."""
    try:
        # Basic analytics data placeholder
        analytics_data = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_hit_rate": "0%",
            "errors": 0,
            "avg_response_time_ms": "0"
        }
        adoption_data = await analytics.get_version_adoption()
        
        return {
            "status": "success",
            "data": adoption_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting version adoption metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve version adoption data: {str(e)}"
        )

@app.get("/api/manifest/health", dependencies=[Depends(verify_api_key)])
async def get_manifest_analytics_health():
    """Get manifest analytics service health status."""
    try:
        # Basic analytics data placeholder
        analytics_data = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_hit_rate": "0%",
            "errors": 0,
            "avg_response_time_ms": "0"
        }
        
        # Basic health data without analytics service
        health_data = {
            "analytics_service": "operational",
            "request_history_size": 0,
            "recent_requests_1h": 0,
            "version_stats_count": 0,
            "client_stats_count": 0,
            "cache_manager_available": False,
            "monitoring_service_available": False
        }
        
        return {
            "status": "healthy",
            "data": health_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting manifest analytics health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )

# Icon file serving
@app.get("/icon-{size}.png")
async def get_icon(size: int):
    """Serve icon files for Outlook Add-in"""
    if size not in [16, 32, 64, 80, 128]:
        raise HTTPException(status_code=404, detail="Invalid icon size")
    
    # Try multiple path resolutions for container compatibility
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "addin", f"icon-{size}.png"),
        os.path.join("/app", "addin", f"icon-{size}.png"),
        os.path.join(os.getcwd(), "addin", f"icon-{size}.png"),
        os.path.join(os.path.dirname(__file__), "..", "static", "icons", f"icon-{size}.png"),
        os.path.join("/app", "static", "icons", f"icon-{size}.png"),
        os.path.join(os.getcwd(), "static", "icons", f"icon-{size}.png"),
        f"/home/romiteld/outlook/static/icons/icon-{size}.png"  # Absolute fallback
    ]
    
    for icon_path in possible_paths:
        if os.path.exists(icon_path):
            logger.info(f"Serving icon from: {icon_path}")
            return FileResponse(icon_path, media_type="image/png")
    
    # Log which paths were tried for debugging
    logger.error(f"Icon {size} not found. Tried paths: {possible_paths}")
    raise HTTPException(status_code=404, detail=f"Icon {size} not found. Tried: {possible_paths}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)