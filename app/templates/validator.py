"""
HTML validation for TalentWell digest emails.
Ensures templates follow Brandon's formatting rules and locked structure.
"""

import re
import logging
from typing import Tuple, List
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


def validate_digest_html(html: str) -> Tuple[bool, List[str]]:
    """
    Validate that the digest HTML follows required structure and formatting rules.
    
    Args:
        html: Complete HTML string to validate
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Basic HTML structure checks
    if not html or len(html) < 100:
        errors.append("HTML content is empty or too short")
        return False, errors
    
    # Check for required HTML elements
    required_elements = [
        ('<!DOCTYPE html>', 'Missing DOCTYPE declaration'),
        ('<html', 'Missing html tag'),
        ('<head>', 'Missing head section'),
        ('<body>', 'Missing body section'),
        ('</html>', 'Missing closing html tag')
    ]
    
    html_lower = html.lower()
    for element, error_msg in required_elements:
        if element.lower() not in html_lower:
            errors.append(error_msg)
    
    # Check for TalentWell branding elements
    branding_checks = [
        ('TalentWell', 'Missing TalentWell branding'),
        ('candidate', 'Missing candidate-related content')
    ]
    
    for brand_text, error_msg in branding_checks:
        if brand_text.lower() not in html_lower:
            errors.append(error_msg)
    
    # Check for required template sections using AST if available
    try:
        from app.templates.ast import ASTCompiler, NodeType
        
        compiler = ASTCompiler()
        ast = compiler.parse_template(html)
        
        # Validate template structure
        structure_errors = compiler.validate_template_structure()
        errors.extend(structure_errors)
        
        # Check for locked sections integrity
        if not _validate_locked_sections(html):
            errors.append("Locked template sections have been modified")
            
    except ImportError:
        logger.warning("AST compiler not available, using basic validation")
        # Fallback to regex-based validation
        errors.extend(_basic_structure_validation(html))
    except Exception as e:
        logger.error(f"Error during AST validation: {e}")
        errors.append(f"Template structure validation error: {str(e)}")
    
    # Check Brandon's specific formatting rules
    formatting_errors = _validate_formatting_rules(html)
    errors.extend(formatting_errors)
    
    # Check for Calendly widget (required)
    if 'calendly' not in html_lower:
        errors.append("Missing Calendly scheduling widget")
    
    # Check for footer compliance
    footer_errors = _validate_footer(html)
    errors.extend(footer_errors)
    
    # Check for internal note if expected
    if 'internal-note' not in html_lower and 'Internal Recipients:' not in html:
        logger.warning("Missing internal note section (may be intentional for single candidate)")
    
    # Determine overall validity
    is_valid = len(errors) == 0
    
    if not is_valid:
        logger.error(f"HTML validation failed with {len(errors)} errors")
        for error in errors:
            logger.error(f"  - {error}")
    
    return is_valid, errors


def _validate_locked_sections(html: str) -> bool:
    """
    Validate that locked (non-modifiable) sections haven't been altered.
    """
    # Check for required static elements that should never change
    required_static = [
        r'<div[^>]*class="header"[^>]*>',  # Header must exist
        r'<div[^>]*class="footer"[^>]*>',  # Footer must exist
        r'© \d{4} TalentWell',  # Copyright notice
        r'Confidential',  # Confidentiality notice
    ]
    
    for pattern in required_static:
        if not re.search(pattern, html, re.IGNORECASE):
            logger.error(f"Missing required static element: {pattern}")
            return False
    
    return True


def _basic_structure_validation(html: str) -> List[str]:
    """
    Basic structure validation when AST compiler is not available.
    """
    errors = []
    
    # Check for main container structure
    if '<div class="container"' not in html:
        errors.append("Missing main container div")
    
    # Check for header section
    if not re.search(r'<div[^>]*class="header"[^>]*>', html):
        errors.append("Missing header section")
    
    # Check for cards container
    if not re.search(r'<div[^>]*class="cards-container"[^>]*>', html) and \
       not re.search(r'<div[^>]*data-ast="cards"[^>]*>', html):
        errors.append("Missing cards container section")
    
    # Check for footer
    if not re.search(r'<div[^>]*class="footer"[^>]*>', html):
        errors.append("Missing footer section")
    
    return errors


def _validate_formatting_rules(html: str) -> List[str]:
    """
    Validate Brandon's specific formatting rules.
    """
    errors = []
    
    # Rule 1: Candidate names must be bold in headers
    candidate_headers = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL)
    for header in candidate_headers:
        if '<strong>' not in header and '<b>' not in header:
            errors.append("Candidate names in headers must be bold")
            break
    
    # Rule 2: Location must have "Location:" label
    if 'candidate-location' in html:
        location_sections = re.findall(r'<div[^>]*class="candidate-location"[^>]*>(.*?)</div>', html, re.DOTALL)
        for section in location_sections:
            if 'Location:' not in section and '<strong>Location:</strong>' not in section:
                errors.append("Location sections must have 'Location:' label")
                break
    
    # Rule 3: Reference codes should be present for candidates
    if 'candidate-card' in html:
        card_count = html.count('candidate-card')
        ref_count = html.count('REF-')
        if ref_count == 0 and card_count > 0:
            errors.append("Candidate cards should have reference codes")
        # Allow some flexibility - not every card needs a ref code for single candidate emails
    
    # Rule 4: Skills should be in list format
    if 'skill-list' in html:
        skill_sections = re.findall(r'<div[^>]*class="skill-list"[^>]*>(.*?)</div>', html, re.DOTALL)
        for section in skill_sections:
            if '<ul>' not in section and '<li>' not in section:
                # Check if it's a simple field instead of a list
                if 'detail-label' not in section:
                    errors.append("Skills should be formatted as lists or labeled fields")
                    break
    
    return errors


def _validate_footer(html: str) -> List[str]:
    """
    Validate footer compliance and required links.
    """
    errors = []
    
    # Extract footer content
    footer_match = re.search(r'<div[^>]*class="footer"[^>]*>(.*?)</div>\s*</div>\s*</body>', html, re.DOTALL | re.IGNORECASE)
    
    if not footer_match:
        errors.append("Footer section not properly structured")
        return errors
    
    footer_content = footer_match.group(1)
    
    # Check for required footer elements
    required_footer_elements = [
        ('TalentWell', 'Footer missing TalentWell branding'),
        ('Confidential', 'Footer missing confidentiality notice'),
        ('Privacy', 'Footer missing privacy policy link')
    ]
    
    for element, error_msg in required_footer_elements:
        if element.lower() not in footer_content.lower():
            errors.append(error_msg)
    
    return errors


def validate_single_candidate_card(card_html: str) -> Tuple[bool, List[str]]:
    """
    Validate a single candidate card HTML fragment.
    
    Args:
        card_html: HTML string for a single candidate card
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Check basic structure
    if not card_html or len(card_html) < 50:
        errors.append("Card HTML is empty or too short")
        return False, errors
    
    # Check for candidate-card class
    if 'candidate-card' not in card_html:
        errors.append("Card missing 'candidate-card' class")
    
    # Check for required fields
    required_fields = [
        ('candidate name', r'<h3[^>]*>.*?<strong>.*?</strong>.*?</h3>|<h3[^>]*><strong>.*?</strong></h3>'),
        ('location', r'Location:|<strong>Location:</strong>'),
        ('reference code', r'REF-[A-Z0-9\-]+')
    ]
    
    for field_name, pattern in required_fields:
        if not re.search(pattern, card_html, re.IGNORECASE | re.DOTALL):
            errors.append(f"Card missing {field_name}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def validate_email_addresses(addresses: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate email addresses for sending.
    
    Args:
        addresses: List of email addresses to validate
        
    Returns:
        Tuple of (all_valid, list_of_invalid_addresses)
    """
    invalid = []
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    for addr in addresses:
        if not email_pattern.match(addr):
            invalid.append(addr)
    
    return len(invalid) == 0, invalid