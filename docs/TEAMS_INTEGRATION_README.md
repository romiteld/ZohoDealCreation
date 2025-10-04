# Microsoft Teams Bot Integration for TalentWell

## Overview

The TalentWell Teams Bot allows users to interact with the Advisor Vault system directly from Microsoft Teams. Users can generate digest previews, apply filters, manage preferences, and view analytics—all through conversational commands and interactive adaptive cards.

## Architecture

### Database Tables

Created by migration `005_teams_integration_tables.sql`:

- **teams_bot_config** - Bot configuration and Azure AD credentials
- **teams_conversations** - Conversation history for analytics
- **teams_user_preferences** - User-specific settings (audience, frequency, filters)
- **teams_digest_requests** - Track digest generation requests and results

### API Endpoints

**Webhook Endpoint**: `/api/teams/webhook`
- Handles incoming Teams activities (messages, invokes, conversation updates)
- Processes user commands and button clicks
- Returns adaptive cards with rich content

**Health Check**: `/api/teams/health`
- Status endpoint for monitoring

### Components

```
app/api/teams/
├── __init__.py                 # Package initialization
├── routes.py                   # FastAPI webhook endpoints
└── adaptive_cards.py           # Adaptive card templates
```

## Features

### 1. Conversational Commands

Users can interact with the bot using natural language:

```
help                           → Show available commands
digest [audience]              → Generate digest preview
digest steve_perry             → Generate for specific audience
preferences                    → View/edit preferences
analytics                      → View usage statistics
```

### 2. Adaptive Cards

**Welcome Card**:
- Shown when bot is added or user says "hello"
- Quick action buttons for common tasks

**Digest Preview Card**:
- Shows top 3 candidates with bullets
- Sentiment analysis indicators
- Filter options (date range, owner, max candidates)
- "Generate Full Digest" action button

**Preferences Card**:
- Default audience selection
- Digest frequency (daily/weekly/monthly)
- Notification toggles

**Error Card**:
- User-friendly error messages
- "Try Again" action button

### 3. Sentiment Analysis Integration

Each candidate card includes:
- Sentiment score (positive/neutral/negative)
- Enthusiasm score (0-100%)
- Professionalism score (0-100%)
- Red flag indicators (concerns detected)

### 4. Score-Based Ranking

Candidates are ranked using composite scoring:
- **Category Priority** (40%): Financial metrics > Licenses > Experience
- **Confidence Score** (40%): From evidence extraction
- **Source Reliability** (15%): CRM > Extraction > Inferred
- **Evidence Quality** (5%): Bonus for multiple evidence sources

## Deployment

### Prerequisites

1. **Azure Resources**:
   - Azure AD app registration
   - Azure Key Vault (for bot secrets)
   - PostgreSQL database (well-intake-db-0903)
   - Container App (well-intake-api)

2. **Environment Variables**:
   ```bash
   DATABASE_URL=postgresql://...
   TEAMS_BOT_APP_ID=secretref:TeamsBot--AppId
   TEAMS_BOT_APP_PASSWORD=secretref:TeamsBot--AppPassword
   ```

### Deployment Steps

1. **Run Migration**:
   ```bash
   cd /home/romiteld/Development/Desktop_Apps/outlook
   chmod +x scripts/deploy_teams_integration.sh
   ./scripts/deploy_teams_integration.sh
   ```

   This script will:
   - Create database tables
   - Register Azure AD app
   - Store credentials in Key Vault
   - Update Container App environment variables

