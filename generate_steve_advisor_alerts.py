#!/usr/bin/env python3
"""
Generate Advisor Vault Candidate Alerts for Steve Perry.

Uses Zoho CRM + Zoom transcripts + TalentWell curator AI formatting.
Processes all 146 vault candidates from CSV export.

Usage:
    python3 generate_steve_advisor_alerts.py --csv Candidates_2025_10_09.csv --output Advisor_Vault_Candidate_Alerts.html

Environment Variables Required:
    - ZOHO_OAUTH_SERVICE_URL
    - ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET
    - OPENAI_API_KEY (for GPT-5 sentiment analysis)
"""

import asyncio
import csv
import logging
import argparse
import sys
import os
import re
import asyncpg
import hashlib
import json
import random
import time
import openai
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import AI bullet generator
from ai_bullet_generator import generate_rich_bullets_with_ai

from app.integrations import ZohoApiClient
from app.zoom_client import ZoomClient
from app.jobs.talentwell_curator import TalentWellCurator, retry_with_exponential_backoff
from app.config import PRIVACY_MODE, FEATURE_GROWTH_EXTRACTION, FEATURE_LLM_SENTIMENT

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_meeting_id_from_url(zoom_url: str) -> Optional[str]:
    """
    Extract Zoom meeting ID from various URL formats.

    Examples:
        - https://us02web.zoom.us/rec/share/ABC123...
        - https://us02web.zoom.us/rec/play/XYZ789...
        - https://zoom.us/j/1234567890

    Returns:
        Meeting ID string or None if not found
    """
    if not zoom_url:
        return None

    # Pattern 1: /rec/share/{id} or /rec/play/{id}
    match = re.search(r'/rec/(?:share|play)/([^/?]+)', zoom_url)
    if match:
        return match.group(1)

    # Pattern 2: /j/{numeric_id}
    match = re.search(r'/j/(\d+)', zoom_url)
    if match:
        return match.group(1)

    # Pattern 3: meeting_id= parameter
    match = re.search(r'meeting_id=([^&]+)', zoom_url)
    if match:
        return match.group(1)

    return None


def get_cache_key(fields: List[str], cvid: str) -> str:
    """
    Generate cache filename from field list + view ID hash.

    Args:
        fields: List of Zoho field names being fetched
        cvid: Custom view ID

    Returns:
        Cache filename like "vault_candidates_a1b2c3d4.json"
    """
    content = f"{cvid}:{','.join(sorted(fields))}"
    hash_val = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"vault_candidates_{hash_val}.json"


def format_location_string(candidate: Dict) -> str:
    """
    Format location string from discrete fields with mobility preferences.

    Phase 3: Uses city, state, and mobility boolean flags (in_office, hybrid, remote).

    Args:
        candidate: Dict with keys: city, state, is_mobile, in_office, hybrid, remote

    Returns:
        Formatted location string like:
        - "Austin, TX (Remote | Hybrid | In-office)"
        - "Texas (Is mobile)"
        - "Location TBD (Is not mobile)"

    Examples:
        {city: "Austin", state: "TX", remote: "Yes", hybrid: "Yes"} → "Austin, TX (Remote | Hybrid)"
        {city: "", state: "TX", is_mobile: True} → "Texas (Is mobile)"
        {city: "", state: "", is_mobile: False} → "Location TBD (Is not mobile)"
    """
    # Build base location
    if candidate.get('city') and candidate.get('state'):
        location_base = f"{candidate['city']}, {candidate['state']}"
    elif candidate.get('state'):
        location_base = candidate['state']
    else:
        location_base = "Location TBD"

    # Build mobility preference string
    mobility_parts = []

    # Helper function to check if candidate is open to a mobility preference
    def is_open_to(value: str) -> bool:
        """
        Check if candidate is open to a mobility preference.
        Zoho values: "Preferred", "Open", "Not Open", "Possibly/Depends"
        """
        if not value:
            return False
        val = str(value).strip().lower()
        # "Preferred" and "Open" mean they're interested
        # "Not Open" means they're not interested
        # "Possibly/Depends" we'll include since it's not a hard no
        # Also handle legacy "Yes"/"No" boolean values
        return val in ['preferred', 'open', 'possibly/depends', 'yes', 'true', '1']

    # Check discrete preference fields
    remote_val = candidate.get('remote', '')
    hybrid_val = candidate.get('hybrid', '')
    in_office_val = candidate.get('in_office', '')

    if is_open_to(remote_val):
        mobility_parts.append("Remote")

    if is_open_to(hybrid_val):
        mobility_parts.append("Hybrid")

    if is_open_to(in_office_val):
        mobility_parts.append("In-office")

    # If discrete preferences exist, use them
    if mobility_parts:
        return f"{location_base} ({' | '.join(mobility_parts)})"

    # Fallback to is_mobile boolean
    if candidate.get('is_mobile'):
        return f"{location_base} (Is mobile)"
    else:
        return f"{location_base} (Is not mobile)"


