"""
Candidate Anonymizer - Privacy-First Data Transformation

Anonymizes vault candidate data to protect confidential information while preserving
market intelligence value. Used in vault alerts and executive digests.

Key Features:
    - Firm name generalization (Merrill Lynch → "a leading national wirehouse")
    - AUM/production rounding to ranges ($1.68B → "$1.5B-$2.0B range")
    - Location normalization (Frisco, TX → Dallas/Fort Worth)
    - University name stripping (MBA from LSU → MBA)
    - Achievement generalization (firm-specific → industry-standard)
    - Proprietary system removal (internal tools → generic descriptions)

Usage:
    anonymizer = CandidateAnonymizer()
    anonymized = anonymizer.anonymize_candidate(candidate_dict)
"""

import re
from typing import Dict, Any, Optional
from decimal import Decimal


class CandidateAnonymizer:
    """Anonymize candidate data for confidentiality."""

    # Firm type mappings
    FIRM_MAPPINGS = {
        # National Wirehouses
        'merrill': 'a leading national wirehouse',
        'morgan stanley': 'a leading national wirehouse',
        'wells fargo': 'a leading national wirehouse',
        'ubs': 'a leading global wirehouse',

        # Regional Brokerages
        'raymond james': 'a prominent regional brokerage',
        'edward jones': 'a prominent regional brokerage',
        'rbc': 'a prominent regional brokerage',
        'stifel': 'a prominent regional brokerage',

        # Independent RIAs
        'ria': 'an independent RIA',
        'registered investment advisor': 'an independent RIA',

        # Private Banks
        'jpmorgan': 'a leading private bank',
        'citigroup': 'a leading private bank',
        'goldman sachs': 'a leading private bank',
        'bank of america': 'a leading private bank',

        # Insurance-affiliated
        'northwestern mutual': 'an insurance-affiliated wealth management firm',
        'massmutual': 'an insurance-affiliated wealth management firm',
        'new york life': 'an insurance-affiliated wealth management firm',

        # Default fallback
        'default': 'a leading financial services firm'
    }

    # Major metro area mappings
    LOCATION_MAPPINGS = {
        # New York Metro
        'new york': 'New York Metro',
        'manhattan': 'New York Metro',
        'brooklyn': 'New York Metro',
        'queens': 'New York Metro',
        'bronx': 'New York Metro',
        'staten island': 'New York Metro',
        'jersey city': 'New York Metro',
        'hoboken': 'New York Metro',
        'newark': 'New York Metro',

        # Los Angeles Metro
        'los angeles': 'Los Angeles Metro',
        'santa monica': 'Los Angeles Metro',
        'beverly hills': 'Los Angeles Metro',
        'pasadena': 'Los Angeles Metro',
        'long beach': 'Los Angeles Metro',

        # Chicago Metro
        'chicago': 'Chicago Metro',
        'naperville': 'Chicago Metro',
        'evanston': 'Chicago Metro',
        'oak park': 'Chicago Metro',

        # San Francisco Bay Area
        'san francisco': 'San Francisco Bay Area',
        'oakland': 'San Francisco Bay Area',
        'san jose': 'San Francisco Bay Area',
        'palo alto': 'San Francisco Bay Area',
        'mountain view': 'San Francisco Bay Area',
        'menlo park': 'San Francisco Bay Area',

        # Dallas/Fort Worth
        'dallas': 'Dallas/Fort Worth',
        'fort worth': 'Dallas/Fort Worth',
        'frisco': 'Dallas/Fort Worth',
        'plano': 'Dallas/Fort Worth',
        'irving': 'Dallas/Fort Worth',

        # Houston
        'houston': 'Houston Metro',
        'sugar land': 'Houston Metro',
        'the woodlands': 'Houston Metro',

        # Boston Metro
        'boston': 'Boston Metro',
        'cambridge': 'Boston Metro',
        'brookline': 'Boston Metro',

        # Washington DC Metro
        'washington': 'Washington DC Metro',
        'arlington': 'Washington DC Metro',
        'alexandria': 'Washington DC Metro',
        'bethesda': 'Washington DC Metro',

        # Miami Metro
        'miami': 'Miami Metro',
        'fort lauderdale': 'Miami Metro',
        'boca raton': 'Miami Metro',

        # Atlanta Metro
        'atlanta': 'Atlanta Metro',
        'buckhead': 'Atlanta Metro',
        'sandy springs': 'Atlanta Metro',

        # Phoenix Metro
        'phoenix': 'Phoenix Metro',
        'scottsdale': 'Phoenix Metro',

        # Philadelphia Metro
        'philadelphia': 'Philadelphia Metro',

        # Seattle Metro
        'seattle': 'Seattle Metro',
        'bellevue': 'Seattle Metro',

        # Denver Metro
        'denver': 'Denver Metro',

        # Minneapolis Metro
        'minneapolis': 'Minneapolis Metro',
    }

    # AUM/Production range mappings (in millions)
    AUM_RANGES = [
        (0, 25, "$10M-$25M range"),
        (25, 50, "$25M-$50M range"),
        (50, 100, "$50M-$100M range"),
        (100, 150, "$100M-$150M range"),
        (150, 250, "$150M-$250M range"),
        (250, 500, "$250M-$500M range"),
        (500, 750, "$500M-$750M range"),
        (750, 1000, "$750M-$1B range"),
        (1000, 1500, "$1B-$1.5B range"),
        (1500, 2000, "$1.5B-$2B range"),
        (2000, 3000, "$2B-$3B range"),
        (3000, 5000, "$3B-$5B range"),
        (5000, float('inf'), "$5B+ range"),
    ]

    def anonymize_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize a single candidate record.

        Args:
            candidate: Raw candidate dict from database

        Returns:
            Anonymized candidate dict with same structure
        """
        anonymized = candidate.copy()

        # Anonymize firm name
        if 'firm' in anonymized and anonymized['firm']:
            anonymized['firm'] = self._anonymize_firm(anonymized['firm'])

        # Round AUM to range
        if 'aum' in anonymized and anonymized['aum']:
            anonymized['aum'] = self._anonymize_aum(anonymized['aum'])

        # Round production to range
        if 'production' in anonymized and anonymized['production']:
            anonymized['production'] = self._anonymize_production(anonymized['production'])

        # Normalize location
        if 'city' in anonymized and 'state' in anonymized:
            anonymized['city'], anonymized['state'] = self._anonymize_location(
                anonymized.get('city', ''),
                anonymized.get('state', '')
            )

        if 'current_location' in anonymized and anonymized['current_location']:
            city, state = anonymized['current_location'].split(',', 1) if ',' in anonymized['current_location'] else (anonymized['current_location'], '')
            normalized_city, normalized_state = self._anonymize_location(city.strip(), state.strip())
            anonymized['current_location'] = f"{normalized_city}, {normalized_state}" if normalized_state else normalized_city

        # Strip university names from education
        if 'professional_designations' in anonymized and anonymized['professional_designations']:
            anonymized['professional_designations'] = self._anonymize_education(
                anonymized['professional_designations']
            )

        # Generalize achievements in notes/headline
        if 'interviewer_notes' in anonymized and anonymized['interviewer_notes']:
            anonymized['interviewer_notes'] = self._anonymize_text(anonymized['interviewer_notes'])

        if 'headline' in anonymized and anonymized['headline']:
            anonymized['headline'] = self._anonymize_text(anonymized['headline'])

        if 'top_performance' in anonymized and anonymized['top_performance']:
            anonymized['top_performance'] = self._anonymize_text(anonymized['top_performance'])

        if 'candidate_experience' in anonymized and anonymized['candidate_experience']:
            anonymized['candidate_experience'] = self._anonymize_text(anonymized['candidate_experience'])

        return anonymized

    def _anonymize_firm(self, firm: str) -> str:
        """Convert firm name to generic type."""
        if not firm:
            return 'a leading financial services firm'

        firm_lower = firm.lower()

        # Check for exact/partial matches
        for key, value in self.FIRM_MAPPINGS.items():
            if key in firm_lower:
                return value

        # Default fallback
        return self.FIRM_MAPPINGS['default']

    def _anonymize_aum(self, aum: str) -> str:
        """Round AUM to range."""
        if not aum:
            return 'AUM not disclosed'

        # Extract numeric value
        value = self._extract_numeric_value(aum)
        if value is None:
            return 'AUM not disclosed'

        # Convert to millions
        value_millions = value / 1_000_000

        # Find matching range
        for min_val, max_val, range_str in self.AUM_RANGES:
            if min_val <= value_millions < max_val:
                return range_str

        return '$5B+ range'

    def _anonymize_production(self, production: str) -> str:
        """Round production to range."""
        if not production:
            return 'Production not disclosed'

        # Extract numeric value
        value = self._extract_numeric_value(production)
        if value is None:
            return 'Production not disclosed'

        # Use same ranges as AUM
        value_millions = value / 1_000_000

        for min_val, max_val, range_str in self.AUM_RANGES:
            if min_val <= value_millions < max_val:
                return range_str

        return '$5B+ range'

    def _anonymize_location(self, city: str, state: str) -> tuple:
        """Normalize location to major metro area."""
        if not city:
            return ('Location not disclosed', '')

        city_lower = city.lower().strip()

        # Check mappings
        for key, metro in self.LOCATION_MAPPINGS.items():
            if key in city_lower:
                return (metro, '')

        # Fallback for cities not in major metros: Use "City, State" format (removes identifying suburbs)
        # This protects privacy while still showing general region
        if state:
            # Remove zip codes and extra details
            city_clean = re.sub(r'\s+\d{5}(-\d{4})?$', '', city.strip())
            # Remove any neighborhood/area descriptors (e.g., "Washington Park, Denver" -> "Denver")
            city_clean = city_clean.split(',')[0].strip()
            return (f"{city_clean} area", state.strip())

        # If no state provided, just show city area
        city_clean = re.sub(r'\s+\d{5}(-\d{4})?$', '', city.strip())
        city_clean = city_clean.split(',')[0].strip()
        return (f"{city_clean} area", '')

    def _anonymize_education(self, education: str) -> str:
        """Strip university names from education credentials."""
        if not education:
            return education

        # Pattern: "MBA from University of XYZ" → "MBA"
        # Pattern: "BS in Finance, ABC University" → "BS in Finance"
        # Pattern: "Master's in Finance (College for Financial Planning)" → "Master's in Finance"

        # Remove " from [University]"
        education = re.sub(r'\s+from\s+[A-Z][a-zA-Z\s&]+(?:University|College|Institute|School)', '', education, flags=re.IGNORECASE)

        # Remove ", [University]"
        education = re.sub(r',\s*[A-Z][a-zA-Z\s&]+(?:University|College|Institute|School)', '', education, flags=re.IGNORECASE)

        # Remove " at [University]"
        education = re.sub(r'\s+at\s+[A-Z][a-zA-Z\s&]+(?:University|College|Institute|School)', '', education, flags=re.IGNORECASE)

        # Remove parenthetical university names: "(College for Financial Planning)" → ""
        education = re.sub(r'\s*\([^)]*(?:University|College|Institute|School)[^)]*\)', '', education, flags=re.IGNORECASE)

        # Remove " of [University]" patterns
        education = re.sub(r'\s+of\s+[A-Z][a-zA-Z\s&]+(?:University|College|Institute|School)', '', education, flags=re.IGNORECASE)

        return education.strip()

    def _anonymize_text(self, text: str) -> str:
        """Remove proprietary systems and firm-specific details from text."""
        if not text:
            return text

        # Remove specific firm names using the firm mappings
        for firm_keyword in self.FIRM_MAPPINGS.keys():
            if firm_keyword != 'default':
                # Case-insensitive replacement
                pattern = re.compile(re.escape(firm_keyword), re.IGNORECASE)
                text = pattern.sub('the firm', text)

        # Remove proprietary system names (common patterns)
        proprietary_patterns = [
            r'\b[A-Z][a-zA-Z]*(?:Pro|Connect|View|Portal|System|Platform|Suite)\b',  # CamelCase systems
            r'\b(?:internal|proprietary)\s+(?:system|platform|tool|software)\b',
        ]

        for pattern in proprietary_patterns:
            text = re.sub(pattern, 'internal systems', text, flags=re.IGNORECASE)

        return text

    def _extract_numeric_value(self, value_str: str) -> Optional[float]:
        """
        Extract numeric value from string with k/m/b suffixes.

        Examples:
            "$1.68B" → 1680000000
            "500M" → 500000000
            "$250k" → 250000
        """
        if not value_str:
            return None

        # Remove currency symbols and commas
        clean = re.sub(r'[\$,]', '', value_str.strip())

        # Extract number and suffix
        match = re.search(r'([\d.]+)\s*([kKmMbB])?', clean)
        if not match:
            return None

        number = float(match.group(1))
        suffix = match.group(2)

        if suffix:
            suffix_lower = suffix.lower()
            if suffix_lower == 'k':
                number *= 1_000
            elif suffix_lower == 'm':
                number *= 1_000_000
            elif suffix_lower == 'b':
                number *= 1_000_000_000

        return number


# Convenience function for module-level usage
def anonymize_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to anonymize a candidate.

    Args:
        candidate: Raw candidate dict from database

    Returns:
        Anonymized candidate dict
    """
    anonymizer = CandidateAnonymizer()
    return anonymizer.anonymize_candidate(candidate)
