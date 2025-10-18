# Teams Bot Deployment Documentation

## Overview
Complete deployment infrastructure, monitoring, and smoke test procedures for Teams Bot conversational AI rollout.

**Version**: 2.0.0
**Feature**: Natural Language Processing with PostgreSQL queries
**Risk Level**: Medium
**Deployment Date**: TBD

---

## 📁 Documentation Structure

### Testing Documentation
- **[Smoke Test Procedure](../testing/teams_bot_smoke.md)** - Detailed QA test scenarios and acceptance criteria
  - 5 core test scenarios with timing targets
  - Performance metrics checklist
  - Transcript capture requirements
  - Issue escalation procedures

### Monitoring Documentation
- **[Metrics & Monitoring](../monitoring/teams_bot_metrics.md)** - Application Insights queries and dashboards
  - 5 key performance indicators (KPIs)
  - Pre-configured alert rules
  - Executive and operations dashboards
  - Troubleshooting guides

### Deployment Documentation
- **[Beta Rollout Plan](beta_rollout_plan.md)** - Phased deployment strategy
  - 5-phase rollout (single user → full production)
  - Feature flag configuration per phase
  - A/B testing implementation
  - Rollback procedures

- **[Deployment Checklist](deployment_checklist.md)** - Step-by-step deployment guide
  - Pre-deployment verification
  - Docker build & registry steps
  - Azure Container Apps commands
  - Post-deployment validation

### Release Documentation
- **[Release Notes Template](../releases/v2.0.0_release_notes_template.md)** - Product communication template
  - New features summary
  - Feature flag migration guide
  - Breaking changes documentation
  - Smoke test results section

---

## 🚀 Quick Start

### Prerequisites
```bash
# Install required tools
az --version          # Azure CLI 2.50+
docker --version      # Docker 24.0+
python3 --version     # Python 3.11+

# Login to Azure
az login
az account set --subscription "3fee2ac0-3a70-4343-a8b2-3a98da1c9682"
```

### Deploy to Production
```bash
# Full deployment (100% traffic)
./scripts/deploy_teams_bot.sh production 0

# Canary deployment (10% traffic)
./scripts/deploy_teams_bot.sh production 10

# Beta environment
./scripts/deploy_teams_bot.sh beta 0
```

### Emergency Rollback
```bash
# Quick rollback to previous revision
./scripts/rollback_teams_bot.sh

# Rollback to specific revision
./scripts/rollback_teams_bot.sh teams-bot--v20251017-143022
```

### Run Smoke Tests
```bash
# Run automated smoke tests
python scripts/smoke_test.py https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io

# Manual smoke test procedure
# Follow: docs/testing/teams_bot_smoke.md
```

---

## 🔧 Configuration

### Environment Variables
```bash
# Core Feature Flags
ENABLE_NLP_CARDS=false        # Adaptive cards for NLP (start with false)
ENABLE_AZURE_AI_SEARCH=false  # Experimental - do not enable
USE_ASYNC_DIGEST=true         # Service Bus integration
PRIVACY_MODE=true             # Company anonymization

# AI Features
FEATURE_LLM_SENTIMENT=true    # GPT-5 sentiment analysis
FEATURE_GROWTH_EXTRACTION=true # Extract growth metrics
OPENAI_MODEL=gpt-5            # Always use gpt-5

# Data Sources
USE_ZOHO_API=false            # PostgreSQL is primary source
ZOHO_DEFAULT_OWNER_EMAIL=steve.perry@emailthewell.com
```

### Azure Resources
```yaml
Subscription: 3fee2ac0-3a70-4343-a8b2-3a98da1c9682
Resource Group: TheWell-Infra-East
Container Registry: wellintakeacr0903
Container App: teams-bot
Environment: well-intake-env
Application Insights: well-intake-insights
```

---

## 📊 Key Metrics & SLAs

### Performance Targets
- **Response Time P95**: < 3 seconds
- **Success Rate**: > 99%
- **Availability**: 99.9%
- **Error Rate**: < 1%

