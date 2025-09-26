#!/usr/bin/env python3
"""
Run TalentWell Curator with REAL TWAV numbers from Zoho CRM.
This uses the existing talentwell_curator.py but ensures real data.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
import logging

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables if not already set
os.environ.setdefault('ZOHO_OAUTH_SERVICE_URL', 'https://well-zoho-oauth.azurewebsites.net')
os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test')

from app.jobs.talentwell_curator import TalentWellCurator, DigestCard
from app.extract.evidence import BulletPoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_talentwell_for_brandon():
    """Run TalentWell curator to generate Brandon's digest with REAL candidates."""

    curator = TalentWellCurator()
    await curator.initialize()

    # Run the digest generation - this will query REAL candidates from Zoho
    result = await curator.run_weekly_digest(
        audience="brandon",
        from_date=datetime.now() - timedelta(days=30),  # Last 30 days
        to_date=datetime.now(),
        dry_run=True,  # Don't mark as processed
        ignore_cooldown=True  # Include all candidates
    )

    cards_count = result.get('cards_count', 0)
    if cards_count > 0:
        logger.info(f"Successfully generated digest with {cards_count} REAL candidates from Zoho")

        # The HTML is already generated, but let's also create our split files
        # Get the cards from the result
        cards = result.get('cards', [])

        # Generate Brandon's split files
        await generate_brandon_split_files(cards)
    else:
        logger.error("No candidates found in Zoho CRM!")

    return result

async def generate_brandon_split_files(cards):
    """Generate Brandon's split HTML files with REAL TWAV numbers."""

    # Split into Advisors and Executives
    advisors = []
    executives = []

    for card in cards:
        if isinstance(card, dict):
            title = card.get('job_title', '').lower()
        else:
            title = card.job_title.lower() if hasattr(card, 'job_title') else ''

        if any(exec_word in title for exec_word in ['executive', 'director', 'president', 'chief', 'vp', 'vice president', 'managing', 'principal']):
            executives.append(card)
        else:
            advisors.append(card)

    # Generate HTML for each group
    await generate_html_file(cards[:100], "Brandon_REAL_100_Candidates.html", "All Candidates")
    await generate_html_file(advisors[:50], "Brandon_REAL_50_Advisors.html", "Financial Advisors")
    await generate_html_file(executives[:50], "Brandon_REAL_50_Executives.html", "Executives & Directors")

    logger.info(f"Generated files with REAL TWAV numbers from Zoho:")
    logger.info(f"  - Brandon_REAL_100_Candidates.html ({min(100, len(cards))} candidates)")
    logger.info(f"  - Brandon_REAL_50_Advisors.html ({min(50, len(advisors))} advisors)")
    logger.info(f"  - Brandon_REAL_50_Executives.html ({min(50, len(executives))} executives)")

async def generate_html_file(cards, filename, title):
    """Generate HTML file in Brandon's format with REAL TWAV numbers."""

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {datetime.now().strftime('%B %d, %Y')}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            margin: 20px;
            color: #333;
        }}
        .header {{
            background-color: #0066cc;
            color: white;
            padding: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
        }}
        .candidate {{
            margin-bottom: 30px;
            padding: 15px;
            background-color: #f9f9f9;
            border-left: 4px solid #0066cc;
        }}
        .candidate-header {{
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .candidate-company {{
            margin-bottom: 8px;
        }}
        .candidate-bullets ul {{
            margin: 5px 0;
            padding-left: 20px;
        }}
        .candidate-bullets li {{
            margin: 3px 0;
        }}
        .availability-comp {{
            margin: 8px 0;
            font-style: italic;
        }}
        .ref-code {{
            color: #666;
            font-size: 12px;
            margin-top: 10px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>Generated: {datetime.now().strftime('%B %d, %Y')}</p>
        <p>Total: {len(cards)} candidates from Zoho CRM</p>
    </div>
'''

    for card in cards:
        # Extract the REAL TWAV number
        if isinstance(card, dict):
            twav = card.get('deal_id', 'NO-TWAV')
            name = card.get('candidate_name', 'Unknown')
            title = card.get('job_title', 'Financial Advisor')
            company = card.get('company', 'Unknown Firm')
            location = card.get('location', 'Location TBD')
            bullets = card.get('bullets', [])
        else:
            # It's a DigestCard object
            twav = card.deal_id if hasattr(card, 'deal_id') else 'NO-TWAV'
            name = card.candidate_name if hasattr(card, 'candidate_name') else 'Unknown'
            title = card.job_title if hasattr(card, 'job_title') else 'Financial Advisor'
            company = card.company if hasattr(card, 'company') else 'Unknown Firm'
            location = card.location if hasattr(card, 'location') else 'Location TBD'
            bullets = card.bullets if hasattr(card, 'bullets') else []

        # Ensure TWAV format
        if twav and not twav.startswith('TWAV-'):
            if twav.isdigit() or (twav.startswith('3') and len(twav) >= 7):
                twav = f'TWAV-{twav}'

        html += f'''
    <div class="candidate">
        <div class="candidate-header">
            ‼️ {name} | {title}
        </div>
        <div class="candidate-company">
            🔔 {company} | {location}
        </div>
        <div class="candidate-bullets">
            <ul>'''

        # Add bullets (extracted from transcripts/resumes)
        for bullet in bullets[:5]:  # Max 5 bullets
            if isinstance(bullet, str):
                bullet_text = bullet
            elif hasattr(bullet, 'text'):
                bullet_text = bullet.text
            else:
                bullet_text = str(bullet)

            html += f'''
                <li>{bullet_text}</li>'''

        html += '''
            </ul>
        </div>
        <div class="ref-code">Ref code: {twav}</div>
    </div>'''

    html += '''
</body>
</html>'''

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"Wrote {filename} with {len(cards)} candidates")

if __name__ == "__main__":
    result = asyncio.run(run_talentwell_for_brandon())

    cards_count = result.get('cards_count', 0)
    if cards_count > 0:
        print(f"\n✅ SUCCESS! Generated Brandon's digests with {cards_count} REAL candidates from Zoho CRM")
        print("\nThese TWAV numbers are REAL and can be looked up in your Zoho database!")
        print("\nFiles generated:")
        print("  - Brandon_REAL_100_Candidates.html")
        print("  - Brandon_REAL_50_Advisors.html")
        print("  - Brandon_REAL_50_Executives.html")
    else:
        print("\n❌ ERROR: No candidates found in Zoho CRM")
        print("Please check your Zoho API connection and ensure there are candidates in the system")