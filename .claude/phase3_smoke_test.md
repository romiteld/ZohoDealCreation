# Phase 3 Smoke Test & Validation Guide

**Date**: 2025-10-14
**Status**: Ready for Internal Testing
**Current Mode**: SYNC (USE_ASYNC_DIGEST=false)

## Step 1: Sync Mode Smoke Test (CURRENT)

### Prerequisites
- Teams Bot deployed: `teams-bot--async-digest-20251014-164116`
- Feature flag: `USE_ASYNC_DIGEST=false`
- Container status: Running

### Test Instructions for Internal Team

**Who Should Test**:
- daniel.romitelli@emailthewell.com
- steve@emailthewell.com
- brandon@emailthewell.com

**Test Commands** (send in Teams):
1. `digest advisors`
2. `digest c_suite`
3. `digest global`

**Expected Behavior** (Sync Mode):
- ⏱️ 6-15 second wait (blocking)
- 📊 Preview card appears with candidate list
- ✅ No acknowledgment card
- ✅ No proactive message later

**What to Watch For**:
- ❌ Any errors or timeouts
- ❌ Different card format
- ❌ Missing candidates
- ❌ Unexpected acknowledgment card (would indicate async mode accidentally enabled)

### Monitoring Commands

**Real-time log monitoring** (run in terminal):
```bash
# Watch Teams Bot logs for digest commands
az containerapp logs show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --follow | grep -E "DIGEST COMMAND|USE_ASYNC_DIGEST"

# Expected output:
# "=== DIGEST COMMAND (SYNC MODE) ==="
# "Feature flag USE_ASYNC_DIGEST=False, using synchronous flow"
```

**Verify feature flag value**:
```bash
# Check current environment variables
az containerapp show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "properties.template.containers[0].env[?name=='USE_ASYNC_DIGEST'].{name:name,value:value}" -o table

# Expected: Empty or blank (defaults to false in code)
```

**Check for errors**:
```bash
# Watch for any errors in last 50 log entries
az containerapp logs show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --tail 50 | grep -i "error\|exception\|failed"
```

### Success Criteria (Sync Mode)
- [x] Container deployed successfully
- [ ] Internal team sends 3 digest commands (advisors, c_suite, global)
- [ ] All 3 commands return preview cards within 6-15 seconds
- [ ] Logs show "DIGEST COMMAND (SYNC MODE)"
- [ ] Logs show "USE_ASYNC_DIGEST=False"
- [ ] No errors in logs
- [ ] No unexpected behavior

**Once all criteria pass** → Ready for async mode enablement

---

## Step 2: Enable Async Mode for Internal Testing

### Pre-Flight Checks
Before flipping the flag, verify Phase 2.5 infrastructure:

```bash
# 1. Check Service Bus queue exists and is empty
az servicebus queue show \
  --resource-group TheWell-Infra-East \
  --namespace-name wellintakebus-standard \
  --name teams-digest-requests \
  --query "countDetails.{active:activeMessageCount,dlq:deadLetterMessageCount}" -o table

# Expected: active=0, dlq=0

# 2. Check digest worker is running
az containerapp show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --query "{name:name,status:properties.runningStatus,replicas:properties.template.scale.minReplicas}" -o table

# Expected: status=Running, replicas=0 (KEDA scales from zero)

# 3. Check KEDA scaling rules
az containerapp show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --query "properties.template.scale.rules[0].{name:name,type:type,queueName:azureQueue.queueName}" -o table

# Expected: type=azure-queue, queueName=teams-digest-requests
```

### Enable Async Mode

**Command**:
```bash
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars USE_ASYNC_DIGEST=true \
  --revision-suffix "async-enabled-$(date +%Y%m%d-%H%M%S)"
```

**Deployment Time**: ~2 minutes

**Verify Flag Enabled**:
```bash
az containerapp show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "properties.template.containers[0].env[?name=='USE_ASYNC_DIGEST']" -o table

# Expected: value=true
```

---

## Step 3: Async Mode Validation

### Test Instructions for Internal Team

**Test Commands** (send in Teams):
1. `digest advisors`
2. Wait and observe
3. `digest c_suite`
4. Wait and observe

**Expected Behavior** (Async Mode):
1. **Immediate** (< 500ms):
   - ⏳ Acknowledgment card appears
   - Title: "⏳ Processing Your Digest Request"
   - Shows audience confirmation
   - Shows request ID

2. **Delayed** (10-15 seconds):
   - 📊 Proactive message with preview card
   - Same format as sync mode
   - Contains candidate list

**What to Watch For**:
- ✅ Acknowledgment card appears immediately
- ✅ Proactive message arrives 10-15s later
- ❌ Any timeout errors
- ❌ Messages stuck in queue
- ❌ Worker errors

### Async Monitoring Dashboard

**Terminal 1 - Teams Bot Logs**:
```bash
az containerapp logs show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --follow | grep -E "DIGEST COMMAND|Published digest request|test_recipient_email"
```

**Expected Output**:
```
=== DIGEST COMMAND (ASYNC MODE) ===
Audience: advisors, User: daniel.romitelli@emailthewell.com, Conversation: ...
Feature flag USE_ASYNC_DIGEST=true, routing to Service Bus
✅ Published digest request <uuid> to Service Bus queue
```

