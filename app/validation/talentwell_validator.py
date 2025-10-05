"""
TalentWell digest HTML validation system.
Validates digest templates and candidate data for email rendering.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from bs4 import BeautifulSoup
from jinja2 import Template, Environment, FileSystemLoader

logger = logging.getLogger(__name__)


@dataclass
class CandidateData:
    """Validated candidate data structure for digest rendering."""
    name: str
    location: str
    hard_skills: List[str]
    availability: str
    compensation: str
    ref_code: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'location': self.location, 
            'hard_skills': self.hard_skills,
            'availability': self.availability,
            'compensation': self.compensation,
            'ref_code': self.ref_code
        }


@dataclass
class DigestData:
    """Complete digest data structure for email rendering."""
    subject: str
    intro_block: str
    candidates: List[CandidateData]
    recipient_email: str = "brandon@emailthewell.com"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'subject': self.subject,
            'intro_block': self.intro_block,
            'candidates': [c.to_dict() for c in self.candidates],
            'recipient_email': self.recipient_email
        }


class TalentWellValidator:
    """Validate TalentWell digest templates and data."""
    
    def __init__(self, template_dir: str = "app/templates/email"):
        self.template_dir = Path(template_dir)
        self.template_path = self.template_dir / "weekly_digest_v1.html"
        
    def load_template(self) -> str:
        """Load the HTML template from disk."""
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")
        
        with open(self.template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def validate_template_structure(self, html: str) -> Tuple[bool, List[str]]:
        """Validate template has required structure and placeholders."""
        errors = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            return False, [f"HTML parsing error: {e}"]
        
        # Check required sections exist
        required_elements = [
            ('div[data-ast="intro_block"]', 'Intro block placeholder'),
            ('div[data-ast="calendly"]', 'Calendly widget'),
            ('div[data-ast="cards"]', 'Cards container')
        ]
        
        for selector, description in required_elements:
            if not soup.select(selector):
                errors.append(f"Missing required element: {description} ({selector})")
        
        # Check required data attributes for modification detection
        modifiable_sections = [
            'data-ast="intro_block"',
            'data-ast="cards"'
        ]
        
        for section in modifiable_sections:
            if section not in html:
                errors.append(f"Missing modifiable section: {section}")
        
        # Verify locked sections are present (NOT MODIFIABLE comments)
        locked_indicators = [
            "<!-- Header Section (NOT MODIFIABLE) -->",
            "<!-- Calendly Widget (NOT MODIFIABLE) -->",
            "<!-- Internal Note (NOT MODIFIABLE) -->", 
            "<!-- Footer (NOT MODIFIABLE) -->"
        ]
        
        for indicator in locked_indicators:
            if indicator not in html:
                errors.append(f"Missing locked section indicator: {indicator}")
        
        return len(errors) == 0, errors
    
    def validate_candidate_data(self, candidate: Dict[str, Any]) -> Tuple[bool, List[str], Optional[CandidateData]]:
        """Validate and convert candidate dictionary to CandidateData."""
        errors = []
        
        # Required fields
        required_fields = ['name', 'location', 'availability', 'compensation']
        for field in required_fields:
            if field not in candidate or not candidate[field]:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return False, errors, None
        
        # Extract and validate hard skills
        hard_skills = candidate.get('hard_skills', [])
        if isinstance(hard_skills, str):
            # Convert string to list (split by newlines or bullets)
            hard_skills = [skill.strip() for skill in re.split(r'[•\n]', hard_skills) if skill.strip()]
        elif not isinstance(hard_skills, list):
            errors.append("hard_skills must be a list or string")
            hard_skills = []
        
        # Generate reference code if not provided
        ref_code = candidate.get('ref_code', '')
        if not ref_code:
            ref_code = f"REF-2025-AUTO-{hash(candidate['name']) % 1000:03d}"
        
        # Validate field lengths
        if len(candidate['name']) > 100:
            errors.append("Name too long (max 100 chars)")
        if len(candidate['location']) > 200:
            errors.append("Location too long (max 200 chars)")
        if len(hard_skills) > 10:
            errors.append("Too many hard skills (max 10)")
        
        if errors:
            return False, errors, None
        
        validated_candidate = CandidateData(
            name=candidate['name'].strip(),
            location=candidate['location'].strip(),
            hard_skills=hard_skills,
            availability=candidate['availability'].strip(),
            compensation=candidate['compensation'].strip(),
            ref_code=ref_code
        )
        
        return True, [], validated_candidate
    
    def validate_digest_data(self, digest_data: Dict[str, Any]) -> Tuple[bool, List[str], Optional[DigestData]]:
        """Validate complete digest data structure."""
        errors = []
        
        # Required fields
        if 'subject' not in digest_data or not digest_data['subject']:
            errors.append("Missing required field: subject")
        
        if 'intro_block' not in digest_data or not digest_data['intro_block']:
            errors.append("Missing required field: intro_block") 
        
        if 'candidates' not in digest_data or not isinstance(digest_data['candidates'], list):
            errors.append("Missing or invalid candidates list")
            
        if not digest_data.get('candidates'):
            errors.append("At least one candidate is required")
        
        if len(digest_data.get('candidates', [])) > 10:
            errors.append("Too many candidates (max 10 per digest)")
        
        if errors:
            return False, errors, None
        
        # Validate each candidate
        validated_candidates = []
        for i, candidate in enumerate(digest_data['candidates']):
            valid, candidate_errors, validated_candidate = self.validate_candidate_data(candidate)
            if not valid:
                errors.extend([f"Candidate {i+1}: {err}" for err in candidate_errors])
            else:
                validated_candidates.append(validated_candidate)
        
        if errors:
            return False, errors, None
        
        # Validate subject line
        subject = digest_data['subject'].strip()
        if len(subject) > 100:
            errors.append("Subject line too long (max 100 chars)")
        
        # Validate intro block  
        intro_block = digest_data['intro_block'].strip()
        if len(intro_block) > 1000:
            errors.append("Intro block too long (max 1000 chars)")
        
        if errors:
            return False, errors, None
        
        validated_digest = DigestData(
            subject=subject,
            intro_block=intro_block,
            candidates=validated_candidates,
            recipient_email=digest_data.get('recipient_email', 'brandon@emailthewell.com')
        )
        
        return True, [], validated_digest
    
    def render_digest(self, digest_data: DigestData) -> str:
        """Render the digest HTML with validated data."""
        template_html = self.load_template()
        
        # Create Jinja2 environment for safe rendering
        env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True
        )
        
        # Load template content as Jinja2 template
        template = env.from_string(template_html)
        
        # Prepare template variables
        template_vars = {
            'subject': digest_data.subject,
            'intro_block': digest_data.intro_block,
            'candidates': digest_data.candidates
        }
        
        # Render the template
        rendered_html = template.render(**template_vars)
        
        return rendered_html
    
    def validate_rendered_html(self, html: str) -> Tuple[bool, List[str]]:
        """Validate the final rendered HTML for email delivery."""
        errors = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            return False, [f"HTML parsing error: {e}"]
        
        # Check for template variables that weren't replaced
        template_vars = re.findall(r'\{\{[^}]+\}\}', html)
        if template_vars:
            errors.append(f"Unreplaced template variables: {template_vars}")
        
        # Check email structure
        if not soup.find('title'):
            errors.append("Missing email title")
        
        if not soup.find('body'):
            errors.append("Missing email body")
        
        # Check for broken links (basic validation)
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            if href.startswith('http') and 'talentwell.com' in href:
                # Skip external link validation for now - would need HTTP requests
                pass
            elif href.startswith('mailto:'):
                # Validate email format
                email = href.replace('mailto:', '')
                if '@' not in email:
                    errors.append(f"Invalid email link: {href}")
        
        # Check CSS is embedded properly
        styles = soup.find_all('style')
        if not styles:
            errors.append("No CSS styles found - email may not render properly")
        
        return len(errors) == 0, errors
    
    def validate_candidate_card(self, card_html: str) -> Tuple[bool, List[str]]:
        """Validate a single candidate card follows Brandon's format."""
        errors = []
        warnings = []
        
        try:
            soup = BeautifulSoup(card_html, 'html.parser')
        except Exception as e:
            return False, [f"HTML parsing error: {e}"]
        
        # Check for required structure
        card_div = soup.find('div', class_='candidate-card')
        if not card_div:
            errors.append("Missing candidate-card div wrapper")
            return False, errors
        
        # Check for bold candidate name
        name_tag = card_div.find('h3')
        if not name_tag:
            errors.append("Missing candidate name (h3)")
        else:
            strong_tag = name_tag.find('strong')
            if not strong_tag:
                warnings.append("Candidate name should be bold (wrapped in <strong>)")
        
        # Check for location with bold label
        location_div = card_div.find('div', class_='candidate-location')
        if not location_div:
            errors.append("Missing candidate-location div")
        else:
            location_strong = location_div.find('strong')
            if not location_strong or 'Location:' not in location_strong.text:
                warnings.append("Location label should be bold and say 'Location:'")
            
            # Check for mobility line (parentheses)
            location_text = location_div.get_text()
            if '(' not in location_text or ')' not in location_text:
                warnings.append("Location should include mobility line in parentheses")
        
        # Check for bullets (2-5 required)
        bullets = card_div.find_all('li')
        if len(bullets) < 2:
            errors.append(f"Too few bullets ({len(bullets)}), minimum 2 required")
        elif len(bullets) > 5:
            warnings.append(f"Too many bullets ({len(bullets)}), maximum 5 recommended")
        
        # Check bullets are hard skills (not soft skills)
        soft_skill_keywords = ['passionate', 'dedicated', 'motivated', 'team player', 
                              'hard working', 'enthusiastic', 'driven', 'dynamic']
        for bullet in bullets:
            bullet_text = bullet.get_text().lower()
            for keyword in soft_skill_keywords:
                if keyword in bullet_text:
                    warnings.append(f"Bullet contains soft skill '{keyword}': {bullet.get_text()[:50]}")
        
        # Check for ref code
        ref_code_div = card_div.find('div', class_='ref-code')
        if not ref_code_div:
            errors.append("Missing ref-code div")
        else:
            ref_text = ref_code_div.get_text()
            if 'TWAV' not in ref_text:
                warnings.append("Ref code should start with TWAV")
        
        # Return validation result
        if errors:
            return False, errors + warnings
        return True, warnings if warnings else []
    
    def full_validation(self, digest_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Perform complete validation and return result summary."""
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'rendered_html': None,
            'digest_data': None
        }
        
        # Step 1: Validate template structure
        template_html = self.load_template()
        template_valid, template_errors = self.validate_template_structure(template_html)
        if not template_valid:
            result['valid'] = False
            result['errors'].extend([f"Template: {err}" for err in template_errors])
            return False, result
        
        # Step 2: Validate digest data
        data_valid, data_errors, validated_data = self.validate_digest_data(digest_data)
        if not data_valid:
            result['valid'] = False
            result['errors'].extend([f"Data: {err}" for err in data_errors])
            return False, result
        
        result['digest_data'] = validated_data.to_dict()
        
        # Step 3: Render digest
        try:
            rendered_html = self.render_digest(validated_data)
            result['rendered_html'] = rendered_html
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Rendering failed: {e}")
            return False, result
        
        # Step 4: Validate rendered HTML
        html_valid, html_errors = self.validate_rendered_html(rendered_html)
        if not html_valid:
            result['valid'] = False
            result['errors'].extend([f"Rendered HTML: {err}" for err in html_errors])
            return False, result
        
        # Add success metrics
        result['candidate_count'] = len(validated_data.candidates)
        result['html_size'] = len(rendered_html)
        result['estimated_tokens'] = len(rendered_html.split())
        
        logger.info(f"Digest validation successful: {result['candidate_count']} candidates, {result['html_size']} bytes")
        
        return True, result


# Create singleton validator
validator = TalentWellValidator()