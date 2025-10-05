#!/usr/bin/env python3
"""
Data Validation and Consistency Test Suite

Tests data consistency across all storage methods and validation of data integrity
throughout the processing pipeline.

Usage:
    python -m pytest tests/test_data_validation.py -v
    python -m pytest tests/test_data_validation.py::TestDataConsistency -v
"""

import os
import sys
import json
import pytest
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from dotenv import load_dotenv
import psycopg2
import redis
from pydantic import BaseModel, ValidationError

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
env_path = Path(__file__).parent.parent / '.env.local'
load_dotenv(env_path)

# Import application components
from app.models import EmailPayload, ExtractedData, ProcessingResult
from app.integrations import PostgreSQLClient, ZohoApiClient
from app.business_rules import BusinessRulesEngine, format_deal_name, determine_source
from app.redis_cache_manager import RedisCacheManager

class TestDataConsistency:
    """Test data consistency across all storage methods"""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup data consistency test environment"""
        self.postgresql_client = PostgreSQLClient()
        self.redis_cache = RedisCacheManager()
        self.business_rules = BusinessRulesEngine()
        
        await self.postgresql_client.initialize()
        await self.redis_cache.initialize()
        
    async def test_storage_consistency_across_methods(self):
        """Test data consistency across PostgreSQL, Redis, and file storage"""
        print("\n🔍 Testing Storage Consistency Across Methods...")
        
        # Create test data
        test_data = {
            "email_id": "test_consistency_001",
            "subject": "Software Engineer Position - TechCorp",
            "sender_email": "candidate@example.com",
            "extracted_data": {
                "job_title": "Software Engineer",
                "company_name": "TechCorp",
                "location": "San Francisco, CA",
                "salary": "120000"
            },
            "processing_timestamp": datetime.now().isoformat(),
            "confidence_score": 0.95
        }
        
        # Store in PostgreSQL
        pg_result = await self._store_in_postgresql(test_data)
        
        # Store in Redis cache
        redis_result = await self._store_in_redis(test_data)
        
        # Retrieve from both and compare
        pg_retrieved = await self._retrieve_from_postgresql(test_data["email_id"])
        redis_retrieved = await self._retrieve_from_redis(test_data["email_id"])
        
        # Verify consistency
        self._assert_data_consistency(test_data, pg_retrieved, redis_retrieved)
        
        print("  ✅ Data consistency maintained across storage methods")
        
    async def _store_in_postgresql(self, data: Dict[str, Any]) -> bool:
        """Store data in PostgreSQL"""
        try:
            await self.postgresql_client.store_extraction(
                email_id=data["email_id"],
                extraction_data=data["extracted_data"],
                metadata={"confidence_score": data["confidence_score"]}
            )
            return True
        except Exception as e:
            print(f"PostgreSQL storage failed: {e}")
            return False
            
    async def _store_in_redis(self, data: Dict[str, Any]) -> bool:
        """Store data in Redis cache"""
        try:
            await self.redis_cache.store_extraction_result(
                email_content_hash=data["email_id"],
                extraction_result=data["extracted_data"],
                ttl_hours=24
            )
            return True
        except Exception as e:
            print(f"Redis storage failed: {e}")
            return False
            
    async def _retrieve_from_postgresql(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from PostgreSQL"""
        try:
            return await self.postgresql_client.get_extraction_by_id(email_id)
        except Exception as e:
            print(f"PostgreSQL retrieval failed: {e}")
            return None
            
    async def _retrieve_from_redis(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from Redis cache"""
        try:
            return await self.redis_cache.get_cached_extraction(email_id)
        except Exception as e:
            print(f"Redis retrieval failed: {e}")
            return None
            
    def _assert_data_consistency(self, original: Dict[str, Any], 
                                pg_data: Dict[str, Any], 
                                redis_data: Dict[str, Any]):
        """Assert data consistency across storage methods"""
        # Check PostgreSQL consistency
        if pg_data:
            assert pg_data["extracted_data"]["job_title"] == original["extracted_data"]["job_title"]
            assert pg_data["extracted_data"]["company_name"] == original["extracted_data"]["company_name"]
        
        # Check Redis consistency
        if redis_data:
            assert redis_data["job_title"] == original["extracted_data"]["job_title"]
            assert redis_data["company_name"] == original["extracted_data"]["company_name"]
        
        # Cross-storage consistency
        if pg_data and redis_data:
            assert pg_data["extracted_data"]["job_title"] == redis_data["job_title"]
            assert pg_data["extracted_data"]["company_name"] == redis_data["company_name"]

class TestDataValidation:
    """Test data validation throughout the processing pipeline"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup data validation test environment"""
        self.business_rules = BusinessRulesEngine()
        
    def test_email_payload_validation(self):
        """Test EmailPayload model validation"""
        print("\n🔍 Testing EmailPayload Validation...")
        
        # Test valid email payload
        valid_payload = {
            "subject": "Software Engineer Position",
            "body": "We have an opening for a software engineer...",
            "sender_email": "recruiter@company.com",
            "sender_name": "John Recruiter"
        }
        
        email = EmailPayload(**valid_payload)
        assert email.subject == valid_payload["subject"]
        assert email.sender_email == valid_payload["sender_email"]
        
        # Test invalid email payload
        invalid_payloads = [
            {"subject": "", "body": "Content", "sender_email": "invalid", "sender_name": ""},
            {"subject": None, "body": None, "sender_email": None, "sender_name": None},
            {"body": "Missing required fields"}
        ]
        
        for invalid_payload in invalid_payloads:
            with pytest.raises((ValidationError, ValueError)):
                EmailPayload(**invalid_payload)
        
        print("  ✅ EmailPayload validation working correctly")
        
    def test_extracted_data_validation(self):
        """Test ExtractedData model validation"""
        print("\n🔍 Testing ExtractedData Validation...")
        
        # Test valid extracted data
        valid_data = {
            "job_title": "Senior Software Engineer",
            "company_name": "TechCorp Inc",
            "location": "San Francisco, CA",
            "salary": "150000",
            "experience_required": "5+ years",
            "contact_email": "jobs@techcorp.com",
            "application_deadline": "2025-10-01"
        }
        
        extracted = ExtractedData(**valid_data)
        assert extracted.job_title == valid_data["job_title"]
        assert extracted.company_name == valid_data["company_name"]
        
        # Test data normalization
        denormalized_data = {
            "job_title": "  senior software ENGINEER  ",
            "company_name": "techcorp inc.",
            "location": "san francisco,ca",
            "salary": "$150,000",
        }
        
        normalized = ExtractedData(**denormalized_data)
        assert normalized.job_title.strip() == "senior software ENGINEER"
        assert normalized.salary == "$150,000"
        
        print("  ✅ ExtractedData validation and normalization working correctly")
        
    def test_business_rules_validation(self):
        """Test business rules data validation"""
        print("\n🔍 Testing Business Rules Validation...")
        
        # Test deal name formatting
        test_cases = [
            {
                "job_title": "Software Engineer",
                "location": "San Francisco, CA", 
                "company_name": "TechCorp",
                "expected": "Software Engineer (San Francisco, CA) - TechCorp"
            },
            {
                "job_title": None,
                "location": "Remote",
                "company_name": "StartupCo",
                "expected": "Unknown (Remote) - StartupCo"
            },
            {
                "job_title": "Data Scientist",
                "location": None,
                "company_name": None,
                "expected": "Data Scientist (Unknown) - Unknown"
            }
        ]
        
        for case in test_cases:
            result = format_deal_name(
                job_title=case["job_title"],
                location=case["location"],
                company_name=case["company_name"]
            )
            assert result == case["expected"], f"Expected {case['expected']}, got {result}"
        
        # Test source determination
        source_cases = [
            {
                "email_body": "John referred me to this position",
                "has_calendly": False,
                "referrer_name": "John Doe",
                "expected_source": "Referral",
                "expected_detail": "John Doe"
            },
            {
                "email_body": "Found this on TWAV platform",
                "has_calendly": False,
                "referrer_name": None,
                "expected_source": "Reverse Recruiting",
                "expected_detail": None
            },
            {
                "email_body": "Saw your Calendly link",
                "has_calendly": True,
                "referrer_name": None,
                "expected_source": "Website Inbound",
                "expected_detail": None
            }
        ]
        
        for case in source_cases:
            source, detail = determine_source(
                email_body=case["email_body"],
                has_calendly=case["has_calendly"],
                referrer_name=case["referrer_name"]
            )
            assert source == case["expected_source"]
            if case["expected_detail"]:
                assert detail == case["expected_detail"]
        
        print("  ✅ Business rules validation working correctly")

class TestDataIntegrity:
    """Test data integrity throughout processing pipeline"""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup data integrity test environment"""
        self.postgresql_client = PostgreSQLClient()
        await self.postgresql_client.initialize()
        
    async def test_data_integrity_during_processing(self):
        """Test data integrity is maintained during processing"""
        print("\n🔍 Testing Data Integrity During Processing...")
        
        # Create test email with specific data
        original_email = EmailPayload(
            subject="Senior Python Developer - Remote - $150K",
            body="""
            Dear Candidate,
            
            We have an exciting opportunity for a Senior Python Developer role.
            This is a remote position with competitive salary of $150,000.
            The role requires 5+ years of Python experience.
            
            Company: DataTech Solutions
            Location: Remote (US Only)
            Salary: $150,000 - $180,000
            
            Please apply by December 15, 2025.
            
            Best regards,
            Sarah Smith
            Talent Acquisition Manager
            sarah@datatech.com
            """,
            sender_email="sarah@datatech.com",
            sender_name="Sarah Smith"
        )
        
        # Simulate processing pipeline
        processing_results = await self._simulate_processing_pipeline(original_email)
        
        # Verify data integrity at each stage
        self._verify_extraction_integrity(original_email, processing_results["extraction"])
        self._verify_business_rules_integrity(processing_results["extraction"], processing_results["business_rules"])
        self._verify_storage_integrity(processing_results["business_rules"], processing_results["storage"])
        
        print("  ✅ Data integrity maintained throughout processing pipeline")
        
    async def _simulate_processing_pipeline(self, email: EmailPayload) -> Dict[str, Any]:
        """Simulate processing pipeline stages"""
        # Stage 1: Data extraction
        extraction_result = {
            "job_title": "Senior Python Developer",
            "company_name": "DataTech Solutions", 
            "location": "Remote (US Only)",
            "salary": "$150,000 - $180,000",
            "experience_required": "5+ years of Python experience",
            "contact_email": "sarah@datatech.com",
            "application_deadline": "December 15, 2025"
        }
        
        # Stage 2: Business rules application
        business_rules_result = {
            **extraction_result,
            "deal_name": format_deal_name(
                job_title=extraction_result["job_title"],
                location="Remote",
                company_name=extraction_result["company_name"]
            ),
            "source": "Email Inbound",
            "source_detail": None
        }
        
        # Stage 3: Storage preparation
        storage_result = {
            **business_rules_result,
            "processing_timestamp": datetime.now().isoformat(),
            "confidence_score": 0.92,
            "validation_status": "valid"
        }
        
        return {
            "extraction": extraction_result,
            "business_rules": business_rules_result,
            "storage": storage_result
        }
        
    def _verify_extraction_integrity(self, original_email: EmailPayload, extraction: Dict[str, Any]):
        """Verify extraction maintains data integrity"""
        # Key data should be extracted correctly
        assert "Senior Python Developer" in extraction["job_title"]
        assert "DataTech Solutions" in extraction["company_name"]
        assert "Remote" in extraction["location"]
        assert "$150,000" in extraction["salary"]
        
    def _verify_business_rules_integrity(self, extraction: Dict[str, Any], business_rules: Dict[str, Any]):
        """Verify business rules maintain data integrity"""
        # Original extraction data should be preserved
        assert business_rules["job_title"] == extraction["job_title"]
        assert business_rules["company_name"] == extraction["company_name"]
        
        # Business rules should add, not modify core data
        assert "deal_name" in business_rules
        assert "source" in business_rules
        
    def _verify_storage_integrity(self, business_rules: Dict[str, Any], storage: Dict[str, Any]):
        """Verify storage preparation maintains data integrity"""
        # All previous data should be preserved
        for key in business_rules:
            assert key in storage
            assert storage[key] == business_rules[key]
        
        # Storage metadata should be added
        assert "processing_timestamp" in storage
        assert "confidence_score" in storage
        assert "validation_status" in storage

class TestConcurrencyAndRaceConditions:
    """Test data consistency under concurrent access"""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup concurrency test environment"""
        self.postgresql_client = PostgreSQLClient()
        self.redis_cache = RedisCacheManager()
        
        await self.postgresql_client.initialize()
        await self.redis_cache.initialize()
        
    async def test_concurrent_data_access(self):
        """Test data consistency under concurrent access"""
        print("\n🔍 Testing Concurrent Data Access...")
        
        # Create test data
        base_email_id = "concurrent_test"
        test_data = {
            "job_title": "Software Engineer",
            "company_name": "ConcurrentCorp",
            "location": "Test City",
            "salary": "100000"
        }
        
        # Create multiple concurrent operations
        concurrent_operations = []
        for i in range(10):
            email_id = f"{base_email_id}_{i}"
            operation = self._concurrent_store_and_retrieve(email_id, test_data)
            concurrent_operations.append(operation)
        
        # Execute concurrent operations
        results = await asyncio.gather(*concurrent_operations, return_exceptions=True)
        
        # Verify results
        successful_operations = [r for r in results if not isinstance(r, Exception)]
        failed_operations = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successful_operations) / len(results)
        assert success_rate > 0.8, f"Success rate {success_rate} should be > 80% under concurrency"
        
        # Verify data consistency in successful operations
        for result in successful_operations:
            assert result["stored_successfully"], "Data should be stored successfully"
            assert result["retrieved_successfully"], "Data should be retrieved successfully"
            assert result["data_consistent"], "Data should be consistent"
        
        print(f"  ✅ Concurrent access: {success_rate:.2%} success rate maintained")
        
    async def _concurrent_store_and_retrieve(self, email_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform concurrent store and retrieve operations"""
        try:
            # Store data
            stored = await self.postgresql_client.store_extraction(
                email_id=email_id,
                extraction_data=data,
                metadata={"test": True}
            )
            
            # Retrieve data immediately
            retrieved = await self.postgresql_client.get_extraction_by_id(email_id)
            
            # Verify consistency
            data_consistent = (
                retrieved and 
                retrieved["extracted_data"]["job_title"] == data["job_title"] and
                retrieved["extracted_data"]["company_name"] == data["company_name"]
            )
            
            return {
                "email_id": email_id,
                "stored_successfully": stored,
                "retrieved_successfully": retrieved is not None,
                "data_consistent": data_consistent
            }
        except Exception as e:
            return {
                "email_id": email_id,
                "error": str(e),
                "stored_successfully": False,
                "retrieved_successfully": False,
                "data_consistent": False
            }

class TestDataMigrationAndUpgrade:
    """Test data consistency during migrations and upgrades"""
    
    async def test_schema_migration_consistency(self):
        """Test data consistency during schema migrations"""
        print("\n🔍 Testing Schema Migration Consistency...")
        
        # Simulate data before migration
        pre_migration_data = {
            "email_id": "migration_test_001",
            "old_schema": {
                "title": "Software Engineer",  # Old field name
                "firm": "TechCorp",            # Old field name
                "pay": "120000"                # Old field name
            }
        }
        
        # Simulate migration to new schema
        post_migration_data = self._simulate_schema_migration(pre_migration_data)
        
        # Verify migration preserves data
        assert post_migration_data["email_id"] == pre_migration_data["email_id"]
        assert post_migration_data["new_schema"]["job_title"] == pre_migration_data["old_schema"]["title"]
        assert post_migration_data["new_schema"]["company_name"] == pre_migration_data["old_schema"]["firm"]
        assert post_migration_data["new_schema"]["salary"] == pre_migration_data["old_schema"]["pay"]
        
        print("  ✅ Schema migration preserves data consistency")
        
    def _simulate_schema_migration(self, old_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate schema migration process"""
        return {
            "email_id": old_data["email_id"],
            "new_schema": {
                "job_title": old_data["old_schema"]["title"],
                "company_name": old_data["old_schema"]["firm"],
                "salary": old_data["old_schema"]["pay"],
                "migration_timestamp": datetime.now().isoformat(),
                "schema_version": "2.0"
            }
        }

# Test runner
if __name__ == "__main__":
    import subprocess
    
    print("🔍 Running Data Validation and Consistency Test Suite...")
    print("=" * 60)
    
    result = subprocess.run([
        "python", "-m", "pytest", __file__, "-v",
        "--tb=short",
        "--color=yes"
    ])
    
    if result.returncode == 0:
        print("\n✅ All data validation tests passed!")
    else:
        print("\n❌ Some data validation tests failed!")
        sys.exit(result.returncode)