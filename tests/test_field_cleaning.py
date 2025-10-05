#!/usr/bin/env python3
"""Unit test for field cleaning logic without API calls"""

import re
import json

def clean_field(value, field_name=None, max_length=100):
    """Clean and truncate field values to prevent entire email content"""
    if not value or value == "Unknown" or value == "null" or value == "None":
        return None

    # Convert to string and strip
    value = str(value).strip()

    # Special handling for specific fields
    if field_name == 'job_title':
        # Common patterns in job titles from Calendly
        if 'Recruiting Consult' in value:
            return 'Recruiting Consultant'
        # Remove everything after first newline
        if '\n' in value:
            value = value.split('\n')[0].strip()
        # Remove "Invitee:" prefix if present
        if 'Invitee:' in value:
            value = value.split('Invitee:')[0].strip()

    elif field_name == 'candidate_name':
        # Extract just the name, not "Roy Janse Invitee Email: ..."
        if 'Invitee Email:' in value:
            value = value.split('Invitee Email:')[0].strip()
        # Remove everything after first newline
        if '\n' in value:
            value = value.split('\n')[0].strip()
        # Clean up "Invitee:" prefix
        if value.startswith('Invitee:'):
            value = value.replace('Invitee:', '').strip()

    elif field_name in ['email', 'referrer_email']:
        # Extract just the email address
        # First check for Calendly pattern "Invitee Email: email@domain.com"
        if 'Invitee Email:' in value:
            # Extract email after "Invitee Email:"
            parts = value.split('Invitee Email:')
            if len(parts) > 1:
                email_part = parts[1].strip()
                # Get just the email address from the remaining text
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_part)
                if email_match:
                    return email_match.group(0)
        # Standard email extraction
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', value)
        if email_match:
            return email_match.group(0)

    elif field_name == 'phone':
        # Extract just the phone number
        # First check for Calendly pattern "Phone +1 xxx-xxx-xxxx" or "Phone: +1..."
        if 'Phone' in value:
            # Extract phone after "Phone" or "Phone:"
            parts = re.split(r'Phone:?\s*', value)
            if len(parts) > 1:
                phone_part = parts[1].strip()
                # Get just the phone number from the remaining text
                phone_match = re.search(r'[\+\d\s\-\(\)\.]+', phone_part)
                if phone_match:
                    phone = phone_match.group(0).strip()
                    # Ensure it's at least 10 digits
                    digits = re.sub(r'\D', '', phone)
                    if len(digits) >= 10:
                        return phone[:30]
        # Standard phone extraction
        phone_match = re.search(r'[\d\s\-\(\)\+\.]+', value)
        if phone_match:
            phone = phone_match.group(0).strip()
            # Ensure it's at least 10 digits
            digits = re.sub(r'\D', '', phone)
            if len(digits) >= 10:
                return phone[:30]

    # General cleanup for all fields
    # If it contains multiple newlines or is too long, it's probably the whole email
    if value.count('\n') > 2 or len(value) > max_length:
        # Try to extract just the first relevant part
        lines = value.split('\n')
        first_line = lines[0].strip()

        # Common patterns to extract from
        if ':' in first_line and len(first_line.split(':')[0]) < 20:
            # It's likely a label:value format
            return first_line.split(':', 1)[-1].strip()[:max_length]
        else:
            # Just take the first part up to max_length
            return first_line[:max_length]

    # Final length check
    if len(value) > max_length:
        value = value[:max_length]

    return value

def extract_recruiting_goals(email_content):
    """Extract recruiting goals from email content for notes field"""
    # Look for recruiting goals question and answer
    goals_pattern = r'What recruiting goals[^?]*\?\s*([^\n]+(?:\n[^\n]+)?)'
    goals_match = re.search(goals_pattern, email_content, re.IGNORECASE)
    if goals_match:
        recruiting_goals = goals_match.group(1).strip()
        # Clean up the goals text
        recruiting_goals = recruiting_goals.replace('Your confirmation email', '').strip()
        if recruiting_goals:
            return f"Recruiting goals: {recruiting_goals[:200]}"
    return None

def extract_phone_from_content(email_content):
    """Extract phone number from email content"""
    phone_pattern = r'Phone[\s:]+(\+?[\d\s\-\(\)\.]+)'
    phone_match = re.search(phone_pattern, email_content)
    if phone_match:
        phone = phone_match.group(1).strip()
        digits = re.sub(r'\D', '', phone)
        if len(digits) >= 10:
            return phone[:30]
    return None

