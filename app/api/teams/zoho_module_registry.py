"""
Dynamic Zoho Module Registry

Loads all 68 Zoho modules from zoho_field_mappings.json and provides:
- Module metadata (fields, types, endpoints)
- Financial field detection for role-based access control
- Module alias resolution (user-friendly names)
- Searchable field identification
- Field-to-module indexing

Usage:
    from app.api.teams.zoho_module_registry import get_module_registry

    registry = get_module_registry()

    # Get module metadata
    leads_meta = registry.get_module_metadata("Leads")

    # Get financial fields
    financial_fields = registry.get_financial_fields("Payments")

    # Resolve aliases
    module_name = registry.resolve_module_alias("candidates")  # → "Leads"
"""

import json
import logging
import os
from typing import Dict, List, Optional, Set, Any
from pathlib import Path

from app.api.teams.financial_redaction import NEVER_REDACT_FIELDS

logger = logging.getLogger(__name__)

# Financial field keywords for automatic detection
FINANCIAL_KEYWORDS = [
    "commission", "payment", "invoice", "salary", "compensation",
    "revenue", "profit", "cost", "fee", "price", "amount",
    "billing", "financial", "budget", "expense", "wage",
    "bonus", "incentive", "earning", "income", "payout",
    "charge", "rate", "total", "subtotal", "tax", "discount"
]

# Modules that are primarily financial in nature
FINANCIAL_MODULES = [
    "Payments",
    "Invoices",
    "Commissions_Paid_Module",
    "Sales_Orders",
    "Purchase_Orders",
    "Quoted_Items",
    "Ordered_Items",
    "Purchase_Items",
    "Invoiced_Items"
]

# Standard module aliases (user-friendly names)
MODULE_ALIASES = {
    "candidates": "Leads",
    "candidate": "Leads",
    "leads": "Leads",
    "jobs": "Jobs",
    "job": "Jobs",
    "positions": "Jobs",
    "openings": "Jobs",
    "submissions": "Submissions",
    "submission": "Submissions",
    "submittals": "Submissions",
    "contacts": "Contacts",
    "contact": "Contacts",
    "people": "Contacts",
    "accounts": "Accounts",
    "account": "Accounts",
    "companies": "Accounts",
    "company": "Accounts",
    "deals": "Deals",
    "deal": "Deals",
    "opportunities": "Deals",
    "tasks": "Tasks",
    "task": "Tasks",
    "todos": "Tasks",
    "events": "Events",
    "event": "Events",
    "meetings": "Events",
    "meeting": "Events",
    "calls": "Calls",
    "call": "Calls",
    "phone_calls": "Calls",
    "products": "Products",
    "product": "Products",
    "quotes": "Quotes",
    "quote": "Quotes",
    "quotations": "Quotes",
    "invoices": "Invoices",
    "invoice": "Invoices",
    "bills": "Invoices",
    "campaigns": "Campaigns",
    "campaign": "Campaigns",
    "vendors": "Vendors",
    "vendor": "Vendors",
    "suppliers": "Vendors",
    "cases": "Cases",
    "case": "Cases",
    "tickets": "Cases",
    "support": "Cases",
    "notes": "Notes",
    "note": "Notes",
    "comments": "Notes",
    "attachments": "Attachments",
    "attachment": "Attachments",
    "files": "Attachments",
    "interviews": "Interviews",
    "interview": "Interviews",
    "payments": "Payments",
    "payment": "Payments",
    "commissions": "Commissions_Paid_Module",
    "commission": "Commissions_Paid_Module",
    "agreements": "Agreements",
    "agreement": "Agreements",
    "contracts": "Agreements",
}


