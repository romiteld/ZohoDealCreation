"""
Application Insights integration for distributed telemetry.

Provides consistent telemetry across all Well services with automatic:
- Request tracking (latency, success/failure)
- Custom metrics (business and performance)
- Exception tracking with context
- Dependency tracking (DB, Redis, external APIs)

CRITICAL FIXES:
- Correct argument order for track_request and track_dependency
- Optional flush parameter to enable batching (default: False)
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager

try:
    from applicationinsights import TelemetryClient
    from applicationinsights.channel import TelemetryChannel, AsynchronousSender, AsynchronousQueue
    from applicationinsights.exceptions import enable
    HAS_APP_INSIGHTS = True
except ImportError:
    HAS_APP_INSIGHTS = False
    logging.warning("applicationinsights package not installed - telemetry disabled")


logger = logging.getLogger(__name__)

# Global telemetry client
_telemetry_client: Optional[Any] = None


def get_telemetry_client(service_name: str = "unknown") -> Optional[Any]:
    """
    Get or create Application Insights telemetry client.

    Args:
        service_name: Name of the service (teams-bot, vault-agent, main-api)

    Returns:
        TelemetryClient instance or None if not configured
    """
    global _telemetry_client

    if not HAS_APP_INSIGHTS:
        return None

    if _telemetry_client is not None:
        return _telemetry_client

    instrumentation_key = os.getenv("APPINSIGHTS_INSTRUMENTATION_KEY")
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if not instrumentation_key and not connection_string:
        logger.warning("Application Insights not configured - telemetry disabled")
        return None

    try:
        # Create custom channel for batching
        sender = AsynchronousSender()
        queue = AsynchronousQueue(sender)
        channel = TelemetryChannel(None, queue)

        if connection_string:
            _telemetry_client = TelemetryClient(
                connection_string=connection_string,
                telemetry_channel=channel
            )
        else:
            _telemetry_client = TelemetryClient(
                instrumentation_key=instrumentation_key,
                telemetry_channel=channel
            )

        # Set cloud role for service identification
        _telemetry_client.context.cloud.role = service_name

        # Enable automatic exception tracking
        enable(instrumentation_key or connection_string)

        logger.info(f"Application Insights telemetry enabled for {service_name}")
        return _telemetry_client

    except Exception as e:
        logger.error(f"Failed to initialize Application Insights: {e}")
        return None


def track_event(
    name: str,
    properties: Optional[Dict[str, str]] = None,
    measurements: Optional[Dict[str, float]] = None,
    service_name: str = "unknown",
    flush: bool = False
):
    """
    Track a custom event.

    Args:
        name: Event name (e.g., "digest_generated", "command_received")
        properties: String properties (user_id, audience, etc.)
        measurements: Numeric measurements (candidate_count, processing_time)
        service_name: Service identifier
        flush: Immediately flush to App Insights (default: False for batching)
    """
    client = get_telemetry_client(service_name)
    if not client:
        return

    try:
        client.track_event(name, properties, measurements)
        if flush:
            client.flush()
    except Exception as e:
        logger.error(f"Failed to track event {name}: {e}")


def track_metric(
    name: str,
    value: float,
    properties: Optional[Dict[str, str]] = None,
    service_name: str = "unknown",
    flush: bool = False
):
    """
    Track a custom metric.

    Args:
        name: Metric name (e.g., "bot_response_time", "digest_delivery_rate")
        value: Metric value
        properties: Dimensions for grouping (audience, command_type)
        service_name: Service identifier
        flush: Immediately flush to App Insights (default: False for batching)
    """
    client = get_telemetry_client(service_name)
    if not client:
        return

    try:
        client.track_metric(name, value, properties=properties)
        if flush:
            client.flush()
    except Exception as e:
        logger.error(f"Failed to track metric {name}: {e}")


def track_exception(
    exception: Exception,
    properties: Optional[Dict[str, str]] = None,
    measurements: Optional[Dict[str, float]] = None,
    service_name: str = "unknown",
    flush: bool = True
):
    """
    Track an exception with context.

    Args:
        exception: The exception to track
        properties: Additional context (user_id, operation)
        measurements: Related metrics (retry_count, time_elapsed)
        service_name: Service identifier
        flush: Immediately flush (default: True for exceptions)
    """
    client = get_telemetry_client(service_name)
    if not client:
        logger.exception(f"Exception in {service_name}: {exception}")
        return

    try:
        client.track_exception(
            type(exception),
            exception,
            None,
            properties,
            measurements
        )
        if flush:
            client.flush()
    except Exception as e:
        logger.error(f"Failed to track exception: {e}")


def track_dependency(
    name: str,
    data: str,
    dependency_type: str,
    duration: float,
    success: bool = True,
    properties: Optional[Dict[str, str]] = None,
    service_name: str = "unknown",
    flush: bool = False
):
    """
    Track a dependency call (database, API, cache).

    FIXED: Uses correct argument order - (name, data, type, success) then kwargs.

    Args:
        name: Dependency name (e.g., "PostgreSQL", "Redis", "Zoho API")
        data: Command/query executed
        dependency_type: Type ("SQL", "HTTP", "Cache")
        duration: Duration in milliseconds
        success: Whether the call succeeded
        properties: Additional context
        service_name: Service identifier
        flush: Immediately flush (default: False for batching)
    """
    client = get_telemetry_client(service_name)
    if not client:
        return

    try:
        # CORRECT order: name, data, dependency_type, success (positional), then kwargs
        client.track_dependency(
            name,
            data,
            dependency_type,
            success,
            duration=duration,
            properties=properties
        )
        if flush:
            client.flush()
    except Exception as e:
        logger.error(f"Failed to track dependency {name}: {e}")


def track_request(
    name: str,
    url: str,
    duration: float,
    response_code: int,
    success: bool,
    properties: Optional[Dict[str, str]] = None,
    service_name: str = "unknown",
    flush: bool = False
):
    """
    Track an HTTP request.

    FIXED: Uses correct argument order - (name, url, success) then kwargs.

    Args:
        name: Request name (e.g., "POST /api/messages")
        url: Request URL
        duration: Duration in milliseconds
        response_code: HTTP status code
        success: Whether the request succeeded
        properties: Additional context
        service_name: Service identifier
        flush: Immediately flush (default: False for batching)
    """
    client = get_telemetry_client(service_name)
    if not client:
        return

    try:
        # CORRECT order: name, url, success (positional), then kwargs
        client.track_request(
            name,
            url,
            success,
            duration=duration,
            response_code=response_code,
            properties=properties
        )
        if flush:
            client.flush()
    except Exception as e:
        logger.error(f"Failed to track request {name}: {e}")


@contextmanager
def track_operation(
    operation_name: str,
    service_name: str = "unknown",
    properties: Optional[Dict[str, str]] = None
):
    """
    Context manager to track an operation's duration and success.

    Usage:
        with track_operation("generate_digest", "vault-agent", {"audience": "advisors"}):
            result = await generate_digest(audience="advisors")

    Automatically tracks:
    - Duration
    - Success/failure
    - Exceptions
    """
    start_time = time.time()
    success = False
    error_type = None

    try:
        yield
        success = True
    except Exception as e:
        error_type = type(e).__name__
        track_exception(e, properties, service_name=service_name, flush=True)
        raise
    finally:
        duration = (time.time() - start_time) * 1000  # Convert to ms

        event_properties = properties or {}
        event_properties["success"] = str(success)
        if error_type:
            event_properties["error_type"] = error_type

        track_event(
            f"operation_{operation_name}",
            properties=event_properties,
            measurements={"duration_ms": duration},
            service_name=service_name,
            flush=False  # Let batching handle this
        )


def flush_telemetry():
    """
    Manually flush all pending telemetry.

    Use this:
    - On application shutdown
    - After critical events that must be recorded immediately
    - In test cleanup to ensure telemetry is sent
    """
    if _telemetry_client:
        _telemetry_client.flush()


# Pre-defined metric names for consistency
class Metrics:
    """Standard metric names across all services."""

    # Teams Bot metrics
    BOT_RESPONSE_TIME = "bot_response_time_ms"
    BOT_COMMAND_COUNT = "bot_command_count"
    BOT_QUERY_COUNT = "bot_natural_language_query_count"
    BOT_ERROR_RATE = "bot_error_rate"

    # Vault Agent metrics
    DIGEST_GENERATION_TIME = "digest_generation_time_ms"
    DIGEST_DELIVERY_SUCCESS_RATE = "digest_delivery_success_rate"
    DIGEST_CANDIDATE_COUNT = "digest_candidate_count"
    DIGEST_EMAIL_SEND_TIME = "digest_email_send_time_ms"

    # Main API metrics
    EMAIL_PROCESSING_TIME = "email_processing_time_ms"
    LANGGRAPH_NODE_TIME = "langgraph_node_time_ms"
    CACHE_HIT_RATE = "cache_hit_rate"
    COST_PER_REQUEST = "cost_per_request_usd"

    # Shared metrics
    DB_QUERY_TIME = "db_query_time_ms"
    REDIS_OPERATION_TIME = "redis_operation_time_ms"
    API_CALL_TIME = "external_api_call_time_ms"


# Pre-defined event names for consistency
class Events:
    """Standard event names across all services."""

    # Teams Bot events
    BOT_MESSAGE_RECEIVED = "bot_message_received"
    BOT_COMMAND_EXECUTED = "bot_command_executed"
    BOT_QUERY_PROCESSED = "bot_natural_language_query_processed"
    BOT_CARD_INTERACTION = "bot_adaptive_card_interaction"

    # Vault Agent events
    DIGEST_GENERATED = "digest_generated"
    DIGEST_DELIVERED = "digest_email_delivered"
    DIGEST_FAILED = "digest_delivery_failed"
    DIGEST_SCHEDULED = "digest_job_scheduled"

    # Main API events
    EMAIL_PROCESSED = "email_processed"
    LANGGRAPH_NODE_EXECUTED = "langgraph_node_executed"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