async def load_candidates_from_zoho(
    use_cache: bool = True,
    cache_ttl: int = None
) -> List[Dict]:
    """
    Fetch vault candidates from Zoho API with intelligent caching.

    Args:
        use_cache: Enable cache lookup/write (default True)
        cache_ttl: Cache lifetime in seconds (default 3600)

    Returns:
        List of candidate dicts with ALL Zoho CRM fields

    Raises:
        Exception: If API call fails and no cache available
    """
    from app.integrations import ZohoApiClient

    # Default cache TTL to 1 hour
    if cache_ttl is None:
        cache_ttl = int(os.getenv('VAULT_CACHE_TTL', '3600'))

    # Define complete field list (using actual Zoho API field names)
    fields = [
        'Full_Name',           # Maps to 'name'
        'First_Name',
        'Last_Name',
        'Candidate_Locator',   # TWAV codes - CRITICAL for privacy
        'Email',
        'Phone',
        'Mobile',
        'id',                  # Record ID
        'Designation',         # Maps to 'title'
        'City',
        'State',
        'Current_Location',    # Full location string
        'In_Office',           # NEW: Discrete preference field
        'Hybrid',              # NEW: Discrete preference field
        'Remote',              # NEW: Discrete preference field
        'Is_Mobile',
        'Location_Detail',     # NEW: Rich location string
        'Mobility_Details',    # NEW: Travel/relocation details
        'Cover_Letter_Recording_URL',
        'Employer',
        'Book_Size_AUM',
        'Production_L12Mo',
        'Professional_Designations',
        'Desired_Comp',
        'When_Available',
        'Top_Performance_Result',
        'Specialty_Area_Expertise',
        'Book_Size_Clients',
        'Headline',
        'Interviewer_Notes',   # PRIMARY data source for bullets
        'Background_Notes',
        'LinkedIn_Profile',
        'Full_Interview_URL',
        'Years_of_Experience',
        'Licenses_Exams_Confirmation_Notes'
    ]

    # Zoho custom view ID for vault candidates
    cvid = '6221978000090941003'  # "_Vault Candidates" view (filters Publish_to_Vault=true)

    # Get cache filename
    cache_dir = Path('.cache')
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / get_cache_key(fields, cvid)

    # Try cache first
    if use_cache and cache_file.exists():
        cache_age = datetime.now().timestamp() - cache_file.stat().st_mtime
        if cache_age < cache_ttl:
            logger.info(f"Using cached data from {cache_file.name} (age: {int(cache_age)}s)")
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                logger.info(f"Rate limit status: {cached.get('rate_limit', {})}")
                return cached['candidates']
        else:
            logger.info(f"Cache expired (age: {int(cache_age)}s > TTL: {cache_ttl}s)")

    # Fetch from Zoho API
    logger.info(f"Fetching vault candidates from Zoho API (view: {cvid})")
    logger.info(f"Requesting {len(fields)} fields from Zoho")

    zoho_client = ZohoApiClient()

    # Build pagination parameters
    page = 1
    per_page = 200  # Zoho max
    all_candidates = []

    while True:
        # Make API request
        response = await zoho_client.get_candidates(
            cvid=cvid,
            fields=fields,
            page=page,
            per_page=per_page
        )

        # Extract data
        data = response.get('data', [])
        info = response.get('info', {})

        # Track rate limits
        rate_limit = {
            'remaining': response.get('headers', {}).get('X-RateLimit-Remaining'),
            'reset': response.get('headers', {}).get('X-RateLimit-Reset'),
            'limit': response.get('headers', {}).get('X-RateLimit-Limit')
        }

        # Debug log if headers missing
        if not rate_limit['remaining']:
            logger.debug("Rate limit headers not returned by Zoho API (X-RateLimit-* headers missing)")
        elif int(rate_limit['remaining']) < 100:
            logger.warning(
                f"⚠️  Rate limit low: {rate_limit['remaining']}/{rate_limit['limit']} remaining "
                f"(resets at {rate_limit['reset']})"
            )

        # Detect silent truncation
        returned_count = info.get('count', len(data))
        if returned_count < per_page and info.get('more_records'):
            logger.warning(
                f"⚠️  Silent truncation detected: API returned {returned_count} < {per_page} "
                f"but claims more_records=true. Pagination may be broken."
            )

        all_candidates.extend(data)
        logger.info(f"Fetched page {page}: {len(data)} candidates (total: {len(all_candidates)})")

        # Check if more pages
        if not info.get('more_records'):
            break

        page += 1

    logger.info(f"Successfully fetched {len(all_candidates)} vault candidates from Zoho")

    # Helper to safely convert to string
    def safe_str(value):
        if value is None or value == 'None':  # Handle Zoho returning string "None"
            return ''
        return str(value).strip()

    # Convert Zoho records to internal format (map actual Zoho field names)
    formatted = []
    for record in all_candidates:
        # Parse city/state from Current_Location if discrete fields empty
        city = safe_str(record.get('City'))
        state = safe_str(record.get('State'))
        current_location = safe_str(record.get('Current_Location'))

        if not city and not state and current_location:
            # Parse "Austin, TX" format
            parts = current_location.split(',')
            if len(parts) == 2:
                city = parts[0].strip()
                state = parts[1].strip()

        # Normalize is_mobile to boolean (Zoho returns "Yes"/"No" strings)
        is_mobile_raw = safe_str(record.get('Is_Mobile'))
        is_mobile = is_mobile_raw.lower() in ['yes', 'true', '1']

        candidate = {
            'twav_number': safe_str(record.get('Candidate_Locator')),
            'name': safe_str(record.get('Full_Name')),           # FIXED: Full_Name not Candidate_Name
            'title': safe_str(record.get('Designation')),        # FIXED: Designation not Title
            'city': city,
            'state': state,
            'is_mobile': is_mobile,  # FIXED: Normalize to boolean
            'location_detail': safe_str(record.get('Location_Detail')),  # NEW
            'mobility_details': safe_str(record.get('Mobility_Details')),  # NEW
            'in_office': safe_str(record.get('In_Office')),  # NEW
            'hybrid': safe_str(record.get('Hybrid')),  # NEW
            'remote': safe_str(record.get('Remote')),  # NEW
            'zoom_url': safe_str(record.get('Cover_Letter_Recording_URL')),
            'email': safe_str(record.get('Email')),
            'phone': safe_str(record.get('Phone')),
            'mobile': safe_str(record.get('Mobile')),
            'record_id': safe_str(record.get('id')),             # FIXED: 'id' not 'Record_Id'

            # CRM enrichment fields
            'firm': safe_str(record.get('Employer')),
            'aum': safe_str(record.get('Book_Size_AUM')),
            'production': safe_str(record.get('Production_L12Mo')),
            'licenses': safe_str(record.get('Professional_Designations')),
            'compensation': safe_str(record.get('Desired_Comp')),
            'availability': safe_str(record.get('When_Available')),
            'top_performance': safe_str(record.get('Top_Performance_Result')),
            'specialty': safe_str(record.get('Specialty_Area_Expertise')),
            'book_size_clients': safe_str(record.get('Book_Size_Clients')),
            'headline': safe_str(record.get('Headline')),
            'interviewer_notes': safe_str(record.get('Interviewer_Notes')),
            'background_notes': safe_str(record.get('Background_Notes')),
            'linkedin': safe_str(record.get('LinkedIn_Profile')),
            'full_interview_url': safe_str(record.get('Full_Interview_URL')),
            'years_experience': safe_str(record.get('Years_of_Experience')),
            'licenses_confirmation': safe_str(record.get('Licenses_Exams_Confirmation_Notes')),
            'notes': []
        }

        # Build location string with mobility preferences (Phase 3)
        candidate['location'] = format_location_string(candidate)

        formatted.append(candidate)

    # Save to cache with metadata
    if use_cache:
        cache_data = {
            'candidates': formatted,
            'rate_limit': rate_limit,
            'fetched_at': datetime.now().isoformat(),
            'field_count': len(fields),
            'cvid': cvid
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"Cached {len(formatted)} candidates to {cache_file.name}")

    return formatted


def load_vault_candidates_from_csv(csv_path: str) -> List[Dict]:
    """
    Parse Candidates_2025_10_09.csv for vault candidates.

    Returns list of candidate dicts with ALL available Zoho CRM fields.
    """
    logger.info(f"Loading candidates from {csv_path}")

    # Increase CSV field size limit to handle long text fields
    csv.field_size_limit(1000000)

    candidates = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Build candidate dict from CSV columns (includes ALL Zoho fields)
            is_mobile_str = row.get('Is Mobile?', 'false').strip().lower()
            is_mobile = is_mobile_str in ['true', 'yes', '1']

            candidate = {
                'twav_number': row.get('Candidate Locator', '').strip(),
                'name': row.get('Candidate Name', '').strip(),
                'title': row.get('Title', '').strip(),
                'city': row.get('City', '').strip(),
                'state': row.get('State', '').strip(),
                'is_mobile': is_mobile,  # Parse boolean from CSV
                'in_office': row.get('In Office?', '').strip(),  # Discrete preference field
                'hybrid': row.get('Hybrid?', '').strip(),  # Discrete preference field
                'remote': row.get('Remote?', '').strip(),  # Discrete preference field
                'zoom_url': row.get('Cover Letter  Recording URL', '').strip(),
                'email': row.get('Email', '').strip(),
                'phone': row.get('Phone', '').strip(),
                'mobile': row.get('Mobile', '').strip(),
                'record_id': row.get('Record Id', '').strip(),

                # CRM enrichment fields from CSV
                'firm': row.get('Employer', '').strip(),
                'aum': row.get('Book Size (AUM)', '').strip(),
                'production': row.get('Production L12Mo', '').strip(),
                'licenses': row.get('Professional Designations', '').strip(),
                'compensation': row.get('Desired Comp', '').strip(),
                'availability': row.get('When Available?', '').strip(),
                'top_performance': row.get('Top Performance Result', '').strip(),
                'specialty': row.get('Specialty Area / Expertise', '').strip(),
                'book_size_clients': row.get('Book Size (Clients)', '').strip(),
                'headline': row.get('Headline', '').strip(),
                'interviewer_notes': row.get('Interviewer Notes', '').strip(),
                'background_notes': row.get('Background Notes', '').strip(),
                'candidate_experience': row.get('Candidate Experience', '').strip(),  # Resume/bio text
                'linkedin': row.get('LinkedIn Profile', '').strip(),
                'full_interview_url': row.get('Full Interview URL', '').strip(),
                'cover_letter_recording_url': row.get('Cover Letter  Recording URL', '').strip(),  # Note: double space in CSV header
                'notes': []  # Will add any additional notes
            }

            # Build location string with mobility preferences (Phase 3)
            candidate['location'] = format_location_string(candidate)

            # Skip candidates without TWAV number
            if not candidate['twav_number']:
                logger.warning(f"Skipping candidate {candidate['name']} - no TWAV number")
                continue

            candidates.append(candidate)

    logger.info(f"Loaded {len(candidates)} candidates with full CRM data from CSV")
    return candidates


