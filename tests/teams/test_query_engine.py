"""
Unit tests for Teams bot natural language query engine.

Tests query classification, filtering logic, and response formatting with mocked Zoho API calls.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from app.api.teams.query_engine import QueryEngine

pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_zoho_client():
    """Mock ZohoApiClient for testing."""
    with patch('app.integrations.ZohoApiClient') as mock_class:
        mock_instance = AsyncMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_openai():
    """Mock OpenAI API for intent classification."""
    with patch('openai.AsyncOpenAI') as mock_class:
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


@pytest.fixture
def sample_deals():
    """Sample deal data from Zoho CRM."""
    return [
        {
            'id': 'deal_001',
            'deal_name': 'Financial Advisor (New York, NY) - Morgan Stanley',
            'stage': 'Meeting Booked',
            'contact_name': 'John Doe',
            'account_name': 'Morgan Stanley',
            'owner_email': 'daniel.romitelli@emailthewell.com',
            'owner_name': 'Daniel Romitelli',
            'created_at': datetime(2025, 9, 15, 10, 30, 0),
            'modified_at': datetime(2025, 9, 20, 14, 15, 0),
            'closing_date': '2025-12-31',
            'amount': 150000.0,
            'description': 'Senior advisor looking to transition',
            'source': 'Referral',
            'source_detail': 'Brandon referred'
        },
        {
            'id': 'deal_002',
            'deal_name': 'Wealth Advisor (Chicago, IL) - Goldman Sachs',
            'stage': 'Closed Won',
            'contact_name': 'Jane Smith',
            'account_name': 'Goldman Sachs',
            'owner_email': 'steve@emailthewell.com',
            'owner_name': 'Steve Perry',
            'created_at': datetime(2025, 10, 1, 9, 0, 0),
            'modified_at': datetime(2025, 10, 5, 16, 30, 0),
            'closing_date': '2025-11-15',
            'amount': 200000.0,
            'description': 'Top performer with $500M AUM',
            'source': 'Website Inbound',
            'source_detail': None
        },
        {
            'id': 'deal_003',
            'deal_name': 'Investment Advisor (Boston, MA) - Fidelity',
            'stage': 'Lead',
            'contact_name': 'Mike Johnson',
            'account_name': 'Fidelity Investments',
            'owner_email': 'daniel.romitelli@emailthewell.com',
            'owner_name': 'Daniel Romitelli',
            'created_at': None,  # Test missing timestamp
            'modified_at': None,
            'closing_date': None,
            'amount': None,
            'description': None,
            'source': 'Email Inbound',
            'source_detail': None
        }
    ]


@pytest.fixture
def sample_meetings():
    """Sample meeting data from Zoho Events module."""
    return [
        {
            'id': 'event_001',
            'subject': 'Interview with John Doe',
            'event_title': 'Interview with John Doe',
            'start_datetime': datetime(2025, 10, 5, 14, 0, 0),
            'end_datetime': datetime(2025, 10, 5, 15, 0, 0),
            'meeting_date': datetime(2025, 10, 5, 14, 0, 0),
            'attendees': ['John Doe', 'Steve Perry', 'Daniel Romitelli'],
            'owner_email': 'steve@emailthewell.com',
            'owner_name': 'Steve Perry',
            'related_to': 'Financial Advisor (New York, NY) - Morgan Stanley',
            'related_to_id': 'deal_001',
            'related_module': 'Deals',
            'description': 'Initial screening interview',
            'location': 'Zoom',
            'created_at': datetime(2025, 10, 4, 10, 0, 0),
            'modified_at': datetime(2025, 10, 4, 10, 0, 0)
        },
        {
            'id': 'event_002',
            'subject': 'Client Meeting - Goldman Sachs',
            'event_title': 'Client Meeting - Goldman Sachs',
            'start_datetime': datetime(2025, 9, 28, 11, 0, 0),
            'end_datetime': datetime(2025, 9, 28, 12, 0, 0),
            'meeting_date': datetime(2025, 9, 28, 11, 0, 0),
            'attendees': ['Jane Smith', 'Brandon'],
            'owner_email': 'brandon@emailthewell.com',
            'owner_name': 'Brandon',
            'related_to': 'Wealth Advisor (Chicago, IL) - Goldman Sachs',
            'related_to_id': 'deal_002',
            'related_module': 'Deals',
            'description': 'Final interview before offer',
            'location': 'Office',
            'created_at': datetime(2025, 9, 27, 9, 0, 0),
            'modified_at': datetime(2025, 9, 27, 9, 0, 0)
        },
        {
            'id': 'event_003',
            'subject': 'Team Standup',
            'event_title': 'Team Standup',
            'start_datetime': None,  # Test missing timestamp
            'end_datetime': None,
            'meeting_date': None,
            'attendees': [],
            'owner_email': 'steve@emailthewell.com',
            'owner_name': 'Steve Perry',
            'related_to': None,
            'related_to_id': None,
            'related_module': None,
            'description': 'Weekly team sync',
            'location': None,
            'created_at': None,
            'modified_at': None
        }
    ]



async def test_deal_count_query(mock_zoho_client, mock_openai, sample_deals):
    """Test counting deals with correct response formatting."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "count",
        "table": "deals",
        "entities": {},
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API response
    mock_zoho_client.query_deals = AsyncMock(return_value=sample_deals)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="how many deals",
        user_email="steve@emailthewell.com"
    )

    # Verify correct count response wording
    assert result["text"] == "Found 3 deals."
    assert result["data"]["count"] == 3



