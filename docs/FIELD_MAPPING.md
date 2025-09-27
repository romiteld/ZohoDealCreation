# Field Mapping: Extracted Data to Zoho CRM

This document maps extracted financial advisor data fields to corresponding Zoho CRM fields, based on Brandon's candidate alert format and business requirements.

## Core Mapping Structure

### Contact Record Fields

| Extracted Field | Zoho Field | Data Type | Notes |
|----------------|------------|-----------|--------|
| `first_name` | `First_Name` | String | Split from full name extraction |
| `last_name` | `Last_Name` | String | Split from full name extraction |
| `email` | `Email` | Email | Primary contact method |
| `phone` | `Phone` | Phone | Mobile preferred |
| `city` | `Mailing_City` | String | From geographic extraction |
| `state` | `Mailing_State` | String | 2-letter state code |
| `linkedin_url` | `LinkedIn_URL` | URL | Custom field for social presence |

### Deal Record Fields

| Extracted Field | Zoho Field | Data Type | Business Rule |
|----------------|------------|-----------|---------------|
| `deal_name` | `Deal_Name` | String | Format: `"[Title] ([Location]) - [Firm]"` |
| `role_title` | `Deal_Name` | String | Embedded in deal name format |
| `location` | `Deal_Name` | String | Geographic component of deal name |
| `source` | `Source` | Picklist | Business logic determines value |
| `referrer_name` | `Source_Detail` | String | When source = "Referral" |
| `compensation_range` | `Expected_Revenue` | Currency | Extract OTE/base amounts |
| `availability` | `Description` | Text Area | Timeline and notice period |

### Company Record Fields

| Extracted Field | Zoho Field | Data Type | Notes |
|----------------|------------|-----------|--------|
| `company_name` | `Account_Name` | String | Current/target employer |
| `phone` | `Phone` | Phone | Company main line |
| `website` | `Website` | URL | Company domain |
| `location` | `Billing_Address` | Address | Company headquarters |

## Financial Advisor Specific Fields

### Custom Zoho Fields for Advisor Data

| Extracted Pattern | Custom Zoho Field | Field Type | Example Values |
|------------------|-------------------|------------|----------------|
| AUM amounts | `Assets_Under_Management` | Currency | `2200000000` (for $2.2B) |
| AUM growth | `AUM_Growth_Story` | Text | `"$43M to $72M in 2 years"` |
| Client count | `Client_Count` | Number | `250` |
| HNW client count | `HNW_Client_Count` | Number | `250` |
| Years experience | `Years_Experience` | Number | `30` |
| Production amount | `Annual_Production` | Currency | `5000000` (for $5M) |
| Close rate | `Close_Rate_Percent` | Number | `47` |
| Performance ranking | `Performance_Ranking` | Text | `"Top 1-3 nationally"` |
| Career progression | `Career_Progression` | Text Area | `"Began as commodities broker, progressed to leadership roles"` |

### License and Designation Fields

| Extracted Pattern | Custom Zoho Field | Field Type | Example Values |
|------------------|-------------------|------------|----------------|
| Series licenses | `Series_Licenses` | Multi-select | `"7,24,55,65,66"` |
| License status | `License_Status` | Picklist | `"Active"`, `"Inactive"`, `"Reactivatable"` |
| CFA status | `CFA_Status` | Picklist | `"Charterholder"`, `"In Progress"`, `"Not Applicable"` |
| CFP status | `CFP_Status` | Picklist | `"Certified"`, `"In Progress"`, `"Since 2000"` |
| Other designations | `Other_Designations` | Multi-select | `"CPWA,WMCP,CTFA"` |
| State licenses | `State_Licenses` | Text | `"CA Life License"` |

### Values and Cultural Fit Fields