class ZohoModuleRegistry:
    """
    Centralized registry for all Zoho CRM modules with intelligent metadata.

    Loads module definitions from zoho_field_mappings.json and provides:
    - Module metadata (fields, types, endpoints, capabilities)
    - Financial field detection for access control
    - Module alias resolution
    - Searchable field identification
    - Cross-module field indexing
    """

    def __init__(self, mappings_file: str = None):
        """
        Initialize the module registry.

        Args:
            mappings_file: Path to zoho_field_mappings.json (optional)
        """
        self.mappings_file = mappings_file or self._find_mappings_file()
        self.modules: Dict[str, Dict[str, Any]] = {}
        self.field_index: Dict[str, Set[str]] = {}  # field_name → set of module names
        self.financial_fields_cache: Dict[str, List[str]] = {}

        # Load module data
        self._load_modules()
        self._build_field_index()

        logger.info(
            f"Loaded {len(self.modules)} Zoho modules from {self.mappings_file}"
        )

    def _find_mappings_file(self) -> str:
        """Find zoho_field_mappings.json in project root."""
        current_dir = Path(__file__).parent

        # Try project root (3 levels up from app/api/teams)
        root_path = current_dir.parent.parent.parent / "zoho_field_mappings.json"
        if root_path.exists():
            return str(root_path)

        # Fallback: check working directory
        cwd_path = Path.cwd() / "zoho_field_mappings.json"
        if cwd_path.exists():
            return str(cwd_path)

        raise FileNotFoundError(
            "zoho_field_mappings.json not found. "
            "Please ensure it exists in project root."
        )

    def _load_modules(self):
        """Load module definitions from zoho_field_mappings.json."""
        try:
            with open(self.mappings_file, 'r') as f:
                data = json.load(f)

            self.modules = data.get("modules", {})

            if not self.modules:
                logger.warning("No modules found in zoho_field_mappings.json")

        except FileNotFoundError:
            logger.error(f"Mappings file not found: {self.mappings_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in mappings file: {e}")
            raise

    def _build_field_index(self):
        """Build reverse index: field_name → modules containing that field."""
        for module_name, module_data in self.modules.items():
            fields = module_data.get("fields", {})
            for field_name in fields.keys():
                if field_name not in self.field_index:
                    self.field_index[field_name] = set()
                self.field_index[field_name].add(module_name)

    def get_module_metadata(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Get complete metadata for a module.

        Args:
            module_name: Zoho module name (e.g., "Leads", "Deals")

        Returns:
            Module metadata dict or None if not found
        """
        return self.modules.get(module_name)

    def get_all_modules(self) -> List[str]:
        """Get list of all module names."""
        return list(self.modules.keys())

    def get_queryable_modules(self) -> List[str]:
        """Get list of modules that support API queries."""
        return [
            name for name, meta in self.modules.items()
            if meta.get("api_supported", False)
        ]

    def get_module_fields(self, module_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all fields for a module.

        Args:
            module_name: Zoho module name

        Returns:
            Dictionary of field_name → field_metadata
        """
        module = self.get_module_metadata(module_name)
        return module.get("fields", {}) if module else {}

    def get_searchable_fields(self, module_name: str) -> List[str]:
        """
        Get fields that are searchable (text, email, phone types).

        Args:
            module_name: Zoho module name

        Returns:
            List of searchable field names
        """
        fields = self.get_module_fields(module_name)
        searchable_types = {"text", "email", "phone", "website", "textarea"}

        return [
            field_name
            for field_name, field_meta in fields.items()
            if field_meta.get("data_type") in searchable_types
        ]

    def get_financial_fields(self, module_name: str) -> List[str]:
        """
        Get financial fields in a module (for role-based access control).

        Args:
            module_name: Zoho module name

        Returns:
            List of financial field names that should be redacted for non-executives
        """
        # Check cache
        if module_name in self.financial_fields_cache:
            return self.financial_fields_cache[module_name]

        financial_fields = []
        fields = self.get_module_fields(module_name)

        # If module is inherently financial, mark all amount/numeric fields
        is_financial_module = module_name in FINANCIAL_MODULES

        for field_name, field_meta in fields.items():
            field_label = field_meta.get("field_label", "").lower()
            api_name = field_meta.get("api_name", "").lower()
            data_type = field_meta.get("data_type", "")

            # Check if field contains financial keywords
            is_financial = any(
                keyword in field_label or keyword in api_name
                for keyword in FINANCIAL_KEYWORDS
            )

            # In financial modules, mark all currency/number fields
            if is_financial_module and data_type in {"currency", "decimal", "double"}:
                is_financial = True

            if is_financial:
                financial_fields.append(field_name)

        # Cache result
        self.financial_fields_cache[module_name] = financial_fields

        return financial_fields

    def resolve_module_alias(self, alias: str) -> Optional[str]:
        """
        Resolve user-friendly alias to official module name.

        Args:
            alias: User-provided module name (e.g., "candidates", "jobs")

        Returns:
            Official module name or None if not found
        """
        alias_lower = alias.lower().strip()

        # Direct match
        if alias_lower in MODULE_ALIASES:
            return MODULE_ALIASES[alias_lower]

        # Check if it's already an official module name
        for module_name in self.modules.keys():
            if module_name.lower() == alias_lower:
                return module_name

        return None

    def get_module_endpoint(self, module_name: str) -> Optional[str]:
        """Get API endpoint for a module."""
        module = self.get_module_metadata(module_name)
        return module.get("api_endpoint") if module else None

    def get_key_fields(self, module_name: str) -> Dict[str, Optional[str]]:
        """
        Get key fields for a module (name, date, owner, etc.).

        Returns:
            Dictionary with keys: name_field, date_field, owner_field, status_field
        """
        fields = self.get_module_fields(module_name)

        key_fields = {
            "name_field": None,
            "date_field": None,
            "owner_field": None,
            "status_field": None,
        }

        # Find name field
        name_candidates = ["Full_Name", "Name", "Deal_Name", "Subject", "Title", "Last_Name"]
        for candidate in name_candidates:
            if candidate in fields:
                key_fields["name_field"] = candidate
                break

        # Find date field (prefer Created_Time)
        date_candidates = ["Created_Time", "Modified_Time", "Created_At", "Date"]
        for candidate in date_candidates:
            if candidate in fields:
                key_fields["date_field"] = candidate
                break

        # Find owner field
        if "Owner" in fields:
            key_fields["owner_field"] = "Owner"

        # Find status field
        status_candidates = ["Status", "Stage", "Deal_Stage", "State"]
        for candidate in status_candidates:
            if candidate in fields:
                key_fields["status_field"] = candidate
                break

        return key_fields

    def find_modules_with_field(self, field_name: str) -> List[str]:
        """
        Find all modules containing a specific field.

        Args:
            field_name: Field name to search for

        Returns:
            List of module names containing this field
        """
        return list(self.field_index.get(field_name, set()))

    def get_module_summary(self, module_name: str) -> str:
        """
        Get human-readable summary of a module.

        Args:
            module_name: Zoho module name

        Returns:
            Summary string
        """
        module = self.get_module_metadata(module_name)
        if not module:
            return f"Module '{module_name}' not found"

        field_count = len(module.get("fields", {}))
        api_supported = "✅" if module.get("api_supported") else "❌"
        singular = module.get("singular_label", "")
        plural = module.get("plural_label", "")

        return (
            f"{module_name} ({singular}/{plural}): "
            f"{field_count} fields, API: {api_supported}"
        )


# Singleton instance
_registry_instance: Optional[ZohoModuleRegistry] = None


def get_module_registry() -> ZohoModuleRegistry:
    """
    Get singleton instance of ZohoModuleRegistry.

    Returns:
        Initialized ZohoModuleRegistry instance
    """
    global _registry_instance

    if _registry_instance is None:
        _registry_instance = ZohoModuleRegistry()

    return _registry_instance


def is_executive(user_email: str) -> bool:
    """
    Check if user is an executive (full financial access).

    Args:
        user_email: User's email address

    Returns:
        True if executive (Steve, Brandon, Daniel), False otherwise
    """
    executive_emails = [
        "steve@emailthewell.com",
        "steve.perry@emailthewell.com",
        "brandon@emailthewell.com",
        "daniel.romitelli@emailthewell.com"
    ]

    email_lower = user_email.lower()
    return any(exec_email in email_lower for exec_email in executive_emails)


def filter_financial_data(
    data: Dict[str, Any],
    module_name: str,
    user_email: str
) -> Dict[str, Any]:
    """
    Redact financial fields for non-executives.

    IMPORTANT: Owner/metadata fields are NEVER redacted - all recruiters need
    to see who owns records for full transparency.

    Args:
        data: Record data from Zoho
        module_name: Module name
        user_email: User's email address

    Returns:
        Filtered data with financial fields redacted as "---" for non-executives
    """
    # Executives see everything
    if is_executive(user_email):
        return data

    # Get financial fields for this module
    registry = get_module_registry()
    financial_fields = registry.get_financial_fields(module_name)

    # Redact financial fields (except owner/metadata fields)
    filtered = data.copy()
    for field in financial_fields:
        # Skip owner and metadata fields - these must stay visible for transparency
        if field in NEVER_REDACT_FIELDS:
            continue

        if field in filtered:
            filtered[field] = "---"  # Redacted for non-executives

    return filtered