async def enrich_candidate_from_zoho(
    candidate: Dict,
    zoho_client: ZohoApiClient
) -> Dict:
    """
    Placeholder for Zoho enrichment - CSV already contains all CRM data.

    CSV export includes: AUM, production, licenses, compensation, headline,
    interviewer notes, background notes, top performance, specialty, etc.

    This function is kept for future use if additional real-time data is needed.
    """
    # CSV already loaded all Zoho fields - no API call needed
    logger.debug(f"Using CSV data for {candidate['name']} (firm: {candidate.get('firm', 'N/A')})")
    return candidate


async def fetch_zoom_transcript(
    candidate: Dict,
    zoom_client: ZoomClient,
    db_pool
) -> Optional[str]:
    """
    Extract transcript from Zoom recording using CSV URL.

    Extracts meeting ID from 'cover_letter_recording_url' field,
    then fetches transcript using ZoomClient.
    """
    candidate_name = candidate.get('name', '')
    zoom_url = candidate.get('cover_letter_recording_url', '')

    if not zoom_url:
        logger.debug(f"No Zoom recording URL for {candidate_name}")
        return None

    # Extract meeting ID from URL
    meeting_id = extract_meeting_id_from_url(zoom_url)
    if not meeting_id:
        logger.warning(f"Could not extract meeting ID from URL for {candidate_name}: {zoom_url}")
        return None

    logger.info(f"Extracted meeting ID {meeting_id} from CSV URL for {candidate_name}")

    try:
        # Fetch transcript using ZoomClient
        transcript = await retry_with_exponential_backoff(
            zoom_client.fetch_zoom_transcript_for_meeting,
            meeting_id,
            max_retries=3,
            initial_delay=2.0,
            backoff_factor=2.0,
            max_delay=30.0
        )

        if transcript:
            logger.info(f"Successfully fetched Zoom transcript for {candidate_name} ({len(transcript)} chars)")
            return transcript
        else:
            logger.warning(f"Empty transcript returned for {candidate_name}")
            return None

    except Exception as e:
        logger.error(f"Error fetching Zoom transcript for {candidate_name}: {e}")
        return None


async def generate_candidate_bullets(
    candidate: Dict,
    curator: TalentWellCurator
) -> List[str]:
    """
    Extract bullets from rich biographical data (Interviewer Notes, Top Performance).

    PRIMARY SOURCES (in order of priority):
    1. Interviewer Notes - Rich biographical narrative
    2. Top Performance - Key achievements and metrics
    3. Zoom transcript (if available) - Supplemental context
    4. CSV fields (AUM, production, licenses, etc.) - Fill gaps

    Returns list of 3-5 bullet strings with specific details about experience, achievements, skills, availability.
    """
    try:
        # STEP 1: Try AI bullet generation with GPT-5-mini (NEW PRIMARY METHOD)
        interviewer_notes = candidate.get('interviewer_notes', '')
        top_performance = candidate.get('top_performance', '')

        if interviewer_notes or top_performance:
            logger.info(f"Using AI bullet generation for {candidate['name']}")

            # Generate structured bullets with AI
            structured_bullets = generate_rich_bullets_with_ai(candidate)

            if structured_bullets and len(structured_bullets) >= 3:
                # Convert structured bullets to HTML with <b> tags
                html_bullets = [render_bullet_with_emphasis(b) for b in structured_bullets]
                logger.info(f"AI generated {len(html_bullets)} rich bullets for {candidate['name']}")
                return html_bullets

            # AI failed or returned too few bullets - fall back to parser
            logger.info(f"AI generated {len(structured_bullets)} bullets, falling back to text parser for {candidate['name']}")
            parsed_bullets = parse_interviewer_notes_to_bullets(
                interviewer_notes=interviewer_notes,
                top_performance=top_performance,
                candidate=candidate
            )

            if len(parsed_bullets) >= 3:
                logger.info(f"Structured parsing extracted {len(parsed_bullets)} bullets for {candidate['name']}")
                return parsed_bullets

        # STEP 2: If structured parsing failed, try AI extraction with full biographical data
        # Build rich text context from ALL available sources
        rich_text_parts = []

        # ALWAYS include Interviewer Notes (primary source)
        if candidate.get('interviewer_notes'):
            rich_text_parts.append(f"INTERVIEWER NOTES:\n{candidate['interviewer_notes']}")

        # ALWAYS include Top Performance (key achievements)
        if candidate.get('top_performance'):
            rich_text_parts.append(f"TOP PERFORMANCE:\n{candidate['top_performance']}")

        # Include Background Notes if available
        if candidate.get('background_notes'):
            rich_text_parts.append(f"BACKGROUND:\n{candidate['background_notes']}")

        # Include Headline if available
        if candidate.get('headline'):
            rich_text_parts.append(f"HEADLINE:\n{candidate['headline']}")

        # Add Zoom transcript as supplemental context (if available)
        if candidate.get('transcript'):
            rich_text_parts.append(f"ZOOM TRANSCRIPT:\n{candidate['transcript']}")

        # Combine all sources into single rich text blob
        combined_text = "\n\n".join(rich_text_parts)

        if not combined_text.strip():
            # No rich text available - use basic CSV field extraction
            logger.warning(f"No rich biographical data for {candidate['name']} - using CSV field extraction")
            structured_fallback = generate_fallback_bullets_structured(candidate)
            return [render_bullet_with_emphasis(b) for b in structured_fallback]

        logger.info(f"Using AI extraction for {candidate['name']} ({len(combined_text)} chars of biographical data)")

        # Prepare candidate data for AI extraction
        candidate_data = {
            'name': candidate.get('name', 'Candidate'),
            'title': candidate.get('title', 'Financial Advisor'),
            'firm': candidate.get('firm', ''),
            'transcript': combined_text,  # Use combined rich text as "transcript"
            'aum': candidate.get('aum', ''),
            'production': candidate.get('production', ''),
            'licenses': candidate.get('licenses', ''),
            'headline': candidate.get('headline', ''),
            'interviewer_notes': candidate.get('interviewer_notes', ''),
            'background_notes': candidate.get('background_notes', ''),
            'top_performance': candidate.get('top_performance', '')
        }

        # Use curator's evidence extractor with rich biographical data
        bullet_points = curator.evidence_extractor.generate_bullets_with_evidence(
            candidate_data=candidate_data,
            transcript=combined_text,
            notes=candidate.get('notes', [])
        )

        if bullet_points:
            # Rank bullets using curator logic (top 5 by score)
            ranked_bullets = curator._rank_bullets_by_score(
                bullets=bullet_points,
                top_n=5
            )

            # Filter out useless AI-generated bullets and apply Steve's cleaning
            bullet_strings = []
            for bp in ranked_bullets:
                text = bp.text

                # Skip generic/useless bullets
                if any(skip in text for skip in [
                    'Holds NONE license',
                    'Holds None license',
                    'Additional details available',
                    'Additional information available'
                ]):
                    continue

                # Apply Steve's cleaning rules (remove candidate names!)
                cleaned = clean_bullet_text(text, candidate.get('name', ''))
                if cleaned:
                    bullet_strings.append(cleaned)

            # Deduplicate AI-extracted bullets
            bullet_strings = deduplicate_bullets(bullet_strings)

            # If AI extraction gave us 3+ good bullets, use them
            if len(bullet_strings) >= 3:
                logger.info(f"AI extracted {len(bullet_strings)} bullets for {candidate['name']}")
                return bullet_strings
            else:
                # AI extraction was weak - supplement with CSV field extraction
                logger.warning(f"AI only extracted {len(bullet_strings)} bullets for {candidate['name']} - supplementing with CSV fields")
                csv_structured = generate_fallback_bullets_structured(candidate)
                csv_bullets = [render_bullet_with_emphasis(b) for b in csv_structured]

                # Merge AI bullets + CSV bullets (deduplicate)
                all_bullets = bullet_strings + csv_bullets
                return deduplicate_bullets(all_bullets)[:5]  # Max 5 total

        # AI extraction failed - use CSV field extraction
        logger.warning(f"AI extraction failed for {candidate['name']} - using CSV field extraction")
        csv_structured = generate_fallback_bullets_structured(candidate)
        return [render_bullet_with_emphasis(b) for b in csv_structured]

    except Exception as e:
        logger.error(f"Error generating bullets for {candidate['name']}: {e}")
        csv_structured = generate_fallback_bullets_structured(candidate)
        return [render_bullet_with_emphasis(b) for b in csv_structured]


