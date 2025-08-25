# Azure App Service Deployment Instructions

## Prerequisites
- Azure CLI installed and logged in
- Access to TheWell-App-East resource group
- Python 3.12 runtime selected in Azure App Service

## Deployment Steps

### 1. Deploy the Package

```bash
# Deploy using ZIP deployment
az webapp deploy \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --src-path deploy.zip \
    --type zip

# Set the startup command
az webapp config set \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --startup-file "bash startup.sh"
```

### 2. Configure Environment Variables

```bash
# Set required environment variables
az webapp config appsettings set \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --settings \
    WEBSITES_PORT=8000 \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    PYTHON_ENABLE_WORKER_EXTENSIONS=1 \
    WEBSITE_RUN_FROM_PACKAGE=0
```

### 3. Monitor Deployment

```bash
# Watch deployment logs
az webapp log tail \
    --resource-group TheWell-App-East \
    --name well-intake-api

# Check deployment status
az webapp show \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --query state
```

### 4. Verify Deployment

```bash
# Test health endpoint
curl https://well-intake-api.azurewebsites.net/health

# Check API documentation
curl https://well-intake-api.azurewebsites.net/docs
```

### 5. Troubleshooting

If deployment fails:

1. Check logs:
```bash
az webapp log download \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --log-file app-logs.zip
```

2. SSH into the container:
```bash
az webapp ssh \
    --resource-group TheWell-App-East \
    --name well-intake-api
```

3. Run verification script manually:
```bash
python verify_imports.py
```

4. Try fallback installer:
```bash
python fallback_installer.py
```

## Package Contents

- **startup.sh**: Main startup script
- **scripts/deploy.sh**: Staged dependency installation
- **requirements_stage*.txt**: Staged requirement files
- **verify_imports.py**: Import verification script
- **fallback_installer.py**: Fallback for problematic packages
- **wheels/**: Pre-built wheels directory
- **app/**: Application code
- **addin/**: Outlook add-in files

## Important Notes

1. The deployment uses staged installation to avoid dependency conflicts
2. SQLite is overridden with pysqlite3-binary for ChromaDB compatibility
3. Gunicorn with Uvicorn workers handles the ASGI application
4. Deployment script runs only once (creates marker file)
5. All logs are sent to stdout for Azure monitoring

## Rollback Procedure

If you need to rollback:

```bash
# List deployment history
az webapp deployment list \
    --resource-group TheWell-App-East \
    --name well-intake-api

# Rollback to previous deployment
az webapp deployment rollback \
    --resource-group TheWell-App-East \
    --name well-intake-api
```
