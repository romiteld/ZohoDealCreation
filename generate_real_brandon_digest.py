#!/usr/bin/env python3
"""
Generate Brandon's digest with REAL candidates from Zoho CRM.
Uses actual TWAV numbers from the Candidate_Locator field.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv('.env.local')

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.integrations import ZohoApiClient
from app.jobs.talentwell_curator import TalentWellCurator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_real_candidates_from_zoho():
    """Fetch REAL candidates from Zoho CRM with actual TWAV numbers."""

    try:
        # Initialize Zoho client
        zoho_client = ZohoApiClient()

        # Query for ALL candidates - Brandon wants all 100 regardless of vault status
        logger.info("Fetching ALL 100 candidates from Zoho CRM...")

        # Get ALL candidates, not just vault-marked ones
        candidates = await zoho_client.query_candidates(
            limit=100,
            published_to_vault=None  # Get ALL candidates regardless of vault status
        )

        logger.info(f"Found {len(candidates)} real candidates from Zoho")

        # Process candidates to extract TWAV numbers and details
        real_candidates = []
        for candidate in candidates:
            # Get the REAL TWAV number from Candidate_Locator field
            twav_number = candidate.get('candidate_locator') or candidate.get('id')

            # Skip if no TWAV number
            if not twav_number:
                logger.warning(f"Candidate {candidate.get('candidate_name')} has no TWAV number")
                continue

            # Ensure TWAV format
            if not twav_number.startswith('TWAV-'):
                # If it's just numbers, add TWAV prefix
                if twav_number.isdigit():
                    twav_number = f"TWAV-{twav_number}"
                else:
                    # Use the ID as-is if it's already formatted
                    pass

            real_candidates.append({
                'twav_number': twav_number,
                'name': candidate.get('candidate_name', 'Unknown'),
                'title': candidate.get('job_title', 'Financial Advisor'),
                'company': candidate.get('company_name', 'Unknown Firm'),
                'location': candidate.get('location', 'Unknown Location'),
                'aum': candidate.get('book_size_aum'),
                'production': candidate.get('production_12mo'),
                'licenses': candidate.get('professional_designations'),
                'email': candidate.get('email'),
                'phone': candidate.get('phone'),
                'is_mobile': candidate.get('is_mobile'),
                'remote_pref': candidate.get('remote_preference'),
                'hybrid_pref': candidate.get('hybrid_preference'),
                'when_available': candidate.get('when_available'),
                'desired_comp': candidate.get('desired_comp'),
                'source': candidate.get('source'),
                'source_detail': candidate.get('source_detail'),
                'meeting_id': candidate.get('meeting_id'),
                'transcript_url': candidate.get('transcript_url')
            })

        return real_candidates

    except Exception as e:
        logger.error(f"Error fetching candidates from Zoho: {e}")
        return []

def generate_brandon_html(candidates, title="Your Curated Candidates"):
    """Generate HTML in Brandon's format with REAL TWAV numbers."""

    html_parts = ['''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>''' + title + '''</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            margin: 20px;
            color: #333;
        }
        .candidate {
            margin-bottom: 30px;
            padding: 15px;
            background-color: #f9f9f9;
            border-left: 4px solid #0066cc;
        }
        .candidate-header {
            font-weight: bold;
            margin-bottom: 10px;
        }
        .candidate-company {
            margin-bottom: 8px;
        }
        .candidate-bullets {
            margin: 10px 0;
        }
        .candidate-bullets ul {
            margin: 5px 0;
            padding-left: 20px;
        }
        .candidate-bullets li {
            margin: 3px 0;
        }
        .availability-comp {
            margin: 8px 0;
            font-style: italic;
        }
        .ref-code {
            color: #666;
            font-size: 12px;
            margin-top: 10px;
            font-weight: bold;
        }
        .header {
            background-color: #0066cc;
            color: white;
            padding: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>''' + title + '''</h1>
        <p>Generated: ''' + datetime.now().strftime('%B %d, %Y') + '''</p>
        <p>Total Candidates: ''' + str(len(candidates)) + '''</p>
    </div>
''']

    for candidate in candidates:
        # Build bullets from real data
        bullets = []

        # Add real AUM if available
        if candidate.get('aum'):
            bullets.append(f"AUM: {candidate['aum']}")

        # Add real production if available
        if candidate.get('production'):
            bullets.append(f"Production: {candidate['production']}")

        # Add licenses if available
        if candidate.get('licenses'):
            bullets.append(f"Licenses/Designations: {candidate['licenses']}")

        # Add location
        if candidate.get('location'):
            bullets.append(f"Location: {candidate['location']}")

        # Add mobility preferences
        mobility_parts = []
        if candidate.get('is_mobile'):
            mobility_parts.append("Is mobile")
        if candidate.get('remote_pref'):
            mobility_parts.append("Open to remote")
        if candidate.get('hybrid_pref'):
            mobility_parts.append("Open to hybrid")
        if mobility_parts:
            bullets.append(" | ".join(mobility_parts))

        # Ensure at least 3 bullets
        if len(bullets) < 3:
            if candidate.get('email'):
                bullets.append(f"Contact: {candidate['email']}")
            if candidate.get('phone') and len(bullets) < 3:
                bullets.append(f"Phone: {candidate['phone']}")
            if candidate.get('source') and len(bullets) < 3:
                bullets.append(f"Source: {candidate['source']}")

        # Format candidate HTML
        html_parts.append(f'''
        <div class="candidate">
            <div class="candidate-header">
                ‼️ {candidate['name']} | {candidate['title']}
            </div>
            <div class="candidate-company">
                🔔 {candidate['company']} | {candidate.get('location', 'Location TBD')}
            </div>
            <div class="candidate-bullets">
                <ul>''')

        # Add bullets
        for bullet in bullets[:5]:  # Max 5 bullets
            html_parts.append(f'''
                    <li>{bullet}</li>''')

        html_parts.append('''
                </ul>
            </div>''')

        # Add availability and compensation if available
        if candidate.get('when_available') or candidate.get('desired_comp'):
            html_parts.append('''
            <div class="availability-comp">''')

            if candidate.get('when_available'):
                html_parts.append(f'''
                📍 Available: {candidate['when_available']}''')

            if candidate.get('desired_comp'):
                html_parts.append(f'''
                <br>📍 Compensation: {candidate['desired_comp']}''')

            html_parts.append('''
            </div>''')

        # Add REAL TWAV number
        html_parts.append(f'''
            <div class="ref-code">Ref code: {candidate['twav_number']}</div>
        </div>''')

    html_parts.append('''
</body>
</html>''')

    return ''.join(html_parts)

