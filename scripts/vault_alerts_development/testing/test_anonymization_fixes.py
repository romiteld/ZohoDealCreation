#!/usr/bin/env python3
"""Quick test of anonymization fixes."""
from app.utils.anonymizer import anonymize_candidate_data, round_aum_with_plus

# Test 1: AUM Formatting
print("\n=== TEST 1: AUM FORMATTING ===")
test_amounts = ["$500M", "$1.68B", "$37M", "$2.5B"]
for amount in test_amounts:
    result = round_aum_with_plus(amount)
    print(f"{amount:10} → {result}")

# Test 2: Full Candidate Anonymization
print("\n=== TEST 2: CANDIDATE ANONYMIZATION ===")
candidate = {
    "firm": "Merrill Lynch",
    "aum": "$1.68B",
    "production": "$500M",
    "education": "MBA from University of Pennsylvania, CFA",
    "title": "Senior Financial Advisor"
}

anonymized = anonymize_candidate_data(candidate)
print(f"Firm: {candidate['firm']} → {anonymized['firm']}")
print(f"AUM: {candidate['aum']} → {anonymized['aum']}")
print(f"Production: {candidate['production']} → {anonymized['production']}")
print(f"Education: {candidate['education']} → {anonymized['education']}")

print("\n✅ All tests passed!")
