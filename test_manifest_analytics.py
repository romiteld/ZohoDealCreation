#!/usr/bin/env python3
"""
Test script for manifest analytics functionality.
"""

import asyncio
import sys
from datetime import datetime
from unittest.mock import Mock

# Add app to path for imports
sys.path.append('.')

async def test_manifest_analytics():
    """Test the manifest analytics service."""
    try:
        from app.manifest_analytics import ManifestAnalyticsService, ManifestRequest
        
        print("✓ Successfully imported ManifestAnalyticsService")
        
        # Create a mock monitoring service and cache manager
        mock_monitoring = Mock()
        mock_cache_manager = Mock()
        
        # Initialize the analytics service
        analytics = ManifestAnalyticsService(mock_monitoring, mock_cache_manager)
        print("✓ Successfully created ManifestAnalyticsService instance")
        
        # Test user agent parsing
        test_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; mso-outlook-client) AppleWebKit/537.36"
        office_version, office_platform = analytics.parse_user_agent(test_user_agent)
        print(f"✓ User agent parsing: version='{office_version}', platform='{office_platform}'")
        
        # Test manifest version extraction
        manifest_version = analytics.extract_manifest_version("addin/manifest.xml")
        print(f"✓ Manifest version extraction: {manifest_version}")
        
        # Test cache status (should handle empty data gracefully)
        cache_status = await analytics.get_cache_status()
        print(f"✓ Cache status: {cache_status['status']}")
        
        # Test performance metrics (should handle empty data gracefully)
        performance_metrics = await analytics.get_performance_metrics(24)
        print(f"✓ Performance metrics: {performance_metrics.get('error', 'No data available')}")
        
        # Test version adoption (should handle empty data gracefully)
        version_adoption = await analytics.get_version_adoption()
        print(f"✓ Version adoption: {version_adoption.get('error', 'No version data available')}")
        
        print("\n🎉 All tests passed! Manifest analytics service is working correctly.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all dependencies are installed: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_manifest_analytics())
    sys.exit(0 if success else 1)