2. **Register Bot in Teams**:
   - Go to [Teams Admin Center](https://admin.teams.microsoft.com/)
   - Apps > Manage apps > Upload custom app
   - Use App ID from deployment output
   - Configure messaging endpoint:
     ```
     https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/webhook
     ```

3. **Grant Permissions**:
   In Azure Portal > App Registrations > TalentWell Bot:
   - API permissions > Add permission > Microsoft Graph
   - Add **User.Read** (Delegated)
   - Add **TeamMember.Read.All** (Delegated)
   - Grant admin consent

4. **Test the Bot**:
   ```
   # In Teams, add the bot
   # Send test commands:
   help
   digest global
   preferences
   analytics
   ```

## Configuration

### Database Configuration

The `teams_bot_config` table stores bot settings:

```sql
SELECT * FROM teams_bot_config;
```

Update configuration:
```sql
UPDATE teams_bot_config
SET service_url = 'https://smba.trafficmanager.net/amer/',
    enabled = TRUE
WHERE app_id = 'talentwell-bot-prod';
```

### User Preferences

Users can set preferences via the bot or directly in database:

```sql
-- View user preferences
SELECT * FROM teams_user_preferences WHERE user_email = 'daniel.romitelli@emailthewell.com';

-- Update preferences
UPDATE teams_user_preferences
SET default_audience = 'steve_perry',
    digest_frequency = 'weekly',
    notification_enabled = TRUE
WHERE user_email = 'daniel.romitelli@emailthewell.com';
```

### Filter Preferences (JSONB)

Users can save complex filters:

```json
{
  "owner": "daniel.romitelli@emailthewell.com",
  "from_date": "2025-09-01",
  "to_date": "2025-10-04",
  "max_candidates": 10,
  "ignore_cooldown": false
}
```

## Analytics

### User Activity View

```sql
SELECT * FROM teams_user_activity
ORDER BY conversation_count DESC
LIMIT 10;
```

Shows:
- Total conversations per user
- Total digest requests
- Last activity timestamps

### Digest Performance View

```sql
SELECT * FROM teams_digest_performance
ORDER BY request_date DESC
LIMIT 30;
```

Shows daily metrics:
- Total requests
- Success rate
- Average execution time
- Max execution time

### Request History

```sql
-- View recent digest requests
SELECT
    request_id,
    user_email,
    audience,
    cards_generated,
    total_candidates,
    execution_time_ms,
    status,
    created_at
FROM teams_digest_requests
ORDER BY created_at DESC
LIMIT 20;

-- Performance analysis
SELECT
    audience,
    COUNT(*) as requests,
    AVG(cards_generated) as avg_cards,
    AVG(execution_time_ms) as avg_time_ms
FROM teams_digest_requests
WHERE status = 'completed'
GROUP BY audience
ORDER BY requests DESC;
```

## Monitoring

### Container App Logs

```bash
# Follow live logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --follow

# Search for Teams-specific logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --tail 100 | grep "Teams"
```

### Health Checks

```bash
# Teams bot health
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/health

# Main API health
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
```

### Database Monitoring

```sql
-- Check active conversations
SELECT COUNT(*) as active_today
FROM teams_conversations
WHERE DATE(created_at) = CURRENT_DATE;

-- Check pending digest requests
SELECT COUNT(*) as pending
FROM teams_digest_requests
WHERE status = 'pending';

-- Check failed requests (last 24 hours)
SELECT
    request_id,
    user_email,
    error_message,
    created_at
FROM teams_digest_requests
WHERE status = 'failed'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

## Troubleshooting

### Common Issues

**1. Bot doesn't respond**
```bash
# Check Container App is running
az containerapp show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --query "{status:properties.runningStatus, replicas:properties.runningStatus}"

# Check environment variables
az containerapp show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --query "properties.template.containers[0].env"
```

**2. Authentication errors**
```bash
# Verify Key Vault secrets
az keyvault secret show \
  --vault-name well-intake-kv \
  --name TeamsBot--AppId

# Check Azure AD app registration
az ad app show --id <APP_ID>
```

**3. Database connection issues**
```sql
-- Check bot configuration
SELECT * FROM teams_bot_config WHERE enabled = TRUE;

-- Test database connectivity
SELECT version();
```

**4. Digest generation fails**
```bash
# Check TalentWell curator logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --tail 100 | grep "TalentWell\|VoIT\|digest"

# Check for database query errors
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --tail 100 | grep "ERROR"
```

## Security

### API Key Protection

- Teams webhook does NOT require API key (uses Azure AD authentication)
- All other endpoints require `X-API-Key` header
- Rate limiting: 100 requests/minute per IP

### Secret Management

- Bot credentials stored in Azure Key Vault
- Container App uses Managed Identity to access secrets
- Database connection strings use Azure AD authentication

### Data Privacy

- Candidate data anonymized per privacy settings
- AUM values rounded to ranges
- Internal recruiter notes filtered out
- Sentiment analysis stored separately

## Future Enhancements

### Planned Features

1. **Proactive Notifications**:
   - Scheduled digest delivery
   - Alert for high-priority candidates
   - Daily/weekly summary notifications

2. **Advanced Filters**:
   - Sentiment-based filtering
   - AUM/production thresholds
   - License/designation requirements
   - Geographic preferences

3. **AI-Powered Recommendations**:
   - Suggest optimal audiences
   - Predict candidate fit scores
   - Recommend follow-up actions

4. **Multi-Audience Support**:
   - Compare digests across audiences
   - Cross-reference candidates
   - Aggregate analytics

## Support

### Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Microsoft Teams Bot Framework](https://docs.microsoft.com/en-us/microsoftteams/platform/)
- [Adaptive Cards Schema](https://adaptivecards.io/explorer/)
- [Azure Container Apps](https://docs.microsoft.com/en-us/azure/container-apps/)

### Contact

For issues or questions:
1. Check logs first (see Monitoring section)
2. Review analytics for patterns
3. Contact: daniel.romitelli@emailthewell.com
