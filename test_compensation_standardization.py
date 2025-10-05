#!/usr/bin/env python3
"""
Test compensation standardization to verify minimal formatting preserves candidate's exact wording.
"""

def test_standardize_compensation():
    """Test the updated _standardize_compensation method."""
    import re

    def _standardize_compensation(raw_text: str) -> str:
        """MINIMAL standardization - preserves candidate's exact wording."""
        if not raw_text:
            return ""

        result = raw_text.strip()

        # 1. Capitalize K, M, B units (handle decimals like 1.5m and ranges like 200-250k)
        result = re.sub(r'([\d.]+)k\b', lambda m: f"{m.group(1)}K", result, flags=re.IGNORECASE)
        result = re.sub(r'([\d.]+)m\b', lambda m: f"{m.group(1)}M", result, flags=re.IGNORECASE)
        result = re.sub(r'([\d.]+)b\b', lambda m: f"{m.group(1)}B", result, flags=re.IGNORECASE)

        # 2. Add $ prefix to the FIRST amount that doesn't have it
        # Match number (with optional decimal) and optional range (200-250K)
        # Only replace first occurrence to avoid adding $ to bonus/commission amounts
        result = re.sub(r'(?<![$\d])([\d.]+(?:-[\d.]+)?)(K|M|B)', r'$\1\2', result, count=1)

        # 3. Standardize "all in" to "OTE"
        result = re.sub(r'\ball in\b', 'OTE', result, flags=re.IGNORECASE)
        result = re.sub(r'\ball-in\b', 'OTE', result, flags=re.IGNORECASE)

        # 4. Add "base" before "+ commission/bonus" if not present
        if re.search(r'\+\s*(commission|bonus)', result, re.IGNORECASE) and \
           not re.search(r'\bbase\b', result, re.IGNORECASE):
            result = re.sub(
                r'(\$\d+[\d\-]*[KMB])\s*(\+)',
                r'\1 base \2',
                result,
                count=1,
                flags=re.IGNORECASE
            )

        return result

    # Test cases based on boss's feedback
    test_cases = [
        # Boss's examples
        ("95k + commission", "$95K base + commission"),
        ("$750k all in", "$750K OTE"),

        # Additional real-world examples
        ("200-250k base + bonus", "$200-250K base + bonus"),
        ("$150K base", "$150K base"),
        ("100k", "$100K"),
        ("1.5m OTE", "$1.5M OTE"),
        ("$95k base + commission", "$95K base + commission"),  # Already formatted
        ("300K all-in", "$300K OTE"),
        ("120k base + 30k bonus", "$120K base + 30K bonus"),

        # Edge cases - should preserve nuance (only first amount gets $ to avoid over-formatting)
        ("Looking for 200k minimum", "Looking for $200K minimum"),
        ("Currently at 150k, seeking 180k+", "Currently at $150K, seeking 180K+"),
        ("$500K-$600K depending on equity", "$500K-$600K depending on equity"),
    ]

    print("=" * 80)
    print("COMPENSATION STANDARDIZATION TEST")
    print("=" * 80)
    print()

    all_passed = True
    for input_text, expected in test_cases:
        result = _standardize_compensation(input_text)
        passed = result == expected
        all_passed = all_passed and passed

        status = "✅" if passed else "❌"
        print(f"{status} Input:    '{input_text}'")
        print(f"   Expected: '{expected}'")
        print(f"   Got:      '{result}'")
        if not passed:
            print(f"   MISMATCH!")
        print()

    print("=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED - Compensation standardization working correctly")
    else:
        print("❌ SOME TESTS FAILED - Review logic")
    print("=" * 80)

    return all_passed

if __name__ == "__main__":
    test_standardize_compensation()
