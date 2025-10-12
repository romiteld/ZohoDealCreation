import asyncio
import pytest
from unittest.mock import MagicMock

from app.config.candidate_keywords import normalize_candidate_type
from app.integrations import ZohoApiClient


def test_query_candidates_respects_advisor_keywords(monkeypatch):
    client = ZohoApiClient()
    sample_response = {
        "data": [
            {
                "id": "1",
                "Full_Name": "Alex Morgan",
                "Candidate_Locator": "TWAV200001",
                "Designation": "Senior Vice President, Wealth Management",
                "Employer": "Fidelity",
                "Current_Location": "Austin, TX",
                "Publish_to_Vault": True,
                "Date_Published_to_Vault": "2025-10-01T00:00:00+00:00",
            },
            {
                "id": "2",
                "Full_Name": "Jordan Blake",
                "Candidate_Locator": "TWAV200002",
                "Designation": "Managing Partner",
                "Employer": "Private RIA",
                "Current_Location": "Denver, CO",
                "Publish_to_Vault": True,
                "Date_Published_to_Vault": "2025-10-01T00:00:00+00:00",
            },
        ]
    }
    monkeypatch.setattr(client, "_make_request", MagicMock(return_value=sample_response))

    results = asyncio.run(
        client.query_candidates(
        limit=10,
        candidate_type="advisor",
        published_to_vault=True,
    ))

    assert len(results) == 1
    assert results[0]["candidate_locator"] == "TWAV200001"


def test_query_candidates_respects_executive_keywords(monkeypatch):
    client = ZohoApiClient()
    sample_response = {
        "data": [
            {
                "id": "1",
                "Full_Name": "Alex Morgan",
                "Candidate_Locator": "TWAV200001",
                "Designation": "Senior Vice President, Wealth Management",
                "Employer": "Fidelity",
                "Current_Location": "Austin, TX",
                "Publish_to_Vault": True,
                "Date_Published_to_Vault": "2025-10-01T00:00:00+00:00",
            },
            {
                "id": "2",
                "Full_Name": "Jordan Blake",
                "Candidate_Locator": "TWAV200002",
                "Designation": "Managing Partner",
                "Employer": "Private RIA",
                "Current_Location": "Denver, CO",
                "Publish_to_Vault": True,
                "Date_Published_to_Vault": "2025-10-01T00:00:00+00:00",
            },
        ]
    }
    monkeypatch.setattr(client, "_make_request", MagicMock(return_value=sample_response))

    results = asyncio.run(
        client.query_candidates(
        limit=10,
        candidate_type="executives",
        published_to_vault=True,
    ))

    assert len(results) == 1
    assert results[0]["candidate_locator"] == "TWAV200002"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Advisor", "advisors"),
        ("c-suite", "c_suite"),
        ("executives", "c_suite"),
        ("unknown", None),
    ],
)
def test_normalize_candidate_type_handles_synonyms(raw, expected):
    assert normalize_candidate_type(raw) == expected
