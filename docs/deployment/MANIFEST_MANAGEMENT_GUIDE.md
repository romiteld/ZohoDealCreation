# Outlook Add-in Manifest Management Guide

## Overview
This comprehensive guide covers updating, refreshing, and managing the Outlook add-in manifest for the Well Intake API system.

## Problem: Microsoft Caches Old Manifest URLs

When you move from Azure App Services to Azure Container Apps, Microsoft's add-in infrastructure continues to cache the old manifest and server URLs, causing your add-in to point to the old (now defunct) deployment.

## Current Manifest Information

### Latest Version: 1.1.0.1
- **Manifest URL**: `https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/manifest.xml`
- **API Endpoint**: `well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io`

### Recent Changes in Version 1.1.0.x
1. **API Endpoints** - Updated to point to Azure Container Apps
2. **JavaScript Files** - Corrected API URLs and authentication
3. **Enhanced Features** - GPT-5-mini support with 400K context window
4. **Security** - Proper API key configuration

### Previous Issues Fixed
- ❌ Old: API calls were going to `well-zoho-oauth.azurewebsites.net`
- ✅ New: API calls now go to current Container Apps endpoint
- ❌ Old: Missing API key in JavaScript files
- ✅ New: API key properly configured

## Quick Update Process

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

Choose the appropriate method based on your access level and requirements:

## Update Methods

### Option A: Remove and Re-add (Fastest - Personal Testing)

**Best for**: Individual users, quick testing, immediate deployment

1. Go to [Outlook Web](https://outlook.office.com)
2. Click **Get Add-ins** → **My Add-ins** → **Custom Add-ins**
3. Find "The Well - Send to Zoho" and click **Remove**
4. Clear browser cache:
   - Windows/Linux: `Ctrl + Shift + Delete`
   - Mac: `Cmd + Shift + Delete`
5. Add the add-in again from URL:
   ```
   https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/manifest.xml
   ```

### Option B: Microsoft 365 Admin Center (Organization-wide)

**Best for**: Organization-wide deployment, managed rollout

1. Go to [Microsoft 365 Admin Center](https://admin.microsoft.com)
2. Navigate to **Settings** → **Integrated apps**
3. Find **"The Well - Send to Zoho"** in the list
4. Click on the app and select **Update**
5. Upload the new manifest from:
   ```
   https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/manifest.xml
   ```
6. Review and approve the update
7. Wait 6-24 hours for propagation to all users

### Option C: Outlook Web Manual Update

**Best for**: Personal updates when admin center isn't available

1. Open [Outlook Web](https://outlook.office.com)
2. Click the **Apps** icon in the left sidebar
3. Click **Manage my apps**
4. Find **"The Well - Send to Zoho"** and click **Remove**
5. Click **Add apps** → **Add a custom app** → **Add from URL**
6. Enter the manifest URL:
   ```
   https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/manifest.xml
   ```
7. Click **Install**

### Option D: PowerShell Deployment (IT Admins)

**Best for**: Automated deployment, scripted updates

```powershell
# Connect to Exchange Online
Connect-ExchangeOnline

# Remove old add-in (if exists)
Get-App -OrganizationApp | Where-Object {$_.DisplayName -eq "The Well - Send to Zoho"} | Remove-App

# Install new version
New-App -OrganizationApp -Url "https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/manifest.xml"
```

## Verification Steps

### 4. Verify Correct Deployment

Run the test script to confirm all endpoints are working:
```bash
python3 test_container_deployment.py
```

Expected output:
- ✓ All Container Apps URLs responding
- ✓ Manifest accessible and valid
- ✓ API endpoints responding with correct authentication
- ✓ Add-in functions properly in Outlook

### Manual Verification Checklist

1. **Manifest Accessibility**:
   ```bash
   curl -I https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/manifest.xml
   # Should return 200 OK
   ```

2. **API Health Check**:
   ```bash
   curl https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io/health
   # Should return {"status": "healthy"}
   ```

3. **Add-in Functionality**:
   - Open Outlook (web or desktop)
   - Verify "Send to Zoho" button appears in ribbon
   - Test email processing functionality
   - Check that processed emails create Zoho records

## Troubleshooting

### Common Issues

1. **"Add-in not loading"**
   - Clear browser cache completely
   - Try incognito/private browsing mode
   - Verify manifest URL is accessible

2. **"Old functionality still appears"**
   - Microsoft's cache hasn't cleared (wait 24-48 hours)
   - Force refresh by removing and re-adding
   - Check that you're using the correct manifest URL

3. **"API calls failing"**
   - Verify API key is properly configured
   - Check that Container Apps endpoint is responsive
   - Review Application Insights for error logs

4. **"Manifest validation errors"**
   - Check manifest XML syntax
   - Verify all URLs are accessible
   - Ensure version number has been incremented

### Emergency Rollback

If the new version has issues:

1. **Revert to Previous Version**:
   ```bash
   # Manually edit manifest version back
   # Redeploy with deploy.sh
   ```

2. **Quick Fix Deployment**:
   ```bash
   # Fix the issue and deploy immediately
   ./deploy.sh
   ```

## Best Practices

1. **Version Management**:
   - Always increment version numbers for manifest changes
   - Use semantic versioning (major.minor.patch.build)
   - Document changes in deployment notes

2. **Testing**:
   - Test in personal Outlook before organization-wide deployment
   - Verify all endpoints before updating manifests
   - Use staging environment for major changes

3. **Communication**:
   - Notify users of upcoming changes
   - Provide clear instructions for updates
   - Set expectations for propagation time

4. **Monitoring**:
   - Monitor Application Insights during deployments
   - Track user adoption of new versions
   - Set up alerts for manifest accessibility issues

## Related Documentation

- [Production Readiness](./PRODUCTION_READINESS.md) - Complete deployment status
- [M365 Troubleshooting](./m365_troubleshoot_commands.md) - Microsoft 365 diagnostic commands
- [Outlook Troubleshooting](./outlook_troubleshoot_commands.md) - Outlook-specific debugging