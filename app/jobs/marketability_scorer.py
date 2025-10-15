"""
Marketability Scorer for Vault Candidates

Calculates a 0-100 marketability score based on weighted factors:
- AUM/Book Size (40 points)
- Production L12Mo (30 points)
- Credentials/Designations (15 points)
- Availability (15 points)

Used for "top N most marketable candidates" queries in Teams Bot.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class MarketabilityScorer:
    """Calculate marketability scores for vault candidates."""

    # Premium designations and their point values
    PREMIUM_DESIGNATIONS = {
        'cfa': 10,
        'cfp': 10,
        'cpa': 7,
        'crpc': 5,
        'ricp': 5,
        'chfc': 5,
        'cima': 5,
        'cpwa': 5,
    }

    # Standard licenses
    STANDARD_LICENSES = {
        'series 7': 2,
        'series 66': 2,
        'series 65': 2,
        'series 63': 1,
        'series 6': 1,
    }

    def __init__(self):
        """Initialize scorer with default weights."""
        self.aum_weight = 40
        self.production_weight = 30
        self.credentials_weight = 15
        self.availability_weight = 15

    def score_candidate(self, candidate: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
        """
        Calculate total marketability score for a candidate.

        Args:
            candidate: Candidate data from Zoho CRM with fields:
                - Book_Size_AUM (str): "$300M", "$1.5B", etc.
                - Production_L12Mo (str): "$1.2M annually", "$500K", etc.
                - Licenses_and_Exams (str): "Series 7, 66, CFP, CFA", etc.
                - When_Available (str): "Immediately", "2 weeks notice", etc.

        Returns:
            Tuple of (total_score, breakdown_dict)
            - total_score: 0-100 float
            - breakdown_dict: {"aum": X, "production": Y, "credentials": Z, "availability": W}
        """
        try:
            # Extract fields with safe defaults
            aum_text = candidate.get('Book_Size_AUM', '') or ''
            production_text = candidate.get('Production_L12Mo', '') or ''
            licenses_text = candidate.get('Licenses_and_Exams', '') or ''
            availability_text = candidate.get('When_Available', '') or ''

            # Calculate component scores
            aum_score = self._score_aum(aum_text)
            production_score = self._score_production(production_text)
            credentials_score = self._score_credentials(licenses_text)
            availability_score = self._score_availability(availability_text)

            # Calculate total
            total = aum_score + production_score + credentials_score + availability_score

            breakdown = {
                'aum': aum_score,
                'production': production_score,
                'credentials': credentials_score,
                'availability': availability_score,
            }

            logger.debug(f"Scored candidate {candidate.get('Candidate_Locator', 'unknown')}: {total:.1f} "
                        f"(AUM: {aum_score}, Prod: {production_score}, Creds: {credentials_score}, Avail: {availability_score})")

            return round(total, 1), breakdown

        except Exception as e:
            logger.error(f"Error scoring candidate {candidate.get('Candidate_Locator', 'unknown')}: {e}")
            return 0.0, {'aum': 0, 'production': 0, 'credentials': 0, 'availability': 0}

    def _score_aum(self, aum_text: str) -> float:
        """
        Score AUM/Book Size (max 40 points).

        Examples:
            "$1.5B" → 40 pts
            "$750M" → 35 pts
            "$300M" → 30 pts
            "$150M" → 20 pts
            "$75M" → 10 pts
        """
        if not aum_text:
            return 0.0

        # Parse dollar amount
        aum_value = self._parse_dollar_amount(aum_text)
        if aum_value is None:
            return 0.0

        # Score based on amount
        if aum_value >= 1_000_000_000:  # $1B+
            return 40.0
        elif aum_value >= 500_000_000:  # $500M+
            return 35.0
        elif aum_value >= 300_000_000:  # $300M+
            return 30.0
        elif aum_value >= 100_000_000:  # $100M+
            return 20.0
        elif aum_value >= 50_000_000:   # $50M+
            return 10.0
        else:                             # <$50M
            return 5.0

    def _score_production(self, production_text: str) -> float:
        """
        Score Production L12Mo (max 30 points).

        Examples:
            "$2.5M annually" → 30 pts
            "$1.2M" → 25 pts
            "$750K" → 20 pts
            "$400K" → 15 pts
        """
        if not production_text:
            return 0.0

        # Parse dollar amount
        production_value = self._parse_dollar_amount(production_text)
        if production_value is None:
            return 0.0

        # Score based on amount
        if production_value >= 2_000_000:    # $2M+
            return 30.0
        elif production_value >= 1_000_000:  # $1M+
            return 25.0
        elif production_value >= 500_000:    # $500K+
            return 20.0
        elif production_value >= 250_000:    # $250K+
            return 15.0
        else:                                 # <$250K
            return 5.0

    def _score_credentials(self, licenses_text: str) -> float:
        """
        Score Credentials/Designations (max 15 points).

        Examples:
            "CFP, CFA" → 15 pts (both premium)
            "CFP, Series 7, 66" → 14 pts (premium + licenses)
            "Series 7, 66, 65" → 6 pts (standard licenses)
        """
        if not licenses_text:
            return 0.0

        licenses_lower = licenses_text.lower()
        score = 0.0

        # Check premium designations
        for designation, points in self.PREMIUM_DESIGNATIONS.items():
            if designation in licenses_lower:
                score += points

        # Check standard licenses
        for license_type, points in self.STANDARD_LICENSES.items():
            if license_type in licenses_lower:
                score += points

        # Cap at max points
        return min(score, 15.0)

    def _score_availability(self, availability_text: str) -> float:
        """
        Score Availability/When_Available (max 15 points).

        Examples:
            "Immediately" → 15 pts
            "ASAP" → 15 pts
            "2 weeks notice" → 12 pts
            "1 month" → 8 pts
            "2-3 months" → 3 pts
        """
        if not availability_text:
            return 5.0  # Unknown = middle score

        avail_lower = availability_text.lower()

        # Immediate availability
        if any(keyword in avail_lower for keyword in ['immediate', 'asap', 'now', 'right away']):
            return 15.0

        # Extract timeframe
        # Pattern: "X weeks" or "X months"
        weeks_match = re.search(r'(\d+)\s*weeks?', avail_lower)
        months_match = re.search(r'(\d+)\s*months?', avail_lower)

        if weeks_match:
            weeks = int(weeks_match.group(1))
            if weeks <= 2:
                return 12.0
            elif weeks <= 4:
                return 8.0
            else:
                return 3.0

        if months_match:
            months = int(months_match.group(1))
            if months == 1:
                return 8.0
            elif months <= 2:
                return 5.0
            else:
                return 3.0

        # Default: unknown timeframe
        return 5.0

    def _parse_dollar_amount(self, text: str) -> Optional[float]:
        """
        Parse dollar amounts with K/M/B suffixes.

        Examples:
            "$1.5B" → 1_500_000_000
            "$750M" → 750_000_000
            "$500K" → 500_000
            "$2M annually" → 2_000_000

        Returns:
            Float dollar amount or None if unparseable
        """
        if not text:
            return None

        # Remove common words
        text = text.lower().replace('annually', '').replace('aum', '').strip()

        # Pattern: $X.XB, $XM, $XK
        pattern = r'\$?\s*(\d+(?:\.\d+)?)\s*([kmb])?'
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            return None

        number = float(match.group(1))
        suffix = match.group(2)

        if suffix:
            suffix_lower = suffix.lower()
            if suffix_lower == 'k':
                return number * 1_000
            elif suffix_lower == 'm':
                return number * 1_000_000
            elif suffix_lower == 'b':
                return number * 1_000_000_000

        # No suffix - assume raw dollar amount if > 1000, else assume millions
        if number > 1000:
            return number
        else:
            # Likely shorthand: "300" means "300M"
            return number * 1_000_000
