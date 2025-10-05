"""
Integration test for Outlook→TalentWell data flow with enrichment caching.
Tests the complete flow from Outlook intake through Zoho deal creation to TalentWell digest.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.integrations import ZohoApiClient
from app.models import ExtractedData
from app.jobs.talentwell_curator import TalentWellCurator


@pytest.mark.asyncio
async def test_complete_outlook_to_talentwell_flow():
    """Test the complete data flow from Outlook intake to TalentWell digest with caching."""

    # Step 1: Create Zoho deal from Outlook intake with enrichment
    zoho_client = ZohoApiClient()

    # Mock Redis client
    mock_redis = AsyncMock()
    zoho_client.redis_client = mock_redis

    # Mock Zoho API responses
    with patch.object(zoho_client, '_make_request') as mock_request:
        # Mock candidate search - return empty to trigger creation
        mock_request.side_effect = [
            {"data": [], "info": {"count": 0}},  # No existing candidate
            {"data": [{"details": {"id": "CAND-123"}}]},  # Created candidate
            {"data": [{"details": {"id": "DEAL-456"}}]},  # Created deal
        ]

        # Create extracted data from Outlook email
        extracted_data = ExtractedData(
            candidate_name="John Smith",
            company_name="Elite Financial Advisors",
            job_title="Senior Wealth Manager",
            location="Chicago, IL",
            email="john.smith@elitefa.com",
            phone="555-0123",
            book_size_aum="$500M",
            production_12mo="$2.5M"
        )

        # Process through Zoho integration
        result = await zoho_client.create_or_update_records(
            extracted_data=extracted_data,
            sender_email="john.smith@elitefa.com"
        )

        # Verify deal was created
        assert result["deal_id"] == "DEAL-456"

        # Verify enrichment was cached
        assert mock_redis.setex.called
        cache_call = mock_redis.setex.call_args
        assert cache_call[0][0] == "enrichment:contact:john.smith@elitefa.com"
        assert cache_call[0][1] == 86400 * 7  # 7-day TTL

        cached_data = json.loads(cache_call[0][2])
        assert cached_data["company"] == "Elite Financial Advisors"
        assert cached_data["job_title"] == "Senior Wealth Manager"
        assert cached_data["location"] == "Chicago, IL"
        assert cached_data["phone"] == "555-0123"

    # Step 2: TalentWell curator reads from enrichment cache
    curator = TalentWellCurator()
    await curator.initialize()

    # Set up the same Redis mock for curator
    curator.redis_client = mock_redis

    # Simulate cached enrichment data
    enrichment_data = {
        "email": "john.smith@elitefa.com",
        "company": "Elite Financial Advisors",
        "job_title": "Senior Wealth Manager",
        "location": "Chicago, IL",
        "phone": "555-0123",
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "source": "outlook_intake"
    }
    mock_redis.get.return_value = json.dumps(enrichment_data).encode()

    # Create a deal with minimal data to test enrichment
    minimal_deal = {
        "id": "DEAL-456",
        "candidate_name": "John Smith",
        "email": "john.smith@elitefa.com",
        "company_name": "Unknown",  # Should be enriched
        "job_title": "Unknown",      # Should be enriched
        "location": "Unknown",        # Should be enriched
        "book_size_aum": "$500M",
        "production_12mo": "$2.5M"
    }

    # Mock other dependencies
    with patch.object(curator, '_normalize_location', return_value="Chicago Metro Area"):
        with patch.object(curator, '_generate_bullets', return_value=["• Senior Wealth Manager with $500M AUM"]):
            # Process the deal
            card = await curator._process_deal(minimal_deal, "steve_perry")

    # Verify enrichment was used
    assert mock_redis.get.called
    assert mock_redis.get.call_args[0][0] == "enrichment:contact:john.smith@elitefa.com"

    # Verify the card was enhanced with cached data
    assert card.company == "Elite Financial Advisors"
    assert card.job_title == "Senior Wealth Manager"
    assert "Chicago" in card.location

    # Verify Outlook enrichment was stored in deal
    assert minimal_deal.get('_outlook_enrichment') is not None
    assert minimal_deal['_outlook_enrichment']['source'] == 'outlook_intake'


@pytest.mark.asyncio
async def test_talentwell_enrichment_fallback():
    """Test that TalentWell gracefully handles missing enrichment cache."""

    curator = TalentWellCurator()
    await curator.initialize()

    # Mock Redis to return None (no cache)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    curator.redis_client = mock_redis

    # Create deal with existing data
    deal = {
        "id": "DEAL-789",
        "candidate_name": "Jane Doe",
        "email": "jane.doe@example.com",
        "company_name": "Original Company",
        "job_title": "Original Title",
        "location": "New York, NY"
    }

    # Mock dependencies
    with patch.object(curator, '_normalize_location', return_value="New York Metro Area"):
        with patch.object(curator, '_generate_bullets', return_value=["• Financial Advisor"]):
            # Process the deal
            card = await curator._process_deal(deal, "steve_perry")

    # Verify cache was checked
    assert mock_redis.get.called

    # Verify original data was preserved (no enrichment available)
    assert card.company == "Original Company"
    assert card.job_title == "Original Title"

    # Verify no enrichment was stored
    assert '_outlook_enrichment' not in deal


@pytest.mark.asyncio
async def test_enrichment_cache_error_handling():
    """Test that enrichment cache errors don't break the flow."""

    curator = TalentWellCurator()
    await curator.initialize()

    # Mock Redis to throw an error
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = Exception("Redis connection failed")
    curator.redis_client = mock_redis

    # Create deal
    deal = {
        "id": "DEAL-999",
        "candidate_name": "Error Test",
        "email": "error@test.com",
        "company_name": "Test Company",
        "job_title": "Test Title",
        "location": "Test Location"
    }

    # Mock dependencies
    with patch.object(curator, '_normalize_location', return_value="Test Metro Area"):
        with patch.object(curator, '_generate_bullets', return_value=["• Test bullet"]):
            with patch('app.jobs.talentwell_curator.logger') as mock_logger:
                # Process the deal - should not raise error
                card = await curator._process_deal(deal, "steve_perry")

    # Verify error was logged but didn't break the flow
    mock_logger.warning.assert_called_with("Failed to fetch Outlook enrichment: Redis connection failed")

    # Verify card was still created with original data
    assert card.company == "Test Company"
    assert card.job_title == "Test Title"


