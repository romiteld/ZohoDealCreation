#!/usr/bin/env python3
"""Test the refactored evidence extraction system with real financial advisor examples."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.extract.evidence import EvidenceExtractor, BulletCategory, BulletPoint
from typing import List, Dict, Any
import json


def test_financial_examples():
    """Test extraction with real examples from Brandon's email."""

    extractor = EvidenceExtractor()

    # Real examples from the HTML file
    test_cases = [
        # Test case 1: AUM metrics
        {
            "text": "Built $2.2B RIA from inception alongside founder; led portfolio design, investment modeling, and firmwide scaling initiatives",
            "expected_category": BulletCategory.FINANCIAL_METRIC,
            "should_extract": ["$2.2B", "RIA"]
        },
        # Test case 2: Client metrics (now expects performance ranking due to "top tier close rate")
        {
            "text": "Managed ~$500M in AUM across 250 HNW clients nationwide; ranked in top tier for close rate (47% vs. 35% avg)",
            "expected_category": BulletCategory.PERFORMANCE_RANKING,
            "should_extract": ["$500M", "AUM", "250", "47%"]
        },
        # Test case 3: Growth metrics
        {
            "text": "Previously grew a $43M book to $72M in 2 years at National Firm",
            "expected_category": BulletCategory.GROWTH_ACHIEVEMENT,
            "should_extract": ["$43M", "$72M", "grew"]
        },
        # Test case 4: Production metrics
        {
            "text": "20+ years in financial services; launched and led successful advisory programs within banks and credit unions, growing AUM from ~$150M to $720M and annual production to ~$5M",
            "expected_category": BulletCategory.GROWTH_ACHIEVEMENT,
            "should_extract": ["$150M", "$720M", "$5M", "production"]
        },
        # Test case 5: Rankings
        {
            "text": "Proven track record of top national performance at multiple national firms; repeatedly ranked #1–3 nationally in asset acquisition",
            "expected_category": BulletCategory.PERFORMANCE_RANKING,
            "should_extract": ["#1–3", "nationally", "ranked"]
        },
        # Test case 6: Large AUM
        {
            "text": "Personally raised $2B+ AUM through national, regional, and HNW channels",
            "expected_category": BulletCategory.FINANCIAL_METRIC,
            "should_extract": ["$2B+", "AUM"]
        },
        # Test case 7: Client relationships (now expects client metric due to "65 relationships")
        {
            "text": "15+ years in financial services with roles across advisory, asset management, and consulting; currently manages $350M AUM across 65 relationships at a private wealth division",
            "expected_category": BulletCategory.CLIENT_METRIC,
            "should_extract": ["$350M", "AUM", "65 relationships"]
        },
        # Test case 8: Licenses
        {
            "text": "Holds Series 7, 63, 65, and life insurance licenses; plans to pursue CFA and CFP",
            "expected_category": BulletCategory.LICENSES,
            "should_extract": ["Series 7", "63", "65", "CFA", "CFP"]
        },
        # Test case 9: Scaled growth
        {
            "text": "16 years in RIA leadership roles; scaled firms from $300M to $1B+ and from 1 to 7 offices with $350M AUM",
            "expected_category": BulletCategory.GROWTH_ACHIEVEMENT,
            "should_extract": ["$300M", "$1B+", "scaled"]
        },
        # Test case 10: Client metrics with retention
        {
            "text": "Former CEO and CCO; built client acquisition infrastructure generating 35+ new clients/month and 97–99% retention",
            "expected_category": BulletCategory.CLIENT_METRIC,
            "should_extract": ["35+", "clients/month", "97–99%", "retention"]
        }
    ]

    print("=" * 80)
    print("TESTING FINANCIAL ADVISOR EVIDENCE EXTRACTION")
    print("=" * 80)
    print()

    passed_tests = 0
    failed_tests = 0

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Text: {test_case['text'][:100]}...")

        # Test categorization
        category = extractor.categorize_bullet(test_case['text'])
        print(f"Expected Category: {test_case['expected_category'].value}")
        print(f"Actual Category: {category.value}")

        category_match = category == test_case['expected_category']
        print(f"✅ Category Match" if category_match else f"❌ Category Mismatch")

        # Test evidence extraction
        evidence = extractor.extract_from_transcript(test_case['text'])
        print(f"\nExtracted Evidence: {len(evidence)} items")

        if evidence:
            for e in evidence[:3]:  # Show first 3 evidence items
                print(f"  - {e.snippet[:80]}... (confidence: {e.confidence})")

        # Check if expected patterns were found
        text_lower = test_case['text'].lower()
        patterns_found = []
        patterns_missing = []

        for pattern in test_case['should_extract']:
            if pattern.lower() in text_lower:
                patterns_found.append(pattern)
            else:
                patterns_missing.append(pattern)

        print(f"\nPatterns Found: {patterns_found}")
        if patterns_missing:
            print(f"Patterns Missing: {patterns_missing}")

        # Overall test result
        test_passed = category_match and len(evidence) > 0
        if test_passed:
            print("✅ Test PASSED")
            passed_tests += 1
        else:
            print("❌ Test FAILED")
            failed_tests += 1

        print("-" * 40)

    # Test bullet generation with a complex example
    print("\n" + "=" * 80)
    print("TESTING BULLET GENERATION WITH EVIDENCE")
    print("=" * 80)

    candidate_data = {
        'job_title': 'Senior Financial Advisor',
        'location': 'Boston, MA',
        'compensation': '$200K-$250K OTE',
        'availability': '2 weeks notice',
        'mobility': 'Open to remote/hybrid',
        'licenses': 'Series 7, 66, CFA'
    }

    transcript = """
    I've managed over $500M in AUM across 250 high net worth clients. My track record includes
    growing a book from $43M to $72M in just 2 years. I consistently ranked #1-3 nationally
    in new asset acquisition. I hold Series 7 and 66 licenses, and earned my CFA charter
    after passing all three levels consecutively. My client retention rate is 97%.
    """

    bullets = extractor.generate_bullets_with_evidence(candidate_data, transcript)

    print(f"\nGenerated {len(bullets)} bullets:")
    for bullet in bullets[:10]:  # Show top 10 bullets
        print(f"\n• {bullet.text}")
        print(f"  Category: {bullet.category.value}")
        print(f"  Confidence: {bullet.confidence_score}")
        print(f"  Evidence Count: {len(bullet.evidence)}")
        if bullet.evidence:
            print(f"  Evidence Sample: {bullet.evidence[0].snippet[:60]}...")

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {len(test_cases)}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")
    print(f"Success Rate: {(passed_tests / len(test_cases) * 100):.1f}%")

    # Validate that tech patterns are removed
    print("\n" + "=" * 80)
    print("VALIDATING TECH PATTERNS REMOVED")
    print("=" * 80)

    tech_text = "Experienced in Python, Java, AWS, Docker, and Kubernetes"
    tech_category = extractor.categorize_bullet(tech_text)
    tech_evidence = extractor.extract_from_transcript(tech_text)

    print(f"Tech Text: {tech_text}")
    print(f"Category: {tech_category.value}")
    print(f"Evidence Found: {len(tech_evidence)}")

    if tech_category != BulletCategory.EXPERIENCE or len(tech_evidence) > 0:
        print("⚠️ WARNING: Tech patterns may still be active!")
    else:
        print("✅ Tech patterns successfully removed")

    return passed_tests, failed_tests


