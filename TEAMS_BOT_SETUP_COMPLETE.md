# ✅ Teams Bot Setup Complete

**Date**: 2025-10-04
**Status**: Automated setup complete - Ready for Teams Admin upload

---

## 🎉 Completed Steps

### 1. Database Migration ✅
- **Tables Created**: 4 tables + 2 analytics views
  - `teams_bot_config`
  - `teams_conversations`
  - `teams_digest_requests`
  - `teams_user_preferences`
  - `teams_user_activity` (view)
  - `teams_digest_performance` (view)

**Verification**:
```bash
az postgres flexible-server execute \
  --name well-intake-db-0903 \
  --admin-user adminuser \
  --admin-password 'W3llDB2025Pass' \
  --database-name wellintake \
  --querytext "SELECT * FROM teams_bot_config"
```

---

### 2. Azure AD App Registration ✅
- **App Name**: TalentWell Assistant
- **App ID**: `34d9338f-ba4e-4a68-9a22-b01892afba83`
- **Tenant ID**: `29ee1479-b5f7-48c5-b665-7de9a8a9033e`
- **Permissions**: User.Read, TeamMember.Read.All

**Status**: ✅ Client secret created and stored in Key Vault

---

### 3. Azure Key Vault Storage ✅
- **Secret Name**: `TalentWellBotSecret`
- **Vault**: `well-intake-kv`
- **Secret ID**: `https://well-intake-kv.vault.azure.net/secrets/TalentWellBotSecret/ae6272595efb4ecda659f6e20dd1a268`

**Verify**:
```bash
az keyvault secret show \
  --vault-name well-intake-kv \
  --name TalentWellBotSecret \
  --query "{name:name, enabled:attributes.enabled}"
```

---

### 4. Container App Configuration ✅
- **Environment Variables Set**:
  - `TEAMS_BOT_APP_ID`: `34d9338f-ba4e-4a68-9a22-b01892afba83`
  - `TEAMS_BOT_TENANT_ID`: `29ee1479-b5f7-48c5-b665-7de9a8a9033e`
- **Latest Revision**: `well-intake-api--0000127`

**Webhook Endpoint**: `https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/webhook`

---

### 5. Teams App Package Created ✅
- **File**: `talentwell-teams-app.zip` (11 KB)
- **Location**: `/home/romiteld/Development/Desktop_Apps/outlook/talentwell-teams-app.zip`
- **Contents**:
  - `manifest.json` (Teams app manifest v1.16)
  - `outline-icon.png` (32x32 icon)
  - `color-icon.png` (128x128 icon)

---

## 📋 Next Steps (Manual - Teams Admin Required)

### Step 1: Upload to Teams Admin Center (5 minutes)
1. Navigate to: https://admin.teams.microsoft.com
2. Click: **Teams apps** → **Manage apps**
3. Click: **Upload new app**
4. Select: `talentwell-teams-app.zip`
5. Click: **Publish**

### Step 2: Grant Admin Consent for Permissions (2 minutes)
1. Navigate to: https://portal.azure.com
2. Go to: **Azure Active Directory** → **App registrations**
3. Find: **TalentWell Assistant** (`34d9338f-ba4e-4a68-9a22-b01892afba83`)
4. Click: **API permissions**
5. Click: **Grant admin consent for [Your Organization]**

### Step 3: Test in Teams (3 minutes)
1. Open Microsoft Teams
2. Click **Apps** → Search "TalentWell"
3. Click **Add**
4. Send test message: `help`

**Expected Response**: Welcome card with available commands

---

## 🧪 Testing Commands

Once the bot is added to Teams, test these commands:

```
help
→ Shows welcome card with command list

digest global
→ Preview of top candidates (all advisors)

digest steve_perry
→ Preview for specific advisor

preferences
→ User settings card

analytics
→ Usage statistics
```

---

## 🔍 Verification Queries

### Check Bot Configuration
```bash
az postgres flexible-server execute \
  --name well-intake-db-0903 \
  --admin-user adminuser \
  --admin-password 'W3llDB2025Pass' \
  --database-name wellintake \
  --querytext "SELECT * FROM teams_bot_config"
```

### Verify Webhook Endpoint
```bash
curl -X GET "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health" \
  | python3 -m json.tool | grep -E "(status|healthy)"
```

