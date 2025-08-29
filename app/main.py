"""
FastAPI main application using Cosmos DB instead of Chroma/SQLite
No more SQLite compatibility issues!
"""

# LangGraph implementation - no ChromaDB/SQLite dependencies
import os
import logging
import asyncio
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status, Header, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
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
    
    # Initialize Service Bus manager if connection string is available
    service_bus_conn = os.getenv("SERVICE_BUS_CONNECTION_STRING")
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

# Create FastAPI app
app = FastAPI(
    title="Well Intake API",
    description="Intelligent email processing with Cosmos DB",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS (including WebSocket support)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Include streaming endpoints
from app.streaming_endpoints import router as streaming_router
app.include_router(streaming_router)

# Initialize services (zoho_integration will be initialized in lifespan)
business_rules = BusinessRulesEngine()
blob_storage = AzureBlobStorage(
    connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING", ""),
    container_name=os.getenv("AZURE_CONTAINER_NAME", "email-attachments")
)

# Legacy - SerperDev was used with CrewAI (now deprecated)
# serper_api_key = os.getenv("SERPER_API_KEY", "")

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
            "/commands.js"
        ]
    }

@app.get("/learning/analytics/{field_name}", dependencies=[Depends(verify_api_key)])
async def get_field_analytics(field_name: str, days_back: int = 30, domain: Optional[str] = None):
    """Get learning analytics for a specific extraction field"""
    try:
        from app.learning_analytics import LearningAnalytics
        from app.correction_learning import CorrectionLearningService
        
        # Initialize services
        correction_service = CorrectionLearningService(None, use_azure_search=True)
        analytics = LearningAnalytics(search_manager=correction_service.search_manager)
        
        # Get field analytics
        result = await analytics.get_field_analytics(
            field_name=field_name,
            days_back=days_back,
            email_domain=domain
        )
        
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
    
    # Check Redis Cache
    try:
        from app.redis_cache_manager import get_cache_manager
        cache_manager = await get_cache_manager()
        if cache_manager._connected:
            metrics = await cache_manager.get_metrics()
            health_status["services"]["redis_cache"] = "operational"
            health_status["cache_metrics"] = {
                "hit_rate": metrics.get("hit_rate", "0%"),
                "total_requests": metrics.get("total_requests", 0),
                "estimated_savings": f"${metrics.get('savings', 0):.2f}"
            }
        else:
            health_status["services"]["redis_cache"] = "not_connected"
    except Exception as e:
        logger.warning(f"Redis cache health check failed: {e}")
        health_status["services"]["redis_cache"] = "not_configured"
    
    return health_status

@app.post("/intake/email", response_model=ZohoResponse, dependencies=[Depends(verify_api_key)])
async def process_email(request: EmailRequest, req: Request):
    """Process email and create Zoho CRM records with learning from user corrections"""
    try:
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
            # Use LangGraph implementation (CrewAI deprecated)
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
    """Get Redis cache performance metrics and optimization recommendations"""
    try:
        from app.redis_cache_manager import get_cache_manager
        from app.cache_strategies import get_strategy_manager
        
        cache_manager = await get_cache_manager()
        strategy_manager = get_strategy_manager()
        
        # Get cache metrics
        cache_metrics = await cache_manager.get_metrics()
        
        # Get strategy metrics
        strategy_metrics = strategy_manager.get_metrics()
        
        # Get optimization recommendations
        optimizations = strategy_manager.optimize_cache_strategy(cache_metrics)
        
        return {
            "status": "connected" if cache_manager._connected else "disconnected",
            "cache_metrics": cache_metrics,
            "strategy_metrics": strategy_metrics,
            "optimizations": optimizations,
            "cost_analysis": {
                "gpt5_mini_per_million": "$0.25",
                "cached_per_million": "$0.025",
                "savings_ratio": "90%",
                "estimated_monthly_savings": f"${cache_metrics.get('estimated_monthly_savings', 0):.2f}"
            }
        }
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Cache not configured or unavailable"
        }

@app.post("/cache/invalidate", dependencies=[Depends(verify_api_key)])
async def invalidate_cache(pattern: Optional[str] = None):
    """Invalidate cache entries matching a pattern"""
    try:
        from app.redis_cache_manager import get_cache_manager
        
        cache_manager = await get_cache_manager()
        deleted_count = await cache_manager.invalidate_cache(pattern)
        
        return {
            "status": "success",
            "deleted_entries": deleted_count,
            "pattern": pattern or "well:email:*"
        }
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cache/warmup", dependencies=[Depends(verify_api_key)])
async def warmup_cache():
    """Pre-warm cache with common email patterns"""
    try:
        from app.redis_cache_manager import get_cache_manager
        from app.cache_strategies import get_strategy_manager
        
        cache_manager = await get_cache_manager()
        strategy_manager = get_strategy_manager()
        
        # Get common patterns
        common_patterns = strategy_manager.get_common_patterns()
        
        # Warm up cache
        cached_count = await cache_manager.warmup_cache(common_patterns)
        
        return {
            "status": "success",
            "patterns_cached": cached_count,
            "patterns": [p["key"] for p in common_patterns]
        }
    except Exception as e:
        logger.error(f"Error warming up cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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