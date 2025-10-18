# Zoho CRM Webhook Setup Guide
## Continuous Sync Deployment & Configuration

### Prerequisites
- [ ] Migration 013 completed in PostgreSQL
- [ ] Azure Service Bus queue `zoho-sync-events` created
- [ ] Environment variables configured (see below)
- [ ] API deployed with webhook endpoint

### Required Environment Variables

```bash
# Add to .env.local or Azure Container App Configuration
ZOHO_WEBHOOK_SECRET=<generate-secure-random-256-bit-key>
SERVICE_BUS_ZOHO_SYNC_QUEUE=zoho-sync-events
REDIS_DEDUPE_TTL_SECONDS=600
ZOHO_MODULES_TO_SYNC=Leads,Deals,Contacts,Accounts
ZOHO_SYNC_INTERVAL_MINUTES=15
```

### Deployment Sequence

#### 1. Run Database Migration (via psql)
```bash
# Connect to Azure PostgreSQL
psql "$(az postgres flexible-server show-connection-string \
  --server-name well-intake-db-0903 \
  --database-name wellintake \
  --admin-user adminuser --query connectionString -o tsv)"

# Run migration
\i migrations/013_zoho_continuous_sync.sql

# Verify tables created
\dt zoho_*
```

#### 2. Create Service Bus Queue
```bash
az servicebus queue create \
  --resource-group TheWell-Infra-East \
  --namespace-name <your-service-bus-namespace> \
  --name zoho-sync-events \
  --max-size 1024
```

#### 3. Deploy API Container
```bash
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:zoho-sync .
docker push wellintakeacr0903.azurecr.io/well-intake-api:zoho-sync
az containerapp update --name well-intake-api --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:zoho-sync
```

#### 4. Deploy Worker Container
```bash
# Create worker Container App
az containerapp create \
  --name zoho-sync-worker \
  --resource-group TheWell-Infra-East \
  --environment <env-name> \
  --image wellintakeacr0903.azurecr.io/zoho-sync-worker:latest \
  --command "python -m app.workers.zoho_sync_worker" \
  --min-replicas 2 --max-replicas 5
```

### Zoho Webhook Configuration

#### Step 1: Test Challenge Endpoint
```bash
# Verify webhook receiver is live
curl "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/zoho/webhooks/health"
```

#### Step 2: Configure in Zoho CRM

1. **Navigate to Zoho CRM**
   - Setup → Automation → Webhooks → Configure Webhook

2. **Create Webhook for Leads**
   - Name: `Well Intake - Leads Sync`
   - Description: `Real-time sync to Well Intake API`
   - Method: **POST**
   - URL: `https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/zoho/webhooks/Leads`
   - Module: **Leads**

3. **Configure Headers**
   - Add Custom Header:
     - Parameter Name: `X-API-Key`
     - Parameter Value: `<your-well-intake-api-key>`

4. **Associate to Workflow**
   - Setup → Automation → Workflow Rules → Create Rule
   - Module: Leads
   - When: Record is Created **OR** Updated **OR** Deleted
   - Instant Action: **Webhooks** → Select "Well Intake - Leads Sync"

5. **Repeat for Deals, Contacts, Accounts**

### Testing

```bash
# Create test lead in Zoho CRM
# Monitor webhook logs
az containerapp logs show --name well-intake-api --resource-group TheWell-Infra-East --follow

# Check database
psql $DATABASE_URL -c "SELECT * FROM zoho_webhook_log ORDER BY received_at DESC LIMIT 5;"
psql $DATABASE_URL -c "SELECT * FROM zoho_leads ORDER BY last_synced_at DESC LIMIT 5;"
```

### Rollback

```bash
# Disable webhooks in Zoho UI
# Stop worker
az containerapp update --name zoho-sync-worker --min-replicas 0
# Run DOWN migration
psql $DATABASE_URL -f migrations/013_down_zoho_continuous_sync.sql
```

### Monitoring

Admin endpoint: `GET /api/teams/admin/zoho-sync-status`

Expected metrics:
- Webhook latency: < 5 seconds p95
- Dedupe hit rate: > 0.10
- Conflict rate: < 0.01
