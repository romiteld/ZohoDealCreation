# Apollo.io Phone Number Discovery Documentation

## Overview

The Well Intake API now includes comprehensive phone number discovery capabilities powered by Apollo.io. This feature automatically discovers and validates phone numbers from multiple sources, differentiating between phone types and providing international formatting.

## Features

### 🔍 Comprehensive Discovery
- **Multiple Sources**: Discovers phones from email text, Apollo person records, and company data
- **Phone Type Classification**: Differentiates between mobile, work, company main line, executive, and recruiter phones
- **International Support**: Handles US, UK, Canadian, and international phone formats
- **Deduplication**: Automatically removes duplicate phone numbers
- **Confidence Scoring**: Provides confidence scores for discovered phones

### 📱 Phone Types Detected
- `mobile` - Personal mobile phones
- `work` - Office/desk phones
- `company_main` - Company reception/main line
- `executive` - C-level executive phones
- `recruiter` - HR/Talent acquisition phones
- `toll_free` - 1-800 numbers
- `fax` - Fax numbers

### 🌐 International Formatting
- E.164 format: `+14155551234`
- National format: `(415) 555-1234`
- International format: `+1 415 555 1234`
- RFC3966 format: `tel:+1-415-555-1234`

## API Endpoints

### 1. Extract Phone Numbers
**Endpoint**: `POST /api/apollo/extract/phones`

Discovers all available phone numbers for a person or company.

```bash
curl -X POST "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/apollo/extract/phones" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john.doe@example.com",
    "name": "John Doe",
    "company": "Example Corp",
    "include_company_phones": true,
    "include_employee_phones": true
  }'
```

**Request Parameters**:
- `email` (optional): Email address to search
- `name` (optional): Person's full name
- `company` (optional): Company name or domain
- `job_title` (optional): Job title for filtering
- `location` (optional): Location for filtering
- `include_company_phones` (bool): Include company main lines
- `include_employee_phones` (bool): Include employee phone numbers

**Response**:
```json
{
  "success": true,
  "primary_contact": {
    "name": "John Doe",
    "email": "john.doe@example.com",
    "title": "Senior Developer",
    "company": "Example Corp",
    "linkedin": "https://linkedin.com/in/johndoe",
    "location": "San Francisco, CA"
  },
  "phone_numbers": [
    {
      "number": "(415) 555-1234",
      "type": "mobile",
      "owner": "John Doe",
      "title": "Senior Developer",
      "confidence": 0.95,
      "international_format": "+1 415 555 1234",
      "raw_number": "4155551234"
    },
    {
      "number": "(415) 555-5678",
      "type": "work",
      "owner": "John Doe",
      "title": "Senior Developer",
      "confidence": 0.90,
      "international_format": "+1 415 555 5678",
      "raw_number": "4155555678"
    },
    {
      "number": "(800) 555-0000",
      "type": "company_main",
      "owner": "Example Corp",
      "title": "Main Line",
      "confidence": 0.99,
      "international_format": "+1 800 555 0000",
      "raw_number": "18005550000"
    }
  ],
  "company_info": {
    "name": "Example Corp",
    "domain": "example.com",
    "website": "https://www.example.com",
    "phone": "(800) 555-0000",
    "industry": "Technology",
    "employee_count": 500,
    "location": "San Francisco, CA"
  },
  "total_phones_found": 3,
  "data_completeness": 85.0,
  "metadata": {
    "search_params": {
      "email": "john.doe@example.com",
      "name": "John Doe",
      "company": "Example Corp"
    },
    "phone_type_breakdown": {
      "mobile": 1,
      "work": 1,
      "company_main": 1,
      "executive": 0,
      "recruiter": 0,
      "other": 0
    }
  }
}
```

### 2. Enrich Contact
**Endpoint**: `POST /api/apollo/enrich/contact`

Comprehensive contact enrichment including phone discovery.

```bash
curl -X POST "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/apollo/enrich/contact" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john.doe@example.com"
  }'
```

### 3. Search People
**Endpoint**: `GET /api/apollo/search/people`

Search for people with phone numbers.

```bash
curl -X GET "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/apollo/search/people?query=CEO%20Microsoft&limit=5" \
  -H "X-API-Key: your-api-key"
```

### 4. Search Companies
**Endpoint**: `GET /api/apollo/search/companies`

Search for companies with phone numbers.

```bash
curl -X GET "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/api/apollo/search/companies?query=Salesforce&limit=3" \
  -H "X-API-Key: your-api-key"
```

## Automatic Integration

### Email Processing Enhancement
The phone discovery feature is automatically integrated into the email processing pipeline:

1. **Initial Extraction**: Extracts phone numbers from email text
2. **Apollo Enrichment**: Searches Apollo for additional phone numbers
3. **Company Discovery**: Finds company main lines and employee phones
4. **Deduplication**: Removes duplicate numbers
5. **Formatting**: Applies international formatting standards
6. **Storage**: Saves all discovered phones with type classification

### LangGraph Integration
Phone discovery is built into the LangGraph extraction node:

