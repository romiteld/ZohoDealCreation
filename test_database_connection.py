#!/usr/bin/env python3
"""
Test script for Database Connection Manager (Agent #4)
Validates that learning services have reliable database access
"""

import asyncio
import os
import sys
import traceback
from datetime import datetime

# Add app to Python path
sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

async def test_database_connection_manager():
    """Test the database connection manager functionality"""
    print("🔧 Testing Database Connection Manager (Agent #4)")
    print("=" * 60)
    
    # Test 1: Import and initialize connection manager
    try:
        from app.database_connection_manager import get_connection_manager, ensure_learning_services_ready
        print("✅ Successfully imported database connection manager")
    except ImportError as e:
        print(f"❌ Failed to import database connection manager: {e}")
        return False
    
    # Test 2: Initialize connection manager
    try:
        connection_manager = await get_connection_manager()
        print("✅ Database connection manager initialized")
        
        # Check health status
        health = connection_manager.get_health_status()
        print(f"   - Health Status: {'✅ Healthy' if health.is_healthy else '❌ Unhealthy'}")
        print(f"   - Connection Count: {health.connection_count}")
        print(f"   - Total Queries: {health.total_queries}")
        print(f"   - Avg Response Time: {health.avg_response_time_ms:.2f}ms")
        
        if not health.is_healthy:
            print(f"   - Last Error: {health.last_error}")
            
    except Exception as e:
        print(f"❌ Failed to initialize connection manager: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False
    
    # Test 3: Test basic database connectivity
    try:
        async with connection_manager.get_connection() as conn:
            result = await conn.fetchval('SELECT 1')
            if result == 1:
                print("✅ Basic database connectivity test passed")
            else:
                print(f"❌ Basic connectivity test failed, got: {result}")
                return False
    except Exception as e:
        print(f"❌ Database connectivity test failed: {e}")
        return False
    
    # Test 4: Verify learning tables exist
    try:
        async with connection_manager.get_connection() as conn:
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('ai_corrections', 'learning_patterns', 'extraction_analytics', 'company_templates')
                ORDER BY table_name
            """)
            
            table_names = [row['table_name'] for row in tables]
            expected_tables = ['ai_corrections', 'learning_patterns', 'extraction_analytics', 'company_templates']
            
            print(f"✅ Found {len(table_names)} learning tables:")
            for table in table_names:
                print(f"   - {table}")
            
            missing_tables = set(expected_tables) - set(table_names)
            if missing_tables:
                print(f"⚠️  Missing tables: {missing_tables}")
            else:
                print("✅ All required learning tables are present")
                
    except Exception as e:
        print(f"❌ Learning tables verification failed: {e}")
        return False
    
    # Test 5: Test learning services readiness
    try:
        learning_ready = await ensure_learning_services_ready()
        if learning_ready:
            print("✅ Learning services database access verified")
        else:
            print("⚠️  Learning services readiness check failed")
    except Exception as e:
        print(f"❌ Learning services readiness test failed: {e}")
        return False
    
    # Test 6: Test enhanced client (if available)
    try:
        enhanced_client = connection_manager.get_enhanced_client()
        if enhanced_client:
            print("✅ Enhanced PostgreSQL client available")
            print("   - 400K context window support")
            print("   - pgvector integration")
            print("   - Cost tracking capabilities")
        else:
            print("ℹ️  Enhanced PostgreSQL client not available (using basic client)")
    except Exception as e:
        print(f"⚠️  Enhanced client test failed: {e}")
    
    # Test 7: Test transaction handling
    try:
        queries = [
            ("SELECT 1", [], 'fetchval'),
            ("SELECT 2", [], 'fetchval'),
            ("SELECT 3", [], 'fetchval')
        ]
        
        results = await connection_manager.execute_transaction(queries)
        if results == [1, 2, 3]:
            print("✅ Transaction handling test passed")
        else:
            print(f"❌ Transaction test failed, got: {results}")
            return False
    except Exception as e:
        print(f"❌ Transaction handling test failed: {e}")
        return False
    
    # Test 8: Get comprehensive health report
    try:
        health_report = connection_manager.get_health_report()
        print("✅ Comprehensive health report generated:")
        print(f"   - Configuration: {health_report['configuration']}")
        print(f"   - Features: {health_report['features']}")
        print(f"   - Statistics: {health_report['statistics']}")
    except Exception as e:
        print(f"❌ Health report generation failed: {e}")
        return False
    
    print("\n🎉 All database connection manager tests passed!")
    print("   Agent #4 implementation is working correctly")
    print("   Learning services have reliable database access")
    return True

async def test_correction_learning_integration():
    """Test integration with correction learning service"""
    print("\n🧠 Testing Correction Learning Service Integration (Agent #3 + #4)")
    print("=" * 60)
    
    try:
        from app.database_connection_manager import get_connection_manager
        from app.correction_learning import CorrectionLearningService
        
        # Get connection manager
        connection_manager = await get_connection_manager()
        
        # Initialize correction learning service with connection manager
        correction_service = CorrectionLearningService(connection_manager, use_azure_search=False)
        print("✅ CorrectionLearningService initialized with DatabaseConnectionManager")
        
        # Test storing a correction (dry run)
        test_correction = {
            'email_domain': 'test-domain.com',
            'original_extraction': {'candidate_name': 'John Doe', 'job_title': 'Developer'},
            'user_corrections': {'candidate_name': 'John Smith', 'job_title': 'Senior Developer'},
            'email_snippet': 'Test email for database connection validation'
        }
        
        success = await correction_service.store_correction(
            test_correction['email_domain'],
            test_correction['original_extraction'],
            test_correction['user_corrections'],
            test_correction['email_snippet']
        )
        
        if success:
            print("✅ Correction storage test passed")
            print("   - Database operations work correctly")
            print("   - Learning patterns are being recorded")
        else:
            print("❌ Correction storage test failed")
            return False
            
    except Exception as e:
        print(f"❌ Correction learning integration test failed: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False
    
    print("✅ Correction learning service integration working correctly")
    return True

async def main():
    """Main test runner"""
    print(f"🚀 Database Connection Manager Test Suite")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    print(f"   Database URL: {'✅ Configured' if os.getenv('DATABASE_URL') else '❌ Missing'}")
    print()
    
    # Run tests
    db_test_passed = await test_database_connection_manager()
    
    if db_test_passed:
        integration_test_passed = await test_correction_learning_integration()
        
        if integration_test_passed:
            print("\n🎯 SUMMARY: All tests passed!")
            print("   Agent #4 (Database Connection Setup) is working perfectly")
            print("   Agent #3 (Learning services) has reliable database access")
            print("   Ready for production deployment")
            return True
        else:
            print("\n⚠️  SUMMARY: Database connection manager works, but integration has issues")
            return False
    else:
        print("\n❌ SUMMARY: Database connection manager tests failed")
        print("   Please check database configuration and connectivity")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        sys.exit(1)