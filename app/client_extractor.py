"""
Client Detail Extraction Module

This module provides AI-powered extraction of client details from email content,
specifically designed to ignore the Outlook add-in user's information and focus
on extracting the true client/candidate details from the email.
"""

import json
import logging
from typing import Dict, Optional, Any
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

async def extract_client_details_with_ai(
    email_content: str,
    user_context: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    """
    Extract client details from email content using AI, explicitly ignoring user context.

    Args:
        email_content: The full email content (subject + body)
        user_context: Dictionary containing user's name and email to ignore

    Returns:
        Dictionary containing extracted client details or None if extraction fails
    """
    try:
        user_name = user_context.get('name', '')
        user_email = user_context.get('email', '')
        user_domain = user_email.split('@')[1] if user_email and '@' in user_email else ''

        prompt = f"""
You are an AI assistant that extracts client/candidate details from recruitment emails.

CRITICAL INSTRUCTION: You must IGNORE any information related to the email user:
- User Name: {user_name}
- User Email: {user_email}
- User Domain: {user_domain}

The user is the person operating the Outlook add-in. Focus ONLY on extracting details about the CLIENT/CANDIDATE mentioned in the email - the person they are recruiting for or the person being referred.

Email Content:
{email_content}

Extract the following information about the CLIENT/CANDIDATE (NOT the user):
- client_name: Full name of the client/candidate
- client_email: Email address of the client/candidate
- job_title: Position or job title mentioned
- company_name: Company the client works for or is being recruited by
- location: City, state, or location mentioned
- phone: Phone number if provided
- notes: Any additional relevant details about the client's background or requirements

Return ONLY a valid JSON object with these fields. If a field cannot be determined, use null.
If no client information can be extracted (only user information present), return null.

Example response format:
{{
    "client_name": "John Smith",
    "client_email": "john.smith@company.com",
    "job_title": "Software Engineer",
    "company_name": "Tech Corp",
    "location": "San Francisco, CA",
    "phone": "+1-555-123-4567",
    "notes": "Looking for senior backend developer with 5+ years Python experience"
}}
"""

        # Call OpenAI API with GPT-5 and temperature=1 as per project requirements
        response = await openai_client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "You are a precise data extraction assistant. Always return valid JSON or null."},
                {"role": "user", "content": prompt}
            ],
            temperature=1,
            max_tokens=1000
        )

        # Extract and parse the response
        content = response.choices[0].message.content.strip()
        logger.info(f"AI extraction response: {content}")

        # Handle null response
        if content.lower() == 'null':
            logger.info("AI determined no client information could be extracted")
            return None

        # Try to parse JSON response
        try:
            extracted_data = json.loads(content)

            # Validate that we have some meaningful client data
            if not any([
                extracted_data.get('client_name'),
                extracted_data.get('client_email'),
                extracted_data.get('job_title'),
                extracted_data.get('company_name')
            ]):
                logger.info("AI extracted data but no meaningful client information found")
                return None

            logger.info(f"Successfully extracted client details: {extracted_data}")
            return extracted_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Raw response: {content}")
            return None

    except Exception as e:
        logger.error(f"Error in client detail extraction: {str(e)}")
        return None