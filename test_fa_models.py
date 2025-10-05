#!/usr/bin/env python3
"""
Simple test to validate financial advisor model enhancements
Tests the data structure without requiring external dependencies
"""

import sys
import json
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

def test_extraction_output_model():
    """Test that ExtractionOutput model includes financial advisor fields"""
    try:
        from langgraph_manager import ExtractionOutput

        print("Testing ExtractionOutput model...")

        # Create a sample extraction with financial advisor data
        sample_data = {
            "first_name": "Michael",
            "last_name": "Thompson",
            "contact_email": "michael.thompson@morganstanley.com",
            "company_name": "Morgan Stanley",
            "aum_managed": "$350M",
            "production_annual": "$1.2M",
            "client_count": "180 clients",
            "licenses_held": ["Series 7", "Series 66", "Life Insurance"],
            "designations": ["CFA", "CFP"],
            "years_experience": "15 years",
            "availability_timeframe": "30 days notice",
            "compensation_range": "$650K-$750K",
            "book_transferable": "85% transferable",
            "specializations": ["High-net-worth", "Estate planning"]
        }

        # Test model creation
        extraction = ExtractionOutput(**sample_data)

        print("✅ ExtractionOutput model created successfully")
        print(f"   AUM: {extraction.aum_managed}")
        print(f"   Production: {extraction.production_annual}")
        print(f"   Licenses: {extraction.licenses_held}")
        print(f"   Designations: {extraction.designations}")
        print(f"   Experience: {extraction.years_experience}")

        return True

    except Exception as e:
        print(f"❌ ExtractionOutput test failed: {e}")
        return False

def test_extracted_data_model():
    """Test that ExtractedData model includes financial advisor fields"""
    try:
        from models import ExtractedData, CompanyRecord, ContactRecord, DealRecord

        print("\nTesting ExtractedData model...")

        # Create sample records
        company_record = CompanyRecord(
            company_name="Morgan Stanley",
            website="https://morganstanley.com"
        )

        contact_record = ContactRecord(
            first_name="Michael",
            last_name="Thompson",
            email="michael.thompson@morganstanley.com",
            city="Chicago",
            state="IL"
        )

        deal_record = DealRecord(
            source="Email Inbound",
            deal_name="Senior Advisor (Chicago) - Morgan Stanley"
        )

        # Create ExtractedData with financial advisor fields
        extracted_data = ExtractedData(
            company_record=company_record,
            contact_record=contact_record,
            deal_record=deal_record,
            aum_managed="$350M",
            production_annual="$1.2M",
            client_count="180 clients",
            licenses_held=["Series 7", "Series 66"],
            designations=["CFA", "CFP"],
            years_experience="15 years",
            availability_timeframe="30 days notice",
            compensation_range="$650K-$750K"
        )

        print("✅ ExtractedData model created successfully")
        print(f"   Contact: {extracted_data.contact_record.first_name} {extracted_data.contact_record.last_name}")
        print(f"   Company: {extracted_data.company_record.company_name}")
        print(f"   AUM: {extracted_data.aum_managed}")
        print(f"   Production: {extracted_data.production_annual}")
        print(f"   Licenses: {extracted_data.licenses_held}")

        return True

    except Exception as e:
        print(f"❌ ExtractedData test failed: {e}")
        return False

def test_model_serialization():
    """Test that models can be serialized to JSON"""
    try:
        from models import ExtractedData, CompanyRecord, ContactRecord, DealRecord

        print("\nTesting model serialization...")

        # Create a complete financial advisor record
        extracted_data = ExtractedData(
            company_record=CompanyRecord(company_name="Goldman Sachs"),
            contact_record=ContactRecord(first_name="Sarah", last_name="Wilson"),
            deal_record=DealRecord(deal_name="Portfolio Manager (NYC) - Goldman Sachs"),
            aum_managed="$220M",
            licenses_held=["Series 7", "Series 66", "Series 65"],
            designations=["CFA"]
        )

        # Convert to dict and JSON
        data_dict = extracted_data.dict()
        json_str = json.dumps(data_dict, indent=2, default=str)

        print("✅ Model serialization successful")
        print("   JSON structure includes:")

        if 'aum_managed' in data_dict and data_dict['aum_managed']:
            print(f"   - AUM: {data_dict['aum_managed']}")
        if 'licenses_held' in data_dict and data_dict['licenses_held']:
            print(f"   - Licenses: {data_dict['licenses_held']}")
        if 'designations' in data_dict and data_dict['designations']:
            print(f"   - Designations: {data_dict['designations']}")

        return True

    except Exception as e:
        print(f"❌ Serialization test failed: {e}")
        return False

def main():
    """Run all model tests"""
    print("Financial Advisor Model Enhancement Tests")
    print("=" * 50)

    results = []

    # Test ExtractionOutput model
    results.append(test_extraction_output_model())

    # Test ExtractedData model
    results.append(test_extracted_data_model())

    # Test serialization
    results.append(test_model_serialization())

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    passed = sum(results)
    total = len(results)

    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed! Financial advisor fields are properly integrated.")
    else:
        print("⚠️  Some tests failed. Check the error messages above.")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)