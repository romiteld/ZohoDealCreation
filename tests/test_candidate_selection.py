#!/usr/bin/env python3
"""
Test Brandon's deterministic candidate selection logic.
Tests Zoho query, Redis deduplication, and canonicalization.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.jobs.talentwell_curator import TalentWellCurator
from app.redis_cache_manager import get_cache_manager

# Load environment variables
load_dotenv('.env.local')

async def test_zoho_query():
    """Test querying Zoho Candidates module."""
    print("Testing Zoho Candidates query...")
    
    curator = TalentWellCurator()
    
    # Test the query with required parameters
    from_date = datetime.now() - timedelta(days=30)
    to_date = datetime.now()
    candidates = await curator._query_deals(
        audience="brandon@emailthewell.com",
        from_date=from_date,
        to_date=to_date,
        owner="Steve Perry"
    )
    
    print(f"✓ Fetched {len(candidates)} candidates from Zoho")
    
    if candidates:
        # Check first candidate has expected fields
        first = candidates[0]
        required_fields = [
            'id', 'Candidate_Name', 'Current_Job_Title', 
            'Current_Firm', 'Current_Location', 'Date_Published_to_Vault'
        ]
        
        for field in required_fields:
            if field in first:
                print(f"  ✓ Field '{field}' present")
            else:
                print(f"  ✗ Field '{field}' missing")
        
        # Verify sorting
        dates = [c.get('Date_Published_to_Vault') for c in candidates[:5]]
        print(f"  First 5 dates: {dates}")
        
        if all(dates[i] <= dates[i+1] for i in range(len(dates)-1) if dates[i] and dates[i+1]):
            print("  ✓ Correctly sorted by Date_Published_to_Vault ascending")
        else:
            print("  ✗ Not properly sorted")
    
    return len(candidates) > 0

async def test_redis_deduplication():
    """Test Redis-based deduplication for last 4 weeks."""
    print("\nTesting Redis deduplication...")
    
    curator = TalentWellCurator()
    cache_mgr = await get_cache_manager()
    
    if not cache_mgr or not cache_mgr.client:
        print("✗ Redis not available for testing")
        return False
    
    # Create test candidates
    test_candidates = [
        {"id": "1001", "Candidate_Name": "Test Person 1"},
        {"id": "1002", "Candidate_Name": "Test Person 2"},
        {"id": "1003", "Candidate_Name": "Test Person 3"},
    ]
    
    # Add some to processed sets for different weeks
    current_week = datetime.now().strftime("%Y-%U")
    last_week = (datetime.now() - timedelta(weeks=1)).strftime("%Y-%U")
    old_week = (datetime.now() - timedelta(weeks=5)).strftime("%Y-%U")
    
    # Mark candidates as processed
    await cache_mgr.client.sadd(f"talentwell:processed:{current_week}", "1001")
    await cache_mgr.client.sadd(f"talentwell:processed:{last_week}", "1002")
    await cache_mgr.client.sadd(f"talentwell:processed:{old_week}", "1003")
    
    # Test filtering
    filtered = await curator._filter_processed_deals(test_candidates)
    
    print(f"  Original candidates: {len(test_candidates)}")
    print(f"  After filtering: {len(filtered)}")
    print(f"  Filtered IDs: {[c['id'] for c in filtered]}")
    
    # Should filter out 1001 and 1002 (within 4 weeks) but keep 1003 (older)
    if len(filtered) == 1 and filtered[0]['id'] == '1003':
        print("  ✓ Correctly filtered last 4 weeks")
        success = True
    else:
        print("  ✗ Filtering logic incorrect")
        success = False
    
    # Cleanup test data
    await cache_mgr.client.delete(f"talentwell:processed:{current_week}")
    await cache_mgr.client.delete(f"talentwell:processed:{last_week}")
    await cache_mgr.client.delete(f"talentwell:processed:{old_week}")
    
    return success

async def test_location_normalization():
    """Test city to metro area normalization."""
    print("\nTesting location normalization...")
    
    curator = TalentWellCurator()
    
    test_cases = [
        ("New York, NY", "New York Metro, NY"),
        ("Brooklyn, NY", "New York Metro, NY"),
        ("San Francisco, CA", "San Francisco Bay Area, CA"),
        ("Gulf Breeze, FL", "Gulf Breeze (Pensacola area), FL"),
        ("Chicago, IL", "Chicago Metro, IL"),
        ("Random City, TX", "Random City, TX"),  # No mapping
    ]
    
    all_passed = True
    for input_loc, expected in test_cases:
        result = await curator._normalize_location(input_loc)
        if result == expected:
            print(f"  ✓ '{input_loc}' → '{result}'")
        else:
            print(f"  ✗ '{input_loc}' → '{result}' (expected '{expected}')")
            all_passed = False
    
    return all_passed

async def test_mobility_line_generation():
    """Test mobility line generation from CRM fields."""
    print("\nTesting mobility line generation...")
    
    curator = TalentWellCurator()
    
    test_cases = [
        # (is_mobile, remote_pref, hybrid_pref, expected)
        (True, True, True, "(Is mobile; Open to Remote or Hybrid)"),
        (False, True, False, "(Is not mobile; Open to Remote)"),
        (False, False, True, "(Is not mobile; Open to Hybrid)"),
        (False, False, False, "(Is not mobile)"),
        (True, False, False, "(Is mobile)"),
    ]
    
    all_passed = True
    for is_mobile, remote, hybrid, expected in test_cases:
        result = curator._build_mobility_line(is_mobile, remote, hybrid)
        if result == expected:
            print(f"  ✓ Mobile={is_mobile}, Remote={remote}, Hybrid={hybrid}")
            print(f"    → '{result}'")
        else:
            print(f"  ✗ Mobile={is_mobile}, Remote={remote}, Hybrid={hybrid}")
            print(f"    → '{result}' (expected '{expected}')")
            all_passed = False
    
    return all_passed

async def test_hard_skill_bullet_generation():
    """Test generation of hard-skill bullets."""
    print("\nTesting hard-skill bullet generation...")
    
    curator = TalentWellCurator()
    
    # Test with sample candidate data
    candidate = {
        "Professional_Designations": "CFP, CFA",
        "Book_Size_AUM": "$250M",
        "Production_12mo": "$2.5M",
        "When_Available": "Q1 2025",
        "Desired_Comp": "$500K base + commission",
        "Current_Job_Title": "Senior Wealth Advisor",
        "Current_Firm": "Morgan Stanley",
    }
    
    # Test with transcript evidence
    transcript = """
    Brandon: Tell me about your experience.
    Candidate: I manage a $250M book with focus on UHNW clients.
    I've been doing comprehensive financial planning for 15 years.
    Brandon: What certifications do you have?
    Candidate: I have my CFP and CFA designations.
    """
    
    # _generate_hard_skill_bullets takes deal, enhanced_data, and transcript
    enhanced_data = {}  # Empty enhanced data for test
    bullets = await curator._generate_hard_skill_bullets(candidate, enhanced_data, transcript)
    
    print(f"  Generated {len(bullets)} bullets:")
    for bullet in bullets:
        print(f"    • {bullet}")
    
    # Check requirements
    if 2 <= len(bullets) <= 5:
        print(f"  ✓ Bullet count in range (2-5)")
    else:
        print(f"  ✗ Bullet count out of range: {len(bullets)}")
    
    # Check for soft skills (should not be present)
    soft_skills = ['passionate', 'dedicated', 'motivated', 'team player']
    has_soft = any(skill in ' '.join(bullets).lower() for skill in soft_skills)
    
    if not has_soft:
        print(f"  ✓ No soft skills detected")
    else:
        print(f"  ✗ Soft skills found in bullets")
    
    return 2 <= len(bullets) <= 5 and not has_soft

async def test_full_selection_flow():
    """Test the complete selection flow end-to-end."""
    print("\nTesting full selection flow...")
    
    curator = TalentWellCurator()
    
    # Run the weekly digest (limited to 3 for testing)
    from_date = datetime.now() - timedelta(days=7)
    to_date = datetime.now()
    result = await curator.run_weekly_digest(
        audience="brandon@emailthewell.com",
        from_date=from_date,
        to_date=to_date,
        owner="Steve Perry",
        max_candidates=3
    )
    
    selected = result.get('candidates', []) if result else []
    print(f"  Selected {len(selected)} candidates")
    
    if selected:
        # Check first candidate structure
        first = selected[0]
        
        required_keys = [
            'name', 'location', 'hard_skills', 
            'availability', 'compensation', 'ref_code'
        ]
        
        for key in required_keys:
            if key in first:
                print(f"    ✓ Has '{key}'")
            else:
                print(f"    ✗ Missing '{key}'")
        
        # Check ref_code format
        if first.get('ref_code', '').startswith('REF-'):
            print(f"    ✓ Ref code format correct: {first['ref_code']}")
        else:
            print(f"    ✗ Invalid ref code: {first.get('ref_code')}")
    
    return len(selected) > 0

async def main():
    """Run all tests."""
    print("=" * 60)
    print("CANDIDATE SELECTION TEST SUITE")
    print("=" * 60)
    
    # Check environment
    print("\nEnvironment Check:")
    print(f"  ZOHO_OAUTH_SERVICE_URL: {'✓' if os.getenv('ZOHO_OAUTH_SERVICE_URL') else '✗'}")
    print(f"  AZURE_REDIS_CONNECTION_STRING: {'✓' if os.getenv('AZURE_REDIS_CONNECTION_STRING') else '✗'}")
    
    # Run tests
    tests = [
        test_location_normalization,
        test_mobility_line_generation,
        test_hard_skill_bullet_generation,
        test_redis_deduplication,
        test_zoho_query,
        test_full_selection_flow,
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed!")
    else:
        print(f"✗ {total - passed} test(s) failed")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)