```python
# Automatic phone discovery in extraction pipeline
if not result.get('phone'):
    # Search Apollo for person's phones
    apollo_person = await apollo_unlimited_people_search(
        email=result.get('email'),
        name=result.get('candidate_name')
    )

    # Extract all phone types
    phones = extract_all_phone_types(apollo_person)

    # Update result with primary phone
    if phones:
        result['phone'] = phones[0]['number']
```

## Phone Utilities

### Phone Validation
```python
from app.phone_utilities import PhoneNumberValidator

# Validate phone number
is_valid, error = PhoneNumberValidator.validate("+1 415 555 1234")

# Detect country
country = PhoneNumberValidator.detect_country("415-555-1234")  # Returns "US"

# Detect phone type
phone_type = PhoneNumberValidator.detect_phone_type("800-555-1234")  # Returns PhoneType.TOLL_FREE
```

### Phone Formatting
```python
from app.phone_utilities import PhoneNumberValidator

# Format phone number
formatted = PhoneNumberValidator.format("4155551234", country="US", international=True)
# Returns:
# {
#   "national": "(415) 555-1234",
#   "international": "+1 415 555 1234",
#   "e164": "+14155551234",
#   "rfc3966": "tel:+1-415-555-1234"
# }
```

### Phone Extraction from Text
```python
from app.phone_utilities import PhoneExtractor

# Extract phones from text
text = "Call me at (415) 555-1234 or my mobile 415.555.5678"
phones = PhoneExtractor.extract_from_text(text)
# Returns list of phone objects with context
```

## Configuration

### Environment Variables
Add to `.env.local`:

```bash
# Apollo.io API Configuration
APOLLO_API_KEY=your-apollo-api-key

# Phone Discovery Settings
APOLLO_PHONE_DISCOVERY_ENABLED=true
APOLLO_INCLUDE_COMPANY_PHONES=true
APOLLO_INCLUDE_EMPLOYEE_PHONES=true
APOLLO_MAX_EMPLOYEE_PHONES=5
```

### Phone Discovery Settings
Configure in `app/config_manager.py`:

```python
class PhoneDiscoveryConfig:
    enabled: bool = True
    include_company_phones: bool = True
    include_employee_phones: bool = True
    max_phones_per_search: int = 10
    confidence_threshold: float = 0.7
    validate_format: bool = True
    international_format: bool = True
```

## Testing

### Run Phone Discovery Tests
```bash
# Test phone discovery endpoints
python test_apollo_phone_discovery.py

# Test phone utilities
python -m pytest tests/test_phone_utilities.py

# Test with specific contact
curl -X POST "http://localhost:8000/api/apollo/extract/phones" \
  -H "X-API-Key: dev-key-only-for-testing" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "include_company_phones": true
  }'
```

## Performance

### Optimization Strategies
1. **Caching**: Phone discoveries are cached for 24 hours
2. **Batch Processing**: Multiple phone lookups in single API call
3. **Deduplication**: Prevents redundant API calls for same numbers
4. **Parallel Search**: Person and company searches run concurrently

### Rate Limits
- Apollo API: 100 requests per minute (Starter plan)
- Phone extraction: ~2-3 seconds per contact
- Bulk processing: 50 contacts per batch

## Best Practices

### 1. Always Validate
```python
# Validate before storing
is_valid, error = PhoneNumberValidator.validate(phone)
if is_valid:
    formatted = PhoneNumberValidator.format(phone)
    store_phone(formatted['e164'])
```

### 2. Use Type Classification
```python
# Different handling for different phone types
if phone_type == PhoneType.MOBILE:
    send_sms(phone)
elif phone_type == PhoneType.WORK:
    add_to_business_contacts(phone)
```

### 3. Handle International Numbers
```python
# Always store in E.164 format
normalized = PhoneNumberValidator.normalize(phone, target_format="e164")
```

### 4. Respect Privacy
- Only discover phones when necessary
- Store phone type metadata for compliance
- Allow users to opt-out of phone discovery

## Troubleshooting

### Common Issues

**No phones found**:
- Check Apollo API key is configured
- Verify email/name exists in Apollo database
- Try searching with company name

**Invalid format**:
- Use PhoneNumberValidator.clean_number() first
- Check country detection is correct
- Verify number has correct digit count

**Rate limits**:
- Implement exponential backoff
- Use caching to reduce API calls
- Batch multiple lookups together

### Debug Logging
Enable debug logging for phone discovery:

```python
import logging
logging.getLogger('app.apollo_enricher').setLevel(logging.DEBUG)
logging.getLogger('app.phone_utilities').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features
- [ ] SMS verification for mobile numbers
- [ ] WhatsApp/Signal detection
- [ ] Phone number scoring/quality assessment
- [ ] Historical phone number tracking
- [ ] International number validation for 150+ countries
- [ ] VoIP detection (Zoom, Teams, etc.)
- [ ] Phone carrier lookup
- [ ] Do Not Call list integration

### API Roadmap
- `POST /api/apollo/verify/phone` - Verify phone ownership
- `GET /api/apollo/phone/history` - Phone number history
- `POST /api/apollo/bulk/phones` - Bulk phone discovery
- `GET /api/apollo/phone/carrier` - Carrier information