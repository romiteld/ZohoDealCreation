"""
Zoho OAuth Token Refresh Service with Reverse Proxy for The Well Recruiting
Enhanced version with proxy capabilities to Container Apps API
"""
import os
import logging
import json
from flask import Flask, jsonify, request, Response, stream_with_context
from datetime import datetime, timedelta
import requests
from urllib.parse import urljoin, urlparse
import time
from threading import Lock
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv('.env.local')

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

# Proxy Configuration
MAIN_API_URL = os.environ.get('MAIN_API_URL', 'https://well-intake-api.orangedesert-c768ae6e.eastus.azurecontainerapps.io')
MAIN_API_KEY = os.environ.get('API_KEY', '')  # Using API_KEY from .env.local
PROXY_TIMEOUT = int(os.environ.get('PROXY_TIMEOUT', '30'))
PROXY_CHUNK_SIZE = int(os.environ.get('PROXY_CHUNK_SIZE', '8192'))

# Rate limiting configuration
RATE_LIMIT = int(os.environ.get('PROXY_RATE_LIMIT', '100'))  # requests per minute
rate_limit_storage = {}
rate_limit_lock = Lock()

# Cache for access token
token_cache = {
    'access_token': None,
    'expires_at': None
}

# Circuit breaker for proxy
circuit_breaker = {
    'failures': 0,
    'last_failure': None,
    'is_open': False,
    'threshold': 5,
    'timeout': 60  # seconds
}

def check_rate_limit(client_ip):
    """Simple rate limiting implementation"""
    current_minute = int(time.time() / 60)
    
    with rate_limit_lock:
        if client_ip not in rate_limit_storage:
            rate_limit_storage[client_ip] = {'minute': current_minute, 'count': 0}
        
        if rate_limit_storage[client_ip]['minute'] < current_minute:
            rate_limit_storage[client_ip] = {'minute': current_minute, 'count': 0}
        
        if rate_limit_storage[client_ip]['count'] >= RATE_LIMIT:
            return False
        
        rate_limit_storage[client_ip]['count'] += 1
        return True

def check_circuit_breaker():
    """Check if circuit breaker is open"""
    if not circuit_breaker['is_open']:
        return True
    
    # Check if timeout has passed
    if circuit_breaker['last_failure']:
        time_since_failure = time.time() - circuit_breaker['last_failure']
        if time_since_failure > circuit_breaker['timeout']:
            circuit_breaker['is_open'] = False
            circuit_breaker['failures'] = 0
            logger.info("Circuit breaker closed after timeout")
            return True
    
    return False

def record_circuit_failure():
    """Record a failure in circuit breaker"""
    circuit_breaker['failures'] += 1
    circuit_breaker['last_failure'] = time.time()
    
    if circuit_breaker['failures'] >= circuit_breaker['threshold']:
        circuit_breaker['is_open'] = True
        logger.warning(f"Circuit breaker opened after {circuit_breaker['failures']} failures")

