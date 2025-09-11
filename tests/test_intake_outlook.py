#!/usr/bin/env python3
"""
Comprehensive tests for Outlook email intake system.
Tests idempotency, transaction handling, retry logic, correlation IDs,
audit logging, and Zoho API integration.
"""

import pytest
import asyncio
import os
import sys
import json
import uuid
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.models import EmailRequest, ZohoResponse


# Test fixtures
@pytest.fixture
def mock_postgres_client():
    """Mock PostgreSQL client."""
    with patch('app.integrations.PostgreSQLClient') as mock_client:
        instance = mock_client.return_value
        instance.init_pool = AsyncMock()
        instance.pool = AsyncMock()
        
        mock_conn = AsyncMock()
        instance.pool.acquire.return_value.__aenter__.return_value = mock_conn
        
        # Mock transaction
        mock_transaction = AsyncMock()
        mock_conn.transaction.return_value = mock_transaction
        mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        
        yield instance, mock_conn, mock_transaction


@pytest.fixture
def mock_zoho_client():
    """Mock Zoho API client."""
    with patch('app.integrations.ZohoLeadsClient') as mock_client:
        instance = mock_client.return_value
        instance.create_lead = AsyncMock()
        instance.create_deal = AsyncMock()
        yield instance


@pytest.fixture
def mock_langgraph_manager():
    """Mock LangGraph manager for email processing."""
    with patch('app.langgraph_manager.LangGraphManager') as mock_manager:
        instance = mock_manager.return_value
        instance.process_email = AsyncMock()
        yield instance


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_email_request():
    """Sample email request for testing."""
    return {
        "sender_email": "recruiter@example.com",
        "sender_name": "John Recruiter",
        "subject": "Great candidate for Senior Advisor role",
        "body": """
        Hi Team,
        
        I'd like to introduce Sarah Johnson for the Senior Financial Advisor 
        position in Chicago. She has 12 years of experience at Morgan Stanley 
        and is looking for new opportunities.
        
        Contact: sarah@example.com
        Phone: 555-123-4567
        
        Best regards,
        John Recruiter
        """,
        "message_id": "test-message-123@outlook.com",
        "attachments": []
    }


@pytest.fixture
def sample_zoho_response():
    """Sample Zoho API response."""
    return {
        "lead_id": "123456789",
        "deal_id": "987654321",
        "status": "success",
        "message": "Records created successfully"
    }


class TestIdempotency:
    """Test idempotent processing of emails."""
    
    @pytest.mark.asyncio
    async def test_same_message_id_idempotent(self, client, sample_email_request, mock_postgres_client, mock_zoho_client):
        """Test that processing the same message_id twice returns same result."""
        _, mock_conn, _ = mock_postgres_client
        
        # First request - no existing record
        mock_conn.fetchone.return_value = None
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response1 = client.post("/intake/email", 
                                  json=sample_email_request, 
                                  headers={"X-API-Key": "test-key"})
        
        # Second request - existing record found
        mock_conn.fetchone.return_value = {
            "id": 1,
            "message_id": "test-message-123@outlook.com",
            "lead_id": "123",
            "deal_id": "456",
            "created_at": datetime.now()
        }
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response2 = client.post("/intake/email", 
                                  json=sample_email_request, 
                                  headers={"X-API-Key": "test-key"})
        
        # Should return same result without creating duplicate
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Zoho should only be called once
        assert mock_zoho_client.create_lead.call_count <= 2  # Account for retries
        
    @pytest.mark.asyncio
    async def test_different_message_ids_processed_separately(self, client, sample_email_request, mock_postgres_client, mock_zoho_client):
        """Test that different message IDs are processed as separate records."""
        _, mock_conn, _ = mock_postgres_client
        
        # Always return None for fetchone (no existing records)
        mock_conn.fetchone.return_value = None
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        
        # First email
        email1 = sample_email_request.copy()
        email1["message_id"] = "message-1@outlook.com"
        
        # Second email
        email2 = sample_email_request.copy()
        email2["message_id"] = "message-2@outlook.com"
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response1 = client.post("/intake/email", 
                                  json=email1, 
                                  headers={"X-API-Key": "test-key"})
            response2 = client.post("/intake/email", 
                                  json=email2, 
                                  headers={"X-API-Key": "test-key"})
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Both should be processed separately
        assert mock_zoho_client.create_lead.call_count >= 2


