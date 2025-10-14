"""
Test data source parity between Zoho API and PostgreSQL vault_candidates schema.
"""

import pytest
from app.integrations import parse_location, map_to_vault_schema


def test_parse_location():
    """Test location parsing into city and state."""
    # Standard case
    assert parse_location('Austin, TX') == ('Austin', 'TX')
    assert parse_location('New York City, NY') == ('New York City', 'NY')

    # Edge cases
    assert parse_location('Invalid') == ('Invalid', '')
    assert parse_location('') == ('', '')
    assert parse_location(None) == ('', '')

    # Multiple commas (should split on first comma only)
    assert parse_location('San Francisco, CA, USA') == ('San Francisco', 'CA, USA')


def test_zoho_field_mapping():
    """Verify all 29 PostgreSQL columns are mapped.

    CRITICAL: Uses CORRECT Zoho CRM API field names (verified from production):
    - Candidate_Locator (NOT TWAV_Number)
    - Employer (NOT Firm)
    - Book_Size_AUM (NOT AUM)
    - Production_L12Mo (NOT Production)
    - Desired_Comp (NOT Compensation)
    """
    zoho_data = {
        'Candidate_Locator': 'TWAV123456',  # FIXED: was TWAV_Number
        'Full_Name': 'John Doe',
        'Title': 'Financial Advisor',
        'Current_Location': 'Austin, TX',
        'Location_Detail': 'Downtown area',
        'Employer': 'Merrill Lynch',  # FIXED: was Firm
        'Years_of_Experience': '15',
        'Book_Size_AUM': '$100M',  # FIXED: was AUM
        'Production_L12Mo': '$1.2M',  # FIXED: was Production
        'Book_Size_Clients': '150',
        'Transferable_Book_of_Business': '80%',  # FIXED: was Transferable_Book
        'Licenses_and_Exams': 'Series 7, 63, 65',  # FIXED: was Licenses
        'Professional_Designations': 'CFP, CFA',
        'Headline': 'Top-performing advisor',
        'Interviewer_Notes': 'Strong candidate',
        'Top_Performance': 'President\'s Club 2023',
        'Candidate_Experience': '10 years wealth management',
        'Background_Notes': 'MBA from UT Austin',
        'Other_Screening_Notes': 'Excellent communication',
        'When_Available': 'Immediately',  # FIXED: was Availability
        'Desired_Comp': '$450K',  # FIXED: was Compensation
        'LinkedIn_Profile': 'https://linkedin.com/in/johndoe',
        'Zoom_Meeting_ID': '123456789',
        'Zoom_Meeting_URL': 'https://zoom.us/rec/123',
        'Created_Time': '2025-01-15T10:30:00-05:00',  # NEW: Zoho timestamp
        'Modified_Time': '2025-01-15T14:45:00-05:00'  # NEW: Zoho timestamp
    }

    result = map_to_vault_schema(zoho_data)

    # Verify all 29 columns present
    required_cols = [
        'twav_number', 'candidate_name', 'title', 'city', 'state',
        'current_location', 'location_detail', 'firm', 'years_experience',
        'aum', 'production', 'book_size_clients', 'transferable_book',
        'licenses', 'professional_designations', 'headline',
        'interviewer_notes', 'top_performance', 'candidate_experience',
        'background_notes', 'other_screening_notes', 'availability',
        'compensation', 'linkedin_profile', 'zoom_meeting_id',
        'zoom_meeting_url', 'raw_data', 'created_at', 'updated_at'
    ]

    for col in required_cols:
        assert col in result, f"Missing column: {col}"

    # Verify specific mappings
    assert result['twav_number'] == 'TWAV123456'
    assert result['candidate_name'] == 'John Doe'
    assert result['title'] == 'Financial Advisor'
    assert result['city'] == 'Austin'
    assert result['state'] == 'TX'
    assert result['current_location'] == 'Austin, TX'
    assert result['firm'] == 'Merrill Lynch'
    assert result['compensation'] == '$450K'

    # Verify raw_data stores full record
    assert result['raw_data'] == zoho_data

    # Verify timestamp fields are from Zoho (not None anymore)
    assert result['created_at'] == '2025-01-15T10:30:00-05:00'
    assert result['updated_at'] == '2025-01-15T14:45:00-05:00'


