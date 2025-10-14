# DLQ Operations Runbook

**Service**: Teams Digest Worker (Azure Service Bus + KEDA)
**Queue**: `teams-digest-requests` (namespace: `wellintakebus-standard`)
**Tool**: [scripts/clear_digest_queue.py](../scripts/clear_digest_queue.py)
**Owner**: DevOps / Platform Team

## Quick Reference

```bash
# List DLQ messages (non-destructive)
python scripts/clear_digest_queue.py --action list

# Purge DLQ (destructive, with confirmation)
python scripts/clear_digest_queue.py --action purge

# Requeue messages for reprocessing
python scripts/clear_digest_queue.py --action requeue

# Requeue with new message IDs (duplicate detection enabled)
python scripts/clear_digest_queue.py --action requeue --regenerate-message-ids

# Skip confirmation (automation)
python scripts/clear_digest_queue.py --action purge --yes
```

## Authentication

### Method 1: Azure CLI (Recommended for Manual Operations)

**Prerequisites**:
- Azure CLI installed (`az --version`)
- Logged in with `az login`
- RBAC role: `Azure Service Bus Data Receiver` or higher

**Usage**:
```bash
az login
az account set --subscription <subscription-id>

# Tool will use DefaultAzureCredential automatically
python scripts/clear_digest_queue.py --action list
```

### Method 2: Connection String (Local Development / Emergency)

**Prerequisites**:
- Service Bus connection string from Azure Portal or Key Vault

**Usage**:
```bash
# Get connection string
export SB_CONN=$(az servicebus namespace authorization-rule keys list \
  --name RootManageSharedAccessKey \
  --namespace-name wellintakebus-standard \
  --resource-group TheWell-Infra-East \
  --query primaryConnectionString -o tsv)

# Use with --connection-string flag
python scripts/clear_digest_queue.py --action list \
  --connection-string "$SB_CONN"
```

### Method 3: Managed Identity (Production / Container Apps)

**Prerequisites**:
- Running from Azure Container App with managed identity enabled
- Managed identity has `Azure Service Bus Data Receiver` role

**Usage**:
```bash
# No additional configuration needed
python scripts/clear_digest_queue.py --action list
```

## Common Operations

### 1. Investigate DLQ Messages

**When**: DLQ alert triggers (dead-letter count > 0 for 5+ minutes)

**Steps**:
```bash
# 1. Check DLQ count
az servicebus queue show \
  --name teams-digest-requests \
  --namespace-name wellintakebus-standard \
  --resource-group TheWell-Infra-East \
  --query "countDetails.deadLetterMessageCount"

# 2. List DLQ messages (non-destructive peek)
python scripts/clear_digest_queue.py --action list

# 3. Analyze error patterns
python scripts/clear_digest_queue.py --action list | grep "Reason:"
# Common reasons:
# - ProcessingException: Worker threw unhandled exception
# - InvalidMessageFormat: Message body failed Pydantic validation
# - DeliveryCountExceeded: Exceeded maxDeliveryCount (3 retries)
```

**Example Output**:
```
📊 Found 5 messages in DLQ:

1. Message ID: abc-123
   Enqueued: 2025-10-14 15:30:00
   Delivery Count: 3
   Reason: ProcessingException
   Description: TypeError: BotFrameworkAdapter.send_activity(): conversation.id can not be None
   Correlation ID: req-12345
```

### 2. Requeue Messages After Fix

**When**: Bug fixed in worker, need to reprocess DLQ messages

**Steps**:
```bash
# 1. Deploy fixed worker revision
az containerapp update --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/teams-digest-worker:latest \
  --revision-suffix "v$(date +%Y%m%d-%H%M%S)"

# 2. Wait for new revision to be ready
az containerapp revision list --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --query "[0].{name:name,state:properties.healthState}" -o table

# 3. Requeue DLQ messages (with confirmation prompt)
python scripts/clear_digest_queue.py --action requeue
# Type: REQUEUE

# 4. Monitor KEDA scaling and worker logs
watch -n 5 'az containerapp replica list \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --query "[].{name:name,state:properties.runningState}" -o table'

az containerapp logs show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --follow
```

**Expected Behavior**:
- ✅ Messages moved from DLQ to active queue
- ✅ KEDA spawns 4-5 replicas in ~60 seconds
- ✅ Worker logs show successful processing
- ✅ DLQ count returns to 0

**Important Notes**:
- **Batch Processing**: Requeue sends 10 messages per API call (90% faster than single-message)
- **Automatic Fallback**: If batch exceeds 256 KB, automatically falls back to single-message sends with warning:
  ```
  ⚠️  Batch too large, falling back to single-message sends...
  ```
- **Property Preservation**: All message properties preserved (correlation_id, TTL, application_properties)
- **Body Integrity**: Uses `normalize_message_body()` to extract actual JSON payload (not metadata string)
- **Message ID Handling**:
  - Default behavior preserves original `message_id` for idempotency
  - If queue has duplicate detection enabled, use `--regenerate-message-ids` to generate new UUIDs:
    ```bash
    python scripts/clear_digest_queue.py --action requeue --regenerate-message-ids
    ```

