"""
Enhanced parsing utilities for Teams Bot NLP interactions.
Handles flexible user input patterns for clarifications and references.
"""
import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def parse_clarification_response(
    user_input: str,
    options: List[Dict[str, str]]
) -> Optional[Dict[str, str]]:
    """
    Parse user's clarification response with flexible matching.

    Supports multiple formats:
    - Numbers: "1", "2", "3"
    - Hash notation: "#1", "#2", "option #3"
    - Words: "first", "second", "third", "last"
    - Partial text matches: "name" matches "Search by Name"
    - Full text: exact option title match

    Args:
        user_input: User's response text
        options: List of {"title": str, "value": str} options

    Returns:
        Matched option dict or None if no match

    Examples:
        >>> options = [{"title": "Search by Name", "value": "search_name"}]
        >>> parse_clarification_response("1", options)
        {"title": "Search by Name", "value": "search_name"}
        >>> parse_clarification_response("#1", options)
        {"title": "Search by Name", "value": "search_name"}
        >>> parse_clarification_response("first", options)
        {"title": "Search by Name", "value": "search_name"}
        >>> parse_clarification_response("name", options)
        {"title": "Search by Name", "value": "search_name"}
    """
    if not user_input or not options:
        return None

    # Clean and normalize input
    cleaned_input = user_input.strip().lower()

    # Pattern 2: Hash notation (#1, #2, option #3, etc.) - Check this first
    hash_match = re.search(r'#(\d+)', cleaned_input)
    if hash_match:
        index = int(hash_match.group(1)) - 1
        if 0 <= index < len(options):
            logger.info(f"Matched option by hash notation: #{index + 1}")
            return options[index]

    # Pattern 1: Direct number (1, 2, 3, etc.) - also check for numbers within text
    number_match = re.search(r'\b(\d+)\b', cleaned_input)
    if number_match:
        index = int(number_match.group(1)) - 1
        if 0 <= index < len(options):
            logger.info(f"Matched option by number: {index + 1}")
            return options[index]

    # Pattern 3: Word numbers (first, second, third, etc.)
    word_numbers = {
        'first': 0, '1st': 0,
        'second': 1, '2nd': 1,
        'third': 2, '3rd': 2,
        'fourth': 3, '4th': 3,
        'fifth': 4, '5th': 4,
        'sixth': 5, '6th': 5,
        'seventh': 6, '7th': 6,
        'eighth': 7, '8th': 7,
        'ninth': 8, '9th': 8,
        'tenth': 9, '10th': 9,
        'last': len(options) - 1
    }

    for word, index in word_numbers.items():
        if word in cleaned_input and 0 <= index < len(options):
            logger.info(f"Matched option by word number: {word}")
            return options[index]

    # Pattern 4: Fuzzy text matching on titles
    best_match = None
    best_score = 0.0
    threshold = 0.6  # Minimum similarity score

    for option in options:
        title_lower = option['title'].lower()

        # Check for exact substring match first
        if cleaned_input in title_lower or title_lower in cleaned_input:
            logger.info(f"Matched option by substring: {option['title']}")
            return option

        # Calculate similarity score
        score = SequenceMatcher(None, cleaned_input, title_lower).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_match = option

    if best_match:
        logger.info(f"Matched option by fuzzy match (score: {best_score:.2f}): {best_match['title']}")
        return best_match

    # Pattern 5: Check if user typed one of the values directly
    for option in options:
        if cleaned_input == option['value'].lower():
            logger.info(f"Matched option by value: {option['value']}")
            return option

    logger.warning(f"No match found for user input: {user_input}")
    return None


def extract_candidate_reference(text: str) -> Optional[Tuple[str, int]]:
    """
    Extract candidate references from conversational text.

    Patterns supported:
    - "tell me more about #1"
    - "what about candidate 2"
    - "show me the third one"
    - "details on the first candidate"
    - "more info on #5"

    Args:
        text: User's message text

    Returns:
        Tuple of (action, index) or None
        Action can be: "details", "more", "expand", etc.

    Examples:
        >>> extract_candidate_reference("tell me more about #1")
        ("more", 1)
        >>> extract_candidate_reference("show details for candidate 3")
        ("details", 3)
    """
    cleaned = text.strip().lower()

    # Patterns for extracting references
    patterns = [
        # Hash notation patterns
        (r'(?:tell me |show |get |give me )?(?:more|details|info|information)(?: about| on| for)? #(\d+)', 'details'),
        (r'#(\d+)(?: ?-? ?(?:more|details|info|information))?', 'details'),

        # Number patterns
        (r'(?:candidate|option|result|number) (\d+)', 'details'),
        (r'(?:the )?(\d+)(?:st|nd|rd|th) (?:one|candidate|option|result)', 'details'),

        # Word number patterns - treat "what about" specially
        (r'(?:what|how) about (?:the )?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth) (?:one|candidate|option|result)', 'more'),
        (r'(?:the )?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth) (?:one|candidate|option|result)', 'details'),

        # "More about" patterns
        (r'(?:tell me |show |get )?more about (?:the )?(\d+)(?:st|nd|rd|th)?', 'more'),
        (r'(?:what|how) about (?:the )?(\d+)(?:st|nd|rd|th)?', 'more'),

        # Expansion patterns
        (r'expand(?: on)? (\d+)', 'expand'),
        (r'drill down(?: on)? (\d+)', 'expand'),
    ]

    for pattern, action in patterns:
        match = re.search(pattern, cleaned)
        if match:
            ref = match.group(1)

            # Convert word numbers to integers
            word_to_num = {
                'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
                'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10
            }

            if ref in word_to_num:
                index = word_to_num[ref]
            else:
                try:
                    index = int(ref)
                except ValueError:
                    continue

            logger.info(f"Extracted reference: action={action}, index={index}")
            return (action, index)

    return None


