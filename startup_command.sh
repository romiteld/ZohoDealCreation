#!/bin/bash
# Azure App Service startup command
# Install dependencies if not already installed
if ! python -c "import uvicorn" 2>/dev/null; then
    echo "Installing requirements..."
    pip install -r requirements.txt
fi

# Start the application
gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker app.main_optimized:app