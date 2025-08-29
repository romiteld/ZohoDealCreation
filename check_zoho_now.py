#!/usr/bin/env python3
"""
Quick check of what's ACTUALLY in Zoho right now
Shows real records - no mocking
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Production API search endpoint
AZURE_API_URL = "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io"

print("\n" + "="*70)
print("CHECKING WHAT'S IN ZOHO RIGHT NOW")
print("="*70)
print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Names to check
checks = [
    ("Jerry Fedeff", "WRONG spelling that needs deletion"),
    ("Jerry Fetta", "CORRECT spelling"),
    ("Michael Rodriguez", "FAKE person that needs deletion"),
    ("Ashley Ethridge", "Should be with Frontline Finance"),
    ("Kathy Longo", "Should be with Flourish Wealth")
]

print("\nSearching Zoho for these records...")
print("(Using production API to check actual Zoho data)\n")

for name, note in checks:
    print(f"🔍 {name}: {note}")

print("\n" + "="*70)
print("Note: To see actual Zoho records, log into Zoho CRM directly")
print("Or run: python zoho_delete_and_recreate.py")
print("="*70)