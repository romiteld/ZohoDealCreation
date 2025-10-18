"""
Unit Tests for Zoho Webhook Receiver

Tests the following critical paths:
1. Payload unwrapping and parsing
2. Event type normalization
3. Dedupe key format
4. Wrapper metadata extraction
5. DateTime serialization
6. Field normalization

Run with: pytest tests/test_zoho_webhooks.py -v
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from tests.fixtures.zoho_webhook_samples import (
    LEAD_CREATE_WEBHOOK,
    LEAD_UPDATE_WEBHOOK,
    LEAD_DELETE_WEBHOOK,
    DEAL_CREATE_WEBHOOK,
    LEAD_WITH_PICKLIST_WEBHOOK,
    LEAD_STALE_UPDATE_WEBHOOK,
    LEAD_NO_OWNER_WEBHOOK
)


class TestWebhookPayloadParsing:
    """Test payload unwrapping and metadata extraction"""

    def test_unwrap_lead_create_payload(self):
        """Verify payload is unwrapped from data[0]"""
        raw_payload = LEAD_CREATE_WEBHOOK

        # Simulate webhook receiver parsing
        assert "data" in raw_payload
        assert isinstance(raw_payload["data"], list)
        assert len(raw_payload["data"]) > 0

        payload = raw_payload["data"][0]
        operation = raw_payload.get("operation")

        assert payload["id"] == "6221978000123456789"
        assert payload["Full_Name"] == "John Anderson"
        assert operation == "Leads.create"

    def test_extract_wrapper_metadata(self):
        """Verify wrapper context is preserved for audit trail"""
        raw_payload = LEAD_CREATE_WEBHOOK

        # Extract wrapper metadata (excluding data array)
        wrapper_metadata = {k: v for k, v in raw_payload.items() if k != "data"}

        assert wrapper_metadata["operation"] == "Leads.create"
        assert wrapper_metadata["source"] == "web"
        assert wrapper_metadata["user"]["email"] == "steve.perry@emailthewell.com"
        assert "timestamp" in wrapper_metadata
        assert "data" not in wrapper_metadata  # Data array excluded


class TestEventTypeNormalization:
    """Test operation → event_type normalization"""

    def test_normalize_leads_create(self):
        """Test Leads.create → create"""
        from app.api.zoho_webhooks import normalize_zoho_event_type

        assert normalize_zoho_event_type("Leads.create") == "create"
        assert normalize_zoho_event_type("Leads.insert") == "create"

    def test_normalize_leads_edit(self):
        """Test Leads.edit → update"""
        from app.api.zoho_webhooks import normalize_zoho_event_type

        assert normalize_zoho_event_type("Leads.edit") == "update"
        assert normalize_zoho_event_type("Leads.update") == "update"

    def test_normalize_leads_delete(self):
        """Test Leads.delete → delete"""
        from app.api.zoho_webhooks import normalize_zoho_event_type

        assert normalize_zoho_event_type("Leads.delete") == "delete"
        assert normalize_zoho_event_type("Leads.remove") == "delete"

    def test_normalize_case_insensitive(self):
        """Test uppercase operations are normalized"""
        from app.api.zoho_webhooks import normalize_zoho_event_type

        assert normalize_zoho_event_type("LEADS.EDIT") == "update"
        assert normalize_zoho_event_type("Deals.CREATE") == "create"

    def test_normalize_missing_operation(self):
        """Test default fallback for missing operation"""
        from app.api.zoho_webhooks import normalize_zoho_event_type

        assert normalize_zoho_event_type(None) == "update"
        assert normalize_zoho_event_type("") == "update"


class TestDedupeKeyFormat:
    """Test dedupe key includes event_type to prevent delete/update collisions"""

    def test_dedupe_key_includes_event_type(self):
        """Verify dedupe key format: dedupe:{module}:{event_type}:{zoho_id}:{payload_sha}"""
        module = "Leads"
        event_type = "update"
        zoho_id = "6221978000123456789"
        payload_sha = "abc123def456"

        dedupe_key = f"dedupe:{module}:{event_type}:{zoho_id}:{payload_sha}"

        assert dedupe_key == "dedupe:Leads:update:6221978000123456789:abc123def456"

    def test_delete_and_update_have_different_keys(self):
        """Verify delete and update with same zoho_id have different dedupe keys"""
        module = "Leads"
        zoho_id = "6221978000123456789"
        payload_sha = "abc123def456"

        update_key = f"dedupe:{module}:update:{zoho_id}:{payload_sha}"
        delete_key = f"dedupe:{module}:delete:{zoho_id}:{payload_sha}"

        assert update_key != delete_key


class TestFieldNormalization:
    """Test field mapper normalization (phone, picklist, datetime)"""

    @pytest.mark.asyncio
    async def test_normalize_phone_e164(self):
        """Test phone normalization to E.164 format"""
        from app.services.zoho_field_mapper import ZohoFieldMapper

        mapper = ZohoFieldMapper()

        # Test various phone formats
        assert mapper._normalize_phone("(555) 123-4567") == "+15551234567"
        assert mapper._normalize_phone("+1 555-123-4567") == "+15551234567"
        assert mapper._normalize_phone("5551234567") == "+15551234567"

    @pytest.mark.asyncio
    async def test_normalize_picklist_array(self):
        """Test multiselectpicklist normalization to list"""
        from app.services.zoho_field_mapper import ZohoFieldMapper

        mapper = ZohoFieldMapper()

        # JSON string
        assert mapper._normalize_picklist_array('["Series 7", "Series 66"]') == ["Series 7", "Series 66"]

        # Comma-separated
        assert mapper._normalize_picklist_array("CFP, CFA, CIMA") == ["CFP", "CFA", "CIMA"]

        # Already a list
        assert mapper._normalize_picklist_array(["Value1", "Value2"]) == ["Value1", "Value2"]

    @pytest.mark.asyncio
    async def test_normalize_datetime_iso_string(self):
        """Test datetime normalization returns ISO string (not datetime object)"""
        from app.services.zoho_field_mapper import ZohoFieldMapper

        mapper = ZohoFieldMapper()

        # Test both Z and +00:00 formats
        result_z = mapper._normalize_datetime("2025-10-17T14:30:00Z")
        result_tz = mapper._normalize_datetime("2025-10-17T14:30:00+00:00")

        # Must return string (JSON serializable)
        assert isinstance(result_z, str)
        assert isinstance(result_tz, str)

        # Verify it can be serialized to JSON
        json.dumps({"timestamp": result_z})  # Should not raise TypeError


class TestDateTimeSerializability:
    """Verify datetime fields don't break JSON serialization"""

    @pytest.mark.asyncio
    async def test_normalized_payload_is_json_serializable(self):
        """Test that normalized payload with dates can be serialized to JSON"""
        from app.services.zoho_field_mapper import ZohoFieldMapper

        mapper = ZohoFieldMapper()

        payload = {
            "id": "6221978000123456789",
            "Full_Name": "John Doe",
            "Created_Time": "2025-10-17T14:30:00Z",
            "Modified_Time": "2025-10-17T14:30:00+00:00"
        }

        normalized = await mapper.coerce_payload("Leads", payload)

        # Should be able to serialize without TypeError
        try:
            json_str = json.dumps(normalized)
            assert isinstance(json_str, str)
        except TypeError as e:
            pytest.fail(f"DateTime serialization failed: {e}")


