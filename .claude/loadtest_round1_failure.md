# Load Test Round 1 - Critical Failure Analysis

## Date: 2025-10-14T10:32:25

### Summary
All 25 load test messages dead-lettered due to image tag mismatch. Worker code was correct but never deployed to production.

### Timeline
- **10:32:25** - Published 25 test messages to queue
- **10:32:03-10:32:19** - KEDA spawned 5 replicas (16 seconds to full scale)
- **10:32:25-10:35:00** - All messages processed with AttributeError
- **10:35:24** - Final state: 0 active, 25 dead-lettered

### Root Cause
1. ✅ Fixed code locally (removed `curator.close()` call at line 438)
2. ✅ Built image with tag `:bugfix` (SHA: `sha256:45a8f1757...`)
3. ✅ Pushed `:bugfix` tag to ACR
4. ❌ **Container App configured to pull `:latest` tag**
5. ❌ **Never updated `:latest` tag with fixed code**
6. ❌ KEDA pulled old `:latest` image with bug still present
7. ❌ All replicas crashed with: `AttributeError: 'TalentWellCurator' object has no attribute 'close'`

### KEDA Behavior Validated ✅
Despite processing failure, KEDA autoscaling worked correctly:
- Scale-up: 0 → 5 replicas in 16 seconds (target: <90s) ✅
- Replica distribution: 25 messages / 5 per replica = 5 replicas ✅
- First replica: 14:32:03
- Last replica: 14:32:19
- Scale-up duration: 16 seconds ✅

### Dead Letter Analysis
- Total messages: 25
- Dead-lettered: 25 (100%)
- Reason: `AttributeError: 'TalentWellCurator' object has no attribute 'close'`
- Delivery attempts per message: 3 (aligned with `maxDeliveryCount=3`) ✅
- Dead-letter mechanism: Working correctly ✅

### Resolution
1. Rebuilt image with `:latest` tag (SHA: `sha256:317303924496b0c821f40fb03a5d8d8f977ae64ba02b9604b19172dd66ec77de`)
2. Pushed to ACR
3. Container App will pull new `:latest` on next KEDA scale-up
4. Ready for Load Test Round 2

### Lessons Learned
1. **Always update `:latest` tag** when deploying fixes to production
2. **Image tag in Container App config must match pushed tag**
3. KEDA autoscaling validated independently of processing logic
4. Dead-letter mechanism protects against poison messages as designed

### Next Steps
1. Purge 25 dead-lettered messages from queue
2. Restart load test with clean queue
3. Verify new `:latest` image is pulled
4. Capture full success metrics
