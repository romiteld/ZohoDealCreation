"""
TalentWell curator for generating weekly digests.
Orchestrates filtering, normalization, caching, and rendering.
"""
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import hashlib

from app.redis_cache_manager import get_cache_manager
from app.cache.c3 import c3_reuse_or_rebuild, C3Entry, DependencyCertificate
from app.cache.voit import voit_orchestration
from app.extract.evidence import EvidenceExtractor, BulletPoint
from app.templates.ast import ASTCompiler
from app.bandits.subject_bandit import SubjectLineBandit as SubjectBandit
from app.integrations import get_zoho_headers, fetch_deal_from_zoho

logger = logging.getLogger(__name__)

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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['bullets'] = [b.to_dict() for b in self.bullets]
        if self.meeting_date:
            result['meeting_date'] = self.meeting_date.isoformat()
        return result


class TalentWellCurator:
    """Orchestrates weekly digest generation."""
    
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
        
        # Step 3: Process each deal with C³/VoIT
        cards = []
        for deal in new_deals:
            card = await self._process_deal(deal, audience)
            if card:
                cards.append(card)
                
        logger.info(f"Generated {len(cards)} cards")
        
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
    
    async def _filter_processed_deals(
        self,
        deals: List[Dict[str, Any]],
        processed_key: str
    ) -> List[Dict[str, Any]]:
        """Filter out already processed deals from last 4 weeks."""
        if not self.redis_client:
            return deals
        
        # Check last 4 weeks of processed candidates
        current_date = datetime.now()
        new_deals = []
        
        for deal in deals:
            candidate_locator = deal.get('candidate_locator') or deal.get('id')
            is_processed = False
            
            # Check last 4 weeks
            for week_offset in range(4):
                check_date = current_date - timedelta(weeks=week_offset)
                year_week = f"{check_date.year}-{check_date.isocalendar()[1]:02d}"
                week_key = f"talentwell:processed:{year_week}"
                
                is_member = await self.redis_client.sismember(week_key, candidate_locator)
                if is_member:
                    is_processed = True
                    logger.info(f"Candidate {candidate_locator} already processed in week {year_week}")
                    break
            
            if not is_processed:
                new_deals.append(deal)
                
        logger.info(f"Filtered {len(deals) - len(new_deals)} already processed candidates")
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
            
            # Normalize location to metro area
            location = await self._normalize_location(location)
            
            # Build mobility line from CRM fields
            mobility_line = self._build_mobility_line(
                deal.get('is_mobile', False),
                deal.get('remote_preference', False),
                deal.get('hybrid_preference', False)
            )
            
            # Fetch Zoom transcript if available
            transcript_text = None
            if deal.get('meeting_id') or deal.get('transcript_url'):
                from app.zoom_client import ZoomClient
                zoom_client = ZoomClient()
                meeting_ref = deal.get('meeting_id') or deal.get('transcript_url')
                try:
                    transcript_text = await zoom_client.fetch_zoom_transcript_for_meeting(meeting_ref)
                    if transcript_text:
                        logger.info(f"Successfully fetched Zoom transcript for candidate {candidate_name}")
                except Exception as e:
                    logger.warning(f"Could not fetch Zoom transcript: {e}")
            
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
            voit_result = await voit_orchestration(
                canonical_record,
                budget=5.0,
                target_quality=0.9
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
            
            # Create card with Brandon's format
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
                evidence_score=self._calculate_evidence_score(bullets)
            )
            
            # Cache the result
            if self.redis_client:
                await self._cache_c3_entry(cache_key, card)
            
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
    
    def _calculate_evidence_score(self, bullets: List[BulletPoint]) -> float:
        """Calculate overall evidence score for bullets."""
        if not bullets:
            return 0.0
            
        scores = [b.confidence for b in bullets]
        return sum(scores) / len(scores)
    
    def _generate_cache_key(self, record: Dict[str, Any], audience: str) -> str:
        """Generate C³ cache key."""
        key_data = f"{json.dumps(record, sort_keys=True)}|{audience}|talentwell_digest"
        return f"c3:digest:{hashlib.sha256(key_data.encode()).hexdigest()}"
    
    async def _get_c3_entry(self, cache_key: str) -> Optional[C3Entry]:
        """Get C³ entry from cache."""
        # Simplified - actual implementation would deserialize full C3Entry
        return None
    
    async def _cache_c3_entry(self, cache_key: str, card: DigestCard):
        """Cache C³ entry."""
        if not self.redis_client:
            return
            
        # Simplified - actual implementation would serialize full C3Entry
        await self.redis_client.setex(
            cache_key,
            86400 * 7,  # 7 days
            json.dumps(card.to_dict())
        )
    
    def _deserialize_card(self, artifact: Any) -> DigestCard:
        """Deserialize card from C³ artifact."""
        # Simplified implementation
        if isinstance(artifact, dict):
            bullets = [
                BulletPoint(**b) if isinstance(b, dict) else b
                for b in artifact.get('bullets', [])
            ]
            artifact['bullets'] = bullets
            return DigestCard(**artifact)
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

        # ONLY add experience if we have REAL data
        years_exp = None
        if deal.get('years_experience'):
            years_exp = deal.get('years_experience')
            bullets.append(BulletPoint(
                text=f"Experience: {years_exp}",
                confidence=0.95,
                source="CRM"
            ))
        elif enhanced_data.get('years_experience'):
            years_exp = enhanced_data.get('years_experience')
            bullets.append(BulletPoint(
                text=f"Experience: {years_exp}",
                confidence=0.95,
                source="Extraction"
            ))

        # Financial metrics take priority - format like Brandon's examples
        # AUM (most important metric)
        if deal.get('book_size_aum'):
            bullets.append(BulletPoint(
                text=f"AUM: {deal['book_size_aum']}",
                confidence=0.95,
                source="CRM"
            ))
        elif enhanced_data.get('aum_managed'):
            bullets.append(BulletPoint(
                text=f"AUM: {enhanced_data['aum_managed']}",
                confidence=0.95,
                source="Extraction"
            ))

        # Extract from ALL available CRM fields - we have this data!
        # Current role (most candidates have this)
        if deal.get('job_title') and deal['job_title'].strip() and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Current Role: {deal['job_title']}",
                confidence=0.9,
                source="CRM"
            ))

        # Company name (most candidates have this)
        if deal.get('company_name') and deal['company_name'].strip() and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Current Firm: {deal['company_name']}",
                confidence=0.9,
                source="CRM"
            ))

        # Location (this is ALWAYS available)
        if deal.get('location') and deal['location'].strip() and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Location: {deal['location']}",
                confidence=0.9,
                source="CRM"
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
            # First try the evidence extractor
            transcript_bullets = await self.evidence_extractor.extract_bullets(
                {"transcript": transcript},
                enhanced_data
            )

            # Add ALL financial-related bullets from transcript
            financial_keywords = [
                '$', 'million', 'billion', 'aum', 'production', 'revenue',
                'clients', 'years', '%', 'portfolio', 'assets', 'book',
                'series 7', 'series 66', 'series 65', 'cfa', 'cfp',
                'top performer', 'president', 'club', 'ranking', 'growth',
                'team', 'managing', 'billion', 'million', 'thousand'
            ]
            for bullet in transcript_bullets:
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

        # Availability (if space available)
        if deal.get('when_available') and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Available: {deal['when_available']}",
                confidence=0.9,
                source="CRM"
            ))
        elif enhanced_data.get('availability_timeframe') and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Available: {enhanced_data['availability_timeframe']}",
                confidence=0.9,
                source="Extraction"
            ))

        # Compensation expectations (lowest priority)
        if deal.get('desired_comp') and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Compensation: {deal['desired_comp']}",
                confidence=0.9,
                source="CRM"
            ))
        elif enhanced_data.get('compensation_range') and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Compensation: {enhanced_data['compensation_range']}",
                confidence=0.9,
                source="Extraction"
            ))

        # CRITICAL: Never add fake data - only return what we actually have
        # If we have less than 3 real bullets, that's acceptable per user requirement
        # If we have more than 5, take the top 5
        if len(bullets) > 5:
            bullets = bullets[:5]

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
            education = deal.get('education') or enhanced_data.get('education')
            if education and education.strip():
                bullets.append(BulletPoint(
                    text=f"Education: {education}",
                    confidence=0.8,
                    source="CRM"
                ))

        # Add industry focus if available
        if len(bullets) < 5:
            industry = deal.get('industry_focus') or enhanced_data.get('industry')
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
                unit_map = {'B': 'billion', 'M': 'million', 'K': 'thousand'}
                bullets.append(BulletPoint(
                    text=f"AUM: ${amount}{unit_map.get(unit.upper(), unit)}",
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