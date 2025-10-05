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

# Access control constants
EXECUTIVE_USERS = [
    "steve@emailthewell.com",      # CEO
    "brandon@emailthewell.com",    # Executive
    "daniel.romitelli@emailthewell.com"  # Executive
]


class QueryEngine:
    """Natural language query engine with role-based access control."""

    def __init__(self):
        """Initialize query engine with OpenAI client."""
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-5-mini"  # Fast model for query classification

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
- deal_notes: Notes on deals (columns: deal_id, note_text, created_by, created_at)
- meetings: Meetings related to deals (columns: deal_id, subject, meeting_date, attendees)

Return JSON with:
{
    "intent_type": "count|list|aggregate|search",
    "table": "deals|deal_notes|meetings",
    "entities": {
        "timeframe": "7d|30d|this_week|last_month|Q4|etc",
        "entity_name": "person/company name if mentioned",
        "search_terms": ["keywords to search"]
    },
    "filters": {
        "stage": "if mentioned",
        "created_after": "ISO date if timeframe specified",
        "created_before": "ISO date if timeframe specified"
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
            return intent

        except Exception as e:
            logger.error(f"Error classifying intent: {e}", exc_info=True)
            # Fallback to basic intent
            return {
                "intent_type": "search",
                "table": "deals",
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
                        note_text,
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
                where_clauses.append(f"note_text ILIKE ${param_count}")
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
                    text += f"{i}. {row['note_text'][:100]}...\n"
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
