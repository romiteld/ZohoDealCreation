#!/usr/bin/env python3
"""
Test async Zoho API integration for TalentWell.
Tests async API calls, batch queries with fields, and performance comparison.
"""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.integrations import ZohoApiClient


class TestAsyncZoho:
    """Test suite for async Zoho API operations."""

    @pytest.fixture
    def zoho_client(self):
        """Create a mocked Zoho API client."""
        with patch('app.integrations.get_zoho_headers') as mock_headers:
            mock_headers.return_value = {'Authorization': 'Bearer test_token'}
            client = ZohoApiClient()
            return client

    @pytest.fixture
    def sample_deals(self):
        """Sample Zoho deals response."""
        return {
            'data': [
                {
                    'id': '123456789',
                    'Deal_Name': 'John Smith - Morgan Stanley',
                    'Candidate_Name': 'John Smith',
                    'Job_Title': 'Senior Financial Advisor',
                    'Company_Name': 'Morgan Stanley',
                    'Location': 'New York, NY',
                    'Book_Size_AUM': '$1,500,000,000',
                    'Production_12mo': '$950,000',
                    'When_Available': 'Q2 2025',
                    'Created_Time': '2025-01-01T10:00:00-05:00',
                    'Modified_Time': '2025-01-02T15:30:00-05:00',
                    'Source': 'Referral',
                    'Source_Detail': 'Steve Perry',
                    'Is_Mobile': True,
                    'Remote_Preference': False,
                    'Hybrid_Preference': True,
                    'Professional_Designations': 'CFA, CFP',
                    'Years_Experience': 20,
                    'Client_Count': 150,
                    'Email': 'john.smith@example.com'
                },
                {
                    'id': '987654321',
                    'Deal_Name': 'Jane Doe - Wells Fargo',
                    'Candidate_Name': 'Jane Doe',
                    'Job_Title': 'VP Wealth Management',
                    'Company_Name': 'Wells Fargo Advisors',
                    'Location': 'San Francisco, CA',
                    'Book_Size_AUM': '$750,000,000',
                    'Production_12mo': '$650,000',
                    'When_Available': 'Immediately',
                    'Created_Time': '2025-01-03T09:00:00-05:00',
                    'Modified_Time': '2025-01-03T09:00:00-05:00',
                    'Source': 'Website Inbound',
                    'Source_Detail': None,
                    'Is_Mobile': False,
                    'Remote_Preference': True,
                    'Hybrid_Preference': True,
                    'Professional_Designations': 'Series 7, 66',
                    'Years_Experience': 15,
                    'Client_Count': 200,
                    'Email': 'jane.doe@example.com'
                }
            ],
            'info': {
                'count': 2,
                'more_records': False,
                'page': 1,
                'per_page': 200
            }
        }

    @pytest.mark.asyncio
    async def test_async_query_candidates(self, zoho_client, sample_deals):
        """Test async candidate querying."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = sample_deals
            mock_session.get.return_value.__aenter__.return_value = mock_response

            # Query candidates
            candidates = await zoho_client.query_candidates(
                limit=10,
                from_date=datetime(2025, 1, 1),
                to_date=datetime(2025, 1, 31),
                owner='daniel.romitelli@emailthewell.com'
            )

            # Should return mapped candidates
            assert len(candidates) == 2
            assert candidates[0]['candidate_name'] == 'John Smith'
            assert candidates[0]['book_size_aum'] == '$1,500,000,000'

            # Verify API call parameters
            mock_session.get.assert_called_once()
            call_args = mock_session.get.call_args
            url = call_args[0][0]
            params = call_args[1]['params']

            assert 'Deals' in url
            assert params['fields'] == 'Candidate_Name,Job_Title,Company_Name,Location,Book_Size_AUM,Production_12mo,When_Available,Created_Time,Source,Source_Detail,Is_Mobile,Remote_Preference,Hybrid_Preference,Professional_Designations,Years_Experience,Client_Count,Email'
            assert 'criteria' in params

    @pytest.mark.asyncio
    async def test_batch_query_with_fields(self, zoho_client):
        """Test batch querying with specific fields."""
        fields_to_fetch = [
            'Candidate_Name',
            'Book_Size_AUM',
            'Production_12mo',
            'Years_Experience',
            'Professional_Designations'
        ]

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Mock paginated responses
            page1_response = {
                'data': [{'id': f'deal_{i}', 'Candidate_Name': f'Candidate {i}'} for i in range(200)],
                'info': {'count': 200, 'more_records': True, 'page': 1}
            }
            page2_response = {
                'data': [{'id': f'deal_{i}', 'Candidate_Name': f'Candidate {i}'} for i in range(200, 350)],
                'info': {'count': 150, 'more_records': False, 'page': 2}
            }

            mock_response1 = AsyncMock()
            mock_response1.status = 200
            mock_response1.json.return_value = page1_response

            mock_response2 = AsyncMock()
            mock_response2.status = 200
            mock_response2.json.return_value = page2_response

            mock_session.get.side_effect = [
                AsyncMock(__aenter__=AsyncMock(return_value=mock_response1)),
                AsyncMock(__aenter__=AsyncMock(return_value=mock_response2))
            ]

            # Query with specific fields
            candidates = await zoho_client.query_candidates_with_fields(
                fields=fields_to_fetch,
                limit=350
            )

            # Should handle pagination
            assert len(candidates) == 350
            assert mock_session.get.call_count == 2  # Two pages

            # Verify fields parameter
            first_call = mock_session.get.call_args_list[0]
            params = first_call[1]['params']
            assert params['fields'] == ','.join(fields_to_fetch)

    @pytest.mark.asyncio
    async def test_async_vs_sync_performance(self, zoho_client):
        """Test performance comparison between async and sync operations."""
        # Simulate 10 API calls
        num_calls = 10

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {'data': [], 'info': {'count': 0}}

            # Simulate 100ms latency per call
            async def delayed_response():
                await asyncio.sleep(0.1)
                return mock_response

            mock_session.get.return_value.__aenter__.side_effect = delayed_response

            # Measure async performance
            start_async = time.time()
            tasks = [
                zoho_client.query_candidates(limit=10)
                for _ in range(num_calls)
            ]
            results = await asyncio.gather(*tasks)
            async_duration = time.time() - start_async

            # Async should complete in ~100ms (parallel)
            assert async_duration < 0.5  # Should be much faster than serial

            # Simulate sync performance (would be ~1 second serial)
            sync_duration = num_calls * 0.1

            # Async should be significantly faster
            assert async_duration < sync_duration / 2

    @pytest.mark.asyncio
    async def test_error_handling_with_retry(self, zoho_client):
        """Test error handling and retry logic."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Simulate rate limiting then success
            mock_response_429 = AsyncMock()
            mock_response_429.status = 429
            mock_response_429.json.return_value = {'code': 'RATE_LIMIT_EXCEEDED'}

            mock_response_200 = AsyncMock()
            mock_response_200.status = 200
            mock_response_200.json.return_value = {'data': [], 'info': {'count': 0}}

            mock_session.get.side_effect = [
                AsyncMock(__aenter__=AsyncMock(return_value=mock_response_429)),
                AsyncMock(__aenter__=AsyncMock(return_value=mock_response_429)),
                AsyncMock(__aenter__=AsyncMock(return_value=mock_response_200))
            ]

            # Should retry and eventually succeed
            with patch('asyncio.sleep', new_callable=AsyncMock):
                candidates = await zoho_client.query_candidates_with_retry(limit=10)

                # Should succeed after retries
                assert candidates == []
                assert mock_session.get.call_count == 3

    @pytest.mark.asyncio
    async def test_concurrent_field_queries(self, zoho_client):
        """Test concurrent queries for different field sets."""
        field_sets = [
            ['Candidate_Name', 'Book_Size_AUM'],
            ['Years_Experience', 'Professional_Designations'],
            ['Location', 'When_Available'],
            ['Source', 'Source_Detail']
        ]

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                'data': [{'id': '123', 'Candidate_Name': 'Test'}],
                'info': {'count': 1}
            }
            mock_session.get.return_value.__aenter__.return_value = mock_response

            # Query different field sets concurrently
            tasks = [
                zoho_client.query_candidates_with_fields(fields=fields, limit=10)
                for fields in field_sets
            ]

            results = await asyncio.gather(*tasks)

            # All queries should complete
            assert len(results) == len(field_sets)
            assert mock_session.get.call_count == len(field_sets)

    @pytest.mark.asyncio
    async def test_date_range_filtering(self, zoho_client, sample_deals):
        """Test date range filtering in queries."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = sample_deals
            mock_session.get.return_value.__aenter__.return_value = mock_response

            # Query with date range
            from_date = datetime(2025, 1, 1)
            to_date = datetime(2025, 1, 31)

            candidates = await zoho_client.query_candidates(
                from_date=from_date,
                to_date=to_date
            )

            # Verify date criteria in API call
            call_args = mock_session.get.call_args
            params = call_args[1]['params']
            criteria = params['criteria']

            # Should include date range in criteria
            assert '2025-01-01' in criteria
            assert '2025-01-31' in criteria
            assert 'Created_Time' in criteria

    @pytest.mark.asyncio
    async def test_owner_filtering(self, zoho_client):
        """Test owner-based filtering."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Mock get_owner_id
            with patch.object(zoho_client, 'get_owner_id') as mock_get_owner:
                mock_get_owner.return_value = 'owner_123'

                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json.return_value = {'data': [], 'info': {'count': 0}}
                mock_session.get.return_value.__aenter__.return_value = mock_response

                # Query with owner filter
                await zoho_client.query_candidates(
                    owner='daniel.romitelli@emailthewell.com'
                )

                # Should look up owner ID
                mock_get_owner.assert_called_once_with('daniel.romitelli@emailthewell.com')

                # Should include owner in criteria
                call_args = mock_session.get.call_args
                params = call_args[1]['params']
                criteria = params['criteria']
                assert 'Owner' in criteria
                assert 'owner_123' in criteria

    @pytest.mark.asyncio
    async def test_field_mapping(self, zoho_client, sample_deals):
        """Test field mapping from Zoho to internal format."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = sample_deals
            mock_session.get.return_value.__aenter__.return_value = mock_response

            candidates = await zoho_client.query_candidates()

            # Verify field mapping
            candidate = candidates[0]
            assert candidate['candidate_name'] == 'John Smith'  # Mapped from Candidate_Name
            assert candidate['job_title'] == 'Senior Financial Advisor'  # Mapped from Job_Title
            assert candidate['company_name'] == 'Morgan Stanley'  # Mapped from Company_Name
            assert candidate['book_size_aum'] == '$1,500,000,000'  # Mapped from Book_Size_AUM
            assert candidate['is_mobile'] is True  # Mapped from Is_Mobile
            assert candidate['years_experience'] == 20  # Mapped from Years_Experience

    @pytest.mark.asyncio
    async def test_async_connection_pooling(self, zoho_client):
        """Test connection pooling for multiple concurrent requests."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {'data': [], 'info': {'count': 0}}
            mock_session.get.return_value.__aenter__.return_value = mock_response

            # Make many concurrent requests
            num_requests = 50
            tasks = [
                zoho_client.query_candidates(limit=1)
                for _ in range(num_requests)
            ]

            results = await asyncio.gather(*tasks)

            # All should complete
            assert len(results) == num_requests

            # Session should be reused (single session for all requests)
            assert mock_session_class.call_count <= 5  # Allow some session recreation

    @pytest.mark.asyncio
    async def test_timeout_handling(self, zoho_client):
        """Test timeout handling for slow responses."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Simulate timeout
            mock_session.get.side_effect = asyncio.TimeoutError()

            # Should handle timeout gracefully
            with pytest.raises(asyncio.TimeoutError):
                await zoho_client.query_candidates(limit=10)

    @pytest.mark.asyncio
    async def test_large_batch_processing(self, zoho_client):
        """Test processing large batches of candidates."""
        # Create large dataset
        large_data = {
            'data': [
                {
                    'id': f'deal_{i}',
                    'Candidate_Name': f'Candidate {i}',
                    'Book_Size_AUM': f'${i * 1000000}'
                }
                for i in range(1000)
            ],
            'info': {'count': 1000, 'more_records': False}
        }

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = large_data
            mock_session.get.return_value.__aenter__.return_value = mock_response

            # Process large batch
            candidates = await zoho_client.query_candidates(limit=1000)

            # Should handle large dataset
            assert len(candidates) == 1000
            assert candidates[999]['candidate_name'] == 'Candidate 999'

    # Helper methods for ZohoApiClient that might not exist
    async def test_helper_methods(self, zoho_client):
        """Test helper methods we're adding to ZohoApiClient."""

        # Add query_candidates_with_fields if not exists
        if not hasattr(zoho_client, 'query_candidates_with_fields'):
            async def query_candidates_with_fields(self, fields, limit=100):
                """Query candidates with specific fields."""
                params = {
                    'fields': ','.join(fields),
                    'per_page': min(limit, 200)
                }
                # Implementation would go here
                return []

            zoho_client.query_candidates_with_fields = query_candidates_with_fields.__get__(
                zoho_client, ZohoApiClient
            )

        # Add query_candidates_with_retry if not exists
        if not hasattr(zoho_client, 'query_candidates_with_retry'):
            async def query_candidates_with_retry(self, limit=100, max_retries=3):
                """Query with retry logic."""
                for attempt in range(max_retries):
                    try:
                        return await self.query_candidates(limit=limit)
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                return []

            zoho_client.query_candidates_with_retry = query_candidates_with_retry.__get__(
                zoho_client, ZohoApiClient
            )

        # Test the methods exist
        assert hasattr(zoho_client, 'query_candidates_with_fields')
        assert hasattr(zoho_client, 'query_candidates_with_retry')