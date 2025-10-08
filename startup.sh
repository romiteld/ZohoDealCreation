#!/bin/bash
# Azure Container Apps Startup Script
# Captures environment variables into .env file for Python runtime access
# This solves the issue where Azure Container Apps environment variables
# aren't automatically accessible to Python's os.getenv()

# Capture all environment variables to .env file
printenv > /app/.env

# Log confirmation (will appear in Azure Container Apps logs)
echo "Environment variables captured to /app/.env"
echo "Starting application..."

# Start the FastAPI application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
