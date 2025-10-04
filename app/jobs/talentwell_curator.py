"""
TalentWell curator for generating weekly digests.
Orchestrates filtering, normalization, caching, and rendering.
"""
import json
import logging
import asyncio
import re
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import hashlib
from dotenv import load_dotenv

from app.redis_cache_manager import get_cache_manager
from app.cache.c3 import c3_reuse_or_rebuild, C3Entry, DependencyCertificate
from app.cache.voit import voit_orchestration
from app.extract.evidence import EvidenceExtractor, BulletPoint
from app.templates.ast import ASTCompiler
from app.bandits.subject_bandit import SubjectLineBandit as SubjectBandit
from app.integrations import get_zoho_headers, fetch_deal_from_zoho
from app.config import VoITConfig

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')


async def retry_with_exponential_backoff(
    func,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 30.0,
    **kwargs
):
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        backoff_factor: Multiplier for delay after each retry (default: 2.0)
        max_delay: Maximum delay between retries in seconds (default: 30.0)

    Returns:
        Function result on success, None on failure after all retries

    Example delays with default settings:
    - Attempt 1: 0s (immediate)
    - Attempt 2: 1s delay
    - Attempt 3: 2s delay
    - Attempt 4: 4s delay
    """
    last_exception = None
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            # Attempt the function call
            result = await func(*args, **kwargs)
            if result is not None or attempt == 0:
                # Success or first attempt
                if attempt > 0:
                    logger.info(f"Retry successful on attempt {attempt + 1}")
                return result

        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                # Calculate delay with exponential backoff
                current_delay = min(delay, max_delay)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {current_delay:.1f}s..."
                )
                await asyncio.sleep(current_delay)
                delay *= backoff_factor
            else:
                logger.error(
                    f"All {max_retries + 1} attempts failed. Last error: {e}"
                )

    return None


@dataclass
class DigestCard:
    """Represents a candidate card in the digest."""
    deal_id: str
    candidate_name: str
    job_title: str
    company: str
    location: str
    bullets: List[BulletPoint]
    metro_area: Optional[str] = None
    firm_type: Optional[str] = None
    source: Optional[str] = None
    source_detail: Optional[str] = None
    meeting_date: Optional[datetime] = None
    transcript_url: Optional[str] = None
    evidence_score: float = 0.0
    # Sentiment analysis fields
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    enthusiasm_score: Optional[float] = None
    professionalism_score: Optional[float] = None
    concerns_detected: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['bullets'] = [b.to_dict() for b in self.bullets]
        if self.meeting_date:
            result['meeting_date'] = self.meeting_date.isoformat()
        return result


class TalentWellCurator:
    """Orchestrates weekly digest generation."""

    # Company anonymization mapping for privacy
    FIRM_TYPE_MAP = {
        'wirehouse': ['Merrill Lynch', 'Morgan Stanley', 'Wells Fargo', 'UBS', 'Raymond James'],
        'ria': ['Nuance Investments', 'Gottfried & Somberg', 'Fisher Investments', 'Edelman Financial'],
        'bank': ['JPMorgan', 'Bank of America', 'Wells Fargo Advisors', 'Citigroup'],
        'insurance': ['Northwestern Mutual', 'MassMutual', 'New York Life', 'Prudential']
    }

    def __init__(self):
        self.cache_manager = None
        self.redis_client = None
        self.evidence_extractor = EvidenceExtractor()
        self.ast_compiler = ASTCompiler()
        self.subject_bandit = None
        self.initialized = False
        
    async def initialize(self):
        """Initialize async components."""
        if self.initialized:
            return
            
        self.cache_manager = await get_cache_manager()
        if self.cache_manager:
            self.redis_client = self.cache_manager.client
        
        # SubjectBandit handles its own initialization
        self.subject_bandit = SubjectBandit("steve_perry")
        
        self.initialized = True
        logger.info("TalentWell curator initialized")
        
    async def run_weekly_digest(
        self,
        audience: str = "steve_perry",
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        owner: Optional[str] = None,
        dry_run: bool = False,
        ignore_cooldown: bool = False
    ) -> Dict[str, Any]:
        """Generate weekly digest for specified audience and date range."""
        
        if not self.initialized:
            await self.initialize()
        
        # Default date range: last 7 days
        if not to_date:
            to_date = datetime.now()
        if not from_date:
            from_date = to_date - timedelta(days=7)
            
        logger.info(f"Generating digest for {audience} from {from_date} to {to_date}, owner={owner}, ignore_cooldown={ignore_cooldown}")
        
        # Track timing for Application Insights
        import time
        start_time = time.time()
        
        # Step 1: Query deals
        deals = await self._query_deals(audience, from_date, to_date, owner)
        logger.info(f"Found {len(deals)} deals for processing (ignore_cooldown={ignore_cooldown})")
        
        # Step 2: Check deduplication (unless ignore_cooldown is True)
        week_key = f"{to_date.year}-{to_date.isocalendar()[1]}"
        processed_key = f"talentwell:processed:{week_key}"
        
        if ignore_cooldown:
            logger.info("Ignoring cooldown - including all candidates")
            new_deals = deals
        else:
            new_deals = await self._filter_processed_deals(deals, processed_key)
            logger.info(f"{len(new_deals)} new deals after deduplication")
        
        # Step 3: Process deals in batches with async parallelization
        cards = await self._process_deals_batch(new_deals, audience)
        logger.info(f"Generated {len(cards)} cards from {len(new_deals)} deals")
        
        # Step 4: Select subject line via bandit
        subject = await self.subject_bandit.select_variant(audience)
        logger.info(f"Selected subject variant: {subject['variant_id']}")
        
        # Step 5: Render HTML with AST compiler
        html_content = await self._render_digest(cards, subject['text'], audience)
        
        # Step 6: Mark deals as processed (if not dry run)
        if not dry_run and self.redis_client:
            for deal in new_deals:
                await self.redis_client.sadd(processed_key, deal['id'])
            await self.redis_client.expire(processed_key, 86400 * 30)  # Keep for 30 days
            
        # Return manifest
        manifest = {
            'audience': audience,
            'from_date': from_date.isoformat(),
            'to_date': to_date.isoformat(),
            'week': week_key,
            'cards_count': len(cards),
            'deals_processed': len(new_deals),
            'subject': subject,
            'generated_at': datetime.now().isoformat(),
            'dry_run': dry_run
        }
        
        # Log performance metrics to Application Insights
        duration = time.time() - start_time
        logger.info(f"Digest generation complete: cards={len(cards)}, total_candidates={len(deals)}, "
                   f"after_cooldown={len(new_deals)}, duration={duration:.2f}s, subject_variant={subject['variant_id']}, "
                   f"ignore_cooldown={ignore_cooldown}")
        
        # Log to Application Insights with custom dimensions
        if hasattr(logger, 'application_insights'):
            logger.application_insights.track_event(
                'WeeklyDigestGenerated',
                properties={
                    'audience': audience,
                    'cards_count': len(cards),
                    'total_candidates': len(deals),
                    'after_cooldown': len(new_deals),
                    'ignore_cooldown': str(ignore_cooldown),
                    'subject_variant': subject['variant_id'],
                    'dry_run': str(dry_run)
                },
                measurements={
                    'duration_seconds': duration,
                    'cards_count': len(cards),
                    'candidates_filtered': len(deals) - len(new_deals)
                }
            )
        
        return {
            'manifest': manifest,
            'email_html': html_content,
            'subject': subject['text'],
            'cards_metadata': [card.to_dict() for card in cards]
        }
    
    async def _query_deals(
        self,
        audience: str,
        from_date: datetime,
        to_date: datetime,
        owner: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Query candidates from Zoho using Brandon's deterministic selection."""
        
        # Try to load from CSV cache first
        if self.redis_client:
            cache_key = f"deals:cache:{audience}:{from_date.date()}:{to_date.date()}:{owner or 'none'}"
            cached = await self.redis_client.get(cache_key)
            if cached:
                logger.info("Using cached deal data")
                return json.loads(cached.decode())
        
        # Query from Zoho API using new query_candidates method
        try:
            from app.integrations import ZohoApiClient
            zoho_client = ZohoApiClient()
            
            # Fetch candidates with Brandon's criteria - NOW PASSING THE FILTERS!
            candidates = await zoho_client.query_candidates(
                limit=100,
                from_date=from_date,
                to_date=to_date,
                owner=owner
            )
            
            logger.info(f"Retrieved {len(candidates)} candidates from Zoho with filters: from={from_date}, to={to_date}, owner={owner}")
            return candidates
            
        except Exception as e:
            logger.error(f"Error querying candidates from Zoho: {e}")
            return []
    
    async def _process_deals_batch(
        self,
        deals: List[Dict[str, Any]],
        audience: str,
        batch_size: int = 10
    ) -> List[DigestCard]:
        """Process deals in batches using async parallelization."""
        all_cards = []

        # Process deals in batches of batch_size
        for i in range(0, len(deals), batch_size):
            batch = deals[i:i + batch_size]

            # Create tasks for parallel processing
            tasks = [self._process_deal(deal, audience) for deal in batch]

            # Execute batch in parallel using asyncio.gather
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out None results and exceptions
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Error in batch processing: {result}")
                elif result is not None:
                    all_cards.append(result)

            logger.info(f"Processed batch {i//batch_size + 1}: {len(batch)} deals → {len([r for r in batch_results if r and not isinstance(r, Exception)])} cards")

        return all_cards

    async def _filter_processed_deals(
        self,
        deals: List[Dict[str, Any]],
        processed_key: str
    ) -> List[Dict[str, Any]]:
        """Filter out already processed deals from last 4 weeks with fuzzy deduplication."""
        if not self.redis_client:
            return deals

        # Check last 4 weeks of processed candidates
        current_date = datetime.now()
        new_deals = []

        for deal in deals:
            candidate_locator = deal.get('candidate_locator') or deal.get('id')
            is_processed = False

            # First check exact match in last 4 weeks
            for week_offset in range(4):
                check_date = current_date - timedelta(weeks=week_offset)
                year_week = f"{check_date.year}-{check_date.isocalendar()[1]:02d}"
                week_key = f"talentwell:processed:{year_week}"

                is_member = await self.redis_client.sismember(week_key, candidate_locator)
                if is_member:
                    is_processed = True
                    logger.info(f"Candidate {candidate_locator} already processed in week {year_week}")
                    break

            # If not exactly processed, check for fuzzy duplicate using embeddings
            if not is_processed:
                is_duplicate = await self._check_duplicate_candidate(
                    deal.get('candidate_name', ''),
                    deal.get('company_name', ''),
                    deal.get('job_title', ''),
                    processed_key.replace(':processed:', ':')  # Extract audience from key
                )
                if is_duplicate:
                    is_processed = True
                    logger.info(f"Candidate {candidate_locator} is a fuzzy duplicate")

            if not is_processed:
                new_deals.append(deal)

        logger.info(f"Filtered {len(deals) - len(new_deals)} already processed candidates (exact + fuzzy)")
        return new_deals
    
    async def _process_deal(
        self,
        deal: Dict[str, Any],
        audience: str
    ) -> Optional[DigestCard]:
        """Process single deal with C³/VoIT, Zoom transcript, and evidence extraction."""
        
        try:
            # Extract base information using Brandon's field mappings
            candidate_name = deal.get('candidate_name', 'Unknown') or 'Unknown'
            job_title = deal.get('job_title', 'Unknown') or 'Unknown'
            company = deal.get('company_name', 'Unknown') or 'Unknown'
            location = deal.get('location', 'Unknown') or 'Unknown'

            # Check for Outlook enrichment cache to enhance data
            candidate_email = deal.get('email') or deal.get('contact_email')
            outlook_enrichment = None
            if candidate_email and self.redis_client:
                cache_key = f"enrichment:contact:{candidate_email.lower()}"
                try:
                    cached_data = await self.redis_client.get(cache_key)
                    if cached_data:
                        outlook_enrichment = json.loads(cached_data.decode())
                        logger.info(f"Found Outlook enrichment for {candidate_email}: {outlook_enrichment.get('source')}")

                        # Enhance deal data with Outlook enrichment if fields are missing
                        if not company or company == 'Unknown':
                            company = outlook_enrichment.get('company', company)
                        if not job_title or job_title == 'Unknown':
                            job_title = outlook_enrichment.get('job_title', job_title)
                        if not location or location == 'Unknown':
                            location = outlook_enrichment.get('location', location)

                        # Store enrichment in deal for later use
                        deal['_outlook_enrichment'] = outlook_enrichment
                except Exception as e:
                    logger.warning(f"Failed to fetch Outlook enrichment: {e}")

            # Normalize location to metro area
            location = await self._normalize_location(location)
            
            # Build mobility line from CRM fields
            mobility_line = self._build_mobility_line(
                deal.get('is_mobile', False),
                deal.get('remote_preference', False),
                deal.get('hybrid_preference', False)
            )
            
            # Fetch Zoom transcript if available (with retry logic)
            transcript_text = None
            if deal.get('meeting_id') or deal.get('transcript_url'):
                from app.zoom_client import ZoomClient
                zoom_client = ZoomClient()
                meeting_ref = deal.get('meeting_id') or deal.get('transcript_url')

                # Use retry logic with exponential backoff
                # Retries: 3 attempts, delays: 1s, 2s, 4s
                logger.info(f"Fetching Zoom transcript for {candidate_name} (meeting: {meeting_ref})")
                transcript_text = await retry_with_exponential_backoff(
                    zoom_client.fetch_zoom_transcript_for_meeting,
                    meeting_ref,
                    max_retries=3,
                    initial_delay=1.0,
                    backoff_factor=2.0,
                    max_delay=10.0
                )

                if transcript_text:
                    logger.info(f"Successfully fetched Zoom transcript for candidate {candidate_name}")
                else:
                    logger.warning(f"Could not fetch Zoom transcript for {candidate_name} after retries")
            
            # Build canonical record with all fields
            canonical_record = {
                'candidate_name': candidate_name,
                'job_title': job_title,
                'company': company,
                'location': location,
                'mobility_line': mobility_line,
                'professional_designations': deal.get('professional_designations'),
                'book_size_aum': deal.get('book_size_aum'),
                'production_12mo': deal.get('production_12mo'),
                'desired_comp': deal.get('desired_comp'),
                'when_available': deal.get('when_available'),
                'candidate_locator': deal.get('candidate_locator') or deal.get('id'),
                'transcript': transcript_text,
                'deal_id': deal.get('id')
            }
            
            cache_key = self._generate_cache_key(canonical_record, audience)
            
            # Try C³ reuse with selector-aware caching
            if self.redis_client:
                cached_entry = await self._get_c3_entry(cache_key)
                if cached_entry:
                    decision, artifact = c3_reuse_or_rebuild(
                        {'touched_selectors': ['talentwell_digest']},
                        cached_entry,
                        delta=0.01,
                        eps=3
                    )
                    
                    if decision == "reuse":
                        logger.info(f"C³ cache hit for deal {deal.get('id')}")
                        return self._deserialize_card(artifact)
            
            # Process with VoIT if not cached
            # Get VoIT configuration for TalentWell context
            voit_config = VoITConfig.get_config_for_context("talentwell_digest")
            voit_result = await voit_orchestration(
                canonical_record,
                budget=voit_config['budget'],
                target_quality=voit_config['target_quality']
            )
            
            # Generate hard-skill bullets (2-5 required)
            bullets = await self._generate_hard_skill_bullets(
                deal,
                voit_result.get('enhanced_data', {}),
                transcript_text
            )
            
            # CRITICAL: Ensure we have 3-5 bullets from ALL data sources
            if len(bullets) < 3:
                logger.warning(f"Only {len(bullets)} bullets for candidate {candidate_name}, extracting from ALL sources")

                # First, try to extract more from transcript if available
                if transcript_text:
                    bullets = await self._extract_more_from_transcript(bullets, transcript_text, deal, voit_result.get('enhanced_data', {}))

                # Extract from resume data if available
                if len(bullets) < 3 and deal.get('resume_text'):
                    bullets = await self._extract_from_resume(bullets, deal.get('resume_text'), deal)

                # Still need more? Add from available CRM fields
                if len(bullets) < 3:
                    bullets = await self._ensure_minimum_bullets(deal, bullets)

                # If STILL less than 3, add generic professional bullets
                if len(bullets) < 3:
                    if deal.get('location'):
                        bullets.append(BulletPoint(
                            text=f"Location: {deal['location']}",
                            confidence=0.7,
                            source="CRM"
                        ))
            elif len(bullets) > 5:
                bullets = bullets[:5]  # Take top 5

            # Analyze candidate sentiment from transcript
            sentiment = await self._analyze_candidate_sentiment(transcript_text)

            # Create card with Brandon's format + sentiment analysis
            card = DigestCard(
                deal_id=deal.get('id'),
                candidate_name=candidate_name,
                job_title=job_title,
                company=company,
                location=f"{location} {mobility_line}",
                bullets=bullets,
                metro_area=location,  # Already normalized
                firm_type=await self._get_firm_type(company),
                source=deal.get('source'),
                source_detail=deal.get('source_detail'),
                meeting_date=deal.get('meeting_date'),
                transcript_url=deal.get('transcript_url'),
                evidence_score=self._calculate_evidence_score(bullets),
                # Sentiment analysis fields
                sentiment_score=sentiment['score'],
                sentiment_label=sentiment['label'],
                enthusiasm_score=sentiment['enthusiasm_score'],
                professionalism_score=sentiment['professionalism_score'],
                concerns_detected=sentiment['concerns_detected']
            )
            
            # Cache the result with full C³ serialization
            if self.redis_client:
                await self._set_c3_entry(cache_key, card, canonical_record, audience)

            return card
            
        except Exception as e:
            logger.error(f"Error processing deal {deal.get('id')}: {e}")
            return None
    
    async def _get_metro_area(self, location: str) -> Optional[str]:
        """Get metro area for location from policy."""
        if not self.redis_client or not location:
            return None

        key = f"geo:metro:{location.lower().replace(' ', '_')}"
        value = await self.redis_client.get(key)
        return value.decode() if value else None
    
    async def _get_firm_type(self, company: str) -> Optional[str]:
        """Get firm type from policy."""
        if not self.redis_client or not company:
            return None

        key = f"policy:employers:{company.lower().replace(' ', '_')}"
        value = await self.redis_client.get(key)
        return value.decode() if value else None

    def _anonymize_company(self, company_name: str, aum: Optional[float] = None) -> str:
        """
        Replace firm names with generic descriptors for privacy.
        Prevents candidate identification through company name.
        """
        if not company_name or company_name == "Unknown":
            return "Not disclosed"

        # Check against known firm types
        for firm_type, firms in self.FIRM_TYPE_MAP.items():
            if any(firm.lower() in company_name.lower() for firm in firms):
                if firm_type == 'wirehouse':
                    return "Major wirehouse"
                elif firm_type == 'ria':
                    # Use AUM to distinguish size if available
                    if aum and aum > 1_000_000_000:  # $1B+
                        return "Large RIA"
                    else:
                        return "Mid-sized RIA"
                elif firm_type == 'bank':
                    return "National bank"
                elif firm_type == 'insurance':
                    return "Insurance brokerage"

        # Generic fallback based on AUM
        if aum:
            if aum > 500_000_000:  # $500M+
                return "Large wealth management firm"
            else:
                return "Boutique advisory firm"

        return "Advisory firm"

    def _parse_aum(self, aum_str: str) -> float:
        """
        Parse AUM string to float value in dollars.
        Examples: "$1.5B" -> 1500000000, "$500M" -> 500000000, "$100K" -> 100000
        """
        if not aum_str:
            return 0.0

        # Remove $ and commas, clean up spaces
        cleaned = aum_str.replace('$', '').replace(',', '').strip()

        # Pattern to extract number and unit
        pattern = r'(\d+(?:\.\d+)?)\s*([BMKbmk])?'
        match = re.match(pattern, cleaned)

        if not match:
            return 0.0

        amount = float(match.group(1))
        unit = match.group(2)

        if unit:
            unit = unit.upper()
            multipliers = {
                'B': 1_000_000_000,
                'M': 1_000_000,
                'K': 1_000
            }
            return amount * multipliers.get(unit, 1)

        return amount

    def _round_aum_for_privacy(self, aum_value: float) -> str:
        """
        Round AUM to privacy-preserving ranges.
        Ranges: $5B+ | $1B–$5B | $500M–$1B | $100M–$500M | Under $100M
        """
        if aum_value >= 5_000_000_000:
            return "$5B+"
        elif aum_value >= 1_000_000_000:
            return "$1B–$5B"
        elif aum_value >= 500_000_000:
            return "$500M–$1B"
        elif aum_value >= 100_000_000:
            return "$100M–$500M"
        elif aum_value > 0:
            return "$100M+"
        else:
            return ""

    def _standardize_compensation(self, raw_text: str) -> str:
        """
        Standardize compensation format to "Target comp: $XXXk–$XXXk OTE".
        Handles variations like "95k Base + Commission 140+ OTE".
        """
        if not raw_text:
            return ""

        # Clean the input
        text = raw_text.lower().replace(',', '')

        # Extract all numbers that could be compensation amounts
        # Pattern for amounts like 95k, 140k, $200k, 300000
        amount_pattern = r'\$?(\d+)(?:k|,000)?'
        amounts = re.findall(amount_pattern, text)

        if not amounts:
            return raw_text  # Return original if can't parse

        # Convert all amounts to thousands
        amounts_in_k = []
        for amt in amounts:
            amt_num = float(amt)
            # If number is > 1000, assume it's in dollars not thousands
            if amt_num > 1000:
                amt_num = amt_num / 1000
            amounts_in_k.append(int(amt_num))

        # Determine if OTE is mentioned
        is_ote = 'ote' in text or 'on target' in text or 'total' in text

        # Format based on number of amounts found
        if len(amounts_in_k) == 1:
            # Single amount
            return f"Target comp: ${amounts_in_k[0]}k{' OTE' if is_ote else ''}"
        elif len(amounts_in_k) >= 2:
            # Range (use min and max)
            min_amt = min(amounts_in_k)
            max_amt = max(amounts_in_k)
            if min_amt == max_amt:
                return f"Target comp: ${max_amt}k{' OTE' if is_ote else ''}"
            else:
                return f"Target comp: ${min_amt}k–${max_amt}k{' OTE' if is_ote else ''}"

        return raw_text  # Fallback to original

    def _is_internal_note(self, text: str) -> bool:
        """
        Filter internal recruiter notes that shouldn't be shown to clients.
        Patterns: "hard time", "TBD", "depending on", "unclear", "didn't say"
        """
        if not text:
            return False

        text_lower = text.lower()

        # Internal note patterns
        internal_patterns = [
            'hard time',
            'tbd',
            'to be determined',
            'depending on',
            'unclear',
            "didn't say",
            "doesn't know",
            "not sure",
            "will need to",
            "might be",
            "possibly",
            "maybe",
            "we need to",
            "follow up on",
            "ask about",
            "verify",
            "confirm with",
            "check on",
            "waiting for",
            "pending"
        ]

        for pattern in internal_patterns:
            if pattern in text_lower:
                return True

        return False

    def _format_availability(self, raw_text: str) -> str:
        """
        Format availability text consistently.
        Remove duplicates like "Available Available".
        Normalize to "Available immediately" or "Available in X weeks/months".
        """
        if not raw_text:
            return ""

        # Clean up duplicate "Available"
        text = re.sub(r'\b(available)\s+\1\b', r'\1', raw_text, flags=re.IGNORECASE)

        # Normalize common patterns
        text_lower = text.lower()

        if 'immediate' in text_lower or 'now' in text_lower or 'asap' in text_lower:
            return "Available immediately"

        # Extract timeframe
        # Pattern for "X weeks/months"
        time_pattern = r'(\d+)\s*(weeks?|months?|days?)'
        match = re.search(time_pattern, text_lower)

        if match:
            number = match.group(1)
            unit = match.group(2)
            # Normalize unit to singular/plural
            if number == '1':
                unit = unit.rstrip('s')
            elif not unit.endswith('s'):
                unit = unit + 's'
            return f"Available in {number} {unit}"

        # Check for specific dates
        if 'january' in text_lower or 'february' in text_lower or 'march' in text_lower:
            # Extract month name
            months = ['january', 'february', 'march', 'april', 'may', 'june',
                     'july', 'august', 'september', 'october', 'november', 'december']
            for month in months:
                if month in text_lower:
                    return f"Available in {month.capitalize()}"

        # Default formatting
        if text_lower.startswith('available'):
            return text
        else:
            return f"Available {text}"

    def _calculate_evidence_score(self, bullets: List[BulletPoint]) -> float:
        """Calculate overall evidence score for bullets."""
        if not bullets:
            return 0.0

        scores = [b.confidence for b in bullets]
        return sum(scores) / len(scores)

    def _score_bullet(self, bullet: BulletPoint) -> float:
        """
        Calculate composite score for bullet ranking.

        Score factors:
        1. Category priority (0.0-1.0): Financial metrics > Licenses > Experience > Availability > Compensation
        2. Confidence score (0.0-1.0): From evidence extraction
        3. Source reliability (0.0-1.0): CRM > Extraction > Inferred
        4. Evidence quality bonus (+0.1 per evidence source, max +0.3)

        Final score: (priority * 0.4) + (confidence * 0.4) + (source * 0.15) + (evidence_bonus * 0.05)
        Range: 0.0 to 1.0
        """
        # Category priority weights (aligned with Brandon's requirements)
        category_priorities = {
            'FINANCIAL_METRIC': 1.0,      # AUM, production (highest priority)
            'GROWTH_ACHIEVEMENT': 0.95,   # Growth metrics
            'PERFORMANCE_RANKING': 0.90,  # Rankings, performance
            'CLIENT_METRIC': 0.85,        # Client count, retention
            'LICENSES': 0.75,             # Professional credentials
            'EDUCATION': 0.65,            # Degrees, certifications
            'EXPERIENCE': 0.60,           # Years of experience
            'AVAILABILITY': 0.40,         # Start date, notice period
            'MOBILITY': 0.35,             # Location preferences
            'COMPENSATION': 0.30          # Salary expectations (lowest priority)
        }

        # Determine category priority
        # Auto-categorize if category not set or is default
        if not hasattr(bullet, 'category') or bullet.category is None or \
           (hasattr(bullet.category, 'name') and bullet.category.name == 'EXPERIENCE'):
            # Auto-categorize based on bullet text
            bullet.category = self.evidence_extractor.categorize_bullet(bullet.text)

        category_name = bullet.category.name if hasattr(bullet, 'category') and bullet.category else 'EXPERIENCE'
        category_priority = category_priorities.get(category_name, 0.5)

        # Confidence score
        confidence = bullet.confidence if hasattr(bullet, 'confidence') else 0.5

        # Source reliability
        source_weights = {
            'CRM': 1.0,          # Most reliable
            'Extraction': 0.85,  # AI-extracted from transcript
            'Inferred': 0.6      # Least reliable
        }
        source = bullet.source if hasattr(bullet, 'source') else 'Inferred'
        source_reliability = source_weights.get(source, 0.7)

        # Evidence quality bonus
        evidence_count = len(bullet.evidence) if hasattr(bullet, 'evidence') and bullet.evidence else 0
        evidence_bonus = min(0.3, evidence_count * 0.1)

        # Calculate composite score
        composite_score = (
            (category_priority * 0.4) +
            (confidence * 0.4) +
            (source_reliability * 0.15) +
            (evidence_bonus * 0.05)
        )

        return round(composite_score, 3)

    async def _analyze_candidate_sentiment(self, transcript: Optional[str]) -> Dict[str, Any]:
        """
        Analyze candidate sentiment from transcript using keyword-based analysis.

        Returns:
            {
                'score': float (0.0-1.0, where 1.0 is most positive),
                'label': str ('positive', 'neutral', 'negative'),
                'enthusiasm_score': float (0.0-1.0),
                'concerns_detected': bool,
                'professionalism_score': float (0.0-1.0)
            }
        """
        if not transcript or len(transcript.strip()) < 50:
            return {
                'score': 0.5,
                'label': 'neutral',
                'enthusiasm_score': 0.5,
                'concerns_detected': False,
                'professionalism_score': 0.5
            }

        transcript_lower = transcript.lower()

        # Positive indicators (enthusiasm, commitment)
        positive_keywords = [
            'excited', 'passionate', 'eager', 'looking forward', 'great opportunity',
            'perfect fit', 'ideal', 'love', 'enjoy', 'motivated', 'enthusiastic',
            'committed', 'dedicated', 'ready', 'confident', 'impressed', 'excellent',
            'outstanding', 'thrilled', 'delighted', 'appreciate'
        ]

        # Negative indicators (hesitation, concerns)
        negative_keywords = [
            'concerned', 'worried', 'uncertain', 'unsure', 'hesitant', 'afraid',
            'risk', 'problem', 'issue', 'difficult', 'challenging', 'unfortunately',
            'disappointed', 'frustrated', 'concerned about', 'not sure if',
            'might not', 'probably not', 'doubt', 'skeptical'
        ]

        # Enthusiasm indicators (strong interest)
        enthusiasm_keywords = [
            'absolutely', 'definitely', 'certainly', 'immediately', 'asap',
            'as soon as possible', 'right away', "can't wait", 'very interested',
            'highly motivated', 'perfect match', 'dream job', 'ideal opportunity'
        ]

        # Professionalism indicators
        professional_keywords = [
            'fiduciary', 'compliance', 'regulatory', 'best practices', 'ethics',
            'professional development', 'continuous learning', 'mentorship',
            'team collaboration', 'client-centric', 'relationship-based',
            'long-term', 'strategic', 'planning'
        ]

        # Concern/red flag indicators
        concern_keywords = [
            'litigation', 'lawsuit', 'termination', 'fired', 'compliance issue',
            'regulatory issue', 'investigation', 'complaint', 'dispute',
            'non-compete', 'legal', 'sue', 'sued'
        ]

        # Count keyword matches
        positive_count = sum(1 for kw in positive_keywords if kw in transcript_lower)
        negative_count = sum(1 for kw in negative_keywords if kw in transcript_lower)
        enthusiasm_count = sum(1 for kw in enthusiasm_keywords if kw in transcript_lower)
        professional_count = sum(1 for kw in professional_keywords if kw in transcript_lower)
        concern_count = sum(1 for kw in concern_keywords if kw in transcript_lower)

        # Calculate sentiment score (0.0 to 1.0)
        total_sentiment_keywords = positive_count + negative_count
        if total_sentiment_keywords > 0:
            sentiment_score = positive_count / total_sentiment_keywords
        else:
            sentiment_score = 0.5  # Neutral default

        # Adjust for enthusiasm
        enthusiasm_score = min(1.0, enthusiasm_count / 3.0)  # 3+ enthusiasm keywords = 1.0

        # Adjust for professionalism
        professionalism_score = min(1.0, professional_count / 4.0)  # 4+ professional keywords = 1.0

        # Detect concerns
        concerns_detected = concern_count > 0

        # Determine label
        if sentiment_score >= 0.7:
            label = 'positive'
        elif sentiment_score >= 0.4:
            label = 'neutral'
        else:
            label = 'negative'

        # Apply concern penalty
        if concerns_detected:
            sentiment_score *= 0.7  # 30% penalty for red flags
            label = 'neutral' if label == 'positive' else label

        result = {
            'score': round(sentiment_score, 2),
            'label': label,
            'enthusiasm_score': round(enthusiasm_score, 2),
            'concerns_detected': concerns_detected,
            'professionalism_score': round(professionalism_score, 2)
        }

        logger.debug(
            f"Sentiment analysis: {label} (score={sentiment_score:.2f}, "
            f"enthusiasm={enthusiasm_score:.2f}, professional={professionalism_score:.2f}, "
            f"concerns={concerns_detected})"
        )

        return result

    def _rank_bullets_by_score(self, bullets: List[BulletPoint], top_n: int = 5) -> List[BulletPoint]:
        """
        Rank bullets by composite score and return top N.

        Steps:
        1. Calculate score for each bullet
        2. Sort by score (descending)
        3. Return top N bullets
        4. Log ranking decisions for debugging
        """
        if not bullets:
            return []

        # Score each bullet
        scored_bullets = [
            (bullet, self._score_bullet(bullet))
            for bullet in bullets
        ]

        # Sort by score (descending)
        scored_bullets.sort(key=lambda x: x[1], reverse=True)

        # Log ranking decisions
        logger.info(f"Bullet ranking scores (top {min(top_n, len(scored_bullets))}):")
        for i, (bullet, score) in enumerate(scored_bullets[:top_n]):
            category = bullet.category.name if hasattr(bullet, 'category') and bullet.category else 'UNKNOWN'
            source = bullet.source if hasattr(bullet, 'source') else 'Unknown'
            logger.info(f"  #{i+1}: {score:.3f} [{category}] [{source}] {bullet.text[:60]}...")

        # Return top N bullets (without scores)
        return [bullet for bullet, score in scored_bullets[:top_n]]

    def _generate_cache_key(self, record: Dict[str, Any], audience: str) -> str:
        """Generate C³ cache key."""
        key_data = f"{json.dumps(record, sort_keys=True)}|{audience}|talentwell_digest"
        return f"c3:digest:{hashlib.sha256(key_data.encode()).hexdigest()}"
    
    async def _get_c3_entry(self, cache_key: str) -> Optional[C3Entry]:
        """Get C³ entry from cache with full deserialization."""
        if not self.redis_client:
            return None

        try:
            # Get the cached entry
            cached_data = await self.redis_client.get(cache_key)
            if not cached_data:
                return None

            # Deserialize the JSON data
            data = json.loads(cached_data.decode())

            # Reconstruct the C3Entry with all components
            import base64

            # Deserialize DependencyCertificate
            dc = DependencyCertificate(
                spans=data['dc']['spans'],
                invariants=data['dc']['invariants'],
                selector_tau=data['dc']['selector_tau']
            )

            # Reconstruct C3Entry
            entry = C3Entry(
                artifact=base64.b64decode(data['artifact']),  # Decode from base64
                dc=dc,
                probes=data['probes'],
                calib_scores=[tuple(cs) for cs in data['calib_scores']],  # Convert lists to tuples
                tau_delta=data['tau_delta'],
                meta=data['meta'],
                selector_ttl=data.get('selector_ttl', {}),
                selector_calib={k: [tuple(cs) for cs in v] for k, v in data.get('selector_calib', {}).items()}
            )

            logger.info(f"C³ cache retrieved: {cache_key}, tau_delta={entry.tau_delta:.4f}")
            return entry

        except Exception as e:
            logger.error(f"Error deserializing C³ entry: {e}")
            return None
    
    async def _set_c3_entry(self, cache_key: str, card: DigestCard,
                          canonical_record: Dict[str, Any], audience: str):
        """Set C³ entry with full serialization."""
        if not self.redis_client:
            return

        try:
            import base64
            import time

            # Serialize the card as artifact
            artifact_data = json.dumps(card.to_dict())
            artifact_b64 = base64.b64encode(artifact_data.encode()).decode()

            # Create dependency certificate
            dc = {
                'spans': {'talentwell_digest': [[0, len(artifact_data)]]},
                'invariants': {'audience': audience},
                'selector_tau': {'talentwell_digest': 0.01}
            }

            # Create the full C3Entry structure for serialization
            entry_data = {
                'artifact': artifact_b64,  # Base64 encoded
                'dc': dc,
                'probes': {'talentwell_digest': []},
                'calib_scores': [[0.0, 0]],  # Initial calibration
                'tau_delta': 0.01,
                'meta': {
                    'embed': [],  # Would normally compute embedding here
                    'fields': canonical_record,
                    'created_at': time.time(),
                    'template_version': 'v1'
                },
                'selector_ttl': {
                    'talentwell_digest': {
                        'alpha': 3,
                        'beta': 7,
                        'last_sampled_ttl': 86400 * 7
                    }
                },
                'selector_calib': {
                    'talentwell_digest': [[0.0, 0]]
                }
            }

            # Cache with 7-day TTL
            await self.redis_client.setex(
                cache_key,
                86400 * 7,  # 7 days TTL
                json.dumps(entry_data)
            )

            logger.info(f"C³ cache stored: {cache_key}, TTL=7 days")

        except Exception as e:
            logger.error(f"Error serializing C³ entry: {e}")
    
    def _deserialize_card(self, artifact: Any) -> DigestCard:
        """Deserialize card from C³ artifact."""
        try:
            # If artifact is bytes, decode it first
            if isinstance(artifact, bytes):
                artifact_data = json.loads(artifact.decode())
            elif isinstance(artifact, str):
                artifact_data = json.loads(artifact)
            elif isinstance(artifact, dict):
                artifact_data = artifact
            else:
                logger.error(f"Unknown artifact type: {type(artifact)}")
                return None

            # Reconstruct BulletPoint objects
            bullets = []
            for b in artifact_data.get('bullets', []):
                if isinstance(b, dict):
                    # Ensure all required fields are present
                    bullet = BulletPoint(
                        text=b.get('text', ''),
                        confidence=b.get('confidence', 0.0),
                        source=b.get('source', 'Unknown')
                    )
                    bullets.append(bullet)
                elif isinstance(b, BulletPoint):
                    bullets.append(b)

            # Convert meeting_date if present
            if 'meeting_date' in artifact_data and artifact_data['meeting_date']:
                if isinstance(artifact_data['meeting_date'], str):
                    artifact_data['meeting_date'] = datetime.fromisoformat(artifact_data['meeting_date'])

            # Create DigestCard with reconstructed data
            return DigestCard(
                deal_id=artifact_data.get('deal_id'),
                candidate_name=artifact_data.get('candidate_name', 'Unknown'),
                job_title=artifact_data.get('job_title', 'Unknown'),
                company=artifact_data.get('company', 'Unknown'),
                location=artifact_data.get('location', 'Unknown'),
                bullets=bullets,
                metro_area=artifact_data.get('metro_area'),
                firm_type=artifact_data.get('firm_type'),
                source=artifact_data.get('source'),
                source_detail=artifact_data.get('source_detail'),
                meeting_date=artifact_data.get('meeting_date'),
                transcript_url=artifact_data.get('transcript_url'),
                evidence_score=artifact_data.get('evidence_score', 0.0),
                # Sentiment analysis fields (from cache)
                sentiment_score=artifact_data.get('sentiment_score'),
                sentiment_label=artifact_data.get('sentiment_label'),
                enthusiasm_score=artifact_data.get('enthusiasm_score'),
                professionalism_score=artifact_data.get('professionalism_score'),
                concerns_detected=artifact_data.get('concerns_detected')
            )

        except Exception as e:
            logger.error(f"Error deserializing card from artifact: {e}")
            return None
    
    async def _render_digest(
        self,
        cards: List[DigestCard],
        subject: str,
        audience: str
    ) -> str:
        """Render digest HTML using AST compiler."""
        
        # Load template
        template_path = "app/templates/email/weekly_digest_v1.html"
        try:
            with open(template_path, 'r') as f:
                template_html = f.read()
        except FileNotFoundError:
            # Fallback to basic HTML if template not found
            logger.warning(f"Template not found: {template_path}, using basic HTML")
            return self._render_basic_html(cards, subject, audience)
        
        # Parse template into AST
        self.ast_compiler.parse_template(template_html)
        
        # Prepare data for rendering
        cards_html = ''.join([self._format_card_html(card) for card in cards])
        render_data = {
            'subject': subject,
            'intro_block': self._generate_intro(audience, len(cards)),
            'cards': cards_html
        }
        
        # Update modifiable content
        self.ast_compiler.update_modifiable_content(render_data)
        
        # Render to HTML
        html_content = self.ast_compiler.render_to_html()
        
        return html_content
    
    def _render_basic_html(self, cards: List[DigestCard], subject: str, audience: str) -> str:
        """Render basic HTML without template."""
        cards_html = ''.join([self._format_card_html(card) for card in cards])
        intro = self._generate_intro(audience, len(cards))
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>{subject}</title></head>
        <body>
            <h1>{subject}</h1>
            <p>{intro}</p>
            <div class="cards">
                {cards_html}
            </div>
        </body>
        </html>
        """
    
    def _generate_intro(self, audience: str, card_count: int) -> str:
        """Generate personalized intro block."""
        intros = {
            'steve_perry': f"Steve, here are {card_count} standout candidates from this week's interviews.",
            'leadership': f"Team, we've identified {card_count} exceptional candidates this week.",
            'default': f"Here are {card_count} top candidates from recent interviews."
        }
        return intros.get(audience, intros['default'])
    
    def _format_card_html(self, card: DigestCard) -> str:
        """Format card as HTML following Brandon's template."""
        bullets_html = '\n'.join([
            f'<li>{bullet.text}</li>'
            for bullet in card.bullets
        ])
        
        # Extract availability and comp info
        availability = ""
        comp = ""
        for bullet in card.bullets:
            if "available" in bullet.text.lower():
                availability = bullet.text
            elif "comp" in bullet.text.lower() or "$" in bullet.text:
                comp = bullet.text
        
        # Generate ref code
        ref_code = f"TWAV-{card.deal_id[-8:]}" if card.deal_id else "TWAV-00000000"
        
        return f"""
        <div class="candidate-card">
            <h3><strong>{card.candidate_name}</strong></h3>
            <div class="candidate-location">
                <strong>Location:</strong> {card.location}
            </div>
            <div class="candidate-details">
                <div class="skill-list">
                    <ul>
                        {bullets_html}
                    </ul>
                </div>
                <div class="availability-comp">
                    {f'<div>{availability}</div>' if availability else ''}
                    {f'<div>{comp}</div>' if comp else ''}
                </div>
            </div>
            <div class="ref-code">Ref code: {ref_code}</div>
        </div>
        """
    
    async def _check_duplicate_candidate(
        self,
        candidate_name: str,
        company_name: str,
        job_title: str,
        audience: str
    ) -> bool:
        """Check for duplicate candidates using embedding-based similarity."""
        if not self.redis_client or not candidate_name:
            return False

        try:
            import numpy as np
            from openai import AsyncOpenAI

            # Create embedding text
            embedding_text = f"{candidate_name} {company_name} {job_title}".strip()

            # Get embedding from OpenAI
            client = AsyncOpenAI()
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=embedding_text
            )
            current_embedding = np.array(response.data[0].embedding)

            # Get recent candidate embeddings from Redis
            embeddings_key = f"candidates:embeddings:{audience}:recent"
            stored_embeddings = await self.redis_client.get(embeddings_key)

            if stored_embeddings:
                stored_data = json.loads(stored_embeddings.decode())

                # Check similarity against each stored embedding
                for stored_candidate in stored_data:
                    stored_vec = np.array(stored_candidate['embedding'])

                    # Calculate cosine similarity
                    cosine_sim = np.dot(current_embedding, stored_vec) / (
                        np.linalg.norm(current_embedding) * np.linalg.norm(stored_vec)
                    )

                    # Check if similarity exceeds threshold
                    if cosine_sim > 0.95:
                        logger.info(f"Found duplicate: '{embedding_text}' matches '{stored_candidate['text']}' (similarity={cosine_sim:.3f})")
                        return True

                # Add current embedding to the list (keep last 100)
                stored_data.append({
                    'text': embedding_text,
                    'embedding': current_embedding.tolist(),
                    'timestamp': datetime.now().isoformat()
                })

                # Keep only last 100 candidates
                stored_data = stored_data[-100:]
            else:
                # Initialize with current embedding
                stored_data = [{
                    'text': embedding_text,
                    'embedding': current_embedding.tolist(),
                    'timestamp': datetime.now().isoformat()
                }]

            # Store updated embeddings
            await self.redis_client.setex(
                embeddings_key,
                86400 * 30,  # Keep for 30 days
                json.dumps(stored_data)
            )

            return False

        except Exception as e:
            logger.error(f"Error checking duplicate candidate: {e}")
            return False

    async def _normalize_location(self, location: str) -> str:
        """Normalize location to metro area using city_context.json."""
        if not location or location == "Unknown":
            return location
            
        # Load city context
        try:
            with open("app/policy/seed/city_context.json", "r") as f:
                city_context = json.load(f)
        except:
            logger.warning("Could not load city_context.json")
            return location
        
        # Normalize location for lookup
        location_key = location.lower().replace(" ", "_").replace(",", "")
        
        # Check for metro area mapping
        if location_key in city_context:
            metro = city_context[location_key]
            # Special handling for small cities like Gulf Breeze
            if "gulf_breeze" in location_key:
                return f"Gulf Breeze (Pensacola area)"
            return metro
        
        # Return original if no mapping found
        return location
    
    def _build_mobility_line(self, is_mobile: bool, remote_pref: bool, hybrid_pref: bool) -> str:
        """Build mobility line from CRM fields per Brandon's format."""
        parts = []
        
        # Mobility status
        if is_mobile:
            parts.append("Is mobile")
        else:
            parts.append("Is not mobile")
        
        # Remote/Hybrid preferences
        prefs = []
        if remote_pref:
            prefs.append("Remote")
        if hybrid_pref:
            prefs.append("Hybrid")
        
        if prefs:
            parts.append(f"Open to {' or '.join(prefs)}")
        
        return f"({'; '.join(parts)})"
    
    async def _generate_hard_skill_bullets(
        self,
        deal: Dict[str, Any],
        enhanced_data: Dict[str, Any],
        transcript: Optional[str]
    ) -> List[BulletPoint]:
        """Generate 3-5 hard skill bullets from ALL available data sources."""
        bullets = []

        # ONLY add experience if we have REAL data (deduplicated)
        years_exp = deal.get('years_experience') or enhanced_data.get('years_experience')
        if years_exp:
            bullets.append(BulletPoint(
                text=f"Experience: {years_exp}",
                confidence=0.95,
                source="CRM" if deal.get('years_experience') else "Extraction"
            ))

        # Financial metrics take priority - format like Brandon's examples
        # AUM (most important metric) - apply privacy rounding
        aum_raw = None
        if deal.get('book_size_aum'):
            aum_value = self._parse_aum(deal['book_size_aum'])
            if aum_value > 0:
                aum_rounded = self._round_aum_for_privacy(aum_value)
                if aum_rounded and not self._is_internal_note(deal['book_size_aum']):
                    bullets.append(BulletPoint(
                        text=f"AUM: {aum_rounded}",
                        confidence=0.95,
                        source="CRM"
                    ))
        elif enhanced_data.get('aum_managed'):
            aum_value = self._parse_aum(enhanced_data['aum_managed'])
            if aum_value > 0:
                aum_rounded = self._round_aum_for_privacy(aum_value)
                if aum_rounded and not self._is_internal_note(enhanced_data['aum_managed']):
                    bullets.append(BulletPoint(
                        text=f"AUM: {aum_rounded}",
                        confidence=0.95,
                        source="Extraction"
                    ))

        # Production metrics (third priority)
        if deal.get('production_12mo'):
            bullets.append(BulletPoint(
                text=f"Production: {deal['production_12mo']}",
                confidence=0.95,
                source="CRM"
            ))
        elif enhanced_data.get('production_annual'):
            bullets.append(BulletPoint(
                text=f"Production: {enhanced_data['production_annual']}",
                confidence=0.95,
                source="Extraction"
            ))

        # Professional designations/licenses (combine for brevity)
        licenses = enhanced_data.get('licenses_held', []) or []
        designations = enhanced_data.get('designations', []) or []
        prof_creds = licenses + designations

        if deal.get('professional_designations'):
            bullets.append(BulletPoint(
                text=f"Licenses/Designations: {deal['professional_designations']}",
                confidence=0.95,
                source="CRM"
            ))
        elif prof_creds and len(bullets) < 4:
            # Format like "Series 7, 66, CFA charterholder"
            bullets.append(BulletPoint(
                text=f"Licenses/Designations: {', '.join(prof_creds[:4])}",  # Limit to avoid long lists
                confidence=0.95,
                source="Extraction"
            ))

        # Client count (if available and bullets < 5)
        if enhanced_data.get('client_count') and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Clients: {enhanced_data['client_count']}",
                confidence=0.9,
                source="Extraction"
            ))

        # Extract MORE financial metrics from transcript if available
        if transcript and len(bullets) < 5:
            # First try the evidence extractor (using correct method name)
            transcript_bullets = self.evidence_extractor.generate_bullets_with_evidence(
                {"transcript": transcript},
                transcript=transcript
            )

            # Add ALL financial-related bullets from transcript (filter internal notes)
            financial_keywords = [
                '$', 'million', 'billion', 'aum', 'production', 'revenue',
                'clients', 'years', '%', 'portfolio', 'assets', 'book',
                'series 7', 'series 66', 'series 65', 'cfa', 'cfp',
                'top performer', 'president', 'club', 'ranking', 'growth',
                'team', 'managing', 'billion', 'million', 'thousand'
            ]
            for bullet in transcript_bullets:
                # Filter out internal notes
                if not self._is_internal_note(bullet.text):
                    if any(keyword in bullet.text.lower() for keyword in financial_keywords):
                        bullets.append(bullet)
                        if len(bullets) >= 5:
                            break

            # If still not enough, do direct transcript mining
            if len(bullets) < 3 and transcript:
                direct_bullets = await self._mine_transcript_directly(transcript, enhanced_data)
                for bullet in direct_bullets:
                    if len(bullets) < 5:
                        bullets.append(bullet)

        # Availability (if space available) - format consistently
        if deal.get('when_available') and len(bullets) < 5:
            formatted_avail = self._format_availability(deal['when_available'])
            if formatted_avail and not self._is_internal_note(formatted_avail):
                bullets.append(BulletPoint(
                    text=formatted_avail,
                    confidence=0.9,
                    source="CRM"
                ))
        elif enhanced_data.get('availability_timeframe') and len(bullets) < 5:
            formatted_avail = self._format_availability(enhanced_data['availability_timeframe'])
            if formatted_avail and not self._is_internal_note(formatted_avail):
                bullets.append(BulletPoint(
                    text=formatted_avail,
                    confidence=0.9,
                    source="Extraction"
                ))

        # Compensation expectations (lowest priority) - standardize format
        if deal.get('desired_comp') and len(bullets) < 5:
            formatted_comp = self._standardize_compensation(deal['desired_comp'])
            if formatted_comp and not self._is_internal_note(formatted_comp):
                bullets.append(BulletPoint(
                    text=formatted_comp,
                    confidence=0.9,
                    source="CRM"
                ))
        elif enhanced_data.get('compensation_range') and len(bullets) < 5:
            formatted_comp = self._standardize_compensation(enhanced_data['compensation_range'])
            if formatted_comp and not self._is_internal_note(formatted_comp):
                bullets.append(BulletPoint(
                    text=formatted_comp,
                    confidence=0.9,
                    source="Extraction"
                ))

        # CRITICAL: Never add fake data - only return what we actually have
        # If we have less than 3 real bullets, that's acceptable per user requirement
        # Use score-based ranking to select the best bullets (max 5)
        if len(bullets) > 5:
            logger.info(f"Ranking {len(bullets)} bullets using composite scoring...")
            bullets = self._rank_bullets_by_score(bullets, top_n=5)
        elif bullets:
            # Even if we have <=5 bullets, rank them for consistency
            bullets = self._rank_bullets_by_score(bullets, top_n=min(5, len(bullets)))

        return bullets
    
    async def _ensure_minimum_bullets(
        self,
        deal: Dict[str, Any],
        existing_bullets: List[BulletPoint]
    ) -> List[BulletPoint]:
        """
        CRITICAL: Only add real data, never fake data per user requirement.
        Return whatever bullets we have - even if less than the target.
        Only add bullets if we have actual verified data from CRM.
        """
        bullets = list(existing_bullets)

        # Add education if available and we need more bullets
        if len(bullets) < 5:
            education = deal.get('education')
            if education and education.strip():
                bullets.append(BulletPoint(
                    text=f"Education: {education}",
                    confidence=0.8,
                    source="CRM"
                ))

        # Add industry focus if available
        if len(bullets) < 5:
            industry = deal.get('industry_focus')
            if industry and industry.strip():
                bullets.append(BulletPoint(
                    text=f"Industry Focus: {industry}",
                    confidence=0.8,
                    source="CRM"
                ))

        # Add location only if we have real location data (important for compliance/licensing)
        if len(bullets) < 5:
            location = None
            if deal.get('location') and deal['location'].strip():
                location = deal['location']
            elif deal.get('contact_city') and deal['contact_city'].strip():
                city = deal['contact_city']
                state = deal.get('contact_state', '').strip()
                location = f"{city}, {state}".strip(', ') if state else city

            if location and location != ', ':
                bullets.append(BulletPoint(
                    text=f"Location: {location}",
                    confidence=0.7,
                    source="CRM"
                ))

        # NEVER pad with fake data - return what we have
        return bullets

    async def _extract_more_from_transcript(
        self,
        existing_bullets: List[BulletPoint],
        transcript: str,
        deal: Dict[str, Any],
        enhanced_data: Dict[str, Any]
    ) -> List[BulletPoint]:
        """Extract additional bullets from transcript to reach minimum 3."""
        bullets = list(existing_bullets)

        if not transcript:
            return bullets

        # Mine the transcript for financial advisor specific info
        transcript_lower = transcript.lower()

        # Look for years of experience mentioned in transcript
        import re
        years_pattern = r'(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|in\s*the\s*industry|in\s*finance|in\s*advisory)'
        years_matches = re.findall(years_pattern, transcript_lower)
        if years_matches and len(bullets) < 5:
            years = max([int(y) for y in years_matches])
            if years > 0:
                bullets.append(BulletPoint(
                    text=f"Experience: {years}+ years in financial services",
                    confidence=0.85,
                    source="Transcript"
                ))

        # Look for specific achievements or metrics in transcript
        achievement_patterns = [
            (r'\$(\d+(?:\.\d+)?)\s*([BMK])', "manages ${}{} in client assets"),
            (r'top\s*(\d+)%', "Top {}% performer"),
            (r'grew\s*(?:book|assets|aum)?\s*(?:by\s*)?(\d+)%', "Grew book by {}%"),
            (r'(\d+)\+?\s*clients?', "{} client relationships")
        ]

        for pattern, template in achievement_patterns:
            matches = re.findall(pattern, transcript_lower)
            if matches and len(bullets) < 5:
                if isinstance(matches[0], tuple):
                    text = template.format(*matches[0])
                else:
                    text = template.format(matches[0])
                bullets.append(BulletPoint(
                    text=text,
                    confidence=0.8,
                    source="Transcript"
                ))

        # Extract specialties mentioned in transcript
        specialties = []
        specialty_keywords = [
            'retirement planning', 'wealth management', 'estate planning',
            '401k', 'pension', 'insurance', 'annuities', 'portfolio management',
            'tax planning', 'financial planning', 'investment advisory'
        ]

        for specialty in specialty_keywords:
            if specialty in transcript_lower and len(bullets) < 5:
                specialties.append(specialty.title())

        if specialties and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Specialties: {', '.join(specialties[:3])}",
                confidence=0.75,
                source="Transcript"
            ))

        return bullets[:5]  # Never exceed 5

    async def _mine_transcript_directly(
        self,
        transcript: str,
        enhanced_data: Dict[str, Any]
    ) -> List[BulletPoint]:
        """Direct mining of transcript for financial advisor information."""
        bullets = []

        if not transcript:
            return bullets

        # Use regex to find specific financial patterns
        import re

        # AUM/Book size patterns
        aum_patterns = [
            r'\$(\d+(?:\.\d+)?)\s*([BMK])\s*(?:AUM|aum|under management|book)',
            r'manage[sd]?\s*\$(\d+(?:\.\d+)?)\s*([BMK])',
            r'book\s*(?:of|size)?\s*\$(\d+(?:\.\d+)?)\s*([BMK])'
        ]

        for pattern in aum_patterns:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            if matches:
                amount, unit = matches[0]
                # Parse and round the AUM value for privacy
                raw_aum = f"${amount}{unit}"
                aum_value = self._parse_aum(raw_aum)
                if aum_value > 0:
                    aum_rounded = self._round_aum_for_privacy(aum_value)
                    if aum_rounded:
                        bullets.append(BulletPoint(
                            text=f"AUM: {aum_rounded}",
                            confidence=0.9,
                            source="Transcript"
                        ))
                        break

        # Production patterns
        prod_patterns = [
            r'production\s*(?:of|is)?\s*\$(\d+(?:\.\d+)?)\s*([BMK])',
            r'\$(\d+(?:\.\d+)?)\s*([BMK])\s*(?:in\s*)?production'
        ]

        for pattern in prod_patterns:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            if matches and len(bullets) < 5:
                amount, unit = matches[0]
                bullets.append(BulletPoint(
                    text=f"Production: ${amount}{unit}",
                    confidence=0.85,
                    source="Transcript"
                ))
                break

        # Team size
        team_pattern = r'team\s*of\s*(\d+)|(\d+)\s*(?:person|people|member)\s*team'
        team_matches = re.findall(team_pattern, transcript, re.IGNORECASE)
        if team_matches and len(bullets) < 5:
            team_size = max([int(t[0] if t[0] else t[1]) for t in team_matches])
            if team_size > 0:
                bullets.append(BulletPoint(
                    text=f"Leads team of {team_size}",
                    confidence=0.8,
                    source="Transcript"
                ))

        return bullets

    async def _extract_from_resume(self, existing_bullets: List[BulletPoint], resume_text: str, deal: Dict[str, Any]) -> List[BulletPoint]:
        """Extract bullets from resume text."""
        bullets = list(existing_bullets)

        if not resume_text:
            return bullets

        import re

        # Extract skills from resume
        skill_patterns = [
            r'series\s*(\d+)',  # Series licenses
            r'(CFA|CFP|CPA|ChFC|CLU|CIMA|CPWA)',  # Professional designations
            r'\$(\d+(?:\.\d+)?)\s*([BMK])(?:illion|illion)?',  # Dollar amounts
            r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',  # Years of experience
        ]

        for pattern in skill_patterns:
            if len(bullets) >= 5:
                break
            matches = re.findall(pattern, resume_text, re.IGNORECASE)
            if matches:
                if 'series' in pattern.lower():
                    for match in matches[:2]:  # Take max 2 series licenses
                        if len(bullets) < 5:
                            bullets.append(BulletPoint(
                                text=f"Licensed: Series {match}",
                                confidence=0.85,
                                source="Resume"
                            ))
                elif 'CFA' in pattern:
                    designations = list(set(matches))[:3]  # Unique designations
                    if designations and len(bullets) < 5:
                        bullets.append(BulletPoint(
                            text=f"Designations: {', '.join(designations)}",
                            confidence=0.85,
                            source="Resume"
                        ))

        return bullets[:5]


# Export curator instance
curator = TalentWellCurator()