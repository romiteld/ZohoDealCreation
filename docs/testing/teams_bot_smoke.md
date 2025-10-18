# Teams Bot Conversational AI - Smoke Test Procedure

## Overview
This document provides detailed smoke test procedures for the Teams Bot conversational AI rollout. Each test scenario validates critical functionality and captures performance metrics.

**Test Environment**: Microsoft Teams (Desktop/Web Client)
**Target Response Time**: < 3 seconds
**Success Rate Target**: > 99%

---

## Pre-Test Setup

### 1. Environment Verification
```bash
# Verify Teams Bot is running
curl https://teams-bot.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health

# Expected Response:
{
  "status": "healthy",
  "service": "teams-bot",
  "version": "1.0.0"
}
```

### 2. Feature Flag Configuration
```bash
# Verify feature flags (in .env.local or Container App config)
ENABLE_NLP_CARDS=true      # Enable conversational AI with cards
PRIVACY_MODE=true           # Anonymization active
USE_ZOHO_API=false          # Using PostgreSQL for queries
USE_ASYNC_DIGEST=true       # Service Bus integration
```

### 3. Test User Setup
- **Primary Tester**: QA team member with standard recruiter access
- **Executive Tester**: User with steve@, brandon@, or daniel.romitelli@ email
- **Teams Channel**: Dedicated test channel for transcript capture

---

## Test Scenarios

### Test 1: Natural Language Query → Text Response
**Objective**: Validate basic NLP understanding and text-only responses

**Steps**:
1. Open Teams chat with bot
2. Send message: "Show me recent deals in Texas"
3. Start timer when message is sent
4. Stop timer when response appears

**Expected Result**:
```
Bot Response (< 3s):
"I found 3 recent deals in Texas:

1. **John Smith** - Morgan Stanley, Dallas
   - Close Date: 2025-10-15
   - Status: Won

2. **Sarah Johnson** - Wells Fargo, Houston
   - Close Date: 2025-10-10
   - Status: In Progress

3. **Mike Davis** - JP Morgan, Austin
   - Close Date: 2025-10-08
   - Status: Won"
```

**Success Criteria**:
- [ ] Response time < 3 seconds
- [ ] Formatted text (no adaptive cards if ENABLE_NLP_CARDS=false)
- [ ] Accurate data from PostgreSQL
- [ ] Proper anonymization if PRIVACY_MODE=true

**Capture**:
- Screenshot of conversation
- Response latency (milliseconds)
- Any error messages

---

### Test 2: Multi-Turn Context
**Objective**: Validate conversation context retention

**Steps**:
1. Continue from Test 1
2. Send: "tell me more about #2"
3. Observe response references previous message

**Expected Result**:
```
Bot Response (< 2s):
"Here are additional details about Sarah Johnson at Wells Fargo, Houston:

- **Role**: Senior Financial Advisor
- **Book Size**: $150M AUM
- **Production**: $1.2M L12Mo
- **Deal Stage**: Negotiation
- **Next Steps**: Contract review scheduled for 10/18
- **Owner**: Steve Perry"
```

**Success Criteria**:
- [ ] Correctly identifies "#2" from previous response
- [ ] Maintains context across turns
- [ ] Response time < 2 seconds (cached context)
- [ ] No 500 errors

---

### Test 3: Clarification Flow
**Objective**: Validate ambiguous query handling

**Steps**:
1. Send: "show me candidates"
2. Bot should request clarification
3. Select option from numbered list

**Expected Result**:
```
Bot Response:
"I need more information to help you. Please select what you're looking for:

1. Vault candidates (most marketable)
2. Recent candidate submissions
3. Candidates by location
4. Candidates by compensation range
5. All active candidates

Please reply with a number (1-5)"

User: "1"

Bot Response:
"Here are the top 5 most marketable vault candidates:
[Anonymized candidate list...]"
```

**Success Criteria**:
- [ ] Numbered options presented clearly
- [ ] User selection processed correctly
- [ ] Appropriate follow-up response
- [ ] Total interaction time < 5 seconds

---

### Test 4: Slash Command → Adaptive Card
**Objective**: Validate slash command with card rendering

**Steps**:
1. Type: `/digest advisors`
2. Press Enter
3. Observe adaptive card generation

**Expected Result**:
- Adaptive card with:
  - Header: "Weekly Candidate Digest - Advisors"
  - 5-10 candidate cards
  - Each card has "View Details" button
  - Formatting preserved (no text overflow)

**Success Criteria**:
- [ ] Card renders within 3 seconds
- [ ] All buttons visible and clickable
- [ ] Proper CSS styling (page-break-inside: avoid)
- [ ] No rendering errors in Teams

