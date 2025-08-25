"""
Main application module for the Well Intake API with Steve's business rules and PostgreSQL integration
"""

import os
import sys
import logging
import hashlib
import time
from fastapi import FastAPI, Depends, HTTPException, Header, BackgroundTasks, UploadFile, File
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from dotenv import load_dotenv
import asyncio
from contextlib import asynccontextmanager
import email
from email.message import EmailMessage
from typing import Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables first
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env.local')
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"Loaded environment from: {env_path}")
else:
    print(f"Warning: .env.local not found at {env_path}")
    load_dotenv()

from app.models import EmailPayload, ExtractedData, ProcessingResult
from app.integrations import AzureBlobStorageClient, ZohoClient, PostgreSQLClient
from app.crewai_manager import EmailProcessingCrew
from app.business_rules import BusinessRulesEngine
from app.static_files import router as static_router
from app.error_handlers import register_error_handlers

# --- Configuration ---
API_KEY = os.getenv("API_KEY")
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- App Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks"""
    logger.info("Starting Well Intake API with PostgreSQL and Steve's business rules...")
    
    try:
        # Initialize PostgreSQL client and ensure tables exist
        pg_client = get_postgres_client()
        if pg_client:
            try:
                await pg_client.ensure_tables()
                logger.info("PostgreSQL tables initialized")
            except Exception as e:
                logger.warning(f"PostgreSQL initialization skipped: {e}")
                # Continue without PostgreSQL - it's optional
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Continue anyway - the app can work without PostgreSQL
    
    yield
    
    logger.info("Shutting down Well Intake API...")
    # Cleanup tasks if needed
    try:
        pg_client = get_postgres_client()
        if pg_client and pg_client.pool:
            await pg_client.pool.close()
            logger.info("PostgreSQL connection pool closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

app = FastAPI(
    title="The Well Recruiting - Email Intake API",
    version="2.1.0",
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
        "https://well-intake-api.azurewebsites.net",
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
            "well-intake-api.azurewebsites.net",
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

# --- Dependency Injection ---
def get_blob_client():
    """Get Azure Blob Storage client"""
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        logger.warning("Azure Storage connection string not configured")
    return AzureBlobStorageClient(conn_str)

def get_postgres_client():
    """Get PostgreSQL client (optional - app works without it)"""
    # Try multiple connection string keys
    pg_conn = (
        os.getenv("POSTGRES_CONNECTION_STRING") or
        os.getenv("DATABASE_URL") or
        os.getenv("POSTGRESQL_CONNECTION_STRING")
    )
    
    if pg_conn:
        try:
            return PostgreSQLClient(pg_conn)
        except ImportError as e:
            logger.warning(f"PostgreSQL client disabled - asyncpg not installed: {e}")
            return None
        except Exception as e:
            logger.warning(f"PostgreSQL client creation failed: {e}")
            return None
    else:
        logger.info("PostgreSQL not configured - running without database features")
        return None

def get_zoho_client():
    """Get Zoho CRM client"""
    pg_client = get_postgres_client()
    return ZohoClient(pg_client)

def get_crew_manager():
    """Get CrewAI manager for email processing"""
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
    if not firecrawl_key:
        logger.warning("Firecrawl API key not configured - web enrichment disabled")
    return EmailProcessingCrew(firecrawl_key)

def get_business_rules():
    """Get business rules engine"""
    return BusinessRulesEngine()

async def verify_api_key(x_api_key: str = Depends(api_key_header)):
    """Verify API key for authentication"""
    if not API_KEY:
        logger.warning("API_KEY not configured - authentication disabled")
        return  # Skip authentication in development
    
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

# --- Helper Functions ---
def extract_email_metadata(raw_email: str) -> dict:
    """Extract key metadata from raw email content."""
    try:
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
    """Always pick Reply-To if present, else From per Steve's feedback."""
    return reply_to if reply_to else from_email

