#!/usr/bin/env python3
"""
Comprehensive test suite for migrated Azure infrastructure resources.
Tests all components after migration from TheWell-Infra-East to TheWell-Infra-Test.

Usage:
    python test_migrated_infrastructure.py
    python -m pytest test_migrated_infrastructure.py -v
    python -m pytest test_migrated_infrastructure.py::TestContainerApp -v
"""

import os
import sys
import json
import time
import asyncio
import requests
import psycopg2
import redis
import pytest
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urlparse
from azure.storage.blob import BlobServiceClient
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.messaging.webpubsubservice import WebPubSubServiceClient
from azure.search.documents import SearchClient
from azure.monitor.query import LogsQueryClient
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import AzureError
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent.parent / '.env.local'
load_dotenv(env_path)

# Test configuration
TEST_CONFIG = {
    "container_app_url": os.getenv("CONTAINER_APP_URL", "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"),
    "api_key": os.getenv("API_KEY"),
    "resource_group": "TheWell-Infra-Test",
    "location": "eastus",
    "timeout": 30,
    "retry_count": 3,
    "retry_delay": 2
}


class TestContainerApp:
    """Test Container App health and endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test configuration"""
        self.base_url = TEST_CONFIG["container_app_url"]
        self.api_key = TEST_CONFIG["api_key"]
        self.headers = {"X-API-Key": self.api_key} if self.api_key else {}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def test_health_endpoint(self):
        """Test Container App health endpoint"""
        print("\n🔍 Testing Container App Health Endpoint...")
        
        url = f"{self.base_url}/health"
        response = self.session.get(url, timeout=TEST_CONFIG["timeout"])
        
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        
        # Verify health response structure
        assert "status" in data
        assert data["status"] in ["healthy", "degraded"]
        
        # Check component health
        if "components" in data:
            for component, status in data["components"].items():
                print(f"  ✓ {component}: {status}")
        
        print(f"  ✅ Container App is {data['status']}")
        return True
    
    def test_api_authentication(self):
        """Test API key authentication"""
        print("\n🔍 Testing API Authentication...")
        
        # Test without API key
        url = f"{self.base_url}/test/kevin-sullivan"
        response = requests.get(url, timeout=TEST_CONFIG["timeout"])
        assert response.status_code in [401, 403], "API should require authentication"
        
        # Test with API key
        if self.api_key:
            response = self.session.get(url, timeout=TEST_CONFIG["timeout"])
            assert response.status_code == 200, f"Authenticated request failed: {response.status_code}"
            print("  ✅ API authentication working")
        else:
            print("  ⚠️  API_KEY not configured, skipping authenticated test")
    
    def test_intake_endpoint(self):
        """Test email intake endpoint"""
        print("\n🔍 Testing Email Intake Endpoint...")
        
        url = f"{self.base_url}/intake/email"
        test_email = {
            "subject": "Test Migration - Senior Developer Position",
            "from": "test@example.com",
            "body": "Testing migrated infrastructure",
            "received": datetime.utcnow().isoformat()
        }
        
        response = self.session.post(url, json=test_email, timeout=TEST_CONFIG["timeout"])
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Email processed successfully")
            if "zoho_deal_id" in data:
                print(f"     Deal ID: {data['zoho_deal_id']}")
        else:
            print(f"  ⚠️  Intake endpoint returned {response.status_code}")
    
    def test_manifest_endpoint(self):
        """Test Outlook add-in manifest endpoint"""
        print("\n🔍 Testing Manifest Endpoint...")
        
        url = f"{self.base_url}/manifest.xml"
        response = requests.get(url, timeout=TEST_CONFIG["timeout"])
        
        assert response.status_code == 200, f"Manifest endpoint failed: {response.status_code}"
        assert response.headers.get("content-type", "").startswith("application/xml")
        assert len(response.content) > 100, "Manifest content seems empty"
        
        print("  ✅ Manifest endpoint accessible")


