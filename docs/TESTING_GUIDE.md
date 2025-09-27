# Financial Advisor Extraction Testing Guide

This guide provides comprehensive testing methodologies for validating financial advisor data extraction using Brandon's real candidate examples.

## Testing Framework Overview

### Test Categories
1. **Pattern Recognition Tests** - Verify regex patterns capture data correctly
2. **Field Mapping Tests** - Ensure extracted data maps to correct Zoho fields
3. **Business Logic Tests** - Validate deal name formatting and source determination
4. **Edge Case Tests** - Handle incomplete or ambiguous data
5. **Integration Tests** - End-to-end extraction and CRM creation
6. **Regression Tests** - Ensure new patterns don't break existing functionality

## Test Data Samples

### Complete Test Cases from Brandon's Examples

#### Test Case 1: CIO/CGO Candidate (High AUM, Executive Level)
**Input Text:**
```
‼️ CIO / CGO Candidate Alert 🔔
📍 Jacksonville, FL (Is Mobile within SE/SW USA)
• Built $2.2B RIA from inception alongside founder; led portfolio design, investment modeling, and firmwide scaling initiatives
• CFA charterholder who passed all 3 levels consecutively
• Formerly held Series 7, 24, 55, 65, and 66; comfortable reactivating licenses if needed
• Passionate about macroeconomics and portfolio construction; led investment due diligence and model customization across 7 strategies
• Values: honesty, sincerity, and self-awareness; thrives in roles with autonomy, high accountability, and clear direction
• Available on 2 weeks' notice; desired comp $150K-$200K OTE
Ref code: TWAV117903
```

**Expected Extraction:**
```json
{
  "role_title": "CIO / CGO",
  "location": "Jacksonville, FL",
  "mobility": "Mobile within SE/SW USA",
  "aum_amount": 2200000000,
  "aum_context": "Built from inception",
  "designations": ["CFA"],
  "cfa_notes": "Passed all 3 levels consecutively",
  "licenses": ["7", "24", "55", "65", "66"],
  "license_status": "Formerly held, reactivatable",
  "specializations": ["macroeconomics", "portfolio construction"],
  "values": "honesty, sincerity, and self-awareness",
  "work_preferences": "autonomy, high accountability, clear direction",
  "availability": "2 weeks' notice",
  "compensation_min": 150000,
  "compensation_max": 200000,
  "compensation_type": "OTE",
  "ref_code": "TWAV117903"
}
```

#### Test Case 2: Private Wealth Advisor (Growth Story, Multiple Metrics)
**Input Text:**
```
‼️ Private Wealth / Advisor Candidate Alert 🔔
📍 St. Louis, MO (Is not mobile; Open to Remote/Hybrid Opportunities)
• 15+ years in financial services; currently manages $350M AUM across 65 relationships at private wealth division
• Previously grew a $43M book to $72M in 2 years at National Firm
• Holds CFA charter and Bachelor's in Finance; prior Series 7, 66, Life & Health (currently inactive but can be reactivated if needed)
• Values: Integrity, Candidness, and High Achievement; thrives in competitive environments
• Available on 2-4 weeks' notice; desired comp $200K OTE
Ref code: TWAV117821
```

**Expected Extraction:**
```json
{
  "role_title": "Private Wealth / Advisor",
  "location": "St. Louis, MO",
  "mobility": "Not mobile",
  "remote_preference": "Remote/Hybrid OK",
  "years_experience": 15,
  "aum_current": 350000000,
  "client_count": 65,
  "aum_growth": "43M to 72M in 2 years",
  "designations": ["CFA"],
  "education": "Bachelor's in Finance",
  "licenses": ["7", "66", "Life & Health"],
  "license_status": "Currently inactive, reactivatable",
  "values": "Integrity, Candidness, and High Achievement",
  "work_style": "thrives in competitive environments",
  "availability": "2-4 weeks' notice",
  "compensation_amount": 200000,
  "compensation_type": "OTE"
}
```

