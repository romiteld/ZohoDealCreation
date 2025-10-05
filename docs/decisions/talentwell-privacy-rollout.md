# TalentWell Privacy & Data Quality Rollout

**Decision Date**: October 5, 2025
**Status**: Approved
**Stakeholder**: Product Owner

## Executive Summary

This document records stakeholder-approved privacy enhancements and data quality improvements for the TalentWell Candidate Vault digest system. All changes are gated by feature flags for instant rollback capability.

## Approved Changes

### 1. Company Anonymization (PRIVACY_MODE)

**Rationale**: Protect candidate privacy by obscuring employer identity while preserving firm context.

**Implementation**:
- Morgan Stanley, Merrill Lynch → "Major wirehouse"
- RBC, Raymond James → "Large regional wirehouse"
- Ameriprise, LPL, Cambridge → "Independent B/D"
- $500M+ AUM → "Major wirehouse" (regardless of actual firm)
- Unknown firms → "Financial services firm"

**Code Location**: `app/jobs/talentwell_curator.py::_anonymize_company()` (lines 425-428, 541-542, 549)

**Feature Flag**: `PRIVACY_MODE=true` (default enabled)

**Rollback**: Set `PRIVACY_MODE=false` in `.env.local` to revert to displaying actual company names

---

### 2. Strict Compensation Format (PRIVACY_MODE)

**Rationale**: Standardize compensation display for consistency and professional presentation.

**Format**: `"Target comp: $XXK–$YYK OTE"`

**Examples**:
- Input: "Looking for 250k to 350k" → Output: "Target comp: $250K–$350K OTE"
- Input: "$500,000 total comp" → Output: "Target comp: $500K OTE"
- Input: "200-300k base + bonus" → Output: "Target comp: $200K–$300K OTE"

**Code Location**: `app/jobs/talentwell_curator.py::_standardize_compensation()` (lines 678-732)

**Feature Flag**: Controlled by `PRIVACY_MODE=true`

**Rollback**: Set `PRIVACY_MODE=false` for light-touch formatting

---

### 3. Location Duplicate Prevention (Data Quality)

**Rationale**: Prevent redundant display of location in both header and bullet points.

**Implementation**:
- Filter bullets containing: "location:", "current firm:", "current role:", "current company:"
- Zero-score assignment in `_score_bullet()` prevents ranking
- Filtered during `_rank_bullets_by_score()` before sorting

**Code Location**: `app/jobs/talentwell_curator.py::_score_bullet()` (lines 854-858), `_rank_bullets_by_score()` (line 1030)

**Feature Flag**: Always enabled (data quality fix, not privacy-related)

**Rollback**: Not applicable - this is a bug fix, not a feature

---

## Feature Flag Architecture

**File**: `app/config/feature_flags.py`

```python
# Privacy features (APPROVED - 2025-10-05)
PRIVACY_MODE = os.getenv('PRIVACY_MODE', 'true').lower() == 'true'

# Performance features (APPROVED - 2025-10-05)
FEATURE_ASYNC_ZOHO = os.getenv('FEATURE_ASYNC_ZOHO', 'true').lower() == 'true'

# AI features
FEATURE_LLM_SENTIMENT = os.getenv('FEATURE_LLM_SENTIMENT', 'false').lower() == 'true'
FEATURE_GROWTH_EXTRACTION = os.getenv('FEATURE_GROWTH_EXTRACTION', 'true').lower() == 'true'

# UX features (Phase 3 - not implemented yet)
FEATURE_AUDIENCE_FILTERING = os.getenv('FEATURE_AUDIENCE_FILTERING', 'false').lower() == 'true'
FEATURE_CANDIDATE_SCORING = os.getenv('FEATURE_CANDIDATE_SCORING', 'false').lower() == 'true'
```

**Exports**: `app/config/__init__.py` exports all flags for application-wide use

---

## Rollback Procedures

