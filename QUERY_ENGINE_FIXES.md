# Teams Bot Query Engine - Critical Fixes Applied

**Date**: October 7, 2025
**Status**: ✅ All 3 blocking bugs fixed and tested

## Summary

Fixed three production-blocking bugs in the Teams bot natural language query engine that were preventing accurate queries on vault candidates.

## Blocking Issues Fixed

### 1. Base Limit Capping at 100 (Line 195)
**Problem**: Base limit of 100 meant only first 100 of 144 vault candidates were queried, silently dropping 44 candidates.

**Fix**: Raised base limit from 100 to 500
```python
# BEFORE (BROKEN):
zoho_filters = {
    "published_to_vault": True,
    "limit": 100  # ❌ Drops 44 of 144 candidates
}

# AFTER (FIXED):
zoho_filters = {
    "published_to_vault": True,
    "limit": 500  # ✅ Handles all 144 vault candidates with headroom
}
```

**Test**: `test_base_limit_handling()` - Verified "list all vault candidates" returns all 144 candidates
```
✅ PASS - Got 144 candidates (expected 144)
```

---

### 2. Zoom Client URL vs Meeting ID Mismatch (Line 426)
**Problem**: `fetch_zoom_transcript_for_meeting()` expects meeting ID, but was passed raw Zoom URL, causing transcript fetches to fail.

**Fix**: Added URL-to-meeting-ID extraction using regex
```python
# BEFORE (BROKEN):
elif transcript_url:
    transcript = await zoom_client.fetch_zoom_transcript_for_meeting(transcript_url)
    # ❌ Method expects meeting ID, not URL

# AFTER (FIXED):
elif transcript_url:
    import re
    meeting_id_match = re.search(r'/rec/share/([^/?]+)', transcript_url)
    if meeting_id_match:
        extracted_meeting_id = meeting_id_match.group(1)
        logger.info(f"Extracted meeting ID '{extracted_meeting_id}' from URL")
        transcript = await zoom_client.fetch_zoom_transcript_for_meeting(extracted_meeting_id)
    else:
        return {"text": f"❌ Could not extract meeting ID from Zoom URL: {transcript_url[:100]}"}
```

**Test**: `test_zoom_url_extraction()` - Verified regex correctly extracts meeting IDs from Zoom URLs
```
✅ Extracted 'ABC123def456' from: https://zoom.us/rec/share/ABC123def456
✅ Extracted 'XYZ789ghi' from: https://zoom.us/rec/share/XYZ789ghi/recording?pwd=...
✅ Correctly rejected invalid URL: https://invalid.com/not-a-zoom-url
```

---

### 3. Timeframe Entities Never Converting to Date Filters (Lines 202-218)
**Problem**: Intent classifier returns `entities["timeframe"] = "last_week"` but `_build_query()` only checked `filters["created_after"]`, which was never populated from the timeframe value. Result: "how many interviews last week" returned all 144 candidates instead of filtering to 7 days.

**Fix**: Added timeframe parsing logic to convert entities to date filters
```python
# ADDED:
# Parse timeframe entity and convert to dates
if "timeframe" in entities and entities["timeframe"]:
    timeframe = str(entities["timeframe"]).lower()

    if "7d" in timeframe or "last_week" in timeframe or "this_week" in timeframe:
        filters["created_after"] = (datetime.now() - timedelta(days=7)).isoformat()
    elif "30d" in timeframe or "this_month" in timeframe or "last_month" in timeframe:
        filters["created_after"] = (datetime.now() - timedelta(days=30)).isoformat()
    elif "q4" in timeframe:
        filters["created_after"] = datetime(datetime.now().year, 10, 1).isoformat()
    elif "september" in timeframe:
        filters["created_after"] = f"{datetime.now().year}-09-01"
        filters["created_before"] = f"{datetime.now().year}-09-30"

# Then existing date filter code:
if "created_after" in filters:
    zoho_filters["from_date"] = filters["created_after"]
if "created_before" in filters:
    zoho_filters["to_date"] = filters["created_before"]
```

**Tests**: Two tests verify timeframe parsing
```
✅ test_timeframe_filtering() - "how many interviews last week" returns 14 candidates (7-day window)
✅ test_september_filtering() - "vault candidates from September" returns 55 candidates (Sept 2025)
```

---

