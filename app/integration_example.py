"""
Integration Example - How to Use Processing Data Builder in Main Flow

This file shows exactly how Agent #1 and other agents can integrate the
comprehensive processing data construction into the main email processing flow.

The examples show minimal code changes needed to add full processing storage.
"""

import logging
from typing import Dict, Any, Optional, Union

from .models import EmailPayload, ExtractedData, ProcessingResult
from .processing_integration_helpers import initialize_processing_integration, record_processing_event

logger = logging.getLogger(__name__)


async def example_main_processing_flow_integration(
    request: EmailPayload, 
    app_state,
    business_rules,
    zoho_integration
):
    """
    Example showing how to integrate processing storage into main.py processing flow.
    
    This demonstrates the minimal changes needed to add comprehensive processing storage
    to the existing email processing logic in main.py.
    """
    
    # STEP 1: Initialize processing integration (once per app startup)
    # This would go in the startup/lifespan function
    processing_helper = await initialize_processing_integration(app_state)
    
    # STEP 2: Record processing start
    processing_context = await processing_helper.record_processing_start(request)
    
    try:
        # STEP 3: Your existing processing logic (unchanged)
        # ... existing validation, sanitization ...
        
        # ... existing attachment processing ...
        
        # ... existing AI extraction with LangGraph ...
        # Assume this returns extracted_data
        extracted_data = ExtractedData(
            candidate_name="John Smith",
            job_title="Senior Financial Advisor", 
            company_name="ABC Wealth Management",
            # ... other fields
        )
        
        # ... existing business rules processing ...
        processed_data = business_rules.process_data(
            extracted_data.model_dump(),
            request.body,
            request.sender_email
        )
        enhanced_data = ExtractedData(**processed_data)
        
        # ... existing duplicate checking ...
        is_duplicate = False  # from duplicate check
        
        # Handle dry run case
        if getattr(request, 'dry_run', False):
            # STEP 4a: Record dry run processing
            await record_processing_event(
                processing_helper,
                "dry_run",
                request,
                extracted_data=enhanced_data,
                processing_context=processing_context
            )
            
            return ProcessingResult(
                status="preview",
                message="Preview only - no Zoho records created",
                extracted=enhanced_data
            )
        
        # ... existing Zoho record creation ...
        zoho_result = await zoho_integration.create_or_update_records(
            enhanced_data,
            request.sender_email,
            [],  # attachment_urls
            is_duplicate
        )
        
        # STEP 4b: Record successful processing with full metadata
        await record_processing_event(
            processing_helper,
            "success" if not is_duplicate else "duplicate",
            request,
            extracted_data=enhanced_data,
            zoho_result=zoho_result,
            existing_zoho_ids=zoho_result if is_duplicate else None,
            processing_context=processing_context
        )
        
        # ... existing response construction ...
        return ProcessingResult(
            status="success",
            deal_id=zoho_result["deal_id"],
            account_id=zoho_result["account_id"],
            contact_id=zoho_result["contact_id"],
            deal_name=zoho_result["deal_name"],
            primary_email=zoho_result["primary_email"],
            message="Email processed successfully"
        )
        
    except Exception as e:
        # STEP 4c: Record processing error with details
        await record_processing_event(
            processing_helper,
            "error",
            request,
            error_message=str(e),
            extracted_data=None,  # or partial data if available
            processing_context=processing_context
        )
        
        logger.error(f"Error processing email: {str(e)}")
        raise


async def example_user_correction_flow_integration(
    request: EmailPayload,
    app_state
):
    """
    Example showing how to integrate user correction processing storage.
    
    This shows how to handle cases where users provide corrections to AI extraction.
    """
    
    processing_helper = await initialize_processing_integration(app_state)
    processing_context = await processing_helper.record_processing_start(request)
    
    try:
        # Original AI extraction (from request.ai_extraction)
        original_extraction = request.ai_extraction or {}
        
        # User corrections (from request.user_corrections) 
        user_corrections = request.user_corrections or {}
        
        # Create corrected data
        corrected_data = ExtractedData(**user_corrections)
        
        # Process with Zoho
        zoho_result = await create_zoho_records(corrected_data)
        
        # Record user correction processing with both original and corrected data
        await record_processing_event(
            processing_helper,
            "user_corrected",
            request,
            original_extraction=original_extraction,
            corrected_extraction=corrected_data,
            zoho_result=zoho_result,
            processing_context=processing_context
        )
        
        return ProcessingResult(
            status="success",
            deal_id=zoho_result["deal_id"],
            message="Email processed with user corrections"
        )
        
    except Exception as e:
        await record_processing_event(
            processing_helper,
            "error",
            request,
            error_message=f"User correction processing failed: {str(e)}",
            processing_context=processing_context
        )
        raise


