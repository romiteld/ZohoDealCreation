# Outlook Add-in Manifest Update Guide

## 🚨 IMPORTANT: You need to update the manifest in Outlook

The manifest has been updated with critical changes that require re-installation in Outlook.

## What Changed in Version 1.1.0.0

### ✅ Critical Updates:
1. **API Endpoints** - Now points to Azure Container Apps (`well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io`)
2. **JavaScript Files** - Updated with correct API URLs and authentication
3. **Version Number** - Updated from 1.0.0.0 to 1.1.0.0
4. **Enhanced Features** - GPT-5-mini support with 400K context window

### 📍 Previous Issues Fixed:
- ❌ Old: API calls were going to `well-zoho-oauth.azurewebsites.net`
- ✅ New: API calls now go to `well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io`
- ❌ Old: Missing API key in JavaScript files
- ✅ New: API key properly configured

## How to Update the Manifest

### Option 1: Update in Microsoft 365 Admin Center (Organization-wide)

1. Go to [Microsoft 365 Admin Center](https://admin.microsoft.com)
2. Navigate to **Settings** → **Integrated apps**
3. Find **"The Well - Send to Zoho"** in the list
4. Click on the app and select **Update**
5. Upload the new manifest from:
   ```
   https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml
   ```
6. Review and approve the update
7. The update will roll out to all users

### Option 2: Update in Outlook Web (Personal Testing)

1. Open [Outlook Web](https://outlook.office.com)
2. Click the **Apps** icon in the left sidebar
3. Click **Manage my apps**
4. Find **"The Well - Send to Zoho"** and click **Remove**
5. Click **Add apps** → **Add a custom app** → **Add from URL**
6. Enter the manifest URL:
   ```
   https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml
   ```
7. Click **Install**

### Option 3: Update via PowerShell (For IT Admins)

```powershell
# Connect to Exchange Online
Connect-ExchangeOnline

# Remove old version
Remove-App -Identity "d2422753-f7f6-4a4a-9e1e-7512f37a50e5"

# Install new version
New-App -Url "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml"
```

## Verification Steps

After updating, verify the add-in is working correctly:

1. **Open an email** in Outlook
2. **Click "The Well - Send to Zoho"** button in the ribbon
3. **Check the taskpane** loads correctly
4. **Test sending an email** to Zoho
5. **Verify in browser console** (F12):
   - API calls should go to `well-intake-api.salmonsmoke-78b2d936`
   - No CORS errors
   - No 404 errors

## Troubleshooting

### If the old version persists:
1. Clear Outlook cache:
   - Windows: `%LocalAppData%\Microsoft\Office\16.0\Wef\`
   - Mac: `~/Library/Containers/com.microsoft.Outlook/Data/Library/Caches/`
2. Sign out and sign back into Outlook
3. Wait 15-30 minutes for cache to refresh

### If API calls fail:
- Check browser console for errors
- Verify API endpoint: `https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/health`
- Should return: `{"status": "healthy"}`

### If the button doesn't appear:
1. Check if add-in is enabled in Outlook settings
2. Try different Outlook client (Web vs Desktop)
3. Check with IT admin if add-ins are allowed

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0.0 | 2025-08-25 | Initial release |
| 1.1.0.0 | 2025-08-29 | - Fixed API endpoints<br>- Added GPT-5-mini support<br>- Enhanced with Azure services<br>- Fixed authentication |

## Support

For issues or questions:
- **API Health Check**: https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/health
- **Manifest URL**: https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/manifest.xml
- **Support**: daniel.romitelli@emailthewell.com

## Important Notes

⚠️ **Users may need to wait 15-30 minutes** after update for changes to take effect due to Office caching.

⚠️ **The App ID remains the same** (`d2422753-f7f6-4a4a-9e1e-7512f37a50e5`) so existing permissions and settings are preserved.

✅ **No data loss** - All existing configurations and settings will be maintained.