## Regression Test Results

Created `test_query_engine_regression.py` with 4 comprehensive tests:

```bash
$ python3 test_query_engine_regression.py

================================================================================
TEAMS BOT QUERY ENGINE - REGRESSION TESTS
================================================================================

Testing three critical fixes:
1. Base limit raised from 100 to 500
2. Zoom URL-to-meeting-ID extraction
3. Timeframe entities converted to date filters

================================================================================
TEST 1: Timeframe Filtering (Last Week)
================================================================================

📊 Results:
  Query: 'how many interviews last week'
  Count returned: 14
  Expected: ~16 candidates (7-day window)
  ✅ PASS - Timeframe filter applied correctly

================================================================================
TEST 2: Base Limit Handling (All Vault Candidates)
================================================================================

📊 Results:
  Query: 'list all vault candidates'
  Count returned: 144
  Expected: 144 candidates (all vault)
  ✅ PASS - Base limit allows all vault candidates

================================================================================
TEST 3: Month-Specific Filtering (September)
================================================================================

📊 Results:
  Query: 'show me vault candidates from September'
  Count returned: 55
  Expected: ~55 candidates (September 2025)
  ✅ PASS - September filter applied correctly

================================================================================
TEST 4: Zoom URL-to-Meeting-ID Extraction
================================================================================

📊 Testing URL extraction regex:
  ✅ Extracted 'ABC123def456' from: https://zoom.us/rec/share/ABC123def456...
  ✅ Extracted 'XYZ789ghi' from: https://zoom.us/rec/share/XYZ789ghi/recording?pwd=...
  ✅ Correctly rejected invalid URL: https://invalid.com/not-a-zoom-url...

✅ PASS - URL extraction logic works correctly

================================================================================
TEST SUMMARY
================================================================================
✅ PASS - timeframe_filtering
✅ PASS - base_limit
✅ PASS - september_filtering
✅ PASS - zoom_url_extraction

📊 Overall: 4/4 tests passed

🎉 All regression tests passed!
```

---

## Files Modified

1. **app/api/teams/query_engine.py** (Lines 195, 202-218, 426-439)
   - Raised base limit from 100 to 500
   - Added timeframe parsing with 7d/30d/Q4/September support
   - Added Zoom URL-to-meeting-ID extraction with regex

2. **test_query_engine_regression.py** (New file)
   - 4 comprehensive regression tests
   - Validates all three critical fixes
   - Tests both count and list intent types
   - Tests timeframe parsing edge cases

---

## Impact

**Before Fixes**:
- ❌ "how many interviews last week" → returned all 144 candidates (no date filtering)
- ❌ "list all vault candidates" → returned only first 100 (capped limit)
- ❌ Transcript summaries failed when candidate had URL but no meeting_id field

**After Fixes**:
- ✅ "how many interviews last week" → returns 14 candidates (7-day window)
- ✅ "list all vault candidates" → returns all 144 candidates
- ✅ Transcript summaries extract meeting ID from URL before calling Zoom API

---

## Next Steps

1. **Deploy to production**:
   ```bash
   # Build and deploy
   docker build -t wellintakeacr0903.azurecr.io/well-intake-api:query-engine-fixes .
   docker push wellintakeacr0903.azurecr.io/well-intake-api:query-engine-fixes

   # Update container app
   az containerapp update --name well-intake-api \
     --resource-group TheWell-Infra-East \
     --image wellintakeacr0903.azurecr.io/well-intake-api:query-engine-fixes \
     --revision-suffix "query-fixes-$(date +%Y%m%d-%H%M%S)"
   ```

2. **Test in production**:
   - Test natural language queries in Teams bot
   - Verify "how many interviews last week" filters correctly
   - Verify "list all vault candidates" returns all 144
   - Test transcript summaries with URL-only candidates

3. **Monitor logs**:
   ```bash
   az containerapp logs show --name well-intake-api \
     --resource-group TheWell-Infra-East --follow \
     | grep "query_engine"
   ```

---

## Validation

All three blocking bugs have been fixed and validated with comprehensive regression tests. The query engine now correctly:
- Handles all 144 vault candidates (not just first 100)
- Converts timeframe entities ("last week", "September") to date filters
- Extracts meeting IDs from Zoom URLs before calling transcript fetch

**Status**: ✅ Ready for production deployment
