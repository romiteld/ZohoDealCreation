"""
Optimized CrewAI manager with lazy loading and improved performance
"""

import os
import json
import logging
import re
import asyncio
from typing import Dict, Optional
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

# Apply sqlite3 patch for Azure compatibility BEFORE any CrewAI imports
import sys
try:
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
    sys.modules['sqlite3.dbapi2'] = pysqlite3.dbapi2
    print(f"[CrewAI] Using pysqlite3 version: {pysqlite3.sqlite_version}")
except ImportError:
    import sqlite3
    print(f"[CrewAI] WARNING: Using system sqlite3 version: {sqlite3.sqlite_version}")
    if hasattr(sqlite3, 'sqlite_version'):
        version_parts = sqlite3.sqlite_version.split('.')
        if len(version_parts) >= 2:
            major, minor = int(version_parts[0]), int(version_parts[1])
            if major < 3 or (major == 3 and minor < 35):
                print(f"[CrewAI] ERROR: SQLite version {sqlite3.sqlite_version} is too old. ChromaDB requires >= 3.35.0")
                print("[CrewAI] Please ensure pysqlite3-binary is installed: pip install pysqlite3-binary")

from app.models import ExtractedData

logger = logging.getLogger(__name__)

# Thread pool for CPU-bound operations
_executor = ThreadPoolExecutor(max_workers=2)