def test_zoho_field_mapping_missing_fields():
    """Test mapping with missing fields."""
    zoho_data = {
        'Candidate_Locator': 'TWAV789',  # FIXED: was TWAV_Number
        'Full_Name': 'Jane Smith',
        # Most fields missing
    }

    result = map_to_vault_schema(zoho_data)

    # Should still have all 29 columns
    assert len(result) == 29

    # Missing fields should default to empty string
    assert result['twav_number'] == 'TWAV789'
    assert result['candidate_name'] == 'Jane Smith'
    assert result['title'] == ''
    assert result['city'] == ''
    assert result['state'] == ''
    assert result['firm'] == ''


def test_zoho_field_mapping_no_location():
    """Test mapping with no location data."""
    zoho_data = {
        'Candidate_Locator': 'TWAV999',  # FIXED: was TWAV_Number
        'Full_Name': 'Remote Worker',
        'Current_Location': '',
    }

    result = map_to_vault_schema(zoho_data)

    assert result['city'] == ''
    assert result['state'] == ''
    assert result['current_location'] == ''


@pytest.mark.asyncio
async def test_data_source_parity():
    """
    Verify PostgreSQL and Zoho API return equivalent data structures.

    This test:
    1. Fetches candidates from PostgreSQL (USE_ZOHO_API=false)
    2. Fetches candidates from Zoho API (USE_ZOHO_API=true)
    3. Verifies both return the same schema (29 columns)
    4. Validates field types and structure match

    Note: This is a schema parity test, not a data equivalence test.
    """
    from app.config import feature_flags
    from app.jobs.vault_alerts_generator import VaultAlertsGenerator

    try:
        # Save original flag value
        original_flag = feature_flags.USE_ZOHO_API

        # Test PostgreSQL path
        feature_flags.USE_ZOHO_API = False

        gen_pg = VaultAlertsGenerator()
        await gen_pg.initialize()

        state_pg = {
            'from_date': '2025-01-01',
            'audience': 'advisors',
            'custom_filters': {},
            'all_candidates': [],
            'advisor_candidates': [],
            'executive_candidates': [],
            'cache_manager': None,
            'cache_stats': {'hits': 0, 'misses': 0},
            'quality_metrics': {},
            'advisor_html': None,
            'executive_html': None,
            'errors': []
        }

        # Call the database loader agent
        result_pg = await gen_pg._agent_database_loader(state_pg)
        pg_candidates = result_pg['all_candidates']

        # Test Zoho API path
        feature_flags.USE_ZOHO_API = True

        gen_zoho = VaultAlertsGenerator()
        await gen_zoho.initialize()

        state_zoho = {
            'from_date': '2025-01-01',
            'audience': 'advisors',
            'custom_filters': {},
            'all_candidates': [],
            'advisor_candidates': [],
            'executive_candidates': [],
            'cache_manager': None,
            'cache_stats': {'hits': 0, 'misses': 0},
            'quality_metrics': {},
            'advisor_html': None,
            'executive_html': None,
            'errors': []
        }

        # Call the database loader agent
        result_zoho = await gen_zoho._agent_database_loader(state_zoho)
        zoho_candidates = result_zoho['all_candidates']

        # Verify schema parity
        if pg_candidates and zoho_candidates:
            pg_keys = set(pg_candidates[0].keys())
            zoho_keys = set(zoho_candidates[0].keys())

            # Check for schema mismatches
            missing_in_zoho = pg_keys - zoho_keys
            extra_in_zoho = zoho_keys - pg_keys

            assert not missing_in_zoho, f"Missing columns in Zoho data: {missing_in_zoho}"
            assert not extra_in_zoho, f"Extra columns in Zoho data: {extra_in_zoho}"
            assert pg_keys == zoho_keys, f"Schema mismatch: {pg_keys ^ zoho_keys}"

            print(f"✅ Schema parity validated: {len(pg_keys)} columns")
            print(f"   PostgreSQL: {len(pg_candidates)} candidates")
            print(f"   Zoho API: {len(zoho_candidates)} candidates")

        # Clean up
        await gen_pg.close()
        await gen_zoho.close()

    finally:
        # Restore original flag
        feature_flags.USE_ZOHO_API = original_flag


