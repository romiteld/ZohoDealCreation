"""
Database migration script for import_exports_v2
Ensures tables have proper constraints for idempotent upserts
"""

import asyncio
import os
import logging
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.integrations import PostgreSQLClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def migrate_tables():
    """Add necessary columns and constraints for idempotent imports"""
    
    client = PostgreSQLClient()
    await client.init_pool()
    
    async with client.pool.acquire() as conn:
        try:
            # Start transaction
            async with conn.transaction():
                
                # 1. Ensure deals table has unique constraint on deal_id
                logger.info("Updating deals table...")
                await conn.execute("""
                    -- Add deal_id column if it doesn't exist
                    ALTER TABLE deals ADD COLUMN IF NOT EXISTS deal_id TEXT;
                    
                    -- Add unique constraint if it doesn't exist
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = 'deals_deal_id_key'
                        ) THEN
                            ALTER TABLE deals ADD CONSTRAINT deals_deal_id_key UNIQUE (deal_id);
                        END IF;
                    END $$;
                    
                    -- Add raw_json column if it doesn't exist
                    ALTER TABLE deals ADD COLUMN IF NOT EXISTS raw_json JSONB;
                """)
                
                # 2. Update deal_stage_history table
                logger.info("Updating deal_stage_history table...")
                await conn.execute("""
                    -- Add columns if they don't exist
                    ALTER TABLE deal_stage_history ADD COLUMN IF NOT EXISTS from_stage TEXT;
                    ALTER TABLE deal_stage_history ADD COLUMN IF NOT EXISTS to_stage TEXT;
                    ALTER TABLE deal_stage_history ADD COLUMN IF NOT EXISTS moved_at TIMESTAMP WITH TIME ZONE;
                    ALTER TABLE deal_stage_history ADD COLUMN IF NOT EXISTS modified_by TEXT;
                    ALTER TABLE deal_stage_history ADD COLUMN IF NOT EXISTS duration_days INTEGER;
                    
                    -- Add unique constraint for idempotent upserts
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = 'deal_stage_history_unique_stage_change'
                        ) THEN
                            ALTER TABLE deal_stage_history 
                            ADD CONSTRAINT deal_stage_history_unique_stage_change 
                            UNIQUE (deal_id, to_stage, moved_at);
                        END IF;
                    END $$;
                """)
                
                # 3. Update meetings table
                logger.info("Updating meetings table...")
                await conn.execute("""
                    -- Rename columns if needed
                    DO $$ 
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'meetings' 
                            AND column_name = 'start_datetime'
                        ) THEN
                            -- Column exists, we're good
                            NULL;
                        ELSIF EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'meetings' 
                            AND column_name = 'meeting_date'
                        ) THEN
                            -- Rename meeting_date to start_datetime
                            ALTER TABLE meetings RENAME COLUMN meeting_date TO start_datetime;
                        ELSE
                            -- Add the column
                            ALTER TABLE meetings ADD COLUMN start_datetime TIMESTAMP WITH TIME ZONE;
                        END IF;
                    END $$;
                    
                    -- Ensure title column exists
                    ALTER TABLE meetings ADD COLUMN IF NOT EXISTS title TEXT;
                    
                    -- Add unique constraint for idempotent upserts
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = 'meetings_unique_meeting'
                        ) THEN
                            ALTER TABLE meetings 
                            ADD CONSTRAINT meetings_unique_meeting 
                            UNIQUE (deal_id, title, start_datetime);
                        END IF;
                    END $$;
                """)
                
                # 4. Update deal_notes table
                logger.info("Updating deal_notes table...")
                await conn.execute("""
                    -- Add note_hash column if it doesn't exist
                    ALTER TABLE deal_notes ADD COLUMN IF NOT EXISTS note_hash TEXT;
                    
                    -- Add unique constraint for idempotent upserts
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = 'deal_notes_unique_note'
                        ) THEN
                            ALTER TABLE deal_notes 
                            ADD CONSTRAINT deal_notes_unique_note 
                            UNIQUE (deal_id, created_at, note_hash);
                        END IF;
                    END $$;
                    
                    -- Create index on note_hash for faster lookups
                    CREATE INDEX IF NOT EXISTS idx_deal_notes_hash 
                    ON deal_notes(note_hash);
                """)
                
                # 5. Add imported_at timestamps if missing
                logger.info("Adding imported_at timestamps...")
                await conn.execute("""
                    ALTER TABLE deals 
                    ADD COLUMN IF NOT EXISTS imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
                    
                    ALTER TABLE deal_stage_history 
                    ADD COLUMN IF NOT EXISTS imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
                    
                    ALTER TABLE meetings 
                    ADD COLUMN IF NOT EXISTS imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
                    
                    ALTER TABLE deal_notes 
                    ADD COLUMN IF NOT EXISTS imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
                """)
                
                # 6. Create indexes for better performance
                logger.info("Creating performance indexes...")
                await conn.execute("""
                    -- Indexes for deals
                    CREATE INDEX IF NOT EXISTS idx_deals_deal_id ON deals(deal_id);
                    CREATE INDEX IF NOT EXISTS idx_deals_imported_at ON deals(imported_at);
                    
                    -- Indexes for stage history
                    CREATE INDEX IF NOT EXISTS idx_stage_history_deal_id ON deal_stage_history(deal_id);
                    CREATE INDEX IF NOT EXISTS idx_stage_history_moved_at ON deal_stage_history(moved_at);
                    CREATE INDEX IF NOT EXISTS idx_stage_history_imported_at ON deal_stage_history(imported_at);
                    
                    -- Indexes for meetings
                    CREATE INDEX IF NOT EXISTS idx_meetings_imported_at ON meetings(imported_at);
                    
                    -- Indexes for notes
                    CREATE INDEX IF NOT EXISTS idx_notes_imported_at ON deal_notes(imported_at);
                """)
                
                logger.info("Migration completed successfully!")
                
                # Get table info for verification
                table_info = {}
                for table in ['deals', 'deal_stage_history', 'meetings', 'deal_notes']:
                    columns = await conn.fetch("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = $1
                        ORDER BY ordinal_position
                    """, table)
                    
                    constraints = await conn.fetch("""
                        SELECT conname, contype
                        FROM pg_constraint
                        WHERE conrelid = $1::regclass
                    """, table)
                    
                    table_info[table] = {
                        'columns': [dict(c) for c in columns],
                        'constraints': [dict(c) for c in constraints]
                    }
                
                return table_info
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise


async def verify_tables():
    """Verify table structure after migration"""
    client = PostgreSQLClient()
    await client.init_pool()
    
    async with client.pool.acquire() as conn:
        # Check for required unique constraints
        constraints = await conn.fetch("""
            SELECT 
                tc.table_name,
                tc.constraint_name,
                array_agg(kcu.column_name) as columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'UNIQUE'
                AND tc.table_name IN ('deals', 'deal_stage_history', 'meetings', 'deal_notes')
            GROUP BY tc.table_name, tc.constraint_name
            ORDER BY tc.table_name, tc.constraint_name
        """)
        
        print("\n=== Unique Constraints ===")
        for row in constraints:
            print(f"{row['table_name']}.{row['constraint_name']}: {row['columns']}")
        
        # Check for indexes
        indexes = await conn.fetch("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE tablename IN ('deals', 'deal_stage_history', 'meetings', 'deal_notes')
            ORDER BY tablename, indexname
        """)
        
        print("\n=== Indexes ===")
        for row in indexes:
            print(f"{row['tablename']}.{row['indexname']}")


if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv('.env.local')
    
    print("Starting database migration for import_exports_v2...")
    
    # Run migration
    loop = asyncio.get_event_loop()
    try:
        table_info = loop.run_until_complete(migrate_tables())
        print("\n✅ Migration completed successfully!")
        
        print("\n=== Verifying tables ===")
        loop.run_until_complete(verify_tables())
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)