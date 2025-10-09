"""
Natural Language Query Engine for Teams Bot.

Provides intelligent query processing with tiered access control:
- Executive users: Full access to all business data
- Regular users: Filtered by owner_email to their own records
"""
import logging
import json
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import asyncpg
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class QueryEngine:
    """Natural language query engine for Teams Bot - all users have full access."""

    def __init__(self):
        """Initialize query engine with OpenAI client."""
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-5-mini"  # Fast model for query classification

    async def process_query(
        self,
        query: str,
        user_email: str,
        db: asyncpg.Connection = None,  # Optional for backward compatibility
        conversation_context: Optional[str] = None,  # Conversation history for context
        override_intent: Optional[Dict[str, Any]] = None  # NEW: Skip classification if provided
    ) -> Dict[str, Any]:
        """
        Process natural language query using ZohoClient - all users have full access.

        Args:
            query: User's natural language query
            user_email: Email of requesting user (for logging only)
            db: Database connection (no longer used, kept for compatibility)
            conversation_context: Optional conversation history for context-aware classification
            override_intent: Optional intent to skip classification (used after clarification)

        Returns:
            Dict with:
            - text: Response text for user
            - card: Optional Adaptive Card (None for now)
            - data: Raw query results
            - confidence_score: Intent classification confidence (0.0-1.0)
        """
        try:
            logger.info(f"Processing query from {user_email}: {query}")

            # Step 1: Classify intent OR use override
            if override_intent:
                intent = override_intent
                confidence = 1.0  # User clarified, now certain
                logger.info("Using override intent, skipping classification")
            else:
                # Normal classification path
                intent, confidence = await self._classify_intent(query, conversation_context)

            # Step 2: Handle transcript summary requests separately
            if intent.get("intent_type") == "transcript_summary":
                return await self._handle_transcript_summary(intent)

            # Step 3: No owner filtering - all users see all data
            intent["owner_filter"] = None

            # Step 4: Build and execute Zoho query
            results, _ = await self._build_query(intent)
            logger.info(f"Querying Zoho CRM with intent: {intent}")

            # Step 5: CRITICAL - Preserve async format flow (user's final correction)
            response = await self._format_response(query, results, intent)

            # Step 6: Inject confidence score
            response["confidence_score"] = confidence

            logger.info(f"Query completed: {len(results)} results returned (confidence: {confidence:.2f})")
            return response

        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return {
                "text": f"❌ Sorry, I encountered an error processing your query: {str(e)}",
                "card": None,
                "data": None,
                "confidence_score": 0.0
            }

    async def _classify_intent(
        self,
        query: str,
        conversation_context: Optional[str] = None
    ) -> Tuple[Dict[str, Any], float]:
        """
        Classify user intent using GPT-5-mini with conversation context.

        Args:
            query: User's natural language query
            conversation_context: Optional conversation history for context awareness

        Returns:
            Tuple of (intent dict, confidence score):
            - intent_type: "count", "list", "aggregate", "search"
            - entities: Extracted entities (dates, names, etc.)
            - table: Primary table to query
            - filters: Query filters
            - confidence: Float 0.0-1.0 indicating classification confidence
        """
        system_prompt = """You are a query classifier for a recruitment CRM system.
Classify the user's intent and extract key entities.

Available data sources:
- vault_candidates: Published candidates with Zoom interviews (candidate_name, candidate_locator, job_title, location, date_published, transcript_url, meeting_id)
- deals: Candidate deals in pipeline (deal_name, stage, contact_name, account_name, owner_email, created_at, modified_at)
- meetings: Events and meetings (subject, meeting_date, attendees, owner_email, related_to, location, created_at)

Pipeline Stages (for deals):
- Lead, Engaged, Meeting Booked, Meetings Completed, Awaiting Offer, Offer Extended, Closed Won, Closed Lost

Intent Types:
- count: Count records ("how many interviews", "total deals", "how many meetings")
- list: Show records ("show me candidates", "list deals", "list meetings")
- aggregate: Group by field ("breakdown by stage", "deals by owner")
- search: Find specific records ("find John Smith", "deals with Morgan Stanley", "meetings with Goldman Sachs")
- transcript_summary: Zoom interview summary for ONE specific candidate ("summarize interview with John Smith")

IMPORTANT: "summarize candidates" or "summarize advisors" = list intent (not transcript_summary)

Return JSON with:
{
    "intent_type": "count|list|aggregate|search|transcript_summary",
    "table": "vault_candidates|deals|meetings",
    "entities": {
        "timeframe": "last week|this month|Q4|September|etc",
        "entity_name": "person/company name",
        "search_terms": ["keywords"],
        "candidate_name": "if specific candidate name",
        "candidate_locator": "if TWAV ID mentioned (e.g., TWAV118252)",
        "meeting_id": "if Zoom meeting ID",
        "stage": "pipeline stage if mentioned"
    },
    "filters": {
        "stage": "pipeline stage filter",
        "created_after": "ISO date start",
        "created_before": "ISO date end"
    },
    "group_by": "field to aggregate on (stage, owner_email, etc)",
    "confidence": 0.0-1.0  // How confident you are in this classification
}

Examples:
- "how many interviews last week" → intent_type: "count", table: "vault_candidates", timeframe: "last week"
- "show me TWAV118252" → intent_type: "search", table: "vault_candidates", candidate_locator: "TWAV118252"
- "who is TWAV118220" → intent_type: "search", table: "vault_candidates", candidate_locator: "TWAV118220"
- "show me all deals in Meeting Booked stage" → intent_type: "list", table: "deals", stage: "Meeting Booked"
- "breakdown of deals by stage" → intent_type: "aggregate", table: "deals", group_by: "stage"
- "find deals with Goldman Sachs" → intent_type: "search", table: "deals", search_terms: ["Goldman Sachs"]
- "summarize financial advisor candidates" → intent_type: "list", table: "vault_candidates", candidate_type: "advisors"
- "summarize interview with John Smith" → intent_type: "transcript_summary", candidate_name: "John Smith"
"""

        # Build user prompt with conversation context if available
        context_text = ""
        if conversation_context:
            context_text = f"\nRecent conversation:\n{conversation_context}\n"

        user_prompt = f"""{context_text}Classify this query: "{query}"

Current date: {datetime.now().strftime('%Y-%m-%d')}

If conversation context is provided, use it to resolve ambiguous references (e.g., "what about last month?" after discussing deals).
Rate your confidence 0.0-1.0 based on clarity and context."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=1  # CRITICAL: Always use temperature=1 for GPT-5 models
            )

            intent = json.loads(response.choices[0].message.content)
            confidence = intent.pop("confidence", 0.8)  # Extract confidence, default 0.8
            logger.debug(f"Classified intent: {intent} (confidence: {confidence:.2f})")
            return intent, confidence

        except Exception as e:
            logger.error(f"Error classifying intent: {e}", exc_info=True)
            # Fallback to basic intent with low confidence
            return {
                "intent_type": "search",
                "table": "deals",
                "entities": {"search_terms": [query]},
                "filters": {}
            }, 0.3  # Low confidence for fallback

    async def _build_query(
        self,
        intent: Dict[str, Any]
    ) -> Tuple[List[Dict], List]:
        """
        Build query using ZohoClient for both vault_candidates and deals.

        Returns:
            Tuple of (results_list, empty_params_list)
        """
        from app.integrations import ZohoApiClient

        intent_type = intent.get("intent_type", "list")
        filters = intent.get("filters", {})
        owner_filter = intent.get("owner_filter")
        table = intent.get("table", "vault_candidates")  # Determine which table to query

        zoho_client = ZohoApiClient()

        # Get entities from intent
        entities = intent.get("entities", {})

        # Route to appropriate query method based on table
        if table == "deals":
            # Build deal query filters
            deal_filters = {
                "limit": 500
            }

            # Apply owner filtering for regular users (not executives)
            if owner_filter:
                deal_filters["owner_email"] = owner_filter

            # Parse timeframe entity and convert to dates
            if "timeframe" in entities and entities["timeframe"]:
                timeframe = str(entities["timeframe"]).lower().replace(" ", "_")
                now = datetime.now()

                # 7-day windows
                if any(token in timeframe for token in ["7d", "last_week", "this_week"]):
                    deal_filters["from_date"] = now - timedelta(days=7)
                    deal_filters["to_date"] = now

                # 30-day windows
                elif "30d" in timeframe:
                    deal_filters["from_date"] = now - timedelta(days=30)
                    deal_filters["to_date"] = now

                # Current month
                elif "this_month" in timeframe:
                    deal_filters["from_date"] = now.replace(day=1, hour=0, minute=0, second=0)
                    deal_filters["to_date"] = now

                # Previous month
                elif "last_month" in timeframe:
                    last_month = now.replace(day=1) - timedelta(days=1)
                    deal_filters["from_date"] = last_month.replace(day=1, hour=0, minute=0, second=0)
                    deal_filters["to_date"] = last_month.replace(hour=23, minute=59, second=59)

                # Q4 (Oct-Dec)
                elif "q4" in timeframe:
                    deal_filters["from_date"] = datetime(now.year, 10, 1)
                    deal_filters["to_date"] = datetime(now.year, 12, 31, 23, 59, 59)

            # Date filters from intent (convert ISO strings to datetime)
            if "created_after" in filters:
                deal_filters["from_date"] = datetime.fromisoformat(filters["created_after"].replace('Z', '+00:00'))
            if "created_before" in filters:
                deal_filters["to_date"] = datetime.fromisoformat(filters["created_before"].replace('Z', '+00:00'))

            # Stage filter
            if "stage" in filters:
                deal_filters["stage"] = filters["stage"]
            elif "stage" in entities:
                deal_filters["stage"] = entities["stage"]

            # Entity name filters (contact or account)
            if "entity_name" in entities:
                # Could be either contact or company - search both fields via client-side filter
                deal_filters["limit"] = 500  # Increase limit for name search

            # Remove None values
            deal_filters = {k: v for k, v in deal_filters.items() if v is not None}

            logger.info(f"Querying Zoho deals with filters: {deal_filters}")

            try:
                results = await zoho_client.query_deals(**deal_filters)

                # Client-side filtering by entity name (contact or account)
                if entities.get("entity_name"):
                    search_name = entities["entity_name"].lower()
                    filtered = [
                        d for d in results
                        if (search_name in (d.get('contact_name') or '').lower() or
                            search_name in (d.get('account_name') or '').lower())
                    ]
                    logger.info(f"Filtered {len(results)} → {len(filtered)} deals by name '{entities['entity_name']}'")
                    results = filtered

                return results, []
            except Exception as e:
                logger.error(f"Error querying Zoho deals: {e}", exc_info=True)
                return [], []

        elif table == "meetings":
            # Build meeting query filters
            meeting_filters = {
                "limit": 500
            }

            # Apply owner filtering for regular users (not executives)
            if owner_filter:
                meeting_filters["owner_email"] = owner_filter

            # Parse timeframe entity and convert to dates
            if "timeframe" in entities and entities["timeframe"]:
                timeframe = str(entities["timeframe"]).lower().replace(" ", "_")
                now = datetime.now()

                # 7-day windows
                if any(token in timeframe for token in ["7d", "last_week", "this_week"]):
                    meeting_filters["from_date"] = now - timedelta(days=7)
                    meeting_filters["to_date"] = now

                # 30-day windows
                elif "30d" in timeframe:
                    meeting_filters["from_date"] = now - timedelta(days=30)
                    meeting_filters["to_date"] = now

                # Current month
                elif "this_month" in timeframe:
                    meeting_filters["from_date"] = now.replace(day=1, hour=0, minute=0, second=0)
                    meeting_filters["to_date"] = now

                # Previous month
                elif "last_month" in timeframe:
                    last_month = now.replace(day=1) - timedelta(days=1)
                    meeting_filters["from_date"] = last_month.replace(day=1, hour=0, minute=0, second=0)
                    meeting_filters["to_date"] = last_month.replace(hour=23, minute=59, second=59)

                # Q4 (Oct-Dec)
                elif "q4" in timeframe:
                    meeting_filters["from_date"] = datetime(now.year, 10, 1)
                    meeting_filters["to_date"] = datetime(now.year, 12, 31, 23, 59, 59)

            # Date filters from intent (convert ISO strings to datetime)
            if "created_after" in filters:
                meeting_filters["from_date"] = datetime.fromisoformat(filters["created_after"].replace('Z', '+00:00'))
            if "created_before" in filters:
                meeting_filters["to_date"] = datetime.fromisoformat(filters["created_before"].replace('Z', '+00:00'))

            # Remove None values
            meeting_filters = {k: v for k, v in meeting_filters.items() if v is not None}

            logger.info(f"Querying Zoho meetings with filters: {meeting_filters}")

            try:
                results = await zoho_client.query_meetings(**meeting_filters)

                # Client-side OR filtering by entity name (event title OR related record)
                # This allows matching either field, not requiring both (server-side would be AND)
                if "entity_name" in entities:
                    search_name = entities["entity_name"].lower()
                    filtered = [
                        m for m in results
                        if (search_name in (m.get('subject') or '').lower() or
                            search_name in (m.get('event_title') or '').lower() or
                            search_name in (m.get('related_to') or '').lower())
                    ]
                    logger.info(f"Filtered {len(results)} → {len(filtered)} meetings by name '{entities['entity_name']}'")
                    results = filtered

                return results, []
            except Exception as e:
                logger.error(f"Error querying Zoho meetings: {e}", exc_info=True)
                return [], []

        else:  # vault_candidates (default)
            # Build Zoho query filters for candidates
            zoho_filters = {
                "published_to_vault": True,  # Always query vault
                "limit": 500  # ✅ Handle all 144 vault candidates with headroom
            }

            # Apply owner filtering for regular users (not executives)
            if owner_filter:
                zoho_filters["owner"] = owner_filter

            # Parse timeframe entity and convert to dates
            if "timeframe" in entities and entities["timeframe"]:
                timeframe = str(entities["timeframe"]).lower().replace(" ", "_")  # Normalize "last week" → "last_week"
                now = datetime.now()

                # 7-day windows
                if any(token in timeframe for token in ["7d", "last_week", "this_week"]):
                    filters["created_after"] = (now - timedelta(days=7)).isoformat()
                    filters["created_before"] = now.isoformat()

                # 30-day windows
                elif "30d" in timeframe:
                    filters["created_after"] = (now - timedelta(days=30)).isoformat()
                    filters["created_before"] = now.isoformat()

                # Current month
                elif "this_month" in timeframe:
                    filters["created_after"] = now.replace(day=1, hour=0, minute=0, second=0).isoformat()
                    filters["created_before"] = now.isoformat()

                # Previous month
                elif "last_month" in timeframe:
                    last_month = now.replace(day=1) - timedelta(days=1)
                    filters["created_after"] = last_month.replace(day=1, hour=0, minute=0, second=0).isoformat()
                    filters["created_before"] = last_month.replace(hour=23, minute=59, second=59).isoformat()

                # Q4 (Oct-Dec)
                elif "q4" in timeframe:
                    filters["created_after"] = datetime(now.year, 10, 1).isoformat()
                    filters["created_before"] = datetime(now.year, 12, 31, 23, 59, 59).isoformat()

                # Specific months
                elif "september" in timeframe or "sep" in timeframe:
                    filters["created_after"] = f"{now.year}-09-01"
                    filters["created_before"] = f"{now.year}-09-30"
                elif "october" in timeframe or "oct" in timeframe:
                    filters["created_after"] = f"{now.year}-10-01"
                    filters["created_before"] = f"{now.year}-10-31"

            # Date filters
            if "created_after" in filters:
                zoho_filters["from_date"] = filters["created_after"]

            if "created_before" in filters:
                zoho_filters["to_date"] = filters["created_before"]

            # Candidate type filter (advisors, c_suite, global)
            if "candidate_type" in entities:
                zoho_filters["candidate_type"] = entities["candidate_type"]

            # Candidate Locator ID filter (exact match, highest priority)
            if "candidate_locator" in entities and entities["candidate_locator"]:
                # Don't need large limit for exact ID match
                zoho_filters["limit"] = 10
                logger.info(f"Searching by Candidate Locator ID: {entities['candidate_locator']}")

            # Increase limit if searching by name (need more candidates to search through)
            elif "entity_name" in entities or "candidate_name" in entities:
                zoho_filters["limit"] = 500  # Fetch more for name search

            # Remove None values
            zoho_filters = {k: v for k, v in zoho_filters.items() if v is not None}

            logger.info(f"Querying Zoho vault candidates with filters: {zoho_filters}")

            try:
                results = await zoho_client.query_candidates(**zoho_filters)

                # Client-side filtering by candidate locator ID (exact match, highest priority)
                candidate_locator = entities.get("candidate_locator")
                if candidate_locator and results:
                    locator_upper = candidate_locator.upper()
                    filtered = [
                        c for c in results
                        if c.get('candidate_locator', '').upper() == locator_upper
                    ]
                    logger.info(f"Filtered {len(results)} → {len(filtered)} by Candidate Locator '{candidate_locator}'")
                    results = filtered

                # Client-side filtering by candidate name if specified
                elif entities.get("entity_name") or entities.get("candidate_name"):
                    search_name = entities.get("entity_name") or entities.get("candidate_name")
                    search_lower = search_name.lower()
                    filtered = [
                        c for c in results
                        if search_lower in c.get('candidate_name', '').lower()
                    ]
                    logger.info(f"Filtered {len(results)} → {len(filtered)} by name '{search_name}'")
                    results = filtered

                return results, []
            except Exception as e:
                logger.error(f"Error querying Zoho CRM: {e}", exc_info=True)
                return [], []

    async def _format_response(
        self,
        query: str,
        results: List[asyncpg.Record],
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format query results into user-friendly response.

        Returns:
            Dict with text, card (optional), and data
        """
        intent_type = intent.get("intent_type", "list")
        table = intent.get("table", "vault_candidates") or "vault_candidates"  # Default to vault_candidates, handle None

        # Handle empty results
        if not results:
            # More helpful error message with table name
            table_display = "vault candidates" if table == "vault_candidates" else table
            return {
                "text": f"I didn't find any {table_display} matching your query.",
                "card": None,
                "data": None
            }

        # Format based on intent type
        if intent_type == "count":
            # For Zoho API, results is a list of records, not a count aggregate
            count = len(results)
            # Use correct table name in response
            table_labels = {
                "vault_candidates": "vault candidates",
                "deals": "deals",
                "meetings": "meetings",
                "deal_notes": "notes"
            }
            label = table_labels.get(table, "records")
            return {
                "text": f"Found {count} {label}.",
                "card": None,
                "data": {"count": count}
            }

        elif intent_type == "aggregate":
            # Format stage aggregation
            text = "Here's the breakdown:\n\n"
            for row in results:
                text += f"- {row['stage']}: {row['count']}\n"
            return {
                "text": text,
                "card": None,
                "data": [dict(row) for row in results]
            }

        else:  # list or search
            # Format based on table
            if table == "deals":
                text = f"Found {len(results)} deals:\n\n"
                for i, row in enumerate(results[:5], 1):
                    text += f"{i}. {row['deal_name']}\n"
                    text += f"   Contact: {row['contact_name'] or 'N/A'}\n"
                    text += f"   Company: {row['account_name'] or 'N/A'}\n"
                    text += f"   Stage: {row['stage'] or 'N/A'}\n"
                    # Safe datetime formatting with fallback
                    created_date = row.get('created_at')
                    created_str = created_date.strftime('%Y-%m-%d') if created_date else 'N/A'
                    text += f"   Created: {created_str}\n\n"

                if len(results) > 5:
                    text += f"\n...and {len(results) - 5} more."

            elif table == "deal_notes":
                text = f"Found {len(results)} notes:\n\n"
                for i, row in enumerate(results[:5], 1):
                    text += f"{i}. {row['note_content'][:100]}...\n"
                    text += f"   By: {row['created_by'] or 'N/A'}\n"
                    # Safe datetime formatting with fallback
                    created_date = row.get('created_at')
                    created_str = created_date.strftime('%Y-%m-%d') if created_date else 'N/A'
                    text += f"   Date: {created_str}\n\n"

                if len(results) > 5:
                    text += f"\n...and {len(results) - 5} more."

            elif table == "meetings":
                text = f"Found {len(results)} meetings:\n\n"
                for i, row in enumerate(results[:5], 1):
                    text += f"{i}. {row['subject']}\n"
                    # Safe datetime formatting with fallback
                    meeting_date = row.get('meeting_date')
                    date_str = meeting_date.strftime('%Y-%m-%d %H:%M') if meeting_date else 'N/A'
                    text += f"   Date: {date_str}\n"
                    if row.get('attendees'):
                        text += f"   Attendees: {', '.join(row['attendees'][:3])}\n"
                    text += "\n"

                if len(results) > 5:
                    text += f"\n...and {len(results) - 5} more."

            else:  # Default: vault candidates (from Zoho API)
                text = f"Found {len(results)} vault candidates:\n\n"
                for i, row in enumerate(results[:5], 1):
                    name = row.get('candidate_name', 'Unknown')
                    title = row.get('job_title', 'No title')
                    location = row.get('location', 'No location')
                    pub_date = row.get('date_published', 'No date')
                    transcript = row.get('transcript_url', '')

                    text += f"{i}. {name}\n"
                    text += f"   Title: {title}\n"
                    text += f"   Location: {location}\n"
                    text += f"   Published: {pub_date}\n"
                    if transcript:
                        text += f"   📹 Zoom transcript available\n"
                    text += "\n"

                if len(results) > 5:
                    text += f"\n...and {len(results) - 5} more."

            return {
                "text": text,
                "card": None,  # TODO: Implement Adaptive Card formatting
                "data": results if isinstance(results, list) else [dict(row) for row in results]
            }

    async def _handle_transcript_summary(
        self,
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle transcript summary requests by fetching Zoom transcript and generating AI summary.

        Args:
            intent: Classified intent with candidate_name or meeting_id

        Returns:
            Response dict with summary text
        """
        from app.zoom_client import ZoomClient
        from app.integrations import ZohoApiClient

        entities = intent.get("entities", {})
        candidate_name = entities.get("candidate_name")
        meeting_id = entities.get("meeting_id")

        logger.info(f"Transcript summary request: candidate={candidate_name}, meeting_id={meeting_id}")

        try:
            # Step 1: Get candidate from vault if name provided
            transcript_url = None
            if candidate_name:
                zoho_client = ZohoApiClient()
                candidates = await zoho_client.query_candidates(
                    published_to_vault=True,
                    limit=500  # Fetch more to find the right candidate
                )

                # Find matching candidate
                matching_candidate = None
                for candidate in candidates:
                    name = candidate.get('candidate_name', '').lower()
                    if candidate_name.lower() in name:
                        matching_candidate = candidate
                        break

                if not matching_candidate:
                    return {
                        "text": f"❌ Could not find candidate '{candidate_name}' in vault.",
                        "card": None,
                        "data": None
                    }

                transcript_url = matching_candidate.get('transcript_url')
                meeting_id = matching_candidate.get('meeting_id')

                if not transcript_url and not meeting_id:
                    return {
                        "text": f"❌ No Zoom recording found for {matching_candidate.get('candidate_name')}.",
                        "card": None,
                        "data": None
                    }

            # Step 2: Fetch transcript from Zoom
            try:
                zoom_client = ZoomClient()
            except ValueError as e:
                # Zoom credentials not configured
                logger.warning(f"Zoom credentials not configured: {e}")
                return {
                    "text": "❌ Zoom transcript summaries are temporarily unavailable. Please contact your administrator to configure Zoom integration.",
                    "card": None,
                    "data": None
                }

            if meeting_id:
                transcript = await zoom_client.fetch_zoom_transcript_for_meeting(meeting_id)
            elif transcript_url:
                # Extract meeting ID from Zoom URL (multiple formats supported)
                import re

                # Try multiple URL patterns:
                # 1. /rec/share/{id}
                # 2. /rec/player/{id}
                # 3. ?startTime= before the share token
                patterns = [
                    r'/rec/share/([^/?&]+)',
                    r'/rec/player/([^/?&]+)',
                    r'share/([^/?&]+)',
                ]

                extracted_meeting_id = None
                for pattern in patterns:
                    match = re.search(pattern, transcript_url)
                    if match:
                        extracted_meeting_id = match.group(1)
                        logger.info(f"Extracted meeting ID '{extracted_meeting_id}' from URL using pattern: {pattern}")
                        break

                if extracted_meeting_id:
                    transcript = await zoom_client.fetch_zoom_transcript_for_meeting(extracted_meeting_id)
                else:
                    # Fallback: Use stored meeting_id hash if available
                    if meeting_id:
                        logger.warning(f"Could not extract meeting ID from URL, falling back to stored meeting_id: {meeting_id}")
                        transcript = await zoom_client.fetch_zoom_transcript_for_meeting(meeting_id)
                    else:
                        return {
                            "text": f"❌ Could not extract meeting ID from Zoom URL: {transcript_url[:100]}",
                            "card": None,
                            "data": None
                        }
            else:
                return {
                    "text": "❌ No meeting ID or transcript URL provided.",
                    "card": None,
                    "data": None
                }

            if not transcript:
                return {
                    "text": "❌ Could not fetch Zoom transcript. It may not be available yet.",
                    "card": None,
                    "data": None
                }

            # Step 3: Generate AI summary using GPT-5-mini
            summary = await self._summarize_transcript(transcript, candidate_name)

            return {
                "text": summary,
                "card": None,
                "data": {"transcript_length": len(transcript), "summary": summary}
            }

        except Exception as e:
            logger.error(f"Error handling transcript summary: {e}", exc_info=True)
            return {
                "text": f"❌ Error generating transcript summary: {str(e)}",
                "card": None,
                "data": None
            }

    async def _summarize_transcript(
        self,
        transcript: str,
        candidate_name: Optional[str] = None
    ) -> str:
        """
        Generate AI summary of Zoom transcript using GPT-5-mini.

        Args:
            transcript: Full Zoom transcript text
            candidate_name: Optional candidate name for context

        Returns:
            Formatted summary text
        """
        system_prompt = """You are an expert recruiter analyzing interview transcripts.
Provide a concise summary highlighting:
1. **Candidate Background**: Current role, firm, book size/AUM
2. **Key Qualifications**: Designations, production, achievements
3. **Motivations**: Why they're seeking a new opportunity
4. **Location Preferences**: Mobility, relocation preferences
5. **Red Flags**: Any concerns or dealbreakers

Keep the summary under 500 words and use bullet points for readability."""

        user_prompt = f"""Summarize this interview transcript:

{transcript[:8000]}  # Limit to ~8K chars to fit context window

Candidate: {candidate_name if candidate_name else 'Unknown'}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=1,  # CRITICAL: Always use temperature=1 for GPT-5 models
                max_tokens=1000
            )

            summary = response.choices[0].message.content
            logger.info(f"Generated transcript summary ({len(summary)} chars)")
            return f"📹 **Interview Summary**\n\n{summary}"

        except Exception as e:
            logger.error(f"Error generating summary: {e}", exc_info=True)
            return f"❌ Error generating summary: {str(e)}"


async def process_natural_language_query(
    query: str,
    user_email: str,
    db: asyncpg.Connection,
    conversation_context: Optional[str] = None,
    override_intent: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to process natural language queries.

    Args:
        query: User's natural language query
        user_email: Email of requesting user
        db: Database connection
        conversation_context: Optional conversation history for context
        override_intent: Optional intent to skip classification (used after clarification)

    Returns:
        Response dict with text, card, and data
    """
    engine = QueryEngine()
    return await engine.process_query(query, user_email, db, conversation_context, override_intent)
