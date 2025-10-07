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
from datetime import datetime, timedelta, timezone
import asyncpg
from openai import AsyncOpenAI

from app.integrations import ZohoApiClient

logger = logging.getLogger(__name__)

# Access control constants
EXECUTIVE_USERS = [
    "steve@emailthewell.com",      # CEO
    "brandon@emailthewell.com",    # Executive
    "daniel.romitelli@emailthewell.com"  # Executive
]


ADVISOR_KEYWORDS = {
    "advisor",
    "advisors",
    "wealth",
    "financial advisor",
    "wealth advisor",
    "investment advisor",
    "book of business"
}

EXECUTIVE_KEYWORDS = {
    "c-suite",
    "c suite",
    "executive",
    "executives",
    "vp",
    "vice president",
    "chief",
    "ceo",
    "cfo",
    "coo",
    "cto",
    "president",
    "director"
}

VAULT_SIGNALS = {
    "talentwell",
    "vault",
    "vault digest",
    "talentwell digest",
    "published to the vault",
    "published in the vault",
    "vault locator",
}

CANDIDATE_SIGNALS = {
    "candidate",
    "candidates",
    "talent",
    "advisor digest",
    "candidate digest",
}


class QueryEngine:
    """Natural language query engine with role-based access control."""

    def __init__(self):
        """Initialize query engine with OpenAI client."""
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-5-mini"  # Fast model for query classification
        self.zoho_client = ZohoApiClient()

    async def process_query(
        self,
        query: str,
        user_email: str,
        db: asyncpg.Connection
    ) -> Dict[str, Any]:
        """
        Process natural language query with access control.

        Args:
            query: User's natural language query
            user_email: Email of requesting user (for access control)
            db: Database connection

        Returns:
            Dict with:
            - text: Response text for user
            - card: Optional Adaptive Card (None for now)
            - data: Raw query results
        """
        try:
            # Determine user access level
            is_executive = user_email in EXECUTIVE_USERS
            scope = "full" if is_executive else "user_only"

            logger.info(f"Processing query from {user_email} (scope: {scope}): {query}")

            # Step 1: Classify intent using GPT-4o
            intent = await self._classify_intent(query, is_executive)

            # Special handling for vault candidate queries
            if intent.get("table") == "vault_candidates":
                return await self._process_candidate_intent(query, intent)

            # Step 2: Apply owner filter for non-executives
            if not is_executive:
                intent["owner_filter"] = user_email
                intent["allowed_tables"] = [
                    "deals",  # Their Zoho deals
                    "deal_notes",  # Their notes
                    "meetings"  # Their meetings
                ]
            else:
                intent["owner_filter"] = None
                intent["allowed_tables"] = "all"

            # Step 3: Build and execute SQL query
            sql, params = await self._build_query(intent)
            logger.info(f"Executing SQL: {sql}")
            logger.debug(f"Parameters: {params}")

            results = await db.fetch(sql, *params)

            # Step 4: Format response
            response = await self._format_response(query, results, intent)

            logger.info(f"Query completed: {len(results)} results")
            return response

        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return {
                "text": f"❌ Sorry, I encountered an error processing your query: {str(e)}",
                "card": None,
                "data": None
            }

    async def _classify_intent(
        self,
        query: str,
        is_executive: bool
    ) -> Dict[str, Any]:
        """
        Classify user intent using GPT-5-mini.

        Returns:
            Intent dict with:
            - intent_type: "count", "list", "aggregate", "search"
            - entities: Extracted entities (dates, names, etc.)
            - table: Primary table to query
            - filters: Query filters
        """
        system_prompt = """You are a query classifier for a recruitment CRM system.
Classify the user's intent and extract key entities.

Available tables:
- deals: Candidate deals (columns: deal_id, deal_name, owner_email, stage, contact_name, account_name, created_at, modified_at)
- deal_notes: Notes on deals (columns: deal_id, note_content, created_by, created_at)
- meetings: Meetings related to deals (columns: deal_id, subject, meeting_date, attendees)
- vault_candidates: TalentWell Vault candidates (columns: candidate_name, job_title, company_name, location, published_to_vault, date_published)

Return JSON with:
{
    "intent_type": "count|list|aggregate|search",
    "table": "deals|deal_notes|meetings|vault_candidates",
    "entities": {
        "timeframe": "7d|30d|this_week|last_month|Q4|etc",
        "entity_name": "person/company name if mentioned",
        "search_terms": ["keywords to search"]
    },
    "filters": {
        "stage": "if mentioned",
        "created_after": "ISO date if timeframe specified",
        "created_before": "ISO date if timeframe specified",
        "candidate_type": "advisors|c_suite if specified",
        "vault_only": "true if user asks about candidates in the vault"
    }
}
"""

        user_prompt = f"""Classify this query: "{query}"

Current date: {datetime.now().strftime('%Y-%m-%d')}"""

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
            logger.debug(f"Classified intent: {intent}")

            if intent.get("table") == "vault_candidates" or self._is_candidate_query(query):
                intent["table"] = "vault_candidates"
                if "filters" not in intent:
                    intent["filters"] = {}
                inferred_type = self._infer_candidate_type(query)
                if inferred_type and not intent["filters"].get("candidate_type"):
                    intent["filters"]["candidate_type"] = inferred_type
                if "vault_only" not in intent["filters"] and "vault" in query.lower():
                    intent["filters"]["vault_only"] = True
            return intent

        except Exception as e:
            logger.error(f"Error classifying intent: {e}", exc_info=True)
            # Fallback to basic intent
            return {
                "intent_type": "search",
                "table": "vault_candidates" if self._is_candidate_query(query) else "deals",
                "entities": {"search_terms": [query]},
                "filters": {}
            }

    async def _build_query(
        self,
        intent: Dict[str, Any]
    ) -> Tuple[str, List[Any]]:
        """
        Build SQL query from classified intent.

        Returns:
            Tuple of (sql_string, parameters)
        """
        table = intent.get("table", "deals")
        intent_type = intent.get("intent_type", "list")
        filters = intent.get("filters", {})
        owner_filter = intent.get("owner_filter")

        # Build base query
        sql = None  # Initialize to avoid UnboundLocalError
        if intent_type == "count":
            sql = f"SELECT COUNT(*) as count FROM {table}"
        elif intent_type == "aggregate":
            sql = f"SELECT stage, COUNT(*) as count FROM {table}"
        else:  # list or search
            if table == "deals":
                sql = """
                    SELECT
                        deal_id,
                        deal_name,
                        contact_name,
                        account_name,
                        stage,
                        owner_email,
                        created_at
                    FROM deals
                """
            elif table == "deal_notes":
                sql = """
                    SELECT
                        deal_id,
                        note_content,
                        created_by,
                        created_at
                    FROM deal_notes
                """
            elif table == "meetings":
                sql = """
                    SELECT
                        deal_id,
                        subject,
                        meeting_date,
                        attendees
                    FROM meetings
                """
            else:
                # Fallback for unsupported tables
                raise ValueError(f"Unsupported table: {table}")

        # Build WHERE clause
        where_clauses = []
        params = []
        param_count = 1

        # Owner filter (for non-executives)
        if owner_filter:
            where_clauses.append(f"owner_email = ${param_count}")
            params.append(owner_filter)
            param_count += 1

        # Date filters
        if "created_after" in filters:
            where_clauses.append(f"created_at >= ${param_count}")
            params.append(filters["created_after"])
            param_count += 1

        if "created_before" in filters:
            where_clauses.append(f"created_at <= ${param_count}")
            params.append(filters["created_before"])
            param_count += 1

        # Stage filter
        if "stage" in filters:
            where_clauses.append(f"stage = ${param_count}")
            params.append(filters["stage"])
            param_count += 1

        # Search terms (basic full-text search)
        entities = intent.get("entities", {})
        search_terms = entities.get("search_terms", [])
        if search_terms and table in ["deals", "deal_notes", "meetings"]:
            if table == "deals":
                where_clauses.append(
                    f"(deal_name ILIKE ${param_count} OR account_name ILIKE ${param_count})"
                )
            elif table == "deal_notes":
                where_clauses.append(f"note_content ILIKE ${param_count}")
            elif table == "meetings":
                where_clauses.append(
                    f"(subject ILIKE ${param_count} OR notes ILIKE ${param_count})"
                )
            params.append(f"%{search_terms[0]}%")
            param_count += 1

        # Add WHERE clause
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        # Add GROUP BY for aggregates
        if intent_type == "aggregate":
            sql += " GROUP BY stage"

        # Add ORDER BY
        if intent_type in ["list", "search"]:
            sql += " ORDER BY created_at DESC LIMIT 10"

        return (sql, params)

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
        table = intent.get("table", "deals")

        # Handle empty results
        if not results:
            return {
                "text": f"I didn't find any {table} matching your query.",
                "card": None,
                "data": None
            }

        # Format based on intent type
        if intent_type == "count":
            count = results[0]["count"]
            return {
                "text": f"Found {count} {table}.",
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
                    text += f"   Created: {row['created_at'].strftime('%Y-%m-%d')}\n\n"

                if len(results) > 5:
                    text += f"\n...and {len(results) - 5} more."

            elif table == "deal_notes":
                text = f"Found {len(results)} notes:\n\n"
                for i, row in enumerate(results[:5], 1):
                    text += f"{i}. {row['note_content'][:100]}...\n"
                    text += f"   By: {row['created_by'] or 'N/A'}\n"
                    text += f"   Date: {row['created_at'].strftime('%Y-%m-%d')}\n\n"

                if len(results) > 5:
                    text += f"\n...and {len(results) - 5} more."

            elif table == "meetings":
                text = f"Found {len(results)} meetings:\n\n"
                for i, row in enumerate(results[:5], 1):
                    text += f"{i}. {row['subject']}\n"
                    text += f"   Date: {row['meeting_date'].strftime('%Y-%m-%d %H:%M')}\n"
                    if row.get('attendees'):
                        text += f"   Attendees: {', '.join(row['attendees'][:3])}\n"
                    text += "\n"

                if len(results) > 5:
                    text += f"\n...and {len(results) - 5} more."

        return {
            "text": text,
            "card": None,  # TODO: Implement Adaptive Card formatting
            "data": [dict(row) for row in results]
        }

    def _is_candidate_query(self, query: str) -> bool:
        """Determine if the query is about TalentWell Vault candidates."""
        lowered = query.lower()

        if any(signal in lowered for signal in VAULT_SIGNALS):
            return True

        if any(signal in lowered for signal in CANDIDATE_SIGNALS):
            return True

        if "vault" in lowered and any(keyword in lowered for keyword in (ADVISOR_KEYWORDS | EXECUTIVE_KEYWORDS)):
            return True

        return False

    def _infer_candidate_type(self, query: str) -> Optional[str]:
        """Infer candidate audience (advisors vs executives) from query keywords."""
        lowered = query.lower()
        if any(keyword in lowered for keyword in ADVISOR_KEYWORDS):
            return "advisors"
        if any(keyword in lowered for keyword in EXECUTIVE_KEYWORDS):
            return "c_suite"
        return None

    def _resolve_timeframe(self, timeframe: Optional[str]) -> Optional[Tuple[datetime, datetime]]:
        """Convert timeframe shorthand into a concrete date range."""
        if not timeframe:
            return None

        now = datetime.now(timezone.utc)
        normalized = timeframe.lower()

        if normalized in {"7d", "last_7_days", "past_week"}:
            return now - timedelta(days=7), now
        if normalized in {"30d", "last_30_days", "past_month"}:
            return now - timedelta(days=30), now
        if normalized in {"this_week"}:
            start = now - timedelta(days=now.weekday())
            return start, now
        if normalized in {"last_week"}:
            end = now - timedelta(days=now.weekday() + 1)
            start = end - timedelta(days=6)
            return start, end
        if normalized in {"this_month"}:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start, now
        if normalized in {"last_month"}:
            first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = first_of_this_month - timedelta(seconds=1)
            start = (first_of_this_month - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start, end
        if normalized in {"ytd", "year_to_date"}:
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return start, now

        # Handle explicit day counts like "14d"
        if normalized.endswith("d") and normalized[:-1].isdigit():
            days = int(normalized[:-1])
            return now - timedelta(days=days), now

        return None

    def _parse_candidate_date(self, value: Optional[str]) -> Optional[datetime]:
        """Parse candidate date strings from Zoho into datetime objects."""
        if not value:
            return None

        value = value.strip()
        iso_candidate = value[:-1] + '+00:00' if value.endswith('Z') else value
        try:
            parsed = datetime.fromisoformat(iso_candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            return parsed
        except ValueError:
            pass

        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    async def _process_candidate_intent(self, query: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle natural language queries targeting TalentWell Vault candidates."""
        filters = intent.get("filters", {})
        candidate_type = filters.get("candidate_type") or self._infer_candidate_type(query)
        vault_only = filters.get("vault_only") or ("vault" in query.lower())
        timeframe = self._resolve_timeframe(intent.get("entities", {}).get("timeframe"))

        try:
            candidates = await self.zoho_client.query_candidates(
                limit=200,
                published_to_vault=True if vault_only else None,
                candidate_type=candidate_type
            )
        except Exception as exc:
            logger.error(f"Error fetching candidates from Zoho: {exc}", exc_info=True)
            return {
                "text": f"❌ I couldn't retrieve candidate data from Zoho: {exc}",
                "card": None,
                "data": None
            }

        # Parse and attach published timestamps for filtering/sorting
        enriched_candidates: List[Tuple[Dict[str, Any], Optional[datetime]]] = []
        for candidate in candidates:
            published_raw = candidate.get("date_published") or candidate.get("Date_Published_to_Vault")
            published_at = self._parse_candidate_date(published_raw)
            enriched_candidates.append((candidate, published_at))

        # Filter by timeframe if requested
        if timeframe:
            start, end = timeframe
            enriched_candidates = [
                (candidate, published_at)
                for candidate, published_at in enriched_candidates
                if published_at and start <= published_at <= end
            ]

        # Ensure deterministic ordering by published date (newest first)
        enriched_candidates.sort(
            key=lambda item: item[1] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )

        candidates = [candidate for candidate, _ in enriched_candidates]

        if not candidates:
            audience_desc = "candidates"
            if candidate_type == "advisors":
                audience_desc = "advisor candidates"
            elif candidate_type == "c_suite":
                audience_desc = "executive candidates"
            return {
                "text": f"I didn't find any {audience_desc} matching your query.",
                "card": None,
                "data": []
            }

        count = len(candidates)
        summary_parts = [f"Found {count} candidate{'s' if count != 1 else ''}"]
        if candidate_type == "advisors":
            summary_parts.append("focused on the advisors audience")
        elif candidate_type == "c_suite":
            summary_parts.append("focused on the executive audience")
        if vault_only:
            summary_parts.append("published to the Vault")
        if timeframe:
            start, end = timeframe
            summary_parts.append(f"between {start.date()} and {end.date()}")

        summary = ' '.join(summary_parts) + "."

        top_lines = []
        for candidate in candidates[:5]:
            name = candidate.get("candidate_name") or "Unnamed Candidate"
            role = candidate.get("job_title") or "Role unknown"
            location = candidate.get("location")
            locator = candidate.get("candidate_locator")
            line = f"• {name} – {role}"
            if location:
                line += f" ({location})"
            if locator:
                line += f" [Locator: {locator}]"
            top_lines.append(line)

        if top_lines:
            summary += "\n\nTop matches:\n" + "\n".join(top_lines)

        if len(candidates) > 5:
            summary += f"\n\n…and {len(candidates) - 5} more candidates match your filters."

        # Limit data payload to prevent oversized responses
        data_preview = candidates[:50]

        return {
            "text": summary,
            "card": None,
            "data": data_preview
        }


async def process_natural_language_query(
    query: str,
    user_email: str,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    """
    Convenience function to process natural language queries.

    Args:
        query: User's natural language query
        user_email: Email of requesting user
        db: Database connection

    Returns:
        Response dict with text, card, and data
    """
    engine = QueryEngine()
    return await engine.process_query(query, user_email, db)
