"""
Test fixtures for repository layer.

Provides both mock and real repository instances for unit and integration testing.
"""

import pytest
from datetime import datetime
from typing import List, Optional
from unittest.mock import Mock, AsyncMock

from app.repositories.zoho_repository import ZohoLeadsRepository, VaultCandidate


class MockZohoLeadsRepository:
    """
    Mock repository for unit tests.

    Returns predefined test data without hitting database or cache.
    """

    def __init__(self):
        self.mock_candidates = [
            VaultCandidate(
                id="1",
                zoho_id="test_zoho_1",
                full_name="John Doe",
                candidate_locator="TWAV-001",
                employer="ABC Financial",
                current_location="New York, NY",
                designation="Senior Financial Advisor",
                book_size_aum="$10M",
                production_l12mo="$500K",
                desired_comp="$200K",
                when_available="Immediately",
                transferrable_book_of_business="Yes",
                licenses_and_exams="Series 7, 66",
                professional_designations="CFP",
                specialty_area_expertise="Retirement Planning",
                is_mobile=True,
                remote=False,
                open_to_hybrid=True,
                in_office=False,
                owner_email="recruiter@emailthewell.com",
                created_time=datetime(2025, 1, 1, 12, 0, 0),
                modified_time=datetime(2025, 10, 15, 10, 30, 0)
            ),
            VaultCandidate(
                id="2",
                zoho_id="test_zoho_2",
                full_name="Jane Smith",
                candidate_locator="TWAV-002",
                employer="XYZ Wealth Management",
                current_location="Chicago, IL",
                designation="Wealth Manager",
                book_size_aum="$15M",
                production_l12mo="$750K",
                desired_comp="$250K",
                when_available="Q1 2025",
                transferrable_book_of_business="Partial",
                licenses_and_exams="Series 7, 65, 24",
                professional_designations="CFA, CFP",
                specialty_area_expertise="High Net Worth",
                is_mobile=False,
                remote=True,
                open_to_hybrid=True,
                in_office=False,
                owner_email="recruiter@emailthewell.com",
                created_time=datetime(2025, 2, 1, 9, 0, 0),
                modified_time=datetime(2025, 10, 16, 14, 15, 0)
            ),
            VaultCandidate(
                id="3",
                zoho_id="test_zoho_3",
                full_name="Mike Johnson",
                candidate_locator="TWAV-003",
                employer="123 Investment Partners",
                current_location="Los Angeles, CA",
                designation="Investment Consultant",
                book_size_aum="$8M",
                production_l12mo="$400K",
                desired_comp="$180K",
                when_available="Immediately",
                transferrable_book_of_business="Yes",
                licenses_and_exams="Series 6, 63",
                professional_designations="None",
                specialty_area_expertise="Estate Planning",
                is_mobile=True,
                remote=False,
                open_to_hybrid=False,
                in_office=True,
                owner_email="recruiter@emailthewell.com",
                created_time=datetime(2025, 3, 1, 8, 0, 0),
                modified_time=datetime(2025, 10, 17, 9, 0, 0)
            )
        ]

    async def get_vault_candidates(
        self,
        limit: int = 500,
        candidate_locator: Optional[str] = None,
        location: Optional[str] = None,
        min_production: Optional[float] = None,
        after_date: Optional[datetime] = None,
        use_cache: bool = True
    ) -> List[VaultCandidate]:
        """Return mock vault candidates with optional filtering."""
        results = self.mock_candidates.copy()

        # Apply filters
        if candidate_locator:
            results = [c for c in results if c.candidate_locator == candidate_locator]

        if location:
            results = [
                c for c in results
                if c.current_location and location.lower() in c.current_location.lower()
            ]

        if min_production:
            results = [
                c for c in results
                if c.production_l12mo and
                float(c.production_l12mo.replace('$', '').replace('K', '000').replace('M', '000000').replace(',', '')) >= min_production
            ]

        if after_date:
            results = [c for c in results if c.modified_time > after_date]

        return results[:limit]

    async def search_candidates(
        self,
        query: str,
        limit: int = 100,
        vault_only: bool = False,
        use_cache: bool = True
    ) -> List[VaultCandidate]:
        """Return mock candidates matching search query."""
        query_lower = query.lower()

        results = [
            c for c in self.mock_candidates
            if (
                query_lower in c.full_name.lower()
                or (c.employer and query_lower in c.employer.lower())
                or (c.current_location and query_lower in c.current_location.lower())
                or (c.designation and query_lower in c.designation.lower())
            )
        ]

        return results[:limit]

    async def invalidate_cache(self, pattern: Optional[str] = None):
        """Mock cache invalidation (no-op for mock)."""
        pass


