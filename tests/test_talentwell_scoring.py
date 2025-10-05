"""
Test cases for the TalentWell curator score-based bullet ranking system.
"""

import pytest
import asyncio
from typing import Dict, List, Any
from unittest.mock import Mock, AsyncMock, patch

# Import from the refactored file for testing
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.extract.evidence import BulletPoint
from app.jobs.talentwell_curator_refactored import TalentWellCuratorRefactored


class TestBulletScoring:
    """Test the bullet scoring system."""

    def setup_method(self):
        """Set up test curator instance."""
        self.curator = TalentWellCuratorRefactored()

    def test_aum_scores_highest(self):
        """Test that AUM bullets score highest (10)."""
        deal = {'candidate_name': 'John Doe', 'company_name': 'Test Firm'}

        test_bullets = [
            BulletPoint(text="AUM: $5B+", confidence=0.95, source="CRM"),
            BulletPoint(text="AUM: $1B–$5B", confidence=0.95, source="CRM"),
            BulletPoint(text="AUM: $500M–$1B", confidence=0.95, source="CRM"),
            BulletPoint(text="Book size: $2B", confidence=0.95, source="CRM"),
            BulletPoint(text="Manages $750 million", confidence=0.95, source="CRM"),
        ]

        scores = [self.curator._score_bullet(b, deal) for b in test_bullets]

        # All AUM bullets should score between 9.5 and 10
        assert all(score >= 9.5 for score in scores)
        # Billion-level AUM should score 10
        assert scores[0] == 10.0  # $5B+
        assert scores[1] == 10.0  # $1B–$5B
        assert scores[3] == 10.0  # $2B
        # Million-level AUM should score 9.8
        assert scores[2] == 9.8  # $500M–$1B
        assert scores[4] == 9.8  # $750 million

    def test_growth_metrics_score_high(self):
        """Test that growth metrics score 9."""
        deal = {'candidate_name': 'John Doe'}

        test_bullets = [
            BulletPoint(text="Grew book by 150%", confidence=0.95, source="CRM"),
            BulletPoint(text="Increased AUM by 200% in 2 years", confidence=0.95, source="CRM"),
            BulletPoint(text="Doubled client base", confidence=0.95, source="CRM"),
            BulletPoint(text="Expanded assets significantly", confidence=0.95, source="CRM"),
        ]

        scores = [self.curator._score_bullet(b, deal) for b in test_bullets]

        # Growth with percentage should score 9.0
        assert scores[0] == 9.0  # 150%
        assert scores[1] == 9.0  # 200%
        # Growth without percentage should score 8.8
        assert scores[2] == 8.8  # Doubled
        assert scores[3] == 8.8  # Expanded

    def test_production_scores_8_5(self):
        """Test that production metrics score 8.5."""
        deal = {'candidate_name': 'John Doe'}

        test_bullets = [
            BulletPoint(text="Production: $500K", confidence=0.95, source="CRM"),
            BulletPoint(text="Annual production $1.2M", confidence=0.95, source="CRM"),
            BulletPoint(text="Revenue: $750K", confidence=0.95, source="CRM"),
        ]

        scores = [self.curator._score_bullet(b, deal) for b in test_bullets]

        # All production bullets should score 8.5
        assert all(score == 8.5 for score in scores)

    def test_rankings_achievements_score_8(self):
        """Test that rankings and achievements score 8."""
        deal = {'candidate_name': 'John Doe'}

        test_bullets = [
            BulletPoint(text="Top 10% producer", confidence=0.95, source="CRM"),
            BulletPoint(text="President's Club 2023", confidence=0.95, source="CRM"),
            BulletPoint(text="#1 ranked advisor in region", confidence=0.95, source="CRM"),
            BulletPoint(text="Award winner 3 years running", confidence=0.95, source="CRM"),
        ]

        scores = [self.curator._score_bullet(b, deal) for b in test_bullets]

        # All rankings/achievements should score 8.0
        assert all(score == 8.0 for score in scores)

    def test_licenses_score_7(self):
        """Test that licenses and designations score 7."""
        deal = {'candidate_name': 'John Doe'}

        test_bullets = [
            BulletPoint(text="Licenses: Series 7, 66, CFA", confidence=0.95, source="CRM"),
            BulletPoint(text="CFA charterholder", confidence=0.95, source="CRM"),
            BulletPoint(text="Series 65 licensed", confidence=0.95, source="CRM"),
        ]

        scores = [self.curator._score_bullet(b, deal) for b in test_bullets]

        # Multiple licenses should score 7.0
        assert scores[0] == 7.0  # Multiple with comma
        # Single license should score 6.8
        assert scores[1] == 6.8  # Single CFA
        assert scores[2] == 6.8  # Single Series 65

    def test_experience_scores_5(self):
        """Test that experience scores 5 with bonus for more years."""
        deal = {'candidate_name': 'John Doe'}

        test_bullets = [
            BulletPoint(text="Experience: 25+ years", confidence=0.95, source="CRM"),
            BulletPoint(text="Experience: 15 years in finance", confidence=0.95, source="CRM"),
            BulletPoint(text="Experience: 5 years", confidence=0.95, source="CRM"),
        ]

        scores = [self.curator._score_bullet(b, deal) for b in test_bullets]

        # 20+ years should score 5.5
        assert scores[0] == 5.5
        # 10-19 years should score 5.2
        assert scores[1] == 5.2
        # <10 years should score 5.0
        assert scores[2] == 5.0

    def test_availability_compensation_score_low(self):
        """Test that availability and compensation score low."""
        deal = {'candidate_name': 'John Doe'}

        test_bullets = [
            BulletPoint(text="Available immediately", confidence=0.9, source="CRM"),
            BulletPoint(text="Available in 2 weeks", confidence=0.9, source="CRM"),
            BulletPoint(text="Target comp: $200k–$300k OTE", confidence=0.9, source="CRM"),
            BulletPoint(text="Compensation: $250k", confidence=0.9, source="CRM"),
        ]

        scores = [self.curator._score_bullet(b, deal) for b in test_bullets]

        # Availability should score 3.0
        assert scores[0] == 3.0
        assert scores[1] == 3.0
        # Compensation should score 2.0
        assert scores[2] == 2.0
        assert scores[3] == 2.0

    def test_location_company_score_zero(self):
        """Test that location and company bullets score 0 (filtered out)."""
        deal = {
            'candidate_name': 'John Doe',
            'company_name': 'Morgan Stanley',
            'location': 'New York, NY'
        }

        test_bullets = [
            BulletPoint(text="Location: New York, NY", confidence=0.7, source="CRM"),
            BulletPoint(text="Company: Morgan Stanley", confidence=0.7, source="CRM"),
            BulletPoint(text="Firm: Large Wirehouse", confidence=0.7, source="CRM"),
            BulletPoint(text="John Doe is the candidate", confidence=0.7, source="CRM"),
        ]

        scores = [self.curator._score_bullet(b, deal) for b in test_bullets]

        # All should score 0 (redundant with header)
        assert all(score == 0.0 for score in scores)