### Emergency Rollback (< 5 minutes)

**If privacy changes cause issues:**

1. **Disable privacy mode**:
   ```bash
   # In Azure Container Apps environment variables
   az containerapp update --name well-intake-api \
     --resource-group TheWell-Infra-East \
     --set-env-vars PRIVACY_MODE=false
   ```

2. **Restart containers** (automatic after env var update)

3. **Verify rollback**:
   ```bash
   curl -X GET "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/vault-agent/status" \
     -H "X-API-Key: your-api-key"
   ```

4. **Clear digest cache**:
   ```python
   from app.cache.c3 import C3Cache
   cache = C3Cache()
   await cache.invalidate_pattern("digest:*")
   ```

### Gradual Rollback (Development/Testing)

**Local development**:
1. Edit `.env.local`: `PRIVACY_MODE=false`
2. Restart uvicorn: `uvicorn app.main:app --reload`
3. Test digest generation: `python -m app.jobs.talentwell_curator --audience steve_perry --days 7`

---

## Validation & Testing

### Unit Tests
**File**: `tests/unit/test_privacy.py` (pending creation)

**Coverage**:
- Company anonymization mapping accuracy
- Compensation parser edge cases
- Location duplicate filtering logic
- Feature flag enable/disable behavior

### Integration Tests
**File**: `tests/integration/test_talentwell_pipeline.py` (pending creation)

**Scenarios**:
- Full digest generation with PRIVACY_MODE=true
- Rollback verification with PRIVACY_MODE=false
- Bullet scoring with location filtering
- Compensation formatting across various inputs

---

## Deployment History

| Date | Change | Flag | Status |
|------|--------|------|--------|
| 2025-10-05 | Created feature flag infrastructure | - | ✅ Deployed |
| 2025-10-05 | Implemented company anonymization | PRIVACY_MODE | ✅ Deployed |
| 2025-10-05 | Added strict compensation parser | PRIVACY_MODE | ✅ Deployed |
| 2025-10-05 | Fixed location bullet duplicates (scoring) | Always on | ✅ Deployed |
| 2025-10-05 | Suppressed location bullets in privacy mode | PRIVACY_MODE | ✅ Deployed |
| 2025-10-05 | Disabled async Zoho (implementation incomplete) | FEATURE_ASYNC_ZOHO | ❌ Reverted |

---

## Future Enhancements (Not Yet Approved)

### Pending Implementation
- **Async Zoho API** (FEATURE_ASYNC_ZOHO):
  - Status: **Blocked** - requires call site updates
  - Issue: `_make_request` returns unawaited Task, breaking all callers
  - Solution: Convert method to `async`, update all `upsert_*` and `query_*` call sites
  - Benefit: 2-3x speedup once properly implemented

### Planned (Pending Stakeholder Review)
- **LLM Sentiment Analysis** (FEATURE_LLM_SENTIMENT): Replace keyword-based sentiment with GPT-5 sentiment scoring
- **Growth Metrics Extraction** (FEATURE_GROWTH_EXTRACTION): ✅ **IMPLEMENTED** - Parse "grew book 40% YoY" patterns from transcripts

### Phase 3 - UX Personalization (Not Implemented)
- **Audience Filtering** (FEATURE_AUDIENCE_FILTERING): Customize bullet scoring by recipient type
- **Candidate Scoring** (FEATURE_CANDIDATE_SCORING): Quality score badges in digest cards

---

## References

- **Implementation Plan**: `/home/romiteld/Development/Desktop_Apps/outlook/docs/talentwell-completion-plan.md`
- **Feature Flags**: `app/config/feature_flags.py`
- **Curator Code**: `app/jobs/talentwell_curator.py`
- **VoIT Config**: `app/config/voit_config.py`

---

**Document Version**: 1.0
**Last Updated**: October 5, 2025
**Next Review**: After 100 digests sent with privacy mode enabled
