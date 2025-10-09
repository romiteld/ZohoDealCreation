# Microsoft Teams Bot Setup Guide for TalentWell Advisor Vault

## Overview
This guide provides step-by-step instructions for setting up a Microsoft Teams bot that integrates with the TalentWell Advisor Vault system. The bot enables Teams users to interact with candidate data, view weekly digests, and access analytics directly within Teams.

## Architecture Components

### 1. Azure Bot Service
- **Bot Registration**: Azure Bot resource for Teams integration
- **Messaging Endpoint**: Webhook URL for Teams messages
- **Authentication**: Azure AD app registration for secure access

### Conversational CRM Query Architecture (RAG)
- **Dedicated RAG Endpoint**: Expose a FastAPI route such as `POST /api/crm/query` that the Teams bot can call when it detects a free-form question about CRM data. This keeps natural language handling decoupled from the `/chat` webhook logic while still reusing the same application container.
- **LangGraph Orchestration**: Route each request through the existing LangGraph pipelines so the bot can determine intent (e.g., `QueryDeals`), extract entities (account names, stages, owners), and decide whether a clarification turn is required.
- **Retrieval Layer**: Convert the recognized intent/entities into structured searches. Prefer semantic lookup against the Azure PostgreSQL + `pgvector` index that mirrors Zoho CRM data; fall back to direct Zoho CRM API calls when semantic data is unavailable or stale. Return normalized deal/contact objects so downstream consumers stay consistent.
- **Generation Layer**: Provide the retrieved objects and prior conversation turns to Azure OpenAI (GPT-5) to produce conversational answers. Keep prompts inside `app/prompts/` and include safeguards (max tokens, temperature) that align with production usage.
- **State Management**: Persist Teams conversation state (keyed by Teams user ID + conversation ID) inside Azure Cache for Redis. Store both the high-level intent history and message transcript so follow-up questions automatically inherit context when invoking the RAG endpoint.
- **Telemetry**: Record each RAG invocation (intent, latency, retrieval source) via Application Insights to monitor quality and surface retraining opportunities.

### 2. API Endpoints
- **Location**: `/app/api/teams/routes.py`
- **Base URL**: `https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams`
- **Key Endpoints**:
  - `POST /chat` - Handle Teams messages
  - `GET /analytics` - Retrieve analytics data
  - `POST /card/action` - Handle Adaptive Card actions

### 3. Adaptive Cards
- **Template Location**: `/app/templates/teams/candidate_card.json`
- **Version**: 1.4 (Teams compatible)
- **Features**: Candidate display, Zoho CRM links, interactive actions

## Prerequisites

### Azure Resources Required
- Azure Subscription (existing: `TheWell-Infra-East`)
- Azure Bot Service
- Azure AD App Registration
- Azure Container Apps (existing: `well-intake-api`)

### Development Tools
```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Install Bot Framework CLI
npm install -g @microsoft/botframework-cli

# Install Teams Toolkit (VS Code extension)
code --install-extension TeamsDevApp.ms-teams-vscode-extension
```

## Step 1: Azure AD App Registration

### Create App Registration
```bash
# Login to Azure
az login

# Set subscription
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Create AD app
az ad app create \
  --display-name "TalentWell Teams Bot" \
  --sign-in-audience "AzureADMyOrg" \
  --required-resource-accesses @- <<EOF
[
  {
    "resourceAppId": "00000003-0000-0000-c000-000000000000",
    "resourceAccess": [
      {
        "id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d",
        "type": "Scope"
      }
    ]
  }
]
EOF
```

### Generate Client Secret
```bash
# Get app ID from previous step
APP_ID="YOUR_APP_ID"

# Create client secret
az ad app credential reset \
  --id $APP_ID \
  --display-name "teams-bot-secret" \
  --years 2
```

Save the generated values:
- **Application ID**: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- **Client Secret**: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- **Tenant ID**: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

## Step 2: Azure Bot Service Setup

### Create Bot Resource
```bash
# Create Bot Service
az bot create \
  --resource-group "TheWell-Infra-East" \
  --name "talentwell-teams-bot" \
  --kind "azurebot" \
  --sku "F0" \
  --appid "$APP_ID" \
  --location "eastus" \
  --endpoint "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/chat"
```

