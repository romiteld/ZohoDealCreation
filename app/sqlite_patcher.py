"""
SQLite3 Patcher for Azure App Service Compatibility

This module MUST be imported before any other modules that use SQLite3 (like ChromaDB).
It patches the system SQLite3 module with pysqlite3-binary which has the required version.

Azure App Service often has an old SQLite version (< 3.35.0) that's incompatible with ChromaDB.
ChromaDB requires SQLite >= 3.35.0 for JSON and other features.
"""

import sys
import logging

logger = logging.getLogger(__name__)

def patch_sqlite():
    """
    Patch sqlite3 module with pysqlite3-binary for Azure compatibility.
    
    Returns:
        bool: True if patching succeeded, False otherwise
    """
    try:
        # First, try to import pysqlite3
        import pysqlite3
        
        # Check version before patching
        sqlite_version = pysqlite3.sqlite_version
        version_parts = sqlite_version.split('.')
        major = int(version_parts[0])
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
        
        if major < 3 or (major == 3 and minor < 35):
            logger.error(f"pysqlite3 version {sqlite_version} is still too old (need >= 3.35.0)")
            return False
        
        # Patch the sqlite3 module
        sys.modules['sqlite3'] = pysqlite3
        sys.modules['sqlite3.dbapi2'] = pysqlite3.dbapi2
        
        logger.info(f"✅ SQLite3 patched successfully with pysqlite3 version {sqlite_version}")
        print(f"[SQLite Patcher] Successfully patched with pysqlite3 version {sqlite_version}")
        return True
        
    except ImportError as e:
        logger.warning(f"pysqlite3-binary not available, trying system sqlite3: {e}")
        
        # Fall back to system sqlite3 and check its version
        try:
            import sqlite3
            sqlite_version = sqlite3.sqlite_version
            version_parts = sqlite_version.split('.')
            major = int(version_parts[0])
            minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            
            if major < 3 or (major == 3 and minor < 35):
                error_msg = (
                    f"⚠️ System SQLite version {sqlite_version} is too old for ChromaDB (need >= 3.35.0)\n"
                    f"Please ensure pysqlite3-binary is installed: pip install pysqlite3-binary"
                )
                logger.error(error_msg)
                print(f"[SQLite Patcher] ERROR: {error_msg}")
                
                # Don't fail completely, let the app try to run
                # ChromaDB might not be used in all code paths
                return False
            else:
                logger.info(f"System SQLite version {sqlite_version} is acceptable")
                print(f"[SQLite Patcher] Using system SQLite version {sqlite_version}")
                return True
                
        except Exception as e2:
            logger.error(f"Failed to check system sqlite3: {e2}")
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error during SQLite patching: {e}")
        return False


# Auto-patch when module is imported
_patch_result = patch_sqlite()

def is_patched():
    """Check if SQLite was successfully patched."""
    return _patch_result

def get_sqlite_version():
    """Get the current SQLite version being used."""
    try:
        import sqlite3
        return sqlite3.sqlite_version
    except:
        return "unknown"