#!/bin/bash

# Optimized startup script for Azure App Service deployment
# This script improves cold start performance and reliability

echo "Starting Well Intake API (Optimized) - $(date)"

# Set environment variables for optimization
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

# Check if running in Azure
if [ ! -z "$WEBSITE_INSTANCE_ID" ]; then
    echo "Running in Azure App Service"
    
    # Use Gunicorn with Uvicorn workers for production
    exec gunicorn app.main_optimized:app \
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
    
    # Use Uvicorn directly for development
    exec uvicorn app.main_optimized:app \
        --host 0.0.0.0 \
        --port $PORT \
        --loop uvloop \
        --log-level info \
        --access-log
fi