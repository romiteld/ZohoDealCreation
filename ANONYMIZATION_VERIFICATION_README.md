# Anonymization Verification System

## 📦 What's Included

This verification system ensures vault alert emails maintain candidate confidentiality by scanning for identifying information before deployment.

### Core Files

1. **verify_anonymization.py** (24KB)
   - Main verification script
   - 107 firm names, 103 universities, 64 locations
   - 15 unique identifier patterns
   - 6 verification checks (3 critical, 3 warnings)

2. **VERIFICATION_GUIDE.md** (9.2KB)
   - Complete documentation
   - Usage examples and integration patterns
   - Severity explanations and fix recommendations

3. **ANONYMIZATION_QUICK_REFERENCE.md** (4.9KB)
   - Quick reference for daily use
   - Do's and don'ts with examples
   - Common patterns and fixes

4. **example_vault_workflow.sh** (3.0KB)
   - End-to-end workflow example
   - Generate → Verify → Deploy pipeline
   - CI/CD integration template

### Test Files

5. **test_anonymization_sample.html** (3.2KB)
   - Contains intentional violations
   - Tests all 6 verification categories
   - Expected: 0% pass rate (fails all checks)

6. **test_anonymization_clean.html** (3.6KB)
   - Properly anonymized example
   - Best practices reference
   - Expected: 100% pass rate

## 🚀 Quick Start

```bash
# Test the script works
python3 verify_anonymization.py test_anonymization_sample.html
# Should show multiple violations

python3 verify_anonymization.py test_anonymization_clean.html
# Should show 100% pass rate

# Scan production files
python3 verify_anonymization.py output/*.html
```

## 📊 Verification Categories

### 🚨 CRITICAL (Deployment Blockers)
1. **Firm Names** - 107 specific firms (wirehouses, RIAs, broker-dealers, banks)
2. **ZIP Codes** - 5-digit ZIP codes that pinpoint locations
3. **Exact AUM** - Precise figures like $1.2B or $450M (should be ranges)

### ⚠️ WARNING (Review Recommended)
4. **Universities** - 103 institutions (Ivy League, top business schools, flagships)
5. **Unique Identifiers** - Rankings, clubs, market shares that fingerprint individuals
6. **Specific Locations** - 64 suburbs/small cities (should use major metros)

## 🎯 Usage Patterns

### Development Workflow
```bash
# Generate alerts
python3 app/jobs/vault_alerts_generator.py --audience advisors

# Verify before deploying
python3 verify_anonymization.py output/boss_format_advisors_20251013.html

# If pass (100% on critical), manually review and deploy
# If fail, fix issues and re-verify
```

### CI/CD Integration
```bash
# Strict mode exits with error code 1 if issues found
python3 verify_anonymization.py --strict output/*.html

if [ $? -eq 0 ]; then
    # All clear - deploy
    python3 app/jobs/vault_alerts_scheduler.py
else
    # Issues found - halt deployment
    echo "Fix anonymization issues before deploying"
    exit 1
fi
```

### Multi-File Scanning
```bash
# Scan multiple audiences at once
python3 verify_anonymization.py output/boss_format_*.html

# Shows summary:
# ✅ advisors: 100%
# ⚠️ c_suite: 83%
# 🚨 global: 50%
# Average: 78%
```

## 🔍 What Gets Detected

The script scans **all visible text content** in HTML files and detects:

- **Exact firm names**: "Merrill Lynch", "Fisher Investments", "LPL Financial"
- **ZIP codes**: Any 5-digit codes (avoiding years 1900-2099)
- **University names**: "Harvard", "LSU", "Penn State" (with smart context filtering)
- **Precise AUM**: "$1.2B", "$450M" (ranges like "$400M-$600M" are OK)
- **Unique achievements**: "#1 nationwide", "Chairman's Club", "15% market share"
- **Specific suburbs**: "Frisco", "Scottsdale", "Greenwich" (metros like "Dallas" are OK)

### Smart False Positive Filtering

The script intelligently avoids flagging:
- **Geographic references**: "South Florida region" is OK (not "University of Florida")
- **Generic phrases**: "prestigious business school" is OK (not "Harvard Business School")
- **AUM ranges**: "$800M-$1.2B" is OK (not exact figure)
- **Metro areas**: "Austin metro" is OK (not "78701 ZIP code")

## 📈 Output Format

