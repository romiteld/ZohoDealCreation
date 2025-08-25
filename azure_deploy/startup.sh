#!/bin/bash
# Azure App Service Startup Script

# Set environment
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Import SQLite override
export PYTHONPATH="/home/site/wwwroot:${PYTHONPATH}"

# Run deployment script if needed
if [ ! -f "/home/.deployment_done" ]; then
    echo "Running deployment script..."
    bash /home/site/wwwroot/scripts/deploy.sh
    touch /home/.deployment_done
fi

# Start the application with Gunicorn and Uvicorn workers
echo "Starting application..."
exec gunicorn     --bind=0.0.0.0:8000     --timeout 600     --workers 2     --worker-class uvicorn.workers.UvicornWorker     --access-logfile -     --error-logfile -     --log-level info     app.main:app
