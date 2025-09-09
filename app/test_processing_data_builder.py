"""
Test Processing Data Builder

This file contains tests to validate that the processing data construction
matches the PostgreSQL schema requirements and handles all edge cases properly.
"""

import json
import pytest
from datetime import datetime
from typing import Dict, Any

from .models import EmailPayload, ExtractedData, ProcessingResult
from .processing_data_builder import (
    ProcessingDataBuilder,
    ProcessingDataValidator,
    create_processing_data,
    create_error_processing_data,
    create_duplicate_processing_data
)


def create_sample_email_request() -> EmailPayload:
    """Create a sample email request for testing."""
    return EmailPayload(
        sender_email="candidate@company.com",
        sender_name="John Candidate",
        subject="Interested in Financial Advisor Position",
        body="I am interested in the financial advisor position at your firm...",
        internet_message_id="<msg-123@outlook.com>",
        reply_to="john.candidate@personalmail.com"
    )


def create_sample_extracted_data() -> ExtractedData:
    """Create sample extracted data for testing."""
    return ExtractedData(
        candidate_name="John Candidate",
        job_title="Senior Financial Advisor",
        location="Fort Wayne, Indiana",
        company_name="ABC Wealth Management",
        referrer_name="Jane Referrer",
        referrer_email="jane@referrer.com",
        email="john.candidate@personalmail.com",
        website="https://abcwealth.com",
        phone="555-123-4567",
        linkedin_url="https://linkedin.com/in/johncandidate",
        notes="Experienced advisor looking for new opportunities",
        industry="Financial Services",
        source="Referral",
        source_detail="Jane Referrer"
    )


def create_sample_zoho_result() -> Dict[str, Any]:
    """Create sample Zoho result for testing."""
    return {
        "deal_id": "123456789",
        "account_id": "987654321",
        "contact_id": "456789123",
        "deal_name": "Senior Financial Advisor (Fort Wayne, Indiana) - ABC Wealth Management",
        "primary_email": "john.candidate@personalmail.com"
    }


