#!/usr/bin/env python3
"""
Check database records to verify email processing is being stored.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import json
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
load_dotenv('.env.local')

from app.integrations import PostgreSQLClient

async def check_database():
    """Check database for recent records."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    try:
        # Initialize PostgreSQL client
        postgres_client = PostgreSQLClient(database_url)
        await postgres_client.init_pool()
        
        async with postgres_client.pool.acquire() as conn:
            print("📊 Recent Email Processing Records:\n")
            
            # Check email_processing_history
            records = await conn.fetch(
                """
                SELECT id, sender_email, subject, deal_name, zoho_deal_id, processed_at
                FROM email_processing_history
                ORDER BY processed_at DESC
                LIMIT 5
                """
            )
            
            if records:
                for record in records:
                    print(f"📧 Email from: {record['sender_email']}")
                    print(f"   Subject: {record['subject']}")
                    print(f"   Deal: {record['deal_name']}")
                    print(f"   Zoho ID: {record['zoho_deal_id']}")
                    print(f"   Processed: {record['processed_at']}")
                    print()
            else:
                print("   No email processing records found")
            
            # Check batch processing status
            print("\n📦 Recent Batch Processing:\n")
            batches = await conn.fetch(
                """
                SELECT batch_id, status, total_emails, processed_emails, created_at
                FROM batch_processing_status
                ORDER BY created_at DESC
                LIMIT 3
                """
            )
            
            if batches:
                for batch in batches:
                    print(f"   Batch: {batch['batch_id']}")
                    print(f"   Status: {batch['status']}")
                    print(f"   Emails: {batch['processed_emails']}/{batch['total_emails']}")
                    print(f"   Created: {batch['created_at']}")
                    print()
            else:
                print("   No batch processing records found")
            
            # Check zoho_record_mapping for deduplication
            print("\n🔗 Recent Zoho Mappings:\n")
            mappings = await conn.fetch(
                """
                SELECT record_type, zoho_id, lookup_value, created_at
                FROM zoho_record_mapping
                ORDER BY created_at DESC
                LIMIT 5
                """
            )
            
            if mappings:
                for mapping in mappings:
                    print(f"   Type: {mapping['record_type']}")
                    print(f"   Zoho ID: {mapping['zoho_id']}")
                    print(f"   Lookup: {mapping['lookup_value']}")
                    print(f"   Created: {mapping['created_at']}")
                    print()
            else:
                print("   No Zoho mapping records found")
                
            # Count total records
            email_count = await conn.fetchval("SELECT COUNT(*) FROM email_processing_history")
            zoho_count = await conn.fetchval("SELECT COUNT(*) FROM zoho_record_mapping")
            
            print("\n📈 Database Statistics:")
            print(f"   Total emails processed: {email_count}")
            print(f"   Total Zoho mappings: {zoho_count}")
        
        await postgres_client.pool.close()
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_database())