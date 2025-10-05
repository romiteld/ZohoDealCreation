"""
Azure AD Authentication Service for User Login
Handles OAuth 2.0 authentication flow for accessing user emails
"""

import os
import logging
import asyncio
import aiohttp
import jwt
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode, urlparse, parse_qs
import secrets

# Configure logging
logger = logging.getLogger(__name__)

class AzureADAuthService:
    """Azure AD authentication service for user login"""
    
    def __init__(self, tenant_id: str = None, client_id: str = None, client_secret: str = None, redirect_uri: str = None):
        self.tenant_id = tenant_id or os.getenv("AZURE_TENANT_ID")
        self.client_id = client_id or os.getenv("AZURE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("AZURE_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.getenv("AZURE_REDIRECT_URI", "https://well-voice-ui.azurewebsites.net/auth/callback")
        
        # Azure AD endpoints
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.authorize_url = f"{self.authority}/oauth2/v2.0/authorize"
        self.token_url = f"{self.authority}/oauth2/v2.0/token"
        
        # Required scopes for Microsoft Graph email access
        self.scopes = [
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/Mail.ReadWrite",
            "https://graph.microsoft.com/User.Read",
            "offline_access"  # For refresh tokens
        ]
        
        # In-memory token storage (use Redis or database in production)
        self.user_tokens = {}
        
    def get_authorization_url(self, state: str = None) -> str:
        """Generate authorization URL for user login"""
        try:
            if not state:
                state = secrets.token_urlsafe(32)
            
            params = {
                'client_id': self.client_id,
                'response_type': 'code',
                'redirect_uri': self.redirect_uri,
                'scope': ' '.join(self.scopes),
                'state': state,
                'response_mode': 'query',
                'prompt': 'select_account'  # Force account selection
            }
            
            auth_url = f"{self.authorize_url}?{urlencode(params)}"
            logger.info(f"Generated authorization URL with state: {state}")
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating authorization URL: {e}")
            raise

    async def exchange_code_for_tokens(self, authorization_code: str, state: str = None) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            token_data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': authorization_code,
                'redirect_uri': self.redirect_uri,
                'grant_type': 'authorization_code',
                'scope': ' '.join(self.scopes)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.token_url, data=token_data) as response:
                    if response.status == 200:
                        tokens = await response.json()
                        
                        # Decode and validate access token
                        user_info = self.decode_token(tokens['access_token'])
                        user_id = user_info.get('oid') or user_info.get('sub')
                        
                        if not user_id:
                            raise Exception("Could not extract user ID from token")
                        
                        # Store tokens with expiration
                        expires_in = tokens.get('expires_in', 3600)
                        expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                        
                        token_info = {
                            'access_token': tokens['access_token'],
                            'refresh_token': tokens.get('refresh_token'),
                            'expires_at': expires_at,
                            'user_id': user_id,
                            'user_email': user_info.get('preferred_username') or user_info.get('upn'),
                            'user_name': user_info.get('name'),
                            'scopes': tokens.get('scope', '').split(' ')
                        }
                        
                        self.user_tokens[user_id] = token_info
                        
                        logger.info(f"Successfully exchanged code for tokens for user {user_id}")
                        return token_info
                    else:
                        error_text = await response.text()
                        logger.error(f"Token exchange failed: {response.status} - {error_text}")
                        raise Exception(f"Token exchange failed: {response.status}")
        
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            raise

    async def refresh_access_token(self, user_id: str) -> Optional[str]:
        """Refresh access token using refresh token"""
        try:
            token_info = self.user_tokens.get(user_id)
            if not token_info or not token_info.get('refresh_token'):
                logger.warning(f"No refresh token available for user {user_id}")
                return None
            
            refresh_data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': token_info['refresh_token'],
                'grant_type': 'refresh_token',
                'scope': ' '.join(self.scopes)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.token_url, data=refresh_data) as response:
                    if response.status == 200:
                        tokens = await response.json()
                        
                        # Update stored token info
                        expires_in = tokens.get('expires_in', 3600)
                        expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                        
                        token_info['access_token'] = tokens['access_token']
                        token_info['expires_at'] = expires_at
                        
                        # Update refresh token if provided
                        if 'refresh_token' in tokens:
                            token_info['refresh_token'] = tokens['refresh_token']
                        
                        self.user_tokens[user_id] = token_info
                        
                        logger.info(f"Successfully refreshed access token for user {user_id}")
                        return tokens['access_token']
                    else:
                        error_text = await response.text()
                        logger.error(f"Token refresh failed: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return None

    async def get_valid_access_token(self, user_id: str) -> Optional[str]:
        """Get valid access token, refreshing if necessary"""
        try:
            token_info = self.user_tokens.get(user_id)
            if not token_info:
                logger.warning(f"No token info found for user {user_id}")
                return None
            
            # Check if token is still valid
            if datetime.utcnow() < token_info['expires_at']:
                return token_info['access_token']
            
            # Token expired, try to refresh
            logger.info(f"Access token expired for user {user_id}, attempting refresh")
            return await self.refresh_access_token(user_id)
        
        except Exception as e:
            logger.error(f"Error getting valid access token: {e}")
            return None

    def decode_token(self, access_token: str) -> Dict[str, Any]:
        """Decode JWT access token without verification (for extracting user info)"""
        try:
            # Split token and decode payload
            header, payload, signature = access_token.split('.')
            
            # Add padding if necessary
            payload += '=' * (4 - len(payload) % 4)
            
            # Decode base64
            decoded_payload = base64.urlsafe_b64decode(payload)
            user_info = jwt.decode(decoded_payload, options={"verify_signature": False})
            
            return user_info
        
        except Exception as e:
            logger.error(f"Error decoding token: {e}")
            return {}

    def is_user_authenticated(self, user_id: str) -> bool:
        """Check if user is authenticated and has valid tokens"""
        token_info = self.user_tokens.get(user_id)
        if not token_info:
            return False
        
        return datetime.utcnow() < token_info['expires_at']

    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get stored user information"""
        token_info = self.user_tokens.get(user_id)
        if not token_info:
            return None
        
        return {
            'user_id': token_info['user_id'],
            'user_email': token_info['user_email'],
            'user_name': token_info['user_name'],
            'scopes': token_info['scopes'],
            'expires_at': token_info['expires_at'].isoformat()
        }

    def logout_user(self, user_id: str) -> bool:
        """Remove user tokens (logout)"""
        if user_id in self.user_tokens:
            del self.user_tokens[user_id]
            logger.info(f"User {user_id} logged out successfully")
            return True
        return False

    async def validate_user_permission(self, user_id: str, required_scopes: list = None) -> bool:
        """Validate user has required permissions"""
        try:
            token_info = self.user_tokens.get(user_id)
            if not token_info:
                return False
            
            if not required_scopes:
                required_scopes = ["https://graph.microsoft.com/Mail.Read"]
            
            user_scopes = token_info.get('scopes', [])
            return all(scope in user_scopes for scope in required_scopes)
        
        except Exception as e:
            logger.error(f"Error validating user permissions: {e}")
            return False

    def get_all_authenticated_users(self) -> Dict[str, Dict[str, Any]]:
        """Get all authenticated users (for admin/monitoring)"""
        users = {}
        for user_id, token_info in self.user_tokens.items():
            users[user_id] = {
                'user_email': token_info.get('user_email'),
                'user_name': token_info.get('user_name'),
                'expires_at': token_info['expires_at'].isoformat(),
                'is_valid': datetime.utcnow() < token_info['expires_at']
            }
        return users

# Global instance
_auth_service = None

def get_auth_service() -> AzureADAuthService:
    """Get global Azure AD authentication service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AzureADAuthService()
    return _auth_service

# FastAPI dependency for authenticated requests
async def require_user_auth(user_id: str = None) -> str:
    """FastAPI dependency to require user authentication"""
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="User ID required")
    
    auth_service = get_auth_service()
    if not auth_service.is_user_authenticated(user_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    return user_id

# Convenience function for testing
async def test_azure_ad_auth():
    """Test function for Azure AD authentication"""
    auth_service = AzureADAuthService()
    
    print("Testing Azure AD Authentication Service")
    
    # Generate authorization URL
    auth_url = auth_service.get_authorization_url("test_state_123")
    print(f"Authorization URL: {auth_url}")
    
    print("\n✅ Azure AD Auth Service initialized successfully")
    print("🔗 Use the authorization URL above to authenticate users")

if __name__ == "__main__":
    asyncio.run(test_azure_ad_auth())