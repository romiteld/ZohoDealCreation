"""
Enhanced extraction module for improving email extraction results
"""

import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def enhance_extraction_result(extraction_result: Dict[str, Any], email_content: str) -> Dict[str, Any]:
    """
    Enhance extraction results with additional pattern matching and validation

    Args:
        extraction_result: Initial extraction result from LangGraph
        email_content: Original email content for additional parsing

    Returns:
        Enhanced extraction result dictionary
    """
    try:
        enhanced = extraction_result.copy()

        # Clean and validate email field
        if enhanced.get('email'):
            email = enhanced['email']
            # Extract just the email if it contains extra content
            if 'Invitee Email:' in email:
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email.split('Invitee Email:')[1])
                if email_match:
                    enhanced['email'] = email_match.group(0)
            elif len(email) > 100:  # Likely contains extra content
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email)
                if email_match:
                    enhanced['email'] = email_match.group(0)

        # Clean and validate phone field
        if enhanced.get('phone'):
            phone = enhanced['phone']
            # Extract just the phone number if it contains extra content
            if 'Phone' in phone:
                phone_match = re.search(r'[\+\d\s\-\(\)\.]+', phone.split('Phone')[1])
                if phone_match:
                    phone_num = phone_match.group(0).strip()
                    # Ensure it has at least 10 digits
                    digits = re.sub(r'\D', '', phone_num)
                    if len(digits) >= 10:
                        enhanced['phone'] = phone_num[:30]
            elif len(phone) > 30:  # Likely contains extra content
                phone_match = re.search(r'[\+\d\s\-\(\)\.]+', phone)
                if phone_match:
                    phone_num = phone_match.group(0).strip()
                    digits = re.sub(r'\D', '', phone_num)
                    if len(digits) >= 10:
                        enhanced['phone'] = phone_num[:30]

        # Extract recruiting goals if not in notes
        if not enhanced.get('notes') or 'recruiting' not in enhanced.get('notes', '').lower():
            goals_pattern = r'What recruiting goals[^?]*\?\s*([^\n]+(?:\n[^\n]+)?)'
            goals_match = re.search(goals_pattern, email_content, re.IGNORECASE)
            if goals_match:
                recruiting_goals = goals_match.group(1).strip()
                recruiting_goals = recruiting_goals.replace('Your confirmation email', '').strip()
                if recruiting_goals:
                    if enhanced.get('notes'):
                        enhanced['notes'] = f"{enhanced['notes']}. Recruiting goals: {recruiting_goals[:200]}"
                    else:
                        enhanced['notes'] = f"Recruiting goals: {recruiting_goals[:200]}"

        # Extract LinkedIn URL if present
        if not enhanced.get('linkedin_url'):
            linkedin_match = re.search(r'linkedin\.com/in/[\w-]+', email_content)
            if linkedin_match:
                enhanced['linkedin_url'] = f"https://{linkedin_match.group(0)}"

        # Extract company from email domain if not present
        if not enhanced.get('company_name') and enhanced.get('email'):
            email = enhanced['email']
            if '@' in email:
                domain = email.split('@')[1]
                # Skip generic email domains
                generic_domains = [
                    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                    'aol.com', 'icloud.com', 'me.com', 'mac.com'
                ]
                if domain not in generic_domains:
                    # Extract company name from domain
                    company = domain.split('.')[0].replace('-', ' ').title()
                    enhanced['company_name'] = company

        # Clean candidate_name field
        if enhanced.get('candidate_name'):
            name = enhanced['candidate_name']
            # Remove "Invitee:" prefix if present
            if name.startswith('Invitee:'):
                name = name.replace('Invitee:', '').strip()
            # Remove everything after "Invitee Email:" if present
            if 'Invitee Email:' in name:
                name = name.split('Invitee Email:')[0].strip()
            # Remove everything after first newline
            if '\n' in name:
                name = name.split('\n')[0].strip()
            enhanced['candidate_name'] = name[:100]  # Limit length

        # Add extraction metadata
        enhanced['extraction_enhanced'] = True
        enhanced['enhancement_timestamp'] = datetime.utcnow().isoformat()

        logger.info(f"Enhanced extraction result: {enhanced}")
        return enhanced

    except Exception as e:
        logger.error(f"Error enhancing extraction result: {e}")
        return extraction_result  # Return original if enhancement fails


def validate_extraction(extraction_result: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate extraction results for completeness and correctness

    Args:
        extraction_result: Extraction result to validate

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    # Check for required fields
    if not extraction_result.get('email'):
        issues.append("Missing email address")
    elif '@' not in extraction_result.get('email', ''):
        issues.append("Invalid email format")
    elif len(extraction_result.get('email', '')) > 100:
        issues.append("Email field contains too much content")

    if not extraction_result.get('candidate_name'):
        issues.append("Missing candidate name")
    elif len(extraction_result.get('candidate_name', '')) > 100:
        issues.append("Candidate name too long (likely contains extra content)")

    # Check for field contamination
    if extraction_result.get('email') and 'Event Date/Time' in extraction_result.get('email', ''):
        issues.append("Email field contains event information")

    if extraction_result.get('phone'):
        phone = extraction_result.get('phone', '')
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 10:
            issues.append("Phone number has fewer than 10 digits")
        elif len(phone) > 30:
            issues.append("Phone field contains too much content")

    is_valid = len(issues) == 0
    return is_valid, issues


def extract_calendly_specific_fields(email_content: str) -> Dict[str, Any]:
    """
    Extract Calendly-specific fields from email content

    Args:
        email_content: Email content to parse

    Returns:
        Dictionary of extracted Calendly fields
    """
    calendly_data = {}

    # Extract invitee name
    invitee_match = re.search(r'Invitee:\s*([^\n]+)', email_content)
    if invitee_match:
        name = invitee_match.group(1).strip()
        if 'Invitee Email:' not in name:  # Ensure we don't include the email part
            calendly_data['invitee_name'] = name

    # Extract invitee email
    invitee_email_match = re.search(r'Invitee Email:\s*([^\n]+)', email_content)
    if invitee_email_match:
        email_text = invitee_email_match.group(1).strip()
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_text)
        if email_match:
            calendly_data['invitee_email'] = email_match.group(0)

    # Extract event date/time
    event_match = re.search(r'Event Date/Time:\s*([^\n]+)', email_content)
    if event_match:
        calendly_data['event_datetime'] = event_match.group(1).strip()

    # Extract meeting location/URL
    zoom_match = re.search(r'(https://[^\s]+zoom[^\s]+)', email_content)
    if zoom_match:
        calendly_data['meeting_url'] = zoom_match.group(1)

    # Extract meeting ID
    meeting_id_match = re.search(r'Meeting ID:\s*([\d\-\s]+)', email_content)
    if meeting_id_match:
        calendly_data['meeting_id'] = meeting_id_match.group(1).strip()

    # Extract phone number
    phone_match = re.search(r'Phone\s*[:\s]*([\+\d\s\-\(\)\.]+)', email_content)
    if phone_match:
        phone = phone_match.group(1).strip()
        digits = re.sub(r'\D', '', phone)
        if len(digits) >= 10:
            calendly_data['phone'] = phone[:30]

    # Extract recruiting goals
    goals_match = re.search(r'What recruiting goals[^?]*\?\s*([^\n]+(?:\n[^\n]+)?)', email_content, re.IGNORECASE)
    if goals_match:
        goals = goals_match.group(1).strip()
        goals = goals.replace('Your confirmation email', '').strip()
        if goals:
            calendly_data['recruiting_goals'] = goals[:500]

    return calendly_data