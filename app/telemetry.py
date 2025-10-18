"""
Simple telemetry module for tracking events.
This is a stub that can be replaced with actual Application Insights integration.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def track_event(event_name: str, properties: Dict[str, Any] = None):
    """
    Track a custom telemetry event.

    Args:
        event_name: Name of the event to track
        properties: Optional properties/metadata for the event
    """
    # For now, just log the events
    # In production, this would send to Application Insights
    logger.info(f"Telemetry Event: {event_name}", extra={"properties": properties or {}})