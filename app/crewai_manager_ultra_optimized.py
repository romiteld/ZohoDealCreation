"""
Ultra-optimized CrewAI manager with advanced performance features
- Caching for repeated emails
- Circuit breaker for API failures
- Smart fallback to regex extraction
- Parallel processing where possible
- Aggressive timeouts and prompt optimization
"""

# CRITICAL: Apply SQLite patch BEFORE any other imports
from app.sqlite_patcher import patch_sqlite, is_patched, get_sqlite_version

# Verify patching succeeded
if not is_patched():
    print(f"[CrewAI Ultra] WARNING: SQLite patching incomplete. Version: {get_sqlite_version()}")
else:
    print(f"[CrewAI Ultra] SQLite ready. Version: {get_sqlite_version()}")

import os
import json
import logging
import re
import asyncio
import time
import hashlib
from typing import Dict, Optional, Any, Tuple
from functools import lru_cache, wraps
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timedelta
import threading

from app.models import ExtractedData

logger = logging.getLogger(__name__)

# Performance configuration
MAX_EMAIL_LENGTH = 1500  # Aggressive truncation for speed
CREW_TIMEOUT = 15  # Total timeout for CrewAI execution
CACHE_TTL_MINUTES = 10  # Cache results for 10 minutes
CIRCUIT_BREAKER_THRESHOLD = 2  # Open after 2 failures
CIRCUIT_BREAKER_RECOVERY = 30  # Recovery time in seconds

# Thread pool for parallel operations
_executor = ThreadPoolExecutor(max_workers=3)

# Global cache for results
class ResultCache:
    def __init__(self, ttl_minutes=CACHE_TTL_MINUTES):
        self._cache = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[ExtractedData]:
        with self._lock:
            if key in self._cache:
                result, timestamp = self._cache[key]
                if datetime.now() - timestamp < self._ttl:
                    return result
                else:
                    del self._cache[key]
        return None
    
    def set(self, key: str, value: ExtractedData):
        with self._lock:
            self._cache[key] = (value, datetime.now())
            # Cleanup old entries
            if len(self._cache) > 100:
                self._cleanup()
    
    def _cleanup(self):
        """Remove expired entries"""
        now = datetime.now()
        expired = [k for k, (_, ts) in self._cache.items() 
                  if now - ts > self._ttl]
        for k in expired:
            del self._cache[k]

_result_cache = ResultCache()

