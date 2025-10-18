# Power BI Streaming Dataset Schemas

**Last Updated**: 2025-10-13

## Overview

This document defines the 8 streaming datasets for the Well Intake Power BI dashboard. All datasets use **Push Streaming** mode with **Historic Data Analysis** enabled.

---

## 1. Deal Processing Metrics

**Dataset Name**: `WellIntake_DealProcessing`

**Update Frequency**: Real-time (on every deal creation/update)

**Schema**:
```json
{
  "timestamp": "datetime",
  "deal_id": "string",
  "zoho_deal_id": "string",
  "candidate_name": "string",
  "company_name": "string",
  "stage": "string",
  "owner_email": "string",
  "source": "string",
  "processing_status": "string",
  "created_via": "string"
}
```

**Fields**:
- `timestamp` - When the deal was processed
- `deal_id` - Internal UUID
- `zoho_deal_id` - Zoho CRM Deal ID
- `candidate_name` - Candidate full name
- `company_name` - Company name
- `stage` - Deal stage (Qualification, Proposal, etc.)
- `owner_email` - Deal owner email
- `source` - Lead source (e.g., "Outlook Add-in", "Zoho Sync")
- `processing_status` - success/failed
- `created_via` - outlook_addin/zoho_sync/manual

---

## 2. VoIT Cost Optimization

**Dataset Name**: `WellIntake_VoIT_Costs`

**Update Frequency**: Real-time (on every AI model selection)

**Schema**:
```json
{
  "timestamp": "datetime",
  "deal_id": "string",
  "text_length": "int",
  "model_selected": "string",
  "estimated_cost_usd": "decimal",
  "actual_tokens_input": "int",
  "actual_tokens_output": "int",
  "actual_cost_usd": "decimal",
  "cache_hit": "boolean",
  "processing_time_ms": "int"
}
```

**Fields**:
- `timestamp` - When VoIT selection occurred
- `deal_id` - Associated deal ID
- `text_length` - Email/input text character count
- `model_selected` - gpt-5-nano/gpt-5-mini/gpt-5
- `estimated_cost_usd` - Pre-execution cost estimate
- `actual_tokens_input` - Actual input tokens used
- `actual_tokens_output` - Actual output tokens used
- `actual_cost_usd` - Actual API cost
- `cache_hit` - Whether C³ cache was used
- `processing_time_ms` - Total processing time

**Calculated Metrics**:
- Cost savings vs always using gpt-5
- Average cost per deal
- Model selection distribution

---

## 3. C³ Cache Performance

**Dataset Name**: `WellIntake_C3_Cache`

**Update Frequency**: Real-time (on every cache operation)

**Schema**:
```json
{
  "timestamp": "datetime",
  "deal_id": "string",
  "cache_operation": "string",
  "cache_hit": "boolean",
  "cache_age_hours": "decimal",
  "confidence_score": "decimal",
  "rebuild_triggered": "boolean",
  "cost_saved_usd": "decimal"
}
```

**Fields**:
- `timestamp` - When cache operation occurred
- `deal_id` - Associated deal ID
- `cache_operation` - lookup/rebuild/invalidate
- `cache_hit` - true if cache was used
- `cache_age_hours` - Age of cached entry (if hit)
- `confidence_score` - C³ confidence score (0-1)
- `rebuild_triggered` - Whether rebuild was needed
- `cost_saved_usd` - Cost saved by using cache

**Calculated Metrics**:
- Cache hit rate (target: 90%)
- Average cost savings per cached request
- Rebuild frequency

---

## 4. Learning System Accuracy

**Dataset Name**: `WellIntake_Learning_Accuracy`

**Update Frequency**: Real-time (on every AI correction)

**Schema**:
```json
{
  "timestamp": "datetime",
  "deal_id": "string",
  "field_name": "string",
  "ai_value": "string",
  "corrected_value": "string",
  "correction_type": "string",
  "pattern_learned": "boolean",
  "confidence_before": "decimal",
  "confidence_after": "decimal"
}
```

