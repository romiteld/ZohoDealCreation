"""
Response Formatter with Financial Data Redaction

Formats Zoho query results into user-friendly responses with role-based access control.
- Executives (Steve, Brandon, Daniel): See all financial fields
- Recruiters: Financial fields redacted as "---"

Usage:
    from app.api.teams.response_formatter import ResponseFormatter

    formatter = ResponseFormatter("Leads", user_email="recruiter@emailthewell.com")
    text = formatter.format_list_response(results, max_items=5)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.api.teams.zoho_module_registry import (
    get_module_registry,
    is_executive,
    filter_financial_data
)
from app.api.teams.financial_redaction import NEVER_REDACT_FIELDS

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    Format Zoho query results with financial data redaction.

    Handles:
    - List responses (show N items)
    - Count responses (total counts)
    - Aggregate responses (group by field)
    - Search responses (specific records)
    - Financial field redaction for non-executives
    """

    def __init__(self, module_name: str, user_email: str):
        """
        Initialize response formatter.

        Args:
            module_name: Zoho module name (e.g., "Leads", "Jobs")
            user_email: User's email for role detection
        """
        self.module_name = module_name
        self.user_email = user_email
        self.user_role = "executive" if is_executive(user_email) else "recruiter"
        self.registry = get_module_registry()
        self.module_meta = self.registry.get_module_metadata(module_name)

        # Get financial fields for this module
        self.financial_fields = self.registry.get_financial_fields(module_name) if self.module_meta else []

        logger.info(
            f"ResponseFormatter initialized: module={module_name}, "
            f"user_role={self.user_role}, financial_fields={len(self.financial_fields)}"
        )

    def format_list_response(
        self,
        results: List[Dict[str, Any]],
        max_items: int = 5,
        intent_type: str = "list"
    ) -> str:
        """
        Format list of records into user-friendly text.

        Args:
            results: List of record dicts from Zoho
            max_items: Maximum items to show
            intent_type: Type of query (list, search, count)

        Returns:
            Formatted text response
        """
        if not results:
            return self._format_empty_response(intent_type)

        # Apply financial redaction to all records
        filtered_results = [
            self._redact_financial_fields(record)
            for record in results
        ]

        # Get key fields for this module
        key_fields = self.registry.get_key_fields(self.module_name)
        name_field = key_fields.get("name_field", "Name")
        date_field = key_fields.get("date_field", "Created_Time")

        # Build response text
        total = len(filtered_results)
        shown = min(max_items, total)

        text = f"Found {total} {self._pluralize(self.module_name)}:\n\n"

        for i, record in enumerate(filtered_results[:shown], 1):
            # Extract key information
            name = record.get(name_field) or record.get("id", "N/A")
            text += f"{i}. **{name}**\n"

            # Add module-specific details
            text += self._format_record_details(record)

            text += "\n"

        if total > shown:
            text += f"\n...and {total - shown} more {self._pluralize(self.module_name)}."

        # Add financial data notice for recruiters
        if self.user_role == "recruiter" and self.financial_fields:
            text += "\n\n_Note: Financial fields are visible to executives only._"

        return text

    def format_count_response(self, count: int) -> str:
        """
        Format count query response.

        Args:
            count: Total count

        Returns:
            Formatted text
        """
        module_label = self._pluralize(self.module_name)
        return f"Total {module_label}: **{count}**"

    def format_aggregate_response(
        self,
        results: List[Dict[str, Any]],
        group_by: str
    ) -> str:
        """
        Format aggregated results (grouped by field).

        Args:
            results: List of records
            group_by: Field name used for grouping

        Returns:
            Formatted text with breakdown
        """
        if not results:
            return self._format_empty_response("aggregate")

        # Group records by field value
        groups: Dict[str, List[Dict]] = {}
        for record in results:
            group_value = str(record.get(group_by, "Unknown"))
            if group_value not in groups:
                groups[group_value] = []
            groups[group_value].append(record)

        # Build response
        text = f"**{self._pluralize(self.module_name)} by {group_by}:**\n\n"

        # Sort by count (descending)
        sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

        for group_value, group_records in sorted_groups:
            count = len(group_records)
            text += f"- **{group_value}**: {count}\n"

        text += f"\n**Total**: {len(results)} {self._pluralize(self.module_name)}"

        return text

    def _redact_financial_fields(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact financial fields for non-executives.

        IMPORTANT: Owner/metadata fields are NEVER redacted - all recruiters need
        to see who owns records for full transparency.

        Args:
            record: Record dict from Zoho

        Returns:
            Record with financial fields redacted (if not executive)
        """
        if self.user_role == "executive":
            return record  # Executives see everything

        # Redact financial fields (except owner/metadata)
        redacted = record.copy()
        for field in self.financial_fields:
            # Skip owner and metadata fields - these must stay visible for transparency
            if field in NEVER_REDACT_FIELDS:
                continue

            if field in redacted:
                redacted[field] = "---"

        return redacted

    def _get_owner_info(self, record: Dict[str, Any]) -> Optional[str]:
        """
        Safely extract owner information from multiple possible field names.

        Args:
            record: Record dict

        Returns:
            Owner email/name if available, None otherwise
        """
        # Check multiple possible owner field names (in order of preference)
        for field in ["Owner_Email", "Owner_Name", "Owner", "owner_email", "owner_name", "owner"]:
            if field in record and record[field]:
                return record[field]
        return None

    def _format_record_details(self, record: Dict[str, Any]) -> str:
        """
        Format module-specific record details.

        Args:
            record: Record dict (already redacted)

        Returns:
            Formatted detail string
        """
        details = []

        # Module-specific formatting
        if self.module_name == "Leads":
            if record.get("Designation"):
                details.append(f"   Title: {record['Designation']}")
            if record.get("Employer"):
                details.append(f"   Company: {record['Employer']}")
            if record.get("Current_Location"):
                details.append(f"   Location: {record['Current_Location']}")
            if record.get("Email"):
                details.append(f"   Email: {record['Email']}")

        elif self.module_name == "Jobs":
            if record.get("Job_Opening_Name"):
                details.append(f"   Position: {record['Job_Opening_Name']}")
            if record.get("Location"):
                details.append(f"   Location: {record['Location']}")
            if record.get("Job_Opening_Status"):
                details.append(f"   Status: {record['Job_Opening_Status']}")
            if record.get("Salary"):
                # Salary is a financial field
                details.append(f"   Salary: {record['Salary']}")

        elif self.module_name == "Deals":
            if record.get("Stage"):
                details.append(f"   Stage: {record['Stage']}")
            if record.get("Account_Name"):
                details.append(f"   Account: {record['Account_Name']}")
            if record.get("Amount"):
                # Amount is a financial field
                details.append(f"   Amount: {record['Amount']}")
            if record.get("Closing_Date"):
                details.append(f"   Close Date: {self._format_date(record['Closing_Date'])}")

        elif self.module_name == "Submissions":
            if record.get("Candidate_Name"):
                details.append(f"   Candidate: {record['Candidate_Name']}")
            if record.get("Job_Title"):
                details.append(f"   Job: {record['Job_Title']}")
            if record.get("Submission_Status"):
                details.append(f"   Status: {record['Submission_Status']}")
            if record.get("Submitted_Date"):
                details.append(f"   Submitted: {self._format_date(record['Submitted_Date'])}")

        elif self.module_name == "Contacts":
            if record.get("Account_Name"):
                details.append(f"   Account: {record['Account_Name']}")
            if record.get("Email"):
                details.append(f"   Email: {record['Email']}")
            if record.get("Phone"):
                details.append(f"   Phone: {record['Phone']}")

        elif self.module_name == "Accounts":
            if record.get("Account_Type"):
                details.append(f"   Type: {record['Account_Type']}")
            if record.get("Industry"):
                details.append(f"   Industry: {record['Industry']}")
            if record.get("Annual_Revenue"):
                # Revenue is a financial field
                details.append(f"   Revenue: {record['Annual_Revenue']}")

        elif self.module_name == "Tasks":
            if record.get("Status"):
                details.append(f"   Status: {record['Status']}")
            if record.get("Priority"):
                details.append(f"   Priority: {record['Priority']}")
            if record.get("Due_Date"):
                details.append(f"   Due: {self._format_date(record['Due_Date'])}")

        elif self.module_name == "Events":
            if record.get("Start_DateTime"):
                details.append(f"   Start: {self._format_datetime(record['Start_DateTime'])}")
            if record.get("Location"):
                details.append(f"   Location: {record['Location']}")

        elif self.module_name == "Invoices":
            if record.get("Invoice_Number"):
                details.append(f"   Invoice #: {record['Invoice_Number']}")
            if record.get("Status"):
                details.append(f"   Status: {record['Status']}")
            if record.get("Grand_Total"):
                # Grand_Total is a financial field
                details.append(f"   Total: {record['Grand_Total']}")
            if record.get("Due_Date"):
                details.append(f"   Due: {self._format_date(record['Due_Date'])}")

        elif self.module_name == "Payments":
            if record.get("Payment_Number"):
                details.append(f"   Payment #: {record['Payment_Number']}")
            if record.get("Amount"):
                # Amount is a financial field
                details.append(f"   Amount: {record['Amount']}")
            if record.get("Payment_Date"):
                details.append(f"   Date: {self._format_date(record['Payment_Date'])}")

        else:
            # Generic fallback for unknown modules
            # Show first 3 non-empty fields (excluding id, Created_Time, Modified_Time)
            skip_fields = {"id", "Created_Time", "Modified_Time", "Owner", "Created_By", "Modified_By"}
            shown = 0
            for key, value in record.items():
                if shown >= 3:
                    break
                if key not in skip_fields and value:
                    details.append(f"   {key}: {value}")
                    shown += 1

        return "\n".join(details) if details else "   (No details available)"

    def _format_empty_response(self, intent_type: str) -> str:
        """
        Format response for empty results.

        Args:
            intent_type: Type of query

        Returns:
            Helpful message
        """
        module_label = self._pluralize(self.module_name)

        if intent_type == "search":
            return f"No {module_label} found matching your search criteria."
        elif intent_type == "count":
            return f"No {module_label} found."
        elif intent_type == "aggregate":
            return f"No {module_label} available for grouping."
        else:
            return f"No {module_label} found."

    def _pluralize(self, module_name: str) -> str:
        """Get plural label for module."""
        if self.module_meta:
            return self.module_meta.get("plural_label", module_name)
        return module_name

    def _format_date(self, date_value: Any) -> str:
        """Format date value to human-readable string."""
        if not date_value:
            return "N/A"

        try:
            if isinstance(date_value, str):
                dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            elif isinstance(date_value, datetime):
                dt = date_value
            else:
                return str(date_value)

            return dt.strftime('%Y-%m-%d')
        except (ValueError, AttributeError):
            return str(date_value)

    def _format_datetime(self, datetime_value: Any) -> str:
        """Format datetime value to human-readable string."""
        if not datetime_value:
            return "N/A"

        try:
            if isinstance(datetime_value, str):
                dt = datetime.fromisoformat(datetime_value.replace('Z', '+00:00'))
            elif isinstance(datetime_value, datetime):
                dt = datetime_value
            else:
                return str(datetime_value)

            return dt.strftime('%Y-%m-%d %H:%M')
        except (ValueError, AttributeError):
            return str(datetime_value)