### 3. Purge Invalid Messages

**When**: Messages are permanently invalid (e.g., malformed data, test messages)

**Steps**:
```bash
# 1. Confirm messages are invalid
python scripts/clear_digest_queue.py --action list | less

# 2. Purge with confirmation
python scripts/clear_digest_queue.py --action purge
# Type: PURGE

# 3. Verify cleanup
az servicebus queue show \
  --name teams-digest-requests \
  --namespace-name wellintakebus-standard \
  --resource-group TheWell-Infra-East \
  --query "countDetails.deadLetterMessageCount"
# Expected: 0
```

**Automation Example** (for known test scenarios):
```bash
# Skip confirmation prompt for automation
python scripts/clear_digest_queue.py --action purge --yes
```

### 4. Emergency: High DLQ Count (100+ Messages)

**When**: DLQ count exceeds 100, potential systemic issue

**Steps**:
```bash
# 1. STOP - Do not requeue yet, investigate root cause
az containerapp logs show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --tail 100 | grep "ERROR"

# 2. Sample DLQ messages
python scripts/clear_digest_queue.py --action list | head -50

# 3. Identify error pattern
python scripts/clear_digest_queue.py --action list | \
  grep "Reason:" | sort | uniq -c
# Example output:
# 95 ProcessingException
#  3 InvalidMessageFormat
#  2 DeliveryCountExceeded

# 4. Coordinate with dev team to deploy fix

# 5. After fix deployed, requeue in controlled manner
# Option A: Requeue all (will spawn max replicas)
python scripts/clear_digest_queue.py --action requeue --yes

# Option B: Purge and alert users to resubmit
python scripts/clear_digest_queue.py --action purge --yes
# Then notify users via Teams/email
```

**Performance Notes**:
- 100 messages = 10 batches (10 API calls)
- Processing time: ~3 minutes with 10 replicas
- Watch for batch size fallbacks (large payloads)

## Monitoring & Validation

### Check Queue Health
```bash
# Quick status
az servicebus queue show \
  --name teams-digest-requests \
  --namespace-name wellintakebus-standard \
  --resource-group TheWell-Infra-East \
  --query "countDetails" -o json

# Expected healthy state:
# {
#   "activeMessageCount": 0-50,  # Low during normal operation
#   "deadLetterMessageCount": 0,  # Alert if > 0 for 5+ minutes
#   "scheduledMessageCount": 0
# }
```

### Validate Worker Processing
```bash
# Check replica count (should scale down when idle)
az containerapp replica list \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --query "length(@)"
# Expected: 0 when queue empty, 1-10 when processing

# Check recent logs for errors
az containerapp logs show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --tail 50 | grep -E "(ERROR|WARNING|Failed)"
```

### Validate Message Body Integrity (After Requeue)
```bash
# Critical: Verify worker receives valid JSON, not metadata string
az containerapp logs show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --follow | grep "Processing digest request"

# ✅ Good: Should see conversation_id fields from original messages
# ❌ Bad: "invalid JSON" errors or "Message State: Received" strings
```

## Troubleshooting

### Issue: "Unauthorized access. 'Listen' claim(s) are required"

**Cause**: User/identity lacks Service Bus RBAC role

**Fix**:
```bash
# Check current roles
az role assignment list \
  --assignee $(az account show --query user.name -o tsv) \
  --scope /subscriptions/<sub-id>/resourceGroups/TheWell-Infra-East/providers/Microsoft.ServiceBus/namespaces/wellintakebus-standard

# Assign required role (requires admin)
az role assignment create \
  --assignee <user-email> \
  --role "Azure Service Bus Data Receiver" \
  --scope /subscriptions/<sub-id>/resourceGroups/TheWell-Infra-East/providers/Microsoft.ServiceBus/namespaces/wellintakebus-standard

# Alternative: Use connection string
python scripts/clear_digest_queue.py --action list \
  --connection-string "Endpoint=sb://..."
```

### Issue: "Batch too large, falling back to single-message sends"

**Cause**: 10 messages exceed Service Bus batch size limit (256 KB)

**Expected Behavior**: Tool automatically falls back to single-message sends

**No Action Required**: This is normal for large payloads. Tool handles gracefully.

**Log Output**:
```
♻️  Requeuing DLQ messages: teams-digest-requests
⚠️  Batch too large, falling back to single-message sends...
♻️  Requeued batch of 10 messages (total: 10)
```

### Issue: Messages Keep Dead-Lettering After Requeue

**Possible Causes**:
1. Worker bug not actually fixed
2. Deployment not live (wrong revision active)
3. Configuration issue (missing env vars)

**Diagnosis**:
```bash
# 1. Verify active revision
az containerapp show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --query "properties.latestRevisionName" -o tsv

# 2. Check revision image SHA
az containerapp revision show \
  --name <revision-name> \
  --resource-group TheWell-Infra-East \
  --query "properties.template.containers[0].image"

# 3. Check worker logs for same error
az containerapp logs show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --revision <revision-name> \
  --tail 100 | grep "ERROR"

# 4. If error persists, purge DLQ and escalate
python scripts/clear_digest_queue.py --action purge --yes
```

