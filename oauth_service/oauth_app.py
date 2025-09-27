"""
Zoho OAuth Token Refresh Service for The Well Recruiting
"""
import os
import logging
import requests
from flask import Flask, jsonify, request
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Zoho OAuth Configuration
ZOHO_CLIENT_ID = os.environ.get('ZOHO_CLIENT_ID')
ZOHO_CLIENT_SECRET = os.environ.get('ZOHO_CLIENT_SECRET')
ZOHO_REFRESH_TOKEN = os.environ.get('ZOHO_REFRESH_TOKEN')
ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
ZOHO_API_DOMAIN = "https://www.zohoapis.com"

# Cache for access token
token_cache = {
    'access_token': None,
    'expires_at': None
}

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'zoho-oauth',
        'timestamp': datetime.utcnow().isoformat(),
        'configured': all([ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN])
    })

@app.route('/oauth/token', methods=['GET', 'POST'])
def get_access_token():
    """Get or refresh Zoho access token"""
    try:
        # Check if we have a valid cached token
        if token_cache['access_token'] and token_cache['expires_at']:
            if datetime.utcnow() < token_cache['expires_at']:
                logger.info("Returning cached access token")
                return jsonify({
                    'access_token': token_cache['access_token'],
                    'expires_at': token_cache['expires_at'].isoformat(),
                    'cached': True
                })
        
        # Refresh the token
        logger.info("Refreshing Zoho access token")
        
        if not all([ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN]):
            logger.error("Missing Zoho OAuth configuration")
            return jsonify({
                'error': 'OAuth configuration missing',
                'configured_items': {
                    'client_id': bool(ZOHO_CLIENT_ID),
                    'client_secret': bool(ZOHO_CLIENT_SECRET),
                    'refresh_token': bool(ZOHO_REFRESH_TOKEN)
                }
            }), 500
        
        # Make refresh token request
        data = {
            'refresh_token': ZOHO_REFRESH_TOKEN,
            'client_id': ZOHO_CLIENT_ID,
            'client_secret': ZOHO_CLIENT_SECRET,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post(ZOHO_TOKEN_URL, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Update cache
            token_cache['access_token'] = token_data.get('access_token')
            # Zoho tokens expire in 1 hour, we'll refresh 5 minutes early
            token_cache['expires_at'] = datetime.utcnow() + timedelta(minutes=55)
            
            logger.info("Successfully refreshed access token")
            
            return jsonify({
                'access_token': token_cache['access_token'],
                'expires_at': token_cache['expires_at'].isoformat(),
                'api_domain': token_data.get('api_domain', ZOHO_API_DOMAIN),
                'cached': False
            })
        else:
            logger.error(f"Failed to refresh token: {response.status_code} - {response.text}")
            return jsonify({
                'error': 'Failed to refresh token',
                'status_code': response.status_code,
                'message': response.text
            }), response.status_code
            
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'service': 'Zoho OAuth Service',
        'version': '1.0.0',
        'endpoints': {
            '/health': 'Health check',
            '/oauth/token': 'Get or refresh access token'
        }
    })

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)