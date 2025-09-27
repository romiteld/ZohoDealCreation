#!/usr/bin/env python3
"""
Database Initialization Script
Sets up all required tables for the Well Intake API including:
- Email processing history
- AI correction learning
- Learning patterns
- pgvector extensions for embeddings
"""

import os
import asyncio
import asyncpg
from typing import Optional
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseInitializer:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
    
    async def create_tables(self):
        """Create all required database tables"""
        conn = await asyncpg.connect(self.database_url)
        
        try:
            # Create pgvector extension (may require superuser)
            logger.info("Creating pgvector extension...")
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                logger.info("✓ pgvector extension created/verified")
            except asyncpg.exceptions.InsufficientPrivilegeError:
                logger.warning("⚠ Cannot create pgvector extension (requires superuser). Continuing without vector support...")
            
            # Create correction learning table
            logger.info("Creating ai_corrections table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_corrections (
                    id SERIAL PRIMARY KEY,
                    email_domain VARCHAR(255),
                    email_snippet TEXT,
                    original_extraction JSONB,
                    user_corrections JSONB,
                    correction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    applied_count INT DEFAULT 0,
                    success_rate FLOAT DEFAULT 0.0
                );
            """)
            
            # Create indexes for ai_corrections
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_corrections_domain 
                ON ai_corrections(email_domain);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_corrections_timestamp 
                ON ai_corrections(correction_timestamp DESC);
            """)
            
            # Create learning patterns table
            logger.info("Creating learning_patterns table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS learning_patterns (
                    id SERIAL PRIMARY KEY,
                    pattern_type VARCHAR(100),
                    pattern_key VARCHAR(255),
                    pattern_value TEXT,
                    confidence FLOAT DEFAULT 0.5,
                    usage_count INT DEFAULT 0,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create index for learning patterns
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_learning_patterns_type_key 
                ON learning_patterns(pattern_type, pattern_key);
            """)
            
            # Create email processing history table
            logger.info("Creating email_processing_history table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS email_processing_history (
                    id SERIAL PRIMARY KEY,
                    email_hash VARCHAR(64) UNIQUE,
                    sender_email VARCHAR(255),
                    sender_domain VARCHAR(255),
                    subject TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    extraction_result JSONB,
                    zoho_deal_id VARCHAR(100),
                    zoho_account_id VARCHAR(100),
                    zoho_contact_id VARCHAR(100),
                    attachments JSONB,
                    processing_time_ms INT,
                    ai_model VARCHAR(50) DEFAULT 'gpt-4-mini',
                    success BOOLEAN DEFAULT true,
                    error_message TEXT
                );
            """)
            
            # Create indexes for email history
            try:
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_email_history_hash 
                    ON email_processing_history(email_hash);
                """)
            except Exception as e:
                logger.warning(f"Could not create email_hash index: {e}")
            
            try:
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_email_history_sender 
                    ON email_processing_history(sender_email);
                """)
            except Exception as e:
                logger.warning(f"Could not create sender_email index: {e}")
            
            try:
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_email_history_zoho_deal 
                    ON email_processing_history(zoho_deal_id);
                """)
            except Exception as e:
                logger.warning(f"Could not create zoho_deal index: {e}")
            
            # Create vector similarity index if pgvector is available
            try:
                logger.info("Creating vector similarity index...")
                # First try to add the column if pgvector exists
                await conn.execute("""
                    ALTER TABLE email_processing_history 
                    ADD COLUMN IF NOT EXISTS content_embedding vector(1536);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_email_embeddings 
                    ON email_processing_history 
                    USING ivfflat (content_embedding vector_cosine_ops)
                    WITH (lists = 100);
                """)
                logger.info("✓ Vector index created")
            except Exception as e:
                logger.warning(f"⚠ Cannot create vector index: {e}. Continuing without vector support...")
            
            # Create custom fields tracking table
            logger.info("Creating custom_fields_usage table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS custom_fields_usage (
                    id SERIAL PRIMARY KEY,
                    field_name VARCHAR(255) UNIQUE,
                    field_type VARCHAR(50),
                    usage_count INT DEFAULT 1,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    common_values JSONB DEFAULT '[]'
                );
            """)
            
            logger.info("✓ All database tables created successfully")
            
            # Check table existence
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename IN ('ai_corrections', 'learning_patterns', 
                                  'email_processing_history', 'custom_fields_usage')
                ORDER BY tablename;
            """)
            
            logger.info(f"Confirmed tables: {[t['tablename'] for t in tables]}")
            
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
        finally:
            await conn.close()
    
    async def verify_setup(self):
        """Verify database setup and show statistics"""
        conn = await asyncpg.connect(self.database_url)
        
        try:
            # Check record counts
            stats = {}
            
            tables = [
                'ai_corrections',
                'learning_patterns',
                'email_processing_history',
                'custom_fields_usage'
            ]
            
            for table in tables:
                try:
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    stats[table] = count
                except:
                    stats[table] = "Not found"
            
            logger.info("\nDatabase Statistics:")
            logger.info("=" * 40)
            for table, count in stats.items():
                logger.info(f"{table:30} : {count:>7} records")
            
            # Check pgvector extension
            ext = await conn.fetchval("""
                SELECT extversion FROM pg_extension WHERE extname = 'vector'
            """)
            
            if ext:
                logger.info(f"\npgvector version: {ext}")
            else:
                logger.warning("\npgvector extension not installed")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error verifying setup: {e}")
            return {}
        finally:
            await conn.close()
    
    async def add_sample_corrections(self):
        """Add sample correction patterns for testing"""
        conn = await asyncpg.connect(self.database_url)
        
        try:
            # Add sample correction
            await conn.execute("""
                INSERT INTO ai_corrections 
                (email_domain, email_snippet, original_extraction, user_corrections)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """,
                "example.com",
                "I'd like to refer John Doe for the position",
                '{"candidate_name": "John Doc", "job_title": "Developer"}',
                '{"candidate_name": "John Doe", "job_title": "Senior Developer"}'
            )
            
            # Add sample learning pattern
            await conn.execute("""
                INSERT INTO learning_patterns 
                (pattern_type, pattern_key, pattern_value, confidence)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """,
                "name_correction",
                "example.com",
                "Check for 'Doe' not 'Doc' spelling",
                0.85
            )
            
            logger.info("✓ Sample data added")
            
        except Exception as e:
            logger.error(f"Error adding sample data: {e}")
        finally:
            await conn.close()


async def main():
    """Main entry point"""
    print("="*60)
    print("  DATABASE INITIALIZATION")
    print("="*60)
    
    initializer = DatabaseInitializer()
    
    try:
        # Create tables
        await initializer.create_tables()
        
        # Verify setup
        stats = await initializer.verify_setup()
        
        # Optionally add sample data
        if input("\nAdd sample correction data? (y/n): ").lower() == 'y':
            await initializer.add_sample_corrections()
            await initializer.verify_setup()
        
        print("\n✅ Database initialization complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))