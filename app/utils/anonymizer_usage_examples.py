"""
Usage examples for the anonymization engine.

Demonstrates common use cases for anonymizing candidate data
in various contexts: vault alerts, weekly digests, API responses.

Author: The Well
Last Updated: 2025-10-13
"""

from typing import List, Dict, Any
from app.utils.anonymizer import (
    anonymize_candidate_data,
    anonymize_candidate_list,
    anonymize_firm_name,
    round_aum_to_range,
    validate_anonymization,
)


# ============================================================================
# EXAMPLE 1: Single Candidate Anonymization
# ============================================================================

def example_single_candidate():
    """Anonymize a single candidate for weekly digest."""
    print("=" * 80)
    print("EXAMPLE 1: Single Candidate Anonymization")
    print("=" * 80)

    candidate = {
        "first_name": "Sarah",
        "last_name": "Johnson",
        "firm": "Merrill Lynch Private Wealth Management",
        "city": "Frisco",
        "state": "TX",
        "zip": "75034",
        "aum": "$1.68B",
        "production": "$8.4M",
        "education": "MBA from Louisiana State University, CFP, CFA",
        "bio": (
            "Top 1% advisor nationally. Ranked #1 in Dallas region. "
            "Chairman's Club member at Merrill Lynch for 5 consecutive years. "
            "Scaled practice from $125M to $1.68B using E23 Consulting framework. "
            "Specializes in high-net-worth clients with $10M+ portfolios."
        ),
        "achievements": "President's Club 2023, captured 52% market share in VA products",
    }

    print("\n--- ORIGINAL DATA ---")
    for key, value in candidate.items():
        print(f"{key:20}: {value}")

    # Anonymize
    anonymized = anonymize_candidate_data(candidate)

    print("\n--- ANONYMIZED DATA ---")
    for key, value in anonymized.items():
        print(f"{key:20}: {value}")

    # Validate
    warnings = validate_anonymization(candidate, anonymized)
    print("\n--- VALIDATION ---")
    if warnings:
        print("⚠️  Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("✅ All checks passed!")

    return anonymized


# ============================================================================
# EXAMPLE 2: Batch Processing for Weekly Digest
# ============================================================================

def example_batch_digest():
    """Anonymize multiple candidates for weekly digest email."""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 2: Batch Processing for Weekly Digest")
    print("=" * 80)

    candidates = [
        {
            "name": "Michael Chen",
            "firm": "Morgan Stanley",
            "city": "San Francisco",
            "state": "CA",
            "aum": "$2.3B",
            "specialty": "Tech executives",
        },
        {
            "name": "Jessica Williams",
            "firm": "Fisher Investments",
            "city": "Grand Rapids",
            "state": "MI",
            "aum": "$850M",
            "specialty": "Healthcare professionals",
        },
        {
            "name": "David Martinez",
            "firm": "LPL Financial",
            "city": "Des Moines",
            "state": "IA",
            "aum": "$425M",
            "specialty": "Business owners",
        },
    ]

    print("\n--- ORIGINAL CANDIDATES ---")
    for i, candidate in enumerate(candidates, 1):
        print(f"\n{i}. {candidate['name']}")
        print(f"   Firm: {candidate['firm']}")
        print(f"   Location: {candidate['city']}, {candidate['state']}")
        print(f"   AUM: {candidate['aum']}")

    # Batch anonymize
    anonymized_list = anonymize_candidate_list(candidates)

    print("\n--- ANONYMIZED CANDIDATES ---")
    for i, candidate in enumerate(anonymized_list, 1):
        print(f"\n{i}. {candidate['name']}")
        print(f"   Firm: {candidate['firm']}")
        city_display = candidate.get('city') or f"{candidate['state']} Region"
        print(f"   Location: {city_display}, {candidate['state']}")
        print(f"   AUM: {candidate['aum']}")

    return anonymized_list


# ============================================================================
# EXAMPLE 3: Vault Alert Card Generation
# ============================================================================

def example_vault_alert_card():
    """Generate anonymized vault alert card content."""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 3: Vault Alert Card (Boss Format)")
    print("=" * 80)

    candidate = {
        "first_name": "Robert",
        "last_name": "Anderson",
        "firm": "UBS Financial Services",
        "city": "Charlotte",
        "state": "NC",
        "aum": "$1.2B",
        "production": "$6M",
        "availability": "Actively exploring",
        "compensation_target": "$850K base + $400K upfront",
        "bio": (
            "Top performer at UBS with 15-year track record. "
            "Built practice from $200M to $1.2B using proprietary Savvy platform. "
            "MBA from Duke University. "
            "Ranked #3 in Southeast region for 3 consecutive years."
        ),
    }

    anonymized = anonymize_candidate_data(candidate)

    # Generate alert card format
    print("\n--- VAULT ALERT CARD ---")
    print(f"‼️ [Active Opportunity] 🔔")
    print(f"📍 {anonymized['city']}, {anonymized['state']}")
    print(f"💰 {anonymized['aum']} AUM | {anonymized['production']} Production")
    print(f"🎯 {anonymized['availability']}")
    print()
    print("Key Highlights:")
    # Split bio into bullets (simulated)
    bullets = [
        f"• Currently at {anonymized['firm']}",
        f"• {anonymized['aum']} in assets under management",
        "• Exceptional growth trajectory over 15 years",
        "• Advanced credentials and industry recognition",
        "• Seeking new platform opportunity",
    ]
    for bullet in bullets:
        print(bullet)

    print("\n💡 Note: All identifying details anonymized per privacy policy")


# ============================================================================
# EXAMPLE 4: API Response Anonymization
# ============================================================================

def example_api_response():
    """Anonymize candidate data for public API response."""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 4: API Response Anonymization")
    print("=" * 80)

    # Simulated database record
    db_record = {
        "id": 12345,
        "created_at": "2025-10-13T10:30:00Z",
        "first_name": "Emily",
        "last_name": "Thompson",
        "email": "emily.t@example.com",
        "phone": "+1-555-0123",
        "firm": "Charles Schwab",
        "previous_firm": "Merrill Lynch",
        "city": "Plano",
        "state": "TX",
        "aum": "$647M",
        "production": "$3.2M",
        "education": "BS Finance from University of Texas, CFP",
        "bio": "Award-winning advisor. President's Club member.",
        "internal_notes": "High priority - contacted 10/1",
        "recruiter_owner": "daniel.romitelli@emailthewell.com",
    }

    print("\n--- DATABASE RECORD (Internal) ---")
    print("Contains PII and internal data...")
    for key in ["id", "email", "phone", "internal_notes", "recruiter_owner"]:
        print(f"{key:20}: {db_record.get(key)}")

    # Anonymize for external API
    anonymized = anonymize_candidate_data(db_record)

    # Remove internal fields for public API
    public_fields = [
        "first_name", "last_name", "firm", "previous_firm",
        "city", "state", "aum", "production", "education", "bio"
    ]
    public_response = {k: anonymized[k] for k in public_fields if k in anonymized}

    print("\n--- PUBLIC API RESPONSE ---")
    for key, value in public_response.items():
        print(f"{key:20}: {value}")

    print("\n✅ PII and internal data removed")
    print("✅ Firm names anonymized")
    print("✅ Location normalized")
    print("✅ Financial figures rounded")


# ============================================================================
# EXAMPLE 5: Selective Field Anonymization
# ============================================================================

def example_selective_anonymization():
    """Anonymize only specific fields while preserving others."""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 5: Selective Field Anonymization")
    print("=" * 80)

    candidate = {
        "name": "James Wilson",
        "contact_email": "james@example.com",  # Keep for recruiter use
        "firm": "Goldman Sachs Private Wealth",
        "city": "New York",
        "state": "NY",
        "aum": "$3.5B",
        "specialty": "Ultra-high net worth",
        "internal_score": 95,
        "recruiter_notes": "Warm lead - previous conversation 9/15",
    }

    print("\n--- SCENARIO: Internal Team View ---")
    print("Keep contact info, anonymize public details")

    anonymized = anonymize_candidate_data(candidate)

    # Restore internal fields after anonymization
    anonymized["contact_email"] = candidate["contact_email"]
    anonymized["internal_score"] = candidate["internal_score"]
    anonymized["recruiter_notes"] = candidate["recruiter_notes"]

    print("\n--- RESULT ---")
    print(f"Name: {anonymized['name']}")
    print(f"Email: {anonymized['contact_email']} (preserved)")
    print(f"Firm: {anonymized['firm']} (anonymized)")
    print(f"Location: {anonymized['city']}, {anonymized['state']} (normalized)")
    print(f"AUM: {anonymized['aum']} (rounded)")
    print(f"Internal Score: {anonymized['internal_score']} (preserved)")
    print(f"Notes: {anonymized['recruiter_notes']} (preserved)")


# ============================================================================
# EXAMPLE 6: Integration with Privacy Mode Flag
# ============================================================================

def example_privacy_mode_integration():
    """Show integration with PRIVACY_MODE feature flag."""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 6: Privacy Mode Integration")
    print("=" * 80)

    import os

    # Simulate feature flag
    PRIVACY_MODE = os.getenv("PRIVACY_MODE", "true").lower() == "true"

    candidate = {
        "firm": "Boutique Wealth Partners",
        "city": "Boulder",
        "state": "CO",
        "aum": "$1.85B",
        "compensation": "$425,000 base",
    }

    print(f"\nPrivacy Mode: {'ENABLED' if PRIVACY_MODE else 'DISABLED'}")
    print("\n--- ORIGINAL ---")
    for key, value in candidate.items():
        print(f"{key:20}: {value}")

    if PRIVACY_MODE:
        candidate = anonymize_candidate_data(candidate)
        print("\n--- ANONYMIZED (Privacy Mode ON) ---")
    else:
        print("\n--- UNCHANGED (Privacy Mode OFF) ---")

    for key, value in candidate.items():
        print(f"{key:20}: {value}")


# ============================================================================
# EXAMPLE 7: Validation and Error Handling
# ============================================================================

def example_validation_workflow():
    """Demonstrate validation workflow."""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 7: Validation Workflow")
    print("=" * 80)

    test_cases = [
        {
            "name": "Good Anonymization",
            "candidate": {
                "firm": "Morgan Stanley",
                "city": "Dallas 75201",
                "aum": "$500M",
            },
        },
        {
            "name": "Incomplete Anonymization (for demo)",
            "candidate": {
                "firm": "Some Unknown Firm",
                "city": "Dallas 75201",  # ZIP not removed
                "education": "MBA from Harvard",  # University not removed
            },
        },
    ]

    for test_case in test_cases:
        print(f"\n--- {test_case['name']} ---")
        original = test_case["candidate"]
        anonymized = anonymize_candidate_data(original)

        warnings = validate_anonymization(original, anonymized)

        if warnings:
            print("⚠️  Validation Issues:")
            for warning in warnings:
                print(f"  - {warning}")
        else:
            print("✅ Validation passed!")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    """Run all examples."""

    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "ANONYMIZATION ENGINE EXAMPLES" + " " * 29 + "║")
    print("╚" + "═" * 78 + "╝")

    try:
        # Run all examples
        example_single_candidate()
        example_batch_digest()
        example_vault_alert_card()
        example_api_response()
        example_selective_anonymization()
        example_privacy_mode_integration()
        example_validation_workflow()

        print("\n\n" + "=" * 80)
        print("✅ All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()