def test_pattern_extraction():
    """Test individual pattern matching."""

    extractor = EvidenceExtractor()

    print("\n" + "=" * 80)
    print("TESTING INDIVIDUAL PATTERN MATCHING")
    print("=" * 80)

    # Test AUM patterns
    aum_examples = [
        "$2.2B RIA",
        "$500M AUM",
        "manages $350M across 65 relationships",
        "$1.5B+ in client assets",
        "book size of $720M",
        "oversees $10M to $150M portfolios"
    ]

    print("\n### AUM Pattern Tests ###")
    for example in aum_examples:
        matches = []
        for pattern in extractor.financial_patterns['aum']:
            import re
            if re.search(pattern, example, re.IGNORECASE):
                matches.append(pattern[:30] + "...")
                break
        print(f"'{example}' -> {'✅ Matched' if matches else '❌ No match'}")

    # Test ranking patterns
    ranking_examples = [
        "ranked #1-3 nationally",
        "top tier close rate 47%",
        "President's Club member",
        "#2 in the nation",
        "top 5% performer",
        "Circle of Champions"
    ]

    print("\n### Ranking Pattern Tests ###")
    for example in ranking_examples:
        matches = []
        for pattern in extractor.ranking_patterns:
            import re
            if re.search(pattern, example, re.IGNORECASE):
                matches.append(pattern[:30] + "...")
                break
        print(f"'{example}' -> {'✅ Matched' if matches else '❌ No match'}")

    # Test growth patterns
    growth_examples = [
        "grew from $200M to $1B",
        "scaled from $300M to $1B+",
        "increased AUM by 300%",
        "doubled production in 2 years",
        "expanded book from $43M to $72M",
        "tripled client base"
    ]

    print("\n### Growth Pattern Tests ###")
    for example in growth_examples:
        matches = []
        for pattern in extractor.financial_patterns['growth']:
            import re
            if re.search(pattern, example, re.IGNORECASE):
                matches.append(pattern[:30] + "...")
                break
        print(f"'{example}' -> {'✅ Matched' if matches else '❌ No match'}")


if __name__ == "__main__":
    print("Financial Advisor Evidence Extraction Test Suite")
    print("=" * 80)

    # Run main tests
    passed, failed = test_financial_examples()

    # Run pattern tests
    test_pattern_extraction()

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)

    # Exit with appropriate code
    if failed == 0:
        print("✅ All tests passed successfully!")
        sys.exit(0)
    else:
        print(f"❌ {failed} tests failed. Please review and fix.")
        sys.exit(1)