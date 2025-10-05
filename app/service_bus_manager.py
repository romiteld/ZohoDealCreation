"""
Azure Service Bus Manager for batch email processing
Handles queue management, message batching, and dead letter queue processing
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from azure.servicebus.aio import ServiceBusClient, ServiceBusReceiver, ServiceBusSender
from azure.servicebus import ServiceBusMessage, ServiceBusMessageBatch
from azure.servicebus.exceptions import ServiceBusError, MessageAlreadySettled
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


class BatchStatus(Enum):
    """Batch processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class EmailBatchMessage:
    """Structure for batch email messages"""
    batch_id: str
    emails: List[Dict[str, Any]]
    total_count: int
    created_at: str
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    
    def to_json(self) -> str:
        """Convert to JSON for Service Bus message"""
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, json_str: str) -> 'EmailBatchMessage':
        """Create from JSON string"""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class BatchProcessingResult:
    """Result of batch processing"""
    batch_id: str
    status: BatchStatus
    processed_count: int
    failed_count: int
    total_count: int
    processing_time_seconds: float
    errors: List[Dict[str, Any]]
    results: List[Dict[str, Any]]


class ServiceBusManager:
    """Azure Service Bus client for email batch processing"""
    
    def __init__(self, connection_string: str = None, queue_name: str = None):
        """
        Initialize Service Bus Manager
        
        Args:
            connection_string: Azure Service Bus connection string
            queue_name: Name of the main processing queue
        """
        self.connection_string = connection_string or os.getenv("SERVICE_BUS_CONNECTION_STRING") or os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
        self.queue_name = queue_name or os.getenv("SERVICE_BUS_QUEUE_NAME") or os.getenv("AZURE_SERVICE_BUS_QUEUE_NAME", "email-batch-queue")
        self.dead_letter_queue = f"{self.queue_name}/$deadletterqueue"
        
        if not self.connection_string:
            raise ValueError("Service Bus connection string is required")
        
        # Batch configuration
        self.max_batch_size = int(os.getenv("MAX_BATCH_SIZE", "50"))
        self.batch_timeout_seconds = int(os.getenv("BATCH_TIMEOUT_SECONDS", "30"))
        self.max_message_size_kb = int(os.getenv("MAX_MESSAGE_SIZE_KB", "256"))
        
        # Initialize client (will be created asynchronously)
        self._client: Optional[ServiceBusClient] = None
        self._sender: Optional[ServiceBusSender] = None
        self._receiver: Optional[ServiceBusReceiver] = None
        
        logger.info(f"Service Bus Manager initialized for queue: {self.queue_name}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def connect(self):
        """Establish connection to Service Bus"""
        try:
            self._client = ServiceBusClient.from_connection_string(
                self.connection_string,
                logging_enable=True
            )
            self._sender = self._client.get_queue_sender(queue_name=self.queue_name)
            self._receiver = self._client.get_queue_receiver(
                queue_name=self.queue_name,
                max_wait_time=self.batch_timeout_seconds
            )
            logger.info("Connected to Azure Service Bus")
        except Exception as e:
            logger.error(f"Failed to connect to Service Bus: {e}")
            raise
    
    async def close(self):
        """Close Service Bus connections"""
        try:
            if self._sender:
                await self._sender.close()
            if self._receiver:
                await self._receiver.close()
            if self._client:
                await self._client.close()
            logger.info("Service Bus connections closed")
        except Exception as e:
            logger.error(f"Error closing Service Bus connections: {e}")
    
    async def send_batch(self, emails: List[Dict[str, Any]], priority: int = 0) -> str:
        """
        Send a batch of emails to the queue
        
        Args:
            emails: List of email dictionaries to process
            priority: Message priority (0-9, higher = more priority)
        
        Returns:
            batch_id: Unique identifier for the batch
        """
        if not self._sender:
            await self.connect()
        
        batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{len(emails)}"
        
        try:
            # Create batch message
            batch_msg = EmailBatchMessage(
                batch_id=batch_id,
                emails=emails,
                total_count=len(emails),
                created_at=datetime.utcnow().isoformat(),
                priority=priority
            )
            
            # Check message size
            message_json = batch_msg.to_json()
            message_size_kb = len(message_json.encode()) / 1024
            
            if message_size_kb > self.max_message_size_kb:
                # Split into smaller batches if too large
                logger.warning(f"Batch {batch_id} too large ({message_size_kb:.2f}KB), splitting...")
                return await self._send_split_batches(emails, priority)
            
            # Create Service Bus message
            service_bus_msg = ServiceBusMessage(
                body=message_json,
                content_type="application/json",
                subject=f"email_batch_{len(emails)}",
                application_properties={
                    "batch_id": batch_id,
                    "email_count": len(emails),
                    "priority": priority
                },
                time_to_live=timedelta(hours=24)
            )
            
            # Send message
            await self._sender.send_messages(service_bus_msg)
            logger.info(f"Sent batch {batch_id} with {len(emails)} emails to queue")
            
            return batch_id
            
        except ServiceBusError as e:
            logger.error(f"Failed to send batch to Service Bus: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending batch: {e}")
            raise
    
    async def _send_split_batches(self, emails: List[Dict[str, Any]], priority: int) -> str:
        """Split large batch into smaller ones"""
        batch_ids = []
        chunk_size = self.max_batch_size // 2  # Use half the max size for safety
        
        for i in range(0, len(emails), chunk_size):
            chunk = emails[i:i + chunk_size]
            batch_id = await self.send_batch(chunk, priority)
            batch_ids.append(batch_id)
        
        # Return combined batch ID
        return f"split_{','.join(batch_ids)}"
    
    async def receive_batch(self, max_messages: int = None) -> List[EmailBatchMessage]:
        """
        Receive a batch of messages from the queue
        
        Args:
            max_messages: Maximum number of messages to receive
        
        Returns:
            List of EmailBatchMessage objects
        """
        if not self._receiver:
            await self.connect()
        
        max_messages = max_messages or self.max_batch_size
        batches = []
        
        try:
            # Receive messages
            messages = await self._receiver.receive_messages(
                max_message_count=max_messages,
                max_wait_time=self.batch_timeout_seconds
            )
            
            for message in messages:
                try:
                    # Parse message
                    batch_msg = EmailBatchMessage.from_json(str(message))
                    batches.append(batch_msg)
                    
                    # Complete the message (remove from queue)
                    await self._receiver.complete_message(message)
                    logger.info(f"Received and completed batch {batch_msg.batch_id}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                    # Send to dead letter queue
                    await self._receiver.dead_letter_message(
                        message,
                        reason="InvalidFormat",
                        error_description=str(e)
                    )
                except MessageAlreadySettled:
                    logger.warning("Message already settled, skipping")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Abandon message for retry
                    await self._receiver.abandon_message(message)
            
            logger.info(f"Received {len(batches)} batches from queue")
            return batches
            
        except ServiceBusError as e:
            logger.error(f"Failed to receive messages from Service Bus: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error receiving messages: {e}")
            raise
    
    async def peek_messages(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        Peek at messages without removing them from queue
        
        Args:
            max_messages: Maximum number of messages to peek
        
        Returns:
            List of message dictionaries
        """
        if not self._receiver:
            await self.connect()
        
        try:
            messages = await self._receiver.peek_messages(max_message_count=max_messages)
            
            peeked_messages = []
            for message in messages:
                try:
                    batch_msg = EmailBatchMessage.from_json(str(message))
                    peeked_messages.append({
                        "batch_id": batch_msg.batch_id,
                        "email_count": batch_msg.total_count,
                        "created_at": batch_msg.created_at,
                        "priority": batch_msg.priority,
                        "retry_count": batch_msg.retry_count
                    })
                except Exception as e:
                    logger.error(f"Error parsing peeked message: {e}")
            
            return peeked_messages
            
        except Exception as e:
            logger.error(f"Error peeking messages: {e}")
            raise
    
    async def process_dead_letter_queue(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        Process messages from dead letter queue
        
        Args:
            max_messages: Maximum number of dead letter messages to process
        
        Returns:
            List of processed dead letter messages
        """
        try:
            # Create dead letter receiver
            dlq_receiver = self._client.get_queue_receiver(
                queue_name=self.dead_letter_queue,
                max_wait_time=5
            )
            
            dead_letters = []
            async with dlq_receiver:
                messages = await dlq_receiver.receive_messages(
                    max_message_count=max_messages,
                    max_wait_time=5
                )
                
                for message in messages:
                    try:
                        # Get dead letter info
                        dead_letter_info = {
                            "message_id": message.message_id,
                            "dead_letter_reason": message.dead_letter_reason,
                            "dead_letter_error_description": message.dead_letter_error_description,
                            "delivery_count": message.delivery_count
                        }
                        
                        # Try to parse the message
                        try:
                            batch_msg = EmailBatchMessage.from_json(str(message))
                            dead_letter_info["batch_id"] = batch_msg.batch_id
                            dead_letter_info["email_count"] = batch_msg.total_count
                            
                            # Check if we should retry
                            if batch_msg.retry_count < batch_msg.max_retries:
                                # Resend to main queue with incremented retry count
                                batch_msg.retry_count += 1
                                await self.send_batch(batch_msg.emails, batch_msg.priority)
                                logger.info(f"Retried batch {batch_msg.batch_id} (attempt {batch_msg.retry_count})")
                                dead_letter_info["action"] = "retried"
                            else:
                                logger.warning(f"Batch {batch_msg.batch_id} exceeded max retries")
                                dead_letter_info["action"] = "abandoned"
                        except Exception as e:
                            logger.error(f"Failed to parse dead letter message: {e}")
                            dead_letter_info["parse_error"] = str(e)
                            dead_letter_info["action"] = "failed"
                        
                        # Complete the dead letter message
                        await dlq_receiver.complete_message(message)
                        dead_letters.append(dead_letter_info)
                        
                    except Exception as e:
                        logger.error(f"Error processing dead letter message: {e}")
                        await dlq_receiver.abandon_message(message)
            
            logger.info(f"Processed {len(dead_letters)} dead letter messages")
            return dead_letters
            
        except Exception as e:
            logger.error(f"Error processing dead letter queue: {e}")
            raise
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status and metrics
        
        Returns:
            Dictionary with queue metrics
        """
        try:
            # Peek at messages to get queue depth
            messages = await self.peek_messages(max_messages=100)
            
            # Calculate metrics
            total_emails = sum(msg.get("email_count", 0) for msg in messages)
            priority_counts = {}
            for msg in messages:
                priority = msg.get("priority", 0)
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            status = {
                "queue_name": self.queue_name,
                "message_count": len(messages),
                "total_emails": total_emails,
                "priority_distribution": priority_counts,
                "max_batch_size": self.max_batch_size,
                "batch_timeout_seconds": self.batch_timeout_seconds,
                "connected": self._client is not None
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {
                "queue_name": self.queue_name,
                "error": str(e),
                "connected": False
            }
    
    async def create_batch_aggregator(self) -> 'BatchAggregator':
        """
        Create a batch aggregator for intelligent batching
        
        Returns:
            BatchAggregator instance
        """
        return BatchAggregator(self)


class BatchAggregator:
    """Intelligent batch aggregation for optimal GPT-5-mini processing"""
    
    def __init__(self, service_bus_manager: ServiceBusManager):
        self.service_bus = service_bus_manager
        self.pending_emails: List[Dict[str, Any]] = []
        self.estimated_tokens = 0
        
        # GPT-5-mini constraints
        self.max_context_tokens = 400000  # 400K token limit
        self.avg_tokens_per_email = 500  # Conservative estimate
        self.buffer_tokens = 10000  # Reserve for system prompts and responses
        self.available_tokens = self.max_context_tokens - self.buffer_tokens
        
        # Batching strategy
        self.optimal_batch_size = min(
            50,  # Max 50 emails per batch
            self.available_tokens // self.avg_tokens_per_email
        )
        
        logger.info(f"Batch aggregator initialized with optimal size: {self.optimal_batch_size}")
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation)"""
        # Rough estimate: 1 token per 4 characters
        return len(text) // 4
    
    def can_add_email(self, email: Dict[str, Any]) -> bool:
        """Check if email can be added to current batch"""
        email_tokens = self.estimate_tokens(
            email.get("body", "") + 
            email.get("subject", "") + 
            str(email.get("attachments", []))
        )
        
        if len(self.pending_emails) >= self.optimal_batch_size:
            return False
        
        if self.estimated_tokens + email_tokens > self.available_tokens:
            return False
        
        return True
    
    def add_email(self, email: Dict[str, Any]) -> bool:
        """
        Add email to pending batch
        
        Args:
            email: Email dictionary to add
        
        Returns:
            True if added, False if batch is full
        """
        if not self.can_add_email(email):
            return False
        
        email_tokens = self.estimate_tokens(
            email.get("body", "") + 
            email.get("subject", "") + 
            str(email.get("attachments", []))
        )
        
        self.pending_emails.append(email)
        self.estimated_tokens += email_tokens
        
        logger.debug(f"Added email to batch. Current size: {len(self.pending_emails)}, "
                    f"Estimated tokens: {self.estimated_tokens}")
        
        return True
    
    def is_ready(self) -> bool:
        """Check if batch is ready for processing"""
        return len(self.pending_emails) >= self.optimal_batch_size
    
    def get_batch(self) -> List[Dict[str, Any]]:
        """Get current batch and reset aggregator"""
        batch = self.pending_emails.copy()
        self.pending_emails = []
        self.estimated_tokens = 0
        return batch
    
    async def flush(self, priority: int = 0) -> Optional[str]:
        """
        Flush pending emails to Service Bus
        
        Args:
            priority: Message priority
        
        Returns:
            batch_id if emails were sent, None otherwise
        """
        if not self.pending_emails:
            return None
        
        batch = self.get_batch()
        batch_id = await self.service_bus.send_batch(batch, priority)
        logger.info(f"Flushed batch {batch_id} with {len(batch)} emails")
        
        return batch_id