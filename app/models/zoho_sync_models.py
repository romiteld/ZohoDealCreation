"""
Pydantic models for Zoho CRM continuous sync system.

Provides type-safe message contracts between:
- Webhook receiver → Service Bus
- Service Bus → Worker
- Worker → Database

All models include JSON schema definitions for validation and documentation.
"""

from pydantic import BaseModel, Field, validator, constr
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class ZohoModule(str, Enum):
    """Supported Zoho CRM modules"""
    LEADS = "Leads"
    DEALS = "Deals"
    CONTACTS = "Contacts"
    ACCOUNTS = "Accounts"


class WebhookEventType(str, Enum):
    """Zoho webhook event types"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EDIT = "edit"  # Alias for update in some Zoho versions


class ProcessingStatus(str, Enum):
    """Webhook log processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictType(str, Enum):
    """Types of sync conflicts"""
    STALE_UPDATE = "stale_update"  # Incoming Modified_Time < stored Modified_Time
    CONCURRENT_WRITE = "concurrent_write"  # Race condition
    MISSING_RECORD = "missing_record"  # Update for non-existent record


class ResolutionStrategy(str, Enum):
    """Conflict resolution strategies"""
    LAST_WRITE_WINS = "last_write_wins"  # Default: use Modified_Time
    MANUAL_REVIEW = "manual_review"  # Flag for admin review
    DISCARD = "discard"  # Ignore incoming update


# =============================================================================
# WEBHOOK LOG MODELS
# =============================================================================

class ZohoWebhookLogEntry(BaseModel):
    """
    Webhook log entry stored in zoho_webhook_log table.

    Persists raw webhook payloads for audit trail and replay capability.
    """
    id: Optional[str] = Field(None, description="UUID primary key (auto-generated)")
    module: ZohoModule = Field(..., description="Zoho CRM module name")
    event_type: WebhookEventType = Field(..., description="Webhook event type")
    zoho_id: constr(pattern=r'^\d+$') = Field(..., description="Zoho record ID (18-digit numeric)")
    payload_raw: Dict[str, Any] = Field(..., description="Full webhook payload from Zoho (JSONB)")
    payload_sha256: constr(min_length=64, max_length=64) = Field(
        ...,
        description="SHA-256 hash of sorted payload for deduplication"
    )
    received_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when webhook was received (ISO 8601)"
    )
    processed_at: Optional[datetime] = Field(None, description="Timestamp when worker completed processing")
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.PENDING,
        description="Current processing status"
    )
    error_message: Optional[str] = Field(None, description="Error details if processing failed")
    retry_count: int = Field(default=0, ge=0, description="Number of worker retry attempts")

    # Wrapper metadata for audit trail
    wrapper_operation: Optional[str] = Field(
        None,
        description="Raw operation string from Zoho wrapper (e.g., 'Leads.edit', 'Deals.create')"
    )
    wrapper_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Full wrapper context from Zoho (source, user, timestamp, etc.)"
    )

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "module": "Leads",
                "event_type": "update",
                "zoho_id": "6221978000123456789",
                "payload_raw": {
                    "id": "6221978000123456789",
                    "Full_Name": "John Doe",
                    "Modified_Time": "2025-10-17T14:30:00Z"
                },
                "payload_sha256": "abc123def456...",
                "received_at": "2025-10-17T14:30:01Z",
                "processed_at": None,
                "processing_status": "pending",
                "error_message": None,
                "retry_count": 0
            }
        }


# =============================================================================
# SERVICE BUS MESSAGE MODELS
# =============================================================================

