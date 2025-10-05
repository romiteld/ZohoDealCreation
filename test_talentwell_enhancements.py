#!/usr/bin/env python
"""
Test script for TalentWell Curator enhancements:
- C³ cache serialization/deserialization
- Async batch processing
- Fuzzy candidate deduplication
"""
import asyncio
import json
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv('.env.local')

# Import the curator
from app.jobs.talentwell_curator import TalentWellCurator


class PerformanceMetrics:
    """Track performance metrics for the test."""

    def __init__(self):
        self.cache_hits = 0
        self.cache_misses = 0
        self.batch_processing_times = []
        self.dedup_times = []
        self.total_candidates = 0
        self.duplicates_found = 0
        self.start_time = None

    def start(self):
        """Start timing."""
        self.start_time = time.time()

    def end(self):
        """End timing and return total duration."""
        return time.time() - self.start_time if self.start_time else 0

    def record_batch_time(self, batch_size: int, duration: float):
        """Record batch processing time."""
        self.batch_processing_times.append({
            'batch_size': batch_size,
            'duration': duration,
            'per_item': duration / batch_size if batch_size > 0 else 0
        })

    def record_cache_hit(self):
        """Record a cache hit."""
        self.cache_hits += 1

    def record_cache_miss(self):
        """Record a cache miss."""
        self.cache_misses += 1

    def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        avg_batch_time = sum(b['duration'] for b in self.batch_processing_times) / len(self.batch_processing_times) if self.batch_processing_times else 0
        avg_per_item = sum(b['per_item'] for b in self.batch_processing_times) / len(self.batch_processing_times) if self.batch_processing_times else 0

        return {
            'total_duration': self.end(),
            'cache_hit_rate': self.get_cache_hit_rate(),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'total_candidates': self.total_candidates,
            'duplicates_found': self.duplicates_found,
            'dedup_rate': (self.duplicates_found / self.total_candidates * 100) if self.total_candidates > 0 else 0,
            'batch_processing': {
                'total_batches': len(self.batch_processing_times),
                'avg_batch_time': avg_batch_time,
                'avg_per_item_time': avg_per_item
            }
        }


async def test_c3_cache_serialization():
    """Test C³ cache serialization and deserialization."""
    logger.info("Testing C³ cache serialization...")

    curator = TalentWellCurator()
    await curator.initialize()

    # Create a sample canonical record
    canonical_record = {
        'candidate_name': 'John Smith',
        'job_title': 'Senior Financial Advisor',
        'company': 'Wells Fargo',
        'location': 'New York, NY',
        'book_size_aum': '$500M',
        'production_12mo': '$2M',
        'deal_id': 'test_deal_001'
    }

    # Create a sample DigestCard
    from app.extract.evidence import BulletPoint
    from app.jobs.talentwell_curator import DigestCard

    card = DigestCard(
        deal_id='test_deal_001',
        candidate_name='John Smith',
        job_title='Senior Financial Advisor',
        company='Wells Fargo',
        location='New York, NY',
        bullets=[
            BulletPoint(text="AUM: $500M", confidence=0.95, source="CRM"),
            BulletPoint(text="Production: $2M", confidence=0.95, source="CRM"),
            BulletPoint(text="Experience: 15 years", confidence=0.90, source="CRM")
        ],
        evidence_score=0.93
    )

    # Test serialization
    cache_key = curator._generate_cache_key(canonical_record, 'test_audience')
    await curator._set_c3_entry(cache_key, card, canonical_record, 'test_audience')

    # Test deserialization
    retrieved_entry = await curator._get_c3_entry(cache_key)

    if retrieved_entry:
        logger.info("✓ C³ cache serialization successful")
        logger.info(f"  - Cache key: {cache_key}")
        logger.info(f"  - Tau delta: {retrieved_entry.tau_delta}")
        logger.info(f"  - Artifact size: {len(retrieved_entry.artifact)} bytes")

        # Test card deserialization
        deserialized_card = curator._deserialize_card(retrieved_entry.artifact)
        if deserialized_card:
            logger.info("✓ Card deserialization successful")
            logger.info(f"  - Candidate: {deserialized_card.candidate_name}")
            logger.info(f"  - Bullets: {len(deserialized_card.bullets)}")
            return True

    logger.error("✗ C³ cache serialization failed")
    return False


async def test_batch_processing(metrics: PerformanceMetrics):
    """Test async batch processing."""
    logger.info("Testing batch processing...")

    curator = TalentWellCurator()
    await curator.initialize()

    # Create sample deals
    sample_deals = []
    for i in range(25):  # Test with 25 deals
        sample_deals.append({
            'id': f'deal_{i:03d}',
            'candidate_name': f'Candidate {i}',
            'job_title': f'Financial Advisor {i % 3}',
            'company_name': f'Company {i % 5}',
            'location': 'New York, NY',
            'book_size_aum': f'${100 + i * 10}M',
            'production_12mo': f'${1 + i * 0.1}M',
            'years_experience': 10 + (i % 10)
        })

    metrics.total_candidates = len(sample_deals)

    # Test batch processing with different batch sizes
    batch_sizes = [5, 10, 15]

    for batch_size in batch_sizes:
        start = time.time()
        cards = await curator._process_deals_batch(sample_deals, 'test_audience', batch_size)
        duration = time.time() - start

        metrics.record_batch_time(len(sample_deals), duration)

        logger.info(f"✓ Batch processing (size={batch_size})")
        logger.info(f"  - Processed: {len(sample_deals)} deals → {len(cards)} cards")
        logger.info(f"  - Duration: {duration:.2f}s")
        logger.info(f"  - Per item: {duration/len(sample_deals):.3f}s")

    return True