class EmailProcessingCrew:
    """Optimized email processing crew with lazy initialization"""
    
    def __init__(self, firecrawl_api_key: str):
        self.firecrawl_api_key = firecrawl_api_key
        self._crew = None
        self._llm = None
        self._search_tool = None
        self._initialized = False
    
    @property
    def llm(self):
        """Lazy load LLM"""
        if not self._llm:
            try:
                # Try multiple approaches to import langchain_openai
                try:
                    from langchain_openai import ChatOpenAI
                    logger.info("langchain_openai imported successfully")
                except ImportError as first_error:
                    logger.warning(f"First import attempt failed: {first_error}")
                    import subprocess
                    import sys
                    
                    # Try installing with pip
                    logger.warning("Attempting to install langchain-openai...")
                    try:
                        subprocess.check_call(
                            [sys.executable, "-m", "pip", "install", "--no-cache-dir", "langchain-openai==0.0.5"],
                            timeout=60
                        )
                        logger.info("Installation completed, attempting import again...")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"pip install failed: {e}")
                    except subprocess.TimeoutExpired:
                        logger.error("pip install timed out")
                    
                    # Try import again after installation
                    try:
                        from langchain_openai import ChatOpenAI
                        logger.info("langchain_openai imported successfully after installation")
                    except ImportError as second_error:
                        logger.error(f"Still cannot import after installation: {second_error}")
                        # Last resort - try importing from langchain.chat_models
                        try:
                            from langchain.chat_models import ChatOpenAI
                            logger.warning("Using fallback import from langchain.chat_models")
                        except ImportError:
                            logger.error("All import attempts failed for ChatOpenAI")
                            raise ImportError("Cannot import ChatOpenAI from any source")
                
                self._llm = ChatOpenAI(
                    model="gpt-5-mini",
                    temperature=1,  # Required for GPT-5-mini
                    api_key=os.getenv("OPENAI_API_KEY"),
                    max_retries=2,
                    request_timeout=30
                )
                logger.info("LLM initialized successfully")
            except ImportError as e:
                logger.error(f"Failed to import LangChain: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize LLM: {e}")
                raise
        return self._llm
    
    @property
    def search_tool(self):
        """Lazy load search tool"""
        if not self._search_tool and self.firecrawl_api_key:
            try:
                from crewai_tools import ScrapeWebsiteTool
                self._search_tool = ScrapeWebsiteTool(
                    config={"api_key": self.firecrawl_api_key}
                )
                logger.info("Search tool initialized successfully")
            except ImportError:
                logger.warning("CrewAI tools not available, web search disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize search tool: {e}")
        return self._search_tool
    
    def _initialize_crew(self):
        """Initialize CrewAI components lazily"""
        if self._initialized:
            return
        
        try:
            from crewai import Agent, Task, Crew, Process
            
            # Create agents with optimized settings
            self.extractor = Agent(
                role='Data Extraction Specialist',
                goal='Extract key recruitment details from email content accurately and efficiently.',
                backstory='Expert in NLP and information extraction from unstructured text.',
                verbose=False,  # Reduce logging overhead
                allow_delegation=False,
                max_iter=2,  # Reduce iterations
                max_execution_time=15,  # Shorter timeout
                llm=self.llm
            )
            
            # Only create researcher if search tool is available
            if self.search_tool:
                self.researcher = Agent(
                    role='Company Research Analyst',
                    goal='Verify company information using web research when needed.',
                    backstory='Skilled researcher for corporate entity verification.',
                    verbose=False,
                    allow_delegation=False,
                    tools=[self.search_tool],
                    max_iter=2,
                    max_execution_time=15,
                    llm=self.llm
                )
            else:
                self.researcher = None
            
            self.validator = Agent(
                role='Data Validator',
                goal='Ensure extracted data is clean and properly formatted.',
                backstory='Quality assurance specialist for data integrity.',
                verbose=False,
                allow_delegation=False,
                max_iter=1,  # Single pass validation
                max_execution_time=10,
                llm=self.llm
            )
            
            self._initialized = True
            logger.info("CrewAI agents initialized successfully")
            
        except ImportError as e:
            logger.error(f"Failed to import CrewAI: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize CrewAI: {e}")
            raise
    
    def _create_crew(self, email_content: str, sender_domain: str):
        """Create crew with optimized task pipeline"""
        from crewai import Task, Crew, Process
        
        # Extraction task (simplified prompt)
        extract_task = Task(
            description=f"""
            Extract from this email:
            - candidate_name: Full name of the job candidate
            - job_title: The position/role
            - location: Geographic location
            - company_name: Any mentioned company
            - referrer_name: Person making the introduction
            
            EMAIL: {email_content[:2000]}
            
            Return JSON with these 5 fields. Use null for unknown values.
            """,
            expected_output='JSON object with 5 fields',
            agent=self.extractor
        )
        
        tasks = [extract_task]
        agents = [self.extractor]
        
        # Add research task only if researcher is available and domain is valid
        if self.researcher and sender_domain and sender_domain != 'unknown.com':
            research_task = Task(
                description=f"""
                If company_name is missing, research the domain '{sender_domain}'.
                Return the same JSON with verified company_name.
                """,
                expected_output='JSON object with verified company_name',
                agent=self.researcher,
                context=[extract_task]
            )
            tasks.append(research_task)
            agents.append(self.researcher)
        
        # Validation task
        validation_task = Task(
            description="""
            Return the JSON data exactly as provided.
            Ensure it has these 5 fields: candidate_name, job_title, location, company_name, referrer_name.
            """,
            expected_output='Clean JSON object',
            agent=self.validator,
            context=tasks[-1:]  # Context from last task
        )
        tasks.append(validation_task)
        agents.append(self.validator)
        
        # Create optimized crew
        return Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=False,  # Reduce output
            memory=False,  # Disable memory for performance
            max_rpm=100,  # Rate limiting
            full_output=False  # Return only final output
        )
    
    def run(self, email_body: str, sender_domain: str) -> ExtractedData:
        """Run extraction with optimized performance"""
        try:
            # Initialize crew if needed
            if not self._initialized:
                self._initialize_crew()
            
            # Create and run crew
            crew = self._create_crew(email_body[:3000], sender_domain)  # Limit input size
            
            # Execute with timeout
            result = crew.kickoff()
            
            # Parse result
            return self._parse_result(result)
            
        except Exception as e:
            logger.error(f"CrewAI extraction failed: {e}")
            # Return default values on failure
            return ExtractedData(
                candidate_name=None,
                job_title=None,
                location=None,
                company_name=None,
                referrer_name=None
            )
    
    async def run_async(self, email_body: str, sender_domain: str) -> ExtractedData:
        """Async wrapper for running extraction in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            self.run,
            email_body,
            sender_domain
        )
    
    def _parse_result(self, result) -> ExtractedData:
        """Parse CrewAI result with improved error handling"""
        try:
            # Handle different result types
            if hasattr(result, 'raw'):
                result_str = result.raw
            elif hasattr(result, 'output'):
                result_str = result.output
            else:
                result_str = str(result)
            
            # Extract JSON using regex
            json_match = re.search(r'\{[^{}]*\}', result_str, re.DOTALL)
            if json_match:
                result_dict = json.loads(json_match.group())
                
                # Validate and clean data
                cleaned_dict = {
                    'candidate_name': self._clean_value(result_dict.get('candidate_name')),
                    'job_title': self._clean_value(result_dict.get('job_title')),
                    'location': self._clean_value(result_dict.get('location')),
                    'company_name': self._clean_value(result_dict.get('company_name')),
                    'referrer_name': self._clean_value(result_dict.get('referrer_name'))
                }
                
                return ExtractedData.model_validate(cleaned_dict)
            else:
                logger.warning(f"No JSON found in result: {result_str[:200]}")
                return ExtractedData()
                
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse crew result: {e}")
            return ExtractedData()
    
    def _clean_value(self, value):
        """Clean extracted value"""
        if value is None or value == "null" or value == "None":
            return None
        if isinstance(value, str):
            value = value.strip()
            if value.lower() in ['unknown', 'n/a', 'none', '']:
                return None
        return value


class SimplifiedEmailExtractor:
    """Fallback extractor using regex patterns (no AI)"""
    
    @staticmethod
    def extract(email_body: str, sender_email: str) -> ExtractedData:
        """Extract data using pattern matching"""
        
        # Extract candidate name from signature or common patterns
        candidate_name = None
        name_patterns = [
            r'(?:Regards|Sincerely|Best|Thanks),?\s*\n+([A-Z][a-z]+ [A-Z][a-z]+)',
            r'(?:Mr\.|Mrs\.|Ms\.|Dr\.)?\s*([A-Z][a-z]+ [A-Z][a-z]+)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, email_body)
            if match:
                candidate_name = match.group(1).strip()
                break
        
        # Extract job title
        job_title = None
        title_patterns = [
            r'(?:position|role|opportunity|job|title)(?:\s+(?:is|of|for))?\s*:?\s*([A-Za-z\s]+)',
            r'(?:Financial Advisor|Senior Advisor|Wealth Manager|Investment Advisor)',
        ]
        for pattern in title_patterns:
            match = re.search(pattern, email_body, re.IGNORECASE)
            if match:
                job_title = match.group(1).strip() if match.groups() else match.group(0).strip()
                break
        
        # Extract location
        location = None
        location_patterns = [
            r'(?:in|at|near|around)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:,\s*[A-Z]{2})?)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s*([A-Z]{2})\b',
        ]
        for pattern in location_patterns:
            match = re.search(pattern, email_body)
            if match:
                location = match.group(0).strip()
                break
        
        # Infer company from email domain
        company_name = None
        if '@' in sender_email:
            domain = sender_email.split('@')[1]
            company_name = domain.split('.')[0].capitalize()
        
        # Extract referrer (person sending the email)
        referrer_name = None
        if sender_email:
            # Try to extract name from email address
            local_part = sender_email.split('@')[0]
            if '.' in local_part:
                parts = local_part.split('.')
                referrer_name = ' '.join(p.capitalize() for p in parts)
        
        return ExtractedData(
            candidate_name=candidate_name,
            job_title=job_title or "Financial Advisor",
            location=location or "Unknown Location",
            company_name=company_name,
            referrer_name=referrer_name
        )