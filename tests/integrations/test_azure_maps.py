"""
Unit tests for Azure Maps geocoding client.
Tests geocoding, reverse geocoding, caching, and error handling.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from datetime import timedelta

from app.integrations.azure_maps import AzureMapsClient, get_azure_maps_client


@pytest.mark.asyncio
async def test_geocode_address_success():
    """Test successful geocoding."""
    client = AzureMapsClient()

    # Mock the API key
    with patch.object(client, '_ensure_api_key', return_value='test-key'):
        # Mock the HTTP response
        mock_response = {
            "results": [{
                "position": {"lat": 47.6062, "lon": -122.3321},
                "address": {
                    "freeformAddress": "Seattle, WA",
                    "municipality": "Seattle",
                    "countrySubdivisionName": "Washington",
                    "countrySubdivisionCode": "WA",
                    "countryCode": "US"
                },
                "confidence": 0.95,
                "type": "Geography"
            }]
        }

        with patch.object(client, '_http_get', return_value=mock_response) as mock_http:
            # Mock cache manager
            mock_cache = AsyncMock()
            mock_cache.get.return_value = None

            with patch('app.integrations.azure_maps.get_cache_manager', return_value=mock_cache):
                results = await client.geocode_address("Seattle, WA", country_filter="US")

            # Verify results
            assert results is not None
            assert len(results) == 1
            assert results[0]["latitude"] == 47.6062
            assert results[0]["longitude"] == -122.3321
            assert results[0]["address"]["municipality"] == "Seattle"
            assert results[0]["confidence"] == 0.95

            # Verify cache was set
            mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_reverse_geocode_success():
    """Test successful reverse geocoding."""
    client = AzureMapsClient()

    with patch.object(client, '_ensure_api_key', return_value='test-key'):
        mock_response = {
            "addresses": [{
                "address": {
                    "freeformAddress": "909 5th Avenue, Seattle, WA 98164",
                    "buildingNumber": "909",
                    "street": "5th Avenue",
                    "municipality": "Seattle",
                    "countrySubdivisionName": "Washington",
                    "postalCode": "98164"
                }
            }]
        }

        with patch.object(client, '_http_get', return_value=mock_response):
            mock_cache = AsyncMock()
            mock_cache.get.return_value = None

            with patch('app.integrations.azure_maps.get_cache_manager', return_value=mock_cache):
                result = await client.reverse_geocode(47.6064, -122.3316)

            assert result is not None
            assert result["latitude"] == 47.6064
            assert result["longitude"] == -122.3316
            assert result["formatted_address"] == "909 5th Avenue, Seattle, WA 98164"
            assert result["address"]["municipality"] == "Seattle"


@pytest.mark.asyncio
async def test_geocode_with_cache_hit():
    """Test that cached results are returned without making HTTP call."""
    client = AzureMapsClient()

    cached_data = [{
        "latitude": 47.6062,
        "longitude": -122.3321,
        "address": {"municipality": "Seattle"}
    }]

    with patch.object(client, '_ensure_api_key', return_value='test-key'):
        # Mock cache with existing data
        mock_cache = AsyncMock()
        mock_cache.get.return_value = json.dumps(cached_data)

        with patch('app.integrations.azure_maps.get_cache_manager', return_value=mock_cache):
            with patch.object(client, '_http_get') as mock_http:
                results = await client.geocode_address("Seattle, WA")

            # Verify cached results are returned
            assert results == cached_data

            # Verify no HTTP call was made
            mock_http.assert_not_called()

            # Verify cache.set was not called (already cached)
            mock_cache.set.assert_not_called()


@pytest.mark.asyncio
async def test_geocode_with_retry_on_timeout():
    """Test retry logic on timeout."""
    client = AzureMapsClient()
    client.max_retries = 2

    with patch.object(client, '_ensure_api_key', return_value='test-key'):
        # First two calls timeout, third succeeds
        mock_response = {
            "results": [{"position": {"lat": 47.6, "lon": -122.3}}]
        }

        side_effects = [
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            mock_response
        ]

        with patch.object(client, '_http_get', side_effect=side_effects) as mock_http:
            mock_cache = AsyncMock()
            mock_cache.get.return_value = None

            with patch('app.integrations.azure_maps.get_cache_manager', return_value=mock_cache):
                with patch('asyncio.sleep'):  # Mock sleep to speed up test
                    results = await client.geocode_address("Seattle")

            # Verify retries occurred
            assert mock_http.call_count == 3
            assert results[0]["latitude"] == 47.6


@pytest.mark.asyncio
async def test_geocode_fails_after_max_retries():
    """Test that geocoding fails after max retries."""
    client = AzureMapsClient()
    client.max_retries = 2

    with patch.object(client, '_ensure_api_key', return_value='test-key'):
        with patch.object(client, '_http_get', side_effect=httpx.TimeoutException("timeout")):
            mock_cache = AsyncMock()
            mock_cache.get.return_value = None

            with patch('app.integrations.azure_maps.get_cache_manager', return_value=mock_cache):
                with patch('asyncio.sleep'):  # Mock sleep to speed up test
                    with pytest.raises(httpx.TimeoutException):
                        await client.geocode_address("Seattle")


@pytest.mark.asyncio
async def test_geocode_skips_url_like_queries():
    """Test that URL-like queries are skipped."""
    client = AzureMapsClient()

    with patch.object(client, '_ensure_api_key', return_value='test-key'):
        # Test various URL patterns
        urls = [
            "http://example.com",
            "https://example.com",
            "www.example.com",
            "example.com/path"
        ]

        for url in urls:
            result = await client.geocode_address(url)
            assert result is None


@pytest.mark.asyncio
async def test_geocode_without_api_key():
    """Test behavior when API key is not available."""
    client = AzureMapsClient()

    with patch.object(client, '_ensure_api_key', return_value=None):
        result = await client.geocode_address("Seattle, WA")
        assert result is None


@pytest.mark.asyncio
async def test_geocode_with_location_bias():
    """Test geocoding with location bias (fuzzy search)."""
    client = AzureMapsClient()

    with patch.object(client, '_ensure_api_key', return_value='test-key'):
        mock_response = {
            "results": [{"position": {"lat": 47.6, "lon": -122.3}}]
        }

        with patch.object(client, '_http_get', return_value=mock_response) as mock_http:
            mock_cache = AsyncMock()
            mock_cache.get.return_value = None

            with patch('app.integrations.azure_maps.get_cache_manager', return_value=mock_cache):
                results = await client.geocode_address(
                    "Starbucks",
                    lat=47.6062,
                    lon=-122.3321,
                    radius_m=5000
                )

            # Verify fuzzy search endpoint was called with correct params
            mock_http.assert_called_once()
            args, kwargs = mock_http.call_args
            assert "/search/fuzzy/json" in args[0]
            assert args[1]["lat"] == 47.6062
            assert args[1]["lon"] == -122.3321
            assert args[1]["radius"] == 5000


@pytest.mark.asyncio
async def test_get_azure_maps_client_singleton():
    """Test that get_azure_maps_client returns singleton instance."""
    client1 = await get_azure_maps_client()
    client2 = await get_azure_maps_client()

    assert client1 is client2


@pytest.mark.asyncio
async def test_geocode_disabled_in_config():
    """Test behavior when Azure Maps is disabled in config."""
    client = AzureMapsClient()
    client.config.enable_azure_maps = False

    result = await client.geocode_address("Seattle, WA")
    assert result is None

    # Verify API key was not loaded
    assert client._api_key is None


@pytest.mark.asyncio
async def test_cache_key_generation():
    """Test deterministic cache key generation."""
    client = AzureMapsClient()

    # Same params should generate same key
    key1 = client._cache_key("geocode", {"q": "Seattle", "country": "US"})
    key2 = client._cache_key("geocode", {"q": "Seattle", "country": "US"})
    assert key1 == key2

    # Different params should generate different keys
    key3 = client._cache_key("geocode", {"q": "Portland", "country": "US"})
    assert key1 != key3

    # Different prefixes should generate different keys
    key4 = client._cache_key("reverse", {"q": "Seattle", "country": "US"})
    assert key1 != key4