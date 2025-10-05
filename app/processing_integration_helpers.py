"""
Processing Integration Helpers

This module provides simple integration points that can be easily added to the
main email processing flow in main.py to ensure all processing events are stored.
"""

import logging
from typing import Dict, Any, Optional, Union

from .models import EmailPayload, ExtractedData, ProcessingResult
from .email_processing_storage import EmailProcessingStorageManager, ProcessingEventTracker

logger = logging.getLogger(__name__)


class ProcessingIntegrationHelper:
    """
    Helper class that provides simple methods for integrating processing storage
    into the main email processing flow with minimal code changes.
    """
    
    def __init__(self, app_state=None):
        """
        Initialize helper with app state.
        
        Args:
            app_state: FastAPI app.state object containing postgres_client
        """
        self.app_state = app_state
        self._storage_manager = None
        self._event_tracker = None
    
    @property
    def storage_manager(self) -> Optional[EmailProcessingStorageManager]:
        """Get or create storage manager instance."""
        if not self._storage_manager and self.app_state:
            postgres_client = getattr(self.app_state, 'postgres_client', None)
            if postgres_client:
                self._storage_manager = EmailProcessingStorageManager(postgres_client)
        return self._storage_manager
    
    @property
    def event_tracker(self) -> Optional[ProcessingEventTracker]:
        """Get or create event tracker instance."""
        if not self._event_tracker and self.storage_manager:
            self._event_tracker = ProcessingEventTracker(self.storage_manager)
        return self._event_tracker
    
    async def record_processing_start(
        self,
        request: EmailPayload,
        processing_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Record the start of email processing.
        
        Args:
            request: Email request payload
            processing_context: Additional context information
            
        Returns:
            Processing context dictionary for use throughout processing
        """
        context = processing_context or {}
        context.update({
            'processing_started_at': logger.handlers[0].format(
                logger.makeRecord(
                    logger.name, logging.INFO, __file__, 0, 
                    "Processing started", (), None
                )
            ) if logger.handlers else None,
            'sender_email': request.sender_email,
            'subject': request.subject[:100] if request.subject else None,
            'has_attachments': len(request.attachments) > 0 if request.attachments else False
        })
        
        logger.info(f"Started processing email from {request.sender_email}")
        return context
    
    async def record_successful_processing(
        self,
        request: EmailPayload,
        extracted_data: ExtractedData,
        zoho_result: Union[ProcessingResult, Dict[str, Any]],
        processing_context: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Record successful email processing completion.
        
        Args:
            request: Original email request
            extracted_data: AI-extracted data
            zoho_result: Zoho integration result
            processing_context: Processing context from start
            
        Returns:
            Processing record ID if stored
        """
        record_id = None
        
        if self.storage_manager:
            record_id = await self.storage_manager.store_successful_processing(
                request=request,
                extracted_data=extracted_data,
                zoho_result=zoho_result
            )
        
        if self.event_tracker:
            self.event_tracker.track_success()
        
        logger.info(f"Recorded successful processing for {request.sender_email}")
        return record_id
    
    async def record_processing_error(
        self,
        request: EmailPayload,
        error_message: str,
        extracted_data: Optional[ExtractedData] = None,
        processing_context: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Record failed email processing.
        
        Args:
            request: Original email request
            error_message: Error description
            extracted_data: Partial extracted data if available
            processing_context: Processing context from start
            
        Returns:
            Processing record ID if stored
        """
        record_id = None
        
        if self.storage_manager:
            record_id = await self.storage_manager.store_error_processing(
                request=request,
                error_message=error_message,
                extracted_data=extracted_data
            )
        
        if self.event_tracker:
            self.event_tracker.track_error()
        
        logger.error(f"Recorded processing error for {request.sender_email}: {error_message}")
        return record_id
    
    async def record_duplicate_processing(
        self,
        request: EmailPayload,
        extracted_data: ExtractedData,
        existing_zoho_ids: Optional[Dict[str, str]] = None,
        processing_context: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Record duplicate email processing event.
        
        Args:
            request: Original email request
            extracted_data: AI-extracted data
            existing_zoho_ids: Found existing Zoho IDs
            processing_context: Processing context from start
            
        Returns:
            Processing record ID if stored
        """
        record_id = None
        
        if self.storage_manager:
            record_id = await self.storage_manager.store_duplicate_processing(
                request=request,
                extracted_data=extracted_data,
                existing_zoho_ids=existing_zoho_ids
            )
        
        if self.event_tracker:
            self.event_tracker.track_duplicate()
        
        logger.info(f"Recorded duplicate processing for {request.sender_email}")
        return record_id
    
    async def record_dry_run_processing(
        self,
        request: EmailPayload,
        extracted_data: ExtractedData,
        processing_context: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Record dry-run processing event.
        
        Args:
            request: Original email request
            extracted_data: AI-extracted data
            processing_context: Processing context from start
            
        Returns:
            Processing record ID if stored
        """
        record_id = None
        
        if self.storage_manager:
            record_id = await self.storage_manager.store_dry_run_processing(
                request=request,
                extracted_data=extracted_data
            )
        
        if self.event_tracker:
            self.event_tracker.track_dry_run()
        
        logger.info(f"Recorded dry-run processing for {request.sender_email}")
        return record_id
    
    async def record_user_correction_processing(
        self,
        request: EmailPayload,
        original_extraction: Dict[str, Any],
        corrected_extraction: ExtractedData,
        zoho_result: Union[ProcessingResult, Dict[str, Any]],
        processing_context: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Record processing with user corrections applied.
        
        Args:
            request: Original email request
            original_extraction: Original AI extraction
            corrected_extraction: User-corrected data
            zoho_result: Zoho integration result
            processing_context: Processing context from start
            
        Returns:
            Processing record ID if stored
        """
        record_id = None
        
        if self.storage_manager:
            record_id = await self.storage_manager.store_user_correction_processing(
                request=request,
                original_extraction=original_extraction,
                corrected_extraction=corrected_extraction,
                zoho_result=zoho_result
            )
        
        if self.event_tracker:
            self.event_tracker.track_user_correction()
        
        logger.info(f"Recorded user-corrected processing for {request.sender_email}")
        return record_id
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get current processing statistics.
        
        Returns:
            Dictionary of processing statistics and status
        """
        stats = {
            'storage_available': self.storage_manager is not None,
            'tracking_available': self.event_tracker is not None,
            'session_stats': {}
        }
        
        if self.event_tracker:
            stats['session_stats'] = self.event_tracker.get_session_stats()
        
        return stats


# Convenience functions for easy integration

async def initialize_processing_integration(app_state) -> ProcessingIntegrationHelper:
    """
    Initialize processing integration helper.
    
    Args:
        app_state: FastAPI app.state object
        
    Returns:
        Configured processing integration helper
    """
    helper = ProcessingIntegrationHelper(app_state)
    
    # Test storage availability
    if helper.storage_manager:
        logger.info("Processing storage integration initialized")
    else:
        logger.warning("Processing storage not available - continuing without storage")
    
    return helper


async def record_processing_event(
    helper: ProcessingIntegrationHelper,
    event_type: str,
    request: EmailPayload,
    **kwargs
) -> Optional[str]:
    """
    Generic function to record any type of processing event.
    
    Args:
        helper: Processing integration helper
        event_type: Type of event (success, error, duplicate, dry_run, user_corrected)
        request: Email request payload
        **kwargs: Additional arguments specific to event type
        
    Returns:
        Processing record ID if stored
    """
    if event_type == "success":
        return await helper.record_successful_processing(
            request=request,
            extracted_data=kwargs.get('extracted_data'),
            zoho_result=kwargs.get('zoho_result'),
            processing_context=kwargs.get('processing_context')
        )
    elif event_type == "error":
        return await helper.record_processing_error(
            request=request,
            error_message=kwargs.get('error_message', 'Unknown error'),
            extracted_data=kwargs.get('extracted_data'),
            processing_context=kwargs.get('processing_context')
        )
    elif event_type == "duplicate":
        return await helper.record_duplicate_processing(
            request=request,
            extracted_data=kwargs.get('extracted_data'),
            existing_zoho_ids=kwargs.get('existing_zoho_ids'),
            processing_context=kwargs.get('processing_context')
        )
    elif event_type == "dry_run":
        return await helper.record_dry_run_processing(
            request=request,
            extracted_data=kwargs.get('extracted_data'),
            processing_context=kwargs.get('processing_context')
        )
    elif event_type == "user_corrected":
        return await helper.record_user_correction_processing(
            request=request,
            original_extraction=kwargs.get('original_extraction'),
            corrected_extraction=kwargs.get('corrected_extraction'),
            zoho_result=kwargs.get('zoho_result'),
            processing_context=kwargs.get('processing_context')
        )
    else:
        logger.error(f"Unknown processing event type: {event_type}")
        return None


def create_simple_processing_wrapper(postgres_client=None):
    """
    Create a simple wrapper for processing storage operations.
    
    This can be used when you don't have access to the full app state
    but want to record processing events.
    
    Args:
        postgres_client: PostgreSQL client instance
        
    Returns:
        Simple storage functions
    """
    storage_manager = EmailProcessingStorageManager(postgres_client) if postgres_client else None
    
    async def store_success(request, extracted_data, zoho_result):
        if storage_manager:
            return await storage_manager.store_successful_processing(
                request, extracted_data, zoho_result
            )
        return None
    
    async def store_error(request, error_message, extracted_data=None):
        if storage_manager:
            return await storage_manager.store_error_processing(
                request, error_message, extracted_data
            )
        return None
    
    async def store_duplicate(request, extracted_data, existing_zoho_ids=None):
        if storage_manager:
            return await storage_manager.store_duplicate_processing(
                request, extracted_data, existing_zoho_ids
            )
        return None
    
    return {
        'store_success': store_success,
        'store_error': store_error,
        'store_duplicate': store_duplicate,
        'available': storage_manager is not None
    }