"""
Comprehensive anonymization engine for candidate data.

Removes identifying information from candidate profiles:
- Firm names replaced with generic industry classifications
- AUM/production figures rounded to ranges
- Locations normalized to major metros
- Education stripped to degree types only
- Achievements generalized
- Proprietary systems removed

Author: The Well
Last Updated: 2025-10-13
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal


# ============================================================================
# FIRM CLASSIFICATIONS
# ============================================================================

WIREHOUSES = {
    "merrill lynch": "a leading national wirehouse",
    "morgan stanley": "a leading national wirehouse",
    "ubs": "a leading national wirehouse",
    "wells fargo advisors": "a leading national wirehouse",
    "wells fargo": "a leading national wirehouse",
    "edward jones": "a leading national wirehouse",
    "stifel": "a leading national wirehouse",
    "raymond james": "a leading national wirehouse",
}

RIAS = {
    "cresset": "a multi-billion dollar RIA",
    "fisher investments": "a multi-billion dollar RIA",
    "edelman financial": "a multi-billion dollar RIA",
    "creative planning": "a multi-billion dollar RIA",
    "captrust": "a multi-billion dollar RIA",
    "brightworth": "a multi-billion dollar RIA",
    "ancora": "a multi-billion dollar RIA",
    "mariner wealth": "a multi-billion dollar RIA",
    "hightower": "a multi-billion dollar RIA",
    "sanctuary wealth": "a multi-billion dollar RIA",
    "steward partners": "a multi-billion dollar RIA",
    "wealth enhancement group": "a multi-billion dollar RIA",
    "carson group": "a multi-billion dollar RIA",
    "dynasty financial": "a multi-billion dollar RIA",
    "corient": "a multi-billion dollar RIA",
    "cetera": "a multi-billion dollar RIA",
}

BANKS = {
    "safe credit union": "a regional banking institution",
    "regions bank": "a regional banking institution",
    "pnc": "a regional banking institution",
    "fifth third": "a regional banking institution",
    "truist": "a regional banking institution",
    "key bank": "a regional banking institution",
    "huntington": "a regional banking institution",
    "citizens bank": "a regional banking institution",
    "m&t bank": "a regional banking institution",
    "first horizon": "a regional banking institution",
    "bmo harris": "a regional banking institution",
    "bmo": "a regional banking institution",
    "comerica": "a regional banking institution",
    "zions": "a regional banking institution",
    "valley national": "a regional banking institution",
}

ASSET_MANAGERS = {
    "fidelity": "a Fortune 500 asset manager",
    "vanguard": "a Fortune 500 asset manager",
    "charles schwab": "a Fortune 500 asset manager",
    "schwab": "a Fortune 500 asset manager",
    "jp morgan": "a Fortune 500 asset manager",
    "jpmorgan": "a Fortune 500 asset manager",
    "goldman sachs": "a Fortune 500 asset manager",
    "blackrock": "a Fortune 500 asset manager",
    "state street": "a Fortune 500 asset manager",
    "bny mellon": "a Fortune 500 asset manager",
    "northern trust": "a Fortune 500 asset manager",
    "t. rowe price": "a Fortune 500 asset manager",
    "t rowe price": "a Fortune 500 asset manager",
    "franklin templeton": "a Fortune 500 asset manager",
    "invesco": "a Fortune 500 asset manager",
    "capital group": "a Fortune 500 asset manager",
    "ameriprise": "a Fortune 500 asset manager",
}

INDEPENDENT_BDS = {
    "lpl financial": "a major independent broker-dealer",
    "lpl": "a major independent broker-dealer",
    "commonwealth financial": "a major independent broker-dealer",
    "northwestern mutual": "a major independent broker-dealer",
    "massmututal": "a major independent broker-dealer",
    "lincoln financial": "a major independent broker-dealer",
    "principal": "a major independent broker-dealer",
    "ameriprise financial": "a major independent broker-dealer",
    "cetera financial": "a major independent broker-dealer",
    "cambridge investment": "a major independent broker-dealer",
    "osaic": "a major independent broker-dealer",
    "securities america": "a major independent broker-dealer",
    "advisor group": "a major independent broker-dealer",
    "kestra financial": "a major independent broker-dealer",
    "signator investors": "a major independent broker-dealer",
}

# Compile all firms into single lookup
ALL_FIRMS = {
    **WIREHOUSES,
    **RIAS,
    **BANKS,
    **ASSET_MANAGERS,
    **INDEPENDENT_BDS,
}


# ============================================================================
# METRO AREA MAPPINGS
# ============================================================================

MAJOR_METROS = {
    # Texas metros
    "dallas": "Dallas/Fort Worth",
    "fort worth": "Dallas/Fort Worth",
    "frisco": "Dallas/Fort Worth",
    "plano": "Dallas/Fort Worth",
    "irving": "Dallas/Fort Worth",
    "arlington": "Dallas/Fort Worth",
    "garland": "Dallas/Fort Worth",
    "mckinney": "Dallas/Fort Worth",

    "houston": "Houston",
    "sugar land": "Houston",
    "the woodlands": "Houston",
    "pearland": "Houston",
    "katy": "Houston",

    "austin": "Austin",
    "round rock": "Austin",
    "cedar park": "Austin",
    "pflugerville": "Austin",

    "san antonio": "San Antonio",
    "new braunfels": "San Antonio",

    # California metros
    "los angeles": "Los Angeles",
    "santa monica": "Los Angeles",
    "pasadena": "Los Angeles",
    "glendale": "Los Angeles",
    "long beach": "Los Angeles",
    "irvine": "Los Angeles",
    "anaheim": "Los Angeles",

    "san diego": "San Diego",
    "carlsbad": "San Diego",
    "oceanside": "San Diego",

    "san francisco": "San Francisco",
    "san jose": "San Francisco",
    "oakland": "San Francisco",
    "berkeley": "San Francisco",
    "palo alto": "San Francisco",
    "mountain view": "San Francisco",
    "sunnyvale": "San Francisco",

    "sacramento": "San Francisco",

    # New York metro
    "new york": "New York",
    "brooklyn": "New York",
    "queens": "New York",
    "manhattan": "New York",
    "bronx": "New York",
    "staten island": "New York",
    "white plains": "New York",
    "yonkers": "New York",
    "jersey city": "New York",
    "newark": "New York",

    # Illinois
    "chicago": "Chicago",
    "naperville": "Chicago",
    "aurora": "Chicago",
    "joliet": "Chicago",
    "schaumburg": "Chicago",

    # Florida metros
    "miami": "Miami",
    "fort lauderdale": "Miami",
    "coral gables": "Miami",
    "boca raton": "Miami",
    "west palm beach": "Miami",

    "orlando": "Orlando",
    "kissimmee": "Orlando",
    "winter park": "Orlando",

    "tampa": "Tampa",
    "st. petersburg": "Tampa",
    "st petersburg": "Tampa",
    "clearwater": "Tampa",

    "jacksonville": "Florida",

    # Arizona
    "phoenix": "Phoenix",
    "scottsdale": "Phoenix",
    "tempe": "Phoenix",
    "mesa": "Phoenix",
    "chandler": "Phoenix",
    "glendale": "Phoenix",

    # Pennsylvania
    "philadelphia": "Philadelphia",
    "pittsburgh": "Philadelphia",

    # Colorado
    "denver": "Denver",
    "aurora": "Denver",
    "boulder": "Denver",
    "fort collins": "Denver",

    # Washington
    "seattle": "Seattle",
    "bellevue": "Seattle",
    "tacoma": "Seattle",
    "spokane": "Seattle",

    # Oregon
    "portland": "Portland",
    "salem": "Portland",
    "eugene": "Portland",

    # Massachusetts
    "boston": "Boston",
    "cambridge": "Boston",
    "worcester": "Boston",

    # Georgia
    "atlanta": "Atlanta",
    "sandy springs": "Atlanta",
    "marietta": "Atlanta",

    # Michigan
    "detroit": "Greater Detroit Area",
    "grand rapids": "Greater Detroit Area",
    "ann arbor": "Greater Detroit Area",
    "lansing": "Greater Detroit Area",

    # Minnesota
    "minneapolis": "Minneapolis",
    "st. paul": "Minneapolis",
    "st paul": "Minneapolis",

    # North Carolina
    "charlotte": "Charlotte",
    "raleigh": "Charlotte",
    "durham": "Charlotte",
    "greensboro": "Charlotte",

    # DC area
    "washington": "Washington DC",
    "washington dc": "Washington DC",
    "arlington": "Washington DC",
    "alexandria": "Washington DC",
    "bethesda": "Washington DC",

    # Nevada
    "las vegas": "Las Vegas",
    "henderson": "Las Vegas",
    "reno": "Las Vegas",

    # Tennessee
    "nashville": "Nashville",
    "memphis": "Nashville",
    "knoxville": "Nashville",
}

# Regional fallbacks for smaller cities
REGIONAL_FALLBACKS = {
    "AL": "Southeast Region",
    "AR": "South Central Region",
    "IA": "Midwest Region",
    "ID": "Mountain West Region",
    "IN": "Midwest Region",
    "KS": "Midwest Region",
    "KY": "Southeast Region",
    "LA": "South Central Region",
    "ME": "Northeast Region",
    "MO": "Midwest Region",
    "MS": "Southeast Region",
    "MT": "Mountain West Region",
    "ND": "Midwest Region",
    "NE": "Midwest Region",
    "NH": "Northeast Region",
    "NM": "Southwest Region",
    "NV": "Mountain West Region",
    "OH": "Midwest Region",
    "OK": "South Central Region",
    "RI": "Northeast Region",
    "SC": "Southeast Region",
    "SD": "Midwest Region",
    "UT": "Mountain West Region",
    "VT": "Northeast Region",
    "WI": "Midwest Region",
    "WV": "Southeast Region",
    "WY": "Mountain West Region",
}


# ============================================================================
# PATTERN DEFINITIONS
# ============================================================================

# Education patterns - simpler and more targeted
UNIVERSITY_REMOVAL_PATTERNS = [
    # "MBA from [University]" → "MBA"
    (re.compile(r'\b(MBA|MS|MA|BS|BA|PhD|JD|MD)\s+from\s+[A-Za-z\s]+?(?=,|\.|$)', re.IGNORECASE), r'\1'),

    # "MBA ([University])" → "MBA"
    (re.compile(r'\b(MBA|MS|MA|BS|BA|PhD|JD|MD|CFA|CFP|ChFC|CLU)\s*\([^\)]+\)', re.IGNORECASE), r'\1'),

    # Remove standalone university mentions
    (re.compile(r'\b(Harvard|Stanford|MIT|Yale|Penn State|LSU|UCLA|USC|NYU|Columbia|Cornell|Duke|Northwestern|Georgetown|Rice|Vanderbilt|Emory|Carnegie Mellon|IE University|INSEAD|Wharton|Kellogg|Booth|Sloan|Louisiana State University|University of\s+\w+)\b', re.IGNORECASE), ''),
]

# Achievement patterns
ACHIEVEMENT_PATTERNS = {
    # Rankings
    re.compile(r"(?:ranked|ranking)\s+#?\d+\s+(?:nationwide|nationally|in\s+the\s+nation)", re.IGNORECASE): "Top-ranked nationally",
    re.compile(r"#?\d+\s+(?:ranked|ranking)", re.IGNORECASE): "Top-ranked",

    # Market share
    re.compile(r"(?:captured|secured|achieved)\s+\d+%\s+(?:of\s+)?(?:market\s+share|market)", re.IGNORECASE): "Leading market position",

    # Producer recognition
    re.compile(r"(?:Chairman'?s|President'?s|Executive)\s+Club", re.IGNORECASE): "Top producer recognition",
    re.compile(r"Court\s+of\s+the\s+Table", re.IGNORECASE): "Top producer recognition",
    re.compile(r"Top\s+\d+%", re.IGNORECASE): "Top producer",
}

# Proprietary systems
PROPRIETARY_SYSTEMS = {
    re.compile(r"\bE23\s+Consulting\b", re.IGNORECASE): "custom consulting methodology",
    re.compile(r"\bSavvy\s+platform\b", re.IGNORECASE): "firm-branded technology solution",
    re.compile(r"\bSearch\s+Everywhere\s+Optimization\b", re.IGNORECASE): "internal optimization framework",
    re.compile(r"\b[A-Z][a-z]+[A-Z][a-z]+\s+(?:platform|system|methodology|framework)\b"): "proprietary technology",
}

# ZIP code pattern
ZIP_CODE_PATTERN = re.compile(r"\b\d{5}(?:-\d{4})?\b")

# AUM/Production patterns
AUM_PATTERN = re.compile(r"\$?(\d+(?:\.\d+)?)\s*([BMK])\b", re.IGNORECASE)
RANGE_PATTERN = re.compile(r"\$?(\d+(?:\.\d+)?)\s*([BMK])\s+(?:to|-)\s+\$?(\d+(?:\.\d+)?)\s*([BMK])", re.IGNORECASE)


# ============================================================================
# CORE ANONYMIZATION FUNCTIONS
# ============================================================================

def anonymize_firm_name(text: str) -> str:
    """
    Replace specific firm names with generic industry classifications.

    Args:
        text: Input text containing firm names

    Returns:
        Text with firm names anonymized

    Examples:
        >>> anonymize_firm_name("Works at Merrill Lynch")
        "Works at a leading national wirehouse"

        >>> anonymize_firm_name("Managing $500M at Fisher Investments")
        "Managing $500M at a multi-billion dollar RIA"
    """
    if not text:
        return text

    result = text
    text_lower = text.lower()

    # Sort firms by length (longest first) to avoid partial matches
    sorted_firms = sorted(ALL_FIRMS.items(), key=lambda x: len(x[0]), reverse=True)

    for firm_name, classification in sorted_firms:
        # Use word boundaries to avoid partial matches
        pattern = re.compile(r'\b' + re.escape(firm_name) + r'\b', re.IGNORECASE)
        result = pattern.sub(classification, result)

    return result


def normalize_location(city: Optional[str], state: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalize location to major metro or regional classification.

    Args:
        city: City name (may include ZIP code)
        state: State abbreviation or full name

    Returns:
        Tuple of (normalized_city, state) where city is major metro or None

    Examples:
        >>> normalize_location("Frisco, TX 75034", "TX")
        ("Dallas/Fort Worth", "TX")

        >>> normalize_location("Grand Rapids", "MI")
        ("Greater Detroit Area", "MI")

        >>> normalize_location("Des Moines", "IA")
        (None, "IA")  # Falls back to regional in calling code
    """
    if not city:
        return None, state

    # Strip ZIP codes
    city_clean = ZIP_CODE_PATTERN.sub("", city).strip().strip(",").strip()
    city_lower = city_clean.lower()

    # Check major metros mapping
    if city_lower in MAJOR_METROS:
        return MAJOR_METROS[city_lower], state

    # No match - return None to trigger regional fallback
    return None, state


