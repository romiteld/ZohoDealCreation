The Well – Edge Extension (MV3)

Load Unpacked

1. Open Edge → edge://extensions/
2. Toggle Developer mode.
3. Click Load unpacked and select extensions/edge/.
4. Pin the extension. Open Outlook Web (outlook.office.com), open a message, click the extension button, then Send current email.

Notes

- DOM extraction is minimal and may need tuning as OWA updates. We can move to Microsoft Graph later via MSAL.
- Backend base URL is configured in popup.html via window.API_BASE_URL.


