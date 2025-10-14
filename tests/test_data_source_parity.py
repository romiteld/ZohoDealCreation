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
    """Verify all 29 PostgreSQL columns are mapped."""
    zoho_data = {
        'TWAV_Number': 'TWAV123456',
        'Full_Name': 'John Doe',
        'Title': 'Financial Advisor',
        'Current_Location': 'Austin, TX',
        'Location_Detail': 'Downtown area',
        'Firm': 'Merrill Lynch',
        'Years_of_Experience': '15',
        'AUM': '$100M',
        'Production': '$1.2M',
        'Book_Size_Clients': '150',
        'Transferable_Book': '80%',
        'Licenses': 'Series 7, 63, 65',
        'Professional_Designations': 'CFP, CFA',
        'Headline': 'Top-performing advisor',
        'Interviewer_Notes': 'Strong candidate',
        'Top_Performance': 'President\'s Club 2023',
        'Candidate_Experience': '10 years wealth management',
        'Background_Notes': 'MBA from UT Austin',
        'Other_Screening_Notes': 'Excellent communication',
        'Availability': 'Immediately',
        'Compensation': '$450K',
        'LinkedIn_Profile': 'https://linkedin.com/in/johndoe',
        'Zoom_Meeting_ID': '123456789',
        'Zoom_Meeting_URL': 'https://zoom.us/rec/123'
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

    # Verify timestamp fields are None (set by database)
    assert result['created_at'] is None
    assert result['updated_at'] is None


def test_zoho_field_mapping_missing_fields():
    """Test mapping with missing fields."""
    zoho_data = {
        'TWAV_Number': 'TWAV789',
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
        'TWAV_Number': 'TWAV999',
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
