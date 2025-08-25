#!/usr/bin/env python
"""
Test script to verify SQLite patching and ChromaDB compatibility
"""

import sys
import os

print("=" * 60)
print("SQLite/ChromaDB Compatibility Test")
print("=" * 60)

# Test 1: Check system SQLite version
print("\n1. System SQLite Version Check:")
try:
    import sqlite3 as system_sqlite
    print(f"   System SQLite version: {system_sqlite.sqlite_version}")
    version_parts = system_sqlite.sqlite_version.split('.')
    major, minor = int(version_parts[0]), int(version_parts[1])
    if major < 3 or (major == 3 and minor < 35):
        print(f"   Warning: System version is too old for ChromaDB (need >= 3.35.0)")
    else:
        print(f"   OK: System version is compatible")
except Exception as e:
    print(f"   Error checking system SQLite: {e}")

# Test 2: Check if pysqlite3-binary is installed
print("\n2. pysqlite3-binary Check:")
try:
    import pysqlite3
    print(f"   OK: pysqlite3-binary is installed")
    print(f"   pysqlite3 version: {pysqlite3.sqlite_version}")
except ImportError:
    print(f"   WARNING: pysqlite3-binary is NOT installed")
    print(f"   Run: pip install pysqlite3-binary")

# Test 3: Test our patcher module
print("\n3. App SQLite Patcher Test:")
try:
    from app.sqlite_patcher import patch_sqlite, is_patched, get_sqlite_version
    
    if is_patched():
        print(f"   OK: Patcher successful")
        print(f"   Active SQLite version: {get_sqlite_version()}")
    else:
        print(f"   WARNING: Patcher incomplete")
        print(f"   Active SQLite version: {get_sqlite_version()}")
        
    # Check the actual sqlite3 module after patching
    import sqlite3
    print(f"   sqlite3 module version: {sqlite3.sqlite_version}")
    
except Exception as e:
    print(f"   Error with app patcher: {e}")

print("\n" + "=" * 60)
print("Test completed")
print("=" * 60)
