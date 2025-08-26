#!/usr/bin/env python3
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

DATABASE_URL = os.getenv("DATABASE_URL")

async def create_tables():
    """Create database tables"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Create pgvector extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("✅ Created pgvector extension")
    except Exception as e:
        print(f"⚠️ pgvector extension: {e}")
    
    # Create tables
    tables = [
        """
        CREATE TABLE IF NOT EXISTS email_processing_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            internet_message_id TEXT UNIQUE,
            sender_email TEXT NOT NULL,
            reply_to_email TEXT,
            primary_email TEXT NOT NULL,
            subject TEXT,
            processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            zoho_deal_id TEXT,
            zoho_account_id TEXT,
            zoho_contact_id TEXT,
            deal_name TEXT,
            company_name TEXT,
            contact_name TEXT,
            processing_status TEXT DEFAULT 'success',
            error_message TEXT,
            raw_extracted_data JSONB,
            email_body_hash TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS email_vectors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email_id UUID REFERENCES email_processing_history(id),
            embedding vector(1536),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS company_enrichment_cache (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain TEXT UNIQUE NOT NULL,
            company_name TEXT,
            website TEXT,
            industry TEXT,
            description TEXT,
            enriched_data JSONB,
            enriched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            source TEXT DEFAULT 'firecrawl'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS zoho_record_mapping (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            record_type TEXT NOT NULL,
            zoho_id TEXT NOT NULL,
            lookup_key TEXT NOT NULL,
            lookup_value TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(record_type, lookup_key, lookup_value)
        )
        """
    ]
    
    for i, table_sql in enumerate(tables, 1):
        try:
            await conn.execute(table_sql)
            table_name = table_sql.split("IF NOT EXISTS ")[1].split("(")[0].strip()
            print(f"✅ Created table {i}/4: {table_name}")
        except Exception as e:
            print(f"❌ Failed to create table {i}: {e}")
    
    # Check tables
    tables_query = """
    SELECT tablename FROM pg_tables 
    WHERE schemaname = 'public' 
    ORDER BY tablename;
    """
    
    tables = await conn.fetch(tables_query)
    print("\nExisting tables:")
    for table in tables:
        print(f"  - {table['tablename']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(create_tables())