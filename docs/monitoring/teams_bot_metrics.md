# Teams Bot Monitoring & Metrics Guide

## Overview
Post-deployment monitoring configuration for Teams Bot conversational AI feature. All queries use Azure Application Insights with 24-hour retention for key metrics.

**Resource Group**: TheWell-Infra-East
**Application Insights**: well-intake-insights
**Target SLAs**: Response < 3s (P95), Success Rate > 99%

---

## Key Performance Indicators (KPIs)

### 1. Response Latency (P95)
**Target**: < 3000ms
**Alert Threshold**: > 5000ms for 5 minutes

```kusto
// Response Latency P95 - Last 24 hours
requests
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| where name contains "webhook" or name contains "invoke"
| summarize
    P50 = percentile(duration, 50),
    P95 = percentile(duration, 95),
    P99 = percentile(duration, 99),
    Count = count()
    by bin(timestamp, 1h)
| render timechart
```

### 2. Invoke Success Rate
**Target**: > 99%
**Alert Threshold**: < 95% for 10 minutes

```kusto
// Invoke Success Rate - Real-time
requests
| where timestamp > ago(1h)
| where cloud_RoleName == "teams-bot"
| where name contains "invoke" or url contains "webhook"
| summarize
    Total = count(),
    Success = countif(success == true),
    Failed = countif(success == false)
    by bin(timestamp, 5m)
| extend SuccessRate = (Success * 100.0) / Total
| project timestamp, SuccessRate, Total, Failed
| render timechart
```

### 3. Clarification Usage Rate
**Target**: Track baseline, optimize if > 30%

```kusto
// Clarification Usage Analysis
customEvents
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| where name == "ClarificationRequested" or name == "QueryProcessed"
| summarize
    ClarificationCount = countif(name == "ClarificationRequested"),
    TotalQueries = countif(name == "QueryProcessed")
    by bin(timestamp, 1h)
| extend ClarificationRate = (ClarificationCount * 100.0) / TotalQueries
| project timestamp, ClarificationRate, ClarificationCount, TotalQueries
```

### 4. Conversation Turns Average
**Target**: 1.5 - 3.0 turns per session

```kusto
// Average Conversation Turns
customEvents
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| where name == "ConversationTurn"
| extend
    SessionId = tostring(customDimensions.session_id),
    TurnNumber = toint(customDimensions.turn_number)
| summarize
    MaxTurns = max(TurnNumber),
    Sessions = dcount(SessionId)
    by bin(timestamp, 1h)
| extend AvgTurns = toreal(MaxTurns) / toreal(Sessions)
| project timestamp, AvgTurns, Sessions
```

### 5. NLP vs Slash Command Ratio
**Target**: Monitor adoption of conversational features

```kusto
// NLP vs Slash Command Usage
customEvents
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| where name in ("NLPQuery", "SlashCommand")
| summarize
    NLP = countif(name == "NLPQuery"),
    Slash = countif(name == "SlashCommand")
    by bin(timestamp, 1h)
| extend NLPRatio = (NLP * 100.0) / (NLP + Slash)
| project timestamp, NLPRatio, NLP, Slash
| render columnchart
```

---

## Error Monitoring

### 500 Error Detection
```kusto
// 500 Errors - Critical Alert
requests
| where timestamp > ago(1h)
| where cloud_RoleName == "teams-bot"
| where resultCode == "500"
| project timestamp, name, duration, operation_Id
| order by timestamp desc
| take 10
```

### Button Click Failures
```kusto
// InvokeResponse Failures
requests
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| where name contains "invoke"
| where success == false
| extend ErrorMessage = tostring(customDimensions.error)
| summarize
    FailureCount = count(),
    UniqueErrors = dcount(ErrorMessage)
    by bin(timestamp, 30m), ErrorMessage
| order by timestamp desc
```

### Exception Tracking
```kusto
// All Exceptions - Last Hour
exceptions
| where timestamp > ago(1h)
| where cloud_RoleName == "teams-bot"
| extend
    ExceptionType = tostring(type),
    Method = tostring(method),
    Message = tostring(outerMessage)
| summarize Count = count() by ExceptionType, Method
| order by Count desc
```

---

## Performance Monitoring

### Database Query Performance
```kusto
// PostgreSQL Query Performance
dependencies
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| where type == "PostgreSQL"
| summarize
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95),
    Count = count()
    by bin(timestamp, 1h), name
| where Count > 10  // Filter noise
| render timechart
```

### Redis Cache Hit Rate
```kusto
// Redis Cache Performance
dependencies
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| where type == "Redis"
| extend CacheHit = tobool(customDimensions.cache_hit)
| summarize
    Hits = countif(CacheHit == true),
    Misses = countif(CacheHit == false)
    by bin(timestamp, 1h)
| extend HitRate = (Hits * 100.0) / (Hits + Misses)
| project timestamp, HitRate, Hits, Misses
```

### Zoho API Latency
```kusto
// Zoho API Performance (if USE_ZOHO_API=true)
dependencies
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| where type == "HTTP" and data contains "zoho"
| summarize
    AvgLatency = avg(duration),
    P95Latency = percentile(duration, 95),
    CallCount = count()
    by bin(timestamp, 1h)
| render timechart
```

---

## User Behavior Analytics

