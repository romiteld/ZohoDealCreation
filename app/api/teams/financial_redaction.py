"""
Financial data redaction configuration.

This module defines the canonical list of fields that should NEVER be redacted,
even when flagged as financial fields. This ensures owner/metadata transparency
across all redaction layers (registry filter + response formatter).

CRITICAL: This is the single source of truth. Any changes here automatically
propagate to both:
- zoho_module_registry.filter_financial_data()
- ResponseFormatter._redact_financial_fields()
"""

# Fields that should NEVER be redacted, regardless of financial classification
# These fields are critical for recruiter transparency and collaboration
NEVER_REDACT_FIELDS = {
    # Owner fields (various casing patterns)
    "Owner", "Owner_Name", "Owner_Email", "Owner_Id",
    
    # Audit/metadata fields
    "Created_By", "Modified_By",
    "Created_Time", "Modified_Time",
    
    # Record identifiers
    "id", "Id", "ID"
}
