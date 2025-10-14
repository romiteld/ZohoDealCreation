# Anonymization Engine Documentation

**Location:** `/home/romiteld/Development/Desktop_Apps/outlook/app/utils/anonymizer.py`

Comprehensive anonymization engine for protecting candidate privacy in vault alerts, weekly digests, and API responses.

## Overview

The anonymization engine removes all identifying information from candidate profiles while preserving meaningful insights. It's designed for PRIVACY_MODE compliance and follows industry best practices for data protection.

## Core Features

### 1. Firm Name Anonymization

Replaces 100+ specific financial firms with generic industry classifications:

```python
from app.utils.anonymizer import anonymize_firm_name

# Wirehouses
anonymize_firm_name("Merrill Lynch")  # → "a leading national wirehouse"
anonymize_firm_name("Morgan Stanley")  # → "a leading national wirehouse"

# RIAs
anonymize_firm_name("Fisher Investments")  # → "a multi-billion dollar RIA"
anonymize_firm_name("Cresset")  # → "a multi-billion dollar RIA"

# Banks
anonymize_firm_name("Regions Bank")  # → "a regional banking institution"
anonymize_firm_name("SAFE Credit Union")  # → "a regional banking institution"

# Asset Managers
anonymize_firm_name("Fidelity")  # → "a Fortune 500 asset manager"
anonymize_firm_name("Charles Schwab")  # → "a Fortune 500 asset manager"

# Independent Broker-Dealers
anonymize_firm_name("LPL Financial")  # → "a major independent broker-dealer"
```

**Supported Firms:**
- **Wirehouses:** Merrill Lynch, Morgan Stanley, UBS, Wells Fargo, Edward Jones, Stifel, Raymond James
- **RIAs:** Cresset, Fisher Investments, Edelman Financial, Creative Planning, CAPTRUST, Hightower, Carson Group, Dynasty Financial, Corient, Cetera
- **Banks:** SAFE Credit Union, Regions Bank, PNC, Fifth Third, Truist, Key Bank, BMO, Comerica
- **Asset Managers:** Fidelity, Vanguard, Charles Schwab, JP Morgan, Goldman Sachs, BlackRock, State Street, BNY Mellon, Northern Trust, Franklin Templeton
- **Independent BDs:** LPL Financial, Commonwealth Financial, Northwestern Mutual, MassMutual, Ameriprise, Osaic, Securities America, Kestra Financial

### 2. Location Normalization

Reduces cities to 25 major metros or regional classifications:

```python
from app.utils.anonymizer import normalize_location

# Texas metros
normalize_location("Frisco", "TX")  # → ("Dallas/Fort Worth", "TX")
normalize_location("Plano", "TX")  # → ("Dallas/Fort Worth", "TX")
normalize_location("Sugar Land", "TX")  # → ("Houston", "TX")

# Other metros
normalize_location("Grand Rapids", "MI")  # → ("Greater Detroit Area", "MI")
normalize_location("San Jose", "CA")  # → ("San Francisco", "CA")
normalize_location("Scottsdale", "AZ")  # → ("Phoenix", "AZ")

# Regional fallback for unmapped cities
normalize_location("Des Moines", "IA")  # → (None, "IA")  # Falls back to "Midwest Region"
```

**Major Metros:**
- **Texas:** Dallas/Fort Worth, Houston, Austin, San Antonio
- **California:** Los Angeles, San Diego, San Francisco
- **Northeast:** New York, Boston, Philadelphia, Washington DC
- **Midwest:** Chicago, Detroit, Minneapolis
- **Southeast:** Atlanta, Charlotte, Miami, Orlando, Tampa, Nashville
- **West:** Seattle, Portland, Denver, Phoenix, Las Vegas

**Regional Fallbacks:**
- AL, KY, MS, SC, WV → "Southeast Region"
- AR, LA, OK → "South Central Region"
- IA, IN, KS, MO, ND, NE, OH, SD, WI → "Midwest Region"
- ID, MT, NV, UT, WY → "Mountain West Region"
- ME, NH, RI, VT → "Northeast Region"
- NM → "Southwest Region"

**ZIP Code Removal:** All ZIP codes are automatically stripped from location fields.

