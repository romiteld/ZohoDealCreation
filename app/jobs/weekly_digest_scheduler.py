"""
Weekly Digest Scheduler

Automated job that runs hourly to check for users who are due to receive
their weekly TalentWell Vault candidate digest via email.

Handles:
- Checking subscriptions_due_for_delivery view for users
- Generating digest HTML using TalentWellCurator
- Sending emails via SMTP
- Tracking deliveries in weekly_digest_deliveries table
- Updating last_digest_sent_at and next_digest_scheduled_at
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import uuid

import asyncpg

from app.jobs.talentwell_curator import TalentWellCurator
from app.database_connection_manager import DatabaseConnectionManager

logger = logging.getLogger(__name__)

# Email Configuration from environment
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "azure_communication_services")
ACS_CONNECTION_STRING = os.getenv("ACS_CONNECTION_STRING")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@emailthewell.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "TalentWell Vault")


class WeeklyDigestScheduler:
    """
    Manages automated weekly digest delivery to subscribed users.
    """

    def __init__(self):
        self.db_manager = DatabaseConnectionManager()
        self.curator = TalentWellCurator()

    async def initialize(self):
        """Initialize database connection and curator."""
        await self.curator.initialize()
        logger.info("WeeklyDigestScheduler initialized")

    async def close(self):
        """Close database connections."""
        await self.db_manager.close()
        logger.info("WeeklyDigestScheduler closed")

    async def get_subscriptions_due(self) -> List[Dict[str, Any]]:
        """
        Get all subscriptions that are due for delivery.

        Returns:
            List of subscription dicts with user preferences
        """
        async with self.db_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT
                    user_id,
                    user_email,
                    user_name,
                    delivery_email,
                    default_audience,
                    digest_frequency,
                    max_candidates_per_digest,
                    timezone,
                    last_digest_sent_at,
                    next_digest_scheduled_at
                FROM subscriptions_due_for_delivery
            """)

            return [dict(row) for row in rows]

    async def generate_digest_for_user(
        self,
        user_id: str,
        audience: str,
        max_candidates: int,
        timezone: str = "America/New_York"
    ) -> Dict[str, Any]:
        """
        Generate digest HTML for a specific user.

        Args:
            user_id: Teams user ID
            audience: Candidate type (advisors, c_suite, global)
            max_candidates: Maximum number of candidates to include
            timezone: User's timezone

        Returns:
            Dict with digest_html, cards, total_candidates
        """
        # Calculate date range (last 7 days)
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=7)

        logger.info(f"Generating digest for user {user_id}: audience={audience}, max={max_candidates}")

        try:
            result = await self.curator.run_weekly_digest(
                audience=audience,
                from_date=from_date.isoformat(),
                to_date=to_date.isoformat(),
                owner=None,  # No owner filter for subscriptions
                max_cards=max_candidates,
                dry_run=False,  # Actually generate the digest
                ignore_cooldown=True  # Allow scheduled deliveries
            )

            return {
                "digest_html": result.get("html", ""),
                "cards": result.get("cards", []),
                "total_candidates": len(result.get("cards", [])),
                "subject_variant": result.get("subject_variant", "Weekly Vault Candidate Digest")
            }

        except Exception as e:
            logger.error(f"Error generating digest for user {user_id}: {e}", exc_info=True)
            raise

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
            html_body: HTML email body
            user_name: Optional recipient name for personalization

        Returns:
            Message ID for tracking

        Raises:
            Exception if email send fails
        """
        from azure.communication.email import EmailClient
        from azure.communication.email import EmailAddress, EmailMessage

        if not ACS_CONNECTION_STRING:
            raise ValueError("ACS_CONNECTION_STRING not configured")

        try:
            # Create email client
            email_client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)

            # Build message
            message = EmailMessage(
                sender=EmailAddress(
                    email=SMTP_FROM_EMAIL,
                    display_name=SMTP_FROM_NAME
                ),
                recipients=EmailAddress(email=to_email),
                subject=subject,
                html_content=html_body
            )

            # Send email (synchronous - will block)
            poller = email_client.begin_send(message)
            result = poller.result()

            logger.info(f"Email sent to {to_email}: {subject} (message_id: {result.message_id})")
            return result.message_id

        except Exception as e:
            logger.error(f"Azure Communication Services send failed to {to_email}: {e}", exc_info=True)
            raise

    async def send_confirmation_email(
        self,
        user_id: str,
        delivery_email: str,
        action: str,
        new_settings: Dict[str, Any],
        previous_settings: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Send confirmation email when user subscribes/unsubscribes/updates.

        Args:
            user_id: Teams user ID
            delivery_email: Email address to send confirmation to
            action: 'subscribe', 'unsubscribe', or 'update'
            new_settings: New preference settings
            previous_settings: Previous settings (for updates)

        Returns:
            Confirmation ID
        """
        confirmation_id = str(uuid.uuid4())

        # Build confirmation message
        if action == "subscribe":
            subject = "✅ Weekly Vault Digest Subscription Confirmed"
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #0078d4;">Welcome to TalentWell Vault Weekly Digest!</h2>

                <p>Your subscription has been confirmed. You will receive weekly candidate digests at:</p>

                <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <strong>📧 Email:</strong> {delivery_email}<br>
                    <strong>📊 Audience:</strong> {new_settings.get('default_audience', 'global').replace('_', ' ').title()}<br>
                    <strong>📅 Frequency:</strong> {new_settings.get('digest_frequency', 'weekly').title()}<br>
                    <strong>👥 Max Candidates:</strong> {new_settings.get('max_candidates_per_digest', 6)} per digest
                </div>

                <p>Your first digest will arrive on <strong>{new_settings.get('next_digest_scheduled_at', 'the next scheduled delivery')}</strong>.</p>

                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    To unsubscribe or update preferences, type <code>preferences</code> in the TalentWell Teams bot.
                </p>
            </body>
            </html>
            """

        elif action == "unsubscribe":
            subject = "Unsubscribed from Weekly Vault Digest"
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #d13438;">You've been unsubscribed</h2>

                <p>You will no longer receive weekly TalentWell Vault candidate digests at <strong>{delivery_email}</strong>.</p>

                <p style="margin-top: 30px;">
                    To re-subscribe, type <code>preferences</code> in the TalentWell Teams bot and enable notifications.
                </p>
            </body>
            </html>
            """

        else:  # action == "update"
            subject = "Weekly Vault Digest Preferences Updated"
            changes = []
            if previous_settings:
                if previous_settings.get('default_audience') != new_settings.get('default_audience'):
                    changes.append(f"Audience: {previous_settings.get('default_audience')} → {new_settings.get('default_audience')}")
                if previous_settings.get('digest_frequency') != new_settings.get('digest_frequency'):
                    changes.append(f"Frequency: {previous_settings.get('digest_frequency')} → {new_settings.get('digest_frequency')}")
                if previous_settings.get('max_candidates_per_digest') != new_settings.get('max_candidates_per_digest'):
                    changes.append(f"Max Candidates: {previous_settings.get('max_candidates_per_digest')} → {new_settings.get('max_candidates_per_digest')}")

            changes_html = "<br>".join([f"• {c}" for c in changes])

            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #0078d4;">Preferences Updated</h2>

                <p>Your Weekly Vault Digest preferences have been updated:</p>

                <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    {changes_html}
                </div>

                <p>Changes will take effect with your next scheduled digest.</p>
            </body>
            </html>
            """

        # Send confirmation email
        try:
            message_id = self.send_email(delivery_email, subject, body)

            # Record confirmation in database
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO subscription_confirmations (
                        confirmation_id, user_id, user_email, delivery_email,
                        action, previous_settings, new_settings,
                        confirmation_sent, confirmation_sent_at, confirmation_email_subject
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE, CURRENT_TIMESTAMP, $8)
                """, confirmation_id, user_id, new_settings.get('user_email'),
                    delivery_email, action,
                    previous_settings, new_settings, subject)

            logger.info(f"Confirmation email sent to {delivery_email}: {action}")
            return confirmation_id

        except Exception as e:
            logger.error(f"Failed to send confirmation email to {delivery_email}: {e}", exc_info=True)
            raise

    async def process_subscription(self, subscription: Dict[str, Any]) -> bool:
        """
        Process a single subscription delivery.

        Args:
            subscription: Subscription dict from database

        Returns:
            True if delivery succeeded, False otherwise
        """
        delivery_id = str(uuid.uuid4())
        user_id = subscription["user_id"]
        delivery_email = subscription["delivery_email"]
        audience = subscription["default_audience"]
        max_candidates = subscription["max_candidates_per_digest"]

        logger.info(f"Processing subscription for {user_id} ({delivery_email})")

        # Create delivery record
        async with self.db_manager.get_connection() as conn:
            await conn.execute("""
                INSERT INTO weekly_digest_deliveries (
                    delivery_id, user_id, user_email, delivery_email,
                    audience, max_candidates, status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, 'processing', CURRENT_TIMESTAMP)
            """, delivery_id, user_id, subscription["user_email"],
                delivery_email, audience, max_candidates)

        start_time = datetime.now()

        try:
            # Generate digest
            result = await self.generate_digest_for_user(
                user_id=user_id,
                audience=audience,
                max_candidates=max_candidates,
                timezone=subscription.get("timezone", "America/New_York")
            )

            digest_html = result["digest_html"]
            cards = result["cards"]
            subject = result["subject_variant"]

            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Send email
            message_id = self.send_email(
                to_email=delivery_email,
                subject=subject,
                html_body=digest_html,
                user_name=subscription.get("user_name")
            )

            # Update delivery record as sent
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE weekly_digest_deliveries
                    SET status = 'sent',
                        cards_generated = $1,
                        total_candidates = $2,
                        execution_time_ms = $3,
                        email_subject = $4,
                        email_sent_at = CURRENT_TIMESTAMP,
                        email_message_id = $5,
                        digest_html = $6,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE delivery_id = $7
                """, len(cards), len(cards), execution_time_ms,
                    subject, message_id, digest_html, delivery_id)

                # Update user's last_digest_sent_at
                await conn.execute("""
                    UPDATE teams_user_preferences
                    SET last_digest_sent_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id)

            logger.info(f"✅ Digest delivered to {delivery_email}: {len(cards)} candidates")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to deliver digest to {delivery_email}: {e}", exc_info=True)

            # Update delivery record as failed
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE weekly_digest_deliveries
                    SET status = 'failed',
                        error_message = $1,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE delivery_id = $2
                """, str(e), delivery_id)

            return False

    async def run(self):
        """
        Main scheduler loop - check for subscriptions due and process them.
        """
        logger.info("🔄 Running weekly digest scheduler...")

        try:
            # Get subscriptions due for delivery
            subscriptions = await self.get_subscriptions_due()

            if not subscriptions:
                logger.info("No subscriptions due for delivery")
                return

            logger.info(f"Found {len(subscriptions)} subscriptions due for delivery")

            # Process each subscription
            results = []
            for subscription in subscriptions:
                success = await self.process_subscription(subscription)
                results.append(success)

            # Summary
            successful = sum(results)
            failed = len(results) - successful
            logger.info(f"✅ Digest scheduler completed: {successful} sent, {failed} failed")

        except Exception as e:
            logger.error(f"Error in digest scheduler: {e}", exc_info=True)


async def main():
    """
    Entry point for scheduled job (cron, Azure Functions Timer, etc.)
    """
    scheduler = WeeklyDigestScheduler()

    try:
        await scheduler.initialize()
        await scheduler.run()
    finally:
        await scheduler.close()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run scheduler
    asyncio.run(main())