### Active Users
```kusto
// Daily Active Users
customEvents
| where timestamp > ago(7d)
| where cloud_RoleName == "teams-bot"
| extend UserId = tostring(customDimensions.user_id)
| summarize DAU = dcount(UserId) by bin(timestamp, 1d)
| render columnchart
```

### Feature Usage
```kusto
// Feature Adoption Metrics
customEvents
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| where name in ("DigestGenerated", "VaultQuery", "DealSearch", "MeetingQuery")
| summarize Count = count() by name
| render piechart
```

### Query Patterns
```kusto
// Most Common Query Types
customEvents
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| where name == "QueryIntent"
| extend Intent = tostring(customDimensions.intent)
| summarize Count = count() by Intent
| order by Count desc
| take 10
```

---

## Alert Configuration

### Critical Alerts (Immediate)

#### 1. High Error Rate
```kusto
// Alert Rule: Success Rate < 95%
requests
| where timestamp > ago(5m)
| where cloud_RoleName == "teams-bot"
| summarize
    SuccessRate = (countif(success == true) * 100.0) / count()
| where SuccessRate < 95
```

**Action**: Email + Teams notification to dev team

#### 2. Response Time Degradation
```kusto
// Alert Rule: P95 > 5000ms
requests
| where timestamp > ago(5m)
| where cloud_RoleName == "teams-bot"
| summarize P95 = percentile(duration, 95)
| where P95 > 5000
```

**Action**: Email to dev team

#### 3. Service Unavailable
```kusto
// Alert Rule: No requests in 5 minutes
requests
| where timestamp > ago(5m)
| where cloud_RoleName == "teams-bot"
| summarize RequestCount = count()
| where RequestCount == 0
```

**Action**: PagerDuty escalation

---

## Dashboard Configuration

### Executive Dashboard
Create Application Insights Dashboard with:

1. **Health Overview**
   - Success Rate (Line chart)
   - Response Time P95 (Line chart)
   - Active Users (Number card)
   - Total Queries Today (Number card)

2. **Usage Patterns**
   - NLP vs Slash Commands (Pie chart)
   - Query Types (Bar chart)
   - Hourly Activity (Heatmap)

3. **Performance Metrics**
   - Database Query Time (Line chart)
   - Cache Hit Rate (Line chart)
   - Error Count (Number card)

### Operations Dashboard
1. **Real-time Monitoring**
   - Live request stream
   - Error log tail
   - Current active sessions

2. **Infrastructure Health**
   - Container CPU/Memory
   - Database connections
   - Redis memory usage

---

## Weekly Report Queries

### Weekly Executive Summary
```kusto
// Weekly Performance Summary
let startTime = ago(7d);
let endTime = now();
requests
| where timestamp between (startTime .. endTime)
| where cloud_RoleName == "teams-bot"
| summarize
    TotalRequests = count(),
    SuccessRate = (countif(success == true) * 100.0) / count(),
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95)
| extend WeekOf = format_datetime(startTime, 'yyyy-MM-dd')
```

### Top Users Report
```kusto
// Top 10 Most Active Users
customEvents
| where timestamp > ago(7d)
| where cloud_RoleName == "teams-bot"
| extend UserId = tostring(customDimensions.user_id)
| summarize
    QueryCount = count(),
    UniqueFeatures = dcount(name)
    by UserId
| order by QueryCount desc
| take 10
```

---

## Telemetry Implementation

### Required Custom Events

```python
# In teams_bot/app/api/teams/routes.py

from app.monitoring import track_event, track_metric

# Track NLP Query
track_event("NLPQuery", {
    "user_id": user_id,
    "query_type": "natural_language",
    "intent": detected_intent,
    "session_id": session_id,
    "turn_number": turn_count
})

# Track Clarification
track_event("ClarificationRequested", {
    "user_id": user_id,
    "original_query": query,
    "options_presented": len(options)
})

# Track Conversation Turn
track_event("ConversationTurn", {
    "session_id": session_id,
    "turn_number": turn_count,
    "user_id": user_id
})

# Track Performance Metric
track_metric("response_latency_ms", latency_ms, {
    "query_type": query_type,
    "cache_hit": was_cached
})
```

---

## Troubleshooting Guide

### High Latency Investigation
1. Check database query performance dashboard
2. Review Redis cache hit rates
3. Analyze Zoho API response times
4. Check container CPU/memory usage

### Low Success Rate Investigation
1. Review recent exceptions
2. Check for InvokeResponse failures
3. Verify database connectivity
4. Review recent deployments

### User Complaints Investigation
1. Filter logs by user_id
2. Review conversation transcript
3. Check for timeout errors
4. Analyze specific query patterns

---

## Maintenance Windows

### Metric Retention
- Real-time: 24 hours (Application Insights)
- Aggregated: 90 days (Application Insights)
- Raw logs: 30 days (Log Analytics)

### Dashboard Refresh
- Executive: Every 5 minutes
- Operations: Real-time (live metrics)
- Weekly Reports: Monday 9 AM EST

---

## Contact & Escalation

### Primary Contacts
- **Dev Team**: teams-bot-dev@wellintake.com
- **Operations**: devops@wellintake.com
- **Product**: product@wellintake.com

### Escalation Path
1. Application Insights Alert → Dev Team Email
2. Critical Alert → PagerDuty → On-call Engineer
3. Service Down → Incident Commander → Executive Team