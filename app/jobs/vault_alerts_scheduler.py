"""
Vault Alerts Scheduler

Automated job that runs hourly to check for executives who are due to receive
their vault candidate alerts via email.

Handles:
- Checking vault_alerts_due_for_delivery view for subscriptions
- Generating alerts HTML using VaultAlertsGenerator (LangGraph 4-agent workflow)
- Sending emails via Azure Communication Services
- Tracking deliveries in vault_alert_deliveries table
- Updating last_vault_alert_sent_at and next_vault_alert_scheduled_at
"""

import os
import asyncio
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import uuid
import json

import asyncpg

from app.jobs.vault_alerts_generator import VaultAlertsGenerator
from well_shared.database.connection import DatabaseConnectionManager

logger = logging.getLogger(__name__)

# Email Configuration from environment
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "azure_communication_services")
ACS_CONNECTION_STRING = os.getenv("ACS_EMAIL_CONNECTION_STRING")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@emailthewell.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "TalentWell Vault Alerts")


class VaultAlertsScheduler:
    """
    Manages automated vault candidate alert delivery to subscribed executives.
    Executive-only feature with custom filtering capabilities.
    """

    def __init__(self):
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        self.db_manager = DatabaseConnectionManager(database_url)

    async def initialize(self):
        """Initialize database connection."""
        logger.info("VaultAlertsScheduler initialized")

    async def close(self):
        """Close database connections."""
        logger.info("VaultAlertsScheduler closed")

    async def get_subscriptions_due(self) -> List[Dict[str, Any]]:
        """
        Get all vault alert subscriptions that are due for delivery.

        Returns:
            List of subscription dicts with executive preferences and custom filters
        """
        async with self.db_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT
                    user_id,
                    user_email,
                    user_name,
                    delivery_email,
                    audience,
                    frequency,
                    max_candidates,
                    custom_filters,
                    timezone,
                    last_vault_alert_sent_at,
                    next_vault_alert_scheduled_at
                FROM vault_alerts_due_for_delivery
            """)

            subscriptions: List[Dict[str, Any]] = []
            for row in rows:
                record = dict(row)
                custom_filters = record.get("custom_filters") or {}
                if isinstance(custom_filters, str):
                    try:
                        custom_filters = json.loads(custom_filters)
                    except json.JSONDecodeError:
                        custom_filters = {}
                record["custom_filters"] = custom_filters
                subscriptions.append(record)

            return subscriptions

    async def generate_vault_alerts(
        self,
        user_id: str,
        audience: str,
        max_candidates: int,
        custom_filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate vault alerts HTML using VaultAlertsGenerator (LangGraph 4-agent workflow).

        Args:
            user_id: Teams user ID
            audience: Candidate type (advisors, executives, both)
            max_candidates: Maximum number of candidates to include
            custom_filters: Optional dict with locations, designations, availability, etc.

        Returns:
            Dict with advisor_html, executive_html, metadata, quality_metrics
        """
        logger.info(f"Generating vault alerts for user {user_id}: audience={audience}, max={max_candidates}")
        logger.info(f"Custom filters: {custom_filters}")

        try:
            generator = VaultAlertsGenerator()
            result = await generator.generate_alerts(
                custom_filters=custom_filters,
                max_candidates=max_candidates,
                save_files=False  # Don't save files for scheduled deliveries
            )

            return result

        except Exception as e:
            logger.error(f"Error generating vault alerts for user {user_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def _extract_html_parts(html: str) -> Tuple[str, str]:
        """Extract style blocks and body content from a generator HTML document."""
        style_blocks = re.findall(r"<style[^>]*>.*?</style>", html, flags=re.IGNORECASE | re.DOTALL)
        styles_markup = "\n".join(style_blocks)

        body_match = re.search(r"<body[^>]*>(.*?)</body>", html, flags=re.IGNORECASE | re.DOTALL)
        body_content = body_match.group(1).strip() if body_match else html.strip()

        return styles_markup, body_content

    def _compose_email_html(self, sections: List[str]) -> str:
        """Merge one or more generator HTML documents into a single email-friendly layout."""
        collected_styles: List[str] = []
        body_segments: List[str] = []

        for section in sections:
            if not section:
                continue
            styles_markup, body_content = self._extract_html_parts(section)
            if styles_markup and styles_markup not in collected_styles:
                collected_styles.append(styles_markup)
            body_segments.append(body_content)

        deduped_styles = "\n".join(collected_styles)
        combined_body = "\n<hr style=\"margin: 40px 0; border: 2px solid #3498db;\">\n".join(body_segments) if body_segments else ""

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {deduped_styles}
</head>
<body>
{combined_body}
</body>
</html>"""

    def _validate_anonymization(self, html: str) -> bool:
        """
        Validate HTML doesn't contain identifiable information.

        Pre-send security check to ensure no confidential information
        leaked through anonymization process. Blocks email if violations found.

        Checks for:
        - Specific firm names (wirehouses, RIAs, banks, asset managers)
        - University names (LSU, Penn State, Harvard, etc.)
        - ZIP codes (5-digit patterns)
        - Exact AUM figures (should be ranges with + or ranges)

        Args:
            html: HTML email body to validate

        Returns:
            True if HTML passes validation (anonymized)
            False if HTML contains violations (identifiable)
        """
        # Comprehensive firm name patterns
        FIRM_PATTERNS = [
            # Wirehouses
            r'Merrill\s+Lynch', r'Morgan\s+Stanley', r'Wells\s+Fargo\s+Advisor',
            r'\bUBS\b', r'Raymond\s+James', r'Edward\s+Jones', r'Stifel',
            # Major RIAs
            r'Cresset', r'Fisher\s+Investments', r'Edelman\s+Financial',
            r'Creative\s+Planning', r'Captrust', r'Brightworth', r'Mariner\s+Wealth',
            r'Hightower', r'Sanctuary\s+Wealth', r'Dynasty\s+Financial',
            # Asset Managers
            r'Charles\s+Schwab', r'\bSchwab\b', r'Fidelity', r'Vanguard',
            r'JP\s*Morgan', r'JPMorgan', r'Goldman\s+Sachs', r'BlackRock',
            r'State\s+Street', r'BNY\s+Mellon', r'Northern\s+Trust',
            # Banks
            r'SAFE\s+Credit\s+Union', r'Regions\s+Bank', r'\bPNC\b',
            r'Fifth\s+Third', r'Truist', r'Key\s+Bank', r'Huntington',
            # Independent BDs
            r'LPL\s+Financial', r'\bLPL\b', r'Commonwealth\s+Financial',
            r'Northwestern\s+Mutual', r'MassMutual', r'Lincoln\s+Financial',
            r'Ameriprise', r'Cetera', r'Cambridge\s+Investment', r'Osaic'
        ]

        for pattern in FIRM_PATTERNS:
            if re.search(pattern, html, re.IGNORECASE):
                logger.error(f"❌ PRE-SEND VALIDATION FAILED: Found firm name pattern '{pattern}'")
                logger.error(f"   Blocking email for security - contains identifiable firm information")
                return False

        # University patterns - matches both "University of X" and "X University" patterns
        UNIVERSITY_PATTERNS = [
            # "University of X Y Z" patterns (multiple words)
            r'University\s+of\s+[\w\s,\-–]+',
            # "X State University" patterns
            r'[\w\s]+\s+State\s+University',
            # "X University" patterns (1-3 words before University)
            r'(?:\w+\s+)?(?:\w+\s+)?\w+\s+University',
            # Named universities
            r'\bLSU\b', r'Penn\s+State', r'Louisiana\s+State',
            r'Harvard', r'Stanford', r'MIT\b', r'Yale', r'Princeton',
            r'Columbia', r'Cornell', r'Duke', r'Northwestern', r'Georgetown',
            r'Vanderbilt', r'Emory', r'Rice', r'Notre\s+Dame',
            r'UCLA', r'USC\b', r'\bNYU\b', r'Michigan', r'Berkeley',
            r'IE\s+University', r'IE\s+Business', r'INSEAD', r'Wharton',
            r'Kellogg', r'Booth', r'Sloan', r'Haas', r'Stern'
        ]

        for pattern in UNIVERSITY_PATTERNS:
            if re.search(pattern, html, re.IGNORECASE):
                logger.error(f"❌ PRE-SEND VALIDATION FAILED: Found university name pattern '{pattern}'")
                logger.error(f"   Blocking email for security - contains identifiable education information")
                return False

        # Check for ZIP codes (5 digits, not phone numbers or years)
        if re.search(r'\b\d{5}\b', html):
            logger.error("❌ PRE-SEND VALIDATION FAILED: Found ZIP code")
            logger.error("   Blocking email for security - contains specific location identifier")
            return False

        # Check for exact AUM figures (should be ranges or have + suffix)
        # Pattern: $X.XB or $XXXM without + or range indicator
        exact_aum_pattern = r'\$\d+\.\d+[BMK](?!\+|\s*-\s*\$)'
        if re.search(exact_aum_pattern, html):
            matches = re.findall(exact_aum_pattern, html)
            logger.error(f"❌ PRE-SEND VALIDATION FAILED: Found exact AUM figure(s): {matches}")
            logger.error(f"   Blocking email for security - AUM should be ranges ($1B-$2B) or with + suffix ($1B+)")
            return False

        logger.info("✅ Pre-send validation PASSED - no identifying information found in HTML")
        return True

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        user_name: Optional[str] = None
    ) -> str:
        """
        Send email via Azure Communication Services.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_body: HTML email body (alerts with inline CSS)
            user_name: Optional recipient name for personalization

        Returns:
            Message ID for tracking

        Raises:
            Exception if email send fails
        """
        from azure.communication.email import EmailClient

        if not ACS_CONNECTION_STRING:
            raise ValueError("ACS_CONNECTION_STRING not configured")

        # ========================================================================
        # CRITICAL SECURITY CHECK: Validate anonymization before sending
        # ========================================================================
        if not self._validate_anonymization(html_body):
            raise ValueError(
                "❌ SECURITY VIOLATION: Email blocked due to anonymization validation failure. "
                "HTML contains identifiable information (firm names, universities, ZIP codes, or exact AUM). "
                "Check application logs for specific violations. "
                "This email will NOT be sent for compliance and confidentiality reasons."
            )

        try:
            # Create email client
            email_client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)

            # Build message using dictionary format (Azure Communication Services 1.0.0 API)
            message = {
                "content": {
                    "subject": subject,
                    "html": html_body
                },
                "recipients": {
                    "to": [
                        {
                            "address": to_email,
                            "displayName": user_name or to_email.split('@')[0]
                        }
                    ]
                },
                "senderAddress": SMTP_FROM_EMAIL
            }

            # Send email (synchronous - will block)
            poller = email_client.begin_send(message)
            result = poller.result()

            message_id = result.get('messageId', 'unknown')
            logger.info(f"Vault alert email sent to {to_email}: {subject} (message_id: {message_id})")
            return message_id

        except Exception as e:
            logger.error(f"Azure Communication Services send failed to {to_email}: {e}", exc_info=True)
            raise

    async def process_subscription(
        self,
        subscription: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a single vault alerts subscription.

        Args:
            subscription: Subscription data from vault_alerts_due_for_delivery view

        Returns:
            Delivery result dict with status and metadata
        """
        user_id = subscription['user_id']
        user_email = subscription['user_email']
        user_name = subscription['user_name']
        delivery_email = subscription['delivery_email']
        audience = subscription['audience']
        frequency = subscription['frequency']
        max_candidates_raw = subscription.get('max_candidates')
        try:
            max_candidates = int(max_candidates_raw)
        except (TypeError, ValueError):
            max_candidates = 50
        max_candidates = max(1, min(max_candidates, 200))

        custom_filters = subscription.get('custom_filters') or {}
        if isinstance(custom_filters, str):
            try:
                custom_filters = json.loads(custom_filters)
            except json.JSONDecodeError:
                custom_filters = {}

        delivery_id = str(uuid.uuid4())
        start_time = datetime.now()

        logger.info(f"Processing vault alert subscription for {user_email} (delivery to: {delivery_email})")

        # Track delivery in database
        async with self.db_manager.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO vault_alert_deliveries (
                    delivery_id, user_id, user_email, delivery_email,
                    audience, frequency, max_candidates, custom_filters,
                    status, created_at, started_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'processing', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                delivery_id, user_id, user_email, delivery_email,
                audience, frequency, max_candidates, json.dumps(custom_filters)
            )

        try:
            # Generate vault alerts using LangGraph 4-agent workflow
            result = await self.generate_vault_alerts(
                user_id=user_id,
                audience=audience,
                max_candidates=max_candidates,
                custom_filters=custom_filters
            )

            advisor_html = result['advisor_html']
            executive_html = result['executive_html']
            metadata = result['metadata']
            quality_metrics = result['quality_metrics']

            # Select which HTML to send based on audience preference
            if audience == "advisors":
                html_body = self._compose_email_html([advisor_html])
                candidate_count = metadata['advisor_count']
            elif audience == "executives":
                html_body = self._compose_email_html([executive_html])
                candidate_count = metadata['executive_count']
            else:  # both
                html_body = self._compose_email_html([advisor_html, executive_html])
                candidate_count = metadata['total_candidates']

            # Build email subject
            subject = f"🔔 Vault Candidate Alerts - {audience.title()} ({candidate_count} candidates)"

            # Send email
            message_id = self.send_email(
                to_email=delivery_email,
                subject=subject,
                html_body=html_body,
                user_name=user_name
            )

            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

            # Update delivery record as successful
            async with self.db_manager.get_connection() as conn:
                await conn.execute(
                    """
                    UPDATE vault_alert_deliveries
                    SET status = 'sent',
                        advisor_cards_count = $2,
                        executive_cards_count = $3,
                        total_candidates = $4,
                        execution_time_ms = $5,
                        email_subject = $6,
                        email_sent_at = CURRENT_TIMESTAMP,
                        email_message_id = $7,
                        advisor_html = $8,
                        executive_html = $9,
                        generation_metadata = $10,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE delivery_id = $1
                    """,
                    delivery_id,
                    metadata['advisor_count'],
                    metadata['executive_count'],
                    metadata['total_candidates'],
                    execution_time,
                    subject,
                    message_id,
                    advisor_html,
                    executive_html,
                    json.dumps(metadata)
                )

                # Update user's last_vault_alert_sent_at timestamp
                await conn.execute(
                    """
                    UPDATE teams_user_preferences
                    SET last_vault_alert_sent_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                    """,
                    user_id
                )

            logger.info(f"✅ Vault alert delivered successfully to {delivery_email} ({candidate_count} candidates)")

            return {
                "delivery_id": delivery_id,
                "status": "sent",
                "user_email": user_email,
                "delivery_email": delivery_email,
                "candidate_count": candidate_count,
                "execution_time_ms": execution_time,
                "message_id": message_id
            }

        except Exception as e:
            logger.error(f"❌ Vault alert delivery failed for {user_email}: {e}", exc_info=True)

            # Update delivery record as failed
            async with self.db_manager.get_connection() as conn:
                await conn.execute(
                    """
                    UPDATE vault_alert_deliveries
                    SET status = 'failed',
                        error_message = $2,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE delivery_id = $1
                    """,
                    delivery_id,
                    str(e)
                )

            return {
                "delivery_id": delivery_id,
                "status": "failed",
                "user_email": user_email,
                "delivery_email": delivery_email,
                "error": str(e)
            }

    async def run(self):
        """
        Main scheduler loop - check for subscriptions and process them.

        Returns:
            Summary of processing results
        """
        logger.info("🔄 Vault Alerts Scheduler: Checking for due subscriptions...")

        # Get subscriptions due for delivery
        subscriptions = await self.get_subscriptions_due()

        if not subscriptions:
            logger.info("No vault alert subscriptions due at this time")
            return {
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "subscriptions": []
            }

        logger.info(f"Found {len(subscriptions)} vault alert subscription(s) due for delivery")

        # Process each subscription
        results = []
        for subscription in subscriptions:
            result = await self.process_subscription(subscription)
            results.append(result)

        # Summary
        successful = len([r for r in results if r['status'] == 'sent'])
        failed = len([r for r in results if r['status'] == 'failed'])

        logger.info(f"✅ Vault Alerts Scheduler completed: {successful} sent, {failed} failed")

        return {
            "processed": len(results),
            "successful": successful,
            "failed": failed,
            "subscriptions": results
        }


# Standalone execution for testing or manual runs
async def main():
    """Run vault alerts scheduler once."""
    scheduler = VaultAlertsScheduler()
    await scheduler.initialize()

    try:
        result = await scheduler.run()
        print(f"\n{'='*80}")
        print(f"Vault Alerts Scheduler Summary:")
        print(f"  Processed: {result['processed']}")
        print(f"  Successful: {result['successful']}")
        print(f"  Failed: {result['failed']}")
        print(f"{'='*80}\n")

    finally:
        await scheduler.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
