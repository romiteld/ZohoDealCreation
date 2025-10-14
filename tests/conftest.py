#!/usr/bin/env python3
"""
Shared pytest configuration and fixtures for TalentWell tests.
Provides common setup, mocks, and utilities for all test files.
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load test environment variables
test_env_path = Path(__file__).parent / '.env.test'
if test_env_path.exists():
    load_dotenv(test_env_path)
else:
    # Load from default location
    load_dotenv('.env.local')

# Import fixtures modules
from tests.fixtures.sample_csv_files import CSVFixtures, generate_test_email_data, generate_zoho_mock_responses
from tests.fixtures.outlook_payloads import OutlookPayloadFixtures


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )


# Event loop configuration for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Environment setup
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    test_env = {
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db',
        'API_KEY': 'test-api-key-12345',
        'OPENAI_API_KEY': 'sk-test-openai-key',
        'ZOHO_OAUTH_SERVICE_URL': 'https://test-zoho-oauth.example.com',
        'ZOHO_DEFAULT_OWNER_EMAIL': 'test@example.com',
        'USE_LANGGRAPH': 'true',
        'REDIS_URL': 'redis://localhost:6379/0',
        'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test==;EndpointSuffix=core.windows.net',
        'FEATURE_C3': 'true',
        'FEATURE_VOIT': 'true',
        'C3_DELTA': '0.01',
        'C3_EPS': '3',
        'VOIT_BUDGET': '5.0',
        'TARGET_QUALITY': '0.9'
    }
    
    with patch.dict(os.environ, test_env):
        yield


# Database mocks
@pytest.fixture
def mock_postgres_pool():
    """Mock PostgreSQL connection pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    transaction = AsyncMock()
    
    # Configure connection manager
    connection_manager = AsyncMock()
    connection_manager.__aenter__ = AsyncMock(return_value=conn)
    connection_manager.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = connection_manager
    
    # Configure transaction
    conn.transaction.return_value = transaction
    transaction.__aenter__ = AsyncMock(return_value=transaction)
    transaction.__aexit__ = AsyncMock(return_value=None)
    
    # Default query responses
    conn.fetch.return_value = []
    conn.fetchone.return_value = None
    conn.fetchrow.return_value = None
    conn.execute.return_value = None
    
    return pool, conn, transaction


@pytest.fixture
def mock_postgres_client(mock_postgres_pool):
    """Mock PostgreSQL client with pool."""
    pool, conn, transaction = mock_postgres_pool
    
    with patch('app.integrations.PostgreSQLClient') as mock_client:
        instance = mock_client.return_value
        instance.init_pool = AsyncMock()
        instance.pool = pool
        yield instance, conn, transaction


# Redis mocks
@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    with patch('redis.Redis') as mock_redis:
        client = AsyncMock()
        mock_redis.return_value = client
        
        # Common Redis operations
        client.get = AsyncMock(return_value=None)
        client.set = AsyncMock(return_value=True)
        client.hget = AsyncMock(return_value=None)
        client.hset = AsyncMock(return_value=True)
        client.lpush = AsyncMock(return_value=1)
        client.rpush = AsyncMock(return_value=1)
        client.lpop = AsyncMock(return_value=None)
        client.rpop = AsyncMock(return_value=None)
        client.expire = AsyncMock(return_value=True)
        client.delete = AsyncMock(return_value=1)
        client.exists = AsyncMock(return_value=False)
        client.pipeline = AsyncMock()
        
        yield client


@pytest.fixture
def mock_cache_manager(mock_redis_client):
    """Mock cache manager with Redis client."""
    with patch('app.redis_cache_manager.get_cache_manager') as mock_get:
        manager = AsyncMock()
        manager.redis_client = mock_redis_client
        mock_get.return_value = manager
        yield manager


# Zoho API mocks
@pytest.fixture
def mock_zoho_client():
    """Mock Zoho API client."""
    with patch('app.integrations.ZohoLeadsClient') as mock_client:
        instance = mock_client.return_value
        
        # Default successful responses
        instance.create_lead = AsyncMock(return_value={
            "data": [{"code": "SUCCESS", "details": {"id": "123456"}}]
        })
        instance.create_deal = AsyncMock(return_value={
            "data": [{"code": "SUCCESS", "details": {"id": "654321"}}]
        })
        instance.update_lead = AsyncMock(return_value={
            "data": [{"code": "SUCCESS", "details": {"id": "123456"}}]
        })
        instance.update_deal = AsyncMock(return_value={
            "data": [{"code": "SUCCESS", "details": {"id": "654321"}}]
        })
        
        yield instance


# LangGraph mocks
@pytest.fixture
def mock_langgraph_manager():
    """Mock LangGraph manager."""
    with patch('app.langgraph_manager.LangGraphManager') as mock_manager:
        instance = mock_manager.return_value
        
        # Default extraction result
        instance.process_email = AsyncMock(return_value={
            "candidate_name": "Test Candidate",
            "job_title": "Financial Advisor",
            "firm_name": "Test Firm",
            "location": "Chicago, IL",
            "contact_email": "test@example.com",
            "contact_phone": "555-123-4567",
            "source": "Email Inbound",
            "source_detail": None
        })
        
        yield instance