@pytest.mark.asyncio
async def test_partial_enrichment():
    """Test that partial enrichment only updates missing fields."""

    curator = TalentWellCurator()
    await curator.initialize()

    # Mock Redis with enrichment data
    mock_redis = AsyncMock()
    enrichment_data = {
        "email": "partial@test.com",
        "company": "Enriched Company",
        "job_title": "Enriched Title",
        "location": "Enriched Location"
    }
    mock_redis.get.return_value = json.dumps(enrichment_data).encode()
    curator.redis_client = mock_redis

    # Create deal with some existing data
    deal = {
        "id": "DEAL-PARTIAL",
        "candidate_name": "Partial Test",
        "email": "partial@test.com",
        "company_name": "Existing Company",  # Should NOT be overwritten
        "job_title": "Unknown",              # Should be enriched
        "location": ""                       # Should be enriched (empty is falsy)
    }

    # Mock dependencies
    with patch.object(curator, '_normalize_location', return_value="Enriched Metro Area"):
        with patch.object(curator, '_generate_bullets', return_value=["• Test"]):
            # Process the deal
            card = await curator._process_deal(deal, "steve_perry")

    # Verify selective enrichment
    assert card.company == "Existing Company"  # Preserved existing
    assert card.job_title == "Enriched Title"  # Enriched missing
    assert "Enriched" in card.location        # Enriched empty


if __name__ == "__main__":
    asyncio.run(pytest.main([__file__, "-v"]))