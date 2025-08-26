"""
Optimized main application module with improved startup performance and reliability
"""

import os
import logging
import hashlib
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from functools import lru_cache

from fastapi import FastAPI, Depends, HTTPException, Header, BackgroundTasks
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

# Lazy imports for heavy modules
def get_email_module():
    """Lazy load email module"""
    import email
    return email

def get_dotenv():
    """Lazy load dotenv and configure environment"""
    from dotenv import load_dotenv
    load_dotenv('.env.local')
    return True

# Initialize environment first
get_dotenv()

# Import local modules with lazy loading where possible
from app.models import EmailPayload, ExtractedData, ProcessingResult
from app.static_files import router as static_router
from app.error_handlers import register_error_handlers

# --- Configuration ---
API_KEY = os.getenv("API_KEY")
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# Configure logging with better format for Azure
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global connection pools and clients (lazy initialized)
_postgres_pool = None
_blob_client = None
_zoho_client = None
_crew_manager = None
_business_rules = None

# --- Optimized App Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Optimized lifecycle with parallel initialization and graceful shutdown"""
    logger.info("Starting Well Intake API (Optimized)...")
    
    # Start background initialization tasks
    init_tasks = []
    
    # Initialize PostgreSQL pool in background
    if os.getenv("POSTGRES_CONNECTION_STRING"):
        init_tasks.append(asyncio.create_task(init_postgres_pool()))
    
    # Wait for critical services only
    if init_tasks:
        results = await asyncio.gather(*init_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Initialization error in task {i}: {result}")
    
    logger.info("Well Intake API started successfully")
    
    yield
    
    # Graceful shutdown
    logger.info("Shutting down Well Intake API...")
    shutdown_tasks = []
    
    if _postgres_pool:
        shutdown_tasks.append(asyncio.create_task(close_postgres_pool()))
    
    if shutdown_tasks:
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
    
    logger.info("Well Intake API shutdown complete")

app = FastAPI(
    title="The Well Recruiting - Email Intake API (Optimized)",
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS for Outlook Add-in
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://outlook.office.com",
        "https://outlook.office365.com",
        "https://outlook.live.com",
        "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io",
        "http://localhost:8000",
        "http://localhost:3000",
        "*"  # Allow all origins in development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add trusted host middleware for production
if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io",
            "*.azurewebsites.net",
            "localhost"
        ]
    )

# Include static file routes for Outlook Add-in
app.include_router(static_router)

# Register error handlers
register_error_handlers(app)

# Set debug mode based on environment
app.debug = os.getenv("ENVIRONMENT", "development") == "development"

# --- Lazy Loading Service Factories ---

async def init_postgres_pool():
    """Initialize PostgreSQL connection pool asynchronously"""
    global _postgres_pool
    if not _postgres_pool:
        try:
            from app.integrations_optimized import PostgreSQLClient
            pg_conn = os.getenv("POSTGRES_CONNECTION_STRING")
            if pg_conn:
                _postgres_pool = PostgreSQLClient(pg_conn)
                await _postgres_pool.init_pool()
                await _postgres_pool.ensure_tables()
                logger.info("PostgreSQL pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}")
            _postgres_pool = None

async def close_postgres_pool():
    """Close PostgreSQL connection pool"""
    global _postgres_pool
    if _postgres_pool and _postgres_pool.pool:
        await _postgres_pool.pool.close()
        logger.info("PostgreSQL pool closed")

@lru_cache(maxsize=1)
def get_blob_client():
    """Lazy initialize Azure Blob Storage client with caching"""
    global _blob_client
    if not _blob_client:
        try:
            from app.integrations_optimized import AzureBlobStorageClient
            conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            if conn_str:
                _blob_client = AzureBlobStorageClient(conn_str)
                logger.info("Azure Blob Storage client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Blob Storage: {e}")
    return _blob_client

async def get_postgres_client():
    """Get PostgreSQL client (async to ensure pool is ready)"""
    global _postgres_pool
    if not _postgres_pool:
        await init_postgres_pool()
    return _postgres_pool

@lru_cache(maxsize=1)
def get_zoho_client():
    """Lazy initialize Zoho client with caching"""
    global _zoho_client
    if not _zoho_client:
        try:
            from app.integrations_optimized import ZohoClient
            _zoho_client = ZohoClient()
            logger.info("Zoho client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Zoho client: {e}")
    return _zoho_client

@lru_cache(maxsize=1)
def get_crew_manager():
    """Lazy initialize CrewAI manager with caching"""
    global _crew_manager
    if not _crew_manager:
        try:
            from app.crewai_manager import EmailProcessingCrew
            firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
            _crew_manager = EmailProcessingCrew(firecrawl_key)
            logger.info("CrewAI manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize CrewAI: {e}")
    return _crew_manager

