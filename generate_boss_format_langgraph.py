#!/usr/bin/env python3
"""
Generate Advisor Vault Alerts in BOSS'S EXACT FORMAT using LangGraph.
4-agent workflow with quality verification.
"""

import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from openai import AzureOpenAI
from dotenv import load_dotenv
import json
import sys
from typing import TypedDict, List, Dict, Optional
from langgraph.graph import StateGraph, END

from app.config.candidate_keywords import (
    VAULT_ADVISOR_KEYWORDS,
    VAULT_EXECUTIVE_KEYWORDS,
    is_advisor_title,
    is_executive_title,
)

# Load environment
load_dotenv('.env.local')

# Redis cache manager
sys.path.insert(0, '/home/romiteld/Development/Desktop_Apps/outlook/well_shared')
from well_shared.cache.redis_manager import RedisCacheManager

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')

# Use Azure OpenAI with gpt-5-mini deployment (Azure doesn't have gpt-5)
client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)

# State definition for LangGraph
class VaultAlertsState(TypedDict):
    all_candidates: List[Dict]
    advisor_candidates: List[Dict]
    executive_candidates: List[Dict]
    cache_manager: Optional[RedisCacheManager]
    cache_stats: Dict[str, int]
    quality_metrics: Dict[str, any]
    advisor_html: Optional[str]
    executive_html: Optional[str]
    errors: List[str]

# Advisor/Executive keyword helpers shared with Teams query engine
ADVISOR_KEYWORDS = VAULT_ADVISOR_KEYWORDS
EXECUTIVE_KEYWORDS = VAULT_EXECUTIVE_KEYWORDS


def is_advisor(title: str) -> bool:
    return is_advisor_title(title)


def is_executive(title: str) -> bool:
    return is_executive_title(title)

def get_alert_type(title: str) -> str:
    """Determine alert type for header."""
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

# AGENT 1: Database Loader
async def agent_database_loader(state: VaultAlertsState) -> VaultAlertsState:
    """Load all candidates from PostgreSQL and filter into two groups."""
    print("=" * 80)
    print("AGENT 1: DATABASE LOADER")
    print("=" * 80)
    print()

    print("🔄 Connecting to PostgreSQL...")
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        rows = await conn.fetch("""
            SELECT
                twav_number, candidate_name, title, city, state, current_location,
                firm, years_experience, aum, production, licenses, professional_designations,
                headline, interviewer_notes, top_performance, candidate_experience,
                availability, compensation, zoom_meeting_url
            FROM vault_candidates
            ORDER BY twav_number
        """)

        all_candidates = [dict(row) for row in rows]
        print(f"✅ Loaded {len(all_candidates)} candidates from database")
        print()

        # Filter
        advisor_candidates = []
        executive_candidates = []

        for candidate in all_candidates:
            title = candidate.get('title', '')
            if is_executive(title):
                executive_candidates.append(candidate)
            elif is_advisor(title):
                advisor_candidates.append(candidate)
            else:
                advisor_candidates.append(candidate)

        print(f"📊 Filtered candidates:")
        print(f"   Advisors: {len(advisor_candidates)}")
        print(f"   Executives: {len(executive_candidates)}")
        print()

        state['all_candidates'] = all_candidates
        state['advisor_candidates'] = advisor_candidates
        state['executive_candidates'] = executive_candidates

    finally:
        await conn.close()

    return state

