"""
LangGraph-based email processing manager to replace CrewAI
Using OpenAI agents with LangGraph orchestration
"""

import os
import json
import logging
import asyncio
from typing import Dict, Optional, Any, List, TypedDict, Annotated
import operator
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from app.models import ExtractedData
from dotenv import load_dotenv

# LangGraph imports
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Send

# Cache imports
from app.redis_cache_manager import get_cache_manager
from app.cache_strategies import get_strategy_manager

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


class EmailProcessingState(TypedDict):
    """Main state for email processing workflow"""
    email_content: str
    sender_domain: str
    extraction_result: Optional[Dict[str, Any]]
    company_research: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    final_output: Optional[ExtractedData]
    messages: Annotated[list, add_messages]
    learning_hints: Optional[str]  # Historical corrections to guide extraction


class ExtractionOutput(BaseModel):
    """Structured output for extraction step"""
    candidate_name: Optional[str] = Field(default=None, description="Full name of the job candidate")
    job_title: Optional[str] = Field(default=None, description="Specific role or position")
    location: Optional[str] = Field(default=None, description="Geographical location for the role")
    company_guess: Optional[str] = Field(default=None, description="Company name mentioned in email")
    referrer_name: Optional[str] = Field(default=None, description="Name of the person sending the email or forwarder")
    referrer_email: Optional[str] = Field(default=None, description="Email address of the referrer")
    phone: Optional[str] = Field(default=None, description="Phone number if present")
    email: Optional[str] = Field(default=None, description="Email address of the candidate if different from sender")
    linkedin_url: Optional[str] = Field(default=None, description="LinkedIn profile URL if present")
    notes: Optional[str] = Field(default=None, description="Additional context or notes from the email")


class CompanyResearch(BaseModel):
    """Structured output for company research"""
    company_name: Optional[str] = Field(default=None, description="Official company name")
    company_domain: Optional[str] = Field(default=None, description="Company domain")
    confidence: float = Field(default=0.0, description="Confidence score 0-1")