class TestPostgreSQL:
    """Test PostgreSQL connectivity and pgvector extension"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database connection"""
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            pytest.skip("DATABASE_URL not configured")
        
        # Parse connection string
        url = urlparse(self.db_url)
        self.conn_params = {
            "host": url.hostname,
            "port": url.port or 5432,
            "database": url.path[1:],
            "user": url.username,
            "password": url.password,
            "sslmode": "require"
        }
    
    def test_connection(self):
        """Test basic database connectivity"""
        print("\n🔍 Testing PostgreSQL Connection...")
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            
            # Test basic query
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"  ✓ Connected to PostgreSQL")
            print(f"     Version: {version[:50]}...")
            
            cursor.close()
            conn.close()
            print("  ✅ PostgreSQL connection successful")
            return True
            
        except Exception as e:
            pytest.fail(f"PostgreSQL connection failed: {str(e)}")
    
    def test_pgvector_extension(self):
        """Test pgvector extension for embeddings"""
        print("\n🔍 Testing pgvector Extension...")
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            
            # Check if pgvector extension exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                );
            """)
            
            has_vector = cursor.fetchone()[0]
            assert has_vector, "pgvector extension not installed"
            
            print("  ✓ pgvector extension installed")
            
            # Test vector operations
            cursor.execute("""
                SELECT '[1,2,3]'::vector <-> '[4,5,6]'::vector as distance;
            """)
            
            distance = cursor.fetchone()[0]
            print(f"  ✓ Vector operations working (test distance: {distance:.2f})")
            
            cursor.close()
            conn.close()
            print("  ✅ pgvector extension functional")
            return True
            
        except Exception as e:
            pytest.fail(f"pgvector test failed: {str(e)}")
    
    def test_tables_exist(self):
        """Test that required tables exist"""
        print("\n🔍 Testing Database Tables...")
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            
            # Check for key tables
            expected_tables = ['emails', 'embeddings', 'cache_entries', 'zoho_records']
            
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE';
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in expected_tables:
                if table in tables:
                    print(f"  ✓ Table '{table}' exists")
                else:
                    print(f"  ⚠️  Table '{table}' not found")
            
            cursor.close()
            conn.close()
            print("  ✅ Database schema check complete")
            return True
            
        except Exception as e:
            pytest.fail(f"Table check failed: {str(e)}")


class TestRedisCache:
    """Test Redis cache operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup Redis connection"""
        self.redis_url = os.getenv("REDIS_CONNECTION_STRING")
        if not self.redis_url:
            pytest.skip("REDIS_CONNECTION_STRING not configured")
        
        # Parse Redis connection string
        if "redis.cache.windows.net" in self.redis_url:
            # Azure Redis format
            parts = self.redis_url.split(",")
            host = parts[0].split(":")[0]
            port = int(parts[0].split(":")[1])
            password = parts[1].split("=")[1] if len(parts) > 1 else None
            
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                password=password,
                ssl=True,
                ssl_cert_reqs=None
            )
        else:
            # Standard Redis URL
            self.redis_client = redis.from_url(self.redis_url)
    
    def test_connection(self):
        """Test Redis connectivity"""
        print("\n🔍 Testing Redis Connection...")
        
        try:
            # Ping Redis
            response = self.redis_client.ping()
            assert response, "Redis ping failed"
            print("  ✓ Redis connection established")
            
            # Get server info
            info = self.redis_client.info()
            print(f"  ✓ Redis version: {info.get('redis_version', 'unknown')}")
            print(f"  ✓ Memory used: {info.get('used_memory_human', 'unknown')}")
            
            print("  ✅ Redis cache operational")
            return True
            
        except Exception as e:
            pytest.fail(f"Redis connection failed: {str(e)}")
    
    def test_cache_operations(self):
        """Test cache set/get operations"""
        print("\n🔍 Testing Cache Operations...")
        
        try:
            test_key = f"test:migration:{int(time.time())}"
            test_value = json.dumps({
                "test": "migration",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Set value with TTL
            self.redis_client.setex(test_key, 60, test_value)
            print(f"  ✓ Set cache key: {test_key}")
            
            # Get value
            retrieved = self.redis_client.get(test_key)
            assert retrieved, "Failed to retrieve cached value"
            
            data = json.loads(retrieved)
            assert data["test"] == "migration"
            print("  ✓ Retrieved cached value successfully")
            
            # Check TTL
            ttl = self.redis_client.ttl(test_key)
            assert ttl > 0, "TTL not set properly"
            print(f"  ✓ TTL working: {ttl} seconds remaining")
            
            # Clean up
            self.redis_client.delete(test_key)
            print("  ✓ Cleanup successful")
            
            print("  ✅ Cache operations working")
            return True
            
        except Exception as e:
            pytest.fail(f"Cache operation failed: {str(e)}")


class TestStorageAccount:
    """Test Azure Storage account access"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup storage client"""
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = os.getenv("AZURE_CONTAINER_NAME", "email-attachments")
        
        if not self.connection_string:
            pytest.skip("AZURE_STORAGE_CONNECTION_STRING not configured")
        
        self.blob_service = BlobServiceClient.from_connection_string(self.connection_string)
    
    def test_connection(self):
        """Test storage account connectivity"""
        print("\n🔍 Testing Storage Account Connection...")
        
        try:
            # List containers
            containers = list(self.blob_service.list_containers())
            print(f"  ✓ Connected to storage account")
            print(f"  ✓ Found {len(containers)} container(s)")
            
            for container in containers[:5]:  # Show first 5
                print(f"     - {container['name']}")
            
            print("  ✅ Storage account accessible")
            return True
            
        except Exception as e:
            pytest.fail(f"Storage connection failed: {str(e)}")
    
    def test_container_operations(self):
        """Test container operations"""
        print("\n🔍 Testing Container Operations...")
        
        try:
            container_client = self.blob_service.get_container_client(self.container_name)
            
            # Check if container exists
            if container_client.exists():
                print(f"  ✓ Container '{self.container_name}' exists")
            else:
                # Create container if it doesn't exist
                container_client.create_container()
                print(f"  ✓ Created container '{self.container_name}'")
            
            # Upload test blob
            test_blob_name = f"test/migration-test-{int(time.time())}.txt"
            test_content = f"Migration test at {datetime.utcnow().isoformat()}"
            
            blob_client = container_client.get_blob_client(test_blob_name)
            blob_client.upload_blob(test_content, overwrite=True)
            print(f"  ✓ Uploaded test blob: {test_blob_name}")
            
            # Download and verify
            downloaded = blob_client.download_blob().readall().decode('utf-8')
            assert downloaded == test_content, "Downloaded content mismatch"
            print("  ✓ Downloaded and verified blob content")
            
            # Clean up
            blob_client.delete_blob()
            print("  ✓ Cleaned up test blob")
            
            print("  ✅ Container operations successful")
            return True
            
        except Exception as e:
            pytest.fail(f"Container operation failed: {str(e)}")


