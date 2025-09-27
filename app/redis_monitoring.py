"""
Redis Cache Monitoring and Alerting System

Provides comprehensive monitoring, alerting, and metrics collection
for Redis cache fallback mechanisms and circuit breaker patterns.
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of Redis cache alerts."""
    CONNECTION_FAILURE = "connection_failure"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    HIGH_ERROR_RATE = "high_error_rate"
    FALLBACK_MODE_ACTIVATED = "fallback_mode_activated"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    RECOVERY = "recovery"


@dataclass
class Alert:
    """Redis cache alert data structure."""
    alert_type: AlertType
    severity: AlertSeverity
    timestamp: datetime
    message: str
    details: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class RedisMetricsSnapshot:
    """Snapshot of Redis metrics at a point in time."""
    timestamp: datetime
    hits: int
    misses: int
    errors: int
    connection_failures: int
    timeout_failures: int
    fallback_activations: int
    savings: float
    uptime_percentage: float
    circuit_breaker_open: bool
    fallback_mode: bool
    is_connected: bool


class RedisMonitoringService:
    """Comprehensive Redis monitoring and alerting service."""
    
    def __init__(self):
        """Initialize monitoring service with configuration."""
        self.alerts: List[Alert] = []
        self.metrics_history: List[RedisMetricsSnapshot] = []
        
        # Alert thresholds
        self.error_rate_threshold = float(os.getenv("REDIS_ERROR_RATE_THRESHOLD", "10.0"))  # percentage
        self.connection_failure_threshold = int(os.getenv("REDIS_CONNECTION_FAILURE_THRESHOLD", "5"))
        self.monitoring_interval = int(os.getenv("REDIS_MONITORING_INTERVAL_MINUTES", "5"))
        
        # Email configuration
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.alert_recipients = os.getenv("REDIS_ALERT_RECIPIENTS", "").split(",")
        self.alert_recipients = [email.strip() for email in self.alert_recipients if email.strip()]
        
        # Slack webhook (optional)
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        
        # Monitoring state
        self.last_alert_times: Dict[AlertType, datetime] = {}
        self.alert_cooldown = timedelta(minutes=15)  # Prevent spam
        
        logger.info("Redis Monitoring Service initialized")
    
    async def collect_metrics_snapshot(self, cache_manager) -> RedisMetricsSnapshot:
        """Collect current metrics snapshot from cache manager."""
        try:
            metrics = await cache_manager.get_metrics()
            
            return RedisMetricsSnapshot(
                timestamp=datetime.now(),
                hits=metrics.get("hits", 0),
                misses=metrics.get("misses", 0),
                errors=metrics.get("errors", 0),
                connection_failures=metrics.get("connection_failures", 0),
                timeout_failures=metrics.get("timeout_failures", 0),
                fallback_activations=metrics.get("fallback_activations", 0),
                savings=metrics.get("savings", 0.0),
                uptime_percentage=float(metrics.get("uptime_percentage", "0").rstrip("%")),
                circuit_breaker_open=cache_manager.circuit_breaker.is_open,
                fallback_mode=cache_manager.fallback_mode,
                is_connected=cache_manager._connected
            )
        except Exception as e:
            logger.error(f"Failed to collect metrics snapshot: {e}")
            return RedisMetricsSnapshot(
                timestamp=datetime.now(),
                hits=0, misses=0, errors=0, connection_failures=0,
                timeout_failures=0, fallback_activations=0, savings=0.0,
                uptime_percentage=0.0, circuit_breaker_open=True,
                fallback_mode=True, is_connected=False
            )
    
    def should_send_alert(self, alert_type: AlertType) -> bool:
        """Check if alert should be sent based on cooldown period."""
        last_sent = self.last_alert_times.get(alert_type)
        if last_sent and datetime.now() - last_sent < self.alert_cooldown:
            return False
        return True
    
    async def analyze_metrics_and_alert(self, cache_manager):
        """Analyze current metrics and send alerts if thresholds are exceeded."""
        snapshot = await self.collect_metrics_snapshot(cache_manager)
        self.metrics_history.append(snapshot)
        
        # Keep only last 24 hours of metrics
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.metrics_history = [
            m for m in self.metrics_history if m.timestamp > cutoff_time
        ]
        
        # Check for alerting conditions
        await self._check_circuit_breaker_alert(snapshot)
        await self._check_fallback_mode_alert(snapshot)
        await self._check_connection_failure_alert(snapshot)
        await self._check_error_rate_alert()
        await self._check_performance_degradation_alert()
        await self._check_recovery_alert(snapshot)
    
    async def _check_circuit_breaker_alert(self, snapshot: RedisMetricsSnapshot):
        """Check if circuit breaker is open and send alert."""
        if snapshot.circuit_breaker_open and self.should_send_alert(AlertType.CIRCUIT_BREAKER_OPEN):
            alert = Alert(
                alert_type=AlertType.CIRCUIT_BREAKER_OPEN,
                severity=AlertSeverity.ERROR,
                timestamp=snapshot.timestamp,
                message="Redis Circuit Breaker is OPEN - Cache operations suspended",
                details={
                    "connection_failures": snapshot.connection_failures,
                    "uptime_percentage": snapshot.uptime_percentage,
                    "fallback_mode": snapshot.fallback_mode
                }
            )
            await self._send_alert(alert)
    
    async def _check_fallback_mode_alert(self, snapshot: RedisMetricsSnapshot):
        """Check if system is in fallback mode and send alert."""
        if snapshot.fallback_mode and self.should_send_alert(AlertType.FALLBACK_MODE_ACTIVATED):
            alert = Alert(
                alert_type=AlertType.FALLBACK_MODE_ACTIVATED,
                severity=AlertSeverity.WARNING,
                timestamp=snapshot.timestamp,
                message="Redis Cache in FALLBACK MODE - Operating without cache",
                details={
                    "is_connected": snapshot.is_connected,
                    "fallback_activations": snapshot.fallback_activations,
                    "estimated_cost_impact": f"${snapshot.savings * 30:.2f}/month lost savings"
                }
            )
            await self._send_alert(alert)
    
    async def _check_connection_failure_alert(self, snapshot: RedisMetricsSnapshot):
        """Check for excessive connection failures."""
        if (snapshot.connection_failures >= self.connection_failure_threshold and 
            self.should_send_alert(AlertType.CONNECTION_FAILURE)):
            alert = Alert(
                alert_type=AlertType.CONNECTION_FAILURE,
                severity=AlertSeverity.ERROR,
                timestamp=snapshot.timestamp,
                message=f"High Redis Connection Failures: {snapshot.connection_failures}",
                details={
                    "connection_failures": snapshot.connection_failures,
                    "timeout_failures": snapshot.timeout_failures,
                    "circuit_breaker_open": snapshot.circuit_breaker_open
                }
            )
            await self._send_alert(alert)
    
    async def _check_error_rate_alert(self):
        """Check if error rate is above threshold."""
        if len(self.metrics_history) < 2:
            return
        
        # Calculate error rate over last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > one_hour_ago]
        
        if not recent_metrics:
            return
        
        total_operations = sum(m.hits + m.misses + m.errors for m in recent_metrics)
        total_errors = sum(m.errors for m in recent_metrics)
        
        if total_operations > 0:
            error_rate = (total_errors / total_operations) * 100
            
            if error_rate > self.error_rate_threshold and self.should_send_alert(AlertType.HIGH_ERROR_RATE):
                alert = Alert(
                    alert_type=AlertType.HIGH_ERROR_RATE,
                    severity=AlertSeverity.WARNING,
                    timestamp=datetime.now(),
                    message=f"High Redis Error Rate: {error_rate:.2f}% (threshold: {self.error_rate_threshold}%)",
                    details={
                        "error_rate_percentage": error_rate,
                        "total_errors": total_errors,
                        "total_operations": total_operations,
                        "time_window": "1 hour"
                    }
                )
                await self._send_alert(alert)
    
    async def _check_performance_degradation_alert(self):
        """Check for performance degradation patterns."""
        if len(self.metrics_history) < 10:  # Need history to compare
            return
        
        # Compare uptime percentage over time
        recent_metrics = self.metrics_history[-5:]  # Last 5 snapshots
        older_metrics = self.metrics_history[-10:-5]  # Previous 5 snapshots
        
        if recent_metrics and older_metrics:
            recent_avg_uptime = sum(m.uptime_percentage for m in recent_metrics) / len(recent_metrics)
            older_avg_uptime = sum(m.uptime_percentage for m in older_metrics) / len(older_metrics)
            
            degradation = older_avg_uptime - recent_avg_uptime
            
            if (degradation > 20.0 and  # 20% degradation
                self.should_send_alert(AlertType.PERFORMANCE_DEGRADATION)):
                alert = Alert(
                    alert_type=AlertType.PERFORMANCE_DEGRADATION,
                    severity=AlertSeverity.WARNING,
                    timestamp=datetime.now(),
                    message=f"Redis Performance Degradation: {degradation:.1f}% drop in uptime",
                    details={
                        "recent_avg_uptime": recent_avg_uptime,
                        "previous_avg_uptime": older_avg_uptime,
                        "degradation_percentage": degradation
                    }
                )
                await self._send_alert(alert)
    
    async def _check_recovery_alert(self, snapshot: RedisMetricsSnapshot):
        """Check if Redis has recovered and send recovery notification."""
        if (snapshot.is_connected and 
            not snapshot.fallback_mode and 
            not snapshot.circuit_breaker_open and
            self.should_send_alert(AlertType.RECOVERY)):
            
            # Only send recovery alert if we had recent issues
            recent_issues = any(
                alert.alert_type in [
                    AlertType.CONNECTION_FAILURE, 
                    AlertType.CIRCUIT_BREAKER_OPEN, 
                    AlertType.FALLBACK_MODE_ACTIVATED
                ] 
                and not alert.resolved 
                and alert.timestamp > datetime.now() - timedelta(hours=2)
                for alert in self.alerts
            )
            
            if recent_issues:
                alert = Alert(
                    alert_type=AlertType.RECOVERY,
                    severity=AlertSeverity.INFO,
                    timestamp=snapshot.timestamp,
                    message="Redis Cache RECOVERED - Full functionality restored",
                    details={
                        "uptime_percentage": snapshot.uptime_percentage,
                        "cache_hit_rate": f"{snapshot.hits / (snapshot.hits + snapshot.misses) * 100:.1f}%" if (snapshot.hits + snapshot.misses) > 0 else "N/A",
                        "estimated_savings_restored": f"${snapshot.savings * 30:.2f}/month"
                    }
                )
                await self._send_alert(alert)
                
                # Mark previous alerts as resolved
                for prev_alert in self.alerts:
                    if (prev_alert.alert_type in [
                        AlertType.CONNECTION_FAILURE, 
                        AlertType.CIRCUIT_BREAKER_OPEN, 
                        AlertType.FALLBACK_MODE_ACTIVATED
                    ] and not prev_alert.resolved):
                        prev_alert.resolved = True
                        prev_alert.resolved_at = datetime.now()
    
    async def _send_alert(self, alert: Alert):
        """Send alert via configured channels (email, Slack)."""
        self.alerts.append(alert)
        self.last_alert_times[alert.alert_type] = alert.timestamp
        
        logger.warning(f"Redis Alert [{alert.severity.value.upper()}]: {alert.message}")
        
        # Send email alert
        if self.alert_recipients and self.smtp_server:
            await self._send_email_alert(alert)
        
        # Send Slack alert
        if self.slack_webhook_url:
            await self._send_slack_alert(alert)
    
    async def _send_email_alert(self, alert: Alert):
        """Send alert via email."""
        try:
            msg = MimeMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = ", ".join(self.alert_recipients)
            msg['Subject'] = f"[Redis Cache Alert - {alert.severity.value.upper()}] {alert.alert_type.value}"
            
            # Create HTML email body
            html_body = f"""
            <html>
            <head></head>
            <body>
                <h2 style="color: {'#dc3545' if alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL] else '#ffc107'};">
                    Redis Cache Alert
                </h2>
                <p><strong>Alert Type:</strong> {alert.alert_type.value}</p>
                <p><strong>Severity:</strong> {alert.severity.value.upper()}</p>
                <p><strong>Timestamp:</strong> {alert.timestamp.isoformat()}</p>
                <p><strong>Message:</strong> {alert.message}</p>
                
                <h3>Details:</h3>
                <ul>
                    {"".join(f"<li><strong>{k}:</strong> {v}</li>" for k, v in alert.details.items())}
                </ul>
                
                <hr>
                <p style="font-size: 12px; color: #666;">
                    This alert was generated by the Well Intake API Redis Monitoring System.
                    <br>
                    Time: {datetime.now().isoformat()}
                </p>
            </body>
            </html>
            """
            
            msg.attach(MimeText(html_body, 'html'))
            
            # Send email (run in thread to avoid blocking)
            def send_email():
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            
            # Run email sending in background
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, send_email)
            
            logger.info(f"Sent email alert for {alert.alert_type.value} to {len(self.alert_recipients)} recipients")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    async def _send_slack_alert(self, alert: Alert):
        """Send alert via Slack webhook."""
        try:
            import aiohttp
            
            color_map = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ff9900",
                AlertSeverity.ERROR: "#ff0000",
                AlertSeverity.CRITICAL: "#800000"
            }
            
            payload = {
                "attachments": [{
                    "color": color_map.get(alert.severity, "#cccccc"),
                    "title": f"Redis Cache Alert - {alert.alert_type.value}",
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert.severity.value.upper(),
                            "short": True
                        },
                        {
                            "title": "Timestamp",
                            "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                            "short": True
                        }
                    ] + [
                        {
                            "title": k.replace("_", " ").title(),
                            "value": str(v),
                            "short": True
                        } for k, v in alert.details.items()
                    ],
                    "footer": "Well Intake API Redis Monitoring",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.slack_webhook_url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Sent Slack alert for {alert.alert_type.value}")
                    else:
                        logger.error(f"Failed to send Slack alert: HTTP {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    def get_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of alerts from the last N hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_alerts = [alert for alert in self.alerts if alert.timestamp > cutoff_time]
        
        summary = {
            "total_alerts": len(recent_alerts),
            "time_window_hours": hours,
            "alerts_by_type": {},
            "alerts_by_severity": {},
            "resolved_alerts": sum(1 for alert in recent_alerts if alert.resolved),
            "unresolved_alerts": sum(1 for alert in recent_alerts if not alert.resolved),
            "latest_alerts": [
                {
                    "type": alert.alert_type.value,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "resolved": alert.resolved
                }
                for alert in recent_alerts[-5:]  # Last 5 alerts
            ]
        }
        
        # Count by type and severity
        for alert in recent_alerts:
            alert_type = alert.alert_type.value
            severity = alert.severity.value
            
            summary["alerts_by_type"][alert_type] = summary["alerts_by_type"].get(alert_type, 0) + 1
            summary["alerts_by_severity"][severity] = summary["alerts_by_severity"].get(severity, 0) + 1
        
        return summary
    
    def get_metrics_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive metrics report."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
        if not recent_metrics:
            return {"error": "No metrics data available"}
        
        # Calculate aggregated statistics
        total_hits = sum(m.hits for m in recent_metrics)
        total_misses = sum(m.misses for m in recent_metrics)
        total_errors = sum(m.errors for m in recent_metrics)
        avg_uptime = sum(m.uptime_percentage for m in recent_metrics) / len(recent_metrics)
        total_savings = sum(m.savings for m in recent_metrics)
        
        latest_metrics = recent_metrics[-1]
        
        return {
            "time_window_hours": hours,
            "data_points": len(recent_metrics),
            "totals": {
                "hits": total_hits,
                "misses": total_misses,
                "errors": total_errors,
                "total_operations": total_hits + total_misses + total_errors,
                "savings_usd": total_savings
            },
            "averages": {
                "uptime_percentage": avg_uptime,
                "hit_rate_percentage": (total_hits / (total_hits + total_misses) * 100) if (total_hits + total_misses) > 0 else 0
            },
            "current_status": {
                "is_connected": latest_metrics.is_connected,
                "fallback_mode": latest_metrics.fallback_mode,
                "circuit_breaker_open": latest_metrics.circuit_breaker_open,
                "uptime_percentage": latest_metrics.uptime_percentage
            },
            "projections": {
                "monthly_savings_usd": total_savings * 30 / (hours / 24),  # Project to monthly
                "monthly_operations": (total_hits + total_misses) * 30 / (hours / 24)
            }
        }
    
    async def start_monitoring(self, cache_manager, interval_minutes: int = None):
        """Start continuous monitoring of Redis cache."""
        interval = interval_minutes or self.monitoring_interval
        
        logger.info(f"Starting Redis monitoring service (interval: {interval} minutes)")
        
        async def monitoring_loop():
            while True:
                try:
                    await self.analyze_metrics_and_alert(cache_manager)
                    await asyncio.sleep(interval * 60)
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(60)  # Wait 1 minute before retrying
        
        # Start monitoring in background
        asyncio.create_task(monitoring_loop())


# Singleton instance
_monitoring_service: Optional[RedisMonitoringService] = None


def get_monitoring_service() -> RedisMonitoringService:
    """Get or create the singleton monitoring service instance."""
    global _monitoring_service
    
    if _monitoring_service is None:
        _monitoring_service = RedisMonitoringService()
    
    return _monitoring_service