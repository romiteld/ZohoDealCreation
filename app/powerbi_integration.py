"""
Power BI Integration for Learning System Analytics
Streams learning metrics, A/B test results, and cost optimization data to Power BI
"""

import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class PowerBIDataset(str, Enum):
    """Power BI datasets for different metric types"""
    EXTRACTION_METRICS = "extraction_metrics"
    AB_TEST_RESULTS = "ab_test_results"
    COST_OPTIMIZATION = "cost_optimization"
    FIELD_ACCURACY = "field_accuracy"
    LEARNING_PATTERNS = "learning_patterns"
    DEAL_PROCESSING = "deal_processing"  # Track individual deals


class ExtractionMetricRow(BaseModel):
    """Schema for extraction metrics in Power BI"""
    extraction_id: str
    timestamp: datetime
    email_domain: str
    overall_confidence: float
    overall_accuracy: float
    processing_time_ms: int
    prompt_variant: Optional[str] = None
    model_version: str = "gpt-5-mini"
    used_template: bool = False
    used_corrections: bool = False
    pattern_matches: int = 0
    cost_usd: float = 0.0


class ABTestResultRow(BaseModel):
    """Schema for A/B test results in Power BI"""
    variant_id: str
    variant_name: str
    timestamp: datetime
    total_uses: int
    successful_extractions: int
    average_accuracy: float
    average_confidence: float
    average_processing_time: float
    is_control: bool
    is_active: bool


class CostOptimizationRow(BaseModel):
    """Schema for cost optimization metrics in Power BI"""
    timestamp: datetime
    model_tier: str  # nano, mini, standard
    total_requests: int
    total_cost_usd: float
    average_tokens_input: int
    average_tokens_output: int
    cache_hit_rate: float
    cost_per_extraction: float
    budget_remaining_usd: float


class FieldAccuracyRow(BaseModel):
    """Schema for field-level accuracy in Power BI"""
    timestamp: datetime
    field_name: str
    email_domain: str
    confidence_score: float
    was_corrected: bool
    accuracy: float
    correction_type: Optional[str] = None


class LearningPatternRow(BaseModel):
    """Schema for learned patterns in Power BI"""
    timestamp: datetime
    pattern_type: str  # template, correction, semantic
    email_domain: str
    usage_count: int
    success_rate: float
    average_improvement: float
    last_used: datetime


class DealProcessingRow(BaseModel):
    """Schema for individual deal processing in Power BI"""
    deal_id: str  # Zoho Deal ID
    extraction_id: str  # Link to extraction metrics
    timestamp: datetime

    # Deal details
    deal_name: str
    company_name: str
    contact_name: str
    email_domain: str
    source: str  # Referral, Email Inbound, etc.

    # Processing metrics
    processing_stage: str  # Extract, Research, Validate, Create
    success: bool
    error_message: Optional[str] = None
    processing_time_ms: int

    # Extraction quality
    extraction_confidence: float
    fields_corrected: int
    used_template: bool
    used_firecrawl: bool
    used_apollo: bool

    # Cost tracking
    model_used: str  # gpt-5-nano, gpt-5-mini, gpt-5
    tokens_input: int
    tokens_output: int
    cost_usd: float

    # Business value
    estimated_deal_value: Optional[float] = None
    deal_stage: Optional[str] = None
    owner_email: str


