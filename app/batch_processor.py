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


class BatchEmailProcessor:
    """Process multiple emails in batches using GPT-5-mini"""
    
    def __init__(
        self,
        openai_api_key: str = None,
        service_bus_manager: ServiceBusManager = None,
        zoho_client: ZohoIntegration = None,
        postgres_client: PostgreSQLClient = None
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
        
        # Blob storage for attachments
        self.blob_storage = AzureBlobStorage(
            connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            container_name=os.getenv("AZURE_CONTAINER_NAME", "email-attachments")
        )
        
        # Processing configuration
        self.max_retries = 3
        self.retry_delay_seconds = 5
        self.batch_timeout_seconds = 300  # 5 minutes per batch
        
        # GPT-5-mini configuration
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.temperature = 1  # CRITICAL: Must be 1 for GPT-5-mini
        self.max_tokens = 8000  # Conservative output limit
        
        logger.info(f"Batch processor initialized with model: {self.model}")
    
    def _create_batch_prompt(self, emails: List[Dict[str, Any]]) -> str:
        """
        Create optimized prompt for batch processing
        
        Args:
            emails: List of email dictionaries
        
        Returns:
            Formatted prompt string
        """
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
                        max_tokens=self.max_tokens,
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
                        original_email.get("sender_email", "")
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
                    
                    # Store in database for deduplication
                    if not is_duplicate and self.postgres_client:
                        await self.postgres_client.store_processed_email(
                            original_email.get("sender_email"),
                            enhanced_data.candidate_name,
                            zoho_result["deal_id"]
                        )
                    
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