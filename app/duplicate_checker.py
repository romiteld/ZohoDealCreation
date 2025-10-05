"""
Enhanced duplicate detection system for preventing duplicate records.
Checks multiple criteria with fuzzy matching and time windows.
"""
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class DuplicateChecker:
    """
    Comprehensive duplicate detection with multiple strategies:
    1. Candidate name + company fuzzy matching
    2. Email-based detection (candidate email, not sender)
    3. Time window protection (5 minutes)
    4. Deal name variation handling
    """

    def __init__(self, postgres_client=None):
        self.postgres_client = postgres_client
        self.duplicate_window_minutes = 5  # Prevent duplicates within 5 minutes

    def normalize_name(self, name: str) -> str:
        """Normalize name for comparison (lowercase, remove extra spaces)."""
        if not name:
            return ""
        return re.sub(r'\s+', ' ', name.lower().strip())

    def normalize_company(self, company: str) -> str:
        """Normalize company name for comparison."""
        if not company:
            return ""
        # Remove common suffixes
        company = company.lower().strip()
        for suffix in [' inc', ' llc', ' corp', ' corporation', ' ltd', ' limited', ' co', '.']:
            company = company.replace(suffix, '')
        return re.sub(r'\s+', ' ', company.strip())

    def similarity_score(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0-1)."""
        if not str1 or not str2:
            return 0.0
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def is_duplicate_candidate(self, candidate1: Dict, candidate2: Dict, threshold: float = 0.85) -> bool:
        """
        Check if two candidates are duplicates based on:
        - Name similarity (>85% match)
        - Company similarity (>85% match)
        - Email exact match
        """
        # Check email first (exact match)
        email1 = candidate1.get('email', '').lower().strip()
        email2 = candidate2.get('email', '').lower().strip()
        if email1 and email2 and email1 == email2:
            return True

        # Check name + company combination
        name1 = self.normalize_name(candidate1.get('candidate_name', ''))
        name2 = self.normalize_name(candidate2.get('candidate_name', ''))

        company1 = self.normalize_company(candidate1.get('company_name', ''))
        company2 = self.normalize_company(candidate2.get('company_name', ''))

        # If names are very similar and companies match
        name_similarity = self.similarity_score(name1, name2)
        company_similarity = self.similarity_score(company1, company2)

        if name_similarity >= threshold and company_similarity >= threshold:
            logger.info(f"Duplicate detected: {name1} vs {name2} (name: {name_similarity:.2%}, company: {company_similarity:.2%})")
            return True

        # Check for exact name match with same job title
        if name1 == name2 and name1:  # Exact name match
            job1 = candidate1.get('job_title', '').lower()
            job2 = candidate2.get('job_title', '').lower()
            if self.similarity_score(job1, job2) >= 0.8:  # Similar job titles
                logger.info(f"Duplicate detected: Same name and similar job: {name1}")
                return True

        return False

    async def check_database_duplicate(self, extracted_data: Dict) -> Optional[Dict]:
        """
        Check for duplicates in the database within the time window.
        Returns existing record if found, None otherwise.
        """
        if not self.postgres_client:
            return None

        try:
            # Get candidate info
            candidate_name = extracted_data.get('candidate_name', '')
            company_name = extracted_data.get('company_name', '')
            candidate_email = extracted_data.get('email', '')

            # Build query to check recent records (last 5 minutes)
            cutoff_time = datetime.utcnow() - timedelta(minutes=self.duplicate_window_minutes)

            query = """
                SELECT
                    deal_id,
                    candidate_name,
                    company_name,
                    email,
                    job_title,
                    created_at,
                    zoho_deal_id,
                    zoho_contact_id,
                    zoho_account_id
                FROM deals
                WHERE created_at >= $1
                ORDER BY created_at DESC
                LIMIT 100
            """

            async with self.postgres_client.pool.acquire() as conn:
                rows = await conn.fetch(query, cutoff_time)

                for row in rows:
                    existing = {
                        'candidate_name': row['candidate_name'],
                        'company_name': row['company_name'],
                        'email': row['email'],
                        'job_title': row['job_title']
                    }

                    if self.is_duplicate_candidate(extracted_data, existing):
                        time_diff = datetime.utcnow() - row['created_at']
                        logger.warning(
                            f"Duplicate detected in database: {candidate_name} at {company_name} "
                            f"(created {time_diff.total_seconds():.0f} seconds ago)"
                        )
                        return {
                            'deal_id': row['deal_id'],
                            'zoho_deal_id': row['zoho_deal_id'],
                            'zoho_contact_id': row['zoho_contact_id'],
                            'zoho_account_id': row['zoho_account_id'],
                            'created_at': row['created_at'],
                            'time_since_creation': time_diff.total_seconds()
                        }

                return None

        except Exception as e:
            logger.error(f"Error checking database for duplicates: {e}")
            return None

    async def check_zoho_duplicate_flexible(self, zoho_client, extracted_data: Dict) -> Optional[Dict]:
        """
        Check Zoho for duplicates with flexible matching.
        Searches by candidate name and checks for similar records.
        """
        try:
            candidate_name = extracted_data.get('candidate_name', '')
            candidate_email = extracted_data.get('email', '')

            if not candidate_name and not candidate_email:
                return None

            # Search Zoho Contacts by email first (most reliable)
            if candidate_email:
                existing_contact = await zoho_client.check_zoho_contact_duplicate(candidate_email)
                if existing_contact:
                    logger.info(f"Found existing contact by email: {candidate_email}")
                    return {
                        'contact_id': existing_contact.get('id'),
                        'contact_name': existing_contact.get('name'),
                        'match_type': 'email_exact'
                    }

            # Search by name if no email match
            if candidate_name:
                # Search for contacts with similar names
                search_name = candidate_name.split()[0] if ' ' in candidate_name else candidate_name
                search_query = f"(Full_Name:contains:{search_name})"

                try:
                    response = zoho_client._make_request("GET", f"Contacts/search?criteria={search_query}")
                    if response.get("data"):
                        for contact in response["data"]:
                            existing = {
                                'candidate_name': contact.get('Full_Name', ''),
                                'company_name': contact.get('Account_Name', {}).get('name', '') if contact.get('Account_Name') else '',
                                'email': contact.get('Email', '')
                            }

                            if self.is_duplicate_candidate(extracted_data, existing, threshold=0.80):
                                logger.info(f"Found similar contact in Zoho: {contact.get('Full_Name')}")
                                return {
                                    'contact_id': contact.get('id'),
                                    'contact_name': contact.get('Full_Name'),
                                    'account_id': contact.get('Account_Name', {}).get('id') if contact.get('Account_Name') else None,
                                    'match_type': 'name_fuzzy'
                                }
                except Exception as e:
                    logger.warning(f"Error searching Zoho contacts by name: {e}")

            return None

        except Exception as e:
            logger.error(f"Error checking Zoho for duplicates: {e}")
            return None

    def should_block_duplicate(self, existing_record: Dict, threshold_seconds: int = 300) -> bool:
        """
        Determine if we should block creation based on existing record.
        Default: Block if duplicate was created within last 5 minutes (300 seconds).
        """
        if not existing_record:
            return False

        time_since = existing_record.get('time_since_creation', float('inf'))
        if time_since <= threshold_seconds:
            return True

        return False