def calculate_email_hash(email_body: str, sender_email: str, subject: str) -> str:
    """Calculate hash for email deduplication."""
    content = f"{sender_email}{subject}{email_body}".encode('utf-8')
    return hashlib.sha256(content).hexdigest()

def process_attachments(attachments, blob_client):
    """Process attachments synchronously"""
    urls = []
    for att in attachments:
        try:
            url = blob_client.upload_file(att.filename, att.content_base64)
            urls.append((att.filename, url))
            logger.info(f"Uploaded attachment: {att.filename}")
        except Exception as e:
            logger.error(f"Failed to upload attachment {att.filename}: {e}")
    return urls

# --- API Endpoints ---
@app.post("/intake/email", response_model=ProcessingResult, status_code=201)
async def process_email_intake(
    payload: EmailPayload,
    x_api_key: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
    blob_client: AzureBlobStorageClient = Depends(get_blob_client),
    zoho_client: ZohoClient = Depends(get_zoho_client),
    pg_client: PostgreSQLClient = Depends(get_postgres_client),
    crew_manager: EmailProcessingCrew = Depends(get_crew_manager),
    business_rules: BusinessRulesEngine = Depends(get_business_rules)
):
    """
    Processes an email with Steve's business rules and PostgreSQL integration:
    1. Check for duplicate emails (PostgreSQL)
    2. Always use Reply-To if present, else From
    3. Strip salutations (Mr., Mrs., etc.) from contact names
    4. Cache Zoho record lookups (PostgreSQL)
    5. Store processing history and enable analytics
    """
    # Authentication check - allow Outlook add-in requests without API key
    is_outlook_addin = "Office" in (user_agent or "") or "Outlook" in (user_agent or "")
    
    if API_KEY and not is_outlook_addin:
        # Require API key for non-add-in requests when API_KEY is configured
        if not x_api_key or x_api_key != API_KEY:
            raise HTTPException(status_code=403, detail="Invalid API Key")
    
    logger.info(f"Processing email from: {payload.sender_email} (Add-in: {is_outlook_addin})")
    
    try:
        # Extract email metadata for traceability
        email_metadata = extract_email_metadata(payload.raw_email) if hasattr(payload, 'raw_email') else {}
        internet_message_id = email_metadata.get("internet_message_id")
        
        # Calculate email hash for deduplication
        email_hash = calculate_email_hash(payload.body, payload.sender_email, payload.subject)
        
        # Check for duplicate processing (PostgreSQL)
        if pg_client:
            duplicate = None
            if internet_message_id:
                duplicate = await pg_client.check_duplicate_email(internet_message_id=internet_message_id)
            if not duplicate:
                duplicate = await pg_client.check_duplicate_email(email_hash=email_hash)
            
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
        
        # Determine primary email address (Reply-To takes precedence)
        reply_to_email = email_metadata.get("reply_to")
        primary_email = determine_primary_email(payload.sender_email, reply_to_email)
        primary_domain = primary_email.split('@')[1] if '@' in primary_email else 'unknown.com'
        
        logger.info(f"Primary email: {primary_email} (Reply-To: {reply_to_email})")
        
        # Check for cached company enrichment (PostgreSQL)
        enriched_data = None
        if pg_client:
            enriched_data = await pg_client.get_company_enrichment(primary_domain)
            if enriched_data:
                logger.info(f"Using cached company data for {primary_domain}")
        
        # Process attachments
        attachment_info = process_attachments(payload.attachments, blob_client)
        
        # Run AI extraction with domain context
        logger.info("Running CrewAI extraction...")
        extracted_data = crew_manager.run(payload.body, primary_domain)
        logger.info(f"AI Extracted Data: {extracted_data.model_dump_json()}")
        
        # Apply business rules
        processed_data = business_rules.process_data(
            extracted_data.model_dump(), 
            payload.body, 
            primary_email
        )
        
        # Infer company from domain if not provided
        company_name = processed_data.get('company_name') or zoho_client.infer_company_from_domain(primary_email)
        
        # Use enriched data if available
        if enriched_data and enriched_data.get('company_name'):
            company_name = enriched_data['company_name']
        
        # Create/update Account with deduplication and caching
        logger.info(f"Creating/updating account: {company_name}")
        account_id = await zoho_client.upsert_account(
            company_name=company_name,
            website=f"https://{primary_domain}",
            enriched_data=enriched_data
        )
        
        # Create/update Contact with proper name handling and caching
        contact_name = processed_data.get('contact_full_name') or processed_data.get('candidate_name', 'Unknown Contact')
        logger.info(f"Creating/updating contact: {contact_name} ({primary_email})")
        contact_id = await zoho_client.upsert_contact(
            full_name=contact_name,
            email=primary_email,
            account_id=account_id
        )
        
        # Create Deal with Steve's exact field mapping
        deal_data = {
            "deal_name": processed_data.get('deal_name'),
            "account_id": account_id,
            "contact_id": contact_id,
            "source": processed_data.get('source_type', 'Email'),
            "source_detail": processed_data.get('source_detail'),
            "pipeline": "Sales Pipeline",
            "description": f"Deal created from email.\nSubject: {payload.subject}\nFrom: {primary_email}\n\n{payload.body[:2000]}"
        }
        
        logger.info(f"Creating deal: {deal_data['deal_name']}")
        deal_id = zoho_client.create_deal(deal_data, internet_message_id)
        
        # Attach files to deal
        for filename, url in attachment_info:
            zoho_client.attach_file_to_deal(deal_id, url, filename)
        
        # Store processing history in PostgreSQL
        if pg_client:
            processing_record = {
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
            
            email_record_id = await pg_client.store_email_processing(processing_record)
            logger.info(f"Stored processing history: {email_record_id}")
            
            # Cache company enrichment if not already cached
            if not enriched_data and processed_data.get('enriched_data'):
                await pg_client.store_company_enrichment(primary_domain, processed_data['enriched_data'])
        
        result = ProcessingResult(
            status="success",
            message=f"Successfully processed email with Deal: {deal_data['deal_name']}",
            deal_id=deal_id,
            account_id=account_id,
            contact_id=contact_id,
            deal_name=deal_data['deal_name'],
            primary_email=primary_email
        )
        
        logger.info(f"Successfully created: Account {account_id}, Contact {contact_id}, Deal {deal_id}")
        return result
        
    except Exception as e:
        # Store error in PostgreSQL if available
        if pg_client:
            try:
                error_record = {
                    'internet_message_id': internet_message_id,
                    'sender_email': payload.sender_email,
                    'primary_email': primary_email,
                    'subject': payload.subject,
                    'processing_status': 'error',
                    'error_message': str(e),
                    'email_body_hash': email_hash
                }
                await pg_client.store_email_processing(error_record)
            except Exception as pg_error:
                logger.error(f"Failed to store error in PostgreSQL: {pg_error}")
        
        logger.error(f"Error in intake process: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/ingest/upload")
async def upload_eml_file(
    file: UploadFile = File(...),
    api_key: str = Depends(verify_api_key),
    blob_client: AzureBlobStorageClient = Depends(get_blob_client),
    zoho_client: ZohoClient = Depends(get_zoho_client),
    pg_client: PostgreSQLClient = Depends(get_postgres_client),
    crew_manager: EmailProcessingCrew = Depends(get_crew_manager),
    business_rules: BusinessRulesEngine = Depends(get_business_rules)
):
    """
    Upload and process .eml/.msg files directly.
    Alternative endpoint for drag-and-drop functionality.
    """
    try:
        # Read uploaded file
        content = await file.read()
        raw_email = content.decode('utf-8', errors='ignore')
        
        # Parse email
        msg = email.message_from_string(raw_email)
        
        # Extract basic fields
        from_email = msg.get("From", "unknown@example.com")
        subject = msg.get("Subject", "No Subject")
        body = ""
        
        # Extract body
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
        else:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        # Create payload
        email_payload = EmailPayload(
            sender_email=from_email,
            subject=subject,
            body=body,
            attachments=[],
            raw_email=raw_email
        )
        
        # Process through main pipeline
        return await process_email_intake(
            email_payload, api_key, blob_client, zoho_client, 
            pg_client, crew_manager, business_rules
        )
        
    except Exception as e:
        logger.error(f"Error processing uploaded file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"File processing failed: {str(e)}")

@app.get("/health")
async def health_check(pg_client: PostgreSQLClient = Depends(get_postgres_client)):
    """Health check endpoint with service status."""
    services = {
        "api": "ok",
        "zoho_crm": "ok",
        "azure_blob": "ok",
        "postgresql": "unknown"
    }
    
    # Check PostgreSQL connection
    if pg_client:
        try:
            await pg_client.init_pool()
            services["postgresql"] = "ok"
        except Exception as e:
            services["postgresql"] = f"error: {str(e)}"
    
    return {
        "status": "ok",
        "version": "2.1.0",
        "business_rules": "Steve Perry approved",
        "zoho_api": "v8",
        "database": "Azure Cosmos DB for PostgreSQL",
        "services": services
    }

@app.get("/test/kevin-sullivan")
async def test_kevin_sullivan_email(
    api_key: str = Depends(verify_api_key),
    blob_client: AzureBlobStorageClient = Depends(get_blob_client),
    zoho_client: ZohoClient = Depends(get_zoho_client),
    pg_client: PostgreSQLClient = Depends(get_postgres_client),
    crew_manager: EmailProcessingCrew = Depends(get_crew_manager),
    business_rules: BusinessRulesEngine = Depends(get_business_rules)
):
    """
    Test endpoint for Kevin Sullivan email scenario.
    Expected results:
    - Account: "Namcoa" (normalized)
    - Contact: "Kevin Sullivan" (no "Mr.")
    - Email: ksullivan@namcoa.com
    - Deal name: [Job Title] ([Location]) - [Firm Name]
    """
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
    
    return await process_email_intake(
        test_payload, api_key, blob_client, zoho_client,
        pg_client, crew_manager, business_rules
    )

@app.get("/analytics/processing-history")
async def get_processing_history(
    limit: int = 20,
    api_key: str = Depends(verify_api_key),
    pg_client: PostgreSQLClient = Depends(get_postgres_client)
):
    """Get recent email processing history."""
    if not pg_client:
        raise HTTPException(status_code=503, detail="PostgreSQL not configured")
    
    await pg_client.init_pool()
    
    query = """
    SELECT 
        internet_message_id,
        sender_email,
        primary_email,
        subject,
        deal_name,
        company_name,
        contact_name,
        processing_status,
        processed_at,
        zoho_deal_id
    FROM email_processing_history 
    ORDER BY processed_at DESC 
    LIMIT $1
    """
    
    async with pg_client.pool.acquire() as conn:
        rows = await conn.fetch(query, limit)
        return [dict(row) for row in rows]

@app.get("/analytics/company-stats")
async def get_company_stats(
    api_key: str = Depends(verify_api_key),
    pg_client: PostgreSQLClient = Depends(get_postgres_client)
):
    """Get company processing statistics."""
    if not pg_client:
        raise HTTPException(status_code=503, detail="PostgreSQL not configured")
    
    await pg_client.init_pool()
    
    query = """
    SELECT 
        company_name,
        COUNT(*) as email_count,
        COUNT(DISTINCT primary_email) as unique_contacts,
        MAX(processed_at) as last_processed
    FROM email_processing_history 
    WHERE company_name IS NOT NULL
    GROUP BY company_name
    ORDER BY email_count DESC
    LIMIT 20
    """
    
    async with pg_client.pool.acquire() as conn:
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]