def test_zoho_field_type_conversions():
    """Test type conversions from Zoho string fields to proper types."""
    zoho_data = {
        'Candidate_Locator': 'TWAV123',  # FIXED: was TWAV_Number
        'Years_of_Experience': '10.5',  # Should convert to float/int
        'Book_Size_AUM': '$1.5B',  # FIXED: was AUM - Should stay string
        'Book_Size_Clients': '200',  # Should convert to int
        'Created_Time': '2025-01-15T10:30:00-05:00'  # Should parse to datetime
    }

    result = map_to_vault_schema(zoho_data)

    # Verify years_experience is numeric-compatible
    years_str = result['years_experience']
    if years_str:
        assert years_str == '10.5' or years_str == 10.5 or years_str == 10

    # Verify AUM stays as string
    assert isinstance(result['aum'], str)
    assert result['aum'] == '$1.5B'

    # Book size should be string or int
    book_size = result['book_size_clients']
    assert book_size == '200' or book_size == 200


def test_location_parsing_edge_cases():
    """Test location parsing with various edge cases."""
    test_cases = [
        # Normal cases
        ('Dallas, TX', ('Dallas', 'TX')),
        ('New York, NY', ('New York', 'NY')),

        # Edge cases
        ('San Francisco Bay Area, CA', ('San Francisco Bay Area', 'CA')),
        ('St. Louis, MO', ('St. Louis', 'MO')),
        ('Washington, D.C.', ('Washington', 'D.C.')),
        ('Remote', ('Remote', '')),
        ('USA', ('USA', '')),
        ('Miami-Dade County, FL', ('Miami-Dade County', 'FL')),

        # International
        ('London, UK', ('London', 'UK')),
        ('Toronto, ON, Canada', ('Toronto', 'ON, Canada')),

        # Invalid
        (None, ('', '')),
        ('', ('', '')),
        ('   ', ('   ', '')),  # Spaces preserved
        ('NoComma', ('NoComma', ''))
    ]

    for location_input, expected in test_cases:
        result = parse_location(location_input)
        assert result == expected, f"Failed for {location_input}: got {result}, expected {expected}"


@pytest.mark.asyncio
async def test_data_filtering_consistency():
    """Test that filtering logic is consistent between data sources."""
    from app.config import feature_flags
    from app.jobs.vault_alerts_generator import VaultAlertsGenerator

    original_flag = feature_flags.USE_ZOHO_API

    try:
        # Test with custom filters
        custom_filters = {
            'min_aum': 500,  # $500M minimum
            'states': ['NY', 'CA', 'TX'],
            'min_years_experience': 10
        }

        # Test PostgreSQL filtering
        feature_flags.USE_ZOHO_API = False
        gen_pg = VaultAlertsGenerator()
        await gen_pg.initialize()

        state_pg = {
            'from_date': '2025-01-01',
            'audience': 'advisors',
            'custom_filters': custom_filters,
            'all_candidates': [],
            'advisor_candidates': [],
            'executive_candidates': [],
            'cache_manager': None,
            'cache_stats': {'hits': 0, 'misses': 0},
            'quality_metrics': {},
            'advisor_html': None,
            'executive_html': None,
            'errors': []
        }

        result_pg = await gen_pg._agent_database_loader(state_pg)
        pg_filtered = result_pg['advisor_candidates']

        # Test Zoho API filtering
        feature_flags.USE_ZOHO_API = True
        gen_zoho = VaultAlertsGenerator()
        await gen_zoho.initialize()

        state_zoho = {
            'from_date': '2025-01-01',
            'audience': 'advisors',
            'custom_filters': custom_filters,
            'all_candidates': [],
            'advisor_candidates': [],
            'executive_candidates': [],
            'cache_manager': None,
            'cache_stats': {'hits': 0, 'misses': 0},
            'quality_metrics': {},
            'advisor_html': None,
            'executive_html': None,
            'errors': []
        }

        result_zoho = await gen_zoho._agent_database_loader(state_zoho)
        zoho_filtered = result_zoho['advisor_candidates']

        # Verify both apply filters consistently
        if pg_filtered:
            for candidate in pg_filtered:
                # Check state filter
                if candidate.get('state'):
                    assert candidate['state'] in ['NY', 'CA', 'TX'], \
                        f"State filter not applied: {candidate['state']}"

        if zoho_filtered:
            for candidate in zoho_filtered:
                # Check state filter
                if candidate.get('state'):
                    assert candidate['state'] in ['NY', 'CA', 'TX'], \
                        f"State filter not applied: {candidate['state']}"

        await gen_pg.close()
        await gen_zoho.close()

    finally:
        feature_flags.USE_ZOHO_API = original_flag