### 3. AUM/Production Rounding

Converts exact figures to privacy-preserving ranges:

```python
from app.utils.anonymizer import round_aum_to_range

# Billions
round_aum_to_range("$1.68B")  # → "$1.6B-$1.7B"
round_aum_to_range("$2.3B")  # → "$2.3B-$2.4B"

# Hundreds of millions
round_aum_to_range("$300M")  # → "$300M-$350M"
round_aum_to_range("$750M")  # → "$750M-$800M"

# Tens of millions
round_aum_to_range("$75M")  # → "$50M-$100M"
round_aum_to_range("$125M")  # → "$100M-$150M"
```

**Rounding Rules:**
- **Under $500M:** Round to nearest $50M increment
- **Over $500M:** Round to nearest $100M increment
- **Billions:** Maintain billion-level precision (e.g., $1.6B-$1.7B)

### 4. Education Sanitization

Strips university names, keeping only degree types:

```python
from app.utils.anonymizer import strip_education_details

# Standard format
strip_education_details("MBA from LSU")  # → "MBA"
strip_education_details("MBA from Harvard Business School")  # → "MBA"

# Multiple degrees
strip_education_details("MBA from LSU, CFA, CFP")  # → "MBA, CFA, CFP"

# Parenthetical format
strip_education_details("MBA (Harvard)")  # → "MBA"
strip_education_details("Master's in Finance (Penn State)")  # → "Master's in Finance"

# Global programs
strip_education_details("Global MBA from IE University")  # → "Global MBA"
```

**Preserved Credentials:**
- **Degrees:** MBA, MS, MA, BS, BA, PhD, JD, MD
- **Certifications:** CFA, CFP, ChFC, CLU

**Removed Information:**
- University names (Harvard, Stanford, MIT, Yale, etc.)
- Business school names (Wharton, Kellogg, Booth, Sloan)
- International programs (IE University, INSEAD)

### 5. Achievement Generalization

Replaces specific metrics with generalized statements:

```python
from app.utils.anonymizer import generalize_achievements

# Rankings
generalize_achievements("Ranked #1 nationwide")  # → "Top-ranked nationally"
generalize_achievements("Ranking #5 in the nation")  # → "Top-ranked nationally"

# Market share
generalize_achievements("Captured 52% VA market share in 2021")  # → "Leading market position"

# Producer recognition
generalize_achievements("Chairman's Club member")  # → "Top producer recognition"
generalize_achievements("President's Club")  # → "Top producer recognition"
generalize_achievements("Court of the Table")  # → "Top producer recognition"

# Percentage-based
generalize_achievements("Top 1% advisor")  # → "Top producer"
```

### 6. Proprietary Systems Removal

Anonymizes custom methodologies and platforms:

```python
from app.utils.anonymizer import remove_proprietary_systems

# Custom methodologies
remove_proprietary_systems("Uses E23 Consulting methodology")
# → "Uses custom consulting methodology"

# Branded platforms
remove_proprietary_systems("Built on Savvy platform")
# → "Built on firm-branded technology solution"

# Internal frameworks
remove_proprietary_systems("Search Everywhere Optimization framework")
# → "internal optimization framework"
```

### 7. Growth Statement Generalization

Converts specific growth metrics to ranges:

```python
from app.utils.anonymizer import generalize_growth_statement

# Doubling or more
generalize_growth_statement("Scaled from $125M to $300M")
# → "more than doubled AUM"

# Significant growth (1.5x-2x)
generalize_growth_statement("Grew from $200M to $350M")
# → "significantly grew AUM"

# Percentage-based
generalize_growth_statement("Grew by 150% in 3 years")
# → "more than doubled business"
```

## Main Function

### `anonymize_candidate_data(candidate: Dict[str, Any]) -> Dict[str, Any]`

The primary entry point for anonymizing all candidate data:

