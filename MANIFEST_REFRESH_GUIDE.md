# Microsoft Outlook Add-in Manifest Refresh Guide

## Problem: Microsoft Caches Old Manifest URLs

When you move from Azure App Services to Azure Container Apps, Microsoft's add-in infrastructure continues to cache the old manifest and server URLs, causing your add-in to point to the old (now defunct) deployment.

## Quick Solution Steps

### 1. Update Manifest Version
```bash
# Increment the version number automatically
python3 update_manifest_version.py
```

### 2. Deploy New Version
```bash
# Run the comprehensive deployment script
./deploy.sh
```

### 3. Force Microsoft to Refresh

#### Option A: Remove and Re-add (Fastest)
1. Go to [Outlook Web](https://outlook.office.com)
2. Click **Get Add-ins** → **My Add-ins** → **Custom Add-ins**
3. Find "The Well - Send to Zoho" and click **Remove**
4. Clear browser cache:
   - Windows/Linux: `Ctrl + Shift + Delete`
   - Mac: `Cmd + Shift + Delete`
5. Add the add-in again from URL:
   ```
   https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml
   ```

#### Option B: Organizational Deployment (IT Admin)
1. Go to [Microsoft 365 Admin Center](https://admin.microsoft.com)
2. Navigate to **Settings** → **Integrated apps**
3. Find "The Well - Send to Zoho"
4. Click **Update** and upload the new manifest
5. Wait 6-24 hours for propagation

### 4. Verify Correct Deployment

Run the test script to confirm all endpoints are working:
```bash
python3 test_container_deployment.py
```

Expected output:
- ✓ All Container Apps URLs responding
- ✓ No requests to old azurewebsites.net
- ✓ Manifest contains correct URLs
- ✓ Static files loading correctly

### 5. Test in Outlook

1. Open any email in Outlook Web
2. Click "Send to Zoho" button
3. Open browser Developer Tools (F12)
4. Check Network tab - all requests should go to:
   ```
   https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io
   ```

## Troubleshooting

### Symptom: Still Seeing Old URLs
- **Solution**: The manifest is still cached. Increment version again and remove/re-add

### Symptom: 404 Errors on taskpane.js
- **Solution**: Docker image needs rebuild. Run `./deploy.sh`

### Symptom: API Returns 403 Forbidden
- **Solution**: Check API_KEY in .env.local matches Container Apps configuration

### Symptom: Outlook Desktop Not Updating
- **Solution**: Desktop clients can take 24-48 hours. Use Outlook Web for immediate testing

## Current URLs

### Production Container Apps
- API: https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io
- Health: https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/health
- Manifest: https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml

### Old App Services (Should NOT be used)
- ❌ https://well-intake-api.azurewebsites.net (deprecated)

## Automated Deployment Process

The `deploy.sh` script handles:
1. Database migrations for correction learning
2. Azure Blob Storage container setup
3. Manifest version increment
4. Docker image build and push
5. Container Apps deployment
6. Health check validation
7. Comprehensive testing

## Manual Testing Checklist

After deployment, verify:
- [ ] Health endpoint returns 200 OK
- [ ] Manifest.xml accessible and contains Container Apps URLs
- [ ] Static files load (commands.js, taskpane.js, config.js)
- [ ] Icons load correctly
- [ ] API accepts test email with API key
- [ ] Kevin Sullivan test endpoint works
- [ ] No CORS errors in browser console
- [ ] Taskpane opens with email data
- [ ] Natural language corrections work
- [ ] Custom fields can be added
- [ ] Send to Zoho creates records
- [ ] Progress indicators display correctly

## Version History

Track manifest versions to ensure updates:
```bash
# Check current version
grep "<Version>" addin/manifest.xml

# View deployment history
az containerapp revision list \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --output table
```

## Support

For issues with manifest refresh:
1. Check Container Apps logs:
   ```bash
   az containerapp logs show \
     --name well-intake-api \
     --resource-group TheWell-Infra-East \
     --follow
   ```

2. Verify all services:
   ```bash
   python3 test_container_deployment.py
   ```

3. Database status:
   ```bash
   python3 initialize_database.py
   ```