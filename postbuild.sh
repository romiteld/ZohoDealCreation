#!/bin/bash
# Azure App Service Post-Build Script
# This script runs after the main build process

echo "=========================================="
echo "Starting Post-Build Process..."
echo "=========================================="

# Verify all critical packages are installed
echo "Verifying package installations..."
python -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"
python -c "import crewai; print(f'CrewAI: {crewai.__version__}')"
python -c "import langchain; print(f'Langchain: {langchain.__version__}')"
python -c "import openai; print(f'OpenAI: {openai.__version__}')"

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p /home/site/wwwroot/logs
mkdir -p /home/site/wwwroot/temp

# Set proper permissions
echo "Setting permissions..."
chmod +x /home/site/wwwroot/prebuild.sh 2>/dev/null || true
chmod +x /home/site/wwwroot/postbuild.sh 2>/dev/null || true
chmod +x /home/site/wwwroot/startup.sh 2>/dev/null || true

# Create a startup script if it doesn't exist
if [ ! -f /home/site/wwwroot/startup.sh ]; then
    echo "Creating startup.sh..."
    cat > /home/site/wwwroot/startup.sh << 'EOF'
#!/bin/bash
echo "Starting Well Intake API..."
cd /home/site/wwwroot
gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker --access-logfile - --error-logfile - app.main:app
EOF
    chmod +x /home/site/wwwroot/startup.sh
fi

echo "=========================================="
echo "Post-Build Process Completed!"
echo "=========================================="

# Display final package list for verification
echo "Installed packages:"
pip list