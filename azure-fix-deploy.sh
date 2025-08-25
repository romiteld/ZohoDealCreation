#!/bin/bash

# Quick fix deployment for Azure App Service
echo "Quick Fix Deployment for Well Intake API"
echo "=========================================="

# Use the fixed requirements file
cp requirements-azure.txt requirements.txt

# Create a simple startup that ensures dependencies are installed
cat > startup-azure.sh << 'EOF'
#!/bin/bash
echo "Azure App Service Startup"
echo "========================="
cd /home/site/wwwroot

# Set SQLite for ChromaDB
export __import__hook__=pysqlite3
export CHROMA_SQLITE_IMPL=pysqlite3

# Simple startup without dependency checks
exec gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 1 --worker-class uvicorn.workers.UvicornWorker app.main:app
EOF

chmod +x startup-azure.sh

# Update app settings to use the new startup
az webapp config set \
  --resource-group TheWell-App-East \
  --name well-intake-api \
  --generic-configurations '{"appCommandLine": "bash startup-azure.sh"}' \
  --output none

# Set build settings
az webapp config appsettings set \
  --resource-group TheWell-App-East \
  --name well-intake-api \
  --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  ENABLE_ORYX_BUILD=true \
  WEBSITE_RUN_FROM_PACKAGE=0 \
  --output none

echo "Creating deployment package..."
zip -r deploy-fix.zip . \
  -x "zoho/*" "*.pyc" "__pycache__/*" ".env*" "*.git*" \
  -x "deploy*.zip" "test_*.py" "venv/*" ".vscode/*"

echo "Deploying..."
az webapp deploy \
  --resource-group TheWell-App-East \
  --name well-intake-api \
  --src-path deploy-fix.zip \
  --type zip \
  --restart true \
  --async false

echo "Deployment initiated. Check status with:"
echo "az webapp log tail --resource-group TheWell-App-East --name well-intake-api"