```
🔍 Anonymization Verification Report
======================================================================

File: boss_format_advisors_20251013.html

✅ Firm Names: PASS (0 specific firms found)
🚨 ZIP Codes: CRITICAL (1 ZIP codes found)
   Line 39: "78701"
      <li>Located in 78701 ZIP code area</li>

Overall Score: 83% (5/6 checks passed)

RECOMMENDATION:
⚠️ Minor issues found - review before deployment
```

## ✅ Best Practices

### DO:
- Use major metro areas: "Dallas-Fort Worth", "Phoenix metro", "Bay Area"
- Use AUM ranges: "$800M-$1.2B", "$400M-$600M"
- Use generic terms: "major wirehouse", "top-tier institution", "elite performer"
- Run verification before every deployment
- Review warnings even if score is passing

### DON'T:
- Use specific firms: "Merrill Lynch", "Fisher Investments"
- Use exact AUM: "$1.2B", "$450M"
- Use universities: "Harvard", "LSU", "Penn State"
- Use ZIP codes: "78701", "10065"
- Use suburbs: "Frisco", "Scottsdale", "Greenwich"
- Deploy files with critical violations

## 🛠️ Customization

To add more patterns, edit the class constants in `verify_anonymization.py`:

```python
class AnonymizationScanner:
    FIRM_NAMES = [...]         # Add more financial firms
    UNIVERSITIES = [...]        # Add more universities
    SPECIFIC_LOCATIONS = [...]  # Add more suburbs
    UNIQUE_IDENTIFIERS = [...]  # Add more regex patterns
```

## 📚 Documentation Structure

1. **ANONYMIZATION_QUICK_REFERENCE.md** - Start here for daily use
2. **VERIFICATION_GUIDE.md** - Complete documentation and troubleshooting
3. **ANONYMIZATION_RULES.md** - Privacy policy and confidentiality standards
4. **example_vault_workflow.sh** - Integration example

## 🧪 Testing

```bash
# Test with intentional violations
python3 verify_anonymization.py test_anonymization_sample.html
# Expected: 0% score, shows violations in all 6 categories

# Test with clean file
python3 verify_anonymization.py test_anonymization_clean.html
# Expected: 100% score, no violations

# Test strict mode (for CI/CD)
python3 verify_anonymization.py --strict test_anonymization_clean.html
echo $?  # Should print: 0 (success)

python3 verify_anonymization.py --strict test_anonymization_sample.html
echo $?  # Should print: 1 (failure)
```

## 📊 Statistics

- **107 Firm Names**: Wirehouses, RIAs, broker-dealers, banks, custodians
- **103 Universities**: Ivy League, top business schools, state flagships, international
- **64 Specific Locations**: Suburbs and small cities to avoid
- **15 Unique Identifier Patterns**: Rankings, clubs, market shares
- **6 Verification Checks**: 3 critical (deployment blockers), 3 warnings

## 🔐 Security Benefits

This verification system protects:
- **Candidate Identity**: Prevents identification through employer/location/education
- **Competitive Intelligence**: No revealing of exact books of business
- **Legal Compliance**: Maintains confidentiality standards
- **Brand Trust**: Demonstrates privacy commitment to candidates

## 🆘 Support & Maintenance

### Common Issues
- **False positives**: Usually filtered automatically (geographic Florida, generic "business school")
- **Missed patterns**: Add to class constants in script
- **Performance**: Handles files up to several MB in <1 second

### Updates
- Add new firms to `FIRM_NAMES` as industry evolves
- Add emerging universities to `UNIVERSITIES`
- Add new suburbs to `SPECIFIC_LOCATIONS` as markets expand

### Contact
- **Technical Issues**: Review VERIFICATION_GUIDE.md troubleshooting
- **Questions**: daniel.romitelli@emailthewell.com
- **Updates**: Check git history for latest changes

## 📝 Integration Checklist

- [ ] Script executable: `chmod +x verify_anonymization.py`
- [ ] Test files present: `test_anonymization_*.html`
- [ ] Documentation reviewed: `VERIFICATION_GUIDE.md`
- [ ] Quick reference printed: `ANONYMIZATION_QUICK_REFERENCE.md`
- [ ] CI/CD pipeline updated: `example_vault_workflow.sh`
- [ ] Team trained on usage and best practices
- [ ] Added to weekly vault alert generation process

## 🎓 Training Resources

1. Run both test files to see violations and clean examples
2. Review ANONYMIZATION_QUICK_REFERENCE.md for do's and don'ts
3. Practice fixing violations in test_anonymization_sample.html
4. Integrate into personal workflow before deploying any alerts

---

**Version**: 1.0
**Created**: 2025-10-13
**Author**: Claude Code
**Maintained by**: Well Intake API Team
