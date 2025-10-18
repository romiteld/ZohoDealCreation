"""
Zoho CRM Webhook Receiver

Handles incoming webhooks from Zoho CRM with:
- Challenge verification during registration (GET)
- HMAC signature validation (POST)
- Redis deduplication
- Webhook log persistence
- Service Bus message enqueueing

Contract: Zoho → Webhook → Service Bus → Worker → PostgreSQL
"""

import os
import hmac
import hashlib
import json
import logging
import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Query, HTTPException, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage

from app.models.zoho_sync_models import (
    ZohoModule,
    WebhookEventType,
    ZohoWebhookLogEntry,
    ZohoSyncMessage,
    ProcessingStatus
)
from well_shared.cache.redis_manager import RedisCacheManager

logger = logging.getLogger(__name__)

# Router for webhook endpoints
router = APIRouter(prefix="/api/zoho/webhooks", tags=["zoho-webhooks"])

# Configuration
ZOHO_WEBHOOK_SECRET = os.getenv("ZOHO_WEBHOOK_SECRET")
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING") or os.getenv(
    "AZURE_SERVICE_BUS_CONNECTION_STRING"
)
SERVICE_BUS_QUEUE_NAME = os.getenv("SERVICE_BUS_ZOHO_SYNC_QUEUE", "zoho-sync-events")
REDIS_DEDUPE_TTL_SECONDS = int(os.getenv("REDIS_DEDUPE_TTL_SECONDS", "600"))  # 10 minutes

# Lazy initialization
_redis_manager: Optional[RedisCacheManager] = None
_service_bus_client: Optional[ServiceBusClient] = None


def get_redis_manager() -> RedisCacheManager:
    """Get or create Redis manager singleton"""
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisCacheManager()
    return _redis_manager


async def get_service_bus_client() -> ServiceBusClient:
    """Get or create Service Bus client singleton"""
    global _service_bus_client
    if _service_bus_client is None:
        _service_bus_client = ServiceBusClient.from_connection_string(
            SERVICE_BUS_CONNECTION_STRING,
            logging_enable=True
        )
    return _service_bus_client


def compute_payload_sha256(payload: dict) -> str:
    """
    Compute SHA-256 hash of payload for deduplication.

    Args:
        payload: Webhook payload dict

    Returns:
        64-character hex string
    """
    # Sort keys for consistent hashing
    payload_json = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(payload_json.encode()).hexdigest()


def verify_hmac_signature(signature: str, body: bytes) -> bool:
    """
    Verify Zoho webhook HMAC signature.

    Args:
        signature: X-Zoho-Signature header value
        body: Raw request body bytes

    Returns:
        True if signature is valid, False otherwise
    """
    if not ZOHO_WEBHOOK_SECRET:
        logger.error("ZOHO_WEBHOOK_SECRET not configured")
        return False

    if not signature:
        logger.warning("Missing X-Zoho-Signature header")
        return False

    # Compute expected signature
    expected = hmac.new(
        ZOHO_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected, signature)


def normalize_zoho_event_type(operation: Optional[str]) -> str:
    """
    Normalize Zoho operation string to WebhookEventType value.

    Zoho sends operation in formats like:
    - "Leads.edit"
    - "Leads.create"
    - "Leads.delete"
    - "edit" (sometimes without module prefix)
    - Uppercase variants

    Args:
        operation: Raw operation string from Zoho webhook

    Returns:
        Normalized event type: "create", "update", or "delete"
    """
    if not operation:
        return "update"  # Default fallback

    # Lowercase and strip module prefix if present
    normalized = operation.lower()
    if "." in normalized:
        # "Leads.edit" -> "edit"
        normalized = normalized.split(".", 1)[1]

    # Map Zoho operations to our enum values
    operation_map = {
        "create": "create",
        "insert": "create",
        "edit": "update",
        "update": "update",
        "delete": "delete",
        "remove": "delete"
    }

    return operation_map.get(normalized, "update")  # Default to update if unknown


# =============================================================================
# WEBHOOK VERIFICATION CHALLENGE (GET)
# =============================================================================

