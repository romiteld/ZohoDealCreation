# PowerBI Monitoring Dashboard - Vault Alerts System

## Overview
Business intelligence dashboard tracking vault alerts delivery, anonymization performance, and user activity.

## Database Connection

### Connection Details
- **Server**: `well-intake-db-0903.postgres.database.azure.com`
- **Database**: `wellintake`
- **Port**: `5432`
- **Username**: `adminuser`
- **SSL Mode**: `require`

### PowerBI Desktop Connection Steps

1. **Open PowerBI Desktop**
2. **Get Data** → **Database** → **PostgreSQL database**
3. **Enter connection details**:
   ```
   Server: well-intake-db-0903.postgres.database.azure.com
   Database: wellintake
   ```
4. **Advanced options** → Add:
   ```
   sslmode=require
   ```
5. **Database authentication**:
   - Username: `adminuser`
   - Password: `W3llDB2025Pass` (get from Azure Key Vault in production)
6. **Select tables**:
   - ✅ `vault_alert_deliveries`
   - ✅ `vault_candidates` (optional, for enrichment)
   - ✅ `teams_user_preferences` (optional, for user details)

## Data Model

### Primary Table: vault_alert_deliveries

**Key Columns**:
- `delivery_id` (PK) - Unique delivery identifier
- `user_email` - Recipient email
- `audience` - advisors/c_suite/global
- `status` - scheduled/in_progress/completed/failed
- `total_candidates` - Candidates included in alert
- `advisor_cards_count` - Advisor format cards generated
- `executive_cards_count` - Executive format cards generated
- `execution_time_ms` - Generation performance
- `email_sent_at` - Delivery timestamp
- `created_at` - Request timestamp
- `error_message` - Failure details (if any)

### Relationships (Optional Enrichment)
- `vault_alert_deliveries.user_id` → `teams_user_preferences.user_id`
- Can join `vault_candidates` via TWAV numbers in `generation_metadata.twav_numbers` array

## DAX Measures

### 1. Delivery Success Rate
```dax
Delivery Success Rate =
VAR TotalDeliveries = COUNTROWS(vault_alert_deliveries)
VAR SuccessfulDeliveries = CALCULATE(
    COUNTROWS(vault_alert_deliveries),
    vault_alert_deliveries[status] = "completed"
)
RETURN
DIVIDE(SuccessfulDeliveries, TotalDeliveries, 0)
```

### 2. Average Execution Time
```dax
Avg Execution Time (sec) =
AVERAGE(vault_alert_deliveries[execution_time_ms]) / 1000
```

### 3. Total Candidates Delivered
```dax
Total Candidates Delivered =
SUM(vault_alert_deliveries[total_candidates])
```

### 4. Anonymization Performance (Proxy)
```dax
Avg Cards Per Candidate =
DIVIDE(
    SUM(vault_alert_deliveries[advisor_cards_count]) +
    SUM(vault_alert_deliveries[executive_cards_count]),
    SUM(vault_alert_deliveries[total_candidates]),
    0
)
```

### 5. Daily Active Users
```dax
Daily Active Users =
DISTINCTCOUNT(vault_alert_deliveries[user_email])
```

### 6. Failure Rate
```dax
Failure Rate =
VAR TotalDeliveries = COUNTROWS(vault_alert_deliveries)
VAR FailedDeliveries = CALCULATE(
    COUNTROWS(vault_alert_deliveries),
    vault_alert_deliveries[status] = "failed"
)
RETURN
DIVIDE(FailedDeliveries, TotalDeliveries, 0)
```

### 7. Audience Distribution
```dax
Audience % =
DIVIDE(
    CALCULATE(COUNTROWS(vault_alert_deliveries)),
    CALCULATE(COUNTROWS(vault_alert_deliveries), ALL(vault_alert_deliveries[audience])),
    0
)
```

## Recommended Visualizations

### Page 1: Executive Overview

#### Visual 1: KPI Cards (Top Row)
- **Total Deliveries** (Card visual)
  - Value: `COUNTROWS(vault_alert_deliveries)`
  - Conditional formatting: None

- **Success Rate** (Gauge visual)
  - Value: `Delivery Success Rate` measure
  - Target: `1.0` (100%)
  - Color zones:
    - Red: 0-0.90 (< 90%)
    - Yellow: 0.90-0.95 (90-95%)
    - Green: 0.95-1.0 (> 95%)