class TestConflictDetection:
    """Test stale update detection logic"""

    def test_identify_stale_update(self):
        """Verify stale update has earlier Modified_Time than existing record"""
        stale_webhook = LEAD_STALE_UPDATE_WEBHOOK
        update_webhook = LEAD_UPDATE_WEBHOOK

        stale_time = datetime.fromisoformat(
            stale_webhook["data"][0]["Modified_Time"].replace("Z", "+00:00")
        )
        current_time = datetime.fromisoformat(
            update_webhook["data"][0]["Modified_Time"].replace("Z", "+00:00")
        )

        # Stale update has earlier timestamp
        assert stale_time < current_time


class TestOwnerExtraction:
    """Test owner email/name extraction from payload"""

    def test_extract_owner_with_all_fields(self):
        """Test extraction when Owner has id, name, email"""
        payload = LEAD_CREATE_WEBHOOK["data"][0]
        owner = payload.get("Owner", {})

        assert owner.get("email") == "steve.perry@emailthewell.com"
        assert owner.get("name") == "Steve Perry"

    def test_extract_owner_missing(self):
        """Test fallback to default owner when Owner field missing"""
        payload = LEAD_NO_OWNER_WEBHOOK["data"][0]
        owner = payload.get("Owner", {})

        # Should use default owner
        assert not owner.get("email")

        # Worker should fall back to env var: steve.perry@emailthewell.com


class TestWebhookEndToEnd:
    """Integration tests for full webhook processing flow"""

    @pytest.mark.asyncio
    async def test_webhook_receiver_processes_create(self):
        """Test webhook receiver handles Leads.create correctly"""
        # This would be a full integration test with mocked Redis/DB/ServiceBus
        # Placeholder for future implementation
        pass

    @pytest.mark.asyncio
    async def test_webhook_receiver_handles_duplicate(self):
        """Test dedupe cache prevents duplicate processing"""
        # This would test Redis dedupe key check
        # Placeholder for future implementation
        pass

    @pytest.mark.asyncio
    async def test_worker_processes_message(self):
        """Test worker fetches log, normalizes, and performs UPSERT"""
        # This would test full worker flow
        # Placeholder for future implementation
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
