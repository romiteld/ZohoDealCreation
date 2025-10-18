# Teams Bot Deployment Checklist

## Pre-Deployment Verification

### Code Quality Checks
- [ ] All unit tests passing
  ```bash
  cd /home/romiteld/Development/Desktop_Apps/outlook
  pytest teams_bot/tests/ -v --cov=teams_bot --cov-report=term-missing
  ```

- [ ] Integration tests passing
  ```bash
  pytest tests/teams/ -v
  pytest tests/test_teams_bot_integration.py -v
  ```

- [ ] Linting checks pass
  ```bash
  flake8 teams_bot/
  black teams_bot/ --check
  pylint teams_bot/app/
  ```

- [ ] Security scan clean
  ```bash
  bandit -r teams_bot/app/
  safety check
  ```

### Feature Flag Documentation
- [ ] All feature flags documented
  ```python
  # Verify in app/config/feature_flags.py
  ENABLE_NLP_CARDS = false  # Default for production
  ENABLE_AZURE_AI_SEARCH = false  # Experimental
  USE_ASYNC_DIGEST = true  # Service Bus enabled
  PRIVACY_MODE = true  # Anonymization active
  ```

- [ ] Environment variables documented
  ```bash
  # Check .env.example is up to date
  cat .env.example | grep -E "ENABLE_|FEATURE_|USE_"
  ```

### Database Migration Check
- [ ] All migrations reviewed
  ```bash
  alembic history
  alembic check
  ```

- [ ] Migration rollback tested
  ```bash
  # Test on staging
  alembic upgrade head
  alembic downgrade -1
  alembic upgrade head
  ```

### Dependencies Audit
- [ ] No security vulnerabilities
  ```bash
  pip-audit
  ```

- [ ] Lock file updated
  ```bash
  pip freeze > requirements.lock
  ```

---

## Docker Build & Registry

### 1. Build Docker Image
```bash
# Navigate to project root
cd /home/romiteld/Development/Desktop_Apps/outlook

# Build teams-bot image
docker build \
  -f teams_bot/Dockerfile \
  -t wellintakeacr0903.azurecr.io/teams-bot:latest \
  -t wellintakeacr0903.azurecr.io/teams-bot:$(date +%Y%m%d-%H%M%S) \
  .

# Verify build
docker run --rm \
  -e API_KEY=test \
  -p 8001:8001 \
  wellintakeacr0903.azurecr.io/teams-bot:latest \
  uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1

# Test health endpoint
curl http://localhost:8001/health
```

### 2. Push to Azure Container Registry
```bash
# Login to ACR
az acr login --name wellintakeacr0903

# Push both tags
docker push wellintakeacr0903.azurecr.io/teams-bot:latest
docker push wellintakeacr0903.azurecr.io/teams-bot:$(date +%Y%m%d-%H%M%S)

# Verify push
az acr repository show-tags \
  --name wellintakeacr0903 \
  --repository teams-bot \
  --orderby time_desc \
  --output table
```

---

## Azure Container Apps Deployment

### 1. Pre-Deployment Environment Check
```bash
# Set Azure context
az account set --subscription "3fee2ac0-3a70-4343-a8b2-3a98da1c9682"

# Verify resource group
az group show --name TheWell-Infra-East

# Check current container app status
az containerapp show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "{Name:name, Status:properties.provisioningState, Url:properties.configuration.ingress.fqdn}"
```

