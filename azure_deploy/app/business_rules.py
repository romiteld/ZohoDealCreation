from typing import Tuple, Optional, Dict, Any
import re

def format_deal_name(job_title: Optional[str], location: Optional[str], company_name: Optional[str]) -> str:
    """
    Formats the deal name according to the strict business rule.
    Rule: [Job Title] ([Location]) - [Firm Name]
    """
    jt = (job_title or "Unknown Role").strip()
    loc = (location or "Unknown Location").strip()
    comp = (company_name or "Unknown Company").strip()
    
    if loc != "Unknown Location" and "," in loc:
        loc = loc.split(',')[0].strip()
        
    return f"{jt} ({loc}) - {comp}"

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

def determine_source(email_body: str, referrer_name: Optional[str]) -> Tuple[str, Optional[str]]:
    """
    Determines the deal source based on email content and referrer info.
    """
    if referrer_name and referrer_name.lower() != "unknown":
        return "Referral", referrer_name
    
    lower_body = email_body.lower()
    if "twav" in lower_body or "advisor vault" in lower_body:
        return "Reverse Recruiting", "TWAV Platform"
    if "calendly.com" in lower_body:
        return "Website Inbound", "Calendly scheduling"
    return "Referral", "Unknown"

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


class BusinessRulesEngine:
    """
    Business rules engine for processing extracted data
    """
    
    def process_data(self, ai_data: Dict, email_body: str, sender_email: str) -> Dict:
        """
        Process extracted data through business rules
        
        Args:
            ai_data: Data extracted by AI
            email_body: Original email body
            sender_email: Sender's email address
            
        Returns:
            Processed data with business rules applied
        """
        result = ai_data.copy() if ai_data else {}
        
        # Format deal name
        job_title = result.get('job_title')
        location = result.get('location')
        company_name = result.get('company_name')
        result['deal_name'] = format_deal_name(job_title, location, company_name)
        
        # Clean contact name
        contact_name = result.get('candidate_name')
        if contact_name:
            full_name, name_parts = clean_contact_name(contact_name)
            result['contact_full_name'] = full_name
            result['contact_first_name'] = name_parts.get('first_name')
            result['contact_last_name'] = name_parts.get('last_name')
        
        # Determine source
        referrer = result.get('referrer')
        source_type, source_detail = determine_source(email_body, referrer)
        result['source_type'] = source_type
        result['source_detail'] = source_detail
        
        # Determine distribution network
        if referrer:
            result['distribution_network'] = determine_distribution_network(referrer)
        
        return result