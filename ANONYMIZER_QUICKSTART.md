# Anonymizer Quick Start Guide

## 🚀 Quick Start

### Basic Usage

```python
from app.utils.anonymizer import anonymize_candidate_data

# Anonymize a single candidate
anonymized = anonymize_candidate_data({
    'firm': 'Merrill Lynch',
    'aum': '$1.68B',
    'city': 'Frisco',
    'state': 'TX',
    'professional_designations': 'MBA from LSU'
})

# Result:
# {
#     'firm': 'a leading national wirehouse',
#     'aum': '$1.5B-$2.0B range',
#     'city': 'Dallas/Fort Worth',
#     'state': '',
#     'professional_designations': 'MBA'
# }
```

### Bulk Anonymization

```python
from app.utils.anonymizer import anonymize_candidate_data

candidates = load_candidates_from_db()

anonymized_candidates = [
    anonymize_candidate_data(candidate)
    for candidate in candidates
]
```

## 📋 Anonymization Rules

| Rule | Before | After |
|------|--------|-------|
| **Firm** | Merrill Lynch | a leading national wirehouse |
| **AUM** | $1.68B | $1.5B-$2.0B range |
| **Production** | $500K | $500M-$750M range |
| **Location** | Frisco, TX 75034 | Dallas/Fort Worth |
| **Education** | MBA from LSU | MBA |
| **Systems** | MerrillConnect | internal systems |

## 🔧 Configuration

### Firm Type Mappings

```python
FIRM_MAPPINGS = {
    'merrill': 'a leading national wirehouse',
    'morgan stanley': 'a leading national wirehouse',
    'raymond james': 'a prominent regional brokerage',
    'jpmorgan': 'a leading private bank',
    'northwestern mutual': 'an insurance-affiliated wealth management firm',
    'default': 'a leading financial services firm'
}
```

### AUM Ranges

```python
AUM_RANGES = [
    (0, 25, "$10M-$25M range"),
    (25, 50, "$25M-$50M range"),
    (50, 100, "$50M-$100M range"),
    (100, 150, "$100M-$150M range"),
    (150, 250, "$150M-$250M range"),
    (250, 500, "$250M-$500M range"),
    (500, 750, "$500M-$750M range"),
    (750, 1000, "$750M-$1B range"),
    (1000, 1500, "$1B-$1.5B range"),
    (1500, 2000, "$1.5B-$2B range"),
    (2000, 3000, "$2B-$3B range"),
    (3000, 5000, "$3B-$5B range"),
    (5000, float('inf'), "$5B+ range"),
]
```

### Major Metro Mappings

```python
LOCATION_MAPPINGS = {
    'new york': 'New York Metro',
    'los angeles': 'Los Angeles Metro',
    'chicago': 'Chicago Metro',
    'san francisco': 'San Francisco Bay Area',
    'dallas': 'Dallas/Fort Worth',
    'frisco': 'Dallas/Fort Worth',  # Handles suburbs
    'houston': 'Houston Metro',
    'boston': 'Boston Metro',
    'washington': 'Washington DC Metro',
    'seattle': 'Seattle Metro',
    # ... 50+ mappings
}
```

## 🧪 Testing

### Run Test Suite

```bash
# Activate virtual environment
source zoho/bin/activate

# Set database connection
export DATABASE_URL='postgresql://adminuser:W3llDB2025Pass@well-intake-db-0903.postgres.database.azure.com:5432/wellintake?sslmode=require'

# Run tests
python3 test_anonymizer.py
```

### Test Output

```
🧪 Anonymizer Test Suite
================================================================================
Sample Size: 10 candidates
Database: well-intake-db-0903.postgres.database.azure.com:5432
Started: 2025-10-13 05:37:43 PM

📊 Loading sample candidates from vault_candidates table...
✅ Loaded 10 candidates

🔬 Testing anonymization on each candidate...
--------------------------------------------------------------------------------

Candidate 1/10: TWAV117733
  ✅ ALL RULES APPLIED CORRECTLY

...

================================================================================
📊 Test Summary
--------------------------------------------------------------------------------
Total Candidates: 10
Passed: 10 (100.0%)
Failed: 0 (0.0%)
Confidentiality Score: 100.0%
================================================================================

✅ All tests passed!
```

## 📦 Integration Examples

### 1. Vault Alerts Generator

```python
# Already integrated in vault_alerts_generator.py
if PRIVACY_MODE:
    all_candidates = [self._anonymize_candidate(c) for c in all_candidates]
```