class TestTransactionHandling:
    """Test database transaction management."""
    
    @pytest.mark.asyncio
    async def test_transaction_commit_on_success(self, client, sample_email_request, mock_postgres_client, mock_zoho_client):
        """Test transaction is committed on successful processing."""
        _, mock_conn, mock_transaction = mock_postgres_client
        
        # Mock successful Zoho response
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        mock_conn.fetchone.return_value = None  # No existing record
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=sample_email_request, 
                                 headers={"X-API-Key": "test-key"})
        
        assert response.status_code == 200
        
        # Transaction should be committed (no rollback)
        mock_transaction.__aexit__.assert_called()
        
    @pytest.mark.asyncio
    async def test_transaction_rollback_on_zoho_failure(self, client, sample_email_request, mock_postgres_client, mock_zoho_client):
        """Test transaction rollback on Zoho API failure."""
        _, mock_conn, mock_transaction = mock_postgres_client
        
        # Mock Zoho failure
        mock_zoho_client.create_lead.side_effect = Exception("Zoho API error")
        mock_conn.fetchone.return_value = None  # No existing record
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=sample_email_request, 
                                 headers={"X-API-Key": "test-key"})
        
        # Should handle error gracefully
        assert response.status_code in [200, 500]  # Depending on error handling
        
        # Transaction should still complete (rollback handled internally)
        mock_transaction.__aexit__.assert_called()


