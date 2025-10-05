"""
Learning Analytics System with Application Insights Integration
Tracks extraction accuracy, confidence scoring, and A/B testing for prompt variations
"""

import os
import json
import logging
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from enum import Enum
import random
import asyncio

# Application Insights imports
try:
    from applicationinsights import TelemetryClient
    from applicationinsights.channel import TelemetryChannel
    from applicationinsights.channel import AsynchronousSender
    from applicationinsights.channel import AsynchronousQueue
    APP_INSIGHTS_AVAILABLE = True
except ImportError:
    APP_INSIGHTS_AVAILABLE = False
    TelemetryClient = None

# Import Azure AI Search manager
from .azure_ai_search_manager import AzureAISearchManager

logger = logging.getLogger(__name__)


class ExtractionMetric(BaseModel):
    """Metrics for a single extraction"""
    extraction_id: str = Field(description="Unique ID for this extraction")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    email_domain: str
    
    # Field-level metrics
    field_scores: Dict[str, float] = Field(description="Confidence score per field")
    field_corrections: Dict[str, bool] = Field(default_factory=dict, description="Whether field was corrected")
    field_accuracy: Dict[str, float] = Field(default_factory=dict, description="Accuracy per field")
    
    # Overall metrics
    overall_confidence: float = Field(description="Overall extraction confidence")
    overall_accuracy: float = Field(default=1.0, description="Overall accuracy after corrections")
    processing_time_ms: int = Field(description="Time taken for extraction in milliseconds")
    
    # A/B testing data
    prompt_variant: Optional[str] = Field(None, description="Which prompt variant was used")
    model_version: str = Field(default="gpt-5-mini", description="Model used for extraction")
    
    # Learning indicators
    used_template: bool = Field(default=False, description="Whether company template was used")
    used_corrections: bool = Field(default=False, description="Whether historical corrections were applied")
    pattern_matches: int = Field(default=0, description="Number of similar patterns found")


class PromptVariant(BaseModel):
    """A/B test variant for prompts"""
    variant_id: str = Field(description="Unique variant identifier")
    variant_name: str = Field(description="Human-readable variant name")
    prompt_template: str = Field(description="The prompt template")
    
    # Performance metrics
    total_uses: int = Field(default=0)
    successful_extractions: int = Field(default=0)
    average_accuracy: float = Field(default=0.0)
    average_confidence: float = Field(default=0.0)
    average_processing_time: float = Field(default=0.0)
    
    # Field-specific performance
    field_performance: Dict[str, float] = Field(default_factory=dict)
    
    # Testing metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    is_active: bool = Field(default=True)
    is_control: bool = Field(default=False, description="Whether this is the control variant")


class TestStrategy(str, Enum):
    """A/B testing strategies"""
    RANDOM = "random"  # Random selection
    EPSILON_GREEDY = "epsilon_greedy"  # Exploit best with exploration
    THOMPSON_SAMPLING = "thompson_sampling"  # Bayesian approach
    ROUND_ROBIN = "round_robin"  # Sequential rotation