### Issue: DLQ Shows 0 Messages But Azure Portal Shows Messages

**Cause**: Replication lag in Service Bus metrics (can take 30-60 seconds)

**Fix**: Wait 1 minute and retry
```bash
sleep 60
python scripts/clear_digest_queue.py --action list
```

### Issue: Requeued Messages Immediately Rejected

**Symptoms**: Messages disappear from active queue without being processed, no worker logs

**Cause**: Queue has duplicate detection enabled and requeued messages have duplicate `message_id`

**Diagnosis**:
```bash
# Check if duplicate detection is enabled
az servicebus queue show \
  --name teams-digest-requests \
  --namespace-name wellintakebus-standard \
  --resource-group TheWell-Infra-East \
  --query "requiresDuplicateDetection"
# Output: true or false
```

**Fix**: Use `--regenerate-message-ids` flag to generate new UUIDs
```bash
# Requeue with fresh message IDs
python scripts/clear_digest_queue.py --action requeue --regenerate-message-ids

# Verify messages reach active queue
az servicebus queue show \
  --name teams-digest-requests \
  --namespace-name wellintakebus-standard \
  --resource-group TheWell-Infra-East \
  --query "countDetails.activeMessageCount"
# Expected: > 0 briefly, then processed by workers
```

**When to Use**:
- ✅ Queue has duplicate detection enabled (`requiresDuplicateDetection: true`)
- ❌ Default behavior (preserves `message_id` for idempotency tracking)

**Trade-offs**:
- ⚠️ **ID Correlation Lost**: Regenerating IDs breaks traceability between DLQ and requeued messages
  - Consider logging old→new mapping if correlation needed for debugging
  - Alternative: Preserve mapping in `application_properties` for audit trail
- ⚠️ **TTL Preservation**: Original `time_to_live` is copied; near-expiry messages may expire immediately after requeue
  - Monitor for messages that requeue but disappear quickly
  - Future enhancement: Add `--refresh-ttl` flag if this becomes a recurring issue

## Automation Examples

### Daily DLQ Health Check (Cron Job)
```bash
#!/bin/bash
# /etc/cron.daily/check-dlq-health.sh

DLQ_COUNT=$(az servicebus queue show \
  --name teams-digest-requests \
  --namespace-name wellintakebus-standard \
  --resource-group TheWell-Infra-East \
  --query "countDetails.deadLetterMessageCount" -o tsv)

if [ "$DLQ_COUNT" -gt 0 ]; then
  echo "⚠️ DLQ has $DLQ_COUNT messages" | \
    mail -s "Teams Digest DLQ Alert" ops@example.com

  # Attach DLQ sample
  python scripts/clear_digest_queue.py --action list > /tmp/dlq-sample.txt
  mail -s "DLQ Sample" -a /tmp/dlq-sample.txt ops@example.com < /dev/null
fi
```

### Post-Deployment DLQ Cleanup (CI/CD)
```bash
#!/bin/bash
# .github/workflows/deploy-digest-worker.yml

# After successful deployment
- name: Requeue DLQ Messages
  run: |
    # Wait for new revision to be ready
    sleep 30

    # Check if DLQ has messages
    DLQ_COUNT=$(az servicebus queue show \
      --name teams-digest-requests \
      --query "countDetails.deadLetterMessageCount" -o tsv)

    if [ "$DLQ_COUNT" -gt 0 ]; then
      echo "Requeuing $DLQ_COUNT DLQ messages..."
      python scripts/clear_digest_queue.py --action requeue --yes
    fi
```

## SLA Targets

| Metric | Target | Action if Exceeded |
|--------|--------|-------------------|
| DLQ Message Age | < 1 hour | Investigate and requeue/purge |
| DLQ Count | 0 messages | Alert after 5 minutes > 0 |
| Requeue Time | < 5 minutes | Check for batch size fallbacks |
| Processing After Requeue | < 10 minutes | Verify KEDA scaling and worker health |

## Escalation

**Level 1** (Operations):
- Monitor DLQ counts
- Run list/purge/requeue operations
- Check worker logs for known errors

**Level 2** (Dev Team):
- Analyze new error patterns
- Deploy worker fixes
- Validate message body integrity

**Level 3** (Platform Team):
- Service Bus infrastructure issues
- RBAC/authentication problems
- KEDA scaling failures

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-10-14 | Initial runbook with DLQ tool v1.0 | DevOps |
| 2025-10-14 | Added batch-size fallback notes | DevOps |
| 2025-10-14 | Added body integrity validation | DevOps |
| 2025-10-14 | Added duplicate detection safeguard (`--regenerate-message-ids`) | DevOps |

## References

- [DLQ Management Tool](../scripts/clear_digest_queue.py) - Script source code
- [End-to-End Test Procedure](../scripts/TEST_DLQ_TOOL.md) - Testing documentation
- [KEDA Configuration Guide](../KEDA_CONFIGURATION.md) - Complete setup documentation
- [Azure Monitor Alerts](https://portal.azure.com) - DLQ alerting configuration
- [Service Bus Documentation](https://learn.microsoft.com/en-us/azure/service-bus-messaging/)