class ZohoSyncMessage(BaseModel):
    """
    Compact message enqueued to Azure Service Bus (zoho-sync-events queue).

    Contains minimal data to identify the webhook; worker fetches full payload
    from zoho_webhook_log table using log_id.
    """
    log_id: str = Field(..., description="Reference to zoho_webhook_log.id (UUID)")
    module: ZohoModule = Field(..., description="Zoho CRM module name")
    event_type: WebhookEventType = Field(..., description="Webhook event type")
    zoho_id: constr(pattern=r'^\d+$') = Field(..., description="Zoho record ID")
    modified_time: datetime = Field(..., description="Modified_Time from Zoho payload (ISO 8601)")
    payload_sha: constr(min_length=64, max_length=64) = Field(
        ...,
        description="SHA-256 hash for deduplication matching"
    )
    retry_count: int = Field(default=0, ge=0, description="Service Bus delivery attempt count")
    enqueued_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when message was enqueued"
    )

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "log_id": "550e8400-e29b-41d4-a716-446655440000",
                "module": "Leads",
                "event_type": "update",
                "zoho_id": "6221978000123456789",
                "modified_time": "2025-10-17T14:30:00Z",
                "payload_sha": "abc123def456...",
                "retry_count": 0,
                "enqueued_at": "2025-10-17T14:30:02Z"
            }
        }


# =============================================================================
# SYNC CONFLICT MODELS
# =============================================================================

class ZohoSyncConflict(BaseModel):
    """
    Sync conflict record stored in zoho_sync_conflicts table.

    Logged when incoming Modified_Time predates stored row (stale update).
    """
    id: Optional[str] = Field(None, description="UUID primary key (auto-generated)")
    module: ZohoModule = Field(..., description="Zoho CRM module name")
    zoho_id: constr(pattern=r'^\d+$') = Field(..., description="Zoho record ID")
    conflict_type: ConflictType = Field(..., description="Type of conflict detected")
    incoming_modified_time: datetime = Field(..., description="Modified_Time from incoming payload")
    existing_modified_time: Optional[datetime] = Field(None, description="Modified_Time from stored row")
    previous_snapshot: Optional[Dict[str, Any]] = Field(
        None,
        description="Full row state before conflict (for manual review)"
    )
    incoming_payload: Dict[str, Any] = Field(..., description="Incoming Zoho payload that caused conflict")
    resolution_strategy: ResolutionStrategy = Field(
        default=ResolutionStrategy.LAST_WRITE_WINS,
        description="How conflict was/will be resolved"
    )
    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when conflict was detected"
    )
    resolved_at: Optional[datetime] = Field(None, description="Timestamp when conflict was resolved")
    resolved_by: Optional[str] = Field(None, description="Email of person who resolved conflict")
    resolution_notes: Optional[str] = Field(None, description="Admin notes about resolution")

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "id": "660e8400-e29b-41d4-a716-446655440001",
                "module": "Leads",
                "zoho_id": "6221978000123456789",
                "conflict_type": "stale_update",
                "incoming_modified_time": "2025-10-17T12:00:00Z",
                "existing_modified_time": "2025-10-17T14:00:00Z",
                "previous_snapshot": {"Full_Name": "John Doe", "sync_version": 3},
                "incoming_payload": {"Full_Name": "John Smith"},
                "resolution_strategy": "last_write_wins",
                "detected_at": "2025-10-17T14:30:00Z",
                "resolved_at": None,
                "resolved_by": None,
                "resolution_notes": None
            }
        }


# =============================================================================
# MODULE RECORD MODELS
# =============================================================================

class ZohoRecordBase(BaseModel):
    """Base model for Zoho module records (Leads, Deals, Contacts, Accounts)"""
    zoho_id: constr(pattern=r'^\d+$') = Field(..., description="Zoho record ID (primary key)")
    owner_email: str = Field(..., description="Record owner email")
    owner_name: Optional[str] = Field(None, description="Record owner name")
    created_time: datetime = Field(..., description="Created_Time from Zoho")
    modified_time: datetime = Field(..., description="Modified_Time from Zoho (for conflict detection)")
    last_synced_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last successful sync timestamp"
    )
    data_payload: Dict[str, Any] = Field(..., description="Full Zoho record as JSONB")
    sync_version: int = Field(default=1, ge=1, description="Increments on each update (optimistic locking)")

    @validator('data_payload')
    def validate_payload_not_empty(cls, v):
        if not v:
            raise ValueError("data_payload cannot be empty")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "zoho_id": "6221978000123456789",
                "owner_email": "steve.perry@emailthewell.com",
                "owner_name": "Steve Perry",
                "created_time": "2025-01-15T10:00:00Z",
                "modified_time": "2025-10-17T14:30:00Z",
                "last_synced_at": "2025-10-17T14:30:05Z",
                "data_payload": {
                    "id": "6221978000123456789",
                    "Full_Name": "John Doe",
                    "Employer": "Advisory Firm",
                    "Book_Size_AUM": "$50M"
                },
                "sync_version": 1
            }
        }


