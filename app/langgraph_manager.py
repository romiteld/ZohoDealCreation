"""
LangGraph-based email processing manager
Using OpenAI agents with LangGraph orchestration
"""

import os
import json
import logging
import asyncio
from typing import Dict, Optional, Any, List, TypedDict, Annotated
import operator
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from app.models import ExtractedData, CompanyRecord, ContactRecord, DealRecord
from dotenv import load_dotenv

# LangGraph imports
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Send

# Cache imports
from app.redis_cache_manager import get_cache_manager
from app.cache_strategies import get_strategy_manager
from app.business_rules import filter_well_info

# C³ and VoIT imports
from app.cache.c3 import (
    C3Entry, DependencyCertificate, 
    c3_reuse_or_rebuild, update_calibration, 
    generate_cache_key, score
)
from app.cache.redis_io import load_c3_entry, save_c3_entry
from app.orchestrator.voit import voit_controller

# Rate limit handling imports
from app.rate_limit_handler import (
    RateLimitHandler,
    CachedFallbackExtractor,
    with_rate_limit_handling
)

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


class EmailProcessingState(TypedDict):
    """Enhanced state for learning-aware email processing workflow"""
    # Core processing data
    email_content: str
    sender_domain: str
    extraction_result: Optional[Dict[str, Any]]
    company_research: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    final_output: Optional[ExtractedData]
    messages: Annotated[list, add_messages]
    
    # Learning system integration
    learning_hints: Optional[str]  # Historical corrections to guide extraction
    prompt_variant: Optional[str]  # A/B testing variant used
    extraction_confidence: Optional[float]  # Overall confidence score
    field_confidence_scores: Optional[Dict[str, float]]  # Per-field confidence
    pattern_matches: Optional[int]  # Number of similar patterns found
    used_company_template: Optional[bool]  # Whether company template was used
    
    # Performance tracking
    start_time: Optional[float]  # Processing start timestamp
    extraction_time: Optional[float]  # Time taken for extraction
    research_time: Optional[float]  # Time taken for research
    validation_time: Optional[float]  # Time taken for validation
    
    # Error handling and fallbacks
    errors: Optional[List[str]]  # Errors encountered during processing
    fallback_used: Optional[bool]  # Whether fallback extraction was used
    
    # Learning feedback data
    correction_learning_enabled: Optional[bool]  # Whether learning is active
    analytics_tracking_enabled: Optional[bool]  # Whether analytics tracking is active
    
    # Quality metrics
    quality_score: Optional[float]  # Overall validation quality score
    completeness_score: Optional[float]  # Data completeness score
    consistency_score: Optional[float]  # Data consistency score
    validation_flags: Optional[List[str]]  # Validation warnings/flags
    
    # Learning context for feedback
    learning_context: Optional[Dict[str, Any]]  # Context for learning system


class ExtractionOutput(BaseModel):
    """Structured output for extraction step - Steve's 3-record template with financial advisor enhancements"""

    # Company Record fields
    company_name: Optional[str] = Field(default=None, description="Official company name ONLY")
    company_phone: Optional[str] = Field(default=None, description="Company phone number ONLY")
    company_website: Optional[str] = Field(default=None, description="Company website URL ONLY")
    company_source: Optional[str] = Field(default=None, description="How company was sourced (e.g., Conference/Trade Show, Referral)")
    source_detail: Optional[str] = Field(default=None, description="Specific source detail (e.g., FutureProof 2026, referrer name)")
    who_gets_credit: Optional[str] = Field(default=None, description="BD Rep, Affiliate, or Both")
    credit_person_name: Optional[str] = Field(default=None, description="Name of person who gets credit (e.g., Steve Perry)")

    # Contact Record fields
    first_name: Optional[str] = Field(default=None, description="Contact's first name ONLY")
    last_name: Optional[str] = Field(default=None, description="Contact's last name ONLY")
    contact_company_name: Optional[str] = Field(default=None, description="Contact's company name (should match company_name)")
    contact_email: Optional[str] = Field(default=None, description="Contact's email address ONLY")
    contact_phone: Optional[str] = Field(default=None, description="Contact's phone number ONLY")
    contact_city: Optional[str] = Field(default=None, description="Contact's city ONLY")
    contact_state: Optional[str] = Field(default=None, description="Contact's state ONLY")
    contact_source: Optional[str] = Field(default=None, description="Contact source (should match company_source)")

    # Deal Record fields
    deal_source: Optional[str] = Field(default=None, description="Deal source (should match company_source)")
    position_title: Optional[str] = Field(default=None, description="Position they're looking for (job title)")
    position_location: Optional[str] = Field(default=None, description="Location for the position (city, state, or Nationwide)")
    pipeline: Optional[str] = Field(default="Sales Pipeline", description="Pipeline name (ALWAYS use 'Sales Pipeline')")
    estimated_closing_date: Optional[str] = Field(default=None, description="Estimated closing date (YYYY-MM-DD format, typically 2-4 months out)")
    description_of_requirements: Optional[str] = Field(default=None, description="Description of requirements/needs")

    # Financial Advisor specific fields
    aum_managed: Optional[str] = Field(default=None, description="Assets Under Management (e.g., $180M, $1.2B)")
    production_annual: Optional[str] = Field(default=None, description="Annual production/revenue (e.g., $650K, $1.5M)")
    client_count: Optional[str] = Field(default=None, description="Number of clients managed (e.g., 180 clients)")
    licenses_held: Optional[List[str]] = Field(default=None, description="Professional licenses (e.g., Series 7, Series 66, Series 65)")
    designations: Optional[List[str]] = Field(default=None, description="Professional designations (e.g., CFA, CFP, CPWA, ChFC)")
    years_experience: Optional[str] = Field(default=None, description="Years of experience in financial services")
    availability_timeframe: Optional[str] = Field(default=None, description="When available (e.g., Immediately, 30 days notice, Q1 2025)")
    compensation_range: Optional[str] = Field(default=None, description="Desired compensation range (e.g., $425K-$500K, $650K+ total)")
    book_transferable: Optional[str] = Field(default=None, description="Percentage of book transferable (e.g., 85% transferable)")
    specializations: Optional[List[str]] = Field(default=None, description="Areas of specialization (e.g., High-net-worth, Estate planning, Alternative investments)")

    # Legacy fields for backward compatibility
    candidate_name: Optional[str] = Field(default=None, description="DEPRECATED: Use first_name + last_name")
    job_title: Optional[str] = Field(default=None, description="DEPRECATED: Use position_title")
    location: Optional[str] = Field(default=None, description="DEPRECATED: Use contact_city + contact_state")
    company_guess: Optional[str] = Field(default=None, description="DEPRECATED: Use company_name")
    referrer_name: Optional[str] = Field(default=None, description="DEPRECATED: Use credit_person_name")
    referrer_email: Optional[str] = Field(default=None, description="DEPRECATED: Not in Steve's template")
    phone: Optional[str] = Field(default=None, description="DEPRECATED: Use contact_phone")
    email: Optional[str] = Field(default=None, description="DEPRECATED: Use contact_email")
    linkedin_url: Optional[str] = Field(default=None, description="DEPRECATED: Not in Steve's template")
    notes: Optional[str] = Field(default=None, description="DEPRECATED: Use description_of_requirements")


class CompanyResearch(BaseModel):
    """Structured output for company research"""
    company_name: Optional[str] = Field(default=None, description="Official company name")
    company_domain: Optional[str] = Field(default=None, description="Company domain")
    confidence: float = Field(default=0.0, description="Confidence score 0-1")


