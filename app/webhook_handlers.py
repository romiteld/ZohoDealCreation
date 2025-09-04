"""
GitHub Webhook Handlers for Automatic Cache Invalidation.
Handles GitHub push events for manifest-related file changes and triggers
Redis cache invalidation automatically with security and monitoring.
"""

import os
import json
import hmac
import hashlib
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from contextlib import asynccontextmanager

from fastapi import HTTPException, Header, Request, status
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


class GitHubWebhookHandler:
    """Handles GitHub webhooks for automatic cache invalidation."""
    
    def __init__(self):
        """Initialize webhook handler with configuration."""
        self.webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET")
        self.github_repo = os.getenv("GITHUB_REPOSITORY", "romiteld/outlook")
        
        # Manifest-related file patterns to watch for changes
        self.watched_patterns = {
            "addin/manifest.xml",
            "addin/*.html",
            "addin/*.js", 
            "addin/*.css",
            "addin/config.js",
            "addin/commands.js",
            "addin/commands.html",
            "addin/taskpane.js",
            "addin/taskpane.html",
            "static/icons/*.png"
        }
        
        # Cache patterns to invalidate based on file changes
        self.cache_invalidation_patterns = {
            "manifest": "well:manifest:*",
            "js_files": "well:js:*",
            "html_files": "well:html:*",
            "config": "well:config:*",
            "icons": "well:icons:*",
            "addin_assets": "well:addin:*"
        }
        
        # Statistics tracking
        self.stats = {
            "webhooks_received": 0,
            "webhooks_processed": 0,
            "cache_invalidations": 0,
            "last_processed": None,
            "errors": 0
        }
    
    def verify_signature(self, payload_body: bytes, signature: str) -> bool:
        """
        Verify GitHub webhook signature using HMAC-SHA256.
        
        Args:
            payload_body: Raw request body as bytes
            signature: GitHub signature header (X-Hub-Signature-256)
        
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("GitHub webhook secret not configured - signature verification disabled")
            return True  # Allow in development mode
        
        if not signature:
            logger.error("Missing GitHub signature header")
            return False
        
        # GitHub sends signature as 'sha256=<hash>'
        if not signature.startswith('sha256='):
            logger.error("Invalid signature format")
            return False
        
        try:
            expected_signature = signature.replace('sha256=', '')
            
            # Calculate HMAC signature
            mac = hmac.new(
                self.webhook_secret.encode(),
                payload_body,
                digestmod=hashlib.sha256
            )
            computed_signature = mac.hexdigest()
            
            # Use timing-safe comparison
            is_valid = hmac.compare_digest(computed_signature, expected_signature)
            
            if not is_valid:
                logger.error("GitHub webhook signature verification failed")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying GitHub signature: {e}")
            return False
    
    def should_invalidate_cache(self, changed_files: List[str]) -> Dict[str, bool]:
        """
        Determine which cache patterns should be invalidated based on changed files.
        
        Args:
            changed_files: List of file paths that changed
        
        Returns:
            Dictionary mapping invalidation reasons to whether they should trigger
        """
        invalidation_needed = {
            "manifest": False,
            "js_files": False, 
            "html_files": False,
            "config": False,
            "icons": False,
            "addin_assets": False
        }
        
        for file_path in changed_files:
            file_path_lower = file_path.lower()
            
            # Check for manifest changes
            if "manifest.xml" in file_path_lower:
                invalidation_needed["manifest"] = True
                invalidation_needed["addin_assets"] = True
            
            # Check for JavaScript changes
            elif file_path_lower.endswith(('.js',)):
                invalidation_needed["js_files"] = True
                if "addin/" in file_path_lower:
                    invalidation_needed["addin_assets"] = True
                if "config.js" in file_path_lower:
                    invalidation_needed["config"] = True
            
            # Check for HTML changes
            elif file_path_lower.endswith(('.html',)):
                invalidation_needed["html_files"] = True
                if "addin/" in file_path_lower:
                    invalidation_needed["addin_assets"] = True
            
            # Check for icon changes
            elif file_path_lower.endswith(('.png', '.jpg', '.jpeg', '.ico')):
                invalidation_needed["icons"] = True
                invalidation_needed["addin_assets"] = True
            
            # Check for CSS changes
            elif file_path_lower.endswith(('.css',)):
                invalidation_needed["addin_assets"] = True
        
        return invalidation_needed
    
    async def invalidate_caches(self, invalidation_map: Dict[str, bool]) -> Dict[str, int]:
        """
        Perform cache invalidation based on the invalidation map.
        
        Args:
            invalidation_map: Map of cache types to invalidate
        
        Returns:
            Dictionary with invalidation results (keys deleted per cache type)
        """
        results = {}
        total_deleted = 0
        
        try:
            from app.redis_cache_manager import get_cache_manager
            from app.azure_cdn_manager import get_cdn_manager, purge_cdn_on_manifest_change
            
            cache_manager = await get_cache_manager()
            
            if not cache_manager._connected:
                logger.warning("Redis cache not connected - skipping invalidation")
                return {"error": "cache_not_connected"}
            
            # Invalidate each cache pattern as needed
            for cache_type, should_invalidate in invalidation_map.items():
                if should_invalidate:
                    pattern = self.cache_invalidation_patterns.get(cache_type, f"well:{cache_type}:*")
                    deleted_count = await cache_manager.invalidate_cache(pattern)
                    results[cache_type] = deleted_count
                    total_deleted += deleted_count
                    
                    logger.info(f"Invalidated {deleted_count} entries for pattern: {pattern}")
            
            # CDN cache purging for manifest-related changes
            manifest_related = any(
                invalidation_map.get(key, False) 
                for key in ["manifest", "js_files", "html_files", "icons", "addin_assets"]
            )
            
            if manifest_related:
                try:
                    # Get current manifest version from environment
                    current_version = os.getenv("MANIFEST_VERSION", "1.3.0.2")
                    
                    logger.info("Triggering CDN cache purge for manifest changes")
                    cdn_result = await purge_cdn_on_manifest_change(
                        changed_files=["manifest.xml", "taskpane.html", "commands.html"],
                        manifest_version=current_version
                    )
                    
                    results["cdn_purge"] = cdn_result
                    logger.info(f"CDN purge completed: {cdn_result.get('success', False)}")
                    
                except Exception as cdn_error:
                    logger.warning(f"CDN purge failed, continuing with Redis invalidation: {cdn_error}")
                    results["cdn_purge"] = {"success": False, "error": str(cdn_error)}
            
            # Update statistics
            self.stats["cache_invalidations"] += total_deleted
            
            return results
            
        except Exception as e:
            logger.error(f"Error during cache invalidation: {e}")
            self.stats["errors"] += 1
            return {"error": str(e)}
    
    async def process_push_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process GitHub push event and trigger cache invalidation if needed.
        
        Args:
            payload: GitHub push event payload
        
        Returns:
            Processing results
        """
        try:
            self.stats["webhooks_received"] += 1
            
            # Extract relevant information
            repository = payload.get("repository", {}).get("full_name", "unknown")
            branch = payload.get("ref", "").replace("refs/heads/", "")
            commits = payload.get("commits", [])
            
            logger.info(f"Processing push event for {repository} on branch {branch} with {len(commits)} commits")
            
            # Only process main/master branch changes
            if branch not in ["main", "master"]:
                logger.info(f"Ignoring push to branch: {branch}")
                return {
                    "status": "ignored",
                    "reason": f"Branch {branch} not monitored",
                    "repository": repository,
                    "branch": branch
                }
            
            # Collect all changed files from commits
            changed_files = set()
            for commit in commits:
                # Get added, modified, and removed files
                for file_list in [commit.get("added", []), commit.get("modified", []), commit.get("removed", [])]:
                    changed_files.update(file_list)
            
            logger.info(f"Total files changed: {len(changed_files)}")
            logger.debug(f"Changed files: {list(changed_files)}")
            
            # Determine cache invalidation needs
            invalidation_map = self.should_invalidate_cache(list(changed_files))
            needs_invalidation = any(invalidation_map.values())
            
            result = {
                "status": "processed",
                "repository": repository,
                "branch": branch,
                "commits_processed": len(commits),
                "files_changed": len(changed_files),
                "cache_invalidation_needed": needs_invalidation,
                "invalidation_map": invalidation_map,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if needs_invalidation:
                # Perform cache invalidation
                invalidation_results = await self.invalidate_caches(invalidation_map)
                result["invalidation_results"] = invalidation_results
                result["total_cache_entries_deleted"] = sum(
                    v for v in invalidation_results.values() 
                    if isinstance(v, int)
                )
                
                logger.info(f"Cache invalidation completed: {result['total_cache_entries_deleted']} entries deleted")
            else:
                result["message"] = "No manifest-related files changed, cache invalidation skipped"
                logger.info("No cache invalidation needed for this push")
            
            self.stats["webhooks_processed"] += 1
            self.stats["last_processed"] = datetime.utcnow().isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing push event: {e}")
            self.stats["errors"] += 1
            raise
    
    async def process_webhook(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process GitHub webhook event.
        
        Args:
            event_type: GitHub event type (e.g., 'push', 'pull_request')
            payload: Event payload
        
        Returns:
            Processing results
        """
        if event_type == "push":
            return await self.process_push_event(payload)
        elif event_type == "ping":
            logger.info("Received GitHub webhook ping event")
            return {
                "status": "pong",
                "message": "Webhook endpoint is active",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            logger.info(f"Ignoring unsupported event type: {event_type}")
            return {
                "status": "ignored", 
                "reason": f"Event type '{event_type}' not supported",
                "supported_events": ["push", "ping"]
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get webhook processing statistics."""
        return {
            **self.stats,
            "webhook_secret_configured": bool(self.webhook_secret),
            "repository": self.github_repo,
            "watched_patterns": list(self.watched_patterns),
            "cache_patterns": self.cache_invalidation_patterns
        }


# Singleton instance
_webhook_handler: Optional[GitHubWebhookHandler] = None


def get_webhook_handler() -> GitHubWebhookHandler:
    """Get or create the singleton webhook handler."""
    global _webhook_handler
    
    if _webhook_handler is None:
        _webhook_handler = GitHubWebhookHandler()
    
    return _webhook_handler


# FastAPI Integration Functions
async def verify_github_webhook(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency for GitHub webhook verification.
    
    Args:
        request: FastAPI request object
    
    Returns:
        Verified payload and metadata
    
    Raises:
        HTTPException: If verification fails
    """
    handler = get_webhook_handler()
    
    try:
        # Get headers
        x_github_event = request.headers.get("X-GitHub-Event")
        x_hub_signature_256 = request.headers.get("X-Hub-Signature-256")
        
        if not x_github_event:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing X-GitHub-Event header"
            )
        
        # Get raw payload
        payload_body = await request.body()
        
        # Verify signature
        if not handler.verify_signature(payload_body, x_hub_signature_256):
            logger.error("GitHub webhook signature verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Parse payload
        try:
            payload = json.loads(payload_body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload"
            )
        
        return {
            "event_type": x_github_event,
            "payload": payload,
            "signature_verified": True,
            "payload_size": len(payload_body)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing error"
        )


async def handle_github_webhook(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle verified GitHub webhook data.
    
    Args:
        webhook_data: Verified webhook data from verify_github_webhook
    
    Returns:
        Processing results
    """
    handler = get_webhook_handler()
    
    try:
        return await handler.process_webhook(
            webhook_data["event_type"],
            webhook_data["payload"]
        )
        
    except Exception as e:
        logger.error(f"Webhook handling error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )


# Application Insights Integration
async def log_webhook_event(event_data: Dict[str, Any], processing_result: Dict[str, Any]):
    """
    Log webhook event to Application Insights for monitoring using available tracing.
    
    Args:
        event_data: Original webhook event data
        processing_result: Result from webhook processing
    """
    try:
        # Import monitoring service
        from app.monitoring import MonitoringService
        
        monitoring = MonitoringService()
        
        # Use OpenTelemetry tracing to log webhook events
        with monitoring.tracer.start_as_current_span("github_webhook_processed") as span:
            span.set_attribute("webhook_event_type", event_data.get("event_type", "unknown"))
            span.set_attribute("repository", processing_result.get("repository", "unknown"))
            span.set_attribute("branch", processing_result.get("branch", "unknown"))
            span.set_attribute("files_changed", processing_result.get("files_changed", 0))
            span.set_attribute("cache_invalidation_needed", processing_result.get("cache_invalidation_needed", False))
            span.set_attribute("cache_entries_deleted", processing_result.get("total_cache_entries_deleted", 0))
            span.set_attribute("processing_status", processing_result.get("status", "unknown"))
            
            # Add webhook source information
            span.set_attribute("event_source", "github_webhook")
            span.set_attribute("handler_version", "1.0")
        
        logger.info("Webhook event traced to Application Insights")
        
    except Exception as e:
        logger.warning(f"Failed to log webhook event to Application Insights: {e}")


# Retry Logic for Cache Operations
@asynccontextmanager
async def retry_cache_operation(max_retries: int = 3, delay: float = 1.0):
    """
    Context manager for retrying cache operations with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Base delay between retries in seconds
    """
    for attempt in range(max_retries + 1):
        try:
            yield attempt
            break
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Cache operation failed after {max_retries + 1} attempts: {e}")
                raise
            
            wait_time = delay * (2 ** attempt)  # Exponential backoff
            logger.warning(f"Cache operation failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {wait_time}s: {e}")
            await asyncio.sleep(wait_time)