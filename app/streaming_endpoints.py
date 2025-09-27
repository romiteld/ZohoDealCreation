"""
FastAPI streaming endpoints for real-time email processing
Supports WebSocket, Server-Sent Events (SSE), and Azure SignalR
"""

import os
import json
import logging
import asyncio
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, Header, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.models import EmailPayload as EmailRequest, ExtractedData
from app.signalr_manager import (
    get_signalr_manager,
    get_streaming_processor,
    StreamEvent,
    StreamEventType
)

logger = logging.getLogger(__name__)

# Create router for streaming endpoints
router = APIRouter(prefix="/stream", tags=["streaming"])

# API Key Authentication
API_KEY = os.getenv("API_KEY", "your-secure-api-key-here")


async def verify_api_key(x_api_key: str = Header(None), api_key: str = Query(None)):
    """Verify API key from header or query parameter"""
    key = x_api_key or api_key
    if not key or key != API_KEY:
        logger.warning("Invalid API key attempt in streaming endpoint")
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return key


@router.get("/negotiate")
async def negotiate(
    request: Request,
    _: str = Depends(verify_api_key)
) -> Dict[str, Any]:
    """SignalR negotiate endpoint for client connection setup
    
    Returns connection information for SignalR or WebSocket fallback
    """
    # Generate unique user ID for this session
    user_id = str(uuid.uuid4())
    
    # Get SignalR manager
    signalr_manager = get_signalr_manager()
    
    # Get negotiate response
    negotiate_response = signalr_manager.get_negotiate_response(user_id)
    
    # Add additional metadata
    negotiate_response.update({
        "userId": user_id,
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "streaming": True,
            "websocket": True,
            "sse": True,
            "signalr": negotiate_response.get("mode") == "signalr"
        }
    })
    
    logger.info(f"Negotiate request for user {user_id}, mode: {negotiate_response.get('mode')}")
    
    return negotiate_response


