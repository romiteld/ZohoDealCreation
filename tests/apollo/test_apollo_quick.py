#!/usr/bin/env python3
"""Quick test of Apollo deep enrichment with proper env loading"""

import asyncio
from dotenv import load_dotenv
import os
import sys

# Load environment variables
load_dotenv('.env.local')

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test():
    from app.apollo_enricher import apollo_deep_enrichment

    print(f"Apollo API Key Loaded: {bool(os.getenv('APOLLO_API_KEY'))}")

    # Test with a known email
    result = await apollo_deep_enrichment(
        email="test@example.com",
        name="Test User",
        extract_all=True
    )

    print(f"\nResult: {result}")
    if result:
        print(f"Completeness: {result.get('data_completeness', 0):.1f}%")
        if result.get('person'):
            print(f"Person found: {result['person'].get('client_name', 'Unknown')}")
        if result.get('company'):
            print(f"Company found: {result['company'].get('company_name', 'Unknown')}")

if __name__ == "__main__":
    asyncio.run(test())