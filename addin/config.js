/**
 * Configuration file for the Outlook Add-in
 * This file should be customized during deployment with the actual API key
 */

// Production configuration
window.API_BASE_URL = 'https://well-intake-api.azurewebsites.net';

// API Key - This should be set during deployment
// In production, this value should be replaced with the actual API key
// or loaded from a secure configuration service
window.API_KEY = ''; // Set this value during deployment

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