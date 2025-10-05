# 🔧 FIX: Remove Old orangedesert URL Cache

## ⚠️ The Problem
You're seeing `well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io` which is the **OLD** Container App URL that no longer exists.

## ✅ The Correct URLs

### Use These URLs Instead:
- **Primary**: `https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io`
- **Front Door**: `https://well-intake-api-dnajdub4azhjcgc3.z03.azurefd.net`

## 🚀 Quick Fix Steps

### 1. Clear Outlook Add-in Cache
```powershell
# Windows - Run in PowerShell as Administrator
Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef" -Recurse | Remove-Item -Force -Recurse
Get-ChildItem -Path "$env:LOCALAPPDATA\Packages\Microsoft.Office.Desktop_8wekyb3d8bbwe\LocalCache\Local\Microsoft\Office\16.0\Wef" -Recurse | Remove-Item -Force -Recurse
```

### 2. Remove Old Add-in from Outlook
1. Open Outlook
2. Go to **Get Add-ins** → **My add-ins**
3. Find "The Well - Send to Zoho"
4. Click the three dots (...) → **Remove**
5. Restart Outlook

### 3. Clear Office Cache
```powershell
# Clear all Office caches
Remove-Item -Path "$env:LOCALAPPDATA\Microsoft\Office\*" -Recurse -Force -ErrorAction SilentlyContinue
```

### 4. Clear Browser Cache (if using Outlook Web)
- Press `Ctrl + Shift + Delete`
- Select "Cached images and files"
- Clear for "All time"

### 5. Re-install with Correct URL
1. Open Outlook
2. Go to **Get Add-ins** → **My add-ins** → **Add from URL**
3. Enter the NEW URL:
   ```
   https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/manifest.xml
   ```
4. Click **Install**

## 🔍 Verify Installation

After reinstalling, check that the add-in is using the correct URL:

1. In Outlook, right-click on the "Send to Zoho" button
2. Select "Inspect" or "Developer Tools"
3. Check the Network tab - all requests should go to:
   - `wittyocean-dfae0f9b` (CORRECT) ✅
   - NOT `orangedesert-c768ae6e` (OLD) ❌

## 💡 Alternative: Direct File Installation

If URL installation still shows old cache, install from file:

1. Download the manifest:
   ```bash
   curl -o manifest.xml https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/manifest.xml
   ```

2. In Outlook:
   - **Get Add-ins** → **My add-ins** → **Add from File**
   - Browse to downloaded `manifest.xml`
   - Click **Install**

## 🛠️ Nuclear Option: Complete Office Reset

If all else fails:

1. Uninstall the add-in
2. Close all Office apps
3. Run as Administrator:
   ```powershell
   # Reset Office
   cd "C:\Program Files\Microsoft Office\root\Office16"
   .\outlook.exe /resetnavpane
   .\outlook.exe /cleanviews
   ```
4. Restart computer
5. Reinstall add-in with new URL

## ✅ Success Indicators

You'll know it's working when:
- No more "server IP address could not be found" errors
- Add-in loads successfully
- Network requests go to `wittyocean` URLs
- Version shows as 1.5.0 in the manifest

## 📞 Still Having Issues?

The add-in IS deployed and working at the new URL. The issue is purely local caching.

Test that it's working:
```bash
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
# Should return: {"status":"healthy","version":"1.5.0","timestamp":"..."}
```

If this curl command works but Outlook doesn't, it's 100% a cache issue on your local machine.