# Weekly Digest Email Subscription - Deployment Guide

## Overview

This guide will walk you through deploying the new weekly digest email subscription feature to your Azure environment.

**What's Being Deployed:**
- Database migration with subscription tables and triggers
- Weekly digest scheduler background job
- Email delivery via Azure Communication Services
- Updated Teams Bot with subscription UI

---

## Prerequisites Check

✅ **Azure Resources Verified:**
- Teams Bot: `TalentWellAssistant` (active)
- Container App: `well-intake-api` (running revision `v20251005-073901`)
- Database: `well-intake-db-0903` (PostgreSQL 15, Ready)
- Email Service: `well-communication-services` (available)

✅ **Current State:**
- Teams integration tables exist: `teams_bot_config`, `teams_conversations`, `teams_user_preferences`, `teams_digest_requests`
- Subscription columns **NOT YET ADDED** to `teams_user_preferences`
- Migration 006 **NOT YET APPLIED**

---

## Step 1: Apply Database Migration

Run migration 006 to add subscription tables and columns.

```bash
# From your local machine (WSL)
cd /home/romiteld/Development/Desktop_Apps/outlook

# Connect to PostgreSQL and apply migration
PGPASSWORD=$(az postgres flexible-server show \
  --name well-intake-db-0903 \
  --resource-group TheWell-Infra-East \
  --query "administratorLogin" -o tsv | xargs -I {} \
  az keyvault secret show \
  --vault-name well-intake-kv \
  --name postgres-password \
  --query value -o tsv) \
psql -h well-intake-db-0903.postgres.database.azure.com \
  -U wellintakeadmin \
  -d wellintake \
  -f migrations/006_weekly_digest_subscriptions.sql
```

**Expected Output:**
```
ALTER TABLE
CREATE INDEX
CREATE INDEX
COMMENT
CREATE TABLE
CREATE INDEX
...
CREATE TRIGGER
CREATE VIEW
CREATE VIEW
```

**Verification:**
```bash
# Check new columns were added
psql -h well-intake-db-0903.postgres.database.azure.com \
  -U wellintakeadmin \
  -d wellintake \
  -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'teams_user_preferences' AND column_name IN ('delivery_email', 'subscription_active');"
```

Should return:
```
    column_name
--------------------
 delivery_email
 subscription_active
```

---

## Step 2: Configure Azure Communication Services for Email

Azure Communication Services is already provisioned. Now we need to configure it for email sending.

### 2.1: Get Connection String

```bash
# Get primary connection string
ACS_CONNECTION_STRING=$(az communication show-connection-string \
  --name well-communication-services \
  --resource-group TheWell-Infra-East \
  --query "primaryConnectionString" -o tsv)

echo "Connection String: $ACS_CONNECTION_STRING"
```

### 2.2: Configure Email Domain

You need to either:
- **Option A**: Use Azure-managed domain (easiest, but emails come from `@xxxxxxxx.azurecomm.net`)
- **Option B**: Connect custom domain (requires DNS verification)

**For now, let's use Azure-managed domain:**

```bash
# Check if email domain exists
az communication email domain list \
  --email-service-name well-communication-services \
  --resource-group TheWell-Infra-East
```

If no domain exists, create one:

```bash
# Create Azure-managed email domain
az communication email domain create \
  --domain-name AzureManagedDomain \
  --email-service-name well-communication-services \
  --resource-group TheWell-Infra-East \
  --location global
```

### 2.3: Get Sender Email Address

```bash
# Get the from address for sending
FROM_EMAIL=$(az communication email domain show \
  --domain-name AzureManagedDomain \
  --email-service-name well-communication-services \
  --resource-group TheWell-Infra-East \
  --query "fromSenderDomain" -o tsv)

echo "FROM_EMAIL: DoNotReply@$FROM_EMAIL"
```

---

## Step 3: Add Environment Variables to Container App

Store email credentials as Container App secrets and environment variables.