#### Test Case 3: Entry Level with Strong Metrics
**Input Text:**
```
‼️ Advisor Candidate Alert 🔔
📍 Orlando, FL (Is not mobile; Open to Remote/Hybrid Opportunities)
• Recent graduate with BA in Sales; studied sales with hands-on cold calling and pitching experience
• Holds active Series 7, 63, and 65 licenses; plans to pursue CFA and CFP
• Client-facing roles at 2 national firms; regularly handles 30–50 calls/day
• Strong service orientation; praised for empathy, conflict resolution, and calming client fears
• Values: trust, loyalty, and perseverance; seeks long-term growth into full advisory role
• Available on 2 weeks' notice; desired comp $80K-$100K
Ref code: TWAV117758
```

**Expected Extraction:**
```json
{
  "role_title": "Advisor",
  "location": "Orlando, FL",
  "mobility": "Not mobile",
  "remote_preference": "Remote/Hybrid OK",
  "education": "BA in Sales",
  "licenses": ["7", "63", "65"],
  "license_status": "Active",
  "designations_planned": ["CFA", "CFP"],
  "call_volume": "30-50 calls/day",
  "soft_skills": ["empathy", "conflict resolution"],
  "values": "trust, loyalty, and perseverance",
  "career_goals": "long-term growth into full advisory role",
  "availability": "2 weeks' notice",
  "compensation_min": 80000,
  "compensation_max": 100000
}
```

## Pattern Recognition Test Suite

### AUM Pattern Tests

```python
def test_aum_patterns():
    test_cases = [
        ("Built $2.2B RIA from inception", {"amount": 2200000000, "context": "Built from inception"}),
        ("manages $350M AUM across 65 relationships", {"amount": 350000000, "clients": 65}),
        ("grew a $43M book to $72M in 2 years", {"growth_from": 43000000, "growth_to": 72000000}),
        ("$10M+ in AUM from scratch", {"amount": 10000000, "qualifier": "minimum", "context": "from scratch"}),
        ("growing AUM from ~$150M to $720M", {"growth_from": 150000000, "growth_to": 720000000}),
        ("$1.5B+ in client assets", {"amount": 1500000000, "qualifier": "minimum"})
    ]

    for text, expected in test_cases:
        result = extract_aum_data(text)
        assert result == expected, f"AUM extraction failed for: {text}"
```

### License Pattern Tests

```python
def test_license_patterns():
    test_cases = [
        ("Series 7, 24, 55, 65, and 66", {"licenses": ["7", "24", "55", "65", "66"]}),
        ("active Series 7, 63, and 65", {"licenses": ["7", "63", "65"], "status": "active"}),
        ("formerly held Series 7, 66", {"licenses": ["7", "66"], "status": "formerly held"}),
        ("currently inactive but can be reactivated", {"status": "inactive, reactivatable"}),
        ("CA Life License", {"state_licenses": ["CA Life"]})
    ]

    for text, expected in test_cases:
        result = extract_license_data(text)
        assert result == expected, f"License extraction failed for: {text}"
```

### Designation Pattern Tests

```python
def test_designation_patterns():
    test_cases = [
        ("CFA charterholder who passed all 3 levels consecutively",
         {"designation": "CFA", "status": "charterholder", "note": "passed all 3 levels consecutively"}),
        ("CFP® since 2000", {"designation": "CFP", "since": 2000}),
        ("currently completing CFP certification", {"designation": "CFP", "status": "in progress"}),
        ("plans to pursue CFA and CFP", {"planned": ["CFA", "CFP"]}),
        ("Holds CPWA designation", {"designation": "CPWA", "status": "holds"})
    ]

    for text, expected in test_cases:
        result = extract_designation_data(text)
        assert result == expected, f"Designation extraction failed for: {text}"
```

## Business Logic Tests

### Deal Name Formatting Tests

```python
def test_deal_name_formatting():
    test_cases = [
        ({
            "role_title": "CIO / CGO",
            "city": "Jacksonville",
            "state": "FL",
            "company_name": "ABC Wealth Management"
        }, "CIO / CGO (Jacksonville, FL) - ABC Wealth Management"),

        ({
            "role_title": "Private Wealth Advisor",
            "city": "St. Louis",
            "state": "MO",
            "company_name": None
        }, "Private Wealth Advisor (St. Louis, MO) - Unknown"),

        ({
            "role_title": None,
            "city": "Orlando",
            "state": "FL",
            "company_name": "XYZ Financial"
        }, "Unknown (Orlando, FL) - XYZ Financial")
    ]

    for input_data, expected in test_cases:
        result = format_deal_name(input_data)
        assert result == expected, f"Deal name formatting failed for: {input_data}"
```