@router.get("/{module}")
async def verify_webhook_challenge(
    module: ZohoModule,
    request: Request,
    challenge: str = Query(..., description="Challenge string from Zoho")
) -> PlainTextResponse:
    """
    Handle Zoho webhook verification challenge during registration.

    Zoho sends: GET /api/zoho/webhooks/{module}?challenge=abc123
                Header: X-Zoho-Signature: <hmac>

    We must return the challenge value as plain text with 200 OK.

    Args:
        module: Zoho CRM module name
        request: FastAPI request object
        challenge: Challenge string from query parameter

    Returns:
        PlainTextResponse with challenge value

    Raises:
        HTTPException: 401 if signature validation fails
    """
    logger.info(f"Received webhook verification challenge for module: {module.value}")

    # Get signature from header (case-insensitive)
    signature = request.headers.get("X-Zoho-Signature") or request.headers.get("x-zoho-signature")

    if not signature:
        logger.error("Missing X-Zoho-Signature header in challenge request")
        raise HTTPException(status_code=401, detail="Missing signature header")

    # Verify HMAC of challenge value
    is_valid = verify_hmac_signature(signature, challenge.encode())

    if not is_valid:
        logger.error(f"Invalid signature for webhook challenge: {module.value}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    logger.info(f"✅ Webhook challenge verified successfully for {module.value}")

    # Return challenge as plain text (Zoho requirement)
    return PlainTextResponse(content=challenge, status_code=200)


# =============================================================================
# WEBHOOK PAYLOAD RECEIVER (POST)
# =============================================================================

@router.post("/{module}")
async def receive_webhook(module: ZohoModule, request: Request) -> JSONResponse:
    """
    Receive and process Zoho CRM webhook payload.

    Processing flow:
    1. Validate HMAC signature
    2. Compute payload SHA-256 for deduplication
    3. Check Redis dedupe cache
    4. Persist to zoho_webhook_log
    5. Enqueue to Service Bus
    6. Return 200 OK (acknowledge within 10s for Zoho)

    Args:
        module: Zoho CRM module name
        request: FastAPI request object

    Returns:
        JSONResponse with acknowledgment

    Raises:
        HTTPException: 401 if signature invalid, 500 if processing fails
    """
    logger.info(f"Received webhook for module: {module.value}")

    # 1. Read raw body for HMAC verification
    body = await request.body()

    # Get signature from header
    signature = request.headers.get("X-Zoho-Signature") or request.headers.get("x-zoho-signature")

    # Verify HMAC
    is_valid = verify_hmac_signature(signature, body)
    if not is_valid:
        logger.error(f"Invalid webhook signature for {module.value}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Parse JSON payload
    try:
        raw_payload = await request.json()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 3. Unwrap Zoho's data structure and extract wrapper metadata
    # Zoho wraps actual record in "data" array: {"data": [{"id": "...", ...}], "operation": "Leads.edit"}
    wrapper_metadata = None
    if "data" in raw_payload and isinstance(raw_payload.get("data"), list) and len(raw_payload["data"]) > 0:
        payload = raw_payload["data"][0]  # Unwrap first record
        operation = raw_payload.get("operation")  # Extract operation from wrapper

        # Preserve full wrapper context for audit trail (excluding data array)
        wrapper_metadata = {k: v for k, v in raw_payload.items() if k != "data"}
    else:
        # Fallback: assume payload is already unwrapped (for backward compatibility)
        payload = raw_payload
        operation = raw_payload.get("operation") or raw_payload.get("event_type")
        logger.warning(f"Webhook payload missing 'data' array, using raw payload: {raw_payload.keys()}")

    # Normalize event type from Zoho's operation format
    event_type = normalize_zoho_event_type(operation)

    # Extract metadata from unwrapped payload
    zoho_id = str(payload.get("id", ""))
    modified_time_str = payload.get("Modified_Time", datetime.utcnow().isoformat())

    if not zoho_id:
        logger.error(f"Missing 'id' field in webhook payload: {payload}")
        raise HTTPException(status_code=400, detail="Missing record ID in payload")

    # Parse modified_time
    try:
        modified_time = datetime.fromisoformat(modified_time_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        logger.warning(f"Invalid Modified_Time format: {modified_time_str}, using current time")
        modified_time = datetime.utcnow()

    # 3. Compute payload hash for deduplication
    payload_sha = compute_payload_sha256(payload)

    # 4. Check Redis dedupe cache
    # Include event_type to prevent delete payloads from colliding with updates
    dedupe_key = f"dedupe:{module.value}:{event_type}:{zoho_id}:{payload_sha}"
    redis_manager = get_redis_manager()

    try:
        # Check if we've already seen this exact payload
        if await redis_manager.client.exists(dedupe_key):
            logger.info(f"✓ Dedupe cache hit for {module.value}:{zoho_id} - skipping duplicate webhook")
            return JSONResponse(
                status_code=200,
                content={"status": "acknowledged", "message": "Duplicate webhook (deduplicated)"}
            )

        # Set dedupe cache key (10-minute TTL)
        await redis_manager.client.setex(dedupe_key, REDIS_DEDUPE_TTL_SECONDS, "processing")
        logger.debug(f"Set dedupe cache key: {dedupe_key} (TTL: {REDIS_DEDUPE_TTL_SECONDS}s)")

    except Exception as e:
        logger.error(f"Redis dedupe check failed: {e}, continuing without deduplication")

    # 5. Persist to zoho_webhook_log
    log_id = str(uuid.uuid4())
    webhook_log = ZohoWebhookLogEntry(
        id=log_id,
        module=module,
        event_type=WebhookEventType(event_type),
        zoho_id=zoho_id,
        payload_raw=payload,
        payload_sha256=payload_sha,
        received_at=datetime.utcnow(),
        processing_status=ProcessingStatus.PENDING,
        retry_count=0,
        wrapper_operation=operation,  # Preserve raw operation string
        wrapper_metadata=wrapper_metadata  # Preserve full wrapper context
    )

    try:
        # Import here to avoid circular dependency
        import asyncpg

        db_url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(db_url)

        await conn.execute("""
            INSERT INTO zoho_webhook_log
                (id, module, event_type, zoho_id, payload_raw, payload_sha256,
                 received_at, processing_status, retry_count, wrapper_operation, wrapper_metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (module, zoho_id, payload_sha256) DO NOTHING
        """,
            log_id, module.value, event_type, zoho_id, json.dumps(payload),
            payload_sha, webhook_log.received_at, "pending", 0,
            operation, json.dumps(wrapper_metadata) if wrapper_metadata else None
        )

        await conn.close()
        logger.info(f"✓ Persisted webhook to log: {log_id}")

    except Exception as e:
        logger.error(f"Failed to persist webhook log: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to persist webhook")

    # 6. Enqueue to Service Bus
    sync_message = ZohoSyncMessage(
        log_id=log_id,
        module=module,
        event_type=WebhookEventType(event_type),
        zoho_id=zoho_id,
        modified_time=modified_time,
        payload_sha=payload_sha,
        retry_count=0,
        enqueued_at=datetime.utcnow()
    )

    try:
        service_bus_client = await get_service_bus_client()
        sender = service_bus_client.get_queue_sender(queue_name=SERVICE_BUS_QUEUE_NAME)

        async with sender:
            message = ServiceBusMessage(
                body=sync_message.model_dump_json(),
                content_type="application/json"
            )
            await sender.send_messages(message)

        logger.info(f"✓ Enqueued message to Service Bus: {log_id} ({module.value}:{zoho_id})")

    except Exception as e:
        logger.error(f"Failed to enqueue to Service Bus: {e}", exc_info=True)
        # Don't fail the webhook - we can retry from webhook log later
        logger.warning(f"Webhook logged but not enqueued (will retry): {log_id}")

    # 7. Return success (acknowledge receipt)
    return JSONResponse(
        status_code=200,
        content={
            "status": "acknowledged",
            "log_id": log_id,
            "module": module.value,
            "zoho_id": zoho_id,
            "message": "Webhook received and queued for processing"
        }
    )


# =============================================================================
# HEALTH CHECK
# =============================================================================

@router.get("/health")
async def webhook_health_check() -> JSONResponse:
    """Health check endpoint for webhook receiver"""

    health_status = {
        "status": "healthy",
        "webhook_secret_configured": bool(ZOHO_WEBHOOK_SECRET),
        "service_bus_configured": bool(SERVICE_BUS_CONNECTION_STRING),
        "redis_connected": False
    }

    # Test Redis connection
    try:
        redis_manager = get_redis_manager()
        await redis_manager.client.ping()
        health_status["redis_connected"] = True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] == "healthy" else 503

    return JSONResponse(status_code=status_code, content=health_status)
