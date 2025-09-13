"""
Application monitoring and observability module for Well Intake API.
Integrates with Azure Application Insights for custom metrics, performance tracking,
cost monitoring, and alert definitions.
"""

import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from functools import wraps
import asyncio
from contextlib import asynccontextmanager

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace, metrics
from opentelemetry.metrics import get_meter
from opentelemetry.trace import get_tracer
from azure.monitor.query import LogsQueryClient, MetricsQueryClient
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import HttpResponseError

# Import for cost calculation
import tiktoken


class MonitoringService:
    """Enterprise monitoring service for Well Intake API."""
    
    def __init__(self):
        """Initialize monitoring with Application Insights."""
        self.connection_string = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
        self.workspace_id = os.getenv('LOG_ANALYTICS_WORKSPACE_ID')
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        
        # Initialize Azure Monitor
        if self.connection_string:
            configure_azure_monitor(
                connection_string=self.connection_string,
                disable_offline_storage=False,
                enable_live_metrics=True
            )
        
        # Initialize OpenTelemetry
        self.tracer = get_tracer("well-intake-api", "1.0.0")
        self.meter = get_meter("well-intake-api", "1.0.0")
        
        # Initialize Azure clients for querying
        self.credential = DefaultAzureCredential()
        self.logs_client = LogsQueryClient(self.credential) if self.workspace_id else None
        self.metrics_client = MetricsQueryClient(self.credential) if self.workspace_id else None
        
        # Create custom metrics
        self._create_custom_metrics()
        
        # Token encoder for cost calculation
        self.encoder = tiktoken.encoding_for_model("gpt-4o-mini")
        
        # Cost rates (per 1M tokens as of 2025)
        self.token_costs = {
            "gpt-4o-mini": {
                "input": 0.15,  # $0.15 per 1M input tokens
                "output": 0.60   # $0.60 per 1M output tokens
            }
        }
    
    def _create_custom_metrics(self):
        """Create custom metrics for monitoring."""
        # Processing metrics
        self.email_processing_counter = self.meter.create_counter(
            "email_processing_total",
            description="Total number of emails processed",
            unit="emails"
        )
        
        self.processing_duration = self.meter.create_histogram(
            "email_processing_duration_seconds",
            description="Duration of email processing",
            unit="seconds"
        )
        
        # GPT-5-mini specific metrics
        self.gpt_request_counter = self.meter.create_counter(
            "gpt_requests_total",
            description="Total GPT-5-mini API requests",
            unit="requests"
        )
        
        self.gpt_token_counter = self.meter.create_counter(
            "gpt_tokens_total",
            description="Total tokens used by GPT-5-mini",
            unit="tokens"
        )
        
        self.gpt_latency = self.meter.create_histogram(
            "gpt_latency_seconds",
            description="GPT-5-mini API latency",
            unit="seconds"
        )
        
        self.gpt_cost_counter = self.meter.create_counter(
            "gpt_cost_usd",
            description="Estimated GPT-5-mini cost in USD",
            unit="USD"
        )
        
        # Zoho integration metrics
        self.zoho_api_counter = self.meter.create_counter(
            "zoho_api_requests_total",
            description="Total Zoho API requests",
            unit="requests"
        )
        
        self.zoho_api_errors = self.meter.create_counter(
            "zoho_api_errors_total",
            description="Total Zoho API errors",
            unit="errors"
        )
        
        # Deduplication metrics
        self.duplicate_detection_counter = self.meter.create_counter(
            "duplicate_detections_total",
            description="Total duplicate records detected",
            unit="duplicates"
        )
        
        # System metrics
        self.active_connections = self.meter.create_up_down_counter(
            "active_connections",
            description="Current active connections",
            unit="connections"
        )
        
        self.memory_usage = self.meter.create_observable_gauge(
            "memory_usage_bytes",
            callbacks=[self._get_memory_usage],
            description="Current memory usage",
            unit="bytes"
        )
    
    def _get_memory_usage(self, options):
        """Callback for memory usage metric."""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss
    
    def calculate_token_cost(self, input_text: str, output_text: str) -> Dict[str, float]:
        """Calculate the cost of GPT-5-mini usage."""
        input_tokens = len(self.encoder.encode(input_text))
        output_tokens = len(self.encoder.encode(output_text))
        
        rates = self.token_costs.get(self.openai_model, self.token_costs["gpt-4o-mini"])
        
        input_cost = (input_tokens / 1_000_000) * rates["input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]
        total_cost = input_cost + output_cost
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost
        }
    
    def track_gpt_request(self, operation_name: str = "gpt_request"):
        """Context manager for tracking GPT-5-mini requests."""
        # Removed @asynccontextmanager to fix generator athrow() error
        
        class GPTTrackingWrapper:
            """Custom async context manager to avoid generator issues"""
            def __init__(self, monitor, op_name):
                self.monitor = monitor
                self.operation_name = op_name
                self.span = None
                self.start_time = None
                self.span_context = None
                
            async def __aenter__(self):
                self.span_context = self.monitor.tracer.start_as_current_span(self.operation_name)
                self.span = self.span_context.__enter__()
                self.start_time = time.time()
                
                # Set span attributes
                self.span.set_attribute("model", self.monitor.openai_model)
                self.span.set_attribute("operation", self.operation_name)
                
                return self.span
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                try:
                    if exc_type is None:
                        # Record success metrics
                        duration = time.time() - self.start_time
                        self.monitor.gpt_request_counter.add(1, {"status": "success", "operation": self.operation_name})
                        self.monitor.gpt_latency.record(duration, {"operation": self.operation_name})
                        
                        self.span.set_attribute("duration_seconds", duration)
                        self.span.set_status(trace.Status(trace.StatusCode.OK))
                    else:
                        # Record error metrics
                        self.monitor.gpt_request_counter.add(1, {"status": "error", "operation": self.operation_name})
                        self.span.record_exception(exc_val)
                        self.span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc_val)))
                finally:
                    if self.span_context:
                        self.span_context.__exit__(exc_type, exc_val, exc_tb)
                
                return False  # Don't suppress exceptions
        
        return GPTTrackingWrapper(self, operation_name)
    
    def track_email_processing(self, func):
        """Decorator for tracking email processing operations."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with self.tracer.start_as_current_span(f"email_processing.{func.__name__}") as span:
                start_time = time.time()
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # Record success metrics
                    duration = time.time() - start_time
                    self.email_processing_counter.add(1, {"status": "success"})
                    self.processing_duration.record(duration)
                    
                    span.set_attribute("duration_seconds", duration)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    
                    return result
                    
                except Exception as e:
                    # Record error metrics
                    self.email_processing_counter.add(1, {"status": "error"})
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    
    def track_zoho_api_call(self, func):
        """Decorator for tracking Zoho API calls."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with self.tracer.start_as_current_span(f"zoho_api.{func.__name__}") as span:
                start_time = time.time()
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # Record success metrics
                    duration = time.time() - start_time
                    self.zoho_api_counter.add(1, {"status": "success", "operation": func.__name__})
                    
                    span.set_attribute("duration_seconds", duration)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    
                    return result
                    
                except Exception as e:
                    # Record error metrics
                    self.zoho_api_errors.add(1, {"operation": func.__name__})
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    
    def record_duplicate_detection(self, record_type: str, record_id: str):
        """Record duplicate detection event."""
        self.duplicate_detection_counter.add(1, {"type": record_type})
        
        with self.tracer.start_as_current_span("duplicate_detection") as span:
            span.set_attribute("record_type", record_type)
            span.set_attribute("record_id", record_id)
    
    def record_gpt_usage(self, input_text: str, output_text: str, operation: str):
        """Record GPT-5-mini usage metrics and cost."""
        cost_info = self.calculate_token_cost(input_text, output_text)
        
        # Record token usage
        self.gpt_token_counter.add(cost_info["input_tokens"], {"type": "input", "operation": operation})
        self.gpt_token_counter.add(cost_info["output_tokens"], {"type": "output", "operation": operation})
        
        # Record cost
        self.gpt_cost_counter.add(cost_info["total_cost"], {"operation": operation})
        
        # Log detailed info
        with self.tracer.start_as_current_span("gpt_usage") as span:
            span.set_attribute("operation", operation)
            span.set_attribute("input_tokens", cost_info["input_tokens"])
            span.set_attribute("output_tokens", cost_info["output_tokens"])
            span.set_attribute("total_cost_usd", cost_info["total_cost"])
        
        return cost_info
    
    async def query_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Query performance metrics from Application Insights."""
        if not self.logs_client or not self.workspace_id:
            return {"error": "Monitoring not configured"}
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # KQL query for performance metrics
        query = """
        customMetrics
        | where timestamp between(datetime({start}) .. datetime({end}))
        | where name in ('email_processing_duration_seconds', 'gpt_latency_seconds')
        | summarize 
            avg_duration = avg(value),
            p95_duration = percentile(value, 95),
            p99_duration = percentile(value, 99),
            max_duration = max(value),
            count = count()
            by name
        """.format(
            start=start_time.isoformat(),
            end=end_time.isoformat()
        )
        
        try:
            response = await self.logs_client.query_workspace(
                workspace_id=self.workspace_id,
                query=query,
                timespan=(start_time, end_time)
            )
            
            return {
                "metrics": response.tables[0].rows if response.tables else [],
                "period": f"{hours} hours",
                "timestamp": datetime.utcnow().isoformat()
            }
        except HttpResponseError as e:
            return {"error": str(e)}
    
    async def query_cost_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Query cost metrics for GPT-5-mini usage."""
        if not self.logs_client or not self.workspace_id:
            return {"error": "Monitoring not configured"}
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # KQL query for cost metrics
        query = """
        customMetrics
        | where timestamp between(datetime({start}) .. datetime({end}))
        | where name == 'gpt_cost_usd'
        | summarize 
            total_cost = sum(value),
            avg_cost_per_request = avg(value),
            request_count = count()
            by bin(timestamp, 1d)
        | order by timestamp asc
        """.format(
            start=start_time.isoformat(),
            end=end_time.isoformat()
        )
        
        try:
            response = await self.logs_client.query_workspace(
                workspace_id=self.workspace_id,
                query=query,
                timespan=(start_time, end_time)
            )
            
            daily_costs = []
            total_cost = 0
            
            for row in response.tables[0].rows if response.tables else []:
                daily_costs.append({
                    "date": row[0],
                    "cost": row[1],
                    "avg_per_request": row[2],
                    "requests": row[3]
                })
                total_cost += row[1] or 0
            
            return {
                "daily_costs": daily_costs,
                "total_cost": total_cost,
                "period_days": days,
                "timestamp": datetime.utcnow().isoformat()
            }
        except HttpResponseError as e:
            return {"error": str(e)}
    
    def get_alert_definitions(self) -> List[Dict[str, Any]]:
        """Get alert definitions for anomaly detection."""
        return [
            {
                "name": "High Error Rate",
                "metric": "email_processing_total",
                "condition": "error_rate > 0.05",
                "severity": "critical",
                "description": "Email processing error rate exceeds 5%",
                "action": "notify_oncall"
            },
            {
                "name": "High GPT Latency",
                "metric": "gpt_latency_seconds",
                "condition": "p95 > 5",
                "severity": "warning",
                "description": "GPT-5-mini P95 latency exceeds 5 seconds",
                "action": "notify_team"
            },
            {
                "name": "Excessive GPT Cost",
                "metric": "gpt_cost_usd",
                "condition": "daily_cost > 100",
                "severity": "warning",
                "description": "Daily GPT-5-mini cost exceeds $100",
                "action": "notify_finance"
            },
            {
                "name": "Zoho API Failures",
                "metric": "zoho_api_errors_total",
                "condition": "error_rate > 0.10",
                "severity": "critical",
                "description": "Zoho API error rate exceeds 10%",
                "action": "notify_oncall"
            },
            {
                "name": "High Duplicate Rate",
                "metric": "duplicate_detections_total",
                "condition": "rate > 0.30",
                "severity": "info",
                "description": "Duplicate detection rate exceeds 30%",
                "action": "log_metric"
            },
            {
                "name": "Memory Usage High",
                "metric": "memory_usage_bytes",
                "condition": "value > 1073741824",  # 1GB
                "severity": "warning",
                "description": "Memory usage exceeds 1GB",
                "action": "notify_team"
            },
            {
                "name": "Processing Duration Anomaly",
                "metric": "email_processing_duration_seconds",
                "condition": "p99 > 10",
                "severity": "warning",
                "description": "Email processing P99 exceeds 10 seconds",
                "action": "notify_team"
            }
        ]
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        # Check Application Insights connection
        health_status["checks"]["application_insights"] = {
            "status": "connected" if self.connection_string else "not_configured"
        }
        
        # Check Log Analytics
        health_status["checks"]["log_analytics"] = {
            "status": "connected" if self.workspace_id else "not_configured"
        }
        
        # Get recent metrics if available
        if self.logs_client and self.workspace_id:
            try:
                perf_metrics = await self.query_performance_metrics(1)
                health_status["checks"]["recent_performance"] = {
                    "status": "available",
                    "data": perf_metrics
                }
            except Exception as e:
                health_status["checks"]["recent_performance"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return health_status


# Global monitoring instance
monitoring = MonitoringService()


# Export decorators and functions for use in other modules
track_email_processing = monitoring.track_email_processing
track_zoho_api_call = monitoring.track_zoho_api_call
track_gpt_request = monitoring.track_gpt_request
record_duplicate_detection = monitoring.record_duplicate_detection
record_gpt_usage = monitoring.record_gpt_usage
query_performance_metrics = monitoring.query_performance_metrics
query_cost_metrics = monitoring.query_cost_metrics
get_alert_definitions = monitoring.get_alert_definitions
health_check = monitoring.health_check