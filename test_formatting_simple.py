#!/usr/bin/env python3
"""
Simplified test script for TalentWell curator formatting improvements.
"""
import re

class FormattingTester:
    """Simplified version of formatting methods for testing."""

    def _parse_aum(self, aum_str: str) -> float:
        """Parse AUM string to float value in dollars."""
        if not aum_str:
            return 0.0

        # Remove $ and commas, clean up spaces
        cleaned = aum_str.replace('$', '').replace(',', '').strip()

        # Pattern to extract number and unit
        pattern = r'(\d+(?:\.\d+)?)\s*([BMKbmk])?'
        match = re.match(pattern, cleaned)

        if not match:
            return 0.0

        amount = float(match.group(1))
        unit = match.group(2)

        if unit:
            unit = unit.upper()
            multipliers = {
                'B': 1_000_000_000,
                'M': 1_000_000,
                'K': 1_000
            }
            return amount * multipliers.get(unit, 1)

        return amount

    def _round_aum_for_privacy(self, aum_value: float) -> str:
        """Round AUM to privacy-preserving ranges."""
        if aum_value >= 5_000_000_000:
            return "$5B+"
        elif aum_value >= 1_000_000_000:
            return "$1B–$5B"
        elif aum_value >= 500_000_000:
            return "$500M–$1B"
        elif aum_value >= 100_000_000:
            return "$100M–$500M"
        elif aum_value > 0:
            return "$100M+"
        else:
            return ""

    def _standardize_compensation(self, raw_text: str) -> str:
        """Standardize compensation format."""
        if not raw_text:
            return ""

        # Clean the input
        text = raw_text.lower().replace(',', '')

        # Extract all numbers that could be compensation amounts
        amount_pattern = r'\$?(\d+)(?:k|,000)?'
        amounts = re.findall(amount_pattern, text)

        if not amounts:
            return raw_text

        # Convert all amounts to thousands
        amounts_in_k = []
        for amt in amounts:
            amt_num = float(amt)
            if amt_num > 1000:
                amt_num = amt_num / 1000
            amounts_in_k.append(int(amt_num))

        # Determine if OTE is mentioned
        is_ote = 'ote' in text or 'on target' in text or 'total' in text

        # Format based on number of amounts found
        if len(amounts_in_k) == 1:
            return f"Target comp: ${amounts_in_k[0]}k{'+ OTE' if is_ote else ''}"
        elif len(amounts_in_k) >= 2:
            min_amt = min(amounts_in_k)
            max_amt = max(amounts_in_k)
            if min_amt == max_amt:
                return f"Target comp: ${max_amt}k{' OTE' if is_ote else ''}"
            else:
                return f"Target comp: ${min_amt}k–${max_amt}k{' OTE' if is_ote else ''}"

        return raw_text

    def _is_internal_note(self, text: str) -> bool:
        """Filter internal recruiter notes."""
        if not text:
            return False

        text_lower = text.lower()

        internal_patterns = [
            'hard time', 'tbd', 'to be determined', 'depending on',
            'unclear', "didn't say", "doesn't know", "not sure",
            "will need to", "might be", "possibly", "maybe",
            "we need to", "follow up on", "ask about", "verify",
            "confirm with", "check on", "waiting for", "pending"
        ]

        for pattern in internal_patterns:
            if pattern in text_lower:
                return True

        return False

    def _format_availability(self, raw_text: str) -> str:
        """Format availability text consistently."""
        if not raw_text:
            return ""

        # Clean up duplicate "Available"
        text = re.sub(r'\b(available)\s+\1\b', r'\1', raw_text, flags=re.IGNORECASE)
        text_lower = text.lower()

        if 'immediate' in text_lower or 'now' in text_lower or 'asap' in text_lower:
            return "Available immediately"

        # Extract timeframe
        time_pattern = r'(\d+)\s*(weeks?|months?|days?)'
        match = re.search(time_pattern, text_lower)

        if match:
            number = match.group(1)
            unit = match.group(2)
            if number == '1':
                unit = unit.rstrip('s')
            elif not unit.endswith('s'):
                unit = unit + 's'
            return f"Available in {number} {unit}"

        # Check for specific dates
        months = ['january', 'february', 'march', 'april', 'may', 'june',
                 'july', 'august', 'september', 'october', 'november', 'december']
        for month in months:
            if month in text_lower:
                return f"Available in {month.capitalize()}"

        if text_lower.startswith('available'):
            return text
        else:
            return f"Available {text}"

def test_all_formatting():
    """Run all formatting tests."""
    tester = FormattingTester()

    print("=" * 60)
    print("TalentWell Curator Formatting Tests")
    print("=" * 60)

    # Test AUM parsing and rounding
    print("\n1. AUM Parsing and Privacy Rounding:")
    print("-" * 50)

    aum_tests = [
        ("$1.5B", "$1B–$5B"),
        ("$500M", "$500M–$1B"),
        ("$2.3 billion", "$1B–$5B"),
        ("$150 million", "$100M–$500M"),
        ("$75M", "$100M+"),
        ("$10B", "$5B+"),
        ("$850 Million", "$500M–$1B"),
    ]

    for input_str, expected in aum_tests:
        parsed = tester._parse_aum(input_str)
        rounded = tester._round_aum_for_privacy(parsed)
        status = "✅" if rounded == expected else "❌"
        print(f"{status} {input_str:20} -> {rounded:15} (expected: {expected})")

    # Test compensation standardization
    print("\n2. Compensation Standardization:")
    print("-" * 50)

    comp_tests = [
        ("95k Base + Commission 140+ OTE", "Target comp: $95k–$140k+ OTE"),
        ("$200,000 total", "Target comp: $200k OTE"),
        ("150k OTE", "Target comp: $150k OTE"),
        ("Base 100k, total 175k", "Target comp: $100k–$175k OTE"),
    ]

    for input_str, expected in comp_tests:
        standardized = tester._standardize_compensation(input_str)
        match = standardized == expected
        status = "✅" if match else "❌"
        print(f"{status} Input: {input_str}")
        print(f"   Output: {standardized}")
        if not match:
            print(f"   Expected: {expected}")

    # Test internal note filtering
    print("\n3. Internal Note Detection:")
    print("-" * 50)

    note_tests = [
        ("Has 10 years experience", False),
        ("TBD - waiting for confirmation", True),
        ("Unclear about compensation", True),
        ("Didn't say when available", True),
        ("Manages $500M AUM", False),
    ]

    for text, should_filter in note_tests:
        is_internal = tester._is_internal_note(text)
        status = "✅" if is_internal == should_filter else "❌"
        action = "FILTER" if is_internal else "KEEP"
        print(f"{status} [{action:6}] {text}")

    # Test availability formatting
    print("\n4. Availability Formatting:")
    print("-" * 50)

    avail_tests = [
        ("Available Available", "Available"),
        ("immediately", "Available immediately"),
        ("2 weeks", "Available in 2 weeks"),
        ("Available 1 month", "Available in 1 month"),
        ("January", "Available in January"),
    ]

    for input_str, expected in avail_tests:
        formatted = tester._format_availability(input_str)
        status = "✅" if formatted == expected else "❌"
        print(f"{status} {input_str:25} -> {formatted}")
        if formatted != expected:
            print(f"   Expected: {expected}")

    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_all_formatting()