async def test_deal_timeframe_filtering(mock_zoho_client, mock_openai, sample_deals):
    """Test deals filtered by timeframe (last month)."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "count",
        "table": "deals",
        "entities": {
            "timeframe": "last month"
        },
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API - should be called with date filters
    recent_deals = [d for d in sample_deals if d['created_at'] and d['created_at'] >= datetime(2025, 9, 1)]
    mock_zoho_client.query_deals = AsyncMock(return_value=recent_deals)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="how many deals last month",
        user_email="steve@emailthewell.com"
    )

    # Verify Zoho was called with date filters
    call_kwargs = mock_zoho_client.query_deals.call_args.kwargs
    assert "from_date" in call_kwargs
    assert "to_date" in call_kwargs

    # Verify count is correct
    assert result["data"]["count"] == len(recent_deals)



async def test_deal_stage_filtering(mock_zoho_client, mock_openai, sample_deals):
    """Test deals filtered by stage."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "list",
        "table": "deals",
        "entities": {
            "stage": "Meeting Booked"
        },
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API
    meeting_booked_deals = [d for d in sample_deals if d['stage'] == 'Meeting Booked']
    mock_zoho_client.query_deals = AsyncMock(return_value=meeting_booked_deals)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="show me deals in Meeting Booked stage",
        user_email="steve@emailthewell.com"
    )

    # Verify stage filter was applied
    call_kwargs = mock_zoho_client.query_deals.call_args.kwargs
    assert call_kwargs["stage"] == "Meeting Booked"

    # Verify results
    assert len(result["data"]) == 1
    assert result["data"][0]["stage"] == "Meeting Booked"



async def test_deal_name_search(mock_zoho_client, mock_openai, sample_deals):
    """Test client-side filtering by contact/account name."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "search",
        "table": "deals",
        "entities": {
            "entity_name": "Goldman Sachs"
        },
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API returns all deals
    mock_zoho_client.query_deals = AsyncMock(return_value=sample_deals)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="find deals with Goldman Sachs",
        user_email="steve@emailthewell.com"
    )

    # Verify client-side filtering worked
    assert len(result["data"]) == 1
    assert result["data"][0]["account_name"] == "Goldman Sachs"



async def test_deal_datetime_none_fallback(mock_zoho_client, mock_openai, sample_deals):
    """Test deals with missing created_at show 'N/A' instead of crashing."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "list",
        "table": "deals",
        "entities": {},
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API - include deal with None timestamp
    mock_zoho_client.query_deals = AsyncMock(return_value=sample_deals)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="list all deals",
        user_email="steve@emailthewell.com"
    )

    # Verify no crash and result contains 'N/A' for missing date
    assert result is not None
    assert "N/A" in result["text"]