class PowerBIIntegration:
    """
    Power BI streaming integration for real-time analytics

    Pushes learning metrics to Power BI datasets using Push API
    Requires Power BI Premium workspace with streaming datasets
    """

    def __init__(
        self,
        workspace_id: Optional[str] = None,
        api_key: Optional[str] = None,
        enable_streaming: bool = True,
        batch_size: int = 100
    ):
        """
        Initialize Power BI integration

        Args:
            workspace_id: Power BI workspace ID (from environment if not provided)
            api_key: Power BI API key (from environment if not provided)
            enable_streaming: Whether to enable real-time streaming
            batch_size: Number of rows to batch before pushing
        """
        self.workspace_id = workspace_id or os.getenv("POWERBI_WORKSPACE_ID")
        self.api_key = api_key or os.getenv("POWERBI_API_KEY")
        self.enable_streaming = enable_streaming and self.workspace_id and self.api_key
        self.batch_size = batch_size

        # Batch caches for each dataset
        self.batches: Dict[PowerBIDataset, List[Dict]] = {
            dataset: [] for dataset in PowerBIDataset
        }

        # Dataset URLs (constructed from workspace ID)
        self.dataset_urls = self._construct_dataset_urls() if self.enable_streaming else {}

        if self.enable_streaming:
            logger.info(f"Power BI streaming enabled for workspace {self.workspace_id}")
        else:
            logger.warning("Power BI streaming disabled - missing credentials")

    def _construct_dataset_urls(self) -> Dict[PowerBIDataset, str]:
        """Construct Power BI Push API URLs for each dataset"""
        base_url = f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}/datasets"

        # These dataset IDs should be created in Power BI first
        # For now, using placeholder - will be updated after dataset creation
        return {
            PowerBIDataset.EXTRACTION_METRICS: f"{base_url}/extraction_metrics/rows?key={self.api_key}",
            PowerBIDataset.AB_TEST_RESULTS: f"{base_url}/ab_test_results/rows?key={self.api_key}",
            PowerBIDataset.COST_OPTIMIZATION: f"{base_url}/cost_optimization/rows?key={self.api_key}",
            PowerBIDataset.FIELD_ACCURACY: f"{base_url}/field_accuracy/rows?key={self.api_key}",
            PowerBIDataset.LEARNING_PATTERNS: f"{base_url}/learning_patterns/rows?key={self.api_key}",
        }

    def log_extraction_metric(self, metric: ExtractionMetricRow) -> None:
        """
        Log an extraction metric to Power BI

        Args:
            metric: Extraction metric data
        """
        if not self.enable_streaming:
            return

        try:
            # Add to batch
            self.batches[PowerBIDataset.EXTRACTION_METRICS].append(metric.dict())

            # Also log to Application Insights for correlation
            logger.info(
                "Extraction metric",
                extra={
                    "custom_dimensions": {
                        "extraction_id": metric.extraction_id,
                        "email_domain": metric.email_domain,
                        "overall_accuracy": metric.overall_accuracy,
                        "overall_confidence": metric.overall_confidence,
                        "model_version": metric.model_version,
                        "cost_usd": metric.cost_usd,
                    }
                }
            )

            # Flush if batch is full
            if len(self.batches[PowerBIDataset.EXTRACTION_METRICS]) >= self.batch_size:
                self._flush_batch(PowerBIDataset.EXTRACTION_METRICS)

        except Exception as e:
            logger.error(f"Failed to log extraction metric to Power BI: {e}")

    def log_ab_test_result(self, result: ABTestResultRow) -> None:
        """Log A/B test results to Power BI"""
        if not self.enable_streaming:
            return

        try:
            self.batches[PowerBIDataset.AB_TEST_RESULTS].append(result.dict())

            logger.info(
                "A/B test result",
                extra={
                    "custom_dimensions": {
                        "variant_id": result.variant_id,
                        "variant_name": result.variant_name,
                        "average_accuracy": result.average_accuracy,
                        "is_control": result.is_control,
                    }
                }
            )

            if len(self.batches[PowerBIDataset.AB_TEST_RESULTS]) >= self.batch_size:
                self._flush_batch(PowerBIDataset.AB_TEST_RESULTS)

        except Exception as e:
            logger.error(f"Failed to log A/B test result to Power BI: {e}")

    def log_cost_optimization(self, metric: CostOptimizationRow) -> None:
        """Log cost optimization metrics to Power BI"""
        if not self.enable_streaming:
            return

        try:
            self.batches[PowerBIDataset.COST_OPTIMIZATION].append(metric.dict())

            logger.info(
                "Cost optimization metric",
                extra={
                    "custom_dimensions": {
                        "model_tier": metric.model_tier,
                        "total_cost_usd": metric.total_cost_usd,
                        "cache_hit_rate": metric.cache_hit_rate,
                        "budget_remaining_usd": metric.budget_remaining_usd,
                    }
                }
            )

            if len(self.batches[PowerBIDataset.COST_OPTIMIZATION]) >= self.batch_size:
                self._flush_batch(PowerBIDataset.COST_OPTIMIZATION)

        except Exception as e:
            logger.error(f"Failed to log cost optimization to Power BI: {e}")

    def log_field_accuracy(self, metric: FieldAccuracyRow) -> None:
        """Log field-level accuracy to Power BI"""
        if not self.enable_streaming:
            return

        try:
            self.batches[PowerBIDataset.FIELD_ACCURACY].append(metric.dict())

            if len(self.batches[PowerBIDataset.FIELD_ACCURACY]) >= self.batch_size:
                self._flush_batch(PowerBIDataset.FIELD_ACCURACY)

        except Exception as e:
            logger.error(f"Failed to log field accuracy to Power BI: {e}")

    def log_learning_pattern(self, pattern: LearningPatternRow) -> None:
        """Log learned pattern to Power BI"""
        if not self.enable_streaming:
            return

        try:
            self.batches[PowerBIDataset.LEARNING_PATTERNS].append(pattern.dict())

            logger.info(
                "Learning pattern",
                extra={
                    "custom_dimensions": {
                        "pattern_type": pattern.pattern_type,
                        "email_domain": pattern.email_domain,
                        "success_rate": pattern.success_rate,
                        "usage_count": pattern.usage_count,
                    }
                }
            )

            if len(self.batches[PowerBIDataset.LEARNING_PATTERNS]) >= self.batch_size:
                self._flush_batch(PowerBIDataset.LEARNING_PATTERNS)

        except Exception as e:
            logger.error(f"Failed to log learning pattern to Power BI: {e}")

    def log_deal_processing(self, deal: DealProcessingRow) -> None:
        """
        Log individual deal processing to Power BI

        This tracks every deal from email → Zoho with full traceability:
        - Which email domain it came from
        - What processing steps were taken
        - How much it cost to process
        - Whether enrichment services were used
        - Final deal details in Zoho

        Args:
            deal: Deal processing data
        """
        if not self.enable_streaming:
            return

        try:
            self.batches[PowerBIDataset.DEAL_PROCESSING].append(deal.dict())

            logger.info(
                "Deal processed",
                extra={
                    "custom_dimensions": {
                        "deal_id": deal.deal_id,
                        "deal_name": deal.deal_name,
                        "company_name": deal.company_name,
                        "email_domain": deal.email_domain,
                        "source": deal.source,
                        "processing_stage": deal.processing_stage,
                        "success": deal.success,
                        "model_used": deal.model_used,
                        "cost_usd": deal.cost_usd,
                        "extraction_confidence": deal.extraction_confidence,
                        "fields_corrected": deal.fields_corrected,
                        "used_firecrawl": deal.used_firecrawl,
                        "used_apollo": deal.used_apollo,
                        "owner_email": deal.owner_email,
                    }
                }
            )

            if len(self.batches[PowerBIDataset.DEAL_PROCESSING]) >= self.batch_size:
                self._flush_batch(PowerBIDataset.DEAL_PROCESSING)

        except Exception as e:
            logger.error(f"Failed to log deal processing to Power BI: {e}")

    def _flush_batch(self, dataset: PowerBIDataset) -> None:
        """Flush a batch of rows to Power BI"""
        if not self.enable_streaming or not self.batches[dataset]:
            return

        try:
            url = self.dataset_urls.get(dataset)
            if not url:
                logger.warning(f"No URL configured for dataset {dataset}")
                return

            # Convert datetime objects to ISO strings
            rows = []
            for row in self.batches[dataset]:
                serialized_row = {}
                for key, value in row.items():
                    if isinstance(value, datetime):
                        serialized_row[key] = value.isoformat()
                    else:
                        serialized_row[key] = value
                rows.append(serialized_row)

            # Push to Power BI
            response = requests.post(
                url,
                json={"rows": rows},
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Flushed {len(rows)} rows to Power BI dataset {dataset.value}")
                self.batches[dataset] = []  # Clear batch
            else:
                logger.error(
                    f"Power BI push failed for {dataset.value}: "
                    f"{response.status_code} - {response.text}"
                )

        except Exception as e:
            logger.error(f"Failed to flush batch to Power BI: {e}")

    def flush_all(self) -> None:
        """Flush all pending batches to Power BI"""
        for dataset in PowerBIDataset:
            self._flush_batch(dataset)

    def create_datasets_schema(self) -> Dict[str, Dict]:
        """
        Generate Power BI dataset schemas for manual creation

        Returns:
            Dictionary of dataset schemas compatible with Power BI REST API
        """
        return {
            "extraction_metrics": {
                "name": "Extraction Metrics",
                "tables": [{
                    "name": "ExtractionMetrics",
                    "columns": [
                        {"name": "extraction_id", "dataType": "string"},
                        {"name": "timestamp", "dataType": "datetime"},
                        {"name": "email_domain", "dataType": "string"},
                        {"name": "overall_confidence", "dataType": "double"},
                        {"name": "overall_accuracy", "dataType": "double"},
                        {"name": "processing_time_ms", "dataType": "int64"},
                        {"name": "prompt_variant", "dataType": "string"},
                        {"name": "model_version", "dataType": "string"},
                        {"name": "used_template", "dataType": "bool"},
                        {"name": "used_corrections", "dataType": "bool"},
                        {"name": "pattern_matches", "dataType": "int64"},
                        {"name": "cost_usd", "dataType": "double"},
                    ]
                }]
            },
            "ab_test_results": {
                "name": "A/B Test Results",
                "tables": [{
                    "name": "ABTestResults",
                    "columns": [
                        {"name": "variant_id", "dataType": "string"},
                        {"name": "variant_name", "dataType": "string"},
                        {"name": "timestamp", "dataType": "datetime"},
                        {"name": "total_uses", "dataType": "int64"},
                        {"name": "successful_extractions", "dataType": "int64"},
                        {"name": "average_accuracy", "dataType": "double"},
                        {"name": "average_confidence", "dataType": "double"},
                        {"name": "average_processing_time", "dataType": "double"},
                        {"name": "is_control", "dataType": "bool"},
                        {"name": "is_active", "dataType": "bool"},
                    ]
                }]
            },
            "cost_optimization": {
                "name": "Cost Optimization",
                "tables": [{
                    "name": "CostOptimization",
                    "columns": [
                        {"name": "timestamp", "dataType": "datetime"},
                        {"name": "model_tier", "dataType": "string"},
                        {"name": "total_requests", "dataType": "int64"},
                        {"name": "total_cost_usd", "dataType": "double"},
                        {"name": "average_tokens_input", "dataType": "int64"},
                        {"name": "average_tokens_output", "dataType": "int64"},
                        {"name": "cache_hit_rate", "dataType": "double"},
                        {"name": "cost_per_extraction", "dataType": "double"},
                        {"name": "budget_remaining_usd", "dataType": "double"},
                    ]
                }]
            },
            "field_accuracy": {
                "name": "Field Accuracy",
                "tables": [{
                    "name": "FieldAccuracy",
                    "columns": [
                        {"name": "timestamp", "dataType": "datetime"},
                        {"name": "field_name", "dataType": "string"},
                        {"name": "email_domain", "dataType": "string"},
                        {"name": "confidence_score", "dataType": "double"},
                        {"name": "was_corrected", "dataType": "bool"},
                        {"name": "accuracy", "dataType": "double"},
                        {"name": "correction_type", "dataType": "string"},
                    ]
                }]
            },
            "learning_patterns": {
                "name": "Learning Patterns",
                "tables": [{
                    "name": "LearningPatterns",
                    "columns": [
                        {"name": "timestamp", "dataType": "datetime"},
                        {"name": "pattern_type", "dataType": "string"},
                        {"name": "email_domain", "dataType": "string"},
                        {"name": "usage_count", "dataType": "int64"},
                        {"name": "success_rate", "dataType": "double"},
                        {"name": "average_improvement", "dataType": "double"},
                        {"name": "last_used", "dataType": "datetime"},
                    ]
                }]
            },
            "deal_processing": {
                "name": "Deal Processing",
                "tables": [{
                    "name": "DealProcessing",
                    "columns": [
                        {"name": "deal_id", "dataType": "string"},
                        {"name": "extraction_id", "dataType": "string"},
                        {"name": "timestamp", "dataType": "datetime"},
                        {"name": "deal_name", "dataType": "string"},
                        {"name": "company_name", "dataType": "string"},
                        {"name": "contact_name", "dataType": "string"},
                        {"name": "email_domain", "dataType": "string"},
                        {"name": "source", "dataType": "string"},
                        {"name": "processing_stage", "dataType": "string"},
                        {"name": "success", "dataType": "bool"},
                        {"name": "error_message", "dataType": "string"},
                        {"name": "processing_time_ms", "dataType": "int64"},
                        {"name": "extraction_confidence", "dataType": "double"},
                        {"name": "fields_corrected", "dataType": "int64"},
                        {"name": "used_template", "dataType": "bool"},
                        {"name": "used_firecrawl", "dataType": "bool"},
                        {"name": "used_apollo", "dataType": "bool"},
                        {"name": "model_used", "dataType": "string"},
                        {"name": "tokens_input", "dataType": "int64"},
                        {"name": "tokens_output", "dataType": "int64"},
                        {"name": "cost_usd", "dataType": "double"},
                        {"name": "estimated_deal_value", "dataType": "double"},
                        {"name": "deal_stage", "dataType": "string"},
                        {"name": "owner_email", "dataType": "string"},
                    ]
                }]
            }
        }


# Global instance for easy access
powerbi = PowerBIIntegration()
