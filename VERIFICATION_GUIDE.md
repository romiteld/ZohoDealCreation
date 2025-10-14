# Anonymization Verification Guide

## Overview

The `verify_anonymization.py` script scans generated vault alert HTML files to detect confidentiality leaks before deployment. This ensures compliance with privacy standards and protects candidate identities.

## Quick Start

```bash
# Single file scan
python3 verify_anonymization.py boss_format_advisors_20251013.html

# Multiple files
python3 verify_anonymization.py output/*.html

# Strict mode (exit with error if issues found) - useful for CI/CD
python3 verify_anonymization.py --strict boss_format_advisors_20251013.html
```

## What It Checks

### 1. Firm Names (CRITICAL) 🚨
Detects specific financial firm names that could identify candidates:
- **Wirehouses**: Merrill Lynch, Morgan Stanley, UBS, Wells Fargo
- **Independent RIAs**: Cresset, Fisher Investments, Edelman, Creative Planning
- **Broker-Dealers**: LPL Financial, Raymond James, Ameriprise
- **Custodians**: Fidelity, Vanguard, Charles Schwab
- **Regional Banks**: SAFE Credit Union, Regions Bank, PNC
- **100+ firm names** total

**Example Violations:**
```html
❌ Currently at Merrill Lynch, managing $450M
✅ 15 years at major wirehouse, managing $400M-$600M
```

### 2. ZIP Codes (CRITICAL) 🚨
Finds 5-digit ZIP codes that could pinpoint locations:

**Example Violations:**
```html
❌ Located in 78701 ZIP code area
✅ Located in Austin metro area
```

### 3. Universities (WARNING) ⚠️
Identifies specific university/college names:
- Ivy League schools (Harvard, Yale, Princeton)
- Top business schools (Stanford GSB, Wharton, Kellogg)
- State flagships (LSU, Penn State, Texas, Michigan)
- 100+ institution names

**Acceptable Usage:**
```html
✅ MBA from top-tier business school
✅ Graduate of prestigious West Coast institution
❌ Harvard Business School graduate
❌ LSU MBA
```

### 4. Exact AUM Figures (CRITICAL) 🚨
Detects precise dollar amounts instead of ranges:

**Example Violations:**
```html
❌ Managing $1.2B in AUM
❌ $450M book of business
✅ Managing $800M-$1.2B across 400+ families
✅ $400M-$600M practice
```

### 5. Unique Identifiers (WARNING) ⚠️
Finds achievement markers that could identify individuals:
- "#1 nationwide" or "#1 in the nation"
- "Chairman's Club" / "President's Club"
- "Barron's Top 100" / "Forbes Top 50"
- Exact market share percentages

**Example Violations:**
```html
❌ #1 nationwide in ultra-high-net-worth acquisition
❌ Chairman's Club member 5 consecutive years
❌ 15% market share in South Florida
✅ Top producer in region
✅ Consistent top-tier performance
```

### 6. Specific Locations (WARNING) ⚠️
Identifies suburbs and small cities (should use major metros):
- **Texas**: Frisco, Plano, Southlake, The Woodlands
- **California**: Palo Alto, Newport Beach, La Jolla
- **Other**: Scottsdale, Greenwich, Winnetka, Des Moines

**Example Violations:**
```html
❌ Based in Scottsdale, AZ
❌ Frisco, TX practice
✅ Phoenix metro area
✅ Dallas-Fort Worth metroplex
```

## Report Format

```
======================================================================
🔍 Anonymization Verification Report
======================================================================

File: boss_format_advisors_20251013.html

✅ Firm Names: PASS (0 specific firms found)
🚨 ZIP Codes: CRITICAL (1 ZIP codes found)
   Line 39: "78701"
      <li>Located in 78701 ZIP code area</li>
✅ Universities: PASS (0 university references found)
🚨 Exact AUM: CRITICAL (2 precise figures found)
   Line 25: "$450M"
      <li>Currently at Merrill Lynch, managing $450M AUM</li>
   Line 37: "$1.2B"
      <li>Currently managing $1.2B in AUM at wirehouse</li>
⚠️ Unique Identifiers: WARNING (1 unique identifiers found)
   Line 38: "Chairman's Club"
      <li>Top producer in region, Chairman's Club member</li>
✅ Specific Locations: PASS (0 suburbs/specific cities found)

Overall Score: 50% (3/6 checks passed)

RECOMMENDATION:
🚨 CRITICAL ISSUES FOUND - DO NOT DEPLOY
   Fix firm names, ZIP codes, and exact AUM figures before sending.

======================================================================
```

## Severity Levels

### 🚨 CRITICAL (Must Fix Before Deployment)
- **Firm Names**: Direct breach of confidentiality
- **ZIP Codes**: Enables precise location tracking
- **Exact AUM**: Fingerprints specific advisors

