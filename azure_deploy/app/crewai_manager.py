import os
import json
import logging
from typing import Dict, Optional
from crewai import Agent, Task, Crew, Process
from firecrawl import FirecrawlApp
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
from app.models import ExtractedData
import re

logger = logging.getLogger(__name__)

class EmailProcessingCrew:
    def __init__(self, firecrawl_api_key: str):
        self.firecrawl_api_key = firecrawl_api_key
        self.firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key) if firecrawl_api_key else None
        # Initialize LLM with GPT-5-mini
        self.llm = ChatOpenAI(
            model="gpt-5-mini",
            temperature=1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        # Create custom tool for web scraping
        self.web_search_tool = self._create_web_search_tool()

    def _create_web_search_tool(self) -> Optional[Tool]:
        """Create a custom tool for web scraping using Firecrawl."""
        if not self.firecrawl_app:
            return None
            
        def search_website(url: str) -> str:
            """Search and scrape a website for information."""
            try:
                # Use firecrawl to scrape the website
                result = self.firecrawl_app.scrape_url(
                    url,
                    params={
                        'formats': ['markdown'],
                        'onlyMainContent': True
                    }
                )
                if result and 'markdown' in result:
                    return result['markdown'][:2000]  # Limit response size
                return "No content found"
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                return f"Error accessing website: {str(e)}"
        
        return Tool(
            name="search_website",
            func=search_website,
            description="Search and scrape a website for information. Input should be a URL."
        )
    
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

        researcher = Agent(
            role='Corporate Intelligence Analyst',
            goal='Verify and find the official company name associated with an email domain using web research.',
            backstory='A skilled web researcher who connects email domains to official corporate entities.',
            verbose=True,
            allow_delegation=False,
            tools=[self.web_search_tool] if self.web_search_tool else [],
            max_iter=3,
            max_execution_time=30,  # 30 seconds timeout
            llm=self.llm
        )

        validator = Agent(
            role='Data Quality Assurance Expert',
            goal='Validate, clean, and standardize all extracted information to ensure it is CRM-ready.',
            backstory='A meticulous data quality expert ensuring all information meets strict formatting standards before system integration.',
            verbose=True,
            allow_delegation=False,
            max_iter=2,
            max_execution_time=30,  # 30 seconds timeout
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
            Review the extracted company_name. If it is null or seems incomplete, use the SENDER DOMAIN `{sender_domain}` to research the official company name.
            If you have the search_website tool available, use it to search https://{sender_domain} to find the official company name.
            Return an updated JSON object with all original fields plus the verified `company_name`.
            """,
            expected_output='A complete JSON object with a verified company_name and all other extracted fields.',
            agent=researcher,
            context=[extract_task]
        )
        
        validation_task = Task(
            description="""
            Take the JSON from the previous task and return it EXACTLY as is.
            Do NOT add any new fields. Do NOT change the structure.
            Simply return the same JSON object with these 5 fields: candidate_name, job_title, location, company_name, referrer_name.
            """,
            expected_output='The exact same JSON object with the 5 required fields.',
            agent=validator,
            context=[research_task]
        )

        return Crew(
            agents=[extractor, researcher, validator],
            tasks=[extract_task, research_task, validation_task],
            process=Process.sequential,
            verbose=True,
            memory=False  # Disabled for performance - was causing 5-10s delays per task
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