### Configure Bot Channels
```bash
# Enable Teams channel
az bot msteams create \
  --resource-group "TheWell-Infra-East" \
  --name "talentwell-teams-bot"
```

## Step 3: Configure Container App

### Update Environment Variables
```bash
# Add bot configuration to Container App
az containerapp update \
  --name "well-intake-api" \
  --resource-group "TheWell-Infra-East" \
  --set-env-vars \
    TEAMS_BOT_APP_ID="$APP_ID" \
    TEAMS_BOT_CLIENT_SECRET="secretref:teams-bot-secret" \
    TEAMS_BOT_TENANT_ID="YOUR_TENANT_ID"
```

### Add Secret to Container App
```bash
az containerapp secret set \
  --name "well-intake-api" \
  --resource-group "TheWell-Infra-East" \
  --secrets "teams-bot-secret=YOUR_CLIENT_SECRET"
```

## Step 4: Teams App Manifest

### Create Teams App Manifest (`manifest.json`)
```json
{
  "$schema": "https://developer.microsoft.com/en-us/json-schemas/teams/v1.16/MicrosoftTeams.schema.json",
  "manifestVersion": "1.16",
  "version": "1.0.0",
  "id": "YOUR_APP_ID",
  "packageName": "com.thewell.talentwell",
  "developer": {
    "name": "The Well",
    "websiteUrl": "https://thewell.com",
    "privacyUrl": "https://thewell.com/privacy",
    "termsOfUseUrl": "https://thewell.com/terms"
  },
  "name": {
    "short": "TalentWell",
    "full": "TalentWell Advisor Vault"
  },
  "description": {
    "short": "Access TalentWell candidate data in Teams",
    "full": "TalentWell Advisor Vault bot provides access to candidate digests, analytics, and Zoho CRM integration directly within Microsoft Teams."
  },
  "icons": {
    "outline": "icon-outline.png",
    "color": "icon-color.png"
  },
  "accentColor": "#0078D4",
  "bots": [
    {
      "botId": "YOUR_APP_ID",
      "scopes": ["personal", "team", "groupchat"],
      "commandLists": [
        {
          "scopes": ["personal", "team", "groupchat"],
          "commands": [
            {
              "title": "digest",
              "description": "Get candidate digest for specified period"
            },
            {
              "title": "filter",
              "description": "Filter candidates by AUM, location, or designation"
            },
            {
              "title": "analytics",
              "description": "View analytics dashboard"
            }
          ]
        }
      ],
      "supportsFiles": false,
      "isNotificationOnly": false
    }
  ],
  "permissions": ["identity", "messageTeamMembers"],
  "validDomains": [
    "well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io",
    "crm.zoho.com"
  ]
}
```

### Package Teams App
```bash
# Create app package
mkdir teams-app
cp manifest.json teams-app/
cp icon-*.png teams-app/

# Create zip package
cd teams-app
zip -r talentwell-teams.zip .
```

## Step 5: Deploy Bot Code

### Update Main Application
Add Teams router to `app/main.py`:

```python
# Import Teams routes
from app.api.teams.routes import router as teams_router

# Add to FastAPI app
app.include_router(teams_router)
```

### Deploy to Container App
```bash
# Build Docker image
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:teams .

# Push to registry
az acr login --name wellintakeacr0903
docker push wellintakeacr0903.azurecr.io/well-intake-api:teams

# Update Container App
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:teams \
  --revision-suffix "teams-v1"
```

## Step 6: Install in Teams