### 2. Environment Variables Configuration
```bash
# Export current environment variables for backup
az containerapp show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "properties.template.containers[0].env" \
  > env_backup_$(date +%Y%m%d).json

# Update environment variables
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars \
    "API_KEY=secretref:api-key" \
    "DATABASE_URL=secretref:database-url" \
    "AZURE_REDIS_CONNECTION_STRING=secretref:redis-connection" \
    "OPENAI_API_KEY=secretref:openai-api-key" \
    "OPENAI_MODEL=gpt-5" \
    "ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth-v2.azurewebsites.net" \
    "ZOHO_DEFAULT_OWNER_EMAIL=steve.perry@emailthewell.com" \
    "EMAIL_PROVIDER=azure_communication_services" \
    "ACS_EMAIL_CONNECTION_STRING=secretref:acs-connection" \
    "ENABLE_NLP_CARDS=false" \
    "ENABLE_AZURE_AI_SEARCH=false" \
    "USE_ASYNC_DIGEST=true" \
    "PRIVACY_MODE=true" \
    "FEATURE_LLM_SENTIMENT=true" \
    "FEATURE_GROWTH_EXTRACTION=true" \
    "USE_ZOHO_API=false"
```

### 3. Deploy New Revision
```bash
# Deploy with specific revision name
REVISION_NAME="v$(date +%Y%m%d-%H%M%S)"

az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/teams-bot:latest \
  --revision-suffix "$REVISION_NAME" \
  --min-replicas 1 \
  --max-replicas 10 \
  --cpu 0.5 \
  --memory 1.0Gi

# Wait for deployment
echo "Waiting for deployment to complete..."
az containerapp revision show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision "teams-bot--$REVISION_NAME" \
  --query "properties.runningState"
```

### 4. Traffic Routing (Blue-Green Deployment)
```bash
# Get current and new revision names
CURRENT_REVISION=$(az containerapp show -n teams-bot -g TheWell-Infra-East --query "properties.latestRevisionName" -o tsv)
NEW_REVISION="teams-bot--$REVISION_NAME"

# Split traffic 90/10 for canary deployment
az containerapp ingress traffic set \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision-weight "$CURRENT_REVISION=90" "$NEW_REVISION=10"

# Monitor for 10 minutes...
sleep 600

# If stable, route 100% to new revision
az containerapp ingress traffic set \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision-weight "$NEW_REVISION=100"
```

---

## Post-Deployment Verification

### 1. Health Check Verification
```bash
# Check health endpoint
curl -f https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health

# Expected response:
# {
#   "status": "healthy",
#   "service": "teams-bot",
#   "version": "1.0.0"
# }
```

### 2. Application Logs Verification
```bash
# Stream logs for 2 minutes
az containerapp logs show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --follow \
  --tail 50 &

LOGS_PID=$!
sleep 120
kill $LOGS_PID

# Check for errors
az containerapp logs show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --tail 100 | grep -i "error\|exception\|failed"
```

### 3. Database Connectivity Test
```bash
# Test database connection via admin endpoint
curl -X GET \
  "https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/admin/test-db" \
  -H "X-API-Key: ${API_KEY}"
```

### 4. Redis Cache Test
```bash
# Test Redis connectivity
curl -X GET \
  "https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/admin/test-cache" \
  -H "X-API-Key: ${API_KEY}"
```

### 5. Teams Webhook Test
```bash
# Send test message to Teams webhook
curl -X POST \
  "https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/webhook" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
    "type": "message",
    "text": "test",
    "from": {"id": "test-user", "name": "Test User"},
    "conversation": {"id": "test-conversation"}
  }'
```

### 6. Application Insights Verification
```kusto
// Check for deployment events
customEvents
| where timestamp > ago(10m)
| where cloud_RoleName == "teams-bot"
| summarize Count = count() by name
| order by Count desc

// Check for errors
exceptions
| where timestamp > ago(10m)
| where cloud_RoleName == "teams-bot"
| project timestamp, message, outerMessage
| order by timestamp desc
```

---

## Monitoring Setup Verification

### 1. Verify Alerts Are Active
```bash
# List configured alerts
az monitor metrics alert list \
  --resource-group TheWell-Infra-East \
  --output table

# Required alerts:
# - teams-bot-high-error-rate (> 5% errors)
# - teams-bot-high-latency (P95 > 5000ms)
# - teams-bot-down (no requests in 5 min)
```