def clean_bullet_text(text: str, candidate_name: str = "") -> str:
    """
    Clean up bullet text to remove problematic patterns per Steve's feedback.

    Fixes:
    1. Remove candidate names (CRITICAL - no names in bullets, only REF codes)
    2. Remove internal recruiter notes ("depending on...", "had a hard time...")
    3. Remove company names to protect anonymity (Privacy Mode)
    4. Standardize repeated phrases
    5. Remove casual/uncertain language
    """
    if not text:
        return text

    # CRITICAL: Remove candidate names from bullets
    # Names should NEVER appear in marketing bullets - only in REF codes
    if candidate_name:
        # Split full name into parts
        name_parts = candidate_name.split()
        for part in name_parts:
            if len(part) > 2:  # Skip initials
                # Remove name with word boundaries
                text = re.sub(r'\b' + re.escape(part) + r'\b', '', text, flags=re.IGNORECASE)

    # Remove common first name patterns at start of sentence
    text = re.sub(r'^[A-Z][a-z]+\s+(became|brings|has|is|was|excels|manages|led)', r'\1', text)
    text = re.sub(r'^[A-Z][a-z]+\s+[A-Z][a-z]+\s+', '', text)  # Remove "Josh Kent"

    # Remove internal notes patterns
    internal_patterns = [
        r'depending on.*?(role|situation|circumstances|experience|his|her|their).*?[\.,]',
        r'depending on.*?$',
        r'had a hard time.*?[\.,]',
        r'had a hard time.*?$',
        r'\(depending on.*?\)',
        r'- internal note:.*?$',
        r'per internal.*?$',
        r'flexible depending.*?$',
        r'open to discussion.*?$'
    ]
    for pattern in internal_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # In Privacy Mode, anonymize company names
    if PRIVACY_MODE:
        # Anonymize specific company names in all contexts
        # Major wirehouses and banks (use \b word boundaries to avoid partial matches)
        text = re.sub(r'\bMerrill Lynch(?:\s+(?:Wealth Management|Pierce Fenner|Bank of America))?\b', 'a major wirehouse', text, flags=re.IGNORECASE)
        text = re.sub(r'\bMorgan Stanley(?:\s+(?:Wealth Management|Smith Barney))?\b', 'a major wirehouse', text, flags=re.IGNORECASE)
        text = re.sub(r'\bEdward Jones(?:\s+(?:Investments))?\b', 'a large brokerage firm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bWells Fargo(?:\s+(?:Advisors|Private Bank))?\b', 'a major bank', text, flags=re.IGNORECASE)
        text = re.sub(r'\bJP Morgan(?:\s+(?:Chase))?\b', 'a major bank', text, flags=re.IGNORECASE)
        text = re.sub(r'\bBank of America(?:\s+(?:Merrill))?\b', 'a major bank', text, flags=re.IGNORECASE)
        text = re.sub(r'\bUBS(?:\s+(?:Financial Services))?\b', 'a major wirehouse', text, flags=re.IGNORECASE)
        text = re.sub(r'\bFidelity(?:\s+(?:Investments))?\b', 'a large financial services firm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bVanguard(?:\s+(?:Group))?\b', 'a large financial services firm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bCharles Schwab(?:\s+(?:& Co))?\b', 'a large brokerage firm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bRaymond James(?:\s+(?:Financial))?\b', 'a financial services firm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bLPL Financial\b', 'an independent broker-dealer', text, flags=re.IGNORECASE)
        text = re.sub(r'\bAmeriprise(?:\s+(?:Financial))?\b', 'a financial services firm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bNorthwestern Mutual\b', 'an insurance and investment firm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bTIAA(?:\s+(?:Nuveen))?\b', 'a financial services firm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bCreative Planning\b', 'an RIA firm', text, flags=re.IGNORECASE)
        text = re.sub(r'\bMerrill Edge\b', 'an online brokerage', text, flags=re.IGNORECASE)
        text = re.sub(r'\bBNP Paribas\b', 'a major bank', text, flags=re.IGNORECASE)

        # Specific companies from Steve's feedback
        text = re.sub(r'Holland & Knight(?:\s+LLP)?', 'a national law firm', text)
        text = re.sub(r'Gottfried & Somberg(?:\s+Wealth Management)?', 'an RIA firm', text)
        text = re.sub(r'Nuance Investments(?:\s+LLC)?', 'an investment firm', text)

        # General patterns for any company name
        firms = [
            r'(?:at|with|of)\s+[A-Z][A-Za-z]+(?:\s+&\s+[A-Z][A-Za-z]+)?(?:\s+(?:Bank|Securities|Investments|Advisors|Capital|Wealth|Financial|Group|Partners|LLC|LLP|Inc|Corp))',
            r'Currently at [A-Z][^\.]+(?:LLC|LLP|Inc|Corp|Bank|Securities|Investments|Advisors)',
            r'works at [A-Z][^\.]+(?:LLC|LLP|Inc|Corp)',
            r',\s+[A-Z][A-Za-z\s&]+(?:LLC|LLP|Inc|Corp)$',
            r'(?:Financial Advisor|Advisor|Director|Manager|Associate)\s+at\s+[A-Z][^\.,]+'  # Job title + company
        ]
        for pattern in firms:
            text = re.sub(pattern, 'at a financial services firm', text, flags=re.IGNORECASE)

    # Remove duplicate words
    text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)

    return text.strip()


def normalize_compensation(comp_str: str) -> str:
    """
    Standardize compensation format per Steve's feedback.

    Examples:
        "95k Base + Commission 140+ OTE" -> "Target comp: $140K+ OTE"
        "$750k - $1.5million all in" -> "Target comp: $750K–$1.5M"
        "200-250k" -> "Target comp: $200K–$250K"
        "$100,000 - $150,000" -> "Target comp: $100K–$150K"
        "$100K or more, along with commission" -> "Target comp: $100K+"
        "Flexible depending on the role" -> "Target comp: Flexible"
    """
    if not comp_str:
        return ""

    comp_str = comp_str.strip()

    # Remove commas from numbers first
    comp_str = comp_str.replace(',', '')

    # Remove internal note patterns
    comp_str = re.sub(r'depending on.*?(role|situation|circumstances|experience).*?$', '', comp_str, flags=re.IGNORECASE).strip()
    comp_str = re.sub(r'depending on.*$', '', comp_str, flags=re.IGNORECASE).strip()
    comp_str = re.sub(r'along with.*$', '', comp_str, flags=re.IGNORECASE).strip()

    # Handle flexible/open responses
    if re.match(r'^(flexible|open|negotiable|tbd)$', comp_str, re.IGNORECASE):
        return f"Target comp: {comp_str.capitalize()}"

    # Extract numbers - handle ranges and single values
    # Pattern 1: Range like "$100000 - $150000" or "200k-250k"
    range_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*([kKmM])?\s*[-–to]\s*\$?(\d+(?:\.\d+)?)\s*([kKmM])?', comp_str, re.IGNORECASE)

    # Pattern 2: Single value with "or more" like "$100K or more"
    or_more_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*([kKmM])?.*?or more', comp_str, re.IGNORECASE)

    # Pattern 3: Any number
    single_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*([kKmM])?', comp_str, re.IGNORECASE)

    if range_match:
        low = range_match.group(1).lstrip('$')
        low_unit = range_match.group(2)
        high = range_match.group(3).lstrip('$')
        high_unit = range_match.group(4)

        # Determine unit (K or M)
        unit = high_unit or low_unit

        if not unit:
            # No K/M specified - check if numbers are > 999 (assume thousands)
            low_val = float(low)
            if low_val > 999:
                # Convert to K
                low = str(int(low_val / 1000))
                high = str(int(float(high) / 1000))
                unit_str = 'K'
            else:
                unit_str = 'K'
        elif unit.lower() == 'm':
            unit_str = 'M'
        else:
            unit_str = 'K'

        return f"Target comp: ${low}{unit_str}–${high}{unit_str}"

    elif or_more_match:
        amount = or_more_match.group(1).lstrip('$')
        unit = or_more_match.group(2)

        if not unit:
            # Check if > 999
            if float(amount) > 999:
                amount = str(int(float(amount) / 1000))
                unit_str = 'K'
            else:
                unit_str = 'K'
        elif unit.lower() == 'm':
            unit_str = 'M'
        else:
            unit_str = 'K'

        return f"Target comp: ${amount}{unit_str}+"

    elif single_match:
        amount = single_match.group(1).lstrip('$')
        unit = single_match.group(2)

        if not unit:
            # Check if > 999
            if float(amount) > 999:
                amount = str(int(float(amount) / 1000))
                unit_str = 'K'
            else:
                unit_str = 'K'
        elif unit.lower() == 'm':
            unit_str = 'M'
        else:
            unit_str = 'K'

        if 'ote' in comp_str.lower():
            return f"Target comp: ${amount}{unit_str}+ OTE"
        else:
            return f"Target comp: ${amount}{unit_str}+"

    # If we got here and comp_str is not empty, return it with label
    if comp_str:
        return f"Target comp: {comp_str}"

    return ""


