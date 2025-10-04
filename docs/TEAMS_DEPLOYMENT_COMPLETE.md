# Teams Integration Deployment Summary

**Date**: 2025-10-04
**Status**: Infrastructure Ready - Code Deployment Pending

---

## ✅ Completed Tasks

### 1. Database Schema
- **Migration File**: `migrations/005_teams_integration_tables.sql`
- **Tables Created** (will execute on first deployment):
  - `teams_bot_config` - Bot configuration and Azure AD credentials
  - `teams_conversations` - Conversation history tracking
  - `teams_user_preferences` - User settings (audience, frequency, filters)
  - `teams_digest_requests` - Digest generation tracking with performance metrics
- **Analytics Views**:
  - `teams_user_activity` - User engagement summary
  - `teams_digest_performance` - Daily performance metrics

### 2. Azure AD App Registration
- **App ID**: `e85b7995-d86f-4f12-8079-6c5fb59d7a16`
- **Display Name**: talentwell-teams-bot
- **Service Principal**: Created
- **Client Secret**: Generated and stored in Key Vault

### 3. Azure Key Vault Secrets
- **Secret Name**: `TeamsBot--AppId`
  - **Value**: e85b7995-d86f-4f12-8079-6c5fb59d7a16
- **Secret Name**: `TeamsBot--AppPassword`
  - **Value**: J-C8Q~nJkUj8qMunQ8AeHc3SkK_5XahVMksvAaza (expires in 2 years)

### 4. Container App Configuration
- **Environment Variables**:
  - `TEAMS_BOT_APP_ID` = secretref:teams-bot-app-id
  - `TEAMS_BOT_APP_PASSWORD` = secretref:teams-bot-app-password
- **System Identity**: Granted Key Vault access (Get, List)
- **Current Revision**: well-intake-api--0000126
- **Status**: Running (2 replicas)

### 5. API Implementation
**Created Files**:
- `app/api/teams/__init__.py` - Package initialization
- `app/api/teams/routes.py` - Webhook endpoints and business logic
  - POST `/api/teams/webhook` - Bot Framework webhook
  - GET `/api/teams/health` - Health check
  - GET `/api/teams/analytics` - Analytics API
- `app/api/teams/adaptive_cards.py` - Card templates
  - Welcome card
  - Help card
  - Digest preview card (with sentiment analysis)
  - Error card
  - Preferences card

**Integration**:
- Routes imported in `app/main.py:51`
- Router included in `app/main.py:3243`

### 6. Configuration Files
**VoIT Configuration**:
- `app/config/voit_config.py` - Shared VoIT configuration
- `app/config/__init__.py` - Module exports

**Deployment**:
- `scripts/deploy_teams_integration.sh` - Automated deployment script
- `run_teams_migration.py` - Migration runner

**Documentation**:
- `docs/TEAMS_INTEGRATION_README.md` - Comprehensive guide
- `docs/TEAMS_DEPLOYMENT_COMPLETE.md` - This file

---

## 📋 Next Steps (Manual Execution Required)

### Step 1: Deploy Code to Container App
Since the Outlook add-in is currently working, deployment must be done carefully:

```bash
# 1. Build Docker image with new Teams code
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:teams-integration .

# 2. Push to Azure Container Registry
az acr login --name wellintakeacr0903
docker push wellintakeacr0903.azurecr.io/well-intake-api:teams-integration

# 3. Update Container App with new image
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:teams-integration \
  --revision-suffix "teams-$(date +%Y%m%d-%H%M%S)"

# 4. Verify deployment
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/health
```

### Step 2: Run Database Migration
The migration SQL file will need to be executed once:

```bash
# Option A: Using psql
PGPASSWORD='W3llDB2025Pass' psql \
  -h well-intake-db-0903.postgres.database.azure.com \
  -U adminuser \
  -d wellintake \
  -f migrations/005_teams_integration_tables.sql

# Option B: Using Python migration runner
python run_teams_migration.py

# Option C: Add to Container App startup script
# Edit scripts/startup.sh to run migration on first boot
```

### Step 3: Register Bot in Microsoft Teams Admin Center