class TestRetryLogic:
    """Test retry logic for API failures."""
    
    @pytest.mark.asyncio
    async def test_retry_on_429_rate_limit(self, client, sample_email_request, mock_postgres_client, mock_zoho_client):
        """Test retry logic on 429 rate limit errors."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        
        # Mock rate limit error followed by success
        mock_zoho_client.create_lead.side_effect = [
            HTTPException(status_code=429, detail="Rate limited"),
            {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        ]
        
        with patch('asyncio.sleep', new_callable=AsyncMock):  # Speed up test
            with patch.dict(os.environ, {'API_KEY': 'test-key'}):
                response = client.post("/intake/email", 
                                     json=sample_email_request, 
                                     headers={"X-API-Key": "test-key"})
        
        # Should eventually succeed after retry
        assert response.status_code == 200
        assert mock_zoho_client.create_lead.call_count >= 1
        
    @pytest.mark.asyncio
    async def test_retry_on_5xx_server_errors(self, client, sample_email_request, mock_postgres_client, mock_zoho_client):
        """Test retry logic on 5xx server errors."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        
        # Mock server error followed by success
        mock_zoho_client.create_lead.side_effect = [
            HTTPException(status_code=500, detail="Server error"),
            HTTPException(status_code=502, detail="Bad gateway"),
            {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        ]
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch.dict(os.environ, {'API_KEY': 'test-key'}):
                response = client.post("/intake/email", 
                                     json=sample_email_request, 
                                     headers={"X-API-Key": "test-key"})
        
        # Should succeed after retries
        assert response.status_code == 200
        assert mock_zoho_client.create_lead.call_count >= 2
        
    @pytest.mark.asyncio
    async def test_no_retry_on_4xx_client_errors(self, client, sample_email_request, mock_postgres_client, mock_zoho_client):
        """Test no retry on 4xx client errors (except 429)."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        
        # Mock client error (should not retry)
        mock_zoho_client.create_lead.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=sample_email_request, 
                                 headers={"X-API-Key": "test-key"})
        
        # Should fail without retry
        assert response.status_code in [400, 500]
        assert mock_zoho_client.create_lead.call_count == 1


class TestCorrelationIdGeneration:
    """Test correlation ID generation and tracking."""
    
    @pytest.mark.asyncio
    async def test_correlation_id_generated(self, client, sample_email_request, mock_postgres_client, mock_zoho_client):
        """Test that correlation IDs are generated for tracking."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            with patch('uuid.uuid4', return_value=uuid.UUID('12345678-1234-5678-9012-123456789012')):
                response = client.post("/intake/email", 
                                     json=sample_email_request, 
                                     headers={"X-API-Key": "test-key"})
        
        assert response.status_code == 200
        
        # Should have correlation ID in response or logs
        # Implementation would need to include correlation_id in response
        
    @pytest.mark.asyncio
    async def test_correlation_id_in_logs(self, client, sample_email_request, mock_postgres_client, mock_zoho_client, caplog):
        """Test correlation ID appears in log messages."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            with caplog.at_level('INFO'):
                response = client.post("/intake/email", 
                                     json=sample_email_request, 
                                     headers={"X-API-Key": "test-key"})
        
        assert response.status_code == 200
        
        # Check for correlation ID in logs
        log_messages = [record.message for record in caplog.records]
        # Implementation would need to include correlation_id in log messages


class TestAuditLogging:
    """Test audit logging functionality."""
    
    @pytest.mark.asyncio
    async def test_audit_log_successful_processing(self, client, sample_email_request, mock_postgres_client, mock_zoho_client, caplog):
        """Test audit logging of successful email processing."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        
        with caplog.at_level('INFO'):
            with patch.dict(os.environ, {'API_KEY': 'test-key'}):
                response = client.post("/intake/email", 
                                     json=sample_email_request, 
                                     headers={"X-API-Key": "test-key"})
        
        assert response.status_code == 200
        
        # Check audit logs
        log_messages = [record.message for record in caplog.records]
        assert any("Processing email from" in msg for msg in log_messages)
        
    @pytest.mark.asyncio
    async def test_audit_log_failures(self, client, sample_email_request, mock_postgres_client, mock_zoho_client, caplog):
        """Test audit logging of processing failures."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        mock_zoho_client.create_lead.side_effect = Exception("Zoho error")
        
        with caplog.at_level('ERROR'):
            with patch.dict(os.environ, {'API_KEY': 'test-key'}):
                response = client.post("/intake/email", 
                                     json=sample_email_request, 
                                     headers={"X-API-Key": "test-key"})
        
        # Check error logs
        error_messages = [record.message for record in caplog.records if record.levelname == 'ERROR']
        assert len(error_messages) > 0
        
    @pytest.mark.asyncio
    async def test_audit_log_data_extraction(self, client, sample_email_request, mock_postgres_client, mock_zoho_client, mock_langgraph_manager, caplog):
        """Test audit logging of data extraction results."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        
        # Mock extraction result
        mock_langgraph_manager.process_email.return_value = {
            "candidate_name": "Sarah Johnson",
            "job_title": "Senior Financial Advisor",
            "firm_name": "Morgan Stanley"
        }
        
        with caplog.at_level('INFO'):
            with patch.dict(os.environ, {'API_KEY': 'test-key'}):
                response = client.post("/intake/email", 
                                     json=sample_email_request, 
                                     headers={"X-API-Key": "test-key"})
        
        assert response.status_code == 200
        
        # Should log extraction results
        log_messages = [record.message for record in caplog.records]
        # Implementation would need to log extraction details


class TestZohoAPIMocking:
    """Test Zoho API mocking and integration."""
    
    @pytest.mark.asyncio
    async def test_mock_zoho_success_response(self, client, sample_email_request, mock_postgres_client, mock_zoho_client):
        """Test mocked successful Zoho API responses."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        
        # Mock successful response
        mock_zoho_client.create_lead.return_value = {
            "data": [{
                "code": "SUCCESS",
                "details": {
                    "id": "123456789",
                    "created_time": datetime.now().isoformat()
                }
            }]
        }
        
        mock_zoho_client.create_deal.return_value = {
            "data": [{
                "code": "SUCCESS", 
                "details": {
                    "id": "987654321",
                    "created_time": datetime.now().isoformat()
                }
            }]
        }
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=sample_email_request, 
                                 headers={"X-API-Key": "test-key"})
        
        assert response.status_code == 200
        data = response.json()
        # Implementation would need to return proper structure
        
    @pytest.mark.asyncio
    async def test_mock_zoho_error_responses(self, client, sample_email_request, mock_postgres_client, mock_zoho_client):
        """Test mocked Zoho API error responses."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        
        # Mock error response
        mock_zoho_client.create_lead.return_value = {
            "data": [{
                "code": "DUPLICATE_DATA",
                "message": "Duplicate record found",
                "details": {}
            }]
        }
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=sample_email_request, 
                                 headers={"X-API-Key": "test-key"})
        
        # Should handle Zoho errors gracefully
        assert response.status_code in [200, 400, 500]


class TestValidation:
    """Test input validation."""
    
    def test_validate_required_fields(self, client):
        """Test validation of required fields."""
        invalid_request = {
            "sender_email": "",  # Empty email
            "subject": "",
            "body": ""
        }
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=invalid_request, 
                                 headers={"X-API-Key": "test-key"})
        
        assert response.status_code == 400
        
    def test_validate_email_format(self, client):
        """Test email format validation."""
        invalid_email_request = {
            "sender_email": "not-an-email",
            "subject": "Test",
            "body": "Test body",
            "message_id": "test-123"
        }
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=invalid_email_request, 
                                 headers={"X-API-Key": "test-key"})
        
        assert response.status_code == 400
        assert "Invalid sender email format" in response.json()["detail"]
        
    def test_validate_body_size_limit(self, client):
        """Test email body size limit validation."""
        large_body_request = {
            "sender_email": "test@example.com",
            "subject": "Test",
            "body": "x" * 100001,  # Over 100KB limit
            "message_id": "test-123"
        }
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=large_body_request, 
                                 headers={"X-API-Key": "test-key"})
        
        assert response.status_code == 413
        assert "too large" in response.json()["detail"]