@pytest.fixture
def mock_zoho_repository():
    """
    Fixture providing mock repository for unit tests.

    Usage:
        def test_something(mock_zoho_repository):
            results = await mock_zoho_repository.get_vault_candidates(limit=10)
            assert len(results) == 3
    """
    return MockZohoLeadsRepository()


@pytest.fixture
async def test_db_connection():
    """
    Fixture providing real database connection for integration tests.

    Note: Requires DATABASE_URL environment variable to be set.
    Uses test database or falls back to development database.
    """
    import os
    import asyncpg

    # Get test database URL
    db_url = os.getenv('TEST_DATABASE_URL') or os.getenv('DATABASE_URL')

    if not db_url:
        pytest.skip("No TEST_DATABASE_URL or DATABASE_URL configured")

    # Create connection
    conn = await asyncpg.connect(db_url)

    try:
        # Set up test schema if needed
        await conn.execute("CREATE SCHEMA IF NOT EXISTS test_schema")
        await conn.execute("SET search_path TO test_schema, public")

        yield conn

    finally:
        # Cleanup
        try:
            await conn.execute("DROP SCHEMA IF EXISTS test_schema CASCADE")
        except Exception:
            pass

        await conn.close()


@pytest.fixture
async def real_zoho_repository(test_db_connection):
    """
    Fixture providing real repository for integration tests.

    Usage:
        @pytest.mark.integration
        async def test_real_query(real_zoho_repository):
            results = await real_zoho_repository.get_vault_candidates(limit=5)
            assert isinstance(results, list)
    """
    import os
    import redis.asyncio as redis

    # Create repository with real DB and Redis
    redis_conn_string = os.getenv('AZURE_REDIS_CONNECTION_STRING')
    redis_client = None
    if redis_conn_string:
        redis_client = await redis.from_url(redis_conn_string)

    repository = ZohoLeadsRepository(test_db_connection, redis_client)

    yield repository

    # Cleanup cache and close Redis after test
    await repository.invalidate_cache()
    if redis_client:
        await redis_client.close()


@pytest.fixture
def mock_asyncpg_connection():
    """
    Fixture providing mock asyncpg connection for unit tests.

    Usage:
        def test_with_mock_db(mock_asyncpg_connection):
            mock_asyncpg_connection.fetch.return_value = [...]
            # Test code
    """
    mock_conn = AsyncMock()

    # Default mock return values
    mock_conn.fetch.return_value = []
    mock_conn.fetchrow.return_value = None
    mock_conn.execute.return_value = None

    return mock_conn


@pytest.fixture
def sample_vault_candidates():
    """
    Fixture providing sample vault candidate data for testing.

    Returns:
        List of 3 VaultCandidate instances
    """
    return [
        VaultCandidate(
            id="1",
            zoho_id="sample_1",
            full_name="Sample Advisor 1",
            candidate_locator="TWAV-S001",
            employer="Sample Firm 1",
            current_location="Boston, MA",
            designation="Financial Advisor",
            book_size_aum="$5M",
            production_l12mo="$300K",
            desired_comp="$150K",
            when_available="Immediately",
            owner_email="test@test.com",
            created_time=datetime(2025, 1, 1),
            modified_time=datetime(2025, 10, 1)
        ),
        VaultCandidate(
            id="2",
            zoho_id="sample_2",
            full_name="Sample Advisor 2",
            candidate_locator="TWAV-S002",
            employer="Sample Firm 2",
            current_location="Seattle, WA",
            designation="Senior Advisor",
            book_size_aum="$12M",
            production_l12mo="$600K",
            desired_comp="$300K",
            when_available="Q2 2025",
            owner_email="test@test.com",
            created_time=datetime(2025, 2, 1),
            modified_time=datetime(2025, 10, 5)
        ),
        VaultCandidate(
            id="3",
            zoho_id="sample_3",
            full_name="Sample Advisor 3",
            candidate_locator="TWAV-S003",
            employer="Sample Firm 3",
            current_location="Miami, FL",
            designation="Wealth Manager",
            book_size_aum="$20M",
            production_l12mo="$1M",
            desired_comp="$500K",
            when_available="Immediately",
            owner_email="test@test.com",
            created_time=datetime(2025, 3, 1),
            modified_time=datetime(2025, 10, 10)
        )
    ]