class TestProcessingDataBuilder:
    """Test cases for ProcessingDataBuilder class."""
    
    def test_sanitize_string_basic(self):
        """Test basic string sanitization."""
        builder = ProcessingDataBuilder()
        
        # Normal string
        result = builder.sanitize_string("Normal text")
        assert result == "Normal text"
        
        # String with null bytes
        result = builder.sanitize_string("Text\x00with\x00nulls")
        assert result == "Textwithulls"
        
        # String with control characters
        result = builder.sanitize_string("Text\x01\x02with\x03controls")
        assert result == "Textwithcontrols"
        
        # None input
        result = builder.sanitize_string(None)
        assert result is None
        
        # Empty string
        result = builder.sanitize_string("")
        assert result is None
    
    def test_sanitize_string_length_limit(self):
        """Test string length limiting."""
        builder = ProcessingDataBuilder()
        
        long_string = "A" * 100
        result = builder.sanitize_string(long_string, max_length=50)
        assert len(result) == 50
        assert result == "A" * 50
    
    def test_generate_email_body_hash(self):
        """Test email body hash generation."""
        builder = ProcessingDataBuilder()
        
        # Normal body
        body = "This is an email body with some content."
        hash1 = builder.generate_email_body_hash(body)
        assert len(hash1) == 64  # SHA-256 hex length
        
        # Same content should generate same hash
        hash2 = builder.generate_email_body_hash(body)
        assert hash1 == hash2
        
        # Different whitespace should generate same hash (normalization)
        body_with_whitespace = "This  is   an    email\n\nbody   with\tsome content."
        hash3 = builder.generate_email_body_hash(body_with_whitespace)
        assert hash1 == hash3
        
        # Empty body
        empty_hash = builder.generate_email_body_hash("")
        assert empty_hash == ""
    
    def test_determine_primary_email(self):
        """Test primary email determination logic."""
        builder = ProcessingDataBuilder()
        
        # Normal request with reply_to
        request = EmailPayload(
            sender_email="sender@company.com",
            subject="Test",
            body="Test",
            reply_to="candidate@personalmail.com"
        )
        primary = builder.determine_primary_email(request)
        assert primary == "candidate@personalmail.com"
        
        # Request without reply_to
        request_no_reply = EmailPayload(
            sender_email="sender@company.com",
            subject="Test",
            body="Test"
        )
        primary = builder.determine_primary_email(request_no_reply)
        assert primary == "sender@company.com"
        
        # Request with invalid reply_to
        request_invalid_reply = EmailPayload(
            sender_email="sender@company.com", 
            subject="Test",
            body="Test",
            reply_to="invalid-email"
        )
        primary = builder.determine_primary_email(request_invalid_reply)
        assert primary == "sender@company.com"
    
    def test_extract_deal_name(self):
        """Test deal name extraction and formatting."""
        builder = ProcessingDataBuilder()
        
        # Complete data
        data = {
            "job_title": "Senior Financial Advisor",
            "location": "Fort Wayne, Indiana",
            "company_name": "ABC Wealth Management"
        }
        deal_name = builder.extract_deal_name(data)
        expected = "Senior Financial Advisor (Fort Wayne, Indiana) - ABC Wealth Management"
        assert deal_name == expected
        
        # Missing data should use "Unknown"
        incomplete_data = {"job_title": "Advisor"}
        deal_name = builder.extract_deal_name(incomplete_data)
        expected = "Advisor (Unknown) - Unknown"
        assert deal_name == expected
        
        # ExtractedData model
        extracted = ExtractedData(
            job_title="Financial Planner",
            location="Chicago, IL", 
            company_name="XYZ Financial"
        )
        deal_name = builder.extract_deal_name(extracted)
        expected = "Financial Planner (Chicago, IL) - XYZ Financial"
        assert deal_name == expected
    
    def test_build_processing_data_complete(self):
        """Test building complete processing data."""
        request = create_sample_email_request()
        extracted_data = create_sample_extracted_data()
        zoho_result = create_sample_zoho_result()
        
        processing_data = ProcessingDataBuilder.build_processing_data(
            request=request,
            extracted_data=extracted_data,
            zoho_result=zoho_result,
            processing_status="success"
        )
        
        # Validate all required fields are present
        required_fields = [
            'internet_message_id', 'sender_email', 'reply_to_email', 'primary_email',
            'subject', 'zoho_deal_id', 'zoho_account_id', 'zoho_contact_id',
            'deal_name', 'company_name', 'contact_name', 'processing_status',
            'error_message', 'raw_extracted_data', 'email_body_hash'
        ]
        
        for field in required_fields:
            assert field in processing_data, f"Missing required field: {field}"
        
        # Validate specific values
        assert processing_data['sender_email'] == "candidate@company.com"
        assert processing_data['reply_to_email'] == "john.candidate@personalmail.com"
        assert processing_data['primary_email'] == "john.candidate@personalmail.com"
        assert processing_data['processing_status'] == "success"
        assert processing_data['zoho_deal_id'] == "123456789"
        assert processing_data['contact_name'] == "John Candidate"
        assert processing_data['company_name'] == "ABC Wealth Management"
        
        # Validate raw data is stored
        assert isinstance(processing_data['raw_extracted_data'], dict)
        assert processing_data['raw_extracted_data']['candidate_name'] == "John Candidate"
    
    def test_build_processing_data_minimal(self):
        """Test building processing data with minimal information."""
        request = EmailPayload(
            sender_email="test@example.com",
            subject="Test Email",
            body="Test content"
        )
        
        processing_data = ProcessingDataBuilder.build_processing_data(
            request=request,
            processing_status="error",
            error_message="Processing failed"
        )
        
        # Should have basic fields
        assert processing_data['sender_email'] == "test@example.com"
        assert processing_data['primary_email'] == "test@example.com"
        assert processing_data['processing_status'] == "error"
        assert processing_data['error_message'] == "Processing failed"
        assert processing_data['zoho_deal_id'] is None
        assert processing_data['raw_extracted_data'] == {}
    
    def test_validation_catches_issues(self):
        """Test that validation catches data issues."""
        builder = ProcessingDataBuilder()
        
        # Test with invalid data
        invalid_data = {
            'sender_email': 'a' * 300,  # Too long
            'processing_status': 'success',
            'raw_extracted_data': "not_a_dict",  # Wrong type
            'email_body_hash': 'test'
        }
        
        # Should fix issues during validation
        builder._validate_processing_data(invalid_data)
        
        assert len(invalid_data['sender_email']) <= 255
        assert isinstance(invalid_data['raw_extracted_data'], dict)