class TestBulletRanking:
    """Test the complete bullet generation and ranking process."""

    @pytest.mark.asyncio
    async def test_growth_metric_appears_first(self):
        """Test that growth metrics appear in top 3 when present."""
        curator = TalentWellCuratorRefactored()

        # Mock data with growth metric
        deal = {
            'candidate_name': 'Jane Smith',
            'company_name': 'Test Firm',
            'book_size_aum': '$500M',
            'production_12mo': '$400K',
            'professional_designations': 'Series 7, 66',
            'years_experience': '12 years',
            'when_available': '2 weeks',
            'desired_comp': '$200K'
        }

        enhanced_data = {
            'achievements': ['Grew book by 200% in 3 years'],
            'client_count': '150'
        }

        transcript = "Grew the book from $150 million to $500 million in just 3 years."

        bullets = await curator._generate_hard_skill_bullets(deal, enhanced_data, transcript)

        # Check that growth metric is in top 3
        growth_found = any('grew' in b.text.lower() or 'growth' in b.text.lower()
                          for b in bullets[:3])
        assert growth_found, f"Growth metric not in top 3. Bullets: {[b.text for b in bullets[:3]]}"

    @pytest.mark.asyncio
    async def test_aum_prioritized_without_growth(self):
        """Test that AUM is #1 when no growth metrics present."""
        curator = TalentWellCuratorRefactored()

        # Mock the helper methods
        curator._parse_aum = lambda x: 2000000000 if '$2B' in x else 0
        curator._round_aum_for_privacy = lambda x: "$1B–$5B" if x >= 1000000000 else ""
        curator._is_internal_note = lambda x: False

        deal = {
            'candidate_name': 'Bob Johnson',
            'company_name': 'Test Firm',
            'book_size_aum': '$2B',
            'production_12mo': '$1.5M',
            'professional_designations': 'CFA, CFP',
            'years_experience': '20 years'
        }

        enhanced_data = {}

        bullets = await curator._generate_hard_skill_bullets(deal, enhanced_data, None)

        # AUM should be first bullet
        assert len(bullets) > 0
        assert 'aum' in bullets[0].text.lower(), f"First bullet is not AUM: {bullets[0].text}"

    @pytest.mark.asyncio
    async def test_location_filtered_out(self):
        """Test that location data never appears in bullets."""
        curator = TalentWellCuratorRefactored()

        deal = {
            'candidate_name': 'Alice Brown',
            'company_name': 'Test Firm',
            'location': 'Chicago, IL',
            'education': 'MBA from Wharton',
            'industry_focus': 'Healthcare',
            'years_experience': '8 years'
        }

        enhanced_data = {
            'aum_managed': '$250M',
            'production_annual': '$500K'
        }

        bullets = await curator._generate_hard_skill_bullets(deal, enhanced_data, None)

        # Location should not be in bullets (score 0)
        location_found = any('location:' in b.text.lower() or 'chicago' in b.text.lower()
                            for b in bullets)
        assert not location_found, f"Location found in bullets: {[b.text for b in bullets]}"

    @pytest.mark.asyncio
    async def test_all_sources_collected_and_scored(self):
        """Test that bullets are collected from ALL sources then scored."""
        curator = TalentWellCuratorRefactored()

        # Mock helper methods
        curator._parse_aum = Mock(return_value=0)
        curator._round_aum_for_privacy = Mock(return_value="")
        curator._is_internal_note = Mock(return_value=False)
        curator.evidence_extractor = Mock()
        curator.evidence_extractor.generate_bullets_with_evidence = Mock(return_value=[
            BulletPoint(text="Top 5% performer nationwide", confidence=0.9, source="Transcript"),
            BulletPoint(text="Manages team of 8", confidence=0.8, source="Transcript")
        ])

        deal = {
            'candidate_name': 'Test Candidate',
            'production_12mo': '$800K',
            'professional_designations': 'Series 7, 66',
            'education': 'MBA Finance'
        }

        enhanced_data = {
            'client_count': '200+ households',
            'years_experience': '15 years'
        }

        transcript = "Top performer with consistent growth"

        bullets = await curator._generate_hard_skill_bullets(deal, enhanced_data, transcript)

        # Should have bullets from multiple sources
        sources = set(b.source for b in bullets)
        assert len(sources) >= 2, f"Not enough source diversity: {sources}"

        # Top performer should rank high (achievement = score 8)
        if any('top' in b.text.lower() for b in bullets):
            top_bullet_index = next(i for i, b in enumerate(bullets)
                                   if 'top' in b.text.lower())
            assert top_bullet_index <= 2, f"Top performer not in top 3: position {top_bullet_index}"


