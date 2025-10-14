"""
Vault Alerts Generator - Reusable LangGraph Module

Generates vault candidate alerts in boss's exact format using 4-agent LangGraph workflow.
Supports custom filtering for executive subscription system.

Architecture:
    Agent 1: Database Loader (with custom filters)
    Agent 2: GPT-5 Bullet Generator (with Redis caching)
    Agent 3: HTML Renderer (boss's exact format)
    Agent 4: Quality Verifier

Usage:
    generator = VaultAlertsGenerator()
    result = await generator.generate_alerts(
        custom_filters={
            "locations": ["New York, NY", "Chicago, IL"],
            "designations": ["CFA", "CFP"],
            "availability": "Immediately",
            "compensation_min": 150000,
            "compensation_max": 250000,
            "date_range_days": 30
        },
        max_candidates=50
    )
"""

import asyncpg
import os
import re
from datetime import datetime, timedelta
from openai import AsyncAzureOpenAI
import json
from typing import TypedDict, List, Dict, Optional, Any
from langgraph.graph import StateGraph, END

from well_shared.cache.redis_manager import RedisCacheManager
from app.config import PRIVACY_MODE
from app.utils.anonymizer import anonymize_candidate_data


# State definition for LangGraph
class VaultAlertsState(TypedDict):
    """State container for LangGraph workflow."""
    all_candidates: List[Dict]
    advisor_candidates: List[Dict]
    executive_candidates: List[Dict]
    cache_manager: Optional[RedisCacheManager]
    cache_stats: Dict[str, int]
    quality_metrics: Dict[str, Any]
    advisor_html: Optional[str]
    executive_html: Optional[str]
    errors: List[str]
    custom_filters: Optional[Dict]


# Advisor and Executive Keywords
ADVISOR_KEYWORDS = [
    'financial advisor', 'wealth advisor', 'investment advisor', 'wealth management',
    'financial adviser', 'private wealth', 'advisor', 'adviser', 'financial consultant',
    'relationship manager', 'portfolio manager', 'client advisor', 'senior advisor',
    'lead advisor', 'associate advisor', 'vice president', 'vp', 'director'
]

EXECUTIVE_KEYWORDS = [
    'ceo', 'chief executive', 'cfo', 'chief financial', 'coo', 'chief operating',
    'cto', 'chief technology', 'cio', 'chief investment', 'president', 'managing director',
    'managing partner', 'partner', 'founder', 'co-founder', 'owner', 'principal',
    'head of', 'cbdo', 'cgo', 'ccdo', 'cgrowth', 'chief growth', 'chief business'
]