**Terminal 2 - Service Bus Queue Depth**:
```bash
# Watch queue activity (run every 5 seconds)
watch -n 5 'az servicebus queue show \
  --resource-group TheWell-Infra-East \
  --namespace-name wellintakebus-standard \
  --name teams-digest-requests \
  --query "countDetails.{active:activeMessageCount,dlq:deadLetterMessageCount,total:totalMessageCount}" -o table'
```

**Expected Pattern**:
```
Active  DLQ  Total
------  ---  -----
0       0    0      # Before test
1       0    1      # Message published
0       0    1      # Message processed (< 15s)
0       0    1      # Idle
```

**Terminal 3 - Worker Logs**:
```bash
az containerapp logs show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --follow | grep -E "Processing digest request|Sending proactive message|test_recipient_email"
```

**Expected Output**:
```
Processing digest request <uuid> for advisors audience
Generating digest via TalentWellCurator...
Digest generated successfully, sending proactive message
✅ Proactive message sent successfully
```

**Terminal 4 - KEDA Scaling**:
```bash
# Watch replica count
watch -n 5 'az containerapp replica list \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --query "[].{name:name,state:properties.runningState,created:properties.createdTime}" -o table'
```

**Expected Pattern**:
```
# Before message: 0 replicas (scaled to zero)
# After message: 1 replica appears (KEDA scales up)
# After processing: Replica stays for ~5 minutes, then scales down
```

### Database Audit Trail

**Check digest requests table**:
```bash
# Connect to database and query
psql "postgresql://adminuser:W3llDB2025Pass@well-intake-db-0903.postgres.database.azure.com:5432/wellintake?sslmode=require" -c "
  SELECT
    request_id,
    user_email,
    audience,
    status,
    created_at,
    completed_at,
    error_message
  FROM teams_digest_requests
  WHERE created_at > NOW() - INTERVAL '1 hour'
  ORDER BY created_at DESC;
"
```

**Expected Output**:
```
request_id  | user_email              | audience  | status    | created_at           | completed_at         | error_message
------------|-------------------------|-----------|-----------|----------------------|----------------------|--------------
<uuid>      | daniel.romitelli@...    | advisors  | queued    | 2025-10-14 16:50:00  | NULL                 | NULL
<uuid>      | daniel.romitelli@...    | advisors  | completed | 2025-10-14 16:48:00  | 2025-10-14 16:48:12  | NULL
```

### Success Criteria (Async Mode)
- [ ] Acknowledgment card appears < 500ms
- [ ] Proactive message arrives 10-15 seconds later
- [ ] Teams Bot logs show "DIGEST COMMAND (ASYNC MODE)"
- [ ] Service Bus queue shows message published
- [ ] Worker logs show message processing
- [ ] KEDA scales worker replica from 0 → 1
- [ ] Database shows request status: queued → completed
- [ ] No messages in DLQ
- [ ] No errors in logs

---

## Step 4: Dead Letter Queue Management

### Check DLQ (If Messages Fail)

**List DLQ messages**:
```bash
curl -X POST "https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/admin/dlq/list" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json"
```

**Replay failed messages**:
```bash
curl -X POST "https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/admin/dlq/replay?max_messages=5" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json"
```

**Purge DLQ** (if needed):
```bash
curl -X POST "https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/teams/admin/dlq/purge" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json"
```

### Common Issues and Fixes

**Issue**: Proactive message doesn't arrive
- Check worker logs for errors
- Check conversation reference stored correctly
- Verify Bot Framework credentials

**Issue**: Worker doesn't scale
- Check KEDA scaling rules configured
- Verify Service Bus connection string
- Check queue has messages

**Issue**: Messages go to DLQ
- Check worker error logs
- Verify message schema matches
- Check database connectivity

---

## Step 5: Rollback (If Needed)

### Instant Rollback to Sync Mode
```bash
# Disable async flag (30 seconds)
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars USE_ASYNC_DIGEST=false
```

### Full Rollback to Previous Revision
```bash
# List revisions
az containerapp revision list \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "[].{name:name,active:properties.active,created:properties.createdTime}" -o table

# Activate previous stable revision
az containerapp revision activate \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision teams-bot--v20251009-002852
```

---

## Validation Checklist Summary

**Sync Mode Smoke Test**:
- [ ] Internal team sends 3 digest commands
- [ ] All return preview cards in 6-15 seconds
- [ ] Logs confirm sync mode active
- [ ] No errors

**Async Mode Validation**:
- [ ] Flag enabled successfully
- [ ] Acknowledgment cards appear immediately
- [ ] Proactive messages arrive 10-15s later
- [ ] Service Bus shows activity
- [ ] Worker processes messages
- [ ] KEDA scaling works
- [ ] Database audit trail correct
- [ ] No DLQ messages

**Once Validated**:
- [ ] Monitor for 24-48 hours
- [ ] Gradual rollout to 10% → 50% → 100%
- [ ] Remove sync code after stable

---

**Status**: Ready for internal smoke testing
**Next**: Internal team to test sync mode → Report results → Enable async flag
