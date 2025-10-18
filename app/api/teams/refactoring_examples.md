# Teams Bot NLP Text-Only Refactoring Examples

## Overview
This document shows before/after examples of the Teams bot refactoring from adaptive cards to text-only responses for a more conversational AI experience.

## 1. Low Confidence Clarification (<50% confidence)

### BEFORE: Adaptive Card Response
```json
{
  "type": "AdaptiveCard",
  "body": [
    {
      "type": "TextBlock",
      "text": "🤔 Need Clarification",
      "weight": "Bolder",
      "size": "Large"
    },
    {
      "type": "TextBlock",
      "text": "Could you provide more details?"
    },
    {
      "type": "Input.ChoiceSet",
      "id": "clarification_response",
      "choices": [
        {"title": "Search by Name", "value": "search_name"},
        {"title": "Search by Company", "value": "search_company"},
        {"title": "Search by Stage", "value": "search_stage"}
      ],
      "style": "expanded"
    }
  ],
  "actions": [
    {
      "type": "Action.Submit",
      "title": "✅ Submit"
    }
  ]
}
```

### AFTER: Text-Only Response
```
🤔 **I need a bit more information...**

_You asked: "show me recent activity"_

Could you provide more details? For example:

1️⃣ Search by candidate name
2️⃣ Search by company
3️⃣ View recent deal activity
4️⃣ Show recent meetings

💡 _Reply with a number (1-4) or type your specific request_
```

### User Response Flexibility (NEW)
- **Before:** Must click button in card
- **After:** Can respond with:
  - Numbers: `1`, `2`, `3`
  - Hash: `#1`, `option #2`
  - Words: `first`, `second`, `the third one`
  - Text: `name`, `company` (fuzzy matches)
  - Full: `Search by candidate name`

---

## 2. Medium Confidence Suggestion (50-80% confidence)

### BEFORE: Suggestion Card
```json
{
  "type": "AdaptiveCard",
  "body": [
    {
      "type": "TextBlock",
      "text": "Found 3 candidates matching your criteria",
      "size": "Medium"
    },
    {
      "type": "Container",
      "separator": true,
      "items": [
        {
          "type": "TextBlock",
          "text": "💡 I'm 65% confident. Need to refine?",
          "isSubtle": true,
          "size": "Small"
        }
      ]
    }
  ],
  "actions": [
    {
      "type": "Action.Submit",
      "title": "🔍 Refine Search"
    }
  ]
}
```

### AFTER: Inline Text Suggestion
```
Found 3 candidates matching your criteria:

1. **John Smith** - Senior Advisor
   📍 New York, NY | 💰 $500K comp
   📊 $2.5M AUM | Available Q1 2025

2. **Jane Doe** - Portfolio Manager
   📍 Chicago, IL | 💰 $750K comp

💡 _I'm 65% confident about this response._
_If this isn't what you're looking for, try being more specific or rephrase your question._
```

---

## 3. High Confidence Results (>80% confidence)

### BEFORE: Results Card
```json
{
  "type": "AdaptiveCard",
  "body": [
    {
      "type": "FactSet",
      "facts": [
        {"title": "Name:", "value": "John Smith"},
        {"title": "Location:", "value": "New York"},
        {"title": "AUM:", "value": "$2.5M"},
        {"title": "Comp:", "value": "$500K"}
      ]
    }
  ]
}
```

### AFTER: Formatted Text Results
```
✅ **Found 3 candidates matching your search**

1. **John Smith** - Senior Advisor
   📍 New York, NY | 💰 $500K comp
   📊 $2.5M AUM | Available Q1 2025

2. **Jane Doe** - Portfolio Manager
   📍 Chicago, IL | 💰 $750K comp
   📊 $5M AUM | Available immediately

3. **Robert Johnson** - Wealth Manager
   📍 Boston, MA | 💰 $400K comp
   📊 $1.8M AUM | Available Q2 2025
```

---

## 4. Error Handling

### BEFORE: Error Card
```json
{
  "type": "AdaptiveCard",
  "body": [
    {
      "type": "TextBlock",
      "text": "⏱️ Too Many Requests",
      "weight": "Bolder",
      "color": "Attention"
    },
    {
      "type": "TextBlock",
      "text": "Rate limit exceeded. Wait a few minutes."
    }
  ]
}
```