class VaultAlertsGenerator:
    """Generate vault candidate alerts using LangGraph 4-agent workflow."""

    def __init__(self, database_url: str = None, redis_connection: str = None):
        """
        Initialize generator with database and cache connections.

        Args:
            database_url: PostgreSQL connection string (defaults to env var)
            redis_connection: Redis connection string (defaults to env var)
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required for VaultAlertsGenerator")

        self.redis_connection = redis_connection or os.getenv('AZURE_REDIS_CONNECTION_STRING')

        azure_api_key = os.getenv('AZURE_OPENAI_KEY')
        azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        azure_api_version = os.getenv('AZURE_OPENAI_API_VERSION')
        if not azure_api_key or not azure_endpoint:
            raise ValueError("Azure OpenAI credentials are required for VaultAlertsGenerator")

        # Azure OpenAI client (use gpt-5-mini deployment)
        self.client = AsyncAzureOpenAI(
            api_key=azure_api_key,
            api_version=azure_api_version,
            azure_endpoint=azure_endpoint
        )
        self.model = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-5-mini')

    async def generate_alerts(
        self,
        custom_filters: Optional[Dict] = None,
        max_candidates: Optional[int] = None,
        save_files: bool = True
    ) -> Dict:
        """
        Generate vault candidate alerts with optional custom filtering.

        Args:
            custom_filters: Optional filters for candidate selection:
                {
                    "locations": ["New York, NY", "Chicago, IL"],
                    "designations": ["CFA", "CFP"],
                    "availability": "Immediately",
                    "compensation_min": 150000,
                    "compensation_max": 250000,
                    "date_range_days": 30,  # Only candidates added in last N days
                    "search_terms": ["portfolio manager", "RIA"]
                }
            max_candidates: Maximum number of candidates to return (None = unlimited)
            save_files: Whether to save HTML files to disk (default: True)

        Returns:
            {
                "advisor_html": "HTML content for advisors",
                "executive_html": "HTML content for executives",
                "advisor_filename": "boss_format_advisors_20251011_095703.html",
                "executive_filename": "boss_format_executives_20251011_095703.html",
                "metadata": {
                    "total_candidates": 146,
                    "advisor_count": 111,
                    "executive_count": 35,
                    "cache_hit_rate": 0.98,
                    "generation_time_seconds": 3.5,
                    "filters_applied": {...}
                },
                "quality_metrics": {...},
                "errors": []
            }
        """
        start_time = datetime.now()

        # Initialize state
        initial_state = VaultAlertsState(
            all_candidates=[],
            advisor_candidates=[],
            executive_candidates=[],
            cache_manager=None,
            cache_stats={'hits': 0, 'misses': 0},
            quality_metrics={},
            advisor_html=None,
            executive_html=None,
            errors=[],
            custom_filters=custom_filters or {}
        )

        # Build and run workflow
        app = await self._build_workflow()
        final_state = await app.ainvoke(initial_state)

        # Close cache manager
        cache_manager = final_state.get('cache_manager')
        if cache_manager:
            try:
                await cache_manager.disconnect()
            except AttributeError:
                pass

        # Apply max_candidates limit if specified
        if max_candidates:
            final_state['advisor_candidates'] = final_state['advisor_candidates'][:max_candidates]
            final_state['executive_candidates'] = final_state['executive_candidates'][:max_candidates]

        # Calculate generation time
        generation_time = (datetime.now() - start_time).total_seconds()

        # Save files if requested
        advisor_filename = None
        executive_filename = None
        if save_files:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            advisor_filename = f"boss_format_advisors_{timestamp}.html"
            executive_filename = f"boss_format_executives_{timestamp}.html"

            with open(advisor_filename, 'w', encoding='utf-8') as f:
                f.write(final_state['advisor_html'])
            with open(executive_filename, 'w', encoding='utf-8') as f:
                f.write(final_state['executive_html'])

        # Build response
        quality_metrics = final_state.get('quality_metrics', {})
        total_candidates = quality_metrics.get('total_candidates', 0)
        cache_stats = final_state.get('cache_stats', {})
        cache_hits = cache_stats.get('hits', 0)
        cache_misses = cache_stats.get('misses', 0)
        cache_operations = cache_hits + cache_misses
        cache_hit_rate = cache_hits / cache_operations if cache_operations else 0.0
        filters_applied = final_state.get('custom_filters') or (custom_filters or {})

        return {
            "advisor_html": final_state.get('advisor_html'),
            "executive_html": final_state.get('executive_html'),
            "advisor_filename": advisor_filename,
            "executive_filename": executive_filename,
            "metadata": {
                "total_candidates": total_candidates,
                "advisor_count": len(final_state['advisor_candidates']),
                "executive_count": len(final_state['executive_candidates']),
                "cache_hit_rate": round(cache_hit_rate, 2),
                "generation_time_seconds": round(generation_time, 2),
                "filters_applied": filters_applied,
                "anonymization_applied": PRIVACY_MODE,
                "anonymization_rules": [
                    "firm_names",
                    "aum_rounding",
                    "production_rounding",
                    "location_normalization"
                ] if PRIVACY_MODE else []
            },
            "quality_metrics": quality_metrics,
            "errors": final_state.get('errors', [])
        }

    async def _build_workflow(self) -> StateGraph:
        """Build the 4-agent LangGraph workflow."""
        workflow = StateGraph(VaultAlertsState)

        workflow.add_node("database_loader", self._agent_database_loader)
        workflow.add_node("bullet_generator", self._agent_bullet_generator)
        workflow.add_node("html_renderer", self._agent_html_renderer)
        workflow.add_node("quality_verifier", self._agent_quality_verifier)

        workflow.set_entry_point("database_loader")
        workflow.add_edge("database_loader", "bullet_generator")
        workflow.add_edge("bullet_generator", "html_renderer")
        workflow.add_edge("html_renderer", "quality_verifier")
        workflow.add_edge("quality_verifier", END)

        return workflow.compile()

    # -------------------------------------------------------------------------
    # Input Validation (SQL Injection Prevention)
    # -------------------------------------------------------------------------

    def _validate_custom_filters(self, filters: Dict) -> Dict:
        """
        Validate and sanitize custom filters to prevent SQL injection attacks.

        Security controls:
        - Whitelist allowed filter keys
        - Type validation for all inputs
        - Range checks for numeric values
        - Length limits for strings
        - Array size limits

        Args:
            filters: Raw filters from API request

        Returns:
            Sanitized filters safe for database queries
        """
        import logging
        logger = logging.getLogger(__name__)

        if not filters:
            return {}

        # Only allow whitelisted keys
        ALLOWED_KEYS = {
            'locations', 'designations', 'availability',
            'compensation_min', 'compensation_max', 'date_range_days', 'search_terms'
        }

        sanitized = {}

        for key, value in filters.items():
            # Only allow whitelisted keys
            if key not in ALLOWED_KEYS:
                logger.warning(f"⚠️ Input validation: Ignoring invalid filter key: {key}")
                continue

            # Validate numeric ranges
            if key in ['compensation_min', 'compensation_max', 'date_range_days']:
                try:
                    sanitized[key] = int(value) if value is not None else None

                    # Range checks to prevent abuse
                    if sanitized[key] is not None:
                        if key == 'date_range_days':
                            # Limit: 1-365 days
                            sanitized[key] = max(1, min(sanitized[key], 365))
                        else:  # compensation
                            # Limit: $0-$10M (reasonable max for financial advisors)
                            sanitized[key] = max(0, min(sanitized[key], 10_000_000))

                except (TypeError, ValueError):
                    logger.warning(f"⚠️ Input validation: Invalid numeric value for {key}: {value}")
                    continue

            # Validate string lists (locations, designations, search_terms)
            elif key in ['locations', 'designations', 'search_terms']:
                if isinstance(value, list):
                    # Sanitize each item
                    sanitized_items = []
                    for item in value[:50]:  # Max 50 items per list
                        if item:
                            item_str = str(item).strip()
                            # Length limit: 100 chars per item
                            if len(item_str) <= 100:
                                sanitized_items.append(item_str)
                            else:
                                logger.warning(f"⚠️ Input validation: String too long in {key}: {item_str[:50]}...")

                    if sanitized_items:
                        sanitized[key] = sanitized_items
                else:
                    logger.warning(f"⚠️ Input validation: Expected list for {key}, got {type(value)}")

            # Validate single string (availability)
            elif key == 'availability':
                if isinstance(value, str):
                    value_str = value.strip()
                    # Length limit: 100 chars
                    if len(value_str) <= 100:
                        sanitized[key] = value_str
                    else:
                        logger.warning(f"⚠️ Input validation: availability string too long: {value_str[:50]}...")
                else:
                    logger.warning(f"⚠️ Input validation: Expected string for availability, got {type(value)}")

        # Log sanitization summary
        if len(sanitized) < len(filters):
            rejected_keys = set(filters.keys()) - set(sanitized.keys())
            logger.info(f"🛡️ Input validation: Rejected {len(rejected_keys)} invalid filter keys: {rejected_keys}")

        return sanitized

    # -------------------------------------------------------------------------
    # AGENT 1: Database Loader (with custom filters)
    # -------------------------------------------------------------------------

    async def _agent_database_loader(self, state: VaultAlertsState) -> VaultAlertsState:
        """Load candidates from PostgreSQL with optional custom filtering."""
        raw_filters = state.get('custom_filters', {}) or {}

        # ========================================================================
        # SECURITY: Validate and sanitize custom filters to prevent SQL injection
        # ========================================================================
        custom_filters = self._validate_custom_filters(raw_filters)

        # Extract sanitized filter values
        locations = custom_filters.get('locations', [])
        designations = custom_filters.get('designations', [])
        availability_filter = custom_filters.get('availability')
        search_terms = custom_filters.get('search_terms', [])
        date_range_days = custom_filters.get('date_range_days')  # Already validated as int
        min_comp = custom_filters.get('compensation_min')  # Already validated as int
        max_comp = custom_filters.get('compensation_max')  # Already validated as int

        conn = await asyncpg.connect(self.database_url)

        try:
            # Build SQL query with custom filters
            query = """
                SELECT
                    twav_number, candidate_name, title, city, state, current_location,
                    firm, years_experience, aum, production, licenses, professional_designations,
                    headline, interviewer_notes, top_performance, candidate_experience,
                    availability, compensation, zoom_meeting_url, created_at
                FROM vault_candidates
                WHERE 1=1
            """
            params = []
            param_index = 1

            # Location filter
            if locations:
                location_conditions = []
                for location in locations:
                    params.append(f"%{location}%")
                    location_conditions.append(f"(city || ', ' || state) ILIKE ${param_index}")
                    param_index += 1
                query += f" AND ({' OR '.join(location_conditions)})"

            # Professional designations filter
            if designations:
                designation_conditions = []
                for designation in designations:
                    params.append(f"%{designation}%")
                    designation_conditions.append(f"professional_designations ILIKE ${param_index}")
                    param_index += 1
                query += f" AND ({' OR '.join(designation_conditions)})"

            # Availability filter
            if availability_filter:
                params.append(f"%{availability_filter}%")
                query += f" AND availability ILIKE ${param_index}"
                param_index += 1

            # Date range filter (candidates added in last N days)
            if date_range_days:
                cutoff_date = datetime.now() - timedelta(days=date_range_days)
                params.append(cutoff_date)
                query += f" AND created_at >= ${param_index}"
                param_index += 1

            # Search terms filter (search in multiple fields)
            if search_terms:
                search_conditions = []
                for term in search_terms:
                    params.append(f"%{term}%")
                    search_conditions.append(
                        f"(title ILIKE ${param_index} OR headline ILIKE ${param_index} OR "
                        f"interviewer_notes ILIKE ${param_index})"
                    )
                    param_index += 1
                query += f" AND ({' OR '.join(search_conditions)})"

            query += " ORDER BY twav_number"

            # Execute query
            if params:
                rows = await conn.fetch(query, *params)
            else:
                rows = await conn.fetch(query)

            all_candidates = [dict(row) for row in rows]

            # **ANONYMIZE ALL CANDIDATES** immediately after loading from database
            if PRIVACY_MODE:
                all_candidates = [anonymize_candidate_data(c) for c in all_candidates]

            # Compensation range filtering (post-query parsing)
            if min_comp is not None or max_comp is not None:
                all_candidates = [
                    candidate for candidate in all_candidates
                    if self._compensation_in_range(candidate.get('compensation'), min_comp, max_comp)
                ]

            # Filter into advisor vs executive categories
            advisor_candidates = []
            executive_candidates = []

            for candidate in all_candidates:
                title = candidate.get('title', '')
                if self._is_executive(title):
                    executive_candidates.append(candidate)
                elif self._is_advisor(title):
                    advisor_candidates.append(candidate)
                else:
                    advisor_candidates.append(candidate)  # Default to advisor

            # Persist normalized filters for downstream metadata
            normalized_filters: Dict[str, Any] = {}
            if locations:
                normalized_filters['locations'] = locations
            if designations:
                normalized_filters['designations'] = designations
            if availability_filter:
                normalized_filters['availability'] = availability_filter
            if min_comp is not None:
                normalized_filters['compensation_min'] = min_comp
            if max_comp is not None:
                normalized_filters['compensation_max'] = max_comp
            if date_range_days:
                normalized_filters['date_range_days'] = date_range_days
            if search_terms:
                normalized_filters['search_terms'] = search_terms

            state['all_candidates'] = all_candidates
            state['advisor_candidates'] = advisor_candidates
            state['executive_candidates'] = executive_candidates
            state['custom_filters'] = normalized_filters

        finally:
            await conn.close()

        return state

    # -------------------------------------------------------------------------
    # AGENT 2: GPT-5 Bullet Generator
    # -------------------------------------------------------------------------

    async def _agent_bullet_generator(self, state: VaultAlertsState) -> VaultAlertsState:
        """Generate 5-6 bullets per candidate using GPT-5 with Redis caching."""
        # Connect to Redis cache
        cache_mgr = RedisCacheManager(connection_string=self.redis_connection)
        await cache_mgr.connect()

        state['cache_manager'] = cache_mgr
        state['cache_stats'] = {'hits': 0, 'misses': 0}

        all_candidates = state['all_candidates']

        # Generate bullets for each candidate
        for candidate in all_candidates:
            bullets = await self._generate_bullets(candidate, cache_mgr, state)
            candidate['bullets'] = bullets

        return state

    async def _generate_bullets(
        self,
        candidate: dict,
        cache_mgr: RedisCacheManager,
        state: VaultAlertsState
    ) -> list:
        """Generate 5-6 compelling bullet points using GPT-5."""
        twav = candidate.get('twav_number', 'UNKNOWN')
        cache_key = f"bullets_boss_format:{twav}"

        # Check cache
        cached = await cache_mgr.get(cache_key)
        if cached:
            state['cache_stats']['hits'] += 1
            return json.loads(cached)

        state['cache_stats']['misses'] += 1

        # Build context from candidate data
        title = candidate.get('title', '')
        firm = candidate.get('firm', '')
        years_exp = candidate.get('years_experience', '')
        aum = candidate.get('aum', '')
        production = candidate.get('production', '')
        licenses = candidate.get('licenses', '')
        headline = candidate.get('headline', '')
        interviewer_notes = candidate.get('interviewer_notes', '')
        top_performance = candidate.get('top_performance', '')
        candidate_experience = candidate.get('candidate_experience', '')
        professional_designations = candidate.get('professional_designations', '')
        availability = candidate.get('availability', 'Not specified')
        compensation = candidate.get('compensation', 'Negotiable')

        context_parts = []
        if title:
            context_parts.append(f"Title: {title}")
        if firm:
            context_parts.append(f"Current Firm: {firm}")
        if years_exp:
            context_parts.append(f"Years Experience: {years_exp}")
        if aum:
            context_parts.append(f"AUM: {aum}")
        if production:
            context_parts.append(f"Production: {production}")
        if professional_designations:
            context_parts.append(f"Credentials: {professional_designations}")
        if licenses:
            context_parts.append(f"Licenses: {licenses}")
        if headline:
            context_parts.append(f"Headline: {headline}")
        if top_performance:
            context_parts.append(f"Top Performance: {top_performance}")
        if candidate_experience:
            context_parts.append(f"Experience Details: {candidate_experience}")
        if interviewer_notes:
            context_parts.append(f"Interviewer Notes: {interviewer_notes}")

        context = "\n".join(context_parts)

        # GPT-5 prompt in boss's exact format with confidentiality rules
        privacy_rules = ""
        if PRIVACY_MODE:
            privacy_rules = """
