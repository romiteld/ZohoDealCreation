"""
Enhanced extraction module with automatic enrichment capabilities
"""

import re
import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class EnhancedExtractor:
    """Enhanced extractor with automatic enrichment from various sources"""
    
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def extract_calendly_data(self, text: str) -> Dict[str, Any]:
        """Extract data from Calendly URLs in the email"""
        calendly_data = {}
        
        # Find Calendly URLs
        calendly_pattern = r'(https?://(?:www\.)?calendly\.com[^\s\'"<>]+)'
        calendly_urls = re.findall(calendly_pattern, text, re.IGNORECASE)
        
        if calendly_urls:
            calendly_data['calendly_url'] = calendly_urls[0]
            
            # Parse URL parameters
            try:
                parsed = urlparse(calendly_urls[0])
                params = parse_qs(parsed.query)
                
                # Extract common Calendly parameters
                if 'name' in params:
                    calendly_data['name'] = params['name'][0].replace('+', ' ')
                if 'email' in params:
                    calendly_data['email'] = params['email'][0]
                if 'phone' in params:
                    calendly_data['phone'] = params['phone'][0]
                if 'location' in params:
                    calendly_data['location'] = params['location'][0].replace('+', ' ')
                    
            except Exception as e:
                logger.debug(f"Could not parse Calendly URL params: {e}")
        
        return calendly_data
    
    def extract_linkedin_url(self, text: str) -> Optional[str]:
        """Extract LinkedIn URL from email text"""
        # Pattern for LinkedIn URLs
        linkedin_pattern = r'(https?://(?:www\.)?linkedin\.com/in/[^\s\'"<>]+)'
        matches = re.findall(linkedin_pattern, text, re.IGNORECASE)
        
        if matches:
            return matches[0].split('?')[0]  # Remove query parameters
        
        return None
    
    async def lookup_company_from_domain(self, email: str) -> Dict[str, Any]:
        """Look up company information from email domain"""
        if not email or '@' not in email:
            return {}
        
        domain = email.split('@')[1].lower()
        
        # Skip generic email domains
        generic_domains = [
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 
            'aol.com', 'icloud.com', 'me.com', 'mac.com', 'msn.com',
            'live.com', 'protonmail.com', 'ymail.com'
        ]
        
        if domain in generic_domains:
            return {}
        
        # Try to fetch company info from domain
        company_info = {}
        
        try:
            # Use Firecrawl or similar service to get company info
            # For now, we'll use basic domain parsing
            company_name = domain.split('.')[0]
            
            # Common patterns to clean up company names
            company_name = company_name.replace('-', ' ').replace('_', ' ')
            
            # Title case the company name
            company_name = ' '.join(word.capitalize() for word in company_name.split())
            
            # Special cases for known domains
            domain_mappings = {
                'mariner.com': 'Mariner Wealth Advisors',
                'wellsfargo.com': 'Wells Fargo',
                'ml.com': 'Merrill Lynch',
                'morganstanley.com': 'Morgan Stanley',
                'ubs.com': 'UBS',
                'emailthewell.com': 'The Well Recruiting Solutions',
                'thewell.com': 'The Well Recruiting Solutions'
            }
            
            if domain in domain_mappings:
                company_name = domain_mappings[domain]
            
            company_info = {
                'company_name': company_name,
                'company_domain': domain,
                'confidence': 0.8 if domain not in domain_mappings else 1.0
            }
            
            # Try to get website
            company_info['website'] = f"https://www.{domain}"
            
        except Exception as e:
            logger.debug(f"Could not lookup company from domain {domain}: {e}")
        
        return company_info
    
    async def search_linkedin_profile(self, name: str, company: str = None) -> Optional[str]:
        """Search for LinkedIn profile URL based on name and company"""
        if not name:
            return None
        
        # This would ideally use LinkedIn API or web search
        # For now, return a formatted search URL
        search_query = f"{name}"
        if company:
            search_query += f" {company}"
        
        # Return LinkedIn search URL (user would need to manually search)
        # In production, this could use Google Custom Search API or similar
        return f"https://www.linkedin.com/search/results/people/?keywords={search_query.replace(' ', '%20')}"
    
    def clean_and_validate_fields(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate extracted fields to prevent truncation"""
        cleaned = {}
        
        for key, value in extracted_data.items():
            if value is None:
                cleaned[key] = None
                continue
            
            # Convert to string and clean
            str_value = str(value).strip()
            
            # Fix specific truncation patterns
            if key == 'candidate_name':
                # Remove common suffixes that indicate truncation
                if 'Invitee Email:' in str_value or 'Email:' in str_value:
                    # Extract just the name part
                    str_value = str_value.split('Invitee Email:')[0].strip()
                    str_value = str_value.split('Email:')[0].strip()
                if str_value.endswith('...'):
                    str_value = str_value[:-3].strip()
                    cleaned[f'{key}_needs_verification'] = True
                cleaned[key] = str_value
            
            elif key == 'job_title':
                # Remove "Invitee:" suffix if present
                if 'Invitee:' in str_value:
                    # Extract the actual job title
                    parts = str_value.split('Invitee:')
                    if parts[0]:
                        str_value = parts[0].strip()
                if str_value.endswith('...'):
                    str_value = str_value[:-3].strip()
                    cleaned[f'{key}_needs_verification'] = True
                cleaned[key] = str_value
            
            # General truncation check
            elif str_value.endswith('...'):
                # Field was likely truncated, mark for expansion
                cleaned[key] = str_value[:-3].strip()
                cleaned[f'{key}_truncated'] = True
            else:
                cleaned[key] = str_value
        
        return cleaned
    
    def extract_location_from_zip(self, text: str) -> Optional[str]:
        """Extract proper location from zip code or partial address"""
        # Pattern for zip codes
        zip_pattern = r'\b(\d{5})(?:-\d{4})?\b'
        zip_matches = re.findall(zip_pattern, text)
        
        if zip_matches:
            # Map common zip codes to cities (expand this mapping)
            zip_to_city = {
                '21501': 'Cumberland, MD',
                '46802': 'Fort Wayne, IN',
                '46804': 'Fort Wayne, IN',
                '46825': 'Fort Wayne, IN',
                '10001': 'New York, NY',
                '90210': 'Beverly Hills, CA',
                '60601': 'Chicago, IL',
                '75201': 'Dallas, TX',
                '85001': 'Phoenix, AZ',
                '92101': 'San Diego, CA',
                '33101': 'Miami, FL',
                '98101': 'Seattle, WA',
                '94102': 'San Francisco, CA',
                '02108': 'Boston, MA',
                '30301': 'Atlanta, GA'
            }
            
            for zip_code in zip_matches:
                # Check first 3 digits for region
                zip_prefix = zip_code[:3]
                if zip_code in zip_to_city:
                    return zip_to_city[zip_code]
                elif zip_prefix in ['215']:  # Maryland
                    return f"Maryland (ZIP: {zip_code})"
                elif zip_prefix in ['468']:  # Fort Wayne area
                    return f"Fort Wayne, IN area"
        
        return None
    
    async def enhance_extraction(self, extraction_result: Dict[str, Any], email_body: str, sender_email: str) -> Dict[str, Any]:
        """Enhance extraction with automatic lookups and enrichment"""
        enhanced = extraction_result.copy()
        
        # Extract Calendly data if present
        calendly_data = self.extract_calendly_data(email_body)
        if calendly_data:
            # Update fields from Calendly if not already present
            if calendly_data.get('calendly_url'):
                enhanced['calendly_url'] = calendly_data['calendly_url']
            if not enhanced.get('email') and calendly_data.get('email'):
                enhanced['email'] = calendly_data['email']
            if not enhanced.get('phone') and calendly_data.get('phone'):
                enhanced['phone'] = calendly_data['phone']
            if not enhanced.get('candidate_name') and calendly_data.get('name'):
                enhanced['candidate_name'] = calendly_data['name']
        
        # Extract LinkedIn URL if not present
        if not enhanced.get('linkedin_url'):
            linkedin_url = self.extract_linkedin_url(email_body)
            if linkedin_url:
                enhanced['linkedin_url'] = linkedin_url
        
        # Lookup company from email domain if not present
        if not enhanced.get('company_name'):
            # Try candidate email first
            candidate_email = enhanced.get('email')
            if candidate_email:
                company_info = await self.lookup_company_from_domain(candidate_email)
                if company_info.get('company_name'):
                    enhanced['company_name'] = company_info['company_name']
                    if not enhanced.get('website'):
                        enhanced['website'] = company_info.get('website')
        
        # Fix location if it looks like a zip code
        if enhanced.get('location'):
            location = enhanced['location']
            # Check if location looks like a partial address or zip
            if re.match(r'^\d{5}', location) or 'ZIP' in location.upper():
                better_location = self.extract_location_from_zip(email_body)
                if better_location:
                    enhanced['location'] = better_location
        
        # Search for LinkedIn if we have a name but no URL
        if enhanced.get('candidate_name') and not enhanced.get('linkedin_url'):
            linkedin_search = await self.search_linkedin_profile(
                enhanced['candidate_name'],
                enhanced.get('company_name')
            )
            if linkedin_search:
                enhanced['linkedin_search_url'] = linkedin_search
        
        # Clean and validate all fields
        enhanced = self.clean_and_validate_fields(enhanced)
        
        # Ensure no truncation in key fields
        if enhanced.get('candidate_name_truncated'):
            logger.warning(f"Candidate name appears truncated: {enhanced.get('candidate_name')}")
        if enhanced.get('job_title_truncated'):
            logger.warning(f"Job title appears truncated: {enhanced.get('job_title')}")
        
        return enhanced


async def enhance_extraction_result(extraction_result: Dict[str, Any], email_body: str, sender_email: str) -> Dict[str, Any]:
    """Main entry point for extraction enhancement"""
    async with EnhancedExtractor() as extractor:
        return await extractor.enhance_extraction(extraction_result, email_body, sender_email)