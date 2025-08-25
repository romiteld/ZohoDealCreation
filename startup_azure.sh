#!/bin/bash

# Azure App Service Startup Script for Well Intake API

# Install missing dependencies that might not be in the deployment
echo "Installing critical dependencies..."
pip install asyncpg langchain-openai --no-cache-dir

# Check if installation was successful
python -c "import asyncpg; print('✓ asyncpg installed')" || echo "✗ asyncpg failed"
python -c "from langchain_openai import ChatOpenAI; print('✓ langchain-openai installed')" || echo "✗ langchain-openai failed"

# Start the application
echo "Starting Well Intake API..."
exec gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker app.main_optimized:app