class LearningAnalytics:
    """Analytics system for tracking and improving extraction accuracy"""
    
    def __init__(
        self,
        search_manager: Optional[AzureAISearchManager] = None,
        app_insights_key: Optional[str] = None,
        enable_ab_testing: bool = True,
        test_strategy: TestStrategy = TestStrategy.EPSILON_GREEDY,
        epsilon: float = 0.1
    ):
        """Initialize learning analytics system"""
        self.search_manager = search_manager or AzureAISearchManager()
        self.enable_ab_testing = enable_ab_testing
        self.test_strategy = test_strategy
        self.epsilon = epsilon
        
        # Initialize Application Insights
        self.telemetry_client = None
        if APP_INSIGHTS_AVAILABLE:
            connection_string = app_insights_key or os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
            if connection_string:
                try:
                    self.telemetry_client = TelemetryClient(connection_string)
                    logger.info("Application Insights initialized for learning analytics")
                except Exception as e:
                    logger.warning(f"Could not initialize Application Insights: {e}")
        
        # Prompt variants for A/B testing
        self.prompt_variants: Dict[str, PromptVariant] = {}
        self._initialize_default_variants()
        
        # In-memory metrics cache (for aggregation before sending to App Insights)
        self.metrics_cache: List[ExtractionMetric] = []
        self.cache_size = 100  # Batch size for sending metrics
    
    def _initialize_default_variants(self):
        """Initialize default prompt variants for A/B testing"""
        if not self.enable_ab_testing:
            return
        
        # Control variant - standard prompt
        control = PromptVariant(
            variant_id="control",
            variant_name="Standard Extraction",
            prompt_template="""Extract the following information from the email:
- Candidate Name: The full name of the person being discussed
- Job Title: The position or role
- Location: The geographical location
- Company Name: The organization name
- Referrer Name: Who made the referral (if any)
- Website: Company website URL
- Phone: Contact number
- Industry: Business sector

Be precise and extract only what is explicitly mentioned.""",
            is_control=True
        )
        
        # Variant A - Structured with examples
        variant_a = PromptVariant(
            variant_id="structured_examples",
            variant_name="Structured with Examples",
            prompt_template="""You are an expert recruiter assistant. Extract candidate information with high precision.

EXTRACTION RULES:
1. Only extract explicitly stated information
2. Use "Unknown" for missing fields
3. Preserve exact formatting from the email

FIELDS TO EXTRACT:
• Candidate Name: Full name (e.g., "John Smith", "Jane Doe-Johnson")
• Job Title: Complete role with seniority (e.g., "Senior Financial Advisor", "VP of Sales")
• Location: City, State format (e.g., "Fort Wayne, Indiana", "New York, NY")
• Company Name: Official organization name
• Referrer Name: Person who referred (if mentioned)
• Website: Full URL including https://
• Phone: Include area code
• Industry: Specific sector (e.g., "Financial Services", "Technology")

Extract the information from the email below:"""
        )
        
        # Variant B - Chain of thought
        variant_b = PromptVariant(
            variant_id="chain_of_thought",
            variant_name="Chain of Thought",
            prompt_template="""Let's carefully extract candidate information step by step.

First, identify:
1. WHO is the main candidate being discussed?
2. WHAT role or position are they in/seeking?
3. WHERE are they located?
4. WHICH company are they associated with?
5. WHO referred them (if anyone)?

Then extract:
- Candidate Name: [from step 1]
- Job Title: [from step 2]
- Location: [from step 3]
- Company Name: [from step 4]
- Referrer Name: [from step 5]
- Website: [any mentioned URL]
- Phone: [any phone number]
- Industry: [infer from context]

Analyze the email below:"""
        )
        
        # Variant C - Confidence-based
        variant_c = PromptVariant(
            variant_id="confidence_based",
            variant_name="Confidence Scoring",
            prompt_template="""Extract candidate information with confidence scores.

For each field, provide:
1. The extracted value
2. Confidence level (HIGH/MEDIUM/LOW)
3. Source quote from email

Fields to extract:
- Candidate Name (person being recruited)
- Job Title (their role/position)
- Location (geographical area)
- Company Name (their organization)
- Referrer Name (who referred them)
- Website (company URL)
- Phone (contact number)
- Industry (business sector)

Only use HIGH confidence for explicitly stated information.
Use MEDIUM for reasonable inferences.
Use LOW or "Unknown" for uncertain extractions.

Email to analyze:"""
        )
        
        # Store variants
        self.prompt_variants = {
            "control": control,
            "structured_examples": variant_a,
            "chain_of_thought": variant_b,
            "confidence_based": variant_c
        }
    
    def select_prompt_variant(
        self,
        email_domain: Optional[str] = None,
        force_variant: Optional[str] = None
    ) -> PromptVariant:
        """Select a prompt variant based on testing strategy"""
        if not self.enable_ab_testing or not self.prompt_variants:
            return self.prompt_variants.get("control", None)
        
        if force_variant and force_variant in self.prompt_variants:
            return self.prompt_variants[force_variant]
        
        active_variants = [v for v in self.prompt_variants.values() if v.is_active]
        
        if not active_variants:
            return self.prompt_variants.get("control", None)
        
        # Apply testing strategy
        if self.test_strategy == TestStrategy.RANDOM:
            return random.choice(active_variants)
        
        elif self.test_strategy == TestStrategy.EPSILON_GREEDY:
            # Explore with probability epsilon, exploit otherwise
            if random.random() < self.epsilon:
                return random.choice(active_variants)
            else:
                # Choose best performing variant
                return max(active_variants, key=lambda v: v.average_accuracy)
        
        elif self.test_strategy == TestStrategy.ROUND_ROBIN:
            # Rotate through variants
            least_used = min(active_variants, key=lambda v: v.total_uses)
            return least_used
        
        elif self.test_strategy == TestStrategy.THOMPSON_SAMPLING:
            # Bayesian approach - sample from beta distribution
            best_score = -1
            best_variant = active_variants[0]
            
            for variant in active_variants:
                # Beta distribution parameters
                alpha = variant.successful_extractions + 1
                beta = variant.total_uses - variant.successful_extractions + 1
                
                # Sample from beta distribution
                score = random.betavariate(alpha, beta)
                
                if score > best_score:
                    best_score = score
                    best_variant = variant
            
            return best_variant
        
        return self.prompt_variants.get("control", None)
    
    async def track_extraction(
        self,
        email_domain: str,
        extraction_result: Dict[str, Any],
        processing_time_ms: int,
        prompt_variant_id: Optional[str] = None,
        used_template: bool = False,
        pattern_matches: int = 0
    ) -> ExtractionMetric:
        """Track metrics for an extraction"""
        try:
            # Calculate field confidence scores
            field_scores = self._calculate_field_confidence(extraction_result)
            
            # Create metric
            metric = ExtractionMetric(
                extraction_id=hashlib.md5(
                    f"{email_domain}:{datetime.utcnow().isoformat()}".encode()
                ).hexdigest(),
                email_domain=email_domain,
                field_scores=field_scores,
                overall_confidence=sum(field_scores.values()) / len(field_scores) if field_scores else 0,
                processing_time_ms=processing_time_ms,
                prompt_variant=prompt_variant_id,
                used_template=used_template,
                pattern_matches=pattern_matches
            )
            
            # Add to cache
            self.metrics_cache.append(metric)
            
            # Send to Application Insights if batch is full
            if len(self.metrics_cache) >= self.cache_size:
                await self._flush_metrics()
            
            # Update variant performance if applicable
            if prompt_variant_id and prompt_variant_id in self.prompt_variants:
                variant = self.prompt_variants[prompt_variant_id]
                variant.total_uses += 1
                variant.last_used = datetime.utcnow()
                
                # Update running averages
                variant.average_confidence = (
                    variant.average_confidence * (variant.total_uses - 1) + metric.overall_confidence
                ) / variant.total_uses
                
                variant.average_processing_time = (
                    variant.average_processing_time * (variant.total_uses - 1) + processing_time_ms
                ) / variant.total_uses
            
            return metric
            
        except Exception as e:
            logger.error(f"Failed to track extraction: {e}")
            return None
    
    async def track_correction(
        self,
        extraction_id: str,
        field_corrections: Dict[str, Tuple[Any, Any]],
        prompt_variant_id: Optional[str] = None
    ):
        """Track user corrections to update accuracy metrics"""
        try:
            # Find the original metric
            metric = next((m for m in self.metrics_cache if m.extraction_id == extraction_id), None)
            
            if metric:
                # Update field accuracy
                total_fields = len(metric.field_scores)
                correct_fields = total_fields - len(field_corrections)
                
                for field in metric.field_scores:
                    metric.field_corrections[field] = field in field_corrections
                    metric.field_accuracy[field] = 0.0 if field in field_corrections else 1.0
                
                metric.overall_accuracy = correct_fields / total_fields if total_fields > 0 else 0
            
            # Update variant performance
            if prompt_variant_id and prompt_variant_id in self.prompt_variants:
                variant = self.prompt_variants[prompt_variant_id]
                
                # Update success rate
                if metric and metric.overall_accuracy >= 0.8:  # 80% threshold for success
                    variant.successful_extractions += 1
                
                # Update average accuracy
                variant.average_accuracy = (
                    variant.average_accuracy * (variant.total_uses - 1) + metric.overall_accuracy
                ) / variant.total_uses
                
                # Update field-specific performance
                for field, was_corrected in field_corrections.items():
                    if field not in variant.field_performance:
                        variant.field_performance[field] = 1.0
                    
                    # Exponential moving average for field performance
                    alpha = 0.1  # Learning rate
                    current_accuracy = 0.0 if was_corrected else 1.0
                    variant.field_performance[field] = (
                        alpha * current_accuracy + (1 - alpha) * variant.field_performance[field]
                    )
            
            # Send correction event to Application Insights
            if self.telemetry_client:
                self.telemetry_client.track_event(
                    "ExtractionCorrected",
                    {
                        "extraction_id": extraction_id,
                        "fields_corrected": len(field_corrections),
                        "overall_accuracy": metric.overall_accuracy if metric else 0,
                        "prompt_variant": prompt_variant_id or "unknown"
                    },
                    {
                        "accuracy": metric.overall_accuracy if metric else 0,
                        "confidence": metric.overall_confidence if metric else 0
                    }
                )
            
        except Exception as e:
            logger.error(f"Failed to track correction: {e}")
    
    async def get_field_analytics(
        self,
        field_name: str,
        days_back: int = 30,
        email_domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get analytics for a specific field"""
        try:
            # Get insights from Azure AI Search
            insights = {}
            if self.search_manager:
                insights = await self.search_manager.get_learning_insights(
                    email_domain=email_domain,
                    field_name=field_name,
                    days_back=days_back
                )
            
            # Calculate field-specific metrics from cache
            field_metrics = []
            for metric in self.metrics_cache:
                if field_name in metric.field_scores:
                    if not email_domain or metric.email_domain == email_domain:
                        field_metrics.append({
                            "confidence": metric.field_scores[field_name],
                            "accuracy": metric.field_accuracy.get(field_name, 1.0),
                            "corrected": metric.field_corrections.get(field_name, False)
                        })
            
            # Calculate statistics
            if field_metrics:
                avg_confidence = sum(m["confidence"] for m in field_metrics) / len(field_metrics)
                avg_accuracy = sum(m["accuracy"] for m in field_metrics) / len(field_metrics)
                correction_rate = sum(1 for m in field_metrics if m["corrected"]) / len(field_metrics)
            else:
                avg_confidence = avg_accuracy = correction_rate = 0
            
            # Get variant performance for this field
            variant_performance = {}
            for variant_id, variant in self.prompt_variants.items():
                if field_name in variant.field_performance:
                    variant_performance[variant_id] = {
                        "name": variant.variant_name,
                        "accuracy": variant.field_performance[field_name],
                        "uses": variant.total_uses
                    }
            
            return {
                "field": field_name,
                "period_days": days_back,
                "domain": email_domain,
                "metrics": {
                    "average_confidence": round(avg_confidence, 3),
                    "average_accuracy": round(avg_accuracy, 3),
                    "correction_rate": round(correction_rate, 3),
                    "total_extractions": len(field_metrics)
                },
                "variant_performance": variant_performance,
                "insights": insights.get("insights", []),
                "recommendations": self._generate_field_recommendations(
                    field_name, avg_accuracy, correction_rate
                )
            }
            
        except Exception as e:
            logger.error(f"Failed to get field analytics: {e}")
            return {}
    
    async def get_variant_report(self) -> Dict[str, Any]:
        """Get A/B testing report for all prompt variants"""
        try:
            report = {
                "test_strategy": self.test_strategy.value,
                "epsilon": self.epsilon if self.test_strategy == TestStrategy.EPSILON_GREEDY else None,
                "variants": {},
                "winner": None,
                "recommendations": []
            }
            
            best_variant = None
            best_accuracy = 0
            
            for variant_id, variant in self.prompt_variants.items():
                if variant.total_uses > 0:
                    report["variants"][variant_id] = {
                        "name": variant.variant_name,
                        "is_control": variant.is_control,
                        "total_uses": variant.total_uses,
                        "success_rate": variant.successful_extractions / variant.total_uses if variant.total_uses > 0 else 0,
                        "average_accuracy": round(variant.average_accuracy, 3),
                        "average_confidence": round(variant.average_confidence, 3),
                        "average_processing_time_ms": round(variant.average_processing_time),
                        "field_performance": {
                            k: round(v, 3) for k, v in variant.field_performance.items()
                        },
                        "last_used": variant.last_used.isoformat() if variant.last_used else None
                    }
                    
                    # Track best variant
                    if variant.average_accuracy > best_accuracy and variant.total_uses >= 10:
                        best_accuracy = variant.average_accuracy
                        best_variant = variant_id
            
            # Determine winner if significant difference
            if best_variant:
                control_accuracy = self.prompt_variants["control"].average_accuracy
                if best_accuracy > control_accuracy * 1.1:  # 10% improvement threshold
                    report["winner"] = best_variant
                    report["recommendations"].append(
                        f"Consider making '{best_variant}' the default prompt (10%+ improvement over control)"
                    )
            
            # Statistical significance check
            if len(report["variants"]) >= 2:
                min_uses = min(v["total_uses"] for v in report["variants"].values())
                if min_uses < 30:
                    report["recommendations"].append(
                        f"Need at least {30 - min_uses} more tests for statistical significance"
                    )
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate variant report: {e}")
            return {}
    
    async def optimize_prompts(self, performance_threshold: float = 0.85):
        """Automatically optimize prompts based on performance"""
        try:
            # Deactivate poorly performing variants
            for variant_id, variant in self.prompt_variants.items():
                if not variant.is_control and variant.total_uses >= 50:
                    if variant.average_accuracy < performance_threshold:
                        variant.is_active = False
                        logger.info(f"Deactivated variant {variant_id} due to low performance")
            
            # Reduce exploration rate if we have a clear winner
            if self.test_strategy == TestStrategy.EPSILON_GREEDY:
                best_variant = max(
                    self.prompt_variants.values(),
                    key=lambda v: v.average_accuracy if v.total_uses > 10 else 0
                )
                
                if best_variant.average_accuracy > 0.9 and best_variant.total_uses > 100:
                    self.epsilon = max(0.01, self.epsilon * 0.9)  # Reduce exploration
                    logger.info(f"Reduced epsilon to {self.epsilon} due to high performance")
            
        except Exception as e:
            logger.error(f"Failed to optimize prompts: {e}")
    
    def _calculate_field_confidence(self, extraction_result: Dict[str, Any]) -> Dict[str, float]:
        """Calculate confidence scores for each field"""
        field_scores = {}
        
        for field, value in extraction_result.items():
            if value is None or value == "" or value == "Unknown":
                field_scores[field] = 0.0
            elif field == "website" and not value.startswith("http"):
                field_scores[field] = 0.5  # Low confidence for incomplete URLs
            elif field == "phone" and len(str(value).replace("-", "").replace(" ", "")) < 10:
                field_scores[field] = 0.5  # Low confidence for short phone numbers
            elif field == "location" and "," not in str(value):
                field_scores[field] = 0.7  # Medium confidence for incomplete locations
            else:
                field_scores[field] = 0.9  # High confidence for complete values
        
        return field_scores
    
    def _generate_field_recommendations(
        self,
        field_name: str,
        accuracy: float,
        correction_rate: float
    ) -> List[str]:
        """Generate recommendations for improving field extraction"""
        recommendations = []
        
        if accuracy < 0.6:
            recommendations.append(f"Critical: {field_name} extraction needs immediate attention")
            
            if field_name == "location":
                recommendations.append("Consider adding location parsing rules for city/state format")
            elif field_name == "job_title":
                recommendations.append("Add seniority level detection (Senior, VP, Director, etc.)")
            elif field_name == "company_name":
                recommendations.append("Implement company name normalization and validation")
        
        if correction_rate > 0.3:
            recommendations.append(f"{field_name} has high correction rate - review extraction logic")
        
        if accuracy > 0.9:
            recommendations.append(f"{field_name} extraction performing well - maintain current approach")
        
        return recommendations
    
    async def _flush_metrics(self):
        """Send batched metrics to Application Insights"""
        if not self.telemetry_client or not self.metrics_cache:
            return
        
        try:
            for metric in self.metrics_cache:
                self.telemetry_client.track_event(
                    "ExtractionMetric",
                    {
                        "extraction_id": metric.extraction_id,
                        "email_domain": metric.email_domain,
                        "prompt_variant": metric.prompt_variant or "default",
                        "model_version": metric.model_version,
                        "used_template": str(metric.used_template),
                        "pattern_matches": str(metric.pattern_matches)
                    },
                    {
                        "overall_confidence": metric.overall_confidence,
                        "overall_accuracy": metric.overall_accuracy,
                        "processing_time_ms": metric.processing_time_ms,
                        **{f"field_confidence_{k}": v for k, v in metric.field_scores.items()}
                    }
                )
            
            # Clear cache after sending
            self.metrics_cache = []
            
            logger.info(f"Flushed {len(self.metrics_cache)} metrics to Application Insights")
            
        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")
    
    async def close(self):
        """Clean up and flush remaining metrics"""
        await self._flush_metrics()
        
        if self.telemetry_client:
            self.telemetry_client.flush()
            # Give it time to send
            await asyncio.sleep(2)