### Monitoring Queries
```kusto
// Response Latency P95
requests
| where cloud_RoleName == "teams-bot"
| where timestamp > ago(1h)
| summarize P95 = percentile(duration, 95)

// Success Rate
requests
| where cloud_RoleName == "teams-bot"
| where timestamp > ago(1h)
| summarize SuccessRate = (countif(success == true) * 100.0) / count()
```

---

## 🔄 Deployment Workflow

### 1. Pre-Deployment (30 min)
- [ ] Run unit tests: `pytest teams_bot/tests/`
- [ ] Run integration tests: `pytest tests/teams/`
- [ ] Security scan: `bandit -r teams_bot/app/`
- [ ] Review feature flags in `app/config/feature_flags.py`

### 2. Build & Deploy (15 min)
```bash
# Automated deployment
./scripts/deploy_teams_bot.sh production 10  # 10% canary
```

### 3. Validation (30 min)
- [ ] Run smoke tests (automated)
- [ ] Manual QA testing per smoke test doc
- [ ] Monitor Application Insights
- [ ] Check error rates

### 4. Decision Point
```bash
# If successful - full rollout
az containerapp ingress traffic set \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --revision-weight "new-revision=100"

# If issues - rollback
./scripts/rollback_teams_bot.sh
```

---

## 🐛 Known Issues & Mitigations

### Current Issue: InvokeResponse 500 Errors
**Status**: Fixed in v2.0.0
**Mitigation**: Proper InvokeResponse with status 200 implemented

### Card Rendering on Mobile
**Status**: Minor formatting issues
**Mitigation**: Set `ENABLE_NLP_CARDS=false` for text-only mode

### Context Timeout
**Status**: By design
**Behavior**: Context lost after 30 minutes of inactivity
**Mitigation**: Start new conversation

---

## 📞 Support & Escalation

### Teams Channels
- **Support**: #teams-bot-support
- **Feedback**: #teams-bot-feedback
- **Incidents**: #teams-bot-incidents

### Contacts
- **Dev Lead**: daniel.romitelli@emailthewell.com
- **QA Lead**: qa.lead@emailthewell.com
- **Product Owner**: product@emailthewell.com
- **On-Call**: Check PagerDuty

### Escalation Path
1. Teams channel notification
2. Email to dev team
3. PagerDuty for critical issues
4. Executive escalation if needed

---

## 📚 Additional Resources

### Internal Documentation
- [Teams Bot User Guide](../guides/teams_bot_user_guide.md)
- [NLP Query Examples](../guides/nlp_examples.md)
- [Troubleshooting Guide](../troubleshooting/teams_bot.md)

### Azure Documentation
- [Container Apps](https://docs.microsoft.com/azure/container-apps/)
- [Application Insights](https://docs.microsoft.com/azure/azure-monitor/app/app-insights-overview)
- [Azure CLI Reference](https://docs.microsoft.com/cli/azure/)

### Scripts
- `deploy_teams_bot.sh` - Automated deployment with testing
- `rollback_teams_bot.sh` - Emergency rollback
- `smoke_test.py` - Automated smoke tests

---

## ✅ Sign-Off Template

### Deployment Engineer
- Name: _________________________
- Date/Time: _________________________
- Version Deployed: _________________________
- All Tests Passed: [ ] Yes [ ] No

### QA Lead
- Name: _________________________
- Smoke Tests Passed: [ ] Yes [ ] No
- Ready for Production: [ ] Yes [ ] No

### Product Owner
- Name: _________________________
- Feature Approved: [ ] Yes [ ] No
- Rollout Approved: [ ] Yes [ ] No

---

## 📝 Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 2.0.0 | 2025-10-17 | Initial NLP release | Teams Bot Team |
| 1.5.0 | 2025-10-15 | Service Bus integration | Teams Bot Team |
| 1.0.0 | 2025-10-01 | Initial Teams Bot | Teams Bot Team |

---

**Last Updated**: 2025-10-17
**Document Owner**: Teams Bot Development Team
**Review Schedule**: Weekly during beta, monthly after GA