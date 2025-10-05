#!/usr/bin/env python3
"""
Test script for TalentWell curator data quality and formatting improvements.
"""
import asyncio
import sys
sys.path.insert(0, '/home/romiteld/Development/Desktop_Apps/outlook')

from app.jobs.talentwell_curator import TalentWellCurator

def test_aum_parsing_and_rounding():
    """Test AUM parsing and privacy rounding."""
    curator = TalentWellCurator()

    print("Testing AUM Parsing and Rounding:")
    print("-" * 50)

    test_cases = [
        ("$1.5B", "$1B–$5B"),
        ("$500M", "$500M–$1B"),
        ("$2.3 billion", "$1B–$5B"),
        ("$150 million", "$100M–$500M"),
        ("$75M", "$100M+"),
        ("$10B", "$5B+"),
        ("250k", "$100M+"),
        ("$850 Million", "$500M–$1B"),
    ]

    for input_str, expected in test_cases:
        parsed_value = curator._parse_aum(input_str)
        rounded = curator._round_aum_for_privacy(parsed_value)
        status = "✅" if rounded == expected else "❌"
        print(f"{status} Input: {input_str:15} -> Parsed: ${parsed_value:,.0f} -> Rounded: {rounded}")
        if rounded != expected:
            print(f"   Expected: {expected}")

def test_compensation_standardization():
    """Test compensation format standardization."""
    curator = TalentWellCurator()

    print("\nTesting Compensation Standardization:")
    print("-" * 50)

    test_cases = [
        ("95k Base + Commission 140+ OTE", "Target comp: $95k–$140k+ OTE"),
        ("$200,000 total", "Target comp: $200k OTE"),
        ("150k OTE", "Target comp: $150k OTE"),
        ("Base 100k, total 175k", "Target comp: $100k–$175k OTE"),
        ("250000", "Target comp: $250k"),
    ]

    for input_str, expected in test_cases:
        standardized = curator._standardize_compensation(input_str)
        status = "✅" if standardized == expected else "❌"
        print(f"{status} Input: {input_str:35} -> Output: {standardized}")
        if standardized != expected:
            print(f"   Expected: {expected}")

def test_internal_note_filtering():
    """Test internal note detection."""
    curator = TalentWellCurator()

    print("\nTesting Internal Note Filtering:")
    print("-" * 50)

    test_cases = [
        ("Has 10 years experience", False),
        ("TBD - waiting for confirmation", True),
        ("Unclear about compensation", True),
        ("Didn't say when available", True),
        ("Manages $500M AUM", False),
        ("Hard time getting exact numbers", True),
        ("Available in 2 weeks", False),
        ("Depending on current deals closing", True),
        ("We need to verify this", True),
    ]

    for text, should_filter in test_cases:
        is_internal = curator._is_internal_note(text)
        status = "✅" if is_internal == should_filter else "❌"
        filter_str = "FILTERED" if is_internal else "KEEP"
        print(f"{status} [{filter_str:8}] {text}")

def test_availability_formatting():
    """Test availability text formatting."""
    curator = TalentWellCurator()

    print("\nTesting Availability Formatting:")
    print("-" * 50)

    test_cases = [
        ("Available Available", "Available"),
        ("immediately", "Available immediately"),
        ("Available now", "Available immediately"),
        ("2 weeks", "Available in 2 weeks"),
        ("Available 1 month", "Available in 1 month"),
        ("3 months notice", "Available in 3 months"),
        ("January", "Available in January"),
        ("Available ASAP", "Available immediately"),
    ]

    for input_str, expected in test_cases:
        formatted = curator._format_availability(input_str)
        status = "✅" if formatted == expected else "❌"
        print(f"{status} Input: {input_str:25} -> Output: {formatted}")
        if formatted != expected:
            print(f"   Expected: {expected}")

def test_integration_example():
    """Test integration with real-world examples."""
    curator = TalentWellCurator()

    print("\nIntegration Test - Processing Real Data:")
    print("-" * 50)

    # Example candidate data
    raw_data = {
        "book_size_aum": "$1.2 Billion",
        "production_12mo": "$850k",
        "desired_comp": "Base 150k + Commission, targeting 225k OTE",
        "when_available": "Available Available in 30 days",
    }

    # Process AUM
    aum_value = curator._parse_aum(raw_data["book_size_aum"])
    aum_rounded = curator._round_aum_for_privacy(aum_value)
    print(f"AUM: {raw_data['book_size_aum']} -> {aum_rounded}")

    # Process compensation
    comp_formatted = curator._standardize_compensation(raw_data["desired_comp"])
    print(f"Comp: {raw_data['desired_comp']}")
    print(f"  -> {comp_formatted}")

    # Process availability
    avail_formatted = curator._format_availability(raw_data["when_available"])
    print(f"Availability: {raw_data['when_available']} -> {avail_formatted}")

    # Check for internal notes
    print("\nInternal Note Checks:")
    bullets = [
        f"AUM: {aum_rounded}",
        comp_formatted,
        avail_formatted,
        "TBD - needs confirmation from manager",
        "Strong performer with proven track record"
    ]

    for bullet in bullets:
        is_internal = curator._is_internal_note(bullet)
        status = "FILTERED" if is_internal else "INCLUDED"
        print(f"  [{status}] {bullet}")

if __name__ == "__main__":
    print("=" * 60)
    print("TalentWell Curator Formatting Tests")
    print("=" * 60)

    test_aum_parsing_and_rounding()
    test_compensation_standardization()
    test_internal_note_filtering()
    test_availability_formatting()
    test_integration_example()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)