```bash
# Add Azure Communication Services connection string as secret
az containerapp secret set \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --secrets \
    acs-connection-string="$ACS_CONNECTION_STRING"

# Set environment variables for email configuration
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --set-env-vars \
    "EMAIL_PROVIDER=azure_communication_services" \
    "ACS_CONNECTION_STRING=secretref:acs-connection-string" \
    "SMTP_FROM_EMAIL=DoNotReply@$FROM_EMAIL" \
    "SMTP_FROM_NAME=TalentWell Vault"
```

**Verification:**
```bash
# Check environment variables were set
az containerapp show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --query "properties.template.containers[0].env[?name=='EMAIL_PROVIDER' || name=='SMTP_FROM_EMAIL']" -o table
```

---

## Step 4: Update Email Sender Code

The `WeeklyDigestScheduler` needs to be updated to use Azure Communication Services instead of SMTP.

### 4.1: Install Azure Communication Email SDK

Update `requirements.txt`:
```bash
# Add to requirements.txt
echo "azure-communication-email==1.0.0" >> requirements.txt
```

### 4.2: Update WeeklyDigestScheduler

The current implementation uses SMTP. We need to update it to use Azure Communication Services.

**File to modify**: `app/jobs/weekly_digest_scheduler.py`

**Current code** (lines 22-28):
```python
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@emailthewell.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "TalentWell Vault")
```

**Replace with**:
```python
# Email configuration - use Azure Communication Services
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "azure_communication_services")
ACS_CONNECTION_STRING = os.getenv("ACS_CONNECTION_STRING")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@emailthewell.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "TalentWell Vault")
```

**Current `send_email()` method** (lines 96-137):
```python
def send_email(self, to_email: str, subject: str, html_body: str, ...) -> str:
    # Uses smtplib
```

**Replace with**:
```python
def send_email(
    self,
    to_email: str,
    subject: str,
    html_body: str,
    user_name: Optional[str] = None
) -> str:
    """
    Send email via Azure Communication Services.
    """
    from azure.communication.email import EmailClient
    from azure.communication.email import EmailContent, EmailAddress, EmailMessage

    if not ACS_CONNECTION_STRING:
        raise ValueError("ACS_CONNECTION_STRING not configured")

    try:
        # Create email client
        email_client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)

        # Build message
        message = EmailMessage(
            sender=EmailAddress(
                email=SMTP_FROM_EMAIL,
                display_name=SMTP_FROM_NAME
            ),
            recipients=EmailAddress(email=to_email),
            subject=subject,
            html_content=html_body
        )

        # Send email
        poller = email_client.begin_send(message)
        result = poller.result()

        logger.info(f"Email sent to {to_email}: {subject} (message_id: {result.message_id})")
        return result.message_id

    except Exception as e:
        logger.error(f"Azure Communication Services send failed to {to_email}: {e}", exc_info=True)
        raise
```

---

## Step 5: Deploy Updated Code

Build and deploy the updated container with new subscription features.

```bash
cd /home/romiteld/Development/Desktop_Apps/outlook

# Build Docker image with cache-busting timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:subscriptions-$TIMESTAMP .

# Login to ACR
az acr login --name wellintakeacr0903

# Push image
docker push wellintakeacr0903.azurecr.io/well-intake-api:subscriptions-$TIMESTAMP

# Update Container App with new image
az containerapp update \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:subscriptions-$TIMESTAMP \
  --revision-suffix "subscriptions-$TIMESTAMP"

# Wait for deployment to complete
az containerapp revision show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --revision well-intake-api--subscriptions-$TIMESTAMP \
  --query "properties.provisioningState"
```

**Expected Output**: `Provisioned`

---

## Step 6: Set Up Scheduled Job for Weekly Digest Delivery

The `WeeklyDigestScheduler` needs to run hourly to check for subscriptions due for delivery.

### Option A: Azure Container Apps Jobs (Recommended)

```bash
# Create Container Apps Job for scheduled digest delivery
az containerapp job create \
  --name well-digest-scheduler \
  --resource-group TheWell-Infra-East \
  --environment well-intake-env \
  --trigger-type "Schedule" \
  --cron-expression "0 * * * *" \
  --image wellintakeacr0903.azurecr.io/well-intake-api:subscriptions-$TIMESTAMP \
  --command "python" "-m" "app.jobs.weekly_digest_scheduler" \
  --cpu 0.5 \
  --memory 1Gi \
  --replica-timeout 3600 \
  --env-vars \
    EMAIL_PROVIDER=azure_communication_services \
    SMTP_FROM_EMAIL=secretref:smtp-from-email \
    SMTP_FROM_NAME="TalentWell Vault" \
  --secrets \
    acs-connection-string="$ACS_CONNECTION_STRING" \
    smtp-from-email="DoNotReply@$FROM_EMAIL"
```

### Option B: Azure Functions Timer Trigger

Create a separate Azure Function app with timer trigger:

```bash
# Create Function App
az functionapp create \
  --name well-digest-scheduler-func \
  --resource-group TheWell-Infra-East \
  --storage-account wellintakestorage0903 \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type Linux \
  --consumption-plan-location eastus

# Deploy function code (requires function.json with timer trigger)
```

---

## Step 7: Verification & Testing

### 7.1: Test Database Migration

```bash
# Connect to database
psql -h well-intake-db-0903.postgres.database.azure.com \
  -U wellintakeadmin \
  -d wellintake

# Verify tables exist
\dt teams_*
\dt weekly_*
\dt subscription_*

# Verify views exist
\dv *_digest_*
\dv *_subscriptions*

# Check trigger is active
SELECT tgname, tgtype FROM pg_trigger WHERE tgname LIKE '%digest%';
```

### 7.2: Test Teams Bot Preferences

1. Open Microsoft Teams
2. Go to 1:1 chat with TalentWell Assistant
3. Type: `preferences`
4. **Expected**: Adaptive Card with new subscription fields:
   - Subscribe to weekly email digests (toggle)
   - Email Address (text input)
   - Max Candidates Per Digest (1-20 slider)
5. Toggle subscription ON
6. Enter email address (or leave blank to use Teams email)
7. Click "💾 Save Preferences"
8. **Expected**: Success message + confirmation email

### 7.3: Test Confirmation Email

Check the email address you provided:
```
Subject: ✅ Weekly Vault Digest Subscription Confirmed

Your subscription has been confirmed:
📧 Email: your.email@company.com
📊 Audience: Global
📅 Frequency: Weekly
👥 Max Candidates: 6 per digest

Your first digest will arrive on Monday, October 9 at 9:00 AM.
```

### 7.4: Test Scheduled Delivery (Manual)

```bash
# SSH into Container App or run locally
az containerapp exec \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --command "python -m app.jobs.weekly_digest_scheduler"

# Check logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --follow \
  | grep "digest scheduler"
```

**Expected Output**:
```
🔄 Running weekly digest scheduler...
Found 1 subscriptions due for delivery
Processing subscription for user_id (email@company.com)
Generating digest for user_id: audience=global, max=6
✅ Digest delivered to email@company.com: 6 candidates
✅ Digest scheduler completed: 1 sent, 0 failed
```

### 7.5: Verify Database Records

```bash
psql -h well-intake-db-0903.postgres.database.azure.com \
  -U wellintakeadmin \
  -d wellintake \
  -c "SELECT user_email, subscription_active, delivery_email, next_digest_scheduled_at FROM teams_user_preferences WHERE subscription_active = TRUE;"
```

Should show your test subscription with calculated next delivery time.

---

## Step 8: Monitor & Troubleshoot

### Check Container App Logs

```bash
# Follow live logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --follow

# Filter for email-related logs
az containerapp logs show \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --tail 100 \
  | grep -E "email|smtp|ACS|subscription"
```

### Check Scheduled Job Execution

```bash
# If using Container Apps Jobs
az containerapp job execution list \
  --name well-digest-scheduler \
  --resource-group TheWell-Infra-East \
  --query "[].{name:name, status:properties.status, startTime:properties.startTime}" -o table
```

### Check Database Activity

