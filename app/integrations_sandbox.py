"""
Zoho CRM Sandbox Integration - Modified to use sandbox endpoints
This is a temporary file for testing with Zoho Sandbox
"""

import os
import logging
from app.integrations import ZohoClient

logger = logging.getLogger(__name__)

class ZohoSandboxClient(ZohoClient):
    """Zoho Client modified for Sandbox environment"""
    
    def __init__(self, pg_client=None):
        # Set sandbox mode
        self.is_sandbox = True
        
        # Use environment variables but modify for sandbox
        self.dc = os.getenv("ZOHO_DC", "com")
        
        # IMPORTANT: Use sandbox subdomain
        self.base_url = f"https://sandbox.zohoapis.{self.dc}/crm/v8"
        self.token_url = f"https://accounts.zoho.{self.dc}/oauth/v2/token"
        
        logger.info(f"🧪 SANDBOX MODE: Using sandbox API at {self.base_url}")
        
        # Initialize parent class (but we'll override the URLs)
        super().__init__(pg_client)
        
        # Override base URL again to ensure sandbox
        self.base_url = f"https://sandbox.zohoapis.{self.dc}/crm/v8"
        
    def _get_access_token(self) -> str:
        """Get access token - needs to be for sandbox organization"""
        logger.info("🧪 Getting SANDBOX access token from OAuth proxy...")
        
        # The OAuth proxy needs to return sandbox-specific tokens
        # You'll need to configure the proxy to support sandbox mode
        oauth_url = f"{os.getenv('ZOHO_OAUTH_SERVICE_URL', '')}/api/token"
        
        # Add sandbox parameter to request
        oauth_url += "?environment=sandbox"
        
        return super()._get_access_token()
    
    def _make_request(self, method: str, endpoint: str, payload=None):
        """Override to log sandbox requests"""
        full_url = f"{self.base_url}/{endpoint}"
        logger.info(f"🧪 SANDBOX API Request: {method} {full_url}")
        
        result = super()._make_request(method, endpoint, payload)
        
        logger.info(f"🧪 SANDBOX Response received")
        return result

# Function to get the appropriate client
def get_zoho_client(pg_client=None, use_sandbox=None):
    """Get Zoho client - production or sandbox based on configuration"""
    
    # Check if sandbox mode is requested
    if use_sandbox is None:
        use_sandbox = os.getenv('ZOHO_SANDBOX_MODE', 'false').lower() == 'true'
    
    if use_sandbox:
        logger.info("🧪 Using Zoho SANDBOX client")
        return ZohoSandboxClient(pg_client)
    else:
        logger.info("🏭 Using Zoho PRODUCTION client")
        return ZohoClient(pg_client)