def parse_refinement_input(text: str) -> Dict[str, Any]:
    """
    Parse user's query refinement input.

    Extracts:
    - Time ranges
    - Entity names
    - Locations
    - Amounts/values
    - Action keywords

    Args:
        text: User's refinement text

    Returns:
        Dictionary with parsed elements
    """
    parsed = {
        "original_text": text,
        "time_range": None,
        "entities": [],
        "locations": [],
        "amounts": [],
        "keywords": [],
        "action": None
    }

    cleaned = text.strip().lower()

    # Extract time ranges
    time_patterns = [
        (r'\b(today|yesterday|tomorrow)\b', 'relative'),
        (r'\b(this|last|next) (week|month|quarter|year)\b', 'period'),
        (r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', 'month'),
        (r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b', 'date'),
        (r'\b(q[1-4])\b', 'quarter'),
    ]

    for pattern, time_type in time_patterns:
        match = re.search(pattern, cleaned)
        if match:
            parsed["time_range"] = {
                "type": time_type,
                "value": match.group(0)
            }
            break

    # Extract amounts/values (currency, percentages, numbers) - Use original text for case
    amount_patterns = [
        r'\$[\d,]+(?:\.\d{2})?[kKmMbB]?',  # Currency
        r'\d+(?:\.\d+)?%',  # Percentages
        r'\b\d+(?:,\d{3})*(?:\.\d+)?[kKmMbB]?\b',  # Numbers with units
    ]

    for pattern in amount_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)  # Use original text
        if matches:
            parsed["amounts"].extend(matches)

    # Extract quoted entities
    quoted_pattern = r'"([^"]+)"'
    quoted_matches = re.findall(quoted_pattern, text)  # Use original text to preserve case
    if quoted_matches:
        parsed["entities"].extend(quoted_matches)

    # Extract location patterns (common US cities/states)
    location_patterns = [
        r'\b(new york|los angeles|chicago|houston|philadelphia|phoenix|san antonio|san diego|dallas|san jose)\b',
        r'\b(ny|ca|tx|fl|il|pa|oh|ga|nc|mi|nj|va|wa|az|ma|in|tn|mo|md|wi)\b',
    ]

    for pattern in location_patterns:
        matches = re.findall(pattern, cleaned)
        if matches:
            parsed["locations"].extend(matches)

    # Extract action keywords
    action_keywords = {
        'search': ['search', 'find', 'look for', 'locate', 'query'],
        'show': ['show', 'display', 'list', 'view', 'present'],
        'get': ['get', 'fetch', 'retrieve', 'pull', 'obtain'],
        'filter': ['filter', 'narrow', 'refine', 'limit', 'restrict'],
        'sort': ['sort', 'order', 'arrange', 'rank'],
        'compare': ['compare', 'contrast', 'versus', 'vs', 'against'],
        'analyze': ['analyze', 'examine', 'review', 'assess', 'evaluate']
    }

    for action, keywords in action_keywords.items():
        for keyword in keywords:
            if keyword in cleaned:
                parsed["action"] = action
                parsed["keywords"].append(keyword)
                break
        if parsed["action"]:
            break

    return parsed


def extract_conversation_context(text: str, previous_messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Extract context from conversation history for better understanding.

    Args:
        text: Current user message
        previous_messages: List of previous messages with role and content

    Returns:
        Context dictionary with relevant information
    """
    context = {
        "refers_to_previous": False,
        "pronouns_requiring_context": [],
        "continuing_thought": False,
        "topic_shift": False,
        "referenced_items": []
    }

    cleaned = text.strip().lower()

    # Check for references to previous messages - check 'those' separately
    if re.search(r'\b(that|those|it|them|this|these)\b', cleaned):
        context["refers_to_previous"] = True
        # Also extract these as requiring context
        demonstratives = re.findall(r'\b(that|those|it|them|this|these)\b', cleaned)
        if demonstratives:
            context["pronouns_requiring_context"].extend(list(set(demonstratives)))

    # Check other reference patterns
    reference_patterns = [
        r'\b(the same|similar|like that|such)\b',
        r'\b(as mentioned|as discussed|as i said|like before)\b',
        r'\b(above|previous|earlier|before)\b',
    ]

    for pattern in reference_patterns:
        if re.search(pattern, cleaned):
            context["refers_to_previous"] = True
            break

    # Extract other pronouns that need context resolution (excluding already captured ones)
    other_pronouns = re.findall(r'\b(he|she|they|his|her|their|its)\b', cleaned)
    if other_pronouns:
        context["pronouns_requiring_context"].extend(list(set(other_pronouns)))
        # Remove duplicates from the final list
        context["pronouns_requiring_context"] = list(set(context["pronouns_requiring_context"]))

    # Check if continuing a thought (starts with conjunctions)
    continuing_patterns = r'^(and |but |or |also |additionally |furthermore |moreover |however )'
    if re.match(continuing_patterns, cleaned):
        context["continuing_thought"] = True

    # Detect potential topic shifts
    if previous_messages:
        last_message = previous_messages[-1].get('content', '').lower()
        # Simple topic shift detection based on keyword overlap
        last_words = set(re.findall(r'\b\w+\b', last_message))
        current_words = set(re.findall(r'\b\w+\b', cleaned))
        overlap = last_words.intersection(current_words)

        # If very little overlap, might be topic shift
        if len(overlap) < 2 and len(current_words) > 3:
            context["topic_shift"] = True

    # Extract referenced items (numbers, ids, names in context)
    item_patterns = [
        r'\b#(\d+)\b',  # Hash references
        r'\bitem (\d+)\b',  # Item numbers
        r'\boption (\d+)\b',  # Option numbers
        r'\bcandidate (\d+)\b',  # Candidate numbers
    ]

    for pattern in item_patterns:
        matches = re.findall(pattern, cleaned)
        if matches:
            context["referenced_items"].extend(matches)

    return context


def validate_and_sanitize_input(text: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validate and sanitize user input for safety and processing.

    Args:
        text: Raw user input

    Returns:
        Tuple of (is_valid, sanitized_text, error_message)
    """
    if not text or not text.strip():
        return False, "", "Input cannot be empty"

    # Remove excessive whitespace
    sanitized = ' '.join(text.split())

    # Check length limits
    if len(sanitized) > 1000:
        return False, "", "Input is too long (max 1000 characters)"

    # Remove potential injection attempts (very basic)
    injection_patterns = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript protocol
        r'on\w+\s*=',  # Event handlers
        r'<iframe[^>]*>',  # Iframes
    ]

    for pattern in injection_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            logger.warning(f"Potential injection attempt detected: {pattern}")
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)

    # Remove unusual Unicode characters but keep emojis and common symbols
    # This regex keeps: letters, numbers, common punctuation, spaces, and emojis
    sanitized = re.sub(r'[^\w\s\-.,!?@#$%&*()+=\[\]{}/\\:;"\'`~|<>€£¥₹\u00A0-\u00FF\u2000-\u206F\u2600-\u26FF\u2700-\u27BF]', '', sanitized)

    # Final validation
    if not sanitized.strip():
        return False, "", "Input contains no valid content after sanitization"

    return True, sanitized.strip(), None


