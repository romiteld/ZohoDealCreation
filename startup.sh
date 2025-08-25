#!/bin/bash

# Well Intake API Startup Script
# This script ensures proper environment setup and application startup

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Well Intake API...${NC}"

# Check if we're in the correct directory
if [ ! -f "app/main.py" ]; then
    echo -e "${RED}Error: Not in the correct directory. Please run from the project root.${NC}"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "zoho" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv zoho
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source zoho/bin/activate

# Check if requirements are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}Dependencies not installed. Installing...${NC}"
    pip install -r requirements.txt
fi

# Check for .env.local file
if [ ! -f ".env.local" ]; then
    echo -e "${RED}Warning: .env.local file not found!${NC}"
    echo "Please create .env.local with your configuration."
    echo "You can copy from .env.example if it exists."
fi

# Set environment variables for development
export ENVIRONMENT=${ENVIRONMENT:-development}
export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8000}

# Kill any existing process on the port
echo -e "${YELLOW}Checking for existing processes on port $PORT...${NC}"
lsof -ti:$PORT | xargs kill -9 2>/dev/null || true

# Start the application
echo -e "${GREEN}Starting FastAPI application on http://$HOST:$PORT${NC}"
echo -e "${GREEN}API Documentation: http://localhost:$PORT/docs${NC}"
echo -e "${GREEN}Health Check: http://localhost:$PORT/health${NC}"

# Use uvicorn for development, gunicorn for production
if [ "$ENVIRONMENT" = "production" ]; then
    echo -e "${GREEN}Running in PRODUCTION mode with Gunicorn...${NC}"
    exec gunicorn \
        --bind=$HOST:$PORT \
        --timeout 600 \
        --workers 2 \
        --worker-class uvicorn.workers.UvicornWorker \
        --access-logfile - \
        --error-logfile - \
        --log-level info \
        app.main:app
else
    echo -e "${GREEN}Running in DEVELOPMENT mode with Uvicorn...${NC}"
    exec uvicorn app.main:app \
        --host $HOST \
        --port $PORT \
        --reload \
        --log-level info
fi