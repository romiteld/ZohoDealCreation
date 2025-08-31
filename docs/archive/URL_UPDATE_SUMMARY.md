# Container App URL Update Summary

## Date: 2025-08-30

## Changes Made

Updated all references from the old Container App URL to the new one:
- **Old URL**: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io`
- **New URL**: `https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io`

## Files Updated

### 1. Outlook Add-in Manifest
- `/home/romiteld/outlook/addin/manifest.xml`
  - Updated IconUrl, HighResolutionIconUrl
  - Updated AppDomain
  - Updated SourceLocation
  - Updated all resource URLs (Commands.Url, Taskpane.Url, Icon URLs)

### 2. Environment Configuration Files
- `/home/romiteld/outlook/.env.local`
  - Updated DATABASE_URL to: `postgresql://[REDACTED]@well-intake-db.postgres.database.azure.com:5432/wellintake?sslmode=require`
  - Updated AZURE_REDIS_CONNECTION_STRING to: `rediss://:[REDACTED]@well-intake-cache-v2.redis.cache.windows.net:6380`

- `/home/romiteld/outlook/voice-ui/.env.local`
  - Updated API_ENDPOINT

### 3. JavaScript Configuration Files
- `/home/romiteld/outlook/addin/config.js`
- `/home/romiteld/outlook/addin/taskpane.js`
- `/home/romiteld/outlook/addin/commands.html`
- `/home/romiteld/outlook/addin/commands.js`
- `/home/romiteld/outlook/voice-ui/public/config.js`
- `/home/romiteld/outlook/voice-ui/public/auth-config.js`
- `/home/romiteld/outlook/voice-ui/public/index.html`
- `/home/romiteld/outlook/voice-ui/server.js`

### 4. Python Test Scripts
- `/home/romiteld/outlook/test_container_deployment.py`
- `/home/romiteld/outlook/test_addin_endpoints.py`
- `/home/romiteld/outlook/update_manifest_version.py`
- `/home/romiteld/outlook/check_zoho_now.py`
- `/home/romiteld/outlook/oauth_service/oauth_proxy_deploy/oauth_app_with_proxy.py`
- `/home/romiteld/outlook/oauth_service/oauth_app_with_proxy.py`

### 5. Deployment Configuration
- `/home/romiteld/outlook/deployment/container_apps_config.yaml`
- `/home/romiteld/outlook/deploy.sh`
- `/home/romiteld/outlook/oauth_service/.env.example`

### 6. Documentation
- `/home/romiteld/outlook/CLAUDE.md` - Updated production URLs section

## Next Steps

1. **Deploy the updated manifest**: 
   - The manifest needs to be redeployed to Azure Container Apps
   - Run: `./deploy.sh` to build and deploy with the new URLs

2. **Update Outlook Add-in**:
   - Remove the existing add-in from Outlook
   - Clear browser cache
   - Re-add the add-in using the new manifest URL: 
     `https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/manifest.xml`

3. **Test the deployment**:
   - Run: `python test_container_deployment.py`
   - Run: `python test_addin_endpoints.py`
   - Verify health endpoint: `https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/health`

4. **Update any external references**:
   - Update any bookmarks or documentation that reference the old URL
   - Update any external services that may be configured with the old endpoint

## Connection String Updates

### Database (PostgreSQL)
- **Old**: `postgresql://[REDACTED]@c-well-intake-db.kaj3v6jxajtw66.postgres.cosmos.azure.com:5432/citus?sslmode=require`
- **New**: `postgresql://[REDACTED]@well-intake-db.postgres.database.azure.com:5432/wellintake?sslmode=require`

### Redis Cache
- **Old**: `rediss://:[REDACTED]@well-intake-cache.redis.cache.windows.net:6380`
- **New**: `rediss://:[REDACTED]@well-intake-cache-v2.redis.cache.windows.net:6380`

## Notes

- All JavaScript files now point to the new Container App URL
- All Python scripts have been updated with the new endpoint
- The manifest version remains at 1.1.0.0 (no version bump needed for URL changes)
- Some documentation files (README.md, various guides) still contain the old URL as historical reference but these don't affect functionality