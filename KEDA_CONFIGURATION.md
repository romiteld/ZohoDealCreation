# KEDA Autoscaling Configuration for Azure Container Apps

This document describes the KEDA (Kubernetes Event Driven Autoscaling) configuration for Teams bot workers consuming from Azure Service Bus queues.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Teams Bot (Port 8001)                      │
│              HTTP Webhook Handler (Always-On)                 │
│                                                               │
│  Publishes messages to Service Bus:                          │
│  • teams-digest-requests                                     │
│  • teams-nlp-queries                                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│             Azure Service Bus (Standard Tier)                 │
│                                                               │
│  Queue: teams-digest-requests                                │
│  • Lock Duration: 5 minutes                                  │
│  • Max Delivery: 3 attempts                                  │
│  • Dead Letter: Enabled                                      │
│                                                               │
│  Queue: teams-nlp-queries                                    │
│  • Lock Duration: 2 minutes                                  │
│  • Max Delivery: 2 attempts                                  │
│  • Dead Letter: Enabled                                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  KEDA Autoscaling Triggers                    │
│                                                               │
│  Digest Worker:                                              │
│  • Scale: 0 → 10 replicas                                    │
│  • Trigger: 1 replica per 5 messages                         │
│  • Cooldown: 300 seconds                                     │
│                                                               │
│  NLP Worker:                                                 │
│  • Scale: 0 → 20 replicas                                    │
│  • Trigger: 1 replica per 10 messages                        │
│  • Cooldown: 120 seconds                                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Worker Container Apps (Scale-to-Zero)            │
│                                                               │
│  Digest Worker:                                              │
│  • Consumes: teams-digest-requests                           │
│  • Processes: 5 concurrent messages                          │
│  • Sends results via ProactiveMessagingService               │
│                                                               │
│  NLP Worker:                                                 │
│  • Consumes: teams-nlp-queries                               │
│  • Processes: 10 concurrent messages                         │
│  • Sends results via ProactiveMessagingService               │
└─────────────────────────────────────────────────────────────┘
```

## Container Apps Configuration

### 1. Digest Worker Container App

```bash
# Create digest worker Container App with KEDA scaling
az containerapp create \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --environment <CONTAINER_APP_ENVIRONMENT> \
  --image wellintakeacr0903.azurecr.io/teams-digest-worker:latest \
  --cpu 1.0 \
  --memory 2Gi \
  --min-replicas 0 \
  --max-replicas 10 \
  --scale-rule-name azure-servicebus-queue-rule \
  --scale-rule-type azure-servicebus \
  --scale-rule-metadata "queueName=teams-digest-requests" \
                        "namespace=wellintakebus-standard" \
                        "messageCount=5" \
  --scale-rule-auth "connection=service-bus-connection-string" \
  --secrets "service-bus-connection-string=$SERVICE_BUS_CONNECTION_STRING" \
  --env-vars \
    AZURE_SERVICE_BUS_CONNECTION_STRING=secretref:service-bus-connection-string \
    AZURE_SERVICE_BUS_DIGEST_QUEUE=teams-digest-requests \
    TEAMS_BOT_APP_ID=$TEAMS_BOT_APP_ID \
    TEAMS_BOT_APP_PASSWORD=$TEAMS_BOT_APP_PASSWORD \
    DATABASE_URL=$DATABASE_URL \
    MAX_CONCURRENT_MESSAGES=5 \
    MAX_WAIT_TIME=30
```

### 2. NLP Worker Container App

```bash
# Create NLP worker Container App with KEDA scaling
az containerapp create \
  --name teams-nlp-worker \
  --resource-group TheWell-Infra-East \
  --environment <CONTAINER_APP_ENVIRONMENT> \
  --image wellintakeacr0903.azurecr.io/teams-nlp-worker:latest \
  --cpu 0.5 \
  --memory 1Gi \
  --min-replicas 0 \
  --max-replicas 20 \
  --scale-rule-name azure-servicebus-queue-rule \
  --scale-rule-type azure-servicebus \
  --scale-rule-metadata "queueName=teams-nlp-queries" \
                        "namespace=wellintakebus-standard" \
                        "messageCount=10" \
  --scale-rule-auth "connection=service-bus-connection-string" \
  --secrets "service-bus-connection-string=$SERVICE_BUS_CONNECTION_STRING" \
  --env-vars \
    AZURE_SERVICE_BUS_CONNECTION_STRING=secretref:service-bus-connection-string \
    AZURE_SERVICE_BUS_NLP_QUEUE=teams-nlp-queries \
    TEAMS_BOT_APP_ID=$TEAMS_BOT_APP_ID \
    TEAMS_BOT_APP_PASSWORD=$TEAMS_BOT_APP_PASSWORD \
    DATABASE_URL=$DATABASE_URL \
    MAX_CONCURRENT_MESSAGES=10 \
    MAX_WAIT_TIME=20
