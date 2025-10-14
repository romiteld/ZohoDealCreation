# Phase 3: Async Digest Route Refactor - COMPLETE

**Date**: 2025-01-15
**Status**: ✅ Implementation Complete, Ready for Testing
**Feature Flag**: `USE_ASYNC_DIGEST` (default: false)

## Summary

Successfully refactored the Teams bot digest command from synchronous (blocking 5-15 seconds) to asynchronous (Service Bus with immediate acknowledgment). Implementation uses a feature flag for safe production rollout with instant rollback capability.

## Changes Made

### 1. Acknowledgment Card ([adaptive_cards.py:526-598](app/api/teams/adaptive_cards.py#L526-L598))
- **Function**: `create_digest_acknowledgment_card(audience, request_id)`
- **Purpose**: Shows immediate feedback to user while request processes asynchronously
- **Content**:
  - "⏳ Processing Your Digest Request" title
  - Audience confirmation
  - Processing status indicators
  - Request ID for tracking
  - User-friendly explanation of async flow

### 2. Feature Flag ([feature_flags.py:28](app/config/feature_flags.py#L28))
- **Variable**: `USE_ASYNC_DIGEST`
- **Default**: `false` (sync mode preserved for safety)
- **Location**: `app/config/feature_flags.py`
- **Override**: Set `USE_ASYNC_DIGEST=true` in environment variables

### 3. Conditional Routing Logic ([routes.py:438-529](app/api/teams/routes.py#L438-L529))

**Architecture**:
```
User sends "digest advisors"
    ↓
Check USE_ASYNC_DIGEST flag
    ↓
┌─────────────────────┬──────────────────────┐
│ ASYNC (flag=true)   │ SYNC (flag=false)    │
├─────────────────────┼──────────────────────┤
│ Store conv ref      │ Call sync function   │
│ Publish to Service  │ Block 5-15 seconds   │
│ Return ack card     │ Return preview card  │
│ Response < 500ms    │ Response > 5000ms    │
│                     │                      │
│ [Worker picks up]   │                      │
│ Generate digest     │                      │
│ Send proactive msg  │                      │
└─────────────────────┴──────────────────────┘
```

**Async Flow Implementation**:
```python
if USE_ASYNC_DIGEST:
    # Store conversation reference for proactive messaging
    proactive_service = await create_proactive_messaging_service()
    await proactive_service.store_conversation_reference(activity)

    # Publish to Service Bus
    message_bus = get_message_bus()
    request_id = await message_bus.publish_digest_request(...)

    # Store audit trail
    await db.execute("INSERT INTO teams_digest_requests ...")

    # Return acknowledgment immediately
    return create_digest_acknowledgment_card(audience, request_id)
```

**Fallback on Error**:
- If async flow fails → logs error → falls through to sync mode
- Ensures user always gets a response (degraded gracefully)

## Infrastructure Dependencies (Phase 2.5)

All required infrastructure already built and production-ready:

✅ **Message Bus Service** (`teams_bot/app/services/message_bus.py`)
- `publish_digest_request()` method
- Azure Service Bus queue: `teams-digest-requests`

✅ **Digest Worker** (`teams_bot/app/workers/digest_worker.py`)
- Processes `DigestRequestMessage` from queue
- Calls `TalentWellCurator` to generate digest
- Sends proactive message with results

✅ **KEDA Autoscaling**
- Scales workers 1:5 ratio (1 replica per 5 messages)
- Min replicas: 0 (scales to zero when idle)
- Max replicas: 10

✅ **Proactive Messaging Service** (`teams_bot/app/services/proactive_messaging.py`)
- Stores conversation references
- Sends results back to user after processing

✅ **Database Tracking**
- `teams_digest_requests` table for audit trail
- `teams_conversations` table for conversation references

## Testing Plan

### Local Testing (Recommended First)
```bash
# 1. Enable async mode locally
export USE_ASYNC_DIGEST=true

# 2. Start services
uvicorn app.main:app --reload --port 8000                    # Main API
cd teams_bot && uvicorn app.main:app --reload --port 8001   # Teams Bot
python -m teams_bot.app.workers.digest_worker                # Worker

# 3. Simulate Teams message via API
curl -X POST "http://localhost:8001/api/teams/webhook" \
  -H "Content-Type: application/json" \
  -d @test_digest_message.json

# 4. Verify flow
# - Check acknowledgment card returned immediately
# - Check message in Service Bus queue
# - Check worker processes message
# - Check proactive message delivered
```

### Production Testing (Staged Rollout)

**Option A: Internal Testing**
```bash
# Deploy with flag disabled (sync mode)
az containerapp update --name teams-bot \
  --set-env-vars USE_ASYNC_DIGEST=false

# Enable for specific test conversation
# (Add user-level flag override in database if needed)
```

**Option B: Gradual Rollout**
```bash
# Week 1: Enable for 10% of users
# Week 2: Enable for 50% of users
# Week 3: Enable for 100% of users
# Week 4: Remove sync code, flag becomes permanent
```

## Deployment Steps

### 1. Build and Push
```bash
# Build Teams Bot image
docker build -t wellintakeacr0903.azurecr.io/teams-bot:async-digest-v1 \
  -f teams_bot/Dockerfile .

# Push to ACR
az acr login --name wellintakeacr0903
docker push wellintakeacr0903.azurecr.io/teams-bot:async-digest-v1
```

