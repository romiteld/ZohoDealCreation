"""
Enterprise security configuration module for Well Intake API.
Implements Azure Key Vault integration, secret rotation, API key management,
and rate limiting for production-grade security.
"""

import os
import json
import secrets
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from functools import wraps
import asyncio
from contextlib import asynccontextmanager

from azure.keyvault.secrets import SecretClient
from azure.keyvault.keys import KeyClient
from azure.keyvault.keys.crypto import CryptographyClient, EncryptionAlgorithm
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
import redis.asyncio as redis
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2


class SecurityConfig:
    """Enterprise security configuration and management."""
    
    def __init__(self):
        """Initialize security configuration."""
        self.key_vault_url = os.getenv('KEY_VAULT_URL')
        self.redis_connection_string = os.getenv('REDIS_CONNECTION_STRING')
        self.use_managed_identity = os.getenv('USE_MANAGED_IDENTITY', 'false').lower() == 'true'
        
        # Initialize Azure credential
        if self.use_managed_identity:
            self.credential = ManagedIdentityCredential()
        else:
            self.credential = DefaultAzureCredential()
        
        # Initialize Key Vault clients
        if self.key_vault_url:
            self.secret_client = SecretClient(
                vault_url=self.key_vault_url,
                credential=self.credential
            )
            self.key_client = KeyClient(
                vault_url=self.key_vault_url,
                credential=self.credential
            )
        else:
            self.secret_client = None
            self.key_client = None
        
        # Initialize Redis for distributed rate limiting and caching
        self.redis_client = None
        if self.redis_connection_string:
            asyncio.create_task(self._init_redis())
        
        # Local encryption key for non-sensitive data
        self.local_key = self._get_or_create_local_key()
        self.fernet = Fernet(self.local_key)
        
        # API key configuration
        self.api_key_rotation_days = int(os.getenv('API_KEY_ROTATION_DAYS', '30'))
        self.api_key_length = int(os.getenv('API_KEY_LENGTH', '32'))
        
        # Rate limiting configuration
        self.rate_limit_enabled = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
        self.rate_limit_requests = int(os.getenv('RATE_LIMIT_REQUESTS', '100'))
        self.rate_limit_period = int(os.getenv('RATE_LIMIT_PERIOD', '60'))  # seconds
        
        # Security headers configuration
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https://appsforoffice.microsoft.com https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline';",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
    
    async def _init_redis(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = await redis.from_url(
                self.redis_connection_string,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def _get_or_create_local_key(self) -> bytes:
        """Get or create local encryption key."""
        # Store encryption key in a secure location outside the repo
        key_file = os.path.join(os.path.expanduser("~"), ".well_intake", "encryption.key")
        key_dir = os.path.dirname(key_file)
        
        # Create directory if it doesn't exist
        if not os.path.exists(key_dir):
            os.makedirs(key_dir, mode=0o700)
        
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict file permissions
            return key
    
    async def get_secret(self, secret_name: str, use_cache: bool = True) -> Optional[str]:
        """
        Retrieve secret from Azure Key Vault with caching.
        
        Args:
            secret_name: Name of the secret in Key Vault
            use_cache: Whether to use Redis cache for the secret
        
        Returns:
            Secret value or None if not found
        """
        if not self.secret_client:
            # Fallback to environment variable
            return os.getenv(secret_name.upper().replace('-', '_'))
        
        # Check cache first
        if use_cache and self.redis_client:
            try:
                cached_value = await self.redis_client.get(f"secret:{secret_name}")
                if cached_value:
                    # Decrypt cached value
                    return self.fernet.decrypt(cached_value.encode()).decode()
            except Exception as e:
                print(f"Cache retrieval error: {e}")
        
        try:
            # Retrieve from Key Vault
            secret = self.secret_client.get_secret(secret_name)
            
            # Cache the encrypted value
            if use_cache and self.redis_client:
                encrypted_value = self.fernet.encrypt(secret.value.encode()).decode()
                await self.redis_client.setex(
                    f"secret:{secret_name}",
                    300,  # 5 minutes cache
                    encrypted_value
                )
            
            return secret.value
        
        except ResourceNotFoundError:
            return None
        except Exception as e:
            print(f"Error retrieving secret {secret_name}: {e}")
            # Fallback to environment variable
            return os.getenv(secret_name.upper().replace('-', '_'))
    
    async def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Store or update secret in Azure Key Vault.
        
        Args:
            secret_name: Name of the secret
            secret_value: Value to store
        
        Returns:
            True if successful, False otherwise
        """
        if not self.secret_client:
            return False
        
        try:
            self.secret_client.set_secret(secret_name, secret_value)
            
            # Invalidate cache
            if self.redis_client:
                await self.redis_client.delete(f"secret:{secret_name}")
            
            return True
        
        except Exception as e:
            print(f"Error setting secret {secret_name}: {e}")
            return False
    
    async def rotate_secret(self, secret_name: str, generator_func=None) -> Tuple[bool, Optional[str]]:
        """
        Rotate a secret in Key Vault.
        
        Args:
            secret_name: Name of the secret to rotate
            generator_func: Optional function to generate new secret value
        
        Returns:
            Tuple of (success, new_value)
        """
        if not self.secret_client:
            return False, None
        
        try:
            # Generate new secret value
            if generator_func:
                new_value = generator_func()
            else:
                new_value = secrets.token_urlsafe(32)
            
            # Store new version
            self.secret_client.set_secret(
                secret_name,
                new_value,
                content_type="text/plain",
                tags={
                    "rotated_at": datetime.utcnow().isoformat(),
                    "rotation_version": str(int(time.time()))
                }
            )
            
            # Invalidate cache
            if self.redis_client:
                await self.redis_client.delete(f"secret:{secret_name}")
            
            return True, new_value
        
        except Exception as e:
            print(f"Error rotating secret {secret_name}: {e}")
            return False, None
    
    def generate_api_key(self) -> str:
        """Generate a secure API key."""
        return f"wia_{secrets.token_urlsafe(self.api_key_length)}"
    
    async def validate_api_key(self, api_key: str) -> Dict[str, Any]:
        """
        Validate an API key and return metadata.
        
        Args:
            api_key: The API key to validate
        
        Returns:
            Dictionary with validation result and metadata
        """
        if not api_key or not api_key.startswith("wia_"):
            return {"valid": False, "reason": "Invalid format"}
        
        # Hash the API key for secure storage/comparison
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Check in Redis cache first
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(f"api_key:{key_hash}")
                if cached_data:
                    data = json.loads(cached_data)
                    
                    # Check expiration
                    if data.get("expires_at"):
                        expires_at = datetime.fromisoformat(data["expires_at"])
                        if expires_at < datetime.utcnow():
                            await self.redis_client.delete(f"api_key:{key_hash}")
                            return {"valid": False, "reason": "Expired"}
                    
                    return {"valid": True, "metadata": data}
            except Exception as e:
                print(f"Cache validation error: {e}")
        
        # Check in Key Vault
        if self.secret_client:
            try:
                secret_name = f"api-key-{key_hash[:16]}"
                secret = self.secret_client.get_secret(secret_name)
                
                metadata = json.loads(secret.value)
                
                # Cache the result
                if self.redis_client:
                    await self.redis_client.setex(
                        f"api_key:{key_hash}",
                        3600,  # 1 hour cache
                        json.dumps(metadata)
                    )
                
                return {"valid": True, "metadata": metadata}
            
            except ResourceNotFoundError:
                return {"valid": False, "reason": "Not found"}
            except Exception as e:
                print(f"Key Vault validation error: {e}")
        
        # Fallback to environment variable
        env_key = os.getenv('API_KEY')
        if env_key and api_key == env_key:
            return {"valid": True, "metadata": {"source": "environment"}}
        
        return {"valid": False, "reason": "Invalid key"}
    
    async def create_api_key(self, metadata: Dict[str, Any]) -> str:
        """
        Create a new API key with metadata.
        
        Args:
            metadata: Dictionary containing key metadata (owner, permissions, etc.)
        
        Returns:
            The generated API key
        """
        api_key = self.generate_api_key()
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Add creation and expiration timestamps
        metadata["created_at"] = datetime.utcnow().isoformat()
        metadata["expires_at"] = (
            datetime.utcnow() + timedelta(days=self.api_key_rotation_days)
        ).isoformat()
        metadata["key_hash"] = key_hash
        
        # Store in Key Vault
        if self.secret_client:
            try:
                secret_name = f"api-key-{key_hash[:16]}"
                self.secret_client.set_secret(
                    secret_name,
                    json.dumps(metadata),
                    content_type="application/json",
                    tags={
                        "type": "api_key",
                        "owner": metadata.get("owner", "unknown"),
                        "created_at": metadata["created_at"]
                    }
                )
            except Exception as e:
                print(f"Error storing API key: {e}")
        
        # Cache in Redis
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    f"api_key:{key_hash}",
                    3600,  # 1 hour cache
                    json.dumps(metadata)
                )
            except Exception as e:
                print(f"Error caching API key: {e}")
        
        return api_key
    
    async def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            api_key: The API key to revoke
        
        Returns:
            True if successfully revoked, False otherwise
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Remove from cache
        if self.redis_client:
            try:
                await self.redis_client.delete(f"api_key:{key_hash}")
            except Exception as e:
                print(f"Error removing from cache: {e}")
        
        # Disable in Key Vault (don't delete, just disable)
        if self.secret_client:
            try:
                secret_name = f"api-key-{key_hash[:16]}"
                secret = self.secret_client.get_secret(secret_name)
                
                metadata = json.loads(secret.value)
                metadata["revoked"] = True
                metadata["revoked_at"] = datetime.utcnow().isoformat()
                
                self.secret_client.set_secret(
                    secret_name,
                    json.dumps(metadata),
                    enabled=False  # Disable the secret
                )
                
                return True
            except Exception as e:
                print(f"Error revoking key in Key Vault: {e}")
        
        return False
    
    def get_rate_limiter(self) -> Limiter:
        """
        Get configured rate limiter instance.
        
        Returns:
            Configured Limiter instance
        """
        if self.redis_client:
            # Use Redis for distributed rate limiting
            storage_uri = self.redis_connection_string
        else:
            # Use in-memory storage for single instance
            storage_uri = "memory://"
        
        return Limiter(
            key_func=get_remote_address,
            default_limits=[f"{self.rate_limit_requests}/{self.rate_limit_period} seconds"],
            storage_uri=storage_uri,
            enabled=self.rate_limit_enabled
        )
    
    async def check_rate_limit(self, identifier: str, limit: int = None, period: int = None) -> bool:
        """
        Check if rate limit is exceeded for an identifier.
        
        Args:
            identifier: Unique identifier (IP, API key, etc.)
            limit: Number of requests allowed (default from config)
            period: Time period in seconds (default from config)
        
        Returns:
            True if within limit, False if exceeded
        """
        if not self.rate_limit_enabled:
            return True
        
        limit = limit or self.rate_limit_requests
        period = period or self.rate_limit_period
        
        if self.redis_client:
            try:
                key = f"rate_limit:{identifier}"
                
                # Increment counter
                count = await self.redis_client.incr(key)
                
                # Set expiration on first request
                if count == 1:
                    await self.redis_client.expire(key, period)
                
                return count <= limit
            
            except Exception as e:
                print(f"Rate limit check error: {e}")
                return True  # Allow on error
        
        # Fallback to allowing request if Redis not available
        return True
    
    async def get_rate_limit_status(self, identifier: str) -> Dict[str, Any]:
        """
        Get current rate limit status for an identifier.
        
        Args:
            identifier: Unique identifier
        
        Returns:
            Dictionary with current count, limit, and reset time
        """
        if not self.rate_limit_enabled or not self.redis_client:
            return {
                "count": 0,
                "limit": self.rate_limit_requests,
                "remaining": self.rate_limit_requests,
                "reset": int(time.time() + self.rate_limit_period)
            }
        
        try:
            key = f"rate_limit:{identifier}"
            count = await self.redis_client.get(key)
            ttl = await self.redis_client.ttl(key)
            
            count = int(count) if count else 0
            remaining = max(0, self.rate_limit_requests - count)
            reset = int(time.time() + ttl) if ttl > 0 else int(time.time() + self.rate_limit_period)
            
            return {
                "count": count,
                "limit": self.rate_limit_requests,
                "remaining": remaining,
                "reset": reset
            }
        
        except Exception as e:
            print(f"Rate limit status error: {e}")
            return {
                "count": 0,
                "limit": self.rate_limit_requests,
                "remaining": self.rate_limit_requests,
                "reset": int(time.time() + self.rate_limit_period)
            }
    
    def apply_security_headers(self, response):
        """
        Apply security headers to response.
        
        Args:
            response: FastAPI response object
        
        Returns:
            Response with security headers
        """
        for header, value in self.security_headers.items():
            response.headers[header] = value
        return response
    
    async def encrypt_sensitive_data(self, data: str) -> str:
        """
        Encrypt sensitive data using Key Vault key.
        
        Args:
            data: Data to encrypt
        
        Returns:
            Encrypted data as base64 string
        """
        if self.key_client:
            try:
                # Get or create encryption key
                key_name = "data-encryption-key"
                key = self.key_client.get_key(key_name)
                
                crypto_client = CryptographyClient(key, credential=self.credential)
                
                # Encrypt data
                result = crypto_client.encrypt(
                    EncryptionAlgorithm.rsa_oaep_256,
                    data.encode()
                )
                
                import base64
                return base64.b64encode(result.ciphertext).decode()
            
            except ResourceNotFoundError:
                # Create key if it doesn't exist
                key = self.key_client.create_rsa_key(key_name, size=2048)
                crypto_client = CryptographyClient(key, credential=self.credential)
                
                result = crypto_client.encrypt(
                    EncryptionAlgorithm.rsa_oaep_256,
                    data.encode()
                )
                
                import base64
                return base64.b64encode(result.ciphertext).decode()
            
            except Exception as e:
                print(f"Encryption error: {e}")
        
        # Fallback to local encryption
        return self.fernet.encrypt(data.encode()).decode()
    
    async def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive data using Key Vault key.
        
        Args:
            encrypted_data: Base64 encoded encrypted data
        
        Returns:
            Decrypted data
        """
        if self.key_client:
            try:
                import base64
                ciphertext = base64.b64decode(encrypted_data.encode())
                
                key_name = "data-encryption-key"
                key = self.key_client.get_key(key_name)
                
                crypto_client = CryptographyClient(key, credential=self.credential)
                
                # Decrypt data
                result = crypto_client.decrypt(
                    EncryptionAlgorithm.rsa_oaep_256,
                    ciphertext
                )
                
                return result.plaintext.decode()
            
            except Exception as e:
                print(f"Decryption error: {e}")
        
        # Fallback to local decryption
        return self.fernet.decrypt(encrypted_data.encode()).decode()
    
    async def audit_log(self, event: str, details: Dict[str, Any]):
        """
        Log security audit event.
        
        Args:
            event: Event type (e.g., "api_key_created", "secret_accessed")
            details: Event details
        """
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "details": details
        }
        
        # Store in Redis for immediate access
        if self.redis_client:
            try:
                key = f"audit:{datetime.utcnow().strftime('%Y%m%d')}:{event}"
                await self.redis_client.lpush(key, json.dumps(audit_entry))
                await self.redis_client.expire(key, 86400 * 30)  # Keep for 30 days
            except Exception as e:
                print(f"Audit log error: {e}")
        
        # Also log to console/file
        print(f"AUDIT: {json.dumps(audit_entry)}")
    
    async def cleanup_expired_keys(self):
        """Clean up expired API keys from Key Vault."""
        if not self.secret_client:
            return
        
        try:
            # List all secrets
            secrets = self.secret_client.list_properties_of_secrets()
            
            for secret_properties in secrets:
                if secret_properties.name.startswith("api-key-"):
                    try:
                        secret = self.secret_client.get_secret(secret_properties.name)
                        metadata = json.loads(secret.value)
                        
                        # Check if expired
                        if metadata.get("expires_at"):
                            expires_at = datetime.fromisoformat(metadata["expires_at"])
                            if expires_at < datetime.utcnow():
                                # Disable expired key
                                self.secret_client.set_secret(
                                    secret_properties.name,
                                    secret.value,
                                    enabled=False
                                )
                                
                                await self.audit_log("api_key_expired", {
                                    "key_name": secret_properties.name,
                                    "owner": metadata.get("owner", "unknown")
                                })
                    
                    except Exception as e:
                        print(f"Error processing secret {secret_properties.name}: {e}")
        
        except Exception as e:
            print(f"Cleanup error: {e}")


# Global security instance
security = SecurityConfig()


# FastAPI dependencies
async def verify_api_key(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency for API key verification.
    
    Args:
        request: FastAPI request object
    
    Returns:
        Validation result dictionary
    
    Raises:
        HTTPException: If API key is invalid
    """
    api_key = request.headers.get("X-API-Key")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    
    validation = await security.validate_api_key(api_key)
    
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid API key: {validation.get('reason', 'Unknown')}"
        )
    
    # Check rate limit
    identifier = f"{api_key}:{request.client.host}"
    if not await security.check_rate_limit(identifier):
        rate_status = await security.get_rate_limit_status(identifier)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(rate_status["limit"]),
                "X-RateLimit-Remaining": str(rate_status["remaining"]),
                "X-RateLimit-Reset": str(rate_status["reset"])
            }
        )
    
    return validation["metadata"]


# Export functions for use in other modules
get_secret = security.get_secret
set_secret = security.set_secret
rotate_secret = security.rotate_secret
validate_api_key = security.validate_api_key
create_api_key = security.create_api_key
revoke_api_key = security.revoke_api_key
check_rate_limit = security.check_rate_limit
get_rate_limit_status = security.get_rate_limit_status
apply_security_headers = security.apply_security_headers
encrypt_sensitive_data = security.encrypt_sensitive_data
decrypt_sensitive_data = security.decrypt_sensitive_data
audit_log = security.audit_log
cleanup_expired_keys = security.cleanup_expired_keys
get_rate_limiter = security.get_rate_limiter