---

### Test 5: Button Click → InvokeResponse
**Objective**: Validate button interactions don't cause 500 errors

**Steps**:
1. From Test 4 card, click "View Details" button
2. Observe response
3. Check for errors

**Expected Result**:
```
Bot Response (Invoke):
"✅ Details for candidate #TWAV-2025-001:
- Full profile available in Zoho CRM
- Contact Steve Perry for more information
- Candidate is actively interviewing"
```

**Success Criteria**:
- [ ] No 500 error
- [ ] InvokeResponse returns status 200
- [ ] Confirmation message displayed
- [ ] No duplicate messages
- [ ] Response time < 1 second

---

## Advanced Test Scenarios

### Test 6: Executive Access Validation
**For executive users only (steve@, brandon@, daniel.romitelli@)**

**Steps**:
1. Login as executive user
2. Send: "show me all deals across all teams"
3. Verify full data access

**Expected**: Complete deal list without owner filtering

---

### Test 7: Error Handling
**Objective**: Validate graceful error handling

**Steps**:
1. Send: "show me data from 2020" (outside data range)
2. Send malformed query: "SELECT * FROM deals"
3. Send extremely long message (>1000 chars)

**Expected Results**:
- Helpful error messages
- No stack traces exposed
- Bot remains responsive

---

## Performance Metrics Checklist

### Response Times
| Scenario | Target | Actual | Pass/Fail |
|----------|--------|--------|-----------|
| Simple Query | < 3s | _____s | [ ] |
| Context Query | < 2s | _____s | [ ] |
| Clarification | < 1s | _____s | [ ] |
| Card Render | < 3s | _____s | [ ] |
| Button Click | < 1s | _____s | [ ] |

### Success Rates
| Metric | Target | Actual | Pass/Fail |
|--------|--------|--------|-----------|
| Query Success | > 99% | ____% | [ ] |
| Card Render | 100% | ____% | [ ] |
| Button Response | 100% | ____% | [ ] |
| Error Recovery | 100% | ____% | [ ] |

---

## Transcript Capture Requirements

### For Each Test:
1. **Screenshot**: Full Teams window showing conversation
2. **Timing Log**: Start/stop times for each interaction
3. **Error Log**: Any error messages or unexpected behavior
4. **Network Trace**: Browser DevTools network tab (if issues occur)

### Logging Format:
```
Test: [Test Number and Name]
Timestamp: [ISO 8601 format]
User Input: [Exact message sent]
Response Time: [milliseconds]
Response Type: [text/card/error]
Success: [true/false]
Notes: [Any observations]
```

---

## Issue Escalation

### Critical Issues (Stop Testing):
- 500 errors on any interaction
- Bot unresponsive > 30 seconds
- Data corruption or incorrect updates
- Security/authentication failures

### Non-Critical Issues (Document & Continue):
- Response time 3-5 seconds
- Minor formatting issues
- Non-blocking UI glitches

### Escalation Path:
1. Document issue with screenshots
2. Check Application Insights for errors
3. Notify development team via Teams
4. Create GitHub issue with reproduction steps

---

## Post-Test Validation

### Data Integrity Check:
```sql
-- Run in PostgreSQL to verify no test data corruption
SELECT COUNT(*) as test_queries
FROM teams_activity_logs
WHERE created_at > NOW() - INTERVAL '1 hour'
AND user_id LIKE '%test%';
```

### Application Insights Query:
```kusto
// Check for errors during test window
exceptions
| where timestamp > ago(1h)
| where cloud_RoleName == "teams-bot"
| summarize ErrorCount = count() by operation_Name
| order by ErrorCount desc
```

---

## Sign-Off

### QA Team:
- **Tester Name**: _________________________
- **Date/Time**: _________________________
- **All Tests Passed**: [ ] Yes [ ] No
- **Ready for Beta**: [ ] Yes [ ] No

### Development Team:
- **Reviewer**: _________________________
- **Issues Resolved**: [ ] Yes [ ] No [ ] N/A
- **Approved for Release**: [ ] Yes [ ] No

---

## Appendix: Common Teams Bot Commands

### Slash Commands:
- `/help` - Show all commands
- `/digest [audience]` - Generate digest (advisors/c_suite/global)
- `/preferences` - User settings
- `/analytics` - Usage statistics
- `/status` - Bot health check

### Natural Language Examples:
- "Show me recent deals"
- "Find candidates in New York"
- "Tell me about meetings this week"
- "What deals closed last month?"
- "Show me top vault candidates"

### Debug Commands (Admin Only):
- `/debug connection` - Test database connection
- `/debug cache` - Redis cache status
- `/debug zoho` - Zoho API status