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


class ExtractionOutput(BaseModel):
    """Structured output for extraction step"""
    candidate_name: Optional[str] = Field(default=None, description="Full name of the job candidate")
    job_title: Optional[str] = Field(default=None, description="Specific role or position")
    location: Optional[str] = Field(default=None, description="Geographical location for the role")
    company_guess: Optional[str] = Field(default=None, description="Company name mentioned in email")
    referrer_name: Optional[str] = Field(default=None, description="Name of the person sending the email")


class CompanyResearch(BaseModel):
    """Structured output for company research"""
    company_name: Optional[str] = Field(default=None, description="Official company name")
    company_domain: Optional[str] = Field(default=None, description="Company domain")
    confidence: float = Field(default=0.0, description="Confidence score 0-1")


class EmailProcessingWorkflow:
    def __init__(self, openai_api_key: str = None):
        # Initialize OpenAI client
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        logger.info("OpenAI client initialized for LangGraph workflow")
        
        # Build the workflow
        self.graph = self._build_workflow()
        logger.info("LangGraph workflow compiled successfully")
    
    async def extract_information(self, state: EmailProcessingState) -> Dict:
        """First node: Extract key information from email"""
        logger.info("---EXTRACTION AGENT---")
        
        system_prompt = """You are a Senior Data Analyst specializing in recruitment email analysis.
        Extract key recruitment details from the email with extreme accuracy.
        Focus on identifying:
        1. Candidate name - the person being referred for the job
        2. Job title - the specific position mentioned
        3. Location - city and state if available
        4. Company name - any company explicitly mentioned
        5. Referrer name - the person sending the email
        
        Be precise and avoid assumptions."""
        
        user_prompt = f"""Analyze this recruitment email and extract the key details:
        
        EMAIL CONTENT:
        {state['email_content']}
        
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
                model="gpt-5-mini",  # Using GPT-5-mini as per requirement
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
            logger.info(f"Extraction completed: {result}")
            
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
        sender_domain = state['sender_domain']
        
        # Use Firecrawl research service
        try:
            from app.firecrawl_research import CompanyResearchService
            research_service = CompanyResearchService()
            
            # Research the company using multiple strategies
            research_result = await research_service.research_company(
                email_domain=sender_domain,
                company_guess=company_guess
            )
            
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
        
        # Merge extraction with research
        validated_data = {
            "candidate_name": extracted.get('candidate_name'),
            "job_title": extracted.get('job_title'),
            "location": extracted.get('location'),
            "company_name": research.get('company_name') or extracted.get('company_guess'),
            "referrer_name": extracted.get('referrer_name')
        }
        
        # Clean and standardize
        for key, value in validated_data.items():
            if value and isinstance(value, str):
                # Clean whitespace and standardize
                validated_data[key] = value.strip()
                # Capitalize names properly
                if key in ['candidate_name', 'referrer_name', 'company_name']:
                    validated_data[key] = ' '.join(word.capitalize() for word in value.split())
        
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
    
    async def process_email(self, email_body: str, sender_domain: str) -> ExtractedData:
        """Main entry point to process an email"""
        
        logger.info(f"Starting LangGraph email processing for domain: {sender_domain}")
        
        # Initial state
        initial_state = {
            "email_content": email_body,
            "sender_domain": sender_domain,
            "extraction_result": None,
            "company_research": None,
            "validation_result": None,
            "final_output": None,
            "messages": []
        }
        
        try:
            # Run the workflow
            result = await self.graph.ainvoke(initial_state)
            
            # Extract the final output
            final_output = result.get("final_output")
            
            if final_output:
                logger.info(f"LangGraph processing successful: {final_output}")
                return final_output
            else:
                logger.error("No final output from LangGraph workflow")
                return ExtractedData()
                
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