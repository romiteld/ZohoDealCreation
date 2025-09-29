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
    original_sender_email: Optional[str] = Field(None, description="Actual sender email for learning pipeline (vs operational override)")
    original_sender_name: Optional[str] = Field(None, description="Actual sender name for learning context")
    subject: str
    body: str
    attachments: List[AttachmentPayload] = []
    raw_email: Optional[str] = Field(None, description="Raw email content for metadata extraction")
    reply_to: Optional[str] = Field(None, description="Reply-To header if different from sender")
    internet_message_id: Optional[str] = Field(None, description="Unique message ID from the email provider (e.g., Graph 'id')")
    user_corrections: Optional[Dict[str, Any]] = Field(None, description="User corrections to AI extraction")
    ai_extraction: Optional[Dict[str, Any]] = Field(None, description="Original AI extraction for learning")
    dry_run: Optional[bool] = Field(False, description="If true, run extraction only and return preview without creating Zoho records")
    user_context: Optional[Dict[str, str]] = Field(None, description="Current Outlook user context (name, email) to ignore in extraction")
    # Optional Graph enrichment fields (Chrome extension thin client)
    graph_access_token: Optional[str] = Field(None, description="Bearer token for Microsoft Graph to fetch the message")
    graph_message_id: Optional[str] = Field(None, description="Microsoft Graph message id (me/messages/{id})")
    graph_conversation_id: Optional[str] = Field(None, description="Graph conversationId for context")

# Steve's Template Structure Models
class CompanyRecord(BaseModel):
    """Company Record fields matching Steve's template"""
    company_name: Optional[str] = Field(None, description="Official company name")
    phone: Optional[str] = Field(None, description="Company phone number")
    website: Optional[str] = Field(None, description="Company website URL")
    company_source: Optional[str] = Field(None, description="How company was sourced (e.g., Conference/Trade Show)")
    source_detail: Optional[str] = Field(None, description="Specific source detail (e.g., FutureProof 2026)")
    who_gets_credit: Optional[str] = Field(None, description="BD Rep, Affiliate, or Both")
    detail: Optional[str] = Field(None, description="Person name who gets credit (e.g., Steve Perry)")

class ContactRecord(BaseModel):
    """Contact Record fields matching Steve's template"""
    first_name: Optional[str] = Field(None, description="Contact's first name")
    last_name: Optional[str] = Field(None, description="Contact's last name")
    company_name: Optional[str] = Field(None, description="Contact's company name")
    email: Optional[str] = Field(None, description="Contact's email address")
    phone: Optional[str] = Field(None, description="Contact's phone number")
    city: Optional[str] = Field(None, description="Contact's city")
    state: Optional[str] = Field(None, description="Contact's state")
    source: Optional[str] = Field(None, description="Contact source (e.g., Conference/Trade Show)")

class DealRecord(BaseModel):
    """Deal Record fields matching Steve's template"""
    source: Optional[str] = Field(None, description="Deal source (e.g., Conference/Trade Show)")
    deal_name: Optional[str] = Field(None, description="Formatted deal name (e.g., Advisors (Nationwide) Capital Investment Advisors)")
    pipeline: Optional[str] = Field("Sales Pipeline", description="Pipeline name (ALWAYS 'Sales Pipeline')")
    closing_date: Optional[str] = Field(None, description="Estimated closing date (YYYY-MM-DD)")
    source_detail: Optional[str] = Field(None, description="Source detail (e.g., FutureProof 2026)")
    description_of_reqs: Optional[str] = Field(None, description="Description of requirements/needs")

class GeoResult(BaseModel):
    """Geocoding result from Azure Maps."""
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")
    address: Optional[Dict[str, Any]] = Field(None, description="Address components")
    formatted_address: Optional[str] = Field(None, description="Full formatted address")
    confidence: Optional[float] = Field(None, description="Geocoding confidence score")

