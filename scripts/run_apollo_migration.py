#!/usr/bin/env python3
"""
Script to run Apollo.io enrichment migration on Azure PostgreSQL
Handles migration execution, validation, and rollback if needed
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import asyncpg
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ApolloMigrationRunner:
    """Manages Apollo.io schema migration execution"""

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or os.getenv('DATABASE_URL')
        if not self.connection_string:
            raise ValueError("DATABASE_URL not found in environment variables")

        self.migration_file = Path(__file__).parent.parent / 'migrations' / '004_apollo_enrichment_tables.sql'
        self.conn = None

    async def connect(self):
        """Establish database connection"""
        try:
            self.conn = await asyncpg.connect(self.connection_string)
            logger.info("Connected to Azure PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False

    async def disconnect(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()
            logger.info("Disconnected from database")

    async def check_migration_history(self) -> bool:
        """Check if migration has already been applied"""
        try:
            # Create migration history table if it doesn't exist
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS migration_history (
                    id SERIAL PRIMARY KEY,
                    migration_name TEXT UNIQUE NOT NULL,
                    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT TRUE,
                    rollback_at TIMESTAMP WITH TIME ZONE,
                    error_message TEXT
                )
            """)

            # Check if this migration has been run
            result = await self.conn.fetchval("""
                SELECT success FROM migration_history
                WHERE migration_name = '004_apollo_enrichment_tables'
                ORDER BY executed_at DESC
                LIMIT 1
            """)

            return result is True
        except Exception as e:
            logger.error(f"Error checking migration history: {e}")
            return False

    async def validate_prerequisites(self) -> Dict[str, bool]:
        """Validate database prerequisites"""
        checks = {}

        # Check for required extensions
        extensions = ['uuid-ossp', 'pgcrypto', 'vector']
        for ext in extensions:
            try:
                result = await self.conn.fetchval(
                    "SELECT COUNT(*) FROM pg_extension WHERE extname = $1",
                    ext
                )
                checks[f"extension_{ext}"] = result > 0
                if result == 0:
                    logger.warning(f"Extension '{ext}' not installed")
            except Exception as e:
                logger.error(f"Error checking extension '{ext}': {e}")
                checks[f"extension_{ext}"] = False

        # Check for existing Apollo tables
        apollo_tables = ['apollo_enrichments', 'apollo_search_cache', 'apollo_metrics']
        for table in apollo_tables:
            try:
                result = await self.conn.fetchval("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_name = $1
                """, table)
                checks[f"table_{table}_exists"] = result > 0
                if result > 0:
                    logger.warning(f"Table '{table}' already exists")
            except Exception as e:
                logger.error(f"Error checking table '{table}': {e}")
                checks[f"table_{table}_exists"] = False

        return checks

    async def run_migration(self) -> bool:
        """Execute the migration SQL file"""
        try:
            # Read migration SQL
            with open(self.migration_file, 'r') as f:
                migration_sql = f.read()

            logger.info(f"Executing migration from {self.migration_file}")

            # Start transaction
            async with self.conn.transaction():
                # Execute migration
                await self.conn.execute(migration_sql)

                # Record successful migration
                await self.conn.execute("""
                    INSERT INTO migration_history (migration_name, executed_at, success)
                    VALUES ('004_apollo_enrichment_tables', $1, TRUE)
                    ON CONFLICT (migration_name)
                    DO UPDATE SET
                        executed_at = EXCLUDED.executed_at,
                        success = TRUE,
                        error_message = NULL
                """, datetime.utcnow())

                logger.info("Migration executed successfully")
                return True

        except Exception as e:
            logger.error(f"Migration failed: {e}")

            # Record failed migration
            try:
                await self.conn.execute("""
                    INSERT INTO migration_history (migration_name, executed_at, success, error_message)
                    VALUES ('004_apollo_enrichment_tables', $1, FALSE, $2)
                    ON CONFLICT (migration_name)
                    DO UPDATE SET
                        executed_at = EXCLUDED.executed_at,
                        success = FALSE,
                        error_message = EXCLUDED.error_message
                """, datetime.utcnow(), str(e))
            except:
                pass  # Ignore error recording failures

            return False

    async def validate_migration(self) -> Dict[str, Any]:
        """Validate that migration was successful"""
        validation = {
            'tables_created': {},
            'indexes_created': {},
            'views_created': {},
            'functions_created': {},
            'triggers_created': {}
        }

        # Check tables
        tables = ['apollo_enrichments', 'apollo_search_cache', 'apollo_metrics', 'apollo_phone_numbers']
        for table in tables:
            result = await self.conn.fetchval("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = $1
            """, table)
            validation['tables_created'][table] = result > 0

        # Check materialized views
        views = ['apollo_enrichment_success_rates', 'apollo_most_enriched_companies', 'apollo_missing_data_report']
        for view in views:
            result = await self.conn.fetchval("""
                SELECT COUNT(*) FROM pg_matviews
                WHERE matviewname = $1
            """, view)
            validation['views_created'][view] = result > 0

        # Check functions
        functions = ['calculate_apollo_completeness_score', 'find_similar_apollo_persons', 'find_similar_apollo_companies']
        for func in functions:
            result = await self.conn.fetchval("""
                SELECT COUNT(*) FROM pg_proc
                WHERE proname = $1
            """, func)
            validation['functions_created'][func] = result > 0

        # Check key indexes
        key_indexes = [
            'idx_apollo_person_email',
            'idx_apollo_company_domain',
            'idx_apollo_person_embedding',
            'idx_apollo_cache_key'
        ]
        for index in key_indexes:
            result = await self.conn.fetchval("""
                SELECT COUNT(*) FROM pg_indexes
                WHERE indexname = $1
            """, index)
            validation['indexes_created'][index] = result > 0

        # Count total success
        total_checks = sum(len(v) for v in validation.values())
        successful_checks = sum(
            sum(1 for success in v.values() if success)
            for v in validation.values()
        )
        validation['success_rate'] = f"{successful_checks}/{total_checks}"
        validation['all_successful'] = successful_checks == total_checks

        return validation

    async def create_sample_data(self) -> bool:
        """Insert sample Apollo enrichment data for testing"""
        try:
            sample_data = """
                INSERT INTO apollo_enrichments (
                    enrichment_type, enrichment_status,
                    person_first_name, person_last_name, person_email,
                    person_title, person_linkedin_url,
                    company_name, company_domain, company_industry,
                    company_employee_count, overall_confidence_score,
                    data_completeness_score, api_credits_used
                ) VALUES
                (
                    'person', 'completed',
                    'John', 'Doe', 'john.doe@example.com',
                    'Software Engineer', 'https://linkedin.com/in/johndoe',
                    'Example Corp', 'example.com', 'Technology',
                    500, 0.95, 0.85, 1
                ),
                (
                    'company', 'completed',
                    NULL, NULL, NULL,
                    NULL, NULL,
                    'TechCorp Inc', 'techcorp.com', 'Software',
                    1000, 0.90, 0.75, 1
                ),
                (
                    'combined', 'partial',
                    'Jane', 'Smith', 'jane.smith@techcorp.com',
                    'Product Manager', NULL,
                    'TechCorp Inc', 'techcorp.com', 'Software',
                    1000, 0.80, 0.60, 2
                )
                ON CONFLICT DO NOTHING;
            """

            await self.conn.execute(sample_data)
            logger.info("Sample data inserted successfully")

            # Refresh materialized views
            await self.conn.execute("SELECT refresh_apollo_materialized_views();")
            logger.info("Materialized views refreshed")

            return True
        except Exception as e:
            logger.error(f"Failed to create sample data: {e}")
            return False

    async def show_statistics(self):
        """Display migration statistics and table counts"""
        try:
            stats = {}

            # Count records in main tables
            tables = ['apollo_enrichments', 'apollo_search_cache', 'apollo_metrics', 'apollo_phone_numbers']
            for table in tables:
                count = await self.conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                stats[table] = count

            # Get materialized view counts
            views = ['apollo_enrichment_success_rates', 'apollo_most_enriched_companies', 'apollo_missing_data_report']
            for view in views:
                try:
                    count = await self.conn.fetchval(f"SELECT COUNT(*) FROM {view}")
                    stats[view] = count
                except:
                    stats[view] = "Not refreshed"

            # Display statistics
            logger.info("\n" + "="*60)
            logger.info("APOLLO MIGRATION STATISTICS")
            logger.info("="*60)

            logger.info("\nTable Record Counts:")
            for table in tables:
                logger.info(f"  {table}: {stats[table]} records")

            logger.info("\nMaterialized View Counts:")
            for view in views:
                logger.info(f"  {view}: {stats[view]}")

            # Check vector extension capabilities
            vector_info = await self.conn.fetchval("""
                SELECT extversion FROM pg_extension WHERE extname = 'vector'
            """)
            if vector_info:
                logger.info(f"\nVector Extension Version: {vector_info}")

            logger.info("="*60 + "\n")

        except Exception as e:
            logger.error(f"Failed to show statistics: {e}")