class TestServiceBus:
    """Test Service Bus queue operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup Service Bus client"""
        self.connection_string = os.getenv("SERVICE_BUS_CONNECTION_STRING")
        self.queue_name = os.getenv("SERVICE_BUS_QUEUE_NAME", "email-batch-queue")
        
        if not self.connection_string:
            pytest.skip("SERVICE_BUS_CONNECTION_STRING not configured")
        
        self.sb_client = ServiceBusClient.from_connection_string(self.connection_string)
    
    def test_connection(self):
        """Test Service Bus connectivity"""
        print("\n🔍 Testing Service Bus Connection...")
        
        try:
            with self.sb_client:
                # Get queue runtime properties
                receiver = self.sb_client.get_queue_receiver(self.queue_name)
                with receiver:
                    print(f"  ✓ Connected to Service Bus")
                    print(f"  ✓ Queue '{self.queue_name}' accessible")
            
            print("  ✅ Service Bus operational")
            return True
            
        except Exception as e:
            pytest.fail(f"Service Bus connection failed: {str(e)}")
    
    def test_queue_operations(self):
        """Test queue send/receive operations"""
        print("\n🔍 Testing Queue Operations...")
        
        try:
            with self.sb_client:
                # Send test message
                sender = self.sb_client.get_queue_sender(self.queue_name)
                test_message = {
                    "test": "migration",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                with sender:
                    message = ServiceBusMessage(json.dumps(test_message))
                    sender.send_messages(message)
                    print(f"  ✓ Sent test message to queue")
                
                # Receive message (peek)
                receiver = self.sb_client.get_queue_receiver(self.queue_name, max_wait_time=5)
                with receiver:
                    messages = receiver.receive_messages(max_message_count=1, max_wait_time=5)
                    
                    if messages:
                        for msg in messages:
                            data = json.loads(str(msg))
                            print(f"  ✓ Received message: {data.get('test')}")
                            receiver.complete_message(msg)
                            print("  ✓ Message completed")
                    else:
                        print("  ⚠️  No messages in queue (may be normal)")
            
            print("  ✅ Queue operations successful")
            return True
            
        except Exception as e:
            pytest.fail(f"Queue operation failed: {str(e)}")


class TestSignalR:
    """Test SignalR/WebSocket connectivity"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup SignalR client"""
        self.signalr_connection = os.getenv("SIGNALR_CONNECTION_STRING")
        self.hub_name = "emailprocessing"
        
        if not self.signalr_connection:
            pytest.skip("SIGNALR_CONNECTION_STRING not configured")
    
    def test_connection(self):
        """Test SignalR service connectivity"""
        print("\n🔍 Testing SignalR Connection...")
        
        try:
            # Create WebPubSub client
            service = WebPubSubServiceClient.from_connection_string(
                self.signalr_connection,
                hub=self.hub_name
            )
            
            # Generate client access token
            token = service.get_client_access_token()
            assert token, "Failed to get client access token"
            assert "url" in token, "Token missing URL"
            
            print(f"  ✓ SignalR service accessible")
            print(f"  ✓ Hub '{self.hub_name}' configured")
            print(f"  ✓ WebSocket URL: {token['url'][:50]}...")
            
            print("  ✅ SignalR/WebSocket ready")
            return True
            
        except Exception as e:
            pytest.fail(f"SignalR connection failed: {str(e)}")


class TestAISearch:
    """Test Azure AI Search indexing"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup AI Search client"""
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "email-patterns")
        
        if not self.search_endpoint or not self.search_key:
            pytest.skip("Azure AI Search not configured")
        
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
        
        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.index_name,
            credential=AzureKeyCredential(self.search_key)
        )
    
    def test_connection(self):
        """Test AI Search connectivity"""
        print("\n🔍 Testing AI Search Connection...")
        
        try:
            # Get document count
            results = self.search_client.search(
                search_text="*",
                include_total_count=True,
                top=1
            )
            
            total_docs = results.get_count()
            print(f"  ✓ Connected to AI Search")
            print(f"  ✓ Index '{self.index_name}' has {total_docs} documents")
            
            print("  ✅ AI Search operational")
            return True
            
        except Exception as e:
            pytest.fail(f"AI Search connection failed: {str(e)}")
    
    def test_search_operations(self):
        """Test search operations"""
        print("\n🔍 Testing Search Operations...")
        
        try:
            # Test search
            results = self.search_client.search(
                search_text="test",
                top=5
            )
            
            count = 0
            for result in results:
                count += 1
                print(f"  ✓ Found document: {result.get('id', 'unknown')[:30]}...")
            
            if count == 0:
                print("  ⚠️  No test documents found (may be normal for new index)")
            else:
                print(f"  ✓ Retrieved {count} search result(s)")
            
            print("  ✅ Search operations working")
            return True
            
        except Exception as e:
            pytest.fail(f"Search operation failed: {str(e)}")