async def test_meeting_count_query(mock_zoho_client, mock_openai, sample_meetings):
    """Test counting meetings with correct response formatting."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "count",
        "table": "meetings",
        "entities": {},
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API response
    mock_zoho_client.query_meetings = AsyncMock(return_value=sample_meetings)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="how many meetings",
        user_email="steve@emailthewell.com"
    )

    # Verify correct count response wording
    assert result["text"] == "Found 3 meetings."
    assert result["data"]["count"] == 3



async def test_meeting_timeframe_filtering(mock_zoho_client, mock_openai, sample_meetings):
    """Test meetings filtered by timeframe (last week)."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "list",
        "table": "meetings",
        "entities": {
            "timeframe": "last week"
        },
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API
    recent_meetings = [m for m in sample_meetings if m['meeting_date'] and m['meeting_date'] >= datetime.now() - timedelta(days=7)]
    mock_zoho_client.query_meetings = AsyncMock(return_value=recent_meetings)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="show me meetings from last week",
        user_email="steve@emailthewell.com"
    )

    # Verify Zoho was called with date filters
    call_kwargs = mock_zoho_client.query_meetings.call_args.kwargs
    assert "from_date" in call_kwargs
    assert "to_date" in call_kwargs



async def test_meeting_name_search_or_logic(mock_zoho_client, mock_openai, sample_meetings):
    """Test client-side OR filtering for meeting name (title OR related_to)."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "search",
        "table": "meetings",
        "entities": {
            "entity_name": "Goldman Sachs"
        },
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API returns all meetings
    mock_zoho_client.query_meetings = AsyncMock(return_value=sample_meetings)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="meetings with Goldman Sachs",
        user_email="steve@emailthewell.com"
    )

    # Verify client-side OR filtering worked
    # Meeting 002 has "Goldman Sachs" in both subject and related_to
    assert len(result["data"]) == 1
    assert "Goldman Sachs" in result["data"][0]["subject"]



async def test_meeting_datetime_none_fallback(mock_zoho_client, mock_openai, sample_meetings):
    """Test meetings with missing meeting_date show 'N/A' instead of crashing."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "list",
        "table": "meetings",
        "entities": {},
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API - include meeting with None timestamp
    mock_zoho_client.query_meetings = AsyncMock(return_value=sample_meetings)

    # Execute query
    engine = QueryEngine()
    result = await engine.process_query(
        query="list all meetings",
        user_email="steve@emailthewell.com"
    )

    # Verify no crash and result contains 'N/A' for missing date
    assert result is not None
    assert "N/A" in result["text"]



async def test_meeting_owner_filtering_regular_user(mock_zoho_client, mock_openai, sample_meetings):
    """Test regular users only see their own meetings."""
    # Mock OpenAI intent classification
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "intent_type": "list",
        "table": "meetings",
        "entities": {},
        "filters": {}
    }"""
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    # Mock Zoho API
    user_meetings = [m for m in sample_meetings if m['owner_email'] == 'brandon@emailthewell.com']
    mock_zoho_client.query_meetings = AsyncMock(return_value=user_meetings)

    # Execute query with regular user email
    engine = QueryEngine()
    result = await engine.process_query(
        query="show my meetings",
        user_email="brandon@emailthewell.com"
    )

    # Verify owner filter applied
    call_kwargs = mock_zoho_client.query_meetings.call_args.kwargs
    assert call_kwargs["owner_email"] == "brandon@emailthewell.com"

    # Verify only brandon's meeting returned
    assert len(result["data"]) == 1
    assert result["data"][0]["owner_email"] == "brandon@emailthewell.com"