### Admin Center Installation
1. Go to [Teams Admin Center](https://admin.teams.microsoft.com)
2. Navigate to **Teams apps** > **Manage apps**
3. Click **Upload** and select `talentwell-teams.zip`
4. Review and approve the app
5. Set permission policies for users

### User Installation
1. In Teams, go to **Apps**
2. Search for "TalentWell"
3. Click **Add** to install personally
4. Or **Add to team** for team-wide access

## Step 7: Testing

### Test Commands
```bash
# Test webhook endpoint
curl -X POST https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "type": "message",
    "text": "digest 7",
    "from": {
      "userPrincipalName": "test@thewell.com"
    }
  }'

# Test analytics endpoint
curl -X GET "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/analytics?user_email=test@thewell.com&timeframe=30d" \
  -H "X-API-Key: YOUR_API_KEY"
```

### Bot Framework Emulator
1. Download [Bot Framework Emulator](https://github.com/Microsoft/BotFramework-Emulator/releases)
2. Configure endpoint: `https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/chat`
3. Add App ID and Password
4. Test bot responses

## Step 8: Monitoring

### Application Insights
```bash
# View bot metrics
az monitor app-insights metrics show \
  --app "well-intake-appinsights" \
  --resource-group "TheWell-Infra-East" \
  --metric "requests/count" \
  --aggregation "Count" \
  --filter "cloud/roleName eq 'teams-bot'"
```

### Container App Logs
```bash
# Stream logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --follow \
  --filter "teams"
```

## Security Considerations

### Authentication Flow
1. Teams sends message to bot endpoint
2. Bot validates Teams authentication token
3. Bot uses API key to access backend services
4. User permissions checked against Azure AD

### API Security
- All endpoints require `X-API-Key` header
- Teams bot service authenticated via Azure AD
- Rate limiting: 100 requests/minute per user
- SSL/TLS encryption for all communications

### Data Privacy
- No candidate PII stored in Teams
- All data fetched real-time from Zoho CRM
- Audit logs maintained in Application Insights
- Compliance with The Well data policies

## Troubleshooting

### Common Issues

#### Bot Not Responding
```bash
# Check bot health
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/health

# Verify bot registration
az bot show \
  --resource-group TheWell-Infra-East \
  --name talentwell-teams-bot
```

#### Authentication Errors
```bash
# Verify app registration
az ad app show --id $APP_ID

# Check secret expiration
az ad app credential list --id $APP_ID
```

#### Card Rendering Issues
- Ensure Adaptive Card version 1.4
- Validate JSON at [Adaptive Cards Designer](https://adaptivecards.io/designer/)
- Check Teams client version (minimum 1.5.00)

## Sample Messages

### Basic Commands
```
User: digest
Bot: [Shows candidate digest for last 7 days]

User: digest 30
Bot: [Shows candidate digest for last 30 days]

User: filter aum >500M
Bot: [Shows candidates with AUM > $500M]

User: analytics 7d
Bot: [Shows analytics dashboard for 7 days]
```

### Advanced Filters
```
User: filter location New York
Bot: [Shows candidates in New York]

User: filter designation CFA
Bot: [Shows candidates with CFA designation]
```

## Maintenance

### Update Bot Configuration
```bash
# Update webhook endpoint
az bot update \
  --resource-group TheWell-Infra-East \
  --name talentwell-teams-bot \
  --endpoint "NEW_ENDPOINT_URL"

# Rotate secrets
az ad app credential reset \
  --id $APP_ID \
  --display-name "teams-bot-secret-v2"
```

### Version Updates
1. Update Teams manifest version
2. Rebuild and push Docker image
3. Update Container App revision
4. Re-upload Teams app package

## Support Contacts

- **Technical Support**: DevOps Team
- **Azure Issues**: Cloud Architecture Team
- **Teams Admin**: IT Admin Team
- **API Issues**: Backend Development Team

## Appendix: Environment Variables

Required environment variables for Container App:

```bash
# Teams Bot Configuration
TEAMS_BOT_APP_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
TEAMS_BOT_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TEAMS_BOT_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# API Configuration (existing)
API_KEY=your-secure-api-key
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net
ZOHO_DEFAULT_OWNER_EMAIL=daniel.romitelli@emailthewell.com

# Azure Services (existing)
DATABASE_URL=postgresql://...
AZURE_REDIS_CONNECTION_STRING=rediss://...
AZURE_STORAGE_CONNECTION_STRING=...
```

## Next Steps

1. **User Training**: Create training materials for end users
2. **Feedback Loop**: Set up user feedback collection
3. **Feature Expansion**: Plan additional bot capabilities
4. **Integration Testing**: Comprehensive end-to-end testing
5. **Performance Optimization**: Monitor and optimize response times