"""
Phone Number Validation and Formatting Utilities

This module provides comprehensive phone number validation, formatting,
and normalization utilities with international support.
"""

import re
import logging
from typing import Optional, Dict, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class PhoneType(Enum):
    """Phone number types"""
    MOBILE = "mobile"
    WORK = "work"
    HOME = "home"
    COMPANY_MAIN = "company_main"
    FAX = "fax"
    TOLL_FREE = "toll_free"
    EXECUTIVE = "executive"
    RECRUITER = "recruiter"
    UNKNOWN = "unknown"


class PhoneNumberValidator:
    """Validates and formats phone numbers with international support"""

    # Country codes with their rules
    COUNTRY_RULES = {
        "US": {
            "code": "+1",
            "min_length": 10,
            "max_length": 10,
            "regex": r"^\d{10}$",
            "format": "({area}) {exchange}-{number}",
            "mobile_prefixes": ["201", "202", "203", "205", "206", "207", "208", "209", "210",
                                "212", "213", "214", "215", "216", "217", "218", "219", "224",
                                "225", "228", "229", "231", "234", "239", "240", "248", "251",
                                "252", "253", "254", "256", "260", "262", "267", "269", "270",
                                "276", "281", "301", "302", "303", "304", "305", "307", "308",
                                "309", "310", "312", "313", "314", "315", "316", "317", "318",
                                "319", "320", "321", "323", "325", "330", "331", "334", "336",
                                "337", "339", "347", "351", "352", "360", "361", "364", "385",
                                "386", "401", "402", "404", "405", "406", "407", "408", "409",
                                "410", "412", "413", "414", "415", "417", "419", "423", "424",
                                "425", "430", "432", "434", "435", "440", "442", "443", "445",
                                "447", "458", "469", "470", "475", "478", "479", "480", "484",
                                "501", "502", "503", "504", "505", "507", "508", "509", "510",
                                "512", "513", "515", "516", "517", "518", "520", "530", "531",
                                "534", "539", "540", "541", "551", "559", "561", "562", "563",
                                "564", "567", "570", "571", "573", "574", "575", "580", "585",
                                "586", "601", "602", "603", "605", "606", "607", "608", "609",
                                "610", "612", "614", "615", "616", "617", "618", "619", "620",
                                "623", "626", "628", "629", "630", "631", "636", "641", "646",
                                "650", "651", "657", "659", "660", "661", "662", "667", "669",
                                "678", "681", "682", "701", "702", "703", "704", "706", "707",
                                "708", "712", "713", "714", "715", "716", "717", "718", "719",
                                "720", "724", "725", "727", "731", "732", "734", "737", "740",
                                "743", "747", "754", "757", "760", "762", "763", "764", "765",
                                "769", "770", "772", "773", "774", "775", "779", "781", "785",
                                "786", "801", "802", "803", "804", "805", "806", "808", "810",
                                "812", "813", "814", "815", "816", "817", "818", "828", "830",
                                "831", "832", "843", "845", "847", "848", "850", "856", "857",
                                "858", "859", "860", "862", "863", "864", "865", "870", "872",
                                "878", "901", "903", "904", "906", "907", "908", "909", "910",
                                "912", "913", "914", "915", "916", "917", "918", "919", "920",
                                "925", "928", "929", "930", "931", "936", "937", "938", "940",
                                "941", "947", "949", "951", "952", "954", "956", "959", "970",
                                "971", "972", "973", "975", "978", "979", "980", "984", "985",
                                "989"],
            "toll_free": ["800", "833", "844", "855", "866", "877", "888"]
        },
        "UK": {
            "code": "+44",
            "min_length": 10,
            "max_length": 11,
            "regex": r"^[0-9]{10,11}$",
            "format": "{std} {number}",
            "mobile_prefixes": ["7"]
        },
        "CA": {
            "code": "+1",
            "min_length": 10,
            "max_length": 10,
            "regex": r"^\d{10}$",
            "format": "({area}) {exchange}-{number}",
            "mobile_prefixes": ["204", "226", "236", "249", "250", "289", "306", "343", "365",
                                "403", "416", "418", "431", "437", "438", "450", "506", "514",
                                "519", "548", "579", "581", "587", "604", "613", "639", "647",
                                "672", "705", "709", "778", "780", "782", "807", "819", "825",
                                "867", "873", "902", "905"]
        }
    }

    @classmethod
    def clean_number(cls, phone: str) -> str:
        """
        Remove all non-numeric characters from phone number

        Args:
            phone: Raw phone number string

        Returns:
            Cleaned numeric string
        """
        return re.sub(r'\D', '', phone)

    @classmethod
    def detect_country(cls, phone: str) -> Optional[str]:
        """
        Detect country based on phone number format

        Args:
            phone: Phone number (cleaned or with formatting)

        Returns:
            Country code (US, UK, CA, etc.) or None
        """
        clean = cls.clean_number(phone)

        # Check for explicit country codes
        if phone.startswith('+1') or (len(clean) == 11 and clean[0] == '1'):
            # Could be US or Canada - need to check area code
            area_code = clean[1:4] if len(clean) == 11 else clean[:3]

            # Check Canadian area codes
            if area_code in cls.COUNTRY_RULES["CA"]["mobile_prefixes"]:
                return "CA"
            return "US"

        elif phone.startswith('+44') or (len(clean) > 10 and clean[:2] == '44'):
            return "UK"

        # Default detection based on length
        elif len(clean) == 10:
            # Likely North American
            area_code = clean[:3]
            if area_code in cls.COUNTRY_RULES["CA"]["mobile_prefixes"]:
                return "CA"
            return "US"

        return None

    @classmethod
    def detect_phone_type(cls, phone: str, country: Optional[str] = None) -> PhoneType:
        """
        Detect the type of phone number

        Args:
            phone: Phone number
            country: Country code (for better detection)

        Returns:
            PhoneType enum value
        """
        clean = cls.clean_number(phone)

        if not country:
            country = cls.detect_country(phone)

        if country in ["US", "CA"]:
            area_code = clean[1:4] if len(clean) == 11 else clean[:3]

            # Check for toll-free
            if area_code in cls.COUNTRY_RULES["US"]["toll_free"]:
                return PhoneType.TOLL_FREE

            # Check for mobile (this is a simplified check)
            # In reality, US mobile detection is complex
            if area_code in cls.COUNTRY_RULES.get(country, {}).get("mobile_prefixes", []):
                return PhoneType.MOBILE

        elif country == "UK":
            # UK mobile numbers start with 07
            if len(clean) >= 2 and clean[0] == '0' and clean[1] == '7':
                return PhoneType.MOBILE
            elif len(clean) >= 3 and clean[:2] == '44' and clean[2] == '7':
                return PhoneType.MOBILE

        return PhoneType.UNKNOWN

    @classmethod
    def validate(cls, phone: str, country: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate a phone number

        Args:
            phone: Phone number to validate
            country: Country code (optional)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not phone:
            return False, "Phone number is required"

        clean = cls.clean_number(phone)

        if not clean:
            return False, "Phone number contains no digits"

        if not country:
            country = cls.detect_country(phone)

        if country and country in cls.COUNTRY_RULES:
            rules = cls.COUNTRY_RULES[country]

            # Check length
            if len(clean) < rules["min_length"]:
                return False, f"Phone number too short for {country}"
            if len(clean) > rules["max_length"] and not (len(clean) == rules["max_length"] + 1 and clean[0] in ['1', '0']):
                return False, f"Phone number too long for {country}"

            # Remove country code if present
            if country in ["US", "CA"] and len(clean) == 11 and clean[0] == '1':
                clean = clean[1:]

            # Check regex pattern
            if rules.get("regex"):
                if not re.match(rules["regex"], clean):
                    return False, f"Invalid phone number format for {country}"

            return True, None

        # Generic validation for unknown countries
        if len(clean) < 7:
            return False, "Phone number too short"
        if len(clean) > 15:
            return False, "Phone number too long"

        return True, None

    @classmethod
    def format(cls, phone: str, country: Optional[str] = None, international: bool = False) -> Dict[str, str]:
        """
        Format a phone number in various styles

        Args:
            phone: Phone number to format
            country: Country code (optional)
            international: Whether to include country code

        Returns:
            Dictionary with different formats
        """
        clean = cls.clean_number(phone)

        if not clean:
            return {"original": phone, "error": "No digits found"}

        if not country:
            country = cls.detect_country(phone)

        formats = {
            "original": phone,
            "cleaned": clean,
            "country": country
        }

        if country == "US" or country == "CA":
            # Handle country code
            if len(clean) == 11 and clean[0] == '1':
                clean = clean[1:]
            elif len(clean) != 10:
                formats["error"] = "Invalid length for North American number"
                return formats

            area = clean[:3]
            exchange = clean[3:6]
            number = clean[6:]

            formats["national"] = f"({area}) {exchange}-{number}"
            formats["international"] = f"+1 {area} {exchange} {number}"
            formats["e164"] = f"+1{clean}"
            formats["rfc3966"] = f"tel:+1-{area}-{exchange}-{number}"

        elif country == "UK":
            # UK formatting is complex, this is simplified
            if len(clean) == 11 and clean[0] == '0':
                # National format
                formats["national"] = f"{clean[:4]} {clean[4:7]} {clean[7:]}"
                formats["international"] = f"+44 {clean[1:4]} {clean[4:7]} {clean[7:]}"
                formats["e164"] = f"+44{clean[1:]}"
            else:
                formats["national"] = phone
                formats["international"] = f"+44 {clean}" if not phone.startswith('+') else phone

        else:
            # Generic formatting
            formats["national"] = phone
            formats["international"] = f"+{clean}" if not phone.startswith('+') else phone
            formats["e164"] = f"+{clean}" if not phone.startswith('+') else phone.replace(' ', '').replace('-', '')

        return formats

    @classmethod
    def normalize(cls, phone: str, target_format: str = "e164") -> Optional[str]:
        """
        Normalize phone number to a standard format

        Args:
            phone: Phone number to normalize
            target_format: Target format (e164, national, international)

        Returns:
            Normalized phone number or None if invalid
        """
        is_valid, error = cls.validate(phone)

        if not is_valid:
            logger.warning(f"Invalid phone number: {phone} - {error}")
            return None

        formatted = cls.format(phone)

        return formatted.get(target_format, formatted.get("cleaned"))


class PhoneExtractor:
    """Extract phone numbers from text with context"""

    # Patterns for phone number extraction
    PHONE_PATTERNS = [
        # US/CA formats
        r'\b(?:\+?1[-.\s]?)?\(?([2-9]\d{2})\)?[-.\s]?([2-9]\d{2})[-.\s]?(\d{4})\b',
        # International format
        r'\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{0,4}',
        # Generic format
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        # With extensions
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\s*(?:ext|x|extension)\.?\s*\d{1,5}\b',
    ]

    # Context keywords for phone type detection
    TYPE_KEYWORDS = {
        PhoneType.MOBILE: ["mobile", "cell", "cellular", "smartphone", "text", "sms", "whatsapp"],
        PhoneType.WORK: ["work", "office", "business", "desk", "direct", "extension", "ext"],
        PhoneType.HOME: ["home", "house", "residence", "personal"],
        PhoneType.FAX: ["fax", "facsimile"],
        PhoneType.COMPANY_MAIN: ["main", "general", "reception", "front desk", "company", "corporate"],
        PhoneType.EXECUTIVE: ["ceo", "president", "director", "vp", "executive", "chief"],
        PhoneType.RECRUITER: ["recruiter", "hr", "human resources", "talent", "hiring"]
    }

    @classmethod
    def extract_from_text(cls, text: str, include_context: bool = True) -> List[Dict[str, any]]:
        """
        Extract phone numbers from text with context

        Args:
            text: Text to extract phone numbers from
            include_context: Whether to include surrounding context

        Returns:
            List of extracted phone numbers with metadata
        """
        results = []
        text_lower = text.lower()

        for pattern in cls.PHONE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                phone = match.group(0)

                # Get context around the match
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end] if include_context else ""
                context_lower = context.lower()

                # Detect phone type from context
                detected_type = PhoneType.UNKNOWN
                for phone_type, keywords in cls.TYPE_KEYWORDS.items():
                    if any(keyword in context_lower for keyword in keywords):
                        detected_type = phone_type
                        break

                # Validate and format
                validator = PhoneNumberValidator()
                is_valid, error = validator.validate(phone)

                if is_valid:
                    formatted = validator.format(phone)

                    results.append({
                        "original": phone,
                        "formatted": formatted.get("national"),
                        "international": formatted.get("international"),
                        "e164": formatted.get("e164"),
                        "type": detected_type.value,
                        "position": match.start(),
                        "context": context.strip() if include_context else None,
                        "confidence": 0.9 if detected_type != PhoneType.UNKNOWN else 0.7
                    })
                else:
                    logger.debug(f"Invalid phone number found: {phone} - {error}")

        # Deduplicate by cleaned number
        seen = set()
        unique_results = []
        for result in results:
            clean = PhoneNumberValidator.clean_number(result["original"])
            if clean not in seen:
                seen.add(clean)
                unique_results.append(result)

        return unique_results

    @classmethod
    def extract_from_email_signature(cls, email_body: str) -> List[Dict[str, any]]:
        """
        Extract phone numbers specifically from email signatures

        Args:
            email_body: Email body text

        Returns:
            List of phone numbers found in signature
        """
        # Common signature markers
        signature_markers = [
            "regards", "sincerely", "best", "thanks", "thank you",
            "sent from", "---", "___", "***", "cheers", "respectfully"
        ]

        # Find potential signature start
        lines = email_body.split('\n')
        signature_start = len(lines)

        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if any(marker in line_lower for marker in signature_markers):
                signature_start = i
                break

        # Extract from signature portion
        signature_text = '\n'.join(lines[signature_start:])

        return cls.extract_from_text(signature_text, include_context=True)