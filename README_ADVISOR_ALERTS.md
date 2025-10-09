# Advisor Vault Candidate Alerts - Steve Perry

This script generates the weekly **Advisor Vault Candidate Alerts** email for Steve Perry using Zoho CRM data, Zoom transcripts, and AI-powered bullet extraction.

## Quick Start

### Test with 5 Candidates
```bash
# Activate environment
source zoho/bin/activate

# Run in test mode (processes only 5 candidates)
python3 generate_steve_advisor_alerts.py --test
```

### Generate Full Report (146 Candidates)
```bash
# Full production run
python3 generate_steve_advisor_alerts.py \
    --csv Candidates_2025_10_09.csv \
    --output Advisor_Vault_Candidate_Alerts.html \
    --max-candidates 146
```

## Output

The script generates `Advisor_Vault_Candidate_Alerts.html` with:
- ‼️ **Candidate Name Alert** 🔔
- 📍 **Location** (City, State)
- **5 AI-generated bullets** (from Zoom transcripts + CRM data)
- **Ref code: TWAV#####**

## Data Flow

1. **CSV Input** → Loads 146 vault candidates with TWAV numbers, names, locations
2. **Zoho Enrichment** → Fetches full CRM data (AUM, production, licenses, notes)
3. **Zoom Transcripts** → Downloads interview recordings where available
4. **AI Bullet Extraction** → TalentWell curator generates top 5 bullets per candidate
5. **HTML Output** → Renders in Brandon's format with Steve's corrections

## Features

✅ **Privacy Mode** - Anonymizes company names ("Merrill Lynch" → "Major wirehouse")
✅ **Growth Extraction** - Finds metrics like "grew 40% YoY", "$1B → $1.5B AUM"
✅ **Sentiment Scoring** - GPT-5 analyzes enthusiasm, professionalism, red flags
✅ **Bullet Ranking** - Prioritizes high-value evidence over generic statements
✅ **Parallel Processing** - 10 concurrent tasks (15-20 minutes for 146 candidates)
✅ **Retry Logic** - Handles transient Zoom API failures gracefully

## Command-Line Options

```bash
python3 generate_steve_advisor_alerts.py [OPTIONS]

Options:
  --csv PATH              Path to CSV export (default: Candidates_2025_10_09.csv)
  --output PATH           Output HTML file (default: Advisor_Vault_Candidate_Alerts.html)
  --max-candidates N      Maximum candidates to process (default: 146)
  --test                  Test mode: process only 5 candidates
  --parallel N            Number of parallel tasks (default: 10)
  -h, --help              Show help message
```

## Environment Variables Required

Ensure `.env.local` contains:
```bash
# Zoho OAuth (via Azure proxy)
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth-v2.azurewebsites.net

# Zoom API
ZOOM_ACCOUNT_ID=xyz
ZOOM_CLIENT_ID=xyz
ZOOM_CLIENT_SECRET=xyz

# OpenAI (for GPT-5 sentiment analysis)
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-5-mini

# Feature flags
PRIVACY_MODE=true
FEATURE_GROWTH_EXTRACTION=true
FEATURE_LLM_SENTIMENT=true
```

## CSV Format (Expected Columns)

The script expects a CSV export from Zoho with these columns:
- `Record Id` - Zoho candidate ID
- `Candidate Locator` - TWAV number (e.g., TWAV118275)
- `Candidate Name` - Full name
- `Title` - Job title
- `City`, `State` - Location
- `Cover Letter  Recording URL` - Zoom meeting link (optional)
- `Email`, `Phone`, `Mobile` - Contact info

## Troubleshooting

### No Zoom transcripts fetched
- Check that `Cover Letter  Recording URL` column has valid Zoom URLs
- Verify `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`, `ZOOM_ACCOUNT_ID` in `.env.local`
- Look for "Could not extract meeting ID" warnings in logs

### Missing bullets / Generic output
- Ensure Zoho enrichment is working (check "Enriched X from Zoho" logs)
- Verify `OPENAI_API_KEY` is valid for GPT-5 sentiment scoring
- Check that candidates have notes, transcripts, or structured CRM fields

### Script hangs or times out
- Reduce `--parallel` from 10 to 5 or 3
- Run in `--test` mode first to validate connectivity
- Check network connectivity to Zoho OAuth proxy and Zoom APIs

### Privacy mode not working
- Verify `PRIVACY_MODE=true` in `.env.local`
- Company names should appear as "Major wirehouse", "Large RIA", etc.
- If seeing real company names, check `app/config/feature_flags.py`

## Example Output

```html
<!DOCTYPE html>
<html>
<head><title>Advisor Vault Candidate Alerts - October 09, 2025</title></head>
<body>
<div class="email-container">

<!-- Candidate 1 -->
<p>‼️ <b>Scott Frantz Alert</b> 🔔<br>
📍 <b>Frisco, TX</b></p>
<ul>
<li>CFA charterholder with Georgetown MBA; 8+ years supporting CIO at major RIA</li>
<li>Manages $300M+ across equities, fixed income, alternatives with institutional-grade due diligence</li>
<li>Series 7/66 previously held at Merrill Lynch; exempt from recertification due to CFA status</li>
<li>Seeking CIO or Director of Investments role (family office, multifamily office, RIA)</li>
<li>Current comp: $300K base + $85K bonus + $50K distributions; targeting similar with growth potential</li>
</ul>
<p class="ref-code">Ref code: TWAV47170</p>

<!-- ... 145 more candidates ... -->

</div>
</body>
</html>
```

## Weekly Automation (Future)

This script can be scheduled to run weekly via:
1. **Azure Container Apps Job** (recommended) - cron schedule, managed identity
2. **Cron on server** - `0 9 * * MON python3 generate_steve_advisor_alerts.py`
3. **GitHub Actions** - scheduled workflow with secrets

For now, run manually and send HTML to Steve via email or upload to portal.

## Files Modified/Created

- `generate_steve_advisor_alerts.py` - Main script (NEW)
- `Candidates_2025_10_09.csv` - Input CSV (EXISTING)
- `Advisor_Vault_Candidate_Alerts.html` - Output HTML (GENERATED)
- `README_ADVISOR_ALERTS.md` - This documentation (NEW)

## Support

For issues or questions:
1. Check logs for error messages
2. Run in `--test` mode with 5 candidates
3. Verify environment variables in `.env.local`
4. Review `app/jobs/talentwell_curator.py` for bullet extraction logic