**Fields**:
- `timestamp` - When correction occurred
- `deal_id` - Associated deal ID
- `field_name` - Field that was corrected (company_name, job_title, etc.)
- `ai_value` - Original AI extraction
- `corrected_value` - User-corrected value
- `correction_type` - manual/automated
- `pattern_learned` - Whether pattern was added to learning_patterns table
- `confidence_before` - AI confidence before correction
- `confidence_after` - Updated confidence after learning

**Calculated Metrics**:
- Accuracy rate by field
- Learning improvement over time
- Most commonly corrected fields

---

## 5. Data Quality & Sync Health

**Dataset Name**: `WellIntake_DataQuality`

**Update Frequency**: 15-minute intervals (via multi-module zoho_sync_scheduler.py)

**Schema**:
```json
{
  "timestamp": "datetime",
  "sync_type": "string",
  "sync_status": "string",
  "records_synced": "int",
  "records_created": "int",
  "records_updated": "int",
  "records_failed": "int",
  "sync_duration_seconds": "int",
  "duplicates_detected": "int",
  "data_quality_score": "decimal"
}
```

**Fields**:
- `timestamp` - Sync completion time
- `sync_type` - deals/contacts/accounts
- `sync_status` - success/partial_failure/failed
- `records_synced` - Total records processed
- `records_created` - New records inserted
- `records_updated` - Existing records updated
- `records_failed` - Failed operations
- `sync_duration_seconds` - Sync execution time
- `duplicates_detected` - Number of duplicates found
- `data_quality_score` - Calculated quality score (0-100)

**Data Quality Score Formula**:
```
quality_score = (
    (records_synced - records_failed) / records_synced * 100
) * 0.7 + (
    (1 - duplicates_detected / records_synced) * 100
) * 0.3
```

---

## 6. Deal Pipeline Analytics

**Dataset Name**: `WellIntake_Pipeline`

**Update Frequency**: Daily aggregate (end of day batch)

**Schema**:
```json
{
  "date": "datetime",
  "stage": "string",
  "owner_email": "string",
  "deal_count": "int",
  "avg_deal_value": "decimal",
  "conversion_rate": "decimal",
  "avg_time_in_stage_days": "decimal"
}
```

**Fields**:
- `date` - Snapshot date
- `stage` - Deal stage
- `owner_email` - Deal owner
- `deal_count` - Number of deals in stage
- `avg_deal_value` - Average deal amount
- `conversion_rate` - % converted to next stage
- `avg_time_in_stage_days` - Average days in current stage

---

## 7. User Activity Metrics

**Dataset Name**: `WellIntake_UserActivity`

**Update Frequency**: Real-time (on user actions)

**Schema**:
```json
{
  "timestamp": "datetime",
  "user_email": "string",
  "action_type": "string",
  "resource_type": "string",
  "resource_id": "string",
  "source": "string",
  "success": "boolean"
}
```

**Fields**:
- `timestamp` - Action timestamp
- `user_email` - User performing action
- `action_type` - create/update/delete/view
- `resource_type` - deal/contact/account
- `resource_id` - ID of affected resource
- `source` - outlook_addin/web_ui/api/zoho_sync
- `success` - Whether action succeeded

---

## 8. Email Alert Triggers

**Dataset Name**: `WellIntake_EmailAlerts`

**Update Frequency**: Real-time (when alerts are sent)

**Schema**:
```json
{
  "timestamp": "datetime",
  "alert_type": "string",
  "alert_severity": "string",
  "triggered_by": "string",
  "recipient_emails": "string",
  "alert_message": "string",
  "resolved": "boolean"
}
```

**Fields**:
- `timestamp` - Alert sent time
- `alert_type` - sync_failure/duplicate_detected/data_quality_low/cost_spike
- `alert_severity` - info/warning/critical
- `triggered_by` - System component that triggered alert
- `recipient_emails` - Comma-separated list (steve@,daniel.romitelli@,brandon@)
- `alert_message` - Alert description
- `resolved` - Whether issue was resolved

**Alert Rules**:
1. **Sync Failure**: Trigger if sync_status = 'failed' for 2 consecutive hours
2. **Duplicate Detected**: Trigger if >10 duplicates found in single sync
3. **Data Quality Low**: Trigger if data_quality_score < 85
4. **Cost Spike**: Trigger if daily AI costs exceed $5 USD

