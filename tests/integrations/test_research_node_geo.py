"""
Integration tests for geocoding in the research node.
Tests location extraction, geocoding integration, and state updates.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any

from app.langgraph_manager import EmailProcessingWorkflow, EmailProcessingState


@pytest.mark.asyncio
async def test_research_node_with_location_hint():
    """Test that research node geocodes location hints."""
    workflow = EmailProcessingWorkflow()

    # Create test state with location hint
    test_state = {
        'email_content': 'Candidate based in Seattle, WA',
        'sender_domain': 'test.com',
        'extraction_result': {
            'candidate_name': 'John Doe',
            'location': 'Seattle, WA',
            'contact_record': {
                'city': 'Seattle',
                'state': 'WA'
            }
        },
        'company_research': {}
    }

    # Mock config to enable Azure Maps
    mock_config = MagicMock()
    mock_config.enable_azure_maps = True
    mock_config.azure_maps_default_country = 'US'

    with patch('app.langgraph_manager.get_extraction_config', return_value=mock_config):
        # Mock Azure Maps client
        mock_maps_client = AsyncMock()
        mock_maps_client.geocode_address.return_value = [{
            'latitude': 47.6062,
            'longitude': -122.3321,
            'address': {
                'municipality': 'Seattle',
                'countrySubdivisionName': 'Washington',
                'freeformAddress': 'Seattle, WA'
            },
            'confidence': 0.95
        }]

        with patch('app.langgraph_manager.get_azure_maps_client', return_value=mock_maps_client):
            # Mock other dependencies
            with patch.object(workflow, 'client') as mock_openai:
                with patch('app.langgraph_manager.CompanyResearchService'):
                    with patch('app.langgraph_manager.RedisCacheManager'):
                        result = await workflow.research_company(test_state)

        # Verify geocoding was called
        mock_maps_client.geocode_address.assert_called_once_with(
            query='Seattle, WA',
            country_filter='US'
        )

        # Verify state was updated with geo data
        assert test_state.get('geo') is not None
        assert test_state['geo']['latitude'] == 47.6062
        assert test_state['geo']['longitude'] == -122.3321


@pytest.mark.asyncio
async def test_research_node_with_coordinates():
    """Test that research node handles reverse geocoding."""
    workflow = EmailProcessingWorkflow()

    # Create test state with coordinates
    test_state = {
        'email_content': 'Meeting at 47.6062, -122.3321',
        'sender_domain': 'test.com',
        'extraction_result': {},
        'company_research': {},
        'coordinates': (47.6062, -122.3321)
    }

    mock_config = MagicMock()
    mock_config.enable_azure_maps = True

    with patch('app.langgraph_manager.get_extraction_config', return_value=mock_config):
        mock_maps_client = AsyncMock()
        mock_maps_client.reverse_geocode.return_value = {
            'latitude': 47.6062,
            'longitude': -122.3321,
            'address': {
                'freeformAddress': '909 5th Avenue, Seattle, WA 98164',
                'municipality': 'Seattle',
                'countrySubdivisionName': 'Washington'
            },
            'formatted_address': '909 5th Avenue, Seattle, WA 98164'
        }

        with patch('app.langgraph_manager.get_azure_maps_client', return_value=mock_maps_client):
            with patch.object(workflow, 'client'):
                with patch('app.langgraph_manager.CompanyResearchService'):
                    with patch('app.langgraph_manager.RedisCacheManager'):
                        result = await workflow.research_company(test_state)

        # Verify reverse geocoding was called
        mock_maps_client.reverse_geocode.assert_called_once_with(47.6062, -122.3321)

        # Verify state was updated
        assert test_state.get('geo') is not None
        assert test_state['geo']['formatted_address'] == '909 5th Avenue, Seattle, WA 98164'


@pytest.mark.asyncio
async def test_research_node_skips_url_locations():
    """Test that research node skips URL-like location hints."""
    workflow = EmailProcessingWorkflow()

    test_state = {
        'email_content': 'Visit us at www.example.com',
        'sender_domain': 'test.com',
        'extraction_result': {
            'location': 'https://example.com'
        },
        'company_research': {}
    }

    mock_config = MagicMock()
    mock_config.enable_azure_maps = True

    with patch('app.langgraph_manager.get_extraction_config', return_value=mock_config):
        mock_maps_client = AsyncMock()

        with patch('app.langgraph_manager.get_azure_maps_client', return_value=mock_maps_client):
            with patch.object(workflow, 'client'):
                with patch('app.langgraph_manager.CompanyResearchService'):
                    with patch('app.langgraph_manager.RedisCacheManager'):
                        result = await workflow.research_company(test_state)

        # Verify geocoding was NOT called for URL
        mock_maps_client.geocode_address.assert_not_called()


@pytest.mark.asyncio
async def test_research_node_geocoding_disabled():
    """Test that research node skips geocoding when disabled."""
    workflow = EmailProcessingWorkflow()

    test_state = {
        'email_content': 'Based in Seattle',
        'sender_domain': 'test.com',
        'extraction_result': {
            'location': 'Seattle, WA'
        },
        'company_research': {}
    }

    # Disable Azure Maps
    mock_config = MagicMock()
    mock_config.enable_azure_maps = False

    with patch('app.langgraph_manager.get_extraction_config', return_value=mock_config):
        with patch('app.langgraph_manager.get_azure_maps_client') as mock_get_client:
            with patch.object(workflow, 'client'):
                with patch('app.langgraph_manager.CompanyResearchService'):
                    with patch('app.langgraph_manager.RedisCacheManager'):
                        result = await workflow.research_company(test_state)

        # Verify Azure Maps client was never created
        mock_get_client.assert_not_called()

        # Verify geo was not added to state
        assert test_state.get('geo') is None


@pytest.mark.asyncio
async def test_research_node_geocoding_error_handling():
    """Test that research node handles geocoding errors gracefully."""
    workflow = EmailProcessingWorkflow()

    test_state = {
        'email_content': 'Based in Seattle',
        'sender_domain': 'test.com',
        'extraction_result': {
            'location': 'Seattle, WA'
        },
        'company_research': {}
    }

    mock_config = MagicMock()
    mock_config.enable_azure_maps = True
    mock_config.azure_maps_default_country = 'US'

    with patch('app.langgraph_manager.get_extraction_config', return_value=mock_config):
        # Mock Azure Maps client to raise an error
        mock_maps_client = AsyncMock()
        mock_maps_client.geocode_address.side_effect = Exception("API Error")

        with patch('app.langgraph_manager.get_azure_maps_client', return_value=mock_maps_client):
            with patch.object(workflow, 'client'):
                with patch('app.langgraph_manager.CompanyResearchService'):
                    with patch('app.langgraph_manager.RedisCacheManager'):
                        # Should not raise, just log error
                        result = await workflow.research_company(test_state)

        # Verify state doesn't have geo data
        assert test_state.get('geo') is None

        # Verify the function completed successfully despite geocoding error
        assert 'company_research' in result


@pytest.mark.asyncio
async def test_research_node_updates_research_result():
    """Test that research node updates research result with geocoded location."""
    workflow = EmailProcessingWorkflow()

    test_state = {
        'email_content': 'Candidate in Seattle area',
        'sender_domain': 'test.com',
        'extraction_result': {
            'location': 'Seattle'
        },
        'company_research': {}
    }

    mock_config = MagicMock()
    mock_config.enable_azure_maps = True
    mock_config.azure_maps_default_country = 'US'

    with patch('app.langgraph_manager.get_extraction_config', return_value=mock_config):
        mock_maps_client = AsyncMock()
        mock_maps_client.geocode_address.return_value = [{
            'latitude': 47.6062,
            'longitude': -122.3321,
            'address': {
                'municipality': 'Seattle',
                'countrySubdivisionName': 'Washington',
                'countrySubdivisionCode': 'WA',
                'freeformAddress': 'Seattle, WA'
            }
        }]

        with patch('app.langgraph_manager.get_azure_maps_client', return_value=mock_maps_client):
            with patch.object(workflow, 'client'):
                with patch('app.langgraph_manager.CompanyResearchService'):
                    with patch('app.langgraph_manager.RedisCacheManager'):
                        result = await workflow.research_company(test_state)

        # Verify research result was updated with city and state
        assert result['company_research'].get('city') == 'Seattle'
        assert result['company_research'].get('state') == 'Washington'


@pytest.mark.asyncio
async def test_research_node_location_priority():
    """Test location extraction priority: extraction > contact record > research."""
    workflow = EmailProcessingWorkflow()

    # Test with location in extraction_result
    test_state = {
        'email_content': 'Candidate info',
        'sender_domain': 'test.com',
        'extraction_result': {
            'location': 'Portland, OR',
            'contact_record': {
                'city': 'Seattle',
                'state': 'WA'
            }
        },
        'company_research': {
            'location': 'San Francisco, CA'
        }
    }

    mock_config = MagicMock()
    mock_config.enable_azure_maps = True
    mock_config.azure_maps_default_country = 'US'

    with patch('app.langgraph_manager.get_extraction_config', return_value=mock_config):
        mock_maps_client = AsyncMock()
        mock_maps_client.geocode_address.return_value = [{
            'latitude': 45.5152,
            'longitude': -122.6784,
            'address': {'municipality': 'Portland'}
        }]

        with patch('app.langgraph_manager.get_azure_maps_client', return_value=mock_maps_client):
            with patch.object(workflow, 'client'):
                with patch('app.langgraph_manager.CompanyResearchService'):
                    with patch('app.langgraph_manager.RedisCacheManager'):
                        result = await workflow.research_company(test_state)

        # Should use 'Portland, OR' from extraction_result
        mock_maps_client.geocode_address.assert_called_with(
            query='Portland, OR',
            country_filter='US'
        )