class EmailProcessingWorkflow:
    def __init__(self, openai_api_key: str = None):
        # Initialize OpenAI/Azure OpenAI client
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_key = os.getenv("AZURE_OPENAI_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
        azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

        if azure_endpoint and azure_key and azure_deployment:
            # Use Azure OpenAI
            base_url = azure_endpoint.rstrip('/') + f"/openai/deployments/{azure_deployment}"
            self.client = AsyncOpenAI(
                api_key=azure_key,
                base_url=base_url,
                default_query={"api-version": azure_api_version}
            )
            self.model_name = azure_deployment  # In Azure, the deployment name is used as model
            logger.info("Azure OpenAI client initialized for LangGraph workflow")
        else:
            # Use OpenAI (non-Azure)
            self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OpenAI API key is required")
            self.client = AsyncOpenAI(api_key=self.api_key)
            # Default to GPT-5-mini if available, else caller may override
            self.model_name = os.getenv("OPENAI_MODEL", "gpt-5-mini")
            logger.info("OpenAI client initialized for LangGraph workflow")
        
        # Build the workflow
        self.graph = self._build_workflow()
        logger.info("LangGraph workflow compiled successfully")
    
    def preprocess_forwarded_email(self, email_content: str) -> tuple[str, bool, Optional[str]]:
        """
        Preprocess email to identify forwarded content and extract forwarder info
        Returns: (processed_content, is_forwarded, forwarder_name)
        """
        import re
        
        # Log the first 500 chars to debug
        logger.info(f"Email content preview (first 500 chars): {email_content[:500]}")
        
        # Common forwarding patterns - more comprehensive list
        forward_patterns = [
            r'-----\s*Original Message\s*-----',
            r'---------- Forwarded message ---------',
            r'Begin forwarded message:',
            r'From:.*\nSent:.*\nTo:.*\nSubject:',
            r'From:.*\nDate:.*\nSubject:',  # Simplified pattern
            r'On .+ wrote:',
            r'> From:.*\n> Date:.*\n> Subject:',
            r'_+\s*\nFrom:',  # Underline separator before From
            r'\*From:\*',  # Bold From: in markdown
            r'From:\s+\S+@\S+',  # Simple From: with email
        ]
        
        is_forwarded = False
        forwarder_name = None
        
        # Check if email is forwarded
        for pattern in forward_patterns:
            match = re.search(pattern, email_content, re.IGNORECASE | re.MULTILINE)
            if match:
                is_forwarded = True
                logger.info(f"Detected forwarded email with pattern: {pattern}")
                logger.info(f"Match found at position {match.start()}: {match.group()[:100]}")
                break
        
        # If forwarded, try to identify the forwarder from the top of the email
        if is_forwarded:
            # Look for sender info at the beginning before the forward marker
            lines = email_content.split('\n')[:10]  # Check first 10 lines
            for line in lines:
                # Look for patterns like "From: Name <email>" or just names before the forward
                from_match = re.match(r'^From:\s*([^<\n]+)', line, re.IGNORECASE)
                if from_match:
                    potential_name = from_match.group(1).strip()
                    # Clean up the name (remove email if present)
                    potential_name = re.sub(r'\s*<.*>', '', potential_name).strip()
                    if potential_name and not '@' in potential_name:
                        forwarder_name = potential_name
                        logger.info(f"Identified forwarder: {forwarder_name}")
                        break
        
        # Add clear markers to help AI understand structure
        if is_forwarded:
            processed_content = f"[FORWARDED EMAIL DETECTED]\n[FORWARDER: {forwarder_name or 'Unknown'}]\n\n{email_content}"
        else:
            processed_content = email_content
        
        return processed_content, is_forwarded, forwarder_name
    
    async def extract_information(self, state: EmailProcessingState) -> Dict:
        """First node: Extract key information from email with learning enhancements"""
        logger.info("---EXTRACTION AGENT---")
        
        email_content = state['email_content']
        sender_domain = state['sender_domain']
        
        # Preprocess for forwarded emails
        processed_content, is_forwarded, forwarder_name = self.preprocess_forwarded_email(email_content)
        if is_forwarded:
            logger.info(f"Processing forwarded email. Forwarder: {forwarder_name}")
            # Use processed content for extraction
            email_content = processed_content
        
        # Initialize learning services for enhanced extraction
        correction_service = None
        learning_analytics = None
        prompt_variant = None
        enhanced_prompt = None
        
        try:
            from app.correction_learning import CorrectionLearningService
            from app.learning_analytics import LearningAnalytics
            
            # Initialize correction service with Azure AI Search
            correction_service = CorrectionLearningService(None, use_azure_search=True)
            
            # Initialize learning analytics and select prompt variant
            learning_analytics = LearningAnalytics(
                search_manager=correction_service.search_manager,
                enable_ab_testing=True
            )
            
            # Select prompt variant for A/B testing
            prompt_variant = learning_analytics.select_prompt_variant(email_domain=sender_domain)
            
            # Get enhanced prompt with historical corrections
            base_prompt = prompt_variant.prompt_template if prompt_variant else ""
            enhanced_prompt = await correction_service.generate_enhanced_prompt(
                base_prompt=base_prompt,
                email_domain=sender_domain,
                email_content=email_content[:1000]
            )
            
            logger.info(f"Using prompt variant: {prompt_variant.variant_name if prompt_variant else 'default'}")
            
        except Exception as e:
            logger.warning(f"Could not initialize learning services: {e}")
        
        # Check cache first
        try:
            cache_manager = await get_cache_manager()
            cached_result = await cache_manager.get_cached_extraction(
                email_content, 
                extraction_type="full"
            )
            
            if cached_result:
                # Use cached result
                extraction_result = cached_result.get("result", {})
                logger.info(f"Using CACHED extraction: {extraction_result}")
                
                return {
                    "extraction_result": extraction_result,
                    "messages": [{"role": "assistant", "content": f"Cached extraction: {extraction_result}"}]
                }
        except Exception as e:
            logger.warning(f"Cache check failed, proceeding without cache: {e}")
        
        # Get learning hints if available
        learning_hints = state.get('learning_hints', '')
        
        # Use enhanced prompt if available, otherwise fall back to default
        if enhanced_prompt:
            system_prompt = enhanced_prompt
        else:
            system_prompt = f"""You are a Senior Data Analyst specializing in recruitment email analysis.
            Extract key recruitment details from the email with high accuracy.
            
            EXTRACTION GUIDELINES:
            1. Extract information that is clearly stated or strongly implied in the email
            2. Use reasonable inference for obvious cases (e.g., email domain often indicates company)
            3. For names, accept variations (First Last, Last First, nicknames)
            4. For locations, accept cities, states, regions, or "Remote"
            5. Return "Unknown" (not null) when information is unclear but attempted
            
            CRITICAL RULES FOR FORWARDED EMAILS:
            - Check if this is a forwarded email (look for "-----Original Message-----", "From:", "Date:", "Subject:", "Begin forwarded message:", etc.)
            - For FORWARDED emails:
              * The person who forwarded the email (top of email) is typically the REFERRER
              * The CANDIDATE information is in the FORWARDED PORTION (the original message)
              * Look for who is being discussed as a potential hire/candidate in the forwarded content
              * The sender of the ORIGINAL forwarded message may be introducing a candidate
            
            IMPORTANT DISTINCTIONS:
            - REFERRER: The person who forwarded/sent you this opportunity (often Steve, Daniel, etc.)
            - CANDIDATE: The actual person being considered for a position (the subject of the discussion)
            - Do NOT confuse the person sending the referral with the candidate being referred
            
            DATA EXTRACTION RULES:
            - Extract information that is clearly stated or reasonably inferred from context
            - If information is unclear, return "Unknown" rather than null
            - candidate_name: The person being discussed as a potential hire (NOT the referrer)
            - referrer_name: The person who forwarded the email or made the introduction
            - email: The CANDIDATE's email address (check signatures, From fields, Calendly links)
            - phone: Extract from email body, signatures, or Calendly link parameters
            - company_name: The CANDIDATE's current company (can infer from email domain if clear)
            - location: City, state, region, or "Remote" (can infer from context like area codes)
            
            CALENDLY EXTRACTION:
            - Look for Calendly URLs (calendly.com)
            - Extract phone numbers from URL parameters (e.g., ?phone=123-456-7890)
            - Extract email from URL parameters (e.g., ?email=john@example.com)
            - Extract name from URL parameters (e.g., ?name=John+Doe)
            
            EXAMPLES OF CORRECT EXTRACTION:
            - If Kathy sends an email about Jerry Fetta: candidate=Jerry Fetta, referrer=Kathy
            - If Steve forwards an email about a consultant: referrer=Steve, candidate=[person discussed in email]
            - If phone/email not in email body but in Calendly link: extract from URL parameters
            
            {learning_hints}
            
            Be accurate but pragmatic. Use reasonable inference where appropriate.
            Return "Unknown" for unclear fields rather than null."""
        
        user_prompt = f"""Analyze this recruitment email and extract the key details:
        
        EMAIL CONTENT:
        {state['email_content']}
        
        IMPORTANT: If this is a forwarded email, make sure to extract information from the forwarded/original message portion.
        Extract and return the information in the required JSON format."""
        
        try:
            # Get the schema and ensure it meets OpenAI's strict requirements
            schema = ExtractionOutput.model_json_schema()
            schema["additionalProperties"] = False
            
            # OpenAI strict mode requires all properties to be in required array
            if "properties" in schema:
                schema["required"] = list(schema["properties"].keys())
                # Ensure nested objects also have additionalProperties: false
                for prop_name, prop_value in schema["properties"].items():
                    if isinstance(prop_value, dict) and prop_value.get("type") == "object":
                        prop_value["additionalProperties"] = False
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "extraction_output",
                        "schema": schema,
                        "strict": True
                    }
                }
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Extraction completed (NEW): {result}")
            
            # Track extraction metrics if learning analytics is available
            if learning_analytics:
                try:
                    import time
                    processing_time = int((time.time() - state.get('start_time', time.time())) * 1000)
                    
                    metric = await learning_analytics.track_extraction(
                        email_domain=sender_domain,
                        extraction_result=result,
                        processing_time_ms=processing_time,
                        prompt_variant_id=prompt_variant.variant_id if prompt_variant else None,
                        used_template=bool(correction_service and correction_service.search_manager and 
                                         await correction_service.search_manager.get_company_template(sender_domain)),
                        pattern_matches=0  # Will be calculated if needed
                    )
                    
                    logger.info(f"Tracked extraction metrics: confidence={metric.overall_confidence:.2f}" if metric else "Metrics tracked")
                except Exception as e:
                    logger.warning(f"Could not track extraction metrics: {e}")
            
            # Cache the result
            try:
                cache_manager = await get_cache_manager()
                strategy_manager = get_strategy_manager()
                
                # Determine caching strategy
                should_cache, ttl, pattern_key = strategy_manager.should_cache(
                    email_content,
                    sender_domain,
                    result
                )
                
                if should_cache:
                    await cache_manager.cache_extraction(
                        email_content,
                        result,
                        extraction_type="full",
                        ttl=ttl
                    )
                    logger.info(f"Cached extraction with TTL: {ttl}")
                    
                    # Also cache pattern if identified
                    if pattern_key:
                        await cache_manager.cache_pattern(pattern_key, result)
                        logger.info(f"Cached pattern: {pattern_key}")
                        
            except Exception as e:
                logger.warning(f"Failed to cache extraction: {e}")
            
            return {
                "extraction_result": result,
                "messages": [{"role": "assistant", "content": f"Extracted: {result}"}]
            }
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {
                "extraction_result": {},
                "messages": [{"role": "assistant", "content": f"Extraction error: {e}"}]
            }
    
    async def research_company(self, state: EmailProcessingState) -> Dict:
        """Second node: Research and verify company information"""
        logger.info("---RESEARCH AGENT---")
        
        extracted = state.get('extraction_result', {})
        company_guess = extracted.get('company_guess')
        candidate_name = extracted.get('candidate_name')
        candidate_email = extracted.get('email')
        candidate_website = extracted.get('website')
        sender_domain = state['sender_domain']
        
        # Use Firecrawl research service with caching
        try:
            from app.firecrawl_research import CompanyResearchService
            from app.redis_cache_manager import RedisCacheManager
            
            research_service = CompanyResearchService()
            cache_manager = RedisCacheManager()
            await cache_manager.connect()
            
            # Determine what to research
            research_domain = None
            
            # Priority 1: Use candidate's website if available
            if candidate_website:
                import re
                domain_match = re.search(r'https?://(?:www\.)?([^/]+)', candidate_website)
                if domain_match:
                    research_domain = domain_match.group(1)
                    logger.info(f"Using candidate website for research: {research_domain}")
            
            # Priority 2: Use candidate's email domain (skip generic domains)
            if not research_domain and candidate_email and '@' in candidate_email:
                email_domain = candidate_email.split('@')[1]
                # Skip generic email domains for company research
                generic_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com', 'icloud.com']
                if email_domain not in generic_domains:
                    research_domain = email_domain
                    logger.info(f"Using candidate email domain for research: {research_domain}")
                else:
                    logger.info(f"Skipping generic email domain: {email_domain}")
            
            # Search for candidate information if we have a name
            candidate_info = {}
            if candidate_name:
                logger.info(f"Searching for candidate information: {candidate_name}")
                # If we have a name like "Jerry Fetta", also search for domain like "jerryfetta.com"
                candidate_info = await research_service.search_candidate_info(candidate_name, company_guess)
                
                # Update extracted info with found data
                if candidate_info:
                    logger.info(f"Found candidate info via Firecrawl: {candidate_info}")
                    # Use found website for company research if available
                    if candidate_info.get('website') and not research_domain:
                        import re
                        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', candidate_info['website'])
                        if domain_match:
                            research_domain = domain_match.group(1)
            
            # Research the company using the best available domain
            if research_domain:
                # Check cache first
                cached_info = await cache_manager.get_domain_info(research_domain)
                if cached_info:
                    logger.info(f"Using cached domain info for: {research_domain}")
                    research_result = cached_info
                else:
                    # Fetch from Firecrawl
                    research_result = await research_service.research_company(
                        email_domain=research_domain,
                        company_guess=company_guess
                    )
                    # Cache the result
                    if research_result and research_result.get('confidence', 0) > 0.5:
                        await cache_manager.cache_domain_info(research_domain, research_result)
            else:
                # Fallback to sender domain
                cached_info = await cache_manager.get_domain_info(sender_domain)
                if cached_info:
                    logger.info(f"Using cached domain info for: {sender_domain}")
                    research_result = cached_info
                else:
                    research_result = await research_service.research_company(
                        email_domain=sender_domain,
                        company_guess=company_guess
                    )
                    # Cache if good confidence
                    if research_result and research_result.get('confidence', 0) > 0.5:
                        await cache_manager.cache_domain_info(sender_domain, research_result)
            
            # If we found a website through candidate search, use it for company info
            if candidate_info.get('website'):
                # Extract company name from personal website if it's there
                logger.info(f"Using candidate website for company info: {candidate_info['website']}")
                # Update research result with website
                research_result['website'] = candidate_info['website']
            
            # Merge candidate info into research result
            research_result.update(candidate_info)
            
            logger.info(f"Research completed with Firecrawl: {research_result}")
            
            return {
                "company_research": research_result,
                "messages": [{"role": "assistant", "content": f"Researched: {research_result}"}]
            }
            
        except Exception as e:
            logger.warning(f"Firecrawl research failed: {e}, using fallback")
            
            # Fallback logic
            company_name = company_guess
            confidence = 0.0
            
            if company_guess:
                confidence = 0.7
            elif sender_domain:
                # Clean domain to get company name
                domain_parts = sender_domain.split('.')
                if domain_parts:
                    company_name = domain_parts[0].replace('-', ' ').title()
                    confidence = 0.4
            
            research_result = {
                "company_name": company_name,
                "company_domain": sender_domain,
                "confidence": confidence,
                "source": "fallback"
            }
            
            logger.info(f"Research completed with fallback: {research_result}")
            
            return {
                "company_research": research_result,
                "messages": [{"role": "assistant", "content": f"Researched: {research_result}"}]
            }
    
    async def validate_and_clean(self, state: EmailProcessingState) -> Dict:
        """Third node: Validate and clean the extracted data"""
        logger.info("---VALIDATION AGENT---")
        
        extracted = state.get('extraction_result', {})
        research = state.get('company_research', {})
        
        # Enhanced Calendly data extraction
        phone = extracted.get('phone')
        email = extracted.get('email')
        calendly_url = extracted.get('calendly_url')
        
        if calendly_url:
            import re
            import urllib.parse
            
            # Try to extract ALL data from Calendly URL parameters
            # Common patterns: ?phone=xxx&email=xxx&name=xxx
            # or answer_1=phone&answer_2=email patterns
            
            # Extract phone if not already found
            if not phone:
                phone_patterns = [
                    r'phone=([0-9\-\+\(\)\s]+)',
                    r'answer_\d+=([0-9\-\+\(\)\s]+)',  # Sometimes phone in answer fields
                    r'a\d+=([0-9\-\+\(\)\s]+)'  # Shortened form
                ]
                for pattern in phone_patterns:
                    phone_match = re.search(pattern, calendly_url)
                    if phone_match:
                        phone = urllib.parse.unquote(phone_match.group(1))
                        # Store in extracted data to preserve it
                        if not extracted.get('phone'):
                            extracted['phone'] = phone
                        logger.info(f"Extracted phone from Calendly: {phone}")
                        break
            
            # Extract email if not already found  
            if not email:
                email_patterns = [
                    r'email=([^&]+)',
                    r'invitee_email=([^&]+)',
                    r'answer_\d+=([^&]*@[^&]+)'  # Email in answer fields
                ]
                for pattern in email_patterns:
                    email_match = re.search(pattern, calendly_url)
                    if email_match:
                        email = urllib.parse.unquote(email_match.group(1))
                        # Store in extracted data to preserve it
                        if not extracted.get('email'):
                            extracted['email'] = email
                        logger.info(f"Extracted email from Calendly: {email}")
                        break
            
            # Extract name if not already found
            if not extracted.get('candidate_name'):
                name_patterns = [
                    r'name=([^&]+)',
                    r'invitee_full_name=([^&]+)',
                    r'first_name=([^&]+).*last_name=([^&]+)'
                ]
                for pattern in name_patterns:
                    name_match = re.search(pattern, calendly_url)
                    if name_match:
                        if len(name_match.groups()) == 2:
                            # First and last name
                            extracted['candidate_name'] = f"{urllib.parse.unquote(name_match.group(1))} {urllib.parse.unquote(name_match.group(2))}"
                        else:
                            extracted['candidate_name'] = urllib.parse.unquote(name_match.group(1))
                        logger.info(f"Extracted name from Calendly: {extracted['candidate_name']}")
                        break
        
        # Determine source based on business rules
        source = "Email Inbound"  # Default
        source_detail = None
        
        if extracted.get('referrer_name') or extracted.get('referrer_email'):
            source = "Referral"
            source_detail = extracted.get('referrer_name')
        elif calendly_url:
            source = "Website Inbound"
        
        # Merge extraction with research - use Firecrawl data to fill missing fields
        validated_data = {
            "candidate_name": extracted.get('candidate_name'),
            "job_title": extracted.get('job_title'),
            "location": extracted.get('location'),
            # Don't use research company if it's generic like "Example" or domain-based guesses
            "company_name": (
                extracted.get('company_guess') or 
                (research.get('company_name') if research.get('confidence', 0) > 0.7 else None)
            ),
            "referrer_name": extracted.get('referrer_name'),
            "referrer_email": extracted.get('referrer_email'),
            # Prioritize extracted email (including from Calendly), fallback to Firecrawl research
            "email": extracted.get('email') or research.get('email'),
            # Prioritize extracted phone (including from Calendly), fallback to Firecrawl research
            "phone": extracted.get('phone') or research.get('phone'),
            # Prioritize extracted LinkedIn, fallback to Firecrawl research
            "linkedin_url": extracted.get('linkedin_url') or research.get('linkedin_url'),
            "notes": extracted.get('notes'),
            # Use Firecrawl website if found
            "website": research.get('website') or research.get('company_domain'),
            "industry": research.get('industry'),  # From research if available
            "source": source,
            "source_detail": source_detail
        }
        
        # Clean and standardize
        for key, value in validated_data.items():
            if value and isinstance(value, str):
                # Clean whitespace and standardize
                validated_data[key] = value.strip()
                # Capitalize names properly
                if key in ['candidate_name', 'referrer_name', 'company_name', 'source_detail']:
                    validated_data[key] = ' '.join(word.capitalize() for word in value.split())
                # Clean URLs
                if key in ['linkedin_url', 'calendly_url', 'website']:
                    # Ensure URLs are properly formatted
                    if value and not value.startswith(('http://', 'https://')):
                        validated_data[key] = f"https://{value}"
        
        logger.info(f"Validation completed: {validated_data}")
        
        # Convert to ExtractedData model
        try:
            final_output = ExtractedData(**validated_data)
        except Exception as e:
            logger.error(f"Failed to create ExtractedData: {e}")
            final_output = ExtractedData()
        
        return {
            "validation_result": validated_data,
            "final_output": final_output,
            "messages": [{"role": "assistant", "content": f"Validated: {validated_data}"}]
        }
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create the graph
        workflow = StateGraph(EmailProcessingState)
        
        # Add nodes
        workflow.add_node("extract", self.extract_information)
        workflow.add_node("research", self.research_company)
        workflow.add_node("validate", self.validate_and_clean)
        
        # Add edges to create sequential flow
        workflow.add_edge(START, "extract")
        workflow.add_edge("extract", "research")
        workflow.add_edge("research", "validate")
        workflow.add_edge("validate", END)
        
        # Compile the workflow
        return workflow.compile()
    
    async def process_email(self, email_body: str, sender_domain: str, learning_hints: str = None, calendly_url: str = None) -> ExtractedData:
        """Main entry point to process an email with optional learning hints"""
        
        logger.info(f"Starting LangGraph email processing for domain: {sender_domain}")
        
        # Initial state
        initial_state = {
            "email_content": email_body,
            "sender_domain": sender_domain,
            "extraction_result": None,
            "company_research": None,
            "validation_result": None,
            "final_output": None,
            "messages": [],
            "learning_hints": learning_hints or ""
        }
        
        try:
            # Run the workflow
            result = await self.graph.ainvoke(initial_state)

            # Extract the final output
            final_output = result.get("final_output") or ExtractedData()

            # Calendly enrichment (best-effort)
            try:
                url = calendly_url or self._extract_calendly_url(email_body)
                if url:
                    extra = await self._enrich_from_calendly(url)
                    for k, v in (extra or {}).items():
                        if hasattr(final_output, k) and v:
                            setattr(final_output, k, v)
            except Exception:
                pass

            logger.info(f"LangGraph processing successful: {final_output}")
            return final_output
                
        except Exception as e:
            logger.error(f"LangGraph processing failed: {e}")
            return ExtractedData()


