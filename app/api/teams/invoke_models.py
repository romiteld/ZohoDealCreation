"""
Data models for Teams Bot invoke response handling.

This module provides structured models for invoke activities, ensuring proper
InvokeResponse format with correlation IDs and telemetry tracking.
"""
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from botbuilder.schema import InvokeResponse


class InvokeStatus(Enum):
    """Standard HTTP-like status codes for invoke responses."""
    SUCCESS = 200
    ACCEPTED = 202
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    RATE_LIMITED = 429
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503


@dataclass
class TelemetryData:
    """Telemetry information for invoke actions."""
    event_name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: Optional[float] = None


@dataclass
class ErrorDetails:
    """Structured error information for invoke failures."""
    error_code: str
    error_message: str
    user_message: str
    stack_trace: Optional[str] = None
    retry_after_seconds: Optional[int] = None


@dataclass
class InvokeActionResult:
    """
    Result of processing an invoke action.

    This dataclass provides a structured way to handle invoke responses,
    ensuring consistent correlation tracking and proper error handling.
    """
    status: InvokeStatus
    user_message: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    telemetry: Optional[TelemetryData] = None
    error_details: Optional[ErrorDetails] = None
    data: Dict[str, Any] = field(default_factory=dict)
    follow_up_activity: Optional[Any] = None  # MessageFactory activity

    def to_invoke_response(self) -> InvokeResponse:
        """
        Convert to Teams InvokeResponse format.

        Returns:
            InvokeResponse with proper status and body structure
        """
        body = {
            "correlationId": self.correlation_id,
            "timestamp": datetime.utcnow().isoformat()
        }

        if self.user_message:
            body["message"] = self.user_message

        if self.data:
            body["data"] = self.data

        if self.error_details:
            body["error"] = {
                "code": self.error_details.error_code,
                "message": self.error_details.error_message,
                "userMessage": self.error_details.user_message
            }
            if self.error_details.retry_after_seconds:
                body["error"]["retryAfter"] = self.error_details.retry_after_seconds

        return InvokeResponse(
            status=self.status.value,
            body=body
        )

    def is_success(self) -> bool:
        """Check if the action was successful."""
        return self.status in [InvokeStatus.SUCCESS, InvokeStatus.ACCEPTED]

    def is_error(self) -> bool:
        """Check if the action resulted in an error."""
        return self.status.value >= 400