| Extracted Pattern | Custom Zoho Field | Field Type | Usage |
|------------------|-------------------|------------|--------|
| Personal values | `Personal_Values` | Text Area | Direct extraction from values statements |
| Career motivations | `Career_Motivations` | Text Area | What they seek in next role |
| Work style preferences | `Work_Style_Preferences` | Text Area | Autonomy, accountability, direction needs |
| Specializations | `Technical_Specializations` | Multi-select | Portfolio construction, planning, etc. |

## Geographic and Mobility Mapping

### Location Fields

| Extracted Pattern | Zoho Field Mapping | Processing Rule |
|------------------|-------------------|-----------------|
| `City, State (Is Mobile)` | `Current_City`, `Current_State`, `Is_Mobile: True` | Split location, set mobility flag |
| `City, State (Is not mobile)` | `Current_City`, `Current_State`, `Is_Mobile: False` | Location constraint |
| `Open to Remote/Hybrid` | `Remote_Preference` | Boolean field |
| `will drive up to X hours` | `Drive_Radius_Hours` | Number field |
| `strong relocation interest to CA` | `Relocation_Interest` | Text field |

### Custom Mobility Fields

| Field Name | Field Type | Purpose |
|------------|------------|---------|
| `Is_Mobile` | Boolean | Can relocate for opportunities |
| `Remote_Preference` | Picklist | `"Remote Only"`, `"Hybrid OK"`, `"In-Person Only"` |
| `Drive_Radius_Hours` | Number | Maximum commute distance |
| `Relocation_Interest` | Text | Target regions for relocation |
| `Current_City` | String | Present location |
| `Current_State` | String | Present state |

## Compensation and Availability Mapping

### Compensation Fields

| Extracted Pattern | Zoho Field | Processing Rule | Example |
|------------------|------------|-----------------|---------|
| `$150K-$200K OTE` | `Min_Compensation`, `Max_Compensation`, `Compensation_Type` | Split range, set type | Min: 150000, Max: 200000, Type: "OTE" |
| `$250K base; $300K-$350K OTE` | `Base_Salary`, `Min_OTE`, `Max_OTE` | Parse multiple components | Base: 250000, Min OTE: 300000, Max OTE: 350000 |
| `$750K - $1M` | `Min_Compensation`, `Max_Compensation` | Executive range | Min: 750000, Max: 1000000 |

### Availability Fields

| Extracted Pattern | Zoho Field | Processing Rule |
|------------------|------------|-----------------|
| `Available on 2 weeks' notice` | `Notice_Period`, `Availability_Status` | Extract timeframe |
| `Available immediately` | `Notice_Period`, `Availability_Status` | Set to immediate |
| `Available on 2-4 weeks' notice` | `Notice_Period_Min`, `Notice_Period_Max` | Range extraction |

## Business Logic for Source Determination

### Source Field Mapping Rules

```python
def determine_source(extracted_data):
    """Business logic for Source field based on email content"""

    if extracted_data.get('referrer_name'):
        return {
            'Source': 'Referral',
            'Source_Detail': extracted_data['referrer_name']
        }
    elif 'TWAV' in extracted_data.get('ref_code', ''):
        return {
            'Source': 'Reverse Recruiting',
            'Source_Detail': 'The Well Advisor Vault'
        }
    elif 'calendly' in extracted_data.get('email_content', '').lower():
        return {
            'Source': 'Website Inbound',
            'Source_Detail': 'Calendly Booking'
        }
    else:
        return {
            'Source': 'Email Inbound',
            'Source_Detail': 'Direct Email'
        }
```

### Deal Name Formatting Logic

```python
def format_deal_name(extracted_data):
    """Generate standardized deal names"""

    job_title = extracted_data.get('role_title', 'Unknown')
    location = f"{extracted_data.get('city', 'Unknown')}, {extracted_data.get('state', 'Unknown')}"
    firm_name = extracted_data.get('company_name', 'Unknown')

    return f"{job_title} ({location}) - {firm_name}"
```

## Data Validation and Quality Rules

### Required Field Validation

