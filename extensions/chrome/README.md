# The Well – Chrome Extension

## Load unpacked
1. Open Chrome and go to `chrome://extensions`.
2. Enable "Developer mode".
3. Click "Load unpacked" and select this folder: `extensions/chrome`.
4. Pin the extension. Click the icon to open the popup.

## Usage
- Click "Preview" to sign in to Microsoft and fetch the current Outlook Web email.
- Review/edit fields, then click "Send to Zoho".

## Permissions
- Uses `chrome.identity.launchWebAuthFlow` to authenticate to Microsoft (Graph scopes: `User.Read`, `Mail.Read`).
- Calls your API at `window.API_BASE_URL` defined in `popup.html`.