# File system mocks
@pytest.fixture
def temp_directory(tmp_path):
    """Provide temporary directory for file operations."""
    return tmp_path


@pytest.fixture
def sample_csv_files(temp_directory):
    """Create sample CSV files in temporary directory."""
    CSVFixtures.write_fixture_files(temp_directory)
    return temp_directory


# Data fixtures
@pytest.fixture
def csv_fixtures():
    """Provide CSV test data fixtures."""
    return CSVFixtures


@pytest.fixture
def email_fixtures():
    """Provide email test data fixtures."""
    return OutlookPayloadFixtures


@pytest.fixture
def sample_emails():
    """Generate sample email data."""
    return generate_test_email_data(5)


@pytest.fixture
def zoho_responses():
    """Provide Zoho API response fixtures."""
    return generate_zoho_mock_responses()


# Application mocks
@pytest.fixture
def mock_app_state():
    """Mock FastAPI app state."""
    state = Mock()
    state.correction_service = AsyncMock()
    state.learning_analytics = AsyncMock()
    return state


@pytest.fixture
def mock_azure_services():
    """Mock Azure service integrations."""
    with patch('app.azure_cost_optimizer.AzureCostOptimizer') as mock_cost, \
         patch('app.azure_ai_search_manager.AzureAISearchManager') as mock_search, \
         patch('app.service_bus_manager.ServiceBusManager') as mock_bus:
        
        # Cost optimizer
        cost_optimizer = mock_cost.return_value
        cost_optimizer.select_model_tier = AsyncMock(return_value='gpt-5-mini')
        cost_optimizer.track_usage = AsyncMock()
        
        # AI Search
        search_manager = mock_search.return_value
        search_manager.semantic_search = AsyncMock(return_value=[])
        search_manager.index_document = AsyncMock()
        
        # Service Bus
        bus_manager = mock_bus.return_value
        bus_manager.send_batch = AsyncMock()
        bus_manager.receive_batch = AsyncMock(return_value=[])
        
        yield {
            'cost_optimizer': cost_optimizer,
            'search_manager': search_manager,
            'bus_manager': bus_manager
        }


# Performance testing utilities
@pytest.fixture
def performance_monitor():
    """Monitor test performance metrics."""
    import time
    import psutil
    import threading
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.start_memory = None
            self.end_memory = None
            self.peak_memory = None
            self._monitoring = False
            self._monitor_thread = None
        
        def start(self):
            self.start_time = time.time()
            self.start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            self.peak_memory = self.start_memory
            self._monitoring = True
            self._monitor_thread = threading.Thread(target=self._monitor_memory)
            self._monitor_thread.start()
        
        def stop(self):
            self.end_time = time.time()
            self.end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            self._monitoring = False
            if self._monitor_thread:
                self._monitor_thread.join()
        
        def _monitor_memory(self):
            while self._monitoring:
                current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                self.peak_memory = max(self.peak_memory, current_memory)
                time.sleep(0.1)
        
        @property
        def elapsed_time(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
        
        @property
        def memory_usage(self):
            if self.start_memory and self.end_memory:
                return {
                    'start_mb': self.start_memory,
                    'end_mb': self.end_memory,
                    'peak_mb': self.peak_memory,
                    'delta_mb': self.end_memory - self.start_memory
                }
            return None
    
    return PerformanceMonitor()


# Error injection utilities
@pytest.fixture
def error_injector():
    """Utility for injecting errors during tests."""
    class ErrorInjector:
        def __init__(self):
            self.patches = []
        
        def inject_database_error(self, error_message="Database error"):
            """Inject database connection error."""
            patch_obj = patch('app.integrations.PostgreSQLClient.init_pool', 
                            side_effect=Exception(error_message))
            self.patches.append(patch_obj)
            return patch_obj.start()
        
        def inject_redis_error(self, error_message="Redis error"):
            """Inject Redis connection error."""
            patch_obj = patch('redis.Redis.ping', 
                            side_effect=Exception(error_message))
            self.patches.append(patch_obj)
            return patch_obj.start()
        
        def inject_zoho_error(self, status_code=500, error_message="Zoho API error"):
            """Inject Zoho API error."""
            from fastapi import HTTPException
            patch_obj = patch('app.integrations.ZohoLeadsClient.create_lead',
                            side_effect=HTTPException(status_code=status_code, detail=error_message))
            self.patches.append(patch_obj)
            return patch_obj.start()
        
        def inject_langgraph_error(self, error_message="Processing error"):
            """Inject LangGraph processing error."""
            patch_obj = patch('app.langgraph_manager.LangGraphManager.process_email',
                            side_effect=Exception(error_message))
            self.patches.append(patch_obj)
            return patch_obj.start()
        
        def cleanup(self):
            """Clean up all injected errors."""
            for patch_obj in reversed(self.patches):
                patch_obj.stop()
            self.patches.clear()
    
    injector = ErrorInjector()
    yield injector
    injector.cleanup()


# Concurrency testing utilities
@pytest.fixture
def concurrency_tester():
    """Utility for testing concurrent operations."""
    class ConcurrencyTester:
        def __init__(self):
            self.results = []
            self.errors = []
        
        async def run_concurrent(self, coroutine_func, *args_list, **kwargs):
            """Run multiple coroutines concurrently."""
            tasks = []
            for args in args_list:
                if isinstance(args, (list, tuple)):
                    task = asyncio.create_task(coroutine_func(*args, **kwargs))
                else:
                    task = asyncio.create_task(coroutine_func(args, **kwargs))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    self.errors.append(result)
                else:
                    self.results.append(result)
            
            return self.results, self.errors
        
        def run_threaded(self, func, *args_list, max_workers=5):
            """Run multiple functions in threads."""
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for args in args_list:
                    if isinstance(args, (list, tuple)):
                        future = executor.submit(func, *args)
                    else:
                        future = executor.submit(func, args)
                    futures.append(future)
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        self.results.append(result)
                    except Exception as e:
                        self.errors.append(e)
            
            return self.results, self.errors
    
    return ConcurrencyTester()


# Custom assertions
def assert_valid_uuid(uuid_string):
    """Assert that string is a valid UUID."""
    import uuid
    try:
        uuid.UUID(uuid_string)
    except ValueError:
        pytest.fail(f"'{uuid_string}' is not a valid UUID")


def assert_valid_email(email_string):
    """Assert that string is a valid email format."""
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email_string):
        pytest.fail(f"'{email_string}' is not a valid email format")