@lru_cache(maxsize=1)
def get_business_rules():
    """Lazy initialize business rules engine with caching"""
    global _business_rules
    if not _business_rules:
        from app.business_rules import BusinessRulesEngine
        _business_rules = BusinessRulesEngine()
        logger.info("Business rules engine initialized")
    return _business_rules

async def verify_api_key(x_api_key: str = Depends(api_key_header)):
    """Verify API key authentication"""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

# --- Optimized Helper Functions ---

def extract_email_metadata(raw_email: str) -> dict:
    """Extract key metadata from raw email content (lazy loading)"""
    try:
        email = get_email_module()
        msg = email.message_from_string(raw_email)
        return {
            "message_id": msg.get("Message-ID"),
            "internet_message_id": msg.get("Internet-Message-ID", msg.get("Message-ID")),
            "reply_to": msg.get("Reply-To"),
            "from": msg.get("From"),
            "subject": msg.get("Subject"),
            "date": msg.get("Date")
        }
    except Exception as e:
        logger.warning(f"Failed to parse email metadata: {e}")
        return {}

def determine_primary_email(from_email: str, reply_to: Optional[str] = None) -> str:
    """Determine primary email address"""
    return reply_to if reply_to else from_email

def calculate_email_hash(email_body: str, sender_email: str, subject: str) -> str:
    """Calculate hash for email deduplication"""
    content = f"{sender_email}{subject}{email_body}".encode('utf-8')
    return hashlib.sha256(content).hexdigest()

async def process_attachments_async(attachments, blob_client):
    """Process attachments asynchronously"""
    if not blob_client or not attachments:
        return []
    
    urls = []
    tasks = []
    
    for att in attachments:
        # Create async task for each upload
        task = asyncio.create_task(
            upload_attachment_async(att, blob_client)
        )
        tasks.append(task)
    
    # Process uploads in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Failed to upload attachment {attachments[i].filename}: {result}")
        else:
            urls.append(result)
    
    return urls

async def upload_attachment_async(attachment, blob_client):
    """Upload single attachment asynchronously"""
    try:
        # Run blocking operation in thread pool
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            blob_client.upload_file,
            attachment.filename,
            attachment.content_base64
        )
        logger.info(f"Uploaded attachment: {attachment.filename}")
        return (attachment.filename, url)
    except Exception as e:
        raise e

# --- Optimized Health Check ---

@app.get("/health")
async def health_check():
    """Lightweight health check that doesn't depend on all services"""
    health_status = {
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": time.time(),
        "services": {}
    }
    
    # Check services asynchronously without blocking
    try:
        # Quick PostgreSQL check
        pg_client = await get_postgres_client()
        if pg_client and pg_client.pool:
            health_status["services"]["postgresql"] = "connected"
        else:
            health_status["services"]["postgresql"] = "not_configured"
    except Exception as e:
        health_status["services"]["postgresql"] = f"error: {str(e)[:50]}"
    
    # Quick checks for other services (non-blocking)
    health_status["services"]["azure_blob"] = "configured" if os.getenv("AZURE_STORAGE_CONNECTION_STRING") else "not_configured"
    health_status["services"]["zoho_oauth"] = "configured" if os.getenv("ZOHO_OAUTH_SERVICE_URL") else "not_configured"
    health_status["services"]["openai"] = "configured" if os.getenv("OPENAI_API_KEY") else "not_configured"
    
    return health_status

@app.get("/health/detailed")
async def detailed_health_check(api_key: str = Depends(verify_api_key)):
    """Detailed health check with full service validation (requires auth)"""
    health_status = await health_check()
    
    # Add detailed checks
    try:
        # Test PostgreSQL query
        pg_client = await get_postgres_client()
        if pg_client:
            async with pg_client.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                health_status["services"]["postgresql_query"] = "success"
    except Exception as e:
        health_status["services"]["postgresql_query"] = f"failed: {str(e)[:50]}"
    
    # Test Zoho connectivity
    try:
        zoho_client = get_zoho_client()
        if zoho_client:
            health_status["services"]["zoho_api"] = "initialized"
    except Exception as e:
        health_status["services"]["zoho_api"] = f"failed: {str(e)[:50]}"
    
    return health_status

# --- Main Email Processing Endpoint (Optimized) ---