# Circuit breaker implementation
class CircuitBreaker:
    def __init__(self, threshold=CIRCUIT_BREAKER_THRESHOLD, recovery_timeout=CIRCUIT_BREAKER_RECOVERY):
        self.threshold = threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        self._lock = threading.Lock()
    
    def call_with_breaker(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        with self._lock:
            if self.state == "open":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "half_open"
                    logger.info("Circuit breaker entering half-open state")
                else:
                    raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            with self._lock:
                if self.state == "half_open":
                    self.state = "closed"
                    self.failure_count = 0
                    logger.info("Circuit breaker closed after successful call")
            return result
        except Exception as e:
            with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.threshold:
                    self.state = "open"
                    logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            raise

_circuit_breaker = CircuitBreaker()


class OptimizedEmailExtractor:
    """Ultra-fast regex-based extraction with enhanced patterns"""
    
    @staticmethod
    def extract(email_body: str, sender_email: str = "") -> ExtractedData:
        """Extract data using optimized regex patterns"""
        
        # Prepare email for processing
        email_lower = email_body.lower()
        
        # Extract candidate name
        candidate_name = None
        name_patterns = [
            # Specific introduction patterns
            r'(?:candidate|advisor|representative)[:.\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'(?:meet|introduce you to|connecting you with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            # Name with title
            r'(?:Mr\.|Mrs\.|Ms\.|Dr\.)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            # Signature pattern
            r'(?:Best|Regards|Sincerely),?\s*\n+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, email_body, re.MULTILINE)
            if match:
                candidate_name = match.group(1).strip()
                # Validate name (should be 2-4 words)
                if 2 <= len(candidate_name.split()) <= 4:
                    break
                else:
                    candidate_name = None
        
        # Extract job title
        job_title = None
        
        # Check for specific titles first
        specific_titles = [
            'Senior Financial Advisor', 'Financial Advisor', 
            'Wealth Manager', 'Investment Advisor', 
            'Portfolio Manager', 'Financial Consultant'
        ]
        
        for title in specific_titles:
            if title.lower() in email_lower:
                job_title = title
                break
        
        if not job_title:
            # Generic patterns
            title_patterns = [
                r'(?:position|role|opportunity)[:.\s]+([A-Za-z\s]+?)(?:\.|,|\n|$)',
                r'(?:working as|serves as)\s+(?:a|an)?\s*([A-Za-z\s]+?)(?:\.|,|\n)',
            ]
            for pattern in title_patterns:
                match = re.search(pattern, email_body, re.IGNORECASE)
                if match:
                    job_title = match.group(1).strip()
                    if len(job_title) < 50:  # Sanity check
                        break
                    else:
                        job_title = None
        
        # Extract location
        location = None
        
        # Common cities in the area
        known_cities = [
            'Fort Wayne', 'Indianapolis', 'Chicago', 'Detroit', 
            'Columbus', 'Cincinnati', 'Milwaukee', 'Cleveland'
        ]
        
        for city in known_cities:
            if city.lower() in email_lower:
                location = city
                # Try to find state
                state_match = re.search(f'{city},?\\s*([A-Z]{{2}})', email_body)
                if state_match:
                    location = f"{city}, {state_match.group(1)}"
                break
        
        if not location:
            # Generic location patterns
            location_patterns = [
                r'(?:based in|located in|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z]{2})\b',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, email_body)
                if match:
                    if match.groups() and len(match.groups()) > 1:
                        location = f"{match.group(1)}, {match.group(2)}"
                    else:
                        location = match.group(1)
                    break
        
        # Extract company name
        company_name = None
        
        # Look for explicit company mentions
        company_patterns = [
            r'(?:at|with|from|representing)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*(?:\s+(?:LLC|Inc|Corp|Company|Group|Partners))?)',
            r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+(?:Financial|Wealth|Investment|Advisory|Capital))',
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, email_body)
            if match:
                potential_company = match.group(1).strip()
                if 2 <= len(potential_company.split()) <= 5:  # Reasonable company name length
                    company_name = potential_company
                    break
        
        # Infer from domain if needed
        if not company_name and sender_email and '@' in sender_email:
            domain = sender_email.split('@')[1].split('.')[0]
            if domain.lower() not in ['gmail', 'yahoo', 'hotmail', 'outlook', 'aol', 'msn']:
                company_name = domain.replace('-', ' ').replace('_', ' ').title()
        
        # Extract referrer name
        referrer_name = None
        
        # Try to get from email
        if sender_email and '@' in sender_email:
            local_part = sender_email.split('@')[0]
            if '.' in local_part:
                parts = local_part.split('.')
                if all(part.isalpha() for part in parts):
                    referrer_name = ' '.join(p.capitalize() for p in parts)
        
        # Look in signature if not found
        if not referrer_name:
            sig_pattern = r'(?:Best|Regards|Sincerely),?\s*\n+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'
            match = re.search(sig_pattern, email_body)
            if match and match.group(1) != candidate_name:
                referrer_name = match.group(1).strip()
        
        return ExtractedData(
            candidate_name=candidate_name,
            job_title=job_title,
            location=location,
            company_name=company_name,
            referrer_name=referrer_name
        )


class UltraOptimizedEmailProcessingCrew:
    """Ultra-optimized email processing with intelligent fallbacks"""
    
    def __init__(self, firecrawl_api_key: str):
        self.firecrawl_api_key = firecrawl_api_key
        self._crew = None
        self._llm = None
        self._agents_initialized = False
        self._fallback_extractor = OptimizedEmailExtractor()
        self._crew_available = True
        self._initialization_lock = threading.Lock()
        
        # Lazy-loaded agents
        self.extractor = None
        self.researcher = None
        self.validator = None
    
    def _initialize_llm(self):
        """Initialize LLM with optimal settings"""
        if self._llm:
            return self._llm
            
        try:
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(
                model="gpt-5-mini",
                temperature=1,  # Required for gpt-5-mini
                api_key=os.getenv("OPENAI_API_KEY"),
                max_retries=1,  # Minimize retries
                request_timeout=10,  # Short timeout
                max_tokens=150  # Limit response size
            )
            logger.info("LLM initialized successfully")
        except Exception as e:
            logger.warning(f"LLM initialization failed, using string config: {e}")
            self._llm = "gpt-5-mini"
        
        return self._llm
    
    def _initialize_agents(self):
        """Initialize CrewAI agents with ultra-optimized settings"""
        with self._initialization_lock:
            if self._agents_initialized:
                return
            
            try:
                from crewai import Agent
                
                # Ultra-fast extractor agent
                self.extractor = Agent(
                    role='Speed Extractor',
                    goal='Extract data in under 5 seconds.',
                    backstory='Lightning-fast data extraction specialist.',
                    verbose=False,
                    allow_delegation=False,
                    max_iter=1,  # Single pass only
                    max_execution_time=5,
                    llm=self._initialize_llm(),
                    memory=False
                )
                
                # Skip researcher in most cases (only if really needed)
                self.researcher = None  # Disabled for speed
                
                # Minimal validator
                self.validator = Agent(
                    role='JSON Formatter',
                    goal='Format as JSON.',
                    backstory='JSON formatting expert.',
                    verbose=False,
                    allow_delegation=False,
                    max_iter=1,
                    max_execution_time=3,
                    llm=self._llm,
                    memory=False
                )
                
                self._agents_initialized = True
                logger.info("Agents initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize agents: {e}")
                self._crew_available = False
                raise
    
    def _create_optimized_crew(self, email_content: str) -> Any:
        """Create ultra-optimized crew for single execution"""
        from crewai import Task, Crew, Process
        
        # Single extraction task with minimal prompt
        extract_task = Task(
            description=f"""Extract ONLY these 5 fields as JSON:
{{"candidate_name":"NAME","job_title":"TITLE","location":"LOCATION","company_name":"COMPANY","referrer_name":"REFERRER"}}

EMAIL: {email_content[:1000]}

Output ONLY the JSON. Nothing else.""",
            expected_output='{"candidate_name":"X","job_title":"Y","location":"Z","company_name":"A","referrer_name":"B"}',
            agent=self.extractor
        )
        
        # Minimal validation
        validate_task = Task(
            description="Output the JSON exactly as provided.",
            expected_output='Same JSON',
            agent=self.validator,
            context=[extract_task]
        )
        
        return Crew(
            agents=[self.extractor, self.validator],
            tasks=[extract_task, validate_task],
            process=Process.sequential,
            verbose=False,
            memory=False,
            max_rpm=100,
            full_output=False,
            max_execution_time=10  # Ultra-aggressive timeout
        )
    
    def _parse_crew_result(self, result) -> Optional[Dict]:
        """Parse CrewAI output to dictionary"""
        try:
            # Get string representation
            if hasattr(result, 'raw'):
                result_str = result.raw
            elif hasattr(result, 'output'):
                result_str = result.output
            else:
                result_str = str(result)
            
            # Find JSON in response
            json_patterns = [
                r'\{[^{}]*"candidate_name"[^{}]*\}',
                r'\{[^{}]*\}',
            ]
            
            for pattern in json_patterns:
                match = re.search(pattern, result_str, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except json.JSONDecodeError:
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse result: {e}")
            return None
    
    def run(self, email_body: str, sender_domain: str) -> ExtractedData:
        """Run extraction with multiple optimization strategies"""
        
        # Generate cache key
        cache_key = hashlib.md5(f"{email_body[:500]}:{sender_domain}".encode()).hexdigest()
        
        # Check cache
        cached_result = _result_cache.get(cache_key)
        if cached_result:
            logger.info("Returning cached extraction result")
            return cached_result
        
        # Prepare email (aggressive truncation)
        truncated_email = email_body[:MAX_EMAIL_LENGTH]
        if len(email_body) > MAX_EMAIL_LENGTH:
            # Try to end at sentence boundary
            last_period = truncated_email.rfind('.')
            if last_period > MAX_EMAIL_LENGTH * 0.7:
                truncated_email = truncated_email[:last_period + 1]
        
        # Try CrewAI if available
        if self._crew_available:
            try:
                # Use circuit breaker
                def crew_execution():
                    if not self._agents_initialized:
                        self._initialize_agents()
                    
                    crew = self._create_optimized_crew(truncated_email)
                    
                    # Execute with timeout
                    import signal
                    
                    class TimeoutException(Exception):
                        pass
                    
                    def timeout_handler(signum, frame):
                        raise TimeoutException()
                    
                    # Set timeout (Unix only)
                    if hasattr(signal, 'SIGALRM'):
                        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(CREW_TIMEOUT)
                    
                    try:
                        result = crew.kickoff()
                        return result
                    finally:
                        if hasattr(signal, 'SIGALRM'):
                            signal.alarm(0)
                            signal.signal(signal.SIGALRM, old_handler)
                
                # Execute with circuit breaker
                crew_result = _circuit_breaker.call_with_breaker(crew_execution)
                
                # Parse result
                parsed = self._parse_crew_result(crew_result)
                if parsed:
                    # Clean and validate
                    extracted = ExtractedData(
                        candidate_name=self._clean_value(parsed.get('candidate_name')),
                        job_title=self._clean_value(parsed.get('job_title')),
                        location=self._clean_value(parsed.get('location')),
                        company_name=self._clean_value(parsed.get('company_name')),
                        referrer_name=self._clean_value(parsed.get('referrer_name'))
                    )
                    
                    # Check if we got meaningful results
                    field_count = sum(1 for f in [extracted.candidate_name, extracted.job_title, 
                                                  extracted.location, extracted.company_name] 
                                     if f is not None)
                    
                    if field_count >= 2:  # At least 2 fields extracted
                        logger.info(f"CrewAI extraction successful with {field_count} fields")
                        _result_cache.set(cache_key, extracted)
                        return extracted
                    else:
                        logger.warning("CrewAI extraction incomplete, using fallback")
                        
            except Exception as e:
                logger.error(f"CrewAI extraction failed: {e}")
                # Disable CrewAI for future calls if too many failures
                if "Circuit breaker is open" in str(e):
                    self._crew_available = False
                    logger.warning("Disabling CrewAI due to repeated failures")
        
        # Fallback to regex extraction
        logger.info("Using optimized regex extraction")
        
        # Determine sender email for extraction
        sender_email = ""
        if sender_domain and '@' not in sender_domain:
            sender_email = f"unknown@{sender_domain}"
        
        fallback_result = self._fallback_extractor.extract(email_body, sender_email)
        
        # Cache the result
        _result_cache.set(cache_key, fallback_result)
        
        return fallback_result
    
    async def run_async(self, email_body: str, sender_domain: str) -> ExtractedData:
        """Async wrapper with proper timeout handling"""
        loop = asyncio.get_event_loop()
        
        try:
            # Execute with asyncio timeout
            result = await asyncio.wait_for(
                loop.run_in_executor(_executor, self.run, email_body, sender_domain),
                timeout=20  # Total timeout for entire operation
            )
            return result
        except asyncio.TimeoutError:
            logger.error("Async timeout, using fallback extractor")
            # Direct fallback extraction (fast)
            sender_email = f"unknown@{sender_domain}" if sender_domain and '@' not in sender_domain else ""
            return self._fallback_extractor.extract(email_body, sender_email)
    
    def _clean_value(self, value: Any) -> Optional[str]:
        """Clean and validate extracted value"""
        if value is None:
            return None
            
        if isinstance(value, str):
            value = value.strip()
            # Remove quotes
            value = value.strip('"\'')
            
            # Check for invalid values
            if value.lower() in ['unknown', 'n/a', 'none', '', 'null', 
                                'not found', 'not available', 'tbd']:
                return None
            
            # Check if it's just placeholder text
            if value in ['NAME', 'TITLE', 'LOCATION', 'COMPANY', 'REFERRER', 
                        'X', 'Y', 'Z', 'A', 'B']:
                return None
            
            return value
        
        return None


# Public interface
EmailProcessingCrew = UltraOptimizedEmailProcessingCrew
SimplifiedEmailExtractor = OptimizedEmailExtractor