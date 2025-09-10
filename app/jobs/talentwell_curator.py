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
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Generate weekly digest for specified audience and date range."""
        
        if not self.initialized:
            await self.initialize()
        
        # Default date range: last 7 days
        if not to_date:
            to_date = datetime.now()
        if not from_date:
            from_date = to_date - timedelta(days=7)
            
        logger.info(f"Generating digest for {audience} from {from_date} to {to_date}")
        
        # Step 1: Query deals
        deals = await self._query_deals(audience, from_date, to_date, owner)
        logger.info(f"Found {len(deals)} deals for processing")
        
        # Step 2: Check deduplication
        week_key = f"{to_date.year}-{to_date.isocalendar()[1]}"
        processed_key = f"talentwell:processed:{week_key}"
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
        """Query deals from Zoho or CSV cache."""
        
        # Try to load from CSV cache first
        if self.redis_client:
            cache_key = f"deals:cache:{audience}:{from_date.date()}:{to_date.date()}"
            cached = await self.redis_client.get(cache_key)
            if cached:
                logger.info("Using cached deal data")
                return json.loads(cached.decode())
        
        # Otherwise, query from Zoho API
        deals = []
        headers = get_zoho_headers()
        
        # Note: Actual Zoho query implementation would go here
        # For now, return empty list (will be populated via CSV import)
        logger.warning("Zoho API query not implemented, using empty list")
        return deals
    
    async def _filter_processed_deals(
        self,
        deals: List[Dict[str, Any]],
        processed_key: str
    ) -> List[Dict[str, Any]]:
        """Filter out already processed deals."""
        if not self.redis_client:
            return deals
            
        new_deals = []
        for deal in deals:
            is_member = await self.redis_client.sismember(processed_key, deal['id'])
            if not is_member:
                new_deals.append(deal)
                
        return new_deals
    
    async def _process_deal(
        self,
        deal: Dict[str, Any],
        audience: str
    ) -> Optional[DigestCard]:
        """Process single deal with C³/VoIT and evidence extraction."""
        
        try:
            # Extract base information
            candidate_name = deal.get('Candidate_Name', 'Unknown')
            job_title = deal.get('Job_Title', 'Unknown')
            company = deal.get('Firm_Name', 'Unknown')
            location = deal.get('Location', 'Unknown')
            
            # Check C³ cache
            canonical_record = {
                'candidate_name': candidate_name,
                'job_title': job_title,
                'company': company,
                'location': location,
                'deal_id': deal['id']
            }
            
            cache_key = self._generate_cache_key(canonical_record, audience)
            
            # Try C³ reuse
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
                        logger.info(f"C³ cache hit for deal {deal['id']}")
                        return self._deserialize_card(artifact)
            
            # Process with VoIT if not cached
            voit_result = await voit_orchestration(
                canonical_record,
                budget=5.0,
                target_quality=0.9
            )
            
            # Extract evidence-linked bullets
            bullets = await self.evidence_extractor.extract_bullets(
                deal,
                voit_result.get('enhanced_data', {})
            )
            
            # Get location context
            metro_area = await self._get_metro_area(location)
            firm_type = await self._get_firm_type(company)
            
            # Create card
            card = DigestCard(
                deal_id=deal['id'],
                candidate_name=candidate_name,
                job_title=job_title,
                company=company,
                location=location,
                bullets=bullets[:3],  # Top 3 bullets
                metro_area=metro_area,
                firm_type=firm_type,
                source=deal.get('Source'),
                source_detail=deal.get('Source_Detail'),
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
        """Format card as HTML."""
        bullets_html = '\n'.join([
            f'<li>{bullet.text}</li>'
            for bullet in card.bullets
        ])
        
        location_info = card.metro_area or card.location
        company_info = f"{card.firm_type} - {card.company}" if card.firm_type else card.company
        
        return f"""
        <div class="candidate-card">
            <h3>{card.candidate_name}</h3>
            <p class="role">{card.job_title} @ {company_info}</p>
            <p class="location">📍 {location_info}</p>
            <ul class="highlights">
                {bullets_html}
            </ul>
            {'<p class="meeting-note">✓ Interview completed ' + card.meeting_date.strftime('%b %d') + '</p>' if card.meeting_date else ''}
        </div>
        """


# Export curator instance
curator = TalentWellCurator()