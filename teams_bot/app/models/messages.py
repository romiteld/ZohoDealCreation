"""Azure Service Bus message schemas for Teams bot.

This module defines Pydantic models for messages sent through Azure Service Bus
queues for asynchronous processing of Teams bot requests.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class MessagePriority(str, Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DigestAudience(str, Enum):
    """Digest audience types."""
    ADVISORS = "advisors"
    C_SUITE = "c_suite"
    GLOBAL = "global"
    PERSONAL = "personal"


class BaseMessage(BaseModel):
    """Base message model with common fields."""

    message_id: UUID = Field(default_factory=uuid4, description="Unique message identifier")
    correlation_id: Optional[UUID] = Field(default=None, description="Correlation ID for tracking related messages")
    session_id: Optional[str] = Field(default=None, description="Session ID for ordered processing")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message creation timestamp")
    ttl_seconds: int = Field(default=3600, description="Time to live in seconds", ge=60, le=86400)
    priority: MessagePriority = Field(default=MessagePriority.NORMAL, description="Message priority")
    retry_count: int = Field(default=0, description="Number of retry attempts", ge=0, le=10)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator('ttl_seconds')
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        """Validate TTL is within reasonable bounds."""
        if v < 60:
            raise ValueError("TTL must be at least 60 seconds")
        if v > 86400:
            raise ValueError("TTL cannot exceed 24 hours (86400 seconds)")
        return v

    def to_service_bus_message(self) -> Dict[str, Any]:
        """Convert to Service Bus message format.

        Returns:
            Dict containing message body and properties for Service Bus.
        """
        return {
            "body": self.model_dump_json(),
            "application_properties": {
                "message_type": self.__class__.__name__,
                "priority": self.priority.value,
                "correlation_id": str(self.correlation_id) if self.correlation_id else None,
                "timestamp": self.timestamp.isoformat(),
            },
            "time_to_live": timedelta(seconds=self.ttl_seconds),
            "session_id": self.session_id,
        }

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class DigestRequestMessage(BaseMessage):
    """Message schema for digest generation requests.

    Example:
        >>> message = DigestRequestMessage(
        ...     conversation_id="conv_123",
        ...     service_url="https://smba.trafficmanager.net/amer/",
        ...     audience=DigestAudience.ADVISORS,
        ...     user_email="user@example.com",
        ...     date_range_days=7,
        ...     include_vault=True
        ... )
    """

    conversation_id: str = Field(..., description="Teams conversation ID", min_length=1)
    service_url: str = Field(..., description="Teams service URL for replies", min_length=1)
    audience: DigestAudience = Field(..., description="Target audience for digest")
    user_email: str = Field(..., description="Requesting user's email", min_length=5)
    user_name: Optional[str] = Field(default=None, description="User's display name")
    tenant_id: Optional[str] = Field(default=None, description="Teams tenant ID")
    date_range_days: int = Field(default=7, description="Days to include in digest", ge=1, le=365)
    include_vault: bool = Field(default=True, description="Include vault candidates")
    include_deals: bool = Field(default=True, description="Include active deals")
    include_meetings: bool = Field(default=True, description="Include recent meetings")
    format_type: str = Field(default="html", description="Output format (html/markdown/text)")

    @field_validator('service_url')
    @classmethod
    def validate_service_url(cls, v: str) -> str:
        """Validate service URL format."""
        if not v.startswith(('https://', 'http://')):
            raise ValueError("Service URL must start with http:// or https://")
        return v

    @field_validator('user_email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation."""
        if '@' not in v:
            raise ValueError("Invalid email format")
        return v.lower()


class NLPQueryMessage(BaseMessage):
    """Message schema for natural language query requests.

    Example:
        >>> message = NLPQueryMessage(
        ...     conversation_id="conv_456",
        ...     service_url="https://smba.trafficmanager.net/amer/",
        ...     query_text="Show me all deals closing this month",
        ...     user_email="user@example.com",
        ...     max_results=10
        ... )
    """

    conversation_id: str = Field(..., description="Teams conversation ID", min_length=1)
    service_url: str = Field(..., description="Teams service URL for replies", min_length=1)
    query_text: str = Field(..., description="Natural language query", min_length=1, max_length=1000)
    user_email: str = Field(..., description="Requesting user's email", min_length=5)
    user_name: Optional[str] = Field(default=None, description="User's display name")
    tenant_id: Optional[str] = Field(default=None, description="Teams tenant ID")
    context_window: Optional[Dict[str, Any]] = Field(default=None, description="Previous conversation context")
    max_results: int = Field(default=20, description="Maximum results to return", ge=1, le=100)
    include_metadata: bool = Field(default=True, description="Include result metadata")
    response_format: str = Field(default="card", description="Response format (card/table/text)")

    @field_validator('query_text')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate and clean query text."""
        # Remove excessive whitespace
        v = ' '.join(v.split())
        if len(v) < 3:
            raise ValueError("Query must be at least 3 characters")
        return v

    @field_validator('service_url')
    @classmethod
    def validate_service_url(cls, v: str) -> str:
        """Validate service URL format."""
        if not v.startswith(('https://', 'http://')):
            raise ValueError("Service URL must start with http:// or https://")
        return v

    @field_validator('user_email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation."""
        if '@' not in v:
            raise ValueError("Invalid email format")
        return v.lower()


class QueueMetricsResponse(BaseModel):
    """Response model for queue metrics."""

    queue_name: str = Field(..., description="Name of the queue")
    active_messages: int = Field(..., description="Number of active messages", ge=0)
    dead_letter_messages: int = Field(..., description="Number of dead letter messages", ge=0)
    scheduled_messages: int = Field(..., description="Number of scheduled messages", ge=0)
    transfer_messages: int = Field(..., description="Number of transfer messages", ge=0)
    total_messages: int = Field(..., description="Total message count", ge=0)
    size_in_bytes: Optional[int] = Field(default=None, description="Queue size in bytes", ge=0)
    accessed_at: Optional[datetime] = Field(default=None, description="Last access time")
    updated_at: Optional[datetime] = Field(default=None, description="Last update time")

    @property
    def is_healthy(self) -> bool:
        """Check if queue is in healthy state."""
        return self.dead_letter_messages < 10 and self.active_messages < 1000

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }