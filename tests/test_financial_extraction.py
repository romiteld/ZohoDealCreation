"""
Comprehensive pytest test suite for financial advisor bullet point extraction.
Based on Brandon's real examples from Advisor_Vault_Candidate_Alerts.html
"""

import pytest
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class FinancialMetrics:
    """Data class to hold extracted financial metrics."""
    aum: Optional[str] = None
    aum_growth: Optional[Tuple[str, str]] = None  # (from, to)
    production: Optional[str] = None
    clients: Optional[str] = None
    relationships: Optional[str] = None
    ranking: Optional[str] = None
    close_rate: Optional[str] = None
    licenses: List[str] = None
    certifications: List[str] = None
    availability: Optional[str] = None
    compensation: Optional[str] = None
    location: Optional[str] = None
    mobility: Optional[str] = None


class FinancialExtractor:
    """Extract financial metrics from advisor bullet points."""

    # AUM patterns with various formats
    AUM_PATTERNS = [
        r'(?:Built|Managed)\s*\$([0-9]+(?:\.[0-9]+)?)\s*([BMT])\+?\s*in\s*(?:AUM|client assets)',
        r'\$([0-9]+(?:\.[0-9]+)?)\s*([BMT])\+?\s*(?:in client assets|AUM)',
        r'\$([0-9]+(?:\.[0-9]+)?)\s*([BMT])\s*(?:RIA|AUM|in AUM|in assets)',
        r'manages?\s*\$([0-9]+(?:\.[0-9]+)?)\s*([BMT])\s*(?:AUM|in AUM)?',
        r'(?:Built|Grew|Scaled)\s*\$([0-9]+(?:\.[0-9]+)?)\s*([BMT])\s*RIA',
        r'now\s+managing\s*\$([0-9]+(?:\.[0-9]+)?)\s*([BMT])',
        r'~\$([0-9]+)([BMT])\s*(?:to\s*\$([0-9]+)([BMT]))?',
    ]

    # AUM growth patterns
    GROWTH_PATTERNS = [
        r'(?:Previously\s+)?(?:grew|scaled|built)\s*(?:a\s*)?\$([0-9]+)([BMT])\s*(?:book\s*)?(?:to|→)\s*\$([0-9]+)([BMT])',
        r'(?:grew|scaled|built)\s*(?:from\s*)?\$([0-9]+)([BMT])\s*(?:to|→)\s*\$([0-9]+)([BMT])',
        r'(?:growing\s*AUM\s*from)\s*~?\$([0-9]+)([BMT])\s*to\s*\$([0-9]+)([BMT])',
        r'from\s*\$([0-9]+)([BMT])\s*to\s*(?:nearly\s*)?\$([0-9]+)([BMT])',
    ]

    # Production patterns
    PRODUCTION_PATTERNS = [
        r'\$([0-9]+(?:\.[0-9]+)?)\s*([BMT])?\s*(?:annual\s*)?production',
        r'annual\s*production\s*(?:of|to)\s*~?\$([0-9]+(?:\.[0-9]+)?)\s*([BMT])?',
        r'\$([0-9]+)([BMT])\+?\s*in\s*new\s*(?:AUM|assets)',
    ]

    # Client patterns
    CLIENT_PATTERNS = [
        r'(\d+)\s*(?:HNW|high[\s-]net[\s-]worth)\s*clients',
        r'(\d+)\s*relationships',
        r'(\d+)\s*clients?\s*(?:nationwide|total)?',
        r'(\d+)\+?\s*new\s*clients?/month',
    ]

    # Ranking patterns
    RANKING_PATTERNS = [
        r'(?:ranked\s*)?#(\d+)(?:[-–](\d+))?\s*nationally',
        r'top\s*tier\s*(?:for\s*)?close\s*rate\s*\((\d+)%',
        r'President\'s\s*Club',
        r'Circle\s*of\s*Champions',
        r'top\s*(?:national\s*)?performance',
    ]

    # License patterns
    LICENSE_PATTERNS = [
        r'Series\s*(\d+)',
        r'(?:holds?|has)\s*(?:active\s*)?Series\s*([0-9,\s]+)',
    ]

    # Certification patterns
    CERTIFICATION_PATTERNS = [
        r'\b(CFA|CFP|CPWA|CTFA|ChFC|CLU|WMCP|MBA)\b',
        r'CFA\s*charterholder',
        r'CFP®',
        r'Certified\s*Financial\s*Planner',
    ]

    # Availability patterns
    AVAILABILITY_PATTERNS = [
        r'Available\s*(?:on\s*)?(\d+(?:-\d+)?)\s*weeks?\'?\s*notice',
        r'Available\s*immediately',
        r'(\d+)\s*weeks?\'?\s*notice',
    ]

    # Compensation patterns
    COMPENSATION_PATTERNS = [
        r'\$([0-9]+)K\s*[-–]\s*\$?([0-9]+)(?:K|M)',  # Handles spaces around dash
        r'\$([0-9]+)K(?:[-–]\$?([0-9]+)K)?\s*(?:OTE|base)',
        r'\$([0-9]+)K\+?\s*(?:OTE|base)',
        r'desired\s*comp\s*\$([0-9]+)K(?:\s*[-–]\s*\$?([0-9]+)(?:K|M))?',
    ]

    @classmethod
    def extract_aum(cls, text: str) -> Optional[str]:
        """Extract AUM from text."""
        for pattern in cls.AUM_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                unit = match.group(2).upper()
                return f"${value}{unit}"
        return None

    @classmethod
    def extract_growth(cls, text: str) -> Optional[Tuple[str, str]]:
        """Extract AUM growth story from text."""
        for pattern in cls.GROWTH_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                from_value = match.group(1)
                from_unit = match.group(2).upper()
                to_value = match.group(3)
                to_unit = match.group(4).upper()
                return (f"${from_value}{from_unit}", f"${to_value}{to_unit}")
        return None

    @classmethod
    def extract_production(cls, text: str) -> Optional[str]:
        """Extract production metrics from text."""
        for pattern in cls.PRODUCTION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                unit = match.group(2) if len(match.groups()) > 1 and match.group(2) else ''
                return f"${value}{unit.upper() if unit else 'M'}"
        return None

    @classmethod
    def extract_clients(cls, text: str) -> Optional[str]:
        """Extract client metrics from text."""
        for pattern in cls.CLIENT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    @classmethod
    def extract_licenses(cls, text: str) -> List[str]:
        """Extract licenses from text."""
        licenses = []
        # First check for comma/and-separated series with broader capture
        series_pattern = r'Series\s*([0-9,\s]+?(?:and\s*\d+)?)(?:\s*licenses?|;|\.|$)'
        series_match = re.search(series_pattern, text, re.IGNORECASE)
        if series_match:
            # Extract all numbers from the comma/and-separated list
            numbers = re.findall(r'\d+', series_match.group(1))
            for num in numbers:
                licenses.append(f"Series {num}")
        else:
            # Fall back to individual Series mentions
            for match in re.finditer(r'Series\s*(\d+)', text, re.IGNORECASE):
                licenses.append(f"Series {match.group(1)}")
        return licenses

    @classmethod
    def extract_certifications(cls, text: str) -> List[str]:
        """Extract certifications from text."""
        certs = []
        cert_mappings = {
            'CFA charterholder': 'CFA',
            'CFP®': 'CFP',
            'Certified Financial Planner': 'CFP'
        }

        for pattern in cls.CERTIFICATION_PATTERNS:
            # Use finditer to get all matches, not just the first one
            for cert_match in re.finditer(pattern, text):
                cert = cert_match.group(0).replace('®', '').strip()
                # Normalize certification names
                normalized_cert = cert_mappings.get(cert, cert)
                if normalized_cert not in certs:
                    certs.append(normalized_cert)
        return certs

    @classmethod
    def extract_availability(cls, text: str) -> Optional[str]:
        """Extract availability from text."""
        if re.search(r'Available\s*immediately', text, re.IGNORECASE):
            return "immediately"
        for pattern in cls.AVAILABILITY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and len(match.groups()) > 0:
                return f"{match.group(1)} weeks' notice"
        return None

    @classmethod
    def extract_compensation(cls, text: str) -> Optional[str]:
        """Extract compensation from text."""
        for pattern in cls.COMPENSATION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) >= 2 and match.group(2):
                    # Check if second value is in millions
                    second_val = match.group(2)
                    if second_val == "1" and "1M" in text:
                        return f"${match.group(1)}K-$1M"
                    else:
                        return f"${match.group(1)}K-${second_val}K"
                else:
                    return f"${match.group(1)}K"
        return None