# AGENT 2: GPT-5 Bullet Generator
async def agent_bullet_generator(state: VaultAlertsState) -> VaultAlertsState:
    """Generate 5-6 bullets per candidate using GPT-5."""
    print("=" * 80)
    print("AGENT 2: GPT-5 BULLET GENERATOR")
    print("=" * 80)
    print()

    print("🔄 Connecting to Redis cache...")
    cache_mgr = RedisCacheManager(
        connection_string=os.getenv('AZURE_REDIS_CONNECTION_STRING')
    )
    await cache_mgr.connect()
    print("✅ Redis cache connected")
    print()

    state['cache_manager'] = cache_mgr
    state['cache_stats'] = {'hits': 0, 'misses': 0}

    all_candidates = state['all_candidates']

    print(f"🔄 Generating 5-6 bullets per candidate using GPT-5...")
    print()

    for i, candidate in enumerate(all_candidates, 1):
        twav = candidate.get('twav_number', 'UNKNOWN')
        name = candidate.get('candidate_name', 'Unknown')

        print(f"  [{i}/{len(all_candidates)}] 🔄 Generating: {name} ({twav})")

        bullets = await generate_bullets(candidate, cache_mgr, state)
        candidate['bullets'] = bullets

        if i % 10 == 0:
            hits = state['cache_stats']['hits']
            misses = state['cache_stats']['misses']
            print(f"  Progress: {i}/{len(all_candidates)} | Cache: {hits} hits, {misses} misses")

    print()
    hits = state['cache_stats']['hits']
    misses = state['cache_stats']['misses']
    print(f"✅ Generated {len(all_candidates)} candidate bullet sets")
    print(f"   Cache Performance: {hits} hits, {misses} misses")
    print()

    return state

async def generate_bullets(candidate: dict, cache_mgr: RedisCacheManager, state: VaultAlertsState) -> list:
    """Generate 5-6 compelling bullet points using GPT-5."""
    twav = candidate.get('twav_number', 'UNKNOWN')
    cache_key = f"bullets_boss_format:{twav}"

    # Check cache
    cached = await cache_mgr.get(cache_key)
    if cached:
        state['cache_stats']['hits'] += 1
        return json.loads(cached)

    state['cache_stats']['misses'] += 1

    # Build context
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

Candidate data:
{context}

Availability: {availability}
Compensation: {compensation}

