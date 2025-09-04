from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import re

# --- API Data Contracts ---

class AttachmentPayload(BaseModel):
    filename: str
    content_base64: str
    content_type: str

class EmailPayload(BaseModel):
    sender_name: Optional[str] = None
    sender_email: str
    subject: str
    body: str
    attachments: List[AttachmentPayload] = []
    raw_email: Optional[str] = Field(None, description="Raw email content for metadata extraction")
    reply_to: Optional[str] = Field(None, description="Reply-To header if different from sender")
    internet_message_id: Optional[str] = Field(None, description="Unique message ID from the email provider (e.g., Graph 'id')")
    user_corrections: Optional[Dict[str, Any]] = Field(None, description="User corrections to AI extraction")
    ai_extraction: Optional[Dict[str, Any]] = Field(None, description="Original AI extraction for learning")
    dry_run: Optional[bool] = Field(False, description="If true, run extraction only and return preview without creating Zoho records")

class ExtractedData(BaseModel):
    candidate_name: Optional[str] = Field(None, description="The full name of the candidate.")
    job_title: Optional[str] = Field(None, description="The job title being discussed (e.g., Advisor).")
    location: Optional[str] = Field(None, description="The location for the role (e.g., Fort Wayne, Indiana).")
    company_name: Optional[str] = Field(None, description="The official name of the candidate's firm.")
    referrer_name: Optional[str] = Field(None, description="The full name of the person who made the referral.")
    referrer_email: Optional[str] = Field(None, description="Email address of the referrer.")
    email: Optional[str] = Field(None, description="Email address of the candidate.")
    website: Optional[str] = Field(None, description="Company website URL.")
    phone: Optional[str] = Field(None, description="Contact phone number.")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL.")
    calendly_url: Optional[str] = Field(None, description="Calendly scheduling link.")
    notes: Optional[str] = Field(None, description="Additional notes or context from the email.")
    industry: Optional[str] = Field(None, description="Company industry or sector.")
    source: Optional[str] = Field(None, description="Lead source (e.g., Referral, Email Inbound).")
    source_detail: Optional[str] = Field(None, description="Additional source details (e.g., referrer name for Source field).")

class ProcessingResult(BaseModel):
    status: str
    message: str
    deal_id: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    deal_name: Optional[str] = Field(None, description="The formatted deal name that was created")
    primary_email: Optional[str] = Field(None, description="The email address used (Reply-To or From)")
    extracted: Optional[ExtractedData] = Field(None, description="Extracted data preview for dry_run flows")

class HealthStatus(BaseModel):
    status: str
    version: str
    business_rules: str
    zoho_api: str
    services: dict = Field(default_factory=dict)

# --- Manifest Versioning Models ---

class ManifestVersion(BaseModel):
    """Model for tracking Outlook add-in manifest versions."""
    version: str = Field(..., description="Semantic version string (e.g., 1.3.0.1)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Version creation timestamp")
    environment: Literal["development", "staging", "production"] = Field("production", description="Target environment")
    cache_key: str = Field(..., description="Unique cache key for this version")
    changelog: Optional[str] = Field(None, description="Version changelog or description")
    is_active: bool = Field(True, description="Whether this version is currently active")
    
    @validator("version")
    def validate_version_format(cls, v):
        """Validate semantic version format."""
        if not re.match(r'^\d+\.\d+\.\d+\.\d+$', v):
            raise ValueError("Version must follow semantic versioning format (e.g., 1.3.0.1)")
        return v
    
    @validator("cache_key")
    def validate_cache_key(cls, v):
        """Ensure cache key is non-empty and valid."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Cache key cannot be empty")
        return v.strip()

class ManifestTemplate(BaseModel):
    """Model for storing manifest XML templates with dynamic placeholders."""
    template_id: str = Field(..., description="Unique identifier for this template")
    template_content: str = Field(..., description="XML template content with placeholders")
    placeholders: Dict[str, str] = Field(default_factory=dict, description="Available placeholder variables")
    resource_urls: Dict[str, str] = Field(default_factory=dict, description="Resource URLs mapping")
    environment: Optional[str] = Field(None, description="Target environment for this template")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Template creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    @validator("template_content")
    def validate_template_content(cls, v):
        """Ensure template contains valid XML structure."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Template content cannot be empty")
        if "<?xml" not in v:
            raise ValueError("Template must contain XML declaration")
        return v

