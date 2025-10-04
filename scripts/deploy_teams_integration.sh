#!/bin/bash

# Teams Integration Deployment Script
# This script sets up Microsoft Teams bot integration for TalentWell

set -e  # Exit on error

echo "==================================="
echo "Teams Integration Deployment"
echo "==================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="TheWell-Infra-East"
POSTGRES_SERVER="well-intake-db-0903"
DATABASE_NAME="well_intake"
KEY_VAULT_NAME="well-intake-kv"
LOCATION="eastus"

echo -e "${YELLOW}Step 1: Running database migration${NC}"
echo "-----------------------------------"

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}ERROR: DATABASE_URL environment variable not set${NC}"
    echo "Please set DATABASE_URL in .env.local"
    exit 1
fi

# Run migration using Python
python3 << 'PYTHON_EOF'
import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv('.env.local')

async def run_migration():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not found")
        return False

    try:
        conn = await asyncpg.connect(database_url)

        # Read migration file
        with open('migrations/005_teams_integration_tables.sql', 'r') as f:
            migration_sql = f.read()

        # Execute migration
        await conn.execute(migration_sql)
        print("✅ Migration executed successfully")

        # Verify tables
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename LIKE 'teams_%'
            ORDER BY tablename
        """)

        print(f"\n✅ Created {len(tables)} Teams tables:")
        for table in tables:
            print(f"   - {table['tablename']}")

        await conn.close()
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

asyncio.run(run_migration())
PYTHON_EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}Migration failed${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 2: Creating Azure AD App Registration${NC}"
echo "-----------------------------------"

# Create Azure AD app for Teams bot
APP_NAME="talentwell-teams-bot"

# Check if app already exists
EXISTING_APP=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv 2>/dev/null)

if [ -z "$EXISTING_APP" ]; then
    echo "Creating new app registration..."

    APP_ID=$(az ad app create \
        --display-name "$APP_NAME" \
        --sign-in-audience "AzureADMyOrg" \
        --query "appId" -o tsv)

    echo "✅ App created with ID: $APP_ID"

    # Create service principal
    az ad sp create --id "$APP_ID" --query "id" -o tsv
    echo "✅ Service principal created"

    # Create client secret
    SECRET_NAME="teams-bot-secret"
    CLIENT_SECRET=$(az ad app credential reset \
        --id "$APP_ID" \
        --append \
        --display-name "$SECRET_NAME" \
        --query "password" -o tsv)

    echo "✅ Client secret created"

else
    APP_ID="$EXISTING_APP"
    echo "✅ Using existing app: $APP_ID"
    echo "⚠️  You'll need to create a new client secret manually if needed"
fi

echo ""
echo -e "${YELLOW}Step 3: Storing credentials in Azure Key Vault${NC}"
echo "-----------------------------------"

# Store bot credentials in Key Vault
if [ ! -z "$CLIENT_SECRET" ]; then
    az keyvault secret set \
        --vault-name "$KEY_VAULT_NAME" \
        --name "TeamsBot--AppId" \
        --value "$APP_ID" \
        --description "Teams bot app ID" \
        --output none

    az keyvault secret set \
        --vault-name "$KEY_VAULT_NAME" \
        --name "TeamsBot--AppPassword" \
        --value "$CLIENT_SECRET" \
        --description "Teams bot app password" \
        --output none

    echo "✅ Credentials stored in Key Vault"
else
    echo "⚠️  Skipping secret storage (no new secret created)"
fi

echo ""
echo -e "${YELLOW}Step 4: Updating database with bot configuration${NC}"
echo "-----------------------------------"

# Update teams_bot_config table
python3 << PYTHON_EOF
import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv('.env.local')

async def update_bot_config():
    database_url = os.getenv('DATABASE_URL')
    conn = await asyncpg.connect(database_url)

    await conn.execute("""
        UPDATE teams_bot_config
        SET app_id = \$1,
            app_password_key_vault_name = \$2,
            tenant_id = \$3,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, "$APP_ID", "TeamsBot--AppPassword", "$TENANT_ID")

    print("✅ Bot configuration updated in database")

    await conn.close()

asyncio.run(update_bot_config())
PYTHON_EOF

echo ""
echo -e "${YELLOW}Step 5: Updating Container App environment variables${NC}"
echo "-----------------------------------"

# Add Teams bot configuration to Container App
az containerapp update \
    --name well-intake-api \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars \
        "TEAMS_BOT_APP_ID=secretref:TeamsBot--AppId" \
        "TEAMS_BOT_APP_PASSWORD=secretref:TeamsBot--AppPassword" \
    --output none

echo "✅ Container App updated with Teams bot configuration"

echo ""
echo -e "${GREEN}==================================="
echo "Teams Integration Setup Complete!"
echo "===================================${NC}"
echo ""
echo "Next steps:"
echo "1. Register the bot in Microsoft Teams Admin Center"
echo "   - App ID: $APP_ID"
echo "   - Messaging endpoint: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/webhook"
echo ""
echo "2. Grant permissions in Azure AD:"
echo "   - Microsoft Graph: User.Read (delegated)"
echo "   - Microsoft Graph: TeamMember.Read.All (delegated)"
echo ""
echo "3. Test the bot:"
echo "   - Add bot to Teams"
echo "   - Send 'help' command"
echo "   - Try 'digest global' to generate preview"
echo ""
echo "4. Monitor logs:"
echo "   az containerapp logs show --name well-intake-api --resource-group $RESOURCE_GROUP --follow"
echo ""