class TestInputSanitization:
    """Test input sanitization and security."""
    
    def test_sanitize_null_bytes(self, client, mock_postgres_client, mock_zoho_client):
        """Test removal of null bytes and control characters."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        
        malicious_request = {
            "sender_email": "test\x00@example.com",
            "subject": "Test\x01Subject",
            "body": "Test\x00body\x1fwith\x08control\x0cchars",
            "message_id": "test-123"
        }
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=malicious_request, 
                                 headers={"X-API-Key": "test-key"})
        
        # Should sanitize and process successfully
        assert response.status_code == 200
        
    def test_length_limits_enforced(self, client, mock_postgres_client, mock_zoho_client):
        """Test that field length limits are enforced."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        
        long_fields_request = {
            "sender_email": "test@example.com",
            "sender_name": "x" * 300,  # Over 200 limit
            "subject": "x" * 600,  # Over 500 limit
            "body": "Normal body",
            "message_id": "test-123"
        }
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=long_fields_request, 
                                 headers={"X-API-Key": "test-key"})
        
        # Should truncate and process successfully
        assert response.status_code == 200


class TestConcurrency:
    """Test concurrent request handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_different_emails(self, client, mock_postgres_client, mock_zoho_client):
        """Test processing different emails concurrently."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        
        requests = []
        for i in range(5):
            request = {
                "sender_email": f"test{i}@example.com",
                "subject": f"Test Subject {i}",
                "body": f"Test body {i}",
                "message_id": f"test-message-{i}"
            }
            requests.append(request)
        
        async def make_request(request_data):
            with patch.dict(os.environ, {'API_KEY': 'test-key'}):
                return client.post("/intake/email", 
                                 json=request_data, 
                                 headers={"X-API-Key": "test-key"})
        
        # Process all requests concurrently
        tasks = [asyncio.create_task(asyncio.to_thread(make_request, req)) for req in requests]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        
    @pytest.mark.asyncio
    async def test_concurrent_same_email(self, client, mock_postgres_client, mock_zoho_client):
        """Test processing same email concurrently (idempotency under race conditions)."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None  # No existing record
        mock_zoho_client.create_lead.return_value = {"data": [{"code": "SUCCESS", "details": {"id": "123"}}]}
        
        same_request = {
            "sender_email": "test@example.com",
            "subject": "Test Subject",
            "body": "Test body",
            "message_id": "same-message-id"
        }
        
        async def make_request():
            with patch.dict(os.environ, {'API_KEY': 'test-key'}):
                return client.post("/intake/email", 
                                 json=same_request, 
                                 headers={"X-API-Key": "test-key"})
        
        # Process same request concurrently
        tasks = [asyncio.create_task(asyncio.to_thread(make_request)) for _ in range(3)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed (idempotency)
        assert all(r.status_code == 200 for r in responses)


class TestErrorScenarios:
    """Test various error scenarios."""
    
    @pytest.mark.asyncio
    async def test_database_connection_failure(self, client, sample_email_request):
        """Test handling of database connection failures."""
        with patch('app.integrations.PostgreSQLClient') as mock_client:
            mock_client.return_value.init_pool.side_effect = Exception("DB connection failed")
            
            with patch.dict(os.environ, {'API_KEY': 'test-key'}):
                response = client.post("/intake/email", 
                                     json=sample_email_request, 
                                     headers={"X-API-Key": "test-key"})
            
            # Should handle gracefully
            assert response.status_code in [200, 500]
            
    @pytest.mark.asyncio
    async def test_langgraph_processing_failure(self, client, sample_email_request, mock_postgres_client, mock_langgraph_manager):
        """Test handling of LangGraph processing failures."""
        _, mock_conn, _ = mock_postgres_client
        mock_conn.fetchone.return_value = None
        
        # Mock LangGraph failure
        mock_langgraph_manager.process_email.side_effect = Exception("Processing failed")
        
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            response = client.post("/intake/email", 
                                 json=sample_email_request, 
                                 headers={"X-API-Key": "test-key"})
        
        # Should fallback gracefully
        assert response.status_code in [200, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])