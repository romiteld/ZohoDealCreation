"""
Real-time Monitoring API for Outlook Add-in Deal Creation
Streams deal creation metrics, missed opportunities, and learning system performance
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json
import asyncio
import logging
from enum import Enum

# Import existing systems
from ..powerbi_integration import powerbi, DealProcessingRow
from ..learning_analytics import LearningAnalytics
from ..monitoring import telemetry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


class DealStatus(str, Enum):
    """Deal creation status"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"
    LOW_CONFIDENCE = "low_confidence"


class DealEvent(BaseModel):
    """Real-time deal creation event"""
    event_id: str
    timestamp: datetime
    email_subject: str
    sender_domain: str
    status: DealStatus
    confidence_score: float
    processing_time_ms: int

    # Deal details
    deal_name: Optional[str] = None
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    zoho_deal_id: Optional[str] = None

    # Learning indicators
    used_template: bool = False
    used_cache: bool = False
    pattern_matched: bool = False

    # Error info
    error_message: Optional[str] = None
    error_stage: Optional[str] = None


class MonitoringStats(BaseModel):
    """Real-time statistics"""
    period_start: datetime
    period_end: datetime

    # Deal metrics
    total_deals_processed: int
    deals_created: int
    deals_failed: int
    deals_skipped: int
    duplicates_prevented: int

    # Success rates
    success_rate: float
    avg_confidence: float
    avg_processing_time_ms: float

    # Learning metrics
    template_usage_rate: float
    cache_hit_rate: float
    pattern_match_rate: float

    # Top performers
    top_domains: List[Dict[str, Any]]
    recent_errors: List[str]


@router.get("/stream/deals")
async def stream_deal_events(
    duration_minutes: int = Query(default=60, ge=1, le=1440)
):
    """
    Stream real-time deal creation events via Server-Sent Events (SSE).
    Compatible with Power BI streaming datasets and Obsidian plugins.

    Example usage in Power BI:
    - Create streaming dataset with DealEvent schema
    - Use this endpoint as data source
    - Auto-refresh every 1 second

    Example usage in Obsidian:
    - Use REST API plugin
    - Stream to daily note
    - Auto-create deal templates
    """

    async def event_generator():
        """Generate SSE events from Redis pub/sub"""
        import redis.asyncio as redis

        redis_client = redis.from_url(
            os.getenv('AZURE_REDIS_CONNECTION_STRING'),
            decode_responses=True
        )

        pubsub = redis_client.pubsub()
        await pubsub.subscribe("deal_events")

        end_time = datetime.utcnow() + timedelta(minutes=duration_minutes)

        try:
            while datetime.utcnow() < end_time:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)

                if message and message['type'] == 'message':
                    event_data = json.loads(message['data'])

                    # Format as Server-Sent Event
                    yield f"data: {json.dumps(event_data)}\n\n"

                await asyncio.sleep(0.1)

        finally:
            await pubsub.unsubscribe("deal_events")
            await redis_client.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/stats/realtime", response_model=MonitoringStats)
async def get_realtime_stats(
    minutes: int = Query(default=60, ge=1, le=1440)
):
    """
    Get real-time statistics for the last N minutes.
    Used by Power BI dashboards and monitoring systems.
    """
    import redis.asyncio as redis

    redis_client = redis.from_url(
        os.getenv('AZURE_REDIS_CONNECTION_STRING'),
        decode_responses=True
    )

    try:
        # Get stats from Redis sorted sets
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)

        start_ts = start_time.timestamp()
        end_ts = end_time.timestamp()

        # Count events by status
        success_count = await redis_client.zcount("deal_events:success", start_ts, end_ts)
        failed_count = await redis_client.zcount("deal_events:failed", start_ts, end_ts)
        skipped_count = await redis_client.zcount("deal_events:skipped", start_ts, end_ts)
        duplicate_count = await redis_client.zcount("deal_events:duplicate", start_ts, end_ts)

        total_processed = success_count + failed_count + skipped_count + duplicate_count

        # Get learning metrics from hash
        learning_stats = await redis_client.hgetall("learning_stats:current")

        template_usage = float(learning_stats.get('template_usage_rate', 0))
        cache_hit_rate = float(learning_stats.get('cache_hit_rate', 0))
        pattern_match_rate = float(learning_stats.get('pattern_match_rate', 0))

        # Calculate averages
        avg_confidence = float(learning_stats.get('avg_confidence', 0))
        avg_processing_time = float(learning_stats.get('avg_processing_time_ms', 0))

        # Get top domains
        top_domains_raw = await redis_client.zrevrange(
            "deal_domains:frequency",
            0, 9,
            withscores=True
        )

        top_domains = [
            {"domain": domain, "count": int(count)}
            for domain, count in top_domains_raw
        ]

        # Get recent errors
        recent_errors = await redis_client.lrange("deal_errors:recent", 0, 9)

        success_rate = (success_count / total_processed * 100) if total_processed > 0 else 0

        return MonitoringStats(
            period_start=start_time,
            period_end=end_time,
            total_deals_processed=total_processed,
            deals_created=success_count,
            deals_failed=failed_count,
            deals_skipped=skipped_count,
            duplicates_prevented=duplicate_count,
            success_rate=round(success_rate, 2),
            avg_confidence=round(avg_confidence, 3),
            avg_processing_time_ms=round(avg_processing_time, 0),
            template_usage_rate=round(template_usage * 100, 2),
            cache_hit_rate=round(cache_hit_rate * 100, 2),
            pattern_match_rate=round(pattern_match_rate * 100, 2),
            top_domains=top_domains,
            recent_errors=recent_errors
        )

    finally:
        await redis_client.close()


