# GitHub Actions Workflows

## Manifest Cache-Bust & Deploy Workflow

### Overview

The `manifest-cache-bust.yml` workflow provides automated deployment of Outlook add-in manifest changes with intelligent cache-busting and version management.

### Features

- **Automatic Trigger**: Activates on changes to `addin/manifest.xml`, `*.html`, `*.js`, or `*.css` files
- **Smart Versioning**: Auto-increments manifest versions based on change type
- **Cache Management**: Clears Redis cache and warms with new versions
- **Azure Integration**: Builds and deploys to Azure Container Apps
- **Health Checks**: Verifies deployment success and service health
- **Rollback Support**: Automatic rollback on deployment failure

### Required GitHub Secrets

Configure the following secrets in your repository:

```
AZURE_CLIENT_ID        # Azure service principal client ID
AZURE_TENANT_ID        # Azure tenant ID  
AZURE_SUBSCRIPTION_ID  # Azure subscription ID
API_KEY               # API key for cache management endpoints
```

### Setup Instructions

#### 1. Create Azure Service Principal

```bash
# Create service principal with contributor role
az ad sp create-for-rbac --name "github-well-intake-deploy" \
  --role contributor \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID/resourceGroups/TheWell-Infra-East \
  --sdk-auth

# Note the output values for GitHub secrets
```

#### 2. Configure GitHub Secrets

In your repository settings > Secrets and variables > Actions:

- **AZURE_CLIENT_ID**: From service principal output
- **AZURE_TENANT_ID**: From service principal output  
- **AZURE_SUBSCRIPTION_ID**: Your Azure subscription ID
- **API_KEY**: Your Well Intake API key from `.env.local`

#### 3. Grant Container Registry Access

```bash
# Grant ACR pull/push access to service principal
az role assignment create \
  --assignee YOUR_CLIENT_ID \
  --role AcrPush \
  --scope /subscriptions/YOUR_SUBSCRIPTION_ID/resourceGroups/TheWell-Infra-East/providers/Microsoft.ContainerRegistry/registries/wellintakeregistry
```

### Version Management

The workflow uses semantic versioning (MAJOR.MINOR.PATCH.BUILD):

- **Major**: Manifest ID, provider, or requirements changes
- **Minor**: New permissions or extension points
- **Patch**: All other changes (default)
- **Build**: Auto-incremented for cache-busting

### Workflow Stages

#### 1. Detect Changes
- Analyzes git diff to determine change scope
- Sets version increment strategy
- Identifies affected files

#### 2. Increment Version  
- Extracts current version from manifest.xml
- Applies semantic versioning rules
- Updates manifest with new version and cache-busting parameters
- Commits changes back to repository

#### 3. Clear Cache
- Invalidates Redis cache patterns for manifest/add-in files
- Warms cache with common access patterns
- Ensures fresh content delivery

#### 4. Build and Deploy
- Builds optimized Docker image with Buildx
- Pushes to Azure Container Registry with caching
- Updates Azure Container Apps with new image
- Monitors deployment progress

#### 5. Post-Deployment
- Verifies service health and readiness
- Tests manifest and taskpane accessibility
- Warms cache with new versioned URLs
- Runs comprehensive smoke tests

#### 6. Notification
- Reports deployment success/failure
- Provides relevant URLs and version info
- Includes troubleshooting guidance

#### 7. Rollback (on failure)
- Reverts manifest version changes
- Attempts container deployment rollback
- Provides manual intervention guidance

### Manual Workflow Triggers

You can manually trigger the workflow with custom version increments:

1. Go to Actions > Manifest Cache-Bust & Deploy
2. Click "Run workflow"
3. Select version increment type (patch/minor/major)
4. Click "Run workflow"

### Troubleshooting

#### Common Issues

**1. Authentication Errors**
```
Error: AADSTS70002: The request body must contain the following parameter: 'client_secret' or 'client_assertion'
```
- Verify `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` secrets
- Ensure service principal has correct permissions

**2. Container Registry Access Denied**
```
Error: denied: access forbidden
```
- Check service principal has `AcrPush` role on container registry
- Verify registry name in workflow matches actual registry

**3. Container App Update Failed**
```
Error: The subscription is not registered to use namespace 'Microsoft.App'
```
- Register Container Apps provider: `az provider register --namespace Microsoft.App`

**4. Cache Clear Failed**
```
Cache clear failed, continuing...
```
- Verify `API_KEY` secret matches your API key
- Check API endpoint is accessible and healthy
- Cache operations are non-blocking, deployment continues

**5. Health Check Timeouts**
```
Health check failed, retrying...
```
- Container Apps may take time to start
- Workflow retries up to 20 times with 15-second intervals
- Check container logs: `az containerapp logs show --name well-intake-api --resource-group TheWell-Infra-East --follow`

#### Debug Steps

1. **Check workflow logs** for detailed error messages
2. **Verify Azure resources** exist and are accessible
3. **Test API endpoints** manually:
   ```bash
   curl -f https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
   curl -f https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/manifest.xml
   ```
4. **Validate container deployment**:
   ```bash
   az containerapp show --name well-intake-api --resource-group TheWell-Infra-East
   ```

### Monitoring

The workflow provides comprehensive monitoring:

- **Deployment Status**: Real-time deployment progress tracking
- **Health Checks**: Service availability verification  
- **Version Tracking**: Clear before/after version reporting
- **Cache Metrics**: Cache clear/warm operation status
- **Smoke Tests**: End-to-end functionality verification

### Best Practices

1. **Test Changes Locally**: Verify manifest syntax before committing
2. **Small Commits**: Make focused changes for clearer version history  
3. **Monitor Deployments**: Check workflow results and health endpoints
4. **Cache Awareness**: Understand that cache-busting ensures fresh content
5. **Rollback Preparedness**: Keep previous versions accessible for emergencies

### Integration with Development Workflow

The workflow integrates seamlessly with your development process:

1. **Make Changes**: Edit manifest.xml or add-in files
2. **Commit & Push**: Normal git workflow triggers automation
3. **Automatic Processing**: Workflow handles versioning and deployment
4. **Verification**: Check health endpoints and manifest accessibility
5. **User Impact**: Outlook add-in users get fresh content automatically

### Cache Strategy

The workflow implements intelligent caching:

- **Invalidation**: Clears old cached versions
- **Warming**: Pre-loads new versions for faster access
- **TTL Management**: Ensures cache freshness with time-based expiration
- **Pattern Matching**: Targets specific cache keys for efficiency

This ensures users always get the latest add-in version while maintaining optimal performance.