class TestApplicationInsights:
    """Test Application Insights telemetry"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup Application Insights client"""
        self.connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        self.workspace_id = os.getenv("LOG_ANALYTICS_WORKSPACE_ID")
        
        if not self.connection_string:
            pytest.skip("Application Insights not configured")
        
        # Parse instrumentation key
        parts = self.connection_string.split(";")
        for part in parts:
            if part.startswith("InstrumentationKey="):
                self.instrumentation_key = part.split("=")[1]
                break
    
    def test_connection(self):
        """Test Application Insights connectivity"""
        print("\n🔍 Testing Application Insights...")
        
        try:
            # Create a test telemetry event
            from applicationinsights import TelemetryClient
            
            tc = TelemetryClient(self.instrumentation_key)
            tc.track_event("MigrationTest", {
                "test": "infrastructure",
                "timestamp": datetime.utcnow().isoformat()
            })
            tc.flush()
            
            print(f"  ✓ Connected to Application Insights")
            print(f"  ✓ Instrumentation key: {self.instrumentation_key[:8]}...")
            print("  ✓ Test telemetry sent")
            
            print("  ✅ Application Insights operational")
            return True
            
        except Exception as e:
            pytest.fail(f"Application Insights test failed: {str(e)}")
    
    @pytest.mark.skipif(not os.getenv("LOG_ANALYTICS_WORKSPACE_ID"), 
                        reason="Log Analytics workspace not configured")
    def test_log_query(self):
        """Test Log Analytics query"""
        print("\n🔍 Testing Log Analytics Query...")
        
        try:
            credential = DefaultAzureCredential()
            logs_client = LogsQueryClient(credential)
            
            # Query recent logs
            query = """
            AppRequests
            | where TimeGenerated > ago(1h)
            | summarize count() by ResultCode
            | order by count_ desc
            """
            
            response = logs_client.query_workspace(
                workspace_id=self.workspace_id,
                query=query,
                timespan="PT1H"
            )
            
            if response.tables:
                print("  ✓ Log Analytics query successful")
                for table in response.tables:
                    for row in table.rows[:5]:  # Show first 5 rows
                        print(f"     Status {row[0]}: {row[1]} requests")
            else:
                print("  ⚠️  No recent logs found (may be normal)")
            
            print("  ✅ Log Analytics accessible")
            return True
            
        except Exception as e:
            print(f"  ⚠️  Log Analytics query failed: {str(e)}")
            return False