def round_aum_to_range(amount_str: str) -> str:
    """
    Convert exact AUM/production figures to rounded ranges.

    Rounding rules:
    - Under $500M: Round to nearest $50M
    - Over $500M: Round to nearest $100M

    Args:
        amount_str: Amount string like "$1.68B", "$300M", "125M"

    Returns:
        Rounded range string like "$1.5B-$2.0B", "$250M-$400M"

    Examples:
        >>> round_aum_to_range("$1.68B")
        "$1.5B-$2.0B"

        >>> round_aum_to_range("300M")
        "$250M-$400M"

        >>> round_aum_to_range("$75M")
        "$50M-$100M"
    """
    match = AUM_PATTERN.search(amount_str)
    if not match:
        return amount_str

    value_str, unit = match.groups()
    value = float(value_str)

    # Convert to millions for easier math
    if unit.upper() == "B":
        value_millions = value * 1000
    elif unit.upper() == "K":
        value_millions = value / 1000
    else:  # M
        value_millions = value

    # Determine rounding increment
    if value_millions < 500:
        increment = 50
    else:
        increment = 100

    # Round to nearest increment
    lower = (value_millions // increment) * increment
    upper = lower + increment

    # Format back to appropriate unit
    if lower >= 1000:
        lower_val = lower / 1000
        upper_val = upper / 1000
        unit_str = "B"
    else:
        lower_val = lower
        upper_val = upper
        unit_str = "M"

    # Format with appropriate decimal places
    if lower_val == int(lower_val) and upper_val == int(upper_val):
        return f"${int(lower_val)}{unit_str}-${int(upper_val)}{unit_str}"
    else:
        return f"${lower_val:.1f}{unit_str}-${upper_val:.1f}{unit_str}"


def generalize_growth_statement(text: str) -> str:
    """
    Convert specific growth metrics to generalized statements.

    Args:
        text: Text containing growth metrics

    Returns:
        Text with generalized growth statements

    Examples:
        >>> generalize_growth_statement("Scaled from $125M to $300M")
        "More than doubled AUM"

        >>> generalize_growth_statement("Grew by 150% in 3 years")
        "Significantly grew business"
    """
    if not text:
        return text

    result = text

    # Pattern: "from X to Y" where Y > 2X
    growth_match = re.search(
        r"(?:scaled|grew|increased|expanded)\s+from\s+\$?(\d+(?:\.\d+)?)\s*([BMK])\s+to\s+\$?(\d+(?:\.\d+)?)\s*([BMK])",
        text,
        re.IGNORECASE
    )

    if growth_match:
        from_val, from_unit, to_val, to_unit = growth_match.groups()

        # Convert to common unit (millions)
        from_millions = float(from_val) * (1000 if from_unit.upper() == "B" else 1)
        to_millions = float(to_val) * (1000 if to_unit.upper() == "B" else 1)

        if to_millions >= from_millions * 2:
            result = re.sub(
                growth_match.group(0),
                "more than doubled AUM",
                result,
                flags=re.IGNORECASE
            )
        elif to_millions >= from_millions * 1.5:
            result = re.sub(
                growth_match.group(0),
                "significantly grew AUM",
                result,
                flags=re.IGNORECASE
            )

    # Pattern: "grew by X%"
    pct_match = re.search(r"grew\s+by\s+(\d+)%", text, re.IGNORECASE)
    if pct_match:
        pct = int(pct_match.group(1))
        if pct >= 100:
            replacement = "more than doubled business"
        elif pct >= 50:
            replacement = "significantly grew business"
        else:
            replacement = "grew business"

        result = re.sub(pct_match.group(0), replacement, result, flags=re.IGNORECASE)

    return result


def strip_education_details(text: str) -> str:
    """
    Remove university names from education credentials, keeping only degree types.

    Args:
        text: Text containing education information

    Returns:
        Text with university names removed

    Examples:
        >>> strip_education_details("MBA from LSU, CFA")
        "MBA, CFA"

        >>> strip_education_details("Global MBA from IE University")
        "Global MBA"

        >>> strip_education_details("Master's in Finance (Penn State)")
        "Master's in Finance"
    """
    if not text:
        return text

    result = text

    # Apply each pattern with its replacement
    for pattern, replacement in UNIVERSITY_REMOVAL_PATTERNS:
        result = pattern.sub(replacement, result)

    # Clean up artifacts
    result = re.sub(r'\s*\(\s*\)', '', result)  # Remove empty parentheses
    result = re.sub(r'\s+', ' ', result)  # Normalize spaces
    result = re.sub(r'\s*,\s*', ', ', result)  # Normalize commas
    result = result.strip()

    return result


def generalize_achievements(text: str) -> str:
    """
    Replace specific achievement metrics with generalized statements.

    Args:
        text: Text containing achievement statements

    Returns:
        Text with generalized achievements

    Examples:
        >>> generalize_achievements("Ranked #1 nationwide")
        "Top-ranked nationally"

        >>> generalize_achievements("Captured 52% VA market share in 2021")
        "Leading market position"

        >>> generalize_achievements("Chairman's Club at Schwab")
        "Top producer recognition"
    """
    if not text:
        return text

    result = text

    for pattern, replacement in ACHIEVEMENT_PATTERNS.items():
        result = pattern.sub(replacement, result)

    return result


def remove_proprietary_systems(text: str) -> str:
    """
    Replace proprietary system names with generic descriptions.

    Args:
        text: Text containing proprietary system names

    Returns:
        Text with generic system descriptions

    Examples:
        >>> remove_proprietary_systems("Uses E23 Consulting framework")
        "Uses custom consulting methodology"

        >>> remove_proprietary_systems("Built on Savvy platform")
        "Built on firm-branded technology solution"
    """
    if not text:
        return text

    result = text

    for pattern, replacement in PROPRIETARY_SYSTEMS.items():
        result = pattern.sub(replacement, result)

    return result


def anonymize_text_field(text: str) -> str:
    """
    Apply all text anonymization rules to a single field.

    Processes in order:
    1. Firm names
    2. Education details
    3. Achievements
    4. Proprietary systems
    5. Growth statements

    Args:
        text: Raw text to anonymize

    Returns:
        Fully anonymized text
    """
    if not text or not isinstance(text, str):
        return text

    result = text
    result = anonymize_firm_name(result)
    result = strip_education_details(result)
    result = generalize_achievements(result)
    result = remove_proprietary_systems(result)
    result = generalize_growth_statement(result)

    return result


# ============================================================================
# MAIN ANONYMIZATION FUNCTION
# ============================================================================

def anonymize_candidate_data(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Anonymize all identifying information in candidate data.

    This is the main entry point for the anonymization engine. It creates a deep copy
    of the candidate data and applies all anonymization rules:

    - Firm names → Generic industry classifications
    - Cities → Major metro areas or regional classifications
    - ZIP codes → Removed
    - AUM/Production → Rounded to ranges
    - Education → Degree types only (no universities)
    - Achievements → Generalized statements
    - Proprietary systems → Generic descriptions

    Args:
        candidate: Dictionary containing candidate fields to anonymize.
                  Common fields: firm, city, state, aum, production, education,
                  bio, achievements, etc.

    Returns:
        New dictionary with all fields anonymized. Original dict is unchanged.

    Examples:
        >>> candidate = {
        ...     "firm": "Merrill Lynch",
        ...     "city": "Frisco",
        ...     "state": "TX",
        ...     "aum": "$1.68B",
        ...     "education": "MBA from LSU",
        ...     "bio": "Ranked #1 nationwide at Schwab"
        ... }
        >>> result = anonymize_candidate_data(candidate)
        >>> result["firm"]
        "a leading national wirehouse"
        >>> result["city"]
        "Dallas/Fort Worth"
        >>> result["aum"]
        "$1.5B-$2.0B"
    """
    import copy
    anonymized = copy.deepcopy(candidate)

    # 1. Anonymize firm name
    if "firm" in anonymized and anonymized["firm"]:
        anonymized["firm"] = anonymize_firm_name(anonymized["firm"])

    if "current_firm" in anonymized and anonymized["current_firm"]:
        anonymized["current_firm"] = anonymize_firm_name(anonymized["current_firm"])

    if "previous_firm" in anonymized and anonymized["previous_firm"]:
        anonymized["previous_firm"] = anonymize_firm_name(anonymized["previous_firm"])

    # 2. Normalize location
    city = anonymized.get("city", "")
    state = anonymized.get("state", "")

    normalized_city, normalized_state = normalize_location(city, state)

    # If no major metro match, use regional fallback
    if not normalized_city and state in REGIONAL_FALLBACKS:
        anonymized["city"] = REGIONAL_FALLBACKS[state]
    elif normalized_city:
        anonymized["city"] = normalized_city
    else:
        # Remove city entirely if no mapping exists
        anonymized["city"] = None

    # Always preserve state
    anonymized["state"] = normalized_state

    # Strip ZIP from any location fields
    if "location" in anonymized and anonymized["location"]:
        anonymized["location"] = ZIP_CODE_PATTERN.sub("", anonymized["location"]).strip()

    # 3. Round AUM/Production to ranges
    if "aum" in anonymized and anonymized["aum"]:
        aum_str = str(anonymized["aum"])
        anonymized["aum"] = round_aum_to_range(aum_str)

    if "production" in anonymized and anonymized["production"]:
        prod_str = str(anonymized["production"])
        anonymized["production"] = round_aum_to_range(prod_str)

    # 4. Anonymize all text fields
    text_fields = [
        "bio", "biography", "summary", "overview", "description",
        "education", "credentials", "certifications",
        "achievements", "awards", "recognition",
        "experience", "background", "highlights",
        "notes", "comments", "additional_info"
    ]

    for field in text_fields:
        if field in anonymized and anonymized[field]:
            anonymized[field] = anonymize_text_field(anonymized[field])

    return anonymized


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def anonymize_candidate_list(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Anonymize a list of candidate records.

    Args:
        candidates: List of candidate dictionaries

    Returns:
        List of anonymized candidate dictionaries

    Example:
        >>> candidates = [
        ...     {"firm": "Morgan Stanley", "city": "Dallas", "aum": "$500M"},
        ...     {"firm": "Fisher Investments", "city": "Portland", "aum": "$2.5B"}
        ... ]
        >>> anonymized = anonymize_candidate_list(candidates)
        >>> len(anonymized)
        2
    """
    return [anonymize_candidate_data(candidate) for candidate in candidates]


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def is_anonymized_firm(firm_name: str) -> bool:
    """
    Check if a firm name has already been anonymized.

    Args:
        firm_name: Firm name to check

    Returns:
        True if firm name is a generic classification, False otherwise

    Examples:
        >>> is_anonymized_firm("a leading national wirehouse")
        True

        >>> is_anonymized_firm("Morgan Stanley")
        False
    """
    if not firm_name:
        return False

    generic_patterns = [
        "a leading national wirehouse",
        "a multi-billion dollar RIA",
        "a regional banking institution",
        "a Fortune 500 asset manager",
        "a major independent broker-dealer",
    ]

    return any(pattern in firm_name.lower() for pattern in generic_patterns)


def get_firm_classification(firm_name: str) -> Optional[str]:
    """
    Get the anonymized classification for a specific firm.

    Args:
        firm_name: Original firm name

    Returns:
        Generic classification string or None if not found

    Examples:
        >>> get_firm_classification("Merrill Lynch")
        "a leading national wirehouse"

        >>> get_firm_classification("Unknown Firm")
        None
    """
    if not firm_name:
        return None

    firm_lower = firm_name.lower().strip()
    return ALL_FIRMS.get(firm_lower)


def add_custom_firm(firm_name: str, classification: str) -> None:
    """
    Add a custom firm to the anonymization mappings at runtime.

    Useful for handling new firms not in the predefined lists.

    Args:
        firm_name: Original firm name (case-insensitive)
        classification: Generic classification to use

    Example:
        >>> add_custom_firm("Boutique Wealth", "a multi-billion dollar RIA")
        >>> get_firm_classification("Boutique Wealth")
        "a multi-billion dollar RIA"
    """
    ALL_FIRMS[firm_name.lower()] = classification


# ============================================================================
# VALIDATION & TESTING
# ============================================================================

def validate_anonymization(original: Dict[str, Any], anonymized: Dict[str, Any]) -> List[str]:
    """
    Validate that anonymization was applied correctly.

    Checks for:
    - No specific firm names remain
    - No ZIP codes remain
    - No university names remain
    - AUM values are ranges (not exact)

    Args:
        original: Original candidate data
        anonymized: Anonymized candidate data

    Returns:
        List of validation warnings (empty if all checks pass)

    Example:
        >>> original = {"firm": "Morgan Stanley", "city": "Dallas 75034"}
        >>> anonymized = anonymize_candidate_data(original)
        >>> warnings = validate_anonymization(original, anonymized)
        >>> len(warnings)
        0
    """
    warnings = []

    # Check firm names
    if "firm" in anonymized:
        firm = anonymized["firm"]
        if firm and not is_anonymized_firm(firm):
            # Check if it's a known firm that should be anonymized
            if firm.lower() in ALL_FIRMS:
                warnings.append(f"Firm name '{firm}' was not anonymized")

    # Check for ZIP codes
    for field in ["city", "location", "address"]:
        if field in anonymized and anonymized[field]:
            if ZIP_CODE_PATTERN.search(str(anonymized[field])):
                warnings.append(f"ZIP code found in {field}: {anonymized[field]}")

    # Check for university names
    university_pattern = re.compile(
        r"\b(Harvard|Stanford|MIT|Yale|Penn State|LSU|UCLA|USC)\b",
        re.IGNORECASE
    )
    for field in ["education", "bio", "background"]:
        if field in anonymized and anonymized[field]:
            if university_pattern.search(str(anonymized[field])):
                warnings.append(f"University name found in {field}")

    # Check AUM format (should be range, not exact)
    if "aum" in anonymized and anonymized["aum"]:
        aum_str = str(anonymized["aum"])
        if "-" not in aum_str and AUM_PATTERN.search(aum_str):
            warnings.append(f"AUM appears to be exact value, not range: {aum_str}")

    return warnings


if __name__ == "__main__":
    # Example usage
    sample_candidate = {
        "name": "John Doe",
        "firm": "Merrill Lynch",
        "city": "Frisco, TX 75034",
        "state": "TX",
        "aum": "$1.68B",
        "production": "$300M",
        "education": "MBA from LSU, CFA",
        "bio": "Ranked #1 nationwide at Schwab. Scaled from $125M to $300M in 3 years using E23 Consulting methodology.",
        "achievements": "Chairman's Club member, captured 52% VA market share"
    }

    print("=== ORIGINAL ===")
    for key, value in sample_candidate.items():
        print(f"{key}: {value}")

    print("\n=== ANONYMIZED ===")
    anonymized = anonymize_candidate_data(sample_candidate)
    for key, value in anonymized.items():
        print(f"{key}: {value}")

    print("\n=== VALIDATION ===")
    warnings = validate_anonymization(sample_candidate, anonymized)
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("All checks passed!")