@app.post("/intake/email", response_model=ProcessingResult, status_code=201)
async def process_email_intake(
    payload: EmailPayload,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Optimized email processing with parallel operations and graceful degradation
    """
    start_time = time.time()
    logger.info(f"Processing email from: {payload.sender_email}")
    
    # Initialize services in parallel
    service_init_tasks = [
        get_postgres_client(),
        asyncio.create_task(asyncio.to_thread(get_blob_client)),
        asyncio.create_task(asyncio.to_thread(get_zoho_client)),
        asyncio.create_task(asyncio.to_thread(get_crew_manager)),
        asyncio.create_task(asyncio.to_thread(get_business_rules))
    ]
    
    # Wait for all services to initialize
    (
        pg_client,
        blob_client,
        zoho_client,
        crew_manager,
        business_rules
    ) = await asyncio.gather(*service_init_tasks, return_exceptions=True)
    
    # Handle exceptions - results are already resolved from gather
    blob_client = blob_client if not isinstance(blob_client, Exception) else None
    zoho_client = zoho_client if not isinstance(zoho_client, Exception) else None
    crew_manager = crew_manager if not isinstance(crew_manager, Exception) else None
    business_rules = business_rules if not isinstance(business_rules, Exception) else None
    
    # Check for critical service failures
    if not zoho_client:
        logger.error("Zoho client not available")
        raise HTTPException(status_code=503, detail="Zoho service unavailable")
    
    try:
        # Extract email metadata
        email_metadata = extract_email_metadata(payload.raw_email) if hasattr(payload, 'raw_email') else {}
        internet_message_id = email_metadata.get("internet_message_id")
        
        # Calculate email hash
        email_hash = calculate_email_hash(payload.body, payload.sender_email, payload.subject)
        
        # Check for duplicates (if PostgreSQL available)
        if pg_client and not isinstance(pg_client, Exception):
            duplicate = await check_duplicate_with_fallback(
                pg_client, internet_message_id, email_hash
            )
            if duplicate:
                logger.info(f"Email already processed: {duplicate.get('zoho_deal_id')}")
                return ProcessingResult(
                    status="duplicate",
                    message=f"Email already processed - Deal: {duplicate.get('deal_name')}",
                    deal_id=duplicate.get('zoho_deal_id'),
                    account_id=duplicate.get('zoho_account_id'),
                    contact_id=duplicate.get('zoho_contact_id'),
                    deal_name=duplicate.get('deal_name'),
                    primary_email=duplicate.get('primary_email')
                )
        
        # Determine primary email
        reply_to_email = email_metadata.get("reply_to")
        primary_email = determine_primary_email(payload.sender_email, reply_to_email)
        primary_domain = primary_email.split('@')[1] if '@' in primary_email else 'unknown.com'
        
        # Process attachments asynchronously
        attachment_task = asyncio.create_task(
            process_attachments_async(payload.attachments, blob_client)
        )
        
        # Run AI extraction (with fallback)
        extracted_data = await run_ai_extraction_with_fallback(
            crew_manager, payload.body, primary_domain
        )
        
        # Apply business rules
        processed_data = business_rules.process_data(
            extracted_data.model_dump(),
            payload.body,
            primary_email
        ) if business_rules else {"deal_name": "Email Processing"}
        
        # Wait for attachments to complete
        attachment_info = await attachment_task
        
        # Create Zoho records
        company_name = processed_data.get('company_name') or zoho_client.infer_company_from_domain(primary_email)
        
        # Create records in Zoho
        account_id = await zoho_client.upsert_account(
            company_name=company_name,
            website=f"https://{primary_domain}"
        )
        
        contact_name = processed_data.get('contact_full_name') or processed_data.get('candidate_name', 'Unknown Contact')
        contact_id = await zoho_client.upsert_contact(
            full_name=contact_name,
            email=primary_email,
            account_id=account_id
        )
        
        deal_data = {
            "deal_name": processed_data.get('deal_name', 'Email Processing'),
            "account_id": account_id,
            "contact_id": contact_id,
            "source": processed_data.get('source_type', 'Email'),
            "source_detail": processed_data.get('source_detail'),
            "pipeline": "Sales Pipeline",
            "description": f"Deal created from email.\nSubject: {payload.subject}\nFrom: {primary_email}"
        }
        
        deal_id = zoho_client.create_deal(deal_data, internet_message_id)
        
        # Attach files in background
        if attachment_info:
            background_tasks.add_task(
                attach_files_to_deal,
                zoho_client,
                deal_id,
                attachment_info
            )
        
        # Store processing history in background
        if pg_client and not isinstance(pg_client, Exception):
            background_tasks.add_task(
                store_processing_history,
                pg_client,
                {
                    'internet_message_id': internet_message_id,
                    'sender_email': payload.sender_email,
                    'reply_to_email': reply_to_email,
                    'primary_email': primary_email,
                    'subject': payload.subject,
                    'zoho_deal_id': deal_id,
                    'zoho_account_id': account_id,
                    'zoho_contact_id': contact_id,
                    'deal_name': deal_data['deal_name'],
                    'company_name': company_name,
                    'contact_name': contact_name,
                    'processing_status': 'success',
                    'raw_extracted_data': extracted_data.model_dump(),
                    'email_body_hash': email_hash
                }
            )
        
        processing_time = time.time() - start_time
        logger.info(f"Email processed successfully in {processing_time:.2f}s")
        
        return ProcessingResult(
            status="success",
            message=f"Successfully processed email with Deal: {deal_data['deal_name']}",
            deal_id=deal_id,
            account_id=account_id,
            contact_id=contact_id,
            deal_name=deal_data['deal_name'],
            primary_email=primary_email
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Error in intake process after {processing_time:.2f}s: {e}", exc_info=True)
        
        # Store error in background if PostgreSQL available
        if pg_client and not isinstance(pg_client, Exception):
            background_tasks.add_task(
                store_error_history,
                pg_client,
                payload,
                str(e),
                email_hash
            )
        
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# --- Background Tasks ---

async def attach_files_to_deal(zoho_client, deal_id: str, attachment_info: list):
    """Attach files to deal in background"""
    for filename, url in attachment_info:
        try:
            zoho_client.attach_file_to_deal(deal_id, url, filename)
        except Exception as e:
            logger.error(f"Failed to attach {filename} to deal {deal_id}: {e}")

async def store_processing_history(pg_client, processing_record: dict):
    """Store processing history in background"""
    try:
        await pg_client.store_email_processing(processing_record)
        logger.info("Processing history stored successfully")
    except Exception as e:
        logger.error(f"Failed to store processing history: {e}")

async def store_error_history(pg_client, payload: EmailPayload, error_message: str, email_hash: str):
    """Store error history in background"""
    try:
        error_record = {
            'sender_email': payload.sender_email,
            'primary_email': payload.sender_email,
            'subject': payload.subject,
            'processing_status': 'error',
            'error_message': error_message,
            'email_body_hash': email_hash
        }
        await pg_client.store_email_processing(error_record)
    except Exception as e:
        logger.error(f"Failed to store error history: {e}")

# --- Fallback Functions ---

async def check_duplicate_with_fallback(pg_client, internet_message_id: str, email_hash: str) -> Optional[Dict]:
    """Check for duplicates with error handling"""
    try:
        if internet_message_id:
            duplicate = await pg_client.check_duplicate_email(internet_message_id=internet_message_id)
            if duplicate:
                return duplicate
        
        return await pg_client.check_duplicate_email(email_hash=email_hash)
    except Exception as e:
        logger.warning(f"Duplicate check failed (non-critical): {e}")
        return None

async def run_ai_extraction_with_fallback(crew_manager, email_body: str, domain: str) -> ExtractedData:
    """Run AI extraction with fallback to basic extraction"""
    if crew_manager:
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, crew_manager.run, email_body, domain),
                timeout=45  # 45 second timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error("AI extraction timed out, using fallback")
        except Exception as e:
            logger.error(f"AI extraction failed: {e}, using fallback")
    
    # Fallback extraction
    return ExtractedData(
        candidate_name="Unknown",
        job_title="Unknown Position",
        location="Unknown Location",
        company_name=None,
        referrer_name=None
    )

# --- Test Endpoint ---

@app.get("/test/kevin-sullivan")
async def test_kevin_sullivan_email(
    api_key: str = Depends(verify_api_key),
    background_tasks: BackgroundTasks = None
):
    """Test endpoint for Kevin Sullivan email scenario (optimized)"""
    test_payload = EmailPayload(
        sender_email="ksullivan@namcoa.com",
        subject="Re: introduction: Kevin and Steve",
        body="""Hi Steve,

Thank you for the introduction. I'm an Advisor looking for opportunities in the Fort Wayne area.

I have experience with financial planning and would be interested in discussing opportunities with Howard Bailey.

Best regards,
Mr. Kevin Sullivan
Senior Financial Advisor
""",
        attachments=[],
        raw_email=f"""Message-ID: <test-kevin-sullivan-{int(time.time())}>
From: ksullivan@namcoa.com
To: steve@example.com
Subject: Re: introduction: Kevin and Steve

[email body here]"""
    )
    
    return await process_email_intake(test_payload, background_tasks, api_key)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main_optimized:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        access_log=False,  # Disable access logs for performance
        loop="uvloop"  # Use uvloop for better performance
    )