| Field Category | Required Fields | Validation Rule |
|---------------|----------------|------------------|
| Contact | `First_Name`, `Last_Name`, `Email` | Must be present and valid format |
| Financial | `Assets_Under_Management` OR `Years_Experience` | At least one financial metric required |
| Geographic | `Current_City`, `Current_State` | Must be valid US city/state |
| Compensation | `Min_Compensation` OR `Max_Compensation` | At least one compensation data point |

### Data Quality Flags

| Quality Issue | Flag Field | Auto-Flagging Logic |
|--------------|------------|---------------------|
| Missing AUM | `Missing_Financial_Data` | No AUM, production, or client count |
| Vague Location | `Location_Unclear` | Generic or multi-city location |
| No Licenses | `Missing_Credentials` | No series licenses or designations |
| Comp Range Too Wide | `Compensation_Unclear` | Range > 100% of minimum |

## Integration with Existing Zoho Structure

### Standard Zoho Fields (Preserve)

| Field | Keep As-Is | Notes |
|-------|------------|--------|
| `Owner` | Use `ZOHO_DEFAULT_OWNER_EMAIL` | Never hardcode IDs |
| `Created_Time` | Auto-populated | System field |
| `Modified_Time` | Auto-populated | System field |
| `Record_Image` | Default | No custom images needed |

### Custom Field Additions (New)

| Field Group | New Fields Needed | Purpose |
|-------------|-------------------|---------|
| Financial Metrics | `Assets_Under_Management`, `Client_Count`, `Annual_Production` | Core advisor metrics |
| Credentials | `Series_Licenses`, `CFA_Status`, `CFP_Status` | Qualification tracking |
| Mobility | `Is_Mobile`, `Remote_Preference`, `Drive_Radius_Hours` | Placement logistics |
| Performance | `Performance_Ranking`, `Close_Rate_Percent` | Track record validation |

## API Field Mapping for Zoho v8

### Contact Creation Payload

```json
{
  "data": [
    {
      "First_Name": "{extracted.first_name}",
      "Last_Name": "{extracted.last_name}",
      "Email": "{extracted.email}",
      "Phone": "{extracted.phone}",
      "Mailing_City": "{extracted.city}",
      "Mailing_State": "{extracted.state}",
      "Assets_Under_Management": "{extracted.aum_amount}",
      "Years_Experience": "{extracted.years_experience}",
      "Series_Licenses": "{extracted.series_licenses}",
      "Personal_Values": "{extracted.personal_values}",
      "Is_Mobile": "{extracted.is_mobile}",
      "Owner": "{ZOHO_DEFAULT_OWNER_EMAIL}"
    }
  ]
}
```

### Deal Creation Payload

```json
{
  "data": [
    {
      "Deal_Name": "{formatted_deal_name}",
      "Source": "{determined_source}",
      "Source_Detail": "{source_detail}",
      "Expected_Revenue": "{extracted.compensation_max}",
      "Contact_Name": "{contact_id}",
      "Account_Name": "{account_id}",
      "Stage": "Qualification",
      "Owner": "{ZOHO_DEFAULT_OWNER_EMAIL}"
    }
  ]
}
```

## Error Handling and Fallbacks

### Missing Data Fallbacks

| Missing Field | Fallback Value | Business Logic |
|--------------|----------------|----------------|
| `company_name` | "Unknown Firm" | Create generic company record |
| `role_title` | "Financial Advisor" | Default professional title |
| `compensation` | NULL | Leave empty, flag for follow-up |
| `location` | Extract from email metadata | Use email domain/IP geolocation |

### Data Transformation Rules

| Raw Extract | Transform Rule | Zoho Value |
|-------------|---------------|------------|
| "$2.2B" | Convert to numeric | 2200000000 |
| "Series 7, 63, 65" | Split and format | ["7", "63", "65"] |
| "2 weeks' notice" | Extract number | 14 (days) |
| "Top 1-3 nationally" | Preserve text | "Top 1-3 nationally" |

This mapping ensures comprehensive capture of Brandon's candidate data while maintaining Zoho CRM integration standards and business process requirements.