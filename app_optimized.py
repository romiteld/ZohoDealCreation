"""
Optimized OAuth service with caching and improved performance
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from flask import Flask, request, jsonify, render_template_string
import requests
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configuration with validation
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "")
ZOHO_DC = os.getenv("ZOHO_DC", "com")
REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI", "https://well-zoho-oauth.azurewebsites.net/callback")

# Token storage (in production, use Redis or secure storage)
_token_cache = {
    'access_token': None,
    'refresh_token': None,
    'expires_at': 0
}

# HTML templates
HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zoho OAuth - The Well Recruiting</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: white;
            padding: 3rem;
            border-radius: 1rem;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            max-width: 500px;
            width: 90%;
        }
        h1 {
            color: #333;
            margin-bottom: 1rem;
            font-size: 2rem;
        }
        .status {
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 1.5rem 0;
            font-weight: 500;
        }
        .status.warning {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffc107;
        }
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #28a745;
        }
        .btn {
            display: inline-block;
            padding: 1rem 2rem;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 0.5rem;
            font-weight: 600;
            transition: all 0.3s;
            border: none;
            cursor: pointer;
        }
        .btn:hover {
            background: #5a67d8;
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }
        .info {
            color: #666;
            margin-top: 1rem;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 Zoho OAuth Service</h1>
        
        {% if token_status %}
        <div class="status success">
            ✅ Token is valid for {{ token_remaining }} more minutes
        </div>
        {% else %}
        <div class="status warning">
            ⚠️ No valid token. Authorization required.
        </div>
        {% endif %}
        
        <a href="{{ auth_url }}" class="btn">Authorize with Zoho</a>
        
        <div class="info">
            <p><strong>Environment:</strong> {{ environment }}</p>
            <p><strong>Time:</strong> {{ current_time }}</p>
        </div>
    </div>
</body>
</html>
"""

SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Success - Zoho OAuth</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: white;
            padding: 3rem;
            border-radius: 1rem;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            max-width: 600px;
            width: 90%;
        }
        h1 { color: #28a745; margin-bottom: 1rem; }
        .token-box {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 1rem 0;
            border: 2px solid #28a745;
        }
        textarea {
            width: 100%;
            padding: 0.5rem;
            font-family: monospace;
            font-size: 0.9rem;
            border: 1px solid #ddd;
            border-radius: 0.25rem;
            resize: vertical;
            min-height: 60px;
        }
        .copy-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.25rem;
            cursor: pointer;
            margin-top: 0.5rem;
        }
        .copy-btn:hover { background: #218838; }
    </style>
    <script>
        function copyToClipboard(elementId) {
            const element = document.getElementById(elementId);
            element.select();
            document.execCommand('copy');
            alert('Copied to clipboard!');
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>✅ Authorization Successful!</h1>
        
        <div class="token-box">
            <h3>Refresh Token (Save This!):</h3>
            <textarea id="refresh_token" readonly>{{ refresh_token }}</textarea>
            <button class="copy-btn" onclick="copyToClipboard('refresh_token')">Copy</button>
        </div>
        
        <div class="token-box">
            <h3>Add to .env.local:</h3>
            <textarea id="env_var" readonly>ZOHO_REFRESH_TOKEN={{ refresh_token }}</textarea>
            <button class="copy-btn" onclick="copyToClipboard('env_var')">Copy</button>
        </div>
        
        <p style="color: #666; margin-top: 1rem;">
            <strong>Important:</strong> Save this refresh token immediately. 
            It will be used to generate access tokens automatically.
        </p>
    </div>
</body>
</html>
"""

def validate_config():
    """Validate required configuration"""
    if not CLIENT_ID or not CLIENT_SECRET:
        logger.error("Missing required Zoho OAuth configuration")
        raise RuntimeError("ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET must be set")

@lru_cache(maxsize=1)
def get_auth_url():
    """Get cached authorization URL"""
    return (
        f"https://accounts.zoho.{ZOHO_DC}/oauth/v2/auth"
        "?scope=ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.users.ALL"
        f"&client_id={CLIENT_ID}"
        "&response_type=code"
        "&access_type=offline"
        f"&redirect_uri={REDIRECT_URI}"
        "&prompt=consent"
    )

def refresh_access_token():
    """Refresh access token using refresh token"""
    global _token_cache
    
    if not _token_cache['refresh_token']:
        logger.warning("No refresh token available")
        return False
    
    token_url = f"https://accounts.zoho.{ZOHO_DC}/oauth/v2/token"
    data = {
        'grant_type': 'refresh_token',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': _token_cache['refresh_token']
    }
    
    try:
        response = requests.post(token_url, data=data, timeout=10)
        if response.status_code == 200:
            tokens = response.json()
            _token_cache['access_token'] = tokens['access_token']
            # Tokens expire in 1 hour, refresh at 50 minutes
            _token_cache['expires_at'] = time.time() + 3000
            logger.info("Access token refreshed successfully")
            return True
    except Exception as e:
        logger.error(f"Failed to refresh access token: {e}")
    
    return False

@app.route('/')
def home():
    """Home page with authorization link"""
    validate_config()
    
    # Check token status
    token_valid = _token_cache['access_token'] and time.time() < _token_cache['expires_at']
    token_remaining = int((_token_cache['expires_at'] - time.time()) / 60) if token_valid else 0
    
    return render_template_string(
        HOME_TEMPLATE,
        auth_url=get_auth_url(),
        token_status=token_valid,
        token_remaining=token_remaining,
        environment=f"Zoho {ZOHO_DC.upper()}",
        current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

@app.route('/callback')
def callback():
    """OAuth callback handler"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        logger.error(f"OAuth error: {error}")
        return f"<h1>Authorization Error</h1><p>{error}</p>", 400
    
    if not code:
        return "<h1>Error</h1><p>No authorization code received</p>", 400
    
    # Exchange code for tokens
    token_url = f"https://accounts.zoho.{ZOHO_DC}/oauth/v2/token"
    data = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'code': code
    }
    
    try:
        response = requests.post(token_url, data=data, timeout=10)
        tokens = response.json()
        
        if 'refresh_token' in tokens:
            # Store tokens
            _token_cache['refresh_token'] = tokens['refresh_token']
            _token_cache['access_token'] = tokens.get('access_token', '')
            _token_cache['expires_at'] = time.time() + 3000
            
            logger.info("OAuth tokens obtained successfully")
            
            return render_template_string(
                SUCCESS_TEMPLATE,
                refresh_token=tokens['refresh_token']
            )
        else:
            logger.error(f"No refresh token in response: {tokens}")
            return f"<h1>Error</h1><pre>{json.dumps(tokens, indent=2)}</pre>", 400
            
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return f"<h1>Error</h1><p>Failed to obtain tokens: {str(e)}</p>", 500

@app.route('/get-token')
def get_token():
    """API endpoint to get current access token"""
    global _token_cache
    
    # Check if token needs refresh
    if time.time() >= _token_cache['expires_at']:
        if not refresh_access_token():
            return jsonify({'error': 'Failed to refresh token'}), 401
    
    if _token_cache['access_token']:
        return jsonify({
            'access_token': _token_cache['access_token'],
            'expires_in': int(_token_cache['expires_at'] - time.time())
        })
    else:
        return jsonify({'error': 'No valid token available'}), 401

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'zoho-oauth',
        'token_valid': _token_cache['access_token'] is not None,
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found(e):
    """404 error handler"""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(e):
    """500 error handler"""
    logger.error(f"Server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# Initialize on startup
@app.before_first_request
def initialize():
    """Initialize service on first request"""
    try:
        validate_config()
        
        # Try to load refresh token from environment
        refresh_token = os.getenv("ZOHO_REFRESH_TOKEN")
        if refresh_token:
            _token_cache['refresh_token'] = refresh_token
            refresh_access_token()
            logger.info("Initialized with refresh token from environment")
    except Exception as e:
        logger.error(f"Initialization failed: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    
    # Use production server if available
    try:
        from waitress import serve
        logger.info(f"Starting Waitress server on port {port}")
        serve(app, host='0.0.0.0', port=port, threads=4)
    except ImportError:
        logger.info(f"Starting Flask development server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)