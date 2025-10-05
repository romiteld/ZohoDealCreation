#!/bin/bash

# Setup GitHub Secrets for Manifest Cache-Bust Workflow
# Usage: ./scripts/setup-github-secrets.sh [GITHUB_REPO]

set -e

# Configuration
GITHUB_REPO="${1:-romiteld/outlook}"
RESOURCE_GROUP="TheWell-Infra-East"
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
CONTAINER_REGISTRY="wellintakeregistry"

echo "🚀 Setting up GitHub secrets for Well Intake API deployment workflow"
echo "📦 Repository: $GITHUB_REPO"
echo "🔧 Resource Group: $RESOURCE_GROUP"
echo "📝 Subscription: $SUBSCRIPTION_ID"
echo

# Check prerequisites
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI not found. Please install: https://cli.github.com/"
    exit 1
fi

# Verify Azure login
if ! az account show &> /dev/null; then
    echo "❌ Not logged into Azure. Please run: az login"
    exit 1
fi

# Verify GitHub authentication
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub. Please run: gh auth login"
    exit 1
fi

echo "✅ Prerequisites checked"
echo

# Create service principal
echo "🔐 Creating Azure service principal..."
SP_NAME="github-well-intake-deploy-$(date +%s)"
SP_SCOPE="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"

SP_OUTPUT=$(az ad sp create-for-rbac \
    --name "$SP_NAME" \
    --role contributor \
    --scopes "$SP_SCOPE" \
    --query '{clientId:appId, clientSecret:password, tenantId:tenant}' \
    --output json)

CLIENT_ID=$(echo "$SP_OUTPUT" | jq -r '.clientId')
CLIENT_SECRET=$(echo "$SP_OUTPUT" | jq -r '.clientSecret')
TENANT_ID=$(echo "$SP_OUTPUT" | jq -r '.tenantId')

echo "✅ Service principal created: $SP_NAME"
echo "📋 Client ID: $CLIENT_ID"
echo "🏢 Tenant ID: $TENANT_ID"
echo

# Grant Container Registry access
echo "🐳 Granting ACR access..."
ACR_SCOPE="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.ContainerRegistry/registries/$CONTAINER_REGISTRY"

az role assignment create \
    --assignee "$CLIENT_ID" \
    --role AcrPush \
    --scope "$ACR_SCOPE" \
    --query "id" \
    --output tsv > /dev/null

echo "✅ ACR push permissions granted"
echo

# Get API key from environment
if [[ -f ".env.local" ]]; then
    API_KEY=$(grep "^API_KEY=" .env.local | cut -d'=' -f2)
    if [[ -z "$API_KEY" ]]; then
        echo "⚠️ API_KEY not found in .env.local"
        read -p "Enter API key for cache management: " -s API_KEY
        echo
    fi
else
    echo "⚠️ .env.local not found"
    read -p "Enter API key for cache management: " -s API_KEY
    echo
fi

if [[ -z "$API_KEY" ]]; then
    echo "❌ API key is required"
    exit 1
fi

echo "✅ API key obtained"
echo

# Set GitHub secrets
echo "🔑 Setting GitHub repository secrets..."

gh secret set AZURE_CLIENT_ID --body "$CLIENT_ID" --repo "$GITHUB_REPO"
gh secret set AZURE_TENANT_ID --body "$TENANT_ID" --repo "$GITHUB_REPO"  
gh secret set AZURE_SUBSCRIPTION_ID --body "$SUBSCRIPTION_ID" --repo "$GITHUB_REPO"
gh secret set API_KEY --body "$API_KEY" --repo "$GITHUB_REPO"

echo "✅ GitHub secrets configured"
echo

# Verify secrets
echo "🔍 Verifying secrets..."
SECRETS_LIST=$(gh secret list --repo "$GITHUB_REPO" --json name --jq '.[].name')

for secret in "AZURE_CLIENT_ID" "AZURE_TENANT_ID" "AZURE_SUBSCRIPTION_ID" "API_KEY"; do
    if echo "$SECRETS_LIST" | grep -q "$secret"; then
        echo "  ✅ $secret"
    else
        echo "  ❌ $secret - NOT FOUND"
    fi
done

echo
echo "🎉 Setup complete!"
echo
echo "📋 Summary:"
echo "  Service Principal: $SP_NAME"
echo "  Client ID: $CLIENT_ID"
echo "  Repository: $GITHUB_REPO"
echo "  Secrets: 4 configured"
echo
echo "🔧 Next steps:"
echo "  1. Test the workflow by making a change to addin/manifest.xml"
echo "  2. Push changes to trigger the workflow"
echo "  3. Monitor workflow progress in GitHub Actions"
echo
echo "📚 Documentation:"
echo "  Workflow: .github/workflows/manifest-cache-bust.yml"
echo "  README: .github/workflows/README.md"
echo
echo "⚠️ Security note:"
echo "  Save these credentials securely. The service principal has contributor access to $RESOURCE_GROUP"
echo "  Client Secret: $CLIENT_SECRET"
echo

# Save credentials to secure file
CREDS_FILE="azure-credentials-$(date +%Y%m%d).json"
cat > "$CREDS_FILE" << EOF
{
  "servicePrincipalName": "$SP_NAME",
  "clientId": "$CLIENT_ID",
  "clientSecret": "$CLIENT_SECRET",
  "tenantId": "$TENANT_ID",
  "subscriptionId": "$SUBSCRIPTION_ID",
  "resourceGroup": "$RESOURCE_GROUP",
  "containerRegistry": "$CONTAINER_REGISTRY",
  "createdAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "💾 Credentials saved to: $CREDS_FILE"
echo "🔒 Keep this file secure and do not commit to version control"