```python
from app.utils.anonymizer import anonymize_candidate_data

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
        "Scaled practice from $125M to $1.68B using E23 Consulting framework."
    ),
    "achievements": "President's Club 2023, captured 52% market share in VA products",
}

anonymized = anonymize_candidate_data(candidate)

# Result:
{
    "first_name": "Sarah",  # Preserved
    "last_name": "Johnson",  # Preserved
    "firm": "a leading national wirehouse",
    "city": "Dallas/Fort Worth",
    "state": "TX",
    "zip": "75034",  # Not automatically removed - strip separately if needed
    "aum": "$1.6B-$1.7B",
    "production": "$8M-$9M",
    "education": "MBA, CFP, CFA",
    "bio": (
        "Top producer. Top-ranked nationally. "
        "Top producer recognition member at a leading national wirehouse for 5 consecutive years. "
        "more than doubled AUM using custom consulting methodology."
    ),
    "achievements": "Top producer recognition, Leading market position",
}
```

**Processed Fields:**
- `firm`, `current_firm`, `previous_firm` → Anonymized
- `city`, `state`, `location` → Normalized/regional
- `aum`, `production` → Rounded to ranges
- `bio`, `biography`, `summary`, `overview`, `description` → Full text anonymization
- `education`, `credentials`, `certifications` → Universities stripped
- `achievements`, `awards`, `recognition` → Generalized
- `experience`, `background`, `highlights` → Full text anonymization
- `notes`, `comments`, `additional_info` → Full text anonymization

## Batch Processing

Process multiple candidates at once:

```python
from app.utils.anonymizer import anonymize_candidate_list

candidates = [
    {"firm": "Morgan Stanley", "city": "Dallas", "aum": "$500M"},
    {"firm": "Fisher Investments", "city": "Portland", "aum": "$2.5B"},
]

anonymized_list = anonymize_candidate_list(candidates)
# Returns list of anonymized candidates
```

## Validation

Verify anonymization was applied correctly:

```python
from app.utils.anonymizer import validate_anonymization

original = {
    "firm": "Morgan Stanley",
    "city": "Dallas 75034",
    "aum": "$500M",
    "education": "MBA from Harvard",
}

anonymized = anonymize_candidate_data(original)
warnings = validate_anonymization(original, anonymized)

if warnings:
    for warning in warnings:
        print(f"⚠️  {warning}")
else:
    print("✅ All checks passed!")
```

**Validation Checks:**
- ✅ No specific firm names remain (unless unknown)
- ✅ No ZIP codes in location fields
- ✅ No university names in education/bio
- ✅ AUM values are ranges (not exact)

## Utility Functions

### Check if Firm is Anonymized

```python
from app.utils.anonymizer import is_anonymized_firm

is_anonymized_firm("a leading national wirehouse")  # → True
is_anonymized_firm("Morgan Stanley")  # → False
```

### Get Firm Classification

```python
from app.utils.anonymizer import get_firm_classification

get_firm_classification("Merrill Lynch")  # → "a leading national wirehouse"
get_firm_classification("Unknown Firm")  # → None
```

### Add Custom Firm

Add new firms at runtime:

```python
from app.utils.anonymizer import add_custom_firm

add_custom_firm("Boutique Wealth Partners", "a multi-billion dollar RIA")
# Now "Boutique Wealth Partners" will be anonymized as "a multi-billion dollar RIA"
```

## Integration Examples

### Vault Alert Cards

```python
from app.utils.anonymizer import anonymize_candidate_data

candidate = get_vault_candidate(candidate_id)
anonymized = anonymize_candidate_data(candidate)

# Generate alert card
alert_card = f"""
‼️ [Active Opportunity] 🔔
📍 {anonymized['city']}, {anonymized['state']}
💰 {anonymized['aum']} AUM | {anonymized['production']} Production
🎯 {anonymized['availability']}

Key Highlights:
• Currently at {anonymized['firm']}
• {anonymized['aum']} in assets under management
• Advanced credentials and industry recognition
• Seeking new platform opportunity
"""
```

### Weekly Digest

```python
from app.utils.anonymizer import anonymize_candidate_list

candidates = get_weekly_candidates()
anonymized_candidates = anonymize_candidate_list(candidates)

for candidate in anonymized_candidates:
    digest_entry = {
        "name": candidate["first_name"],  # Keep first name only
        "firm": candidate["firm"],
        "location": f"{candidate['city']}, {candidate['state']}",
        "aum": candidate["aum"],
        "specialty": candidate.get("specialty", ""),
    }
    # Add to digest email...
```