class TestScoringExamples:
    """Document scoring examples for different scenarios."""

    def setup_method(self):
        """Set up test curator instance."""
        self.curator = TalentWellCuratorRefactored()

    def test_scoring_example_high_value_candidate(self):
        """Example: High-value candidate with growth and AUM."""
        deal = {'candidate_name': 'Elite Advisor', 'company_name': 'Major Firm'}

        bullets_with_scores = [
            (BulletPoint(text="AUM: $5B+", confidence=0.95, source="CRM"), 10.0),
            (BulletPoint(text="Grew book by 300% in 4 years", confidence=0.95, source="CRM"), 9.0),
            (BulletPoint(text="Production: $3.5M", confidence=0.95, source="CRM"), 8.5),
            (BulletPoint(text="Top 1% producer nationally", confidence=0.95, source="CRM"), 8.0),
            (BulletPoint(text="Clients: 400+ households", confidence=0.9, source="CRM"), 7.5),
            (BulletPoint(text="Licenses: Series 7, 66, CFA, CFP", confidence=0.95, source="CRM"), 7.0),
            (BulletPoint(text="Experience: 25+ years", confidence=0.95, source="CRM"), 5.5),
            (BulletPoint(text="Available in 30 days", confidence=0.9, source="CRM"), 3.0),
        ]

        # Verify scoring
        for bullet, expected_score in bullets_with_scores:
            actual_score = self.curator._score_bullet(bullet, deal)
            assert actual_score == expected_score, f"Bullet '{bullet.text}' scored {actual_score}, expected {expected_score}"

        # Document the expected output order (top 5)
        expected_order = [
            "AUM: $5B+",                      # Score: 10.0
            "Grew book by 300% in 4 years",   # Score: 9.0
            "Production: $3.5M",               # Score: 8.5
            "Top 1% producer nationally",      # Score: 8.0
            "Clients: 400+ households"         # Score: 7.5
        ]

        print("\nHigh-Value Candidate Bullet Order:")
        for i, text in enumerate(expected_order, 1):
            print(f"  {i}. {text}")

    def test_scoring_example_standard_candidate(self):
        """Example: Standard candidate without growth metrics."""
        deal = {'candidate_name': 'Standard Advisor', 'company_name': 'Regional Firm'}

        bullets_with_scores = [
            (BulletPoint(text="AUM: $100M–$500M", confidence=0.95, source="CRM"), 9.8),
            (BulletPoint(text="Production: $450K", confidence=0.95, source="CRM"), 8.5),
            (BulletPoint(text="Clients: 125", confidence=0.9, source="CRM"), 7.5),
            (BulletPoint(text="Licenses: Series 7, 66", confidence=0.95, source="CRM"), 7.0),
            (BulletPoint(text="Experience: 10 years", confidence=0.95, source="CRM"), 5.2),
            (BulletPoint(text="Education: MBA Finance", confidence=0.8, source="CRM"), 4.0),
            (BulletPoint(text="Available immediately", confidence=0.9, source="CRM"), 3.0),
            (BulletPoint(text="Target comp: $150k–$200k", confidence=0.9, source="CRM"), 2.0),
        ]

        # Document the expected output order (top 5)
        expected_order = [
            "AUM: $100M–$500M",      # Score: 9.8
            "Production: $450K",      # Score: 8.5
            "Clients: 125",          # Score: 7.5
            "Licenses: Series 7, 66", # Score: 7.0
            "Experience: 10 years"    # Score: 5.2
        ]

        print("\nStandard Candidate Bullet Order:")
        for i, text in enumerate(expected_order, 1):
            print(f"  {i}. {text}")

    def test_scoring_example_early_career(self):
        """Example: Early career advisor with limited metrics."""
        deal = {'candidate_name': 'Junior Advisor', 'company_name': 'Small Firm'}

        bullets_with_scores = [
            (BulletPoint(text="Licenses: Series 7, 66", confidence=0.95, source="CRM"), 7.0),
            (BulletPoint(text="Experience: 3 years", confidence=0.95, source="CRM"), 5.0),
            (BulletPoint(text="Education: Bachelor's Finance", confidence=0.8, source="CRM"), 4.0),
            (BulletPoint(text="Specialties: Retirement planning, 401k", confidence=0.75, source="CRM"), 3.5),
            (BulletPoint(text="Available immediately", confidence=0.9, source="CRM"), 3.0),
            (BulletPoint(text="Target comp: $80k–$120k", confidence=0.9, source="CRM"), 2.0),
        ]

        # Document the expected output order (top 5, may be less)
        expected_order = [
            "Licenses: Series 7, 66",              # Score: 7.0
            "Experience: 3 years",                  # Score: 5.0
            "Education: Bachelor's Finance",        # Score: 4.0
            "Specialties: Retirement planning, 401k", # Score: 3.5
            "Available immediately"                 # Score: 3.0
        ]

        print("\nEarly Career Candidate Bullet Order:")
        for i, text in enumerate(expected_order, 1):
            print(f"  {i}. {text}")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "-s"])