class InvokeResponseBuilder:
    """
    Builder for creating structured invoke responses.

    This class provides a fluent interface for building invoke responses
    with proper error handling and correlation tracking.
    """

    def __init__(self, action: str):
        """
        Initialize builder for a specific action.

        Args:
            action: The invoke action being processed
        """
        self.action = action
        self.result = InvokeActionResult(status=InvokeStatus.SUCCESS)
        self.start_time = datetime.utcnow()

    def with_success(self, message: str = "Action completed successfully") -> 'InvokeResponseBuilder':
        """Set success status with optional message."""
        self.result.status = InvokeStatus.SUCCESS
        self.result.user_message = message
        return self

    def with_accepted(self, message: str = "Action accepted for processing") -> 'InvokeResponseBuilder':
        """Set accepted status for async operations."""
        self.result.status = InvokeStatus.ACCEPTED
        self.result.user_message = message
        return self

    def with_error(
        self,
        status: InvokeStatus,
        error_code: str,
        error_message: str,
        user_message: Optional[str] = None,
        stack_trace: Optional[str] = None
    ) -> 'InvokeResponseBuilder':
        """
        Set error status with details.

        Args:
            status: Error status code
            error_code: Internal error code
            error_message: Technical error message
            user_message: User-friendly error message
            stack_trace: Optional stack trace for debugging
        """
        self.result.status = status
        self.result.error_details = ErrorDetails(
            error_code=error_code,
            error_message=error_message,
            user_message=user_message or f"An error occurred processing your request. Reference: {self.result.correlation_id}",
            stack_trace=stack_trace
        )
        return self

    def with_rate_limit(self, retry_after_seconds: int = 60) -> 'InvokeResponseBuilder':
        """Set rate limit error with retry information."""
        self.result.status = InvokeStatus.RATE_LIMITED
        self.result.error_details = ErrorDetails(
            error_code="RATE_LIMITED",
            error_message="Too many requests",
            user_message="You've made too many requests. Please wait before trying again.",
            retry_after_seconds=retry_after_seconds
        )
        return self

    def with_data(self, data: Dict[str, Any]) -> 'InvokeResponseBuilder':
        """Add response data."""
        self.result.data = data
        return self

    def with_correlation_id(self, correlation_id: str) -> 'InvokeResponseBuilder':
        """Set specific correlation ID."""
        self.result.correlation_id = correlation_id
        return self

    def with_follow_up(self, activity: Any) -> 'InvokeResponseBuilder':
        """Add follow-up activity to send after invoke response."""
        self.result.follow_up_activity = activity
        return self

    def with_telemetry(
        self,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> 'InvokeResponseBuilder':
        """
        Add telemetry data.

        Args:
            event_name: Telemetry event name
            properties: Additional event properties
        """
        duration_ms = (datetime.utcnow() - self.start_time).total_seconds() * 1000
        self.result.telemetry = TelemetryData(
            event_name=event_name,
            properties={
                "action": self.action,
                "correlation_id": self.result.correlation_id,
                "status": self.result.status.value,
                **(properties or {})
            },
            duration_ms=duration_ms
        )
        return self

    def build(self) -> InvokeActionResult:
        """Build and return the invoke action result."""
        # Add default telemetry if not set
        if not self.result.telemetry:
            self.with_telemetry(f"invoke_action_{self.action}")
        return self.result


def create_success_response(
    action: str,
    message: str = "Success",
    data: Optional[Dict[str, Any]] = None
) -> InvokeActionResult:
    """
    Helper to create a success response.

    Args:
        action: The action that was processed
        message: Success message
        data: Optional response data

    Returns:
        InvokeActionResult with success status
    """
    builder = InvokeResponseBuilder(action).with_success(message)
    if data:
        builder.with_data(data)
    return builder.build()


def create_error_response(
    action: str,
    error: Exception,
    correlation_id: Optional[str] = None
) -> InvokeActionResult:
    """
    Helper to create an error response from an exception.

    Args:
        action: The action that failed
        error: The exception that occurred
        correlation_id: Optional correlation ID to use

    Returns:
        InvokeActionResult with error status
    """
    builder = InvokeResponseBuilder(action)
    if correlation_id:
        builder.with_correlation_id(correlation_id)

    # Determine appropriate status based on error type
    if isinstance(error, ValueError):
        status = InvokeStatus.BAD_REQUEST
        error_code = "INVALID_INPUT"
    elif isinstance(error, PermissionError):
        status = InvokeStatus.FORBIDDEN
        error_code = "ACCESS_DENIED"
    elif isinstance(error, FileNotFoundError):
        status = InvokeStatus.NOT_FOUND
        error_code = "RESOURCE_NOT_FOUND"
    else:
        status = InvokeStatus.INTERNAL_ERROR
        error_code = "INTERNAL_ERROR"

    import traceback
    stack_trace = traceback.format_exc()

    builder.with_error(
        status=status,
        error_code=error_code,
        error_message=str(error),
        user_message=f"An error occurred. Please try again. (Ref: {builder.result.correlation_id})",
        stack_trace=stack_trace
    )

    return builder.build()


def create_async_accepted_response(
    action: str,
    request_id: str,
    message: str = "Your request has been accepted and is being processed"
) -> InvokeActionResult:
    """
    Helper to create an accepted response for async operations.

    Args:
        action: The action being processed
        request_id: The async request ID
        message: User-friendly message

    Returns:
        InvokeActionResult with accepted status
    """
    return (
        InvokeResponseBuilder(action)
        .with_accepted(message)
        .with_data({"requestId": request_id})
        .build()
    )