### AFTER: Conversational Error
```
⏱️ **Too Many Requests**

You've been asking questions pretty quickly! Please wait a few minutes before trying again.

_Rate limit: 3 clarifications per 5 minutes_
```

---

## 5. Conversation Flow Example

### Full Conversation (Text-Only)

**User:** "show me the good ones"

**Bot:**
```
🤔 **I need a bit more information...**

_You asked: "show me the good ones"_

What are you looking for?

1️⃣ Top performing advisors
2️⃣ High-value deals
3️⃣ Best candidates by AUM
4️⃣ Highly rated team members

💡 _Reply with a number (1-4) or type your specific request_
```

**User:** "3"

**Bot:**
```
✅ **Top 5 Candidates by AUM**

1. **Michael Chen** - Portfolio Manager
   📍 San Francisco, CA | 💰 $1.2M comp
   📊 $15M AUM | Available immediately

2. **Sarah Williams** - Senior Advisor
   📍 Chicago, IL | 💰 $850K comp
   📊 $12M AUM | Available Q1 2025

3. **David Martinez** - Wealth Manager
   📍 Miami, FL | 💰 $750K comp
   📊 $9.5M AUM | Available Q2 2025

4. **Emily Johnson** - Investment Advisor
   📍 Boston, MA | 💰 $600K comp
   📊 $7.2M AUM | Available immediately

5. **James Wilson** - Senior Associate
   📍 Dallas, TX | 💰 $500K comp
   📊 $6.8M AUM | Available Q1 2025
```

**User:** "tell me more about #2"

**Bot:**
```
📋 **Sarah Williams - Detailed Profile**

**Current Role:** Senior Advisor at Wealth Management Corp
**Location:** Chicago, IL (Open to remote)
**Experience:** 12 years in wealth management

**Financial Metrics:**
• 📊 AUM: $12M
• 💰 Current Comp: $850K
• 📈 Production L12Mo: $2.1M
• 🎯 Desired Comp: $900K-1.1M

**Availability:**
• When: Q1 2025
• Notice Period: 60 days
• Non-compete: None

**Specializations:**
• High Net Worth Individuals
• Estate Planning
• Tax-efficient Strategies
• Alternative Investments

**Licenses:** Series 7, 66, Insurance
**Designations:** CFP, ChFC

💡 _Would you like to see similar candidates or schedule an introduction?_
```

---

## Key Improvements

### 1. **Natural Conversation Flow**
- No button clicking required
- Flexible input parsing
- Context-aware responses

### 2. **Better Readability**
- Markdown formatting with **bold** and _italics_
- Emojis for visual hierarchy
- Structured bullet points
- Clear sections

### 3. **Analytics Tracking**
- Every clarification logged to `conversation_clarifications` table
- Response methods tracked (number, text, hash, fuzzy)
- Time-to-response metrics
- Success rates per user

### 4. **User Experience**
- Faster interactions (no card rendering)
- Works better on mobile
- Accessible for screen readers
- More personal feel

### 5. **Developer Benefits**
- Simpler code (no complex card JSON)
- Easier to test and maintain
- Better logging and debugging
- Reusable formatting functions

---

## Migration Notes

### Files Modified
1. **New Files:**
   - `app/api/teams/nlp_formatters.py` - Text formatting helpers
   - `app/api/teams/nlp_parser.py` - Input parsing utilities
   - `migrations/014_conversation_clarifications_tracking.sql` - Analytics table

2. **Modified Files:**
   - `app/api/teams/routes.py` - Refactored NLP handlers (lines 630-810)

### Backward Compatibility
- Slash commands (`/help`, `/digest`, etc.) still use cards
- Admin functions maintain card interfaces
- Only natural language queries converted to text

### Testing Checklist
- [ ] Low confidence clarifications display as text
- [ ] Medium confidence suggestions show inline
- [ ] High confidence results format properly
- [ ] Number responses work (1, 2, 3)
- [ ] Hash notation works (#1, #2)
- [ ] Text matching works (fuzzy)
- [ ] Analytics tracking captures all interactions
- [ ] Error messages display conversationally
- [ ] Memory manager stores text responses
- [ ] Follow-up questions maintain context