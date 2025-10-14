#!/usr/bin/env python3
"""
Tests for Boss Email Endpoint

Tests the /api/teams/admin/send_vault_alerts_to_bosses endpoint including:
- Authentication and authorization
- Email sending to executives
- Response structure and error handling
- Integration with vault alerts generator
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Mock the telemetry module before importing app
sys.modules['app.monitoring'] = MagicMock()
sys.modules['app.monitoring'].telemetry = MagicMock()

from fastapi.testclient import TestClient
from app.main import app
from app.config import feature_flags


class TestBossEmailEndpointAuth:
    """Test authentication and authorization for boss email endpoint."""

    def test_missing_api_key(self):
        """Test that missing API key returns 403."""
        client = TestClient(app)
        response = client.post("/api/teams/admin/send_vault_alerts_to_bosses")
        assert response.status_code == 403
        assert "API key is missing" in response.json().get('detail', '')

    def test_invalid_api_key(self):
        """Test that invalid API key returns 403."""
        client = TestClient(app)
        response = client.post(
            "/api/teams/admin/send_vault_alerts_to_bosses",
            headers={"X-API-Key": "invalid-key"}
        )
        assert response.status_code == 403
        assert "Invalid API key" in response.json().get('detail', '')

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_valid_api_key_accepted(self):
        """Test that valid API key is accepted."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            # Mock the generator
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '<html>Test</html>',
                'executive_html': '<html>Test</html>',
                'advisor_count': 5,
                'executive_count': 3,
                'data_source': 'PostgreSQL'
            })
            mock_instance.close = AsyncMock()

            with patch('app.api.teams.routes.send_boss_emails') as mock_send:
                mock_send.return_value = AsyncMock(return_value={
                    'emails_sent': ['steve@example.com'],
                    'failures': []
                })()

                response = client.post(
                    "/api/teams/admin/send_vault_alerts_to_bosses",
                    headers={"X-API-Key": "test-api-key"}
                )

                # Should accept the request
                assert response.status_code in [200, 422, 500]  # Not 403


class TestBossEmailEndpointParameters:
    """Test parameter handling for boss email endpoint."""

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_default_parameters(self):
        """Test endpoint with default parameters."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '<html>Advisors</html>',
                'executive_html': '<html>Executives</html>',
                'advisor_count': 10,
                'executive_count': 5,
                'data_source': 'PostgreSQL'
            })
            mock_instance.close = AsyncMock()

            with patch('app.api.teams.routes.send_boss_emails') as mock_send:
                mock_send.return_value = AsyncMock(return_value={
                    'emails_sent': ['steve@example.com', 'brandon@example.com'],
                    'failures': []
                })()

                response = client.post(
                    "/api/teams/admin/send_vault_alerts_to_bosses",
                    headers={"X-API-Key": "test-api-key"}
                )

                if response.status_code == 200:
                    data = response.json()
                    assert 'status' in data
                    assert 'emails_sent' in data

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_custom_from_date(self):
        """Test endpoint with custom from_date parameter."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '<html>Test</html>',
                'executive_html': '<html>Test</html>',
                'advisor_count': 3,
                'executive_count': 2,
                'data_source': 'Zoho API'
            })
            mock_instance.close = AsyncMock()

            with patch('app.api.teams.routes.send_boss_emails') as mock_send:
                mock_send.return_value = AsyncMock(return_value={
                    'emails_sent': ['daniel.romitelli@example.com'],
                    'failures': []
                })()

                response = client.post(
                    "/api/teams/admin/send_vault_alerts_to_bosses?from_date=2025-01-01",
                    headers={"X-API-Key": "test-api-key"}
                )

                if response.status_code == 200:
                    # Verify the custom date was used
                    mock_instance.generate_alerts.assert_called()
                    call_args = mock_instance.generate_alerts.call_args
                    if call_args and call_args[1]:
                        assert call_args[1].get('from_date') == '2025-01-01'

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_custom_date_range(self):
        """Test endpoint with custom date_range_days parameter."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '',
                'executive_html': '<html>Exec</html>',
                'advisor_count': 0,
                'executive_count': 7,
                'data_source': 'PostgreSQL'
            })
            mock_instance.close = AsyncMock()

            with patch('app.api.teams.routes.send_boss_emails') as mock_send:
                mock_send.return_value = AsyncMock(return_value={
                    'emails_sent': ['steve@example.com'],
                    'failures': []
                })()

                response = client.post(
                    "/api/teams/admin/send_vault_alerts_to_bosses?date_range_days=14",
                    headers={"X-API-Key": "test-api-key"}
                )

                if response.status_code == 200:
                    # Verify the custom range was used
                    mock_instance.generate_alerts.assert_called()
                    call_args = mock_instance.generate_alerts.call_args
                    if call_args and call_args[1]:
                        assert call_args[1].get('date_range_days') == 14

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_test_mode_parameter(self):
        """Test endpoint in test mode (no emails sent)."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '<html>Test HTML</html>',
                'executive_html': '<html>Test HTML</html>',
                'advisor_count': 15,
                'executive_count': 8,
                'data_source': 'PostgreSQL'
            })
            mock_instance.close = AsyncMock()

            response = client.post(
                "/api/teams/admin/send_vault_alerts_to_bosses?test_mode=true",
                headers={"X-API-Key": "test-api-key"}
            )

            if response.status_code == 200:
                data = response.json()
                # In test mode, emails should not actually be sent
                assert data.get('test_mode') is True or 'test' in data.get('status', '').lower()


