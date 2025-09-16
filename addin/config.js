/**
 * Configuration file for the Outlook Add-in
 * 
 * IMPORTANT: API credentials are stored in .env.local file
 * The API key should NEVER be exposed in client-side code in production.
 * 
 * For production deployment:
 * 1. API key is stored in .env.local (not committed to version control)
 * 2. Consider implementing a server-side proxy to add API key headers
 * 3. Or use Azure AD authentication for more secure access
 */

// Production configuration - Using Azure Container Apps directly
// Note: Changed from Azure Front Door to Container Apps URL to avoid CSP violations
window.API_BASE_URL = 'https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io';

// API Key - Should be injected during deployment or handled server-side
// WARNING: Never hardcode API keys in client-side code
// For now, using a placeholder that will be replaced during deployment
window.API_KEY = '';

// Note: Since browser JavaScript cannot directly access .env.local,
// you need either:
// 1. A build process that injects the value from .env.local
// 2. A server-side proxy that adds the API key header
// 3. Azure AD authentication for the add-in

/**
 * Configuration instructions for deployment:
 * 
 * 1. Replace the empty API_KEY value with your actual API key
 * 2. This file should be served alongside commands.js
 * 3. Ensure this file is loaded before commands.js in any HTML pages
 * 
 * Security note: Never commit the actual API key to source control.
 * Use environment-specific deployment processes to inject the key.
 */