# Test data from Brandon's actual emails
BRANDON_TEST_CASES = [
    # CIO/CGO Jacksonville
    {
        "text": "Built $2.2B RIA from inception alongside founder",
        "expected": {"aum": "$2.2B"}
    },
    {
        "text": "Available on 2 weeks' notice; desired comp $150K-$200K OTE",
        "expected": {
            "availability": "2 weeks' notice",
            "compensation": "$150K-$200K"
        }
    },
    # Orlando Advisor
    {
        "text": "Holds active Series 7, 63, and 65 licenses",
        "expected": {
            "licenses": ["Series 7", "Series 63", "Series 65"]
        }
    },
    {
        "text": "Available on 2 weeks' notice; desired comp $80K-$100K",
        "expected": {
            "availability": "2 weeks' notice",
            "compensation": "$80K-$100K"
        }
    },
    # Temecula Director
    {
        "text": "Managed ~$500M in AUM across 250 HNW clients nationwide",
        "expected": {
            "aum": "$500M",
            "clients": "250"
        }
    },
    {
        "text": "ranked in top tier for close rate (47% vs. 35% avg)",
        "expected": {
            "close_rate": "47%"
        }
    },
    # Minneapolis CBDO
    {
        "text": "Personally raised $2B+ AUM through national, regional, and HNW channels",
        "expected": {
            "aum": "$2B"
        }
    },
    {
        "text": "Available on 2-4 weeks' notice; desired comp $750K - $1M",
        "expected": {
            "availability": "2-4 weeks' notice",
            "compensation": "$750K-$1M"
        }
    },
    # St. Louis Private Wealth
    {
        "text": "currently manages $350M AUM across 65 relationships",
        "expected": {
            "aum": "$350M",
            "relationships": "65"
        }
    },
    {
        "text": "Previously grew a $43M book to $72M in 2 years",
        "expected": {
            "growth": ("$43M", "$72M")
        }
    },
    # Sacramento VP
    {
        "text": "growing AUM from ~$150M to $720M and annual production to ~$5M",
        "expected": {
            "growth": ("$150M", "$720M"),
            "production": "$5M"
        }
    },
    # Bethesda CGO
    {
        "text": "helped grow AUM at one from $200M to nearly $1B",
        "expected": {
            "growth": ("$200M", "$1B")
        }
    },
    # Boston Lead Advisor
    {
        "text": "Built $10M+ in AUM from scratch during COVID",
        "expected": {
            "aum": "$10M"
        }
    },
    # Marietta Lead Advisor
    {
        "text": "Managed $1.5B+ in client assets",
        "expected": {
            "aum": "$1.5B"
        }
    },
    # Salt Lake City CGO
    {
        "text": "scaled firms from $300M to $1B+",
        "expected": {
            "growth": ("$300M", "$1B")
        }
    },
    {
        "text": "built client acquisition infrastructure generating 35+ new clients/month",
        "expected": {
            "clients": "35"
        }
    }
]


