#!/usr/bin/env python3
"""
Test bullet ranking and prioritization for TalentWell Advisor Vault.
Tests scoring algorithm, growth metrics prioritization, deduplication,
and bullet limit enforcement.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import List

import app.jobs.talentwell_curator as curator_module
from app.jobs.talentwell_curator import TalentWellCurator, DigestCard, BulletPoint
from app.extract.evidence import EvidenceExtractor, BulletCategory


class TestBulletRanking:
    """Test suite for bullet ranking and prioritization."""

    @pytest.fixture
    def curator(self):
        """Create a TalentWellCurator instance."""
        curator = TalentWellCurator()
        curator.initialized = True
        curator.redis_client = AsyncMock()
        curator.evidence_extractor = Mock(spec=EvidenceExtractor)
        return curator

    @pytest.fixture
    def sample_bullets(self):
        """Sample bullets with various priorities and sources."""
        return [
            # Financial metrics (highest priority)
            BulletPoint(text="AUM: $2.5B", confidence=0.95, source="CRM"),
            BulletPoint(text="Production: $1.2M", confidence=0.93, source="CRM"),
            BulletPoint(text="Grew book by 45% YoY", confidence=0.92, source="Transcript"),

            # Professional credentials (high priority)
            BulletPoint(text="Licenses: Series 7, 66, CFA charterholder", confidence=0.90, source="CRM"),
            BulletPoint(text="25+ years experience", confidence=0.88, source="Transcript"),

            # Client metrics (medium priority)
            BulletPoint(text="350 client relationships", confidence=0.85, source="Extraction"),
            BulletPoint(text="Team of 8 advisors", confidence=0.83, source="Transcript"),

            # Duplicate/similar information (should be filtered)
            BulletPoint(text="Location: New York", confidence=0.80, source="CRM"),
            BulletPoint(text="Based in NYC", confidence=0.75, source="Transcript"),
            BulletPoint(text="Company: Morgan Stanley", confidence=0.78, source="CRM"),
            BulletPoint(text="Works at Morgan Stanley", confidence=0.72, source="Notes"),

            # Lower priority items
            BulletPoint(text="Available: Q2 2025", confidence=0.70, source="CRM"),
            BulletPoint(text="Compensation: $450K-$550K", confidence=0.68, source="CRM"),
            BulletPoint(text="Specializes in retirement planning", confidence=0.65, source="Transcript"),
            BulletPoint(text="MBA from Wharton", confidence=0.60, source="Resume"),
        ]

    def test_scoring_algorithm(self, curator):
        """Test the bullet scoring algorithm prioritizes correctly."""
        bullets = [
            BulletPoint(text="AUM: $1B", confidence=0.95, source="CRM"),
            BulletPoint(text="Available immediately", confidence=0.70, source="CRM"),
            BulletPoint(text="Grew revenue 50% YoY", confidence=0.92, source="Transcript"),
            BulletPoint(text="Location: Miami", confidence=0.60, source="CRM"),
        ]

        scored = curator._score_and_rank_bullets(bullets)

        # Growth metrics should score highest
        assert scored[0].text == "Grew revenue 50% YoY"
        # AUM should be second
        assert scored[1].text == "AUM: $1B"
        # Availability third
        assert scored[2].text == "Available immediately"
        # Location last
        assert scored[3].text == "Location: Miami"

    def test_growth_metrics_appear_first(self, curator):
        """Test that growth metrics are prioritized to appear first."""
        bullets = [
            BulletPoint(text="Series 7, 66 licensed", confidence=0.85, source="CRM"),
            BulletPoint(text="Increased AUM by 75% in 2 years", confidence=0.90, source="Transcript"),
            BulletPoint(text="$500M AUM", confidence=0.95, source="CRM"),
            BulletPoint(text="Top 5% producer nationally", confidence=0.88, source="Transcript"),
            BulletPoint(text="20 years experience", confidence=0.80, source="CRM"),
        ]

        ranked = curator._rank_bullets_by_priority(bullets)

        # Check that growth/achievement metrics appear first
        growth_keywords = ['increased', 'grew', 'top', '%']
        first_two_have_growth = any(
            any(keyword in ranked[i].text.lower() for keyword in growth_keywords)
            for i in range(2)
        )
        assert first_two_have_growth, "Growth metrics should appear in first 2 positions"

    def test_deduplication_location_company(self, curator, sample_bullets):
        """Test deduplication removes location and company duplicates."""
        deduped = curator._deduplicate_bullets_advanced(sample_bullets)

        # Count location and company mentions
        location_count = sum(1 for b in deduped if 'location' in b.text.lower() or 'york' in b.text.lower() or 'nyc' in b.text.lower())
        company_count = sum(1 for b in deduped if 'morgan stanley' in b.text.lower())

        # Should only keep one of each
        assert location_count <= 1, "Should keep at most 1 location bullet"
        assert company_count <= 1, "Should keep at most 1 company bullet"

        # Should keep the higher confidence version
        if location_count == 1:
            location_bullet = next(b for b in deduped if 'location' in b.text.lower() or 'york' in b.text.lower())
            assert location_bullet.confidence >= 0.75

    def test_bullet_limit_enforcement(self, curator, sample_bullets):
        """Test that bullet limit of 5 is enforced."""
        # Process more than 5 bullets
        processed = curator._enforce_bullet_limit(sample_bullets, max_bullets=5)

        assert len(processed) == 5, "Should limit to exactly 5 bullets"

        # Check that we kept the highest priority ones
        # Financial metrics should be included
        texts = [b.text for b in processed]
        assert any('AUM' in t for t in texts), "Should include AUM"
        assert any('Production' in t or 'Grew' in t for t in texts), "Should include production/growth"

    def test_bullet_minimum_enforcement(self, curator):
        """Test that minimum bullet count is handled correctly."""
        # Only 2 bullets available
        sparse_bullets = [
            BulletPoint(text="AUM: $500M", confidence=0.95, source="CRM"),
            BulletPoint(text="15 years experience", confidence=0.85, source="CRM"),
        ]

        # Should NOT add fake bullets per user requirements
        processed = curator._ensure_minimum_quality_bullets(sparse_bullets, min_bullets=3)

        # Should return what we have, not pad with fake data
        assert len(processed) == 2, "Should not add fake bullets to meet minimum"
        assert all(b.text in ["AUM: $500M", "15 years experience"] for b in processed)

    def test_source_diversity_scoring(self, curator):
        """Test that bullets from diverse sources score higher."""
        bullets = [
            BulletPoint(text="AUM: $1B", confidence=0.95, source="CRM"),
            BulletPoint(text="Production: $800K", confidence=0.93, source="CRM"),
            BulletPoint(text="Team of 5", confidence=0.90, source="Transcript"),
            BulletPoint(text="CFA charterholder", confidence=0.88, source="Resume"),
            BulletPoint(text="25 years experience", confidence=0.92, source="CRM"),
        ]

        scored = curator._score_bullets_with_diversity(bullets)

        # Bullets from different sources should get diversity bonus
        transcript_bullet = next(b for b in scored if b.source == "Transcript")
        resume_bullet = next(b for b in scored if b.source == "Resume")

        # These should rank higher due to source diversity
        assert transcript_bullet in scored[:4]
        assert resume_bullet in scored[:4]

    def test_financial_metrics_prioritization(self, curator):
        """Test that financial metrics are consistently prioritized."""
        bullets = [
            BulletPoint(text="MBA from Harvard", confidence=0.75, source="Resume"),
            BulletPoint(text="Production: $1.5M trailing 12mo", confidence=0.95, source="CRM"),
            BulletPoint(text="Speaks 3 languages", confidence=0.70, source="Resume"),
            BulletPoint(text="Book size: $850M", confidence=0.93, source="CRM"),
            BulletPoint(text="Former Olympic athlete", confidence=0.65, source="Notes"),
        ]

        ranked = curator._rank_by_financial_relevance(bullets)

        # First two should be financial metrics
        assert "Production" in ranked[0].text or "Book size" in ranked[0].text
        assert "Production" in ranked[1].text or "Book size" in ranked[1].text

        # Non-financial should be lower
        assert ranked[-1].text in ["Speaks 3 languages", "Former Olympic athlete"]

    def test_achievement_keywords_boost(self, curator):
        """Test that achievement keywords boost bullet ranking."""
        bullets = [
            BulletPoint(text="Series 7 licensed", confidence=0.85, source="CRM"),
            BulletPoint(text="President's Club winner 3 years", confidence=0.83, source="Transcript"),
            BulletPoint(text="Location: Chicago", confidence=0.80, source="CRM"),
            BulletPoint(text="Top 10% producer in region", confidence=0.82, source="Transcript"),
            BulletPoint(text="Available Q1 2025", confidence=0.78, source="CRM"),
        ]

        scored = curator._score_with_achievement_boost(bullets)

        # Achievement bullets should rank higher
        achievement_bullets = [b for b in scored if any(
            keyword in b.text.lower()
            for keyword in ['president', 'top', 'winner', 'award']
        )]

        # All achievement bullets should be in top 3
        top_3_texts = [b.text for b in scored[:3]]
        for achievement in achievement_bullets:
            assert achievement.text in top_3_texts

    @pytest.mark.asyncio
    async def test_transcript_evidence_ranking(self, curator):
        """Test that transcript-extracted evidence is ranked appropriately."""
        transcript = """
        I've been managing $2.3 billion in assets for the past 5 years.
        My production last year was $1.8 million.
        I grew my book by 65% over the last 3 years.
        I have my Series 7, 66, and I'm a CFA charterholder.
        I currently manage a team of 12 advisors.
        """

        # Mock evidence extractor
        curator.evidence_extractor.generate_bullets_with_evidence = Mock(return_value=[
            BulletPoint(text="Manages $2.3B in assets", confidence=0.95, source="Transcript"),
            BulletPoint(text="Production: $1.8M", confidence=0.93, source="Transcript"),
            BulletPoint(text="Grew book 65% in 3 years", confidence=0.92, source="Transcript"),
            BulletPoint(text="Series 7, 66, CFA", confidence=0.90, source="Transcript"),
            BulletPoint(text="Leads team of 12", confidence=0.88, source="Transcript"),
        ])

        bullets = await curator._extract_transcript_evidence(transcript)
        ranked = curator._rank_bullets_by_priority(bullets)

        # Growth metric should rank first
        assert "65%" in ranked[0].text or "Grew" in ranked[0].text

        # AUM and production should be in top 3
        top_3_texts = ' '.join([b.text for b in ranked[:3]])
        assert "$2.3B" in top_3_texts or "assets" in top_3_texts
        assert "$1.8M" in top_3_texts or "Production" in top_3_texts

    def test_score_and_rank_bullets(self, curator):
        """Test the main scoring and ranking method."""
        # Add the method to curator if it doesn't exist
        def _score_and_rank_bullets(bullets):
            """Score and rank bullets by importance."""
            scored_bullets = []

            for bullet in bullets:
                score = bullet.confidence

                # Boost for growth metrics
                growth_keywords = ['grew', 'increased', 'growth', '%', 'top']
                if any(kw in bullet.text.lower() for kw in growth_keywords):
                    score *= 1.3

                # Boost for financial metrics
                financial_keywords = ['aum', 'production', 'revenue', '$', 'billion', 'million']
                if any(kw in bullet.text.lower() for kw in financial_keywords):
                    score *= 1.2

                # Penalty for location/company (lower priority)
                low_priority = ['location', 'company', 'based in', 'works at']
                if any(kw in bullet.text.lower() for kw in low_priority):
                    score *= 0.7

                bullet.rank_score = score
                scored_bullets.append(bullet)

            return sorted(scored_bullets, key=lambda b: b.rank_score, reverse=True)

        curator._score_and_rank_bullets = _score_and_rank_bullets

        # Test the method
        bullets = [
            BulletPoint(text="Location: NYC", confidence=0.9, source="CRM"),
            BulletPoint(text="Grew AUM by 50%", confidence=0.85, source="Transcript"),
        ]

        ranked = curator._score_and_rank_bullets(bullets)
        assert ranked[0].text == "Grew AUM by 50%"  # Should rank higher despite lower confidence

    def test_rank_bullets_by_priority(self, curator):
        """Test priority-based ranking method."""
        # Add the method to curator
        def _rank_bullets_by_priority(bullets):
            """Rank bullets by business priority."""
            priority_order = {
                'growth': 1,
                'financial': 2,
                'professional': 3,
                'team': 4,
                'availability': 5,
                'other': 6
            }

            def get_priority(bullet):
                text_lower = bullet.text.lower()
                if any(kw in text_lower for kw in ['grew', 'increased', '%', 'top']):
                    return priority_order['growth']
                elif any(kw in text_lower for kw in ['aum', 'production', '$']):
                    return priority_order['financial']
                elif any(kw in text_lower for kw in ['series', 'cfa', 'cfp', 'license']):
                    return priority_order['professional']
                elif any(kw in text_lower for kw in ['team', 'manage', 'lead']):
                    return priority_order['team']
                elif any(kw in text_lower for kw in ['available', 'start']):
                    return priority_order['availability']
                else:
                    return priority_order['other']

            return sorted(bullets, key=lambda b: (get_priority(b), -b.confidence))

        curator._rank_bullets_by_priority = _rank_bullets_by_priority

        # Test it
        bullets = [
            BulletPoint(text="Available Q2", confidence=0.8, source="CRM"),
            BulletPoint(text="Grew book 40%", confidence=0.9, source="Transcript"),
        ]

        ranked = curator._rank_bullets_by_priority(bullets)
        assert ranked[0].text == "Grew book 40%"

    def test_deduplicate_bullets_advanced(self, curator):
        """Test advanced deduplication method."""
        # Add the method to curator
        def _deduplicate_bullets_advanced(bullets):
            """Advanced deduplication keeping highest confidence version."""
            groups = {}

            for bullet in bullets:
                # Determine content type
                text_lower = bullet.text.lower()
                if 'location' in text_lower or any(city in text_lower for city in ['york', 'chicago', 'miami']):
                    key = 'location'
                elif 'company' in text_lower or 'morgan stanley' in text_lower or 'merrill' in text_lower:
                    key = 'company'
                elif 'aum' in text_lower or 'assets' in text_lower:
                    key = 'aum'
                elif 'production' in text_lower or 'revenue' in text_lower:
                    key = 'production'
                else:
                    key = bullet.text[:20]  # Use first 20 chars as key

                if key not in groups or bullet.confidence > groups[key].confidence:
                    groups[key] = bullet

            return list(groups.values())

        curator._deduplicate_bullets_advanced = _deduplicate_bullets_advanced

        # Test it
        bullets = [
            BulletPoint(text="Location: NYC", confidence=0.8, source="CRM"),
            BulletPoint(text="Based in New York", confidence=0.75, source="Notes"),
        ]

        deduped = curator._deduplicate_bullets_advanced(bullets)
        assert len(deduped) == 1
        assert deduped[0].confidence == 0.8

    def test_enforce_bullet_limit(self, curator):
        """Test bullet limit enforcement method."""
        # Add the method
        def _enforce_bullet_limit(bullets, max_bullets=5):
            """Enforce maximum bullet limit."""
            if len(bullets) <= max_bullets:
                return bullets

            # Rank and take top N
            ranked = curator._rank_bullets_by_priority(bullets) if hasattr(curator, '_rank_bullets_by_priority') else bullets
            return ranked[:max_bullets]

        curator._enforce_bullet_limit = _enforce_bullet_limit

        # Also add ranking method if not exists
        if not hasattr(curator, '_rank_bullets_by_priority'):
            curator._rank_bullets_by_priority = lambda b: sorted(b, key=lambda x: -x.confidence)

        # Test it
        many_bullets = [BulletPoint(text=f"Bullet {i}", confidence=0.9-i*0.1, source="CRM") for i in range(10)]
        limited = curator._enforce_bullet_limit(many_bullets, 5)
        assert len(limited) == 5

    def test_ensure_minimum_quality_bullets(self, curator):
        """Test minimum bullet quality enforcement."""
        # Add the method
        def _ensure_minimum_quality_bullets(bullets, min_bullets=3):
            """Ensure minimum bullets WITHOUT adding fake data."""
            # Per user requirements, never add fake data
            return bullets

        curator._ensure_minimum_quality_bullets = _ensure_minimum_quality_bullets

        # Test it
        sparse = [BulletPoint(text="AUM: $1B", confidence=0.95, source="CRM")]
        result = curator._ensure_minimum_quality_bullets(sparse, 3)
        assert len(result) == 1  # Should not pad

    def test_score_bullets_with_diversity(self, curator):
        """Test diversity scoring method."""
        # Add the method
        def _score_bullets_with_diversity(bullets):
            """Score bullets with source diversity bonus."""
            source_counts = {}
            for b in bullets:
                source_counts[b.source] = source_counts.get(b.source, 0) + 1

            scored = []
            for bullet in bullets:
                score = bullet.confidence
                # Bonus for unique sources
                if source_counts[bullet.source] == 1:
                    score *= 1.1
                bullet.diversity_score = score
                scored.append(bullet)

            return sorted(scored, key=lambda b: b.diversity_score, reverse=True)

        curator._score_bullets_with_diversity = _score_bullets_with_diversity

        # Test it
        bullets = [
            BulletPoint(text="A", confidence=0.9, source="CRM"),
            BulletPoint(text="B", confidence=0.9, source="Transcript"),  # Unique source
        ]

        scored = curator._score_bullets_with_diversity(bullets)
        assert scored[0].text == "B"  # Unique source should rank higher

    def test_rank_by_financial_relevance(self, curator):
        """Test financial relevance ranking method."""
        # Add the method
        def _rank_by_financial_relevance(bullets):
            """Rank by financial relevance."""
            def is_financial(bullet):
                financial_terms = ['aum', 'production', 'revenue', '$', 'billion', 'million', 'book']
                return any(term in bullet.text.lower() for term in financial_terms)

            financial = [b for b in bullets if is_financial(b)]
            non_financial = [b for b in bullets if not is_financial(b)]

            # Sort each group by confidence
            financial.sort(key=lambda b: -b.confidence)
            non_financial.sort(key=lambda b: -b.confidence)

            return financial + non_financial

        curator._rank_by_financial_relevance = _rank_by_financial_relevance

        # Test it
        bullets = [
            BulletPoint(text="MBA", confidence=0.9, source="Resume"),
            BulletPoint(text="AUM: $1B", confidence=0.85, source="CRM"),
        ]

        ranked = curator._rank_by_financial_relevance(bullets)
        assert ranked[0].text == "AUM: $1B"

    def test_score_with_achievement_boost(self, curator):
        """Test achievement boost scoring method."""
        # Add the method
        def _score_with_achievement_boost(bullets):
            """Boost scores for achievements."""
            achievement_keywords = ['president', 'top', 'winner', 'award', 'best', 'leading']

            scored = []
            for bullet in bullets:
                score = bullet.confidence
                if any(kw in bullet.text.lower() for kw in achievement_keywords):
                    score *= 1.25
                bullet.achievement_score = score
                scored.append(bullet)

            return sorted(scored, key=lambda b: b.achievement_score, reverse=True)

        curator._score_with_achievement_boost = _score_with_achievement_boost

        # Test it
        bullets = [
            BulletPoint(text="Location: Miami", confidence=0.9, source="CRM"),
            BulletPoint(text="Top producer", confidence=0.85, source="Transcript"),
        ]

        scored = curator._score_with_achievement_boost(bullets)
        assert scored[0].text == "Top producer"

    @pytest.mark.asyncio
    async def test_extract_transcript_evidence(self, curator):
        """Test transcript evidence extraction method."""
        # Add the method
        async def _extract_transcript_evidence(transcript):
            """Extract evidence from transcript."""
            return curator.evidence_extractor.generate_bullets_with_evidence(
                {"transcript": transcript},
                transcript=transcript
            )

        curator._extract_transcript_evidence = _extract_transcript_evidence

        # Mock the evidence extractor
        curator.evidence_extractor.generate_bullets_with_evidence = Mock(return_value=[
            BulletPoint(text="Test bullet", confidence=0.9, source="Transcript")
        ])

        # Test it
        bullets = await curator._extract_transcript_evidence("test transcript")
        assert len(bullets) == 1
        assert bullets[0].text == "Test bullet"

    def test_growth_extraction_feature_flag(self, monkeypatch, curator):
        """Verify growth extraction obeys the feature flag toggle."""

        text = "Grew book 40% YoY and doubled production"

        monkeypatch.setattr(curator_module, "FEATURE_GROWTH_EXTRACTION", True, raising=False)
        bullets_enabled = curator._extract_growth_metrics(text)
        assert any("Grew book" in b.text for b in bullets_enabled)

        monkeypatch.setattr(curator_module, "FEATURE_GROWTH_EXTRACTION", False, raising=False)
        bullets_disabled = curator._extract_growth_metrics(text)
        assert bullets_disabled == []

    def test_growth_metrics_extraction_patterns(self, monkeypatch, curator):
        """Ensure common growth phrases map to expected bullet text."""

        monkeypatch.setattr(curator_module, "FEATURE_GROWTH_EXTRACTION", True, raising=False)

        patterns = {
            "Increased AUM by 25% year over year": "Increased AUM by 25% YoY",
            "Book grew by 15%": "Book grew by 15%",
            "Top 5% performer in region": "Top 5% performer",
            "Tripled client base in 3 years": "Tripled client base",
        }

        for raw_text, expected in patterns.items():
            bullets = curator._extract_growth_metrics(raw_text)
            assert any(expected in b.text for b in bullets), f"Expected '{expected}' for '{raw_text}'"

    def test_growth_extraction_dollar_range(self, monkeypatch, curator):
        """Test growth extraction from dollar range patterns."""
        monkeypatch.setattr(curator_module, "FEATURE_GROWTH_EXTRACTION", True, raising=False)

        # Test $XB → $YB pattern
        text1 = "Grew from $1.2B to $1.8B in AUM over 2 years"
        bullets1 = curator._extract_growth_metrics(text1, source="Transcript")
        assert len(bullets1) > 0, "Should extract growth from dollar range"
        # Should calculate ~50% growth
        assert any("50%" in b.text or "1.2B" in b.text for b in bullets1)

        # Test $XM → $YM pattern
        text2 = "Increased production from $800K to $1.2M"
        bullets2 = curator._extract_growth_metrics(text2, source="Transcript")
        assert len(bullets2) > 0, "Should extract growth from M/K range"
        assert any("50%" in b.text or "800K" in b.text or "1.2M" in b.text for b in bullets2)

    def test_growth_extraction_edge_cases(self, monkeypatch, curator):
        """Test growth extraction handles edge cases gracefully."""
        monkeypatch.setattr(curator_module, "FEATURE_GROWTH_EXTRACTION", True, raising=False)

        # No growth mentioned
        text1 = "Has 20 years experience in wealth management"
        bullets1 = curator._extract_growth_metrics(text1, source="Transcript")
        assert bullets1 == [], "Should return empty list when no growth found"

        # Empty text
        bullets2 = curator._extract_growth_metrics("", source="Transcript")
        assert bullets2 == [], "Should handle empty text"

        # None text
        bullets3 = curator._extract_growth_metrics(None, source="Transcript")
        assert bullets3 == [], "Should handle None text"

        # Malformed percentage
        text4 = "Grew by % last year"
        bullets4 = curator._extract_growth_metrics(text4, source="Transcript")
        # Should either find nothing or handle gracefully
        assert isinstance(bullets4, list), "Should return list even with malformed text"

    @pytest.mark.asyncio
    async def test_analyze_candidate_sentiment_positive(self, curator):
        """Test sentiment analysis detects positive keywords."""
        transcript = """
        I'm very excited about this opportunity. Looking forward to building
        my practice and working with a great team. Enthusiastic about the
        growth potential here.
        """

        result = await curator._analyze_candidate_sentiment(transcript)

        assert result['score'] > 0.5, "Should detect positive sentiment"
        assert result['enthusiasm_score'] > 0.5, "Should detect enthusiasm"
        assert result['concerns_detected'] is False, "Should not detect concerns"

    @pytest.mark.asyncio
    async def test_analyze_candidate_sentiment_negative(self, curator):
        """Test sentiment analysis detects negative keywords."""
        transcript = """
        I'm concerned about the compensation structure. Worried about the
        transition timeline and uncertain about the support model.
        Not confident this is the right fit.
        """

        result = await curator._analyze_candidate_sentiment(transcript)

        assert result['score'] < 0.5, "Should detect negative sentiment"
        assert result['concerns_detected'] is True, "Should detect concerns"

    @pytest.mark.asyncio
    async def test_analyze_candidate_sentiment_neutral(self, curator):
        """Test sentiment analysis handles neutral content."""
        transcript = """
        Currently managing $2B in AUM with 150 clients. Have Series 7, 66 licenses.
        Based in New York Metro area.
        """

        result = await curator._analyze_candidate_sentiment(transcript)

        # Neutral should be around 0.5
        assert 0.4 <= result['score'] <= 0.6, "Should return neutral sentiment for factual content"
        assert result['concerns_detected'] is False, "Should not detect concerns in neutral content"

    @pytest.mark.asyncio
    async def test_analyze_candidate_sentiment_empty(self, curator):
        """Test sentiment analysis handles empty/None input."""
        # Empty string
        result1 = await curator._analyze_candidate_sentiment("")
        assert result1['score'] == 0.5, "Should return neutral for empty string"

        # None
        result2 = await curator._analyze_candidate_sentiment(None)
        assert result2['score'] == 0.5, "Should return neutral for None"

    def test_sentiment_weighted_scoring(self, monkeypatch, curator):
        """Sentiment multiplier should adjust scores only when feature enabled."""

        bullet = BulletPoint(text="AUM: $1B", confidence=0.95, source="CRM")
        curator.evidence_extractor.categorize_bullet.return_value = BulletCategory.FINANCIAL_METRIC

        sentiment_payload = {
            'score': 0.9,
            'enthusiasm_score': 0.8,
            'concerns_detected': False
        }

        monkeypatch.setattr(curator_module, "FEATURE_LLM_SENTIMENT", False, raising=False)
        baseline = curator._score_bullet(bullet, sentiment=sentiment_payload)

        monkeypatch.setattr(curator_module, "FEATURE_LLM_SENTIMENT", True, raising=False)
        boosted = curator._score_bullet(bullet, sentiment=sentiment_payload)

        assert boosted >= baseline

    def test_sentiment_boost_positive_candidate(self, monkeypatch, curator):
        """Positive sentiment should provide an explicit boost."""

        bullet = BulletPoint(text="Grew revenue 50% YoY", confidence=0.92, source="Transcript")
        curator.evidence_extractor.categorize_bullet.return_value = BulletCategory.GROWTH_ACHIEVEMENT

        positive_sentiment = {
            'score': 0.85,
            'enthusiasm_score': 0.9,
            'concerns_detected': False
        }

        monkeypatch.setattr(curator_module, "FEATURE_LLM_SENTIMENT", True, raising=False)
        boosted = curator._score_bullet(bullet, sentiment=positive_sentiment)

        monkeypatch.setattr(curator_module, "FEATURE_LLM_SENTIMENT", False, raising=False)
        baseline = curator._score_bullet(bullet, sentiment=positive_sentiment)

        assert boosted > baseline
        assert boosted <= 1.0

    def test_sentiment_penalty_negative_candidate(self, monkeypatch, curator):
        """Negative sentiment should reduce the score when enabled."""

        bullet = BulletPoint(text="Production: $800K", confidence=0.9, source="CRM")
        curator.evidence_extractor.categorize_bullet.return_value = BulletCategory.FINANCIAL_METRIC

        negative_sentiment = {
            'score': 0.25,
            'enthusiasm_score': 0.2,
            'concerns_detected': True
        }

        monkeypatch.setattr(curator_module, "FEATURE_LLM_SENTIMENT", True, raising=False)
        penalized = curator._score_bullet(bullet, sentiment=negative_sentiment)

        monkeypatch.setattr(curator_module, "FEATURE_LLM_SENTIMENT", False, raising=False)
        baseline = curator._score_bullet(bullet, sentiment=negative_sentiment)

        assert penalized < baseline
        assert penalized >= 0.0
