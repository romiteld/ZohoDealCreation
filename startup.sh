#!/bin/bash
echo "Starting Well Intake API - $(date)"

# Ensure pip is updated
python -m pip install --upgrade pip

# Install requirements
echo "Installing requirements..."
python -m pip install -r requirements.txt --no-cache-dir

# Verify critical imports
echo "Verifying installations..."
python -c "import fastapi; print('✓ FastAPI')" || exit 1
python -c "import uvicorn; print('✓ Uvicorn')" || exit 1
python -c "import asyncpg; print('✓ AsyncPG')" || exit 1
python -c "import crewai; print('✓ CrewAI')" || exit 1

# Start the application
echo "Starting Gunicorn..."
exec gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 1 --worker-class uvicorn.workers.UvicornWorker app.main_optimized:app