### 2. Dashboard Access Check
- [ ] Executive Dashboard: https://portal.azure.com/#dashboard/teams-bot-exec
- [ ] Operations Dashboard: https://portal.azure.com/#dashboard/teams-bot-ops
- [ ] Metrics visible and updating

### 3. Log Analytics Query Test
```bash
# Test log query access
az monitor log-analytics query \
  --workspace "well-intake-logs" \
  --analytics-query "ContainerAppConsoleLogs | where ContainerAppName_s == 'teams-bot' | take 10"
```

---

## Rollback Decision Points

### Immediate Rollback Triggers
- [ ] Error rate > 10% for 5 minutes
- [ ] Response time P95 > 10s for 5 minutes
- [ ] Database connection failures
- [ ] Teams webhook returning 500 errors
- [ ] Memory usage > 90% sustained

### Rollback Commands
```bash
# Quick rollback to previous revision
PREVIOUS_REVISION=$(az containerapp revision list \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "[?properties.active && name!='teams-bot--$REVISION_NAME'].name | [0]" \
  -o tsv)

az containerapp ingress traffic set \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision-weight "$PREVIOUS_REVISION=100"

# Deactivate problematic revision
az containerapp revision deactivate \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision "teams-bot--$REVISION_NAME"
```

---

## Communication & Handoff

### 1. Deployment Notification
```markdown
Subject: Teams Bot v2.0.0 Deployed to Production

Team,

Teams Bot has been successfully deployed to production.

Deployment Details:
- Version: 2.0.0
- Revision: teams-bot--v20251017-143022
- Features: NLP support (disabled by default)
- Status: ✅ All health checks passing

Monitoring:
- Dashboard: [Link to dashboard]
- Logs: [Link to Application Insights]

Next Steps:
- QA smoke testing (30 minutes)
- Beta rollout begins tomorrow

Contact: @teams-bot-dev for issues
```

### 2. QA Handoff Package
- [ ] Smoke test document: `/docs/testing/teams_bot_smoke.md`
- [ ] Test credentials provided
- [ ] Test Teams channel access granted
- [ ] Application Insights access granted

### 3. Operations Handoff
- [ ] Runbook updated: `/docs/operations/teams_bot_runbook.md`
- [ ] Alert recipients configured
- [ ] PagerDuty integration tested
- [ ] Rollback procedure documented

---

## Sign-Off

### Deployment Engineer
- **Name**: _________________________
- **Date/Time**: _________________________
- **All checks passed**: [ ] Yes [ ] No
- **Issues encountered**: _________________________

### QA Lead
- **Name**: _________________________
- **Smoke tests passed**: [ ] Yes [ ] No [ ] In Progress
- **Ready for beta**: [ ] Yes [ ] No

### Product Owner
- **Name**: _________________________
- **Deployment approved**: [ ] Yes [ ] No
- **Beta rollout approved**: [ ] Yes [ ] No

---

## Appendix: Troubleshooting

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Container fails to start | Check environment variables, verify secrets |
| High memory usage | Scale up container, check for memory leaks |
| Database connection timeout | Verify connection string, check firewall rules |
| Teams webhook 401 | Verify API key, check Teams app registration |
| Redis connection failed | Check connection string, verify TLS settings |

### Emergency Contacts
- **Azure Support**: 1-800-AZURE-00
- **On-Call Engineer**: Check PagerDuty
- **Dev Team Lead**: daniel.romitelli@emailthewell.com
- **Infrastructure Team**: devops@emailthewell.com

### Useful Commands
```bash
# Get container logs
az containerapp logs show -n teams-bot -g TheWell-Infra-East --tail 100

# Scale manually
az containerapp update -n teams-bot -g TheWell-Infra-East --min-replicas 2 --max-replicas 20

# Restart container
az containerapp revision restart -n teams-bot -g TheWell-Infra-East --revision <revision-name>

# Check resource consumption
az monitor metrics list --resource <resource-id> --metric "CpuUsage,MemoryUsage" --interval PT1M
```