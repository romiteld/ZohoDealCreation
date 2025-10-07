"""
Email send helper for Vault Agent integration.
Provides simplified interface to the TalentWell email delivery system.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.mail.send import EmailMessage, EmailDeliveryManager, inline_css_for_email

logger = logging.getLogger(__name__)

# Note: inline_css_for_email is now imported from app.mail.send
# This ensures consistency - all CSS inlining uses the same css-inline library


async def send_html_email(
    subject: str,
    html: str,
    to: List[str],
    from_address: Optional[str] = None,
    from_name: str = "TalentWell",
    reply_to: Optional[str] = None,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    Send HTML email using the TalentWell delivery system.
    
    Args:
        subject: Email subject line
        html: Complete HTML content for the email
        to: List of recipient email addresses
        from_address: Optional sender address (defaults to environment variable)
        from_name: Sender display name (defaults to "TalentWell")
        reply_to: Optional reply-to address
        test_mode: Whether this is a test send
        
    Returns:
        Dictionary with send results including:
        - success: bool
        - provider: str (which provider was used)
        - message_id: Optional[str]
        - error: Optional[str]
        - recipients: int (count of recipients)
    """
    try:
        # Add test prefix if in test mode
        if test_mode:
            subject = f"[TEST] {subject}"
        
        # Use environment variable for from_address if not provided
        if not from_address:
            from_address = os.getenv(
                'TALENTWELL_FROM_ADDRESS',
                'DoNotReply@389fbf3b-307d-4882-af6a-d86d98329028.azurecomm.net'
            )
        
        # Use environment variable for reply_to if not provided
        if not reply_to:
            reply_to = os.getenv('TALENTWELL_REPLY_TO', 'steve@emailthewell.com')

        # Inline CSS for email client compatibility (Azure Communication Services requires this)
        html_inlined = inline_css_for_email(html)

        # Create email message with inlined CSS
        message = EmailMessage(
            to_addresses=to,
            subject=subject,
            html_body=html_inlined,
            text_body=None,  # HTML-only for now
            from_address=from_address,
            from_name=from_name,
            reply_to=reply_to,
            bcc_addresses=None  # No BCC for single candidate alerts
        )
        
        # Initialize delivery manager
        delivery_manager = EmailDeliveryManager()
        
        # Send the email
        result = await delivery_manager.send_email(message)
        
        # Log summary (no PII)
        logger.info(f"Email send attempt - Subject: '{subject[:50]}...', Recipients: {len(to)}, "
                   f"Provider: {result.provider}, Success: {result.success}")
        
        # Build response
        response = {
            'success': result.success,
            'provider': result.provider,
            'message_id': result.message_id,
            'error': result.error,
            'recipients': len(to),
            'timestamp': result.timestamp.isoformat() if result.timestamp else None
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return {
            'success': False,
            'provider': 'none',
            'message_id': None,
            'error': str(e),
            'recipients': len(to) if to else 0,
            'timestamp': datetime.utcnow().isoformat()
        }


async def send_test_email(
    test_recipient: str,
    card_html: str
) -> Dict[str, Any]:
    """
    Send a test candidate alert email.
    
    Args:
        test_recipient: Email address to send test to
        card_html: HTML for the candidate card
        
    Returns:
        Dictionary with send results
    """
    from app.templates.render import render_single_candidate
    from app.templates.validator import validate_digest_html
    
    try:
        # Render the email
        email_html = render_single_candidate(card_html)
        
        # Validate
        is_valid, errors = validate_digest_html(email_html)
        if not is_valid:
            return {
                'success': False,
                'provider': 'none',
                'message_id': None,
                'error': f"Validation failed: {', '.join(errors)}",
                'recipients': 0
            }
        
        # Send
        return await send_html_email(
            subject="TalentWell – Candidate Alert (Test)",
            html=email_html,
            to=[test_recipient],
            test_mode=True
        )
        
    except Exception as e:
        logger.error(f"Test email failed: {e}")
        return {
            'success': False,
            'provider': 'none',
            'message_id': None,
            'error': str(e),
            'recipients': 0
        }


async def send_batch_emails(
    recipients: List[Dict[str, Any]],
    template: str = "single_candidate",
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    Send emails to multiple recipients with personalized content.
    
    Args:
        recipients: List of dicts with 'email', 'card_html', and optional 'subject'
        template: Template type to use
        test_mode: Whether this is a test batch
        
    Returns:
        Summary of batch send results
    """
    from app.templates.render import render_single_candidate
    from app.templates.validator import validate_digest_html
    
    results = {
        'total': len(recipients),
        'sent': 0,
        'failed': 0,
        'errors': [],
        'details': []
    }
    
    for recipient_data in recipients:
        try:
            email = recipient_data.get('email')
            card_html = recipient_data.get('card_html')
            subject = recipient_data.get('subject', 'TalentWell – Candidate Alert')
            
            if not email or not card_html:
                results['failed'] += 1
                results['errors'].append(f"Missing email or card_html for recipient")
                continue
            
            # Render email
            if template == "single_candidate":
                email_html = render_single_candidate(card_html)
            else:
                # Could support other templates in future
                email_html = render_single_candidate(card_html)
            
            # Validate
            is_valid, errors = validate_digest_html(email_html)
            if not is_valid:
                results['failed'] += 1
                results['errors'].append(f"Validation failed for {email}: {errors[0] if errors else 'unknown'}")
                continue
            
            # Send
            send_result = await send_html_email(
                subject=subject,
                html=email_html,
                to=[email],
                test_mode=test_mode
            )
            
            if send_result['success']:
                results['sent'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(f"Send failed for {email}: {send_result.get('error')}")
            
            results['details'].append({
                'email': email,
                'success': send_result['success'],
                'provider': send_result.get('provider'),
                'message_id': send_result.get('message_id')
            })
            
        except Exception as e:
            results['failed'] += 1
            results['errors'].append(f"Exception for recipient: {str(e)}")
            logger.error(f"Batch send error: {e}")
    
    logger.info(f"Batch send complete - Sent: {results['sent']}/{results['total']}")
    
    return results


def get_email_config() -> Dict[str, Any]:
    """
    Get current email configuration and provider status.
    
    Returns:
        Dictionary with configuration details
    """
    try:
        delivery_manager = EmailDeliveryManager()
        provider_status = delivery_manager.get_provider_status()
        
        return {
            'configured': True,
            'providers': provider_status,
            'from_address': os.getenv(
                'TALENTWELL_FROM_ADDRESS',
                'DoNotReply@389fbf3b-307d-4882-af6a-d86d98329028.azurecomm.net'
            ),
            'reply_to': os.getenv('TALENTWELL_REPLY_TO', 'steve@emailthewell.com'),
            'system_ready': len(provider_status.get('available_providers', [])) > 0
        }
    except Exception as e:
        logger.error(f"Failed to get email config: {e}")
        return {
            'configured': False,
            'error': str(e),
            'system_ready': False
        }