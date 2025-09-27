# Zoho CRM Sandbox Testing Guide

## Overview
This guide explains how to test the Well Intake API with Zoho CRM Sandbox to verify that all three records (Company, Contact, Deal) are created properly WITHOUT affecting production data.

## Zoho Sandbox Setup

### 1. Access Zoho Sandbox
1. Login to your Zoho CRM account
2. Go to **Setup** → **Developer Space** → **Sandbox**
3. Create a new sandbox or use existing one
4. Your sandbox will have a separate URL like `sandbox.zoho.com`

### 2. Generate Sandbox OAuth Tokens
Since the Azure OAuth proxy already handles authentication, you need to:

1. **Configure OAuth Proxy for Sandbox** (One-time setup)
   - The OAuth service at `https://well-zoho-oauth-v2.azurewebsites.net` needs to support sandbox mode
   - Add a query parameter `?environment=sandbox` to token requests

2. **Use Existing Authentication**
   - The current setup already uses the OAuth proxy
   - We just need to modify the API endpoints to use `sandbox.zohoapis.com`

## Testing the Calendly Email

### Test Data
Using the email you provided:
- **Contact**: Tim Koski (tim.koski@everpar.com)
- **Phone**: +1 918-237-1276  
- **Company**: Everpar (inferred from domain)
- **Location**: Tulsa
- **Requirements**: Hiring plan for 2025-2028

### Expected Zoho Records

#### 1. Company Record (Account)
- **Company Name**: Everpar
- **Phone**: (Will be enriched by Firecrawl/Apollo)
- **Website**: https://everpar.com
- **Detail**: Steve Perry (owner)
- **Source**: Website Inbound
- **Source Detail**: Calendly scheduling

#### 2. Contact Record
- **First Name**: Tim
- **Last Name**: Koski
- **Email**: tim.koski@everpar.com
- **Phone**: +1 918-237-1276
- **City**: Tulsa
- **State**: OK (if inferred)

#### 3. Deal Record
- **Deal Name**: Lead Advisor (Tulsa) - Everpar
- **Source**: Website Inbound
- **Closing Date**: [60 days from today]
- **Description of Requirements**: "Plan to hire 2 new lead advisors as soon as possible..."
- **Pipeline**: Recruitment

## Running the Test

### Option 1: Use Modified Integration (Recommended)

1. **Set Environment Variable**
   ```bash
   export ZOHO_SANDBOX_MODE=true
   ```

2. **Run Test Script**
   ```bash
   cd /home/romiteld/outlook
   python test_calendly_sandbox.py
   ```

### Option 2: Manual API Test with cURL

```bash
# Set to sandbox mode
export API_URL="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
export API_KEY="your-api-key"

# Test with sandbox parameter
curl -X POST "$API_URL/intake/email?sandbox=true" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d @calendly_test_payload.json
```

### Option 3: Modify Backend Temporarily

1. Update `app/integrations.py` line 799:
   ```python
   # Change from:
   self.base_url = f"https://www.zohoapis.{self.dc}/crm/v8"
   # To:
   self.base_url = f"https://sandbox.zohoapis.{self.dc}/crm/v8"
   ```

2. Deploy to test environment or run locally

## Verification Steps

### 1. Check Sandbox Zoho CRM
1. Login to sandbox: `https://sandbox.zoho.com`
2. Navigate to **Accounts** module
3. Search for "Everpar"
4. Verify all fields are populated

### 2. Check Contact
1. Navigate to **Contacts** module
2. Search for "Tim Koski"
3. Verify:
   - Email: tim.koski@everpar.com
   - Phone: +1 918-237-1276
   - City: Tulsa
   - Linked to Everpar account

### 3. Check Deal
1. Navigate to **Deals** module
2. Search for "Lead Advisor (Tulsa) - Everpar"
3. Verify:
   - Pipeline: Recruitment
   - Description contains hiring requirements
   - Linked to contact and account

## Important Notes

1. **Token Separation**: Sandbox uses different OAuth tokens than production
2. **Data Isolation**: Sandbox data is completely separate from production
3. **API Limits**: Sandbox may have different rate limits
4. **Test Safely**: Always use sandbox for testing to avoid production data issues

## Troubleshooting

### Common Issues

1. **Authentication Error**
   - Ensure OAuth proxy supports sandbox mode
   - Verify sandbox tokens are being used

2. **404 Errors**
   - Check API endpoint is using `sandbox.zohoapis.com`
   - Verify sandbox organization ID

3. **Missing Fields**
   - Ensure all custom fields exist in sandbox
   - Field API names must match between environments

## Next Steps

After successful sandbox testing:
1. Verify all three records created correctly
2. Check field mappings are accurate
3. Test duplicate detection
4. Validate business rules (source determination, deal naming)
5. Once confirmed, the same code will work in production