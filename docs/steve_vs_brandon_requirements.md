# Steve's Requirements (PRIORITY) vs Brandon's Additions

## Steve's Core Requirements (DO NOT CHANGE)
✅ **3-Record Structure**: Company, Contact, Deal (not mixed "client information")
✅ **21 Specific Fields**:
- Company Record (7): Company Name, Phone, Website, Company Source, Source Detail, Who Gets Credit, Detail
- Contact Record (8): First Name, Last Name, Company Name, Email, Phone, City, State, Source
- Deal Record (6): Deal Name, Pipeline, Closing Date, Source Detail, Description of Reqs

✅ **Deal Name Format**: `[Job Title] ([Location]) [Company Name]`
✅ **Clean separation of records in Zoho**

## Brandon's Additions (SAFE TO ADD - Don't conflict with Steve)

### ✅ SAFE ADDITIONS (Enhance Steve's structure):
1. **Dynamic Owner Assignment** - Steve didn't specify owner, so using current user is fine
2. **Web Enrichment** - Enhances Steve's existing fields (Company Phone, Website, Contact City/State)
3. **LinkedIn Profile** - New field addition, doesn't conflict
4. **Import Batch/Description** - Metadata fields, don't affect Steve's structure
5. **Distribution Network** - New field, doesn't conflict
6. **Estimated Req Quantity & One Time Revenue** - New fields, don't conflict
7. **Duplicate Detection UI** - Improves UX, doesn't change data structure

### ⚠️ POTENTIAL CONFLICTS TO HANDLE CAREFULLY:
1. **Who Gets Credit Logic**
   - Steve has "Who Gets Credit" field with options: BD Rep, Affiliate, Both
   - Brandon wants: BD Rep (default), Referral, FP Transitions → Eric Leeper
   - **Solution**: Keep Steve's field structure, just enhance the logic for auto-population

2. **Source Fields**
   - Steve has "Company Source" and "Source Detail"
   - Brandon wants these user-selectable
   - **Solution**: Make them dropdowns as Brandon wants, but keep Steve's field names

3. **Owner Fields**
   - Steve doesn't specify owner
   - Brandon wants dynamic owner (current user)
   - **Solution**: Add owner fields but don't remove any of Steve's fields

## Implementation Priority:
1. **First**: Ensure Steve's 21 fields and 3-record structure work perfectly
2. **Then**: Add Brandon's enhancements that don't conflict
3. **Finally**: Carefully implement Brandon's logic that enhances Steve's fields

## What NOT to Do:
- Don't change the 3-record structure
- Don't rename Steve's fields
- Don't change Deal Name format
- Don't merge records back into "client information"
- Don't remove any of Steve's 21 fields

## Safe Implementation Plan:
```javascript
// Steve's structure stays exactly the same
class CompanyRecord {
    // Steve's 7 fields - NO CHANGES
    company_name: string
    phone: string
    website: string
    company_source: string
    source_detail: string
    who_gets_credit: string
    detail: string

    // Brandon's additions (safe to add)
    owner: string  // dynamic from current user
    import_batch: string
    distribution_network: string
}

class ContactRecord {
    // Steve's 8 fields - NO CHANGES
    first_name: string
    last_name: string
    company_name: string
    email: string
    phone: string
    city: string
    state: string
    source: string

    // Brandon's additions (safe to add)
    owner: string
    linkedin_profile: string
    title: string  // from enrichment
    import_description: string
}

class DealRecord {
    // Steve's 6 fields - NO CHANGES
    deal_name: string  // MUST stay as [Job Title] ([Location]) [Company Name]
    pipeline: string
    closing_date: string
    source_detail: string
    description_of_reqs: string

    // Brandon's additions (safe to add)
    owner: string
    estimated_req_quantity: number
    one_time_revenue: number
}
```

## Summary:
Brandon's requirements mostly ENHANCE Steve's structure without breaking it. We can add all of Brandon's features as long as we:
1. Keep Steve's exact 21-field structure
2. Keep the 3-record separation
3. Keep Deal Name format
4. Add Brandon's fields as additions, not replacements