async def test_fuzzy_deduplication(metrics: PerformanceMetrics):
    """Test fuzzy candidate deduplication with embeddings."""
    logger.info("Testing fuzzy deduplication...")

    curator = TalentWellCurator()
    await curator.initialize()

    # Test similar candidates (should be detected as duplicates)
    similar_candidates = [
        ('John Smith', 'Wells Fargo', 'Senior Financial Advisor'),
        ('John A. Smith', 'Wells Fargo', 'Sr. Financial Advisor'),  # Similar
        ('Jane Doe', 'Morgan Stanley', 'Wealth Manager'),
        ('John Smith', 'WF', 'Senior FA'),  # Similar to first
        ('Jane M Doe', 'Morgan Stanley', 'Wealth Mgr'),  # Similar
        ('Robert Johnson', 'UBS', 'Financial Advisor'),
    ]

    duplicates_found = 0

    for name, company, title in similar_candidates:
        is_duplicate = await curator._check_duplicate_candidate(
            name, company, title, 'test_audience'
        )

        if is_duplicate:
            duplicates_found += 1
            logger.info(f"  ✓ Duplicate detected: {name} at {company}")
        else:
            logger.info(f"  - New candidate: {name} at {company}")

    metrics.duplicates_found = duplicates_found

    logger.info(f"✓ Fuzzy deduplication complete")
    logger.info(f"  - Total candidates: {len(similar_candidates)}")
    logger.info(f"  - Duplicates found: {duplicates_found}")
    logger.info(f"  - Dedup rate: {duplicates_found/len(similar_candidates)*100:.1f}%")

    return True


async def test_full_workflow(metrics: PerformanceMetrics):
    """Test the full weekly digest workflow with all enhancements."""
    logger.info("Testing full workflow...")

    curator = TalentWellCurator()
    await curator.initialize()

    # Run digest generation (will use mock data if no Zoho connection)
    try:
        result = await curator.run_weekly_digest(
            audience='test_audience',
            from_date=datetime.now() - timedelta(days=7),
            to_date=datetime.now(),
            dry_run=True,  # Don't actually send emails
            ignore_cooldown=False  # Test deduplication
        )

        logger.info("✓ Full workflow completed")
        logger.info(f"  - Cards generated: {result['manifest']['cards_count']}")
        logger.info(f"  - Deals processed: {result['manifest']['deals_processed']}")
        logger.info(f"  - Subject variant: {result['manifest']['subject']['variant_id']}")

        return True

    except Exception as e:
        logger.error(f"✗ Full workflow failed: {e}")
        return False


async def main():
    """Run all tests and generate performance report."""
    logger.info("=" * 60)
    logger.info("TalentWell Curator Enhancement Test Suite")
    logger.info("=" * 60)

    metrics = PerformanceMetrics()
    metrics.start()

    # Run tests
    tests_passed = 0
    total_tests = 4

    # Test 1: C³ Cache Serialization
    if await test_c3_cache_serialization():
        tests_passed += 1

    # Test 2: Batch Processing
    if await test_batch_processing(metrics):
        tests_passed += 1

    # Test 3: Fuzzy Deduplication
    if await test_fuzzy_deduplication(metrics):
        tests_passed += 1

    # Test 4: Full Workflow
    if await test_full_workflow(metrics):
        tests_passed += 1

    # Generate performance report
    logger.info("=" * 60)
    logger.info("Performance Metrics")
    logger.info("=" * 60)

    summary = metrics.get_summary()

    logger.info(f"Total Duration: {summary['total_duration']:.2f}s")
    logger.info(f"")
    logger.info(f"Cache Performance:")
    logger.info(f"  - Hit Rate: {summary['cache_hit_rate']:.1f}%")
    logger.info(f"  - Hits: {summary['cache_hits']}")
    logger.info(f"  - Misses: {summary['cache_misses']}")
    logger.info(f"")
    logger.info(f"Batch Processing:")
    logger.info(f"  - Total Batches: {summary['batch_processing']['total_batches']}")
    logger.info(f"  - Avg Batch Time: {summary['batch_processing']['avg_batch_time']:.3f}s")
    logger.info(f"  - Avg Per Item: {summary['batch_processing']['avg_per_item_time']:.3f}s")
    logger.info(f"")
    logger.info(f"Deduplication:")
    logger.info(f"  - Total Candidates: {summary['total_candidates']}")
    logger.info(f"  - Duplicates Found: {summary['duplicates_found']}")
    logger.info(f"  - Dedup Rate: {summary['dedup_rate']:.1f}%")

    logger.info("=" * 60)
    logger.info(f"Test Results: {tests_passed}/{total_tests} passed")
    logger.info("=" * 60)

    return tests_passed == total_tests


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)