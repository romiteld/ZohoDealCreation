# OAuth Service Reverse Proxy Deployment Guide

## Overview
This guide covers deploying the enhanced OAuth service with reverse proxy capabilities to Azure App Service.

## Deployment Options

### Option 1: Python Flask Application (Recommended)
Deploy the enhanced OAuth service with built-in reverse proxy capabilities.

### Option 2: IIS URL Rewrite with web.config
Use Azure App Service's IIS URL Rewrite module for Windows App Services.

---

## Option 1: Flask-Based Reverse Proxy Deployment

### Prerequisites
- Azure CLI installed
- Access to Azure subscription
- API key for Container Apps API

### Step 1: Prepare Environment Configuration

Create `.env.local` file with your configuration:
```bash
# Copy from .env.example
cp .env.example .env.local

# Edit .env.local with your values
```

Required environment variables:
```bash
# Zoho OAuth Configuration
ZOHO_CLIENT_ID=your-zoho-client-id
ZOHO_CLIENT_SECRET=your-zoho-client-secret
ZOHO_REFRESH_TOKEN=your-zoho-refresh-token

# Proxy Configuration
MAIN_API_URL=https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io
MAIN_API_KEY=your-api-key
PROXY_TIMEOUT=30
PROXY_RATE_LIMIT=100
```

### Step 2: Create Deployment Package

```bash
# Create deployment directory
mkdir oauth_proxy_deploy
cd oauth_proxy_deploy

# Copy necessary files
cp ../oauth_app_with_proxy.py .
cp ../requirements.txt .
cp ../.env.local .

# Create startup file for Azure
echo "gunicorn --bind=0.0.0.0 --timeout 600 oauth_app_with_proxy:app" > startup.txt

# Create zip package
zip -r oauth_proxy_deploy.zip .
```

### Step 3: Deploy to Azure App Service

```bash
# Set variables
RESOURCE_GROUP="TheWell-App-East"
APP_NAME="well-zoho-oauth"
LOCATION="eastus"

# Deploy using Azure CLI
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --src oauth_proxy_deploy.zip

# Set environment variables
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --settings @.env.local

# Set Python version
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --python-version 3.11

# Set startup command
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 oauth_app_with_proxy:app"
```

### Step 4: Test Deployment

```bash
# Test health endpoint
curl https://well-zoho-oauth.azurewebsites.net/health

# Test OAuth token endpoint
curl https://well-zoho-oauth.azurewebsites.net/oauth/token

# Test proxy health
curl https://well-zoho-oauth.azurewebsites.net/proxy/health

# Run full test suite
python test_proxy.py
```

---

## Option 2: IIS URL Rewrite Deployment

### Step 1: Enable Application Request Routing

In Azure Portal:
1. Go to your App Service
2. Navigate to Configuration > Application settings
3. Add setting: `WEBSITE_LOAD_ROOT_CERTIFICATES=*`

### Step 2: Deploy web.config

1. Copy `web.config` to your App Service root
2. Update the Container Apps URL in rewrite rules
3. Deploy via FTP, Git, or ZIP deployment

### Step 3: Configure API Key

Add application setting in Azure Portal:
- Name: `API_KEY`
- Value: `your-api-key`

### Step 4: Test URL Rewrite Rules

```bash
# Test proxy endpoints
curl https://well-zoho-oauth.azurewebsites.net/api/health
curl https://well-zoho-oauth.azurewebsites.net/manifest.xml
```

---

## Monitoring & Troubleshooting

### View Logs

```bash
# Stream logs
az webapp log tail \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME

# Download logs
az webapp log download \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --log-file logs.zip
```

### Common Issues

1. **502 Bad Gateway**
   - Check API key configuration
   - Verify Container Apps API is running
   - Check network connectivity

2. **Timeout Errors**
   - Increase PROXY_TIMEOUT setting
   - Check Container Apps performance

3. **Rate Limiting**
   - Adjust PROXY_RATE_LIMIT setting
   - Monitor request patterns

4. **Circuit Breaker Open**
   - Check backend service health
   - Review error logs for failure patterns

### Performance Tuning

1. **Gunicorn Workers**
   ```bash
   # Increase workers for higher load
   gunicorn --workers 4 --threads 2 --timeout 600 oauth_app_with_proxy:app
   ```

2. **App Service Scaling**
   - Scale up: Choose higher tier (P1v2, P2v2)
   - Scale out: Add more instances

3. **Caching**
   - OAuth tokens cached for 55 minutes
   - Consider adding response caching for static content

---

## Security Considerations

1. **API Key Protection**
   - Store in Azure Key Vault
   - Use managed identities when possible

2. **Network Security**
   - Enable HTTPS only
   - Configure CORS appropriately
   - Use Azure Front Door for DDoS protection

3. **Rate Limiting**
   - Adjust PROXY_RATE_LIMIT based on usage
   - Monitor for abuse patterns

---

## Rollback Procedure

If issues occur after deployment:

```bash
# Revert to previous version
az webapp deployment list \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME

# Rollback to specific deployment
az webapp deployment rollback \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --deployment-id <deployment-id>
```

---

## Testing Endpoints

After deployment, test these endpoints:

- **Health Check**: `GET /health`
- **OAuth Token**: `GET /oauth/token`
- **Proxy Health**: `GET /proxy/health`
- **API Proxy**: `POST /api/intake/email`
- **Test Endpoint**: `GET /api/test/kevin-sullivan`
- **Manifest**: `GET /manifest.xml`
- **Static Files**: `GET /static/*`

Use the provided `test_proxy.py` script for comprehensive testing.