### 2. Weekly Digests

```python
from app.utils.anonymizer import anonymize_candidate_data

# Load candidates
candidates = await load_vault_candidates()

# Anonymize for privacy-safe digest
anonymized = [anonymize_candidate_data(c) for c in candidates]

# Generate digest
digest_html = generate_digest(anonymized)
```

### 3. Teams Bot Responses

```python
from app.utils.anonymizer import anonymize_candidate_data

@router.post("/teams/query")
async def query_candidates(query: str):
    # Execute query
    results = await execute_query(query)

    # Anonymize results for privacy
    anonymized_results = [
        anonymize_candidate_data(candidate)
        for candidate in results
    ]

    # Return anonymized results
    return create_response(anonymized_results)
```

## 🛡️ Privacy Compliance

### What Gets Anonymized

✅ **Firm names** → Generic descriptors
✅ **AUM values** → Rounded ranges
✅ **Production figures** → Rounded ranges
✅ **Specific locations** → Major metro areas
✅ **University names** → Removed
✅ **Proprietary systems** → Generic descriptions

### What Gets Preserved

✅ **Professional designations** (CFP®, CFA®, ChFC®)
✅ **Licenses** (Series 7, 65, 66)
✅ **Years of experience**
✅ **General location** (city/state or metro)
✅ **Job titles**
✅ **Availability**
✅ **Compensation ranges**

## 🔍 Validation

### Check Anonymization Quality

```python
from app.utils.anonymizer import anonymize_candidate_data

original = load_candidate('TWAV117895')
anonymized = anonymize_candidate_data(original)

# Verify firm anonymization
assert 'Avantia' not in anonymized['firm']
assert 'leading financial services firm' in anonymized['firm']

# Verify AUM rounding
assert anonymized['aum'] == '$250M-$500M range'

# Verify location normalization
assert anonymized['city'] == 'Seattle Metro'
```

## 📊 Metrics

### Confidentiality Score

The test suite calculates a confidentiality score based on:
- Number of rules applied successfully
- Total rules tested (6 rules × N candidates)
- Formula: `(passed_rules / total_rules) × 100`

**Current Score: 100.0%** ✅

### Test Coverage

- ✅ Firm name anonymization
- ✅ AUM/production rounding
- ✅ Location normalization
- ✅ University name stripping
- ✅ Achievement generalization
- ✅ Proprietary system removal

## 🐛 Troubleshooting

### Issue: Firm not recognized

**Solution:** Add firm to `FIRM_MAPPINGS` in `anonymizer.py`:

```python
FIRM_MAPPINGS = {
    'your_firm': 'appropriate descriptor',
    # ...
}
```

### Issue: Location not normalized

**Solution:** Add location to `LOCATION_MAPPINGS`:

```python
LOCATION_MAPPINGS = {
    'your_city': 'Appropriate Metro Area',
    # ...
}
```

### Issue: University still showing

**Solution:** Check if university name matches pattern. Add custom pattern if needed:

```python
def _anonymize_education(self, education: str) -> str:
    # Add custom pattern
    education = re.sub(r'your_pattern', '', education, flags=re.IGNORECASE)
    return education.strip()
```

## 📝 Best Practices

1. **Always test** after modifying mappings
2. **Run full test suite** before deployment
3. **Review anonymized output** manually for edge cases
4. **Update mappings** when new firm types appear
5. **Monitor confidentiality score** in production
6. **Log anonymization failures** for continuous improvement

## 🚀 Deployment Checklist

- [ ] Run test suite: `python3 test_anonymizer.py`
- [ ] Verify 100% pass rate
- [ ] Review anonymization_test_report.txt
- [ ] Test with production data sample
- [ ] Enable PRIVACY_MODE in .env.local
- [ ] Deploy to staging environment
- [ ] Validate in staging
- [ ] Deploy to production
- [ ] Monitor logs for anonymization errors

## 📚 Related Files

- `/app/utils/anonymizer.py` - Core anonymization module (CANONICAL)
- `/test_anonymizer.py` - Test suite
- `/anonymization_test_report.txt` - Latest test results
- `/ANONYMIZATION_TEST_SUMMARY.md` - Detailed test summary
- `/app/config/feature_flags.py` - PRIVACY_MODE flag

## 📞 Support

For questions or issues:
1. Check test report: `anonymization_test_report.txt`
2. Review code: `app/utils/anonymizer.py`
3. Run test suite: `python3 test_anonymizer.py`
4. Contact development team
