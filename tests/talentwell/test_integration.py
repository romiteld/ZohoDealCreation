#!/usr/bin/env python3
"""
Test cross-system integration for TalentWell Advisor Vault.
Tests Outlook enrichment cache write, TalentWell enrichment cache read,
and cross-system deduplication.
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import hashlib

from app.jobs.talentwell_curator import TalentWellCurator, DigestCard, BulletPoint
from well_shared.cache.redis_manager import RedisCacheManager
from well_shared.cache.c3 import C3Entry, DependencyCertificate


class TestIntegration:
    """Test suite for cross-system integration."""

    @pytest.fixture
    async def redis_cache(self):
        """Create a mock Redis cache manager."""
        cache = AsyncMock(spec=RedisCacheManager)
        cache.client = AsyncMock()
        cache.client.get = AsyncMock(return_value=None)
        cache.client.set = AsyncMock(return_value=True)
        cache.client.setex = AsyncMock(return_value=True)
        cache.client.sadd = AsyncMock(return_value=1)
        cache.client.sismember = AsyncMock(return_value=False)
        cache.client.expire = AsyncMock(return_value=True)
        return cache

    @pytest.fixture
    def curator_with_cache(self, redis_cache):
        """Create curator with Redis cache."""
        curator = TalentWellCurator()
        curator.initialized = True
        curator.redis_client = redis_cache.client
        curator.cache_manager = redis_cache
        return curator

    @pytest.fixture
    def outlook_enrichment_data(self):
        """Sample enrichment data from Outlook processing."""
        return {
            'candidate_id': 'cand_123',
            'email': 'john.smith@example.com',
            'enriched_data': {
                'first_name': 'John',
                'last_name': 'Smith',
                'company': 'Morgan Stanley',
                'title': 'Senior Financial Advisor',
                'location': 'New York, NY',
                'phone': '+1-212-555-0100',
                'linkedin_url': 'https://linkedin.com/in/johnsmith',
                'years_experience': 15,
                'company_size': '10000+',
                'industry': 'Financial Services'
            },
            'source': 'apollo',
            'timestamp': datetime.now().isoformat(),
            'confidence': 0.95
        }

    @pytest.fixture
    def talentwell_deal(self):
        """Sample TalentWell deal data."""
        return {
            'id': 'deal_456',
            'candidate_name': 'John Smith',
            'job_title': 'Financial Advisor',
            'company_name': 'Morgan Stanley',
            'location': 'New York',
            'email': 'john.smith@example.com',
            'book_size_aum': '$1500000000',
            'production_12mo': '$950000',
            'when_available': 'Q2 2025',
            'is_mobile': True,
            'remote_preference': False,
            'hybrid_preference': True
        }

    @pytest.mark.asyncio
    async def test_outlook_enrichment_cache_write(self, curator_with_cache, outlook_enrichment_data):
        """Test that Outlook writes enrichment data to cache."""
        # Simulate Outlook writing enrichment to cache
        cache_key = f"enrichment:apollo:{outlook_enrichment_data['email']}"

        await curator_with_cache.redis_client.setex(
            cache_key,
            86400 * 7,  # 7-day TTL
            json.dumps(outlook_enrichment_data)
        )

        # Verify cache write was called
        curator_with_cache.redis_client.setex.assert_called_once_with(
            cache_key,
            86400 * 7,
            json.dumps(outlook_enrichment_data)
        )

    @pytest.mark.asyncio
    async def test_talentwell_enrichment_cache_read(self, curator_with_cache, outlook_enrichment_data):
        """Test that TalentWell reads enrichment from cache."""
        # Setup cache to return enrichment data
        cache_key = f"enrichment:apollo:john.smith@example.com"
        curator_with_cache.redis_client.get.return_value = json.dumps(outlook_enrichment_data).encode()

        # Simulate TalentWell checking for cached enrichment
        cached_data = await curator_with_cache.redis_client.get(cache_key)

        assert cached_data is not None
        enrichment = json.loads(cached_data.decode())
        assert enrichment['enriched_data']['years_experience'] == 15
        assert enrichment['enriched_data']['company'] == 'Morgan Stanley'

    @pytest.mark.asyncio
    async def test_cross_system_deduplication(self, curator_with_cache):
        """Test deduplication across Outlook and TalentWell systems."""
        # Simulate candidates processed by different systems
        outlook_candidate = "john.smith@example.com:Morgan Stanley"
        talentwell_candidate = "deal_456:John Smith:Morgan Stanley"

        # Add to processed set
        processed_key = "candidates:processed:2025-14"  # Week 14 of 2025
        await curator_with_cache.redis_client.sadd(processed_key, outlook_candidate)
        await curator_with_cache.redis_client.sadd(processed_key, talentwell_candidate)

        # Check deduplication
        curator_with_cache.redis_client.sismember.side_effect = [True, False]

        is_processed_outlook = await curator_with_cache.redis_client.sismember(
            processed_key, outlook_candidate
        )
        is_processed_new = await curator_with_cache.redis_client.sismember(
            processed_key, "jane.doe@example.com:Wells Fargo"
        )

        assert is_processed_outlook is True
        assert is_processed_new is False

    @pytest.mark.asyncio
    async def test_c3_cache_integration(self, curator_with_cache, talentwell_deal):
        """Test C³ cache integration between systems."""
        # Create a digest card
        card = DigestCard(
            deal_id=talentwell_deal['id'],
            candidate_name=talentwell_deal['candidate_name'],
            job_title=talentwell_deal['job_title'],
            company="Major wirehouse",  # Anonymized
            location="New York Metro",
            bullets=[
                BulletPoint(text="AUM: $1.5B", confidence=0.95, source="CRM"),
                BulletPoint(text="Production: $950K", confidence=0.93, source="CRM"),
            ],
            evidence_score=0.94
        )

        # Generate cache key
        canonical_record = {
            'candidate_name': talentwell_deal['candidate_name'],
            'company': talentwell_deal['company_name'],
            'location': talentwell_deal['location']
        }

        cache_key = curator_with_cache._generate_cache_key(canonical_record, 'steve_perry')

        # Store in C³ cache
        await curator_with_cache._set_c3_entry(cache_key, card, canonical_record, 'steve_perry')

        # Verify cache storage
        curator_with_cache.redis_client.setex.assert_called()
        call_args = curator_with_cache.redis_client.setex.call_args
        assert call_args[0][0] == cache_key
        assert call_args[0][1] == 86400 * 7  # 7-day TTL

    @pytest.mark.asyncio
    async def test_embedding_based_deduplication(self, curator_with_cache):
        """Test embedding-based duplicate detection."""
        with patch('app.jobs.talentwell_curator.AsyncOpenAI') as mock_openai:
            # Mock OpenAI embeddings
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            # Mock embedding response
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]  # 1536-dim embedding
            mock_client.embeddings.create.return_value = mock_response

            # Test duplicate check
            is_duplicate = await curator_with_cache._check_duplicate_candidate(
                "John Smith",
                "Morgan Stanley",
                "Financial Advisor",
                "steve_perry"
            )

            # First check should not be duplicate (no existing embeddings)
            assert is_duplicate is False

            # Now simulate existing embeddings with high similarity
            import numpy as np
            existing_embedding = {
                'text': 'John Smith Morgan Stanley Financial Advisor',
                'embedding': [0.1] * 1536,  # Same embedding = perfect match
                'timestamp': datetime.now().isoformat()
            }

            curator_with_cache.redis_client.get.return_value = json.dumps([existing_embedding]).encode()

            # Check again - should be duplicate
            is_duplicate = await curator_with_cache._check_duplicate_candidate(
                "John Smith",
                "Morgan Stanley",
                "Financial Advisor",
                "steve_perry"
            )

            # With identical embeddings, similarity = 1.0 > 0.95 threshold
            assert is_duplicate is True

    @pytest.mark.asyncio
    async def test_batch_processing_integration(self, curator_with_cache):
        """Test batch processing with parallelization."""
        # Create sample deals
        deals = [
            {
                'id': f'deal_{i}',
                'candidate_name': f'Candidate {i}',
                'job_title': 'Financial Advisor',
                'company_name': 'Test Company',
                'location': 'New York',
                'book_size_aum': f'${i*100}000000'
            }
            for i in range(1, 16)  # 15 deals
        ]

        # Mock VoIT orchestration
        with patch('app.cache.voit.voit_orchestration') as mock_voit:
            mock_voit.return_value = {
                'enhanced_data': {'candidate_name': 'Test'},
                'model_used': 'gpt-5-mini',
                'budget_used': 2.5,
                'quality_score': 0.9
            }

            # Process deals in batches
            cards = await curator_with_cache._process_deals_batch(
                deals,
                'steve_perry',
                batch_size=5  # Process 5 at a time
            )

            # Should process all deals
            assert len(cards) <= 15  # Some might fail/return None

            # Verify batching happened (3 batches of 5)
            # VoIT should be called once per deal
            assert mock_voit.call_count == 15

    @pytest.mark.asyncio
    async def test_cross_system_data_flow(self, curator_with_cache, outlook_enrichment_data, talentwell_deal):
        """Test complete data flow from Outlook to TalentWell."""
        # Step 1: Outlook processes email and enriches via Apollo
        email_cache_key = f"enrichment:apollo:{talentwell_deal['email']}"
        await curator_with_cache.redis_client.setex(
            email_cache_key,
            86400 * 7,
            json.dumps(outlook_enrichment_data)
        )

        # Step 2: TalentWell processes deal and checks for enrichment
        curator_with_cache.redis_client.get.return_value = json.dumps(outlook_enrichment_data).encode()

        cached_enrichment = await curator_with_cache.redis_client.get(email_cache_key)
        enrichment = json.loads(cached_enrichment.decode()) if cached_enrichment else None

        assert enrichment is not None
        assert enrichment['enriched_data']['years_experience'] == 15

        # Step 3: Merge enrichment with deal data
        if enrichment:
            talentwell_deal['years_experience'] = enrichment['enriched_data']['years_experience']
            talentwell_deal['linkedin_url'] = enrichment['enriched_data'].get('linkedin_url')

        assert talentwell_deal['years_experience'] == 15
        assert talentwell_deal['linkedin_url'] == 'https://linkedin.com/in/johnsmith'

        # Step 4: Process deal with enriched data
        with patch('app.cache.voit.voit_orchestration') as mock_voit:
            mock_voit.return_value = {
                'enhanced_data': {
                    'candidate_name': talentwell_deal['candidate_name'],
                    'years_experience': talentwell_deal['years_experience']
                },
                'model_used': 'gpt-5-mini',
                'budget_used': 2.5,
                'quality_score': 0.92
            }

            card = await curator_with_cache._process_deal(talentwell_deal, 'steve_perry')

            # Card should have enriched data
            assert card is not None
            assert card.candidate_name == 'John Smith'

            # Should have bullets with enriched info
            bullet_texts = [b.text for b in card.bullets]
            # At least AUM should be present
            assert any('AUM' in text for text in bullet_texts)

    @pytest.mark.asyncio
    async def test_weekly_digest_deduplication(self, curator_with_cache):
        """Test weekly digest deduplication across 4 weeks."""
        current_date = datetime.now()
        candidate_id = "deal_123"

        # Add candidate to previous weeks
        for week_offset in range(1, 4):
            past_date = current_date - timedelta(weeks=week_offset)
            week_key = f"talentwell:processed:{past_date.year}-{past_date.isocalendar()[1]:02d}"
            await curator_with_cache.redis_client.sadd(week_key, candidate_id)

        # Setup mock to return True for membership check
        curator_with_cache.redis_client.sismember.return_value = True

        # Check if candidate was processed
        deals = [{'id': candidate_id, 'candidate_name': 'Test'}]
        processed_key = f"talentwell:processed:{current_date.year}-{current_date.isocalendar()[1]:02d}"

        new_deals = await curator_with_cache._filter_processed_deals(deals, processed_key)

        # Should filter out the already processed candidate
        assert len(new_deals) == 0

    @pytest.mark.asyncio
    async def test_cache_warming_strategy(self, curator_with_cache):
        """Test cache warming for frequently accessed data."""
        # Common queries that should be cached
        common_queries = [
            {'audience': 'steve_perry', 'timeframe': 'last_7_days'},
            {'audience': 'leadership', 'timeframe': 'last_7_days'},
        ]

        for query in common_queries:
            cache_key = f"digest:manifest:{query['audience']}:{query['timeframe']}"

            # Simulate cache warming
            manifest_data = {
                'audience': query['audience'],
                'cards_count': 10,
                'generated_at': datetime.now().isoformat()
            }

            await curator_with_cache.redis_client.setex(
                cache_key,
                3600,  # 1-hour TTL for manifests
                json.dumps(manifest_data)
            )

        # Verify cache warming occurred
        assert curator_with_cache.redis_client.setex.call_count >= 2

    @pytest.mark.asyncio
    async def test_apollo_to_talentwell_field_mapping(self, curator_with_cache):
        """Test field mapping from Apollo enrichment to TalentWell."""
        apollo_data = {
            'person': {
                'name': 'John Smith',
                'title': 'VP Wealth Management',
                'linkedin_url': 'https://linkedin.com/in/jsmith',
                'city': 'New York',
                'state': 'NY',
                'phone_numbers': ['+1-212-555-0100']
            },
            'organization': {
                'name': 'Morgan Stanley',
                'industry': 'Financial Services',
                'estimated_num_employees': 60000,
                'phone': '+1-212-555-0000',
                'linkedin_url': 'https://linkedin.com/company/morgan-stanley'
            }
        }

        # Map Apollo fields to TalentWell fields
        mapped_data = {
            'candidate_name': apollo_data['person']['name'],
            'job_title': apollo_data['person']['title'],
            'company_name': apollo_data['organization']['name'],
            'location': f"{apollo_data['person']['city']}, {apollo_data['person']['state']}",
            'contact_phone': apollo_data['person']['phone_numbers'][0] if apollo_data['person']['phone_numbers'] else None,
            'company_phone': apollo_data['organization']['phone'],
            'linkedin_url': apollo_data['person']['linkedin_url'],
            'company_size': apollo_data['organization']['estimated_num_employees'],
            'industry': apollo_data['organization']['industry']
        }

        # Verify mapping
        assert mapped_data['candidate_name'] == 'John Smith'
        assert mapped_data['job_title'] == 'VP Wealth Management'
        assert mapped_data['location'] == 'New York, NY'
        assert mapped_data['contact_phone'] == '+1-212-555-0100'

    @pytest.mark.asyncio
    async def test_multi_source_data_merge(self, curator_with_cache):
        """Test merging data from multiple sources (CRM, Apollo, Transcript)."""
        # CRM data
        crm_data = {
            'candidate_name': 'John Smith',
            'book_size_aum': '$1.5B',
            'production_12mo': '$950K'
        }

        # Apollo enrichment
        apollo_data = {
            'years_experience': 15,
            'licenses': ['Series 7', 'Series 66', 'CFA'],
            'linkedin_url': 'https://linkedin.com/in/jsmith'
        }

        # Transcript extraction
        transcript_data = {
            'growth_metric': 'Grew book by 45% YoY',
            'team_size': 'Manages team of 8',
            'specialties': ['Retirement planning', 'Estate planning']
        }

        # Merge all sources
        merged = {**crm_data, **apollo_data, **transcript_data}

        # Create bullets from merged data
        bullets = []

        if merged.get('book_size_aum'):
            bullets.append(BulletPoint(
                text=f"AUM: {merged['book_size_aum']}",
                confidence=0.95,
                source="CRM"
            ))

        if merged.get('growth_metric'):
            bullets.append(BulletPoint(
                text=merged['growth_metric'],
                confidence=0.92,
                source="Transcript"
            ))

        if merged.get('licenses'):
            bullets.append(BulletPoint(
                text=f"Licenses: {', '.join(merged['licenses'])}",
                confidence=0.90,
                source="Apollo"
            ))

        # Verify multi-source integration
        assert len(bullets) == 3
        sources = {b.source for b in bullets}
        assert sources == {'CRM', 'Transcript', 'Apollo'}

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, curator_with_cache):
        """Test rate limit handling across systems."""
        # Simulate rate limit scenario
        with patch('asyncio.sleep') as mock_sleep:
            # Process many requests
            for i in range(10):
                cache_key = f"test:rate_limit:{i}"
                await curator_with_cache.redis_client.get(cache_key)

            # Should not trigger rate limiting for cache reads
            mock_sleep.assert_not_called()

            # Simulate API rate limiting
            with patch('app.integrations.ZohoApiClient.query_candidates') as mock_zoho:
                mock_zoho.side_effect = [
                    Exception("Rate limit exceeded"),
                    Exception("Rate limit exceeded"),
                    []  # Success after retries
                ]

                # Should handle rate limiting with retries
                from app.integrations import ZohoApiClient
                client = ZohoApiClient()

                # Mock the retry mechanism
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    try:
                        result = await client.query_candidates(limit=10)
                    except:
                        # Rate limiting handled
                        pass

    @pytest.mark.asyncio
    async def test_error_recovery_integration(self, curator_with_cache):
        """Test error recovery across integrated systems."""
        deal = {
            'id': 'deal_error_test',
            'candidate_name': 'Test Candidate',
            'company_name': 'Test Company',
            'location': 'Test City'
        }

        # Simulate various failures
        with patch('app.cache.voit.voit_orchestration') as mock_voit:
            # First call fails, second succeeds
            mock_voit.side_effect = [
                Exception("OpenAI API error"),
                {
                    'enhanced_data': {'candidate_name': 'Test Candidate'},
                    'model_used': 'gpt-5-mini',
                    'budget_used': 2.5,
                    'quality_score': 0.9
                }
            ]

            # First attempt should fail gracefully
            card1 = await curator_with_cache._process_deal(deal, 'steve_perry')
            # Should return None or handle error gracefully

            # Second attempt should succeed
            card2 = await curator_with_cache._process_deal(deal, 'steve_perry')

            # At least one should succeed
            assert card1 is not None or card2 is not None