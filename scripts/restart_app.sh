#!/bin/bash

# Kill any existing Python processes running the app
echo "Stopping existing processes..."
pkill -f "uvicorn app.main"
pkill -f "python.*app.py"
pkill -f "python.*main.py"

# Clear Python cache
echo "Clearing Python cache..."
find /home/romiteld/outlook -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Restart the application
echo "Starting fresh application..."
cd /home/romiteld/outlook

# Export environment variables
export $(cat .env.local | xargs)

# Start the application with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
