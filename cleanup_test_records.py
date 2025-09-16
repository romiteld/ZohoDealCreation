#!/usr/bin/env python3
"""
Script to identify and clean up test records from production Zoho CRM.
This addresses Brandon's request to "stop testing shit in production and clean up your test records."
"""

import asyncio
import os
import sys
import httpx
from datetime import datetime
from typing import List, Dict, Any
import json

# Load environment variables
from dotenv import load_dotenv
load_dotenv('.env.local')

class ZohoTestRecordCleaner:
    def __init__(self):
        self.api_base = "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
        self.api_key = os.getenv('API_KEY')
        self.headers = {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }

        # Known test records from our testing
        self.known_test_records = {
            'kevin_sullivan': {
                'contact_id': '6221978000100019021',
                'company_id': '6221978000100700056',
                'deal_id': '6221978000101417224',
                'deal_name': 'Senior Financial Advisor (Fort Wayne) - Well Partners Recruiting'
            }
        }

        # Test patterns to identify other test records
        self.test_patterns = [
            'test',
            'sample',
            'demo',
            'kevin sullivan',
            'well partners recruiting',
            'referrer@wellpartners.com',
            'test@',
            'example@',
            'sample@',
            'demo@'
        ]

    async def identify_test_records(self) -> Dict[str, List[Dict]]:
        """Identify potential test records in Zoho CRM."""
        print("🔍 Identifying test records in production Zoho CRM...")

        test_records = {
            'deals': [],
            'contacts': [],
            'accounts': []
        }

        # For now, we'll focus on the known test record
        # In a production scenario, we'd query Zoho API to find records matching test patterns

        # Add the known Kevin Sullivan test record
        test_records['deals'].append({
            'id': self.known_test_records['kevin_sullivan']['deal_id'],
            'name': self.known_test_records['kevin_sullivan']['deal_name'],
            'reason': 'Known test record from Kevin Sullivan test endpoint'
        })

        test_records['contacts'].append({
            'id': self.known_test_records['kevin_sullivan']['contact_id'],
            'name': 'Kevin Sullivan',
            'reason': 'Known test contact from test endpoint'
        })

        test_records['accounts'].append({
            'id': self.known_test_records['kevin_sullivan']['company_id'],
            'name': 'Well Partners Recruiting',
            'reason': 'Known test company from test endpoint'
        })

        return test_records

    async def validate_test_record(self, record_type: str, record_id: str) -> bool:
        """Validate that a record is indeed a test record before deletion."""
        print(f"🔍 Validating {record_type} record {record_id}...")

        # For known test records, we can be confident
        if record_id in [
            self.known_test_records['kevin_sullivan']['deal_id'],
            self.known_test_records['kevin_sullivan']['contact_id'],
            self.known_test_records['kevin_sullivan']['company_id']
        ]:
            return True

        # For other records, we'd need to query Zoho API to check details
        # This is a safety measure to prevent accidental deletion of real data
        return False

    async def delete_zoho_record(self, record_type: str, record_id: str) -> bool:
        """Delete a record from Zoho CRM."""
        print(f"🗑️  Deleting {record_type} record {record_id}...")

        # Note: The current API doesn't have direct delete endpoints exposed
        # We'd need to either:
        # 1. Add delete endpoints to the API
        # 2. Use Zoho API directly with authentication
        # 3. Mark records as deleted/test in Zoho

        # For now, we'll simulate the cleanup and document what needs to be deleted
        print(f"   ⚠️  DELETE ACTION NEEDED: {record_type} ID {record_id}")
        return False

    async def cleanup_test_records(self, dry_run: bool = True) -> Dict[str, Any]:
        """Main cleanup process."""
        print(f"🧹 Starting test record cleanup (dry_run={dry_run})...")
        print(f"   📅 {datetime.now().isoformat()}")
        print()

        # Identify test records
        test_records = await self.identify_test_records()

        cleanup_summary = {
            'identified': {},
            'deleted': {},
            'errors': [],
            'dry_run': dry_run
        }

        for record_type, records in test_records.items():
            print(f"\n📋 {record_type.upper()} RECORDS TO CLEAN:")
            cleanup_summary['identified'][record_type] = len(records)
            cleanup_summary['deleted'][record_type] = 0

            for record in records:
                print(f"   • ID: {record['id']}")
                print(f"     Name: {record.get('name', 'N/A')}")
                print(f"     Reason: {record['reason']}")

                if not dry_run:
                    # Validate before deletion
                    is_valid_test = await self.validate_test_record(record_type, record['id'])
                    if is_valid_test:
                        success = await self.delete_zoho_record(record_type, record['id'])
                        if success:
                            cleanup_summary['deleted'][record_type] += 1
                        else:
                            cleanup_summary['errors'].append(f"Failed to delete {record_type} {record['id']}")
                    else:
                        cleanup_summary['errors'].append(f"Validation failed for {record_type} {record['id']}")
                else:
                    print(f"     Status: Would be deleted (dry run)")

        print(f"\n📊 CLEANUP SUMMARY:")
        print(f"   Mode: {'DRY RUN' if dry_run else 'LIVE CLEANUP'}")
        for record_type in ['deals', 'contacts', 'accounts']:
            identified = cleanup_summary['identified'].get(record_type, 0)
            deleted = cleanup_summary['deleted'].get(record_type, 0)
            print(f"   {record_type.title()}: {identified} identified, {deleted} deleted")

        if cleanup_summary['errors']:
            print(f"   Errors: {len(cleanup_summary['errors'])}")
            for error in cleanup_summary['errors']:
                print(f"     • {error}")

        return cleanup_summary

    async def manual_zoho_cleanup_instructions(self) -> str:
        """Generate manual cleanup instructions for Brandon or team."""
        instructions = """
# MANUAL ZOHO CLEANUP INSTRUCTIONS

## Overview
The following test records were identified in production Zoho CRM and need manual deletion:

## TEST RECORDS TO DELETE

### 1. Kevin Sullivan Test Record Set
- **Deal ID**: 6221978000101417224
  - Deal Name: "Senior Financial Advisor (Fort Wayne) - Well Partners Recruiting"
  - Source: Test endpoint /test/kevin-sullivan

- **Contact ID**: 6221978000100019021
  - Contact Name: "Kevin Sullivan"
  - Email: Associated with test data

- **Company ID**: 6221978000100700056
  - Company Name: "Well Partners Recruiting"
  - Source: Test company record

## DELETION STEPS

1. **Log into Zoho CRM** as admin
2. **Delete Deal First**:
   - Go to Deals module
   - Search for Deal ID: 6221978000101417224
   - Delete "Senior Financial Advisor (Fort Wayne) - Well Partners Recruiting"
3. **Delete Contact**:
   - Go to Contacts module
   - Search for Contact ID: 6221978000100019021
   - Delete "Kevin Sullivan" contact
4. **Delete Company** (if no other records reference it):
   - Go to Accounts module
   - Search for Account ID: 6221978000100700056
   - Delete "Well Partners Recruiting" if no other contacts/deals reference it

## VERIFICATION
After deletion, test the endpoint:
```
GET /test/kevin-sullivan
```
Should return "no existing record" or create fresh test data.

## PREVENTION
- Use separate Zoho sandbox/development instance for testing
- Implement test record flagging in production
- Add cleanup automation to test workflows
"""
        return instructions

async def main():
    """Main execution function."""
    print("🔧 Well Intake API - Test Record Cleanup Tool")
    print("=" * 50)

    cleaner = ZohoTestRecordCleaner()

    # Run dry run first to see what would be cleaned
    print("PHASE 1: DRY RUN ANALYSIS")
    print("-" * 30)
    dry_run_results = await cleaner.cleanup_test_records(dry_run=True)

    print("\n" + "=" * 50)
    print("PHASE 2: MANUAL CLEANUP INSTRUCTIONS")
    print("-" * 30)

    instructions = await cleaner.manual_zoho_cleanup_instructions()
    print(instructions)

    # Save instructions to file
    with open('/tmp/zoho_cleanup_instructions.md', 'w') as f:
        f.write(instructions)

    print(f"\n📄 Instructions saved to: /tmp/zoho_cleanup_instructions.md")
    print("\n✅ Cleanup analysis complete!")
    print("\n🚨 ACTION REQUIRED: Manual deletion needed in Zoho CRM")
    print("   See instructions above or in /tmp/zoho_cleanup_instructions.md")

if __name__ == "__main__":
    asyncio.run(main())