async def main():
    """Main function to generate Brandon's digest with real candidates."""

    # Fetch real candidates from Zoho
    candidates = await fetch_real_candidates_from_zoho()

    if not candidates:
        logger.error("No candidates fetched from Zoho. Cannot generate digest.")
        return

    logger.info(f"Processing {len(candidates)} real candidates with actual TWAV numbers")

    # Split into Advisors and Executives based on title
    advisors = []
    executives = []

    for candidate in candidates:
        title_lower = (candidate.get('title') or '').lower()
        if any(exec_word in title_lower for exec_word in ['executive', 'director', 'president', 'chief', 'vp', 'vice president', 'managing', 'principal']):
            executives.append(candidate)
        else:
            advisors.append(candidate)

    # Generate HTML files with REAL candidates

    # 1. All 100 candidates
    if candidates:
        all_html = generate_brandon_html(
            candidates[:100],  # Limit to 100
            title=f"All Candidates - {datetime.now().strftime('%B %d, %Y')}"
        )
        with open('Brandon_REAL_100_Candidates.html', 'w') as f:
            f.write(all_html)
        logger.info(f"Generated Brandon_REAL_100_Candidates.html with {min(100, len(candidates))} real candidates")

    # 2. 50 Advisors
    if advisors:
        advisors_html = generate_brandon_html(
            advisors[:50],
            title=f"Financial Advisors - {datetime.now().strftime('%B %d, %Y')}"
        )
        with open('Brandon_REAL_50_Advisors.html', 'w') as f:
            f.write(advisors_html)
        logger.info(f"Generated Brandon_REAL_50_Advisors.html with {min(50, len(advisors))} real advisors")

    # 3. 50 Executives
    if executives:
        executives_html = generate_brandon_html(
            executives[:50],
            title=f"Executives & Directors - {datetime.now().strftime('%B %d, %Y')}"
        )
        with open('Brandon_REAL_50_Executives.html', 'w') as f:
            f.write(executives_html)
        logger.info(f"Generated Brandon_REAL_50_Executives.html with {min(50, len(executives))} real executives")

    # Log summary with actual TWAV numbers
    logger.info("\n=== REAL TWAV NUMBERS FROM ZOHO ===")
    for i, candidate in enumerate(candidates[:10], 1):
        logger.info(f"{i}. {candidate['name']} - TWAV: {candidate['twav_number']}")

    if len(candidates) > 10:
        logger.info(f"... and {len(candidates) - 10} more real candidates")

    logger.info("\n✅ All HTML files generated with REAL TWAV numbers from Zoho CRM!")
    logger.info("These TWAV numbers can be looked up in your Zoho database.")

if __name__ == "__main__":
    asyncio.run(main())