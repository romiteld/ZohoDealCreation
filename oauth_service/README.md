# OAuth Service with Reverse Proxy

## Overview
Enhanced OAuth service that provides:
1. Zoho OAuth token refresh functionality
2. Reverse proxy to Container Apps API
3. Automatic API key injection
4. Rate limiting and circuit breaker protection

## Features

### OAuth Endpoints
- `GET /health` - Health check with proxy status
- `GET|POST /oauth/token` - Get or refresh Zoho access token

### Reverse Proxy Endpoints
- `/api/*` - Proxies to Container Apps API with authentication
- `/proxy/health` - Direct backend health check
- `/proxy/test/kevin-sullivan` - Test endpoint proxy
- `/manifest.xml` - Outlook Add-in manifest
- `/static/*` - Static files for Outlook Add-in

### Security Features
- Automatic API key injection (from .env.local)
- Rate limiting (100 requests/minute per IP)
- Circuit breaker (opens after 5 failures)
- Request forwarding headers (X-Forwarded-*)
- CORS support

## Configuration

All configuration is loaded from `.env.local`:

```bash
# Required OAuth settings (already in your .env.local)
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REFRESH_TOKEN=...

# API Key (already in your .env.local)
API_KEY=...

# Optional proxy settings
MAIN_API_URL=https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io
PROXY_TIMEOUT=30
PROXY_RATE_LIMIT=100
```

## Deployment

### Quick Deploy
```bash
# Make deployment script executable
chmod +x deploy.sh

# Run deployment (requires Azure CLI)
./deploy.sh
```

### Manual Deploy
1. Create deployment package:
   ```bash
   zip -r oauth_proxy_deploy.zip oauth_app_with_proxy.py requirements.txt startup.txt .env.local
   ```

2. Deploy to Azure App Service:
   ```bash
   az webapp deployment source config-zip \
     --resource-group TheWell-App-East \
     --name well-zoho-oauth \
     --src oauth_proxy_deploy.zip
   ```

## Testing

### Local Testing
```bash
# Test configuration loading
python test_local.py

# Run Flask app locally
python oauth_app_with_proxy.py
```

### Production Testing
```bash
# Run full test suite
python test_proxy.py
```

### Test Endpoints
- Health: `https://well-zoho-oauth.azurewebsites.net/health`
- OAuth Token: `https://well-zoho-oauth.azurewebsites.net/oauth/token`
- Proxy Health: `https://well-zoho-oauth.azurewebsites.net/proxy/health`
- API Proxy: `https://well-zoho-oauth.azurewebsites.net/api/intake/email`

## Architecture

```
Client Request → OAuth Service (App Service)
                       ↓
                 [Add API Key]
                 [Add Zoho Token if needed]
                       ↓
              Container Apps API
```

## Benefits

1. **Single Entry Point**: All API calls through one URL
2. **Automatic Authentication**: API key handled server-side
3. **Token Management**: Zoho tokens cached and refreshed
4. **Enhanced Security**: Additional validation layer
5. **Better Monitoring**: Centralized logging
6. **Rate Protection**: Built-in rate limiting and circuit breaker

## Monitoring

View logs in Azure Portal or CLI:
```bash
az webapp log tail --resource-group TheWell-App-East --name well-zoho-oauth
```

## Rollback

If issues occur:
```bash
# List deployments
az webapp deployment list --resource-group TheWell-App-East --name well-zoho-oauth

# Rollback to previous version
az webapp deployment rollback --resource-group TheWell-App-East --name well-zoho-oauth
```