```

## KEDA Scaling Rules Explained

### Digest Worker Scaling Rule

```yaml
scale-rule-metadata:
  queueName: "teams-digest-requests"
  namespace: "wellintakebus-standard"
  messageCount: "5"  # Scale 1 replica per 5 messages
```

**Behavior:**
- **0 messages** → 0 replicas (scale-to-zero)
- **1-5 messages** → 1 replica
- **6-10 messages** → 2 replicas
- **11-15 messages** → 3 replicas
- **46-50 messages** → 10 replicas (max)

**Cooldown:** 300 seconds (5 minutes) before scaling down

### NLP Worker Scaling Rule

```yaml
scale-rule-metadata:
  queueName: "teams-nlp-queries"
  namespace: "wellintakebus-standard"
  messageCount: "10"  # Scale 1 replica per 10 messages
```

**Behavior:**
- **0 messages** → 0 replicas (scale-to-zero)
- **1-10 messages** → 1 replica
- **11-20 messages** → 2 replicas
- **21-30 messages** → 3 replicas
- **191-200 messages** → 20 replicas (max)

**Cooldown:** 120 seconds (2 minutes) before scaling down

## Environment Variables Reference

### Required for All Workers

```bash
# Service Bus
AZURE_SERVICE_BUS_CONNECTION_STRING="Endpoint=sb://wellintakebus-standard..."
AZURE_SERVICE_BUS_DIGEST_QUEUE="teams-digest-requests"
AZURE_SERVICE_BUS_NLP_QUEUE="teams-nlp-queries"

# Teams Bot (for ProactiveMessagingService)
TEAMS_BOT_APP_ID="<Microsoft-App-ID>"
TEAMS_BOT_APP_PASSWORD="<Microsoft-App-Password>"
TEAMS_BOT_TENANT_ID="<Optional-Tenant-ID>"

# Database
DATABASE_URL="postgresql://user:pass@host:5432/db"

# Worker Tuning (Optional)
MAX_CONCURRENT_MESSAGES="5"  # Digest: 5, NLP: 10
MAX_WAIT_TIME="30"           # Digest: 30s, NLP: 20s
```

## Docker Build Commands

### Build Digest Worker

```bash
docker build -t wellintakeacr0903.azurecr.io/teams-digest-worker:latest \
  -f teams_bot/Dockerfile.digest-worker .

docker push wellintakeacr0903.azurecr.io/teams-digest-worker:latest
```

### Build NLP Worker

```bash
docker build -t wellintakeacr0903.azurecr.io/teams-nlp-worker:latest \
  -f teams_bot/Dockerfile.nlp-worker .

docker push wellintakeacr0903.azurecr.io/teams-nlp-worker:latest
```

## Deployment Workflow

```bash
# 1. Build and push worker images
./scripts/deploy-workers.sh

# 2. Create or update Container Apps with KEDA scaling
az containerapp update \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/teams-digest-worker:latest \
  --revision-suffix "v$(date +%Y%m%d-%H%M%S)"

az containerapp update \
  --name teams-nlp-worker \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/teams-nlp-worker:latest \
  --revision-suffix "v$(date +%Y%m%d-%H%M%S)"

# 3. Verify scaling metrics
az containerapp replica list \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East