class CacheBustConfig(BaseModel):
    """Configuration for cache busting strategies."""
    ttl: int = Field(300, description="Cache TTL in seconds", ge=0)
    invalidation_triggers: List[str] = Field(
        default_factory=lambda: ["push", "release", "manual"], 
        description="Events that trigger cache invalidation"
    )
    fallback_strategy: Literal["serve_stale", "force_refresh", "error"] = Field(
        "serve_stale", 
        description="Strategy when cache is unavailable"
    )
    max_age: int = Field(3600, description="Maximum cache age in seconds", ge=0)
    cache_headers: Dict[str, str] = Field(
        default_factory=lambda: {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        },
        description="HTTP cache control headers"
    )
    
    @validator("ttl", "max_age")
    def validate_positive_values(cls, v):
        """Ensure TTL and max_age are positive."""
        if v < 0:
            raise ValueError("TTL and max_age must be non-negative")
        return v

class WebhookPayload(BaseModel):
    """Model for GitHub webhook payloads that trigger manifest updates."""
    repository: str = Field(..., description="Repository name (e.g., 'owner/repo')")
    ref: str = Field(..., description="Git reference (e.g., 'refs/heads/main')")
    commits: List[Dict[str, Any]] = Field(default_factory=list, description="List of commit objects")
    changed_files: List[str] = Field(default_factory=list, description="List of changed file paths")
    pusher_name: Optional[str] = Field(None, description="Name of the person who pushed")
    pusher_email: Optional[str] = Field(None, description="Email of the person who pushed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Webhook received timestamp")
    event_type: Literal["push", "release", "pull_request"] = Field("push", description="GitHub event type")
    
    @validator("repository")
    def validate_repository_format(cls, v):
        """Validate repository name format."""
        if not re.match(r'^[\w\-\.]+/[\w\-\.]+$', v):
            raise ValueError("Repository must be in 'owner/repo' format")
        return v

class CacheOperation(BaseModel):
    """Model for tracking cache operations and their results."""
    operation_type: Literal["get", "set", "delete", "invalidate", "warmup"] = Field(..., description="Type of cache operation")
    key: str = Field(..., description="Cache key used in operation")
    ttl: Optional[int] = Field(None, description="TTL used for set operations", ge=0)
    success: bool = Field(..., description="Whether the operation was successful")
    response_time_ms: Optional[float] = Field(None, description="Operation response time in milliseconds", ge=0)
    error_message: Optional[str] = Field(None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Operation timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional operation metadata")
    
    @validator("key")
    def validate_cache_key(cls, v):
        """Ensure cache key is valid."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Cache key cannot be empty")
        return v.strip()

# --- Manifest Versioning Response Models ---

class ManifestVersionResponse(BaseModel):
    """Response model for manifest version operations."""
    version: ManifestVersion
    template_applied: bool = Field(False, description="Whether template was successfully applied")
    cache_updated: bool = Field(False, description="Whether cache was updated")
    manifest_url: Optional[str] = Field(None, description="URL to the generated manifest")
    
class CacheBustResponse(BaseModel):
    """Response model for cache busting operations."""
    operations: List[CacheOperation] = Field(default_factory=list, description="List of cache operations performed")
    total_keys_invalidated: int = Field(0, description="Total number of cache keys invalidated")
    success_rate: float = Field(0.0, description="Success rate of operations (0.0-1.0)", ge=0.0, le=1.0)
    duration_ms: float = Field(0.0, description="Total operation duration in milliseconds", ge=0.0)