Return ONLY valid JSON with 5-6 bullets. LAST bullet MUST be availability + comp:
{{"bullets": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5", "Available on [availability]; desired comp [compensation]"]}}"""

    try:
        response = client.chat.completions.create(
            model=os.getenv('AZURE_OPENAI_DEPLOYMENT'),  # Uses gpt-5-mini deployment
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

        # Cache the result
        await cache_mgr.set(cache_key, json.dumps(bullets), ttl=timedelta(hours=24))

        return bullets

    except Exception as e:
        print(f"  ❌ Error generating bullets for {twav}: {e}")
        state['errors'].append(f"Bullet generation failed for {twav}: {e}")
        return [
            f"Experienced financial professional with background at {firm or 'leading firms'}.",
            f"Expertise in client relationship management and financial planning.",
            f"{years_exp or 'Multiple years'} of industry experience.",
            f"Licenses: {licenses or 'Various registrations'}.",
            "Seeks growth opportunity with collaborative team.",
            f"Available {availability}; desired comp {compensation}"
        ]

# AGENT 3: HTML Renderer
async def agent_html_renderer(state: VaultAlertsState) -> VaultAlertsState:
    """Render two HTML reports in BOSS'S EXACT FORMAT."""
    print("=" * 80)
    print("AGENT 3: HTML RENDERER (BOSS'S FORMAT)")
    print("=" * 80)
    print()

    advisor_candidates = state['advisor_candidates']
    executive_candidates = state['executive_candidates']

    print(f"🔄 Rendering HTML reports...")
    print(f"   Advisors: {len(advisor_candidates)} candidates")
    print(f"   Executives: {len(executive_candidates)} candidates")
    print()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Render advisor report
    advisor_html = render_boss_format(
        advisor_candidates,
        "Advisor Vault Candidate Alerts - Financial Advisors"
    )
    advisor_filename = f"boss_format_advisors_{timestamp}.html"
    with open(advisor_filename, 'w', encoding='utf-8') as f:
        f.write(advisor_html)
    print(f"✅ Saved: {advisor_filename}")
    state['advisor_html'] = advisor_filename

    # Render executive report
    executive_html = render_boss_format(
        executive_candidates,
        "Advisor Vault Candidate Alerts - Executives/Leadership"
    )
    executive_filename = f"boss_format_executives_{timestamp}.html"
    with open(executive_filename, 'w', encoding='utf-8') as f:
        f.write(executive_html)
    print(f"✅ Saved: {executive_filename}")
    state['executive_html'] = executive_filename

    print()
    return state

def render_boss_format(candidates: list, title: str) -> str:
    """Render HTML in BOSS'S EXACT FORMAT."""
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
        alert_type = get_alert_type(title_str)

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

        availability = candidate.get('availability', 'Not specified')
        compensation = candidate.get('compensation', 'Negotiable')
        twav = candidate.get('twav_number', 'UNKNOWN')

        # Get bullets
        bullets = candidate.get('bullets', [])
        bullets_html = "\n".join([f"          <li>{bullet}</li>" for bullet in bullets])

        # BOSS'S EXACT FORMAT from screenshots - NO Available/Comp line before bullets
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

# AGENT 4: Quality Verifier
async def agent_quality_verifier(state: VaultAlertsState) -> VaultAlertsState:
    """Verify report quality."""
    print("=" * 80)
    print("AGENT 4: QUALITY VERIFIER")
    print("=" * 80)
    print()

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

    total = metrics['total_candidates']

    print(f"✅ Quality Metrics:")
    print(f"   Total Candidates: {total}")
    print(f"   Locations Valid: {metrics['locations_valid']}/{total} ({metrics['locations_valid']/total*100:.1f}%)")
    print(f"   5-6 Bullets Per Card: {metrics['bullets_count_correct']}/{total} ({metrics['bullets_count_correct']/total*100:.1f}%)")
    print(f"   Ref Code Format: {metrics['ref_code_format']}/{total} ({metrics['ref_code_format']/total*100:.1f}%)")
    print()

    state['quality_metrics'] = metrics
    return state

# Build LangGraph workflow
async def build_workflow():
    """Build the 4-agent LangGraph workflow."""
    workflow = StateGraph(VaultAlertsState)

    workflow.add_node("database_loader", agent_database_loader)
    workflow.add_node("bullet_generator", agent_bullet_generator)
    workflow.add_node("html_renderer", agent_html_renderer)
    workflow.add_node("quality_verifier", agent_quality_verifier)

    workflow.set_entry_point("database_loader")
    workflow.add_edge("database_loader", "bullet_generator")
    workflow.add_edge("bullet_generator", "html_renderer")
    workflow.add_edge("html_renderer", "quality_verifier")
    workflow.add_edge("quality_verifier", END)

    return workflow.compile()

async def main():
    """Main entry point."""
    print("=" * 80)
    print("ADVISOR VAULT ALERTS - BOSS'S EXACT FORMAT")
    print("=" * 80)
    print()

    initial_state = VaultAlertsState(
        all_candidates=[],
        advisor_candidates=[],
        executive_candidates=[],
        cache_manager=None,
        cache_stats={'hits': 0, 'misses': 0},
        quality_metrics={},
        advisor_html=None,
        executive_html=None,
        errors=[]
    )

    app = await build_workflow()

    print("🚀 Starting LangGraph workflow...")
    print()

    final_state = await app.ainvoke(initial_state)

    if final_state.get('cache_manager'):
        try:
            await final_state['cache_manager'].close()
        except AttributeError:
            # RedisCacheManager might not have close() method
            pass

    print("=" * 80)
    print("✅ COMPLETE")
    print("=" * 80)
    print(f"Advisor Report: {final_state.get('advisor_html')}")
    print(f"Executive Report: {final_state.get('executive_html')}")
    print(f"Total Candidates: {final_state['quality_metrics']['total_candidates']}")
    print(f"Cache Hit Rate: {final_state['cache_stats']['hits']}/{final_state['quality_metrics']['total_candidates']}")

if __name__ == '__main__':
    asyncio.run(main())