def normalize_availability(avail_str: str) -> str:
    """
    Standardize availability format per Steve's feedback.

    Examples:
        "Available Available Immediately" -> "Available immediately"
        "2 weeks notice" -> "Available in 2 weeks"
        "Immediately" -> "Available immediately"
    """
    if not avail_str:
        return ""

    avail_str = avail_str.strip()

    # Remove duplicate "Available" words
    avail_str = re.sub(r'\bAvailable\s+Available\b', 'Available', avail_str, flags=re.IGNORECASE)

    # Standardize format
    if re.match(r'^immediately$', avail_str, re.IGNORECASE):
        return "Available immediately"
    elif re.match(r'^available\s+immediately$', avail_str, re.IGNORECASE):
        return "Available immediately"
    elif re.search(r'(\d+)\s*weeks?', avail_str, re.IGNORECASE):
        weeks = re.search(r'(\d+)', avail_str).group(1)
        return f"Available in {weeks} weeks"
    elif re.search(r'(\d+)\s*months?', avail_str, re.IGNORECASE):
        months = re.search(r'(\d+)', avail_str).group(1)
        return f"Available in {months} months"

    # Default: ensure it starts with "Available"
    if not avail_str.lower().startswith('available'):
        return f"Available {avail_str.lower()}"

    return avail_str


def round_aum_for_privacy(aum_str: str) -> str:
    """
    Round AUM values to broad ranges per Steve's feedback to protect anonymity.

    Examples:
        "$1.5B" -> "$1B+ AUM"
        "$9B" -> "$5B+ AUM"
        "300000000" -> "$250M+ AUM"
    """
    if not aum_str:
        return ""

    # Extract numeric value
    aum_str = str(aum_str).strip()

    # Try to parse the number
    try:
        # Remove $ and commas
        clean = re.sub(r'[\$,]', '', aum_str)

        # Check if it's already in K/M/B format
        if re.search(r'[BMK]', clean, re.IGNORECASE):
            match = re.search(r'([\d.]+)\s*([BMK])', clean, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                unit = match.group(2).upper()

                if unit == 'B':
                    if value >= 5:
                        return "$5B+ AUM"
                    elif value >= 1:
                        return "$1B+ AUM"
                    else:
                        return "$500M+ AUM"
                elif unit == 'M':
                    if value >= 500:
                        return "$500M+ AUM"
                    elif value >= 250:
                        return "$250M+ AUM"
                    elif value >= 100:
                        return "$100M+ AUM"
                    else:
                        return "$50M+ AUM"
        else:
            # Assume it's a raw number
            value = float(clean)

            if value >= 1_000_000_000:  # Billions
                billions = value / 1_000_000_000
                if billions >= 5:
                    return "$5B+ AUM"
                elif billions >= 1:
                    return "$1B+ AUM"
                else:
                    return "$500M+ AUM"
            elif value >= 1_000_000:  # Millions
                millions = value / 1_000_000
                if millions >= 500:
                    return "$500M+ AUM"
                elif millions >= 250:
                    return "$250M+ AUM"
                elif millions >= 100:
                    return "$100M+ AUM"
                else:
                    return "$50M+ AUM"
    except:
        pass

    return f"{aum_str} AUM"


def deduplicate_bullets(bullets: List[str]) -> List[str]:
    """
    Remove duplicate or near-duplicate bullets per Steve's feedback.

    Issues to fix:
    1. "15 years of experience" followed by "14 years of experience"
    2. "Holds Series 6, 7, 24, 63, 66" followed by "Holds Series 6, 7, 63, 66"
    3. Same information stated twice
    """
    if not bullets:
        return bullets

    unique_bullets = []
    seen_content = set()

    for bullet in bullets:
        # Normalize for comparison (lowercase, remove extra spaces)
        normalized = re.sub(r'\s+', ' ', bullet.lower().strip())

        # Check if we've seen very similar content
        is_duplicate = False
        for seen in seen_content:
            # If 80% of words match, consider it a duplicate
            bullet_words = set(normalized.split())
            seen_words = set(seen.split())
            if bullet_words and seen_words:
                overlap = len(bullet_words & seen_words) / max(len(bullet_words), len(seen_words))
                if overlap > 0.8:
                    is_duplicate = True
                    break

        if not is_duplicate:
            unique_bullets.append(bullet)
            seen_content.add(normalized)

    return unique_bullets


def generate_rich_bullets_with_ai(candidate: Dict) -> List[Dict[str, any]]:
    """
    Use GPT-5-mini to generate 4 structured bullets (3 if data sparse) matching screenshot format.

    Returns structured format:
        [
            {
                "text": "8 years in institutional investment sales...",
                "emphasis": ["8 years", "RIAs", "family offices"],
                "source_field": "interviewer_notes"
            },
            ...
        ]

    Temperature: 0.2 with input randomization for variety without hallucination risk.
    """

    # Build fact-only context
    context = {}

    # CRITICAL: Include resume/bio first (richest data source)
    if candidate.get('candidate_experience'):
        context['candidate_experience'] = f"Resume/Experience:\n{candidate['candidate_experience']}"

    if candidate.get('years_experience'):
        context['years_experience'] = f"Years of experience: {candidate['years_experience']}"

    if candidate.get('licenses') or candidate.get('licenses_confirmation'):
        licenses = candidate.get('licenses') or candidate.get('licenses_confirmation')
        context['licenses'] = f"Licenses and designations: {licenses}"

    if candidate.get('interviewer_notes'):
        context['interviewer_notes'] = f"Interview notes:\n{candidate['interviewer_notes']}"

    if candidate.get('top_performance'):
        context['top_performance'] = f"Top performance:\n{candidate['top_performance']}"

    if candidate.get('headline'):
        context['headline'] = f"Headline: {candidate['headline']}"

    if candidate.get('aum'):
        context['aum'] = f"AUM/Book size: {candidate['aum']}"

    if candidate.get('production'):
        context['production'] = f"Production: {candidate['production']}"

    if candidate.get('background_notes'):
        context['background_notes'] = f"Background:\n{candidate['background_notes']}"

    # Check if we have enough data
    total_chars = sum(len(str(v)) for v in context.values())
    target_bullet_count = 4 if total_chars > 500 else 3

    # CRITICAL: Randomize input order for variety (instead of high temperature)
    context_items = list(context.items())
    random.shuffle(context_items)
    biographical_data = '\n\n'.join([v for k, v in context_items])

    # Build prompt
    prompt = f"""You are writing marketing bullets for a financial advisor candidate alert.

CANDIDATE DATA:
{biographical_data}

TASK: Generate exactly {target_bullet_count} structured bullets in JSON format.

REQUIREMENTS:
1. Each bullet: 1-3 sentences with specific metrics (years, AUM, growth %)
2. Bold key achievements using emphasis keywords (NO <b> tags in text)
3. Keywords to emphasize:
   - Financial metrics: "$650M AUM", "$10M-$15M+", "40% growth"
   - Designations: "MBA", "CFA", "CFP", "CPRC", "MDRT"
   - Client types: "HNW", "UHNW", "institutional", "RIAs"
   - Rankings: "top 5%", "ranked #31 nationally"
4. NO candidate names (privacy requirement)
5. Extract from source data ONLY - no fabrication

RETURN FORMAT:
{{
    "bullets": [
        {{
            "text": "Full bullet text here",
            "emphasis": ["keyword1", "keyword2"],
            "source_field": "interviewer_notes"
        }}
    ]
}}
"""

    # Retry logic for OpenAI API (same pattern as Zoom client)
    max_retries = 3
    base_delay = 1.0
    result_json = None

    for attempt in range(max_retries):
        try:
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

            response = client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting facts from biographical data for financial advisor marketing."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1,  # Required by gpt-5 (only supported value)
                response_format={"type": "json_object"}
            )

            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)

            # Success - break retry loop
            break

        except (openai.APIConnectionError, openai.RateLimitError, openai.APITimeoutError) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"OpenAI API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay:.1f}s...")
                time.sleep(delay)  # Use time.sleep, not asyncio.sleep (this is not async)
            else:
                logger.warning(f"OpenAI API failed after {max_retries} attempts: {e}")
                return []
        except Exception as e:
            logger.warning(f"AI bullet generation failed: {e}")
            return []

    # Check if we got a valid response
    if result_json is None:
        logger.warning(f"AI bullet generation failed after {max_retries} retries")
        return []

    bullets = result_json.get('bullets', [])

    # Verify minimum bullet count
    if len(bullets) < target_bullet_count:
        logger.warning(f"AI generated {len(bullets)} bullets, expected {target_bullet_count}")

    # CRITICAL: Post-anonymization emphasis verification
    verified_bullets = []
    for bullet in bullets:
        text = bullet.get('text', '')
        emphasis_keywords = bullet.get('emphasis', [])

        # Remove candidate name if it leaked through
        if candidate.get('name'):
            name_parts = candidate['name'].split()
            for part in name_parts:
                if len(part) > 2:  # Skip initials
                    text = re.sub(r'\b' + re.escape(part) + r'\b', '', text, flags=re.IGNORECASE)

        # Verify each emphasis keyword exists in anonymized text
        valid_emphasis = []
        for keyword in emphasis_keywords:
            if keyword.lower() in text.lower():
                valid_emphasis.append(keyword)
            else:
                logger.debug(f"Emphasis keyword '{keyword}' not found in anonymized text, dropping")

        verified_bullets.append({
            'text': text.strip(),
            'emphasis': valid_emphasis,
            'source_field': bullet.get('source_field', 'unknown')
        })

    return verified_bullets[:target_bullet_count]