CONFIDENTIALITY RULES (CRITICAL):
- NO specific firm names (use generic descriptors: "Major wirehouse", "Large RIA", "National bank")
- NO exact AUM (use rounded ranges: "$1B+ AUM", "$500M+ AUM")
- NO exact production (use rounded ranges: "$500K+ production")
- YES to licenses, designations, title, location (city/state), years experience
- YES to achievements, rankings, growth metrics
"""

        prompt = f"""Write 5-6 compelling bullet points for a financial advisor candidate alert.

EXAMPLE FORMAT from boss:
• Built $2.2B RIA from inception alongside founder; led portfolio design, investment modeling, and firmwide scaling initiatives
• CFA charterholder who passed 3 levels consecutively
• Formerly held Series 7, 24, 55, 65, and 66; comfortable reactivating licenses if needed
• Passionate about macroeconomics and portfolio construction; led investment due diligence and model customization across 7 strategies
• Values: honesty, sincerity, and self-awareness; thrives in roles with autonomy, high accountability, and clear direction
• Available on 2 weeks' notice; desired comp $150K-$200K OTE

CRITICAL RULES:
1. Write 5-6 bullets (NOT 4)
2. Start with BIGGEST achievements (AUM, production, growth, rankings)
3. Include credentials and licenses
4. Add personality/values bullet
5. LAST bullet MUST repeat availability and compensation exactly
6. Use active verbs and specific numbers
{privacy_rules}
Candidate data:
{context}