def example_integration_points_for_main_py():
    """
    Code snippets that show exact integration points for main.py
    
    These are the minimal changes needed to add processing storage to main.py
    """
    
    integration_points = {
        
        "startup_integration": """
        # Add to lifespan function in main.py after PostgreSQL client initialization:
        
        if hasattr(app.state, 'postgres_client') and app.state.postgres_client:
            from app.processing_integration_helpers import initialize_processing_integration
            app.state.processing_helper = await initialize_processing_integration(app.state)
            logger.info("Processing storage integration initialized")
        else:
            app.state.processing_helper = None
            logger.warning("Processing storage not available")
        """,
        
        "process_email_start": """
        # Add at the start of process_email function:
        
        # Initialize processing tracking
        processing_context = None
        if hasattr(req.app.state, 'processing_helper') and req.app.state.processing_helper:
            processing_context = await req.app.state.processing_helper.record_processing_start(request)
        """,
        
        "successful_processing": """
        # Add after successful Zoho record creation:
        
        # Record successful processing
        if hasattr(req.app.state, 'processing_helper') and req.app.state.processing_helper:
            await req.app.state.processing_helper.record_successful_processing(
                request=request,
                extracted_data=enhanced_data,
                zoho_result=zoho_result
            )
        """,
        
        "dry_run_processing": """
        # Add in dry_run handling section:
        
        # Record dry run processing
        if hasattr(req.app.state, 'processing_helper') and req.app.state.processing_helper:
            await req.app.state.processing_helper.record_dry_run_processing(
                request=request,
                extracted_data=enhanced_data
            )
        """,
        
        "duplicate_processing": """
        # Add when duplicate is detected:
        
        # Record duplicate processing
        if is_duplicate and hasattr(req.app.state, 'processing_helper') and req.app.state.processing_helper:
            await req.app.state.processing_helper.record_duplicate_processing(
                request=request,
                extracted_data=enhanced_data,
                existing_zoho_ids={
                    'deal_id': zoho_result.get('deal_id'),
                    'account_id': zoho_result.get('account_id'),
                    'contact_id': zoho_result.get('contact_id')
                }
            )
        """,
        
        "error_processing": """
        # Add in exception handler:
        
        except Exception as e:
            # Record processing error
            if hasattr(req.app.state, 'processing_helper') and req.app.state.processing_helper:
                await req.app.state.processing_helper.record_processing_error(
                    request=request,
                    error_message=str(e),
                    extracted_data=None  # or partial data if available
                )
            
            logger.error(f"Error processing email: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        """,
        
        "user_correction_processing": """
        # Add when user corrections are provided:
        
        if request.user_corrections and request.ai_extraction:
            # Record user correction processing
            if hasattr(req.app.state, 'processing_helper') and req.app.state.processing_helper:
                await req.app.state.processing_helper.record_user_correction_processing(
                    request=request,
                    original_extraction=request.ai_extraction,
                    corrected_extraction=enhanced_data,
                    zoho_result=zoho_result
                )
        """
    }
    
    return integration_points


def example_health_check_integration():
    """
    Example of how to add processing storage health check to the health endpoint.
    """
    
    health_check_addition = """
    # Add to health_check function in main.py:
    
    # Check processing storage
    try:
        if hasattr(app.state, 'processing_helper') and app.state.processing_helper:
            stats = app.state.processing_helper.get_processing_stats()
            health_status["services"]["processing_storage"] = "operational" if stats['storage_available'] else "not_available"
            health_status["processing_stats"] = stats['session_stats']
        else:
            health_status["services"]["processing_storage"] = "not_configured"
    except Exception as e:
        logger.warning(f"Processing storage health check failed: {e}")
        health_status["services"]["processing_storage"] = "error"
    """
    
    return health_check_addition


async def create_zoho_records(extracted_data):
    """Mock function for example purposes."""
    return {
        "deal_id": "123456789",
        "account_id": "987654321", 
        "contact_id": "456789123",
        "deal_name": "Senior Financial Advisor (Fort Wayne) - ABC Wealth Management",
        "primary_email": "john.smith@abcwealth.com"
    }


# Summary for Agent #1 and other agents:
INTEGRATION_SUMMARY = """
PROCESSING DATA BUILDER INTEGRATION SUMMARY

For Agent #1 (Main API Storage Integration):

1. INITIALIZATION (app startup):
   - Add processing_helper to app.state during lifespan
   - Uses existing postgres_client

2. CORE INTEGRATION (process_email function):
   - Call record_processing_start() at beginning
   - Call appropriate record_*_processing() methods at completion
   - Handle all processing outcomes: success, error, duplicate, dry_run

3. MINIMAL CODE CHANGES:
   - ~10 lines added to startup
   - ~5-10 lines per processing outcome
   - Graceful fallback if storage not available

4. COMPREHENSIVE DATA STORAGE:
   - All required fields for store_email_processing()
   - Proper sanitization and validation
   - Full metadata including Zoho IDs, error details, timestamps

5. COORDINATION WITH OTHER AGENTS:
   - Agent #4 can use the stored data for database operations
   - Data structure is consistent across all agents
   - Helper functions available for any agent to use

KEY FILES CREATED:
- processing_data_builder.py: Core data construction with validation
- email_processing_storage.py: Storage manager with full CRUD operations  
- processing_integration_helpers.py: Simple integration helpers
- integration_example.py: Complete examples and integration points

USAGE:
The helper automatically handles data construction, validation, and storage.
Agent #1 just needs to call the appropriate record_*_processing() method
with the original request and results - everything else is handled automatically.
"""