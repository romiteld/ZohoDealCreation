"""
Rate limit handler for OpenAI API calls with exponential backoff and fallback mechanisms
"""

import asyncio
import logging
import time
import re
from typing import Dict, Any, Optional, Callable
from functools import wraps
from openai import RateLimitError, APIError

logger = logging.getLogger(__name__)


class RateLimitHandler:
    """Handles rate limits with exponential backoff and fallback strategies"""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.last_rate_limit_time = {}  # Track rate limits per model

    def calculate_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay"""
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        # Add jitter to prevent thundering herd
        import random
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter

    async def handle_with_retry(
        self,
        func: Callable,
        *args,
        fallback_func: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic for rate limits

        Args:
            func: The async function to execute
            fallback_func: Optional fallback function if all retries fail
            *args, **kwargs: Arguments to pass to the function
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                # Check if we should wait before attempting (if recently rate limited)
                model = kwargs.get('model', 'default')
                if model in self.last_rate_limit_time:
                    time_since_limit = time.time() - self.last_rate_limit_time[model]
                    if time_since_limit < 60:  # Wait at least 60 seconds after rate limit
                        wait_time = 60 - time_since_limit
                        logger.info(f"Waiting {wait_time:.1f}s before retry due to recent rate limit")
                        await asyncio.sleep(wait_time)

                # Try to execute the function
                result = await func(*args, **kwargs)

                # Clear rate limit tracking on success
                if model in self.last_rate_limit_time:
                    del self.last_rate_limit_time[model]

                return result

            except Exception as e:
                last_exception = e
                error_str = str(e)

                # Check if it's a rate limit error
                is_rate_limit = (
                    isinstance(e, RateLimitError) or
                    "429" in error_str or
                    "rate limit" in error_str.lower() or
                    "too many requests" in error_str.lower()
                )

                if is_rate_limit:
                    model = kwargs.get('model', 'default')
                    self.last_rate_limit_time[model] = time.time()

                    if attempt < self.max_retries - 1:
                        delay = self.calculate_delay(attempt)

                        # Check if error message contains retry-after header
                        retry_after = self._extract_retry_after(error_str)
                        if retry_after:
                            delay = max(delay, retry_after)

                        logger.warning(
                            f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}). "
                            f"Waiting {delay:.1f}s before retry..."
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Max retries reached. Rate limit persists.")
                        break
                else:
                    # Not a rate limit error, don't retry
                    logger.error(f"Non-rate-limit error: {e}")
                    break

        # All retries exhausted or non-retryable error
        if fallback_func:
            logger.info("Using fallback extraction method")
            try:
                return await fallback_func(*args, **kwargs)
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                raise last_exception
        else:
            raise last_exception

    def _extract_retry_after(self, error_message: str) -> Optional[float]:
        """Extract retry-after value from error message"""
        # Look for patterns like "retry after 60 seconds"
        match = re.search(r'retry after (\d+) seconds', error_message, re.IGNORECASE)
        if match:
            return float(match.group(1))

        # Look for patterns like "Please retry after 60"
        match = re.search(r'retry after (\d+)', error_message, re.IGNORECASE)
        if match:
            return float(match.group(1))

        return None


def with_rate_limit_handling(
    max_retries: int = 3,
    fallback_func: Optional[Callable] = None
):
    """
    Decorator to add rate limit handling to async functions

    Usage:
        @with_rate_limit_handling(max_retries=3)
        async def my_openai_call():
            return await openai.chat.completions.create(...)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            handler = RateLimitHandler(max_retries=max_retries)
            return await handler.handle_with_retry(
                func,
                *args,
                fallback_func=fallback_func,
                **kwargs
            )
        return wrapper
    return decorator


class CachedFallbackExtractor:
    """
    Fallback extractor that uses cached patterns and regex when API fails
    """

    def __init__(self):
        self.patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'(?:Phone[:\s]+)?(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})',
            'calendly_invitee': r'Invitee:\s*([^\n]+)',
            'calendly_email': r'Invitee Email:\s*([^\n]+)',
            'recruiting_goals': r'What recruiting goals[^?]*\?\s*([^\n]+(?:\n[^\n]+)?)',
            'linkedin': r'linkedin\.com/in/[\w-]+',
            'name_patterns': [
                r'(?:Candidate|Name|Contact):\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
                r'(?:Mr\.|Ms\.|Mrs\.|Dr\.)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
            ]
        }

    async def extract_from_email(
        self,
        email_content: str,
        sender_domain: str
    ) -> Dict[str, Any]:
        """
        Extract information using pattern matching as fallback
        """
        result = {}

        # Extract email
        email_match = re.search(self.patterns['email'], email_content)
        if email_match:
            result['email'] = email_match.group(0)

        # Extract phone
        phone_match = re.search(self.patterns['phone'], email_content)
        if phone_match:
            phone = phone_match.group(1) if phone_match.group(1) else phone_match.group(0)
            # Clean up phone number
            phone = re.sub(r'[^\d\+\-\(\)\s]', '', phone).strip()
            digits = re.sub(r'\D', '', phone)
            if len(digits) >= 10:
                result['phone'] = phone

        # Calendly-specific extractions
        if 'calendly' in email_content.lower():
            # Extract invitee name
            invitee_match = re.search(self.patterns['calendly_invitee'], email_content)
            if invitee_match:
                name = invitee_match.group(1).strip()
                # Clean up name (remove "Invitee Email:" if it follows)
                if 'Invitee Email:' in name:
                    name = name.split('Invitee Email:')[0].strip()
                result['candidate_name'] = name

            # Extract invitee email
            invitee_email_match = re.search(self.patterns['calendly_email'], email_content)
            if invitee_email_match:
                email_text = invitee_email_match.group(1).strip()
                # Extract just the email from the text
                email_only = re.search(self.patterns['email'], email_text)
                if email_only:
                    result['email'] = email_only.group(0)

            # Extract recruiting goals
            goals_match = re.search(self.patterns['recruiting_goals'], email_content, re.IGNORECASE)
            if goals_match:
                goals = goals_match.group(1).strip()
                goals = goals.replace('Your confirmation email', '').strip()
                if goals:
                    result['notes'] = f"Recruiting goals: {goals[:200]}"

        # Extract LinkedIn URL
        linkedin_match = re.search(self.patterns['linkedin'], email_content)
        if linkedin_match:
            result['linkedin_url'] = f"https://{linkedin_match.group(0)}"

        # Try to extract names if not found yet
        if 'candidate_name' not in result:
            for pattern in self.patterns['name_patterns']:
                name_match = re.search(pattern, email_content)
                if name_match:
                    result['candidate_name'] = name_match.group(1).strip()
                    break

        # Infer company from email domain if available
        if 'email' in result and '@' in result['email']:
            domain = result['email'].split('@')[1]
            # Skip generic email domains
            generic_domains = [
                'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                'aol.com', 'icloud.com', 'me.com', 'mac.com'
            ]
            if domain not in generic_domains:
                # Extract company name from domain
                company = domain.split('.')[0].replace('-', ' ').title()
                result['company_guess'] = company

        # Use sender domain as fallback for company
        if 'company_guess' not in result and sender_domain:
            company = sender_domain.split('.')[0].replace('-', ' ').title()
            result['company_guess'] = company

        logger.info(f"Fallback extraction completed: {result}")
        return result


# Global instance for reuse
rate_limit_handler = RateLimitHandler()
fallback_extractor = CachedFallbackExtractor()