# TalentWell Backend Deployment Checklist

## Pre-Deployment Verification

### 1. ✅ Environment Configuration
- [x] `.env.local` updated with Zoom credentials
- [x] `ZOOM_ACCOUNT_ID` = 5UAzr-y6QGe3_e0oEqLnNg
- [x] `ZOOM_CLIENT_ID` = lqcsA40TJSCqDlIuWfxgQ  
- [x] `ZOOM_CLIENT_SECRET` = MgbDpa1QEp2p0ydwOiB67zH58AFWt673
- [x] `ZOOM_SECRET_TOKEN` = RIX3TgGtQn6ptoWta2XfJg
- [x] `ZOOM_VERIFICATION_TOKEN` = 0kBX1MhLRWWuU8oAOR2Kqw
- [x] `TALENTWELL_API_KEY` configured

### 2. 🔐 Zoom App Configuration
**Required Actions in Zoom Marketplace:**
1. Visit: https://marketplace.zoom.us/develop/apps
2. Find your Server-to-Server OAuth app
3. Add these scopes:
   - `recording:read:admin`
   - `cloud_recording:read:list_recording_files`
   - `cloud_recording:read:list_recording_files:admin`
4. Save changes and note any reauthorization requirements

### 3. 📦 Code Implementation Status
- [x] **Zoom Integration** (`app/zoom_client.py`)
  - Server-to-Server OAuth authentication
  - Meeting recording retrieval
  - VTT transcript parsing
  - Meeting ID extraction from URLs

- [x] **Candidate Selection Logic** (`app/jobs/talentwell_curator.py`)
  - Query Zoho Candidates with `Published_to_Vault=true`
  - Filter by `Candidate_Status NOT IN ('Placed','Hired')`
  - Sort by `Date_Published_to_Vault` ascending (deterministic)
  - Redis deduplication (last 4 weeks)
  - City-to-metro normalization with Gulf Breeze mapping
  - Mobility line generation from CRM booleans
  - Zoom transcript integration
  - Hard-skill bullet generation (2-5 bullets)

- [x] **Email Support** (`app/api/vault_agent/routes.py`)
  - Single-candidate email via `/api/vault-agent/publish`
  - Brandon's HTML format (bold headers, location, mobility)
  - 2-5 bullet validation with fallbacks
  - TWAV reference code generation

- [x] **Validation** (`app/validation/talentwell_validator.py`)
  - `validate_candidate_card` method
  - Brandon's format requirements
  - Soft skill detection and warnings

## Deployment Steps

### 1. Run Local Tests
```bash
# Run comprehensive test suite
python run_all_tests.py

# Or run individual tests
python tests/test_zoom_integration.py
python tests/test_candidate_selection.py
python tests/test_email_rendering.py
```

### 2. Build and Push Docker Image
```bash
# Build the Docker image
docker build -t wellintakeregistry.azurecr.io/well-intake-api:latest .

# Login to Azure Container Registry
az acr login --name wellintakeregistry

# Push the image
docker push wellintakeregistry.azurecr.io/well-intake-api:latest
```

### 3. Update Azure Container App
```bash
# Update with new image
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeregistry.azurecr.io/well-intake-api:latest

# Or use the deployment script
./deploy.sh
```

### 4. Set Environment Variables in Azure
```bash
# Set Zoom credentials
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --set-env-vars \
    ZOOM_ACCOUNT_ID=5UAzr-y6QGe3_e0oEqLnNg \
    ZOOM_CLIENT_ID=lqcsA40TJSCqDlIuWfxgQ \
    ZOOM_CLIENT_SECRET=MgbDpa1QEp2p0ydwOiB67zH58AFWt673 \
    ZOOM_SECRET_TOKEN=RIX3TgGtQn6ptoWta2XfJg \
    ZOOM_VERIFICATION_TOKEN=0kBX1MhLRWWuU8oAOR2Kqw
```

## Post-Deployment Testing

### 1. Health Check
```bash
curl https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
```

### 2. Test Zoom Integration
```bash
# Test with a known meeting ID
curl -X POST "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/vault-agent/ingest" \
  -H "X-API-Key: ${TALENTWELL_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "email",
    "payload": {
      "candidate_name": "Test Candidate",
      "meeting_id": "85725475967"
    }
  }'
```

### 3. Test TalentWell Digest
1. Navigate to `/talentwell` admin page
2. Select "Weekly" mode
3. Set date range to capture test candidates
4. Click "Validate" to preview
5. Click "Send" to deliver to Brandon

### 4. Test Single-Candidate Email
```bash
# Ingest candidate
LOCATOR=$(curl -X POST "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/vault-agent/ingest" \
  -H "X-API-Key: ${TALENTWELL_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{...candidate data...}' | jq -r '.locator')

# Publish to email
curl -X POST "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/vault-agent/publish" \
  -H "X-API-Key: ${TALENTWELL_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"locator\": \"$LOCATOR\",
    \"channels\": [\"email_campaign\"],
    \"email\": {
      \"to\": [\"brandon@emailthewell.com\"],
      \"subject\": \"TalentWell - New Candidate Alert\"
    }
  }"
```

### 5. Monitor Logs
```bash
# View container logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --follow

# Check for Zoom authentication
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --follow | grep -i zoom
```

## Validation Checklist

### Brandon's Format Requirements
- [ ] Candidate name is **bold** (h3 > strong)
- [ ] Location label is **bold** ("Location:")
- [ ] Mobility line in parentheses after location
- [ ] 2-5 hard-skill bullets (no soft skills)
- [ ] Reference code starts with "TWAV"
- [ ] No soft skill keywords (passionate, dedicated, etc.)

### Integration Points
- [ ] Zoom transcripts fetching successfully
- [ ] Redis deduplication working (4-week window)
- [ ] Zoho query returning candidates
- [ ] Email delivery to Brandon confirmed
- [ ] City-to-metro normalization (Gulf Breeze → Pensacola area)

## Troubleshooting

### Issue: "Invalid access token" from Zoom
**Solution**: Add required scopes in Zoom App Marketplace

### Issue: No candidates returned
**Check**:
1. Zoho has candidates with `Published_to_Vault=true`
2. Candidates not in 'Placed' or 'Hired' status
3. Redis deduplication not blocking all candidates

### Issue: Email not received
**Check**:
1. Email provider configured (ACS/SendGrid/SMTP)
2. Recipient email correct
3. Check spam folder

## Success Criteria

✅ **Deployment is successful when:**
1. Zoom transcripts fetch without authentication errors
2. Candidates are selected deterministically (oldest first)
3. Emails arrive in Brandon's inbox with proper formatting
4. Reference codes follow TWAV pattern
5. Mobility lines correctly reflect CRM booleans
6. No soft skills appear in bullets

## Contact

For issues or questions:
- Backend: Review logs in Application Insights
- Zoom App: Check scopes at https://marketplace.zoom.us/develop/apps
- Email Delivery: Check Azure Communication Services logs