class TestProcessingDataValidator:
    """Test cases for ProcessingDataValidator class."""
    
    def test_validate_zoho_ids(self):
        """Test Zoho ID validation."""
        validator = ProcessingDataValidator()
        
        # Valid Zoho IDs
        valid_data = {
            'zoho_deal_id': '123456789',
            'zoho_account_id': '987654321',
            'zoho_contact_id': '456789123'
        }
        results = validator.validate_zoho_ids(valid_data)
        assert all(results.values())
        
        # Invalid Zoho IDs
        invalid_data = {
            'zoho_deal_id': 'abc123',  # Non-numeric
            'zoho_account_id': '987654321',  # Valid
            'zoho_contact_id': ''  # Empty
        }
        results = validator.validate_zoho_ids(invalid_data)
        assert not results['deal_id_valid']
        assert results['account_id_valid']
        assert results['contact_id_valid']  # Empty is valid (None)
    
    def test_check_data_consistency(self):
        """Test data consistency checking."""
        validator = ProcessingDataValidator()
        
        # Consistent data
        good_data = {
            'sender_email': 'sender@company.com',
            'reply_to_email': 'reply@personal.com',
            'processing_status': 'success',
            'error_message': None
        }
        warnings = validator.check_data_consistency(good_data)
        assert len(warnings) == 0
        
        # Inconsistent data
        bad_data = {
            'sender_email': 'same@email.com',
            'reply_to_email': 'same@email.com',  # Same as sender
            'processing_status': 'error',
            'error_message': None  # Missing error message for error status
        }
        warnings = validator.check_data_consistency(bad_data)
        assert len(warnings) >= 1


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def test_create_processing_data(self):
        """Test create_processing_data convenience function."""
        request = create_sample_email_request()
        extracted_data = create_sample_extracted_data()
        zoho_result = create_sample_zoho_result()
        
        processing_data = create_processing_data(
            request=request,
            extracted_data=extracted_data,
            zoho_result=zoho_result,
            processing_status="success"
        )
        
        assert processing_data['processing_status'] == "success"
        assert processing_data['sender_email'] == request.sender_email
        assert processing_data['zoho_deal_id'] == zoho_result['deal_id']
    
    def test_create_error_processing_data(self):
        """Test create_error_processing_data convenience function."""
        request = create_sample_email_request()
        error_msg = "AI extraction failed"
        
        processing_data = create_error_processing_data(
            request=request,
            error_message=error_msg
        )
        
        assert processing_data['processing_status'] == "error"
        assert processing_data['error_message'] == error_msg
        assert processing_data['zoho_deal_id'] is None
    
    def test_create_duplicate_processing_data(self):
        """Test create_duplicate_processing_data convenience function."""
        request = create_sample_email_request()
        extracted_data = create_sample_extracted_data()
        existing_ids = {
            'deal_id': '999888777',
            'account_id': '777888999'
        }
        
        processing_data = create_duplicate_processing_data(
            request=request,
            extracted_data=extracted_data,
            existing_zoho_ids=existing_ids
        )
        
        assert processing_data['processing_status'] == "duplicate"
        assert processing_data['zoho_deal_id'] == '999888777'
        assert processing_data['zoho_account_id'] == '777888999'


def test_schema_compatibility():
    """
    Test that generated data is compatible with PostgreSQL schema.
    
    This validates that all fields match the expected database schema
    from store_email_processing() method.
    """
    request = create_sample_email_request()
    extracted_data = create_sample_extracted_data()
    zoho_result = create_sample_zoho_result()
    
    processing_data = create_processing_data(
        request=request,
        extracted_data=extracted_data,
        zoho_result=zoho_result
    )
    
    # Expected schema fields from integrations.py store_email_processing
    expected_fields = [
        'internet_message_id', 'sender_email', 'reply_to_email', 'primary_email',
        'subject', 'zoho_deal_id', 'zoho_account_id', 'zoho_contact_id',
        'deal_name', 'company_name', 'contact_name', 'processing_status',
        'error_message', 'raw_extracted_data', 'email_body_hash'
    ]
    
    # Check all expected fields are present
    for field in expected_fields:
        assert field in processing_data, f"Missing schema field: {field}"
    
    # Check no extra fields (database won't accept them)
    extra_fields = set(processing_data.keys()) - set(expected_fields)
    assert len(extra_fields) == 0, f"Unexpected extra fields: {extra_fields}"
    
    # Validate field types and constraints
    assert isinstance(processing_data['raw_extracted_data'], dict)
    
    # Validate string length constraints
    string_fields = {
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
    
    for field, max_length in string_fields.items():
        value = processing_data.get(field)
        if value is not None:
            assert len(str(value)) <= max_length, f"Field {field} exceeds max length {max_length}"


if __name__ == "__main__":
    # Run basic tests
    print("Testing Processing Data Builder...")
    
    # Test basic functionality
    request = create_sample_email_request()
    extracted_data = create_sample_extracted_data()
    zoho_result = create_sample_zoho_result()
    
    processing_data = create_processing_data(
        request=request,
        extracted_data=extracted_data,
        zoho_result=zoho_result
    )
    
    print("✓ Basic processing data creation works")
    print(f"✓ Generated {len(processing_data)} fields")
    print(f"✓ Primary email: {processing_data['primary_email']}")
    print(f"✓ Deal name: {processing_data['deal_name']}")
    print(f"✓ Zoho deal ID: {processing_data['zoho_deal_id']}")
    print(f"✓ Raw data fields: {len(processing_data['raw_extracted_data'])}")
    
    # Test error case
    error_data = create_error_processing_data(
        request=request,
        error_message="Test error"
    )
    
    print("✓ Error processing data creation works")
    print(f"✓ Error status: {error_data['processing_status']}")
    print(f"✓ Error message: {error_data['error_message']}")
    
    # Test schema compatibility
    test_schema_compatibility()
    print("✓ Schema compatibility verified")
    
    print("\nProcessing Data Builder is ready for integration!")
    print("Agent #1 can now use this system for comprehensive processing storage.")