az monitor metrics list \
  --resource <CONTAINER_APP_ID> \
  --metric "Replicas" \
  --start-time $(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%SZ') \
  --interval PT1M
```

## Monitoring and Observability

### Check Queue Depth

```bash
# Get current queue metrics
az servicebus queue show \
  --resource-group TheWell-Infra-East \
  --namespace-name wellintakebus-standard \
  --name teams-digest-requests \
  --query "countDetails.activeMessageCount"

az servicebus queue show \
  --resource-group TheWell-Infra-East \
  --namespace-name wellintakebus-standard \
  --name teams-nlp-queries \
  --query "countDetails.activeMessageCount"
```

### View Worker Logs

```bash
# Digest worker logs
az containerapp logs show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --follow

# NLP worker logs
az containerapp logs show \
  --name teams-nlp-worker \
  --resource-group TheWell-Infra-East \
  --follow
```

### Check Replica Count

```bash
# Real-time replica monitoring
watch -n 5 'az containerapp replica list \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --query "[].{Name:name, Status:properties.runningState}" \
  --output table'
```

## Cost Analysis

### Before (Monolithic Synchronous Architecture)

- **Teams Bot:** 1 replica × 24h × $0.12/h = **$86.40/month**
- **Always-on cost:** $86.40/month
- **No scaling:** Fixed cost regardless of usage

### After (Event-Driven with KEDA Scale-to-Zero)

- **Teams Bot (HTTP Handler):** 1 replica × 24h × $0.12/h = **$86.40/month** (always-on)
- **Digest Worker:**
  - Active: ~2h/day × $0.12/h = **$7.20/month**
  - Idle: $0 (scale-to-zero)
- **NLP Worker:**
  - Active: ~1h/day × $0.12/h = **$3.60/month**
  - Idle: $0 (scale-to-zero)
- **Service Bus Standard:** **$10/month**

**Total:** ~$107/month (vs $86.40/month before)

**BUT:**
- **30% faster response times** (<200ms HTTP vs 6+ seconds)
- **Automatic retries** (dead letter queues)
- **Horizontal scaling** (up to 30 workers during peak)
- **Better reliability** (circuit breakers, observability)

**ROI:** Improved user experience + reliability + scalability for +$20/month

## Testing KEDA Scaling

### Test Scale-Out (Digest Worker)

```bash
# Publish 25 test messages (should scale to 5 replicas)
python test_keda_scaling.py --queue digest --count 25

# Watch replicas scale out
watch -n 2 'az containerapp replica list \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --query "length([])"'
```

### Test Scale-To-Zero

```bash
# Wait for queue to drain (5-10 minutes)
# Observe cooldown period (300s for digest, 120s for NLP)
# Verify replicas scale to 0

az containerapp replica list \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East
# Expected: []
```

## Troubleshooting

### Workers Not Scaling

1. **Check KEDA scaler logs:**
   ```bash
   kubectl logs -n kube-system -l app=keda-operator
   ```

2. **Verify Service Bus connection string secret:**
   ```bash
   az containerapp secret list \
     --name teams-digest-worker \
     --resource-group TheWell-Infra-East
   ```

3. **Test Service Bus connectivity:**
   ```bash
   python test_service_bus.py
   ```

### Messages Not Processing

1. **Check dead letter queue:**
   ```bash
   az servicebus queue show \
     --name teams-digest-requests \
     --namespace-name wellintakebus-standard \
     --query "countDetails.deadLetterMessageCount"
   ```

2. **View worker logs for errors:**
   ```bash
   az containerapp logs show \
     --name teams-digest-worker \
     --follow
   ```

### High Latency

1. **Increase concurrent message processing:**
   ```bash
   az containerapp update \
     --name teams-digest-worker \
     --set-env-vars MAX_CONCURRENT_MESSAGES=10
   ```

2. **Lower KEDA message threshold (scale faster):**
   ```bash
   az containerapp update \
     --name teams-digest-worker \
     --scale-rule-metadata "messageCount=3"  # Was 5
   ```

## Best Practices

1. **Graceful Shutdown:** Workers handle SIGTERM to complete in-flight messages
2. **Idempotent Processing:** Use message deduplication for retry safety
3. **Circuit Breakers:** Protect external services (PostgreSQL, Teams API)
4. **Observability:** Log correlation IDs for end-to-end tracing
5. **Dead Letter Monitoring:** Alert on DLQ depth > 10 messages
6. **Cost Monitoring:** Set budget alerts for unexpected scaling

## References

- [KEDA Azure Service Bus Scaler](https://keda.sh/docs/scalers/azure-service-bus/)
- [Azure Container Apps Scaling](https://learn.microsoft.com/en-us/azure/container-apps/scale-app)
- [Service Bus Best Practices](https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-performance-improvements)