# Test cases
test_cases = [
    {
        "name": "Test 1: Calendly email with problematic format",
        "input": {
            "candidate_name": "Roy Janse Invitee Email: roy.janse@mariner.com Event Date/Time: 11:30am",
            "email": "roy.janse@mariner.com Event Date/Time: 11:30am - Thursday, September 11, 2025",
            "phone": "Phone +1 864-430-5074 What recruiting goals",
            "job_title": "Recruiting Consultant Interview",
            "notes": None
        },
        "expected": {
            "candidate_name": "Roy Janse",
            "email": "roy.janse@mariner.com",
            "phone": "+1 864-430-5074",
            "job_title": "Recruiting Consultant",
            "notes": None
        }
    },
    {
        "name": "Test 2: Full email content in field",
        "input": {
            "email": """Invitee Email: john.doe@example.com
Event Date/Time: 10:00am
Location: Zoom
Meeting ID: 123-456-7890
Phone: +1 555-123-4567""",
            "phone": None
        },
        "expected": {
            "email": "john.doe@example.com",
            "phone": None
        }
    },
    {
        "name": "Test 3: Phone extraction from various formats",
        "input": {
            "phone": "Phone: +1 (555) 123-4567"
        },
        "expected": {
            "phone": "+1 (555) 123-4567"
        }
    }
]

# Sample Calendly email for goal extraction
CALENDLY_EMAIL = """
Invitee: Roy Janse
Invitee Email: roy.janse@mariner.com
Phone +1 864-430-5074
What recruiting goals or ideas would you like to discuss?
Mid-career advisors to our Greenville team.
Your confirmation email might land in spam/junk.
"""

def run_tests():
    """Run all test cases"""
    print("=" * 80)
    print("Field Cleaning Unit Tests")
    print("=" * 80)

    # Test field cleaning
    for test in test_cases:
        print(f"\n{test['name']}")
        print("-" * 40)

        results = {}
        for field_name, value in test['input'].items():
            if value is not None:
                cleaned = clean_field(value, field_name, 100 if field_name != 'notes' else 500)
                results[field_name] = cleaned

                expected = test['expected'].get(field_name)
                if cleaned == expected:
                    print(f"✅ {field_name}: {cleaned}")
                else:
                    print(f"❌ {field_name}")
                    print(f"   Got:      {cleaned}")
                    print(f"   Expected: {expected}")

    # Test recruiting goals extraction
    print("\n" + "=" * 80)
    print("Recruiting Goals Extraction Test")
    print("-" * 40)

    goals = extract_recruiting_goals(CALENDLY_EMAIL)
    if goals and "Mid-career advisors" in goals:
        print(f"✅ Goals extracted: {goals}")
    else:
        print(f"❌ Goals not properly extracted: {goals}")

    # Test phone extraction from content
    print("\n" + "=" * 80)
    print("Phone Extraction from Content Test")
    print("-" * 40)

    phone = extract_phone_from_content(CALENDLY_EMAIL)
    if phone == "+1 864-430-5074":
        print(f"✅ Phone extracted: {phone}")
    else:
        print(f"❌ Phone not properly extracted: {phone}")

    # Test edge case: entire email content in a field
    print("\n" + "=" * 80)
    print("Edge Case: Entire Email in Field")
    print("-" * 40)

    long_value = CALENDLY_EMAIL  # Entire email content
    cleaned_email = clean_field(long_value, 'email', 100)
    cleaned_name = clean_field("Roy Janse " + CALENDLY_EMAIL, 'candidate_name', 50)

    print(f"Email field (from full content): {cleaned_email}")
    print(f"Name field (from full content): {cleaned_name}")

    if cleaned_email == "roy.janse@mariner.com":
        print("✅ Correctly extracted just the email address")
    else:
        print("❌ Failed to extract just the email address")

    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print("The field cleaning logic should:")
    print("1. Extract only the specific value (not entire email content)")
    print("2. Handle Calendly-specific patterns")
    print("3. Clean up prefixes like 'Invitee:' and 'Phone:'")
    print("4. Extract recruiting goals to notes field")
    print("5. Limit field lengths appropriately")

if __name__ == "__main__":
    run_tests()