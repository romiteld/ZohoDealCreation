# Teams Bot Conversational AI - Beta Rollout Plan

## Overview
Phased rollout strategy for Teams Bot conversational AI features with risk mitigation and rollback procedures.

**Release Version**: 2.0.0
**Feature**: Natural Language Processing with Adaptive Cards
**Risk Level**: Medium (new user interaction paradigm)

---

## Phase 1: Single User Testing (Day 1-3)

### Target Users
```yaml
beta_users:
  - email: "qa.tester@emailthewell.com"
  - email: "daniel.romitelli@emailthewell.com"

rollout_percentage: 1%
environment: production
feature_flags:
  ENABLE_NLP_CARDS: false  # Text-only responses initially
```

### Implementation Steps

#### 1. User-Specific Feature Flag
```python
# In teams_bot/app/api/teams/routes.py

def should_enable_nlp_cards(user_email: str) -> bool:
    """Check if user should get NLP card features."""

    # Beta user list (move to database/config later)
    BETA_USERS = [
        "qa.tester@emailthewell.com",
        "daniel.romitelli@emailthewell.com"
    ]

    # Check if user is in beta
    if user_email in BETA_USERS:
        return True

    # Check global flag
    return os.getenv('ENABLE_NLP_CARDS', 'false').lower() == 'true'
```

#### 2. Deploy with User Override
```bash
# Add environment variable for beta users
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars \
    BETA_USERS="qa.tester@emailthewell.com,daniel.romitelli@emailthewell.com" \
    ENABLE_NLP_CARDS=false
```

### Validation Checklist
- [ ] Beta users can access NLP features
- [ ] Non-beta users get traditional responses
- [ ] No performance degradation
- [ ] Error rates remain < 1%
- [ ] Response times < 3s

---

## Phase 2: Team Testing (Day 4-7)

### Expansion Criteria
- Phase 1 success rate > 99%
- No critical bugs reported
- Response time P95 < 3s

### Target Teams
```yaml
beta_teams:
  - team_id: "19:team_TheWell_QA@thread.tacv2"
  - team_id: "19:team_TheWell_Dev@thread.tacv2"

rollout_percentage: 10%
feature_flags:
  ENABLE_NLP_CARDS: false  # Still text-only
```

### Implementation
```python
# teams_bot/app/config/beta_config.py

BETA_CONFIG = {
    "users": [
        "qa.tester@emailthewell.com",
        "daniel.romitelli@emailthewell.com"
    ],
    "teams": [
        "19:team_TheWell_QA@thread.tacv2",
        "19:team_TheWell_Dev@thread.tacv2"
    ],
    "features": {
        "nlp_enabled": True,
        "cards_enabled": False,  # Phase 2 still text-only
        "azure_ai_search": False
    }
}

def is_beta_enabled(context):
    """Check if beta features should be enabled."""
    user_email = context.get('user_email')
    team_id = context.get('team_id')

    # Check user or team membership
    if user_email in BETA_CONFIG['users']:
        return True
    if team_id in BETA_CONFIG['teams']:
        return True

    return False
```

### Monitoring
```kusto
// Beta vs Non-Beta Performance Comparison
customEvents
| where timestamp > ago(24h)
| where cloud_RoleName == "teams-bot"
| extend IsBeta = tobool(customDimensions.is_beta)
| summarize
    AvgLatency = avg(todouble(customDimensions.latency_ms)),
    ErrorRate = countif(tostring(customDimensions.success) == "false") * 100.0 / count()
    by IsBeta, bin(timestamp, 1h)
| render timechart
```

---

## Phase 3: Cards Enablement (Day 8-14)

### Feature Activation
```yaml
rollout_percentage: 10%  # Same users/teams
feature_flags:
  ENABLE_NLP_CARDS: true  # Enable adaptive cards for beta
```

### Deployment
```bash
# Update environment variable
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars ENABLE_NLP_CARDS=true \
  --revision-suffix "beta-cards-$(date +%Y%m%d)"
```

### Card Rendering Validation
- [ ] Cards render correctly in Teams desktop
- [ ] Cards render correctly in Teams web
- [ ] Cards render correctly in Teams mobile
- [ ] Button clicks return InvokeResponse (not 500)
- [ ] CSS page-break-inside prevents card splitting

---

## Phase 4: Gradual Rollout (Day 15-21)

### Progressive Expansion
```yaml
Day 15-17:
  rollout_percentage: 25%
  target: "Selected recruiters"

Day 18-19:
  rollout_percentage: 50%
  target: "All recruiters"

Day 20-21:
  rollout_percentage: 75%
  target: "All users except executives"
```

### A/B Testing Configuration
```python
# teams_bot/app/config/ab_testing.py

import hashlib

def get_rollout_group(user_id: str) -> str:
    """Determine rollout group based on user ID hash."""
    hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    percentage = hash_value % 100

    if percentage < 25:
        return "beta"
    elif percentage < 50:
        return "control"
    else:
        return "excluded"

def get_feature_config(user_id: str) -> dict:
    """Get feature configuration based on rollout group."""
    group = get_rollout_group(user_id)

    if group == "beta":
        return {
            "nlp_enabled": True,
            "cards_enabled": True,
            "azure_ai_search": False
        }
    else:
        return {
            "nlp_enabled": False,
            "cards_enabled": False,
            "azure_ai_search": False
        }
```