def render_bullet_with_emphasis(structured_bullet: Dict) -> str:
    """
    Render structured bullet with HTML <b> tags around emphasis keywords.

    Args:
        structured_bullet: {text: str, emphasis: List[str], source_field: str}

    Returns:
        HTML string with <b> tags: "8 years in <b>RIAs</b> and <b>family offices</b>"
    """
    text = structured_bullet.get('text', '')
    emphasis_keywords = structured_bullet.get('emphasis', [])

    # Sort keywords by length (longest first) to avoid partial replacements
    emphasis_keywords = sorted(emphasis_keywords, key=len, reverse=True)

    for keyword in emphasis_keywords:
        # Case-insensitive replacement with <b> tags
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        text = pattern.sub(f'<b>{keyword}</b>', text)

    return text


def parse_interviewer_notes_to_bullets(interviewer_notes: str, top_performance: str, candidate: Dict) -> List[str]:
    """
    Parse rich biographical text into 3-4 marketing bullets that sell the candidate.

    Target format:
    - "15+ years in financial services; SIE, Series 7, 66; Life & Health Insurance; SE-AWMA designation"
    - "Built $15M+ book from scratch at national bank in under 2 years; previously led $120M 401(k) ERISA book; top advisor within 6 months"
    - "Skilled in Salesforce, MS Office; emphasizes communication, regular client contact, milestone follow-ups"
    - "Available immediately; Target comp: $100K–$150K"

    Returns 3-4 bullets (NO names, just marketing facts).
    """
    bullets = []
    combined_text = f"{interviewer_notes}\n\n{top_performance}"

    # BULLET 1: Years + ALL Licenses/Designations
    bullet1_parts = []

    # Extract years
    years_match = re.search(r'(\d+)\+?\s*years?', combined_text, re.IGNORECASE)
    if years_match:
        bullet1_parts.append(f"{years_match.group(1)}+ years in financial services")

    # Extract ALL licenses and designations
    license_parts = []

    # SIE
    if re.search(r'\bSIE\b', combined_text):
        license_parts.append('SIE')

    # Series licenses
    series_matches = re.findall(r'Series\s+(\d{1,2})', combined_text, re.IGNORECASE)
    if series_matches:
        unique_series = sorted(set(series_matches), key=lambda x: int(x))
        license_parts.append('Series ' + ', '.join(unique_series))

    # Life & Health
    if re.search(r'\bLife\s+(?:&|and)\s+Health', combined_text, re.IGNORECASE):
        license_parts.append('Life & Health Insurance')

    # Designations
    for pattern in [r'\bSE-AWMA\b', r'\bCFA\b', r'\bCFP\b', r'\bCRPC\b', r'\bRICP\b']:
        match = re.search(pattern, combined_text)
        if match:
            license_parts.append(f"{match.group(0)} designation")

    if license_parts:
        bullet1_parts.extend(license_parts)

    if bullet1_parts:
        bullets.append('; '.join(bullet1_parts))

    # BULLET 2: Top Achievements ($ figures, rankings, timeframes)
    achievement_parts = []

    # Extract specific achievements from top_performance field (highest priority)
    if top_performance:
        # Clean and take full text as primary achievement (NO NAME!)
        primary_achievement = clean_bullet_text(top_performance.strip(), candidate.get('name', ''))
        if primary_achievement:
            # Truncate at sentence boundary
            sentences = re.split(r'[\.!]\s+', primary_achievement)
            if sentences and len(sentences[0]) < 200:
                achievement_parts.append(sentences[0])

    # Extract AUM/production figures from interviewer notes
    aum_matches = re.findall(r'(\$\d+(?:\.\d+)?[BMK])\s+(?:in\s+)?(?:managed money|AUM|book|401\(k\)|ERISA)', combined_text, re.IGNORECASE)
    unique_aum = list(dict.fromkeys(aum_matches))  # Preserve order, remove dupes
    if unique_aum and len(achievement_parts) == 0:
        # If no top_performance, use AUM as primary achievement
        achievement_parts.extend([f"{amt} AUM" for amt in unique_aum[:2]])

    if achievement_parts:
        bullets.append('; '.join(achievement_parts[:2]))  # Max 2 achievement phrases

    # BULLET 3: Skills/Strengths (technical skills, soft skills)
    skill_parts = []

    # Extract technical skills (Salesforce, MS Office, platforms)
    tech_skills = []
    if re.search(r'\bSalesforce\b', combined_text, re.IGNORECASE):
        tech_skills.append('Salesforce')
    if re.search(r'\bMS Office\b', combined_text, re.IGNORECASE):
        tech_skills.append('MS Office')

    if tech_skills:
        skill_parts.append(f"Skilled in {', '.join(tech_skills)}")

    # Extract soft skills/strengths (look for descriptive phrases)
    strength_keywords = [
        'communication', 'client education', 'relationship', 'trust',
        'collaboration', 'leadership', 'mentoring', 'coaching'
    ]

    # Find sentences containing strength keywords
    sentences = re.split(r'[\.!]\s+', interviewer_notes)
    for sentence in sentences:
        for keyword in strength_keywords:
            if keyword in sentence.lower() and len(sentence) < 150:
                cleaned = clean_bullet_text(sentence.strip(), candidate.get('name', ''))
                if cleaned and len(cleaned) > 20:
                    # Extract the key phrase (remove unnecessary context)
                    # Look for patterns like "excels in X", "strong background in X", "skilled in X"
                    key_phrase_match = re.search(r'(?:excels?|skilled|strong|proven|extensive|emphasizes?|focused)\s+(?:in|on|at|with)\s+([^,\.;]{15,100})', cleaned, re.IGNORECASE)
                    if key_phrase_match:
                        skill_parts.append(f"emphasizes {key_phrase_match.group(1)}")
                        break
        if len(skill_parts) >= 2:  # Stop after finding 2 skills
            break

    if skill_parts:
        bullets.append('; '.join(skill_parts[:2]))  # Max 2 skill phrases

    # BULLET 4: Availability + Compensation (ALWAYS include if available)
    practical = []

    if candidate.get('availability'):
        avail = normalize_availability(candidate['availability'])
        if avail:
            practical.append(avail)

    if candidate.get('compensation'):
        comp = normalize_compensation(candidate['compensation'])
        if comp:
            practical.append(comp)

    if practical:
        bullets.append('; '.join(practical))

    return bullets[:4]  # Exactly 3-4 bullets


