"""
Natural Language Query Engine for Teams Bot.

Provides intelligent query processing with role-based financial data access:
- ALL users: Full access to all business data (no owner filtering)
- Executive users (Steve, Brandon, Daniel): See all fields including financial data
- Regular recruiters: See all data but financial fields are redacted
"""
import logging
import json
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, timezone
import asyncpg
from openai import AsyncAzureOpenAI

from app.config.candidate_keywords import normalize_candidate_type
from app.integrations import ZohoApiClient
from app.api.teams.zoho_module_registry import get_module_registry, is_executive
from app.repositories.zoho_repository import ZohoLeadsRepository

logger = logging.getLogger(__name__)

class QueryEngine:
    """Natural language query engine for Teams Bot - all users have full access."""

    def __init__(self):
        """Initialize query engine with Azure OpenAI client."""
        # Use Azure OpenAI (not regular OpenAI API)
        self.client = AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
        self.redis_manager = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Lazy initialization of Redis client."""
        if self._initialized:
            return

        try:
            from well_shared.cache.redis_manager import get_cache_manager

            # Initialize Redis manager
            self.redis_manager = await get_cache_manager()

            if self.redis_manager:
                # Test connection
                await self.redis_manager.connect()
                logger.info("QueryEngine initialized successfully with Redis")
            else:
                logger.warning("QueryEngine initialized without Redis - circuit breaker unavailable")

            self._initialized = True

        except Exception as e:
            logger.warning(f"QueryEngine initialization failed: {e}")
            # Don't raise - allow degraded operation
            self._initialized = True  # Mark as initialized to prevent retry loops

    def _check_user_role(self, user_email: str) -> str:
        """
        Check if user is executive (full financial access) or recruiter (no financial data).

        Args:
            user_email: User's email address

        Returns:
            "executive" if Steve/Brandon/Daniel, "recruiter" otherwise
        """
        return "executive" if is_executive(user_email) else "recruiter"

    async def process_query(
        self,
        query: str,
        user_email: str,
        db: asyncpg.Connection = None,  # Optional for backward compatibility
        conversation_context: Optional[str] = None,  # Conversation history for context
        override_intent: Optional[Dict[str, Any]] = None,  # Skip classification if provided
        activity: Optional[Any] = None  # Bot Framework Activity for proactive messaging
    ) -> Dict[str, Any]:
        """
        Process natural language query using ZohoClient - all users have full access.

        Args:
            query: User's natural language query
            user_email: Email of requesting user (for logging only)
            db: Database connection (no longer used, kept for compatibility)
            conversation_context: Optional conversation history for context-aware classification
            override_intent: Optional intent to skip classification (used after clarification)
            activity: Optional Bot Framework Activity for proactive messaging support

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

            # Step 2.5: Handle email query requests separately
            if intent.get("intent_type") == "email_query":
                return await self._handle_email_query(intent, user_email)

            # Step 2.6: Handle marketable candidates requests separately
            if intent.get("intent_type") == "marketable_candidates":
                return await self._handle_marketable_candidates(intent, user_email, activity)

            # Step 3: Determine user role for financial data filtering
            user_role = self._check_user_role(user_email)
            intent["user_role"] = user_role
            intent["user_email"] = user_email  # Pass for redaction
            logger.info(f"User {user_email} role: {user_role}")

            # Step 4: Build and execute query (PostgreSQL for vault, Zoho API for others)
            results, _ = await self._build_query(intent, db)
            if intent.get("validation_error"):
                logger.info("Validation error detected during query build; returning user message")
                return {
                    "text": intent["validation_error"],
                    "card": None,
                    "data": None,
                    "confidence_score": confidence,
                }
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
        Classify user intent using GPT-5-mini with conversation context and circuit breaker.

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
        await self._ensure_initialized()

        # Check circuit breaker BEFORE making expensive LLM call
        if self.redis_manager and self.redis_manager._is_circuit_breaker_open():
            logger.warning("Circuit breaker open - skipping LLM classification")
            # Return fallback intent with low confidence
            return {
                "intent_type": "search",
                "table": "deals",
                "entities": {"search_terms": [query]},
                "filters": {}
            }, 0.3

        # Dynamically load all 68 Zoho modules from registry
        registry = get_module_registry()
        queryable_modules = registry.get_queryable_modules()

        # Build module descriptions
        module_descriptions = []
        for module_name in queryable_modules[:20]:  # Show top 20 to avoid token limits
            meta = registry.get_module_metadata(module_name)
            singular = meta.get("singular_label", module_name)
            plural = meta.get("plural_label", module_name)
            field_count = len(meta.get("fields", {}))
            module_descriptions.append(f"- {module_name} ({singular}/{plural}): {field_count} fields available")

        # Add special data sources
        module_descriptions.extend([
            "- emails: User inbox via Microsoft Graph (subject, from_address, body, attachments)",
            "\nNote: 68 total Zoho modules available - use module aliases like 'candidates'→Leads, 'jobs'→Jobs, 'submissions'→Submissions"
        ])

        available_modules_text = "\n".join(module_descriptions)

        system_prompt = f"""You are a query classifier for a recruitment CRM system with access to ALL Zoho CRM modules.
Classify the user's intent and extract key entities.

Available data sources (top 20 shown, 68 total available):
{available_modules_text}

Common module aliases (user-friendly names):
- candidates/candidate → Leads
- jobs/job/positions → Jobs
- submissions/submission → Submissions
- contacts/contact → Contacts
- accounts/companies → Accounts
- deals/opportunities → Deals
- tasks/todos → Tasks
- events/meetings → Events
- calls → Calls
- invoices/bills → Invoices
- payments → Payments
- campaigns → Campaigns

Pipeline Stages (for deals):
- Lead, Engaged, Meeting Booked, Meetings Completed, Awaiting Offer, Offer Extended, Closed Won, Closed Lost

Intent Types:
- count: Count records ("how many interviews", "total deals", "how many meetings", "how many emails")
- list: Show records ("show me candidates", "list deals", "list meetings", "show my emails")
- aggregate: Group by field ("breakdown by stage", "deals by owner", "emails by sender")
- search: Find specific records ("find John Smith", "deals with Morgan Stanley", "meetings with Goldman Sachs", "emails from recruiter@company.com")
- transcript_summary: Zoom interview summary for ONE specific candidate ("summarize interview with John Smith")
- email_query: Search user's inbox via Microsoft Graph ("show my recent emails", "emails about candidates", "find emails from Morgan Stanley")
- marketable_candidates: Find top N most marketable vault candidates ("give me the 10 most marketable candidates", "top 5 marketable advisors", "best candidates from the vault")

IMPORTANT: "summarize candidates" or "summarize advisors" = list intent (not transcript_summary)

Return JSON with:
{
    "intent_type": "count|list|aggregate|search|transcript_summary|email_query|marketable_candidates|query_module",
    "table": "Leads|Jobs|Submissions|Contacts|Accounts|Deals|Tasks|Events|Calls|Invoices|Payments|Campaigns|<any_zoho_module>|emails",
    "module_alias": "user's friendly name if provided (e.g., 'candidates', 'jobs')",
    "entities": {
        "timeframe": "last week|this month|Q4|September|etc",
        "entity_name": "person/company name",
        "search_terms": ["keywords"],
        "candidate_name": "if specific candidate name",
        "candidate_locator": "if TWAV ID mentioned (e.g., TWAV118252)",
        "meeting_id": "if Zoom meeting ID",
        "stage": "pipeline stage if mentioned",
        "email_sender": "if filtering by email sender",
        "email_subject": "if searching by subject",
        "hours_back": 24,  // Hours to look back for emails (default: 24)
        "limit": 10  // For marketable_candidates: number of candidates to return (default: 10)
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
- "show my recent emails" → intent_type: "email_query", table: "emails", hours_back: 24
- "emails about candidates from last week" → intent_type: "email_query", table: "emails", search_terms: ["candidates"], timeframe: "last week"
- "find emails from Morgan Stanley" → intent_type: "email_query", table: "emails", email_sender: "Morgan Stanley"
- "give me the 10 most marketable candidates" → intent_type: "marketable_candidates", table: "vault_candidates", limit: 10
- "top 5 marketable advisors from the vault" → intent_type: "marketable_candidates", table: "vault_candidates", limit: 5
- "show me the best candidates" → intent_type: "marketable_candidates", table: "vault_candidates", limit: 10

NEW MODULES (use exact module names or resolve aliases):
- "show me jobs in Texas" → intent_type: "list", table: "Jobs", search_terms: ["Texas"]
- "find open positions" → intent_type: "list", table: "Jobs", filters: {"status": "Open"}
- "submissions for TWAV109867" → intent_type: "search", table: "Submissions", search_terms: ["TWAV109867"]
- "pending submissions" → intent_type: "list", table: "Submissions", filters: {"status": "Pending"}
- "contacts at Morgan Stanley" → intent_type: "search", table: "Contacts", search_terms: ["Morgan Stanley"]
- "show me accounts" → intent_type: "list", table: "Accounts"
- "invoices from last quarter" → intent_type: "list", table: "Invoices", timeframe: "Q4"
- "unpaid invoices" → intent_type: "list", table: "Invoices", filters: {"status": "Unpaid"}
- "my pending tasks" → intent_type: "list", table: "Tasks", filters: {"status": "Pending"}
- "high priority tasks" → intent_type: "list", table: "Tasks", filters: {"priority": "High"}
- "active campaigns" → intent_type: "list", table: "Campaigns", filters: {"status": "Active"}
- "payments from last month" → intent_type: "list", table: "Payments", timeframe: "last month"

OWNER/EMPLOYEE NAME RECOGNITION:
When a query mentions a person's name (e.g., "Jay", "Steve", "Brandon", "Daniel"), treat it as an owner/person search:
- "How many deals has Jay made?" → intent_type: "count", table: "Deals", search_terms: ["Jay"], entity_name: "Jay"
- "Show me Jay's jobs" → intent_type: "list", table: "Jobs", search_terms: ["Jay"], entity_name: "Jay"
- "Submissions by Brandon" → intent_type: "list", table: "Submissions", search_terms: ["Brandon"], entity_name: "Brandon"
- "Daniel's deals" → intent_type: "list", table: "Deals", search_terms: ["Daniel"], entity_name: "Daniel"

IMPORTANT:
1. For any module query, resolve user-friendly aliases to official module names using the mapping above
2. When a person's name appears in the query, add it to both search_terms and entity_name for owner filtering
3. Be confident (>0.7) when recognizing common first names as employee references
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

            # DO NOT call record_success() - not a public helper
            return intent, confidence

        except Exception as e:
            logger.error(f"Error classifying intent: {e}", exc_info=True)

            # Record circuit breaker failure
            if self.redis_manager:
                self.redis_manager._record_circuit_breaker_failure()

            # Fallback to basic intent with low confidence
            return {
                "intent_type": "search",
                "table": "deals",
                "entities": {"search_terms": [query]},
                "filters": {}
            }, 0.3  # Low confidence for fallback

    async def _build_query(
        self,
        intent: Dict[str, Any],
        db: asyncpg.Connection = None
    ) -> Tuple[List[Dict], List]:
        """
        Build query using repository (PostgreSQL) for vault_candidates and ZohoClient for other modules.

        Returns:
            Tuple of (results_list, empty_params_list)
        """
        intent_type = intent.get("intent_type", "list")
        filters = intent.get("filters", {})
        user_role = intent.get("user_role", "recruiter")  # For financial redaction
        user_email = intent.get("user_email", "")  # For financial redaction
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

            # NO owner filtering - all users see all deals

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

            if self._validate_date_range(deal_filters, intent, "deals"):
                return [], []

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

            # NO owner filtering - all users see all meetings

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

            if self._validate_date_range(meeting_filters, intent, "meetings"):
                return [], []

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

        elif table in ["vault_candidates", "vault", "candidates"]:  # vault_candidates
            # Build Zoho API query filters for vault candidates (REAL-TIME DATA)
            zoho_filters = {
                "limit": 500,  # Fetch up to 500 candidates
                "published_to_vault": True  # Only vault candidates
            }

            # NO owner filtering - all users see all vault candidates

            # Parse timeframe entity and convert to dates
            if "timeframe" in entities and entities["timeframe"]:
                timeframe = str(entities["timeframe"]).lower().replace(" ", "_")  # Normalize "last week" → "last_week"
                now = datetime.now()

                # 7-day windows
                if any(token in timeframe for token in ["7d", "last_week", "this_week"]):
                    zoho_filters["from_date"] = now - timedelta(days=7)
                    zoho_filters["to_date"] = now

                # 30-day windows
                elif "30d" in timeframe:
                    zoho_filters["from_date"] = now - timedelta(days=30)
                    zoho_filters["to_date"] = now

                # Current month
                elif "this_month" in timeframe:
                    zoho_filters["from_date"] = now.replace(day=1, hour=0, minute=0, second=0)
                    zoho_filters["to_date"] = now

                # Previous month
                elif "last_month" in timeframe:
                    last_month = now.replace(day=1) - timedelta(days=1)
                    zoho_filters["from_date"] = last_month.replace(day=1, hour=0, minute=0, second=0)
                    zoho_filters["to_date"] = last_month.replace(hour=23, minute=59, second=59)

                # Q4 (Oct-Dec)
                elif "q4" in timeframe:
                    zoho_filters["from_date"] = datetime(now.year, 10, 1)
                    zoho_filters["to_date"] = datetime(now.year, 12, 31, 23, 59, 59)

                # Specific months
                elif "september" in timeframe or "sep" in timeframe:
                    zoho_filters["from_date"] = datetime(now.year, 9, 1)
                    zoho_filters["to_date"] = datetime(now.year, 9, 30, 23, 59, 59)
                elif "october" in timeframe or "oct" in timeframe:
                    zoho_filters["from_date"] = datetime(now.year, 10, 1)
                    zoho_filters["to_date"] = datetime(now.year, 10, 31, 23, 59, 59)

            # Date filters from SQL generation (override timeframe if present)
            if "created_after" in filters and filters["created_after"]:
                created_after = filters["created_after"]
                if isinstance(created_after, str) and created_after.strip():
                    # Handle ISO format with 'Z' suffix (replace with +00:00)
                    created_after = created_after.replace('Z', '+00:00')
                    zoho_filters["from_date"] = datetime.fromisoformat(created_after)
                elif isinstance(created_after, datetime):
                    zoho_filters["from_date"] = created_after

            if "created_before" in filters and filters["created_before"]:
                created_before = filters["created_before"]
                if isinstance(created_before, str) and created_before.strip():
                    # Handle ISO format with 'Z' suffix (replace with +00:00)
                    created_before = created_before.replace('Z', '+00:00')
                    zoho_filters["to_date"] = datetime.fromisoformat(created_before)
                elif isinstance(created_before, datetime):
                    zoho_filters["to_date"] = created_before

            # Candidate type filter (advisors, c_suite, global)
            raw_candidate_type = entities.get("candidate_type")
            if isinstance(raw_candidate_type, list):
                raw_candidate_type = raw_candidate_type[0] if raw_candidate_type else None

            normalized_candidate_type = normalize_candidate_type(raw_candidate_type)
            if normalized_candidate_type:
                if raw_candidate_type and raw_candidate_type != normalized_candidate_type:
                    logger.info(
                        "Normalized candidate_type '%s' to '%s' for vault query",
                        raw_candidate_type,
                        normalized_candidate_type,
                    )
                zoho_filters["candidate_type"] = normalized_candidate_type
                logger.info(f"Filtering by candidate type: {normalized_candidate_type}")

            # Build custom filters for client-side filtering
            custom_filters = {}

            # Candidate Locator ID filter (TWAV number - exact match, highest priority)
            if "candidate_locator" in entities and entities["candidate_locator"]:
                custom_filters["candidate_locator"] = entities["candidate_locator"].upper()
                zoho_filters["limit"] = 10  # Don't need large limit for exact ID match
                logger.info(f"Searching by Candidate Locator ID: {entities['candidate_locator']}")

            # Candidate name filter (partial match)
            elif "entity_name" in entities or "candidate_name" in entities:
                search_name = entities.get("entity_name") or entities.get("candidate_name")
                custom_filters["candidate_name"] = search_name
                zoho_filters["limit"] = 500  # Fetch more for name search
                logger.info(f"Searching by candidate name: {search_name}")

            # Location filter (city, state, or location)
            if "location" in entities and entities["location"]:
                custom_filters["location"] = entities["location"]

            # Company/Firm filter
            if "firm" in entities and entities["firm"]:
                custom_filters["company_name"] = entities["firm"]

            # Add custom filters if any
            if custom_filters:
                zoho_filters["custom_filters"] = custom_filters

            # Remove None values
            zoho_filters = {k: v for k, v in zoho_filters.items() if v is not None}

            logger.info(f"Querying PostgreSQL vault_candidates with filters: {zoho_filters}")

            try:
                # Query PostgreSQL zoho_leads table (fast local data)
                if not db:
                    logger.error("Database connection not available for vault query")
                    return [], []

                repo = ZohoLeadsRepository(db, redis_client=None)  # No Redis for now

                # Map filters from query engine to repository parameters
                repo_filters = {
                    "limit": zoho_filters.get("limit", 500),
                    "use_cache": False  # Disable cache for real-time queries
                }

                # Extract custom filters
                custom = zoho_filters.get("custom_filters", {})
                if custom.get("candidate_locator"):
                    repo_filters["candidate_locator"] = custom["candidate_locator"]
                if custom.get("location"):
                    repo_filters["location"] = custom["location"]

                # Map date filters (use from_date as after_date)
                if zoho_filters.get("from_date"):
                    repo_filters["after_date"] = zoho_filters["from_date"]

                # Query repository
                candidates = await repo.get_vault_candidates(**repo_filters)

                # Convert VaultCandidate models back to dicts for compatibility
                results = [c.dict() for c in candidates]

                logger.info(f"Found {len(results)} vault candidates from PostgreSQL (<100ms)")
                return results, []

            except Exception as e:
                logger.error(f"Error querying PostgreSQL vault_candidates: {e}", exc_info=True)
                return [], []

        else:
            # NEW: Generic module query handler for all other 65 modules
            # Resolve module alias to official name
            registry = get_module_registry()
            module_name = registry.resolve_module_alias(table)

            if not module_name:
                # Try using table name as-is (might already be official name)
                module_name = table

            logger.info(f"Querying generic Zoho module: {module_name}")

            # Build filters using FilterBuilder
            from app.api.teams.filter_builder import FilterBuilder
            builder = FilterBuilder(module_name)

            try:
                filter_params = builder.build_filters(entities, additional_filters=filters)

                # Query using new universal method
                results = await zoho_client.query_module(
                    module_name=module_name,
                    **filter_params,
                    limit=500
                )

                logger.info(f"Retrieved {len(results)} records from {module_name}")
                return results, []

            except Exception as e:
                logger.error(f"Error querying Zoho module '{module_name}': {e}", exc_info=True)
                return [], []

    def _normalize_module_name(self, table: str) -> str:
        """
        Normalize legacy module names to Zoho PascalCase format.

        Args:
            table: Module name from intent (e.g., "deals", "meetings", "vault_candidates")

        Returns:
            PascalCase module name (e.g., "Deals", "Events", "Leads")
        """
        module_mapping = {
            "deals": "Deals",
            "meetings": "Events",
            "vault_candidates": "Leads",
            "deal_notes": "Notes"
        }
        return module_mapping.get(table, table.title())

    def _convert_field_name_to_pascal_case(self, field_name: str) -> str:
        """
        Convert a single field name from snake_case to PascalCase.

        Args:
            field_name: Field name in snake_case (e.g., "stage", "invoice_status")

        Returns:
            Field name in PascalCase (e.g., "Stage", "Invoice_Status")
        """
        # Common field mappings (snake_case → PascalCase)
        field_mapping = {
            # Deal fields
            "deal_name": "Deal_Name",
            "contact_name": "Contact_Name",
            "account_name": "Account_Name",
            "stage": "Stage",
            "amount": "Amount",
            "created_at": "Created_Time",
            "modified_at": "Modified_Time",

            # Owner fields - ALWAYS map to safe keys in NEVER_REDACT_FIELDS
            # This prevents "Owner" from being flagged as financial
            "owner_email": "Owner_Email",  # Safe: in NEVER_REDACT_FIELDS
            "owner_name": "Owner_Name",    # Safe: in NEVER_REDACT_FIELDS
            "owner_id": "Owner_Id",        # Safe: in NEVER_REDACT_FIELDS
            "owner": "Owner_Email",        # Map generic "owner" to safe key

            # Meeting fields
            "subject": "Event_Title",
            "meeting_date": "Start_DateTime",
            "attendees": "Participants",

            # Candidate fields
            "candidate_name": "Full_Name",
            "job_title": "Designation",
            "location": "Current_Location",
            "date_published": "Date_Published_to_Vault",
            "transcript_url": "Zoom_Transcript_URL",

            # Common fields
            "id": "id",
            "note_content": "Note_Content",
            "created_by": "Created_By",

            # Status/state fields
            "status": "Status",
            "invoice_status": "Invoice_Status",
            "submission_status": "Submission_Status",
            "job_status": "Job_Status"
        }

        # Use mapping if available, otherwise convert snake_case to PascalCase
        if field_name in field_mapping:
            return field_mapping[field_name]
        else:
            # Convert snake_case to PascalCase: "my_field_name" → "My_Field_Name"
            return "_".join(word.capitalize() for word in field_name.split("_"))

    def _convert_to_pascal_case(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert snake_case field names to PascalCase for registry compatibility.

        Handles legacy snake_case payloads from query_deals/query_meetings.

        Args:
            record: Record dict with snake_case keys

        Returns:
            Record dict with PascalCase keys
        """
        converted = {}
        for key, value in record.items():
            # Use the field name converter
            new_key = self._convert_field_name_to_pascal_case(key)
            converted[new_key] = value

        return converted

    async def _format_response(
        self,
        query: str,
        results: List[asyncpg.Record],
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format query results into user-friendly response with financial data redaction.

        Returns:
            Dict with text, card (optional), and data
        """
        from app.api.teams.response_formatter import ResponseFormatter
        from app.api.teams.zoho_module_registry import filter_financial_data

        intent_type = intent.get("intent_type", "list")
        table = intent.get("table", "vault_candidates") or "vault_candidates"
        user_email = intent.get("user_email", "")

        # Normalize module name to PascalCase for registry compatibility
        normalized_module = self._normalize_module_name(table)

        # Convert asyncpg.Record to dict if needed (for PostgreSQL results)
        results_as_dicts = []
        for row in results:
            if isinstance(row, dict):
                results_as_dicts.append(row)
            else:
                # asyncpg.Record - convert to dict
                results_as_dicts.append(dict(row))

        # Handle empty results
        if not results_as_dicts:
            # Use ResponseFormatter for consistent empty response
            formatter = ResponseFormatter(normalized_module, user_email=user_email)
            return {
                "text": formatter._format_empty_response(intent_type),
                "card": None,
                "data": None
            }

        # Convert snake_case fields to PascalCase for registry compatibility
        # This is needed for legacy paths (deals, meetings, vault_candidates)
        # that normalize Zoho payloads to snake_case
        pascal_case_results = []
        for record in results_as_dicts:
            # Detect if record has snake_case keys (contains underscore in non-capitalized position)
            has_snake_case = any(
                "_" in key and not key[0].isupper()
                for key in record.keys()
                if key not in ["id"]  # Skip "id" which is lowercase in both formats
            )

            if has_snake_case:
                # Convert to PascalCase for registry compatibility
                converted = self._convert_to_pascal_case(record)
                pascal_case_results.append(converted)
                logger.debug(f"Converted snake_case record to PascalCase: {list(record.keys())[:3]} → {list(converted.keys())[:3]}")
            else:
                # Already in PascalCase (from new query_module path)
                pascal_case_results.append(record)

        # Apply financial field redaction for non-executives
        # This ensures recruiters see "---" for financial fields
        # IMPORTANT: Use normalized_module (PascalCase) and pascal_case_results
        filtered_results = [
            filter_financial_data(record, normalized_module, user_email)
            for record in pascal_case_results
        ]

        # Use ResponseFormatter for consistent formatting
        # IMPORTANT: Use normalized_module (PascalCase) for proper module detection
        formatter = ResponseFormatter(normalized_module, user_email=user_email)

        # Format based on intent type
        if intent_type == "count":
            count = len(filtered_results)
            text = formatter.format_count_response(count)
            return {
                "text": text,
                "card": None,
                "data": {"count": count}
            }

        elif intent_type == "aggregate":
            # For aggregate queries, get the group_by field from intent
            group_by = intent.get("group_by", "stage")

            # Convert group_by field to PascalCase to match converted record keys
            # This ensures record.get(group_by) finds the field after casing conversion
            group_by_pascal = self._convert_field_name_to_pascal_case(group_by)
            logger.debug(f"Converted group_by field: {group_by} → {group_by_pascal}")

            text = formatter.format_aggregate_response(filtered_results, group_by_pascal)
            return {
                "text": text,
                "card": None,
                "data": filtered_results
            }

        else:  # list or search
            # Use ResponseFormatter's module-aware formatting
            text = formatter.format_list_response(
                filtered_results,
                max_items=5,
                intent_type=intent_type
            )

            return {
                "text": text,
                "card": None,  # TODO: Implement Adaptive Card formatting
                "data": filtered_results
            }

    def _validate_date_range(
        self,
        filters: Dict[str, Any],
        intent: Dict[str, Any],
        table_name: str,
    ) -> bool:
        """Validate date bounds and set a user-friendly error when inverted.

        Returns True if validation fails so the caller can short-circuit before hitting Zoho.
        """
        from_date = self._ensure_datetime(filters.get("from_date"))
        to_date = self._ensure_datetime(filters.get("to_date"))

        if from_date and to_date and from_date > to_date:
            intent["validation_error"] = (
                "It looks like the start date comes after the end date. Please swap the dates and try again."
            )
            logger.info(
                "Skipping Zoho %s query due to invalid date range: %s > %s",
                table_name,
                from_date,
                to_date,
            )
            return True

        return False

    @staticmethod
    def _ensure_datetime(value: Any) -> Optional[datetime]:
        """Convert supported date representations to datetime objects for validation."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, str) and value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None

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

    async def _handle_email_query(
        self,
        intent: Dict[str, Any],
        user_email: str
    ) -> Dict[str, Any]:
        """
        Handle email query requests by fetching from Microsoft Graph API.

        Args:
            intent: Classified intent with email filters
            user_email: Email of requesting user

        Returns:
            Response dict with email results
        """
        from app.microsoft_graph_client import MicrosoftGraphClient
        entities = intent.get("entities", {})

        # Extract search parameters
        search_terms = entities.get("search_terms", [])
        email_sender = entities.get("email_sender")
        email_subject = entities.get("email_subject")
        hours_back = entities.get("hours_back", 24)

        # Convert timeframe to hours_back if specified
        timeframe = entities.get("timeframe")
        if timeframe:
            timeframe_lower = str(timeframe).lower().replace(" ", "_")
            if any(token in timeframe_lower for token in ["7d", "last_week", "this_week"]):
                hours_back = 168  # 7 days
            elif "30d" in timeframe_lower or "month" in timeframe_lower:
                hours_back = 720  # 30 days

        logger.info(f"Email query request: search_terms={search_terms}, sender={email_sender}, hours_back={hours_back}")

        try:
            # Step 1: Initialize Microsoft Graph client
            try:
                graph_client = MicrosoftGraphClient()
            except ValueError as e:
                # Microsoft Graph credentials not configured
                logger.warning(f"Microsoft Graph credentials not configured: {e}")
                return {
                    "text": "❌ Email queries require Microsoft Graph API configuration. Please contact your administrator to set up AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET.",
                    "card": None,
                    "data": None
                }

            # Step 2: Fetch emails for user
            emails = await graph_client.get_user_emails(
                user_email=user_email,
                filter_recruitment=True,  # Apply recruitment filtering
                hours_back=hours_back,
                max_emails=50
            )

            if not emails:
                return {
                    "text": f"📧 No emails found in the last {hours_back} hours.",
                    "card": None,
                    "data": []
                }

            # Step 3: Apply additional filters
            filtered_emails = emails

            # Filter by sender if specified
            if email_sender:
                filtered_emails = [
                    email for email in filtered_emails
                    if email_sender.lower() in email.from_address.lower() or
                       email_sender.lower() in email.from_name.lower()
                ]

            # Filter by subject if specified
            if email_subject:
                filtered_emails = [
                    email for email in filtered_emails
                    if email_subject.lower() in email.subject.lower()
                ]

            # Filter by search terms if specified
            if search_terms:
                filtered_emails = [
                    email for email in filtered_emails
                    if any(term.lower() in email.subject.lower() or
                          term.lower() in email.body.lower()
                          for term in search_terms)
                ]

            # Step 4: Format response
            if not filtered_emails:
                return {
                    "text": f"📧 No matching emails found with the specified filters.",
                    "card": None,
                    "data": []
                }

            # Build response text
            response_text = f"📧 **Found {len(filtered_emails)} email(s)**\n\n"

            for idx, email in enumerate(filtered_emails[:10], 1):  # Limit to 10 emails
                response_text += f"**{idx}. {email.subject}**\n"
                response_text += f"   From: {email.from_name} <{email.from_address}>\n"
                response_text += f"   Received: {email.received_time}\n"
                if email.has_attachments:
                    response_text += f"   📎 Attachments: {len(email.attachments)}\n"
                response_text += "\n"

            if len(filtered_emails) > 10:
                response_text += f"_...and {len(filtered_emails) - 10} more emails_"

            return {
                "text": response_text,
                "card": None,
                "data": [email.to_dict() for email in filtered_emails]
            }

        except Exception as e:
            logger.error(f"Error handling email query: {e}", exc_info=True)
            return {
                "text": f"❌ Error querying emails: {str(e)}",
                "card": None,
                "data": None
            }

    async def _handle_marketable_candidates(
        self,
        intent: Dict[str, Any],
        user_email: str,
        activity: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Handle marketable candidates query by queuing Service Bus request.

        Args:
            intent: Classified intent with limit parameter
            user_email: Email of requesting user
            activity: Optional Bot Framework Activity for proactive messaging

        Returns:
            Response dict acknowledging the query
        """
        from azure.servicebus.aio import ServiceBusClient
        from azure.servicebus import ServiceBusMessage
        import json

        entities = intent.get("entities", {})
        limit = entities.get("limit", 10)

        logger.info(f"Marketable candidates query from {user_email}: limit={limit}")

        try:
            # Step 1: Send initial acknowledgment
            acknowledgment_text = f"⚡ **Analyzing vault candidates for marketability...**\n\n"
            acknowledgment_text += f"📊 Fetching all vault candidates from Zoho CRM\n"
            acknowledgment_text += f"🔍 Scoring based on: AUM (40%), Production (30%), Credentials (15%), Availability (15%)\n"
            acknowledgment_text += f"📈 Will return top {limit} most marketable candidates\n\n"
            acknowledgment_text += f"_This may take 30-60 seconds. I'll send updates as I progress..._"

            # Step 2: Queue Service Bus message for async processing
            connection_string = os.getenv("SERVICE_BUS_CONNECTION_STRING") or os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")

            if not connection_string:
                logger.error("SERVICE_BUS_CONNECTION_STRING not configured")
                return {
                    "text": "❌ Service Bus not configured. Please contact your administrator.",
                    "card": None,
                    "data": None
                }

            queue_name = "vault-marketability-analysis"

            # Prepare conversation reference for proactive messaging
            conversation_reference = None
            if activity:
                try:
                    from botbuilder.core import TurnContext
                    # Create conversation reference from activity
                    conv_ref = TurnContext.get_conversation_reference(activity)

                    # Helper to safely get attribute or dict value
                    def safe_get(obj, key, default=None):
                        """Get value from object attribute or dict key"""
                        if isinstance(obj, dict):
                            return obj.get(key, default)
                        return getattr(obj, key, default)

                    # Serialize to dict (handle both object and dict formats)
                    conversation_reference = {
                        "service_url": safe_get(conv_ref, 'service_url'),
                        "channel_id": safe_get(conv_ref, 'channel_id'),
                        "user": {
                            "id": safe_get(safe_get(conv_ref, 'user'), 'id'),
                            "name": safe_get(safe_get(conv_ref, 'user'), 'name', "")
                        } if safe_get(conv_ref, 'user') else None,
                        "conversation": {
                            "id": safe_get(safe_get(conv_ref, 'conversation'), 'id'),
                            "is_group": safe_get(safe_get(conv_ref, 'conversation'), 'is_group', False)
                        } if safe_get(conv_ref, 'conversation') else None,
                        "bot": {
                            "id": safe_get(safe_get(conv_ref, 'bot'), 'id'),
                            "name": safe_get(safe_get(conv_ref, 'bot'), 'name', "")
                        } if safe_get(conv_ref, 'bot') else None
                    }

                    conv_id = safe_get(safe_get(conv_ref, 'conversation'), 'id', 'unknown')
                    logger.info(f"Created conversation reference for proactive messaging: {conv_id}")
                except Exception as e:
                    logger.warning(f"Failed to create conversation reference: {e}", exc_info=True)

            # Prepare query data
            query_data = {
                "limit": limit,
                "user_id": user_email,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "conversation_reference": conversation_reference
            }

            # Send to Service Bus
            async with ServiceBusClient.from_connection_string(connection_string) as client:
                sender = client.get_queue_sender(queue_name=queue_name)
                async with sender:
                    message = ServiceBusMessage(
                        body=json.dumps({"query_data": query_data}),
                        content_type="application/json",
                        subject="marketable_candidates_query"
                    )
                    await sender.send_messages(message)
                    logger.info(f"Queued marketability query for {user_email}")

            return {
                "text": acknowledgment_text,
                "card": None,
                "data": {"queued": True, "limit": limit}
            }

        except Exception as e:
            logger.error(f"Error handling marketable candidates query: {e}", exc_info=True)
            return {
                "text": f"❌ Error processing marketability query: {str(e)}",
                "card": None,
                "data": None
            }


async def process_natural_language_query(
    query: str,
    user_email: str,
    db: asyncpg.Connection,
    conversation_context: Optional[str] = None,
    override_intent: Optional[Dict[str, Any]] = None,
    activity: Optional[Any] = None  # Bot Framework Activity for proactive messaging
) -> Dict[str, Any]:
    """
    Convenience function to process natural language queries.

    Args:
        query: User's natural language query
        user_email: Email of requesting user
        db: Database connection
        conversation_context: Optional conversation history for context
        override_intent: Optional intent to skip classification (used after clarification)
        activity: Optional Bot Framework Activity for proactive messaging support

    Returns:
        Response dict with text, card, and data
    """
    engine = QueryEngine()
    return await engine.process_query(query, user_email, db, conversation_context, override_intent, activity)