---

## Environment Variables

Add to `.env.local`:

```bash
# Power BI Configuration
ENABLE_POWERBI_LOGGING=false
POWERBI_WORKSPACE_ID=your-workspace-id
POWERBI_DATASET_DEAL_PROCESSING=dataset-id-1
POWERBI_DATASET_VOIT_COSTS=dataset-id-2
POWERBI_DATASET_C3_CACHE=dataset-id-3
POWERBI_DATASET_LEARNING_ACCURACY=dataset-id-4
POWERBI_DATASET_DATA_QUALITY=dataset-id-5
POWERBI_DATASET_PIPELINE=dataset-id-6
POWERBI_DATASET_USER_ACTIVITY=dataset-id-7
POWERBI_DATASET_EMAIL_ALERTS=dataset-id-8

# Alert Configuration
ALERT_RECIPIENTS=steve@emailthewell.com,daniel.romitelli@emailthewell.com,brandon@emailthewell.com
ALERT_SYNC_FAILURE_THRESHOLD_HOURS=2
ALERT_DUPLICATE_THRESHOLD=10
ALERT_QUALITY_SCORE_THRESHOLD=85
ALERT_COST_SPIKE_THRESHOLD_USD=5.0
```

---

## Setup Instructions

### 1. Create Datasets in Power BI Premium

For each of the 8 datasets:

1. Go to Power BI workspace
2. Click **+ New** → **Streaming dataset**
3. Select **API** as source
4. Enable **Historic data analysis**
5. Copy the schema JSON for each dataset
6. Save and copy the dataset ID
7. Add dataset ID to `.env.local`

### 2. Enable Logging

Set `ENABLE_POWERBI_LOGGING=true` in production `.env`.

### 3. Deploy to Azure

Deploy updated container with Power BI integration:

```bash
docker build -t wellintakeacr0903.azurecr.io/well-intake-api:powerbi .
az acr login --name wellintakeacr0903
docker push wellintakeacr0903.azurecr.io/well-intake-api:powerbi
az containerapp update --name well-intake-api \
  --resource-group TheWell-Infra-East \
  --image wellintakeacr0903.azurecr.io/well-intake-api:powerbi \
  --set-env-vars ENABLE_POWERBI_LOGGING=true
```

### 4. Create Dashboard

1. Create new Power BI report
2. Connect to all 8 streaming datasets
3. Build visualizations:
   - Deal processing success rate (line chart)
   - VoIT cost savings (card + line chart)
   - C³ cache hit rate (gauge)
   - Learning accuracy trends (line chart)
   - Data quality score (gauge)
   - Pipeline funnel (funnel chart)
   - User activity heatmap (matrix)
   - Recent alerts (table)

---

## Dashboard Refresh Rates

- **Real-time tiles**: Refresh every 1 second
- **Historic data visuals**: Refresh every 15 minutes
- **Daily aggregates**: Refresh once per day at midnight

---

## Monitoring

Track these KPIs:

1. **Deal Processing Success Rate**: Target >95%
2. **VoIT Cost Savings**: Track monthly trend
3. **C³ Cache Hit Rate**: Target >90%
4. **Learning Accuracy**: Track improvement over time
5. **Data Quality Score**: Maintain >90
6. **Sync Success Rate**: Target 100%
7. **Alert Response Time**: Track time to resolution

---

## Troubleshooting

### Dataset not receiving data

1. Check `ENABLE_POWERBI_LOGGING=true` in container app
2. Verify dataset IDs in environment variables
3. Check container logs for Power BI errors
4. Verify Azure Communication Services credentials

### High cost alerts

1. Review VoIT model selection distribution
2. Check C³ cache hit rate
3. Verify text length distributions
4. Consider adjusting COMPLEXITY_THRESHOLDS

### Low data quality score

1. Run duplicate detection: `python3 app/admin/detect_duplicates.py`
2. Check zoho_sync_history for failures
3. Review learning_patterns for accuracy issues
4. Investigate failed records in sync logs