class ZohoLeadRecord(ZohoRecordBase):
    """Zoho Lead record (vault candidates)"""
    pass


class ZohoDealRecord(ZohoRecordBase):
    """Zoho Deal record"""
    pass


class ZohoContactRecord(ZohoRecordBase):
    """Zoho Contact record"""
    pass


class ZohoAccountRecord(ZohoRecordBase):
    """Zoho Account record"""
    pass


# =============================================================================
# ADMIN/API RESPONSE MODELS
# =============================================================================

class ModuleSyncStatus(BaseModel):
    """Per-module sync status for admin dashboard"""
    module: ZohoModule
    status: Literal["healthy", "degraded", "unhealthy"]
    lag_seconds: float = Field(..., description="Time since last successful sync")
    last_sync: datetime
    webhook_count_24h: int = Field(..., description="Webhooks received in last 24 hours")
    polling_count_24h: int = Field(..., description="Polling sync operations in last 24 hours")
    conflict_count_24h: int = Field(..., description="Conflicts detected in last 24 hours")
    dedupe_hit_rate: float = Field(..., ge=0.0, le=1.0, description="Redis cache hit rate (0.0-1.0)")

    class Config:
        use_enum_values = True


class ServiceBusQueueStatus(BaseModel):
    """Azure Service Bus queue metrics"""
    queue_depth: int = Field(..., description="Total messages in queue")
    active_message_count: int = Field(..., description="Messages being processed")
    dead_letter_count: int = Field(..., description="Messages in dead-letter queue")


class SyncConflictSummary(BaseModel):
    """Summary of recent unresolved conflicts"""
    module: ZohoModule
    zoho_id: str
    detected_at: datetime
    conflict_type: ConflictType

    class Config:
        use_enum_values = True


class SyncAlert(BaseModel):
    """Alert triggered by monitoring system"""
    severity: Literal["info", "warning", "error", "critical"]
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ZohoSyncStatusResponse(BaseModel):
    """Complete sync status response for admin endpoint"""
    modules: Dict[str, ModuleSyncStatus]
    service_bus: ServiceBusQueueStatus
    conflicts: list[SyncConflictSummary]
    alerts: list[SyncAlert]
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "modules": {
                    "Leads": {
                        "module": "Leads",
                        "status": "healthy",
                        "lag_seconds": 3.2,
                        "last_sync": "2025-10-17T14:45:00Z",
                        "webhook_count_24h": 1523,
                        "polling_count_24h": 96,
                        "conflict_count_24h": 2,
                        "dedupe_hit_rate": 0.15
                    }
                },
                "service_bus": {
                    "queue_depth": 12,
                    "active_message_count": 3,
                    "dead_letter_count": 0
                },
                "conflicts": [],
                "alerts": [],
                "last_updated": "2025-10-17T14:50:00Z"
            }
        }


# =============================================================================
# WEBHOOK CHALLENGE MODEL (for Zoho verification)
# =============================================================================

class ZohoWebhookChallenge(BaseModel):
    """Zoho webhook verification challenge during registration"""
    challenge: str = Field(..., description="Challenge string from Zoho")

    class Config:
        json_schema_extra = {
            "example": {
                "challenge": "abc123xyz789..."
            }
        }
