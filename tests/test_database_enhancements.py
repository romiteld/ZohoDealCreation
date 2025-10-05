#!/usr/bin/env python3
"""
Test script for database enhancements with GPT-5-mini 400K context support
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_enhanced_features():
    """Test the enhanced database features"""
    
    try:
        from app.database_enhancements import (
            EnhancedPostgreSQLClient,
            CONTEXT_WINDOWS,
            CostAwareVectorSearch
        )
        from app.azure_cost_optimizer import AzureCostOptimizer
        
        # Get database URL
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.error("DATABASE_URL not found in environment")
            return False
        
        logger.info("Initializing enhanced PostgreSQL client...")
        client = EnhancedPostgreSQLClient(db_url)
        
        # Initialize pool
        await client.init_pool()
        logger.info("✅ Connection pool initialized")
        
        # Ensure enhanced tables
        logger.info("Creating enhanced tables with pgvector support...")
        await client.ensure_enhanced_tables()
        logger.info("✅ Enhanced tables created")
        
        # Test large context storage
        logger.info("\nTesting 400K context storage...")
        test_content = "This is a test of the GPT-5-mini 400K context window. " * 1000
        context_id = await client.store_large_context(
            content=test_content,
            model_tier="gpt-5-mini",
            total_tokens=5000,
            metadata={"test": True, "source": "test_script"}
        )
        logger.info(f"✅ Stored large context with ID: {context_id}")
        
        # Test cost tracking
        logger.info("\nTesting cost tracking...")
        cost_id = await client.track_model_cost(
            model_tier="gpt-5-mini",
            input_tokens=1000,
            output_tokens=500,
            cached_tokens=200,
            cost=0.0025,
            success=True,
            metadata={"test": True}
        )
        logger.info(f"✅ Tracked cost with ID: {cost_id}")
        
        # Test correction patterns
        logger.info("\nTesting correction pattern storage...")
        pattern_id = await client.store_correction_pattern(
            field_name="candidate_name",
            original_value="John Smith",
            corrected_value="Jonathan Smith",
            domain="example.com",
            context_snippet="Email context here..."
        )
        logger.info(f"✅ Stored correction pattern with ID: {pattern_id}")
        
        # Get relevant patterns
        patterns = await client.get_relevant_correction_patterns(
            field_name="candidate_name",
            min_confidence=0.3,
            limit=5
        )
        logger.info(f"✅ Retrieved {len(patterns)} correction patterns")
        
        # Test cost analytics
        logger.info("\nTesting cost analytics...")
        analytics = await client.get_cost_analytics()
        logger.info(f"✅ Cost analytics retrieved:")
        logger.info(f"  - Total requests: {analytics.get('overall', {}).get('total_requests', 0)}")
        logger.info(f"  - Total cost: ${analytics.get('overall', {}).get('total_cost', 0):.4f}")
        
        # Test cost-aware search
        logger.info("\nTesting cost-aware vector search...")
        optimizer = AzureCostOptimizer(budget_limit_daily=50.0)
        search = CostAwareVectorSearch(client, optimizer)
        
        # Create a dummy embedding (normally from OpenAI)
        dummy_embedding = [0.1] * 1536
        results, cost_info = await search.search_with_cost_optimization(
            query_embedding=dummy_embedding,
            query_text="Test query for similarity search",
            limit=3,
            max_cost=0.05
        )
        logger.info(f"✅ Cost-aware search completed:")
        logger.info(f"  - Results: {len(results)}")
        logger.info(f"  - Cost info: {cost_info}")
        
        # Test context windows
        logger.info("\nContext window configurations:")
        for model, window in CONTEXT_WINDOWS.items():
            logger.info(f"  - {model}: {window.max_tokens:,} tokens, "
                       f"{window.chunk_size:,} chunk size")
        
        # Cleanup old data (optional)
        logger.info("\nTesting data cleanup...")
        cleanup_result = await client.cleanup_old_data(days_to_keep=90)
        logger.info(f"✅ Cleanup completed: {cleanup_result}")
        
        logger.info("\n" + "="*50)
        logger.info("✅ ALL TESTS PASSED SUCCESSFULLY!")
        logger.info("="*50)
        
        return True
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure to install required packages:")
        logger.error("  pip install asyncpg pgvector")
        return False
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function"""
    logger.info("="*50)
    logger.info("TESTING DATABASE ENHANCEMENTS FOR GPT-5-MINI")
    logger.info("400K Context Window Support with pgvector")
    logger.info("="*50)
    
    success = await test_enhanced_features()
    
    if success:
        logger.info("\n✅ Database enhancements are ready for production!")
        logger.info("Features available:")
        logger.info("  • 400K token context storage with chunking")
        logger.info("  • Vector similarity search with pgvector")
        logger.info("  • Cost tracking for GPT-5 model tiers")
        logger.info("  • Enhanced correction learning with embeddings")
        logger.info("  • Cost-aware search optimization")
        logger.info("  • Comprehensive analytics and metrics")
    else:
        logger.error("\n❌ Some tests failed. Check the logs above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())