# Response to Brandon's Feedback (9/5/2025)

Brandon,

Thank you for the detailed feedback! Here's the implementation plan addressing each point:

## Completed Items ✅
- **Steve's 3-record structure**: Backend and frontend now properly create Company/Contact/Deal records with all 21 fields
- **Test records cleaned**: Production Zoho environment is now clean

## Implementation Plan for Your Feedback

### 1. Duplicate Detection & Matching ✅
**Already Implemented**: Backend has PostgreSQL deduplication with exact and fuzzy matching
**Enhancement Needed**:
- Add UI modal for user to select existing record or create new when duplicates found
- Surface the duplicate detection results to the frontend

### 2. Dynamic Owner Assignment
**Current Issue**: Hardcoded owner
**Solution**:
- Detect current Outlook user via Office.context.mailbox.userProfile
- Map to Zoho user ID dynamically
- Pass owner through all record creation

### 3. Web Data Enrichment
**Requirements**:
- Company: Phone, website, address from web (not from sender's signature)
- Contact: Title, city, state, LinkedIn profile
**Solution**:
- Integrate Clearbit/Hunter.io API for company enrichment
- Use email domain to fetch company data
- Parse signature blocks with AI to extract contact details
- Filter out sender's own company info (detect via email domain match)

### 4. Import Tracking Fields
**New Fields to Add**:
- Import Batch field for tracking
- Import Description field
- Distribution Network (user-selectable dropdown)
- Estimated Req Quantity (numeric input)
- One Time Revenue (currency input)

### 5. Credit Attribution Logic
**Business Rules**:
- Default: BD Rep gets credit
- If referral detected: Referrer gets credit
- If from FP Transitions: Eric Leeper gets credit
- Make this user-editable before submission

### 6. User-Selectable Fields
**Before Record Creation**:
- Source dropdown (Email Inbound, Referral, etc.)
- Source Detail (free text)
- Distribution Network dropdown
- Who Gets Credit selection
- Estimated quantities and revenue

## Timeline
- **Week 1**: Duplicate detection, fuzzy matching, user selection modal
- **Week 2**: Web enrichment integration, signature parsing
- **Week 3**: New fields, import tracking, credit logic
- **Testing**: Continuous throughout
- **Deployment**: End of Week 3

## Technical Approach
1. **Duplicate Check**: Query Zoho before showing form
2. **Enrichment**: Parallel API calls during extraction
3. **UI Updates**: Additional fields in taskpane
4. **Validation**: Ensure owner can't be null
5. **Audit Trail**: Track all import batches

Would you like me to prioritize any specific items from this list?

Best,
Daniel