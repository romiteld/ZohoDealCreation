"""
Mock chromadb module to prevent import errors
This allows CrewAI to import without actually using ChromaDB
"""

import sys

class MockChromaDB:
    """Mock ChromaDB module"""
    def __getattr__(self, name):
        # Return mock for any attribute access
        return lambda *args, **kwargs: None

# Create mock module
chromadb = MockChromaDB()
sys.modules['chromadb'] = chromadb
sys.modules['chromadb.utils'] = chromadb
sys.modules['chromadb.config'] = chromadb

# Mock sqlite3 version check
import sqlite3
sqlite3.sqlite_version = "3.46.1"  # Fake version to bypass check