### Source Determination Tests

```python
def test_source_determination():
    test_cases = [
        ({"ref_code": "TWAV117903", "referrer_name": None},
         {"source": "Reverse Recruiting", "source_detail": "The Well Advisor Vault"}),

        ({"referrer_name": "John Smith", "ref_code": "REF123"},
         {"source": "Referral", "source_detail": "John Smith"}),

        ({"email_content": "scheduled via calendly", "ref_code": None},
         {"source": "Website Inbound", "source_detail": "Calendly Booking"}),

        ({"ref_code": None, "referrer_name": None},
         {"source": "Email Inbound", "source_detail": "Direct Email"})
    ]

    for input_data, expected in test_cases:
        result = determine_source(input_data)
        assert result == expected, f"Source determination failed for: {input_data}"
```

## Edge Case Testing

### Incomplete Data Tests

```python
def test_incomplete_data_handling():
    """Test extraction with missing or partial information"""

    edge_cases = [
        # Missing compensation
        ("Available immediately; seeking new opportunities",
         {"availability": "immediately", "compensation": None}),

        # Vague AUM reference
        ("significant AUM growth over 5 years",
         {"aum_growth": "significant over 5 years", "quantified": False}),

        # Complex location
        ("Remote within Eastern US; will consider relocation",
         {"location": "Remote", "region": "Eastern US", "relocation": True}),

        # Multiple compensation structures
        ("$250K base; $300K-$350K OTE; $500K stretch target",
         {"base": 250000, "ote_min": 300000, "ote_max": 350000, "stretch": 500000})
    ]

    for text, expected in edge_cases:
        result = extract_with_fallbacks(text)
        assert_partial_match(result, expected)
```

### Ambiguous Data Tests

```python
def test_ambiguous_data_resolution():
    """Test handling of ambiguous or conflicting information"""

    ambiguous_cases = [
        # Multiple AUM references
        ("Previously managed $100M, currently overseeing $200M in client assets",
         {"previous_aum": 100000000, "current_aum": 200000000}),

        # License status confusion
        ("Series 7 and 66 (may need reactivation)",
         {"licenses": ["7", "66"], "status": "may need reactivation"}),

        # Conflicting mobility
        ("Based in NYC but open to relocation within tri-state area",
         {"location": "NYC", "mobility": "regional", "region": "tri-state area"})
    ]

    for text, expected in ambiguous_cases:
        result = extract_ambiguous_data(text)
        assert_contains_keys(result, expected.keys())
```

## Integration Testing

### End-to-End Email Processing Test

```python
def test_full_email_processing():
    """Test complete email extraction and Zoho record creation"""

    # Use Brandon's real example
    sample_email = """
    ‼️ Lead Advisor Candidate Alert 🔔
    📍 Marietta, GA (Is Mobile; strong relocation interest to CA or PNW)
    • 25+ years in financial services with advisory, trading, and planning experience
    • Managed $1.5B+ in client assets; clientele range from $5M to $300M+
    • Proven top-tier producer: consistent President's Club and Circle of Champions
    • Licensed with Series 7 & 66; open to obtaining life/insurance license if required
    • Seeking lead advisor role with focus on client conversion and relationship management
    • Available on 2 weeks' notice; desired comp $200K-$250K+ OTE
    Ref code: TWAV101673
    """

    # Process email
    extraction_result = process_email(sample_email)

    # Validate extraction
    assert extraction_result['role_title'] == "Lead Advisor"
    assert extraction_result['years_experience'] == 25
    assert extraction_result['aum_amount'] == 1500000000
    assert extraction_result['licenses'] == ["7", "66"]
    assert extraction_result['compensation_min'] == 200000
    assert extraction_result['compensation_max'] == 250000

    # Test Zoho record creation
    contact_record = create_contact_record(extraction_result)
    deal_record = create_deal_record(extraction_result, contact_record['id'])

    # Validate Zoho field mapping
    assert contact_record['Assets_Under_Management'] == 1500000000
    assert contact_record['Years_Experience'] == 25
    assert contact_record['Is_Mobile'] == True
    assert deal_record['Deal_Name'] == "Lead Advisor (Marietta, GA) - Unknown"
    assert deal_record['Expected_Revenue'] == 250000
```

