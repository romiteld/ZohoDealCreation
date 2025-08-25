#!/bin/bash

# Azure App Service Custom Startup Script with Dependency Management
# This script ensures all dependencies are properly installed at runtime

echo "Azure Well Intake API Startup - $(date)"

# Set Python environment variables
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=random
export PYTHONUTF8=1

# Azure App Service specific
export WEBSITE_HOSTNAME=${WEBSITE_HOSTNAME:-localhost}
export PORT=${PORT:-8000}

# Performance optimizations
export MALLOC_TRIM_THRESHOLD_=100000
export MALLOC_MMAP_MAX_=65536

# CRITICAL: Force pysqlite3 to be used instead of system sqlite3
export LD_PRELOAD=/usr/local/lib/python3.12/site-packages/pysqlite3/__init__.py

# Check if running in Azure
if [ ! -z "$WEBSITE_INSTANCE_ID" ]; then
    echo "Running in Azure App Service - Instance: $WEBSITE_INSTANCE_ID"
    
    # CRITICAL: Ensure pip is up to date
    echo "Updating pip..."
    python -m pip install --upgrade pip
    
    # CRITICAL: Install pysqlite3-binary FIRST
    echo "Installing pysqlite3-binary to replace system sqlite3..."
    python -m pip install --no-cache-dir --force-reinstall pysqlite3-binary
    
    # Test that pysqlite3 works
    echo "Testing pysqlite3 installation..."
    python -c "import pysqlite3; print(f'pysqlite3 version: {pysqlite3.version}')" || echo "WARNING: pysqlite3 test failed"
    
    # CRITICAL: Force reinstall key dependencies
    echo "Ensuring critical dependencies are installed..."
    
    # Install uvicorn and gunicorn first (needed for startup)
    python -m pip install --no-cache-dir uvicorn[standard]==0.24.0 gunicorn==21.2.0
    
    # Install openai with correct version
    echo "Installing openai and langchain packages..."
    python -m pip install --no-cache-dir --force-reinstall \
        openai==1.68.2 \
        langchain==0.1.0 \
        langchain-core==0.1.0 \
        langchain-community==0.0.10 \
        langchain-openai==0.0.5
    
    # Install remaining critical packages
    echo "Installing remaining packages..."
    python -m pip install --no-cache-dir \
        fastapi==0.104.1 \
        crewai==0.159.0 \
        firecrawl-py==0.0.16 \
        setuptools==69.0.2
    
    # Verify critical imports
    echo "Verifying critical imports..."
    python -c "
import sys
try:
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
    print('✓ pysqlite3 patched successfully')
except ImportError:
    print('✗ pysqlite3 missing')
    
try:
    import uvicorn
    print('✓ uvicorn')
except ImportError:
    print('✗ uvicorn missing')
    
try:
    import fastapi
    print('✓ fastapi')
except ImportError:
    print('✗ fastapi missing')
    
try:
    import langchain_openai
    print('✓ langchain_openai')
except ImportError:
    print('✗ langchain_openai missing')
    
try:
    import crewai
    print('✓ crewai')
except ImportError:
    print('✗ crewai missing')
"
    
    # Check if we should use optimized or standard version
    if [ -f "app/main_optimized.py" ]; then
        echo "Using optimized main module"
        APP_MODULE="app.main_optimized:app"
    else
        echo "Using standard main module"
        APP_MODULE="app.main:app"
    fi
    
    echo "Starting Gunicorn with Uvicorn workers..."
    exec gunicorn $APP_MODULE \
        --bind 0.0.0.0:$PORT \
        --workers 2 \
        --worker-class uvicorn.workers.UvicornWorker \
        --timeout 120 \
        --graceful-timeout 30 \
        --keep-alive 5 \
        --max-requests 1000 \
        --max-requests-jitter 50 \
        --preload \
        --access-logfile - \
        --error-logfile - \
        --log-level info \
        --worker-tmp-dir /dev/shm
else
    echo "Running in development mode"
    
    # Development mode - activate virtual environment if it exists
    if [ -d "zoho" ]; then
        echo "Activating virtual environment..."
        source zoho/bin/activate
    fi
    
    # Check dependencies
    if ! python -c "import uvicorn" 2>/dev/null; then
        echo "Installing development dependencies..."
        pip install -r requirements.txt
    fi
    
    # Use Uvicorn directly for development
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --reload \
        --log-level info
fi