Availability: {availability}
Compensation: {compensation}

Return ONLY valid JSON with 5-6 bullets. LAST bullet MUST be availability + comp:
{{"bullets": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5", "Available on [availability]; desired comp [compensation]"]}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert financial recruiter writing compelling bullet points."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            bullets = result.get('bullets', [])

            # Strip leading bullet characters that GPT might add
            bullets = [bullet.lstrip('• ').lstrip('- ').strip() for bullet in bullets]

            # Validate we got 5-6 bullets
            if len(bullets) < 5 or len(bullets) > 6:
                # Add availability bullet if missing
                bullets.append(f"Available {availability}; desired comp {compensation}")

            # Cache the result (24 hour TTL)
            await cache_mgr.set(cache_key, json.dumps(bullets), ttl=timedelta(hours=24))

            return bullets

        except Exception as e:
            state['errors'].append(f"Bullet generation failed for {twav}: {e}")
            return [
                f"Experienced financial professional with background at {firm or 'leading firms'}.",
                f"Expertise in client relationship management and financial planning.",
                f"{years_exp or 'Multiple years'} of industry experience.",
                f"Licenses: {licenses or 'Various registrations'}.",
                "Seeks growth opportunity with collaborative team.",
                f"Available {availability}; desired comp {compensation}"
            ]

    # -------------------------------------------------------------------------
    # AGENT 3: HTML Renderer (Boss's Exact Format)
    # -------------------------------------------------------------------------

    async def _agent_html_renderer(self, state: VaultAlertsState) -> VaultAlertsState:
        """Render HTML reports in BOSS'S EXACT FORMAT."""
        advisor_candidates = state['advisor_candidates']
        executive_candidates = state['executive_candidates']

        # Render advisor report
        advisor_html = self._render_boss_format(
            advisor_candidates,
            "Advisor Vault Candidate Alerts - Financial Advisors"
        )
        state['advisor_html'] = advisor_html

        # Render executive report
        executive_html = self._render_boss_format(
            executive_candidates,
            "Advisor Vault Candidate Alerts - Executives/Leadership"
        )
        state['executive_html'] = executive_html

        return state

    def _render_boss_format(self, candidates: list, title: str) -> str:
        """Render HTML in BOSS'S EXACT FORMAT with print-optimized CSS."""
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title} - {timestamp}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .stats {{
            background: #fff;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .candidate-card {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .candidate-card h2 {{
            color: #2c3e50;
            margin-top: 0;
        }}
        .candidate-card ul {{
            line-height: 1.8;
        }}
        @media print {{
            .candidate-card {{
                page-break-inside: avoid;
                break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <h1>📊 {title}</h1>
    <div class="stats">
        <p><strong>Generated:</strong> {timestamp}</p>
        <p><strong>Total Candidates:</strong> {len(candidates)}</p>
    </div>

    <div class="candidates">
"""

        for candidate in candidates:
            title_str = candidate.get('title', 'Unknown')
            alert_type = self._get_alert_type(title_str)

            # Location formatting
            city = candidate.get('city', '')
            state = candidate.get('state', '')
            location = candidate.get('current_location', '')

            if city and state:
                location = f"{city}, {state}"
            elif location:
                location = location
            else:
                location = "Location TBD"

            twav = candidate.get('twav_number', 'UNKNOWN')
            bullets = candidate.get('bullets', [])
            bullets_html = "\n".join([f"          <li>{bullet}</li>" for bullet in bullets])

            # BOSS'S EXACT FORMAT - NO Available/Comp line before bullets
            card = f"""
      <div class="candidate-card">
        <h2>‼️  {alert_type} 🔔</h2>
        <p><strong>📍 Location: {location}</strong> (Is not mobile; <strong>Open to Remote</strong> or Hybrid)</p>
        <ul>
{bullets_html}
        </ul>
        <p>Ref code: {twav}</p>
      </div>
"""
            html += card

        html += """
    </div>
</body>
</html>"""

        return html

    # -------------------------------------------------------------------------
    # AGENT 4: Quality Verifier
    # -------------------------------------------------------------------------

    async def _agent_quality_verifier(self, state: VaultAlertsState) -> VaultAlertsState:
        """Verify report quality metrics."""
        all_candidates = state['all_candidates']

        metrics = {
            'total_candidates': len(all_candidates),
            'locations_valid': 0,
            'bullets_count_correct': 0,
            'ref_code_format': 0
        }

        for candidate in all_candidates:
            location = candidate.get('current_location') or f"{candidate.get('city', '')}, {candidate.get('state', '')}"
            if location and location != ", ":
                metrics['locations_valid'] += 1

            bullets = candidate.get('bullets', [])
            if len(bullets) >= 5 and len(bullets) <= 6:
                metrics['bullets_count_correct'] += 1

            twav = candidate.get('twav_number', '')
            if twav.startswith('TWAV'):
                metrics['ref_code_format'] += 1

        state['quality_metrics'] = metrics
        return state

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        """Safely convert values to integers."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            cleaned = str(value).strip()
            return int(cleaned) if cleaned else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_compensation_values(compensation_text: str) -> List[int]:
        """Extract numeric compensation values (supports k/m/b suffixes)."""
        normalized = re.sub(r'[,\$]', '', compensation_text.lower())
        values: List[int] = []

        for match in re.finditer(r'(\d+(?:\.\d+)?)(\s*[kmb])?', normalized):
            number = float(match.group(1))
            suffix = (match.group(2) or '').strip()
            if suffix == 'k':
                number *= 1_000
            elif suffix == 'm':
                number *= 1_000_000
            elif suffix == 'b':
                number *= 1_000_000_000

            if number >= 1_000:
                values.append(int(number))

        return values

    def _compensation_in_range(
        self,
        compensation_text: Optional[str],
        min_value: Optional[int],
        max_value: Optional[int]
    ) -> bool:
        """Determine if compensation text satisfies requested range."""
        if min_value is None and max_value is None:
            return True

        if not compensation_text:
            return False

        values = self._extract_compensation_values(compensation_text)
        if not values:
            return False

        candidate_min = min(values)
        candidate_max = max(values)

        if min_value is not None and candidate_max < min_value:
            return False
        if max_value is not None and candidate_min > max_value:
            return False

        return True

    def _is_advisor(self, title: str) -> bool:
        """Check if title contains advisor keywords."""
        if not title:
            return False
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in ADVISOR_KEYWORDS)

    def _is_executive(self, title: str) -> bool:
        """Check if title contains executive keywords."""
        if not title:
            return False
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in EXECUTIVE_KEYWORDS)

    def _get_alert_type(self, title: str) -> str:
        """Determine alert type for header based on job title."""
        if not title:
            return "Advisor Candidate Alert"

        title_lower = title.lower()

        # Check for C-suite titles first (most specific)
        if 'cio' in title_lower or 'cgo' in title_lower:
            return "CIO / CGO Candidate Alert"
        elif 'ceo' in title_lower or 'coo' in title_lower:
            return "CEO / President Candidate Alert"
        elif 'cfo' in title_lower:
            return "CFO Candidate Alert"

        # Check for executive leadership titles
        elif 'president' in title_lower or 'founder' in title_lower:
            return "CEO / President Candidate Alert"
        elif 'managing director' in title_lower or 'managing partner' in title_lower:
            return "Managing Director / Partner Candidate Alert"
        elif 'partner' in title_lower and 'advisor' not in title_lower:
            return "Partner / Principal Candidate Alert"
        elif 'principal' in title_lower and 'advisor' not in title_lower:
            return "Partner / Principal Candidate Alert"

        # Check for VP and director titles
        elif ('vice president' in title_lower or 'vp ' in title_lower or ' vp' in title_lower) and 'advisor' not in title_lower:
            return "Vice President Candidate Alert"
        elif 'head of' in title_lower:
            return "Head of Department Candidate Alert"
        elif ('director' in title_lower or 'evp' in title_lower or 'svp' in title_lower) and 'advisor' not in title_lower:
            return "Director / Executive Candidate Alert"

        # Default to advisor
        else:
            return "Advisor Candidate Alert"

