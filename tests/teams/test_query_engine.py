"""
Unit tests for Teams bot natural language query engine.

Tests query classification, filtering logic, and response formatting with mocked Zoho API calls.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from app.api.teams.query_engine import QueryEngine


@pytest.fixture
def mock_zoho_client():
    """Mock ZohoApiClient for testing."""
    with patch('app.api.teams.query_engine.ZohoApiClient') as mock_class:
        mock_instance = AsyncMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_openai():
    """Mock OpenAI API for intent classification."""
    with patch('app.api.teams.query_engine.AsyncOpenAI') as mock_class:
        mock_client = MagicMock()
        mock_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_vault_candidates():
    """Sample vault candidate data."""
    return [
        {
            'candidate_name': 'Chad Terry',
            'candidate_locator': 'TWAV118252',
            'job_title': 'CEO',
            'location': 'Des Moines, IA',
            'date_published': '2025-10-06',
            'transcript_url': 'https://zoom.us/rec/share/ABC123',
            'meeting_id': 'meeting_001'
        },
        {
            'candidate_name': 'John Smith',
            'candidate_locator': 'TWAV118220',
            'job_title': 'CFO',
            'location': 'Portland, OR',
            'date_published': '2025-09-25',
            'transcript_url': 'https://zoom.us/rec/share/XYZ789',
            'meeting_id': 'meeting_002'
        },
        {
            'candidate_name': 'Jane Doe',
            'candidate_locator': 'TWAV118203',
            'job_title': 'VP Sales',
            'location': 'Seattle, WA',
            'date_published': '2025-10-01',
            'transcript_url': None,
            'meeting_id': None
        }
    ]


@pytest.mark.asyncio
async def test_candidate_locator_query(mock_zoho_client, mock_openai, sample_vault_candidates):
    """Test querying by Candidate Locator ID."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "search",
        "table": "vault_candidates",
        "entities": {
            "candidate_locator": "TWAV118252"
        },
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API response
    mock_zoho_client.query_candidates = AsyncMock(return_value=sample_vault_candidates[:1])

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="show me TWAV118252",
        user_email="steve@emailthewell.com"
    )

    # Verify results
    assert result is not None
    assert "Chad Terry" in result["text"]
    assert result["data"][0]["candidate_locator"] == "TWAV118252"


@pytest.mark.asyncio
async def test_timeframe_filtering_last_week(mock_zoho_client, mock_openai, sample_vault_candidates):
    """Test 'last week' timeframe converts to date filters."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "count",
        "table": "vault_candidates",
        "entities": {
            "timeframe": "last week"
        },
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API response with recent candidates only
    recent_candidates = [c for c in sample_vault_candidates if c['date_published'] >= '2025-10-01']
    mock_zoho_client.query_candidates = AsyncMock(return_value=recent_candidates)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="how many interviews last week",
        user_email="steve@emailthewell.com"
    )

    # Verify Zoho was called with date filters
    call_kwargs = mock_zoho_client.query_candidates.call_args.kwargs
    assert "from_date" in call_kwargs
    assert "to_date" in call_kwargs

    # Verify count is correct
    assert result["data"]["count"] == len(recent_candidates)


@pytest.mark.asyncio
async def test_base_limit_raised(mock_zoho_client, mock_openai):
    """Test base limit is 500, not 100."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "list",
        "table": "vault_candidates",
        "entities": {},
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API response with 144 candidates
    mock_candidates = [
        {
            'candidate_name': f'Candidate {i}',
            'candidate_locator': f'TWAV{118000 + i}',
            'job_title': 'Advisor',
            'location': 'USA',
            'date_published': '2025-09-15'
        }
        for i in range(144)
    ]
    mock_zoho_client.query_candidates = AsyncMock(return_value=mock_candidates)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="list all vault candidates",
        user_email="steve@emailthewell.com"
    )

    # Verify Zoho was called with limit=500
    call_kwargs = mock_zoho_client.query_candidates.call_args.kwargs
    assert call_kwargs["limit"] == 500

    # Verify all 144 candidates returned
    assert len(result["data"]) == 144


@pytest.mark.asyncio
async def test_name_search_filtering(mock_zoho_client, mock_openai, sample_vault_candidates):
    """Test client-side name filtering works."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "search",
        "table": "vault_candidates",
        "entities": {
            "candidate_name": "John Smith"
        },
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API returns all candidates
    mock_zoho_client.query_candidates = AsyncMock(return_value=sample_vault_candidates)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="show me John Smith",
        user_email="steve@emailthewell.com"
    )

    # Verify only John Smith returned
    assert len(result["data"]) == 1
    assert result["data"][0]["candidate_name"] == "John Smith"


@pytest.mark.asyncio
async def test_executive_access_no_owner_filter(mock_zoho_client, mock_openai, sample_vault_candidates):
    """Test executive users get full data access."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "list",
        "table": "vault_candidates",
        "entities": {},
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API
    mock_zoho_client.query_candidates = AsyncMock(return_value=sample_vault_candidates)

    # Execute query with executive email
    engine = QueryEngine()
    result = await engine.process_query(
        query="list all candidates",
        user_email="steve@emailthewell.com"  # CEO - executive access
    )

    # Verify no owner filter applied
    call_kwargs = mock_zoho_client.query_candidates.call_args.kwargs
    assert "owner" not in call_kwargs

    # Verify all candidates returned
    assert len(result["data"]) == 3


@pytest.mark.asyncio
async def test_regular_user_owner_filter(mock_zoho_client, mock_openai, sample_vault_candidates):
    """Test regular users get owner-filtered data."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "list",
        "table": "vault_candidates",
        "entities": {},
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API
    mock_zoho_client.query_candidates = AsyncMock(return_value=sample_vault_candidates[:1])

    # Execute query with regular user email
    engine = QueryEngine()
    result = await engine.process_query(
        query="list my candidates",
        user_email="recruiter@emailthewell.com"  # Regular user
    )

    # Verify owner filter applied
    call_kwargs = mock_zoho_client.query_candidates.call_args.kwargs
    assert call_kwargs["owner"] == "recruiter@emailthewell.com"


@pytest.mark.asyncio
async def test_month_filtering_september(mock_zoho_client, mock_openai, sample_vault_candidates):
    """Test September timeframe generates correct date range."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "list",
        "table": "vault_candidates",
        "entities": {
            "timeframe": "September"
        },
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API
    september_candidates = [c for c in sample_vault_candidates if c['date_published'].startswith('2025-09')]
    mock_zoho_client.query_candidates = AsyncMock(return_value=september_candidates)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="show me vault candidates from September",
        user_email="steve@emailthewell.com"
    )

    # Verify date filters
    call_kwargs = mock_zoho_client.query_candidates.call_args.kwargs
    assert call_kwargs["from_date"] == "2025-09-01"
    assert call_kwargs["to_date"] == "2025-09-30"

    # Verify only September candidates returned
    assert len(result["data"]) == 1
    assert result["data"][0]["candidate_name"] == "John Smith"
