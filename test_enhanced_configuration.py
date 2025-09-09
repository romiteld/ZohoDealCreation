#!/usr/bin/env python3
"""
Enhanced Configuration System Test

This script tests the new enhanced configuration system with:
- Database fallback handling
- Azure service optional dependencies
- Configuration validation
- Health monitoring
- Graceful degradation
"""

import asyncio
import os
import sys
import logging
import tempfile
import json
from datetime import datetime
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_env_scenarios() -> Dict[str, Dict[str, str]]:
    """Create different environment scenarios for testing"""
    
    # Base configuration with API key only
    base_config = {
        "API_KEY": "test-api-key-12345",
        "USE_LANGGRAPH": "true",
        "OPENAI_API_KEY": "sk-test-key",
        "OPENAI_MODEL": "gpt-5",
        "OPENAI_TEMPERATURE": "1"
    }
    
    scenarios = {
        "minimal": base_config.copy(),
        
        "database_only": {
            **base_config,
            "DATABASE_URL": "postgresql://test:test@localhost:5432/testdb"
        },
        
        "redis_only": {
            **base_config,
            "AZURE_REDIS_CONNECTION_STRING": "rediss://:testkey@test.redis.cache.windows.net:6380"
        },
        
        "storage_only": {
            **base_config,
            "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=testkey;EndpointSuffix=core.windows.net"
        },
        
        "full_azure": {
            **base_config,
            "DATABASE_URL": "postgresql://test:test@localhost:5432/testdb",
            "AZURE_REDIS_CONNECTION_STRING": "rediss://:testkey@test.redis.cache.windows.net:6380",
            "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=testkey;EndpointSuffix=core.windows.net",
            "AZURE_SERVICE_BUS_CONNECTION_STRING": "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=testkey",
            "AZURE_SIGNALR_CONNECTION_STRING": "Endpoint=https://test.service.signalr.net;AccessKey=testkey;Version=1.0;",
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_KEY": "testkey",
            "APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=testkey"
        },
        
        "partial_config": {
            **base_config,
            "DATABASE_URL": "postgresql://test:test@localhost:5432/testdb",
            "AZURE_REDIS_CONNECTION_STRING": "rediss://:testkey@test.redis.cache.windows.net:6380",
            # Missing storage and other services
        }
    }
    
    return scenarios

