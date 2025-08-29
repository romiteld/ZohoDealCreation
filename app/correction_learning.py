"""
Correction Learning System with Azure AI Search Integration
Stores user corrections to AI extractions and uses semantic search for pattern matching
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pydantic import BaseModel, Field

# Import Azure AI Search manager
from .azure_ai_search_manager import AzureAISearchManager

logger = logging.getLogger(__name__)


class CorrectionRecord(BaseModel):
    """Record of a user correction to AI extraction"""
    id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    email_domain: str
    original_extraction: Dict[str, Any]
    user_corrections: Dict[str, Any]
    field_corrections: Dict[str, Dict[str, Any]]  # field_name -> {original, corrected}
    email_snippet: Optional[str] = None  # First 500 chars of email for context
    confidence_score: float = Field(default=0.5, description="Confidence in the extraction")
    
    def get_learning_patterns(self) -> List[Dict[str, Any]]:
        """Extract learning patterns from this correction"""
        patterns = []
        for field, correction in self.field_corrections.items():
            if correction['original'] != correction['corrected']:
                patterns.append({
                    'field': field,
                    'pattern_type': 'value_correction',
                    'from_value': correction['original'],
                    'to_value': correction['corrected'],
                    'domain': self.email_domain,
                    'confidence_delta': -0.1  # Reduce confidence when correction needed
                })
        return patterns


class CorrectionLearningService:
    """Service to manage correction learning and AI improvement with Azure AI Search"""
    
    def __init__(self, db_client, use_azure_search: bool = True):
        self.db = db_client
        self.use_azure_search = use_azure_search
        
        # Initialize Azure AI Search if enabled
        self.search_manager = None
        if use_azure_search and os.getenv("AZURE_SEARCH_ENDPOINT"):
            try:
                self.search_manager = AzureAISearchManager()
                logger.info("Azure AI Search integration enabled for correction learning")
            except Exception as e:
                logger.warning(f"Could not initialize Azure AI Search: {e}")
                self.search_manager = None
        
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Ensure correction tables exist in database"""
        try:
            # Create corrections table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS ai_corrections (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ DEFAULT NOW(),
                    email_domain VARCHAR(255),
                    original_extraction JSONB,
                    user_corrections JSONB,
                    field_corrections JSONB,
                    email_snippet TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Create learning patterns table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS learning_patterns (
                    id SERIAL PRIMARY KEY,
                    field_name VARCHAR(100),
                    pattern_type VARCHAR(50),
                    from_value TEXT,
                    to_value TEXT,
                    email_domain VARCHAR(255),
                    frequency INT DEFAULT 1,
                    last_seen TIMESTAMPTZ DEFAULT NOW(),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Create index for faster lookups
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_corrections_domain 
                ON ai_corrections(email_domain)
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_field_domain 
                ON learning_patterns(field_name, email_domain)
            """)
            
            logger.info("Correction learning tables initialized")
            
        except Exception as e:
            logger.warning(f"Could not create correction tables: {e}")
    
    async def store_correction(
        self,
        email_domain: str,
        original_extraction: Dict[str, Any],
        user_corrections: Dict[str, Any],
        email_snippet: Optional[str] = None,
        confidence_score: float = 0.5
    ) -> bool:
        """Store a user correction for learning with Azure AI Search integration"""
        try:
            # Calculate field-level corrections
            field_corrections = {}
            for field in user_corrections.keys():
                original_value = original_extraction.get(field)
                corrected_value = user_corrections.get(field)
                
                if original_value != corrected_value:
                    field_corrections[field] = {
                        'original': original_value,
                        'corrected': corrected_value
                    }
            
            # Store in Azure AI Search if available
            if self.search_manager:
                try:
                    # Index the pattern for semantic search
                    await self.search_manager.index_email_pattern(
                        email_domain=email_domain,
                        email_content=email_snippet or "",
                        extraction_result=original_extraction,
                        corrections=field_corrections,
                        confidence_score=confidence_score
                    )
                    
                    # Update company template
                    await self.search_manager.update_company_template(
                        company_domain=email_domain,
                        extraction_data=original_extraction,
                        corrections=user_corrections
                    )
                except Exception as e:
                    logger.warning(f"Could not store in Azure AI Search: {e}")
            
            # Store correction record in PostgreSQL
            if self.db:
                self.db.execute("""
                    INSERT INTO ai_corrections 
                    (email_domain, original_extraction, user_corrections, field_corrections, email_snippet)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    email_domain,
                    json.dumps(original_extraction),
                    json.dumps(user_corrections),
                    json.dumps(field_corrections),
                    email_snippet[:500] if email_snippet else None
                ))
                
                # Update learning patterns
                for field, correction in field_corrections.items():
                    await self._update_learning_pattern(
                        field_name=field,
                        from_value=correction['original'],
                        to_value=correction['corrected'],
                        email_domain=email_domain
                    )
            
            logger.info(f"Stored correction with {len(field_corrections)} field changes")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store correction: {e}")
            return False
    
    async def _update_learning_pattern(
        self,
        field_name: str,
        from_value: Any,
        to_value: Any,
        email_domain: str
    ):
        """Update or create a learning pattern"""
        try:
            # Check if pattern exists
            result = self.db.execute("""
                SELECT id, frequency FROM learning_patterns
                WHERE field_name = %s 
                AND from_value = %s 
                AND to_value = %s 
                AND email_domain = %s
            """, (field_name, str(from_value), str(to_value), email_domain))
            
            if result:
                # Update frequency
                pattern_id = result[0]['id']
                self.db.execute("""
                    UPDATE learning_patterns 
                    SET frequency = frequency + 1, last_seen = NOW()
                    WHERE id = %s
                """, (pattern_id,))
            else:
                # Create new pattern
                self.db.execute("""
                    INSERT INTO learning_patterns 
                    (field_name, pattern_type, from_value, to_value, email_domain)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    field_name,
                    'value_correction',
                    str(from_value),
                    str(to_value),
                    email_domain
                ))
            
        except Exception as e:
            logger.warning(f"Could not update learning pattern: {e}")
    
    async def get_domain_corrections(
        self,
        email_domain: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent corrections for a domain"""
        try:
            results = self.db.execute("""
                SELECT * FROM ai_corrections
                WHERE email_domain = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (email_domain, limit))
            
            return [dict(r) for r in results] if results else []
            
        except Exception as e:
            logger.warning(f"Could not fetch domain corrections: {e}")
            return []
    
    async def get_common_patterns(
        self,
        email_domain: Optional[str] = None,
        field_name: Optional[str] = None,
        min_frequency: int = 2
    ) -> List[Dict[str, Any]]:
        """Get common correction patterns"""
        try:
            query = """
                SELECT * FROM learning_patterns
                WHERE frequency >= %s
            """
            params = [min_frequency]
            
            if email_domain:
                query += " AND email_domain = %s"
                params.append(email_domain)
            
            if field_name:
                query += " AND field_name = %s"
                params.append(field_name)
            
            query += " ORDER BY frequency DESC, last_seen DESC LIMIT 20"
            
            results = self.db.execute(query, tuple(params))
            
            return [dict(r) for r in results] if results else []
            
        except Exception as e:
            logger.warning(f"Could not fetch learning patterns: {e}")
            return []
    
    async def generate_enhanced_prompt(
        self,
        base_prompt: str,
        email_domain: str,
        email_content: Optional[str] = None
    ) -> str:
        """Enhance AI prompt with historical corrections and semantic patterns"""
        try:
            correction_hints = []
            
            # Use Azure AI Search for semantic pattern matching if available
            if self.search_manager and email_content:
                # Search for similar patterns
                similar_patterns = await self.search_manager.search_similar_patterns(
                    email_content=email_content,
                    email_domain=email_domain,
                    top_k=3,
                    min_confidence=0.6
                )
                
                if similar_patterns:
                    correction_hints.append("Based on similar emails:")
                    for pattern in similar_patterns:
                        # Add corrections from similar patterns
                        corrections = pattern.get('corrections', {})
                        for field, correction in corrections.items():
                            hint = f"- {field}: Often needs correction (confidence: {pattern['confidence_score']:.2f})"
                            correction_hints.append(hint)
                        
                        # Add improvement suggestions
                        for suggestion in pattern.get('improvement_suggestions', [])[:2]:
                            correction_hints.append(f"- {suggestion}")
                
                # Get company template if available
                company_template = await self.search_manager.get_company_template(email_domain)
                if company_template:
                    correction_hints.append(f"\nCompany template ({company_template['company_name']}):")
                    common_fields = company_template.get('common_fields', {})
                    for field, common_values in common_fields.items():
                        if common_values:
                            hint = f"- {field} commonly: {', '.join(common_values[:3])}"
                            correction_hints.append(hint)
            
            # Fallback to database patterns if Azure Search not available
            else:
                # Get common patterns for this domain
                patterns = await self.get_common_patterns(email_domain=email_domain)
                
                if patterns:
                    for pattern in patterns[:5]:  # Use top 5 patterns
                        hint = f"- For {pattern['field_name']}: Users often correct '{pattern['from_value']}' to '{pattern['to_value']}'"
                        correction_hints.append(hint)
                
                # Get recent corrections
                recent_corrections = await self.get_domain_corrections(email_domain, limit=3)
                if recent_corrections:
                    correction_hints.append("\nRecent user corrections from this domain:")
                    for correction in recent_corrections:
                        field_corrections = json.loads(correction['field_corrections'])
                        for field, changes in field_corrections.items():
                            hint = f"- {field}: '{changes['original']}' → '{changes['corrected']}'"
                            correction_hints.append(hint)
            
            # Only enhance if we have corrections to apply
            if not correction_hints:
                return base_prompt
            
            # Enhance prompt
            enhanced_prompt = f"""{base_prompt}

IMPORTANT LEARNING FROM USER CORRECTIONS:
Based on previous user feedback for emails from {email_domain}, please note:
{chr(10).join(correction_hints)}

Apply these learnings to improve accuracy for this extraction."""
            
            return enhanced_prompt
            
        except Exception as e:
            logger.warning(f"Could not enhance prompt: {e}")
            return base_prompt


class FeedbackLoop:
    """Manages the feedback loop between user corrections and AI improvement"""
    
    def __init__(self, correction_service: CorrectionLearningService):
        self.correction_service = correction_service
    
    async def process_user_feedback(
        self,
        email_data: Dict[str, Any],
        ai_extraction: Dict[str, Any],
        user_edits: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process user feedback and store for learning"""
        
        # Extract email domain
        sender_email = email_data.get('sender_email', '')
        email_domain = sender_email.split('@')[1] if '@' in sender_email else 'unknown'
        
        # Store the correction
        await self.correction_service.store_correction(
            email_domain=email_domain,
            original_extraction=ai_extraction,
            user_corrections=user_edits,
            email_snippet=email_data.get('body', '')[:500]
        )
        
        # Return analysis of the correction
        changes = {}
        for field in user_edits.keys():
            if ai_extraction.get(field) != user_edits.get(field):
                changes[field] = {
                    'original': ai_extraction.get(field),
                    'corrected': user_edits.get(field),
                    'change_type': self._classify_change(
                        ai_extraction.get(field),
                        user_edits.get(field)
                    )
                }
        
        return {
            'total_fields': len(user_edits),
            'fields_corrected': len(changes),
            'corrections': changes,
            'learning_stored': True
        }
    
    def _classify_change(self, original: Any, corrected: Any) -> str:
        """Classify the type of change made"""
        if original is None and corrected is not None:
            return 'added_missing'
        elif original is not None and corrected is None:
            return 'removed_incorrect'
        elif original != corrected:
            if isinstance(original, str) and isinstance(corrected, str):
                if original.lower() == corrected.lower():
                    return 'case_correction'
                elif corrected in original or original in corrected:
                    return 'partial_correction'
            return 'value_change'
        return 'no_change'