# Backwards compatibility wrapper
class EmailProcessingCrew:
    """Compatibility wrapper to match CrewAI interface"""
    
    def __init__(self, serper_api_key: str = None):
        self.workflow = EmailProcessingWorkflow()
        logger.info("EmailProcessingCrew initialized with LangGraph backend")
    
    def run(self, email_body: str, sender_domain: str) -> ExtractedData:
        """Synchronous wrapper for compatibility"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a task
            task = asyncio.create_task(
                self.workflow.process_email(email_body, sender_domain)
            )
            return asyncio.run_until_complete(task)
        else:
            # Create new event loop
            return asyncio.run(self.workflow.process_email(email_body, sender_domain))
    
    async def run_async(self, email_body: str, sender_domain: str) -> ExtractedData:
        """Async method matching CrewAI interface"""
        return await self.workflow.process_email(email_body, sender_domain)

    def _extract_calendly_url(self, text: str) -> str:
        import re
        m = re.search(r"https?://(?:www\.)?calendly\.com/[\w\-/.?=&]+", text, re.IGNORECASE)
        return m.group(0) if m else None

    async def _enrich_from_calendly(self, url: str) -> dict:
        try:
            import aiohttp, re
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as resp:  # Reduced from 5s to 3s
                    if resp.status != 200:
                        return {}
                    html = await resp.text()
            phone = re.search(r"(\+?\d[\d\s().-]{7,}\d)", html)
            email = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", html)
            return {
                "phone": phone.group(0) if phone else None,
                "candidate_email": email.group(0) if email else None
            }
        except Exception:
            return {}


# Simple fallback extractor (unchanged)
class SimplifiedEmailExtractor:
    """Fallback email extractor when LangGraph is not available."""
    
    @staticmethod
    def extract(email_body: str, sender_email: str) -> ExtractedData:
        """Extract basic information from email using pattern matching."""
        # Extract sender domain for company inference
        domain = sender_email.split('@')[1] if '@' in sender_email else ''
        company_name = domain.split('.')[0].title() if domain else None
        
        # Basic extraction logic (fallback when AI fails)
        return ExtractedData(
            candidate_name=None,
            job_title=None,
            location=None,
            company_name=company_name,
            referrer_name=None
        )