### Metrics Tracking
```kusto
// A/B Test Results
customEvents
| where timestamp > ago(7d)
| where cloud_RoleName == "teams-bot"
| extend Group = tostring(customDimensions.rollout_group)
| summarize
    Users = dcount(tostring(customDimensions.user_id)),
    Queries = count(),
    AvgLatency = avg(todouble(customDimensions.latency_ms)),
    SuccessRate = countif(tostring(customDimensions.success) == "true") * 100.0 / count()
    by Group
| order by Group
```

---

## Phase 5: Full Production (Day 22+)

### Go-Live Criteria
- [ ] Beta success rate > 99.5%
- [ ] No critical bugs in 7 days
- [ ] Response time P95 < 3s
- [ ] User satisfaction score > 4.0/5.0
- [ ] Executive approval received

### Full Deployment
```bash
# Full production rollout
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars \
    ENABLE_NLP_CARDS=true \
    ENABLE_AZURE_AI_SEARCH=false \
    BETA_USERS="" \
  --revision-suffix "prod-nlp-$(date +%Y%m%d)"
```

---

## Rollback Procedures

### Immediate Rollback (< 5 minutes)
```bash
# Quick rollback to previous revision
az containerapp revision list \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "[?properties.active].{Name:name, Created:properties.createdTime}" \
  --output table

# Activate previous stable revision
az containerapp revision activate \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision <previous-revision-name>

# Deactivate problematic revision
az containerapp revision deactivate \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision <current-revision-name>
```

### Feature Flag Rollback (< 1 minute)
```bash
# Disable NLP features immediately
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars ENABLE_NLP_CARDS=false \
  --no-wait

# Verify rollback
curl https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health
```

### Database Rollback (if needed)
```sql
-- Rollback any schema changes
BEGIN TRANSACTION;

-- Example: Remove new columns if added
ALTER TABLE teams_conversations
DROP COLUMN IF EXISTS nlp_intent,
DROP COLUMN IF EXISTS conversation_context;

-- Clear beta user preferences
UPDATE teams_user_preferences
SET beta_features = '{}'
WHERE beta_features IS NOT NULL;

COMMIT;
```

---

## Risk Mitigation

### Known Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| 500 errors on button clicks | High | InvokeResponse fix deployed first |
| Card rendering issues | Medium | Test on all Teams clients |
| Performance degradation | Medium | Cache warm-up, monitoring |
| User confusion | Low | Help documentation, training |
| Data inconsistency | Low | Feature flags, not data changes |

### Circuit Breaker Pattern
```python
# teams_bot/app/utils/circuit_breaker.py

class NLPCircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.is_open = False

    def call(self, func, *args, **kwargs):
        if self.is_open:
            if time.time() - self.last_failure_time > self.timeout:
                self.is_open = False  # Try to close
                self.failure_count = 0
            else:
                return self.fallback_response()

        try:
            result = func(*args, **kwargs)
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.is_open = True
                logger.error(f"Circuit breaker opened after {self.failure_count} failures")

            return self.fallback_response()

    def fallback_response(self):
        return {
            "type": "text",
            "text": "I'm having trouble processing natural language queries. Please use slash commands instead."
        }
```

---

## Communication Plan

### Stakeholder Updates

#### Day 0 (Pre-Launch)
```
Subject: Teams Bot NLP Beta Starting Tomorrow

Team,

We're beginning the beta rollout of natural language processing for the Teams bot tomorrow.

Phase 1 (Days 1-3): QA team only
Phase 2 (Days 4-7): Dev team included
Phase 3 (Days 8-14): Adaptive cards enabled
Phase 4 (Days 15-21): Gradual rollout to recruiters
Phase 5 (Day 22+): Full production

Success metrics are being tracked in Application Insights.

- Teams Bot Team
```

#### Daily Status Template
```
Date: [Date]
Phase: [Current Phase]
Rollout %: [Percentage]

Metrics (Last 24h):
- Success Rate: [XX.X%]
- Avg Response Time: [X.Xs]
- Users Affected: [Count]
- Critical Issues: [Count]

Next Steps:
- [Action items]

Rollback Decision: [ ] Proceed [ ] Hold [ ] Rollback
```

---

## Success Criteria

### Phase Progression Requirements
- Error rate < 1%
- Response time P95 < 3s
- No critical bugs reported
- Positive user feedback

### Final Success Metrics
- [ ] 99.5% success rate sustained for 7 days
- [ ] Response time consistently < 3s
- [ ] Zero data corruption incidents
- [ ] User adoption > 50%
- [ ] Executive satisfaction confirmed

---

## Appendix: Quick Commands

### Check Current Status
```bash
# Current revision
az containerapp revision show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision $(az containerapp show -n teams-bot -g TheWell-Infra-East --query "properties.latestRevisionName" -o tsv)

# Current environment variables
az containerapp show \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --query "properties.template.containers[0].env[?name=='ENABLE_NLP_CARDS']"
```

### Monitor Beta Users
```kusto
// Beta User Activity
customEvents
| where timestamp > ago(1h)
| where cloud_RoleName == "teams-bot"
| where tostring(customDimensions.user_email) in (
    "qa.tester@emailthewell.com",
    "daniel.romitelli@emailthewell.com"
)
| project timestamp, user = tostring(customDimensions.user_email),
          action = name, success = tobool(customDimensions.success)
| order by timestamp desc
```

### Emergency Contacts
- **Dev Lead**: daniel.romitelli@emailthewell.com
- **QA Lead**: qa.lead@emailthewell.com
- **Ops Team**: devops@emailthewell.com
- **PagerDuty**: #teams-bot-incidents