@router.websocket("/ws/email-processing")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time email processing
    
    Handles bidirectional communication for streaming extraction results
    """
    connection_id = str(uuid.uuid4())
    signalr_manager = get_signalr_manager()
    streaming_processor = get_streaming_processor()
    
    try:
        # Accept WebSocket connection
        await websocket.accept()
        logger.info(f"WebSocket connection accepted: {connection_id}")
        
        # Start connection handler in background
        handler_task = asyncio.create_task(
            signalr_manager.handle_connection(connection_id, websocket)
        )
        
        # Listen for email processing requests
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "process_email":
                    # Extract email data
                    email_data = message.get("data", {})
                    
                    # Start streaming processing
                    asyncio.create_task(
                        streaming_processor.process_email_streaming(
                            connection_id=connection_id,
                            email_content=email_data.get("body", ""),
                            sender_email=email_data.get("sender_email", "")
                        )
                    )
                    
                elif message.get("type") == "ping":
                    # Respond to ping
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
                elif message.get("type") == "close":
                    # Client requested close
                    break
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
                break
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from WebSocket {connection_id}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": {"message": "Invalid JSON format"}
                }))
            except Exception as e:
                logger.error(f"WebSocket error for {connection_id}: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": {"message": str(e)}
                }))
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        # Clean up
        handler_task.cancel()
        await signalr_manager.unregister_connection(connection_id)
        logger.info(f"WebSocket connection closed: {connection_id}")


@router.post("/sse/process-email")
async def sse_process_email(
    request: EmailRequest,
    req: Request,
    _: str = Depends(verify_api_key)
):
    """Server-Sent Events endpoint for streaming email processing
    
    Fallback option when WebSocket is not available
    """
    connection_id = str(uuid.uuid4())
    signalr_manager = get_signalr_manager()
    streaming_processor = get_streaming_processor()
    
    async def event_generator():
        """Generate SSE events"""
        try:
            # Create a queue for this connection
            event_queue = asyncio.Queue()
            signalr_manager.connection_queues[connection_id] = event_queue
            
            # Start processing in background
            process_task = asyncio.create_task(
                streaming_processor.process_email_streaming(
                    connection_id=connection_id,
                    email_content=request.body,
                    sender_email=request.sender_email
                )
            )
            
            # Stream events from queue
            while True:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    
                    # Format as SSE
                    yield {
                        "event": event.type.value,
                        "data": json.dumps({
                            "data": event.data,
                            "timestamp": event.timestamp,
                            "sequence": event.sequence
                        })
                    }
                    
                    # Check if processing is complete
                    if event.type in [StreamEventType.COMPLETE, StreamEventType.ERROR]:
                        break
                        
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {
                        "event": "ping",
                        "data": json.dumps({"timestamp": datetime.utcnow().isoformat()})
                    }
                    
                # Check if client disconnected
                if await req.is_disconnected():
                    break
                    
        except Exception as e:
            logger.error(f"SSE generator error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
        finally:
            # Clean up
            process_task.cancel()
            if connection_id in signalr_manager.connection_queues:
                del signalr_manager.connection_queues[connection_id]
    
    return EventSourceResponse(event_generator())


@router.post("/batch/process-email")
async def batch_process_email(
    request: EmailRequest,
    req: Request,
    _: str = Depends(verify_api_key),
    stream_chunks: bool = Query(True, description="Stream response in chunks")
):
    """Batch processing endpoint with optional chunked streaming
    
    Process email and return results in chunks for progressive display
    """
    connection_id = str(uuid.uuid4())
    streaming_processor = get_streaming_processor()
    
    if not stream_chunks:
        # Non-streaming mode - process and return complete result
        try:
            result = await streaming_processor.process_email_streaming(
                connection_id=connection_id,
                email_content=request.body,
                sender_email=request.sender_email
            )
            
            return {
                "status": "success",
                "data": result,
                "processing_time": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def chunk_generator():
        """Generate response chunks"""
        try:
            # Track events
            events = []
            signalr_manager = get_signalr_manager()
            event_queue = asyncio.Queue()
            signalr_manager.connection_queues[connection_id] = event_queue
            
            # Start processing
            process_task = asyncio.create_task(
                streaming_processor.process_email_streaming(
                    connection_id=connection_id,
                    email_content=request.body,
                    sender_email=request.sender_email
                )
            )
            
            # Collect events and yield as chunks
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=5.0)
                    events.append(event)
                    
                    # Yield chunk
                    chunk = json.dumps({
                        "type": event.type.value,
                        "data": event.data,
                        "sequence": event.sequence
                    }) + "\n"
                    
                    yield chunk.encode('utf-8')
                    
                    # Check if complete
                    if event.type in [StreamEventType.COMPLETE, StreamEventType.ERROR]:
                        break
                        
                except asyncio.TimeoutError:
                    # Timeout - check if still processing
                    if process_task.done():
                        break
                    continue
                    
        except Exception as e:
            logger.error(f"Chunk generator error: {e}")
            yield json.dumps({"type": "error", "error": str(e)}).encode('utf-8')
        finally:
            # Clean up
            process_task.cancel()
            if connection_id in signalr_manager.connection_queues:
                del signalr_manager.connection_queues[connection_id]
    
    return StreamingResponse(
        chunk_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/health")
async def streaming_health():
    """Health check for streaming services"""
    signalr_manager = get_signalr_manager()
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(signalr_manager.connections),
        "signalr_configured": bool(signalr_manager.endpoint),
        "features": {
            "websocket": True,
            "sse": True,
            "signalr": bool(signalr_manager.endpoint),
            "batch_streaming": True
        }
    }


@router.get("/metrics")
async def streaming_metrics(_: str = Depends(verify_api_key)):
    """Get streaming service metrics"""
    signalr_manager = get_signalr_manager()
    
    # Calculate connection statistics
    connections = []
    for conn_id, conn_info in signalr_manager.connections.items():
        connections.append({
            "id": conn_id,
            "connected_at": conn_info["connected_at"].isoformat(),
            "last_ping": conn_info["last_ping"].isoformat(),
            "duration_seconds": (datetime.utcnow() - conn_info["connected_at"]).total_seconds()
        })
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(connections),
        "connections": connections,
        "total_queued_events": sum(
            q.qsize() for q in signalr_manager.connection_queues.values()
        )
    }


# WebSocket connection manager for testing
@router.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    """Test WebSocket endpoint for debugging"""
    await websocket.accept()
    
    try:
        # Send test messages
        test_sequence = [
            StreamEvent(StreamEventType.CONNECTION_ESTABLISHED, {"message": "Connected"}),
            StreamEvent(StreamEventType.EXTRACTION_START, {"message": "Starting extraction"}),
            StreamEvent(StreamEventType.EXTRACTION_FIELD, {"field": "candidate_name", "value": "John Doe"}),
            StreamEvent(StreamEventType.EXTRACTION_FIELD, {"field": "job_title", "value": "Software Engineer"}),
            StreamEvent(StreamEventType.RESEARCH_START, {"message": "Researching company"}),
            StreamEvent(StreamEventType.RESEARCH_RESULT, {"company_name": "Tech Corp", "confidence": 0.9}),
            StreamEvent(StreamEventType.VALIDATION_START, {"message": "Validating data"}),
            StreamEvent(StreamEventType.VALIDATION_RESULT, {"status": "valid"}),
            StreamEvent(StreamEventType.COMPLETE, {"message": "Processing complete"})
        ]
        
        for i, event in enumerate(test_sequence):
            event.sequence = i + 1
            await websocket.send_text(event.to_json())
            await asyncio.sleep(0.5)  # Simulate processing delay
        
        # Keep connection open for further testing
        while True:
            data = await websocket.receive_text()
            if data == "close":
                break
            # Echo back
            await websocket.send_text(f"Echo: {data}")
            
    except WebSocketDisconnect:
        logger.info("Test WebSocket disconnected")
    except Exception as e:
        logger.error(f"Test WebSocket error: {e}")
        
        
# Export router for inclusion in main app
__all__ = ['router']