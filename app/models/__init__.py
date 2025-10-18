"""
Models Package

Exports all Pydantic models for the application:
- Email processing models (EmailPayload, ProcessingResult, ExtractedData, etc.)
- Zoho sync models (ZohoModule, WebhookEventType, ZohoSyncMessage, etc.)
"""

# Import email/processing models
from app.models.email_models import (
    AttachmentPayload,
    EmailPayload,
    ProcessingResult,
    ExtractedData,
    CompanyRecord,
    ContactRecord,
    DealRecord,
    WeeklyDigestFilters,
    # Add any other exports from email_models.py that are used
)

# Import Zoho sync models
from app.models.zoho_sync_models import (
    ZohoModule,
    WebhookEventType,
    ProcessingStatus,
    ConflictType,
    ResolutionStrategy,
    ZohoWebhookLogEntry,
    ZohoSyncMessage,
    ZohoSyncConflict,
    ZohoRecordBase,
)

__all__ = [
    # Email/processing models
    "AttachmentPayload",
    "EmailPayload",
    "ProcessingResult",
    "ExtractedData",
    "CompanyRecord",
    "ContactRecord",
    "DealRecord",
    "WeeklyDigestFilters",
    # Zoho sync models
    "ZohoModule",
    "WebhookEventType",
    "ProcessingStatus",
    "ConflictType",
    "ResolutionStrategy",
    "ZohoWebhookLogEntry",
    "ZohoSyncMessage",
    "ZohoSyncConflict",
    "ZohoRecordBase",
]
