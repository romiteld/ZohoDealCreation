"""
Azure SignalR Service Manager for real-time streaming
Handles WebSocket connections and progressive result streaming
"""

import os
import json
import logging
import asyncio
import time
from typing import Dict, Any, Optional, AsyncGenerator, List
from datetime import datetime, timedelta
import jwt
import aiohttp
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class StreamEventType(Enum):
    """Types of streaming events"""
    CONNECTION_ESTABLISHED = "connection_established"
    EXTRACTION_START = "extraction_start"
    EXTRACTION_TOKEN = "extraction_token"
    EXTRACTION_FIELD = "extraction_field"
    RESEARCH_START = "research_start"
    RESEARCH_RESULT = "research_result"
    VALIDATION_START = "validation_start"
    VALIDATION_RESULT = "validation_result"
    ZOHO_START = "zoho_start"
    ZOHO_PROGRESS = "zoho_progress"
    ZOHO_COMPLETE = "zoho_complete"
    ERROR = "error"
    COMPLETE = "complete"


@dataclass
class StreamEvent:
    """Streaming event data structure"""
    type: StreamEventType
    data: Any
    timestamp: float = None
    sequence: int = 0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_json(self) -> str:
        """Convert to JSON for transmission"""
        return json.dumps({
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "sequence": self.sequence
        })