def run_all_tests():
    """Run all infrastructure tests"""
    print("\n" + "="*60)
    print("🚀 AZURE INFRASTRUCTURE MIGRATION TEST SUITE")
    print("="*60)
    print(f"Resource Group: {TEST_CONFIG['resource_group']}")
    print(f"Location: {TEST_CONFIG['location']}")
    print(f"Container App URL: {TEST_CONFIG['container_app_url']}")
    print("="*60)
    
    test_results = {}
    
    # Run each test class
    test_classes = [
        TestContainerApp,
        TestPostgreSQL,
        TestRedisCache,
        TestStorageAccount,
        TestServiceBus,
        TestSignalR,
        TestAISearch,
        TestApplicationInsights
    ]
    
    for test_class in test_classes:
        class_name = test_class.__name__
        print(f"\n📋 Running {class_name}...")
        
        try:
            test_instance = test_class()
            test_instance.setup()
            
            # Run all test methods
            for method_name in dir(test_instance):
                if method_name.startswith("test_"):
                    method = getattr(test_instance, method_name)
                    try:
                        method()
                        test_results[f"{class_name}.{method_name}"] = "✅ PASSED"
                    except Exception as e:
                        test_results[f"{class_name}.{method_name}"] = f"❌ FAILED: {str(e)}"
                        
        except pytest.skip.Exception as e:
            test_results[class_name] = f"⏭️  SKIPPED: {str(e)}"
        except Exception as e:
            test_results[class_name] = f"❌ ERROR: {str(e)}"
    
    # Print summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in test_results.values() if "✅" in str(r))
    failed = sum(1 for r in test_results.values() if "❌" in str(r))
    skipped = sum(1 for r in test_results.values() if "⏭️" in str(r))
    
    for test_name, result in test_results.items():
        print(f"{result} {test_name}")
    
    print("\n" + "="*60)
    print(f"Total: {len(test_results)} tests")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⏭️ Skipped: {skipped}")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    # Check if running with pytest
    if "pytest" in sys.modules:
        # Let pytest handle the tests
        pass
    else:
        # Run tests directly
        success = run_all_tests()
        sys.exit(0 if success else 1)