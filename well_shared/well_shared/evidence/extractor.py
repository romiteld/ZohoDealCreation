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
    FINANCIAL_METRIC = "financial_metric"  # AUM, production, book size
    GROWTH_ACHIEVEMENT = "growth_achievement"  # Growth metrics and achievements
    CLIENT_METRIC = "client_metric"  # Client count, retention, relationships
    PERFORMANCE_RANKING = "performance_ranking"  # Rankings and performance metrics
    LICENSES = "licenses"  # Series licenses, designations
    EDUCATION = "education"  # Degrees, certifications
    EXPERIENCE = "experience"  # Years of experience, roles
    COMPENSATION = "compensation"  # Salary expectations
    AVAILABILITY = "availability"  # Start date, notice period
    MOBILITY = "mobility"  # Location, relocation preferences


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
    source: Optional[str] = None  # Added to support talentwell_curator
    
    def has_valid_evidence(self) -> bool:
        """Check if bullet has required evidence"""
        if not self.required_evidence:
            return True

        # Financial metrics and achievements must have transcript evidence
        if self.category in [BulletCategory.FINANCIAL_METRIC,
                             BulletCategory.GROWTH_ACHIEVEMENT,
                             BulletCategory.PERFORMANCE_RANKING,
                             BulletCategory.CLIENT_METRIC]:
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
        # Financial metrics patterns
        self.financial_patterns = {
            'aum': [
                r'\$[\d,]+(?:\.\d+)?\s*(?:billion|b|B)\s*(?:RIA|AUM|aum|in assets|under management)?',
                r'\$[\d,]+(?:\.\d+)?\s*(?:million|m|M|MM)\s*(?:RIA|AUM|aum|in assets|under management)?',
                r'\$[\d,]+(?:\.\d+)?\s*(?:thousand|k|K)\s*(?:RIA|AUM|aum|in assets|under management)?',
                r'(?:AUM|aum|assets under management|book size)[:\s]+\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?',
                r'(?:manages?|managing|oversee[sn]?|responsible for)[\s\w]*\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?',
                r'(?:book|portfolio)[\s\w]*\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?',
                r'(?:built|founded|grew|raised)[\s\w]*\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?\s*(?:RIA|firm|assets|AUM)'
            ],
            'production': [
                r'\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?\s*(?:annual production|production|in production)',
                r'(?:production|revenue|generated)[:\s]+\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?',
                r'(?:produces?|producing|generated?)[\s\w]*\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?\s*(?:annually|per year)?'
            ],
            'growth': [
                r'(?:grew|growth|increased?|expanded?)[\s\w]*(?:from )?[~]?\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?[\s\w]*(?:to )[~]?\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?',
                r'(?:growing|grew|growth|increased?|expanded?)[\s\w]*(?:AUM|aum|assets|book|production)[\s\w]*(?:from|to|by)[\s\w]*[~]?[\$\d,]+(?:\.\d+)?\s*[BMKbmk]?',
                r'(?:increased?|grew|expanded?)[\s\w]*(?:AUM|aum|assets|book|production)[\s\w]*(?:by )?\d+(?:\.\d+)?%',
                r'\d+[%x]\s*(?:growth|increase|expansion)',
                r'(?:doubled|tripled|quadrupled)[\s\w]*(?:AUM|aum|assets|book|production|client base)',
                r'(?:scaled|scaling)[\s\w]*(?:from )?[~]?\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?[\s\w]*(?:to )[~]?\$[\d,]+(?:\.\d+)?\s*[BMKbmk]?'
            ]
        }

        # Performance and ranking patterns
        self.ranking_patterns = [
            r'#\d+(?:\s*[-–—]\s*\d+)?\s*(?:nationally|in nation|in the nation|across firm|company.?wide)',
            r'(?:ranked|ranking)\s*(?:#)?\d+(?:\s*[-–—]\s*\d+)?',
            r'(?:top\s*)?\d+(?:%|percent)\s*(?:performer|producer|advisor)',
            r'(?:top|best)\s*(?:tier|percentile|performer|producer)',
            r'(?:president\'?s club|circle of champions|chairman\'?s club)',
            r'(?:close rate|conversion rate|win rate)[:\s]+\d+(?:\.\d+)?%'
        ]

        # Client metrics patterns
        self.client_patterns = [
            r'\d+\+?\s*(?:clients?|relationships?|households?|families)',
            r'(?:serve[sd]?|serving|manages?|managing)[\s\w]*\d+\+?\s*(?:clients?|relationships?)',
            r'\d+(?:\.\d+)?%\s*(?:retention|client retention|renewal rate)',
            r'(?:retention rate|renewal rate)[:\s]+\d+(?:\.\d+)?%',
            r'\d+\+?\s*(?:HNW|UHNW|high.?net.?worth|ultra.?high)\s*(?:clients?|individuals?|families)'
        ]

        # License and certification patterns
        self.license_patterns = [
            r'(?:series|sie)\s*\d+(?:[,\s]+\d+)*',
            r'(?:CFA|CFP|ChFC|CLU|CPWA|CTFA|CIMA|WMCP|AAMS|AIF)(?:\s*(?:charter|charterholder|certification|certified))?',
            r'(?:holds?|holding|have|earned?)[\s\w]*(?:series|CFA|CFP|ChFC|CLU|CPWA)\s*\w+',
            r'(?:licensed?|licensing|certification|certified)\s*(?:in|for|as)[\s\w]+',
            r'(?:life\s*(?:and|&)\s*health|property\s*(?:and|&)\s*casualty)\s*(?:license|licensed)',
            r'(?:passed all \d levels|level [IVX123] (?:passed|candidate))'
        ]
    
    def extract_from_transcript(self, transcript: str) -> List[Evidence]:
        """Extract evidence from interview transcript or email content"""
        evidence_list = []

        if not transcript:
            return evidence_list

        # Split into sentences for snippet extraction (avoid splitting on decimal numbers)
        # First, protect decimal numbers in dollar amounts
        protected_text = re.sub(r'(\$[\d,]+)\.(\d+)([BMKbmk]?)', r'\1DECIMAL\2\3', transcript)
        sentences = re.split(r'[.!?]+', protected_text)
        # Restore decimal points
        sentences = [re.sub(r'DECIMAL', '.', s) for s in sentences]

        for i, sentence in enumerate(sentences):
            sentence_clean = sentence.strip()
            if not sentence_clean:
                continue

            # Check for AUM/Book Size metrics
            for pattern in self.financial_patterns['aum']:
                if re.search(pattern, sentence_clean, re.IGNORECASE):
                    evidence_list.append(Evidence(
                        source_type="transcript",
                        source_id=f"transcript_line_{i}",
                        snippet=sentence_clean,
                        confidence=0.95
                    ))
                    break

            # Check for production metrics
            for pattern in self.financial_patterns['production']:
                if re.search(pattern, sentence_clean, re.IGNORECASE):
                    evidence_list.append(Evidence(
                        source_type="transcript",
                        source_id=f"transcript_line_{i}",
                        snippet=sentence_clean,
                        confidence=0.95
                    ))
                    break

            # Check for growth metrics
            for pattern in self.financial_patterns['growth']:
                if re.search(pattern, sentence_clean, re.IGNORECASE):
                    evidence_list.append(Evidence(
                        source_type="transcript",
                        source_id=f"transcript_line_{i}",
                        snippet=sentence_clean,
                        confidence=0.95
                    ))
                    break

            # Check for performance rankings
            for pattern in self.ranking_patterns:
                if re.search(pattern, sentence_clean, re.IGNORECASE):
                    evidence_list.append(Evidence(
                        source_type="transcript",
                        source_id=f"transcript_line_{i}",
                        snippet=sentence_clean,
                        confidence=0.9
                    ))
                    break

            # Check for client metrics
            for pattern in self.client_patterns:
                if re.search(pattern, sentence_clean, re.IGNORECASE):
                    evidence_list.append(Evidence(
                        source_type="transcript",
                        source_id=f"transcript_line_{i}",
                        snippet=sentence_clean,
                        confidence=0.9
                    ))
                    break

            # Check for licenses and certifications
            for pattern in self.license_patterns:
                if re.search(pattern, sentence_clean, re.IGNORECASE):
                    evidence_list.append(Evidence(
                        source_type="transcript",
                        source_id=f"transcript_line_{i}",
                        snippet=sentence_clean,
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
        # Check for growth achievements FIRST (highest priority)
        if any(re.search(p, text, re.IGNORECASE) for p in self.financial_patterns.get('growth', [])):
            return BulletCategory.GROWTH_ACHIEVEMENT

        # Check for performance rankings
        if any(re.search(p, text, re.IGNORECASE) for p in self.ranking_patterns):
            return BulletCategory.PERFORMANCE_RANKING

        # Check for client metrics
        if any(re.search(p, text, re.IGNORECASE) for p in self.client_patterns):
            return BulletCategory.CLIENT_METRIC

        # Check for other financial metrics (AUM, production)
        if any(re.search(p, text, re.IGNORECASE) for p in self.financial_patterns.get('aum', [])):
            return BulletCategory.FINANCIAL_METRIC
        if any(re.search(p, text, re.IGNORECASE) for p in self.financial_patterns.get('production', [])):
            return BulletCategory.FINANCIAL_METRIC

        # Check for licenses and certifications
        if any(re.search(p, text, re.IGNORECASE) for p in self.license_patterns):
            return BulletCategory.LICENSES

        # Check for other categories
        text_lower = text.lower()
        if re.search(r'(salary|compensation|pay|earnings|bonus|OTE|base)', text_lower):
            return BulletCategory.COMPENSATION

        if re.search(r'(available|start|begin|notice|immediately)', text_lower):
            return BulletCategory.AVAILABILITY

        if re.search(r'(relocate|move|location|remote|hybrid|mobile)', text_lower):
            return BulletCategory.MOBILITY

        if re.search(r'(degree|university|college|education|MBA|BS|BA|study)', text_lower):
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
                BulletCategory.FINANCIAL_METRIC,
                BulletCategory.GROWTH_ACHIEVEMENT,
                BulletCategory.PERFORMANCE_RANKING,
                BulletCategory.CLIENT_METRIC,
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
        
        # Extract financial achievements from transcript if available
        if transcript:
            achievements = self._extract_skills_from_text(transcript)
            for achievement in achievements[:5]:  # Top 5 achievements
                # Format achievement as proper bullet point
                if achievement.startswith('manages'):
                    bullets.append(achievement.capitalize())
                elif achievement.startswith('production'):
                    bullets.append(f"Annual {achievement}")
                elif achievement.startswith('ranked'):
                    bullets.append(achievement.capitalize())
                else:
                    bullets.append(achievement.capitalize())
        
        # Licenses and certifications
        if candidate_data.get('licenses'):
            for license in candidate_data['licenses'].split(','):
                bullets.append(f"Holds {license.strip()} license")
        
        return bullets
    
    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extract financial achievements and metrics from text"""
        achievements = []

        # Extract AUM/book size metrics
        for pattern in self.financial_patterns['aum']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:2]:  # Limit to top 2 AUM metrics
                if isinstance(match, tuple):
                    achievement = ' '.join(str(m) for m in match if m)
                else:
                    achievement = str(match)
                if achievement and achievement not in achievements:
                    achievements.append(f"manages {achievement}")

        # Extract production metrics
        for pattern in self.financial_patterns['production']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:1]:  # Limit to top production metric
                if isinstance(match, tuple):
                    achievement = ' '.join(str(m) for m in match if m)
                else:
                    achievement = str(match)
                if achievement and achievement not in achievements:
                    achievements.append(f"production: {achievement}")

        # Extract growth achievements
        for pattern in self.financial_patterns['growth']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:1]:  # Limit to top growth metric
                if isinstance(match, tuple):
                    achievement = ' '.join(str(m) for m in match if m)
                else:
                    achievement = str(match)
                if achievement and achievement not in achievements:
                    achievements.append(achievement)

        # Extract rankings
        for pattern in self.ranking_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:1]:  # Limit to top ranking
                if isinstance(match, tuple):
                    achievement = ' '.join(str(m) for m in match if m)
                else:
                    achievement = str(match)
                if achievement and achievement not in achievements:
                    achievements.append(f"ranked {achievement}")

        return achievements[:5]  # Return top 5 achievements
    
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