### Check Container App Logs
```bash
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --tail 50 \
  | grep -i teams
```

---

## 📊 Monitoring

### View Bot Analytics After Testing
```bash
# Conversation count
az postgres flexible-server execute \
  --name well-intake-db-0903 \
  --admin-user adminuser \
  --admin-password 'W3llDB2025Pass' \
  --database-name wellintake \
  --querytext "SELECT COUNT(*) FROM teams_conversations"

# User activity
az postgres flexible-server execute \
  --name well-intake-db-0903 \
  --admin-user adminuser \
  --admin-password 'W3llDB2025Pass' \
  --database-name wellintake \
  --querytext "SELECT * FROM teams_user_activity"

# Digest performance
az postgres flexible-server execute \
  --name well-intake-db-0903 \
  --admin-user adminuser \
  --admin-password 'W3llDB2025Pass' \
  --database-name wellintake \
  --querytext "SELECT * FROM teams_digest_performance ORDER BY request_date DESC LIMIT 7"
```

---

## 🔧 Troubleshooting

### Bot Not Responding
```bash
# 1. Check health endpoint
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health

# 2. Check Container App logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --tail 100

# 3. Verify environment variables
az containerapp show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --query "properties.template.containers[0].env[?contains(name, 'TEAMS')]"
```

### Permission Denied Errors
- Ensure admin consent was granted (Step 2 above)
- Verify app ID matches in manifest and Azure AD
- Check tenant ID is correct in environment variables

### Webhook 500 Errors
```bash
# Check if bot secret is accessible from Container App
az containerapp exec \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --command "echo TEAMS_BOT_APP_ID: $TEAMS_BOT_APP_ID"
```

---

## 📁 Important Files

| File | Location | Purpose |
|------|----------|---------|
| **Teams Package** | `talentwell-teams-app.zip` | Upload to Teams Admin Center |
| **Manifest** | `teams-app-manifest.json` | Teams app configuration |
| **Migration SQL** | `migrations/005_teams_integration_tables.sql` | Database schema |
| **Bot Routes** | `app/api/teams/routes.py` | Webhook handlers |
| **Adaptive Cards** | `app/api/teams/adaptive_cards.py` | UI card templates |
| **Setup Guide** | `docs/TEAMS_BOT_SETUP.md` | Detailed documentation |

---

## 🔑 Credentials Summary

**⚠️ SENSITIVE - Keep Secure**

| Resource | Value |
|----------|-------|
| **App ID** | `34d9338f-ba4e-4a68-9a22-b01892afba83` |
| **Tenant ID** | `29ee1479-b5f7-48c5-b665-7de9a8a9033e` |
| **Client Secret** | Stored in Key Vault: `TalentWellBotSecret` |
| **Webhook URL** | `https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/webhook` |

---

## ✅ Pre-Launch Checklist

- [x] Database tables created and configured
- [x] Azure AD app registered with permissions
- [x] Client secret stored securely in Key Vault
- [x] Container App environment variables set
- [x] Teams app package created
- [x] Webhook endpoint verified as accessible
- [ ] **TODO**: Upload app to Teams Admin Center
- [ ] **TODO**: Grant admin consent for API permissions
- [ ] **TODO**: Test bot in Teams with `help` command
- [ ] **TODO**: Verify digest generation works
- [ ] **TODO**: Monitor logs for any errors

---

## 🎯 Success Criteria

The bot is fully functional when:
1. ✅ Health endpoint returns `"status": "healthy"`
2. ⏳ Bot responds to `help` command in Teams
3. ⏳ Digest commands generate candidate cards
4. ⏳ Adaptive card buttons trigger actions
5. ⏳ Database records conversations and requests

---

## 📚 Additional Resources

- [Teams App Manifest Schema](https://docs.microsoft.com/en-us/microsoftteams/platform/resources/schema/manifest-schema)
- [Bot Framework Documentation](https://docs.microsoft.com/en-us/azure/bot-service/)
- [Adaptive Cards Documentation](https://adaptivecards.io/designer/)
- [TalentWell Curator Details](./TALENTWELL_AI_IMPLEMENTATION.md)

---

**Setup completed by**: Claude Code (AI Assistant)
**Next action**: Upload `talentwell-teams-app.zip` to Teams Admin Center
**Support**: Check `docs/TEAMS_BOT_SETUP.md` for detailed troubleshooting
