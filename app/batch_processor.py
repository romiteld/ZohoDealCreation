"""
Batch email processor using GPT-5-mini's 400K context window
Processes multiple emails in a single API call for efficiency
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import time

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.models import ExtractedData
from app.service_bus_manager import (
    ServiceBusManager, 
    EmailBatchMessage, 
    BatchProcessingResult,
    BatchStatus
)
from app.integrations import ZohoApiClient as ZohoIntegration, AzureBlobStorageClient as AzureBlobStorage, PostgreSQLClient
from app.business_rules import BusinessRulesEngine
from app.monitoring import MonitoringService
from app.correction_learning import CorrectionLearningService, CorrectionRecord
from app.learning_analytics import LearningAnalytics, ExtractionMetric, TestStrategy
from app.azure_ai_search_manager import AzureAISearchManager

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


class BatchExtractedData(BaseModel):
    """Structured output for batch extraction"""
    emails: List[Dict[str, Any]] = Field(
        description="List of extracted data for each email"
    )
    
    class EmailData(BaseModel):
        """Individual email extraction"""
        email_index: int = Field(description="Index of the email in the batch")
        candidate_name: Optional[str] = Field(default=None)
        job_title: Optional[str] = Field(default=None)
        location: Optional[str] = Field(default=None)
        company_name: Optional[str] = Field(default=None)
        referrer_name: Optional[str] = Field(default=None)
        website: Optional[str] = Field(default=None)
        phone: Optional[str] = Field(default=None)
        industry: Optional[str] = Field(default=None)
        confidence_score: float = Field(default=0.0, description="Extraction confidence 0-1")


@dataclass
class ProcessingMetrics:
    """Metrics for batch processing performance"""
    batch_id: str
    total_emails: int
    processed_emails: int
    failed_emails: int
    total_tokens_used: int
    processing_time_seconds: float
    avg_time_per_email: float
    api_calls: int
    errors: List[str]
    
    # Learning metrics
    pattern_matches_used: int = 0
    corrections_applied: int = 0
    templates_used: int = 0
    confidence_scores: List[float] = None
    
    def __post_init__(self):
        if self.confidence_scores is None:
            self.confidence_scores = []


class BatchEmailProcessor:
    """Process multiple emails in batches using GPT-5-mini with comprehensive learning integration"""
    
    def __init__(
        self,
        openai_api_key: str = None,
        service_bus_manager: ServiceBusManager = None,
        zoho_client: ZohoIntegration = None,
        postgres_client: PostgreSQLClient = None,
        learning_service: CorrectionLearningService = None,
        analytics_service: LearningAnalytics = None,
        search_manager: AzureAISearchManager = None
    ):
        """
        Initialize batch processor
        
        Args:
            openai_api_key: OpenAI API key
            service_bus_manager: Service Bus manager instance
            zoho_client: Zoho API client
            postgres_client: PostgreSQL client for deduplication
        """
        # Initialize OpenAI client
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        # Service dependencies
        self.service_bus = service_bus_manager
        self.zoho_client = zoho_client or ZohoIntegration(
            oauth_service_url=os.getenv("ZOHO_OAUTH_SERVICE_URL")
        )
        self.postgres_client = postgres_client
        
        # Business rules engine
        self.business_rules = BusinessRulesEngine()
        
        # Initialize monitoring service
        try:
            self.monitoring = MonitoringService()
            logger.info("Batch processor monitoring initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize monitoring: {e}")
            self.monitoring = None
        
        # Blob storage for attachments
        self.blob_storage = AzureBlobStorage(
            connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            container_name=os.getenv("AZURE_CONTAINER_NAME", "email-attachments")
        )
        
        # Learning and analytics services
        self.learning_service = learning_service
        self.analytics_service = analytics_service
        self.search_manager = search_manager
        
        # Initialize learning services if not provided
        if not self.learning_service and self.postgres_client:
            try:
                self.learning_service = CorrectionLearningService(
                    db_client=self.postgres_client,
                    use_azure_search=bool(search_manager)
                )
                logger.info("Correction learning service initialized for batch processing")
            except Exception as e:
                logger.warning(f"Could not initialize learning service: {e}")
        
        if not self.analytics_service:
            try:
                self.analytics_service = LearningAnalytics(
                    search_manager=search_manager,
                    app_insights_key=os.getenv("APPINSIGHTS_INSTRUMENTATION_KEY")
                )
                logger.info("Learning analytics service initialized for batch processing")
            except Exception as e:
                logger.warning(f"Could not initialize analytics service: {e}")
        
        if not self.search_manager and os.getenv("AZURE_SEARCH_ENDPOINT"):
            try:
                self.search_manager = AzureAISearchManager()
                logger.info("Azure AI Search manager initialized for batch processing")
            except Exception as e:
                logger.warning(f"Could not initialize search manager: {e}")
        
        # Processing configuration
        self.max_retries = 3
        self.retry_delay_seconds = 5
        self.batch_timeout_seconds = 300  # 5 minutes per batch
        
        # GPT-5-mini configuration
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.temperature = 1  # CRITICAL: Must be 1 for GPT-5-mini
        self.max_tokens = 8000  # Conservative output limit
        
        logger.info(f"Batch processor initialized with model: {self.model}")
    
    def _calculate_batch_cost(self, total_tokens: int) -> float:
        """
        Calculate estimated cost for batch processing based on tokens used
        
        Args:
            total_tokens: Total tokens consumed
        
        Returns:
            Estimated cost in USD
        """
        # GPT-5-mini pricing: $0.25 per 1M input tokens, $1.00 per 1M output tokens
        # Assume 80% input, 20% output for batch processing
        if self.model == "gpt-5-mini":
            input_tokens = total_tokens * 0.8
            output_tokens = total_tokens * 0.2
            input_cost = (input_tokens / 1_000_000) * 0.25
            output_cost = (output_tokens / 1_000_000) * 1.00
            return input_cost + output_cost
        else:
            # Fallback pricing
            return (total_tokens / 1_000_000) * 1.00
    
    async def _create_enhanced_batch_prompt(
        self, 
        emails: List[Dict[str, Any]], 
        use_learning: bool = True
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Create enhanced batch prompt using learning patterns and company templates
        
        Args:
            emails: List of email dictionaries
            use_learning: Whether to apply learning patterns
        
        Returns:
            Tuple of (enhanced prompt, learning_context)
        """
        learning_context = {
            "templates_used": 0,
            "patterns_applied": 0,
            "corrections_found": 0,
            "domain_insights": {}
        }
        
        # Base prompt structure
        prompt = """You are a Senior Data Analyst specializing in recruitment email analysis.
        Process the following batch of emails and extract key recruitment details.
        
        CRITICAL RULES:
        1. ONLY extract information EXPLICITLY stated in each email
        2. Return null/None for missing information - NEVER make it up
        3. Each email should be processed independently
        4. Maintain high accuracy and consistency across the batch
        5. Use domain-specific patterns when available
        
        For each email, extract:
        - candidate_name: The person being referred for the job
        - job_title: The specific position mentioned
        - location: City and state if available
        - company_name: Any company explicitly mentioned
        - referrer_name: ONLY if explicitly stated as "referred by"
        - phone: Contact phone number if present
        - website: Company website if mentioned
        - industry: Industry or sector if mentioned
        - confidence_score: Your confidence in the extraction (0.0 to 1.0)
        
        """
        
        # Add learning-enhanced guidance if services available
        if use_learning and (self.learning_service or self.search_manager):
            domain_patterns = await self._get_domain_patterns(emails)
            if domain_patterns:
                prompt += "\n\nDOMAIN-SPECIFIC PATTERNS TO APPLY:\n"
                for domain, patterns in domain_patterns.items():
                    if patterns:
                        prompt += f"\nFor emails from {domain}:\n"
                        for pattern in patterns[:3]:  # Limit to top 3 patterns
                            prompt += f"- {pattern.get('description', '')}\n"
                        learning_context["domain_insights"][domain] = len(patterns)
                        learning_context["patterns_applied"] += len(patterns[:3])
        
        # Add company templates if available
        if self.search_manager:
            templates = await self._get_company_templates(emails)
            if templates:
                prompt += "\n\nCOMPANY TEMPLATES TO REFERENCE:\n"
                for template in templates[:5]:  # Limit to top 5 templates
                    prompt += f"- {template.get('company')}: {template.get('pattern')}\n"
                learning_context["templates_used"] = len(templates[:5])
        
        prompt += "\n\nEMAILS TO PROCESS:\n"
        
        # Add emails with enhanced context
        for i, email in enumerate(emails):
            prompt += f"\n\n--- EMAIL {i} ---\n"
            prompt += f"From: {email.get('sender_email', 'unknown')}\n"
            prompt += f"Subject: {email.get('subject', 'No subject')}\n"
            
            # Add domain context if available
            domain = email.get('sender_email', '').split('@')[-1] if '@' in email.get('sender_email', '') else ''
            if domain in learning_context.get("domain_insights", {}):
                prompt += f"Domain Context: {learning_context['domain_insights'][domain]} patterns available\n"
            
            prompt += f"Body:\n{email.get('body', 'No content')}\n"
        
        prompt += "\n\nReturn ONLY valid JSON array with extracted data for each email."
        
        return prompt, learning_context
    
    async def _get_domain_patterns(self, emails: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Get learning patterns for email domains in the batch"""
        if not self.learning_service:
            return {}
        
        domain_patterns = {}
        domains = set()
        
        for email in emails:
            sender_email = email.get('sender_email', '')
            if '@' in sender_email:
                domain = sender_email.split('@')[-1]
                domains.add(domain)
        
        try:
            for domain in domains:
                patterns = await self.learning_service.get_domain_patterns(domain)
                if patterns:
                    domain_patterns[domain] = patterns
        except Exception as e:
            logger.warning(f"Could not fetch domain patterns: {e}")
        
        return domain_patterns
    
    async def _get_company_templates(self, emails: List[Dict[str, Any]]) -> List[Dict]:
        """Get company-specific templates from Azure AI Search"""
        if not self.search_manager:
            return []
        
        try:
            # Extract company names mentioned in emails for template lookup
            companies = set()
            for email in emails:
                body = email.get('body', '').lower()
                # Simple company extraction (could be enhanced)
                words = body.split()
                for word in words:
                    if len(word) > 3 and word.isalpha():
                        companies.add(word.capitalize())
            
            templates = []
            for company in list(companies)[:10]:  # Limit company lookups
                template = await self.search_manager.get_company_template(company)
                if template:
                    templates.append(template)
            
            return templates
        except Exception as e:
            logger.warning(f"Could not fetch company templates: {e}")
            return []
    
    def _create_batch_prompt(self, emails: List[Dict[str, Any]]) -> str:
        """Legacy prompt creation for backward compatibility"""
        prompt = """You are a Senior Data Analyst specializing in recruitment email analysis.
        Process the following batch of emails and extract key recruitment details.
        
        CRITICAL RULES:
        1. ONLY extract information EXPLICITLY stated in each email
        2. Return null/None for missing information - NEVER make it up
        3. Each email should be processed independently
        4. Maintain high accuracy and consistency across the batch
        
        For each email, extract:
        - candidate_name: The person being referred for the job
        - job_title: The specific position mentioned
        - location: City and state if available
        - company_name: Any company explicitly mentioned
        - referrer_name: ONLY if explicitly stated as "referred by"
        - phone: Contact phone number if present
        - website: Company website if mentioned
        - industry: Industry or sector if mentioned
        
        Return the results as a JSON array with one object per email.
        Include an "email_index" field to match each result to its input.
        
        EMAILS TO PROCESS:
        """
        
        for i, email in enumerate(emails):
            prompt += f"\n\n--- EMAIL {i} ---\n"
            prompt += f"From: {email.get('sender_email', 'unknown')}\n"
            prompt += f"Subject: {email.get('subject', 'No subject')}\n"
            prompt += f"Body:\n{email.get('body', 'No content')}\n"
        
        prompt += "\n\nReturn ONLY valid JSON array with extracted data for each email."
        
        return prompt
    
    async def process_batch(
        self, 
        batch_message: EmailBatchMessage,
        progress_callback: Optional[callable] = None
    ) -> BatchProcessingResult:
        """
        Process a batch of emails using GPT-5-mini
        
        Args:
            batch_message: Batch message from Service Bus
            progress_callback: Optional callback for progress updates
        
        Returns:
            BatchProcessingResult with processing details
        """
        start_time = time.time()
        metrics = ProcessingMetrics(
            batch_id=batch_message.batch_id,
            total_emails=batch_message.total_count,
            processed_emails=0,
            failed_emails=0,
            total_tokens_used=0,
            processing_time_seconds=0,
            avg_time_per_email=0,
            api_calls=0,
            errors=[]
        )
        
        results = []
        errors = []
        
        try:
            logger.info(f"Processing batch {batch_message.batch_id} with {batch_message.total_count} emails")
            
            # Create batch status record
            if self.postgres_client:
                try:
                    await self.postgres_client.create_batch_status(
                        batch_message.batch_id, 
                        batch_message.total_count,
                        metadata={
                            "model": self.model,
                            "priority": getattr(batch_message, 'priority', 0),
                            "created_by": "batch_processor"
                        }
                    )
                    # Update to processing status
                    await self.postgres_client.update_batch_status(
                        batch_message.batch_id,
                        status='processing'
                    )
                except Exception as e:
                    logger.warning(f"Failed to create batch status: {e}")
            
            # Create batch prompt
            prompt = self._create_batch_prompt(batch_message.emails)
            
            # Estimate tokens (for monitoring)
            estimated_tokens = len(prompt) // 4
            logger.info(f"Estimated input tokens: {estimated_tokens}")
            
            # Call GPT-5-mini with structured output
            for attempt in range(self.max_retries):
                try:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a data extraction specialist. Return ONLY valid JSON."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        temperature=self.temperature,  # MUST be 1 for GPT-5-mini
                        max_completion_tokens=self.max_tokens,
                        response_format={"type": "json_object"}
                    )
                    
                    metrics.api_calls += 1
                    metrics.total_tokens_used = response.usage.total_tokens if response.usage else estimated_tokens
                    
                    # Parse response
                    raw_response = response.choices[0].message.content
                    extracted_data = json.loads(raw_response)
                    
                    # Handle both array and object responses
                    if isinstance(extracted_data, dict) and "emails" in extracted_data:
                        email_results = extracted_data["emails"]
                    elif isinstance(extracted_data, list):
                        email_results = extracted_data
                    else:
                        raise ValueError("Invalid response format from GPT-5-mini")
                    
                    logger.info(f"Successfully extracted {len(email_results)} email results")
                    break
                    
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error on attempt {attempt + 1}: {e}")
                    if attempt == self.max_retries - 1:
                        raise
                    await asyncio.sleep(self.retry_delay_seconds)
                except Exception as e:
                    logger.error(f"API call error on attempt {attempt + 1}: {e}")
                    if attempt == self.max_retries - 1:
                        raise
                    await asyncio.sleep(self.retry_delay_seconds)
            
            # Process each extracted result
            for i, email_data in enumerate(email_results):
                try:
                    # Get original email
                    email_index = email_data.get("email_index", i)
                    if email_index >= len(batch_message.emails):
                        logger.warning(f"Invalid email index {email_index}, using {i}")
                        email_index = min(i, len(batch_message.emails) - 1)
                    
                    original_email = batch_message.emails[email_index]
                    
                    # Create ExtractedData object
                    extracted = ExtractedData(
                        candidate_name=email_data.get("candidate_name"),
                        job_title=email_data.get("job_title"),
                        location=email_data.get("location"),
                        company_name=email_data.get("company_name"),
                        referrer_name=email_data.get("referrer_name"),
                        website=email_data.get("website"),
                        phone=email_data.get("phone"),
                        industry=email_data.get("industry")
                    )
                    
                    # Apply business rules
                    processed_data = self.business_rules.process_data(
                        extracted.model_dump(),
                        original_email.get("body", ""),
                        original_email.get("sender_email", ""),
                        original_email.get("subject", "")
                    )
                    enhanced_data = ExtractedData(**processed_data)
                    
                    # Check for duplicates if PostgreSQL is available
                    is_duplicate = False
                    if self.postgres_client:
                        is_duplicate = await self.postgres_client.check_duplicate(
                            original_email.get("sender_email"),
                            enhanced_data.candidate_name
                        )
                    
                    # Process attachments
                    attachment_urls = []
                    if original_email.get("attachments"):
                        for attachment in original_email["attachments"]:
                            url = await self.blob_storage.upload_attachment(
                                attachment.get("filename"),
                                attachment.get("content"),
                                attachment.get("content_type")
                            )
                            if url:
                                attachment_urls.append(url)
                    
                    # Create Zoho records
                    zoho_result = await self.zoho_client.create_or_update_records(
                        enhanced_data,
                        original_email.get("sender_email"),
                        attachment_urls,
                        is_duplicate
                    )
                    
                    # Store comprehensive email processing history
                    if self.postgres_client:
                        try:
                            # Extract email body hash for deduplication
                            import hashlib
                            email_body = original_email.get("body", "")
                            email_body_hash = hashlib.md5(email_body.encode('utf-8')).hexdigest() if email_body else None
                            
                            # Prepare comprehensive processing data
                            processing_data = {
                                'internet_message_id': original_email.get('internet_message_id'),
                                'sender_email': original_email.get("sender_email"),
                                'reply_to_email': original_email.get('reply_to'),
                                'primary_email': zoho_result.get("primary_email") or original_email.get("sender_email"),
                                'subject': original_email.get("subject"),
                                'zoho_deal_id': zoho_result.get("deal_id"),
                                'zoho_account_id': zoho_result.get("account_id"),
                                'zoho_contact_id': zoho_result.get("contact_id"),
                                'deal_name': zoho_result.get("deal_name"),
                                'company_name': enhanced_data.company_name,
                                'contact_name': enhanced_data.candidate_name,
                                'processing_status': 'success' if not is_duplicate else 'duplicate_found',
                                'error_message': None,
                                'raw_extracted_data': enhanced_data.model_dump() if hasattr(enhanced_data, 'model_dump') else enhanced_data.__dict__,
                                'email_body_hash': email_body_hash
                            }
                            
                            # Store processing record
                            processing_id = await self.postgres_client.store_email_processing(processing_data)
                            logger.info(f"Stored batch email processing record with ID: {processing_id}")
                            
                        except Exception as storage_error:
                            logger.warning(f"Failed to store batch email processing history: {storage_error}")
                            # Fallback to basic storage
                            if not is_duplicate:
                                try:
                                    await self.postgres_client.store_processed_email(
                                        original_email.get("sender_email"),
                                        enhanced_data.candidate_name,
                                        zoho_result["deal_id"]
                                    )
                                except Exception as fallback_error:
                                    logger.warning(f"Fallback storage also failed: {fallback_error}")
                                    metrics.errors.append(f"Storage failed: {fallback_error}")
                    
                    results.append({
                        "email_index": email_index,
                        "status": "success",
                        "zoho_result": zoho_result,
                        "was_duplicate": is_duplicate
                    })
                    
                    metrics.processed_emails += 1
                    
                    # Update progress if callback provided
                    if progress_callback:
                        await progress_callback(
                            batch_message.batch_id,
                            metrics.processed_emails,
                            batch_message.total_count
                        )
                    
                except Exception as e:
                    logger.error(f"Error processing email {i}: {e}")
                    
                    # Store failed processing record
                    if self.postgres_client:
                        try:
                            email_index = email_data.get("email_index", i) if 'email_data' in locals() else i
                            if email_index < len(batch_message.emails):
                                failed_email = batch_message.emails[email_index]
                                
                                # Extract email body hash for failed record
                                import hashlib
                                email_body = failed_email.get("body", "")
                                email_body_hash = hashlib.md5(email_body.encode('utf-8')).hexdigest() if email_body else None
                                
                                # Store failed processing record
                                processing_data = {
                                    'internet_message_id': failed_email.get('internet_message_id'),
                                    'sender_email': failed_email.get("sender_email"),
                                    'reply_to_email': failed_email.get('reply_to'),
                                    'primary_email': failed_email.get("sender_email"),
                                    'subject': failed_email.get("subject"),
                                    'zoho_deal_id': None,
                                    'zoho_account_id': None,
                                    'zoho_contact_id': None,
                                    'deal_name': None,
                                    'company_name': None,
                                    'contact_name': None,
                                    'processing_status': 'failed',
                                    'error_message': str(e),
                                    'raw_extracted_data': {},
                                    'email_body_hash': email_body_hash
                                }
                                
                                await self.postgres_client.store_email_processing(processing_data)
                                logger.info(f"Stored failed batch email processing record for email {i}")
                                
                        except Exception as storage_error:
                            logger.warning(f"Failed to store failed email processing record: {storage_error}")
                    
                    errors.append({
                        "email_index": i,
                        "error": str(e)
                    })
                    metrics.failed_emails += 1
                    metrics.errors.append(str(e))
            
            # Calculate final metrics
            processing_time = time.time() - start_time
            metrics.processing_time_seconds = processing_time
            metrics.avg_time_per_email = processing_time / max(metrics.processed_emails, 1)
            
            # Determine overall status
            if metrics.failed_emails == 0:
                status = BatchStatus.COMPLETED
            elif metrics.processed_emails == 0:
                status = BatchStatus.FAILED
            else:
                status = BatchStatus.PARTIAL
            
            logger.info(f"Batch {batch_message.batch_id} completed: "
                       f"{metrics.processed_emails}/{metrics.total_emails} processed, "
                       f"{metrics.failed_emails} failed in {processing_time:.2f}s")
            
            # Log batch metrics to Application Insights
            if self.monitoring:
                try:
                    # Custom batch metrics
                    batch_metrics = {
                        "batch_id": batch_message.batch_id,
                        "total_emails": metrics.total_emails,
                        "processed_emails": metrics.processed_emails,
                        "failed_emails": metrics.failed_emails,
                        "success_rate": metrics.processed_emails / max(metrics.total_emails, 1),
                        "processing_time_seconds": processing_time,
                        "avg_time_per_email": metrics.avg_time_per_email,
                        "tokens_used": metrics.total_tokens_used,
                        "api_calls": metrics.api_calls,
                        "cost_estimate": self._calculate_batch_cost(metrics.total_tokens_used),
                        "status": status.value if hasattr(status, 'value') else str(status)
                    }
                    
                    # Track as custom event
                    await self.monitoring.track_custom_event(
                        "batch_processing_completed",
                        batch_metrics
                    )
                    
                    # Track performance metrics
                    await self.monitoring.track_performance_metric(
                        "batch_processing_time",
                        processing_time,
                        {"batch_size": metrics.total_emails}
                    )
                    
                    await self.monitoring.track_performance_metric(
                        "batch_success_rate", 
                        metrics.processed_emails / max(metrics.total_emails, 1),
                        {"batch_id": batch_message.batch_id}
                    )
                    
                    # Track cost metrics
                    if metrics.total_tokens_used > 0:
                        cost = self._calculate_batch_cost(metrics.total_tokens_used)
                        await self.monitoring.track_cost_metric(
                            self.model,
                            metrics.total_tokens_used,
                            cost,
                            custom_dimensions={"operation": "batch_processing", "batch_id": batch_message.batch_id}
                        )
                    
                    logger.info(f"Batch metrics logged to Application Insights for batch {batch_message.batch_id}")
                    
                except Exception as monitoring_error:
                    logger.warning(f"Failed to log batch metrics: {monitoring_error}")
            
            # Update batch status in database
            if self.postgres_client:
                try:
                    await self.postgres_client.update_batch_status(
                        batch_message.batch_id,
                        status=status.value if hasattr(status, 'value') else str(status).lower(),
                        processed_emails=metrics.processed_emails,
                        failed_emails=metrics.failed_emails,
                        processing_time_seconds=processing_time,
                        tokens_used=metrics.total_tokens_used,
                        estimated_cost=self._calculate_batch_cost(metrics.total_tokens_used),
                        metadata={
                            "model": self.model,
                            "api_calls": metrics.api_calls,
                            "success_rate": metrics.processed_emails / max(metrics.total_emails, 1),
                            "avg_time_per_email": metrics.avg_time_per_email
                        }
                    )
                    logger.info(f"Updated batch status in database for batch {batch_message.batch_id}")
                except Exception as e:
                    logger.warning(f"Failed to update batch status: {e}")
            
            return BatchProcessingResult(
                batch_id=batch_message.batch_id,
                status=status,
                processed_count=metrics.processed_emails,
                failed_count=metrics.failed_emails,
                total_count=metrics.total_emails,
                processing_time_seconds=processing_time,
                errors=errors,
                results=results
            )
            
        except Exception as e:
            logger.error(f"Critical error processing batch {batch_message.batch_id}: {e}")
            
            # Update batch status to failed
            if self.postgres_client:
                try:
                    await self.postgres_client.update_batch_status(
                        batch_message.batch_id,
                        status='failed',
                        failed_emails=batch_message.total_count,
                        processing_time_seconds=time.time() - start_time,
                        error_message=str(e)
                    )
                except Exception as status_error:
                    logger.warning(f"Failed to update batch status to failed: {status_error}")
            
            return BatchProcessingResult(
                batch_id=batch_message.batch_id,
                status=BatchStatus.FAILED,
                processed_count=0,
                failed_count=batch_message.total_count,
                total_count=batch_message.total_count,
                processing_time_seconds=time.time() - start_time,
                errors=[{"batch_error": str(e)}],
                results=[]
            )
    
    async def process_from_queue(
        self,
        max_batches: int = 1,
        progress_callback: Optional[callable] = None
    ) -> List[BatchProcessingResult]:
        """
        Process batches from Service Bus queue
        
        Args:
            max_batches: Maximum number of batches to process
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of BatchProcessingResult objects
        """
        if not self.service_bus:
            raise ValueError("Service Bus manager not configured")
        
        results = []
        
        try:
            # Receive batches from queue
            batches = await self.service_bus.receive_batch(max_messages=max_batches)
            
            if not batches:
                logger.info("No batches available in queue")
                return results
            
            logger.info(f"Processing {len(batches)} batches from queue")
            
            # Process each batch
            for batch in batches:
                result = await self.process_batch(batch, progress_callback)
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing from queue: {e}")
            raise
    
    async def process_emails_optimized(
        self,
        emails: List[Dict[str, Any]],
        auto_batch: bool = True
    ) -> List[BatchProcessingResult]:
        """
        Process emails with optimal batching strategy
        
        Args:
            emails: List of email dictionaries
            auto_batch: Automatically determine optimal batch sizes
        
        Returns:
            List of processing results
        """
        if not self.service_bus:
            # Process directly without queuing
            batch_msg = EmailBatchMessage(
                batch_id=f"direct_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                emails=emails,
                total_count=len(emails),
                created_at=datetime.utcnow().isoformat()
            )
            result = await self.process_batch(batch_msg)
            return [result]
        
        # Use batch aggregator for optimal batching
        aggregator = await self.service_bus.create_batch_aggregator()
        batch_ids = []
        
        for email in emails:
            if not aggregator.add_email(email):
                # Batch is full, send it
                batch_id = await aggregator.flush()
                if batch_id:
                    batch_ids.append(batch_id)
                
                # Add email to new batch
                aggregator.add_email(email)
        
        # Flush remaining emails
        batch_id = await aggregator.flush()
        if batch_id:
            batch_ids.append(batch_id)
        
        logger.info(f"Created {len(batch_ids)} optimized batches for {len(emails)} emails")
        
        # Process all batches
        results = await self.process_from_queue(max_batches=len(batch_ids))
        
        return results
    
    def get_processing_stats(self, results: List[BatchProcessingResult]) -> Dict[str, Any]:
        """
        Calculate aggregate statistics from processing results
        
        Args:
            results: List of batch processing results
        
        Returns:
            Dictionary with aggregate statistics
        """
        total_emails = sum(r.total_count for r in results)
        processed_emails = sum(r.processed_count for r in results)
        failed_emails = sum(r.failed_count for r in results)
        total_time = sum(r.processing_time_seconds for r in results)
        
        stats = {
            "total_batches": len(results),
            "total_emails": total_emails,
            "processed_emails": processed_emails,
            "failed_emails": failed_emails,
            "success_rate": processed_emails / max(total_emails, 1),
            "total_processing_time": total_time,
            "avg_time_per_email": total_time / max(processed_emails, 1),
            "avg_batch_size": total_emails / max(len(results), 1),
            "batch_details": [
                {
                    "batch_id": r.batch_id,
                    "status": r.status.value,
                    "processed": r.processed_count,
                    "failed": r.failed_count,
                    "time": r.processing_time_seconds
                }
                for r in results
            ]
        }
        
        return stats


class BatchProcessingOrchestrator:
    """Orchestrate batch processing with monitoring and error recovery"""
    
    def __init__(
        self,
        processor: BatchEmailProcessor,
        service_bus: ServiceBusManager
    ):
        self.processor = processor
        self.service_bus = service_bus
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        
    async def start_processing_loop(
        self,
        poll_interval_seconds: int = 30,
        max_concurrent_batches: int = 3
    ):
        """
        Start continuous processing loop
        
        Args:
            poll_interval_seconds: How often to check for new batches
            max_concurrent_batches: Maximum concurrent batch processing
        """
        logger.info(f"Starting batch processing loop (poll interval: {poll_interval_seconds}s)")
        
        while True:
            try:
                # Check queue status
                status = await self.service_bus.get_queue_status()
                
                if status.get("message_count", 0) > 0:
                    # Process available batches
                    active_tasks = len([t for t in self.processing_tasks.values() if not t.done()])
                    
                    if active_tasks < max_concurrent_batches:
                        # Start new processing task
                        task = asyncio.create_task(
                            self.processor.process_from_queue(max_batches=1)
                        )
                        task_id = f"task_{datetime.utcnow().timestamp()}"
                        self.processing_tasks[task_id] = task
                        
                        logger.info(f"Started processing task {task_id}")
                
                # Clean up completed tasks
                completed = [tid for tid, task in self.processing_tasks.items() if task.done()]
                for task_id in completed:
                    result = await self.processing_tasks[task_id]
                    logger.info(f"Task {task_id} completed with {len(result)} batches")
                    del self.processing_tasks[task_id]
                
                # Process dead letter queue periodically
                if datetime.utcnow().second == 0:  # Once per minute
                    await self.service_bus.process_dead_letter_queue()
                
                await asyncio.sleep(poll_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(poll_interval_seconds)
    
    async def stop_processing(self):
        """Stop all processing tasks gracefully"""
        logger.info("Stopping batch processing...")
        
        # Cancel all active tasks
        for task_id, task in self.processing_tasks.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled task {task_id}")
        
        # Wait for tasks to complete
        if self.processing_tasks:
            await asyncio.gather(*self.processing_tasks.values(), return_exceptions=True)
        
        logger.info("Batch processing stopped")


class EnhancedBatchEmailProcessor(BatchEmailProcessor):
    """Enhanced batch processor with comprehensive learning integration"""
    
    async def _store_email_processing_comprehensive(
        self,
        original_email: Dict[str, Any],
        extracted_data: ExtractedData,
        zoho_result: Dict[str, Any],
        confidence_score: float,
        processing_time_ms: int,
        learning_context: Dict[str, Any]
    ):
        """Store comprehensive email processing data with learning metrics"""
        if not self.postgres_client:
            return
        
        try:
            import hashlib
            email_body = original_email.get("body", "")
            email_body_hash = hashlib.md5(email_body.encode('utf-8')).hexdigest() if email_body else None
            
            processing_data = {
                'internet_message_id': original_email.get('internet_message_id'),
                'sender_email': original_email.get("sender_email"),
                'reply_to_email': original_email.get('reply_to'),
                'primary_email': zoho_result.get("primary_email") or original_email.get("sender_email"),
                'subject': original_email.get("subject"),
                'zoho_deal_id': zoho_result.get("deal_id"),
                'zoho_account_id': zoho_result.get("account_id"),
                'zoho_contact_id': zoho_result.get("contact_id"),
                'deal_name': zoho_result.get("deal_name"),
                'company_name': extracted_data.company_name,
                'contact_name': extracted_data.candidate_name,
                'processing_status': 'batch_success',
                'error_message': None,
                'raw_extracted_data': extracted_data.model_dump(),
                'email_body_hash': email_body_hash,
                # Learning-specific fields
                'confidence_score': confidence_score,
                'processing_time_ms': processing_time_ms,
                'patterns_used': learning_context.get('patterns_applied', 0),
                'templates_used': learning_context.get('templates_used', 0),
                'learning_applied': bool(learning_context.get('patterns_applied', 0) > 0 or learning_context.get('templates_used', 0) > 0)
            }
            
            processing_id = await self.postgres_client.store_email_processing(processing_data)
            logger.debug(f"Stored comprehensive batch processing record with ID: {processing_id}")
            
        except Exception as e:
            logger.warning(f"Failed to store comprehensive processing data: {e}")
    
    async def _create_extraction_metric(
        self,
        email_domain: str,
        extracted_data: ExtractedData,
        confidence_score: float,
        processing_time_ms: int,
        learning_context: Dict[str, Any]
    ):
        """Create extraction metric for learning analytics"""
        if not self.analytics_service:
            return
        
        try:
            from app.learning_analytics import ExtractionMetric
            import uuid
            
            metric = ExtractionMetric(
                extraction_id=str(uuid.uuid4()),
                email_domain=email_domain,
                field_scores={
                    'candidate_name': confidence_score,
                    'job_title': confidence_score,
                    'location': confidence_score,
                    'company_name': confidence_score
                },
                overall_confidence=confidence_score,
                processing_time_ms=processing_time_ms,
                used_template=learning_context.get('templates_used', 0) > 0,
                used_corrections=learning_context.get('patterns_applied', 0) > 0,
                pattern_matches=learning_context.get('patterns_applied', 0)
            )
            
            await self.analytics_service.record_extraction_metric(metric)
            logger.debug(f"Recorded extraction metric for domain: {email_domain}")
            
        except Exception as e:
            logger.warning(f"Failed to create extraction metric: {e}")
    
    async def _store_batch_learning_insights(
        self,
        batch_id: str,
        metrics: ProcessingMetrics,
        learning_context: Dict[str, Any]
    ):
        """Store batch-level learning insights for continuous improvement"""
        if not self.analytics_service:
            return
        
        try:
            insights = {
                'batch_id': batch_id,
                'total_emails': metrics.total_emails,
                'success_rate': metrics.processed_emails / max(metrics.total_emails, 1),
                'avg_confidence': sum(metrics.confidence_scores) / max(len(metrics.confidence_scores), 1) if metrics.confidence_scores else 0.0,
                'patterns_effectiveness': learning_context.get('patterns_applied', 0) / max(metrics.total_emails, 1),
                'templates_effectiveness': learning_context.get('templates_used', 0) / max(metrics.total_emails, 1),
                'avg_processing_time': metrics.avg_time_per_email,
                'domain_distribution': learning_context.get('domain_insights', {}),
                'error_rate': metrics.failed_emails / max(metrics.total_emails, 1),
                'learning_applied_count': metrics.pattern_matches_used + metrics.templates_used
            }
            
            await self.analytics_service.store_batch_insights(batch_id, insights)
            logger.info(f"Stored batch learning insights for {batch_id}")
            
        except Exception as e:
            logger.warning(f"Failed to store batch learning insights: {e}")
    
    async def get_batch_learning_report(self, batch_ids: List[str]) -> Dict[str, Any]:
        """Generate learning effectiveness report for multiple batches"""
        if not self.analytics_service:
            return {"error": "Analytics service not available"}
        
        try:
            report = {
                "batch_count": len(batch_ids),
                "total_emails_analyzed": 0,
                "overall_success_rate": 0.0,
                "learning_impact": {
                    "patterns_usage": 0.0,
                    "templates_usage": 0.0,
                    "confidence_improvement": 0.0
                },
                "performance_trends": [],
                "domain_insights": {},
                "recommendations": []
            }
            
            # Aggregate data from all batches
            for batch_id in batch_ids:
                insights = await self.analytics_service.get_batch_insights(batch_id)
                if insights:
                    report["total_emails_analyzed"] += insights.get("total_emails", 0)
                    report["overall_success_rate"] += insights.get("success_rate", 0.0)
                    
                    # Track learning usage
                    report["learning_impact"]["patterns_usage"] += insights.get("patterns_effectiveness", 0.0)
                    report["learning_impact"]["templates_usage"] += insights.get("templates_effectiveness", 0.0)
                    
                    # Aggregate domain insights
                    for domain, count in insights.get("domain_distribution", {}).items():
                        if domain not in report["domain_insights"]:
                            report["domain_insights"][domain] = 0
                        report["domain_insights"][domain] += count
            
            # Calculate averages
            if len(batch_ids) > 0:
                report["overall_success_rate"] /= len(batch_ids)
                report["learning_impact"]["patterns_usage"] /= len(batch_ids)
                report["learning_impact"]["templates_usage"] /= len(batch_ids)
            
            # Generate recommendations
            if report["learning_impact"]["patterns_usage"] < 0.3:
                report["recommendations"].append("Consider expanding pattern matching rules for better accuracy")
            
            if report["overall_success_rate"] < 0.8:
                report["recommendations"].append("Review failed extractions to identify common issues")
            
            if len(report["domain_insights"]) > 0:
                top_domain = max(report["domain_insights"], key=report["domain_insights"].get)
                report["recommendations"].append(f"Focus learning improvements on {top_domain} domain")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate batch learning report: {e}")
            return {"error": str(e)}
    
    async def optimize_batch_processing(self) -> Dict[str, Any]:
        """Analyze processing patterns and suggest optimizations"""
        try:
            optimization_report = {
                "current_performance": {},
                "bottlenecks": [],
                "recommendations": [],
                "learning_effectiveness": {}
            }
            
            if self.analytics_service:
                # Get performance metrics
                performance = await self.analytics_service.get_performance_summary()
                optimization_report["current_performance"] = performance
                
                # Identify bottlenecks
                if performance.get("avg_processing_time", 0) > 2000:  # > 2 seconds
                    optimization_report["bottlenecks"].append("High processing time - consider prompt optimization")
                
                if performance.get("confidence_score", 0) < 0.7:
                    optimization_report["bottlenecks"].append("Low confidence scores - review extraction patterns")
                
                # Learning effectiveness analysis
                learning_stats = await self.analytics_service.get_learning_effectiveness()
                optimization_report["learning_effectiveness"] = learning_stats
                
                if learning_stats.get("pattern_hit_rate", 0) < 0.4:
                    optimization_report["recommendations"].append("Expand pattern library for better matching")
                
                if learning_stats.get("template_usage", 0) < 0.3:
                    optimization_report["recommendations"].append("Create more company-specific templates")
            
            # System-level optimizations
            if not self.search_manager:
                optimization_report["recommendations"].append("Enable Azure AI Search for better pattern matching")
            
            if not self.learning_service:
                optimization_report["recommendations"].append("Enable correction learning for continuous improvement")
            
            return optimization_report
            
        except Exception as e:
            logger.error(f"Failed to generate optimization report: {e}")
            return {"error": str(e)}


# Factory function for creating enhanced batch processors
def create_enhanced_batch_processor(
    openai_api_key: str = None,
    service_bus_manager: ServiceBusManager = None,
    zoho_client: ZohoIntegration = None,
    postgres_client: PostgreSQLClient = None,
    enable_learning: bool = True
) -> EnhancedBatchEmailProcessor:
    """
    Create an enhanced batch processor with learning integration
    
    Args:
        openai_api_key: OpenAI API key
        service_bus_manager: Service Bus manager instance
        zoho_client: Zoho API client
        postgres_client: PostgreSQL client
        enable_learning: Whether to enable learning features
    
    Returns:
        EnhancedBatchEmailProcessor instance
    """
    # Initialize learning services if enabled
    learning_service = None
    analytics_service = None
    search_manager = None
    
    if enable_learning:
        # Initialize search manager
        if os.getenv("AZURE_SEARCH_ENDPOINT"):
            try:
                search_manager = AzureAISearchManager()
            except Exception as e:
                logger.warning(f"Could not initialize search manager: {e}")
        
        # Initialize learning service
        if postgres_client:
            try:
                learning_service = CorrectionLearningService(
                    db_client=postgres_client,
                    use_azure_search=bool(search_manager)
                )
            except Exception as e:
                logger.warning(f"Could not initialize learning service: {e}")
        
        # Initialize analytics service
        try:
            analytics_service = LearningAnalytics(
                search_manager=search_manager,
                app_insights_key=os.getenv("APPINSIGHTS_INSTRUMENTATION_KEY")
            )
        except Exception as e:
            logger.warning(f"Could not initialize analytics service: {e}")
    
    return EnhancedBatchEmailProcessor(
        openai_api_key=openai_api_key,
        service_bus_manager=service_bus_manager,
        zoho_client=zoho_client,
        postgres_client=postgres_client,
        learning_service=learning_service,
        analytics_service=analytics_service,
        search_manager=search_manager
    )