def record_circuit_success():
    """Record a success in circuit breaker"""
    if circuit_breaker['failures'] > 0:
        circuit_breaker['failures'] = max(0, circuit_breaker['failures'] - 1)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    proxy_status = 'healthy' if check_circuit_breaker() else 'circuit_open'
    
    return jsonify({
        'status': 'healthy',
        'service': 'zoho-oauth-proxy',
        'timestamp': datetime.utcnow().isoformat(),
        'oauth_configured': all([ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN]),
        'proxy_configured': bool(MAIN_API_KEY),
        'proxy_status': proxy_status,
        'proxy_target': MAIN_API_URL
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

@app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy_api(path):
    """Proxy requests to Container Apps API"""
    client_ip = request.remote_addr
    
    # Rate limiting
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return jsonify({'error': 'Rate limit exceeded'}), 429
    
    # Circuit breaker check
    if not check_circuit_breaker():
        logger.warning("Circuit breaker is open")
        return jsonify({'error': 'Service temporarily unavailable'}), 503
    
    try:
        # Build target URL
        target_url = urljoin(MAIN_API_URL, f'/{path}')
        if request.query_string:
            target_url += '?' + request.query_string.decode()
        
        logger.info(f"Proxying {request.method} request to {target_url}")
        
        # Prepare headers
        headers = {key: value for key, value in request.headers if key.lower() not in 
                  ['host', 'content-length', 'connection']}
        
        # Add authentication header
        if MAIN_API_KEY:
            headers['X-API-Key'] = MAIN_API_KEY
        
        # Add forwarded headers
        headers['X-Forwarded-For'] = client_ip
        headers['X-Forwarded-Proto'] = request.scheme
        headers['X-Forwarded-Host'] = request.host
        headers['X-Original-URL'] = request.url
        
        # Get request data
        data = None
        json_data = None
        files = None
        
        if request.method in ['POST', 'PUT', 'PATCH']:
            if request.is_json:
                json_data = request.get_json()
            elif request.files:
                files = {key: (file.filename, file.stream, file.content_type) 
                        for key, file in request.files.items()}
                data = request.form.to_dict()
            else:
                data = request.get_data()
        
        # Make proxy request
        proxy_response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=data,
            json=json_data,
            files=files,
            timeout=PROXY_TIMEOUT,
            stream=True,
            allow_redirects=False
        )
        
        # Record success for circuit breaker
        record_circuit_success()
        
        # Build response
        response_headers = {}
        for key, value in proxy_response.headers.items():
            if key.lower() not in ['content-encoding', 'content-length', 'connection']:
                response_headers[key] = value
        
        # Handle streaming response
        def generate():
            for chunk in proxy_response.iter_content(chunk_size=PROXY_CHUNK_SIZE):
                if chunk:
                    yield chunk
        
        response = Response(
            stream_with_context(generate()),
            status=proxy_response.status_code,
            headers=response_headers
        )
        
        return response
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout proxying request to {path}")
        record_circuit_failure()
        return jsonify({'error': 'Request timeout'}), 504
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error proxying request: {str(e)}")
        record_circuit_failure()
        return jsonify({'error': 'Connection error to backend service'}), 502
        
    except Exception as e:
        logger.error(f"Error proxying request: {str(e)}")
        record_circuit_failure()
        return jsonify({'error': 'Internal proxy error', 'message': str(e)}), 500

@app.route('/proxy/health', methods=['GET'])
def proxy_health_check():
    """Direct health check of the proxied API"""
    try:
        target_url = urljoin(MAIN_API_URL, '/health')
        headers = {'X-API-Key': MAIN_API_KEY} if MAIN_API_KEY else {}
        
        response = requests.get(target_url, headers=headers, timeout=10)
        
        return jsonify({
            'proxy_status': 'healthy',
            'backend_status': response.status_code,
            'backend_response': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        })
    except Exception as e:
        return jsonify({
            'proxy_status': 'unhealthy',
            'error': str(e)
        }), 503

@app.route('/proxy/test/kevin-sullivan', methods=['GET'])
def proxy_test_kevin():
    """Proxy Kevin Sullivan test endpoint"""
    return proxy_api('test/kevin-sullivan')

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with enhanced documentation"""
    return jsonify({
        'service': 'Zoho OAuth Service with Reverse Proxy',
        'version': '2.0.0',
        'endpoints': {
            'oauth': {
                '/health': 'Health check',
                '/oauth/token': 'Get or refresh Zoho access token'
            },
            'proxy': {
                '/api/*': 'Proxy to Container Apps API',
                '/proxy/health': 'Check backend API health',
                '/proxy/test/kevin-sullivan': 'Test Kevin Sullivan endpoint'
            }
        },
        'configuration': {
            'proxy_target': MAIN_API_URL,
            'proxy_configured': bool(MAIN_API_KEY),
            'oauth_configured': all([ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN]),
            'rate_limit': f'{RATE_LIMIT} requests/minute',
            'timeout': f'{PROXY_TIMEOUT} seconds'
        }
    })

@app.route('/manifest.xml', methods=['GET'])
def proxy_manifest():
    """Proxy Outlook Add-in manifest"""
    return proxy_api('manifest.xml')

@app.route('/static/<path:path>', methods=['GET'])
def proxy_static(path):
    """Proxy static files for Outlook Add-in"""
    return proxy_api(f'static/{path}')

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found', 'path': request.path}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)