- **Total Candidates Delivered** (Card visual)
  - Value: `Total Candidates Delivered` measure

- **Daily Active Users** (Card visual)
  - Value: `Daily Active Users` measure
  - Filter: `created_at` = Today

#### Visual 2: Deliveries Over Time (Line Chart)
- **X-axis**: `created_at` (by day)
- **Y-axis**: `COUNT(delivery_id)`
- **Legend**: `status` (completed/failed/in_progress)
- **Colors**:
  - Green: completed
  - Red: failed
  - Yellow: in_progress

#### Visual 3: Success Rate Trend (Area Chart)
- **X-axis**: `created_at` (by day)
- **Y-axis**: `Delivery Success Rate` measure
- **Goal line**: 95%
- **Color**: Green gradient

#### Visual 4: Audience Distribution (Donut Chart)
- **Legend**: `audience`
- **Values**: `COUNT(delivery_id)`
- **Labels**: Show percentage

### Page 2: Performance Metrics

#### Visual 1: Execution Time Trend (Combo Chart)
- **X-axis**: `created_at` (by hour)
- **Column Y-axis**: `Avg Execution Time (sec)` measure
- **Line Y-axis**: `COUNT(delivery_id)`
- **Goal line**: 30 seconds (expected max)

#### Visual 2: Performance by Audience (Clustered Bar)
- **Y-axis**: `audience`
- **X-axis**: `Avg Execution Time (sec)` measure
- **Data labels**: Show values

#### Visual 3: Candidates Per Alert (Histogram)
- **X-axis**: `total_candidates` (bins: 0-10, 10-20, 20-30, 30+)
- **Y-axis**: `COUNT(delivery_id)`

#### Visual 4: Cards Generated (Stacked Column)
- **X-axis**: `created_at` (by day)
- **Y-axis**:
  - `SUM(advisor_cards_count)` (green)
  - `SUM(executive_cards_count)` (blue)
- **Legend**: Card type

### Page 3: Failures & Debugging

#### Visual 1: Recent Failures (Table)
- **Columns**:
  - `created_at` (formatted: MM/DD/YYYY HH:mm)
  - `user_email`
  - `audience`
  - `error_message` (truncated to 100 chars)
  - `execution_time_ms`
- **Filter**: `status` = "failed"
- **Sort**: `created_at` DESC
- **Top N**: 50 most recent

#### Visual 2: Failure Rate by Audience (Clustered Column)
- **X-axis**: `audience`
- **Y-axis**: `Failure Rate` measure
- **Goal line**: 5% (acceptable threshold)
- **Color**: Red for > 5%

#### Visual 3: Error Message Word Cloud
- **Category**: Parse `error_message` for common terms
- **Values**: `COUNT(delivery_id)`
- **Requires**: Custom visual from AppSource

#### Visual 4: Time to Failure (Scatter)
- **X-axis**: `execution_time_ms`
- **Y-axis**: `total_candidates`
- **Legend**: `status`
- **Size**: Fixed
- **Filter**: Include failed deliveries
- **Insight**: Identify if failures correlate with execution time or candidate count

### Page 4: User Activity

#### Visual 1: Top Users by Deliveries (Bar Chart)
- **Y-axis**: `user_email`
- **X-axis**: `COUNT(delivery_id)`
- **Sort**: Descending
- **Top N**: 20 users

#### Visual 2: User Engagement Heatmap (Matrix)
- **Rows**: `user_email`
- **Columns**: `WEEKDAY(created_at)` (Mon-Sun)
- **Values**: `COUNT(delivery_id)`
- **Conditional formatting**: Color scale (white to blue)

#### Visual 3: Audience Preference by User (Stacked Bar)
- **Y-axis**: `user_email` (Top 10)
- **X-axis**: `COUNT(delivery_id)`
- **Legend**: `audience`
- **Values**: Show percentage

## Filters (All Pages)

### Page-Level Filters
- **Date Range**: `created_at` (relative date filter)
  - Default: Last 30 days
  - Options: Today, Last 7 days, Last 30 days, Last 90 days, All time

- **Audience**: Multi-select slicer
  - Options: advisors, c_suite, global
  - Default: All selected

- **Status**: Multi-select slicer
  - Options: completed, failed, in_progress, scheduled
  - Default: All selected

## Refresh Schedule