## Performance Testing

### Extraction Speed Tests

```python
def test_extraction_performance():
    """Ensure extraction completes within performance requirements"""

    import time

    # Test with various email sizes
    email_sizes = [
        ("small", 500),    # ~500 characters
        ("medium", 2000),  # ~2000 characters
        ("large", 5000)    # ~5000 characters
    ]

    for size_name, char_count in email_sizes:
        test_email = generate_test_email(char_count)

        start_time = time.time()
        result = extract_advisor_data(test_email)
        end_time = time.time()

        processing_time = end_time - start_time

        # Should complete within 2 seconds for any size
        assert processing_time < 2.0, f"{size_name} email took {processing_time}s"
        assert result is not None, f"Failed to extract from {size_name} email"
```

## Validation Test Suite

### Data Quality Tests

```python
def test_data_quality_validation():
    """Test data quality flags and validation rules"""

    quality_tests = [
        # Missing financial data
        ({}, ["missing_financial_data"]),

        # Vague location
        ({"location": "Remote"}, ["location_unclear"]),

        # No credentials
        ({"licenses": [], "designations": []}, ["missing_credentials"]),

        # Wide compensation range
        ({"compensation_min": 50000, "compensation_max": 200000}, ["compensation_unclear"]),

        # Complete profile (no flags)
        ({
            "aum_amount": 100000000,
            "location": "Chicago, IL",
            "licenses": ["7", "66"],
            "compensation_min": 150000,
            "compensation_max": 175000
        }, [])
    ]

    for data, expected_flags in quality_tests:
        flags = validate_data_quality(data)
        assert set(flags) == set(expected_flags), f"Quality validation failed for {data}"
```

## Regression Testing

### Backward Compatibility Tests

```python
def test_backward_compatibility():
    """Ensure new patterns don't break existing functionality"""

    # Historical test cases that should continue working
    legacy_cases = load_legacy_test_cases()

    for case in legacy_cases:
        original_result = case['expected_result']
        current_result = extract_advisor_data(case['input'])

        # Key fields should remain consistent
        key_fields = ['aum_amount', 'years_experience', 'licenses', 'location']
        for field in key_fields:
            if field in original_result:
                assert current_result.get(field) == original_result[field], \
                    f"Regression in {field} for case {case['id']}"
```

## Test Execution Framework

### Running All Tests

```python
def run_comprehensive_tests():
    """Execute full test suite with reporting"""

    test_suites = [
        test_aum_patterns,
        test_license_patterns,
        test_designation_patterns,
        test_deal_name_formatting,
        test_source_determination,
        test_incomplete_data_handling,
        test_ambiguous_data_resolution,
        test_full_email_processing,
        test_extraction_performance,
        test_data_quality_validation,
        test_backward_compatibility
    ]

    results = []
    for test_suite in test_suites:
        try:
            test_suite()
            results.append(f"✅ {test_suite.__name__} - PASSED")
        except Exception as e:
            results.append(f"❌ {test_suite.__name__} - FAILED: {str(e)}")

    # Generate test report
    generate_test_report(results)
    return results
```

### Manual Testing Checklist

#### Pre-Deployment Validation
- [ ] Test with all real Brandon examples from the HTML file
- [ ] Verify AUM amounts are correctly converted to numeric values
- [ ] Confirm license extraction handles all format variations
- [ ] Check designation parsing including in-progress status
- [ ] Validate geographic and mobility constraint extraction
- [ ] Ensure values statements are preserved exactly
- [ ] Test compensation range parsing for all formats
- [ ] Verify deal name formatting follows business rules
- [ ] Confirm Zoho field mapping is complete and accurate
- [ ] Test error handling for malformed input data

#### Performance Validation
- [ ] Processing time < 2 seconds for typical emails
- [ ] Memory usage remains stable during batch processing
- [ ] Error rates < 1% for well-formatted input
- [ ] Graceful degradation for partial data

#### Integration Validation
- [ ] Zoho API calls succeed with extracted data
- [ ] Contact records created with all mapped fields
- [ ] Deal records linked correctly to contacts
- [ ] Company records created when applicable
- [ ] Source determination logic works correctly
- [ ] Owner assignment uses environment variable

This testing guide ensures comprehensive validation of the financial advisor extraction system using Brandon's proven data patterns and business requirements.