```sql
-- Active subscriptions
SELECT * FROM active_digest_subscriptions;

-- Subscriptions due now
SELECT * FROM subscriptions_due_for_delivery;

-- Recent deliveries
SELECT
  delivery_email,
  status,
  cards_generated,
  email_sent_at,
  error_message
FROM weekly_digest_deliveries
ORDER BY created_at DESC
LIMIT 10;

-- Confirmation emails sent
SELECT
  user_email,
  delivery_email,
  action,
  confirmation_sent,
  confirmation_sent_at
FROM subscription_confirmations
ORDER BY created_at DESC
LIMIT 10;
```

---

## Rollback Plan

If something goes wrong, you can rollback the deployment:

### Rollback Code Deployment

```bash
# Revert to previous revision
PREVIOUS_REVISION="well-intake-api--v20251005-073901"

az containerapp revision activate \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --revision $PREVIOUS_REVISION

# Set 100% traffic to previous revision
az containerapp ingress traffic set \
  --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --revision-weight "$PREVIOUS_REVISION=100"
```

### Rollback Database Migration

⚠️ **WARNING**: Rolling back database changes is complex. Only do this if absolutely necessary.

```sql
-- Disable all subscriptions (safer than dropping tables)
UPDATE teams_user_preferences SET subscription_active = FALSE;

-- If you must drop the new tables
DROP TABLE IF EXISTS subscription_confirmations CASCADE;
DROP TABLE IF EXISTS weekly_digest_deliveries CASCADE;

-- Remove new columns (this will lose data!)
ALTER TABLE teams_user_preferences
  DROP COLUMN IF EXISTS delivery_email,
  DROP COLUMN IF EXISTS max_candidates_per_digest,
  DROP COLUMN IF EXISTS subscription_active,
  DROP COLUMN IF EXISTS last_digest_sent_at,
  DROP COLUMN IF EXISTS next_digest_scheduled_at;

-- Drop views
DROP VIEW IF EXISTS subscriptions_due_for_delivery;
DROP VIEW IF EXISTS active_digest_subscriptions;

-- Drop triggers
DROP TRIGGER IF EXISTS teams_user_preferences_schedule_digest ON teams_user_preferences;
DROP FUNCTION IF EXISTS update_next_digest_scheduled();
DROP FUNCTION IF EXISTS calculate_next_digest_time(VARCHAR, VARCHAR);
```

---

## Post-Deployment Checklist

- [ ] Migration 006 applied successfully
- [ ] Azure Communication Services configured with email domain
- [ ] Container App environment variables set
- [ ] Code deployed with Azure Communication Services email client
- [ ] Scheduled job created and running hourly
- [ ] Teams Bot preferences card shows subscription fields
- [ ] Test subscription created and confirmation email received
- [ ] Manual scheduler run successful
- [ ] Database records created correctly
- [ ] Logs show no errors

---

## Next Steps

1. **Monitor first week of automated deliveries**
   - Check `weekly_digest_deliveries` table daily
   - Monitor email bounce rates
   - Collect user feedback

2. **Add custom domain** (optional)
   - Configure DNS records for `@emailthewell.com`
   - Verify domain in Azure Communication Services
   - Update `SMTP_FROM_EMAIL` to use custom domain

3. **Set up alerts**
   - Azure Monitor alert for failed deliveries
   - Email notification when scheduler fails
   - Daily summary of delivery stats

4. **Documentation**
   - Update user guide with subscription instructions
   - Create troubleshooting guide for common issues
   - Document unsubscribe process

---

## Support Resources

- **Azure Communication Services Docs**: https://learn.microsoft.com/en-us/azure/communication-services/
- **Container Apps Jobs**: https://learn.microsoft.com/en-us/azure/container-apps/jobs
- **Teams Bot Documentation**: `docs/TEAMS_BOT_CAPABILITIES.md`
- **Migration Files**: `migrations/006_weekly_digest_subscriptions.sql`
- **Scheduler Code**: `app/jobs/weekly_digest_scheduler.py`
