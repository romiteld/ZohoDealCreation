"""
Centralized telemetry helper for Application Insights integration.

This module provides a singleton TelemetryHelper class for tracking
custom events and metrics across the application.

Usage:
    from app.utils.telemetry import telemetry

    telemetry.track_zoho_call(
        duration_ms=150,
        success=True,
        module='deals'
    )
"""
import os
from applicationinsights import TelemetryClient
from applicationinsights.channel import SynchronousSender, SynchronousQueue, TelemetryChannel


class TelemetryHelper:
    """
    Singleton helper for Application Insights telemetry tracking.

    Initializes with Azure Application Insights connection string
    and provides methods for tracking custom events.
    """

    def __init__(self):
        """
        Initialize telemetry client with Application Insights.

        Parses the APPLICATIONINSIGHTS_CONNECTION_STRING environment variable
        to extract the InstrumentationKey and configures a custom channel
        with 15-second batching for optimal performance.
        """
        try:
            conn_str = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING', '')
            # Parse InstrumentationKey from connection string
            key = self._parse_instrumentation_key(conn_str)

            # Configure channel with 15-second batch interval
            sender = SynchronousSender()
            queue = SynchronousQueue(sender)
            channel = TelemetryChannel(None, queue)
            channel.sender.send_buffer_size = 1
            channel.sender.send_time = 15.0  # 15 seconds

            self.client = TelemetryClient(key, channel)
            self.client.context.application.ver = '2.0'
        except Exception as e:
            print(f"Warning: Telemetry initialization failed: {e}")
            self.client = None

    def _parse_instrumentation_key(self, conn_str: str) -> str:
        """
        Extract InstrumentationKey from Application Insights connection string.

        Args:
            conn_str: Connection string in format
                     "InstrumentationKey=xxx;IngestionEndpoint=yyy;..."

        Returns:
            The instrumentation key or empty string if not found
        """
        for part in conn_str.split(';'):
            if part.startswith('InstrumentationKey='):
                return part.split('=', 1)[1]
        return ''

    def track_zoho_call(self, duration_ms: int, success: bool, module: str = 'unknown'):
        """
        Track a Zoho API call event with duration and success status.

        Args:
            duration_ms: Call duration in milliseconds
            success: Whether the call succeeded
            module: Which module made the call (e.g., 'deals', 'contacts')

        Example:
            telemetry.track_zoho_call(duration_ms=150, success=True, module='deals')
        """
        if not self.client:
            return
        try:
            self.client.track_event('zoho_api_call', {
                'module': module,
                'success': str(success),
                'duration_ms': duration_ms
            })
            # FIXED: Removed flush() - let 15-second batch interval handle it
        except Exception as e:
            print(f"Warning: Telemetry tracking failed: {e}")


# Singleton instance
telemetry = TelemetryHelper()