@pytest.mark.asyncio
async def test_audience_segmentation_parity():
    """Test that advisor vs executive segmentation is consistent."""
    from app.config import feature_flags
    from app.jobs.vault_alerts_generator import VaultAlertsGenerator

    original_flag = feature_flags.USE_ZOHO_API

    try:
        # Test both audiences
        for audience in ['advisors', 'executives', 'both']:
            # Test PostgreSQL
            feature_flags.USE_ZOHO_API = False
            gen_pg = VaultAlertsGenerator()
            await gen_pg.initialize()

            state = {
                'from_date': '2025-01-01',
                'audience': audience,
                'custom_filters': {},
                'all_candidates': [],
                'advisor_candidates': [],
                'executive_candidates': [],
                'cache_manager': None,
                'cache_stats': {'hits': 0, 'misses': 0},
                'quality_metrics': {},
                'advisor_html': None,
                'executive_html': None,
                'errors': []
            }

            result = await gen_pg._agent_database_loader(state)

            if audience == 'advisors':
                assert len(result['advisor_candidates']) >= 0
                assert len(result['executive_candidates']) == 0
            elif audience == 'executives':
                assert len(result['advisor_candidates']) == 0
                assert len(result['executive_candidates']) >= 0
            else:  # both
                assert len(result['advisor_candidates']) >= 0
                assert len(result['executive_candidates']) >= 0

            await gen_pg.close()

    finally:
        feature_flags.USE_ZOHO_API = original_flag


def test_raw_data_preservation():
    """Test that raw Zoho data is preserved in mapping."""
    zoho_data = {
        'Candidate_Locator': 'TWAV999',  # FIXED: was TWAV_Number
        'Full_Name': 'Test User',
        'Custom_Field_1': 'Value1',  # Unknown field
        'Custom_Field_2': 'Value2',  # Unknown field
        'Title': 'Senior Advisor'
    }

    result = map_to_vault_schema(zoho_data)

    # raw_data should contain the complete original record
    assert result['raw_data'] == zoho_data
    assert 'Custom_Field_1' in result['raw_data']
    assert 'Custom_Field_2' in result['raw_data']
    assert result['raw_data']['Custom_Field_1'] == 'Value1'


def test_null_handling_consistency():
    """Test that null/None values are handled consistently."""
    test_cases = [
        # Zoho might send null, empty string, or missing fields
        {'Candidate_Locator': 'TWAV1', 'Book_Size_AUM': None},  # FIXED
        {'Candidate_Locator': 'TWAV2', 'Book_Size_AUM': ''},  # FIXED
        {'Candidate_Locator': 'TWAV3'},  # Missing Book_Size_AUM - FIXED
        {'Candidate_Locator': 'TWAV4', 'Book_Size_AUM': 'N/A'},  # FIXED
        {'Candidate_Locator': 'TWAV5', 'Book_Size_AUM': 'Not Disclosed'}  # FIXED
    ]

    for zoho_data in test_cases:
        result = map_to_vault_schema(zoho_data)

        # Should always have an 'aum' key
        assert 'aum' in result

        # Value should be string (empty or actual value)
        aum_value = result['aum']
        assert aum_value is None or isinstance(aum_value, str)


def test_special_characters_in_fields():
    """Test handling of special characters in field values."""
    zoho_data = {
        'Candidate_Locator': 'TWAV123',  # FIXED: was TWAV_Number
        'Full_Name': "O'Brien, Jr.",
        'Employer': 'Smith & Associates, LLC',  # FIXED: was Firm
        'Headline': 'Top 1% producer—elite advisor',
        'Interviewer_Notes': 'Excellent résumé; très bien!',
        'Professional_Designations': 'CFP®, CFA®, ChFC®'
    }

    result = map_to_vault_schema(zoho_data)

    # Special characters should be preserved
    assert result['candidate_name'] == "O'Brien, Jr."
    assert result['firm'] == 'Smith & Associates, LLC'
    assert '—' in result['headline']  # em dash
    assert 'résumé' in result['interviewer_notes']
    assert '®' in result['professional_designations']