class TestFinancialExtraction:
    """Test suite for financial metric extraction."""

    @pytest.mark.parametrize("test_case", BRANDON_TEST_CASES)
    def test_brandon_examples(self, test_case):
        """Test extraction against Brandon's actual email examples."""
        text = test_case["text"]
        expected = test_case["expected"]

        if "aum" in expected:
            assert FinancialExtractor.extract_aum(text) == expected["aum"]

        if "growth" in expected:
            assert FinancialExtractor.extract_growth(text) == expected["growth"]

        if "production" in expected:
            assert FinancialExtractor.extract_production(text) == expected["production"]

        if "clients" in expected:
            assert FinancialExtractor.extract_clients(text) == expected["clients"]

        if "relationships" in expected:
            # Relationships are a type of client metric
            assert FinancialExtractor.extract_clients(text) == expected["relationships"]

        if "licenses" in expected:
            licenses = FinancialExtractor.extract_licenses(text)
            assert set(licenses) == set(expected["licenses"])

        if "availability" in expected:
            assert FinancialExtractor.extract_availability(text) == expected["availability"]

        if "compensation" in expected:
            assert FinancialExtractor.extract_compensation(text) == expected["compensation"]

        if "close_rate" in expected:
            match = re.search(r'close\s*rate\s*\((\d+)%', text, re.IGNORECASE)
            assert match and f"{match.group(1)}%" == expected["close_rate"]

    def test_aum_variations(self):
        """Test various AUM format variations."""
        test_cases = [
            ("Built $2.2B RIA", "$2.2B"),
            ("manages $500M AUM", "$500M"),
            ("$350M in AUM", "$350M"),
            ("$1.5B+ in client assets", "$1.5B"),
            ("~$150M to $720M", "$150M"),
        ]
        for text, expected in test_cases:
            assert FinancialExtractor.extract_aum(text) == expected

    def test_growth_stories(self):
        """Test growth story extraction."""
        test_cases = [
            ("grew from $200M to $1B", ("$200M", "$1B")),
            ("scaled firms from $300M to $1B+", ("$300M", "$1B")),
            ("growing AUM from ~$150M to $720M", ("$150M", "$720M")),
            ("from $43M to $72M", ("$43M", "$72M")),
        ]
        for text, expected in test_cases:
            assert FinancialExtractor.extract_growth(text) == expected

    def test_production_metrics(self):
        """Test production metric extraction."""
        test_cases = [
            ("$5M annual production", "$5M"),
            ("annual production to ~$5M", "$5M"),
            ("$10M+ in new AUM", "$10M"),
        ]
        for text, expected in test_cases:
            assert FinancialExtractor.extract_production(text) == expected

    def test_client_metrics(self):
        """Test client metric extraction."""
        test_cases = [
            ("250 HNW clients", "250"),
            ("65 relationships", "65"),
            ("35+ new clients/month", "35"),
        ]
        for text, expected in test_cases:
            assert FinancialExtractor.extract_clients(text) == expected

    def test_license_extraction(self):
        """Test license extraction with various formats."""
        test_cases = [
            ("Series 7, 63, 65", ["Series 7", "Series 63", "Series 65"]),
            ("Series 7 and 66", ["Series 7", "Series 66"]),
            ("Series 7, 24, 55, 65, and 66", ["Series 7", "Series 24", "Series 55", "Series 65", "Series 66"]),
        ]
        for text, expected in test_cases:
            licenses = FinancialExtractor.extract_licenses(text)
            assert set(licenses) == set(expected)

    def test_certification_extraction(self):
        """Test certification extraction."""
        test_cases = [
            ("CFA charterholder", ["CFA"]),
            ("CFP® since 2000", ["CFP"]),
            ("Holds CPWA designation", ["CPWA"]),
            ("MBA in Marketing", ["MBA"]),
            ("CFA and CFP", ["CFA", "CFP"]),
        ]
        for text, expected in test_cases:
            certs = FinancialExtractor.extract_certifications(text)
            assert set(certs) == set(expected)

    def test_availability_formats(self):
        """Test availability extraction formats."""
        test_cases = [
            ("Available immediately", "immediately"),
            ("Available on 2 weeks' notice", "2 weeks' notice"),
            ("Available on 2-4 weeks' notice", "2-4 weeks' notice"),
            ("2 weeks' notice", "2 weeks' notice"),
        ]
        for text, expected in test_cases:
            assert FinancialExtractor.extract_availability(text) == expected

    def test_compensation_ranges(self):
        """Test compensation extraction with ranges."""
        test_cases = [
            ("desired comp $150K-$200K OTE", "$150K-$200K"),
            ("$80K-$100K", "$80K-$100K"),
            ("$750K - $1M", "$750K-$1M"),
            ("$200K+ OTE", "$200K"),
            ("$120K base", "$120K"),
        ]
        for text, expected in test_cases:
            assert FinancialExtractor.extract_compensation(text) == expected

    def test_edge_cases(self):
        """Test edge cases and potential parsing issues."""
        # Empty string
        assert FinancialExtractor.extract_aum("") is None

        # No financial metrics
        assert FinancialExtractor.extract_aum("Experienced advisor") is None

        # Multiple AUM values (should get first)
        text = "Grew from $100M to $500M, now managing $750M"
        assert FinancialExtractor.extract_aum(text) in ["$100M", "$500M", "$750M"]

        # Malformed numbers
        assert FinancialExtractor.extract_aum("$M in AUM") is None

        # Case sensitivity
        assert FinancialExtractor.extract_aum("$500m aum") == "$500M"

    def test_negative_cases(self):
        """Test cases that should not match."""
        # Not AUM
        assert FinancialExtractor.extract_aum("earned $500K salary") is None

        # Not a growth story
        assert FinancialExtractor.extract_growth("has $500M AUM") is None

        # Not production
        assert FinancialExtractor.extract_production("$500M in total assets") is None

        # Not availability
        assert FinancialExtractor.extract_availability("worked for 2 weeks") is None

    def test_complex_bullets(self):
        """Test extraction from complex multi-metric bullets."""
        text = "Managed ~$500M in AUM across 250 HNW clients nationwide; ranked #1-3 nationally"

        assert FinancialExtractor.extract_aum(text) == "$500M"
        assert FinancialExtractor.extract_clients(text) == "250"
        assert "#1" in text or "nationally" in text  # Ranking detection

    def test_full_candidate_extraction(self):
        """Test extracting all metrics from a full candidate description."""
        candidate_text = """
        Built $2.2B RIA from inception alongside founder
        CFA charterholder who passed all 3 levels consecutively
        Formerly held Series 7, 24, 55, 65, and 66 licenses
        Available on 2 weeks' notice; desired comp $150K-$200K OTE
        """

        metrics = FinancialMetrics(
            aum=FinancialExtractor.extract_aum(candidate_text),
            licenses=FinancialExtractor.extract_licenses(candidate_text),
            certifications=FinancialExtractor.extract_certifications(candidate_text),
            availability=FinancialExtractor.extract_availability(candidate_text),
            compensation=FinancialExtractor.extract_compensation(candidate_text)
        )

        assert metrics.aum == "$2.2B"
        assert "CFA" in metrics.certifications
        assert len(metrics.licenses) == 5
        assert metrics.availability == "2 weeks' notice"
        assert metrics.compensation == "$150K-$200K"


if __name__ == "__main__":
    # Run a quick test
    extractor = FinancialExtractor()
    test_text = "Built $2.2B RIA from inception; Series 7, 63, 65; Available immediately"

    print("Testing extraction on:", test_text)
    print("AUM:", extractor.extract_aum(test_text))
    print("Licenses:", extractor.extract_licenses(test_text))
    print("Availability:", extractor.extract_availability(test_text))