async def test_config_manager(scenario_name: str, env_vars: Dict[str, str]):
    """Test configuration manager with specific environment"""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing scenario: {scenario_name}")
    logger.info(f"{'='*60}")
    
    # Set environment variables
    original_env = {}
    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        # Import and test configuration manager
        from app.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        
        # Test configuration loading
        health_status = config_manager.get_health_status()
        recommendations = config_manager.get_fallback_recommendations()
        
        logger.info(f"✅ Configuration Manager initialized")
        logger.info(f"   Database enabled: {config_manager.database.enabled}")
        logger.info(f"   Services configured: {len([s for s in config_manager.services.values() if s.connection_string])}")
        
        if recommendations:
            logger.info(f"   Recommendations ({len(recommendations)}):")
            for i, rec in enumerate(recommendations, 1):
                logger.info(f"     {i}. {rec}")
        
        return {
            "status": "success",
            "database_enabled": config_manager.database.enabled,
            "services_configured": len([s for s in config_manager.services.values() if s.connection_string]),
            "recommendations": len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"❌ Configuration Manager failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }
        
    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value

async def test_database_manager(scenario_name: str, env_vars: Dict[str, str]):
    """Test database manager with specific environment"""
    
    logger.info(f"\n--- Testing Database Manager for {scenario_name} ---")
    
    # Set environment variables
    original_env = {}
    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        from app.enhanced_database_manager import EnhancedDatabaseManager
        from app.config_manager import get_config_manager
        
        config_manager = get_config_manager()
        db_manager = EnhancedDatabaseManager(config_manager.database)
        
        # Test initialization (won't connect to real DB)
        success = await db_manager.initialize()
        
        health_status = db_manager.get_health_status()
        
        logger.info(f"✅ Database Manager initialized")
        logger.info(f"   Available: {db_manager.is_available()}")
        logger.info(f"   Fallback mode: {db_manager.state.fallback_mode}")
        logger.info(f"   Features: {sum(db_manager.state.features.to_dict().values())} enabled")
        
        # Test fallback query
        result = await db_manager.execute_query(
            "SELECT 1", 
            fallback_value="fallback_result"
        )
        logger.info(f"   Fallback query result: {result}")
        
        await db_manager.cleanup()
        
        return {
            "status": "success",
            "available": db_manager.is_available(),
            "fallback_mode": db_manager.state.fallback_mode,
            "features_enabled": sum(db_manager.state.features.to_dict().values())
        }
        
    except Exception as e:
        logger.error(f"❌ Database Manager failed: {e}")
        return {
            "status": "failed", 
            "error": str(e)
        }
        
    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value

async def test_azure_service_manager(scenario_name: str, env_vars: Dict[str, str]):
    """Test Azure service manager with specific environment"""
    
    logger.info(f"\n--- Testing Azure Service Manager for {scenario_name} ---")
    
    # Set environment variables
    original_env = {}
    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        from app.azure_service_manager import AzureServiceManager
        
        service_manager = AzureServiceManager()
        await service_manager.initialize()
        
        health_summary = service_manager.get_health_summary()
        
        # Test file storage fallback
        test_content = b"Test file content for fallback testing"
        storage_result = await service_manager.store_file(
            "test-file.txt",
            test_content
        )
        
        logger.info(f"✅ Azure Service Manager initialized")
        logger.info(f"   Overall status: {health_summary['overall_status']}")
        logger.info(f"   Storage mode: {health_summary['storage_mode']}")
        logger.info(f"   Services available: {sum(1 for s in health_summary['services'].values() if s['available'])}")
        logger.info(f"   File storage test: {storage_result['success']} ({storage_result['mode']})")
        
        if health_summary['recommendations']:
            logger.info(f"   Recommendations: {len(health_summary['recommendations'])}")
        
        await service_manager.cleanup()
        
        return {
            "status": "success",
            "overall_status": health_summary['overall_status'],
            "storage_mode": health_summary['storage_mode'],
            "services_available": sum(1 for s in health_summary['services'].values() if s['available']),
            "file_storage_works": storage_result['success']
        }
        
    except Exception as e:
        logger.error(f"❌ Azure Service Manager failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }
        
    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value

async def test_startup_manager(scenario_name: str, env_vars: Dict[str, str]):
    """Test startup manager with specific environment"""
    
    logger.info(f"\n--- Testing Startup Manager for {scenario_name} ---")
    
    # Set environment variables
    original_env = {}
    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        from app.enhanced_startup_manager import StartupManager
        
        # Create a mock app state
        class MockAppState:
            pass
        
        mock_app_state = MockAppState()
        
        startup_manager = StartupManager()
        initialization_results = await startup_manager.initialize_application(mock_app_state)
        
        logger.info(f"✅ Startup Manager completed")
        logger.info(f"   Overall status: {initialization_results['overall_status']}")
        logger.info(f"   Startup time: {initialization_results.get('startup_time_seconds', 0):.2f}s")
        logger.info(f"   Services initialized: {len(initialization_results['services'])}")
        logger.info(f"   Recommendations: {len(initialization_results.get('recommendations', []))}")
        
        # Test health status
        health_status = startup_manager.get_health_status()
        logger.info(f"   Health check successful: {bool(health_status)}")
        
        await startup_manager.cleanup()
        
        return {
            "status": "success",
            "overall_status": initialization_results['overall_status'],
            "startup_time": initialization_results.get('startup_time_seconds', 0),
            "services_count": len(initialization_results['services']),
            "recommendations_count": len(initialization_results.get('recommendations', []))
        }
        
    except Exception as e:
        logger.error(f"❌ Startup Manager failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }
        
    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value

async def run_comprehensive_tests():
    """Run comprehensive tests across all scenarios"""
    
    logger.info("🧪 Starting Comprehensive Enhanced Configuration Tests")
    logger.info("=" * 80)
    
    scenarios = create_test_env_scenarios()
    test_results = {}
    
    for scenario_name, env_vars in scenarios.items():
        logger.info(f"\n🎯 Testing Scenario: {scenario_name.upper()}")
        logger.info(f"Environment variables: {len(env_vars)}")
        
        scenario_results = {}
        
        # Test each manager
        scenario_results['config_manager'] = await test_config_manager(scenario_name, env_vars)
        scenario_results['database_manager'] = await test_database_manager(scenario_name, env_vars)
        scenario_results['azure_service_manager'] = await test_azure_service_manager(scenario_name, env_vars)
        scenario_results['startup_manager'] = await test_startup_manager(scenario_name, env_vars)
        
        test_results[scenario_name] = scenario_results
        
        # Summary for this scenario
        success_count = sum(1 for result in scenario_results.values() if result.get('status') == 'success')
        logger.info(f"\n📊 Scenario {scenario_name}: {success_count}/{len(scenario_results)} managers successful")
    
    # Overall summary
    logger.info(f"\n{'='*80}")
    logger.info("📋 COMPREHENSIVE TEST SUMMARY")
    logger.info(f"{'='*80}")
    
    total_tests = 0
    successful_tests = 0
    
    for scenario_name, scenario_results in test_results.items():
        scenario_success = sum(1 for result in scenario_results.values() if result.get('status') == 'success')
        scenario_total = len(scenario_results)
        total_tests += scenario_total
        successful_tests += scenario_success
        
        status_icon = "✅" if scenario_success == scenario_total else "⚠️" if scenario_success > 0 else "❌"
        logger.info(f"{status_icon} {scenario_name.ljust(15)}: {scenario_success}/{scenario_total} successful")
    
    success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
    logger.info(f"\n🎯 Overall Success Rate: {successful_tests}/{total_tests} ({success_rate:.1f}%)")
    
    if success_rate >= 90:
        logger.info("🎉 EXCELLENT: Enhanced configuration system is working great!")
    elif success_rate >= 70:
        logger.info("👍 GOOD: Enhanced configuration system is working well with minor issues")
    elif success_rate >= 50:
        logger.info("⚠️ FAIR: Enhanced configuration system has some issues that need attention")
    else:
        logger.info("❌ POOR: Enhanced configuration system needs significant fixes")
    
    # Generate test report
    report_path = "/tmp/enhanced_config_test_report.json"
    test_report = {
        "timestamp": datetime.utcnow().isoformat(),
        "test_scenarios": len(scenarios),
        "total_tests": total_tests,
        "successful_tests": successful_tests,
        "success_rate": success_rate,
        "results": test_results
    }
    
    with open(report_path, 'w') as f:
        json.dump(test_report, f, indent=2)
    
    logger.info(f"📄 Detailed test report saved to: {report_path}")
    
    return test_results

if __name__ == "__main__":
    try:
        # Ensure we can import our modules
        sys.path.insert(0, '/home/romiteld/outlook')
        
        # Run the comprehensive tests
        results = asyncio.run(run_comprehensive_tests())
        
        # Exit with appropriate code
        total_scenarios = len(results)
        successful_scenarios = sum(
            1 for scenario_results in results.values() 
            if all(r.get('status') == 'success' for r in scenario_results.values())
        )
        
        if successful_scenarios == total_scenarios:
            sys.exit(0)  # All tests passed
        elif successful_scenarios > 0:
            sys.exit(1)  # Some tests failed
        else:
            sys.exit(2)  # All tests failed
            
    except Exception as e:
        logger.error(f"Critical test failure: {e}")
        sys.exit(3)  # Critical error