class SignalRConnectionManager:
    """Manages Azure SignalR Service connections"""
    
    def __init__(self, connection_string: str = None):
        """Initialize SignalR connection manager
        
        Args:
            connection_string: Azure SignalR connection string
        """
        self.connection_string = connection_string or os.getenv("AZURE_SIGNALR_CONNECTION_STRING", "")
        self.hub_name = "EmailProcessingHub"
        self.endpoint = None
        self.access_key = None
        
        # Parse connection string if provided
        if self.connection_string:
            self._parse_connection_string()
        
        # Track active connections
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.connection_queues: Dict[str, asyncio.Queue] = {}
        
        logger.info("SignalR Connection Manager initialized")
    
    def _parse_connection_string(self):
        """Parse Azure SignalR connection string"""
        parts = {}
        for part in self.connection_string.split(';'):
            if '=' in part:
                key, value = part.split('=', 1)
                parts[key] = value
        
        self.endpoint = parts.get('Endpoint', '').rstrip('/')
        self.access_key = parts.get('AccessKey', '')
        
        if not self.endpoint or not self.access_key:
            logger.warning("Invalid SignalR connection string, falling back to WebSocket/SSE")
    
    def generate_access_token(self, user_id: str, ttl_minutes: int = 60) -> str:
        """Generate JWT access token for SignalR
        
        Args:
            user_id: User identifier
            ttl_minutes: Token time-to-live in minutes
            
        Returns:
            JWT access token
        """
        if not self.access_key:
            return ""
        
        now = datetime.utcnow()
        payload = {
            "aud": f"{self.endpoint}/client/?hub={self.hub_name}",
            "iat": now,
            "exp": now + timedelta(minutes=ttl_minutes),
            "nameid": user_id
        }
        
        return jwt.encode(payload, self.access_key, algorithm="HS256")
    
    def get_negotiate_response(self, user_id: str) -> Dict[str, Any]:
        """Get SignalR negotiate response for client connection
        
        Args:
            user_id: User identifier
            
        Returns:
            Negotiate response with connection info
        """
        if self.endpoint and self.access_key:
            # Azure SignalR Service mode
            return {
                "url": f"{self.endpoint}/client/?hub={self.hub_name}",
                "accessToken": self.generate_access_token(user_id),
                "mode": "signalr"
            }
        else:
            # Fallback to direct WebSocket
            return {
                "url": "/ws/email-processing",
                "mode": "websocket"
            }
    
    async def register_connection(self, connection_id: str, websocket: Any):
        """Register a new WebSocket connection
        
        Args:
            connection_id: Unique connection identifier
            websocket: WebSocket connection object
        """
        self.connections[connection_id] = {
            "websocket": websocket,
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow()
        }
        self.connection_queues[connection_id] = asyncio.Queue()
        logger.info(f"Registered connection: {connection_id}")
    
    async def unregister_connection(self, connection_id: str):
        """Unregister a WebSocket connection
        
        Args:
            connection_id: Connection identifier to remove
        """
        if connection_id in self.connections:
            del self.connections[connection_id]
        if connection_id in self.connection_queues:
            del self.connection_queues[connection_id]
        logger.info(f"Unregistered connection: {connection_id}")
    
    async def send_event(self, connection_id: str, event: StreamEvent):
        """Send event to specific connection
        
        Args:
            connection_id: Target connection
            event: Event to send
        """
        if connection_id in self.connection_queues:
            await self.connection_queues[connection_id].put(event)
    
    async def broadcast_event(self, event: StreamEvent, exclude: List[str] = None):
        """Broadcast event to all connections
        
        Args:
            event: Event to broadcast
            exclude: List of connection IDs to exclude
        """
        exclude = exclude or []
        for conn_id in self.connections:
            if conn_id not in exclude:
                await self.send_event(conn_id, event)
    
    async def handle_connection(self, connection_id: str, websocket: Any):
        """Handle WebSocket connection lifecycle
        
        Args:
            connection_id: Connection identifier
            websocket: WebSocket connection
        """
        try:
            # Register connection
            await self.register_connection(connection_id, websocket)
            
            # Send connection established event
            await self.send_event(
                connection_id,
                StreamEvent(
                    type=StreamEventType.CONNECTION_ESTABLISHED,
                    data={"connection_id": connection_id}
                )
            )
            
            # Create tasks for sending and receiving
            send_task = asyncio.create_task(self._send_loop(connection_id, websocket))
            receive_task = asyncio.create_task(self._receive_loop(connection_id, websocket))
            ping_task = asyncio.create_task(self._ping_loop(connection_id, websocket))
            
            # Wait for any task to complete
            done, pending = await asyncio.wait(
                [send_task, receive_task, ping_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
            
        except Exception as e:
            logger.error(f"Connection error for {connection_id}: {e}")
        finally:
            await self.unregister_connection(connection_id)
    
    async def _send_loop(self, connection_id: str, websocket: Any):
        """Send events from queue to WebSocket
        
        Args:
            connection_id: Connection identifier
            websocket: WebSocket connection
        """
        queue = self.connection_queues[connection_id]
        
        while connection_id in self.connections:
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                
                # Send event
                await websocket.send_text(event.to_json())
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Send error for {connection_id}: {e}")
                break
    
    async def _receive_loop(self, connection_id: str, websocket: Any):
        """Receive messages from WebSocket
        
        Args:
            connection_id: Connection identifier
            websocket: WebSocket connection
        """
        while connection_id in self.connections:
            try:
                message = await websocket.receive_text()
                
                # Update last activity
                if connection_id in self.connections:
                    self.connections[connection_id]["last_ping"] = datetime.utcnow()
                
                # Handle client messages (pings, etc.)
                if message == "ping":
                    await websocket.send_text("pong")
                
            except Exception as e:
                logger.error(f"Receive error for {connection_id}: {e}")
                break
    
    async def _ping_loop(self, connection_id: str, websocket: Any):
        """Send periodic pings to keep connection alive
        
        Args:
            connection_id: Connection identifier
            websocket: WebSocket connection
        """
        while connection_id in self.connections:
            try:
                await asyncio.sleep(30)  # Ping every 30 seconds
                await websocket.send_text(json.dumps({"type": "ping"}))
            except Exception as e:
                logger.error(f"Ping error for {connection_id}: {e}")
                break


class StreamingEmailProcessor:
    """Processes emails with streaming updates"""
    
    def __init__(self, signalr_manager: SignalRConnectionManager):
        """Initialize streaming processor
        
        Args:
            signalr_manager: SignalR connection manager
        """
        self.signalr = signalr_manager
        self.sequence_counter = 0
    
    def _next_sequence(self) -> int:
        """Get next sequence number"""
        self.sequence_counter += 1
        return self.sequence_counter
    
    async def stream_extraction(
        self,
        connection_id: str,
        email_content: str,
        sender_domain: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream extraction process with progressive updates
        
        Args:
            connection_id: Target connection ID
            email_content: Email content to process
            sender_domain: Sender's domain
            
        Yields:
            Extraction progress updates
        """
        # Start extraction
        await self.signalr.send_event(
            connection_id,
            StreamEvent(
                type=StreamEventType.EXTRACTION_START,
                data={"message": "Starting AI extraction..."},
                sequence=self._next_sequence()
            )
        )
        
        # Import LangGraph components
        from app.langgraph_manager import EmailProcessingWorkflow, ExtractionOutput
        from openai import AsyncOpenAI
        
        # Initialize OpenAI client for streaming
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Prepare extraction prompt
        system_prompt = """You are a Senior Data Analyst specializing in recruitment email analysis.
        Extract key recruitment details from the email with extreme accuracy.
        
        Focus on identifying:
        1. Candidate name - the person being referred for the job
        2. Job title - the specific position mentioned
        3. Location - city and state if available
        4. Company name - any company explicitly mentioned
        5. Referrer name - ONLY if explicitly stated as "referred by"
        
        Return extracted fields as they are found."""
        
        user_prompt = f"""Analyze this recruitment email and extract key details:
        
        EMAIL CONTENT:
        {email_content}
        
        Extract and return information progressively as you find it."""
        
        try:
            # Stream extraction with OpenAI
            stream = await client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=True,
                temperature=1  # Required for GPT-5-mini
            )
            
            accumulated_text = ""
            field_buffer = {}
            last_field_update = time.time()
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    accumulated_text += token
                    
                    # Stream individual tokens for real-time display
                    await self.signalr.send_event(
                        connection_id,
                        StreamEvent(
                            type=StreamEventType.EXTRACTION_TOKEN,
                            data={"token": token},
                            sequence=self._next_sequence()
                        )
                    )
                    
                    # Parse for field updates (every 200ms or when complete field detected)
                    current_time = time.time()
                    if current_time - last_field_update > 0.2:
                        fields = self._parse_extraction_fields(accumulated_text)
                        
                        for field_name, field_value in fields.items():
                            if field_name not in field_buffer or field_buffer[field_name] != field_value:
                                field_buffer[field_name] = field_value
                                
                                await self.signalr.send_event(
                                    connection_id,
                                    StreamEvent(
                                        type=StreamEventType.EXTRACTION_FIELD,
                                        data={
                                            "field": field_name,
                                            "value": field_value,
                                            "confidence": 0.8  # Can be refined based on context
                                        },
                                        sequence=self._next_sequence()
                                    )
                                )
                                
                                yield {
                                    "field": field_name,
                                    "value": field_value,
                                    "timestamp": current_time
                                }
                        
                        last_field_update = current_time
            
            # Final field parsing
            final_fields = self._parse_extraction_fields(accumulated_text)
            
            # Return final extraction result
            yield {
                "status": "complete",
                "extraction": final_fields,
                "raw_text": accumulated_text
            }
            
        except Exception as e:
            logger.error(f"Streaming extraction error: {e}")
            await self.signalr.send_event(
                connection_id,
                StreamEvent(
                    type=StreamEventType.ERROR,
                    data={"error": str(e)},
                    sequence=self._next_sequence()
                )
            )
            yield {"status": "error", "error": str(e)}
    
    def _parse_extraction_fields(self, text: str) -> Dict[str, Any]:
        """Parse extraction fields from accumulated text
        
        Args:
            text: Accumulated response text
            
        Returns:
            Parsed field dictionary
        """
        fields = {}
        
        # Simple pattern matching for field extraction
        # This can be enhanced with more sophisticated parsing
        patterns = {
            "candidate_name": r"(?:candidate|name|person):\s*([A-Za-z\s]+)",
            "job_title": r"(?:position|title|role|job):\s*([A-Za-z\s]+)",
            "location": r"(?:location|city|area):\s*([A-Za-z\s,]+)",
            "company_name": r"(?:company|firm|organization):\s*([A-Za-z\s]+)",
            "referrer_name": r"(?:referrer|referred by):\s*([A-Za-z\s]+)"
        }
        
        import re
        for field_name, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fields[field_name] = match.group(1).strip()
        
        # Also try to parse JSON if present
        try:
            # Look for JSON structure in the text
            json_start = text.find('{')
            json_end = text.rfind('}')
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end + 1]
                parsed = json.loads(json_str)
                if isinstance(parsed, dict):
                    fields.update(parsed)
        except:
            pass
        
        return fields
    
    async def stream_research(
        self,
        connection_id: str,
        company_guess: Optional[str],
        sender_domain: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream company research process
        
        Args:
            connection_id: Target connection ID
            company_guess: Guessed company name
            sender_domain: Sender's domain
            
        Yields:
            Research progress updates
        """
        await self.signalr.send_event(
            connection_id,
            StreamEvent(
                type=StreamEventType.RESEARCH_START,
                data={
                    "message": "Researching company information...",
                    "domain": sender_domain
                },
                sequence=self._next_sequence()
            )
        )
        
        try:
            # Import research service
            from app.firecrawl_research import CompanyResearchService
            research_service = CompanyResearchService()
            
            # Start research with timeout
            research_task = asyncio.create_task(
                research_service.research_company(
                    email_domain=sender_domain,
                    company_guess=company_guess
                )
            )
            
            # Send progress updates while researching
            start_time = time.time()
            while not research_task.done():
                elapsed = time.time() - start_time
                
                if elapsed > 5:  # 5 second timeout
                    research_task.cancel()
                    break
                
                await self.signalr.send_event(
                    connection_id,
                    StreamEvent(
                        type=StreamEventType.RESEARCH_RESULT,
                        data={
                            "status": "searching",
                            "elapsed": elapsed
                        },
                        sequence=self._next_sequence()
                    )
                )
                
                await asyncio.sleep(0.5)
            
            if research_task.done():
                result = await research_task
                
                await self.signalr.send_event(
                    connection_id,
                    StreamEvent(
                        type=StreamEventType.RESEARCH_RESULT,
                        data={
                            "status": "complete",
                            "result": result
                        },
                        sequence=self._next_sequence()
                    )
                )
                
                yield result
            else:
                # Timeout - use fallback
                fallback_result = {
                    "company_name": company_guess or sender_domain.split('.')[0].title(),
                    "confidence": 0.3,
                    "source": "timeout_fallback"
                }
                
                yield fallback_result
                
        except Exception as e:
            logger.error(f"Research error: {e}")
            yield {
                "company_name": company_guess,
                "confidence": 0.1,
                "source": "error_fallback"
            }
    
    async def stream_validation(
        self,
        connection_id: str,
        extracted_data: Dict[str, Any],
        research_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Stream validation process
        
        Args:
            connection_id: Target connection ID
            extracted_data: Extracted information
            research_data: Research results
            
        Returns:
            Validated data
        """
        await self.signalr.send_event(
            connection_id,
            StreamEvent(
                type=StreamEventType.VALIDATION_START,
                data={"message": "Validating and cleaning data..."},
                sequence=self._next_sequence()
            )
        )
        
        # Merge and validate data
        validated = {
            "candidate_name": extracted_data.get("candidate_name"),
            "job_title": extracted_data.get("job_title"),
            "location": extracted_data.get("location"),
            "company_name": research_data.get("company_name") or extracted_data.get("company_guess"),
            "referrer_name": extracted_data.get("referrer_name"),
            "phone": extracted_data.get("phone"),
            "email": extracted_data.get("email")
        }
        
        # Clean and standardize
        for key, value in validated.items():
            if value and isinstance(value, str):
                validated[key] = value.strip()
                if key in ['candidate_name', 'referrer_name', 'company_name']:
                    validated[key] = ' '.join(word.capitalize() for word in value.split())
        
        await self.signalr.send_event(
            connection_id,
            StreamEvent(
                type=StreamEventType.VALIDATION_RESULT,
                data=validated,
                sequence=self._next_sequence()
            )
        )
        
        return validated
    
    async def process_email_streaming(
        self,
        connection_id: str,
        email_content: str,
        sender_email: str
    ) -> Dict[str, Any]:
        """Process email with full streaming support
        
        Args:
            connection_id: Target connection ID
            email_content: Email body content
            sender_email: Sender's email address
            
        Returns:
            Processing result
        """
        self.sequence_counter = 0
        sender_domain = sender_email.split('@')[1] if '@' in sender_email else 'unknown.com'
        
        try:
            # Stream extraction
            extraction_result = {}
            async for update in self.stream_extraction(connection_id, email_content, sender_domain):
                if update.get("status") == "complete":
                    extraction_result = update.get("extraction", {})
                elif update.get("status") == "error":
                    raise Exception(update.get("error"))
            
            # Stream research
            research_result = {}
            async for update in self.stream_research(
                connection_id,
                extraction_result.get("company_guess"),
                sender_domain
            ):
                research_result = update
            
            # Stream validation
            validated_data = await self.stream_validation(
                connection_id,
                extraction_result,
                research_result
            )
            
            # Send completion event
            await self.signalr.send_event(
                connection_id,
                StreamEvent(
                    type=StreamEventType.COMPLETE,
                    data={
                        "message": "Processing complete",
                        "result": validated_data
                    },
                    sequence=self._next_sequence()
                )
            )
            
            return validated_data
            
        except Exception as e:
            logger.error(f"Streaming processing error: {e}")
            await self.signalr.send_event(
                connection_id,
                StreamEvent(
                    type=StreamEventType.ERROR,
                    data={"error": str(e)},
                    sequence=self._next_sequence()
                )
            )
            raise


# Singleton instances
_signalr_manager: Optional[SignalRConnectionManager] = None
_streaming_processor: Optional[StreamingEmailProcessor] = None


def get_signalr_manager() -> SignalRConnectionManager:
    """Get or create SignalR manager instance"""
    global _signalr_manager
    if _signalr_manager is None:
        _signalr_manager = SignalRConnectionManager()
    return _signalr_manager


def get_streaming_processor() -> StreamingEmailProcessor:
    """Get or create streaming processor instance"""
    global _streaming_processor
    if _streaming_processor is None:
        _streaming_processor = StreamingEmailProcessor(get_signalr_manager())
    return _streaming_processor