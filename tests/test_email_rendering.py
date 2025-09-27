#!/usr/bin/env python3
"""
Test email rendering and validation for TalentWell digests.
Tests HTML generation, Brandon's format validation, and Vault Agent endpoint.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.validation.talentwell_validator import TalentWellValidator, CandidateData, DigestData

# Load environment variables
load_dotenv('.env.local')

def test_candidate_card_validation():
    """Test validation of candidate card HTML format."""
    print("Testing candidate card validation...")
    
    validator = TalentWellValidator()
    
    # Test valid card (Brandon's format)
    valid_card = """
    <div class="candidate-card">
        <h3><strong>John Smith</strong></h3>
        <div class="candidate-location">
            <strong>Location:</strong> New York, NY (Is mobile; Open to Remote)
        </div>
        <div class="candidate-details">
            <ul>
                <li>CFP and CFA designations</li>
                <li>$250M AUM book size</li>
                <li>15 years wealth management experience</li>
            </ul>
        </div>
        <div class="ref-code">Ref code: TWAV-2025-001</div>
    </div>
    """
    
    is_valid, issues = validator.validate_candidate_card(valid_card)
    print(f"  Valid card test: {'✓' if is_valid else '✗'}")
    if issues:
        print(f"  Issues found: {issues}")
    
    # Test invalid cards
    test_cases = [
        ("Missing bold name", """
        <div class="candidate-card">
            <h3>John Smith</h3>
            <div class="candidate-location"><strong>Location:</strong> NYC</div>
            <ul><li>Skill 1</li><li>Skill 2</li></ul>
            <div class="ref-code">TWAV-001</div>
        </div>
        """),
        ("Too few bullets", """
        <div class="candidate-card">
            <h3><strong>John Smith</strong></h3>
            <div class="candidate-location"><strong>Location:</strong> NYC (Is mobile)</div>
            <ul><li>Only one skill</li></ul>
            <div class="ref-code">TWAV-001</div>
        </div>
        """),
        ("Soft skills present", """
        <div class="candidate-card">
            <h3><strong>John Smith</strong></h3>
            <div class="candidate-location"><strong>Location:</strong> NYC (Is mobile)</div>
            <ul>
                <li>Passionate about wealth management</li>
                <li>Dedicated team player</li>
            </ul>
            <div class="ref-code">TWAV-001</div>
        </div>
        """),
    ]
    
    all_passed = True
    for name, html in test_cases:
        is_valid, issues = validator.validate_candidate_card(html)
        if not is_valid:
            print(f"  ✓ Correctly flagged: {name}")
        else:
            print(f"  ✗ Should have failed: {name}")
            all_passed = False
    
    return all_passed

def test_digest_data_validation():
    """Test validation of complete digest data."""
    print("\nTesting digest data validation...")
    
    validator = TalentWellValidator()
    
    # Test valid digest
    valid_digest = {
        "subject": "TalentWell Weekly Digest - Q1 2025",
        "intro_block": "This week's top candidates for your review.",
        "candidates": [
            {
                "name": "John Smith",
                "location": "New York, NY",
                "hard_skills": ["CFP", "CFA", "$250M AUM"],
                "availability": "Q1 2025",
                "compensation": "$500K+",
                "ref_code": "TWAV-001"
            },
            {
                "name": "Jane Doe",
                "location": "San Francisco, CA",
                "hard_skills": ["Series 7", "Series 66", "FINRA registered"],
                "availability": "Immediate",
                "compensation": "$400K base",
                "ref_code": "TWAV-002"
            }
        ],
        "recipient_email": "brandon@emailthewell.com"
    }
    
    is_valid, errors, validated = validator.validate_digest_data(valid_digest)
    
    if is_valid:
        print(f"  ✓ Valid digest accepted")
        print(f"    Candidate count: {len(validated.candidates)}")
    else:
        print(f"  ✗ Valid digest rejected: {errors}")
    
    # Test invalid cases
    invalid_cases = [
        ("Missing subject", {
            "intro_block": "Test",
            "candidates": [{"name": "Test", "location": "NYC", "availability": "Now", "compensation": "$100K"}]
        }),
        ("No candidates", {
            "subject": "Test",
            "intro_block": "Test",
            "candidates": []
        }),
        ("Too many candidates", {
            "subject": "Test",
            "intro_block": "Test",
            "candidates": [{"name": f"Person {i}", "location": "NYC", "availability": "Now", "compensation": "$100K"} for i in range(11)]
        }),
    ]
    
    all_passed = is_valid
    for name, data in invalid_cases:
        is_valid, errors, _ = validator.validate_digest_data(data)
        if not is_valid:
            print(f"  ✓ Correctly rejected: {name}")
        else:
            print(f"  ✗ Should have rejected: {name}")
            all_passed = False
    
    return all_passed

def test_html_rendering():
    """Test HTML template rendering."""
    print("\nTesting HTML rendering...")
    
    validator = TalentWellValidator()
    
    # Check template exists
    if not validator.template_path.exists():
        print(f"  ✗ Template not found: {validator.template_path}")
        return False
    
    print(f"  ✓ Template found: {validator.template_path}")
    
    # Create test digest
    digest = DigestData(
        subject="Test Digest",
        intro_block="Testing HTML rendering with Brandon's format.",
        candidates=[
            CandidateData(
                name="Test Candidate",
                location="Gulf Breeze, FL",
                hard_skills=["CFP", "Series 7", "$150M AUM"],
                availability="Q2 2025",
                compensation="$350K",
                ref_code="TWAV-TEST-001"
            )
        ],
        recipient_email="test@emailthewell.com"
    )
    
    try:
        html = validator.render_digest(digest)
        print(f"  ✓ Rendered HTML: {len(html)} bytes")
        
        # Check for key elements
        checks = [
            ("Subject in HTML", digest.subject in html),
            ("Intro block in HTML", digest.intro_block in html),
            ("Candidate name in HTML", "Test Candidate" in html),
            ("Location in HTML", "Gulf Breeze" in html),
            ("Ref code in HTML", "TWAV-TEST-001" in html),
        ]
        
        all_good = True
        for check_name, result in checks:
            if result:
                print(f"    ✓ {check_name}")
            else:
                print(f"    ✗ {check_name}")
                all_good = False
        
        return all_good
        
    except Exception as e:
        print(f"  ✗ Rendering failed: {e}")
        return False

def test_rendered_html_validation():
    """Test validation of final rendered HTML."""
    print("\nTesting rendered HTML validation...")
    
    validator = TalentWellValidator()
    
    # Test valid HTML
    valid_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TalentWell Digest</title>
        <style>body { font-family: Arial; }</style>
    </head>
    <body>
        <h1>Weekly Digest</h1>
        <div class="content">Content here</div>
    </body>
    </html>
    """
    
    is_valid, errors = validator.validate_rendered_html(valid_html)
    if is_valid:
        print(f"  ✓ Valid HTML accepted")
    else:
        print(f"  ✗ Valid HTML rejected: {errors}")
    
    # Test HTML with issues
    invalid_cases = [
        ("Unreplaced variables", "<html><body>Hello {{name}}</body></html>"),
        ("Missing title", "<html><body>Content</body></html>"),
        ("Missing body", "<html><title>Test</title></html>"),
    ]
    
    all_passed = is_valid
    for name, html in invalid_cases:
        is_valid, errors = validator.validate_rendered_html(html)
        if not is_valid:
            print(f"  ✓ Correctly flagged: {name}")
        else:
            print(f"  ✗ Should have flagged: {name}")
            all_passed = False
    
    return all_passed

