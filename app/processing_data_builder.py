"""
Processing Data Builder - Comprehensive data object construction for email processing storage

This module provides utilities to build the processing_data dictionary required by
the store_email_processing() method in integrations.py with full metadata and validation.
"""

import json
import hashlib
import logging
from typing import Dict, Any, Optional, Union, List
from datetime import datetime

from .models import EmailPayload, ExtractedData, ProcessingResult

logger = logging.getLogger(__name__)


class ProcessingDataBuilder:
    """
    Builder class for constructing comprehensive processing data objects
    with all required metadata, validation, and sanitization.
    """
    
    @staticmethod
    def sanitize_string(value: Union[str, None], max_length: Optional[int] = None) -> Optional[str]:
        """
        Sanitize and validate string inputs for database storage.
        
        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length (truncate if exceeded)
            
        Returns:
            Sanitized string or None if input was None/empty
        """
        if not value:
            return None
            
        # Remove null bytes and control characters
        sanitized = value.replace('\x00', '').strip()
        
        # Remove control characters except newlines and tabs
        import re
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', sanitized)
        
        # Truncate if too long
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
            logger.warning(f"Truncated string to {max_length} characters")
            
        return sanitized if sanitized else None
    
    @staticmethod
    def generate_email_body_hash(body: str) -> str:
        """
        Generate consistent hash for email body deduplication.
        
        Args:
            body: Email body content
            
        Returns:
            SHA-256 hash of normalized body content
        """
        if not body:
            return ""
            
        # Normalize whitespace and remove common variations
        normalized = ' '.join(body.strip().split())
        
        # Generate hash
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    @staticmethod
    def determine_primary_email(request: EmailPayload) -> str:
        """
        Determine primary email address following business logic.
        
        Args:
            request: Email request payload
            
        Returns:
            Primary email address (Reply-To if exists, otherwise sender)
        """
        # Prefer reply_to if available and valid
        if hasattr(request, 'reply_to') and request.reply_to:
            reply_to = ProcessingDataBuilder.sanitize_string(request.reply_to)
            if reply_to and '@' in reply_to:
                return reply_to
                
        return request.sender_email
    
    @staticmethod
    def extract_deal_name(extracted_data: Union[ExtractedData, Dict[str, Any]]) -> Optional[str]:
        """
        Extract or format deal name from extracted data.
        
        Args:
            extracted_data: Extracted data from AI processing
            
        Returns:
            Formatted deal name or None
        """
        if isinstance(extracted_data, ExtractedData):
            data = extracted_data.model_dump()
        else:
            data = extracted_data or {}
            
        job_title = data.get('job_title') or 'Unknown'
        location = data.get('location') or 'Unknown' 
        company = data.get('company_name') or 'Unknown'
        
        # Follow business rules format: "[Job Title] ([Location]) - [Firm Name]"
        return f"{job_title} ({location}) - {company}"
    
    @classmethod
    def build_processing_data(
        cls,
        request: EmailPayload,
        extracted_data: Optional[Union[ExtractedData, Dict[str, Any]]] = None,
        zoho_result: Optional[Union[ProcessingResult, Dict[str, Any]]] = None,
        processing_status: str = "success",
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build comprehensive processing data dictionary for storage.
        
        Args:
            request: Original email request payload
            extracted_data: AI-extracted data (optional)
            zoho_result: Result from Zoho integration (optional)
            processing_status: Processing status (success, error, duplicate, etc.)
            error_message: Error details if processing failed
            
        Returns:
            Complete processing data dictionary matching PostgreSQL schema
        """
        try:
            # Extract core email metadata
            processing_data = {
                # Email identification and headers
                'internet_message_id': cls.sanitize_string(
                    getattr(request, 'internet_message_id', None), 
                    max_length=255
                ),
                'sender_email': cls.sanitize_string(request.sender_email, max_length=255),
                'reply_to_email': cls.sanitize_string(
                    getattr(request, 'reply_to', None), 
                    max_length=255
                ),
                'primary_email': cls.sanitize_string(
                    cls.determine_primary_email(request), 
                    max_length=255
                ),
                'subject': cls.sanitize_string(request.subject, max_length=500),
                
                # Processing metadata
                'processing_status': processing_status,
                'error_message': cls.sanitize_string(error_message, max_length=1000),
                'email_body_hash': cls.generate_email_body_hash(request.body),
                
                # Initialize Zoho IDs as None
                'zoho_deal_id': None,
                'zoho_account_id': None,
                'zoho_contact_id': None,
                'deal_name': None,
                'company_name': None,
                'contact_name': None,
                'raw_extracted_data': {}
            }
            
            # Process extracted data if provided
            if extracted_data:
                if isinstance(extracted_data, ExtractedData):
                    data_dict = extracted_data.model_dump()
                else:
                    data_dict = extracted_data
                    
                # Store complete raw extracted data
                processing_data['raw_extracted_data'] = data_dict
                
                # Extract specific fields for database columns
                processing_data['deal_name'] = cls.sanitize_string(
                    cls.extract_deal_name(data_dict),
                    max_length=255
                )
                processing_data['company_name'] = cls.sanitize_string(
                    data_dict.get('company_name'),
                    max_length=255
                )
                processing_data['contact_name'] = cls.sanitize_string(
                    data_dict.get('candidate_name'),
                    max_length=255
                )
            
            # Process Zoho result if provided
            if zoho_result:
                if isinstance(zoho_result, ProcessingResult):
                    result_dict = zoho_result.model_dump()
                elif hasattr(zoho_result, '__dict__'):
                    result_dict = zoho_result.__dict__
                else:
                    result_dict = zoho_result
                    
                # Extract Zoho IDs with validation
                processing_data['zoho_deal_id'] = cls.sanitize_string(
                    result_dict.get('deal_id'),
                    max_length=50
                )
                processing_data['zoho_account_id'] = cls.sanitize_string(
                    result_dict.get('account_id'),
                    max_length=50
                )
                processing_data['zoho_contact_id'] = cls.sanitize_string(
                    result_dict.get('contact_id'),
                    max_length=50
                )
                
                # Override deal name if provided by Zoho result
                if result_dict.get('deal_name'):
                    processing_data['deal_name'] = cls.sanitize_string(
                        result_dict['deal_name'],
                        max_length=255
                    )
            
            # Validation and cleanup
            cls._validate_processing_data(processing_data)
            
            logger.info(f"Built processing data for {processing_data['sender_email']}")
            return processing_data
            
        except Exception as e:
            logger.error(f"Error building processing data: {e}")
            # Return minimal safe data structure
            return cls._build_minimal_processing_data(request, str(e))
    
    @classmethod
    def _validate_processing_data(cls, data: Dict[str, Any]) -> None:
        """
        Validate processing data structure and content.
        
        Args:
            data: Processing data dictionary to validate
            
        Raises:
            ValueError: If validation fails
        """
        required_fields = [
            'sender_email', 'primary_email', 'processing_status', 
            'email_body_hash', 'raw_extracted_data'
        ]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate email format for email fields
        email_fields = ['sender_email', 'reply_to_email', 'primary_email']
        for field in email_fields:
            if data.get(field):
                email = data[field]
                if '@' not in email or len(email) > 255:
                    logger.warning(f"Invalid email format in {field}: {email}")
        
        # Ensure raw_extracted_data is a dictionary
        if not isinstance(data['raw_extracted_data'], dict):
            data['raw_extracted_data'] = {}
            
        # Validate string lengths don't exceed database limits
        string_limits = {
            'internet_message_id': 255,
            'sender_email': 255,
            'reply_to_email': 255,
            'primary_email': 255,
            'subject': 500,
            'zoho_deal_id': 50,
            'zoho_account_id': 50,
            'zoho_contact_id': 50,
            'deal_name': 255,
            'company_name': 255,
            'contact_name': 255,
            'error_message': 1000
        }
        
        for field, max_len in string_limits.items():
            if data.get(field) and len(str(data[field])) > max_len:
                logger.warning(f"Field {field} exceeds max length {max_len}, truncating")
                data[field] = str(data[field])[:max_len]
    
    @classmethod
    def _build_minimal_processing_data(cls, request: EmailPayload, error: str) -> Dict[str, Any]:
        """
        Build minimal safe processing data structure for error cases.
        
        Args:
            request: Original email request
            error: Error message
            
        Returns:
            Minimal processing data dictionary
        """
        return {
            'internet_message_id': getattr(request, 'internet_message_id', None),
            'sender_email': cls.sanitize_string(request.sender_email, 255),
            'reply_to_email': cls.sanitize_string(getattr(request, 'reply_to', None), 255),
            'primary_email': cls.sanitize_string(cls.determine_primary_email(request), 255),
            'subject': cls.sanitize_string(request.subject, 500),
            'zoho_deal_id': None,
            'zoho_account_id': None,
            'zoho_contact_id': None,
            'deal_name': None,
            'company_name': None,
            'contact_name': None,
            'processing_status': 'error',
            'error_message': cls.sanitize_string(error, 1000),
            'raw_extracted_data': {},
            'email_body_hash': cls.generate_email_body_hash(request.body or "")
        }


class ProcessingDataValidator:
    """
    Additional validation utilities for processing data integrity.
    """
    
    @staticmethod
    def validate_zoho_ids(data: Dict[str, Any]) -> Dict[str, bool]:
        """
        Validate Zoho ID formats and consistency.
        
        Args:
            data: Processing data dictionary
            
        Returns:
            Dictionary of validation results for each Zoho ID type
        """
        validation_results = {
            'deal_id_valid': True,
            'account_id_valid': True,
            'contact_id_valid': True
        }
        
        # Check Zoho ID formats (typically numeric strings)
        zoho_fields = {
            'zoho_deal_id': 'deal_id_valid',
            'zoho_account_id': 'account_id_valid', 
            'zoho_contact_id': 'contact_id_valid'
        }
        
        for field, result_key in zoho_fields.items():
            value = data.get(field)
            if value:
                # Zoho IDs should be numeric strings
                if not (isinstance(value, str) and value.isdigit()):
                    validation_results[result_key] = False
                    logger.warning(f"Invalid Zoho ID format for {field}: {value}")
        
        return validation_results
    
    @staticmethod
    def check_data_consistency(data: Dict[str, Any]) -> List[str]:
        """
        Check for data consistency issues.
        
        Args:
            data: Processing data dictionary
            
        Returns:
            List of consistency warnings
        """
        warnings = []
        
        # Check email consistency
        if data.get('reply_to_email') and data.get('sender_email'):
            if data['reply_to_email'] == data['sender_email']:
                warnings.append("Reply-To email same as sender email")
        
        # Check if deal name matches extracted data
        raw_data = data.get('raw_extracted_data', {})
        if data.get('deal_name') and raw_data:
            expected_deal = ProcessingDataBuilder.extract_deal_name(raw_data)
            if expected_deal and expected_deal != data['deal_name']:
                warnings.append("Deal name mismatch with extracted data")
        
        # Check processing status consistency
        if data.get('processing_status') == 'error' and not data.get('error_message'):
            warnings.append("Error status without error message")
        
        if data.get('processing_status') == 'success' and data.get('error_message'):
            warnings.append("Success status with error message")
        
        return warnings


def create_processing_data(
    request: EmailPayload,
    extracted_data: Optional[Union[ExtractedData, Dict[str, Any]]] = None,
    zoho_result: Optional[Union[ProcessingResult, Dict[str, Any]]] = None,
    processing_status: str = "success",
    error_message: Optional[str] = None,
    validate_consistency: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to create comprehensive processing data.
    
    Args:
        request: Original email request payload
        extracted_data: AI-extracted data (optional)
        zoho_result: Result from Zoho integration (optional)
        processing_status: Processing status
        error_message: Error details if processing failed
        validate_consistency: Whether to perform consistency validation
        
    Returns:
        Complete processing data dictionary ready for storage
    """
    # Build the processing data
    processing_data = ProcessingDataBuilder.build_processing_data(
        request=request,
        extracted_data=extracted_data,
        zoho_result=zoho_result,
        processing_status=processing_status,
        error_message=error_message
    )
    
    # Perform additional validation if requested
    if validate_consistency:
        validator = ProcessingDataValidator()
        
        # Check Zoho ID validity
        zoho_validation = validator.validate_zoho_ids(processing_data)
        if not all(zoho_validation.values()):
            logger.warning(f"Zoho ID validation issues: {zoho_validation}")
        
        # Check data consistency
        consistency_warnings = validator.check_data_consistency(processing_data)
        if consistency_warnings:
            logger.warning(f"Data consistency warnings: {consistency_warnings}")
    
    return processing_data


def create_error_processing_data(
    request: EmailPayload,
    error_message: str,
    extracted_data: Optional[Union[ExtractedData, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Convenience function to create processing data for error cases.
    
    Args:
        request: Original email request payload
        error_message: Error description
        extracted_data: Partial extracted data if available
        
    Returns:
        Processing data dictionary for error case
    """
    return create_processing_data(
        request=request,
        extracted_data=extracted_data,
        processing_status="error",
        error_message=error_message,
        validate_consistency=False
    )


def create_duplicate_processing_data(
    request: EmailPayload,
    extracted_data: Optional[Union[ExtractedData, Dict[str, Any]]] = None,
    existing_zoho_ids: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Convenience function to create processing data for duplicate cases.
    
    Args:
        request: Original email request payload
        extracted_data: AI-extracted data
        existing_zoho_ids: Existing Zoho record IDs
        
    Returns:
        Processing data dictionary for duplicate case
    """
    # Convert existing IDs to ProcessingResult format
    zoho_result = None
    if existing_zoho_ids:
        zoho_result = {
            'deal_id': existing_zoho_ids.get('deal_id'),
            'account_id': existing_zoho_ids.get('account_id'),
            'contact_id': existing_zoho_ids.get('contact_id'),
            'deal_name': existing_zoho_ids.get('deal_name')
        }
    
    return create_processing_data(
        request=request,
        extracted_data=extracted_data,
        zoho_result=zoho_result,
        processing_status="duplicate",
        error_message=None,
        validate_consistency=True
    )