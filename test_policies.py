#!/usr/bin/env python3
"""
Test script for policy seeding system
"""

import os
import sys
import asyncio
import json
import requests
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent))

from dotenv import load_dotenv

# Import directly to avoid import issues
import sys
sys.path.append(str(Path(__file__).parent / "app" / "admin"))
from seed_policies_v2 import PolicySeeder

# Load environment variables
load_dotenv('.env.local')
load_dotenv()


async def test_policy_seeder():
    """Test the PolicySeeder class directly."""
    print("Testing PolicySeeder class...")
    
    seeder = PolicySeeder()
    
    try:
        # Initialize
        await seeder.initialize()
        print("✓ Initialized connections")
        
        # Seed all policies
        results = await seeder.seed_all()
        print(f"✓ Seeded policies: {results}")
        
        # Test reload from database
        reload_results = await seeder.reload_from_database()
        print(f"✓ Reloaded from database: {reload_results}")
        
        # Test policy lookups
        if seeder.redis_client and seeder.redis_client._connected:
            # Test employer lookup
            firm_type = await seeder.redis_client.client.get("policy:employers:morgan stanley")
            print(f"✓ Morgan Stanley firm type: {firm_type}")
            
            # Test city lookup
            metro = await seeder.redis_client.client.get("geo:metro:manhattan")
            print(f"✓ Manhattan metro: {metro}")
            
            # Test subject bandit
            subject = await seeder.redis_client.client.get("bandit:subjects:global:v1")
            if subject:
                subject_data = json.loads(subject)
                print(f"✓ Subject V1: {subject_data}")
            
            # Test selector prior
            tau = await seeder.redis_client.client.get("c3:tau:mobility")
            ttl_data = await seeder.redis_client.client.get("ttl:mobility")
            if tau and ttl_data:
                ttl_params = json.loads(ttl_data)
                print(f"✓ Mobility selector: tau={tau}, alpha={ttl_params['alpha']}, beta={ttl_params['beta']}")
        
        print("✓ All policy seeder tests passed!")
        
    except Exception as e:
        print(f"✗ Policy seeder test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await seeder.close()


def test_api_endpoints():
    """Test the FastAPI endpoints (requires running server)."""
    print("\nTesting API endpoints...")
    
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("✗ API_KEY not found in environment")
        return
    
    base_url = "http://localhost:8000"
    headers = {"X-API-Key": api_key}
    
    try:
        # Test policy stats
        response = requests.get(f"{base_url}/api/admin/policies/stats", headers=headers)
        if response.status_code == 200:
            stats = response.json()
            print(f"✓ Policy stats: {stats}")
        else:
            print(f"✗ Stats endpoint failed: {response.status_code}")
        
        # Test policy seeding
        seed_data = {
            "clear_existing": True,
            "seed_employers": True,
            "seed_cities": True,
            "seed_subjects": True,
            "seed_selectors": True
        }
        response = requests.post(
            f"{base_url}/api/admin/policies/seed",
            json=seed_data,
            headers=headers
        )
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Policy seeding: {result}")
        else:
            print(f"✗ Seed endpoint failed: {response.status_code} - {response.text}")
        
        # Test policy query
        query_data = {
            "policy_type": "employer",
            "key": "morgan stanley"
        }
        response = requests.post(
            f"{base_url}/api/admin/policies/query",
            json=query_data,
            headers=headers
        )
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Policy query: {result}")
        else:
            print(f"✗ Query endpoint failed: {response.status_code}")
        
        print("✓ All API endpoint tests passed!")
        
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to server at http://localhost:8000")
        print("  Start the server with: uvicorn app.main:app --reload --port 8000")
    except Exception as e:
        print(f"✗ API endpoint test failed: {e}")


def test_national_firm_detection():
    """Test national firm detection logic."""
    print("\nTesting national firm detection...")
    
    test_firms = [
        ("Morgan Stanley", True),
        ("Wells Fargo", True),
        ("LPL Financial", True),
        ("Smith & Associates", False),
        ("Local Financial Advisors", False),
        ("JP Morgan", True),
        ("Edward Jones", True),
        ("Random Investment Group", False)
    ]
    
    for firm_name, expected_national in test_firms:
        firm_lower = firm_name.lower()
        is_national = any(
            national in firm_lower 
            for national in PolicySeeder.NATIONAL_FIRMS
        )
        
        if is_national == expected_national:
            print(f"✓ {firm_name}: {'National' if is_national else 'Independent'}")
        else:
            print(f"✗ {firm_name}: Expected {'National' if expected_national else 'Independent'}, got {'National' if is_national else 'Independent'}")


def test_metro_mappings():
    """Test metro area mappings."""
    print("\nTesting metro area mappings...")
    
    test_cities = [
        ("Manhattan", "NYC Metro"),
        ("Brooklyn", "NYC Metro"),
        ("Los Angeles", "LA Metro"),
        ("Boston", "Boston Metro"),
        ("Chicago", "Chicago Metro")
    ]
    
    for city, expected_metro in test_cities:
        actual_metro = PolicySeeder.METRO_MAPPINGS.get(city.lower())
        if actual_metro == expected_metro:
            print(f"✓ {city} → {actual_metro}")
        else:
            print(f"✗ {city}: Expected {expected_metro}, got {actual_metro}")


async def main():
    """Run all tests."""
    print("Running Policy Seeding System Tests")
    print("=" * 50)
    
    # Test national firm detection
    test_national_firm_detection()
    
    # Test metro mappings
    test_metro_mappings()
    
    # Test policy seeder directly
    await test_policy_seeder()
    
    # Test API endpoints (requires server)
    test_api_endpoints()
    
    print("\n" + "=" * 50)
    print("Policy testing complete!")


if __name__ == "__main__":
    asyncio.run(main())