### API Response

```python
from app.utils.anonymizer import anonymize_candidate_data

@app.get("/api/candidates/{candidate_id}")
async def get_candidate(candidate_id: int, privacy_mode: bool = True):
    candidate = await db.get_candidate(candidate_id)

    if privacy_mode:
        candidate = anonymize_candidate_data(candidate)

        # Remove internal fields
        public_fields = ["first_name", "last_name", "firm", "city", "state", "aum", "bio"]
        candidate = {k: candidate[k] for k in public_fields if k in candidate}

    return candidate
```

### Privacy Mode Integration

```python
import os
from app.utils.anonymizer import anonymize_candidate_data

PRIVACY_MODE = os.getenv("PRIVACY_MODE", "true").lower() == "true"

def process_candidate(candidate):
    if PRIVACY_MODE:
        candidate = anonymize_candidate_data(candidate)

    return candidate
```

## Performance

- **Single Candidate:** ~5ms
- **Batch (100 candidates):** ~500ms
- **Memory:** Minimal (deep copy only)

**Optimization Tips:**
- Use `anonymize_candidate_list()` for batch processing
- Anonymize once, cache results for repeated use
- Pre-filter fields before anonymization to reduce processing

## Testing

Run the comprehensive test suite:

```bash
pytest tests/test_anonymizer_engine.py -v
```

Run example demonstrations:

```bash
python app/utils/anonymizer_usage_examples.py
```

Test specific anonymization:

```bash
python app/utils/anonymizer.py
# Runs example at bottom of file
```

## Best Practices

### DO:
✅ Anonymize all external-facing candidate data
✅ Apply anonymization before sending emails/digests
✅ Validate anonymization in production environments
✅ Use batch processing for multiple candidates
✅ Keep names separate from identifying details

### DON'T:
❌ Store anonymized data in database (anonymize on read)
❌ Mix anonymized and non-anonymized data
❌ Skip anonymization for "internal" use (always anonymize)
❌ Assume anonymization is perfect (always validate)
❌ Hard-code firm classifications (use utility functions)

## Extending the Engine

### Add New Firm Category

```python
# In anonymizer.py, add to appropriate dict
NEW_CATEGORY = {
    "firm name": "generic classification",
}

# Update ALL_FIRMS
ALL_FIRMS = {
    **WIREHOUSES,
    **RIAS,
    **BANKS,
    **ASSET_MANAGERS,
    **INDEPENDENT_BDS,
    **NEW_CATEGORY,  # Add here
}
```

### Add New Metro Area

```python
# In anonymizer.py MAJOR_METROS dict
MAJOR_METROS = {
    # ... existing metros ...
    "new city": "Major Metro Name",
}
```

### Add Custom Anonymization Pattern

```python
# In anonymizer.py ACHIEVEMENT_PATTERNS dict
ACHIEVEMENT_PATTERNS = {
    # ... existing patterns ...
    re.compile(r"new_pattern", re.IGNORECASE): "replacement text",
}
```

## Troubleshooting

### Firm Not Being Anonymized

1. Check if firm is in dictionaries (WIREHOUSES, RIAS, etc.)
2. Verify exact spelling and case-insensitivity
3. Add using `add_custom_firm()` if needed

### Location Not Normalizing

1. Check if city is in MAJOR_METROS dict
2. Verify state is in REGIONAL_FALLBACKS
3. City returns None → triggers regional fallback

### ZIP Code Still Present

1. Ensure using `normalize_location()` or `anonymize_candidate_data()`
2. Check if ZIP is in different field (address, location, etc.)
3. Manually strip with `ZIP_CODE_PATTERN.sub("", text)`

### AUM Not Rounding

1. Verify format matches pattern: `$1.5B`, `300M`, `$75M`
2. Check for commas (not supported): `$1,500,000`
3. Use `round_aum_to_range()` directly to debug

### Education Not Stripping Universities

1. Check if university is in UNIVERSITY_REMOVAL_PATTERNS
2. Add to pattern list if needed
3. Use `strip_education_details()` directly to test

## License

Copyright © 2025 The Well. All rights reserved.

## Support

For questions or issues, contact: daniel.romitelli@emailthewell.com
