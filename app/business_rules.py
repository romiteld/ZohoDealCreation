from typing import Tuple, Optional, Dict, Any
import re

def filter_well_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filters out The Well Recruiting Solutions information from client/candidate data.
    This prevents the referrer's information from being mistaken as client data.
    """
    # The Well's known information to exclude
    well_info = {
        'company_names': ['The Well Recruiting Solutions', 'The Well', 'Well Recruiting'],
        'addresses': ['21501 N. 78th Ave #100', 'Peoria, AZ 85382', 'Peoria, AZ', 'Peoria'],
        'phones': ['806.500.4359', '8065004359', '(806) 500-4359'],
        'emails': ['@emailthewell.com', '@thewell.com']
    }

    filtered_data = data.copy()

    # Check and clear company name if it's The Well
    if filtered_data.get('company_name'):
        for well_company in well_info['company_names']:
            if well_company.lower() in filtered_data['company_name'].lower():
                filtered_data['company_name'] = None
                break

    # Check and clear location if it's The Well's address
    if filtered_data.get('location'):
        for well_address in well_info['addresses']:
            if well_address.lower() in filtered_data['location'].lower():
                filtered_data['location'] = None
                break

    # Check and clear phone if it's The Well's phone
    if filtered_data.get('phone'):
        # Normalize phone for comparison
        normalized_phone = re.sub(r'[^\d]', '', filtered_data['phone'])
        for well_phone in well_info['phones']:
            normalized_well = re.sub(r'[^\d]', '', well_phone)
            if normalized_well == normalized_phone:
                filtered_data['phone'] = None
                break

    # Check and clear email if it's from The Well domain
    if filtered_data.get('email'):
        for well_email in well_info['emails']:
            if well_email in filtered_data['email'].lower():
                filtered_data['email'] = None
                break

    return filtered_data

def format_deal_name(job_title: Optional[str], location: Optional[str], company_name: Optional[str],
                     use_steve_format: bool = False) -> str:
    """
    Formats the deal name according to business rules.

    Legacy format: [Position] [Location] - [Company Name]
    Steve's template format: [Job Title] ([Location]) [Company Name]
    """
    # Use None for missing values - DO NOT use placeholder text
    jt = job_title.strip() if job_title else None
    loc = location.strip() if location else None
    comp = company_name.strip() if company_name else None

    # If location has comma, take only city (first part) for legacy format
    if loc and "," in loc and not use_steve_format:
        loc = loc.split(',')[0].strip()

    if use_steve_format:
        # Steve's template format: [Job Title] ([Location]) - [Company Name]
        if jt and loc and comp:
            return f"{jt} ({loc}) - {comp}"
        elif jt and comp:
            # Missing location
            return f"{jt} {comp}"
        elif jt and loc:
            # Missing company
            return f"{jt} ({loc})"
        elif comp:
            # Only company available
            return comp
        else:
            return None
    else:
        # Legacy format: [Position] [Location] - [Company Name]
        if jt and loc and comp:
            return f"{jt} {loc} - {comp}"
        elif jt and comp:
            return f"{jt} - {comp}"
        elif jt and loc:
            return f"{jt} {loc}"
        elif comp:
            return comp
        else:
            return None

def format_client_deal_name(client_name: Optional[str], company_name: Optional[str]) -> str:
    """
    Formats deal name for client consultation emails.
    Format: "Recruiting Services - [Client Name] ([Company])"
    """
    if not client_name:
        return "Recruiting Services - Consultation"
    
    if company_name:
        return f"Recruiting Services - {client_name} ({company_name})"
    else:
        return f"Recruiting Services - {client_name}"

def clean_contact_name(name: Optional[str]) -> Tuple[Optional[str], Dict[str, str]]:
    """
    Removes honorifics from a name and splits into first/last.
    """
    if not name:
        return None, {"first_name": "Unknown", "last_name": "Contact"}
    
    honorifics = ["Mr.", "Mrs.", "Ms.", "Dr.", "Prof."]
    cleaned_name = name
    for h in honorifics:
        cleaned_name = re.sub(rf'\b{re.escape(h)}\b', '', cleaned_name, flags=re.IGNORECASE).strip()
    
    cleaned_name = ' '.join(cleaned_name.split())
    parts = cleaned_name.split()
    if not parts:
        return cleaned_name, {"first_name": "Unknown", "last_name": "Contact"}
        
    first_name = parts[0]
    last_name = " ".join(parts[1:]) if len(parts) > 1 else "Contact"
    
    return cleaned_name, {"first_name": first_name, "last_name": last_name}

def is_client_consultation_email(email_body: str, subject: str = "", sender_email: str = "") -> bool:
    """
    Detects if this is a client consultation email rather than a candidate application.
    """
    lower_body = email_body.lower()
    lower_subject = subject.lower()
    lower_sender = sender_email.lower()
    
    # Calendly consultation indicators
    consultation_keywords = [
        "recruiting consult", "consultation", "recruiting services",
        "discuss your recruiting", "hiring challenges", "recruiting goals",
        "build your ideal team", "hiring solutions", "recruiting strategies"
    ]
    
    # Check if it's a Calendly meeting about recruiting services
    is_from_calendly = "calendly.com" in lower_body or "calendly.com" in lower_sender
    
    if is_from_calendly:
        for keyword in consultation_keywords:
            if keyword in lower_body or keyword in lower_subject:
                return True
    
    # Also check for recruiting consult in subject even without calendly
    if "recruiting consult" in lower_subject:
        return True
    
    return False

def determine_source(email_body: str, referrer_name: Optional[str], sender_email: str = "", subject: str = "") -> Tuple[str, Optional[str]]:
    """
    Determines the deal source based on email content and referrer info.
    """
    if referrer_name and referrer_name.lower() != "unknown":
        return "Referral", referrer_name
    
    lower_body = email_body.lower()
    lower_sender = sender_email.lower()
    
    # Check if this is a consultation email - these are referrals even if from Calendly
    if is_client_consultation_email(email_body, subject, sender_email):
        return "Referral", "Client consultation scheduling"
    
    if "twav" in lower_body or "advisor vault" in lower_body:
        return "Reverse Recruiting", "TWAV Platform"
    if "calendly.com" in lower_body or "calendly.com" in lower_sender:
        return "Website Inbound", "Calendly scheduling"
    return "Email Inbound", "Direct email contact"

def determine_distribution_network(referrer_name: Optional[str]) -> Optional[str]:
    """
    Maps a known referrer to their distribution network.
    """
    if not referrer_name:
        return None
    
    referrer_map = {
        "phil blosser": "Advisors Excel"
    }
    for key, network in referrer_map.items():
        if key in referrer_name.lower():
            return network
    return None


def extract_manual_referrer(email_body: str, sender_email: str) -> Optional[str]:
    """
    Extract referrer information from manual referral emails.
    """
    import re
    
    lower_body = email_body.lower()
    
    # Patterns to look for referrer information
    referrer_patterns = [
        r'referral from\s+([^.\n]+)',
        r'referred by\s+([^.\n]+)',
        r'referrer:\s*([^.\n]+)',
        r'from\s+([^@\s]+(?:\s+[^@\s]+)*)\s*(?:@|\sat\s)',  # "from josh whitehead at advisors excel"
    ]
    
    for pattern in referrer_patterns:
        match = re.search(pattern, lower_body)
        if match:
            referrer_name = match.group(1).strip()
            # Clean up common endings
            referrer_name = re.sub(r'\s+(at|@|from|of)\s.*$', '', referrer_name).strip()
            if referrer_name and len(referrer_name) > 2:
                return referrer_name.title()
    
    # Check if sender is from a known referral source (not internal)
    if sender_email and not any(domain in sender_email.lower() for domain in ['emailthewell.com', 'calendly.com']):
        # Extract name from email sender
        if '@advisorsexcel.com' in sender_email.lower():
            sender_name = sender_email.split('@')[0].replace('.', ' ').title()
            return sender_name
    
    return None

class BusinessRulesEngine:
    """
    Business rules engine for processing extracted data
    """
    
    def process_data(self, ai_data: Dict, email_body: str, sender_email: str, subject: str = "") -> Dict:
        """
        Process extracted data through business rules

        Args:
            ai_data: Data extracted by AI
            email_body: Original email body
            sender_email: Sender's email address
            subject: Email subject line

        Returns:
            Processed data with business rules applied
        """
        result = ai_data.copy() if ai_data else {}

        # Filter out The Well's information from client/candidate data
        result = filter_well_info(result)
        
        # Try to extract manual referrer information if not already provided
        if not result.get('referrer'):
            manual_referrer = extract_manual_referrer(email_body, sender_email)
            if manual_referrer:
                result['referrer'] = manual_referrer
        
        # Check if this is a client consultation email
        is_consultation = is_client_consultation_email(email_body, subject, sender_email)
        
        if is_consultation:
            # Handle as client consultation deal
            client_name = result.get('candidate_name')  # In consultation emails, this is the client name
            company_name = result.get('company_name')
            
            # Extract client info from Calendly data if available
            if not client_name and "calendly.com" in email_body:
                # Try to extract from email content
                import re
                # Look for "Invitee: [Name]" pattern
                invitee_match = re.search(r'Invitee:\s*([^\n]+)', email_body)
                if invitee_match:
                    client_name = invitee_match.group(1).strip()
                    result['candidate_name'] = client_name
                
                # Look for email in Calendly content
                email_match = re.search(r'Invitee Email:\s*([^\n]+)', email_body)
                if email_match:
                    client_email = email_match.group(1).strip()
                    result['email'] = client_email
                    # Extract company from email domain
                    if not company_name and '@' in client_email:
                        domain = client_email.split('@')[1]
                        # Simple company name extraction from domain
                        company_guess = domain.split('.')[0].title()
                        result['company_name'] = company_guess
                        company_name = company_guess
            
            # Format as client consultation deal
            deal_name = format_client_deal_name(client_name, company_name)
            result['deal_name'] = deal_name
            result['is_client_consultation'] = True
            result['job_title'] = "Recruiting Services"  # This is what we're selling
            
        else:
            # Handle as regular candidate application
            # Check if we have Steve's 3-record structure
            has_structured_records = (
                result.get('company_record') or
                result.get('contact_record') or
                result.get('deal_record')
            )

            # Format deal name using appropriate format
            job_title = result.get('job_title')
            location = result.get('location')
            company_name = result.get('company_name')

            # Don't use placeholder values - keep as None if missing
            deal_name = format_deal_name(
                job_title, location, company_name,
                use_steve_format=has_structured_records
            )
            if deal_name:
                result['deal_name'] = deal_name
            else:
                # Mark that deal name needs user input
                result['deal_name'] = None
                result['requires_user_input'] = True
                result['missing_fields'] = []
                if not job_title:
                    result['missing_fields'].append('job_title')
                if not location:
                    result['missing_fields'].append('location')
                if not company_name:
                    result['missing_fields'].append('company_name')
        
        # Clean contact name - don't use "Unknown" placeholders
        contact_name = result.get('candidate_name')
        if contact_name:
            full_name, name_parts = clean_contact_name(contact_name)
            result['contact_full_name'] = full_name
            # Only set first/last name if we have real values
            if name_parts.get('first_name') != 'Unknown':
                result['contact_first_name'] = name_parts.get('first_name')
            if name_parts.get('last_name') != 'Contact':
                result['contact_last_name'] = name_parts.get('last_name')
        
        # Determine source
        referrer = result.get('referrer')
        source_type, source_detail = determine_source(email_body, referrer, sender_email, subject)
        result['source_type'] = source_type
        result['source_detail'] = source_detail
        
        # Determine distribution network
        if referrer:
            result['distribution_network'] = determine_distribution_network(referrer)
        
        return result