def generate_fallback_bullets_structured(candidate: Dict) -> List[Dict]:
    """
    Generate 3-4 structured bullets with emphasis keywords for fallback path.

    Returns structured format matching AI output:
    [{text: str, emphasis: List[str], source_field: str}]

    This ensures consistent formatting across AI and fallback paths.
    """
    plain_bullets = generate_fallback_bullets_plain(candidate)

    # Convert plain bullets to structured format with emphasis extraction
    structured_bullets = []

    # Define patterns for emphasis keywords
    financial_patterns = [
        r'\$[\d,]+[BMK]?(?:\s*(?:AUM|production|clients))?',  # $650M, $10M AUM, $5M production
        r'\d+\+?\s*years?',  # 10+ years, 15 years
        r'\d+%',  # 40%, 25%
        r'top\s+\d+%',  # top 5%
    ]

    designation_patterns = [
        r'\b(?:CFP|CFA|MBA|CPRC|MDRT|CLU|ChFC|CPA)\b',  # Professional designations
    ]

    for bullet in plain_bullets:
        emphasis_keywords = []

        # Extract financial metrics for emphasis
        for pattern in financial_patterns:
            matches = re.findall(pattern, bullet, re.IGNORECASE)
            emphasis_keywords.extend(matches)

        # Extract designations for emphasis
        for pattern in designation_patterns:
            matches = re.findall(pattern, bullet, re.IGNORECASE)
            emphasis_keywords.extend(matches)

        # Deduplicate emphasis keywords
        emphasis_keywords = list(dict.fromkeys(emphasis_keywords))

        structured_bullets.append({
            'text': bullet,
            'emphasis': emphasis_keywords,
            'source_field': 'csv_fallback'
        })

    return structured_bullets


def generate_fallback_bullets_plain(candidate: Dict) -> List[str]:
    """
    Generate 3-4 plain text MARKETING BULLETS (used internally by structured wrapper).

    Format: Concise, punchy bullets highlighting:
    - Years of experience + AUM/production metrics
    - Specialty areas and key strengths
    - Licenses and certifications
    - Availability and compensation

    NO long biographical paragraphs - just the best selling points.
    """
    bullets = []

    # BULLET 1: Experience + AUM/Production (the "wow" factor)
    experience_parts = []

    # Extract years from ALL text fields (headline, interviewer_notes, top_performance)
    years_text = ' '.join([
        str(candidate.get('headline', '') or ''),
        str(candidate.get('interviewer_notes', '') or ''),
        str(candidate.get('top_performance', '') or ''),
        str(candidate.get('title', '') or '')
    ])
    years_match = re.search(r'(\d+)\+?\s*years?', years_text, re.IGNORECASE)
    if years_match:
        experience_parts.append(f"{years_match.group(1)}+ years experience")

    # Add AUM if available (rounded for privacy) - this is HIGH PRIORITY
    if candidate.get('aum'):
        aum = round_aum_for_privacy(candidate['aum'])
        if aum and aum != ' AUM':
            experience_parts.append(aum)

    # Add production if available
    if candidate.get('production'):
        prod = str(candidate['production']).strip()
        if prod and prod.upper() not in ['NONE', 'N/A', 'NA', '-', '']:
            if not prod.startswith('$'):
                prod = f"${prod}"
            experience_parts.append(f"{prod} production")

    # Add book size (clients) if available
    if candidate.get('book_size_clients'):
        clients = str(candidate['book_size_clients']).strip()
        if clients and clients.upper() not in ['NONE', 'N/A', 'NA', '-', '']:
            experience_parts.append(f"{clients} clients")

    if experience_parts:
        bullets.append(' | '.join(experience_parts))

    # BULLET 2: Specialty + ONE Key Strength
    specialty_parts = []

    if candidate.get('specialty'):
        spec = str(candidate['specialty']).strip()
        if spec and spec.upper() not in ['NONE', 'N/A', 'NA', '-']:
            specialty_parts.append(f"Specialty: {spec}")

    # Extract ONE concise strength from top performance or interviewer notes
    strength = None
    if candidate.get('top_performance'):
        strength = clean_bullet_text(str(candidate['top_performance']), candidate.get('name', ''))
        if strength and len(strength) > 150:
            # Truncate at sentence boundary
            sentences = re.split(r'[\.!]\s+', strength)
            strength = sentences[0] if sentences else strength[:150]
    elif candidate.get('interviewer_notes'):
        notes = str(candidate['interviewer_notes']).strip()
        if notes:
            # Extract first sentence or 150 chars
            cleaned = clean_bullet_text(notes, candidate.get('name', ''))
            sentences = re.split(r'[\.!]\s+', cleaned)
            strength = sentences[0] if sentences and len(sentences[0]) < 150 else cleaned[:150]

    if strength:
        specialty_parts.append(strength)

    if specialty_parts:
        bullets.append(' | '.join(specialty_parts))

    # BULLET 3: Licenses ONLY (exclude certifications like CFP)
    if candidate.get('licenses'):
        lic_str = str(candidate['licenses']).strip()
        if lic_str and lic_str.upper() not in ['NONE', 'N/A', 'NA', '-', '']:
            # Extract ONLY Series numbers (7, 63, 65, 66, etc.)
            series_matches = re.findall(r'\b(\d{1,3})\b', lic_str)
            if series_matches:
                # Sort numerically and format as "Series 7, 63, 65"
                series_list = ', '.join(sorted(set(series_matches), key=lambda x: int(x)))
                bullets.append(f'Licenses: Series {series_list}')
            # If no Series numbers but other licenses, show them
            elif not re.search(r'\bCFP\b', lic_str, re.IGNORECASE):
                bullets.append(f'Licenses: {lic_str}')

    # BULLET 4: Availability + Compensation (the practical details)
    practical = []

    if candidate.get('availability'):
        avail_bullet = normalize_availability(candidate['availability'])
        if avail_bullet:
            # Remove "Available" prefix since we'll add it
            avail_clean = avail_bullet.replace('Available ', '').strip()
            if avail_clean:
                practical.append(f"Available: {avail_clean}")

    if candidate.get('compensation'):
        comp_bullet = normalize_compensation(candidate['compensation'])
        if comp_bullet:
            practical.append(comp_bullet)

    if practical:
        bullets.append(' | '.join(practical))

    # Return 3-4 bullets (no biographical paragraphs)
    return bullets[:4]


