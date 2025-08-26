import os
import json
import logging
import asyncio
import re
from typing import Dict, Optional, Any, List
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from app.models import ExtractedData
from app.custom_llm import ChatOpenAIWithoutStop  # Import our custom LLM
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()  # Fallback to .env if .env.local doesn't exist

logger = logging.getLogger(__name__)

# Import proper CrewAI tools
try:
    from crewai_tools import SerperDevTool
    CREWAI_TOOLS_AVAILABLE = True
    logger.info("crewai_tools imported successfully")
except ImportError:
    logger.warning("crewai_tools not available, web search will be disabled")
    CREWAI_TOOLS_AVAILABLE = False


class EmailProcessingCrew:
    def __init__(self, serper_api_key: str = None):
        # Serper API key from environment if not provided
        self.serper_api_key = serper_api_key or os.getenv("SERPER_API_KEY")
        
        # Log Serper API key status
        if self.serper_api_key:
            logger.info(f"Serper API key configured (length: {len(self.serper_api_key)})")
        else:
            logger.warning("Serper API key not found in environment")
        
        # Initialize LLM with GPT-5, using custom class to handle stop parameter
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY not found in environment")
                raise ValueError("OPENAI_API_KEY is required")
            
            # Initialize with custom ChatOpenAI class that removes stop parameter
            model_name = os.getenv("OPENAI_MODEL", "gpt-5")
            
            # Use the custom ChatOpenAI wrapper that handles stop parameter removal
            self.llm = ChatOpenAIWithoutStop(
                model_name=model_name,  # Use model_name parameter
                temperature=1,  # Required for GPT-5 models
                api_key=api_key,
                max_retries=2,
                timeout=30,
                streaming=False  # Disable streaming for GPT-5 (requires organization verification)
            )
            logger.info(f"LLM initialized successfully with ChatOpenAIWithoutStop for model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize ChatOpenAI: {e}")
            raise
        
        # Create web search tool using proper CrewAI SerperDevTool
        try:
            if CREWAI_TOOLS_AVAILABLE and self.serper_api_key:
                # Use the proper CrewAI SerperDevTool
                self.web_search_tool = SerperDevTool()
                logger.info("SerperDevTool initialized successfully for CrewAI")
            else:
                if not CREWAI_TOOLS_AVAILABLE:
                    logger.warning("crewai_tools package not available, web search disabled")
                else:
                    logger.warning("SERPER_API_KEY not configured, web search disabled")
                self.web_search_tool = None
        except Exception as e:
            logger.error(f"Error creating SerperDevTool: {e}")
            self.web_search_tool = None
    
    def setup_crew(self) -> Crew:
        extractor = Agent(
            role='Senior Data Analyst',
            goal='Extract key recruitment details from an email with extreme accuracy.',
            backstory='An expert in NLP trained to find specific entities like names, job titles, locations, companies, and referrers in unstructured text.',
            verbose=True,
            allow_delegation=False,
            max_iter=3,
            max_execution_time=30,  # 30 seconds timeout
            llm=self.llm
        )

        # Only add tools if web_search_tool was successfully created
        researcher_tools = []
        if self.web_search_tool is not None:
            researcher_tools = [self.web_search_tool]
            
        researcher = Agent(
            role='Corporate Intelligence Analyst',
            goal='Verify and find the official company name associated with an email domain using web research.',
            backstory='A skilled web researcher who connects email domains to official corporate entities.',
            verbose=True,
            allow_delegation=False,
            tools=researcher_tools,
            max_iter=5,  # Increased from 3 to prevent timeout
            max_execution_time=45,  # Increased from 30 seconds
            llm=self.llm
        )

        validator = Agent(
            role='Data Quality Assurance Expert',
            goal='Validate, clean, and standardize all extracted information to ensure it is CRM-ready.',
            backstory='A meticulous data quality expert ensuring all information meets strict formatting standards before system integration.',
            verbose=True,
            allow_delegation=False,
            max_iter=3,
            max_execution_time=45,  # Increased from 30 seconds
            llm=self.llm
        )

        extract_task = Task(
            description="""
            Analyze the following email and extract these specific details:
            1. candidate_name: The full name of the job candidate being discussed.
            2. job_title: The specific role or position (e.g., 'Financial Advisor').
            3. location: The geographical location for the role (city and state if available).
            4. company_name: Any company name explicitly mentioned in the email.
            5. referrer_name: The name of the person sending the email or making the introduction.
            
            EMAIL CONTENT: --- {email_content} ---
            Return a JSON object with all five fields. Use null for any field you cannot determine.
            """,
            expected_output='A valid JSON object containing: candidate_name, job_title, location, company_name, referrer_name.',
            agent=extractor
        )

        research_task = Task(
            description="""
            Take the extraction results from the previous task and verify the company information.
            
            Review the extracted company_name. If it is null or seems incomplete, use the SENDER DOMAIN `{sender_domain}` to research the official company name.
            If you have the search_website tool available, use it to search for information about {sender_domain}.
            
            Return an updated JSON object with all five fields: candidate_name, job_title, location, company_name, referrer_name.
            Keep all original field values from the extraction unchanged except for company_name if you found a better one through research.
            """,
            expected_output='A complete JSON object with a verified company_name and all other extracted fields.',
            agent=researcher,
            context=[extract_task]
        )
        
        validation_task = Task(
            description="""
            Take the JSON data from the research task and validate it.
            
            Clean and standardize the data, then return a JSON object with EXACTLY these 5 fields:
            - candidate_name: The full name of the candidate
            - job_title: The job title or position
            - location: The geographical location
            - company_name: The company name (verified or original)
            - referrer_name: The person who sent the email
            
            Use null for any missing values. Do not add any other fields.
            """,
            expected_output='A clean JSON object with exactly 5 fields: candidate_name, job_title, location, company_name, referrer_name.',
            agent=validator,
            context=[research_task]
        )

        return Crew(
            agents=[extractor, researcher, validator],
            tasks=[extract_task, research_task, validation_task],
            process=Process.sequential,
            verbose=True,
            memory=False,  # Disabled for performance - was causing 5-10s delays per task
            stream=False  # Disable streaming at crew level for GPT-5
        )

    def run(self, email_body: str, sender_domain: str) -> ExtractedData:
        crew = self.setup_crew()
        result = crew.kickoff(inputs={"email_content": email_body, "sender_domain": sender_domain})
        
        try:
            # Handle CrewOutput object or string response
            if hasattr(result, 'raw'):
                result_str = result.raw
            else:
                result_str = str(result)
            
            # Extract the JSON part of the string response
            json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
            if json_match:
                result_dict = json.loads(json_match.group())
                return ExtractedData.model_validate(result_dict)
            else:
                logger.error(f"Could not parse JSON from crew result: {result_str}")
                return ExtractedData()
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to decode or validate crew result: {e}\nRaw result: {result_str}")
            return ExtractedData()
    
    async def run_async(self, email_body: str, sender_domain: str) -> ExtractedData:
        """Async wrapper for the run method."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, email_body, sender_domain)


class SimplifiedEmailExtractor:
    """Fallback email extractor when CrewAI is not available."""
    
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