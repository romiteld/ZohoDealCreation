"""
Shared tone and formatting utilities for candidate alert generation.

Used by:
- generate_steve_advisor_alerts.py (main script)
- ai_bullet_generator.py (AI bullet generation)

Boss requirement: "Calm authority. No 'rare', 'exceptional', 'standout'."
"""

import re
from typing import List


def apply_tone_guardrails(text: str) -> str:
    """
    Global tone filter: remove hype language everywhere.

    Boss requirement: "Calm authority. No 'rare', 'exceptional', 'standout'."

    Args:
        text: Input text that may contain hype language

    Returns:
        Cleaned text with calm, professional tone
    """
    HYPE_REPLACEMENTS = {
        # Adjective replacements (calm authority)
        r'\b(?:rare|exceptional)\s+(?:opportunity|find|talent|performer)\b': 'strong candidate',
        r'\ban\s+absolute\s+standout\b': 'a recognized performer',
        r'\bunicorn\s+candidate\b': 'high-performing candidate',
        r'\bphenomenal\s+': 'strong ',
        r'\bextraordinary\s+': 'proven ',

        # Standout patterns (catch all forms)
        r'\bstandout\s+(?:result|case|performance|achievement|success|performer|candidate)\b': 'notable',
        r'\b(?:a|an|one)\s+standout\s+': 'a strong ',

        # Remove standalone hype adjectives
        r'\b(?:rare|exceptional|outstanding|phenomenal|extraordinary|standout)\b': '',
    }

    for pattern, replacement in HYPE_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Clean up multiple spaces
    text = re.sub(r'\s{2,}', ' ', text).strip()

    return text


def simplify_rare_title(title: str) -> str:
    """
    Simplify rare/identifiable titles while preserving grammar.

    Boss requirement: Avoid combinations that could identify candidates
    (e.g., "Director of Advisor Succession Strategy and Practice Integration")

    Args:
        title: Job title that may be overly specific

    Returns:
        Simplified title that preserves meaning but reduces identifiability
    """
    TITLE_SIMPLIFICATIONS = {
        # Full phrase replacements (preserve structure)
        r'Director of Advisor Succession Strategy and Practice Integration': 'Senior Operations Leader',
        r'Vice President of (?:Succession|Integration|Strategy)': 'Senior Operations Leader',
        r'Chief (\w+) Officer': r'Executive Leadership (\1)',

        # Regional identifiers (preserve noun)
        r'Top \d+ RIA in the Pacific Northwest': 'Leading regional RIA',
        r'(?:Pacific Northwest|Southwest|Northeast) branch': 'regional office',

        # Rank removals
        r'ranked #\d+ nationally': 'top-ranked nationally',
    }

    for pattern, replacement in TITLE_SIMPLIFICATIONS.items():
        title = re.sub(pattern, replacement, title, flags=re.IGNORECASE)

    # Clean artifacts
    title = re.sub(r'\s+in the\s+$', '', title)  # Dangling "in the"
    title = re.sub(r'\s{2,}', ' ', title).strip()  # Clean spaces

    return title


def remove_asterisks(html: str) -> str:
    """
    Remove all asterisks from HTML (eliminates manual post-processing).

    Also fixes nested bold tags if any are present.

    Args:
        html: HTML content that may contain asterisks

    Returns:
        Cleaned HTML with no asterisks
    """
    # Remove all asterisks
    html = re.sub(r'\*+', '', html)

    # Fix nested bold tags if any (e.g., <b>text<b>more</b></b>)
    html = re.sub(r'<b>([^<]*)<b>([^<]*)</b></b>', r'<b>\1\2</b>', html)

    return html


def rewrap_bold_emphasis(text: str, emphasis_keywords: List[str]) -> str:
    """
    Re-wrap bold tags around key metrics after paragraph conversion.

    Boss feedback: Keep bold emphasis on financial metrics, designations.

    Args:
        text: Paragraph text with bold tags stripped
        emphasis_keywords: List of keywords to re-bold (e.g., ["$650M AUM", "MBA"])

    Returns:
        Text with <b> tags re-wrapped around emphasis keywords
    """
    # Sort by length (longest first) to avoid partial replacements
    emphasis_keywords = sorted(emphasis_keywords, key=len, reverse=True)

    for keyword in emphasis_keywords:
        # Case-insensitive replacement (only first occurrence)
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        text = pattern.sub(f'<b>{keyword}</b>', text, count=1)

    return text


def extract_emphasis_keywords(text: str) -> List[str]:
    """
    Extract keywords to bold (financial metrics, designations, client types).

    Patterns match:
    - Financial metrics: $650M, $10M-$15M, 40%, top 5%
    - Designations: CFP, CFA, MBA, CPRC, etc.
    - Client types: HNW, UHNW, institutional, RIA, wirehouse

    Args:
        text: Bullet or paragraph text to extract keywords from

    Returns:
        Deduplicated list of keywords to emphasize with <b> tags
    """
    keywords = []

    # Financial patterns (AUM, production, percentages)
    financial_patterns = [
        r'\$[\d,]+(?:\.\d+)?[BMK]?(?:\s*(?:AUM|production|clients))?',  # $650M AUM, $10M production
        r'\d+%',  # 40%, 25%
        r'top\s+\d+%',  # top 5%
    ]

    # Professional designations
    designation_patterns = [
        r'\b(?:CFP|CFA|MBA|CPRC|MDRT|CLU|ChFC|CPA|CRPC|RICP)\b',
    ]

    # Client types and firm descriptions
    client_patterns = [
        r'\b(?:HNW|UHNW|institutional|RIA|wirehouse)\b',
    ]

    # Extract all matches
    for pattern in financial_patterns + designation_patterns + client_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        keywords.extend(matches)

    # Deduplicate while preserving order
    return list(dict.fromkeys(keywords))