def render_advisor_alerts_html(candidates: List[Dict], output_path: str):
    """
    Generate HTML matching Advisor_Vault_Candidate_Alerts.html format.

    Brandon's format:
    - ‼️ **Candidate Name Alert** 🔔
    - 📍 **Location**
    - 5 bullets (NOT more, NOT fewer)
    - Ref code: TWAV#####
    """
    logger.info(f"Rendering HTML for {len(candidates)} candidates")

    html_parts = ['''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Advisor Vault Candidate Alerts - ''' + datetime.now().strftime('%B %d, %Y') + '''</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .email-container {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
            padding: 20px;
        }
        p {
            margin: 12px 0;
        }
        ul {
            margin: 10px 0 20px 0;
            padding-left: 25px;
        }
        li {
            margin: 8px 0;
        }
        b {
            font-weight: 600;
        }
        .ref-code {
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }
        .candidate-card {
            border-bottom: 1px solid #eee;
            padding-bottom: 20px;
            margin-bottom: 20px;
        }
        .candidate-card:last-child {
            border-bottom: none;
        }
    </style>
</head>
<body>
    <div class="email-container">
        <h1>Advisor Vault Candidate Alerts</h1>
        <p><i>Generated: ''' + datetime.now().strftime('%B %d, %Y at %I:%M %p') + '''</i></p>
        <p><b>Total Candidates: ''' + str(len(candidates)) + '''</b></p>
        <hr>
''']

    for candidate in candidates:
        html_parts.append('\n<div class="candidate-card">')

        # Header WITHOUT candidate name (Steve's privacy requirement)
        # Format: "Senior Advisor Candidate Alert" or "Director / Lead Advisor Candidate Alert"
        title = candidate.get('title', 'Advisor')

        # Remove company names AND candidate names from title (Privacy Mode)
        if PRIVACY_MODE:
            title = clean_bullet_text(title, candidate.get('name', ''))  # Apply same company anonymization + name removal

        alert_title = f"{title} Candidate Alert"

        # Location already formatted by format_location_string() (Phase 3)
        location = candidate['location']

        html_parts.append(f'''
<p>‼️ <b>{alert_title}</b> 🔔<br>
📍 <b>{location}</b></p>
<ul>
''')

        # Add bullets (ONLY REAL DATA - can be fewer than 5)
        bullets = candidate.get('bullets', [])
        if bullets:
            for bullet in bullets[:5]:  # Max 5, but can be fewer
                html_parts.append(f'\n<li>{bullet}</li>')
        else:
            # If no bullets at all, show minimal info
            html_parts.append(f'\n<li>{candidate.get("title", "Financial Advisor")}</li>')

        html_parts.append('\n</ul>')

        # TWAV reference code
        html_parts.append(f'\n<p class="ref-code">Ref code: {candidate["twav_number"]}</p>')

        html_parts.append('\n</div>')

    html_parts.append('''
    </div>
</body>
</html>''')

    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(html_parts))

    logger.info(f"Generated {output_path} with {len(candidates)} candidates")


async def process_candidate(
    candidate: Dict,
    zoho_client: ZohoApiClient,
    zoom_client: ZoomClient,
    curator: TalentWellCurator,
    db_conn
) -> Dict:
    """
    Process a single candidate: enrich from Zoho, fetch Zoom transcript, extract bullets.
    """
    logger.info(f"Processing {candidate['name']} ({candidate['twav_number']})")

    # Step 1: Enrich from Zoho
    candidate = await enrich_candidate_from_zoho(candidate, zoho_client)

    # Step 2: Fetch Zoom transcript from database by participant name
    transcript = await fetch_zoom_transcript(candidate, zoom_client, db_conn)
    candidate['transcript'] = transcript

    # Step 3: Generate bullets using TalentWell curator
    bullets = await generate_candidate_bullets(candidate, curator)
    candidate['bullets'] = bullets

    logger.info(f"Completed processing {candidate['name']}")
    return candidate


async def main():
    """Main function to generate Steve's Advisor Vault Candidate Alerts."""

    # Parse CLI arguments
    parser = argparse.ArgumentParser(
        description='Generate Advisor Vault Candidate Alerts for Steve Perry'
    )
    parser.add_argument(
        '--csv',
        default='Candidates_2025_10_09.csv',
        help='Path to CSV export of vault candidates'
    )
    parser.add_argument(
        '--output',
        default='Advisor_Vault_Candidate_Alerts.html',
        help='Output HTML file path'
    )
    parser.add_argument(
        '--max-candidates',
        type=int,
        default=146,
        help='Maximum number of candidates to process'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: process only first 5 candidates'
    )
    parser.add_argument(
        '--parallel',
        type=int,
        default=10,
        help='Number of parallel candidate processing tasks'
    )
    parser.add_argument(
        '--source',
        choices=['csv', 'zoho'],
        default='csv',
        help='Data source: csv (local file) or zoho (API with cache)'
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable Zoho API cache (always fetch fresh data)'
    )
    parser.add_argument(
        '--cache-ttl',
        type=int,
        default=3600,
        help='Cache TTL in seconds (default: 3600 = 1 hour)'
    )

    args = parser.parse_args()

    # Override max candidates in test mode
    if args.test:
        args.max_candidates = 5
        logger.info("TEST MODE: Processing only 5 candidates")

    logger.info(f"Starting Advisor Vault Candidate Alerts generation")
    logger.info(f"Data source: {args.source}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Max candidates: {args.max_candidates}")
    logger.info(f"Privacy mode: {PRIVACY_MODE}")
    logger.info(f"Growth extraction: {FEATURE_GROWTH_EXTRACTION}")
    logger.info(f"LLM sentiment: {FEATURE_LLM_SENTIMENT}")

    # Load candidates from selected source
    if args.source == 'zoho':
        logger.info(f"Loading from Zoho API (cache: {not args.no_cache}, TTL: {args.cache_ttl}s)")
        candidates = await load_candidates_from_zoho(
            use_cache=not args.no_cache,
            cache_ttl=args.cache_ttl
        )
    else:
        logger.info(f"Loading from CSV: {args.csv}")
        candidates = load_vault_candidates_from_csv(args.csv)

    if len(candidates) == 0:
        logger.error("No candidates found in CSV. Exiting.")
        return

    # Limit to max_candidates
    candidates = candidates[:args.max_candidates]
    logger.info(f"Processing {len(candidates)} candidates")

    # Initialize clients
    logger.info("Initializing Zoho client...")
    zoho_client = ZohoApiClient()
    # Note: ZoomClient will be created per-task to avoid race conditions in parallel execution

    # Initialize TalentWell curator
    logger.info("Initializing TalentWell curator...")
    curator = TalentWellCurator()
    await curator.initialize()

    # Create PostgreSQL connection pool for Zoom meeting lookups (parallel-safe)
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not set in environment")
        return

    logger.info("Creating PostgreSQL connection pool...")
    db_pool = await asyncpg.create_pool(database_url, min_size=5, max_size=20)

    try:
        # Process candidates in parallel batches
        processed_candidates = []
        batch_size = args.parallel

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(candidates) + batch_size - 1)//batch_size}")

            # Process batch in parallel (each task gets its own ZoomClient + connection from pool)
            tasks = [
                process_candidate(candidate, zoho_client, ZoomClient(), curator, db_pool)
                for candidate in batch
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and add successful results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Error processing candidate: {result}")
                else:
                    processed_candidates.append(result)

        logger.info(f"Successfully processed {len(processed_candidates)}/{len(candidates)} candidates")

        # Generate HTML
        render_advisor_alerts_html(processed_candidates, args.output)

        logger.info(f"✅ Advisor Vault Candidate Alerts generation complete!")
        logger.info(f"Output: {args.output}")
        logger.info(f"Total candidates: {len(processed_candidates)}")

    finally:
        # Close database connection pool
        await db_pool.close()
        logger.info("Database connection pool closed")


if __name__ == "__main__":
    asyncio.run(main())