**Action Required**: Fix all critical issues immediately. Files with critical issues should NOT be deployed.

### ⚠️ WARNING (Review Recommended)
- **Universities**: Less critical but still identifying
- **Unique Identifiers**: May reveal identity through achievements
- **Specific Locations**: Narrows geographic area too much

**Action Recommended**: Review and consider generalizing. Not deployment-blocking but should be addressed.

## Usage Modes

### Standard Scan
```bash
python3 verify_anonymization.py boss_format_advisors_20251013.html
```
Shows full report with all findings and line numbers.

### Strict Mode (CI/CD)
```bash
python3 verify_anonymization.py --strict boss_format_advisors_20251013.html
echo $?  # Exit code: 0 = no issues, 1 = issues found
```
Use in automated pipelines to block deployment if issues exist.

### Multi-File Scan
```bash
python3 verify_anonymization.py output/*.html
```
Scans multiple files and shows aggregate summary:
```
Multi-File Summary (3 files)
======================================================================

✅ boss_format_advisors_20251013.html: 100%
⚠️ boss_format_c_suite_20251013.html: 83%
🚨 boss_format_global_20251013.html: 50%

Average Score: 78%
```

## Installation

### Requirements
```bash
# Optional: colorama for colored output
pip install colorama

# Script works without colorama but output is monochrome
```

### Make Executable
```bash
chmod +x verify_anonymization.py
```

## Integration with Vault Alert Workflow

### Pre-Deployment Checklist
1. Generate HTML files using `generate_boss_format_langgraph.py`
2. Run verification: `python3 verify_anonymization.py output/*.html`
3. Review findings and fix critical issues
4. Re-run verification until 100% pass rate on critical checks
5. Manual review of warnings
6. Deploy via email scheduler

### Automated Pipeline (Future)
```bash
#!/bin/bash
# Weekly vault alert generation with verification

# Generate alerts
python3 app/jobs/vault_alerts_generator.py

# Verify anonymization
python3 verify_anonymization.py --strict output/*.html

if [ $? -eq 0 ]; then
    echo "✅ Verification passed - deploying alerts"
    python3 app/jobs/vault_alerts_scheduler.py
else
    echo "🚨 Verification failed - alerts NOT deployed"
    # Send notification to admin
    exit 1
fi
```

## Common Fixes

### Firm Name Violations
```html
# Before
Currently at Merrill Lynch, managing $450M

# After
15 years at major wirehouse, managing $400M-$600M
```

### ZIP Code Violations
```html
# Before
Located in 78701 ZIP code area

# After
Located in Austin metro area
```

### University Violations
```html
# Before
LSU MBA, Harvard Business School graduate

# After
MBA from top-tier Southern institution, prestigious business school graduate
```

### Exact AUM Violations
```html
# Before
Managing $1.2B in AUM, $450M book

# After
Managing $800M-$1.2B, $400M-$600M book
```

### Unique Identifier Violations
```html
# Before
#1 nationwide, Chairman's Club member, 15% market share

# After
Top-tier producer, consistent elite performance, significant regional presence
```

### Location Violations
```html
# Before
Based in Scottsdale, Frisco office, Greenwich practice

# After
Phoenix metro area, Dallas-Fort Worth metroplex, NYC metro region
```

## False Positives

The script is designed to minimize false positives:

1. **Generic Education References**: "prestigious business school" is allowed
2. **Location Names**: "Miami" in geographic context is allowed (not "Miami University")
3. **AUM Ranges**: "$800M-$1.2B" is acceptable (ranges are good)
4. **Generic Achievements**: "top producer" is allowed (specific rankings are not)

## Customization

To add more patterns to scan, edit the class constants in `verify_anonymization.py`:

```python
class AnonymizationScanner:
    FIRM_NAMES = [...]        # Add more firms
    UNIVERSITIES = [...]       # Add more schools
    UNIQUE_IDENTIFIERS = [...]  # Add more patterns
    SPECIFIC_LOCATIONS = [...]  # Add more suburbs
```

## Testing

Test file included: `test_anonymization_sample.html`

```bash
# Test the script with sample violations
python3 verify_anonymization.py test_anonymization_sample.html
```

Expected output: Multiple violations across all categories.

## Support

For issues or questions:
- Review this guide first
- Check CLAUDE.md for project context
- Test with `test_anonymization_sample.html` to verify script behavior
- Contact: daniel.romitelli@emailthewell.com

## Version History

- **v1.0** (2025-10-13): Initial release with 6 verification checks
  - 100+ firm names
  - ZIP code detection
  - 100+ universities
  - Exact AUM detection
  - Unique identifier patterns
  - 50+ specific locations