1. **Navigate to**: https://admin.teams.microsoft.com/
2. **Apps** > **Manage apps** > **Upload custom app**
3. **Configure**:
   - **App ID**: e85b7995-d86f-4f12-8079-6c5fb59d7a16
   - **Messaging Endpoint**: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/webhook
   - **Display Name**: TalentWell Assistant
   - **Description**: AI-powered candidate digest generator for financial advisors

### Step 4: Grant Azure AD Permissions

1. **Navigate to**: Azure Portal > Azure Active Directory > App Registrations
2. **Find**: talentwell-teams-bot (e85b7995-d86f-4f12-8079-6c5fb59d7a16)
3. **API Permissions** > **Add Permission** > **Microsoft Graph**:
   - `User.Read` (Delegated)
   - `TeamMember.Read.All` (Delegated)
4. **Grant admin consent** for these permissions

### Step 5: Test the Integration

```bash
# 1. Verify endpoints
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/health

# 2. Check database tables
# (via PostgreSQL MCP or psql)
SELECT tablename FROM pg_tables
WHERE schemaname = 'public' AND tablename LIKE 'teams_%';

# 3. In Microsoft Teams:
# - Add the bot
# - Send: "help"
# - Send: "digest global"
# - Send: "preferences"
# - Send: "analytics"
```

---

## 🔒 Security Considerations

- ✅ **No API Key Required** for `/api/teams/webhook` (uses Azure AD authentication)
- ✅ **Secrets in Key Vault** (not in code or environment files)
- ✅ **System-Assigned Managed Identity** for Key Vault access
- ✅ **Database Connection** uses SSL mode (sslmode=require)
- ⚠️ **Client Secret Expiration**: 2 years from creation (2025-10-04)

---

## 📊 Architecture Overview

```
┌─────────────────┐
│ Microsoft Teams │
│     Client      │
└────────┬────────┘
         │ HTTPS POST
         ▼
┌─────────────────────────────────────────────┐
│  Azure Container App (well-intake-api)      │
│  ┌────────────────────────────────────────┐ │
│  │ /api/teams/webhook                     │ │
│  │  - handle_message_activity()           │ │
│  │  - handle_invoke_activity()            │ │
│  │  - handle_conversation_update()        │ │
│  └────────────┬───────────────────────────┘ │
│               │                              │
│               ▼                              │
│  ┌────────────────────────────────────────┐ │
│  │ TalentWellCurator                      │ │
│  │  - run_weekly_digest()                 │ │
│  │  - Score-based bullet ranking          │ │
│  │  - Sentiment analysis                  │ │
│  └────────────┬───────────────────────────┘ │
└───────────────┼──────────────────────────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌─────────┐ ┌──────────┐ ┌────────┐
│PostgreSQL│ │Azure     │ │Zoho    │
│  Teams  │ │Key Vault │ │CRM     │
│  Tables │ │          │ │        │
└─────────┘ └──────────┘ └────────┘
```

---

## 🎯 Expected User Experience

1. **User adds bot to Teams**
   - Receives welcome card with quick action buttons

2. **User types "digest global"**
   - Bot generates preview with top 3 candidates
   - Shows bullets with sentiment scores
   - Offers "Generate Full Digest" button

3. **User clicks filter button**
   - Shows date range, audience, and owner filters
   - Regenerates preview with filtered results

4. **User types "preferences"**
   - Shows current settings
   - Allows updating default audience, frequency, notifications

5. **User types "analytics"**
   - Shows total conversations, digest requests
   - Lists recent digest history

---

## 📝 Notes

- **Outlook Add-in**: Not affected by Teams integration (separate endpoints)
- **Database Migration**: Required before first use of Teams features
- **Bot Registration**: Must be completed in Teams Admin Center
- **Permissions**: Require admin consent for production use

---

## 🔗 Resources

- **Teams Bot Framework**: https://docs.microsoft.com/en-us/microsoftteams/platform/
- **Adaptive Cards**: https://adaptivecards.io/explorer/
- **Container Apps**: https://docs.microsoft.com/en-us/azure/container-apps/
- **Key Vault**: https://docs.microsoft.com/en-us/azure/key-vault/

---

## 🚨 Rollback Plan

If Teams integration causes issues:

```bash
# Revert to previous revision
az containerapp revision list \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --query "[0:2].{name:name, active:properties.active}" -o table

az containerapp revision activate \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --revision <PREVIOUS_REVISION_NAME>
```

---

**End of Deployment Summary**
