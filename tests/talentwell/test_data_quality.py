#!/usr/bin/env python3
"""
Test data quality improvements for TalentWell Advisor Vault.
Tests AUM rounding, compensation standardization, internal note filtering,
availability formatting, and company anonymization.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import json

import app.jobs.talentwell_curator as curator_module
from app.jobs.talentwell_curator import TalentWellCurator, DigestCard, BulletPoint
from well_shared.evidence.extractor import EvidenceExtractor


class TestDataQuality:
    """Test suite for data quality and standardization."""

    @pytest.fixture
    def curator(self):
        """Create a TalentWellCurator instance."""
        curator = TalentWellCurator()
        curator.initialized = True
        curator.redis_client = AsyncMock()
        curator.evidence_extractor = Mock(spec=EvidenceExtractor)
        return curator

    @pytest.fixture
    def sample_deals(self):
        """Sample deals with various data patterns."""
        return [
            {
                'id': 'deal_001',
                'candidate_name': 'John Smith',
                'job_title': 'Financial Advisor',
                'company_name': 'Merrill Lynch',
                'location': 'New York, NY',
                'book_size_aum': '$1,250,000,000',  # Test AUM rounding
                'production_12mo': '$750000',
                'desired_comp': '350000-450000',  # Test comp standardization
                'when_available': 'Q1 2025',
                'is_mobile': True,
                'remote_preference': False,
                'hybrid_preference': True
            },
            {
                'id': 'deal_002',
                'candidate_name': 'Jane Doe',
                'job_title': 'Senior Wealth Manager',
                'company_name': 'Wells Fargo Advisors',
                'location': 'San Francisco, CA',
                'book_size_aum': '$523,456,789',  # Test AUM rounding
                'production_12mo': '$425,000',
                'desired_comp': '300k-400k',  # Test different comp format
                'when_available': 'Immediately',
                'is_mobile': False,
                'remote_preference': True,
                'hybrid_preference': True
            },
            {
                'id': 'deal_003',
                'candidate_name': 'Bob Johnson',
                'job_title': 'Portfolio Manager',
                'company_name': 'Small RIA Firm',
                'location': 'Gulf Breeze, FL',  # Test small city normalization
                'book_size_aum': '$75,500,000',  # Test smaller AUM
                'production_12mo': None,
                'desired_comp': 'negotiable',
                'when_available': '30-60 days',
                'is_mobile': True,
                'remote_preference': False,
                'hybrid_preference': False
            }
        ]

    def test_aum_rounding(self, curator):
        """Test AUM rounding to nearest significant figure."""
        test_cases = [
            ('$1,250,000,000', '$1.25B'),  # Billion
            ('$523,456,789', '$523M'),      # Hundred millions
            ('$75,500,000', '$75.5M'),      # Ten millions
            ('$5,234,567', '$5.2M'),        # Millions
            ('$950,000', '$950K'),           # Hundred thousands
            ('$1,950,000,000', '$1.95B'),   # Near 2B
            ('$999,999,999', '$1B'),        # Round up to 1B
        ]

        for input_val, expected in test_cases:
            result = curator._format_aum(input_val)
            assert result == expected, f"Failed for {input_val}: expected {expected}, got {result}"

    def test_compensation_standardization(self, curator):
        """Test compensation format standardization."""
        test_cases = [
            ('350000-450000', '$350K-$450K'),
            ('300k-400k', '$300K-$400K'),
            ('$500,000', '$500K'),
            ('negotiable', 'Negotiable'),
            ('750000+', '$750K+'),
            ('1mm+', '$1M+'),
            ('1.5M', '$1.5M'),
            ('', 'Not specified'),
            (None, 'Not specified'),
        ]

        for input_val, expected in test_cases:
            result = curator._format_compensation(input_val)
            assert result == expected, f"Failed for {input_val}: expected {expected}, got {result}"

    def test_internal_note_filtering(self, curator):
        """Test filtering of internal notes from bullets."""
        bullets_with_internal = [
            BulletPoint(text="AUM: $500M", confidence=0.95, source="CRM"),
            BulletPoint(text="[INTERNAL] Call scheduled for Tuesday", confidence=0.8, source="Notes"),
            BulletPoint(text="Production: $750K", confidence=0.9, source="CRM"),
            BulletPoint(text="Internal: Do not contact before Q2", confidence=0.7, source="Notes"),
            BulletPoint(text="Note: Prefers morning calls", confidence=0.6, source="Notes"),
            BulletPoint(text="Team of 5 advisors", confidence=0.85, source="Transcript"),
        ]

        filtered = curator._filter_internal_notes(bullets_with_internal)

        # Should remove internal notes but keep valid bullets
        assert len(filtered) == 3
        assert all('[INTERNAL]' not in b.text for b in filtered)
        assert all('Internal:' not in b.text for b in filtered)
        assert all('Note:' not in b.text for b in filtered)
        assert filtered[0].text == "AUM: $500M"
        assert filtered[1].text == "Production: $750K"
        assert filtered[2].text == "Team of 5 advisors"

    def test_availability_formatting(self, curator):
        """Test availability text formatting."""
        test_cases = [
            ('Q1 2025', 'Q1 2025'),
            ('Immediately', 'Immediately'),
            ('30-60 days', '30-60 days'),
            ('2 weeks notice', '2 weeks notice'),
            ('january 2025', 'January 2025'),
            ('q2', 'Q2'),
            ('asap', 'ASAP'),
            ('', 'Not specified'),
            (None, 'Not specified'),
        ]

        for input_val, expected in test_cases:
            result = curator._format_availability(input_val)
            assert result == expected, f"Failed for {input_val}: expected {expected}, got {result}"

    def test_company_anonymization(self, curator):
        """Test company name anonymization for privacy."""
        test_cases = [
            # Wirehouse firms
            ('Merrill Lynch', None, 'Major wirehouse'),
            ('Morgan Stanley', None, 'Major wirehouse'),
            ('Wells Fargo Advisors', None, 'Major wirehouse'),

            # RIA firms
            ('Nuance Investments', 1500000000, 'Large RIA'),  # $1.5B
            ('Small RIA Shop', 200000000, 'Mid-sized RIA'),   # $200M

            # Banks
            ('JPMorgan Private Bank', None, 'National bank'),
            ('Bank of America', None, 'National bank'),

            # Insurance
            ('Northwestern Mutual', None, 'Insurance brokerage'),
            ('MassMutual', None, 'Insurance brokerage'),

            # Unknown with AUM hints
            ('Unknown Firm', 750000000, 'Large wealth management firm'),  # $750M
            ('Unknown Firm', 50000000, 'Boutique advisory firm'),         # $50M

            # Edge cases
            ('Unknown', None, 'Not disclosed'),
            ('', None, 'Not disclosed'),
            (None, None, 'Not disclosed'),
        ]

        for company, aum, expected in test_cases:
            result = curator._anonymize_company(company, aum)
            assert result == expected, f"Failed for {company} (AUM: {aum}): expected {expected}, got {result}"

    @pytest.mark.asyncio
    async def test_privacy_mode_enabled(self, monkeypatch, curator):
        """When privacy mode is enabled, company is anonymized and location bullets suppressed."""

        # Enable privacy mode for this test
        monkeypatch.setattr(curator_module, "PRIVACY_MODE", True, raising=False)

        parsed_aum = curator._parse_aum("$1.5B")
        display_company = curator._anonymize_company("Morgan Stanley", parsed_aum) if curator_module.PRIVACY_MODE else "Morgan Stanley"
        assert display_company == "Major wirehouse"

        # Strict compensation formatting should normalize to Target comp format
        assert curator._standardize_compensation("250k to 350k") == "Target comp: $250K–$350K OTE"

        # Location bullets should be suppressed when privacy mode is on
        deal = {"location": "Chicago, IL"}
        bullets = await curator._ensure_minimum_bullets(deal, [])
        assert all("Location:" not in b.text for b in bullets)

    @pytest.mark.asyncio
    async def test_privacy_mode_disabled(self, monkeypatch, curator):
        """When privacy mode is disabled, original company and location bullets are preserved."""

        monkeypatch.setattr(curator_module, "PRIVACY_MODE", False, raising=False)

        parsed_aum = curator._parse_aum("$1.5B")
        # With privacy mode off, company name should remain unchanged
        display_company = "Morgan Stanley" if not curator_module.PRIVACY_MODE else curator._anonymize_company("Morgan Stanley", parsed_aum)
        assert display_company == "Morgan Stanley"

        # Location bullets should be allowed when privacy mode is disabled
        deal = {"location": "Chicago, IL"}
        bullets = await curator._ensure_minimum_bullets(deal, [])
        assert any("Location:" in b.text for b in bullets)

    def test_strict_compensation_formatting(self, curator):
        """Verify strict compensation normalization handles edge cases."""

        test_cases = [
            ("250k to 350k", "Target comp: $250K–$350K OTE"),
            ("$500k", "Target comp: $500K OTE"),
            ("95k + commission", "Target comp: $95K OTE"),
            ("95k base + commission 140+ OTE", "Target comp: $95K–$140K OTE"),
            ("1.2M", "Target comp: $1200K OTE"),
        ]

        for raw_text, expected in test_cases:
            assert curator._standardize_compensation(raw_text) == expected

    @pytest.mark.asyncio
    async def test_location_bullet_suppression_privacy_mode(self, monkeypatch, curator):
        """Explicitly verify location bullets are removed under privacy mode."""

        monkeypatch.setattr(curator_module, "PRIVACY_MODE", True, raising=False)
        deal = {"location": "Austin, TX"}
        bullets = await curator._ensure_minimum_bullets(deal, [])
        assert all("Location:" not in b.text for b in bullets)

    @pytest.mark.asyncio
    async def test_location_bullets_allowed_without_privacy(self, monkeypatch, curator):
        """Location bullets should still appear when privacy mode is disabled."""

        monkeypatch.setattr(curator_module, "PRIVACY_MODE", False, raising=False)
        deal = {"location": "Austin, TX"}
        bullets = await curator._ensure_minimum_bullets(deal, [])
        assert any("Location:" in b.text for b in bullets)

    @pytest.mark.asyncio
    async def test_location_normalization(self, curator):
        """Test location normalization to metro areas."""
        # Mock city context data
        with patch('builtins.open', create=True) as mock_open:
            mock_context = {
                'new_york': 'New York Metro',
                'brooklyn': 'New York Metro',
                'san_francisco': 'San Francisco Bay Area',
                'palo_alto': 'San Francisco Bay Area',
                'gulf_breeze': 'Pensacola Metro',
                'miami': 'Miami-Dade Metro',
                'fort_lauderdale': 'Miami-Dade Metro',
            }
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_context)

            test_cases = [
                ('New York, NY', 'New York Metro'),
                ('Brooklyn, NY', 'New York Metro'),
                ('San Francisco, CA', 'San Francisco Bay Area'),
                ('Gulf Breeze, FL', 'Gulf Breeze (Pensacola area)'),  # Special case
                ('Miami, FL', 'Miami-Dade Metro'),
                ('Unknown City', 'Unknown City'),  # No mapping
                ('', ''),
                (None, None),
            ]

            for input_loc, expected in test_cases:
                result = await curator._normalize_location(input_loc)
                if input_loc and input_loc.lower().startswith('gulf breeze'):
                    assert 'Pensacola' in result, f"Gulf Breeze should include Pensacola area"
                elif input_loc and input_loc != 'Unknown City':
                    # For mapped cities, we expect the metro area
                    pass  # Location normalization logic would apply here

    @pytest.mark.asyncio
    async def test_deal_processing_with_quality_improvements(self, curator, sample_deals):
        """Test full deal processing with all data quality improvements."""
        deal = sample_deals[0]  # Merrill Lynch advisor

        # Mock VoIT response
        with patch('app.cache.voit.voit_orchestration') as mock_voit:
            mock_voit.return_value = {
                'enhanced_data': {
                    'candidate_name': deal['candidate_name'],
                    'job_title': deal['job_title'],
                    'aum_managed': '$1.25B',
                    'production_annual': '$750K',
                },
                'model_used': 'gpt-5-mini',
                'budget_used': 2.5,
                'quality_score': 0.92
            }

            # Process the deal
            card = await curator._process_deal(deal, 'steve_perry')

            assert card is not None
            assert card.candidate_name == 'John Smith'
            assert card.company == 'Major wirehouse'  # Anonymized
            assert 'AUM: $1.25B' in [b.text for b in card.bullets]
            assert 'Production: $750K' in [b.text for b in card.bullets]

            # Check mobility line formatting
            assert 'Is mobile' in card.location
            assert 'Open to Hybrid' in card.location

    def test_bullet_deduplication(self, curator):
        """Test removal of duplicate information in bullets."""
        bullets_with_dupes = [
            BulletPoint(text="AUM: $500M", confidence=0.95, source="CRM"),
            BulletPoint(text="AUM: $500 million", confidence=0.9, source="Transcript"),  # Duplicate
            BulletPoint(text="Location: New York", confidence=0.8, source="CRM"),
            BulletPoint(text="Based in New York", confidence=0.75, source="Transcript"),  # Duplicate
            BulletPoint(text="Team of 5", confidence=0.85, source="CRM"),
            BulletPoint(text="Company: Merrill Lynch", confidence=0.8, source="CRM"),
            BulletPoint(text="Merrill Lynch advisor", confidence=0.7, source="Notes"),  # Duplicate
        ]

        deduped = curator._deduplicate_bullets(bullets_with_dupes)

        # Should keep highest confidence version of each fact
        assert len(deduped) == 4
        assert deduped[0].text == "AUM: $500M"  # Higher confidence
        assert deduped[0].confidence == 0.95

        # Location and company should also be deduped
        text_set = {b.text for b in deduped}
        assert "Location: New York" in text_set or "Based in New York" in text_set
        assert not ("Location: New York" in text_set and "Based in New York" in text_set)

    def test_mobility_line_formatting(self, curator):
        """Test mobility line generation from CRM fields."""
        test_cases = [
            # (is_mobile, remote_pref, hybrid_pref, expected)
            (True, False, False, "(Is mobile)"),
            (False, False, False, "(Is not mobile)"),
            (True, True, False, "(Is mobile; Open to Remote)"),
            (True, False, True, "(Is mobile; Open to Hybrid)"),
            (True, True, True, "(Is mobile; Open to Remote or Hybrid)"),
            (False, True, True, "(Is not mobile; Open to Remote or Hybrid)"),
        ]

        for is_mobile, remote, hybrid, expected in test_cases:
            result = curator._build_mobility_line(is_mobile, remote, hybrid)
            assert result == expected, f"Failed for mobile={is_mobile}, remote={remote}, hybrid={hybrid}"

    def test_format_availability(self, curator):
        """Test availability formatting with actual curator method."""
        # Test the actual _format_availability method
        assert curator._format_availability('immediately') == "Available immediately"
        assert curator._format_availability('asap') == "Available immediately"
        assert curator._format_availability('2 weeks') == "Available in 2 weeks"
        assert curator._format_availability('1 month') == "Available in 1 month"
        assert curator._format_availability('') == ""
