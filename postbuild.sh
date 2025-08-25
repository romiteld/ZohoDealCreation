#!/bin/bash
echo "=== Post-build script starting ==="

# CRITICAL: Install pysqlite3-binary first for ChromaDB/CrewAI compatibility
echo "Installing pysqlite3-binary for SQLite fix..."
pip install --no-cache-dir --force-reinstall pysqlite3-binary==0.5.4

# Ensure all dependencies are installed
pip install --no-cache-dir -r requirements.txt

# Install additional dependencies that might be missing
pip install --no-cache-dir typing-extensions==4.8.0
pip install --no-cache-dir pydantic-core==2.20.1
pip install --no-cache-dir pydantic==2.8.2

# Ensure langchain-openai is installed
pip install --no-cache-dir langchain-openai==0.0.5

# Test imports to ensure everything works
python -c "
import sys
print('Python version:', sys.version)
print('Testing imports...')

# Test SQLite patch first
try:
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
    import sqlite3
    print(f'✓ SQLite patched. Version: {sqlite3.sqlite_version}')
except Exception as e:
    print(f'✗ SQLite patch failed: {e}')

try:
    import fastapi
    print('✓ FastAPI imported')
except ImportError as e:
    print(f'✗ FastAPI import failed: {e}')

try:
    import uvicorn
    print('✓ Uvicorn imported')
except ImportError as e:
    print(f'✗ Uvicorn import failed: {e}')

try:
    import crewai
    print('✓ CrewAI imported')
except ImportError as e:
    print(f'✗ CrewAI import failed: {e}')

try:
    from app.main import app
    print('✓ Main app imported successfully')
except ImportError as e:
    print(f'✗ Main app import failed: {e}')

print('Import test completed')
"

echo "=== Post-build script completed ==="