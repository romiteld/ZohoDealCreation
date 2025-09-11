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
            candidate_name = deal.get('candidate_name', 'Unknown')
            job_title = deal.get('job_title', 'Unknown')
            company = deal.get('company_name', 'Unknown')
            location = deal.get('location', 'Unknown')
            
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
            
            # Validate we have 2-5 bullets
            if len(bullets) < 2:
                logger.warning(f"Only {len(bullets)} bullets for candidate {candidate_name}, generating more")
                bullets = await self._ensure_minimum_bullets(deal, bullets)
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
        if not self.redis_client:
            return None
            
        key = f"geo:metro:{location.lower().replace(' ', '_')}"
        value = await self.redis_client.get(key)
        return value.decode() if value else None
    
    async def _get_firm_type(self, company: str) -> Optional[str]:
        """Get firm type from policy."""
        if not self.redis_client:
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
        """Generate 2-5 hard skill bullets, no soft skills."""
        bullets = []
        
        # Professional designations / licenses
        if deal.get('professional_designations'):
            bullets.append(BulletPoint(
                text=f"Licenses/Designations: {deal['professional_designations']}",
                confidence=0.95,
                source="CRM"
            ))
        
        # AUM/Book Size
        if deal.get('book_size_aum'):
            bullets.append(BulletPoint(
                text=f"Book Size: {deal['book_size_aum']}",
                confidence=0.95,
                source="CRM"
            ))
        
        # Production
        if deal.get('production_12mo'):
            bullets.append(BulletPoint(
                text=f"12-Month Production: {deal['production_12mo']}",
                confidence=0.95,
                source="CRM"
            ))
        
        # Extract from transcript if available
        if transcript and len(bullets) < 5:
            transcript_bullets = await self.evidence_extractor.extract_bullets(
                {"transcript": transcript},
                enhanced_data
            )
            # Filter for hard skills only
            for bullet in transcript_bullets:
                if any(keyword in bullet.text.lower() for keyword in 
                       ['$', 'million', 'billion', 'aum', 'clients', 'years', '%', 'portfolio']):
                    bullets.append(bullet)
                    if len(bullets) >= 5:
                        break
        
        # When Available
        if deal.get('when_available') and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Available: {deal['when_available']}",
                confidence=0.9,
                source="CRM"
            ))
        
        # Desired Comp
        if deal.get('desired_comp') and len(bullets) < 5:
            bullets.append(BulletPoint(
                text=f"Desired Compensation: {deal['desired_comp']}",
                confidence=0.9,
                source="CRM"
            ))
        
        return bullets
    
    async def _ensure_minimum_bullets(
        self,
        deal: Dict[str, Any],
        existing_bullets: List[BulletPoint]
    ) -> List[BulletPoint]:
        """Ensure we have at least 2 bullets."""
        bullets = list(existing_bullets)
        
        # Add generic hard skills if needed
        if len(bullets) < 2:
            if deal.get('job_title'):
                bullets.append(BulletPoint(
                    text=f"Current Role: {deal['job_title']}",
                    confidence=0.8,
                    source="CRM"
                ))
        
        if len(bullets) < 2:
            if deal.get('company_name'):
                bullets.append(BulletPoint(
                    text=f"Current Firm: {deal['company_name']}",
                    confidence=0.8,
                    source="CRM"
                ))
        
        return bullets


# Export curator instance
curator = TalentWellCurator()