def assert_response_time(actual_seconds, max_seconds):
    """Assert that response time is within acceptable limits."""
    if actual_seconds > max_seconds:
        pytest.fail(f"Response time {actual_seconds:.2f}s exceeds limit of {max_seconds}s")


def assert_memory_usage(memory_mb, max_mb):
    """Assert that memory usage is within acceptable limits."""
    if memory_mb > max_mb:
        pytest.fail(f"Memory usage {memory_mb:.2f}MB exceeds limit of {max_mb}MB")


# Register custom assertions
pytest.assert_valid_uuid = assert_valid_uuid
pytest.assert_valid_email = assert_valid_email
pytest.assert_response_time = assert_response_time
pytest.assert_memory_usage = assert_memory_usage


# Service Bus specific fixtures
@pytest.fixture
async def service_bus_client():
    """Mock Service Bus client for testing."""
    from app.service_bus_manager import ServiceBusManager

    # Use mock connection string for testing
    client = ServiceBusManager(
        connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test==",
        queue_name="test-queue"
    )

    # Mock the Azure SDK internals
    client._client = AsyncMock()
    client._sender = AsyncMock()
    client._receiver = AsyncMock()

    # Configure default behaviors
    client._sender.send_messages = AsyncMock()
    client._receiver.receive_messages = AsyncMock(return_value=[])
    client._receiver.peek_messages = AsyncMock(return_value=[])
    client._receiver.complete_message = AsyncMock()
    client._receiver.abandon_message = AsyncMock()
    client._receiver.dead_letter_message = AsyncMock()

    yield client

    # Cleanup
    await client.close()


@pytest.fixture
def mock_conversation_reference():
    """Mock Teams conversation reference for proactive messaging."""
    return {
        "conversation_id": "test-conv-123",
        "service_url": "https://smba.trafficmanager.net/amer/",
        "tenant_id": "test-tenant-id",
        "user": {
            "id": "test-user-id",
            "name": "Test User"
        },
        "bot": {
            "id": "test-bot-id",
            "name": "Test Bot"
        },
        "channel_id": "msteams",
        "locale": "en-US"
    }


@pytest.fixture
def mock_circuit_breaker():
    """Mock circuit breaker for testing failure scenarios."""
    from unittest.mock import MagicMock

    breaker = MagicMock()
    breaker.state = "closed"
    breaker.failure_count = 0
    breaker.success_count = 0
    breaker.last_failure_time = None
    breaker.is_open = False

    def open_circuit():
        breaker.state = "open"
        breaker.is_open = True

    def close_circuit():
        breaker.state = "closed"
        breaker.is_open = False
        breaker.failure_count = 0

    breaker.open = open_circuit
    breaker.close = close_circuit

    return breaker


@pytest.fixture
def mock_message_bus_service():
    """Mock message bus service for testing."""
    service = AsyncMock()
    service.publish_digest_request = AsyncMock(return_value="msg-123")
    service.process_digest_message = AsyncMock()
    service.send_proactive_message = AsyncMock()
    service.store_conversation_reference = AsyncMock()
    service.get_conversation_reference = AsyncMock(return_value=None)

    return service