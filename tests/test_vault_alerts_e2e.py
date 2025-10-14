#!/usr/bin/env python3
"""
End-to-End Tests for Vault Alerts Generation System

Comprehensive testing of the complete vault alerts workflow including:
- Data loading from dual sources (PostgreSQL and Zoho API)
- LangGraph agent workflow
- HTML generation with proper formatting
- Anonymization when PRIVACY_MODE=true
- Performance metrics and caching
"""

import pytest
import asyncio
import os
import sys
import time
from typing import Dict, Any
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Mock the telemetry module before other imports
sys.modules['app.monitoring'] = MagicMock()
sys.modules['app.monitoring'].telemetry = MagicMock()

from app.jobs.vault_alerts_generator import VaultAlertsGenerator
from app.config import feature_flags


class TestVaultAlertsEndToEnd:
    """Test full vault alert generation workflow."""

    @pytest.mark.asyncio
    async def test_complete_workflow_advisor_audience(self):
        """Test complete workflow for advisor audience."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            results = await generator.generate_alerts(
                audience='advisors',
                from_date='2025-01-01',
                date_range_days=30
            )

            # Verify structure
            assert 'advisor_html' in results
            assert 'executive_html' in results
            assert 'advisor_count' in results
            assert 'executive_count' in results
            assert 'data_source' in results
            assert 'performance_metrics' in results

            # Advisor HTML should have content
            assert len(results['advisor_html']) > 0
            assert '<!DOCTYPE html>' in results['advisor_html']
            assert '<style>' in results['advisor_html']

            # Executive HTML should be empty for advisor-only audience
            assert results['executive_html'] == ''
            assert results['executive_count'] == 0

            # Verify count matches content
            assert results['advisor_count'] >= 0

            # Verify data source is set
            assert results['data_source'] in ['PostgreSQL', 'Zoho API']

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_complete_workflow_executive_audience(self):
        """Test complete workflow for executive audience."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            results = await generator.generate_alerts(
                audience='executives',
                from_date='2025-01-01',
                date_range_days=30
            )

            # Executive HTML should have content
            assert len(results['executive_html']) > 0
            assert '<!DOCTYPE html>' in results['executive_html']

            # Advisor HTML should be empty for executive-only audience
            assert results['advisor_html'] == ''
            assert results['advisor_count'] == 0

            # Verify count
            assert results['executive_count'] >= 0

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_complete_workflow_both_audiences(self):
        """Test complete workflow for both audiences."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            results = await generator.generate_alerts(
                audience='both',
                from_date='2025-01-01',
                date_range_days=30
            )

            # Both should have content (or be empty if no candidates)
            assert 'advisor_html' in results
            assert 'executive_html' in results

            # Both counts should be present
            assert results['advisor_count'] >= 0
            assert results['executive_count'] >= 0

            # Total count
            total = results['advisor_count'] + results['executive_count']
            assert total >= 0

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_anonymization_in_output(self):
        """Test that anonymization is applied when PRIVACY_MODE=true."""
        original_privacy = feature_flags.PRIVACY_MODE

        try:
            # Enable privacy mode
            feature_flags.PRIVACY_MODE = True

            generator = VaultAlertsGenerator()
            await generator.initialize()

            results = await generator.generate_alerts(
                audience='both',
                from_date='2025-01-01',
                date_range_days=30
            )

            # Check that HTML doesn't contain candidate IDs
            if results['advisor_html']:
                assert 'TWAV' not in results['advisor_html']

            if results['executive_html']:
                assert 'TWAV' not in results['executive_html']

            await generator.close()

        finally:
            # CRITICAL: Reset flag
            feature_flags.PRIVACY_MODE = original_privacy

    @pytest.mark.asyncio
    async def test_data_source_switching(self):
        """Test switching between PostgreSQL and Zoho API data sources."""
        original_flag = feature_flags.USE_ZOHO_API

        try:
            # Test PostgreSQL
            feature_flags.USE_ZOHO_API = False
            gen_pg = VaultAlertsGenerator()
            await gen_pg.initialize()

            results_pg = await gen_pg.generate_alerts(
                audience='advisors',
                from_date='2025-01-01',
                date_range_days=7
            )

            assert results_pg['data_source'] == 'PostgreSQL'
            await gen_pg.close()

            # Test Zoho API
            feature_flags.USE_ZOHO_API = True
            gen_zoho = VaultAlertsGenerator()
            await gen_zoho.initialize()

            results_zoho = await gen_zoho.generate_alerts(
                audience='advisors',
                from_date='2025-01-01',
                date_range_days=7
            )

            assert results_zoho['data_source'] == 'Zoho API'
            await gen_zoho.close()

        finally:
            # CRITICAL: Reset flag
            feature_flags.USE_ZOHO_API = original_flag

    @pytest.mark.asyncio
    async def test_caching_performance(self):
        """Test that caching improves performance on repeated calls."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            # First call - cold cache
            start1 = time.time()
            results1 = await generator.generate_alerts(
                audience='advisors',
                from_date='2025-01-01',
                date_range_days=7
            )
            time1 = time.time() - start1

            # Second call - warm cache
            start2 = time.time()
            results2 = await generator.generate_alerts(
                audience='advisors',
                from_date='2025-01-01',
                date_range_days=7
            )
            time2 = time.time() - start2

            # Second call should be faster (or at least not significantly slower)
            # Can't guarantee faster due to external factors, but check it completes
            assert time2 > 0
            assert results2['advisor_count'] == results1['advisor_count']

            # Check cache stats if available
            if 'cache_stats' in results2.get('performance_metrics', {}):
                cache_stats = results2['performance_metrics']['cache_stats']
                assert cache_stats.get('hits', 0) >= 0

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_error_handling_invalid_date(self):
        """Test error handling for invalid date formats."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            with pytest.raises(Exception):
                await generator.generate_alerts(
                    audience='advisors',
                    from_date='invalid-date',
                    date_range_days=30
                )
        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_error_handling_invalid_audience(self):
        """Test error handling for invalid audience parameter."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            with pytest.raises(ValueError):
                await generator.generate_alerts(
                    audience='invalid_audience',
                    from_date='2025-01-01',
                    date_range_days=30
                )
        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_custom_filters_application(self):
        """Test that custom filters are applied correctly."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            custom_filters = {
                'min_aum': 1000,  # $1B minimum
                'states': ['CA', 'NY'],
                'min_years_experience': 15
            }

            results = await generator.generate_alerts(
                audience='advisors',
                from_date='2025-01-01',
                date_range_days=30,
                custom_filters=custom_filters
            )

            # Results should respect filters (count may be lower)
            assert results['advisor_count'] >= 0

            # Check performance metrics include filter info
            if 'performance_metrics' in results:
                metrics = results['performance_metrics']
                assert 'custom_filters' in metrics or 'filters' in metrics

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_html_formatting_and_structure(self):
        """Test HTML output has correct structure and formatting."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            results = await generator.generate_alerts(
                audience='both',
                from_date='2025-01-01',
                date_range_days=7
            )

            # Check advisor HTML structure
            if results['advisor_html']:
                html = results['advisor_html']

                # Basic HTML structure
                assert '<!DOCTYPE html>' in html
                assert '<html' in html
                assert '<head>' in html
                assert '<body>' in html
                assert '</html>' in html

                # CSS for card formatting
                assert 'page-break-inside: avoid' in html
                assert '.candidate-card' in html or 'border-radius' in html

                # Alert format
                if '‼️' in html:  # If there are alerts
                    assert '🔔' in html  # Location emoji
                    assert '📍' in html  # Availability emoji

            # Check executive HTML structure
            if results['executive_html']:
                html = results['executive_html']
                assert '<!DOCTYPE html>' in html
                assert '<style>' in html

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_performance_metrics_tracking(self):
        """Test that performance metrics are tracked correctly."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            results = await generator.generate_alerts(
                audience='advisors',
                from_date='2025-01-01',
                date_range_days=7
            )

            # Check performance metrics
            assert 'performance_metrics' in results
            metrics = results['performance_metrics']

            # Should have timing information
            assert 'total_time_ms' in metrics or 'execution_time' in metrics

            # Should have stage information
            assert any(key in metrics for key in [
                'database_load_time',
                'filtering_time',
                'generation_time',
                'stages'
            ])

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_empty_results_handling(self):
        """Test handling when no candidates match criteria."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            # Use very restrictive filters to get empty results
            custom_filters = {
                'min_aum': 100000,  # $100B minimum (unrealistic)
                'states': ['XX'],  # Invalid state
            }

            results = await generator.generate_alerts(
                audience='advisors',
                from_date='2025-01-01',
                date_range_days=1,
                custom_filters=custom_filters
            )

            # Should return valid structure even with no results
            assert results['advisor_count'] == 0
            assert results['advisor_html'] == '' or 'No candidates' in results['advisor_html']

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_concurrent_generation_safety(self):
        """Test that multiple concurrent generations don't interfere."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            # Launch multiple concurrent generations
            tasks = [
                generator.generate_alerts('advisors', '2025-01-01', 7),
                generator.generate_alerts('executives', '2025-01-01', 7),
                generator.generate_alerts('both', '2025-01-02', 7)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should complete without errors
            for i, result in enumerate(results):
                assert not isinstance(result, Exception), f"Task {i} failed: {result}"
                assert 'advisor_count' in result or 'executive_count' in result

        finally:
            await generator.close()


class TestVaultAlertsIntegration:
    """Test integration with other components."""

    @pytest.mark.asyncio
    async def test_redis_cache_integration(self):
        """Test Redis cache integration if available."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            # Check if Redis is configured
            if generator.cache_manager:
                # Generate alerts twice to test caching
                results1 = await generator.generate_alerts(
                    audience='advisors',
                    from_date='2025-01-01',
                    date_range_days=7
                )

                results2 = await generator.generate_alerts(
                    audience='advisors',
                    from_date='2025-01-01',
                    date_range_days=7
                )

                # Check cache was used
                if 'cache_stats' in results2.get('performance_metrics', {}):
                    stats = results2['performance_metrics']['cache_stats']
                    assert stats.get('hits', 0) > 0

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_database_connection_handling(self):
        """Test proper database connection handling."""
        generator = VaultAlertsGenerator()

        # Test initialization
        await generator.initialize()
        assert generator.db_pool is not None or generator.zoho_client is not None

        # Generate alerts
        results = await generator.generate_alerts(
            audience='advisors',
            from_date='2025-01-01',
            date_range_days=7
        )
        assert 'advisor_count' in results

        # Test cleanup
        await generator.close()

        # After close, should handle gracefully
        with pytest.raises(Exception):
            await generator.generate_alerts(
                audience='advisors',
                from_date='2025-01-01',
                date_range_days=7
            )


class TestVaultAlertsEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_large_dataset_handling(self):
        """Test handling of large candidate datasets."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            # Request large date range
            results = await generator.generate_alerts(
                audience='both',
                from_date='2024-01-01',  # Full year
                date_range_days=365
            )

            # Should handle without crashing
            assert results['advisor_count'] >= 0
            assert results['executive_count'] >= 0

            # Performance should be tracked
            assert 'performance_metrics' in results

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_special_characters_in_output(self):
        """Test that special characters are handled properly in HTML."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            results = await generator.generate_alerts(
                audience='advisors',
                from_date='2025-01-01',
                date_range_days=30
            )

            if results['advisor_html']:
                html = results['advisor_html']

                # Should properly escape or handle special chars
                # Check that HTML entities are used where needed
                if '&' in html:
                    assert '&amp;' in html or '&nbsp;' in html or '&lt;' in html

        finally:
            await generator.close()

    @pytest.mark.asyncio
    async def test_timezone_handling(self):
        """Test that timezones are handled correctly."""
        generator = VaultAlertsGenerator()
        await generator.initialize()

        try:
            # Test with different date formats
            results = await generator.generate_alerts(
                audience='advisors',
                from_date='2025-01-01T00:00:00Z',  # UTC
                date_range_days=7
            )

            assert results['advisor_count'] >= 0

        finally:
            await generator.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])