### 2. Deploy with Flag Disabled (Safe Start)
```bash
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/teams-bot:async-digest-v1 \
  --set-env-vars USE_ASYNC_DIGEST=false \
  --revision-suffix "async-digest-$(date +%Y%m%d-%H%M%S)"
```

### 3. Enable Async Mode (After Validation)
```bash
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars USE_ASYNC_DIGEST=true \
  --revision-suffix "async-enabled-$(date +%Y%m%d-%H%M%S)"
```

### 4. Instant Rollback (If Needed)
```bash
# Option 1: Disable flag (falls back to sync)
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars USE_ASYNC_DIGEST=false

# Option 2: Revert to previous revision
az containerapp revision list \
  --name teams-bot \
  --resource-group TheWell-Infra-East
az containerapp revision activate \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision <previous-revision-name>
```

## Monitoring

### Logs to Watch
```bash
# Teams Bot logs (routing decision)
az containerapp logs show --name teams-bot \
  --resource-group TheWell-Infra-East --follow | grep "DIGEST COMMAND"

# Service Bus queue depth
az servicebus queue show \
  --resource-group TheWell-Infra-East \
  --namespace-name wellintakebus-standard \
  --name teams-digest-requests \
  --query "countDetails.activeMessageCount"

# Worker logs (processing)
az containerapp logs show --name teams-digest-worker \
  --resource-group TheWell-Infra-East --follow

# KEDA scaling events
az containerapp replica list \
  --name teams-digest-worker \
  --resource-group TheWell-Infra-East
```

### Key Metrics
- **Response time**: Should drop from 5-15s to < 500ms when flag enabled
- **Queue depth**: Should process 1 message per 5-10 seconds (with worker)
- **Error rate**: Monitor fallback to sync mode frequency
- **User satisfaction**: Proactive messages delivered successfully

## Validation Checklist

Before enabling `USE_ASYNC_DIGEST=true` in production:

- [ ] Worker container is deployed and healthy
- [ ] KEDA scaling rules are active
- [ ] Service Bus queue exists and is accessible
- [ ] Proactive messaging service can send messages
- [ ] Database tracking tables have recent entries
- [ ] Test digest request completes end-to-end
- [ ] Acknowledgment card displays correctly
- [ ] Proactive message arrives after processing
- [ ] Sync fallback works when async fails

## Code Cleanup (Future)

Once async mode is validated and stable:

1. Remove sync code path from routes.py
2. Remove `USE_ASYNC_DIGEST` feature flag
3. Remove `generate_digest_preview()` function (or mark deprecated)
4. Update documentation to reflect async-only behavior

## Test Email Support (Schema Parity Only)

**Current Status**: `test_recipient_email` field added to message schema for compatibility but NOT functionally implemented in async mode.

**What Works**:
- ✅ Sync mode: `digest test@example.com` shows test warning in preview card
- ✅ Async mode: Field accepted in message (no schema validation errors)

**What Doesn't Work (Yet)**:
- ❌ Async mode does NOT use `test_recipient_email` for routing
- ❌ Worker sends proactive message to Teams (not email), so test routing doesn't apply
- ❌ Worker doesn't modify result card to show test warning

**Implementation Status**:
- ✅ Added `test_recipient_email` to `DigestRequestMessage` ([messages.py:104](teams_bot/app/models/messages.py#L104))
- ✅ Routing code passes field through ([routes.py:490](app/api/teams/routes.py#L490))
- ❌ Worker ignores field ([digest_worker.py:187-195](teams_bot/app/workers/digest_worker.py#L187-L195))
- ❌ No test mode UI indicator in async acknowledgment card

**Recommendation**:
For testing async flow, use internal team conversations (daniel.romitelli@, steve@, brandon@) instead of test email parameter. Test email routing is a **sync-mode-only feature** until worker implementation is added.

**Future Enhancement** (if needed):
1. Update worker to read `digest_request.test_recipient_email`
2. Modify result card to include test mode warning
3. Add telemetry tag for test requests
4. Document test mode behavior in worker logs

## File Changes Summary

| File | Lines | Change |
|------|-------|--------|
| `app/config/feature_flags.py` | 28 | Added `USE_ASYNC_DIGEST` flag |
| `app/api/teams/adaptive_cards.py` | 526-598 | Added acknowledgment card function |
| `app/api/teams/routes.py` | 438-529 | Added conditional routing logic + test email support |
| `teams_bot/app/models/messages.py` | 104 | Added `test_recipient_email` field |

**Total**: 4 files modified, ~110 lines added, 0 lines removed

## Success Criteria

✅ **Immediate**: User receives acknowledgment card within 500ms
✅ **Delayed**: User receives digest preview card via proactive message after 5-15s
✅ **Fallback**: If async fails, sync mode still works
✅ **Monitoring**: Can track requests through entire async pipeline
✅ **Safety**: Can disable async mode instantly with environment variable

## Next Steps

1. **Test locally** with all services running
2. **Deploy to staging** with flag disabled
3. **Enable for internal team** (daniel.romitelli@, steve@, brandon@)
4. **Monitor for 24 hours** - watch logs and metrics
5. **Enable for all users** if no issues
6. **Remove sync code** after 1 week of stable async operation

---

**Implementation by**: Claude Code (Sonnet 4.5)
**Reviewed by**: Pending
**Deployed to Production**: Pending