### PowerBI Service Configuration
1. **Publish report** to PowerBI Service workspace
2. **Configure gateway** (if connecting from on-premises)
   - Use Azure PostgreSQL connector
   - Whitelist PowerBI Service IP ranges in Azure PostgreSQL firewall
3. **Schedule refresh**:
   - **Frequency**: Every 1 hour
   - **Time zones**: UTC
   - **Failure notifications**: Send to admin team

### Gateway-less Option (Recommended)
- Use **Azure PostgreSQL connector** (native cloud)
- No on-premises gateway required
- Configure scheduled refresh directly in PowerBI Service

## Security & Access

### Row-Level Security (RLS) - Optional
If limiting users to see only their own deliveries:

```dax
[user_email] = USERPRINCIPALNAME()
```

Apply this filter to `vault_alert_deliveries` table for non-admin users.

### Role Assignment
- **Admin Role**: Full access, no RLS filters
- **User Role**: RLS applied, see only their deliveries
- **Executive Role**: Can see all deliveries, filtered by audience = "c_suite" or "global"

## Monitoring Alerts

### Setup PowerBI Alerts (in Service)
1. **Success Rate Alert**:
   - Metric: `Delivery Success Rate`
   - Condition: Falls below 0.95 (95%)
   - Notification: Email to admin team

2. **Daily Delivery Volume Alert**:
   - Metric: `COUNT(delivery_id)` where `created_at` = Today
   - Condition: Falls below 1 (no deliveries today)
   - Notification: Email to admin team (might indicate system issue)

3. **Execution Time Alert**:
   - Metric: `Avg Execution Time (sec)`
   - Condition: Exceeds 60 seconds
   - Notification: Email to DevOps (performance degradation)

## Troubleshooting

### Connection Issues
- **Error: SSL connection required**
  - Add `sslmode=require` to connection string
  - Check Azure PostgreSQL firewall allows PowerBI Service IPs

- **Error: Authentication failed**
  - Verify credentials in Azure Key Vault
  - Check `adminuser` has SELECT permissions on tables

### Performance Issues
- **Slow refresh times**
  - Add indexes on `created_at`, `status`, `user_email` (already exist)
  - Use **DirectQuery** mode instead of **Import** for real-time data
  - Limit historical data to last 90 days for Import mode

### Data Quality Issues
- **Missing deliveries**
  - Check `vault_alerts_scheduler.py` logs for insertion errors
  - Verify Azure Container App is running
  - Check database connection string in `.env.local`

## Next Steps

1. ✅ **Connect PowerBI Desktop** to PostgreSQL database
2. ✅ **Create measures** (copy DAX from this document)
3. ✅ **Build Page 1** (Executive Overview) with KPI cards and time series
4. ✅ **Build Page 2** (Performance Metrics) with execution time analysis
5. ✅ **Build Page 3** (Failures & Debugging) for troubleshooting
6. ✅ **Build Page 4** (User Activity) for engagement tracking
7. ✅ **Publish to PowerBI Service** workspace
8. ✅ **Schedule refresh** (hourly)
9. ✅ **Setup alerts** for success rate and delivery volume
10. ✅ **Share dashboard** with steve@, brandon@, daniel.romitelli@

## Sample Queries for Testing

### Test data generation (development only):
```sql
-- Insert test delivery
INSERT INTO vault_alert_deliveries (
    delivery_id, user_id, user_email, delivery_email,
    audience, status, total_candidates, advisor_cards_count,
    execution_time_ms, email_sent_at, created_at
) VALUES (
    'test-001', 'user123', 'test@emailthewell.com', 'test@emailthewell.com',
    'advisors', 'completed', 10, 10,
    15000, NOW(), NOW()
);
```

### Check delivery statistics:
```sql
SELECT
    audience,
    COUNT(*) as total_deliveries,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
    AVG(execution_time_ms)/1000.0 as avg_execution_sec,
    SUM(total_candidates) as total_candidates_delivered
FROM vault_alert_deliveries
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY audience
ORDER BY total_deliveries DESC;
```

## Documentation Updates

After PowerBI setup is complete, update:
- `CLAUDE.md` - Add PowerBI dashboard URL and access instructions
- `README.md` - Add monitoring section
- Azure DevOps wiki - Add operational runbook

---

**Created**: 2025-10-13
**Version**: 1.0
**Owner**: Well Intake API Team
**Last Updated**: 2025-10-13
