/**
 * Configuration file for the Outlook Add-in
 * This file should be customized during deployment with the actual API key
 */

// Production configuration
window.API_BASE_URL = 'https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io';

// API Key - This should be set during deployment
// In production, this value should be replaced with the actual API key
// or loaded from a secure configuration service
window.API_KEY = 'e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384'; // Set this value during deployment

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