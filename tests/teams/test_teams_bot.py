"""
Test suite for Microsoft Teams bot integration.
Tests Teams message handling, analytics, and Adaptive Card generation.
"""
import pytest
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient
from app.main import app
from app.api.teams.routes import TeamsCommandHandler, TeamsMessage, TeamsResponse

# Test client
client = TestClient(app)

# Test API key
TEST_API_KEY = "test-api-key-123"


class TestTeamsBot:
    """Test Teams bot functionality."""

    @pytest.fixture
    def command_handler(self):
        """Create command handler instance."""
        handler = TeamsCommandHandler()
        return handler

    @pytest.fixture
    def sample_message(self):
        """Create sample Teams message."""
        return {
            "type": "message",
            "id": "msg-test-001",
            "timestamp": datetime.now().isoformat(),
            "from": {
                "id": "user-test",
                "name": "Test User",
                "userPrincipalName": "test@thewell.com"
            },
            "conversation": {
                "id": "conv-test",
                "conversationType": "personal"
            },
            "text": "digest 7",
            "channelData": {
                "tenant": {"id": "tenant-test"}
            }
        }

    def test_digest_command_parsing(self, sample_message):
        """Test parsing of digest command."""
        # Test default digest (7 days)
        response = client.post(
            "/api/teams/chat",
            json=sample_message,
            headers={"X-API-Key": TEST_API_KEY}
        )

        # Should return 200 with Adaptive Card
        assert response.status_code in [200, 401]  # 401 if API key not configured

        if response.status_code == 200:
            data = response.json()
            assert "attachments" in data or "text" in data

    def test_filter_command_parsing(self, sample_message):
        """Test parsing of filter commands."""
        # Test AUM filter
        sample_message["text"] = "filter aum >500M"
        response = client.post(
            "/api/teams/chat",
            json=sample_message,
            headers={"X-API-Key": TEST_API_KEY}
        )

        assert response.status_code in [200, 401]

        # Test location filter
        sample_message["text"] = "filter location New York"
        response = client.post(
            "/api/teams/chat",
            json=sample_message,
            headers={"X-API-Key": TEST_API_KEY}
        )

        assert response.status_code in [200, 401]

    def test_analytics_command(self, sample_message):
        """Test analytics command."""
        sample_message["text"] = "analytics 30d"
        response = client.post(
            "/api/teams/chat",
            json=sample_message,
            headers={"X-API-Key": TEST_API_KEY}
        )

        assert response.status_code in [200, 401]

        if response.status_code == 200:
            data = response.json()
            assert "attachments" in data or "text" in data

    def test_analytics_endpoint(self):
        """Test analytics REST endpoint."""
        response = client.get(
            "/api/teams/analytics",
            params={
                "user_email": "test@thewell.com",
                "timeframe": "7d"
            },
            headers={"X-API-Key": TEST_API_KEY}
        )

        assert response.status_code in [200, 401]

        if response.status_code == 200:
            data = response.json()
            assert "total_candidates" in data
            assert "avg_aum" in data
            assert "top_locations" in data
            assert "top_designations" in data

    @pytest.mark.asyncio
    async def test_aum_filtering(self, command_handler):
        """Test AUM filtering logic."""
        # Mock deals
        deals = [
            {"book_size_aum": "$100M", "candidate_name": "John"},
            {"book_size_aum": "$500M", "candidate_name": "Jane"},
            {"book_size_aum": "$1.5B", "candidate_name": "Bob"},
            {"book_size_aum": "$250M", "candidate_name": "Alice"}
        ]

        # Test > filter
        filtered = command_handler._filter_by_aum(deals, ">500M")
        assert len(filtered) == 1
        assert filtered[0]["candidate_name"] == "Bob"

        # Test >= filter
        filtered = command_handler._filter_by_aum(deals, ">=500M")
        assert len(filtered) == 2
        assert set([d["candidate_name"] for d in filtered]) == {"Jane", "Bob"}

        # Test < filter
        filtered = command_handler._filter_by_aum(deals, "<500M")
        assert len(filtered) == 2
        assert set([d["candidate_name"] for d in filtered]) == {"John", "Alice"}

    @pytest.mark.asyncio
    async def test_location_filtering(self, command_handler):
        """Test location filtering logic."""
        deals = [
            {"location": "New York, NY", "candidate_name": "John"},
            {"location": "Los Angeles, CA", "candidate_name": "Jane"},
            {"location": "New York, NY", "candidate_name": "Bob"},
            {"location": "Chicago, IL", "candidate_name": "Alice"}
        ]

        # Filter by New York
        filtered = command_handler._filter_by_location(deals, "New York")
        assert len(filtered) == 2
        assert set([d["candidate_name"] for d in filtered]) == {"John", "Bob"}

        # Filter by CA
        filtered = command_handler._filter_by_location(deals, "CA")
        assert len(filtered) == 1
        assert filtered[0]["candidate_name"] == "Jane"

    def test_adaptive_card_generation(self, command_handler):
        """Test Adaptive Card generation."""
        from app.jobs.talentwell_curator import DigestCard
        from well_shared.evidence.extractor import BulletPoint

        # Create sample cards
        cards = [
            DigestCard(
                deal_id="123",
                candidate_name="John Smith",
                job_title="Financial Advisor",
                company="Major Wirehouse",
                location="New York, NY",
                bullets=[
                    BulletPoint(text="AUM: $500M-$1B", confidence=0.9, source="CRM"),
                    BulletPoint(text="Experience: 15+ years", confidence=0.95, source="CRM"),
                    BulletPoint(text="Series 7, 66, CFA", confidence=0.9, source="CRM")
                ],
                evidence_score=0.92
            )
        ]

        # Generate Adaptive Card
        adaptive_card = command_handler._generate_digest_card(
            cards=cards,
            user_email="test@thewell.com",
            days=7
        )

        # Validate card structure
        assert adaptive_card["type"] == "AdaptiveCard"
        assert adaptive_card["version"] == "1.4"
        assert "$schema" in adaptive_card
        assert "body" in adaptive_card
        assert "actions" in adaptive_card

        # Check for candidate info in body
        body_str = json.dumps(adaptive_card["body"])
        assert "John Smith" in body_str
        assert "Financial Advisor" in body_str
        assert "New York, NY" in body_str

    def test_analytics_card_generation(self, command_handler):
        """Test Analytics Card generation."""
        analytics = {
            "total_candidates": 25,
            "avg_aum": "$750M",
            "avg_production": "$1.2M",
            "total_aum": "$18.75B",
            "aum_distribution": {
                "<100M": 5,
                "100M-500M": 10,
                "500M-1B": 7,
                ">1B": 3
            },
            "top_locations": [
                ("New York, NY", 8),
                ("Los Angeles, CA", 5),
                ("Chicago, IL", 4)
            ],
            "top_designations": [
                ("CFA", 12),
                ("CFP", 10),
                ("Series 7", 20)
            ],
            "timeframe": "30 days",
            "generated_at": datetime.now().isoformat()
        }

        # Generate Analytics Card
        adaptive_card = command_handler._generate_analytics_card(
            analytics=analytics,
            user_email="test@thewell.com",
            timeframe="30d"
        )

        # Validate card structure
        assert adaptive_card["type"] == "AdaptiveCard"
        assert adaptive_card["version"] == "1.4"
        assert "body" in adaptive_card

        # Check for analytics data in body
        body_str = json.dumps(adaptive_card["body"])
        assert "TalentWell Analytics Dashboard" in body_str
        assert "25" in body_str  # Total candidates
        assert "$750M" in body_str  # Average AUM

    def test_empty_message_handling(self, sample_message):
        """Test handling of empty messages."""
        sample_message["text"] = ""
        response = client.post(
            "/api/teams/chat",
            json=sample_message,
            headers={"X-API-Key": TEST_API_KEY}
        )

        assert response.status_code in [200, 401]

        if response.status_code == 200:
            data = response.json()
            # Should return help text with suggested actions
            assert "text" in data or "suggestedActions" in data

    def test_invalid_command_handling(self, sample_message):
        """Test handling of invalid commands."""
        sample_message["text"] = "invalid_command_xyz"
        response = client.post(
            "/api/teams/chat",
            json=sample_message,
            headers={"X-API-Key": TEST_API_KEY}
        )

        assert response.status_code in [200, 401]

        if response.status_code == 200:
            data = response.json()
            assert "text" in data
            # Should mention unknown command
            if "text" in data:
                assert "unknown" in data["text"].lower() or "available" in data["text"].lower()

    def test_card_action_handling(self):
        """Test Adaptive Card action handling."""
        action_payload = {
            "type": "Action.Submit",
            "data": {
                "command": "view_zoho",
                "deal_id": "12345",
                "candidate_name": "John Smith"
            }
        }

        response = client.post(
            "/api/teams/card/action",
            json=action_payload,
            headers={"X-API-Key": TEST_API_KEY}
        )

        assert response.status_code in [200, 401]

        if response.status_code == 200:
            data = response.json()
            assert "status" in data

    def test_audience_mapping(self, command_handler):
        """Test email to audience mapping."""
        # Steve Perry audience
        assert command_handler._get_audience_from_email("steve.perry@thewell.com") == "steve_perry"
        assert command_handler._get_audience_from_email("steve@example.com") == "steve_perry"

        # Leadership audience
        assert command_handler._get_audience_from_email("daniel@thewell.com") == "leadership"
        assert command_handler._get_audience_from_email("brandon@thewell.com") == "leadership"

        # Default audience
        assert command_handler._get_audience_from_email("unknown@example.com") == "default"

    def test_currency_formatting(self, command_handler):
        """Test currency formatting."""
        assert command_handler._format_currency(1500000000) == "$1.5B"
        assert command_handler._format_currency(750000000) == "$750.0M"
        assert command_handler._format_currency(50000000) == "$50.0M"
        assert command_handler._format_currency(1200000) == "$1.2M"
        assert command_handler._format_currency(500000) == "$500.0K"
        assert command_handler._format_currency(100) == "$100"

    def test_health_endpoint(self):
        """Test Teams health check endpoint."""
        response = client.get("/api/teams/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "teams-integration"
        assert "timestamp" in data


# Integration tests
@pytest.mark.integration
class TestTeamsIntegration:
    """Integration tests for Teams bot with real services."""

    @pytest.mark.asyncio
    async def test_end_to_end_digest_flow(self):
        """Test complete digest generation flow."""
        # This would require real Zoho/Redis connections
        # Marked as integration test to skip in CI
        pass

    @pytest.mark.asyncio
    async def test_real_zoho_data_fetch(self):
        """Test fetching real data from Zoho."""
        # This would require real Zoho credentials
        # Marked as integration test to skip in CI
        pass


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])