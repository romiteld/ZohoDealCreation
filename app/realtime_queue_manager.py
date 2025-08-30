"""
Real-time Email Queue Manager with WebSocket Support
Manages email processing queue with live updates to Voice UI
"""

import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

# Configure logging
logger = logging.getLogger(__name__)

class EmailStatus(Enum):
    """Email processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    REJECTED = "rejected"

@dataclass
class QueueEmail:
    """Email in processing queue"""
    id: str
    from_address: str
    from_name: str
    subject: str
    body: str
    timestamp: str
    status: EmailStatus
    priority: str = "normal"
    user_id: Optional[str] = None
    extracted_data: Optional[Dict] = None
    error_message: Optional[str] = None
    processing_started_at: Optional[str] = None
    processing_completed_at: Optional[str] = None
    
    def to_dict(self):
        data = asdict(self)
        data['status'] = self.status.value
        return data

class RealTimeQueueManager:
    """Manages email queue with real-time WebSocket updates"""
    
    def __init__(self):
        # Email queue storage (in production, use Redis or database)
        self.email_queue: Dict[str, QueueEmail] = {}
        
        # WebSocket connections by user
        self.active_connections: Dict[str, List[WebSocket]] = {}
        
        # Queue processing statistics
        self.stats = {
            "total_emails": 0,
            "processed_emails": 0,
            "failed_emails": 0,
            "average_processing_time": 0.0,
            "last_updated": datetime.utcnow().isoformat()
        }
        
        # Background task for queue monitoring
        self.monitoring_task = None
        
    async def connect_websocket(self, websocket: WebSocket, user_id: str):
        """Connect a WebSocket for real-time updates"""
        try:
            await websocket.accept()
            
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            
            self.active_connections[user_id].append(websocket)
            logger.info(f"WebSocket connected for user {user_id}")
            
            # Send initial queue state
            await self.send_queue_update(user_id)
            
        except Exception as e:
            logger.error(f"WebSocket connection error for user {user_id}: {e}")
            raise

    async def disconnect_websocket(self, websocket: WebSocket, user_id: str):
        """Disconnect a WebSocket"""
        try:
            if user_id in self.active_connections:
                if websocket in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(websocket)
                
                # Clean up empty connection lists
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            logger.info(f"WebSocket disconnected for user {user_id}")
            
        except Exception as e:
            logger.error(f"WebSocket disconnection error: {e}")

    async def add_email_to_queue(self, email_data: Dict, user_id: str = None) -> str:
        """Add email to processing queue"""
        try:
            email_id = email_data.get('id', str(uuid.uuid4()))
            
            queue_email = QueueEmail(
                id=email_id,
                from_address=email_data.get('from_address', ''),
                from_name=email_data.get('from_name', ''),
                subject=email_data.get('subject', ''),
                body=email_data.get('body', ''),
                timestamp=email_data.get('timestamp', datetime.utcnow().isoformat()),
                status=EmailStatus.PENDING,
                priority=email_data.get('priority', 'normal'),
                user_id=user_id
            )
            
            self.email_queue[email_id] = queue_email
            self.stats["total_emails"] += 1
            self.stats["last_updated"] = datetime.utcnow().isoformat()
            
            logger.info(f"Added email {email_id} to queue for user {user_id}")
            
            # Notify all connected clients
            await self.broadcast_queue_update()
            
            return email_id
            
        except Exception as e:
            logger.error(f"Error adding email to queue: {e}")
            raise

    async def update_email_status(self, email_id: str, status: EmailStatus, 
                                extracted_data: Dict = None, error_message: str = None):
        """Update email processing status"""
        try:
            if email_id not in self.email_queue:
                logger.warning(f"Email {email_id} not found in queue")
                return False
            
            email = self.email_queue[email_id]
            old_status = email.status
            email.status = status
            
            if status == EmailStatus.PROCESSING:
                email.processing_started_at = datetime.utcnow().isoformat()
            elif status in [EmailStatus.PROCESSED, EmailStatus.FAILED, EmailStatus.REJECTED]:
                email.processing_completed_at = datetime.utcnow().isoformat()
                
                # Update statistics
                if status == EmailStatus.PROCESSED:
                    self.stats["processed_emails"] += 1
                elif status == EmailStatus.FAILED:
                    self.stats["failed_emails"] += 1
                
                # Calculate processing time
                if email.processing_started_at:
                    try:
                        start_time = datetime.fromisoformat(email.processing_started_at.replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(email.processing_completed_at.replace('Z', '+00:00'))
                        processing_time = (end_time - start_time).total_seconds()
                        
                        # Update rolling average
                        current_avg = self.stats["average_processing_time"]
                        processed_count = self.stats["processed_emails"] + self.stats["failed_emails"]
                        self.stats["average_processing_time"] = (
                            (current_avg * (processed_count - 1) + processing_time) / processed_count
                        )
                    except Exception as avg_error:
                        logger.warning(f"Error calculating processing time: {avg_error}")
            
            if extracted_data:
                email.extracted_data = extracted_data
            
            if error_message:
                email.error_message = error_message
            
            self.stats["last_updated"] = datetime.utcnow().isoformat()
            
            logger.info(f"Updated email {email_id} status: {old_status.value} -> {status.value}")
            
            # Notify connected clients
            await self.broadcast_queue_update()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating email status: {e}")
            return False

    async def get_queue_state(self, user_id: str = None) -> Dict[str, Any]:
        """Get current queue state"""
        try:
            # Filter emails by user if specified
            if user_id:
                user_emails = {k: v for k, v in self.email_queue.items() 
                             if v.user_id == user_id or v.user_id is None}
            else:
                user_emails = self.email_queue
            
            # Convert to list format
            emails_list = [email.to_dict() for email in user_emails.values()]
            
            # Sort by timestamp (newest first)
            emails_list.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Calculate counts for this user's emails
            pending_count = sum(1 for email in user_emails.values() 
                              if email.status == EmailStatus.PENDING)
            processing_count = sum(1 for email in user_emails.values() 
                                 if email.status == EmailStatus.PROCESSING)
            processed_count = sum(1 for email in user_emails.values() 
                                if email.status == EmailStatus.PROCESSED)
            
            queue_state = {
                "emails": emails_list,
                "total_count": len(emails_list),
                "pending_count": pending_count,
                "processing_count": processing_count,
                "processed_count": processed_count,
                "failed_count": sum(1 for email in user_emails.values() 
                                  if email.status == EmailStatus.FAILED),
                "rejected_count": sum(1 for email in user_emails.values() 
                                    if email.status == EmailStatus.REJECTED),
                "stats": self.stats,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return queue_state
            
        except Exception as e:
            logger.error(f"Error getting queue state: {e}")
            return {"error": str(e)}

    async def send_queue_update(self, user_id: str):
        """Send queue update to specific user's WebSocket connections"""
        try:
            if user_id not in self.active_connections:
                return
            
            queue_state = await self.get_queue_state(user_id)
            message = {
                "type": "queue_update",
                "data": queue_state
            }
            
            # Send to all connections for this user
            disconnected_sockets = []
            for websocket in self.active_connections[user_id]:
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(message)
                    else:
                        disconnected_sockets.append(websocket)
                except Exception as send_error:
                    logger.warning(f"Error sending to WebSocket: {send_error}")
                    disconnected_sockets.append(websocket)
            
            # Clean up disconnected sockets
            for socket in disconnected_sockets:
                await self.disconnect_websocket(socket, user_id)
                
        except Exception as e:
            logger.error(f"Error sending queue update to user {user_id}: {e}")

    async def broadcast_queue_update(self):
        """Broadcast queue update to all connected users"""
        try:
            for user_id in list(self.active_connections.keys()):
                await self.send_queue_update(user_id)
        except Exception as e:
            logger.error(f"Error broadcasting queue update: {e}")

    async def send_email_notification(self, email_id: str, notification_type: str, data: Dict = None):
        """Send specific email notification"""
        try:
            if email_id not in self.email_queue:
                return
            
            email = self.email_queue[email_id]
            user_id = email.user_id
            
            if not user_id or user_id not in self.active_connections:
                return
            
            message = {
                "type": "email_notification",
                "notification_type": notification_type,
                "email_id": email_id,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send to user's connections
            for websocket in self.active_connections[user_id]:
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(message)
                except Exception as send_error:
                    logger.warning(f"Error sending notification: {send_error}")
                    
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")

    async def remove_email_from_queue(self, email_id: str) -> bool:
        """Remove email from queue"""
        try:
            if email_id in self.email_queue:
                del self.email_queue[email_id]
                logger.info(f"Removed email {email_id} from queue")
                
                # Notify clients
                await self.broadcast_queue_update()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing email from queue: {e}")
            return False

    async def cleanup_old_emails(self, hours_old: int = 24):
        """Clean up old processed/failed emails"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
            removed_count = 0
            
            emails_to_remove = []
            for email_id, email in self.email_queue.items():
                if email.status in [EmailStatus.PROCESSED, EmailStatus.FAILED, EmailStatus.REJECTED]:
                    email_time = datetime.fromisoformat(email.timestamp.replace('Z', '+00:00'))
                    if email_time < cutoff_time:
                        emails_to_remove.append(email_id)
            
            for email_id in emails_to_remove:
                if await self.remove_email_from_queue(email_id):
                    removed_count += 1
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old emails from queue")
            
            return removed_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old emails: {e}")
            return 0

    async def start_monitoring(self):
        """Start background queue monitoring"""
        try:
            if self.monitoring_task is None or self.monitoring_task.done():
                self.monitoring_task = asyncio.create_task(self._monitoring_loop())
                logger.info("Started queue monitoring task")
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")

    async def stop_monitoring(self):
        """Stop background queue monitoring"""
        try:
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                await self.monitoring_task
                logger.info("Stopped queue monitoring task")
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")

    async def _monitoring_loop(self):
        """Background monitoring loop"""
        try:
            while True:
                # Clean up old emails every hour
                await self.cleanup_old_emails()
                
                # Send periodic updates (every 30 seconds)
                await self.broadcast_queue_update()
                
                # Wait 30 seconds
                await asyncio.sleep(30)
                
        except asyncio.CancelledError:
            logger.info("Queue monitoring task cancelled")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")

# Global instance
_queue_manager = None

def get_queue_manager() -> RealTimeQueueManager:
    """Get global queue manager instance"""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = RealTimeQueueManager()
    return _queue_manager

# WebSocket endpoint handler
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time queue updates"""
    queue_manager = get_queue_manager()
    
    try:
        await queue_manager.connect_websocket(websocket, user_id)
        
        # Start monitoring if not already running
        await queue_manager.start_monitoring()
        
        # Keep connection alive
        while True:
            try:
                # Wait for messages from client
                message = await websocket.receive_json()
                
                # Handle client requests
                if message.get("type") == "request_update":
                    await queue_manager.send_queue_update(user_id)
                elif message.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                    
            except WebSocketDisconnect:
                break
            except Exception as msg_error:
                logger.warning(f"WebSocket message error: {msg_error}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        await queue_manager.disconnect_websocket(websocket, user_id)

# Test function
async def test_queue_manager():
    """Test function for queue manager"""
    manager = get_queue_manager()
    
    print("Testing Real-time Queue Manager")
    
    # Add test email
    test_email = {
        "id": "test_001",
        "from_address": "test@example.com",
        "from_name": "Test User",
        "subject": "Test Email",
        "body": "This is a test email",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    email_id = await manager.add_email_to_queue(test_email, "test_user")
    print(f"Added test email: {email_id}")
    
    # Update status
    await manager.update_email_status(email_id, EmailStatus.PROCESSING)
    print("Updated to processing")
    
    await manager.update_email_status(email_id, EmailStatus.PROCESSED, {"candidate_name": "John Doe"})
    print("Updated to processed")
    
    # Get queue state
    state = await manager.get_queue_state("test_user")
    print(f"Queue state: {len(state['emails'])} emails")
    
    print("✅ Queue Manager test completed")

if __name__ == "__main__":
    asyncio.run(test_queue_manager())