async def main():
    """Main execution function"""
    runner = ApolloMigrationRunner()

    try:
        # Connect to database
        if not await runner.connect():
            logger.error("Failed to connect to database")
            return 1

        # Check if migration already applied
        if await runner.check_migration_history():
            logger.info("Migration '004_apollo_enrichment_tables' has already been applied")

            # Show current statistics
            await runner.show_statistics()
            return 0

        # Validate prerequisites
        logger.info("Checking prerequisites...")
        prereqs = await runner.validate_prerequisites()

        # Warn about existing tables
        existing_tables = [k for k, v in prereqs.items() if k.startswith('table_') and v]
        if existing_tables:
            logger.warning(f"Existing tables found: {existing_tables}")
            response = input("Continue with migration? (y/N): ")
            if response.lower() != 'y':
                logger.info("Migration cancelled by user")
                return 0

        # Run migration
        logger.info("Starting migration...")
        if await runner.run_migration():
            logger.info("Migration completed successfully")

            # Validate migration
            validation = await runner.validate_migration()
            if validation['all_successful']:
                logger.info("All validation checks passed")
            else:
                logger.warning("Some validation checks failed:")
                for category, checks in validation.items():
                    if isinstance(checks, dict):
                        failed = [k for k, v in checks.items() if not v]
                        if failed:
                            logger.warning(f"  {category}: {failed}")

            # Ask about sample data
            response = input("\nInsert sample data for testing? (y/N): ")
            if response.lower() == 'y':
                await runner.create_sample_data()

            # Show final statistics
            await runner.show_statistics()

            logger.info("\n✅ Apollo.io enrichment schema is ready for use!")
            logger.info("Remember to:")
            logger.info("  1. Set up periodic refresh of materialized views")
            logger.info("  2. Configure appropriate user permissions")
            logger.info("  3. Monitor API credit usage through apollo_metrics table")

            return 0
        else:
            logger.error("Migration failed - check logs for details")
            return 1

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        await runner.disconnect()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)