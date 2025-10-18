"""
Unit tests for invoke response models and handlers.

Tests the InvokeActionResult dataclass, InvokeResponseBuilder,
and proper InvokeResponse generation for Teams Bot.
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock
import traceback

from botbuilder.schema import InvokeResponse

from app.api.teams.invoke_models import (
    InvokeStatus,
    TelemetryData,
    ErrorDetails,
    InvokeActionResult,
    InvokeResponseBuilder,
    create_success_response,
    create_error_response,
    create_async_accepted_response
)


class TestInvokeStatus:
    """Test suite for InvokeStatus enum."""

    def test_status_values(self):
        """Test that status codes have correct values."""
        assert InvokeStatus.SUCCESS.value == 200
        assert InvokeStatus.ACCEPTED.value == 202
        assert InvokeStatus.BAD_REQUEST.value == 400
        assert InvokeStatus.UNAUTHORIZED.value == 401
        assert InvokeStatus.FORBIDDEN.value == 403
        assert InvokeStatus.NOT_FOUND.value == 404
        assert InvokeStatus.RATE_LIMITED.value == 429
        assert InvokeStatus.INTERNAL_ERROR.value == 500
        assert InvokeStatus.SERVICE_UNAVAILABLE.value == 503


class TestTelemetryData:
    """Test suite for TelemetryData dataclass."""

    def test_telemetry_creation(self):
        """Test creating telemetry data."""
        telemetry = TelemetryData(
            event_name="test_event",
            properties={"key": "value"},
            duration_ms=150.5
        )

        assert telemetry.event_name == "test_event"
        assert telemetry.properties == {"key": "value"}
        assert telemetry.duration_ms == 150.5
        assert isinstance(telemetry.timestamp, datetime)

    def test_telemetry_defaults(self):
        """Test telemetry default values."""
        telemetry = TelemetryData(event_name="test")

        assert telemetry.properties == {}
        assert telemetry.duration_ms is None
        assert telemetry.timestamp is not None


class TestErrorDetails:
    """Test suite for ErrorDetails dataclass."""

    def test_error_details_creation(self):
        """Test creating error details."""
        error = ErrorDetails(
            error_code="TEST_ERROR",
            error_message="Something went wrong",
            user_message="An error occurred",
            stack_trace="Stack trace here",
            retry_after_seconds=60
        )

        assert error.error_code == "TEST_ERROR"
        assert error.error_message == "Something went wrong"
        assert error.user_message == "An error occurred"
        assert error.stack_trace == "Stack trace here"
        assert error.retry_after_seconds == 60

    def test_error_details_minimal(self):
        """Test error details with minimal fields."""
        error = ErrorDetails(
            error_code="ERROR",
            error_message="Error",
            user_message="User error"
        )

        assert error.stack_trace is None
        assert error.retry_after_seconds is None


class TestInvokeActionResult:
    """Test suite for InvokeActionResult dataclass."""

    def test_result_creation_with_defaults(self):
        """Test creating result with default values."""
        result = InvokeActionResult(status=InvokeStatus.SUCCESS)

        assert result.status == InvokeStatus.SUCCESS
        assert result.user_message is None
        assert result.correlation_id is not None
        assert len(result.correlation_id) == 36  # UUID format
        assert result.telemetry is None
        assert result.error_details is None
        assert result.data == {}
        assert result.follow_up_activity is None

    def test_result_creation_with_all_fields(self):
        """Test creating result with all fields."""
        telemetry = TelemetryData(event_name="test")
        error = ErrorDetails("CODE", "message", "user message")

        result = InvokeActionResult(
            status=InvokeStatus.BAD_REQUEST,
            user_message="Bad request",
            correlation_id="test-123",
            telemetry=telemetry,
            error_details=error,
            data={"key": "value"},
            follow_up_activity="activity"
        )

        assert result.status == InvokeStatus.BAD_REQUEST
        assert result.user_message == "Bad request"
        assert result.correlation_id == "test-123"
        assert result.telemetry == telemetry
        assert result.error_details == error
        assert result.data == {"key": "value"}
        assert result.follow_up_activity == "activity"

    def test_to_invoke_response_success(self):
        """Test converting success result to InvokeResponse."""
        result = InvokeActionResult(
            status=InvokeStatus.SUCCESS,
            user_message="Operation completed",
            correlation_id="test-123",
            data={"result": "data"}
        )

        response = result.to_invoke_response()

        assert isinstance(response, InvokeResponse)
        assert response.status == 200
        assert response.body["correlationId"] == "test-123"
        assert response.body["message"] == "Operation completed"
        assert response.body["data"] == {"result": "data"}
        assert "error" not in response.body

    def test_to_invoke_response_error(self):
        """Test converting error result to InvokeResponse."""
        error_details = ErrorDetails(
            error_code="TEST_ERROR",
            error_message="Technical error",
            user_message="User friendly error",
            retry_after_seconds=30
        )

        result = InvokeActionResult(
            status=InvokeStatus.INTERNAL_ERROR,
            correlation_id="error-123",
            error_details=error_details
        )

        response = result.to_invoke_response()

        assert isinstance(response, InvokeResponse)
        assert response.status == 500
        assert response.body["correlationId"] == "error-123"
        assert response.body["error"]["code"] == "TEST_ERROR"
        assert response.body["error"]["message"] == "Technical error"
        assert response.body["error"]["userMessage"] == "User friendly error"
        assert response.body["error"]["retryAfter"] == 30

    def test_is_success(self):
        """Test is_success method."""
        success_result = InvokeActionResult(status=InvokeStatus.SUCCESS)
        assert success_result.is_success() is True

        accepted_result = InvokeActionResult(status=InvokeStatus.ACCEPTED)
        assert accepted_result.is_success() is True

        error_result = InvokeActionResult(status=InvokeStatus.BAD_REQUEST)
        assert error_result.is_success() is False

    def test_is_error(self):
        """Test is_error method."""
        success_result = InvokeActionResult(status=InvokeStatus.SUCCESS)
        assert success_result.is_error() is False

        error_result = InvokeActionResult(status=InvokeStatus.BAD_REQUEST)
        assert error_result.is_error() is True

        server_error = InvokeActionResult(status=InvokeStatus.INTERNAL_ERROR)
        assert server_error.is_error() is True


class TestInvokeResponseBuilder:
    """Test suite for InvokeResponseBuilder."""

    def test_builder_with_success(self):
        """Test building a success response."""
        builder = InvokeResponseBuilder("test_action")
        result = builder.with_success("Success!").build()

        assert result.status == InvokeStatus.SUCCESS
        assert result.user_message == "Success!"
        assert result.telemetry.event_name == "invoke_action_test_action"

    def test_builder_with_accepted(self):
        """Test building an accepted response."""
        builder = InvokeResponseBuilder("async_action")
        result = builder.with_accepted("Processing...").build()

        assert result.status == InvokeStatus.ACCEPTED
        assert result.user_message == "Processing..."

    def test_builder_with_error(self):
        """Test building an error response."""
        builder = InvokeResponseBuilder("error_action")
        result = builder.with_error(
            status=InvokeStatus.BAD_REQUEST,
            error_code="INVALID_INPUT",
            error_message="Invalid input provided",
            user_message="Please check your input",
            stack_trace="Stack trace"
        ).build()

        assert result.status == InvokeStatus.BAD_REQUEST
        assert result.error_details.error_code == "INVALID_INPUT"
        assert result.error_details.error_message == "Invalid input provided"
        assert result.error_details.user_message == "Please check your input"
        assert result.error_details.stack_trace == "Stack trace"

    def test_builder_with_rate_limit(self):
        """Test building a rate limit response."""
        builder = InvokeResponseBuilder("rate_limited_action")
        result = builder.with_rate_limit(retry_after_seconds=120).build()

        assert result.status == InvokeStatus.RATE_LIMITED
        assert result.error_details.error_code == "RATE_LIMITED"
        assert result.error_details.retry_after_seconds == 120

    def test_builder_with_data(self):
        """Test adding data to response."""
        builder = InvokeResponseBuilder("data_action")
        result = builder.with_success().with_data({"key": "value"}).build()

        assert result.data == {"key": "value"}

    def test_builder_with_correlation_id(self):
        """Test setting specific correlation ID."""
        builder = InvokeResponseBuilder("correlated_action")
        result = builder.with_correlation_id("custom-id-123").build()

        assert result.correlation_id == "custom-id-123"

    def test_builder_with_follow_up(self):
        """Test adding follow-up activity."""
        activity = MagicMock()
        builder = InvokeResponseBuilder("follow_up_action")
        result = builder.with_follow_up(activity).build()

        assert result.follow_up_activity == activity

    def test_builder_with_telemetry(self):
        """Test adding telemetry."""
        builder = InvokeResponseBuilder("telemetry_action")
        result = builder.with_telemetry(
            event_name="custom_event",
            properties={"custom": "property"}
        ).build()

        assert result.telemetry.event_name == "custom_event"
        assert result.telemetry.properties["custom"] == "property"
        assert result.telemetry.properties["action"] == "telemetry_action"
        assert result.telemetry.properties["status"] == 200
        assert result.telemetry.duration_ms is not None

    def test_builder_chain(self):
        """Test method chaining."""
        result = (
            InvokeResponseBuilder("chained_action")
            .with_success("Success")
            .with_data({"result": "data"})
            .with_correlation_id("chain-123")
            .with_telemetry("chained_event", {"prop": "value"})
            .build()
        )

        assert result.status == InvokeStatus.SUCCESS
        assert result.user_message == "Success"
        assert result.data == {"result": "data"}
        assert result.correlation_id == "chain-123"
        assert result.telemetry.event_name == "chained_event"


class TestHelperFunctions:
    """Test suite for helper functions."""

    def test_create_success_response(self):
        """Test create_success_response helper."""
        response = create_success_response(
            action="test",
            message="Test success",
            data={"key": "value"}
        )

        assert response.status == InvokeStatus.SUCCESS
        assert response.user_message == "Test success"
        assert response.data == {"key": "value"}
        assert response.telemetry is not None

    def test_create_success_response_minimal(self):
        """Test create_success_response with minimal args."""
        response = create_success_response(action="test")

        assert response.status == InvokeStatus.SUCCESS
        assert response.user_message == "Success"
        assert response.data == {}

    def test_create_error_response_value_error(self):
        """Test create_error_response with ValueError."""
        error = ValueError("Invalid value")
        response = create_error_response("test_action", error)

        assert response.status == InvokeStatus.BAD_REQUEST
        assert response.error_details.error_code == "INVALID_INPUT"
        assert response.error_details.error_message == "Invalid value"
        assert response.correlation_id is not None

    def test_create_error_response_permission_error(self):
        """Test create_error_response with PermissionError."""
        error = PermissionError("Access denied")
        response = create_error_response("test_action", error)

        assert response.status == InvokeStatus.FORBIDDEN
        assert response.error_details.error_code == "ACCESS_DENIED"

    def test_create_error_response_not_found(self):
        """Test create_error_response with FileNotFoundError."""
        error = FileNotFoundError("File not found")
        response = create_error_response("test_action", error)

        assert response.status == InvokeStatus.NOT_FOUND
        assert response.error_details.error_code == "RESOURCE_NOT_FOUND"

    def test_create_error_response_generic(self):
        """Test create_error_response with generic exception."""
        error = Exception("Something went wrong")
        response = create_error_response("test_action", error)

        assert response.status == InvokeStatus.INTERNAL_ERROR
        assert response.error_details.error_code == "INTERNAL_ERROR"
        assert response.error_details.stack_trace is not None

    def test_create_error_response_with_correlation_id(self):
        """Test create_error_response with custom correlation ID."""
        error = Exception("Error")
        response = create_error_response("test", error, "custom-123")

        assert response.correlation_id == "custom-123"

    def test_create_async_accepted_response(self):
        """Test create_async_accepted_response helper."""
        response = create_async_accepted_response(
            action="async_test",
            request_id="req-123",
            message="Processing your request"
        )

        assert response.status == InvokeStatus.ACCEPTED
        assert response.user_message == "Processing your request"
        assert response.data == {"requestId": "req-123"}

    def test_create_async_accepted_response_default_message(self):
        """Test async response with default message."""
        response = create_async_accepted_response(
            action="async_test",
            request_id="req-123"
        )

        assert response.user_message == "Your request has been accepted and is being processed"


class TestInvokeResponseIntegration:
    """Integration tests for invoke response flow."""

    def test_full_success_flow(self):
        """Test complete success flow from builder to InvokeResponse."""
        # Build result
        result = (
            InvokeResponseBuilder("complete_action")
            .with_success("Operation completed successfully")
            .with_data({"result": "success", "count": 10})
            .with_correlation_id("flow-123")
            .build()
        )

        # Convert to InvokeResponse
        invoke_response = result.to_invoke_response()

        # Verify complete response structure
        assert invoke_response.status == 200
        assert invoke_response.body["correlationId"] == "flow-123"
        assert invoke_response.body["message"] == "Operation completed successfully"
        assert invoke_response.body["data"]["result"] == "success"
        assert invoke_response.body["data"]["count"] == 10
        assert "timestamp" in invoke_response.body

    def test_full_error_flow(self):
        """Test complete error flow from exception to InvokeResponse."""
        try:
            # Simulate an error
            raise ValueError("Invalid input: missing required field")
        except ValueError as e:
            # Create error response
            result = create_error_response("error_action", e, "error-flow-123")

            # Convert to InvokeResponse
            invoke_response = result.to_invoke_response()

            # Verify error response structure
            assert invoke_response.status == 400
            assert invoke_response.body["correlationId"] == "error-flow-123"
            assert invoke_response.body["error"]["code"] == "INVALID_INPUT"
            assert "Invalid input" in invoke_response.body["error"]["message"]
            assert "error-flow-123" in invoke_response.body["error"]["userMessage"]

    def test_rate_limit_flow(self):
        """Test rate limit response flow."""
        result = (
            InvokeResponseBuilder("rate_limited")
            .with_rate_limit(retry_after_seconds=60)
            .build()
        )

        invoke_response = result.to_invoke_response()

        assert invoke_response.status == 429
        assert invoke_response.body["error"]["code"] == "RATE_LIMITED"
        assert invoke_response.body["error"]["retryAfter"] == 60