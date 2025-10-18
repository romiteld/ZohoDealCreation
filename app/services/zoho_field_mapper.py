"""
Zoho Field Mapper Service

Loads canonical zoho_field_mappings.json and provides:
- Module metadata loading with caching
- Field value normalization (phone, picklist, owner, dates)
- Record diff computation for conflict detection
- Checksum-based reload detection

Single source of truth for all Zoho CRM field mappings.
Contract: Uses zoho_field_mappings.json:1 as authoritative schema.
"""

import os
import json
import hashlib
import logging
import re
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ZohoFieldMapper:
    """
    Centralized field mapping and normalization service.

    Loads module definitions from zoho_field_mappings.json once at startup,
    caches in memory, and provides fast lookup/normalization functions.
    """

    def __init__(self, mappings_file: Optional[str] = None):
        """
        Initialize field mapper with canonical mappings file.

        Args:
            mappings_file: Path to zoho_field_mappings.json (optional, auto-discovers)
        """
        self.mappings_file = mappings_file or self._find_mappings_file()
        self._mappings: Optional[Dict] = None
        self._checksum: Optional[str] = None
        self._modules_cache: Dict[str, Dict] = {}

        # Load mappings on initialization
        self._load_mappings()

        logger.info(
            f"Field mapper initialized with {len(self._mappings.get('modules', {}))} modules "
            f"from {self.mappings_file}"
        )

    def _find_mappings_file(self) -> str:
        """
        Auto-discover zoho_field_mappings.json in project root.

        Returns:
            Absolute path to mappings file

        Raises:
            FileNotFoundError: If mappings file not found
        """
        # Try relative to current file (app/services/)
        current_dir = Path(__file__).parent
        root_path = current_dir.parent.parent / "zoho_field_mappings.json"

        if root_path.exists():
            return str(root_path)

        # Fallback: check working directory
        cwd_path = Path.cwd() / "zoho_field_mappings.json"
        if cwd_path.exists():
            return str(cwd_path)

        raise FileNotFoundError(
            "zoho_field_mappings.json not found. "
            "Ensure it exists in project root directory."
        )

    def _load_mappings(self):
        """Load and cache zoho_field_mappings.json"""
        try:
            with open(self.mappings_file, 'r') as f:
                content = f.read()

                # Compute checksum for reload detection
                self._checksum = hashlib.sha256(content.encode()).hexdigest()

                # Parse JSON
                self._mappings = json.loads(content)

                # Pre-cache module metadata for fast lookups
                for module_name in self._mappings.get("modules", {}).keys():
                    self._modules_cache[module_name] = self._mappings["modules"][module_name]

                logger.info(f"✓ Loaded {len(self._modules_cache)} modules, checksum: {self._checksum[:8]}...")

        except FileNotFoundError:
            logger.error(f"Mappings file not found: {self.mappings_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in mappings file: {e}")
            raise

    def get_checksum(self) -> str:
        """
        Get current mappings file checksum.

        Returns:
            SHA-256 hex digest (64 chars)
        """
        return self._checksum

    def reload_if_changed(self, new_checksum: str):
        """
        Reload mappings if checksum has changed.

        Args:
            new_checksum: Expected checksum to compare against
        """
        if new_checksum != self._checksum:
            logger.info(f"Checksum changed, reloading mappings: {self._checksum[:8]} → {new_checksum[:8]}")
            self._load_mappings()

    def get_module_metadata(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Get complete metadata for a module.

        Args:
            module_name: Zoho module name (e.g., "Leads", "Deals")

        Returns:
            Module metadata dict or None if not found
        """
        return self._modules_cache.get(module_name)

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

    async def coerce_payload(self, module: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize/coerce field values in a Zoho payload.

        Transformations:
        - Phone: Strip non-digits, format as E.164 if possible
        - Picklist (multiselectpicklist): Parse JSON array or comma-separated → Python list
        - Owner: Resolve {"id": "...", "name": "..."} → owner_email via lookup
        - Date/DateTime: Parse ISO 8601 → datetime object

        Args:
            module: Zoho module name
            payload: Raw webhook payload

        Returns:
            Normalized payload dict
        """
        fields_meta = self.get_module_fields(module)
        normalized = payload.copy()

        for field_name, field_meta in fields_meta.items():
            if field_name not in payload:
                continue

            value = payload[field_name]
            data_type = field_meta.get("data_type")

            # Phone normalization
            if data_type == "phone" and value:
                normalized[field_name] = self._normalize_phone(value)

            # Picklist array normalization
            elif data_type == "multiselectpicklist" and value:
                normalized[field_name] = self._normalize_picklist_array(value)

            # Date/DateTime normalization
            elif data_type in ("date", "datetime") and value:
                normalized[field_name] = self._normalize_datetime(value)

            # Owner lookup (keep as-is, extraction happens in worker)
            # No normalization needed here - worker handles owner extraction

        return normalized

    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number to E.164 format if possible.

        Args:
            phone: Raw phone string (e.g., "(555) 123-4567", "+1 555-123-4567")

        Returns:
            Normalized phone (e.g., "+15551234567")
        """
        # Strip all non-digit characters
        digits_only = re.sub(r'\D', '', phone)

        # If starts with 1 and has 11 digits, assume US number
        if len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+{digits_only}"

        # If 10 digits, assume US number missing country code
        if len(digits_only) == 10:
            return f"+1{digits_only}"

        # Otherwise, add + if not present
        if digits_only and not phone.startswith('+'):
            return f"+{digits_only}"

        return phone  # Return original if can't normalize

    def _normalize_picklist_array(self, value: Any) -> List[str]:
        """
        Normalize picklist array value.

        Zoho sends multiselectpicklist as:
        - JSON array string: '["Value1", "Value2"]'
        - Comma-separated: "Value1, Value2"
        - Already parsed list: ["Value1", "Value2"]

        Args:
            value: Raw picklist value

        Returns:
            Python list of strings
        """
        # Already a list
        if isinstance(value, list):
            return value

        # JSON array string
        if isinstance(value, str) and value.startswith('['):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        # Comma-separated string
        if isinstance(value, str):
            return [v.strip() for v in value.split(',') if v.strip()]

        # Fallback: convert to single-item list
        return [str(value)]

    def _normalize_datetime(self, value: str) -> Optional[str]:
        """
        Normalize Zoho datetime string to ISO 8601 format.

        Validates the datetime string can be parsed, then returns it as a normalized
        ISO string (not a Python datetime object) to ensure JSON serialization compatibility.

        Args:
            value: ISO 8601 datetime string

        Returns:
            Normalized ISO 8601 string or None if parsing fails
        """
        try:
            # Zoho format: "2025-10-17T14:30:00Z" or "2025-10-17T14:30:00+00:00"
            # Validate by parsing, then return as normalized ISO string
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            # Return as ISO string with timezone (JSON serializable)
            return dt.isoformat()
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse datetime: {value}, error: {e}")
            return None

    def diff_records(
        self,
        existing: Dict[str, Any],
        incoming: Dict[str, Any],
        module: str
    ) -> Dict[str, Any]:
        """
        Compute diff between existing and incoming records.

        Used for conflict resolution and audit trail.

        Args:
            existing: Stored record data_payload
            incoming: Incoming webhook payload
            module: Zoho module name

        Returns:
            Dictionary of changed fields: {field_name: {"old": ..., "new": ...}}
        """
        fields_meta = self.get_module_fields(module)
        diff = {}

        # Check all fields in incoming payload
        for field_name, new_value in incoming.items():
            old_value = existing.get(field_name)

            # Skip if values are equal
            if old_value == new_value:
                continue

            # Field changed - add to diff
            diff[field_name] = {
                "old": old_value,
                "new": new_value,
                "data_type": fields_meta.get(field_name, {}).get("data_type", "unknown")
            }

        return diff

    def get_searchable_fields(self, module: str) -> List[str]:
        """
        Get fields that are searchable (for full-text search).

        Args:
            module: Zoho module name

        Returns:
            List of searchable field names
        """
        fields = self.get_module_fields(module)
        searchable_types = {"text", "email", "phone", "website", "textarea"}

        return [
            field_name
            for field_name, field_meta in fields.items()
            if field_meta.get("data_type") in searchable_types
        ]

    def validate_required_fields(
        self,
        module: str,
        payload: Dict[str, Any]
    ) -> List[str]:
        """
        Validate that all required fields are present in payload.

        Args:
            module: Zoho module name
            payload: Record payload to validate

        Returns:
            List of missing required field names (empty if valid)
        """
        fields = self.get_module_fields(module)
        missing = []

        for field_name, field_meta in fields.items():
            is_required = field_meta.get("required", False)

            if is_required and field_name not in payload:
                missing.append(field_name)

        return missing
