# Power BI Dashboard Implementation Checklist

**Status**: Infrastructure Complete, Code Integration Pending
**Last Updated**: 2025-10-13

---

## ✅ Completed Tasks

### 1. Database Infrastructure
- [x] Created `zoho_user_mapping` table (10 owners)
- [x] Imported 176 production deals (March 2025+)
- [x] Created `zoho_sync_metadata` table
- [x] Created `zoho_sync_history` table for audit trail
- [x] Added unique index on `deals.zoho_deal_id`
- [x] Cleaned duplicate deals (removed 3 duplicates, 70 test deals)

### 2. Background Jobs
- [x] Created `zoho_sync_scheduler.py` (hourly sync with Zoho CRM)
- [x] Implemented sync metadata tracking
- [x] Added sync history logging

### 3. Data Quality
- [x] Created `detect_duplicates.py` with 90% fuzzy matching
- [x] Generated `duplicates_report_2025_10_13.csv`
- [x] Found 4 duplicate pairs (Rob Russell, Katie Lortie, Rebecca Dunne, BML/Tradition)

### 4. Documentation
- [x] Created `POWERBI_DATASET_SCHEMAS.md` with 8 streaming datasets
- [x] Documented all schema fields and calculated metrics
- [x] Added environment variable configuration
- [x] Added setup instructions and troubleshooting guide

---

## ⏳ Pending Tasks (Code Integration Required)

### Task 8: Instrument app/main.py with Power BI Telemetry

**File**: [app/main.py](../app/main.py)

**Integration Points**:

1. **After successful deal creation** (line ~1600):
```python
try:
    if os.getenv('ENABLE_POWERBI_LOGGING') == 'true':
        from app.powerbi_integration import log_deal_processing
        await log_deal_processing({
            'timestamp': datetime.now(),
            'deal_id': deal.id,
            'zoho_deal_id': zoho_response.get('data', [{}])[0].get('id'),
            'candidate_name': extracted_data.candidate_name,
            'company_name': extracted_data.company_name,
            'stage': extracted_data.stage,
            'owner_email': extracted_data.owner_email,
            'source': 'Outlook Add-in',
            'processing_status': 'success',
            'created_via': 'outlook_addin'
        })
except Exception as e:
    logger.error(f"Power BI logging failed (non-blocking): {e}")
```

2. **On processing failure** (line ~1650):
```python
try:
    if os.getenv('ENABLE_POWERBI_LOGGING') == 'true':
        from app.powerbi_integration import log_deal_processing
        await log_deal_processing({
            'timestamp': datetime.now(),
            'deal_id': None,
            'zoho_deal_id': None,
            'candidate_name': extracted_data.candidate_name if extracted_data else None,
            'company_name': extracted_data.company_name if extracted_data else None,
            'stage': None,
            'owner_email': None,
            'source': 'Outlook Add-in',
            'processing_status': 'failed',
            'created_via': 'outlook_addin'
        })
except Exception as e:
    logger.error(f"Power BI logging failed (non-blocking): {e}")
```

**Safety Rules**:
- ✅ All telemetry wrapped in try/except blocks
- ✅ Feature flag: `ENABLE_POWERBI_LOGGING` (default: false)
- ✅ Non-blocking: failures don't affect deal creation
- ✅ Zero changes to existing business logic

---

### Task 9: Add VoIT and C³ Logging to langgraph_manager.py

**File**: [app/langgraph_manager.py](../app/langgraph_manager.py)

**Integration Points**:

1. **After VoIT model selection** (in extraction node):
```python
try:
    if os.getenv('ENABLE_POWERBI_LOGGING') == 'true':
        from app.powerbi_integration import log_voit_cost
        await log_voit_cost({
            'timestamp': datetime.now(),
            'deal_id': state.get('deal_id'),
            'text_length': len(state['email_content']),
            'model_selected': selected_model,
            'estimated_cost_usd': estimated_cost,
            'actual_tokens_input': response.usage.prompt_tokens,
            'actual_tokens_output': response.usage.completion_tokens,
            'actual_cost_usd': calculate_actual_cost(response.usage, selected_model),
            'cache_hit': state.get('cache_hit', False),
            'processing_time_ms': processing_time_ms
        })
except Exception as e:
    logger.error(f"VoIT logging failed (non-blocking): {e}")
```

2. **After C³ cache operation** (in cache check):
```python
try:
    if os.getenv('ENABLE_POWERBI_LOGGING') == 'true':
        from app.powerbi_integration import log_c3_cache
        await log_c3_cache({
            'timestamp': datetime.now(),
            'deal_id': state.get('deal_id'),
            'cache_operation': 'lookup',
            'cache_hit': cache_hit,
            'cache_age_hours': cache_age_hours if cache_hit else None,
            'confidence_score': confidence_score,
            'rebuild_triggered': rebuild_triggered,
            'cost_saved_usd': cost_saved if cache_hit else 0
        })
except Exception as e:
    logger.error(f"C³ logging failed (non-blocking): {e}")
```

