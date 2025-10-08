"""
LangExtract-based Email Extractor for Enhanced Structured Data Extraction
Provides Google's LangExtract integration with source grounding and visualization
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import hashlib

# LangExtract imports
import langextract as lx
from langextract.config import ModelProvider

# Local imports
from app.models import ExtractedData
from well_shared.cache.redis_manager import get_cache_manager

logger = logging.getLogger(__name__)


class LangExtractEmailExtractor:
    """
    Enhanced email extractor using Google's LangExtract library.
    Provides source grounding, multi-pass extraction, and visualization.
    """
    
    def __init__(self, model_provider: str = "openai", model_id: str = None):
        """
        Initialize LangExtract email extractor.
        
        Args:
            model_provider: Provider name (openai, gemini, ollama)
            model_id: Specific model identifier (uses config if None)
        """
        # Load configuration
        from app.config_manager import get_extraction_config
        self.config = get_extraction_config()
        
        self.model_provider = model_provider
        self.model_id = model_id or self.config.langextract_model
        
        # Configure model based on environment
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        # Azure OpenAI configuration
        self.azure_openai_endpoint = self.config.azure_openai_endpoint
        self.azure_openai_api_key = self.config.azure_openai_api_key
        self.azure_openai_api_version = self.config.azure_openai_api_version
        self.azure_openai_deployment = self.config.azure_openai_deployment
        self.use_azure_openai = self.config.use_azure_openai
        
        # Extraction schema definition
        self.extraction_schema = {
            "candidate_name": {
                "type": "string",
                "description": "Full name of the candidate/person seeking employment",
                "required": True
            },
            "job_title": {
                "type": "string", 
                "description": "Job title or position being sought (e.g., 'Financial Advisor', 'Senior Developer')",
                "required": False
            },
            "location": {
                "type": "string",
                "description": "Geographic location for the role or candidate (city, state format)",
                "required": False
            },
            "company_name": {
                "type": "string",
                "description": "Official name of the candidate's current or target company",
                "required": False
            },
            "referrer_name": {
                "type": "string",
                "description": "Full name of the person making the referral",
                "required": False
            },
            "referrer_email": {
                "type": "string",
                "description": "Email address of the referrer",
                "required": False
            },
            "email": {
                "type": "string",
                "description": "Candidate's email address",
                "required": False
            },
            "phone": {
                "type": "string",
                "description": "Contact phone number",
                "required": False
            },
            "linkedin_url": {
                "type": "string",
                "description": "LinkedIn profile URL",
                "required": False
            },
            "website": {
                "type": "string",
                "description": "Company or personal website URL",
                "required": False
            },
            "industry": {
                "type": "string",
                "description": "Industry or business sector",
                "required": False
            },
            "notes": {
                "type": "string",
                "description": "Additional context, background, or important details from the email",
                "required": False
            }
        }
        
        # Few-shot examples for training
        self.training_examples = [
            {
                "input": """
                Hi,
                
                I wanted to introduce you to Sarah Johnson, a Financial Advisor based in Austin, Texas. 
                She's currently with Merrill Lynch and has been looking for new opportunities.
                
                You can reach her at sarah.j@email.com or 512-555-0123.
                Her LinkedIn is linkedin.com/in/sarahjohnson-fa
                
                Best regards,
                Mike Stevens
                mike@referrals.com
                """,
                "output": {
                    "candidate_name": "Sarah Johnson",
                    "job_title": "Financial Advisor", 
                    "location": "Austin, Texas",
                    "company_name": "Merrill Lynch",
                    "referrer_name": "Mike Stevens",
                    "referrer_email": "mike@referrals.com",
                    "email": "sarah.j@email.com",
                    "phone": "512-555-0123",
                    "linkedin_url": "linkedin.com/in/sarahjohnson-fa",
                    "notes": "Looking for new opportunities"
                }
            },
            {
                "input": """
                Subject: Candidate Introduction - Senior Developer Position
                
                Hello,
                
                I'm writing to introduce David Chen, who is interested in senior developer roles.
                David has 8 years of experience and is currently at Google in Mountain View.
                He specializes in Python and machine learning.
                
                Contact: d.chen.dev@gmail.com
                
                Thanks,
                Jennifer Walsh
                """,
                "output": {
                    "candidate_name": "David Chen",
                    "job_title": "Senior Developer",
                    "location": "Mountain View",
                    "company_name": "Google", 
                    "referrer_name": "Jennifer Walsh",
                    "email": "d.chen.dev@gmail.com",
                    "notes": "8 years experience, Python and machine learning specialist"
                }
            }
        ]
        
        # Performance metrics
        self.stats = {
            "extractions_performed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_extraction_time_ms": 0,
            "source_groundings_found": 0,
            "validation_passes": 0,
            "errors": []
        }
    
    async def extract_from_email(self, 
                                email_content: str, 
                                sender_domain: str = None,
                                use_cache: bool = True,
                                enable_visualization: bool = False) -> Tuple[ExtractedData, Dict[str, Any]]:
        """
        Extract structured data from email using LangExtract.
        
        Args:
            email_content: Raw email text
            sender_domain: Sender's domain for context
            use_cache: Whether to use Redis caching
            enable_visualization: Generate HTML visualization
            
        Returns:
            Tuple of (ExtractedData, metadata_dict)
        """
        start_time = datetime.now()
        self.stats["extractions_performed"] += 1
        
        try:
            # Check cache first
            if use_cache:
                cached_result = await self._check_cache(email_content)
                if cached_result:
                    self.stats["cache_hits"] += 1
                    logger.info("Using cached LangExtract result")
                    return cached_result["extracted_data"], cached_result["metadata"]
            
            self.stats["cache_misses"] += 1
            
            # Prepare LangExtract configuration
            model_config = self._get_model_config()
            
            # Enhanced prompt with domain context
            prompt_description = self._build_extraction_prompt(sender_domain)
            
            # Perform extraction with LangExtract
            logger.info(f"Starting LangExtract extraction for domain: {sender_domain}")
            
            # Configure extraction parameters based on Azure OpenAI vs standard OpenAI
            extraction_params = {
                "text_or_documents": email_content,
                "prompt_description": prompt_description,
                "examples": self.training_examples,
                "model_id": self.model_id,
                "model_provider": model_config,
                "schema": self.extraction_schema,
                "enable_source_grounding": True,
                "max_workers": 1,  # Sequential for consistency
                "chunk_size": 2000,  # Handle long emails
                "enable_validation": True
            }
            
            # Add Azure OpenAI specific configuration if enabled
            if self.use_azure_openai and self.azure_openai_endpoint:
                extraction_params.update({
                    "azure_endpoint": self.azure_openai_endpoint,
                    "azure_api_key": self.azure_openai_api_key,
                    "azure_api_version": self.azure_openai_api_version,
                    "azure_deployment": self.azure_openai_deployment
                })
                logger.info(f"Using Azure OpenAI endpoint: {self.azure_openai_endpoint} with deployment: {self.azure_openai_deployment}")
            else:
                logger.info("Using standard OpenAI configuration")
            
            result = lx.extract(**extraction_params)
            
            # Process LangExtract results
            extracted_data, metadata = await self._process_langextract_result(
                result, 
                email_content,
                enable_visualization
            )
            
            # Cache the result
            if use_cache:
                await self._cache_result(email_content, extracted_data, metadata)
            
            # Update statistics
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_stats(processing_time, metadata)
            
            logger.info(f"LangExtract extraction completed in {processing_time:.2f}ms")
            
            return extracted_data, metadata
            
        except Exception as e:
            error_msg = f"LangExtract extraction failed: {str(e)}"
            logger.error(error_msg)
            self.stats["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "sender_domain": sender_domain
            })
            
            # Fallback to basic extraction
            return await self._fallback_extraction(email_content), {"error": error_msg}
    
    def _get_model_config(self) -> ModelProvider:
        """Configure the model provider for LangExtract."""
        if self.model_provider == "openai":
            return ModelProvider.OPENAI
        elif self.model_provider == "gemini":
            return ModelProvider.GEMINI
        elif self.model_provider == "ollama":
            return ModelProvider.OLLAMA
        else:
            return ModelProvider.OPENAI  # Default fallback
    
    def _build_extraction_prompt(self, sender_domain: str = None) -> str:
        """Build enhanced extraction prompt with domain context."""
        base_prompt = """
        Extract recruitment information from this email with high precision.

        Focus on identifying:
        1. The candidate (person seeking employment or being referred)
        2. Their professional details (title, company, location)
        3. Contact information (email, phone, LinkedIn)
        4. Any referrer information
        5. Additional context or notes

        CRITICAL RULES:
        - Extract ONLY specific values, not descriptions
        - For candidate_name: Extract the person's full name only
        - For job_title: Extract the specific role/title only
        - For location: Extract the CANDIDATE'S location (city, state format) - NOT the referrer's location
        - For company_name: Extract the CANDIDATE'S current company only - NOT the referrer's company
        - For referrer_name: Extract the REFERRER'S name (person making the introduction)
        - For referrer_email: Extract the REFERRER'S email address
        - Be precise and avoid extracting surrounding text
        - IMPORTANT: Do not confuse the referrer's information with the candidate's information
        - The candidate is the person being recommended for a job
        - The referrer is the person making the recommendation
        """
        
        # Add domain-specific context if available
        if sender_domain:
            domain_context = f"""
            
            DOMAIN CONTEXT: This email is from {sender_domain}
            - Adjust extraction based on known patterns from this domain
            - Pay attention to company-specific formats or terminology
            """
            base_prompt += domain_context
        
        return base_prompt
    
    async def _process_langextract_result(self, 
                                        result: Any, 
                                        original_email: str,
                                        enable_visualization: bool = False) -> Tuple[ExtractedData, Dict[str, Any]]:
        """Process and validate LangExtract extraction results."""
        
        try:
            # Extract the main data
            extracted_dict = {}
            source_groundings = {}
            confidence_scores = {}
            
            # LangExtract returns structured results with source grounding
            if hasattr(result, 'extractions') and result.extractions:
                for extraction in result.extractions:
                    field_name = extraction.get('field', '')
                    field_value = extraction.get('value', '')
                    source_span = extraction.get('source_span', {})
                    confidence = extraction.get('confidence', 0.0)
                    
                    if field_name and field_value:
                        extracted_dict[field_name] = field_value
                        source_groundings[field_name] = source_span
                        confidence_scores[field_name] = confidence
                        
                        self.stats["source_groundings_found"] += 1
            
            # Convert to ExtractedData model
            extracted_data = ExtractedData(**extracted_dict)
            
            # Build metadata
            metadata = {
                "extraction_method": "langextract",
                "model_provider": self.model_provider,
                "model_id": self.model_id,
                "source_groundings": source_groundings,
                "confidence_scores": confidence_scores,
                "total_extractions": len(extracted_dict),
                "avg_confidence": sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0.0,
                "timestamp": datetime.now().isoformat()
            }
            
            # Generate visualization if requested
            if enable_visualization:
                try:
                    visualization_html = await self._generate_visualization(
                        original_email, 
                        extracted_dict, 
                        source_groundings
                    )
                    metadata["visualization_html"] = visualization_html
                except Exception as e:
                    logger.warning(f"Visualization generation failed: {e}")
            
            return extracted_data, metadata
            
        except Exception as e:
            logger.error(f"Error processing LangExtract result: {e}")
            # Return minimal fallback
            return ExtractedData(), {"error": str(e), "extraction_method": "langextract_fallback"}
    
    async def _generate_visualization(self, 
                                    email_content: str, 
                                    extractions: Dict[str, str],
                                    source_groundings: Dict[str, Dict]) -> str:
        """Generate interactive HTML visualization of extractions with source grounding."""
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>LangExtract Email Analysis</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .email-content {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .extraction-item {{ margin: 10px 0; padding: 10px; border-left: 3px solid #007acc; }}
                .field-name {{ font-weight: bold; color: #007acc; }}
                .field-value {{ margin-left: 10px; }}
                .source-highlight {{ background-color: yellow; padding: 2px; }}
                .confidence {{ font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <h2>LangExtract Email Analysis Results</h2>
            
            <h3>Original Email:</h3>
            <div class="email-content">
                {email_content}
            </div>
            
            <h3>Extracted Data:</h3>
            <div class="extractions">
        """
        
        for field, value in extractions.items():
            confidence = source_groundings.get(field, {}).get('confidence', 0.0)
            html_template += f"""
                <div class="extraction-item">
                    <span class="field-name">{field}:</span>
                    <span class="field-value">{value}</span>
                    <span class="confidence">(confidence: {confidence:.2f})</span>
                </div>
            """
        
        html_template += """
            </div>
            
            <h3>Source Grounding:</h3>
            <p>Highlighted sections show where each piece of data was extracted from the original email.</p>
            
        </body>
        </html>
        """
        
        return html_template
    
    async def _check_cache(self, email_content: str) -> Optional[Dict[str, Any]]:
        """Check Redis cache for existing extraction results."""
        try:
            cache_manager = await get_cache_manager()
            cache_key = f"langextract:{hashlib.md5(email_content.encode()).hexdigest()}"
            
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            
        except Exception as e:
            logger.debug(f"Cache check failed: {e}")
        
        return None
    
    async def _cache_result(self, 
                          email_content: str, 
                          extracted_data: ExtractedData, 
                          metadata: Dict[str, Any]) -> None:
        """Cache extraction results in Redis."""
        try:
            cache_manager = await get_cache_manager()
            cache_key = f"langextract:{hashlib.md5(email_content.encode()).hexdigest()}"
            
            cache_data = {
                "extracted_data": extracted_data.model_dump() if hasattr(extracted_data, 'model_dump') else extracted_data.__dict__,
                "metadata": metadata,
                "cached_at": datetime.now().isoformat()
            }
            
            # Cache for 24 hours
            await cache_manager.set(cache_key, json.dumps(cache_data), expire=86400)
            
        except Exception as e:
            logger.debug(f"Caching failed: {e}")
    
    async def _fallback_extraction(self, email_content: str) -> ExtractedData:
        """Fallback extraction when LangExtract fails."""
        logger.warning("Using fallback extraction method")
        
        # Basic regex-based extraction as fallback
        import re
        
        # Try to extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, email_content)
        
        # Try to extract phone numbers
        phone_pattern = r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b'
        phones = re.findall(phone_pattern, email_content)
        
        return ExtractedData(
            email=emails[0] if emails else None,
            phone=phones[0] if phones else None,
            notes="Fallback extraction - LangExtract failed"
        )
    
    def _update_stats(self, processing_time_ms: float, metadata: Dict[str, Any]) -> None:
        """Update performance statistics."""
        # Update average processing time
        current_avg = self.stats["avg_extraction_time_ms"]
        total_extractions = self.stats["extractions_performed"]
        
        self.stats["avg_extraction_time_ms"] = (
            (current_avg * (total_extractions - 1) + processing_time_ms) / total_extractions
        )
        
        # Update other metrics
        if "source_groundings" in metadata:
            self.stats["source_groundings_found"] += len(metadata["source_groundings"])
        
        self.stats["validation_passes"] += 1
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        return {
            **self.stats,
            "cache_hit_rate": (
                self.stats["cache_hits"] / max(1, self.stats["cache_hits"] + self.stats["cache_misses"]) * 100
            ),
            "avg_source_groundings_per_extraction": (
                self.stats["source_groundings_found"] / max(1, self.stats["extractions_performed"])
            )
        }
    
    async def compare_with_baseline(self, 
                                  email_content: str, 
                                  baseline_result: ExtractedData) -> Dict[str, Any]:
        """Compare LangExtract results with baseline extraction method."""
        
        langextract_result, metadata = await self.extract_from_email(email_content)
        
        # Field-by-field comparison
        comparison = {
            "langextract_result": langextract_result.model_dump() if hasattr(langextract_result, 'model_dump') else langextract_result.__dict__,
            "baseline_result": baseline_result.model_dump() if hasattr(baseline_result, 'model_dump') else baseline_result.__dict__,
            "field_differences": {},
            "metadata": metadata,
            "comparison_timestamp": datetime.now().isoformat()
        }
        
        # Compare each field
        for field in self.extraction_schema.keys():
            langextract_value = getattr(langextract_result, field, None)
            baseline_value = getattr(baseline_result, field, None)
            
            if langextract_value != baseline_value:
                comparison["field_differences"][field] = {
                    "langextract": langextract_value,
                    "baseline": baseline_value,
                    "confidence": metadata.get("confidence_scores", {}).get(field, 0.0)
                }
        
        comparison["total_differences"] = len(comparison["field_differences"])
        comparison["agreement_rate"] = (
            (len(self.extraction_schema) - len(comparison["field_differences"])) / 
            len(self.extraction_schema) * 100
        )
        
        return comparison


# Global instance
_langextract_extractor: Optional[LangExtractEmailExtractor] = None


def get_langextract_extractor() -> LangExtractEmailExtractor:
    """Get or create global LangExtract extractor instance."""
    global _langextract_extractor
    
    if _langextract_extractor is None:
        # Load configuration to get correct model and provider
        from app.config_manager import get_extraction_config
        config = get_extraction_config()
        
        # Use Azure OpenAI if configured, otherwise fallback to standard OpenAI
        provider = "azure" if config.use_azure_openai else "openai"
        model_id = config.langextract_model or "gpt-5-mini"
        
        _langextract_extractor = LangExtractEmailExtractor(
            model_provider=provider,
            model_id=model_id
        )
    
    return _langextract_extractor