class EmailProcessingWorkflow:
    def __init__(self, openai_api_key: str = None):
        # Initialize OpenAI/Azure OpenAI client
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_key = os.getenv("AZURE_OPENAI_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
        azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

        if azure_endpoint and azure_key and azure_deployment:
            # Use Azure OpenAI
            base_url = azure_endpoint.rstrip('/') + f"/openai/deployments/{azure_deployment}"
            self.client = AsyncOpenAI(
                api_key=azure_key,
                base_url=base_url,
                default_query={"api-version": azure_api_version}
            )
            self.model_name = azure_deployment  # In Azure, the deployment name is used as model
            logger.info("Azure OpenAI client initialized for LangGraph workflow")
        else:
            # Use OpenAI (non-Azure)
            self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OpenAI API key is required")
            self.client = AsyncOpenAI(api_key=self.api_key)
            # Default to GPT-5-mini if available, else caller may override
            self.model_name = os.getenv("OPENAI_MODEL", "gpt-5-mini")
            logger.info("OpenAI client initialized for LangGraph workflow")

        # Initialize rate limit handler and fallback extractor
        self.rate_limit_handler = RateLimitHandler(
            max_retries=3,
            initial_delay=2.0,
            max_delay=60.0
        )
        self.fallback_extractor = CachedFallbackExtractor()

        # Build the workflow
        self.graph = self._build_workflow()
        logger.info("LangGraph workflow compiled successfully")
    
    def _calculate_field_confidence_scores(self, extraction_result: Dict[str, Any]) -> Dict[str, float]:
        """Calculate confidence scores for each extracted field"""
        field_scores = {}
        
        for field, value in extraction_result.items():
            if value is None or value == "" or value == "Unknown":
                field_scores[field] = 0.0
            elif field == "website" and value and not str(value).startswith("http"):
                field_scores[field] = 0.5  # Low confidence for incomplete URLs
            elif field == "phone" and value and len(str(value).replace("-", "").replace(" ", "").replace("(", "").replace(")", "")) < 10:
                field_scores[field] = 0.6  # Medium confidence for short phone numbers
            elif field == "location" and value and "," not in str(value):
                field_scores[field] = 0.7  # Medium confidence for incomplete locations
            elif field == "email" and value and "@" not in str(value):
                field_scores[field] = 0.3  # Low confidence for malformed emails
            elif field == "linkedin_url" and value and "linkedin.com" not in str(value).lower():
                field_scores[field] = 0.4  # Low confidence for non-LinkedIn URLs
            else:
                field_scores[field] = 0.9  # High confidence for complete values
        
        return field_scores
    
    def _fallback_extraction(self, email_content: str, sender_domain: str) -> Dict[str, Any]:
        """Simple fallback extraction when AI extraction fails"""
        import re
        
        # Basic pattern matching for fallback
        fallback_result = {}
        
        # Try to extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, email_content)
        if emails:
            fallback_result['email'] = emails[0]
        
        # Try to extract phone numbers
        phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, email_content)
        if phones:
            fallback_result['phone'] = ''.join(phones[0]) if isinstance(phones[0], tuple) else phones[0]
        
        # Basic company name from domain
        if sender_domain:
            company_parts = sender_domain.split('.')
            if company_parts:
                fallback_result['company_name'] = company_parts[0].replace('-', ' ').title()
        
        return fallback_result
    
    def _calculate_validation_scores(self, validated_data: Dict[str, Any], extracted: Dict[str, Any], research: Dict[str, Any]) -> Dict[str, float]:
        """Calculate comprehensive validation quality scores"""
        scores = {
            'validation_confidence': 0.0,
            'quality_score': 0.0,
            'completeness_score': 0.0,
            'consistency_score': 0.0,
            'validation_flags': []
        }
        
        # Calculate completeness score
        required_fields = ['candidate_name', 'job_title', 'location', 'company_name']
        completed_required = sum(1 for field in required_fields if validated_data.get(field))
        scores['completeness_score'] = completed_required / len(required_fields)
        
        # Calculate consistency score (how well extraction, research, and validation align)
        consistency_checks = 0
        consistency_passes = 0
        
        # Check email domain consistency
        if validated_data.get('email') and validated_data.get('company_name'):
            email_domain = validated_data['email'].split('@')[1] if '@' in validated_data['email'] else ''
            company_name = validated_data['company_name'].lower()
            consistency_checks += 1
            if any(word in email_domain.lower() for word in company_name.split() if len(word) > 2):
                consistency_passes += 1
        
        # Check research consistency
        if research.get('company_name') and validated_data.get('company_name'):
            consistency_checks += 1
            if research['company_name'].lower() in validated_data['company_name'].lower() or \
               validated_data['company_name'].lower() in research['company_name'].lower():
                consistency_passes += 1
        
        scores['consistency_score'] = consistency_passes / consistency_checks if consistency_checks > 0 else 1.0
        
        # Overall quality score (weighted average)
        scores['quality_score'] = (
            scores['completeness_score'] * 0.4 +
            scores['consistency_score'] * 0.3 +
            (1.0 if not scores['validation_flags'] else 0.8) * 0.3
        )
        
        # Validation flags
        if scores['completeness_score'] < 0.5:
            scores['validation_flags'].append('low_completeness')
        if scores['consistency_score'] < 0.6:
            scores['validation_flags'].append('consistency_issues')
        if not validated_data.get('candidate_name'):
            scores['validation_flags'].append('missing_candidate_name')
        
        return scores
    
    def _prepare_learning_context(self, state: EmailProcessingState, extracted: Dict[str, Any], research: Dict[str, Any], validated: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context data for learning system feedback"""
        import time
        return {
            'email_domain': state.get('sender_domain'),
            'prompt_variant_used': state.get('prompt_variant'),
            'pattern_matches_found': state.get('pattern_matches', 0),
            'company_template_used': state.get('used_company_template', False),
            'extraction_confidence': state.get('extraction_confidence', 0.5),
            'field_confidence_scores': state.get('field_confidence_scores', {}),
            'processing_times': {
                'extraction': state.get('extraction_time', 0),
                'research': state.get('research_time', 0),
                'validation': state.get('validation_time', 0),
                'total': state.get('start_time') and (time.time() - state['start_time'])
            },
            'data_quality': {
                'completeness_score': state.get('completeness_score', 0),
                'consistency_score': state.get('consistency_score', 0),
                'quality_score': state.get('quality_score', 0)
            },
            'error_context': {
                'errors_encountered': state.get('errors', []),
                'fallback_used': state.get('fallback_used', False)
            }
        }
    
    async def _store_processing_feedback(self, result: Dict[str, Any]):
        """Store processing feedback for learning system improvements"""
        try:
            if not result.get('correction_learning_enabled'):
                return
            
            learning_context = result.get('learning_context', {})
            
            # Store processing metrics if analytics are enabled
            if result.get('analytics_tracking_enabled'):
                from app.learning_analytics import LearningAnalytics
                
                analytics = LearningAnalytics(enable_ab_testing=False)  # Just for storage
                await analytics.track_extraction(
                    email_domain=learning_context.get('email_domain', 'unknown'),
                    extraction_result=result.get('extraction_result', {}),
                    processing_time_ms=int(learning_context.get('processing_times', {}).get('total', 0) * 1000),
                    prompt_variant_id=learning_context.get('prompt_variant_used'),
                    used_template=learning_context.get('company_template_used', False),
                    pattern_matches=learning_context.get('pattern_matches_found', 0)
                )
            
        except Exception as e:
            logger.warning(f"Could not store processing feedback: {e}")
    
    async def process_email_with_learning(self, email_body: str, sender_domain: str, learning_hints: str = None) -> Dict[str, Any]:
        """Enhanced email processing with C³ cache and VoIT orchestration."""
        import time
        import hashlib
        
        logger.info(f"Starting learning-enhanced email processing for domain: {sender_domain}")
        
        # Try C³ cache first if enabled
        if os.getenv("FEATURE_C3", "false").lower() == "true":
            cache_mgr = get_cache_manager()
            if cache_mgr and cache_mgr.redis_client:
                # Generate canonical record for C³
                canonical = {
                    "email_body": email_body,
                    "sender_domain": sender_domain,
                    "learning_hints": learning_hints
                }
                
                cache_key = generate_cache_key(canonical, channel="email")
                entry = await load_c3_entry(cache_mgr.redis_client, cache_key)
                
                if entry:
                    # Generate embedding for request
                    hash_val = hashlib.sha256(email_body.encode()).hexdigest()
                    embed = [float(int(hash_val[i:i+2], 16))/255 for i in range(0, min(64, len(hash_val)), 2)]
                    
                    req_context = {
                        "embed": embed,
                        "fields": {"sender_domain": sender_domain},
                        "touched_selectors": []
                    }
                    
                    mode, payload = c3_reuse_or_rebuild(
                        req_context, entry,
                        float(os.getenv("C3_DELTA", "0.01")),
                        int(os.getenv("C3_EPS", "3"))
                    )
                    
                    if mode == "reuse":
                        logger.info("C³ cache hit - returning cached extraction")
                        cached_result = json.loads(entry.artifact.decode())
                        return cached_result
        
        # Initialize learning services
        correction_service = None
        learning_analytics = None
        processing_start = time.time()
        
        try:
            from app.correction_learning import CorrectionLearningService
            from app.learning_analytics import LearningAnalytics
            
            # Initialize services
            correction_service = CorrectionLearningService(None, use_azure_search=True)
            learning_analytics = LearningAnalytics(
                search_manager=correction_service.search_manager,
                enable_ab_testing=True
            )
            
            logger.info("Learning services initialized successfully")
            
        except Exception as e:
            logger.warning(f"Could not initialize learning services: {e}")
        
        # Enhanced initial state with learning tracking
        enhanced_state = {
            # Core workflow data
            'email_content': email_body,
            'sender_domain': sender_domain,
            'learning_hints': learning_hints or '',
            
            # Learning integration
            'correction_learning_enabled': bool(correction_service),
            'analytics_tracking_enabled': bool(learning_analytics),
            'start_time': processing_start,
            'errors': [],
            
            # Initialize all state fields for workflow
            'extraction_result': None,
            'company_research': None,
            'validation_result': None,
            'final_output': None,
            'messages': [],
            'prompt_variant': None,
            'extraction_confidence': None,
            'field_confidence_scores': None,
            'pattern_matches': None,
            'used_company_template': None,
            'extraction_time': None,
            'research_time': None,
            'validation_time': None,
            'fallback_used': None,
            'quality_score': None,
            'completeness_score': None,
            'consistency_score': None,
            'validation_flags': None,
            'learning_context': None
        }
        
        # Run the enhanced workflow
        try:
            result = await self.graph.ainvoke(enhanced_state)
            
            # Calculate total processing time
            total_time = time.time() - processing_start
            
            # Prepare comprehensive learning context
            learning_context = self._prepare_learning_context(
                result, 
                result.get('extraction_result', {}),
                result.get('company_research', {}),
                result.get('validation_result', {})
            )
            
            # Update learning context with final metrics
            learning_context['processing_times']['total'] = total_time
            result['learning_context'] = learning_context
            
            # Store feedback for future improvements
            await self._store_processing_feedback(result)
            
            # Log comprehensive results
            logger.info(f"Enhanced processing complete - Total: {total_time:.2f}s, Quality: {result.get('quality_score', 0):.2f}, Confidence: {result.get('extraction_confidence', 0):.2f}")
            
            # Apply VoIT orchestration if enabled
            if os.getenv("FEATURE_VOIT", "false").lower() == "true":
                artifact_ctx = {
                    "spans": [
                        {
                            "id": "extraction",
                            "quality": result.get('extraction_confidence', 0.5),
                            "cached_text": json.dumps(result.get('extraction_result', {})),
                            "ctx": {
                                "retrieval_dispersion": 0.2,
                                "rule_conflicts": len(result.get('validation_flags', [])) * 0.1,
                                "c3_margin": 0.3,
                                "needs_fact_check": bool(result.get('company_research'))
                            }
                        }
                    ]
                }
                voit_result = voit_controller(artifact_ctx)
                logger.info(f"VoIT orchestration applied: {voit_result.get('total_quality', 0):.2f}")
            
            # Save to C³ cache if enabled
            if os.getenv("FEATURE_C3", "false").lower() == "true":
                cache_mgr = get_cache_manager()
                if cache_mgr and cache_mgr.redis_client:
                    # Generate canonical record
                    canonical = {
                        "email_body": email_body,
                        "sender_domain": sender_domain,
                        "learning_hints": learning_hints
                    }
                    cache_key = generate_cache_key(canonical, channel="email")
                    
                    # Generate embedding
                    hash_val = hashlib.sha256(email_body.encode()).hexdigest()
                    embed = [float(int(hash_val[i:i+2], 16))/255 for i in range(0, min(64, len(hash_val)), 2)]
                    
                    # Create new C³ entry
                    new_entry = C3Entry(
                        artifact=json.dumps(result).encode(),
                        dc=DependencyCertificate(spans={}, invariants={}),
                        probes={},
                        calib_scores=[],
                        tau_delta=1e9,
                        meta={
                            "embed": embed,
                            "fields": {"sender_domain": sender_domain},
                            "created_at": time.time(),
                            "template_version": "v1"
                        }
                    )
                    await save_c3_entry(cache_mgr.redis_client, cache_key, new_entry)
                    logger.info(f"Saved result to C³ cache: {cache_key}")
            
            return {
                'final_output': result.get('final_output') or ExtractedData(),
                'processing_metrics': {
                    'total_time_seconds': total_time,
                    'extraction_confidence': result.get('extraction_confidence', 0.5),
                    'quality_score': result.get('quality_score', 0.0),
                    'completeness_score': result.get('completeness_score', 0.0),
                    'pattern_matches': result.get('pattern_matches', 0),
                    'used_template': result.get('used_company_template', False),
                    'prompt_variant': result.get('prompt_variant'),
                    'errors_count': len(result.get('errors', [])),
                    'fallback_used': result.get('fallback_used', False)
                },
                'learning_context': learning_context,
                'raw_result': result
            }
            
        except Exception as e:
            logger.error(f"Enhanced workflow processing failed: {e}")
            
            # Return fallback result with error context
            fallback_result = ExtractedData()
            total_time = time.time() - processing_start
            
            return {
                'final_output': fallback_result,
                'processing_metrics': {
                    'total_time_seconds': total_time,
                    'extraction_confidence': 0.1,
                    'quality_score': 0.0,
                    'completeness_score': 0.0,
                    'pattern_matches': 0,
                    'used_template': False,
                    'prompt_variant': None,
                    'errors_count': 1,
                    'fallback_used': True,
                    'processing_error': str(e)
                },
                'learning_context': {
                    'email_domain': sender_domain,
                    'processing_error': str(e),
                    'processing_times': {'total': total_time}
                },
                'raw_result': None
            }
    
    async def get_learning_insights(self, email_domain: str = None) -> Dict[str, Any]:
        """Get learning insights and analytics for the workflow"""
        try:
            from app.learning_analytics import LearningAnalytics
            from app.correction_learning import CorrectionLearningService
            
            # Initialize services
            correction_service = CorrectionLearningService(None, use_azure_search=True)
            learning_analytics = LearningAnalytics(
                search_manager=correction_service.search_manager,
                enable_ab_testing=True
            )
            
            insights = {
                'prompt_variants': {},
                'field_analytics': {},
                'domain_patterns': {},
                'recommendations': []
            }
            
            # Get A/B testing report
            variant_report = await learning_analytics.get_variant_report()
            insights['prompt_variants'] = variant_report
            
            # Get field-specific analytics
            important_fields = ['candidate_name', 'job_title', 'location', 'company_name', 'email', 'phone']
            for field in important_fields:
                field_analytics = await learning_analytics.get_field_analytics(
                    field_name=field,
                    email_domain=email_domain,
                    days_back=30
                )
                if field_analytics:
                    insights['field_analytics'][field] = field_analytics
            
            # Get domain-specific patterns if available
            if email_domain and correction_service:
                domain_corrections = await correction_service.get_domain_corrections(email_domain, limit=5)
                common_patterns = await correction_service.get_common_patterns(email_domain=email_domain)
                
                insights['domain_patterns'] = {
                    'recent_corrections': len(domain_corrections),
                    'common_patterns': len(common_patterns),
                    'patterns': common_patterns[:3]  # Top 3 patterns
                }
            
            # Generate recommendations
            if variant_report.get('winner'):
                insights['recommendations'].append(f"Consider switching to prompt variant '{variant_report['winner']}'")
            
            poor_fields = [field for field, analytics in insights['field_analytics'].items() 
                          if analytics.get('metrics', {}).get('average_accuracy', 1.0) < 0.7]
            if poor_fields:
                insights['recommendations'].append(f"Focus on improving extraction for: {', '.join(poor_fields)}")
            
            return insights
            
        except Exception as e:
            logger.error(f"Could not get learning insights: {e}")
            return {'error': str(e)}
    
    async def create_correction_feedback(
        self, 
        email_domain: str,
        original_extraction: Dict[str, Any],
        user_corrections: Dict[str, Any],
        email_snippet: str = None
    ) -> Dict[str, Any]:
        """Create feedback from user corrections to improve future extractions"""
        try:
            from app.correction_learning import CorrectionLearningService, FeedbackLoop
            
            # Initialize correction service
            correction_service = CorrectionLearningService(None, use_azure_search=True)
            feedback_loop = FeedbackLoop(correction_service)
            
            # Prepare email data structure
            email_data = {
                'sender_email': f'user@{email_domain}',
                'body': email_snippet or ''
            }
            
            # Process the feedback
            feedback_result = await feedback_loop.process_user_feedback(
                email_data=email_data,
                ai_extraction=original_extraction,
                user_edits=user_corrections
            )
            
            logger.info(f"Correction feedback processed: {feedback_result['fields_corrected']} fields corrected out of {feedback_result['total_fields']}")
            
            # Return comprehensive feedback analysis
            return {
                'feedback_stored': feedback_result['learning_stored'],
                'corrections_analysis': {
                    'total_fields': feedback_result['total_fields'],
                    'fields_corrected': feedback_result['fields_corrected'],
                    'accuracy_rate': 1.0 - (feedback_result['fields_corrected'] / max(feedback_result['total_fields'], 1)),
                    'corrections': feedback_result['corrections']
                },
                'learning_impact': {
                    'will_improve_future_extractions': feedback_result['fields_corrected'] > 0,
                    'domain_patterns_updated': True,
                    'prompt_enhancement_available': bool(correction_service.search_manager)
                },
                'recommendations': self._generate_correction_recommendations(feedback_result['corrections'])
            }
            
        except Exception as e:
            logger.error(f"Could not create correction feedback: {e}")
            return {
                'error': str(e),
                'feedback_stored': False
            }
    
    def _generate_correction_recommendations(self, corrections: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on user corrections"""
        recommendations = []
        
        correction_types = {}
        for field, correction_info in corrections.items():
            change_type = correction_info.get('change_type', 'unknown')
            if change_type not in correction_types:
                correction_types[change_type] = []
            correction_types[change_type].append(field)
        
        # Generate specific recommendations
        if 'added_missing' in correction_types:
            recommendations.append(f"Consider improving extraction prompts for: {', '.join(correction_types['added_missing'])}")
        
        if 'value_change' in correction_types:
            recommendations.append(f"Review extraction accuracy for: {', '.join(correction_types['value_change'])}")
        
        if 'case_correction' in correction_types:
            recommendations.append("Consider adding case normalization for name fields")
        
        if len(corrections) > 3:
            recommendations.append("High correction rate - consider domain-specific prompt tuning")
        
        return recommendations
    
    async def optimize_workflow_performance(self) -> Dict[str, Any]:
        """Analyze and optimize workflow performance based on learning data"""
        try:
            from app.learning_analytics import LearningAnalytics
            from app.correction_learning import CorrectionLearningService
            
            # Initialize services
            correction_service = CorrectionLearningService(None, use_azure_search=True)
            learning_analytics = LearningAnalytics(
                search_manager=correction_service.search_manager,
                enable_ab_testing=True
            )
            
            optimization_results = {
                'prompt_optimization': {},
                'workflow_adjustments': {},
                'performance_improvements': [],
                'recommendations': []
            }
            
            # Optimize prompts based on performance
            await learning_analytics.optimize_prompts(performance_threshold=0.85)
            
            # Get variant performance report
            variant_report = await learning_analytics.get_variant_report()
            optimization_results['prompt_optimization'] = variant_report
            
            # Analyze workflow performance patterns
            workflow_recommendations = []
            
            # Check if we should adjust extraction strategy
            if variant_report.get('winner'):
                workflow_recommendations.append({
                    'type': 'prompt_variant',
                    'action': f"Switch to variant '{variant_report['winner']}' for improved performance",
                    'expected_improvement': '10-15% accuracy increase'
                })
            
            # Analyze error patterns to suggest workflow improvements
            if correction_service:
                try:
                    # Get recent correction patterns across all domains
                    recent_patterns = await correction_service.get_common_patterns(min_frequency=3)
                    
                    if recent_patterns:
                        common_issues = {}
                        for pattern in recent_patterns:
                            field = pattern.get('field_name')
                            if field not in common_issues:
                                common_issues[field] = 0
                            common_issues[field] += pattern.get('frequency', 0)
                        
                        # Suggest workflow adjustments for problematic fields
                        for field, frequency in common_issues.items():
                            if frequency > 5:  # High error frequency
                                workflow_recommendations.append({
                                    'type': 'extraction_enhancement',
                                    'field': field,
                                    'action': f"Add specialized extraction logic for {field}",
                                    'frequency': frequency
                                })
                except Exception as e:
                    logger.warning(f"Could not analyze correction patterns: {e}")
            
            optimization_results['workflow_adjustments'] = {
                'recommendations': workflow_recommendations,
                'total_improvements': len(workflow_recommendations)
            }
            
            # Performance improvement suggestions
            performance_improvements = [
                "Enable Azure AI Search for better pattern matching",
                "Use company templates for known domains",
                "Implement field-specific validation rules",
                "Add confidence-based routing for extractions"
            ]
            
            optimization_results['performance_improvements'] = performance_improvements
            
            # Overall recommendations
            recommendations = []
            if len(workflow_recommendations) > 0:
                recommendations.append(f"Implement {len(workflow_recommendations)} workflow optimizations")
            if variant_report.get('winner'):
                recommendations.append("Deploy winning prompt variant to production")
            recommendations.append("Continue A/B testing for ongoing improvements")
            
            optimization_results['recommendations'] = recommendations
            
            logger.info(f"Workflow optimization complete: {len(workflow_recommendations)} improvements identified")
            
            return optimization_results
            
        except Exception as e:
            logger.error(f"Could not optimize workflow performance: {e}")
            return {
                'error': str(e),
                'optimization_performed': False
            }
    
    async def get_workflow_health_metrics(self) -> Dict[str, Any]:
        """Get comprehensive health metrics for the workflow"""
        try:
            metrics = {
                'learning_system_status': {},
                'extraction_performance': {},
                'error_rates': {},
                'optimization_opportunities': []
            }
            
            # Check learning system status
            try:
                from app.correction_learning import CorrectionLearningService
                from app.learning_analytics import LearningAnalytics
                
                correction_service = CorrectionLearningService(None, use_azure_search=True)
                learning_analytics = LearningAnalytics(
                    search_manager=correction_service.search_manager,
                    enable_ab_testing=True
                )
                
                metrics['learning_system_status'] = {
                    'correction_learning_active': bool(correction_service),
                    'azure_search_available': bool(correction_service and correction_service.search_manager),
                    'analytics_tracking_active': bool(learning_analytics),
                    'ab_testing_enabled': learning_analytics.enable_ab_testing if learning_analytics else False
                }
                
                # Get recent performance metrics
                if learning_analytics:
                    field_metrics = {}
                    for field in ['candidate_name', 'job_title', 'location', 'company_name']:
                        field_analytics = await learning_analytics.get_field_analytics(field, days_back=7)
                        if field_analytics and field_analytics.get('metrics'):
                            field_metrics[field] = field_analytics['metrics']
                    
                    metrics['extraction_performance'] = field_metrics
                
            except Exception as e:
                metrics['learning_system_status']['error'] = str(e)
            
            # Analyze error patterns
            error_analysis = {
                'total_errors_tracked': 0,
                'common_error_types': [],
                'fallback_usage_rate': 0.0
            }
            
            # Add optimization opportunities
            opportunities = []
            if not metrics['learning_system_status'].get('azure_search_available'):
                opportunities.append("Enable Azure AI Search for improved pattern matching")
            
            if not metrics['learning_system_status'].get('ab_testing_enabled'):
                opportunities.append("Enable A/B testing for prompt optimization")
            
            # Check extraction performance for optimization opportunities
            perf_metrics = metrics.get('extraction_performance', {})
            poor_performing_fields = [
                field for field, field_metrics in perf_metrics.items()
                if field_metrics.get('average_accuracy', 1.0) < 0.8
            ]
            
            if poor_performing_fields:
                opportunities.append(f"Improve extraction accuracy for: {', '.join(poor_performing_fields)}")
            
            metrics['error_rates'] = error_analysis
            metrics['optimization_opportunities'] = opportunities
            
            return metrics
            
        except Exception as e:
            logger.error(f"Could not get workflow health metrics: {e}")
            return {
                'error': str(e),
                'metrics_available': False
            }
    
    def preprocess_forwarded_email(self, email_content: str) -> tuple[str, bool, Optional[str]]:
        """
        Preprocess email to identify forwarded content and extract forwarder info
        Returns: (processed_content, is_forwarded, forwarder_name)
        """
        import re
        
        # Log the first 500 chars to debug
        logger.info(f"Email content preview (first 500 chars): {email_content[:500]}")
        
        # Common forwarding patterns - more comprehensive list
        forward_patterns = [
            r'-----\s*Original Message\s*-----',
            r'---------- Forwarded message ---------',
            r'Begin forwarded message:',
            r'From:.*\nSent:.*\nTo:.*\nSubject:',
            r'From:.*\nDate:.*\nSubject:',  # Simplified pattern
            r'On .+ wrote:',
            r'> From:.*\n> Date:.*\n> Subject:',
            r'_+\s*\nFrom:',  # Underline separator before From
            r'\*From:\*',  # Bold From: in markdown
            r'From:\s+\S+@\S+',  # Simple From: with email
        ]
        
        is_forwarded = False
        forwarder_name = None
        
        # Check if email is forwarded
        for pattern in forward_patterns:
            match = re.search(pattern, email_content, re.IGNORECASE | re.MULTILINE)
            if match:
                is_forwarded = True
                logger.info(f"Detected forwarded email with pattern: {pattern}")
                logger.info(f"Match found at position {match.start()}: {match.group()[:100]}")
                break
        
        # If forwarded, try to identify the forwarder from the top of the email
        if is_forwarded:
            # Look for sender info at the beginning before the forward marker
            lines = email_content.split('\n')[:10]  # Check first 10 lines
            for line in lines:
                # Look for patterns like "From: Name <email>" or just names before the forward
                from_match = re.match(r'^From:\s*([^<\n]+)', line, re.IGNORECASE)
                if from_match:
                    potential_name = from_match.group(1).strip()
                    # Clean up the name (remove email if present)
                    potential_name = re.sub(r'\s*<.*>', '', potential_name).strip()
                    if potential_name and not '@' in potential_name:
                        forwarder_name = potential_name
                        logger.info(f"Identified forwarder: {forwarder_name}")
                        break
        
        # Add clear markers to help AI understand structure
        if is_forwarded:
            processed_content = f"[FORWARDED EMAIL DETECTED]\n[FORWARDER: {forwarder_name or 'Unknown'}]\n\n{email_content}"
        else:
            processed_content = email_content
        
        return processed_content, is_forwarded, forwarder_name
    
    async def extract_information(self, state: EmailProcessingState) -> Dict:
        """First node: Extract key information from email with learning enhancements"""
        logger.info("---EXTRACTION AGENT---")
        
        email_content = state['email_content']
        sender_domain = state['sender_domain']
        
        # Check if LangExtract is enabled via configuration
        from app.config_manager import get_extraction_config
        extraction_config = get_extraction_config()
        use_langextract = extraction_config.use_langextract
        
        # Preprocess for forwarded emails
        processed_content, is_forwarded, forwarder_name = self.preprocess_forwarded_email(email_content)
        if is_forwarded:
            logger.info(f"Processing forwarded email. Forwarder: {forwarder_name}")
            # Use processed content for extraction
            email_content = processed_content
        
        # Try LangExtract first if enabled
        if use_langextract:
            try:
                from app.langextract_email_extractor import get_langextract_extractor
                
                logger.info("Using LangExtract for structured data extraction")
                langextract_extractor = get_langextract_extractor()
                
                extracted_data, metadata = await langextract_extractor.extract_from_email(
                    email_content=email_content,
                    sender_domain=sender_domain,
                    use_cache=extraction_config.langextract_cache_enabled,
                    enable_visualization=extraction_config.langextract_visualization
                )
                
                # Convert ExtractedData to extraction result format
                extraction_result = {
                    "candidate_name": extracted_data.candidate_name,
                    "job_title": extracted_data.job_title,
                    "location": extracted_data.location,
                    "company_name": extracted_data.company_name,
                    "referrer_name": extracted_data.referrer_name,
                    "referrer_email": extracted_data.referrer_email,
                    "email": extracted_data.email,
                    "phone": extracted_data.phone,
                    "linkedin_url": extracted_data.linkedin_url,
                    "website": extracted_data.website,
                    "industry": extracted_data.industry,
                    "notes": extracted_data.notes
                }
                
                logger.info(f"LangExtract extraction completed with {metadata.get('total_extractions', 0)} fields")
                
                return {
                    "extraction_result": extraction_result,
                    "messages": [{"role": "assistant", "content": f"LangExtract extraction: {extraction_result}"}],
                    "langextract_metadata": metadata
                }
                
            except ImportError:
                logger.warning("LangExtract not available, falling back to OpenAI extraction")
            except Exception as e:
                logger.warning(f"LangExtract extraction failed: {e}, falling back to OpenAI extraction")
        
        # Continue with original OpenAI-based extraction
        
        # Initialize learning services for enhanced extraction
        correction_service = None
        learning_analytics = None
        prompt_variant = None
        enhanced_prompt = None
        enhancement_used = False
        
        try:
            from app.correction_learning import CorrectionLearningService
            from app.learning_analytics import LearningAnalytics
            
            # Initialize correction service with Azure AI Search
            correction_service = CorrectionLearningService(None, use_azure_search=True)
            
            # Initialize learning analytics and select prompt variant
            learning_analytics = LearningAnalytics(
                search_manager=correction_service.search_manager,
                enable_ab_testing=True
            )
            
            # Select prompt variant for A/B testing
            prompt_variant = learning_analytics.select_prompt_variant(email_domain=sender_domain)
            
            # Get enhanced prompt with historical corrections
            base_prompt = prompt_variant.prompt_template if prompt_variant else ""
            enhanced_prompt = await correction_service.generate_enhanced_prompt(
                base_prompt=base_prompt,
                email_domain=sender_domain,
                email_content=email_content[:1000]
            )
            
            # Track if enhancement was successfully applied
            enhancement_used = bool(enhanced_prompt and enhanced_prompt != base_prompt)
            
            logger.info(f"Using prompt variant: {prompt_variant.variant_name if prompt_variant else 'default'}")
            logger.info(f"Prompt enhancement status: {'applied' if enhancement_used else 'no enhancements available'}")
            
        except Exception as e:
            logger.warning(f"Could not initialize learning services: {e}")
            enhanced_prompt = None
            enhancement_used = False
        
        # Check cache first
        try:
            cache_manager = await get_cache_manager()
            cached_result = await cache_manager.get_cached_extraction(
                email_content, 
                extraction_type="full"
            )
            
            if cached_result:
                # Use cached result
                extraction_result = cached_result.get("result", {})
                logger.info(f"Using CACHED extraction: {extraction_result}")
                
                return {
                    "extraction_result": extraction_result,
                    "messages": [{"role": "assistant", "content": f"Cached extraction: {extraction_result}"}]
                }
        except Exception as e:
            logger.warning(f"Cache check failed, proceeding without cache: {e}")
        
        # Get learning hints if available
        learning_hints = state.get('learning_hints', '')
        
        # Use enhanced prompt if available, otherwise fall back to default
        if enhanced_prompt:
            system_prompt = enhanced_prompt
            logger.info(f"Using enhanced prompt with historical corrections for domain: {sender_domain}")
        else:
            # Default system prompt
            system_prompt = f"""You are a Senior Data Analyst specializing in recruitment email analysis with expertise in financial advisor placements.
            Extract key recruitment details into THREE SEPARATE RECORD TYPES following Steve's template structure.

            YOUR TASK: Extract data into Company Record, Contact Record, and Deal Record fields:

            === COMPANY RECORD FIELDS ===
            ⚠️ CRITICAL: These fields are for the CANDIDATE'S EMPLOYER, NOT The Well!
            - company_name: The company where the CANDIDATE/CLIENT works
              • Extract from THEIR email domain (e.g., roy.janse@mariner.com → "Mariner")
              • NEVER use "The Well Recruiting Solutions" here
              • If candidate email is steve@example.com → company_name: "Example"
            - company_phone: The CANDIDATE'S company phone (NOT The Well's phone)
            - company_website: The CANDIDATE'S company website (e.g., mariner.com → "https://mariner.com")
            - company_source: How sourced (e.g., "Conference/Trade Show", "Referral", "Email Inbound")
            - source_detail: Specific detail (e.g., "FutureProof 2026", referrer name)
            - who_gets_credit: "BD Rep", "Affiliate", or "Both"
            - credit_person_name: Name of person who gets credit (e.g., "Steve Perry")

            === CONTACT RECORD FIELDS ===
            - first_name: Contact's first name ONLY (e.g., "Troy")
            - last_name: Contact's last name ONLY (e.g., "Tomczak")
            - contact_company_name: Same as company_name
            - contact_email: Contact's email address ONLY
            - contact_phone: Contact's phone number ONLY
            - contact_city: Contact's city ONLY (e.g., "Atlanta")
            - contact_state: Contact's state ONLY (e.g., "GA")
            - contact_source: Same as company_source

            === DEAL RECORD FIELDS ===
            - deal_source: Same as company_source
            - position_title: Job position sought (e.g., "Advisors", "Sales Leader")
            - position_location: Position location (e.g., "Nationwide", "Newport Beach, CA")
            - pipeline: ALWAYS use "Sales Pipeline" (this is the only pipeline)
            - estimated_closing_date: Estimate 2-4 months out (YYYY-MM-DD format)
            - description_of_requirements: Brief description of needs

            === FINANCIAL ADVISOR SPECIFIC FIELDS ===
            CRITICAL: Extract these financial metrics when dealing with advisor/wealth manager candidates:
            - aum_managed: Assets Under Management (e.g., "$180M", "$1.2B", "$350 million")
            - production_annual: Annual production/revenue (e.g., "$650K", "$1.5M production", "$425K base + bonus")
            - client_count: Number of clients (e.g., "180 clients", "250 households")
            - licenses_held: Professional licenses as LIST (e.g., ["Series 7", "Series 66", "Series 65", "Insurance"])
            - designations: Professional certifications as LIST (e.g., ["CFA", "CFP", "CPWA", "ChFC"])
            - years_experience: Years in financial services (e.g., "15 years", "10+ years")
            - availability_timeframe: When available (e.g., "Immediately", "30 days notice", "Q1 2025")
            - compensation_range: Desired compensation (e.g., "$425K-$500K", "$650K+ total", "$380K")
            - book_transferable: Percentage of book transferable (e.g., "85% transferable", "90% portable")
            - specializations: Areas of expertise as LIST (e.g., ["High-net-worth", "Estate planning", "Alternative investments", "401k plans"])

            SOURCE DETERMINATION RULES:
            - If email mentions referrer/forwarded → "Referral" + referrer name in source_detail
            - If from conference/event → "Conference/Trade Show" + event name in source_detail
            - If direct inquiry → "Email Inbound" + "Direct email contact" in source_detail
            - If Calendly meeting → "Website Inbound" + "Calendly scheduling" in source_detail

            DEAL NAME FORMATTING (for validation):
            Format should be: "[Position] ([Location]) - [Company]"
            Examples:
            - "Advisors (Nationwide) - Capital Investment Advisors"
            - "Sales Leader (US Remote) - Hoxton Wealth USA"
            - "Assistant (Nashville) - AJ Advisors"

            CALENDLY EMAIL SPECIAL RULES:
            - "Invitee:" → first_name + last_name
            - "Invitee Email:" → contact_email
            - Meeting title → position_title
            - Questions about recruiting goals → description_of_requirements
            - Meeting organizer → credit_person_name

            FORWARDED EMAIL RULES:
            - Forwarder = referrer (credit_person_name)
            - Original message = candidate info
            - Source = "Referral"

            CRITICAL EXTRACTION RULES:
            - Extract ONLY specific values, NOT entire sentences
            - If unclear, use "Unknown" rather than null
            - Separate names into first_name and last_name properly
            - Ensure consistency across all three record types (same company_name, source, etc.)
            - Location fields: extract city and state separately when possible
            - COMPANY NAME: Extract from CANDIDATE'S email domain (e.g., roy.janse@mariner.com → "Mariner")
            - DO NOT use sender's company (The Well) as the candidate's company
            
            {learning_hints}
            
            Be accurate but extract ONLY the specific values, not entire paragraphs.
            Return "Unknown" for unclear fields rather than null."""
        
        user_prompt = f"""Analyze this recruitment email and extract the key details:

        EMAIL CONTENT:
        {state['email_content']}

        ⚠️ CRITICAL EXTRACTION RULES - READ CAREFULLY:
        1. If this is a forwarded email, extract candidate info from the ORIGINAL/FORWARDED message
        2. COMPANY FIELDS = CANDIDATE'S EMPLOYER INFORMATION:
           - If candidate email is roy.janse@mariner.com → company_name: "Mariner" (NOT "The Well")
           - company_phone = Mariner's phone number (NOT The Well's phone)
           - company_website = "https://mariner.com" (NOT The Well's website)
        3. NEVER use "The Well Recruiting Solutions" for company_name - that's the RECRUITER, not the CANDIDATE
        4. The Well = RECRUITER/SENDER. The company fields are for where the CANDIDATE works!

        Extract and return the information in the required JSON format."""
        
        try:
            # Get the schema and ensure it meets OpenAI's strict requirements
            schema = ExtractionOutput.model_json_schema()
            schema["additionalProperties"] = False

            # OpenAI strict mode requires all properties to be in required array
            if "properties" in schema:
                schema["required"] = list(schema["properties"].keys())
                # Ensure nested objects also have additionalProperties: false
                for prop_name, prop_value in schema["properties"].items():
                    if isinstance(prop_value, dict) and prop_value.get("type") == "object":
                        prop_value["additionalProperties"] = False

            # Define the API call as a separate function for retry handling
            async def make_openai_call():
                return await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "extraction_output",
                            "schema": schema,
                            "strict": True
                        }
                    }
                )

            # Define fallback function that uses pattern matching
            async def fallback_extraction():
                logger.info("Using fallback extraction due to API unavailability")
                fallback_result = await self.fallback_extractor.extract_from_email(
                    state['email_content'],
                    sender_domain
                )
                # Return a mock response object that mimics OpenAI response structure
                class MockResponse:
                    class Choice:
                        class Message:
                            def __init__(self, content):
                                self.content = content
                        def __init__(self, content):
                            self.message = self.Message(content)
                    def __init__(self, content):
                        self.choices = [self.Choice(json.dumps(fallback_result))]
                return MockResponse(fallback_result)

            # Try API call with retry and fallback
            try:
                response = await self.rate_limit_handler.handle_with_retry(
                    make_openai_call,
                    fallback_func=fallback_extraction
                )
            except Exception as e:
                logger.error(f"All extraction attempts failed: {e}")
                # Last resort: use basic fallback
                response = await fallback_extraction()

            result = json.loads(response.choices[0].message.content)
            
            # Post-process to ensure we only have clean, short values
            def clean_field(value, field_name=None, max_length=100):
                """Clean and truncate field values to prevent entire email content"""
                if not value or value == "Unknown" or value == "null" or value == "None":
                    return None
                    
                # Convert to string and strip
                value = str(value).strip()
                
                # Special handling for specific fields
                if field_name == 'job_title':
                    # Common patterns in job titles from Calendly
                    if 'Recruiting Consult' in value:
                        return 'Recruiting Consultant'
                    # Remove everything after first newline
                    if '\n' in value:
                        value = value.split('\n')[0].strip()
                    # Remove "Invitee:" prefix if present
                    if 'Invitee:' in value:
                        value = value.split('Invitee:')[0].strip()
                        
                elif field_name == 'candidate_name':
                    # Extract just the name, not "Roy Janse Invitee Email: ..."
                    if 'Invitee Email:' in value:
                        value = value.split('Invitee Email:')[0].strip()
                    # Remove everything after first newline
                    if '\n' in value:
                        value = value.split('\n')[0].strip()
                    # Clean up "Invitee:" prefix
                    if value.startswith('Invitee:'):
                        value = value.replace('Invitee:', '').strip()
                        
                elif field_name in ['email', 'referrer_email']:
                    # Extract just the email address
                    import re
                    # First check for Calendly pattern "Invitee Email: email@domain.com"
                    if 'Invitee Email:' in value:
                        # Extract email after "Invitee Email:"
                        parts = value.split('Invitee Email:')
                        if len(parts) > 1:
                            email_part = parts[1].strip()
                            # Get just the email address from the remaining text
                            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_part)
                            if email_match:
                                return email_match.group(0)
                    # Standard email extraction
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', value)
                    if email_match:
                        return email_match.group(0)
                        
                elif field_name == 'phone':
                    # Extract just the phone number
                    import re
                    # First check for Calendly pattern "Phone +1 xxx-xxx-xxxx" or "Phone: +1..."
                    if 'Phone' in value:
                        # Extract phone after "Phone" or "Phone:"
                        parts = re.split(r'Phone:?\s*', value)
                        if len(parts) > 1:
                            phone_part = parts[1].strip()
                            # Get just the phone number from the remaining text
                            phone_match = re.search(r'[\+\d\s\-\(\)\.]+', phone_part)
                            if phone_match:
                                phone = phone_match.group(0).strip()
                                # Ensure it's at least 10 digits
                                digits = re.sub(r'\D', '', phone)
                                if len(digits) >= 10:
                                    return phone[:30]
                    # Standard phone extraction
                    phone_match = re.search(r'[\d\s\-\(\)\+\.]+', value)
                    if phone_match:
                        phone = phone_match.group(0).strip()
                        # Ensure it's at least 10 digits
                        digits = re.sub(r'\D', '', phone)
                        if len(digits) >= 10:
                            return phone[:30]
                
                # General cleanup for all fields
                # If it contains multiple newlines or is too long, it's probably the whole email
                if value.count('\n') > 2 or len(value) > max_length:
                    # Try to extract just the first relevant part
                    lines = value.split('\n')
                    first_line = lines[0].strip()
                    
                    # Common patterns to extract from
                    if ':' in first_line and len(first_line.split(':')[0]) < 20:
                        # It's likely a label:value format
                        return first_line.split(':', 1)[-1].strip()[:max_length]
                    else:
                        # Just take the first part up to max_length
                        return first_line[:max_length]
                
                # Final length check
                if len(value) > max_length:
                    value = value[:max_length]
                    
                return value
            
            # Clean each field with appropriate max lengths
            cleaned_result = {}
            field_limits = {
                'candidate_name': 50,
                'job_title': 50,
                'location': 50,
                'company_guess': 50,
                'referrer_name': 50,
                'referrer_email': 100,
                'phone': 30,
                'email': 100,
                'linkedin_url': 200,
                'notes': 500  # Notes can be longer to capture recruiting goals
            }

            for field, limit in field_limits.items():
                if field in result:
                    cleaned_result[field] = clean_field(result.get(field), field, limit)

            # Add financial advisor specific fields
            financial_fields = [
                'aum_managed', 'production_annual', 'client_count',
                'years_experience', 'availability_timeframe', 'compensation_range',
                'book_transferable'
            ]
            for field in financial_fields:
                if field in result and result[field]:
                    cleaned_result[field] = clean_field(result.get(field), field, 100)

            # Handle list fields (licenses, designations, specializations)
            list_fields = ['licenses_held', 'designations', 'specializations']
            for field in list_fields:
                if field in result and result[field]:
                    if isinstance(result[field], list):
                        cleaned_result[field] = result[field]
                    elif isinstance(result[field], str):
                        # Convert string to list if needed
                        items = [item.strip() for item in result[field].split(',')]
                        cleaned_result[field] = items

            # Special handling for Calendly emails - extract recruiting goals if not in notes
            if 'calendly' in state['email_content'].lower():
                import re
                # Look for recruiting goals question and answer
                goals_pattern = r'What recruiting goals[^?]*\?\s*([^\n]+(?:\n[^\n]+)?)'
                goals_match = re.search(goals_pattern, state['email_content'], re.IGNORECASE)
                if goals_match and (not cleaned_result.get('notes') or len(cleaned_result.get('notes', '')) < 50):
                    recruiting_goals = goals_match.group(1).strip()
                    # Clean up the goals text
                    recruiting_goals = recruiting_goals.replace('Your confirmation email', '').strip()
                    if recruiting_goals:
                        # Append to existing notes or create new
                        existing_notes = cleaned_result.get('notes', '')
                        if existing_notes:
                            cleaned_result['notes'] = f"{existing_notes}. Recruiting goals: {recruiting_goals[:200]}"
                        else:
                            cleaned_result['notes'] = f"Recruiting goals: {recruiting_goals[:200]}"

                # Also look for phone number if not extracted
                if not cleaned_result.get('phone'):
                    phone_pattern = r'Phone[\s:]+(\+?[\d\s\-\(\)\.]+)'
                    phone_match = re.search(phone_pattern, state['email_content'])
                    if phone_match:
                        phone = phone_match.group(1).strip()
                        digits = re.sub(r'\D', '', phone)
                        if len(digits) >= 10:
                            cleaned_result['phone'] = phone[:30]
            
            result = cleaned_result
            logger.info(f"Extraction completed (CLEANED): {result}")
            
            # Track extraction metrics if learning analytics is available
            if learning_analytics:
                try:
                    import time
                    processing_time = int((time.time() - state.get('start_time', time.time())) * 1000)
                    
                    metric = await learning_analytics.track_extraction(
                        email_domain=sender_domain,
                        extraction_result=result,
                        processing_time_ms=processing_time,
                        prompt_variant_id=prompt_variant.variant_id if prompt_variant else None,
                        used_template=bool(correction_service and correction_service.search_manager and 
                                         await correction_service.search_manager.get_company_template(sender_domain)),
                        pattern_matches=0  # Will be calculated if needed
                    )
                    
                    # Track prompt enhancement usage and effectiveness
                    if enhancement_used:
                        logger.info(f"Tracked enhanced extraction: confidence={metric.overall_confidence:.2f}, enhancement_applied=True")
                        # Could add Application Insights custom event here
                        try:
                            if hasattr(learning_analytics, 'telemetry_client') and learning_analytics.telemetry_client:
                                learning_analytics.telemetry_client.track_event(
                                    'prompt_enhancement_applied',
                                    {
                                        'email_domain': sender_domain,
                                        'extraction_confidence': metric.overall_confidence,
                                        'prompt_variant': prompt_variant.variant_name if prompt_variant else 'default'
                                    }
                                )
                        except Exception as te:
                            logger.debug(f"Could not track telemetry: {te}")
                    else:
                        logger.info(f"Tracked standard extraction: confidence={metric.overall_confidence:.2f}, enhancement_applied=False")
                        
                except Exception as e:
                    logger.warning(f"Could not track extraction metrics: {e}")
            
            # Cache the result
            try:
                cache_manager = await get_cache_manager()
                strategy_manager = get_strategy_manager()
                
                # Determine caching strategy
                should_cache, ttl, pattern_key = strategy_manager.should_cache(
                    email_content,
                    sender_domain,
                    result
                )
                
                if should_cache:
                    await cache_manager.cache_extraction(
                        email_content,
                        result,
                        extraction_type="full",
                        ttl=ttl
                    )
                    logger.info(f"Cached extraction with TTL: {ttl}")
                    
                    # Also cache pattern if identified
                    if pattern_key:
                        await cache_manager.cache_pattern(pattern_key, result)
                        logger.info(f"Cached pattern: {pattern_key}")
                        
            except Exception as e:
                logger.warning(f"Failed to cache extraction: {e}")
            
            # Apply enhancement to extraction result
            try:
                from app.enhanced_extraction import enhance_extraction_result
                enhanced_result = await enhance_extraction_result(
                    result,
                    state.get('email_content', ''),
                    sender_domain
                )
                logger.info(f"Enhanced extraction with automatic lookups: {enhanced_result}")
                result = enhanced_result
            except Exception as e:
                logger.warning(f"Could not enhance extraction: {e}")

            # Apply Apollo phone discovery if no phone found or to find additional phones
            try:
                if not result.get('phone') or True:  # Always try to discover more phones
                    from app.apollo_enricher import apollo_unlimited_people_search, apollo_unlimited_company_search
                    from app.phone_utilities import PhoneExtractor

                    logger.info("Starting Apollo phone number discovery...")

                    # Extract any phones from email text first
                    email_phones = PhoneExtractor.extract_from_text(state.get('email_content', ''))
                    if email_phones:
                        logger.info(f"Found {len(email_phones)} phone numbers in email text")

                    # Search Apollo for person's phone numbers
                    person_phones = []
                    if result.get('email') or result.get('candidate_name'):
                        apollo_person = await apollo_unlimited_people_search(
                            email=result.get('email'),
                            name=result.get('candidate_name'),
                            company_domain=sender_domain,
                            job_title=result.get('job_title')
                        )

                        if apollo_person:
                            # Extract all phone numbers
                            if apollo_person.get('phone'):
                                person_phones.append({
                                    'number': apollo_person['phone'],
                                    'type': 'primary'
                                })
                            if apollo_person.get('mobile_phone'):
                                person_phones.append({
                                    'number': apollo_person['mobile_phone'],
                                    'type': 'mobile'
                                })
                            if apollo_person.get('work_phone'):
                                person_phones.append({
                                    'number': apollo_person['work_phone'],
                                    'type': 'work'
                                })

                            # Update result with Apollo data
                            if not result.get('phone') and person_phones:
                                result['phone'] = person_phones[0]['number']

                            # Add additional enriched fields
                            if apollo_person.get('linkedin_url') and not result.get('linkedin_url'):
                                result['linkedin_url'] = apollo_person['linkedin_url']
                            if apollo_person.get('firm_company') and not result.get('company_guess'):
                                result['company_guess'] = apollo_person['firm_company']

                            logger.info(f"Apollo person search found {len(person_phones)} phone numbers")

                    # Search Apollo for company phone numbers
                    company_phones = []
                    if result.get('company_guess'):
                        apollo_company = await apollo_unlimited_company_search(
                            company_name=result.get('company_guess')
                        )

                        if apollo_company:
                            if apollo_company.get('phone'):
                                company_phones.append({
                                    'number': apollo_company['phone'],
                                    'type': 'company_main'
                                })

                            # Add key employee phones
                            for employee in apollo_company.get('key_employees', [])[:3]:
                                if employee.get('phone'):
                                    company_phones.append({
                                        'number': employee['phone'],
                                        'type': 'work',
                                        'owner': employee.get('name')
                                    })

                            logger.info(f"Apollo company search found {len(company_phones)} phone numbers")

                    # Combine all discovered phones
                    all_phones = email_phones + [{'original': p['number'], 'type': p['type']} for p in person_phones + company_phones]

                    if all_phones:
                        # Add phone discovery metadata to notes
                        phone_summary = f"Discovered {len(all_phones)} phone numbers: "
                        phone_types = {}
                        for p in all_phones:
                            ptype = p.get('type', 'unknown')
                            phone_types[ptype] = phone_types.get(ptype, 0) + 1

                        phone_summary += ', '.join([f"{count} {ptype}" for ptype, count in phone_types.items()])

                        existing_notes = result.get('notes', '')
                        if existing_notes:
                            result['notes'] = f"{existing_notes}. {phone_summary}"
                        else:
                            result['notes'] = phone_summary

                        logger.info(f"Phone discovery complete: {phone_summary}")

            except Exception as e:
                logger.warning(f"Apollo phone discovery failed: {e}")
            
            return {
                "extraction_result": result,
                "messages": [{"role": "assistant", "content": f"Extracted: {result}"}]
            }
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {
                "extraction_result": {},
                "messages": [{"role": "assistant", "content": f"Extraction error: {e}"}]
            }
    
    async def research_company(self, state: EmailProcessingState) -> Dict:
        """Second node: Research and verify company information"""
        logger.info("---RESEARCH AGENT---")
        
        extracted = state.get('extraction_result', {})
        company_guess = extracted.get('company_guess')
        candidate_name = extracted.get('candidate_name')
        candidate_email = extracted.get('email')
        candidate_website = extracted.get('website')
        sender_domain = state['sender_domain']
        
        # Use Firecrawl research service with caching
        try:
            from app.firecrawl_research import CompanyResearchService
            from app.redis_cache_manager import RedisCacheManager

            # Import the Firecrawl v2 Fire Agent for enhanced enrichment
            try:
                from app.firecrawl_v2_adapter import FirecrawlV2Agent
                ultra_service = FirecrawlV2Agent()
                use_ultra_enrichment = True
                logger.info("✅ Using Firecrawl v2 Fire Agent for enhanced enrichment")
            except ImportError as e:
                ultra_service = None
                use_ultra_enrichment = False
                logger.warning(f"⚠️ Firecrawl v2 Fire Agent not available: {e}")

            research_service = CompanyResearchService()
            cache_manager = RedisCacheManager()
            await cache_manager.connect()
            
            # Determine what to research
            research_domain = None

            # Log extracted data for debugging
            logger.info(f"🔍 DEBUG - Research Node Input:")
            logger.info(f"  - Candidate Email: {candidate_email}")
            logger.info(f"  - Candidate Website: {candidate_website}")
            logger.info(f"  - Company Guess: {company_guess}")
            logger.info(f"  - Sender Domain: {sender_domain}")

            # Priority 1: Use candidate's website if available
            if candidate_website:
                import re
                domain_match = re.search(r'https?://(?:www\.)?([^/]+)', candidate_website)
                if domain_match:
                    research_domain = domain_match.group(1)
                    logger.info(f"✅ Using candidate website for research: {research_domain}")

            # Priority 2: Use candidate's email domain (for clients/candidates with company emails)
            if not research_domain and candidate_email and '@' in candidate_email:
                email_domain = candidate_email.split('@')[1]
                # Skip generic email domains for company research
                generic_domains = [
                    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                    'aol.com', 'icloud.com', 'me.com', 'mac.com', 'msn.com',
                    'live.com', 'protonmail.com', 'ymail.com'
                ]
                if email_domain not in generic_domains:
                    research_domain = email_domain
                    logger.info(f"✅ Using candidate/client email domain for research: {research_domain}")
                else:
                    logger.info(f"⚠️ Candidate has generic email domain: {email_domain}")
                    # For clients/candidates with generic emails, try to infer company from name
                    if company_guess and company_guess.lower() not in ['unknown', 'n/a', '']:
                        # Try to construct possible domain from company name
                        import re
                        # Clean company name for domain construction
                        clean_name = re.sub(r'[^\w\s]', '', company_guess.lower())
                        clean_name = clean_name.replace(' ', '')
                        # Common domain extensions to try
                        extensions = ['.com', '.org', '.net', '.co', '.io', '.solutions', '.biz', '.info', '.us', '.ai', '.tech']
                        possible_domains = [f"{clean_name}{ext}" for ext in extensions]
                        # Also try with www prefix for some common ones
                        possible_domains.extend([f"www.{clean_name}.com", f"www.{clean_name}.org"])
                        logger.info(f"🔍 Will try to research company '{company_guess}' via web search with multiple TLDs")
            
            # Search for candidate information if we have a name
            candidate_info = {}
            if candidate_name:
                logger.info(f"Searching for candidate information: {candidate_name}")
                # If we have a name like "Jerry Fetta", also search for domain like "jerryfetta.com"
                candidate_info = await research_service.search_candidate_info(candidate_name, company_guess)
                
                # Update extracted info with found data
                if candidate_info:
                    logger.info(f"Found candidate info via Firecrawl: {candidate_info}")
                    # Use found website for company research if available
                    if candidate_info.get('website') and not research_domain:
                        import re
                        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', candidate_info['website'])
                        if domain_match:
                            research_domain = domain_match.group(1)
            
            # Research the company using the best available domain
            if research_domain:
                # Check cache first
                cached_info = await cache_manager.get_domain_info(research_domain)
                if cached_info:
                    logger.info(f"Using cached domain info for: {research_domain}")
                    research_result = cached_info
                else:
                    # Fetch from Firecrawl
                    research_result = await research_service.research_company(
                        email_domain=research_domain,
                        company_guess=company_guess
                    )
                    # Cache the result
                    if research_result and research_result.get('confidence', 0) > 0.5:
                        await cache_manager.cache_domain_info(research_domain, research_result)
            else:
                # Fallback to sender domain
                cached_info = await cache_manager.get_domain_info(sender_domain)
                if cached_info:
                    logger.info(f"Using cached domain info for: {sender_domain}")
                    research_result = cached_info
                else:
                    research_result = await research_service.research_company(
                        email_domain=sender_domain,
                        company_guess=company_guess
                    )
                    # Cache if good confidence
                    if research_result and research_result.get('confidence', 0) > 0.5:
                        await cache_manager.cache_domain_info(sender_domain, research_result)
            
            # If we found a website through candidate search, use it for company info
            if candidate_info.get('website'):
                # Extract company name from personal website if it's there
                logger.info(f"Using candidate website for company info: {candidate_info['website']}")
                # Update research result with website
                research_result['website'] = candidate_info['website']
            
            # Merge candidate info into research result
            research_result.update(candidate_info)

            # 🚀 NEW: Apollo.io enrichment for accurate company phone/website
            if candidate_email:
                try:
                    from app.apollo_enricher import enrich_contact_with_apollo
                    apollo_data = await enrich_contact_with_apollo(candidate_email)

                    if apollo_data:
                        logger.info(f"🎯 Apollo.io enrichment successful for {candidate_email}")

                        # Apollo data provides accurate company info - prioritize it
                        if apollo_data.get('website'):
                            research_result['website'] = apollo_data['website']
                            logger.info(f"📱 Updated website from Apollo: {apollo_data['website']}")

                        # Apollo often has better company phone than web scraping
                        if apollo_data.get('phone'):
                            research_result['phone'] = apollo_data['phone']
                            logger.info(f"☎️ Updated phone from Apollo: {apollo_data['phone']}")

                        # Company name from Apollo is usually more accurate
                        if apollo_data.get('firm_company'):
                            research_result['company_name'] = apollo_data['firm_company']
                            logger.info(f"🏢 Updated company name from Apollo: {apollo_data['firm_company']}")

                        # Job title and location
                        if apollo_data.get('job_title'):
                            research_result['job_title'] = apollo_data['job_title']
                        if apollo_data.get('location'):
                            research_result['location'] = apollo_data['location']

                        # Mark as Apollo-enhanced
                        research_result['apollo_enriched'] = True
                        research_result['confidence'] = min(research_result.get('confidence', 0.5) + 0.3, 1.0)

                    else:
                        logger.info(f"🔍 No Apollo data found for {candidate_email}")

                except Exception as e:
                    logger.error(f"❌ Apollo enrichment failed for {candidate_email}: {str(e)}")

            # Apply ultra enrichment if available
            if use_ultra_enrichment and ultra_service and research_domain:
                try:
                    logger.info(f"🚀 Applying Firecrawl v2 Supercharged enrichment for: {research_domain}")

                    # Prepare email data for enrichment
                    email_data = {
                        "sender_email": state.get("sender_email", ""),
                        "sender_name": candidate_name or "",
                        "body": state.get("email_content", "")
                    }

                    # Prepare extracted data
                    extracted_data = state.get("extraction_result", {})
                    if extracted_data and 'company_record' in extracted_data:
                        extracted_data['company_record']['company_domain'] = research_domain

                    # Get enriched data
                    enriched = await ultra_service.enrich_email_data(
                        email_data=email_data,
                        extracted_data=extracted_data
                    )

                    # Update research result with enriched data
                    if enriched and enriched.get("enrichments"):
                        enrichments = enriched["enrichments"]

                        # Add company enrichment data
                        if enrichments.get("company"):
                            company_data = enrichments["company"]
                            logger.info(f"✅ Enriched company data: revenue={company_data.get('revenue')}, "
                                      f"employees={company_data.get('employee_count')}, "
                                      f"funding={company_data.get('funding_total')}")

                            # Add to research result
                            research_result.update({
                                "revenue": company_data.get("revenue"),
                                "employee_count": company_data.get("employee_count"),
                                "employee_range": company_data.get("employee_range"),
                                "funding_total": company_data.get("funding_total"),
                                "latest_funding": company_data.get("latest_funding_round"),
                                "valuation": company_data.get("valuation"),
                                "tech_stack": company_data.get("tech_stack", []),
                                "founders": company_data.get("founders", []),
                                "executives": company_data.get("key_executives", []),
                                "headquarters": company_data.get("headquarters"),
                                "industry": company_data.get("industry"),
                                "products": company_data.get("products", []),
                                "enrichment_source": "firecrawl_v2_supercharged"
                            })

                            # Update extraction result if it exists
                            if state.get("extraction_result") and state["extraction_result"].get("company_record"):
                                state["extraction_result"]["company_record"].update({
                                    "revenue": company_data.get("revenue"),
                                    "employee_count": company_data.get("employee_count"),
                                    "funding": company_data.get("funding_total"),
                                    "tech_stack": ", ".join(company_data.get("tech_stack", []))[:255] if company_data.get("tech_stack") else None,
                                    "enrichment_data": json.dumps({
                                        "revenue": company_data.get("revenue"),
                                        "employees": company_data.get("employee_count"),
                                        "funding": company_data.get("funding_total"),
                                        "valuation": company_data.get("valuation"),
                                        "tech_stack": company_data.get("tech_stack", []),
                                        "industry": company_data.get("industry"),
                                        "products": company_data.get("products", [])
                                    })
                                })

                        # Add candidate enrichment data
                        if enrichments.get("candidate"):
                            candidate_data = enrichments["candidate"]
                            research_result.update({
                                "candidate_linkedin": candidate_data.get("linkedin_url"),
                                "candidate_personal_site": candidate_data.get("personal_website"),
                                "candidate_github": candidate_data.get("github"),
                                "candidate_skills": candidate_data.get("skills", [])
                            })

                    logger.info(f"✅ Ultra enrichment completed successfully")

                except Exception as e:
                    logger.warning(f"Ultra enrichment failed: {e}, continuing with standard data")

            logger.info(f"Research completed with Firecrawl: {research_result}")

            return {
                "company_research": research_result,
                "messages": [{"role": "assistant", "content": f"Researched: {research_result}"}]
            }
            
        except Exception as e:
            logger.warning(f"Firecrawl research failed: {e}, using fallback")
            
            # Fallback logic
            company_name = company_guess
            confidence = 0.0
            
            if company_guess:
                confidence = 0.7
            elif sender_domain:
                # Clean domain to get company name
                domain_parts = sender_domain.split('.')
                if domain_parts:
                    company_name = domain_parts[0].replace('-', ' ').title()
                    confidence = 0.4
            
            research_result = {
                "company_name": company_name,
                "company_domain": sender_domain,
                "confidence": confidence,
                "source": "fallback"
            }
            
            logger.info(f"Research completed with fallback: {research_result}")
            
            return {
                "company_research": research_result,
                "messages": [{"role": "assistant", "content": f"Researched: {research_result}"}]
            }
    
    async def validate_and_clean(self, state: EmailProcessingState) -> Dict:
        """Third node: Validate and clean the extracted data"""
        logger.info("---VALIDATION AGENT---")
        
        extracted = state.get('extraction_result', {})
        research = state.get('company_research', {})
        
        # Enhanced Calendly data extraction
        phone = extracted.get('phone')
        email = extracted.get('email')
        calendly_url = extracted.get('calendly_url')
        
        if calendly_url:
            import re
            import urllib.parse
            
            # Try to extract ALL data from Calendly URL parameters
            # Common patterns: ?phone=xxx&email=xxx&name=xxx
            # or answer_1=phone&answer_2=email patterns
            
            # Extract phone if not already found
            if not phone:
                phone_patterns = [
                    r'phone=([0-9\-\+\(\)\s]+)',
                    r'answer_\d+=([0-9\-\+\(\)\s]+)',  # Sometimes phone in answer fields
                    r'a\d+=([0-9\-\+\(\)\s]+)'  # Shortened form
                ]
                for pattern in phone_patterns:
                    phone_match = re.search(pattern, calendly_url)
                    if phone_match:
                        phone = urllib.parse.unquote(phone_match.group(1))
                        # Store in extracted data to preserve it
                        if not extracted.get('phone'):
                            extracted['phone'] = phone
                        logger.info(f"Extracted phone from Calendly: {phone}")
                        break
            
            # Extract email if not already found  
            if not email:
                email_patterns = [
                    r'email=([^&]+)',
                    r'invitee_email=([^&]+)',
                    r'answer_\d+=([^&]*@[^&]+)'  # Email in answer fields
                ]
                for pattern in email_patterns:
                    email_match = re.search(pattern, calendly_url)
                    if email_match:
                        email = urllib.parse.unquote(email_match.group(1))
                        # Store in extracted data to preserve it
                        if not extracted.get('email'):
                            extracted['email'] = email
                        logger.info(f"Extracted email from Calendly: {email}")
                        break
            
            # Extract name if not already found
            if not extracted.get('candidate_name'):
                name_patterns = [
                    r'name=([^&]+)',
                    r'invitee_full_name=([^&]+)',
                    r'first_name=([^&]+).*last_name=([^&]+)'
                ]
                for pattern in name_patterns:
                    name_match = re.search(pattern, calendly_url)
                    if name_match:
                        if len(name_match.groups()) == 2:
                            # First and last name
                            extracted['candidate_name'] = f"{urllib.parse.unquote(name_match.group(1))} {urllib.parse.unquote(name_match.group(2))}"
                        else:
                            extracted['candidate_name'] = urllib.parse.unquote(name_match.group(1))
                        logger.info(f"Extracted name from Calendly: {extracted['candidate_name']}")
                        break
        
        # Determine source based on business rules
        source = "Email Inbound"  # Default
        source_detail = None
        
        if extracted.get('referrer_name') or extracted.get('referrer_email'):
            source = "Referral"
            source_detail = extracted.get('referrer_name')
        elif calendly_url:
            source = "Website Inbound"
        
        # Merge extraction with research - use Firecrawl data to fill missing fields
        validated_data = {
            "candidate_name": extracted.get('candidate_name'),
            "job_title": extracted.get('job_title'),
            "location": extracted.get('location'),
            # Use extracted company name first, then research if confident
            "company_name": (
                extracted.get('company_name') or
                extracted.get('company_guess') or
                (research.get('company_name') if research.get('confidence', 0) > 0.7 else None)
            ),
            "referrer_name": extracted.get('referrer_name'),
            "referrer_email": extracted.get('referrer_email'),
            # Prioritize extracted email (including from Calendly), fallback to Firecrawl research
            "email": extracted.get('email') or research.get('email'),
            # Company phone from research (NOT candidate's personal phone)
            "company_phone": research.get('phone'),
            # Candidate's personal phone from extraction
            "phone": extracted.get('phone'),
            # Prioritize extracted LinkedIn, fallback to Firecrawl research
            "linkedin_url": extracted.get('linkedin_url') or research.get('linkedin_url'),
            "notes": extracted.get('notes'),
            # Company website from research
            "company_website": research.get('website') or f"https://{research.get('company_domain', '')}" if research.get('company_domain') else None,
            # Legacy website field for backward compatibility
            "website": research.get('website') or research.get('company_domain'),
            "industry": research.get('industry'),  # From research if available
            "source": source,
            "source_detail": source_detail
        }

        # Filter out The Well's information from client/candidate data
        validated_data = filter_well_info(validated_data)
        
        # Clean and standardize
        for key, value in validated_data.items():
            if value and isinstance(value, str):
                # Clean whitespace and standardize
                validated_data[key] = value.strip()
                # Capitalize names properly
                if key in ['candidate_name', 'referrer_name', 'company_name', 'source_detail']:
                    validated_data[key] = ' '.join(word.capitalize() for word in value.split())
                # Clean URLs
                if key in ['linkedin_url', 'calendly_url', 'website']:
                    # Ensure URLs are properly formatted
                    if value and not value.startswith(('http://', 'https://')):
                        validated_data[key] = f"https://{value}"
        
        logger.info(f"Validation completed: {validated_data}")

        # Create Steve's 3-record structure from extracted data
        from app.models import CompanyRecord, ContactRecord, DealRecord
        from app.business_rules import format_deal_name

        # Parse name into first and last
        full_name = extracted.get('first_name', '') + ' ' + extracted.get('last_name', '')
        if not full_name.strip() and extracted.get('candidate_name'):
            # Fallback to legacy candidate_name field
            full_name = extracted.get('candidate_name', '')
            name_parts = full_name.strip().split(' ', 1) if full_name else ['', '']
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
        else:
            first_name = extracted.get('first_name', '')
            last_name = extracted.get('last_name', '')

        # Create Company Record - prioritize research data (Apollo/Firecrawl) over extraction
        company_record = CompanyRecord(
            company_name=research.get('company_name') or extracted.get('company_name') or extracted.get('company_guess') or validated_data.get('company_name'),
            phone=research.get('phone') or extracted.get('company_phone') or validated_data.get('company_phone'),  # Research phone first
            website=research.get('website') or extracted.get('company_website') or validated_data.get('company_website'),  # Research website first
            company_source=extracted.get('company_source') or source,
            source_detail=extracted.get('source_detail') or source_detail,
            who_gets_credit=extracted.get('who_gets_credit'),
            detail=extracted.get('credit_person_name') or extracted.get('referrer_name')
        )

        # Get city/state from research data (Firecrawl/Apollo provide these directly now)
        research_city = research.get('city')
        research_state = research.get('state')

        # Fallback: Try to extract city/state from full address if not provided separately
        if (not research_city or not research_state) and research.get('address'):
            # Parse address like "123 Main St, San Francisco, CA 94105"
            address_parts = research.get('address', '').split(',')
            if len(address_parts) >= 3:
                # Typical format: street, city, state+zip
                if not research_city:
                    research_city = address_parts[-2].strip() if len(address_parts) > 1 else None
                if not research_state:
                    state_zip = address_parts[-1].strip() if address_parts else ''
                    # Extract state (usually 2 letters before zip)
                    import re
                    state_match = re.search(r'([A-Z]{2})\s*\d{5}', state_zip)
                    if state_match:
                        research_state = state_match.group(1)
                    else:
                        # Might just be state without zip
                        research_state = state_zip.strip()[:2] if len(state_zip.strip()) >= 2 else None

        # Create Contact Record with research data as fallback
        contact_record = ContactRecord(
            first_name=first_name,
            last_name=last_name,
            company_name=extracted.get('contact_company_name') or company_record.company_name,
            email=extracted.get('contact_email') or extracted.get('email') or validated_data.get('email'),
            phone=extracted.get('contact_phone') or extracted.get('phone') or validated_data.get('phone'),
            city=extracted.get('contact_city') or research_city,  # Use research city as fallback
            state=extracted.get('contact_state') or research_state,  # Use research state as fallback
            source=extracted.get('contact_source') or source
        )

        # Parse location for city/state if STILL not set (last resort)
        if not contact_record.city and extracted.get('location'):
            location_parts = extracted.get('location', '').split(',')
            if location_parts:
                contact_record.city = location_parts[0].strip()
                if len(location_parts) > 1:
                    contact_record.state = location_parts[1].strip()

        # Create Deal Record with Steve's format
        job_title = extracted.get('position_title') or extracted.get('job_title') or validated_data.get('job_title')
        location = extracted.get('position_location') or extracted.get('location') or validated_data.get('location')

        # Format deal name using Steve's format
        deal_name = format_deal_name(
            job_title=job_title,
            location=location,
            company_name=company_record.company_name,
            use_steve_format=True
        )

        deal_record = DealRecord(
            source=extracted.get('deal_source') or source,
            deal_name=deal_name,
            pipeline="Sales Pipeline",  # ALWAYS use Sales Pipeline as the only pipeline
            closing_date=extracted.get('estimated_closing_date'),
            source_detail=extracted.get('source_detail') or source_detail,
            description_of_reqs=extracted.get('description_of_requirements') or extracted.get('notes')
        )

        # Convert to ExtractedData model with Steve's structure and financial advisor fields
        try:
            final_output = ExtractedData(
                company_record=company_record,
                contact_record=contact_record,
                deal_record=deal_record,
                # Financial advisor specific fields from extraction
                aum_managed=extracted.get('aum_managed'),
                production_annual=extracted.get('production_annual'),
                client_count=extracted.get('client_count'),
                licenses_held=extracted.get('licenses_held'),
                designations=extracted.get('designations'),
                years_experience=extracted.get('years_experience'),
                availability_timeframe=extracted.get('availability_timeframe'),
                compensation_range=extracted.get('compensation_range'),
                book_transferable=extracted.get('book_transferable'),
                specializations=extracted.get('specializations'),
                # Keep legacy fields for backward compatibility
                candidate_name=full_name.strip() or validated_data.get('candidate_name'),
                job_title=job_title or validated_data.get('job_title'),
                location=location or validated_data.get('location'),
                company_name=company_record.company_name or validated_data.get('company_name'),
                referrer_name=validated_data.get('referrer_name'),
                referrer_email=validated_data.get('referrer_email'),
                email=contact_record.email or validated_data.get('email'),
                phone=contact_record.phone or validated_data.get('phone'),
                linkedin_url=validated_data.get('linkedin_url'),
                notes=deal_record.description_of_reqs or validated_data.get('notes'),
                website=company_record.website or validated_data.get('website'),
                industry=validated_data.get('industry'),
                source=source,
                source_detail=source_detail
            )
        except Exception as e:
            logger.error(f"Failed to create ExtractedData with 3-record structure: {e}")
            # Fallback to legacy structure
            final_output = ExtractedData(**validated_data)
        
        return {
            "validation_result": validated_data,
            "final_output": final_output,
            "messages": [{"role": "assistant", "content": f"Validated: {validated_data}"}]
        }
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create the graph
        workflow = StateGraph(EmailProcessingState)
        
        # Add nodes
        workflow.add_node("extract", self.extract_information)
        workflow.add_node("research", self.research_company)
        workflow.add_node("validate", self.validate_and_clean)
        
        # Add edges to create sequential flow
        workflow.add_edge(START, "extract")
        workflow.add_edge("extract", "research")
        workflow.add_edge("research", "validate")
        workflow.add_edge("validate", END)
        
        # Compile the workflow
        return workflow.compile()
    
    async def get_prompt_enhancement_status(self, email_domain: str) -> Dict[str, Any]:
        """Get status of prompt enhancement capabilities for debugging"""
        status = {
            "correction_service_available": False,
            "learning_analytics_available": False,
            "azure_search_available": False,
            "prompt_variants_active": False,
            "domain_patterns_count": 0,
            "company_template_available": False,
            "enhancement_ready": False
        }
        
        try:
            from app.correction_learning import CorrectionLearningService
            from app.learning_analytics import LearningAnalytics
            
            # Check correction service
            correction_service = CorrectionLearningService(None, use_azure_search=True)
            status["correction_service_available"] = True
            
            if correction_service.search_manager:
                status["azure_search_available"] = True
                
                # Check for company template
                template = await correction_service.search_manager.get_company_template(email_domain)
                status["company_template_available"] = bool(template)
                
                # Check for domain patterns
                patterns = await correction_service.get_common_patterns(email_domain=email_domain)
                status["domain_patterns_count"] = len(patterns) if patterns else 0
            
            # Check learning analytics
            learning_analytics = LearningAnalytics(
                search_manager=correction_service.search_manager,
                enable_ab_testing=True
            )
            status["learning_analytics_available"] = True
            status["prompt_variants_active"] = len([v for v in learning_analytics.prompt_variants.values() if v.is_active]) > 0
            
            # Overall enhancement readiness
            status["enhancement_ready"] = (
                status["correction_service_available"] and
                (status["domain_patterns_count"] > 0 or status["company_template_available"])
            )
            
        except Exception as e:
            logger.debug(f"Error checking prompt enhancement status: {e}")
        
        return status

    async def process_email(self, email_body: str, sender_domain: str, learning_hints: str = None, calendly_url: str = None) -> ExtractedData:
        """Main entry point to process an email with optional learning hints"""
        
        logger.info(f"Starting LangGraph email processing for domain: {sender_domain}")
        
        # Log enhancement status for debugging
        try:
            enhancement_status = await self.get_prompt_enhancement_status(sender_domain)
            logger.info(f"Prompt enhancement status: {enhancement_status}")
        except Exception as e:
            logger.debug(f"Could not check enhancement status: {e}")
        
        # Initial state
        initial_state = {
            "email_content": email_body,
            "sender_domain": sender_domain,
            "extraction_result": None,
            "company_research": None,
            "validation_result": None,
            "final_output": None,
            "messages": [],
            "learning_hints": learning_hints or ""
        }
        
        try:
            # Run the workflow
            result = await self.graph.ainvoke(initial_state)

            # Extract the final output
            final_output = result.get("final_output") or ExtractedData()

            # Calendly enrichment (best-effort)
            try:
                url = calendly_url or self._extract_calendly_url(email_body)
                if url:
                    extra = await self._enrich_from_calendly(url)
                    for k, v in (extra or {}).items():
                        if hasattr(final_output, k) and v:
                            setattr(final_output, k, v)
            except Exception:
                pass

            logger.info(f"LangGraph processing successful: {final_output}")
            return final_output
                
        except Exception as e:
            logger.error(f"LangGraph processing failed: {e}")
            return ExtractedData()


