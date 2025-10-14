# Anonymization Quick Reference

## 🚀 Quick Start

```bash
# Single file
python3 verify_anonymization.py boss_format_advisors_20251013.html

# Multiple files
python3 verify_anonymization.py output/*.html

# CI/CD mode (exits with error if issues found)
python3 verify_anonymization.py --strict output/*.html
```

## ✅ DO's and ❌ DON'Ts

### Firm Names

| ❌ DON'T | ✅ DO |
|----------|--------|
| Currently at Merrill Lynch | 15 years at major wirehouse |
| Fisher Investments advisor | Independent RIA practice |
| LPL Financial producer | National broker-dealer platform |
| SAFE Credit Union | Regional financial institution |

### AUM Figures

| ❌ DON'T | ✅ DO |
|----------|--------|
| Managing $1.2B | Managing $800M-$1.5B |
| $450M book | $400M-$600M book |
| Exactly $2.3B AUM | Over $2B in assets |

### Universities

| ❌ DON'T | ✅ DO |
|----------|--------|
| Harvard MBA | MBA from prestigious institution |
| LSU graduate | Graduate of top Southern university |
| Penn State alumnus | Major state university graduate |
| Wharton School | Elite business school |

### Geographic Locations

| ❌ DON'T | ✅ DO |
|----------|--------|
| Frisco, TX | Dallas-Fort Worth metro |
| Scottsdale practice | Phoenix metro area |
| ZIP code 78701 | Austin metro area |
| Des Moines office | Major Midwest market |

### Unique Identifiers

| ❌ DON'T | ✅ DO |
|----------|--------|
| #1 nationwide | Top-tier producer nationally |
| Chairman's Club member | Elite performance tier |
| Barron's Top 100 | Nationally recognized advisor |
| 15% market share | Significant market presence |

## 📊 Verification Scoring

- **100%** = ✅ Safe for deployment
- **80-99%** = ⚠️ Review warnings, likely okay
- **<80%** = 🚨 Critical issues, do NOT deploy

## 🔍 Severity Levels

### 🚨 CRITICAL (Blocks Deployment)
1. **Firm Names** - Identifies exact employer
2. **ZIP Codes** - Pinpoints exact location
3. **Exact AUM** - Fingerprints specific advisor

### ⚠️ WARNING (Review Recommended)
4. **Universities** - May identify via education
5. **Unique Identifiers** - Rankings/achievements
6. **Specific Locations** - Suburbs instead of metros

## 🛠️ Common Fixes

### Pattern 1: Firm Name + AUM
```html
Before: "15 years at Merrill Lynch, managing $1.2B"
After:  "15 years at major wirehouse, managing $800M-$1.5B"
```

### Pattern 2: Education + Location
```html
Before: "Harvard MBA based in 78701 (Austin)"
After:  "MBA from prestigious institution based in Austin metro"
```

### Pattern 3: Achievement + Firm
```html
Before: "Chairman's Club at Morgan Stanley, #1 in region"
After:  "Elite performance tier at major wirehouse, top regional producer"
```

### Pattern 4: Specific Suburb
```html
Before: "Scottsdale practice with $450M AUM"
After:  "Phoenix metro practice with $400M-$600M AUM"
```

## 📝 Checklist Before Deployment

- [ ] Run verification: `python3 verify_anonymization.py output/*.html`
- [ ] Check overall score is ≥80%
- [ ] Fix ALL critical issues (firms, ZIPs, exact AUM)
- [ ] Review warnings (universities, identifiers, locations)
- [ ] Verify ranges used instead of exact figures
- [ ] Confirm major metros used instead of suburbs
- [ ] Manual spot-check for edge cases
- [ ] Test email rendering in Outlook
- [ ] Deploy via scheduler

## 🔧 Troubleshooting

### False Positive: Geographic "Florida"
```html
❌ Flagged: "market presence in South Florida"
✅ Actually OK: It's a geographic reference, not "University of Florida"
```
**Fix**: Script now detects geographic context automatically.

### False Positive: Generic "business school"
```html
❌ Flagged: "graduate of prestigious business school"
✅ Actually OK: Generic phrase, not specific institution
```
**Fix**: Script filters out generic phrases when preceded by "prestigious/top-tier".

### Missing Detection: Misspelled Firm
```html
⚠️ Not caught: "Merill Linch" (typo)
```
**Solution**: Add common misspellings to FIRM_NAMES list in script.

## 📈 Integration with CI/CD

```bash
#!/bin/bash
# Generate + Verify + Deploy pipeline

python3 app/jobs/vault_alerts_generator.py --output output/alerts.html

if python3 verify_anonymization.py --strict output/alerts.html; then
    echo "✅ Verification passed - deploying"
    python3 app/jobs/vault_alerts_scheduler.py
else
    echo "🚨 Verification failed - halting deployment"
    exit 1
fi
```

## 📚 Full Documentation

See [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) for complete details.

## 🆘 Support

- **Issues**: Check VERIFICATION_GUIDE.md troubleshooting section
- **Testing**: Use `test_anonymization_sample.html` for violations
- **Clean Example**: Use `test_anonymization_clean.html` for reference
- **Contact**: daniel.romitelli@emailthewell.com

---

**Version**: 1.0 | **Updated**: 2025-10-13
