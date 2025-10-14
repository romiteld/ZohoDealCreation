# Phase 3 Deployment Log

**Date**: 2025-10-14
**Deployed By**: Claude Code (Sonnet 4.5)
**Status**: ✅ DEPLOYED TO PRODUCTION (Flag Disabled - Sync Mode Active)

## Deployment Summary

Successfully deployed Phase 3 async digest feature to production with feature flag **disabled** for safe rollout.

### Deployment Details

**Container Image**:
- Name: `wellintakeacr0903.azurecr.io/teams-bot:async-digest-v1`
- Digest: `sha256:bf9e9077b3d5ffb8ebc24e6d494f39b64a46302bfe2ffae5da2c337fa17f138a`
- Build Time: 2025-10-14 16:40:00 UTC

**Container App**:
- Name: `teams-bot`
- Resource Group: `TheWell-Infra-East`
- Revision: `teams-bot--async-digest-20251014-164116`
- Status: **Running**
- FQDN: `teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io`

**Feature Flag Configuration**:
- `USE_ASYNC_DIGEST=false` (explicitly set in environment variables)
- **Current Behavior**: Synchronous digest generation (legacy mode)
- **Async Mode**: Available but disabled, ready for activation

### Verification Checklist

**Pre-Deployment**:
- [x] Docker image built successfully
- [x] Image pushed to ACR
- [x] Feature flag defaults to `false`
- [x] Documentation updated with correct env var name (`USE_ASYNC_DIGEST`)
- [x] Test email limitation documented

**Post-Deployment**:
- [x] Container app deployed successfully
- [x] Latest revision active: `teams-bot--async-digest-20251014-164116`
- [x] Container status: Running
- [ ] **PENDING**: Test sync mode in Teams (send "digest advisors")
- [ ] **PENDING**: Verify sync behavior unchanged
- [ ] **PENDING**: Enable async flag for internal testing

## Current Architecture

```
User sends "digest advisors" in Teams
    ↓
[routes.py] Check USE_ASYNC_DIGEST flag
    ↓
USE_ASYNC_DIGEST=false → SYNC MODE (ACTIVE)
    ↓
[generate_digest_preview()] Runs synchronously
    ↓
[TalentWellCurator] Generates digest (blocks 5-15s)
    ↓
[Returns preview card] User receives result immediately
```

## Next Steps - Staged Rollout

### Step 1: Verify Sync Mode (CURRENT STEP)
**Action**: Test digest command in Teams to confirm sync mode still works
```bash
# In Teams, send:
digest advisors

# Expected behavior:
# - 5-15 second wait
# - Preview card with candidates
# - No acknowledgment card
# - Logs should show "DIGEST COMMAND (SYNC MODE)"
```

**Verification**:
```bash
# Check logs for sync mode confirmation
az containerapp logs show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --follow | grep "DIGEST COMMAND"
```

### Step 2: Enable Async for Internal Testing
**Action**: Flip flag to enable async mode
```bash
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars USE_ASYNC_DIGEST=true \
  --revision-suffix "async-enabled-$(date +%Y%m%d-%H%M%S)"
```

**Who Should Test**:
- daniel.romitelli@emailthewell.com
- steve@emailthewell.com
- brandon@emailthewell.com

**What to Test**:
1. Send `digest advisors` in Teams
2. Expect immediate acknowledgment card (< 500ms)
3. Expect proactive message with results (10-15 seconds later)
4. Verify message appears in Service Bus queue
5. Verify worker processes message
6. Check `teams_digest_requests` table for audit trail

### Step 3: Monitor Async Flow
**Monitoring Commands**:
```bash
# Teams Bot logs (routing decision)
az containerapp logs show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --follow | grep "DIGEST COMMAND"

# Service Bus queue depth
az servicebus queue show \
  --resource-group TheWell-Infra-East \
  --namespace-name wellintakebus-standard \
  --name teams-digest-requests \
  --query "countDetails.{active:activeMessageCount,dlq:deadLetterMessageCount}" -o table

# Worker logs
az containerapp logs show \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East \
  --follow | grep "DigestRequestMessage"

# Database audit trail
psql $DATABASE_URL -c "
  SELECT request_id, user_email, audience, status, created_at
  FROM teams_digest_requests
  ORDER BY created_at DESC
  LIMIT 10;
"
```

### Step 4: DLQ Tool (If Needed)
If messages fail and land in dead letter queue:
```bash
# List DLQ messages
curl -X POST "http://localhost:8001/api/teams/admin/dlq/list" \
  -H "X-API-Key: $API_KEY"

# Replay failed messages
curl -X POST "http://localhost:8001/api/teams/admin/dlq/replay?max_messages=10" \
  -H "X-API-Key: $API_KEY"

# Clear DLQ
curl -X POST "http://localhost:8001/api/teams/admin/dlq/purge" \
  -H "X-API-Key: $API_KEY"
```

### Step 5: Gradual Production Rollout
Once internal testing passes (24-48 hours):

**Week 1**: Enable for 10% of users (A/B testing)
**Week 2**: Enable for 50% of users
**Week 3**: Enable for 100% of users
**Week 4**: Remove sync code, async becomes permanent

## Rollback Plan

### Instant Rollback (30 seconds)
```bash
# Option 1: Disable flag (keeps new code, falls back to sync)
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars USE_ASYNC_DIGEST=false
```

### Full Rollback (2 minutes)
```bash
# Option 2: Revert to previous revision
az containerapp revision list \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "[].{name:name,active:properties.active,traffic:properties.trafficWeight}" -o table

# Activate previous revision
az containerapp revision activate \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision teams-bot--v20251009-002852  # Previous stable revision
```

## Success Metrics

**Sync Mode (Current)**:
- ✅ Digest command works as before
- ✅ Response time: 5-15 seconds
- ✅ No errors in logs
- ✅ Users receive preview cards

**Async Mode (After Flag Enabled)**:
- ✅ Acknowledgment card appears < 500ms
- ✅ Proactive message arrives 10-15s later
- ✅ Worker processes messages from queue
- ✅ KEDA scales workers (0 → 1+ replicas)
- ✅ No messages in DLQ
- ✅ User satisfaction maintained/improved

## Infrastructure Status

**Phase 2.5 Dependencies** (Already Deployed):
- ✅ Azure Service Bus queue: `teams-digest-requests`
- ✅ Digest worker container: `teams-digest-worker`
- ✅ KEDA autoscaling: Active (1:5 ratio)
- ✅ Proactive messaging service: Deployed
- ✅ Database tables: `teams_digest_requests`, `teams_conversations`
- ✅ DLQ management tool: Available

**Current Status**:
- Teams Bot: **Running** (sync mode)
- Digest Worker: **Running** (waiting for messages)
- Service Bus Queue: **Active** (0 messages)
- KEDA: **Monitoring** (0 replicas scaled)

---

**Deployment Status**: ✅ SUCCESS
**Next Action**: Test sync mode in Teams to verify no regressions
**Ready for**: Async flag enablement after sync verification passes

**Documentation**: [phase3_async_digest_complete.md](.claude/phase3_async_digest_complete.md)