def detect_query_intent(text: str) -> Dict[str, Any]:
    """
    Quick intent detection for routing queries appropriately.

    Args:
        text: User's query text

    Returns:
        Dictionary with detected intent and confidence
    """
    cleaned = text.strip().lower()

    # Define intent patterns with keywords
    intent_patterns = {
        "greeting": {
            "patterns": [r'\b(hi|hello|hey|good morning|good afternoon|good evening)\b'],
            "confidence": 0.95
        },
        "help": {
            "patterns": [r'\b(help|how do i|how can i|what can you|capabilities|commands)\b'],
            "confidence": 0.9
        },
        "analytics": {
            "patterns": [r'\b(analytics|metrics|statistics|performance|report|dashboard)\b'],
            "confidence": 0.9  # Higher priority for specific analytics keywords
        },
        "search": {
            "patterns": [r'\b(search|find|look for|locate|show me|get me|list)\b'],
            "confidence": 0.85
        },
        "filter": {
            "patterns": [r'\b(filter|only|just|exclude|include|with|without)\b'],
            "confidence": 0.8
        },
        "sort": {
            "patterns": [r'\b(sort|order by|rank|top|bottom|highest|lowest|most|least)\b'],
            "confidence": 0.85
        },
        "compare": {
            "patterns": [r'\b(compare|versus|vs|difference between|better|worse)\b'],
            "confidence": 0.85
        },
        "update": {
            "patterns": [r'\b(update|change|modify|edit|set|configure)\b'],
            "confidence": 0.8
        },
        "delete": {
            "patterns": [r'\b(delete|remove|cancel|clear|reset)\b'],
            "confidence": 0.85
        },
        "confirm": {
            "patterns": [r'\b(yes|no|confirm|cancel|approve|reject|ok|okay|sure|nope)\b'],
            "confidence": 0.95
        }
    }

    detected_intents = []

    for intent_name, config in intent_patterns.items():
        for pattern in config["patterns"]:
            if re.search(pattern, cleaned):
                detected_intents.append({
                    "intent": intent_name,
                    "confidence": config["confidence"]
                })
                break

    # Return the highest confidence intent or unknown
    if detected_intents:
        detected_intents.sort(key=lambda x: x["confidence"], reverse=True)
        return detected_intents[0]

    return {"intent": "unknown", "confidence": 0.3}