class ExtractedData(BaseModel):
    """Main extracted data structure with Steve's 3-record format and financial advisor enhancements"""
    company_record: Optional[CompanyRecord] = Field(None, description="Company information")
    contact_record: Optional[ContactRecord] = Field(None, description="Contact information")
    deal_record: Optional[DealRecord] = Field(None, description="Deal information")

    # Financial Advisor specific fields
    aum_managed: Optional[str] = Field(None, description="Assets Under Management (e.g., $180M, $1.2B)")
    production_annual: Optional[str] = Field(None, description="Annual production/revenue (e.g., $650K, $1.5M)")
    client_count: Optional[str] = Field(None, description="Number of clients managed (e.g., 180 clients)")
    licenses_held: Optional[List[str]] = Field(None, description="Professional licenses (e.g., Series 7, Series 66)")
    designations: Optional[List[str]] = Field(None, description="Professional designations (e.g., CFA, CFP, CPWA)")
    years_experience: Optional[str] = Field(None, description="Years of experience in financial services")
    availability_timeframe: Optional[str] = Field(None, description="When available (e.g., Immediately, 30 days notice)")
    compensation_range: Optional[str] = Field(None, description="Desired compensation range (e.g., $425K-$500K)")
    book_transferable: Optional[str] = Field(None, description="Percentage of book transferable (e.g., 85% transferable)")
    specializations: Optional[List[str]] = Field(None, description="Areas of specialization (e.g., High-net-worth, Estate planning)")

    # Legacy fields for backward compatibility - will be deprecated
    candidate_name: Optional[str] = Field(None, description="DEPRECATED: Use contact_record.first_name + last_name")
    job_title: Optional[str] = Field(None, description="DEPRECATED: Use deal_record.deal_name")
    location: Optional[str] = Field(None, description="DEPRECATED: Use contact_record.city + state")
    company_name: Optional[str] = Field(None, description="DEPRECATED: Use company_record.company_name")
    referrer_name: Optional[str] = Field(None, description="DEPRECATED: Use company_record.detail")
    referrer_email: Optional[str] = Field(None, description="DEPRECATED: Not in Steve's template")
    email: Optional[str] = Field(None, description="DEPRECATED: Use contact_record.email")
    website: Optional[str] = Field(None, description="DEPRECATED: Use company_record.website")
    phone: Optional[str] = Field(None, description="DEPRECATED: Use contact_record.phone")
    linkedin_url: Optional[str] = Field(None, description="DEPRECATED: Not in Steve's template")
    notes: Optional[str] = Field(None, description="DEPRECATED: Use deal_record.description_of_reqs")
    industry: Optional[str] = Field(None, description="DEPRECATED: Not in Steve's template")
    source: Optional[str] = Field(None, description="DEPRECATED: Use deal_record.source")
    source_detail: Optional[str] = Field(None, description="DEPRECATED: Use deal_record.source_detail")

class ProcessingResult(BaseModel):
    status: str
    message: str
    deal_id: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    deal_name: Optional[str] = Field(None, description="The formatted deal name that was created")
    primary_email: Optional[str] = Field(None, description="The email address used (Reply-To or From)")
    extracted: Optional[ExtractedData] = Field(None, description="Extracted data preview for dry_run flows")
    saved_to_db: Optional[bool] = Field(None, description="Whether the deal was saved to database")
    saved_to_zoho: Optional[bool] = Field(None, description="Whether the deal was saved to Zoho CRM")
    correlation_id: Optional[str] = Field(None, description="Unique correlation ID for tracking this request")
    missing_fields: Optional[list] = Field(None, description="List of missing fields if user input is required")
    duplicate_info: Optional[dict] = Field(None, description="Information about duplicate records if found")

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

class WeeklyDigestFilters(BaseModel):
    """Model for TalentWell weekly digest test-send filters."""
    audience: Optional[str] = Field(default="global", description="Target audience for digest")
    owner: Optional[str] = Field(None, description="Deal owner filter")
    from_: Optional[str] = Field(None, alias="from", description="Start date (YYYY-MM-DD)")
    to_date: Optional[str] = Field(None, alias="to", description="End date (YYYY-MM-DD)")  
    max_candidates: Optional[int] = Field(default=6, description="Maximum number of candidates", ge=1, le=50)
    recipients: Optional[List[str]] = Field(None, description="Email recipients")
    dry_run: Optional[bool] = Field(default=False, description="Return HTML without sending")
    fallback_if_empty: Optional[bool] = Field(default=True, description="Retry with wider criteria if no candidates found")
    ignore_cooldown: Optional[bool] = Field(default=False, description="Ignore 4-week cooldown for recently sent candidates")
    
    @validator("from_", "to_date")
    def validate_dates(cls, v):
        """Validate date format if provided."""
        if v:
            try:
                from datetime import datetime
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format")
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
