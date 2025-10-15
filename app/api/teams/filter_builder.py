"""
Dynamic Zoho Filter Builder

Translates natural language entities into Zoho API filter criteria.
Supports all field types and operators across all 68 Zoho modules.

Usage:
    from app.api.teams.filter_builder import FilterBuilder

    builder = FilterBuilder("Leads")
    filters = builder.build_filters({
        "location": "Texas",
        "status": "Open",
        "created_after": "2025-01-01"
    })

    # Result: {"criteria": "(location:contains:Texas)and(status:equals:Open)..."}
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from app.api.teams.zoho_module_registry import get_module_registry

logger = logging.getLogger(__name__)


class FilterBuilder:
    """
    Build Zoho API filter criteria from natural language entities.

    Handles:
    - Date range filters (created_after, created_before, etc.)
    - Text search (contains, starts_with, ends_with)
    - Numeric comparisons (gt, gte, lt, lte)
    - Exact matches (equals, not_equals)
    - List operators (in, not_in)
    - Null checks (is_null, is_not_null)
    """

    # Operator mapping: NLP → Zoho API
    OPERATOR_MAP = {
        "contains": "contains",
        "starts_with": "starts_with",
        "ends_with": "ends_with",
        "eq": "equals",
        "equals": "equals",
        "ne": "not_equals",
        "not_equals": "not_equals",
        "gt": "greater_than",
        "gte": "greater_equal",
        "lt": "less_than",
        "lte": "less_equal",
        "in": "in",
        "not_in": "not_in",
        "is_null": "is_null",
        "is_not_null": "is_not_null"
    }

    # Date field patterns (common across modules)
    DATE_FIELDS = {
        "Created_Time", "Modified_Time", "Created_At", "Modified_At",
        "Date_Published_to_Vault", "Next_Interview_Scheduled",
        "Meeting_Date", "Start_DateTime", "End_DateTime",
        "Due_Date", "Closing_Date", "Expected_Close_Date",
        "Submitted_Date", "Interview_Date", "Offer_Date",
        "Start_Date", "End_Date", "Payment_Date", "Invoice_Date"
    }

    def __init__(self, module_name: str):
        """
        Initialize filter builder for a specific module.

        Args:
            module_name: Zoho module name (e.g., "Leads", "Jobs")
        """
        self.module_name = module_name
        self.registry = get_module_registry()
        self.module_meta = self.registry.get_module_metadata(module_name)

        if not self.module_meta:
            logger.warning(f"Module '{module_name}' not found in registry")

    def build_filters(
        self,
        entities: Dict[str, Any],
        additional_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build Zoho API filter parameters from NLP entities.

        Args:
            entities: Extracted entities from NLP (dates, names, keywords, etc.)
            additional_filters: Additional raw filters to apply

        Returns:
            Dictionary of Zoho API parameters including 'criteria' string

        Example:
            entities = {
                "timeframe": "last week",
                "location": "Texas",
                "status": "Open"
            }

            filters = builder.build_filters(entities)
            # Result: {
            #     "criteria": "(Created_Time:greater_equal:2025-01-08T00:00:00Z)and(location:contains:Texas)and(status:equals:Open)"
            # }
        """
        criteria_parts = []

        # Process timeframe entity → date range filters
        if "timeframe" in entities and entities["timeframe"]:
            date_criteria = self._parse_timeframe(entities["timeframe"])
            if date_criteria:
                criteria_parts.extend(date_criteria)

        # Process explicit date filters
        if "created_after" in entities:
            date_str = self._format_date(entities["created_after"])
            criteria_parts.append(f"(Created_Time:greater_equal:{date_str})")

        if "created_before" in entities:
            date_str = self._format_date(entities["created_before"])
            criteria_parts.append(f"(Created_Time:less_equal:{date_str})")

        # Process text search filters
        if "search_terms" in entities and entities["search_terms"]:
            # Text search across multiple fields (OR logic)
            search_terms = entities["search_terms"]
            if isinstance(search_terms, list) and search_terms:
                # Search in name/title fields
                search_fields = self._get_searchable_fields()
                if search_fields:
                    # OR across fields for each search term
                    for term in search_terms:
                        field_criteria = [
                            f"({field}:contains:{term})"
                            for field in search_fields[:3]  # Limit to top 3 fields
                        ]
                        # Combine with OR
                        if field_criteria:
                            criteria_parts.append(f"({'or'.join(field_criteria)})")

        # Process entity name (person or company name)
        if "entity_name" in entities and entities["entity_name"]:
            name = entities["entity_name"]
            # Search in name fields
            name_fields = ["Full_Name", "Name", "Account_Name", "Contact_Name", "Last_Name"]
            name_criteria = [
                f"({field}:contains:{name})"
                for field in name_fields
                if field in self._get_module_fields()
            ]
            if name_criteria:
                criteria_parts.append(f"({'or'.join(name_criteria)})")

        # Process status/stage filters
        if "status" in entities and entities["status"]:
            criteria_parts.append(f"(Status:equals:{entities['status']})")

        if "stage" in entities and entities["stage"]:
            # Check if module has Stage or Deal_Stage field
            if "Stage" in self._get_module_fields():
                criteria_parts.append(f"(Stage:equals:{entities['stage']})")
            elif "Deal_Stage" in self._get_module_fields():
                criteria_parts.append(f"(Deal_Stage:equals:{entities['stage']})")

        # Process location filters
        if "location" in entities and entities["location"]:
            location = entities["location"]
            # Search in location fields
            location_fields = ["Current_Location", "Location", "City", "State", "Address"]
            loc_criteria = [
                f"({field}:contains:{location})"
                for field in location_fields
                if field in self._get_module_fields()
            ]
            if loc_criteria:
                criteria_parts.append(f"({'or'.join(loc_criteria)})")

        # Process additional raw filters
        if additional_filters:
            for key, value in additional_filters.items():
                if "__" in key:
                    # Handle operator suffix (e.g., "aum__gte")
                    field, operator = key.rsplit("__", 1)
                    zoho_operator = self.OPERATOR_MAP.get(operator, "equals")
                    criteria_parts.append(f"({field}:{zoho_operator}:{value})")
                else:
                    # Simple equality
                    criteria_parts.append(f"({key}:equals:{value})")

        # Combine criteria with AND logic
        if criteria_parts:
            criteria = "(" + "and".join(criteria_parts) + ")"
            return {"criteria": criteria}
        else:
            return {}

    def _parse_timeframe(self, timeframe: str) -> List[str]:
        """
        Parse timeframe string into date range criteria.

        Args:
            timeframe: Natural language timeframe (e.g., "last week", "this month")

        Returns:
            List of criteria strings for date filtering
        """
        from datetime import datetime, timedelta

        timeframe_lower = timeframe.lower().replace(" ", "_")
        now = datetime.now(timezone.utc)
        criteria = []

        # 7-day windows
        if any(token in timeframe_lower for token in ["7d", "last_week", "this_week"]):
            start_date = (now - timedelta(days=7)).isoformat()
            criteria.append(f"(Created_Time:greater_equal:{start_date})")

        # 30-day windows
        elif "30d" in timeframe_lower or "last_month" in timeframe_lower:
            start_date = (now - timedelta(days=30)).isoformat()
            criteria.append(f"(Created_Time:greater_equal:{start_date})")

        # This month
        elif "this_month" in timeframe_lower:
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_date = start_of_month.isoformat()
            criteria.append(f"(Created_Time:greater_equal:{start_date})")

        # Q4 (Oct-Dec)
        elif "q4" in timeframe_lower:
            q4_start = datetime(now.year, 10, 1, tzinfo=timezone.utc).isoformat()
            q4_end = datetime(now.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).isoformat()
            criteria.append(f"(Created_Time:greater_equal:{q4_start})")
            criteria.append(f"(Created_Time:less_equal:{q4_end})")

        # Q1, Q2, Q3 (similar logic)
        elif "q1" in timeframe_lower:
            q1_start = datetime(now.year, 1, 1, tzinfo=timezone.utc).isoformat()
            q1_end = datetime(now.year, 3, 31, 23, 59, 59, tzinfo=timezone.utc).isoformat()
            criteria.append(f"(Created_Time:greater_equal:{q1_start})")
            criteria.append(f"(Created_Time:less_equal:{q1_end})")

        elif "q2" in timeframe_lower:
            q2_start = datetime(now.year, 4, 1, tzinfo=timezone.utc).isoformat()
            q2_end = datetime(now.year, 6, 30, 23, 59, 59, tzinfo=timezone.utc).isoformat()
            criteria.append(f"(Created_Time:greater_equal:{q2_start})")
            criteria.append(f"(Created_Time:less_equal:{q2_end})")

        elif "q3" in timeframe_lower:
            q3_start = datetime(now.year, 7, 1, tzinfo=timezone.utc).isoformat()
            q3_end = datetime(now.year, 9, 30, 23, 59, 59, tzinfo=timezone.utc).isoformat()
            criteria.append(f"(Created_Time:greater_equal:{q3_start})")
            criteria.append(f"(Created_Time:less_equal:{q3_end})")

        return criteria

    def _format_date(self, date_value: Any) -> str:
        """
        Format date value to ISO 8601 string for Zoho API.

        Args:
            date_value: Date string, datetime object, or ISO string

        Returns:
            ISO 8601 formatted datetime string with timezone
        """
        if isinstance(date_value, datetime):
            return date_value.isoformat()
        elif isinstance(date_value, str):
            # Try parsing ISO string
            try:
                dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                return dt.isoformat()
            except ValueError:
                # Try parsing common formats
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"]:
                    try:
                        dt = datetime.strptime(date_value, fmt)
                        dt = dt.replace(tzinfo=timezone.utc)
                        return dt.isoformat()
                    except ValueError:
                        continue

        # Fallback: return as-is
        return str(date_value)

    def _get_searchable_fields(self) -> List[str]:
        """Get searchable text fields for this module."""
        if not self.module_meta:
            return []
        return self.registry.get_searchable_fields(self.module_name)

    def _get_module_fields(self) -> List[str]:
        """Get all field names for this module."""
        if not self.module_meta:
            return []
        fields = self.module_meta.get("fields", {})
        return list(fields.keys())


def build_criteria_string(filters: List[Dict[str, Any]], logic: str = "and") -> str:
    """
    Build Zoho criteria string from filter list.

    Args:
        filters: List of filter dicts with 'field', 'operator', 'value'
        logic: Combine with 'and' or 'or' (default: 'and')

    Returns:
        Zoho criteria string

    Example:
        filters = [
            {"field": "Status", "operator": "equals", "value": "Open"},
            {"field": "Location", "operator": "contains", "value": "Texas"}
        ]

        criteria = build_criteria_string(filters)
        # Result: "(Status:equals:Open)and(Location:contains:Texas)"
    """
    criteria_parts = []
    for f in filters:
        field = f.get("field")
        operator = f.get("operator", "equals")
        value = f.get("value")

        if field and value is not None:
            criteria_parts.append(f"({field}:{operator}:{value})")

    if criteria_parts:
        return "(" + logic.join(criteria_parts) + ")"
    else:
        return ""