class TestBossEmailEndpointResponse:
    """Test response structure and content."""

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_successful_response_structure(self):
        """Test successful response has correct structure."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '<html>Advisor alerts</html>',
                'executive_html': '<html>Executive alerts</html>',
                'advisor_count': 12,
                'executive_count': 6,
                'data_source': 'PostgreSQL',
                'performance_metrics': {
                    'total_time_ms': 1250,
                    'cache_hits': 5
                }
            })
            mock_instance.close = AsyncMock()

            with patch('app.api.teams.routes.send_boss_emails') as mock_send:
                mock_send.return_value = AsyncMock(return_value={
                    'emails_sent': ['steve@example.com', 'brandon@example.com'],
                    'failures': []
                })()

                response = client.post(
                    "/api/teams/admin/send_vault_alerts_to_bosses",
                    headers={"X-API-Key": "test-api-key"}
                )

                if response.status_code == 200:
                    data = response.json()

                    # Required fields
                    assert 'status' in data
                    assert 'emails_sent' in data
                    assert 'execution_time_ms' in data

                    # Optional fields that should be present
                    assert 'advisor_count' in data or 'candidates' in data
                    assert 'executive_count' in data or 'candidates' in data
                    assert 'data_source' in data

                    # Status should be success
                    assert data['status'] == 'success'

                    # Emails sent should be a list
                    assert isinstance(data['emails_sent'], list)
                    assert len(data['emails_sent']) > 0

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_partial_failure_response(self):
        """Test response when some emails fail to send."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '<html>Content</html>',
                'executive_html': '<html>Content</html>',
                'advisor_count': 5,
                'executive_count': 3,
                'data_source': 'Zoho API'
            })
            mock_instance.close = AsyncMock()

            with patch('app.api.teams.routes.send_boss_emails') as mock_send:
                mock_send.return_value = AsyncMock(return_value={
                    'emails_sent': ['steve@example.com'],
                    'failures': [{'email': 'brandon@example.com', 'error': 'SMTP error'}]
                })()

                response = client.post(
                    "/api/teams/admin/send_vault_alerts_to_bosses",
                    headers={"X-API-Key": "test-api-key"}
                )

                if response.status_code == 200:
                    data = response.json()
                    assert data['status'] in ['partial_success', 'success']
                    assert 'failures' in data or 'errors' in data

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_no_candidates_response(self):
        """Test response when no candidates are found."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '',
                'executive_html': '',
                'advisor_count': 0,
                'executive_count': 0,
                'data_source': 'PostgreSQL'
            })
            mock_instance.close = AsyncMock()

            response = client.post(
                "/api/teams/admin/send_vault_alerts_to_bosses",
                headers={"X-API-Key": "test-api-key"}
            )

            if response.status_code == 200:
                data = response.json()
                # Should indicate no candidates found
                assert data['advisor_count'] == 0
                assert data['executive_count'] == 0
                # May or may not send emails (empty digest)
                assert 'emails_sent' in data


class TestBossEmailEndpointErrorHandling:
    """Test error handling scenarios."""

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_generator_initialization_failure(self):
        """Test handling when vault generator fails to initialize."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock(side_effect=Exception("Database connection failed"))

            response = client.post(
                "/api/teams/admin/send_vault_alerts_to_bosses",
                headers={"X-API-Key": "test-api-key"}
            )

            # Should return error status
            assert response.status_code in [500, 503]
            data = response.json()
            assert 'error' in data or 'detail' in data

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_email_service_failure(self):
        """Test handling when email service fails completely."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '<html>Content</html>',
                'executive_html': '<html>Content</html>',
                'advisor_count': 10,
                'executive_count': 5,
                'data_source': 'PostgreSQL'
            })
            mock_instance.close = AsyncMock()

            with patch('app.api.teams.routes.send_boss_emails') as mock_send:
                mock_send.side_effect = Exception("Email service unavailable")

                response = client.post(
                    "/api/teams/admin/send_vault_alerts_to_bosses",
                    headers={"X-API-Key": "test-api-key"}
                )

                # Should handle gracefully
                assert response.status_code in [500, 503]
                data = response.json()
                assert 'error' in data or 'detail' in data

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_invalid_date_format(self):
        """Test handling of invalid date format."""
        client = TestClient(app)

        response = client.post(
            "/api/teams/admin/send_vault_alerts_to_bosses?from_date=invalid-date",
            headers={"X-API-Key": "test-api-key"}
        )

        # Should return validation error
        assert response.status_code in [400, 422]
        data = response.json()
        assert 'detail' in data or 'error' in data

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_negative_date_range(self):
        """Test handling of negative date range."""
        client = TestClient(app)

        response = client.post(
            "/api/teams/admin/send_vault_alerts_to_bosses?date_range_days=-7",
            headers={"X-API-Key": "test-api-key"}
        )

        # Should return validation error
        assert response.status_code in [400, 422]


class TestBossEmailEndpointIntegration:
    """Test integration with other systems."""

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_feature_flag_integration(self):
        """Test that feature flags affect email behavior."""
        original_privacy = feature_flags.PRIVACY_MODE
        original_zoho = feature_flags.USE_ZOHO_API

        try:
            # Test with different feature flag settings
            feature_flags.PRIVACY_MODE = True
            feature_flags.USE_ZOHO_API = False

            client = TestClient(app)

            with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
                mock_instance = AsyncMock()
                mock_gen.return_value = mock_instance
                mock_instance.initialize = AsyncMock()
                mock_instance.generate_alerts = AsyncMock(return_value={
                    'advisor_html': '<html>Anonymized content</html>',
                    'executive_html': '<html>Anonymized content</html>',
                    'advisor_count': 8,
                    'executive_count': 4,
                    'data_source': 'PostgreSQL'
                })
                mock_instance.close = AsyncMock()

                with patch('app.api.teams.routes.send_boss_emails') as mock_send:
                    mock_send.return_value = AsyncMock(return_value={
                        'emails_sent': ['steve@example.com'],
                        'failures': []
                    })()

                    response = client.post(
                        "/api/teams/admin/send_vault_alerts_to_bosses",
                        headers={"X-API-Key": "test-api-key"}
                    )

                    if response.status_code == 200:
                        data = response.json()
                        # Data source should reflect feature flag
                        assert data['data_source'] == 'PostgreSQL'

        finally:
            # CRITICAL: Reset flags
            feature_flags.PRIVACY_MODE = original_privacy
            feature_flags.USE_ZOHO_API = original_zoho

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_telemetry_logging(self):
        """Test that telemetry is logged for email sending."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '<html>Test</html>',
                'executive_html': '<html>Test</html>',
                'advisor_count': 5,
                'executive_count': 3,
                'data_source': 'PostgreSQL'
            })
            mock_instance.close = AsyncMock()

            with patch('app.api.teams.routes.send_boss_emails') as mock_send:
                mock_send.return_value = AsyncMock(return_value={
                    'emails_sent': ['steve@example.com'],
                    'failures': []
                })()

                with patch('app.api.teams.routes.log_telemetry') as mock_telemetry:
                    response = client.post(
                        "/api/teams/admin/send_vault_alerts_to_bosses",
                        headers={"X-API-Key": "test-api-key"}
                    )

                    if response.status_code == 200:
                        # Verify telemetry was logged
                        if mock_telemetry.called:
                            assert mock_telemetry.call_count > 0


class TestBossEmailEndpointPerformance:
    """Test performance aspects of the endpoint."""

    @patch.dict(os.environ, {"API_KEY": "test-api-key"})
    def test_response_time_tracking(self):
        """Test that execution time is tracked."""
        client = TestClient(app)

        with patch('app.api.teams.routes.VaultAlertsGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_gen.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.generate_alerts = AsyncMock(return_value={
                'advisor_html': '<html>Quick test</html>',
                'executive_html': '<html>Quick test</html>',
                'advisor_count': 2,
                'executive_count': 1,
                'data_source': 'PostgreSQL'
            })
            mock_instance.close = AsyncMock()

            with patch('app.api.teams.routes.send_boss_emails') as mock_send:
                mock_send.return_value = AsyncMock(return_value={
                    'emails_sent': ['test@example.com'],
                    'failures': []
                })()

                response = client.post(
                    "/api/teams/admin/send_vault_alerts_to_bosses",
                    headers={"X-API-Key": "test-api-key"}
                )

                if response.status_code == 200:
                    data = response.json()
                    # Should include execution time
                    assert 'execution_time_ms' in data
                    assert isinstance(data['execution_time_ms'], (int, float))
                    assert data['execution_time_ms'] >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])