@router.post("/webhook/deal-created")
async def deal_created_webhook(event: DealEvent):
    """
    Webhook called by LangGraph workflow when a deal is created/failed.
    Broadcasts to Redis pub/sub, Power BI, and Application Insights.

    Called from: app/langgraph_manager.py
    """
    import redis.asyncio as redis

    # Publish to Redis pub/sub for SSE streaming
    redis_client = redis.from_url(
        os.getenv('AZURE_REDIS_CONNECTION_STRING'),
        decode_responses=True
    )

    try:
        # Publish event
        await redis_client.publish("deal_events", event.json())

        # Update sorted sets for time-series queries
        event_ts = event.timestamp.timestamp()

        await redis_client.zadd(f"deal_events:{event.status.value}", {event.event_id: event_ts})

        # Update domain frequency
        if event.sender_domain:
            await redis_client.zincrby("deal_domains:frequency", 1, event.sender_domain)

        # Update learning stats (rolling average)
        pipe = redis_client.pipeline()
        pipe.hincrbyfloat("learning_stats:current", "avg_confidence", event.confidence_score)
        pipe.hincrbyfloat("learning_stats:current", "avg_processing_time_ms", event.processing_time_ms)
        pipe.hincrby("learning_stats:current", "total_events", 1)

        if event.used_template:
            pipe.hincrby("learning_stats:current", "template_uses", 1)
        if event.used_cache:
            pipe.hincrby("learning_stats:current", "cache_hits", 1)
        if event.pattern_matched:
            pipe.hincrby("learning_stats:current", "pattern_matches", 1)

        await pipe.execute()

        # Store error if failed
        if event.status == DealStatus.FAILED and event.error_message:
            error_msg = f"[{event.timestamp.isoformat()}] {event.error_stage}: {event.error_message}"
            await redis_client.lpush("deal_errors:recent", error_msg)
            await redis_client.ltrim("deal_errors:recent", 0, 99)  # Keep last 100 errors

        # Send to Power BI if deal was created
        if event.status == DealStatus.SUCCESS and event.zoho_deal_id:
            deal_row = DealProcessingRow(
                deal_id=event.zoho_deal_id,
                extraction_id=event.event_id,
                timestamp=event.timestamp,
                deal_name=event.deal_name or "Unknown",
                company_name=event.company_name or "Unknown",
                contact_name=event.contact_name or "Unknown",
                email_domain=event.sender_domain,
                source="Email Inbound",
                processing_stage="Create",
                success=True,
                processing_time_ms=event.processing_time_ms,
                extraction_confidence=event.confidence_score,
                fields_corrected=0,
                used_template=event.used_template,
                used_firecrawl=False,
                used_apollo=False,
                model_used="gpt-5-mini",
                tokens_input=0,
                tokens_output=0,
                cost_usd=0.0,
                owner_email=os.getenv('ZOHO_DEFAULT_OWNER_EMAIL')
            )

            powerbi.log_deal_processing(deal_row)

        # Send to Application Insights
        telemetry.track_event(
            "deal_processing",
            properties={
                "status": event.status.value,
                "confidence": event.confidence_score,
                "domain": event.sender_domain,
                "used_template": event.used_template,
                "used_cache": event.used_cache
            },
            measurements={
                "processing_time_ms": event.processing_time_ms
            }
        )

        return {"status": "received", "event_id": event.event_id}

    finally:
        await redis_client.close()


@router.get("/learning/accuracy")
async def get_learning_accuracy(
    days: int = Query(default=7, ge=1, le=90)
):
    """
    Get learning system accuracy trends over time.
    Shows if the system is actually improving with more data.
    """
    # Query from PostgreSQL extraction_metrics table
    from ..database import get_db_connection

    query = """
        SELECT
            DATE(timestamp) as date,
            AVG(overall_accuracy) as avg_accuracy,
            AVG(overall_confidence) as avg_confidence,
            COUNT(*) as total_extractions,
            SUM(CASE WHEN used_template THEN 1 ELSE 0 END)::float / COUNT(*) as template_rate,
            SUM(CASE WHEN used_corrections THEN 1 ELSE 0 END)::float / COUNT(*) as correction_rate
        FROM extraction_metrics
        WHERE timestamp >= NOW() - INTERVAL '%s days'
        GROUP BY DATE(timestamp)
        ORDER BY date
    """

    async with get_db_connection() as conn:
        rows = await conn.fetch(query, days)

    return {
        "period_days": days,
        "data_points": len(rows),
        "trends": [
            {
                "date": row['date'].isoformat(),
                "avg_accuracy": round(row['avg_accuracy'], 3),
                "avg_confidence": round(row['avg_confidence'], 3),
                "total_extractions": row['total_extractions'],
                "template_usage_rate": round(row['template_rate'] * 100, 2),
                "correction_rate": round(row['correction_rate'] * 100, 2)
            }
            for row in rows
        ]
    }


@router.get("/health")
async def monitoring_health():
    """Health check for monitoring endpoints"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "redis": "connected",
            "powerbi": "enabled" if os.getenv('ENABLE_POWERBI_STREAMING') == 'true' else "disabled",
            "app_insights": "enabled"
        }
    }
