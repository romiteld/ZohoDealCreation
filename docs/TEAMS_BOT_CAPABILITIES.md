# TalentWell Teams Bot - Complete Capabilities Guide

## Overview

The TalentWell Teams Bot is a Microsoft Teams integration that provides automated candidate digest delivery, natural language querying of Zoho CRM data, and interactive Adaptive Cards for managing preferences and viewing analytics.

**Current Status**: ✅ Fully operational in 1:1 personal chats
**Limitation**: ❌ Not yet configured for channels or group chats (see [Future Enhancements](#future-enhancements))

---

## Core Features

### 1. Weekly Digest Generation

Generate curated candidate digests with automatic email delivery subscriptions.

#### Commands:
- `digest` - Generate digest using your default audience preference
- `digest advisors` - Generate digest for Financial/Wealth/Investment Advisors only
- `digest c_suite` - Generate digest for C-Suite executives (CEOs, CFOs, VPs, Directors)
- `digest global` - Generate digest for all candidates (both types)
- `digest <email@company.com>` - Test mode: route digest to specific email

#### Features:
- **Smart Filtering**: Filters by job title keywords (not owner email)
- **Scoring & Ranking**: Uses VoIT (Value of Insight Tree) for candidate prioritization
- **Zoom Transcript Analysis**: Extracts evidence from Zoom meeting transcripts
- **Privacy Mode**: Company anonymization and data obfuscation (enabled by default)
- **Sentiment Analysis**: GPT-5 powered sentiment scoring from transcripts
- **Growth Extraction**: Parses growth metrics like "grew 40% YoY" or "$1B → $1.5B AUM"

#### Digest Format:
```
‼️ [Job Title] Candidate Alert 🔔
[Candidate Name]
📍 [Location]
• Bullet point 1
• Bullet point 2
• Bullet point 3
• Bullet point 4
• Bullet point 5
Ref code: TWAV[8-digit ID]
```

#### Weekly Email Subscriptions:
- Subscribe via `preferences` command
- Choose delivery email, frequency (daily/weekly/monthly), and max candidates (1-20)
- Automatic delivery at 9 AM in your timezone
- Confirmation emails sent for subscribe/unsubscribe/update actions
- Managed by `WeeklyDigestScheduler` background job

---

### 2. Natural Language Query Engine

Ask questions about your Zoho CRM data using conversational language.

#### Access Control:
- **Executive Users** (steve@, brandon@, daniel.romitelli@): Full access to all business data
- **Regular Recruiters**: Filtered to see only their own records (by `owner_email`)

#### Query Examples:

**Candidate Queries:**
- "How many vault candidates were published last week?"
- "Show me all candidates from Q4"
- "Who are the top advisors from California?"
- "Find candidates with AUM over $1B"

**Meeting Queries:**
- "How many interviews did I have last month?"
- "Show me all meetings with zoom transcripts"
- "What meetings did Brandon attend last week?"

**Deal Queries:**
- "How many deals are in the pipeline?"
- "Show me my active deals"
- "What's the status of John Smith?"

#### How It Works:
1. **Intent Classification**: GPT-5-mini classifies query intent and extracts entities
2. **Access Control**: Applies owner filtering for non-executives
3. **Zoho Query**: Queries Zoho CRM Candidates module (not PostgreSQL cache)
4. **Response Formatting**: Returns results in plain text or Adaptive Cards

#### Supported Data:
- ✅ **Candidates** (Zoho CRM Candidates module - 144 vault records)
- ✅ **Deals** (Zoho CRM Deals module)
- ✅ **Deal Notes** (Zoho CRM Notes module)
- ✅ **Meetings** (includes Zoom transcripts when available)
- ❌ **NOT** the local PostgreSQL cache (only 73 records)

---

### 3. Preferences Management

Customize your bot experience and email subscription settings.

#### Command:
- `preferences` - Show/edit your preferences

#### Available Settings:

**Bot Preferences:**
- **Default Audience**: Choose default candidate type (Advisors, C-Suite, Global)
- **Digest Frequency**: How often to receive digests (Daily, Weekly, Monthly)
- **Bot Notifications**: Enable/disable bot notifications

**Email Subscription:**
- **Subscribe to Weekly Digests**: Toggle email delivery on/off
- **Email Address**: Choose delivery email (defaults to Teams email if blank)
- **Max Candidates Per Digest**: Set candidate limit (1-20, default: 6)

#### Subscription Flow:
1. User types `preferences`
2. Bot shows Adaptive Card with current settings
3. User modifies settings and clicks "💾 Save Preferences"
4. Bot saves to database and triggers scheduled delivery calculation
5. Confirmation email sent to delivery address
6. User receives first digest at next scheduled time

---

### 4. Analytics Dashboard

View your Teams Bot usage statistics and digest request history.

#### Command:
- `analytics` - View your usage stats

#### Metrics Shown:
- Total conversations with bot
- Total digest requests generated
- Last conversation timestamp
- Last digest request timestamp
- Recent digest performance (cards generated, execution time)

---

### 5. Help System

Get formatted help with all available commands and capabilities.

#### Command:
- `help` - Display comprehensive help card

#### Help Card Includes:
- Command reference with examples
- Audience filtering explanation
- Natural language query tips
- Link to full documentation

---

## Technical Architecture

### Data Flow

#### Digest Generation:
```
User Command → Teams Bot API → TalentWellCurator
                                      ↓
                              ZohoClient (OAuth Proxy)
                                      ↓
                              Zoho CRM API (144 records)
                                      ↓
                              VoIT Ranking Engine
                                      ↓
                              Zoom Transcript Fetching
                                      ↓
                              GPT-5 Sentiment Analysis
                                      ↓
                              HTML Digest Generation
                                      ↓
                              Email Delivery (if subscribed)
```

#### Natural Language Queries:
```
User Question → Teams Bot API → QueryEngine
                                      ↓
                              GPT-5-mini (Intent Classification)
                                      ↓
                              Access Control (Executive vs Recruiter)
                                      ↓
                              ZohoClient.query_candidates()
                                      ↓
                              OAuth Proxy → Zoho CRM API
                                      ↓
                              Response Formatting → User
```

### Database Schema

#### Tables:
1. **teams_user_preferences** - User settings and subscription state
   - `delivery_email` - Email for weekly digest delivery
   - `max_candidates_per_digest` - Candidate limit (1-20)
   - `subscription_active` - Email subscription enabled/disabled
   - `last_digest_sent_at` - Last successful delivery timestamp
   - `next_digest_scheduled_at` - Calculated next delivery time

2. **teams_conversations** - Chat history for analytics
   - Tracks all messages and bot responses
   - Used for conversation_count analytics

3. **teams_digest_requests** - Preview/interactive digest requests
   - Stores dry-run digest previews
   - Tracks cards generated and execution time

4. **weekly_digest_deliveries** - Automated email delivery tracking
   - Tracks scheduled/processing/sent/failed states
   - Stores email_message_id for bounce tracking
   - Records execution_time_ms for performance monitoring

5. **subscription_confirmations** - Email confirmation audit trail
   - Tracks subscribe/unsubscribe/update actions
   - Stores previous and new settings for comparison
   - Records confirmation_sent_at timestamp

#### Views:
- **teams_user_activity** - User activity summary
- **teams_digest_performance** - Daily digest metrics
- **active_digest_subscriptions** - Active subscriptions with stats
- **subscriptions_due_for_delivery** - Subscriptions ready for delivery

### Background Jobs

#### WeeklyDigestScheduler
**Location**: `app/jobs/weekly_digest_scheduler.py`

**Purpose**: Automated hourly job that processes weekly digest email deliveries

**Process**:
1. Query `subscriptions_due_for_delivery` view
2. For each subscription:
   - Generate digest using TalentWellCurator
   - Send email via SMTP
   - Update `last_digest_sent_at`
   - Record delivery in `weekly_digest_deliveries`
3. Log success/failure counts

**Configuration**:
```python
SMTP_HOST = "smtp.gmail.com"  # From environment
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = "noreply@emailthewell.com"
```

**Deployment**:
- Azure Container Apps scheduled trigger (hourly)
- Or Azure Functions Timer trigger
- Or Linux cron job: `0 * * * * python app/jobs/weekly_digest_scheduler.py`

---

## Zoom Transcript Integration

### How It Works

1. **Transcript Fetching** (`app/jobs/talentwell_curator.py:447-470`):
   ```python
   from app.zoom_client import ZoomClient
   zoom_client = ZoomClient()
   transcript_text = await zoom_client.fetch_zoom_transcript_for_meeting(meeting_id)
   ```

2. **Evidence Extraction** (`app/jobs/talentwell_curator.py:1040-1100`):
   - Parses AUM/Book Size: `r'\$[\d,]+(?:\.\d+)?\s*(?:billion|B)\s*(?:AUM|aum)'`
   - Parses Production: `r'\$[\d,]+(?:\.\d+)?\s*[BMK]?\s*(?:annual production)'`
   - Extracts growth metrics: `r'grew.*?(\d+)%'`

3. **Sentiment Analysis** (`app/jobs/talentwell_curator.py:1012-1044`):
   - GPT-5-mini analyzes enthusiasm, professionalism, red flags
   - Applies 5-15% boost/penalty to bullet scores
   - Falls back to keyword-based heuristics if GPT-5 fails

### Queryable via Natural Language

**Yes** - Zoom transcript data is fully queryable:

```
User: "Show me candidates with Zoom transcripts from last week"
Bot: Queries Zoho for candidates with meeting_id or transcript_url populated

User: "What did we learn about John Smith in his interview?"
Bot: Retrieves transcript text and sentiment analysis from Zoho record
```

**Available Fields**:
- `meeting_id` - Zoom meeting ID
- `transcript_url` - Cloud recording URL
- `meeting_date` - When interview occurred
- `attendees` - Who attended (JSON array)

**Transcript Content**: Stored in Zoho CRM as meeting notes or separate transcript field (implementation detail varies)

---

## Feature Flags

### Active Features (Default: ON)
- `FEATURE_C3=true` - C³ cache with conformal prediction
- `FEATURE_VOIT=true` - VoIT orchestration for adaptive reasoning
- `PRIVACY_MODE=true` - Company anonymization & strict compensation formatting
- `FEATURE_GROWTH_EXTRACTION=true` - Growth metrics extraction from transcripts
- `FEATURE_LLM_SENTIMENT=true` - GPT-5 sentiment analysis

### Environment Variables
```bash
# VoIT Configuration
VOIT_BUDGET=5.0              # Processing budget in dollars
TARGET_QUALITY=0.9           # Target quality score (0.0-1.0)
C3_DELTA=0.01               # Risk bound for C³ (1%)

# Model Tier Selection
GPT_5_NANO_MODEL=gpt-3.5-turbo
GPT_5_MINI_MODEL=gpt-4o-mini
GPT_5_MODEL=gpt-4o

# SMTP Configuration (for email subscriptions)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-username
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=noreply@emailthewell.com
```

---

## Deployment Requirements

### 1. Database Migration
```bash
# Apply weekly subscription migration
psql $DATABASE_URL -f migrations/006_weekly_digest_subscriptions.sql
```

### 2. Environment Variables
Add SMTP credentials to Azure Container Apps:
```bash
az containerapp secret set \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --secrets \
    smtp-username=your-username \
    smtp-password=your-password
```

### 3. Scheduled Job Setup
**Option A: Azure Container Apps with Cron**
```bash
# Add hourly cron job to container startup
echo "0 * * * * python /app/app/jobs/weekly_digest_scheduler.py" >> /etc/crontab
```

**Option B: Azure Functions Timer Trigger**
```python
# function.json
{
  "bindings": [
    {
      "name": "timer",
      "type": "timerTrigger",
      "direction": "in",
      "schedule": "0 0 * * * *"  # Every hour
    }
  ]
}
```

### 4. Verification
```bash
# Test scheduler manually
python app/jobs/weekly_digest_scheduler.py

# Check logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --follow
```

---

## Future Enhancements

### Channels & Group Chat Support (Planned)

**Current Limitation**: Bot only works in 1:1 personal chats. Cannot @mention in channels or group chats.

**To Add Channel Support:**
1. Update bot manifest (`migrations/005_teams_integration_tables.sql`) to include team/channel scope
2. Modify `handle_message_activity()` in `app/api/teams/routes.py:355-430` to handle channel messages
3. Leverage existing `remove_mention_text()` helper for @mention parsing
4. Add channel-specific permission checks (public vs private channels)
5. Test @mention triggering in:
   - Team channels
   - Group chats
   - Private channels

**Implementation Files**:
- Bot manifest configuration
- `app/api/teams/routes.py:355-430` (message handler)
- `app/api/teams/adaptive_cards.py` (response cards)

**Use Cases**:
- `@TalentWell digest advisors` in #recruiting channel
- `@TalentWell analytics` in team standup
- Quick candidate queries without leaving channel context

### Additional Planned Features

- **Candidate Scoring Dashboard**: Visual analytics for candidate pipeline
- **Bulk Export**: Export digest candidates to CSV/Excel
- **Custom Filters**: Save favorite query filters for quick access
- **Notification Alerts**: Real-time notifications for high-priority candidates
- **Integration with Outlook Add-in**: Sync preferences between Teams and Outlook

---

## Troubleshooting

### Common Issues

#### 1. "0 of 0 candidates" in Digest
**Cause**: `published_to_vault=True` filter not applied
**Fix**: Verify `app/jobs/talentwell_curator.py:304` includes filter parameter

#### 2. Confirmation Email Not Sent
**Cause**: Missing SMTP credentials
**Fix**: Set `SMTP_USERNAME` and `SMTP_PASSWORD` in environment variables

#### 3. Bot Doesn't Respond in Channel
**Cause**: Bot not configured for channels (1:1 only)
**Workaround**: Use 1:1 chat or implement channel support (see Future Enhancements)

#### 4. Query Returns Wrong Data
**Cause**: Executive user sees all data, recruiter sees filtered data
**Expected**: This is correct behavior based on access control

#### 5. Scheduled Delivery Not Working
**Cause**: Background job not running
**Fix**: Verify cron job or Azure Function timer trigger is active

### Debugging Commands

```bash
# Check database preferences
psql $DATABASE_URL -c "SELECT * FROM teams_user_preferences WHERE subscription_active = TRUE;"

# View active subscriptions
psql $DATABASE_URL -c "SELECT * FROM subscriptions_due_for_delivery;"

# Check recent deliveries
psql $DATABASE_URL -c "SELECT * FROM weekly_digest_deliveries ORDER BY created_at DESC LIMIT 10;"

# Test scheduler manually
python app/jobs/weekly_digest_scheduler.py
```

---

## API Reference

### POST /api/teams/messages
Handle incoming Teams messages (commands and queries)

**Authentication**: Microsoft Teams Bot Framework
**Body**: Bot Framework Activity JSON

### POST /api/teams/invoke
Handle Adaptive Card button clicks

**Authentication**: Microsoft Teams Bot Framework
**Body**: Invoke activity with action data

### Internal Functions

#### `generate_digest_preview()`
Generate digest preview without sending email

**Parameters**:
- `user_id` (str): Teams user ID
- `user_email` (str): Teams user email
- `conversation_id` (str): Teams conversation ID
- `audience` (str): Candidate type filter
- `db` (asyncpg.Connection): Database connection
- `filters` (Dict, optional): Additional filters

**Returns**: MessageFactory with Adaptive Card

#### `save_user_preferences()`
Save user preferences and trigger confirmation email

**Parameters**:
- `user_id` (str): Teams user ID
- `user_email` (str): Teams user email
- `preferences` (Dict): Form submission data
- `db` (asyncpg.Connection): Database connection

**Returns**: Success/error message

---

## Security Considerations

### Access Control
- **Executive users**: Hardcoded list in `app/api/teams/query_engine.py:14-18`
- **Regular users**: Automatic owner filtering by `user_email`
- **Email delivery**: User can specify different email than Teams account

### Data Privacy
- **PRIVACY_MODE**: Anonymizes company names to generic descriptors
- **Compensation**: Formatted as broad ranges (`$XXK-$YYK OTE`)
- **Location**: Only in header, filtered from bullets

### Authentication
- **Bot Framework**: Validates Microsoft Teams signatures
- **OAuth Proxy**: Centralizes Zoho credentials
- **No API keys in client**: Teams users never see backend API key

---

## Performance Metrics

### Typical Response Times
- **Digest Generation**: 2-5 seconds (6 candidates, with Zoom transcripts)
- **Natural Language Query**: 1-3 seconds (GPT-5-mini classification + Zoho query)
- **Preferences Save**: <500ms (database update + email send)
- **Help Card**: <100ms (static card generation)

### Cost per Operation
- **Digest with VoIT**: $0.15 - $0.75 (depends on model tier selection)
- **Natural Language Query**: $0.03 - $0.10 (GPT-5-mini intent classification)
- **Sentiment Analysis**: $0.05 - $0.15 per candidate (GPT-5-mini)
- **Email Delivery**: $0.001 per email (SMTP)

---

## Change Log

### 2025-10-06 - Weekly Email Subscriptions
- ✅ Added email subscription fields to preferences
- ✅ Created `WeeklyDigestScheduler` background job
- ✅ Implemented confirmation emails for subscribe/unsubscribe/update
- ✅ Added `weekly_digest_deliveries` tracking table
- ✅ Created `subscriptions_due_for_delivery` database view
- ✅ Updated Adaptive Cards with subscription UI

### 2025-10-05 - Natural Language Query Engine
- ✅ Added GPT-5-mini intent classification
- ✅ Implemented tiered access control (executives vs recruiters)
- ✅ Rewrote query engine to use ZohoClient (not PostgreSQL)
- ✅ Fixed email extraction from Teams `additional_properties`

### 2025-10-05 - Privacy & AI Enhancements
- ✅ Enabled company anonymization (PRIVACY_MODE)
- ✅ Added growth metrics extraction
- ✅ Implemented GPT-5 sentiment analysis
- ✅ Added 5-15% sentiment-based boost/penalty

### 2025-10-04 - Teams Bot Launch
- ✅ Initial bot deployment
- ✅ Command system (help, digest, preferences, analytics)
- ✅ Adaptive Cards for interactive UI
- ✅ Database schema migration

---

## Support & Documentation

**Primary Documentation**: [CLAUDE.md](/home/romiteld/Development/Desktop_Apps/outlook/CLAUDE.md)
**Architecture Decisions**: [docs/decisions/](/home/romiteld/Development/Desktop_Apps/outlook/docs/decisions/)
**Migration Files**: [migrations/](/home/romiteld/Development/Desktop_Apps/outlook/migrations/)
**Issue Tracking**: [GitHub Issues](https://github.com/your-org/outlook)

For questions or support, contact the TalentWell engineering team.
