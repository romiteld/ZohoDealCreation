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

# Start Zoho multi-module sync scheduler in background
# This provides continuous sync for Leads, Deals, Contacts, Accounts
echo "Starting Zoho sync scheduler (multi-module)..."
python3 -m app.jobs.zoho_sync_scheduler &
SCHEDULER_PID=$!
echo "Zoho sync scheduler started (PID: $SCHEDULER_PID)"

# Start the FastAPI application (foreground)
echo "Starting FastAPI application..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
