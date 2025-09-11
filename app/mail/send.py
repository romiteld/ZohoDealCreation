"""
TalentWell email delivery system with multiple provider support.
Supports Azure Communication Services Email, SendGrid, and SMTP fallback.
"""

import os
import logging
import smtplib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json

logger = logging.getLogger(__name__)

try:
    from azure.communication.email import EmailClient
    from azure.identity import DefaultAzureCredential
    AZURE_EMAIL_AVAILABLE = True
except ImportError:
    AZURE_EMAIL_AVAILABLE = False
    logger.warning("Azure Communication Services Email not available")

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    logger.warning("SendGrid not available")


@dataclass
class EmailMessage:
    """Email message structure for delivery."""
    to_addresses: List[str]
    subject: str
    html_body: str
    text_body: Optional[str] = None
    from_address: str = None  # Will be set from environment
    from_name: str = "TalentWell"
    reply_to: Optional[str] = None
    bcc_addresses: Optional[List[str]] = None
    
    def __post_init__(self):
        """Set defaults from environment variables after initialization."""
        if self.from_address is None:
            self.from_address = os.getenv('TALENTWELL_FROM_ADDRESS', 'DoNotReply@389fbf3b-307d-4882-af6a-d86d98329028.azurecomm.net')


@dataclass
class DeliveryResult:
    """Result of email delivery attempt."""
    success: bool
    provider: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'provider': self.provider,
            'message_id': self.message_id,
            'error': self.error,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class EmailDeliveryManager:
    """Multi-provider email delivery with intelligent fallback."""
    
    def __init__(self):
        self.providers = []
        self._initialize_providers()
        
    def _initialize_providers(self):
        """Initialize available email providers in priority order."""
        
        # 1. Azure Communication Services Email (primary)
        if AZURE_EMAIL_AVAILABLE and self._is_azure_email_configured():
            try:
                connection_string = os.getenv('ACS_EMAIL_CONNECTION_STRING')
                if connection_string:
                    self.azure_client = EmailClient.from_connection_string(connection_string)
                    self.providers.append('azure_email')
                    logger.info("Azure Communication Services Email initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Azure Email: {e}")
        
        # 2. SendGrid (secondary)
        if SENDGRID_AVAILABLE and os.getenv('SENDGRID_API_KEY'):
            try:
                self.sendgrid_client = sendgrid.SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
                self.providers.append('sendgrid')
                logger.info("SendGrid initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize SendGrid: {e}")
        
        # 3. SMTP (fallback)
        if self._is_smtp_configured():
            self.providers.append('smtp')
            logger.info("SMTP fallback initialized")
        
        if not self.providers:
            logger.error("No email providers available")
    
    def _is_azure_email_configured(self) -> bool:
        """Check if Azure Email is properly configured."""
        return bool(os.getenv('ACS_EMAIL_CONNECTION_STRING') or 
                   (os.getenv('ACS_EMAIL_ENDPOINT') and os.getenv('ACS_EMAIL_ACCESS_KEY')))
    
    def _is_smtp_configured(self) -> bool:
        """Check if SMTP is properly configured."""
        return bool(os.getenv('SMTP_HOST') and os.getenv('SMTP_PORT') and 
                   os.getenv('SMTP_USERNAME') and os.getenv('SMTP_PASSWORD'))
    
    async def send_via_azure_email(self, message: EmailMessage) -> DeliveryResult:
        """Send email via Azure Communication Services Email."""
        try:
            email_message = {
                "senderAddress": message.from_address,
                "content": {
                    "subject": message.subject,
                    "html": message.html_body
                },
                "recipients": {
                    "to": [{"address": addr} for addr in message.to_addresses]
                }
            }
            
            if message.text_body:
                email_message["content"]["plainText"] = message.text_body
            
            if message.reply_to:
                email_message["replyTo"] = [{"address": message.reply_to}]
            
            if message.bcc_addresses:
                email_message["recipients"]["bcc"] = [{"address": addr} for addr in message.bcc_addresses]
            
            # Send the message
            poller = self.azure_client.begin_send(email_message)
            result = poller.result()
            
            return DeliveryResult(
                success=True,
                provider="azure_email",
                message_id=result.message_id if hasattr(result, 'message_id') else None,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Azure Email delivery failed: {e}")
            return DeliveryResult(
                success=False,
                provider="azure_email", 
                error=str(e),
                timestamp=datetime.utcnow()
            )
    
    async def send_via_sendgrid(self, message: EmailMessage) -> DeliveryResult:
        """Send email via SendGrid."""
        try:
            from_email = Email(message.from_address, message.from_name)
            to_emails = [To(addr) for addr in message.to_addresses]
            
            content = Content("text/html", message.html_body)
            
            mail = Mail(
                from_email=from_email,
                to_emails=to_emails,
                subject=message.subject,
                html_content=content
            )
            
            if message.text_body:
                mail.add_content(Content("text/plain", message.text_body))
            
            if message.reply_to:
                mail.reply_to = Email(message.reply_to)
            
            if message.bcc_addresses:
                for bcc_addr in message.bcc_addresses:
                    mail.add_bcc(Email(bcc_addr))
            
            response = self.sendgrid_client.send(mail)
            
            return DeliveryResult(
                success=response.status_code in [200, 202],
                provider="sendgrid",
                message_id=response.headers.get('X-Message-Id'),
                error=None if response.status_code in [200, 202] else f"Status: {response.status_code}",
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"SendGrid delivery failed: {e}")
            return DeliveryResult(
                success=False,
                provider="sendgrid",
                error=str(e),
                timestamp=datetime.utcnow()
            )
    
    async def send_via_smtp(self, message: EmailMessage) -> DeliveryResult:
        """Send email via SMTP (fallback)."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = message.subject
            msg['From'] = f"{message.from_name} <{message.from_address}>"
            msg['To'] = ', '.join(message.to_addresses)
            
            if message.reply_to:
                msg['Reply-To'] = message.reply_to
            
            # Add text and HTML parts
            if message.text_body:
                text_part = MIMEText(message.text_body, 'plain')
                msg.attach(text_part)
            
            html_part = MIMEText(message.html_body, 'html')
            msg.attach(html_part)
            
            # Connect and send
            smtp_host = os.getenv('SMTP_HOST')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_user = os.getenv('SMTP_USERNAME')
            smtp_pass = os.getenv('SMTP_PASSWORD')
            smtp_use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
            
            server = smtplib.SMTP(smtp_host, smtp_port)
            if smtp_use_tls:
                server.starttls()
            
            server.login(smtp_user, smtp_pass)
            
            # Prepare recipient list
            recipients = message.to_addresses.copy()
            if message.bcc_addresses:
                recipients.extend(message.bcc_addresses)
            
            result = server.send_message(msg, to_addrs=recipients)
            server.quit()
            
            return DeliveryResult(
                success=True,
                provider="smtp",
                message_id=None,  # SMTP doesn't provide message ID
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"SMTP delivery failed: {e}")
            return DeliveryResult(
                success=False,
                provider="smtp",
                error=str(e),
                timestamp=datetime.utcnow()
            )
    
    async def send_email(self, message: EmailMessage, preferred_provider: Optional[str] = None) -> DeliveryResult:
        """Send email with automatic provider fallback."""
        if not self.providers:
            return DeliveryResult(
                success=False,
                provider="none",
                error="No email providers available",
                timestamp=datetime.utcnow()
            )
        
        # Try preferred provider first if specified and available
        providers_to_try = []
        if preferred_provider and preferred_provider in self.providers:
            providers_to_try.append(preferred_provider)
            providers_to_try.extend([p for p in self.providers if p != preferred_provider])
        else:
            providers_to_try = self.providers.copy()
        
        last_error = None
        
        for provider in providers_to_try:
            try:
                logger.info(f"Attempting email delivery via {provider}")
                
                if provider == 'azure_email':
                    result = await self.send_via_azure_email(message)
                elif provider == 'sendgrid':
                    result = await self.send_via_sendgrid(message)
                elif provider == 'smtp':
                    result = await self.send_via_smtp(message)
                else:
                    continue
                
                if result.success:
                    logger.info(f"Email delivered successfully via {provider}")
                    return result
                else:
                    logger.warning(f"Email delivery failed via {provider}: {result.error}")
                    last_error = result.error
                    
            except Exception as e:
                logger.error(f"Exception during {provider} delivery: {e}")
                last_error = str(e)
                continue
        
        # All providers failed
        return DeliveryResult(
            success=False,
            provider="all_failed",
            error=f"All providers failed. Last error: {last_error}",
            timestamp=datetime.utcnow()
        )
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all configured email providers."""
        status = {
            'available_providers': self.providers,
            'primary_provider': self.providers[0] if self.providers else None,
            'provider_details': {}
        }
        
        # Check each provider configuration
        if 'azure_email' in self.providers:
            status['provider_details']['azure_email'] = {
                'configured': True,
                'connection_string': bool(os.getenv('ACS_EMAIL_CONNECTION_STRING')),
                'endpoint': bool(os.getenv('ACS_EMAIL_ENDPOINT'))
            }
        
        if 'sendgrid' in self.providers:
            status['provider_details']['sendgrid'] = {
                'configured': True,
                'api_key': bool(os.getenv('SENDGRID_API_KEY'))
            }
        
        if 'smtp' in self.providers:
            status['provider_details']['smtp'] = {
                'configured': True,
                'host': os.getenv('SMTP_HOST'),
                'port': os.getenv('SMTP_PORT'),
                'username': bool(os.getenv('SMTP_USERNAME')),
                'use_tls': os.getenv('SMTP_USE_TLS', 'true')
            }
        
        return status


class TalentWellMailer:
    """Specialized mailer for TalentWell digest emails."""
    
    def __init__(self):
        self.delivery_manager = EmailDeliveryManager()
        self.default_recipients = ["brandon@emailthewell.com"]
        self.internal_recipients = ["brandon@emailthewell.com", "leadership@emailthewell.com"]
    
    async def send_weekly_digest(self, 
                                subject: str, 
                                html_content: str,
                                recipient_email: Optional[str] = None,
                                include_internal: bool = True,
                                test_mode: bool = False) -> Dict[str, Any]:
        """Send TalentWell weekly digest with appropriate recipients."""
        
        # Determine recipients
        primary_recipients = [recipient_email] if recipient_email else self.default_recipients.copy()
        
        if include_internal and not test_mode:
            # Add internal recipients via BCC to avoid exposing emails
            bcc_recipients = [addr for addr in self.internal_recipients if addr not in primary_recipients]
        else:
            bcc_recipients = None
        
        # Add test mode prefix
        if test_mode:
            subject = f"[TEST] {subject}"
        
        # Create message
        message = EmailMessage(
            to_addresses=primary_recipients,
            subject=subject,
            html_body=html_content,
            from_address=os.getenv('TALENTWELL_FROM_ADDRESS', 'DoNotReply@389fbf3b-307d-4882-af6a-d86d98329028.azurecomm.net'),
            from_name=os.getenv('TALENTWELL_FROM_NAME', 'TalentWell'),
            reply_to=os.getenv('TALENTWELL_REPLY_TO', 'steve@emailthewell.com'),
            bcc_addresses=bcc_recipients
        )
        
        # Send email
        result = await self.delivery_manager.send_email(message)
        
        # Log delivery result
        log_entry = {
            'type': 'weekly_digest',
            'test_mode': test_mode,
            'recipients': primary_recipients,
            'bcc_recipients': bcc_recipients,
            'subject': subject,
            'delivery_result': result.to_dict()
        }
        
        logger.info(f"Weekly digest delivery: {json.dumps(log_entry)}")
        
        return {
            'success': result.success,
            'provider': result.provider,
            'message_id': result.message_id,
            'error': result.error,
            'recipients': {
                'primary': primary_recipients,
                'bcc': bcc_recipients
            },
            'test_mode': test_mode,
            'timestamp': result.timestamp.isoformat() if result.timestamp else None
        }
    
    async def send_test_digest(self, subject: str, html_content: str, test_recipient: str) -> Dict[str, Any]:
        """Send test digest to a specific recipient."""
        return await self.send_weekly_digest(
            subject=subject,
            html_content=html_content, 
            recipient_email=test_recipient,
            include_internal=False,
            test_mode=True
        )
    
    def get_email_status(self) -> Dict[str, Any]:
        """Get email system status and configuration."""
        provider_status = self.delivery_manager.get_provider_status()
        
        return {
            'email_providers': provider_status,
            'default_recipients': self.default_recipients,
            'internal_recipients': self.internal_recipients,
            'system_ready': len(provider_status['available_providers']) > 0
        }


# Create singleton instance
mailer = TalentWellMailer()