# Backwards compatibility wrapper
class EmailProcessingCrew:
    """Email processing manager wrapper"""
    
    def __init__(self, serper_api_key: str = None):
        self.workflow = EmailProcessingWorkflow()
        logger.info("EmailProcessingCrew initialized with LangGraph backend")
    
    def run(self, email_body: str, sender_domain: str) -> ExtractedData:
        """Synchronous wrapper for compatibility"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a task
            task = asyncio.create_task(
                self.workflow.process_email(email_body, sender_domain)
            )
            return asyncio.run_until_complete(task)
        else:
            # Create new event loop
            return asyncio.run(self.workflow.process_email(email_body, sender_domain))
    
    async def run_async(self, email_body: str, sender_domain: str) -> ExtractedData:
        """Async processing method"""
        return await self.workflow.process_email(email_body, sender_domain)

    def _extract_calendly_url(self, text: str) -> str:
        import re
        m = re.search(r"https?://(?:www\.)?calendly\.com/[\w\-/.?=&]+", text, re.IGNORECASE)
        return m.group(0) if m else None

    async def _enrich_from_calendly(self, url: str) -> dict:
        try:
            import aiohttp, re
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as resp:  # Reduced from 5s to 3s
                    if resp.status != 200:
                        return {}
                    html = await resp.text()
            phone = re.search(r"(\+?\d[\d\s().-]{7,}\d)", html)
            email = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", html)
            return {
                "phone": phone.group(0) if phone else None,
                "candidate_email": email.group(0) if email else None
            }
        except Exception:
            return {}


# Simple fallback extractor (unchanged)
class SimplifiedEmailExtractor:
    """Fallback email extractor when LangGraph is not available."""
    
    @staticmethod
    def extract(email_body: str, sender_email: str) -> ExtractedData:
        """Extract basic information from email using pattern matching."""
        # Extract sender domain for company inference
        domain = sender_email.split('@')[1] if '@' in sender_email else ''
        company_name = domain.split('.')[0].title() if domain else None
        
        # Basic extraction logic (fallback when AI fails)
        return ExtractedData(
            candidate_name=None,
            job_title=None,
            location=None,
            company_name=company_name,
            referrer_name=None
        )