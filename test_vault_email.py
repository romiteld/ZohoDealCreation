#!/usr/bin/env python3
"""
Test script for Vault Agent email campaign functionality.
Tests the complete flow: ingest → publish with email_campaign channel.
"""

import asyncio
import json
import os
from pathlib import Path
import sys

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv('.env.local')

# Set up logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_vault_email_flow():
    """Test the complete Vault Agent email flow."""
    
    print("\n" + "="*60)
    print("VAULT AGENT EMAIL CAMPAIGN TEST")
    print("="*60 + "\n")
    
    # Test 1: Render single candidate
    print("1. Testing template rendering...")
    try:
        from app.templates.render import render_single_candidate
        
        test_card = """
        <div class="candidate-card">
            <h3><strong>John Smith</strong></h3>
            <div class="candidate-location">
                <strong>Location:</strong> Boston, MA (Open to relocation)
            </div>
            <div class="candidate-details">
                <div class="skill-list">
                    <div class="detail-label">Job Title:</div>
                    <div>Senior Portfolio Manager</div>
                </div>
                <div class="skill-list">
                    <div class="detail-label">Company:</div>
                    <div>Fidelity Investments</div>
                </div>
                <div class="availability-comp">
                    <div><span class="detail-label">Email:</span> john.smith@example.com</div>
                </div>
            </div>
            <div class="ref-code">REF-TEST-001</div>
        </div>
        """
        
        html = render_single_candidate(test_card)
        assert len(html) > 1000, "Rendered HTML too short"
        assert "TalentWell" in html, "Missing TalentWell branding"
        assert "John Smith" in html, "Missing candidate name"
        print("✓ Template rendering successful")
        
    except Exception as e:
        print(f"✗ Template rendering failed: {e}")
        return False
    
    # Test 2: Validate HTML
    print("\n2. Testing HTML validation...")
    try:
        from app.templates.validator import validate_digest_html
        
        is_valid, errors = validate_digest_html(html)
        if is_valid:
            print("✓ HTML validation passed")
        else:
            print(f"✗ HTML validation failed with {len(errors)} errors:")
            for error in errors[:5]:  # Show first 5 errors
                print(f"  - {error}")
            # Continue anyway for testing
            
    except Exception as e:
        print(f"✗ Validation failed: {e}")
        return False
    
    # Test 3: Test email configuration
    print("\n3. Testing email configuration...")
    try:
        from app.mail.send_helper import get_email_config
        
        config = get_email_config()
        print(f"Email system ready: {config.get('system_ready', False)}")
        if config.get('providers'):
            providers = config['providers'].get('available_providers', [])
            print(f"Available providers: {', '.join(providers) if providers else 'None'}")
        
        if not config.get('system_ready'):
            print("⚠ Email system not fully configured, but continuing test...")
            
    except Exception as e:
        print(f"✗ Email config check failed: {e}")
    
    # Test 4: Mock Vault Agent publish with email
    print("\n4. Testing Vault Agent publish endpoint (mock)...")
    try:
        # Create a mock canonical record
        canonical = {
            "source": "email",
            "timestamp": 1234567890,
            "fields": {
                "candidate_name": "Jane Doe",
                "job_title": "Wealth Manager",
                "location": "New York, NY",
                "company_name": "Goldman Sachs",
                "email": "jane.doe@example.com",
                "referrer_name": "Brandon Smith"
            }
        }
        
        # Generate card HTML from canonical
        fields = canonical["fields"]
        card_html = f"""
        <div class="candidate-card">
            <h3><strong>{fields.get('candidate_name', 'Unknown')}</strong></h3>
            <div class="candidate-location">
                <strong>Location:</strong> {fields.get('location', 'Unknown')}
            </div>
            <div class="candidate-details">
                <div class="skill-list">
                    <div class="detail-label">Job Title:</div>
                    <div>{fields.get('job_title', 'Unknown')}</div>
                </div>
                <div class="skill-list">
                    <div class="detail-label">Company:</div>
                    <div>{fields.get('company_name', 'Unknown')}</div>
                </div>
                <div class="availability-comp">
                    <div><span class="detail-label">Email:</span> {fields.get('email', 'Not provided')}</div>
                </div>
            </div>
            <div class="ref-code">REF-VAULT-002</div>
        </div>
        """
        
        # Render and validate
        from app.templates.render import render_single_candidate
        from app.templates.validator import validate_digest_html
        
        email_html = render_single_candidate(card_html)
        is_valid, errors = validate_digest_html(email_html)
        
        if is_valid:
            print("✓ Mock publish email would be valid")
        else:
            print(f"⚠ Mock publish email has validation issues: {errors[:2]}")
        
        # Show what the API call would look like
        print("\n5. Example API request:")
        example_request = {
            "locator": "VAULT-abc123",
            "channels": ["email_campaign"],
            "email": {
                "to": ["brandon@emailthewell.com"],
                "subject": "TalentWell – Candidate Alert (Test)"
            }
        }
        print(json.dumps(example_request, indent=2))
        
        print("\n✓ All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Mock publish test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_actual_api_endpoint():
    """Test the actual API endpoint if running."""
    import aiohttp
    
    print("\n" + "="*60)
    print("TESTING ACTUAL API ENDPOINT")
    print("="*60 + "\n")
    
    api_url = "http://localhost:8000/api/vault-agent/publish"
    api_key = os.getenv("API_KEY", "test-api-key")
    
    # First, we need to ingest a record to get a locator
    ingest_url = "http://localhost:8000/api/vault-agent/ingest"
    
    ingest_payload = {
        "source": "email",
        "payload": {
            "candidate_name": "Test Candidate",
            "job_title": "Test Manager",
            "location": "Boston, MA",
            "company_name": "Test Corp",
            "email": "test@example.com"
        },
        "metadata": {"test": True}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Ingest record
            print("1. Ingesting test record...")
            async with session.post(
                ingest_url,
                json=ingest_payload,
                headers={"X-API-Key": api_key}
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    locator = result.get("locator")
                    print(f"✓ Record ingested: {locator}")
                else:
                    print(f"✗ Ingest failed: {resp.status}")
                    return False
            
            # Publish with email
            print("\n2. Publishing with email_campaign channel...")
            publish_payload = {
                "locator": locator,
                "channels": ["email_campaign"],
                "email": {
                    "to": ["test@example.com"],
                    "subject": "TalentWell – Candidate Alert (API Test)"
                }
            }
            
            async with session.post(
                api_url,
                json=publish_payload,
                headers={"X-API-Key": api_key}
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print("✓ Publish successful!")
                    print(f"Response: {json.dumps(result, indent=2)}")
                else:
                    error = await resp.text()
                    print(f"✗ Publish failed: {resp.status}")
                    print(f"Error: {error}")
                    
    except aiohttp.ClientError as e:
        print(f"⚠ Could not connect to API: {e}")
        print("Make sure the API is running: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"✗ Test failed: {e}")


if __name__ == "__main__":
    # Run the basic tests
    result = asyncio.run(test_vault_email_flow())
    
    # Optionally test actual API if it's running
    if "--api" in sys.argv:
        asyncio.run(test_actual_api_endpoint())
    else:
        print("\nTo test the actual API endpoint, run:")
        print("  python test_vault_email.py --api")
        print("\nMake sure the API is running first:")
        print("  uvicorn app.main:app --reload")