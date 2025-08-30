# Microsoft Azure AD B2C Authentication Setup

This guide will help you set up Microsoft Azure AD B2C authentication for the Well Voice UI.

## Prerequisites

- Microsoft Azure subscription with AI Cloud Partner Program credits ($2,400-$4,000/year)
- Admin access to Azure portal
- Domain name for your application (e.g., `well-voice-ui.azurewebsites.net`)

## Step 1: Create Azure AD B2C Tenant

1. **Navigate to Azure Portal**: Go to [portal.azure.com](https://portal.azure.com)
2. **Create B2C Tenant**: 
   - Search for "Azure AD B2C" in the search bar
   - Click "Create a B2C tenant"
   - Choose "Create a new Azure AD B2C Tenant"
   - Fill in:
     - **Organization name**: `The Well Voice UI`
     - **Initial domain name**: `thewell` (results in `thewell.onmicrosoft.com`)
     - **Country/Region**: United States
   - Click "Review + create"

## Step 2: Register Web Application

1. **Navigate to B2C tenant**: Switch to your newly created B2C tenant
2. **Register application**:
   - Go to "App registrations" > "New registration"
   - **Name**: `Well Voice UI`
   - **Supported account types**: `Accounts in any identity provider or organizational directory`
   - **Redirect URI**: 
     - Type: `Web`
     - URL: `https://your-domain.com` (replace with your actual domain)
   - Click "Register"

3. **Configure application**:
   - Note the **Application (client) ID** - you'll need this
   - Go to "Authentication" > "Web" > "Redirect URIs"
   - Add: `http://localhost:3000` (for development)
   - Add: `https://well-voice-ui.azurewebsites.net` (for production)
   - Check "Access tokens" and "ID tokens"
   - Click "Save"

## Step 3: Create User Flow (Policy)

1. **Create sign-up/sign-in policy**:
   - Go to "User flows" > "New user flow"
   - Select "Sign up and sign in" > "Recommended"
   - **Name**: `signupsignin1`
   - **Identity providers**: Check "Email signup"
   - **User attributes and claims**:
     - Collect: Email Address, Display Name, Given Name, Surname
     - Return: Email Addresses, Display Name, Given Name, Surname, User's Object ID
   - Click "Create"

## Step 4: Update Configuration Files

### Update `voice-ui/.env.local`:

```bash
# Azure AD B2C Configuration
AZURE_CLIENT_ID=your-application-client-id-here
AZURE_TENANT_NAME=thewell
AZURE_POLICY_NAME=B2C_1_signupsignin1
AZURE_REDIRECT_URI=https://your-domain.com
AZURE_AUTHORITY=https://thewell.b2clogin.com

# Existing configurations...
AZURE_SPEECH_KEY=892f34c92b764c3dbe8e08d204aa85ad
AZURE_SPEECH_REGION=eastus
API_ENDPOINT=https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io
API_KEY=e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384
```

### Update `voice-ui/public/auth-config.js`:

Replace the placeholder values in the `getConfigValue` function:

```javascript
const config = {
  'AZURE_CLIENT_ID': 'your-actual-client-id-here',
  'AZURE_TENANT_NAME': 'thewell',  // Or your tenant name
  'AZURE_POLICY_NAME': 'B2C_1_signupsignin1',
  'AZURE_REDIRECT_URI': window.location.origin
};
```

## Step 5: Test the Authentication Flow

1. **Local Testing**:
   ```bash
   cd voice-ui
   npm start
   # Open http://localhost:3000
   # Click "Sign in with Microsoft"
   ```

2. **Production Deployment**:
   - Deploy to Azure App Service
   - Ensure redirect URIs include your production domain
   - Test the sign-in flow

## Step 6: Troubleshooting

### Common Issues:

1. **CORS Errors**:
   - Ensure redirect URIs are correctly configured
   - Check that your domain matches exactly (including protocol)

2. **Token Validation Errors**:
   - Verify the client ID in `auth-config.js` matches Azure
   - Check that the tenant name is correct
   - Ensure the policy name matches (`B2C_1_signupsignin1`)

3. **Development vs Production**:
   - Use different redirect URIs for development and production
   - Test login button only shows in development mode
   - Production should only show Microsoft sign-in

### Testing Commands:

```bash
# Test authentication endpoint
curl -X POST "https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io/auth/validate" \
  -H "Authorization: Bearer test-token-12345" | python -m json.tool

# Expected response:
{
  "status": "valid",
  "auth_type": "test",
  "user_id": "test-user",
  "timestamp": "2025-08-30T...",
  "voice_ui_access": true
}
```

## Security Benefits

✅ **Enterprise Security**: Azure AD B2C provides enterprise-grade authentication  
✅ **Single Sign-On**: Users can sign in once and access multiple services  
✅ **Multi-Factor Authentication**: Optional MFA for enhanced security  
✅ **Compliance**: GDPR, SOC, ISO compliance built-in  
✅ **Cost Effective**: Covered by your Microsoft AI Cloud Partner Program credits  

## Next Steps

Once authentication is working:

1. **Enable MFA**: Configure multi-factor authentication in Azure AD B2C
2. **Custom Branding**: Add your organization's branding to the sign-in page
3. **User Management**: Set up user roles and permissions
4. **Monitoring**: Configure Azure Application Insights for auth monitoring
5. **Backup Authentication**: Consider adding alternative authentication methods

## Support

- **Microsoft Partner Support**: Use your AI Cloud Partner Program benefits for technical support
- **Azure Documentation**: [Azure AD B2C Documentation](https://docs.microsoft.com/en-us/azure/active-directory-b2c/)
- **MSAL.js Documentation**: [Microsoft Authentication Library](https://docs.microsoft.com/en-us/azure/active-directory/develop/msal-overview)