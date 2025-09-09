"""
Email Processing Storage Integration

This module provides integration between the main email processing flow and
the processing data storage system, ensuring all email processing events
are properly recorded with comprehensive metadata.
"""

import logging
from typing import Dict, Any, Optional, Union, List
from datetime import datetime

from .models import EmailPayload, ExtractedData, ProcessingResult
from .processing_data_builder import (
    create_processing_data,
    create_error_processing_data,
    create_duplicate_processing_data
)

logger = logging.getLogger(__name__)


class EmailProcessingStorageManager:
    """
    Manager class for handling email processing storage operations.
    
    This class coordinates between the main processing flow and the PostgreSQL
    storage system to ensure comprehensive tracking of all processing events.
    """
    
    def __init__(self, postgres_client=None):
        """
        Initialize storage manager.
        
        Args:
            postgres_client: PostgreSQL client instance for storage operations
        """
        self.postgres_client = postgres_client
    
    async def store_successful_processing(
        self,
        request: EmailPayload,
        extracted_data: ExtractedData,
        zoho_result: Union[ProcessingResult, Dict[str, Any]]
    ) -> Optional[str]:
        """
        Store successful email processing with complete metadata.
        
        Args:
            request: Original email request payload
            extracted_data: AI-extracted data
            zoho_result: Zoho integration result
            
        Returns:
            Processing record ID if stored successfully, None otherwise
        """
        if not self.postgres_client:
            logger.warning("PostgreSQL client not available, skipping storage")
            return None
        
        try:
            # Build comprehensive processing data
            processing_data = create_processing_data(
                request=request,
                extracted_data=extracted_data,
                zoho_result=zoho_result,
                processing_status="success"
            )
            
            # Store in database
            record_id = await self.postgres_client.store_email_processing(processing_data)
            
            logger.info(f"Stored successful processing record {record_id} for {request.sender_email}")
            return record_id
            
        except Exception as e:
            logger.error(f"Failed to store successful processing: {e}")
            return None
    
    async def store_error_processing(
        self,
        request: EmailPayload,
        error_message: str,
        extracted_data: Optional[ExtractedData] = None
    ) -> Optional[str]:
        """
        Store failed email processing with error details.
        
        Args:
            request: Original email request payload
            error_message: Description of the error
            extracted_data: Partial extracted data if available
            
        Returns:
            Processing record ID if stored successfully, None otherwise
        """
        if not self.postgres_client:
            logger.warning("PostgreSQL client not available, skipping error storage")
            return None
        
        try:
            # Build error processing data
            processing_data = create_error_processing_data(
                request=request,
                error_message=error_message,
                extracted_data=extracted_data
            )
            
            # Store in database
            record_id = await self.postgres_client.store_email_processing(processing_data)
            
            logger.info(f"Stored error processing record {record_id} for {request.sender_email}: {error_message}")
            return record_id
            
        except Exception as e:
            logger.error(f"Failed to store error processing: {e}")
            return None
    
    async def store_duplicate_processing(
        self,
        request: EmailPayload,
        extracted_data: ExtractedData,
        existing_zoho_ids: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Store duplicate email processing event.
        
        Args:
            request: Original email request payload
            extracted_data: AI-extracted data
            existing_zoho_ids: Existing Zoho record IDs that were found
            
        Returns:
            Processing record ID if stored successfully, None otherwise
        """
        if not self.postgres_client:
            logger.warning("PostgreSQL client not available, skipping duplicate storage")
            return None
        
        try:
            # Build duplicate processing data
            processing_data = create_duplicate_processing_data(
                request=request,
                extracted_data=extracted_data,
                existing_zoho_ids=existing_zoho_ids
            )
            
            # Store in database
            record_id = await self.postgres_client.store_email_processing(processing_data)
            
            logger.info(f"Stored duplicate processing record {record_id} for {request.sender_email}")
            return record_id
            
        except Exception as e:
            logger.error(f"Failed to store duplicate processing: {e}")
            return None
    
    async def store_dry_run_processing(
        self,
        request: EmailPayload,
        extracted_data: ExtractedData
    ) -> Optional[str]:
        """
        Store dry-run processing event (preview only).
        
        Args:
            request: Original email request payload
            extracted_data: AI-extracted data
            
        Returns:
            Processing record ID if stored successfully, None otherwise
        """
        if not self.postgres_client:
            logger.warning("PostgreSQL client not available, skipping dry-run storage")
            return None
        
        try:
            # Build dry-run processing data (no Zoho IDs)
            processing_data = create_processing_data(
                request=request,
                extracted_data=extracted_data,
                processing_status="dry_run"
            )
            
            # Store in database
            record_id = await self.postgres_client.store_email_processing(processing_data)
            
            logger.info(f"Stored dry-run processing record {record_id} for {request.sender_email}")
            return record_id
            
        except Exception as e:
            logger.error(f"Failed to store dry-run processing: {e}")
            return None
    
    async def store_user_correction_processing(
        self,
        request: EmailPayload,
        original_extraction: Dict[str, Any],
        corrected_extraction: ExtractedData,
        zoho_result: Union[ProcessingResult, Dict[str, Any]]
    ) -> Optional[str]:
        """
        Store processing event with user corrections applied.
        
        Args:
            request: Original email request payload
            original_extraction: Original AI extraction results
            corrected_extraction: User-corrected data
            zoho_result: Zoho integration result
            
        Returns:
            Processing record ID if stored successfully, None otherwise
        """
        if not self.postgres_client:
            logger.warning("PostgreSQL client not available, skipping correction storage")
            return None
        
        try:
            # Build processing data with correction metadata
            processing_data = create_processing_data(
                request=request,
                extracted_data=corrected_extraction,
                zoho_result=zoho_result,
                processing_status="user_corrected"
            )
            
            # Add correction metadata to raw data
            processing_data['raw_extracted_data']['original_ai_extraction'] = original_extraction
            processing_data['raw_extracted_data']['user_corrections_applied'] = True
            processing_data['raw_extracted_data']['correction_timestamp'] = datetime.utcnow().isoformat()
            
            # Store in database
            record_id = await self.postgres_client.store_email_processing(processing_data)
            
            logger.info(f"Stored user-corrected processing record {record_id} for {request.sender_email}")
            return record_id
            
        except Exception as e:
            logger.error(f"Failed to store user correction processing: {e}")
            return None
    
    async def get_processing_history(
        self,
        sender_email: Optional[str] = None,
        internet_message_id: Optional[str] = None,
        limit: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve processing history records.
        
        Args:
            sender_email: Filter by sender email
            internet_message_id: Filter by message ID
            limit: Maximum number of records to return
            
        Returns:
            List of processing history records or None if error
        """
        if not self.postgres_client:
            logger.warning("PostgreSQL client not available")
            return None
        
        try:
            # This would need to be implemented in the PostgreSQL client
            # For now, return empty list
            logger.info(f"Processing history query: email={sender_email}, msg_id={internet_message_id}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to retrieve processing history: {e}")
            return None


class ProcessingEventTracker:
    """
    Event tracker for monitoring processing patterns and performance.
    """
    
    def __init__(self, storage_manager: EmailProcessingStorageManager):
        """
        Initialize event tracker.
        
        Args:
            storage_manager: Storage manager instance
        """
        self.storage_manager = storage_manager
        self.session_stats = {
            'successful_processing': 0,
            'failed_processing': 0,
            'duplicate_processing': 0,
            'dry_run_processing': 0,
            'user_corrections': 0
        }
    
    def track_success(self):
        """Track successful processing event."""
        self.session_stats['successful_processing'] += 1
        logger.debug("Tracked successful processing event")
    
    def track_error(self):
        """Track failed processing event."""
        self.session_stats['failed_processing'] += 1
        logger.debug("Tracked failed processing event")
    
    def track_duplicate(self):
        """Track duplicate processing event."""
        self.session_stats['duplicate_processing'] += 1
        logger.debug("Tracked duplicate processing event")
    
    def track_dry_run(self):
        """Track dry-run processing event."""
        self.session_stats['dry_run_processing'] += 1
        logger.debug("Tracked dry-run processing event")
    
    def track_user_correction(self):
        """Track user correction event."""
        self.session_stats['user_corrections'] += 1
        logger.debug("Tracked user correction event")
    
    def get_session_stats(self) -> Dict[str, int]:
        """
        Get current session statistics.
        
        Returns:
            Dictionary of processing event counts
        """
        return self.session_stats.copy()
    
    def reset_stats(self):
        """Reset session statistics."""
        self.session_stats = {key: 0 for key in self.session_stats}
        logger.info("Reset processing statistics")


def create_storage_manager(postgres_client=None) -> EmailProcessingStorageManager:
    """
    Factory function to create storage manager instance.
    
    Args:
        postgres_client: PostgreSQL client instance
        
    Returns:
        Configured storage manager
    """
    return EmailProcessingStorageManager(postgres_client)


def create_event_tracker(postgres_client=None) -> ProcessingEventTracker:
    """
    Factory function to create event tracker instance.
    
    Args:
        postgres_client: PostgreSQL client instance
        
    Returns:
        Configured event tracker
    """
    storage_manager = create_storage_manager(postgres_client)
    return ProcessingEventTracker(storage_manager)