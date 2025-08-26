"""
FastAPI main application using Cosmos DB instead of Chroma/SQLite
No more SQLite compatibility issues!
"""

# No ChromaDB mocking needed when bypassing CrewAI
import os
import logging
import asyncio
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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

# API Key Authentication
API_KEY = os.getenv("API_KEY", "your-secure-api-key-here")

async def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key from header"""
    if x_api_key != API_KEY:
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )
    return x_api_key

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
    
    yield
    
    # Shutdown
    logger.info("Shutting down Well Intake API")
    if hasattr(app.state, 'vector_store') and app.state.vector_store:
        from app.vector_store import cleanup_vector_store
        await cleanup_vector_store()
    if hasattr(app.state, 'postgres_client') and app.state.postgres_client:
        await app.state.postgres_client.close()

# Create FastAPI app
app = FastAPI(
    title="Well Intake API",
    description="Intelligent email processing with Cosmos DB",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services (zoho_integration will be initialized in lifespan)
business_rules = BusinessRulesEngine()
blob_storage = AzureBlobStorage(
    connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING", ""),
    container_name=os.getenv("AZURE_CONTAINER_NAME", "email-attachments")
)

# Initialize CrewAI with SerperDevTool for web search
serper_api_key = os.getenv("SERPER_API_KEY", "")

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Well Intake API",
        "version": "2.0.0",
        "status": "operational",
        "storage": "Cosmos DB for PostgreSQL",
        "vector_support": "pgvector",
        "no_sqlite": True,
        "endpoints": [
            "/health",
            "/intake/email",
            "/test/kevin-sullivan",
            "/manifest.xml",
            "/commands.js"
        ]
    }

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
            "vector_store": "cosmos_db_pgvector"
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
    
    return health_status

@app.post("/intake/email", response_model=ZohoResponse, dependencies=[Depends(verify_api_key)])
async def process_email(request: EmailRequest, req: Request):
    """Process email and create Zoho CRM records"""
    try:
        logger.info(f"Processing email from {request.sender_email}")
        
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
        
        # Check if we should use LangGraph or legacy CrewAI
        use_langgraph = os.getenv("USE_LANGGRAPH", "true").lower() == "true"
        bypass_crewai = os.getenv("BYPASS_CREWAI", "false").lower() == "true"
        
        if use_langgraph:
            # Use new LangGraph implementation
            try:
                logger.info("Using LangGraph for email processing")
                from app.langgraph_manager import EmailProcessingCrew
                processor = EmailProcessingCrew(serper_api_key)
                extracted_data = await processor.run_async(request.body, sender_domain)
                logger.info(f"Extracted data with LangGraph: {extracted_data}")
            except Exception as e:
                logger.warning(f"LangGraph processing failed: {e}, using fallback extractor")
                from app.langgraph_manager import SimplifiedEmailExtractor
                extracted_data = SimplifiedEmailExtractor.extract(request.body, request.sender_email)
                logger.info(f"Extracted data with fallback: {extracted_data}")
        elif bypass_crewai:
            logger.info("CrewAI bypassed via feature flag, using simplified extractor")
            from app.crewai_manager import SimplifiedEmailExtractor
            extracted_data = SimplifiedEmailExtractor.extract(request.body, request.sender_email)
            logger.info(f"Extracted data with fallback: {extracted_data}")
        else:
            # Try to use CrewAI if available, otherwise use fallback
            try:
                from app.crewai_manager import EmailProcessingCrew
                crew_processor = EmailProcessingCrew(serper_api_key)
                extracted_data = await crew_processor.run_async(request.body, sender_domain)
                logger.info(f"Extracted data with CrewAI: {extracted_data}")
            except Exception as e:
                logger.warning(f"CrewAI processing failed: {e}, using fallback extractor")
                from app.crewai_manager import SimplifiedEmailExtractor
                extracted_data = SimplifiedEmailExtractor.extract(request.body, request.sender_email)
                logger.info(f"Extracted data with fallback: {extracted_data}")
        
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

# Static file serving for Outlook Add-in
@app.get("/manifest.xml")
async def get_manifest():
    """Serve Outlook Add-in manifest"""
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "addin", "manifest.xml")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/xml")
    raise HTTPException(status_code=404, detail="Manifest not found")

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

@app.get("/taskpane.html")
async def get_taskpane():
    """Serve Outlook Add-in task pane"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "addin", "taskpane.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Taskpane.html not found")

# Icon file serving
@app.get("/icon-{size}.png")
async def get_icon(size: int):
    """Serve icon files for Outlook Add-in"""
    if size not in [16, 32, 80]:
        raise HTTPException(status_code=404, detail="Invalid icon size")
    
    icon_path = os.path.join(os.path.dirname(__file__), "..", "static", "icons", f"icon-{size}.png")
    if os.path.exists(icon_path):
        return FileResponse(icon_path, media_type="image/png")
    raise HTTPException(status_code=404, detail=f"Icon {size} not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)