**Safety Rules**:
- ✅ All telemetry wrapped in try/except blocks
- ✅ Feature flag: `ENABLE_POWERBI_LOGGING` (default: false)
- ✅ Non-blocking: failures don't affect AI processing
- ✅ Zero changes to existing LangGraph workflow

---

### Task 10: Update .env.local Template

**File**: `.env.local.example`

**Add these sections**:

```bash
# ========================================
# Power BI Configuration
# ========================================
ENABLE_POWERBI_LOGGING=false
POWERBI_WORKSPACE_ID=your-workspace-id-here
POWERBI_DATASET_DEAL_PROCESSING=dataset-id-1
POWERBI_DATASET_VOIT_COSTS=dataset-id-2
POWERBI_DATASET_C3_CACHE=dataset-id-3
POWERBI_DATASET_LEARNING_ACCURACY=dataset-id-4
POWERBI_DATASET_DATA_QUALITY=dataset-id-5
POWERBI_DATASET_PIPELINE=dataset-id-6
POWERBI_DATASET_USER_ACTIVITY=dataset-id-7
POWERBI_DATASET_EMAIL_ALERTS=dataset-id-8

# ========================================
# Alert Configuration
# ========================================
ALERT_RECIPIENTS=steve@emailthewell.com,daniel.romitelli@emailthewell.com,brandon@emailthewell.com
ALERT_SYNC_FAILURE_THRESHOLD_HOURS=2
ALERT_DUPLICATE_THRESHOLD=10
ALERT_QUALITY_SCORE_THRESHOLD=85
ALERT_COST_SPIKE_THRESHOLD_USD=5.0

# ========================================
# Zoho Sync Configuration
# ========================================
ZOHO_SYNC_INTERVAL_HOURS=1
ZOHO_SYNC_ENABLED=false
```

---

## 📋 Deployment Steps

### Step 1: Create Power BI Datasets

1. Log into Power BI Premium workspace
2. Create 8 streaming datasets using schemas in `POWERBI_DATASET_SCHEMAS.md`
3. Copy dataset IDs to `.env.local`

### Step 2: Enable Background Sync

1. Add to Azure Container App environment:
```bash
az containerapp update --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --set-env-vars ZOHO_SYNC_ENABLED=true ZOHO_SYNC_INTERVAL_HOURS=1
```

2. Start background job:
```bash
# In container startup
python3 app/jobs/zoho_sync_scheduler.py &
```

### Step 3: Test Telemetry (Staging First)

1. Set `ENABLE_POWERBI_LOGGING=true` in staging
2. Process 20 test emails via Outlook Add-in
3. Verify data appears in Power BI streaming datasets
4. Check for any errors in container logs

### Step 4: Enable in Production

1. Set `ENABLE_POWERBI_LOGGING=true` in production
2. Monitor for 24 hours
3. Verify dashboard updates correctly
4. Check alert emails are sent

### Step 5: Create Dashboard

1. Create new Power BI report
2. Add visualizations for all 8 datasets
3. Configure automatic refresh (1 sec for real-time, 15 min for historic)
4. Share with Steve, Brandon, Daniel

---

## 🔍 Current Database Status

```
Total Deals: 176 (March 1, 2025 - October 3, 2025)

Owner Breakdown:
  Steve Perry: 95 deals
  Jay Robinson: 48 deals
  Ashley Price: 13 deals
  Jason Sebastian: 12 deals
  Wesley Pennock: 6 deals
  Steven Marple: 2 deals

Duplicates Found: 4 pairs
Test Deals Removed: 70 (Daniel Romitelli)
```

---

## ⚠️ Important Notes

1. **NO changes to Outlook Add-in code** - Add-in still works perfectly
2. **All telemetry is non-blocking** - Failures won't affect deal creation
3. **Feature flag protected** - Enable only when ready
4. **Deploy to staging first** - Test before production
5. **Rollback plan** - Set `ENABLE_POWERBI_LOGGING=false` to disable

---

## 📊 Expected Results

After full deployment:

- **Real-time dashboard** showing deal processing metrics
- **Cost optimization insights** from VoIT model selection
- **Cache performance tracking** (90% hit rate target)
- **Learning system accuracy** trends over time
- **Automatic email alerts** for sync failures, duplicates, quality issues
- **Data quality monitoring** with sync health tracking

---

## 🚀 Next Steps for User

1. **Create 8 Power BI streaming datasets** using schemas in documentation
2. **Add dataset IDs to container app environment variables**
3. **Decide on deployment timeline** (staging vs production)
4. **Review instrumentation code** before integration
5. **Test in staging environment first**
6. **Enable in production** after successful staging test

---

## 📞 Support

If issues occur:

1. Check container logs: `az containerapp logs show --name well-intake-api --follow`
2. Disable telemetry: Set `ENABLE_POWERBI_LOGGING=false`
3. Check Power BI dataset health in workspace
4. Verify Azure Communication Services for email alerts
5. Review zoho_sync_history table for sync failures

---

**Status Summary**: All infrastructure and documentation complete. Code integration pending user approval and staging deployment.