#!/bin/bash

echo "========================================"
echo "Final Fix for Well Intake API Deployment"
echo "========================================"

# Step 1: Ensure we have the simplified requirements
echo "Step 1: Creating clean requirements.txt..."
cat > requirements.txt << 'EOF'
# Core Web Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
gunicorn==21.2.0
flask==3.0.0

# Azure and Storage
azure-storage-blob==12.19.0

# Database
asyncpg==0.29.0
psycopg2-binary==2.9.9
pgvector==0.2.4

# HTTP
requests==2.31.0
tenacity==8.2.3
httpx==0.27.2

# Data Processing
pydantic==2.8.2
python-multipart==0.0.6
email-validator==2.1.0
beautifulsoup4==4.12.2
lxml==4.9.3

# Environment
python-dotenv==1.0.0
setuptools==69.0.2

# SQLite for ChromaDB
pysqlite3-binary==0.5.2

# AI - CrewAI will handle langchain dependencies
numpy==1.26.2
openai==1.68.2
crewai[tools]==0.159.0

# Web Research
firecrawl-py==0.0.16

# Logging
structlog==23.2.0

# Security
python-jose[cryptography]==3.3.0
EOF

# Step 2: Create a simple startup script
echo "Step 2: Creating startup script..."
cat > startup.sh << 'EOF'
#!/bin/bash
cd /home/site/wwwroot
export __import__hook__=pysqlite3
export CHROMA_SQLITE_IMPL=pysqlite3
exec gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 1 --worker-class uvicorn.workers.UvicornWorker app.main:app
EOF
chmod +x startup.sh

# Step 3: Configure Azure App Service for proper build
echo "Step 3: Configuring Azure App Service..."
az webapp config appsettings set \
  --resource-group TheWell-App-East \
  --name well-intake-api \
  --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  ENABLE_ORYX_BUILD=true \
  PYTHON_ENABLE_GUNICORN_MULTIWORKERS=true \
  WEBSITES_ENABLE_APP_SERVICE_STORAGE=true \
  WEBSITE_RUN_FROM_PACKAGE=0 \
  --output none

# Step 4: Set the startup command
echo "Step 4: Setting startup command..."
az webapp config set \
  --resource-group TheWell-App-East \
  --name well-intake-api \
  --generic-configurations '{"appCommandLine": "bash startup.sh"}' \
  --output none

# Step 5: Create deployment package
echo "Step 5: Creating deployment package..."
rm -f final-deploy.zip
zip -r final-deploy.zip . \
  -i "*.py" "*.txt" "*.sh" "*.json" "*.yaml" "*.xml" "*.html" "*.js" \
  -i "app/*" "static/*" "addin/*" \
  -x "zoho/*" "venv/*" "__pycache__/*" "*.pyc" ".git/*" "test_*.py" \
  -x "deploy*.zip" "logs/*" "temp/*" ".env*"

echo "Package size: $(du -h final-deploy.zip | cut -f1)"

# Step 6: Deploy
echo "Step 6: Deploying to Azure..."
az webapp deploy \
  --resource-group TheWell-App-East \
  --name well-intake-api \
  --src-path final-deploy.zip \
  --type zip \
  --restart true \
  --async false

echo "========================================"
echo "Deployment complete!"
echo "Wait 2-3 minutes for the app to start."
echo ""
echo "Check status with:"
echo "  curl https://well-intake-api.azurewebsites.net/health"
echo ""
echo "View logs with:"
echo "  az webapp log tail --resource-group TheWell-App-East --name well-intake-api"
echo "========================================"