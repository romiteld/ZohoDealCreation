# Azure App Service Deployment Guide
## Optimized Deployment Package for Well Intake API

This guide provides a comprehensive, multi-stage deployment approach that handles dependency installation issues on Azure App Service Python 3.12 runtime.

## 🚀 Quick Start

```bash
# 1. Create optimized deployment package
python azure_deploy_setup.py

# 2. Deploy to Azure
bash deploy_to_azure.sh

# 3. If issues arise, troubleshoot
python azure_troubleshoot.py
```

## 📦 Package Components

### Core Scripts

1. **`azure_deploy_setup.py`** - Main deployment package creator
   - Creates staged requirements files
   - Generates deployment scripts
   - Builds optimized `deploy.zip`
   - Handles SQLite override for ChromaDB

2. **`deploy_to_azure.sh`** - Automated deployment script
   - Checks Azure CLI and login
   - Verifies resources
   - Deploys package
   - Monitors deployment

3. **`optimize_requirements.py`** - Requirements optimizer
   - Creates compatible dependency versions
   - Resolves conflicts
   - Generates multiple requirement variants

4. **`azure_troubleshoot.py`** - Diagnostic and repair tool
   - Checks app status
   - Identifies issues
   - Applies automatic fixes
   - Generates reports

## 🔧 Deployment Process

### Stage 1: Preparation

```bash
# Optimize requirements for Azure compatibility
python optimize_requirements.py

# This creates:
# - requirements_optimized.txt (production-ready)
# - requirements_minimal.txt (testing)
# - check_dependencies.py (conflict checker)
```

### Stage 2: Package Creation

```bash
# Create deployment package with staged installation
python azure_deploy_setup.py

# This creates:
# - azure_deploy/ directory with staged requirements
# - deploy.zip (ready for Azure)
# - Startup scripts with proper configuration
# - Verification scripts
```

### Stage 3: Deployment

```bash
# Deploy to Azure App Service
bash deploy_to_azure.sh

# Or manually:
az webapp deploy \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --src-path deploy.zip \
    --type zip
```

### Stage 4: Verification

```bash
# Check deployment status
bash deploy_to_azure.sh --status

# Monitor logs
bash deploy_to_azure.sh --logs

# Run troubleshooter if issues
python azure_troubleshoot.py
```

## 🏗️ Architecture

### Staged Dependency Installation

The deployment uses a 4-stage installation process to avoid conflicts:

**Stage 1: Core Dependencies**
- setuptools, pip, wheel
- FastAPI, Uvicorn, Gunicorn
- Basic utilities

**Stage 2: Database & Azure**
- Azure Storage SDK
- PostgreSQL drivers
- pgvector extension

**Stage 3: AI/ML Framework**
- NumPy (required first)
- OpenAI SDK
- Langchain ecosystem (specific order)

**Stage 4: Application Specific**
- CrewAI
- Firecrawl
- Additional tools

### Key Features

1. **SQLite Override**: Handles ChromaDB compatibility
   ```python
   import pysqlite3
   sys.modules['sqlite3'] = pysqlite3
   ```

2. **Retry Logic**: Each stage retries 3 times on failure

3. **Verification**: Tests all imports after installation

4. **Fallback**: Alternative installation if main process fails

## 🔍 Troubleshooting

### Common Issues and Solutions

#### 1. Module Import Errors

**Issue**: `ModuleNotFoundError: No module named 'langchain'`

**Solution**:
```bash
# Redeploy with optimized requirements
python azure_deploy_setup.py
bash deploy_to_azure.sh
```

#### 2. Timeout During Startup

**Issue**: Application times out during initialization

**Solution**:
```bash
# Increase timeout
az webapp config set \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --startup-file "timeout 900 bash startup.sh"
```

#### 3. CrewAI Temperature Error

**Issue**: `temperature must be 1 for GPT-5-mini`

**Solution**: Already handled in optimized code - ensures temperature=1

#### 4. Memory Issues

**Issue**: Out of memory during package installation

**Solution**:
```bash
# Scale up temporarily for deployment
az webapp scale \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --sku P1V2

# Deploy
bash deploy_to_azure.sh

# Scale back down
az webapp scale \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --sku B1
```

### Using the Troubleshooter

```bash
# Run automatic diagnosis
python azure_troubleshoot.py

# The tool will:
# 1. Check Azure CLI access
# 2. Verify app status
# 3. Check configurations
# 4. Test endpoints
# 5. Apply fixes if authorized
# 6. Generate detailed report
```

## 📊 Monitoring

### View Logs

```bash
# Real-time logs
az webapp log tail \
    --resource-group TheWell-App-East \
    --name well-intake-api

# Download logs
az webapp log download \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --log-file logs.zip
```

### SSH Access

```bash
# SSH into container for debugging
az webapp ssh \
    --resource-group TheWell-App-East \
    --name well-intake-api

# Once connected, verify imports:
python verify_imports.py
```

### Test Endpoints

```bash
# Health check
curl https://well-intake-api.azurewebsites.net/health

# API documentation
curl https://well-intake-api.azurewebsites.net/docs

# Test endpoint (requires API key)
curl -X GET "https://well-intake-api.azurewebsites.net/test/kevin-sullivan" \
     -H "X-API-Key: your-api-key"
```

## 🔄 Rollback

If deployment fails:

```bash
# Option 1: Automated rollback
bash deploy_to_azure.sh --rollback

# Option 2: Manual rollback
az webapp deployment rollback \
    --resource-group TheWell-App-East \
    --name well-intake-api
```

## 📝 Environment Variables

Ensure these are set in Azure:

```bash
az webapp config appsettings set \
    --resource-group TheWell-App-East \
    --name well-intake-api \
    --settings \
    API_KEY="your-api-key" \
    OPENAI_API_KEY="sk-..." \
    AZURE_STORAGE_CONNECTION_STRING="..." \
    DATABASE_URL="postgresql://..." \
    ZOHO_OAUTH_SERVICE_URL="https://well-zoho-oauth.azurewebsites.net"
```

## 🎯 Success Indicators

Your deployment is successful when:

1. ✅ Health endpoint returns 200 OK
2. ✅ API documentation loads at /docs
3. ✅ No import errors in logs
4. ✅ Test endpoint processes sample data
5. ✅ CrewAI agents execute without timeout

## 📋 Deployment Checklist

- [ ] Requirements optimized (`python optimize_requirements.py`)
- [ ] Package created (`python azure_deploy_setup.py`)
- [ ] Azure CLI logged in (`az login`)
- [ ] Deployment executed (`bash deploy_to_azure.sh`)
- [ ] Health check passing
- [ ] Logs monitored for errors
- [ ] Test endpoint verified
- [ ] Environment variables set
- [ ] Outlook add-in tested

## 🆘 Support

If issues persist after following this guide:

1. Run the troubleshooter with verbose output
2. Check the generated `troubleshooting_report.txt`
3. Review Azure App Service logs in detail
4. Verify all environment variables are set correctly
5. Test with minimal requirements first

## 📚 Additional Resources

- [Azure App Service Python Documentation](https://docs.microsoft.com/en-us/azure/app-service/configure-language-python)
- [CrewAI Documentation](https://docs.crewai.com/)
- [Langchain Azure Deployment](https://python.langchain.com/docs/deployment/azure)
- [FastAPI on Azure](https://docs.microsoft.com/en-us/azure/app-service/quickstart-python)

---

**Note**: This deployment package is specifically optimized for the Well Intake API with its unique dependencies (CrewAI, Langchain, pgvector) and Azure App Service Python 3.12 runtime in Canada Central region.