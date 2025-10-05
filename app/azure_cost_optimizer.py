"""
Azure Cost Optimizer for GPT-5 Model Tiering
Intelligently selects the most cost-effective model based on email complexity
Integrates with Azure Application Insights for monitoring
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import asyncio
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import metrics
from opentelemetry.metrics import get_meter

logger = logging.getLogger(__name__)

class ModelTier(Enum):
    """GPT-5 model tiers with pricing (per 1M tokens)"""
    NANO = "gpt-5-nano"  # $0.05 input, $0.40 output
    MINI = "gpt-5-mini"  # $0.25 input, $2.00 output  
    FULL = "gpt-5"      # $1.25 input, $10.00 output

@dataclass
class ModelPricing:
    """Pricing information for each model"""
    input_price: float  # Per 1M tokens
    output_price: float  # Per 1M tokens
    cached_input_price: float  # Cached input pricing
    max_context: int  # Maximum context window
    
PRICING = {
    ModelTier.NANO: ModelPricing(0.05, 0.40, 0.005, 400000),
    ModelTier.MINI: ModelPricing(0.25, 2.00, 0.025, 400000),
    ModelTier.FULL: ModelPricing(1.25, 10.00, 0.125, 400000),
}

@dataclass
class EmailComplexity:
    """Email complexity analysis"""
    word_count: int
    has_attachments: bool
    has_tables: bool
    has_multiple_candidates: bool
    language_complexity: float  # 0-1 score
    domain_specificity: float  # 0-1 score
    confidence_required: float  # 0-1 score
    
class AzureCostOptimizer:
    """Optimizes model selection and tracks costs using Azure services"""
    
    def __init__(
        self,
        application_insights_key: Optional[str] = None,
        budget_limit_daily: float = 100.0,
        enable_metrics: bool = True
    ):
        self.app_insights_key = application_insights_key or os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        self.budget_limit = budget_limit_daily
        self.daily_spend = 0.0
        self.metrics_enabled = enable_metrics
        
        # Initialize Azure Monitor if key is provided
        if self.app_insights_key and enable_metrics:
            configure_azure_monitor(
                connection_string=self.app_insights_key,
                enable_live_metrics=True,
            )
            self.meter = get_meter("well-intake-api")
            self._setup_metrics()
        else:
            self.meter = None
            
        # Cache for model performance
        self.model_performance: Dict[ModelTier, Dict] = {
            tier: {"success_rate": 0.95, "avg_latency": 0, "total_calls": 0}
            for tier in ModelTier
        }
        
    def _setup_metrics(self):
        """Setup Azure Application Insights custom metrics"""
        if not self.meter:
            return
            
        # Token usage metrics
        self.token_counter = self.meter.create_counter(
            name="gpt5.tokens.used",
            description="Total tokens used",
            unit="tokens"
        )
        
        # Cost metrics
        self.cost_counter = self.meter.create_counter(
            name="gpt5.cost.total",
            description="Total cost in USD",
            unit="USD"
        )
        
        # Model selection metrics
        self.model_histogram = self.meter.create_histogram(
            name="gpt5.model.selection",
            description="Model tier selection distribution",
            unit="selection"
        )
        
        # Cache hit rate
        self.cache_counter = self.meter.create_counter(
            name="gpt5.cache.hits",
            description="Cache hit count",
            unit="hits"
        )
        
    def analyze_email_complexity(self, email_content: str, attachments: List[Dict] = None) -> EmailComplexity:
        """Analyze email complexity to determine appropriate model tier"""
        
        # Basic metrics
        word_count = len(email_content.split())
        has_attachments = bool(attachments and len(attachments) > 0)
        
        # Check for tables (simple heuristic)
        has_tables = bool(re.search(r'\|.*\|.*\|', email_content))
        
        # Check for multiple candidates
        candidate_patterns = [
            r'\b(?:candidate|applicant|person|individual)\s*#?\d+',
            r'\b(?:first|second|third|another)\s+(?:candidate|applicant)',
            r'\band\s+(?:also|additionally)\s+\w+\s+\w+\s+(?:for|as)',
        ]
        multiple_candidates = sum(1 for p in candidate_patterns if re.search(p, email_content, re.I)) > 1
        
        # Language complexity (based on sentence length and vocabulary)
        sentences = re.split(r'[.!?]+', email_content)
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        language_complexity = min(avg_sentence_length / 30, 1.0)  # Normalize to 0-1
        
        # Domain specificity (check for industry terms)
        domain_terms = [
            'advisor', 'portfolio', 'aum', 'fiduciary', 'compliance', 
            'series', 'cfa', 'cfp', 'finra', 'ria', 'broker-dealer'
        ]
        domain_matches = sum(1 for term in domain_terms if term in email_content.lower())
        domain_specificity = min(domain_matches / 5, 1.0)  # Normalize to 0-1
        
        # Confidence requirement (based on data criticality)
        critical_indicators = ['referral', 'urgent', 'asap', 'immediately', 'high priority']
        confidence_required = 0.5 if any(ind in email_content.lower() for ind in critical_indicators) else 0.3
        
        return EmailComplexity(
            word_count=word_count,
            has_attachments=has_attachments,
            has_tables=has_tables,
            has_multiple_candidates=multiple_candidates,
            language_complexity=language_complexity,
            domain_specificity=domain_specificity,
            confidence_required=confidence_required
        )
    
    def select_model_tier(
        self, 
        complexity: EmailComplexity,
        force_tier: Optional[ModelTier] = None,
        respect_budget: bool = True
    ) -> Tuple[ModelTier, Dict[str, Any]]:
        """Select optimal model tier based on complexity and constraints"""
        
        if force_tier:
            return force_tier, {"reason": "forced", "complexity": asdict(complexity)}
        
        # Calculate complexity score (0-100)
        complexity_score = (
            complexity.word_count / 10 +  # Up to 50 points for length
            (10 if complexity.has_attachments else 0) +
            (10 if complexity.has_tables else 0) +
            (15 if complexity.has_multiple_candidates else 0) +
            complexity.language_complexity * 10 +
            complexity.domain_specificity * 10 +
            complexity.confidence_required * 15
        )
        
        # Determine base tier
        if complexity_score < 30:
            selected_tier = ModelTier.NANO
        elif complexity_score < 60:
            selected_tier = ModelTier.MINI
        else:
            selected_tier = ModelTier.FULL
            
        # Budget check
        if respect_budget and self.daily_spend > self.budget_limit * 0.8:
            # Downgrade if approaching budget limit
            if selected_tier == ModelTier.FULL:
                selected_tier = ModelTier.MINI
            elif selected_tier == ModelTier.MINI:
                selected_tier = ModelTier.NANO
                
        # Performance check - upgrade if model is failing
        if self.model_performance[selected_tier]["success_rate"] < 0.7:
            if selected_tier == ModelTier.NANO:
                selected_tier = ModelTier.MINI
            elif selected_tier == ModelTier.MINI:
                selected_tier = ModelTier.FULL
                
        # Log metric
        if self.meter:
            self.model_histogram.record(
                complexity_score,
                {"model": selected_tier.value}
            )
            
        reasoning = {
            "complexity_score": complexity_score,
            "complexity": asdict(complexity),
            "selected_tier": selected_tier.value,
            "daily_spend": self.daily_spend,
            "budget_remaining": self.budget_limit - self.daily_spend,
            "model_performance": self.model_performance[selected_tier]
        }
        
        logger.info(f"Selected model tier: {selected_tier.value} (score: {complexity_score:.2f})")
        return selected_tier, reasoning
    
    def calculate_cost(
        self,
        model_tier: ModelTier,
        input_tokens: int,
        output_tokens: int,
        cached: bool = False
    ) -> float:
        """Calculate cost for a specific model usage"""
        
        pricing = PRICING[model_tier]
        
        input_cost = (
            (input_tokens / 1_000_000) * 
            (pricing.cached_input_price if cached else pricing.input_price)
        )
        output_cost = (output_tokens / 1_000_000) * pricing.output_price
        
        total_cost = input_cost + output_cost
        
        # Track metrics
        if self.meter:
            self.token_counter.add(
                input_tokens + output_tokens,
                {"model": model_tier.value, "cached": str(cached)}
            )
            self.cost_counter.add(
                total_cost,
                {"model": model_tier.value}
            )
            
        # Update daily spend
        self.daily_spend += total_cost
        
        return total_cost
    
    def record_model_performance(
        self,
        model_tier: ModelTier,
        success: bool,
        latency_ms: float,
        extraction_quality: float = 1.0
    ):
        """Record model performance metrics"""
        
        perf = self.model_performance[model_tier]
        perf["total_calls"] += 1
        
        # Update success rate (moving average)
        alpha = 0.1  # Smoothing factor
        perf["success_rate"] = (1 - alpha) * perf["success_rate"] + alpha * (1.0 if success else 0.0)
        
        # Update average latency
        perf["avg_latency"] = (
            (perf["avg_latency"] * (perf["total_calls"] - 1) + latency_ms) / 
            perf["total_calls"]
        )
        
        # Log to Application Insights
        if self.meter:
            self.meter.create_histogram(
                "gpt5.model.latency",
                "Model latency in milliseconds"
            ).record(latency_ms, {"model": model_tier.value, "success": str(success)})
            
    def get_cost_report(self) -> Dict[str, Any]:
        """Generate cost report with insights"""
        
        return {
            "daily_spend": self.daily_spend,
            "budget_limit": self.budget_limit,
            "budget_utilization": (self.daily_spend / self.budget_limit) * 100,
            "model_performance": {
                tier.value: perf 
                for tier, perf in self.model_performance.items()
            },
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate cost optimization recommendations"""
        
        recommendations = []
        
        # Budget recommendations
        if self.daily_spend > self.budget_limit * 0.9:
            recommendations.append("⚠️ Approaching daily budget limit. Consider increasing cache usage.")
        
        # Performance recommendations
        for tier, perf in self.model_performance.items():
            if perf["success_rate"] < 0.8 and perf["total_calls"] > 10:
                recommendations.append(
                    f"📉 {tier.value} has low success rate ({perf['success_rate']:.1%}). "
                    f"Consider upgrading complex emails to higher tier."
                )
                
        # Latency recommendations  
        high_latency_models = [
            tier.value for tier, perf in self.model_performance.items()
            if perf["avg_latency"] > 3000
        ]
        if high_latency_models:
            recommendations.append(
                f"⏱️ High latency detected for: {', '.join(high_latency_models)}. "
                f"Consider implementing streaming or caching."
            )
            
        if not recommendations:
            recommendations.append("✅ System operating within optimal parameters")
            
        return recommendations
    
    async def optimize_batch_processing(
        self,
        emails: List[Dict[str, Any]]
    ) -> List[Tuple[Dict, ModelTier]]:
        """Optimize model selection for batch processing"""
        
        # Analyze all emails
        complexities = []
        for email in emails:
            complexity = self.analyze_email_complexity(
                email.get("body", ""),
                email.get("attachments", [])
            )
            complexities.append(complexity)
            
        # Group by recommended tier
        email_tiers = []
        for email, complexity in zip(emails, complexities):
            tier, reasoning = self.select_model_tier(complexity)
            email_tiers.append((email, tier))
            
        # Sort by tier to maximize batching efficiency
        email_tiers.sort(key=lambda x: list(ModelTier).index(x[1]))
        
        return email_tiers
    
    def reset_daily_budget(self):
        """Reset daily spending counter (call via cron/timer)"""
        logger.info(f"Daily spend reset. Previous: ${self.daily_spend:.2f}")
        self.daily_spend = 0.0
        
        # Reset model performance metrics
        for tier in self.model_performance:
            self.model_performance[tier]["total_calls"] = 0


# Usage example
if __name__ == "__main__":
    # Initialize optimizer
    optimizer = AzureCostOptimizer(
        budget_limit_daily=50.0,
        enable_metrics=True
    )
    
    # Analyze email
    test_email = """
    Hi Team,
    
    I wanted to introduce you to three exceptional candidates for your wealth management positions:
    
    1. John Smith - Senior Financial Advisor with 15 years experience, CFA, managing $500M AUM
    2. Sarah Johnson - Portfolio Manager, Series 7 & 66, specializing in alternative investments
    3. Michael Brown - Compliance Officer with FINRA expertise
    
    All candidates are available for immediate placement.
    
    Best regards,
    Recruiter
    """
    
    complexity = optimizer.analyze_email_complexity(test_email)
    tier, reasoning = optimizer.select_model_tier(complexity)
    
    print(f"Selected Model: {tier.value}")
    print(f"Reasoning: {json.dumps(reasoning, indent=2)}")
    
    # Calculate cost
    cost = optimizer.calculate_cost(tier, 1000, 500, cached=False)
    print(f"Estimated Cost: ${cost:.4f}")
    
    # Get report
    report = optimizer.get_cost_report()
    print(f"Cost Report: {json.dumps(report, indent=2)}")