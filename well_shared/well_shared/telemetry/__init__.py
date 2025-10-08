"""
Application Insights telemetry for Well services.

Provides unified telemetry across:
- Teams Bot
- Vault Agent
- Main API
"""

from .insights import (
    get_telemetry_client,
    track_event,
    track_metric,
    track_exception,
    track_dependency,
    track_request,
    track_operation,
    flush_telemetry,
    Metrics,
    Events,
)

__all__ = [
    "get_telemetry_client",
    "track_event",
    "track_metric",
    "track_exception",
    "track_dependency",
    "track_request",
    "track_operation",
    "flush_telemetry",
    "Metrics",
    "Events",
]
