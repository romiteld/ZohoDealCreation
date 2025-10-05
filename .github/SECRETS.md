# GitHub Secrets Configuration

## ⚠️ CRITICAL: Required GitHub Secrets for Deployment

You MUST configure these secrets in your GitHub repository for the workflows to function.

### 🔧 How to Add Secrets

1. Go to your GitHub repository: https://github.com/romiteld/outlook
2. Click on **Settings** (in the repository, not your profile)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Add each secret below with its exact name and value

### 📋 Required Secrets

#### 1. Azure Container Registry (ACR) Credentials
```
Secret Name: ACR_USERNAME
Value: wellintakeacr0903
```

```
Secret Name: ACR_PASSWORD
Value: [REDACTED - Add your ACR password here]
```

#### 2. Azure Service Principal (for Azure CLI)
```
Secret Name: AZURE_CLIENT_ID
Value: [Your Azure service principal client ID]
```

```
Secret Name: AZURE_CLIENT_SECRET
Value: [Your Azure service principal client secret]
```

```
Secret Name: AZURE_TENANT_ID
Value: [Your Azure tenant ID]
```

```
Secret Name: AZURE_SUBSCRIPTION_ID
Value: [Your Azure subscription ID]
```

#### 3. Container App Configuration
```
Secret Name: AZURE_RESOURCE_GROUP
Value: TheWell-Infra-East
```

```
Secret Name: AZURE_CONTAINER_APP_NAME
Value: well-intake-api
```

### 🚀 After Adding Secrets

Once all secrets are configured:
1. Any push to `main` branch will trigger automatic deployment
2. Monitor the Actions tab for deployment progress
3. Check deployment at: https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health

### 🔒 Security Notes

- **NEVER** commit actual secret values to the repository
- Rotate secrets regularly through Azure Portal
- Use Azure Key Vault references where possible
- Monitor GitHub Security tab for any exposed secrets

### 📝 Secret Rotation

When rotating secrets:
1. Update the secret in Azure (ACR, Service Principal, etc.)
2. Update the corresponding GitHub secret
3. Trigger a new deployment to verify