async def test_vault_agent_endpoint():
    """Test Vault Agent /publish endpoint for email_campaign."""
    print("\nTesting Vault Agent endpoint...")
    
    # Skip if not running locally
    api_url = os.getenv("API_URL", "http://localhost:8000")
    api_key = os.getenv("API_KEY")
    
    if not api_key:
        print("  ⚠ API_KEY not set, skipping endpoint test")
        return True
    
    async with httpx.AsyncClient() as client:
        # First, ingest a test record
        ingest_payload = {
            "source": "email",
            "payload": {
                "candidate_name": "API Test Candidate",
                "job_title": "Senior Wealth Advisor",
                "location": "Miami, FL",
                "company_name": "Test Firm LLC",
                "referrer_name": "Brandon Test",
                "email": "test@example.com",
                "is_mobile": True,
                "remote_preference": True,
                "hybrid_preference": False,
                "professional_designations": "CFP, ChFC",
                "book_size_aum": "$300M",
                "production_12mo": "$3M",
                "when_available": "Q2 2025",
                "desired_comp": "$450K base"
            },
            "metadata": {"test": True}
        }
        
        try:
            # Ingest
            response = await client.post(
                f"{api_url}/api/vault-agent/ingest",
                json=ingest_payload,
                headers={"X-API-Key": api_key}
            )
            
            if response.status_code != 200:
                print(f"  ✗ Ingest failed: {response.status_code}")
                return False
            
            ingest_result = response.json()
            locator = ingest_result.get("locator")
            print(f"  ✓ Ingested record: {locator}")
            
            # Publish to email_campaign
            publish_payload = {
                "locator": locator,
                "channels": ["email_campaign"],
                "email": {
                    "to": ["test@emailthewell.com"],
                    "subject": "Test - Single Candidate Alert"
                }
            }
            
            response = await client.post(
                f"{api_url}/api/vault-agent/publish",
                json=publish_payload,
                headers={"X-API-Key": api_key}
            )
            
            if response.status_code != 200:
                print(f"  ✗ Publish failed: {response.status_code}")
                print(f"    Response: {response.text}")
                return False
            
            result = response.json()
            email_result = result.get("results", {}).get("email_campaign", {})
            
            print(f"  ✓ Published to email_campaign")
            print(f"    Success: {email_result.get('success')}")
            print(f"    Provider: {email_result.get('provider')}")
            print(f"    Recipients: {email_result.get('recipients')}")
            
            return email_result.get("success", False)
            
        except Exception as e:
            print(f"  ✗ API test failed: {e}")
            return False

async def main():
    """Run all tests."""
    print("=" * 60)
    print("EMAIL RENDERING TEST SUITE")
    print("=" * 60)
    
    # Synchronous tests
    sync_tests = [
        test_candidate_card_validation,
        test_digest_data_validation,
        test_html_rendering,
        test_rendered_html_validation,
    ]
    
    results = []
    for test in sync_tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Async test
    try:
        result = await test_vault_agent_endpoint()
        results.append(result)
    except Exception as e:
        print(f"✗ Async test failed: {e}")
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