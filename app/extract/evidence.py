"""
Evidence extraction and bullet point generation with confidence scoring.
Links bullets to transcript snippets and CRM fields.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EvidenceType(Enum):
    """Types of evidence sources"""
    TRANSCRIPT = "transcript"
    CRM_FIELD = "crm_field"
    EMAIL = "email"
    ATTACHMENT = "attachment"
    INFERRED = "inferred"


class BulletCategory(Enum):
    """Categories of bullet points with evidence requirements"""
    HARD_SKILL = "hard_skill"           # Requires transcript evidence
    SOFT_SKILL = "soft_skill"           # Requires transcript evidence
    EDUCATION = "education"             # Can use CRM or transcript
    EXPERIENCE = "experience"           # Can use CRM or transcript
    COMPENSATION = "compensation"       # CRM field preferred
    AVAILABILITY = "availability"       # CRM field preferred
    MOBILITY = "mobility"               # CRM field preferred
    LICENSES = "licenses"               # Requires evidence


@dataclass
class Evidence:
    """Evidence supporting a bullet point"""
    source_type: str        # "transcript", "crm_field", "email", "note"
    source_id: str          # Field name or document ID
    snippet: str            # Actual text evidence
    confidence: float       # 0.0 to 1.0
    timestamp: Optional[str] = None


@dataclass
class BulletPoint:
    """A single bullet point with evidence"""
    text: str
    category: BulletCategory = BulletCategory.EXPERIENCE
    evidence: List[Evidence] = field(default_factory=list)
    confidence_score: float = 0.5
    required_evidence: bool = True
    # Compatibility fields for existing code
    confidence: float = 0.5
    evidence_type: Optional[EvidenceType] = None
    source_snippet: Optional[str] = None
    crm_field: Optional[str] = None
    
    def has_valid_evidence(self) -> bool:
        """Check if bullet has required evidence"""
        if not self.required_evidence:
            return True
        
        # Hard/soft skills must have transcript evidence
        if self.category in [BulletCategory.HARD_SKILL, BulletCategory.SOFT_SKILL]:
            return any(e.source_type == "transcript" for e in self.evidence)
        
        # Licenses must have some evidence
        if self.category == BulletCategory.LICENSES:
            return len(self.evidence) > 0
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'text': self.text,
            'confidence': self.confidence,
            'evidence_type': self.evidence_type.value if self.evidence_type else None,
            'source_snippet': self.source_snippet,
            'crm_field': self.crm_field
        }


class EvidenceExtractor:
    """Extract and link evidence to bullet points"""
    
    def __init__(self):
        self.skill_patterns = {
            'hard': [
                r'(python|java|javascript|c\+\+|sql|react|angular|vue)',
                r'(aws|azure|gcp|docker|kubernetes)',
                r'(machine learning|data science|ai|ml)',
                r'(database|postgresql|mysql|mongodb)',
                r'(api|rest|graphql|microservices)'
            ],
            'soft': [
                r'(leadership|management|team)',
                r'(communication|presentation|interpersonal)',
                r'(problem.?solving|analytical|critical thinking)',
                r'(collaboration|teamwork|cross.?functional)'
            ]
        }
        
        self.license_patterns = [
            r'(series \d+|sie|finra)',
            r'(cfa|cfp|chfc|clu|cpwa)',
            r'(licensed|certification|certified)',
            r'(registered|registration)'
        ]
    
    def extract_from_transcript(self, transcript: str) -> List[Evidence]:
        """Extract evidence from interview transcript"""
        evidence_list = []
        
        if not transcript:
            return evidence_list
        
        # Split into sentences for snippet extraction
        sentences = re.split(r'[.!?]+', transcript)
        
        for i, sentence in enumerate(sentences):
            sentence_lower = sentence.lower().strip()
            if not sentence_lower:
                continue
            
            # Check for hard skills
            for pattern in self.skill_patterns['hard']:
                if re.search(pattern, sentence_lower):
                    evidence_list.append(Evidence(
                        source_type="transcript",
                        source_id=f"transcript_line_{i}",
                        snippet=sentence.strip(),
                        confidence=0.9
                    ))
                    break
            
            # Check for soft skills
            for pattern in self.skill_patterns['soft']:
                if re.search(pattern, sentence_lower):
                    evidence_list.append(Evidence(
                        source_type="transcript",
                        source_id=f"transcript_line_{i}",
                        snippet=sentence.strip(),
                        confidence=0.8
                    ))
                    break
            
            # Check for licenses
            for pattern in self.license_patterns:
                if re.search(pattern, sentence_lower):
                    evidence_list.append(Evidence(
                        source_type="transcript",
                        source_id=f"transcript_line_{i}",
                        snippet=sentence.strip(),
                        confidence=0.95
                    ))
                    break
        
        return evidence_list
    
    def extract_from_crm(self, crm_data: Dict[str, Any]) -> List[Evidence]:
        """Extract evidence from CRM fields"""
        evidence_list = []
        
        # Map CRM fields to evidence
        field_mappings = {
            'compensation': ['salary', 'compensation', 'comp_expectations'],
            'availability': ['start_date', 'availability', 'notice_period'],
            'mobility': ['location', 'relocation', 'mobility', 'remote_preference'],
            'education': ['education', 'degree', 'university', 'certifications'],
            'experience': ['years_experience', 'current_role', 'previous_roles']
        }
        
        for category, fields in field_mappings.items():
            for field in fields:
                if field in crm_data and crm_data[field]:
                    evidence_list.append(Evidence(
                        source_type="crm_field",
                        source_id=field,
                        snippet=str(crm_data[field]),
                        confidence=1.0  # CRM data is considered highly reliable
                    ))
        
        return evidence_list
    
    def categorize_bullet(self, text: str) -> BulletCategory:
        """Categorize a bullet point based on its content"""
        text_lower = text.lower()
        
        # Check for specific categories
        if any(re.search(p, text_lower) for p in self.skill_patterns['hard']):
            return BulletCategory.HARD_SKILL
        
        if any(re.search(p, text_lower) for p in self.skill_patterns['soft']):
            return BulletCategory.SOFT_SKILL
        
        if any(re.search(p, text_lower) for p in self.license_patterns):
            return BulletCategory.LICENSES
        
        if re.search(r'(salary|compensation|pay|earnings|bonus)', text_lower):
            return BulletCategory.COMPENSATION
        
        if re.search(r'(available|start|begin|notice)', text_lower):
            return BulletCategory.AVAILABILITY
        
        if re.search(r'(relocate|move|location|remote|hybrid)', text_lower):
            return BulletCategory.MOBILITY
        
        if re.search(r'(degree|university|college|education|study)', text_lower):
            return BulletCategory.EDUCATION
        
        return BulletCategory.EXPERIENCE
    
    def calculate_confidence(self, bullet: str, evidence: List[Evidence]) -> float:
        """Calculate confidence score for a bullet point"""
        if not evidence:
            return 0.2  # Low confidence without evidence
        
        # Weight evidence by source type
        weights = {
            'crm_field': 1.0,
            'transcript': 0.9,
            'note': 0.7,
            'email': 0.6
        }
        
        total_weight = 0
        weighted_confidence = 0
        
        for e in evidence:
            weight = weights.get(e.source_type, 0.5)
            total_weight += weight
            weighted_confidence += weight * e.confidence
        
        if total_weight > 0:
            base_confidence = weighted_confidence / total_weight
        else:
            base_confidence = 0.3
        
        # Boost confidence if multiple evidence sources
        if len(evidence) > 1:
            base_confidence = min(1.0, base_confidence * 1.1)
        
        # Reduce confidence for vague bullets
        if len(bullet.split()) < 5:
            base_confidence *= 0.8
        
        return round(base_confidence, 2)
    
    def link_evidence_to_bullet(self, bullet_text: str, 
                               all_evidence: List[Evidence]) -> List[Evidence]:
        """Link relevant evidence to a specific bullet"""
        linked = []
        bullet_lower = bullet_text.lower()
        
        for evidence in all_evidence:
            snippet_lower = evidence.snippet.lower()
            
            # Check for keyword overlap
            bullet_words = set(re.findall(r'\w+', bullet_lower))
            snippet_words = set(re.findall(r'\w+', snippet_lower))
            
            # Calculate overlap ratio
            if bullet_words and snippet_words:
                overlap = len(bullet_words & snippet_words)
                ratio = overlap / min(len(bullet_words), len(snippet_words))
                
                if ratio > 0.3:  # 30% word overlap threshold
                    linked.append(evidence)
        
        return linked
    
    def generate_bullets_with_evidence(self, 
                                      candidate_data: Dict[str, Any],
                                      transcript: Optional[str] = None,
                                      notes: Optional[List[str]] = None) -> List[BulletPoint]:
        """Generate bullet points with linked evidence"""
        bullets = []
        
        # Extract all available evidence
        all_evidence = []
        
        if transcript:
            all_evidence.extend(self.extract_from_transcript(transcript))
        
        all_evidence.extend(self.extract_from_crm(candidate_data))
        
        if notes:
            for note in notes:
                all_evidence.append(Evidence(
                    source_type="note",
                    source_id="deal_note",
                    snippet=note[:200],  # First 200 chars
                    confidence=0.7
                ))
        
        # Generate bullets from candidate data
        bullet_texts = self._generate_bullet_texts(candidate_data, transcript)
        
        for text in bullet_texts:
            category = self.categorize_bullet(text)
            linked_evidence = self.link_evidence_to_bullet(text, all_evidence)
            confidence = self.calculate_confidence(text, linked_evidence)
            
            # Determine if evidence is required
            required = category in [
                BulletCategory.HARD_SKILL,
                BulletCategory.SOFT_SKILL,
                BulletCategory.LICENSES
            ]
            
            bullet = BulletPoint(
                text=text,
                category=category,
                evidence=linked_evidence,
                confidence_score=confidence,
                required_evidence=required
            )
            
            # Only include if has valid evidence or not required
            if bullet.has_valid_evidence():
                bullets.append(bullet)
            else:
                logger.warning(f"Dropping bullet without required evidence: {text}")
        
        # Sort by confidence score
        bullets.sort(key=lambda b: b.confidence_score, reverse=True)
        
        return bullets
    
    def _generate_bullet_texts(self, candidate_data: Dict[str, Any], 
                              transcript: Optional[str]) -> List[str]:
        """Generate raw bullet text from candidate data"""
        bullets = []
        
        # Skills from job title
        if candidate_data.get('job_title'):
            bullets.append(f"Current role: {candidate_data['job_title']}")
        
        # Location and mobility
        if candidate_data.get('location'):
            location = candidate_data['location']
            bullets.append(f"Based in {location}")
            
            if candidate_data.get('mobility'):
                bullets.append(f"Open to relocation: {candidate_data['mobility']}")
        
        # Compensation expectations
        if candidate_data.get('compensation'):
            bullets.append(f"Compensation expectations: {candidate_data['compensation']}")
        
        # Availability
        if candidate_data.get('availability'):
            bullets.append(f"Available to start: {candidate_data['availability']}")
        
        # Extract skills from transcript if available
        if transcript:
            skills = self._extract_skills_from_text(transcript)
            for skill in skills[:5]:  # Top 5 skills
                bullets.append(f"Experienced in {skill}")
        
        # Licenses and certifications
        if candidate_data.get('licenses'):
            for license in candidate_data['licenses'].split(','):
                bullets.append(f"Holds {license.strip()} license")
        
        return bullets
    
    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extract skill mentions from text"""
        skills = set()
        text_lower = text.lower()
        
        # Hard skills
        for pattern in self.skill_patterns['hard']:
            matches = re.findall(pattern, text_lower)
            skills.update(matches)
        
        # Soft skills (limit to avoid too many generic ones)
        soft_count = 0
        for pattern in self.skill_patterns['soft']:
            if soft_count >= 2:  # Max 2 soft skills
                break
            matches = re.findall(pattern, text_lower)
            if matches:
                skills.add(matches[0])
                soft_count += 1
        
        return list(skills)
    
    def filter_bullets_by_confidence(self, bullets: List[BulletPoint], 
                                    min_confidence: float = 0.6) -> List[BulletPoint]:
        """Filter bullets by minimum confidence threshold"""
        return [b for b in bullets if b.confidence_score >= min_confidence]
    
    def format_bullets_for_display(self, bullets: List[BulletPoint], 
                                  include_evidence: bool = False) -> List[Dict[str, Any]]:
        """Format bullets for display in email or UI"""
        formatted = []
        
        for bullet in bullets:
            item = {
                'text': bullet.text,
                'category': bullet.category.value,
                'confidence': bullet.confidence_score
            }
            
            if include_evidence and bullet.evidence:
                item['evidence'] = [
                    {
                        'source': e.source_type,
                        'snippet': e.snippet[:100] + '...' if len(e.snippet) > 100 else e.snippet
                    }
                    for e in bullet.evidence[:2]  # Max 2 evidence items
                ]
            
            formatted.append(item)
        
        return formatted