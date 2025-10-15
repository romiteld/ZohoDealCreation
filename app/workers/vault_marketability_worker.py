"""
Vault Marketability Worker

Processes "top N most marketable candidates" queries via Service Bus.
- Fetches vault candidates from Zoho CRM API
- Scores candidates using MarketabilityScorer
- Streams progress updates to Teams
- Returns top N with anonymization
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from botbuilder.core import TurnContext
from botbuilder.schema import Activity

from app.jobs.marketability_scorer import MarketabilityScorer
from app.services.streaming_messenger import TeamsStreamingMessenger, create_marketable_candidates_card
from app.utils.anonymizer import anonymize_candidate_data
from app.integrations import get_zoho_headers

logger = logging.getLogger(__name__)


class VaultMarketabilityWorker:
    """Service Bus worker for vault marketability queries."""

    def __init__(self):
        """Initialize worker with Service Bus connection."""
        self.connection_string = os.getenv("SERVICE_BUS_CONNECTION_STRING") or os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
        if not self.connection_string:
            raise ValueError("SERVICE_BUS_CONNECTION_STRING required")

        self.queue_name = "vault-marketability-analysis"
        self.zoho_api_base = "https://www.zohoapis.com/crm/v8"
        self.zoho_vault_view_id = os.getenv("ZOHO_VAULT_VIEW_ID", "6221978000090941003")

        self.scorer = MarketabilityScorer()
        self._client: Optional[ServiceBusClient] = None
        self._receiver = None

    async def start(self):
        """Start processing messages from queue."""
        logger.info(f"Starting vault marketability worker on queue: {self.queue_name}")

        try:
            self._client = ServiceBusClient.from_connection_string(
                self.connection_string,
                logging_enable=True
            )
            self._receiver = self._client.get_queue_receiver(
                queue_name=self.queue_name,
                max_wait_time=30
            )

            async with self._receiver:
                while True:
                    messages = await self._receiver.receive_messages(max_message_count=1, max_wait_time=5)

                    for msg in messages:
                        try:
                            await self._process_message(msg)
                            await self._receiver.complete_message(msg)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            await self._receiver.abandon_message(msg)

                    await asyncio.sleep(1)  # Prevent tight loop

        except Exception as e:
            logger.error(f"Worker error: {e}")
            raise
        finally:
            await self.close()

    async def _process_message(self, message):
        """Process a single marketability query."""
        try:
            body = json.loads(str(message))
            query_data = body.get("query_data", {})

            conversation_reference = query_data.get("conversation_reference")
            limit = query_data.get("limit", 10)
            user_id = query_data.get("user_id")

            logger.info(f"Processing marketability query for user {user_id}, limit={limit}")

            if not conversation_reference:
                logger.warning("No conversation reference provided - cannot send proactive message")
                # Still process but won't be able to send results back
            else:
                logger.info(f"Conversation reference found for proactive messaging: {conversation_reference.get('conversation', {}).get('id', 'unknown')}")

            # Fetch all vault candidates from Zoho
            candidates = await self._fetch_vault_candidates()

            if not candidates:
                logger.warning("No vault candidates found in Zoho")
                if conversation_reference:
                    await self._send_proactive_message(
                        conversation_reference,
                        "❌ No vault candidates found in Zoho CRM."
                    )
                return

            total_candidates = len(candidates)
            logger.info(f"Fetched {total_candidates} vault candidates from Zoho")

            # Send progress update if possible
            if conversation_reference:
                await self._send_proactive_message(
                    conversation_reference,
                    f"⚡ Fetched {total_candidates} vault candidates. Now scoring..."
                )

            # Score candidates with streaming updates
            scored_candidates = await self._score_candidates_with_streaming(
                candidates,
                conversation_reference,
                total_candidates
            )

            # Sort by score (highest first)
            scored_candidates.sort(key=lambda x: x['score'], reverse=True)

            # Take top N
            top_candidates = scored_candidates[:limit]

            # Anonymize and format
            anonymized_candidates = []
            for candidate in top_candidates:
                anonymized = self._anonymize_and_format(candidate)
                anonymized_candidates.append(anonymized)

            # Send adaptive card to Teams
            await self._send_results_card(
                conversation_reference,
                anonymized_candidates,
                total_candidates
            )

            logger.info(f"Completed marketability query: {len(top_candidates)} results")

        except Exception as e:
            logger.error(f"Error in _process_message: {e}", exc_info=True)
            raise

    async def _fetch_vault_candidates(self) -> List[Dict[str, Any]]:
        """
        Fetch all vault candidates from Zoho CRM API.

        Uses custom view ID: 6221978000090941003
        """
        try:
            headers = await get_zoho_headers()

            # Use custom view to get vault candidates from Leads module
            # Custom view filters by Publish_to_Vault = True
            url = f"{self.zoho_api_base}/Leads"
            params = {
                "cvid": self.zoho_vault_view_id,  # Custom view: _Vault Candidates
                "per_page": 200,  # Max per page
                "page": 1
            }

            all_candidates = []
            page = 1

            import aiohttp
            async with aiohttp.ClientSession() as session:
                while True:
                    params["page"] = page

                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status != 200:
                            logger.error(f"Zoho API error: {response.status}")
                            if response.status != 204:  # 204 = no content is ok
                                text = await response.text()
                                logger.error(f"Response: {text[:200]}")
                            break

                        data = await response.json()
                        candidates = data.get("data", [])

                        if not candidates:
                            break

                        all_candidates.extend(candidates)

                        # Check if more pages
                        info = data.get("info", {})
                        if not info.get("more_records", False):
                            break

                        page += 1
                        await asyncio.sleep(0.5)  # Rate limiting

            logger.info(f"Fetched {len(all_candidates)} vault candidates from Zoho")
            return all_candidates

        except Exception as e:
            logger.error(f"Error fetching vault candidates: {e}", exc_info=True)
            return []

    async def _score_candidates_with_streaming(
        self,
        candidates: List[Dict[str, Any]],
        conversation_reference: Optional[Dict[str, Any]],
        total_count: int
    ) -> List[Dict[str, Any]]:
        """
        Score candidates with streaming progress updates every 25 candidates.
        """
        scored_candidates = []
        batch_size = 25

        for idx, candidate in enumerate(candidates, 1):
            # Score candidate
            score, breakdown = self.scorer.score_candidate(candidate)

            scored_candidates.append({
                **candidate,
                'score': score,
                'score_breakdown': breakdown
            })

            # Send progress update every batch_size candidates (~2 seconds)
            if idx % batch_size == 0 or idx == total_count:
                progress_pct = int((idx / total_count) * 100)
                logger.info(f"⚡ Progress: {idx}/{total_count} candidates scored ({progress_pct}%)")

                # Send proactive message if possible
                if conversation_reference:
                    await self._send_proactive_message(
                        conversation_reference,
                        f"⚡ Progress: {idx}/{total_count} candidates scored ({progress_pct}%)"
                    )

        return scored_candidates

    def _anonymize_and_format(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize and format candidate for display.

        Returns dict with:
            - candidate_locator: TWAV code
            - score: Marketability score
            - location: Anonymized location
            - key_bullet: Top achievement
            - firm_type: Anonymized firm type
            - availability: When available
        """
        # Apply full anonymization
        anonymized = anonymize_candidate_data(candidate)

        # Extract key bullet (first bullet from anonymized data)
        # This would ideally come from the bullet generator, but for now use a simple extraction
        key_bullet = self._extract_key_bullet(anonymized)

        return {
            'candidate_locator': candidate.get('Candidate_Locator', 'Unknown'),
            'score': candidate.get('score', 0),
            'location': anonymized.get('location', 'Unknown'),
            'key_bullet': key_bullet,
            'firm_type': anonymized.get('current_employer', 'Advisory firm'),
            'availability': candidate.get('When_Available', 'TBD')
        }

    def _extract_key_bullet(self, anonymized: Dict[str, Any]) -> str:
        """
        Extract key achievement bullet from anonymized candidate.

        Prioritizes:
        1. AUM management experience
        2. Production/revenue achievements
        3. Client relationship highlights
        4. Credentials
        """
        # Check for AUM in book size
        aum = anonymized.get('book_size_aum', '')
        if aum and aum != 'Not disclosed':
            return f"Manages {aum} in client assets"

        # Check for production
        production = anonymized.get('production_l12mo', '')
        if production and production != 'Not disclosed':
            return f"Generated {production} in trailing 12-month production"

        # Check for credentials
        licenses = anonymized.get('licenses_and_exams', '')
        if licenses:
            return f"Holds {licenses}"

        # Default
        return "Experienced financial advisor seeking new opportunities"

    async def _send_proactive_message(
        self,
        conversation_reference: Dict[str, Any],
        text: str
    ) -> bool:
        """
        Send proactive message to Teams using conversation reference.

        Args:
            conversation_reference: Serialized conversation reference
            text: Message text to send

        Returns:
            True if successful, False otherwise
        """
        try:
            from botbuilder.core import BotFrameworkAdapter, TurnContext
            from botbuilder.schema import Activity, ActivityTypes, ConversationAccount, ChannelAccount, ConversationReference
            from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
            from botbuilder.core.bot_framework_adapter import BotFrameworkAdapterSettings

            # Get credentials from environment
            app_id = os.getenv("MICROSOFT_APP_ID")
            app_password = os.getenv("MICROSOFT_APP_PASSWORD")

            if not app_id or not app_password:
                logger.error("MICROSOFT_APP_ID or MICROSOFT_APP_PASSWORD not configured")
                return False

            # Create bot adapter
            settings = BotFrameworkAdapterSettings(app_id, app_password)
            adapter = BotFrameworkAdapter(settings)

            # Deserialize conversation reference
            conv_ref = ConversationReference(
                service_url=conversation_reference.get("service_url"),
                channel_id=conversation_reference.get("channel_id"),
                user=ChannelAccount(
                    id=conversation_reference["user"]["id"],
                    name=conversation_reference["user"].get("name", "")
                ) if conversation_reference.get("user") else None,
                conversation=ConversationAccount(
                    id=conversation_reference["conversation"]["id"],
                    is_group=conversation_reference["conversation"].get("is_group", False)
                ) if conversation_reference.get("conversation") else None,
                bot=ChannelAccount(
                    id=conversation_reference["bot"]["id"],
                    name=conversation_reference["bot"].get("name", "")
                ) if conversation_reference.get("bot") else None
            )

            # Send proactive message
            async def callback(turn_context: TurnContext):
                await turn_context.send_activity(Activity(
                    type=ActivityTypes.message,
                    text=text
                ))

            await adapter.continue_conversation(
                conv_ref,
                callback,
                app_id
            )

            logger.info(f"Sent proactive message: {text[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to send proactive message: {e}", exc_info=True)
            return False

    async def _send_results_card(
        self,
        conversation_reference: Optional[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        total_analyzed: int
    ):
        """
        Send adaptive card with results to Teams using proactive messaging.
        """
        try:
            from botbuilder.core import BotFrameworkAdapter, TurnContext, MessageFactory, CardFactory
            from botbuilder.schema import Activity, ActivityTypes, ConversationAccount, ChannelAccount, ConversationReference
            from botbuilder.core.bot_framework_adapter import BotFrameworkAdapterSettings

            if not conversation_reference:
                logger.warning("No conversation reference - cannot send results card")
                return

            # Generate adaptive card
            card = create_marketable_candidates_card(candidates, total_analyzed)

            # Get credentials from environment
            app_id = os.getenv("MICROSOFT_APP_ID")
            app_password = os.getenv("MICROSOFT_APP_PASSWORD")

            if not app_id or not app_password:
                logger.error("MICROSOFT_APP_ID or MICROSOFT_APP_PASSWORD not configured")
                return

            # Create bot adapter
            settings = BotFrameworkAdapterSettings(app_id, app_password)
            adapter = BotFrameworkAdapter(settings)

            # Deserialize conversation reference
            conv_ref = ConversationReference(
                service_url=conversation_reference.get("service_url"),
                channel_id=conversation_reference.get("channel_id"),
                user=ChannelAccount(
                    id=conversation_reference["user"]["id"],
                    name=conversation_reference["user"].get("name", "")
                ) if conversation_reference.get("user") else None,
                conversation=ConversationAccount(
                    id=conversation_reference["conversation"]["id"],
                    is_group=conversation_reference["conversation"].get("is_group", False)
                ) if conversation_reference.get("conversation") else None,
                bot=ChannelAccount(
                    id=conversation_reference["bot"]["id"],
                    name=conversation_reference["bot"].get("name", "")
                ) if conversation_reference.get("bot") else None
            )

            # Send adaptive card via proactive message
            async def callback(turn_context: TurnContext):
                attachment = CardFactory.adaptive_card(card)
                message = MessageFactory.attachment(attachment)
                await turn_context.send_activity(message)

            await adapter.continue_conversation(
                conv_ref,
                callback,
                app_id
            )

            logger.info(f"Sent results card with {len(candidates)} candidates")

        except Exception as e:
            logger.error(f"Error sending results card: {e}", exc_info=True)

    async def close(self):
        """Close Service Bus connections."""
        try:
            if self._receiver:
                await self._receiver.close()
            if self._client:
                await self._client.close()
            logger.info("Worker connections closed")
        except Exception as e:
            logger.error(f"Error closing worker: {e}")


async def main():
    """Main entry point for running worker."""
    worker = VaultMarketabilityWorker()
    await worker.start()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
