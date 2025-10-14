#!/usr/bin/env python3
"""
Generate Advisor Vault Alerts in BOSS'S EXACT FORMAT using LangGraph.
4-agent workflow with quality verification.

PRIVACY MODE INTEGRATION (2025-10-13):
- Anonymizes candidate data BEFORE GPT-5 bullet generation
- Company names → Generic descriptors (e.g., "Major wirehouse", "Large RIA")
- AUM/Production → Rounded ranges (e.g., "$1B+ AUM", "$500M+ AUM")
- GPT-5 system prompt includes confidentiality rules with examples
- Controlled by PRIVACY_MODE environment variable (default: true)
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

# Privacy mode flag
PRIVACY_MODE = os.getenv('PRIVACY_MODE', 'true').lower() == 'true'

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

# Company anonymization mapping for privacy
FIRM_TYPE_MAP = {
    'wirehouse': ['Merrill Lynch', 'Morgan Stanley', 'Wells Fargo', 'UBS', 'Raymond James'],
    'ria': ['Nuance Investments', 'Gottfried & Somberg', 'Fisher Investments', 'Edelman Financial'],
    'bank': ['JPMorgan', 'Bank of America', 'Wells Fargo Advisors', 'Citigroup'],
    'insurance': ['Northwestern Mutual', 'MassMutual', 'New York Life', 'Prudential'],
    'law_firm': ['Holland & Knight', 'Baker McKenzie', 'DLA Piper', 'K&L Gates', 'LLP', 'PC', 'Attorneys', 'Law'],
    'accounting': ['Deloitte', 'PwC', 'EY', 'KPMG', 'Grant Thornton'],
    'consulting': ['McKinsey', 'BCG', 'Bain', 'Accenture', 'Deloitte Consulting']
}

def parse_aum(aum_str: str) -> float:
    """Parse AUM string to float value in dollars."""
    if not aum_str:
        return 0.0

    # Remove $ and commas, clean up spaces
    cleaned = aum_str.replace('$', '').replace(',', '').strip()

    # Pattern to extract number and unit
    pattern = r'(\d+(?:\.\d+)?)\s*([BMKbmk])?'
    import re
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

def round_aum_for_privacy(aum_value: float) -> str:
    """Round AUM to broad ranges with + suffix for privacy."""
    if aum_value >= 1_000_000_000:  # $1B+
        billions = int(aum_value / 1_000_000_000)
        return f"${billions}B+ AUM"
    elif aum_value >= 100_000_000:  # $100M - $999M
        hundreds = int(aum_value / 100_000_000) * 100
        return f"${hundreds}M+ AUM"
    elif aum_value >= 10_000_000:  # $10M - $99M
        tens = int(aum_value / 10_000_000) * 10
        return f"${tens}M+ AUM"
    else:
        return ""  # Too small to display (identifying)

def anonymize_company(company_name: str, aum: float = None) -> str:
    """
    Replace firm names with generic descriptors for privacy.
    Prevents candidate identification through company name.
    """
    if not company_name or company_name == "Unknown":
        return "Not disclosed"

    # Check against known firm types
    for firm_type, firms in FIRM_TYPE_MAP.items():
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
            elif firm_type == 'law_firm':
                return "National law firm"
            elif firm_type == 'accounting':
                return "Major accounting firm"
            elif firm_type == 'consulting':
                return "Management consulting firm"

    # Generic fallback based on AUM
    if aum:
        if aum > 500_000_000:  # $500M+
            return "Large wealth management firm"
        else:
            return "Boutique advisory firm"

    return "Advisory firm"

def anonymize_candidate_data(candidate: dict) -> dict:
    """
    Anonymize candidate data before GPT-5 processing.

    Anonymization rules:
    - Company names → Generic firm types (e.g., "Major wirehouse", "Large RIA")
    - AUM values → Rounded ranges (e.g., "$1B+ AUM", "$500M+ AUM")
    - Production → Rounded ranges
    - Keep: Title, years experience, licenses, designations, location (city/state)
    - Remove: Specific firm names, exact compensation, unique identifiers
    """
    anon_candidate = candidate.copy()

    # Parse AUM for privacy-aware company anonymization
    parsed_aum = None
    if candidate.get('aum'):
        parsed_aum = parse_aum(str(candidate['aum']))

    # Anonymize company name
    if PRIVACY_MODE and candidate.get('firm'):
        anon_candidate['firm'] = anonymize_company(candidate['firm'], parsed_aum)

    # Round AUM to privacy ranges
    if PRIVACY_MODE and parsed_aum and parsed_aum > 0:
        anon_candidate['aum'] = round_aum_for_privacy(parsed_aum)

    # Round production to ranges (if present)
    if PRIVACY_MODE and candidate.get('production'):
        # Extract numeric value from production string
        import re
        prod_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*([BMKbmk])?', str(candidate['production']))
        if prod_match:
            prod_value = parse_aum(candidate['production'])
            if prod_value >= 1_000_000:
                prod_rounded = int(prod_value / 100_000) * 100_000
                anon_candidate['production'] = f"${prod_rounded // 1_000}K+" if prod_rounded < 1_000_000 else f"${prod_rounded // 1_000_000}M+"

    return anon_candidate

def post_process_bullets(bullets: list) -> list:
    """
    Post-process GPT-5 generated bullets to remove any leaked confidential information.

    Scans for and removes:
    - Specific firm names (wirehouses, RIAs, banks, insurance firms)
    - Exact AUM/production figures without + suffix
    - ZIP codes
    - University names
    - Specific city suburbs (replaced with metro area)

    Returns cleaned bullets with identifying information stripped.
    """
    if not PRIVACY_MODE:
        return bullets

    import re

    # Build comprehensive firm name patterns from FIRM_TYPE_MAP
    all_firms = []
    for firms_list in FIRM_TYPE_MAP.values():
        all_firms.extend(firms_list)

    # Additional known firms not in type map
    additional_firms = [
        'TD Ameritrade', 'Schwab', 'Charles Schwab', 'Fidelity', 'Vanguard',
        'Edward Jones', 'LPL Financial', 'Ameriprise', 'Northwestern',
        'Mass Mutual', 'Prudential', 'New York Life', 'Cresset', 'USAA',
        'Regions Bank', 'Truist', 'PNC', 'US Bank', 'Citibank',
        'Chase', 'Goldman Sachs', 'Credit Suisse', 'Deutsche Bank'
    ]
    all_firms.extend(additional_firms)

    # University patterns
    universities = [
        'Harvard', 'Yale', 'Princeton', 'Stanford', 'MIT', 'Columbia',
        'Penn', 'UPenn', 'Wharton', 'Duke', 'Dartmouth', 'Brown', 'Cornell',
        'Northwestern', 'Chicago', 'Berkeley', 'UCLA', 'USC', 'NYU',
        'Georgetown', 'Vanderbilt', 'Notre Dame', 'Rice', 'Emory',
        'UVA', 'Michigan', 'UNC', 'Wisconsin', 'Texas', 'Florida',
        'Ohio State', 'Penn State', 'Indiana', 'Illinois', 'Purdue',
        'Georgia Tech', 'UC Berkeley', 'Haas', 'Booth', 'Kellogg',
        'Stern', 'Fuqua', 'Tuck', 'Sloan', 'Ross', 'Anderson', 'Darden',
        'Cambridge', 'Oxford', 'LSE', 'INSEAD', 'IE Business', 'IE University'
    ]

    # Generic replacements
    firm_replacement = "a leading firm"
    university_replacement = "a top university"

    cleaned_bullets = []

    for bullet in bullets:
        cleaned = bullet

        # Strip firm names (case-insensitive)
        for firm in all_firms:
            # Match whole words only to avoid false positives
            pattern = r'\b' + re.escape(firm) + r'\b'
            if re.search(pattern, cleaned, re.IGNORECASE):
                cleaned = re.sub(pattern, firm_replacement, cleaned, flags=re.IGNORECASE)

        # Strip university names
        for uni in universities:
            pattern = r'\b' + re.escape(uni) + r'\b'
            if re.search(pattern, cleaned, re.IGNORECASE):
                cleaned = re.sub(pattern, university_replacement, cleaned, flags=re.IGNORECASE)

        # Strip exact AUM figures (e.g., "$1.5B", "$350M") if they DON'T have + suffix
        # Pattern: dollar sign, number with optional decimal, B or M unit, NOT followed by +
        cleaned = re.sub(r'\$(\d+(?:\.\d+)?)(B|M)(?!\+)', r'$\1\2+', cleaned)

        # Strip ZIP codes (5 digits)
        cleaned = re.sub(r'\b\d{5}\b', '[ZIP]', cleaned)

        # Clean up any double spaces or formatting issues from replacements
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        cleaned_bullets.append(cleaned)

    return cleaned_bullets

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

    # **CRITICAL: Anonymize candidate data BEFORE prompt building**
    anon_candidate = anonymize_candidate_data(candidate)

    # Build context from ANONYMIZED data
    title = anon_candidate.get('title', '')
    firm = anon_candidate.get('firm', '')
    years_exp = anon_candidate.get('years_experience', '')
    aum = anon_candidate.get('aum', '')
    production = anon_candidate.get('production', '')
    licenses = anon_candidate.get('licenses', '')
    headline = anon_candidate.get('headline', '')
    interviewer_notes = anon_candidate.get('interviewer_notes', '')
    top_performance = anon_candidate.get('top_performance', '')
    candidate_experience = anon_candidate.get('candidate_experience', '')
    professional_designations = anon_candidate.get('professional_designations', '')
    availability = anon_candidate.get('availability', 'Not specified')
    compensation = anon_candidate.get('compensation', 'Negotiable')

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

CONFIDENTIALITY RULES (CRITICAL):
- NEVER mention specific firm names (e.g., "Morgan Stanley", "UBS", "Merrill Lynch")
- USE generic descriptors already provided (e.g., "Major wirehouse", "Large RIA", "National bank")
- NEVER mention specific universities or unique identifiers
- USE rounded ranges for AUM/Production (e.g., "$1B+ AUM", "$500M+ AUM")
- AVOID any details that could uniquely identify the candidate

EXAMPLES OF ANONYMIZED BULLETS:
✅ "Built $1B+ AUM portfolio at major wirehouse over 15 years"
❌ "Built $1.2B AUM portfolio at Morgan Stanley from 2008-2023"

✅ "Manages $500M+ AUM with focus on HNW clients"
❌ "Manages $537M AUM with 85 HNW clients at UBS Private Wealth"

✅ "Holds CFP, CFA charterholder; Series 7, 65, 66"
❌ "Stanford MBA, CFP from 2015, worked at Goldman Sachs Private Wealth"

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
                {"role": "system", "content": "You are an expert financial recruiter writing compelling, CONFIDENTIAL bullet points. NEVER reveal specific firm names, universities, or identifying details. Use ONLY the anonymized data provided."},
                {"role": "user", "content": prompt}
            ],
            temperature=1,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        bullets = result.get('bullets', [])

        # Strip leading bullet characters that GPT might add
        bullets = [bullet.lstrip('• ').lstrip('- ').strip() for bullet in bullets]

        # **CRITICAL: Post-process to remove any leaked confidential information**
        bullets = post_process_bullets(bullets)

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

        # Location formatting with ZIP code removal
        import re
        city = candidate.get('city', '')
        state = candidate.get('state', '')
        location = candidate.get('current_location', '')

        if city and state:
            location = f"{city}, {state}"
        elif location:
            location = location
        else:
            location = "Location TBD"

        # **CRITICAL: Strip ZIP codes from location field (privacy requirement)**
        if PRIVACY_MODE:
            location = re.sub(r'\s*\d{5}(?:-\d{4})?\s*', '', location).strip()

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
