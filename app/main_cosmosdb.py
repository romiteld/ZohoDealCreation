"""
FastAPI main application using Cosmos DB instead of Chroma/SQLite
No more SQLite compatibility issues!
"""

import logging
import os
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

# Initialize structured logging
import structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Import models and services
from app.models import EmailRequest, ZohoResponse, ErrorResponse
from app.business_rules import BusinessRulesEngine
from app.integrations import ZohoIntegration, AzureBlobStorage, PostgreSQLClient
from app.crewai_manager_cosmosdb import EmailProcessingCrew
from app.vector_store import get_vector_store, cleanup_vector_store

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
    
    # Initialize vector store
    try:
        vector_store = await get_vector_store()
        logger.info("Cosmos DB vector store initialized")
    except Exception as e:
        logger.warning(f"Vector store initialization failed (will continue without): {e}")
    
    # Initialize PostgreSQL client
    postgres_client = PostgreSQLClient()
    await postgres_client.initialize()
    app.state.postgres_client = postgres_client
    
    yield
    
    # Shutdown
    logger.info("Shutting down Well Intake API")
    await cleanup_vector_store()
    await postgres_client.close()

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

# Initialize services
business_rules = BusinessRulesEngine()
zoho_integration = ZohoIntegration()
blob_storage = AzureBlobStorage()

# Initialize CrewAI with Firecrawl
firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY", "")
crew_processor = EmailProcessingCrew(firecrawl_api_key)

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
        if hasattr(app.state, 'postgres_client'):
            await app.state.postgres_client.test_connection()
            health_status["services"]["cosmos_db"] = "operational"
    except:
        health_status["services"]["cosmos_db"] = "error"
    
    # Check Zoho
    try:
        zoho_integration.get_access_token()
        health_status["services"]["zoho"] = "operational"
    except:
        health_status["services"]["zoho"] = "error"
    
    # Check Blob Storage
    try:
        blob_storage.get_container_client()
        health_status["services"]["blob_storage"] = "operational"
    except:
        health_status["services"]["blob_storage"] = "error"
    
    return health_status

@app.post("/intake/email", response_model=ZohoResponse, dependencies=[Depends(verify_api_key)])
async def process_email(request: EmailRequest):
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
        
        # Process with CrewAI (now using Cosmos DB)
        extracted_data = await crew_processor.run_async(request.body, sender_domain)
        logger.info(f"Extracted data: {extracted_data}")
        
        # Apply business rules
        enhanced_data = business_rules.apply_rules(extracted_data, request)
        
        # Check for duplicates using Cosmos DB
        postgres_client = app.state.postgres_client
        is_duplicate = await postgres_client.check_duplicate(
            request.sender_email,
            enhanced_data.candidate_name
        )
        
        if is_duplicate:
            logger.info(f"Duplicate detected for {request.sender_email}")
        
        # Create or update Zoho records
        deal_id = await zoho_integration.create_or_update_records(
            enhanced_data,
            request.sender_email,
            attachment_urls,
            is_duplicate
        )
        
        # Store in database for deduplication
        if not is_duplicate:
            await postgres_client.store_processed_email(
                request.sender_email,
                enhanced_data.candidate_name,
                deal_id
            )
        
        return ZohoResponse(
            success=True,
            deal_id=deal_id,
            message="Email processed successfully",
            extracted_data=enhanced_data.model_dump()
        )
        
    except Exception as e:
        logger.error(f"Error processing email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test/kevin-sullivan", dependencies=[Depends(verify_api_key)])
async def test_kevin_sullivan():
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
    
    return await process_email(test_email)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)