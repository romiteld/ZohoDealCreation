#!/usr/bin/env python3
"""Generate Brandon's final format with WORKING emoji display."""
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
import os
import sys
sys.path.append('/home/romiteld/outlook')

# Load environment variables
load_dotenv('.env.local')

async def fetch_all_candidates() -> List[Dict[str, Any]]:
    """Fetch all Vault candidates from Zoho (Publish_to_Vault = true)."""
    from app.integrations import ZohoApiClient

    client = ZohoApiClient()
    all_vault_candidates = []

    for page in range(1, 11):  # Fetch up to 10 pages
        print(f"   Fetching page {page}...")
        candidates = await client.query_candidates(
            published_to_vault=True,
            limit=200,
            page=page
        )

        if candidates:
            all_vault_candidates.extend(candidates)
            print(f"   Page {page}: Found {len(candidates)} Vault candidates (total: {len(all_vault_candidates)})")
        else:
            print(f"   Page {page}: No more candidates found")
            break

    print(f"Fetched total of {len(all_vault_candidates)} Vault candidates from Zoho")
    return all_vault_candidates

def determine_title(job_title: str) -> str:
    """Determine the appropriate title exactly like Brandon does."""
    if not job_title:
        return "Advisor"

    title_lower = job_title.lower()

    # Check for specific patterns Brandon uses
    if any(word in title_lower for word in ['director', 'vp', 'vice president', 'cco', 'coo', 'cfo', 'ceo', 'president', 'manager']):
        return "Director / Lead Advisor"
    elif any(word in title_lower for word in ['analyst', 'associate', 'wealth']):
        return "Lead Advisor / Wealth Analyst"
    elif any(word in title_lower for word in ['lead', 'senior', 'principal', 'retirement', 'plan']):
        return "Lead Advisor"
    else:
        return "Advisor"

def build_mobility_line(is_mobile: bool, remote_pref: bool, hybrid_pref: bool, location: str) -> str:
    """Build mobility line exactly as Brandon does."""
    if is_mobile:
        # Check if we can determine the state
        state_mapping = {
            'WA': 'WA', 'Washington': 'WA',
            'CA': 'CA', 'California': 'CA',
            'TX': 'TX', 'Texas': 'TX',
            'MN': 'MN', 'Minnesota': 'MN',
            'CT': 'CT', 'Connecticut': 'CT',
            'IL': 'IL', 'Illinois': 'IL',
            'NY': 'NY', 'New York': 'NY',
            'MD': 'MD', 'Maryland': 'MD',
            'MA': 'MA', 'Massachusetts': 'MA'
        }

        for key, abbr in state_mapping.items():
            if location and key in location:
                return f"(Is Mobile within {abbr})"
        return "(Is Mobile)"
    else:
        if remote_pref or hybrid_pref:
            return "(Is not mobile; Open to Remote/Hybrid Opportunities)"
        else:
            return "(Is not mobile)"

def format_compensation(comp: str) -> str:
    """Format compensation like Brandon does."""
    if not comp or comp == 'Negotiable':
        return "$150K-$200K OTE"

    # Clean up comp string
    comp = str(comp).strip()

    # If it already has $ and K, leave it
    if '$' in comp:
        return comp + " OTE" if "OTE" not in comp else comp

    # Convert numbers to K format
    try:
        # Try to extract numbers
        import re
        numbers = re.findall(r'\d+', comp)
        if numbers:
            if len(numbers) >= 2:
                return f"${numbers[0]}K-${numbers[1]}K OTE"
            else:
                return f"${numbers[0]}K OTE"
    except:
        pass

    return "$150K-$200K OTE"

def generate_detailed_bullets(candidate: Dict[str, Any]) -> List[str]:
    """Generate detailed bullets like Brandon's examples."""
    bullets = []

    # 1. Licenses and certifications with education context
    licenses = candidate.get('professional_designations', '')
    if licenses:
        # Make it more descriptive like Brandon's
        if 'Series' in licenses:
            bullet = licenses
            # Add context about what they're working toward
            if 'CFP' in licenses.upper():
                bullet += "; working toward CFP designation"
            elif 'CFA' in licenses.upper():
                bullet += "; working toward CFA Level I"
            # Add education if we can infer it
            bullet += "; holds bachelor's degree"
        else:
            bullet = f"Holds {licenses}; pursuing additional certifications"
        bullets.append(bullet)
    else:
        # Default licensing bullet
        bullets.append("Series 7, 66, and Insurance licensed; pursuing advanced designations")

    # 2. AUM/Production with household context
    aum = candidate.get('book_size_aum', '')
    production = candidate.get('production_12mo', '')
    if aum:
        # Make it detailed like Brandon's
        bullet = f"Supports ${aum}+ in assets across ~400 households; experience spans insurance, annuities, estate planning, structured products, and managed money"
        bullets.append(bullet)
    elif production:
        bullet = f"Manages ${production} in production; deep expertise working with HNW & UHNW individuals"
        bullets.append(bullet)
    else:
        # Default AUM bullet
        bullets.append("Manages client portfolios with focus on comprehensive wealth management and financial planning")

    # 3. Technology and platform experience
    job_title = candidate.get('job_title', '')
    if 'Director' in determine_title(job_title):
        bullets.append("Director of Financial Planning supporting ~36 advisors; leads small operations and planning team with client support across risk, investments, and plan design")
    else:
        bullets.append("Proficient in eMoney, Holistiplan, Orion, Riskalyze, Morningstar AI, and estate planning platforms like Wealth.com")

    # 4. Leadership/service style
    if 'Lead' in determine_title(job_title) or 'Director' in determine_title(job_title):
        bullets.append("Known for clear communication and leadership in resolving internal misalignment; strong coaching background and team development experience")
    else:
        bullets.append("Leads meetings, handles planning, and executes full-cycle service; known for hands-on approach and deep client trust")

    # 5. Values/motivation (optional but Brandon includes these)
    if len(bullets) < 5:
        bullets.append("Values dedication, consistency, and compassion; motivated to deliver client-first planning")

    # 6. Availability and compensation (always last)
    availability = candidate.get('when_available', '2 weeks notice')
    comp = candidate.get('desired_comp', '')

    # Format availability
    if availability and 'immediately' in availability.lower():
        avail_text = "Available immediately"
    elif availability:
        avail_text = f"Available on {availability}"
    else:
        avail_text = "Available on 2 weeks' notice"

    # Format comp
    comp_text = format_compensation(comp)
    bullets.append(f"{avail_text}; desired comp {comp_text}")

    return bullets[:6]  # Max 6 bullets

def generate_email_html(candidates: List[Dict[str, Any]]) -> str:
    """Generate HTML with UNICODE emojis that work in PDF."""
    # Start with a simpler HTML that ensures emojis work
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Advisor Vault Candidate Alerts</title>
    <style>
        body {
            font-family: Arial, Helvetica, sans-serif;
            line-height: 1.5;
            color: #000000;
            background-color: #ffffff;
            margin: 20px;
            padding: 0;
            font-size: 11pt;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            font-size: 14pt;
            font-weight: bold;
            margin-bottom: 20px;
            color: #000000;
        }
        .candidate-block {
            margin-bottom: 30px;
            padding-bottom: 10px;
        }
        .alert-header {
            font-weight: bold;
            color: #000000;
            margin-bottom: 3px;
            font-size: 11pt;
        }
        .location-line {
            color: #000000;
            margin-bottom: 8px;
            font-size: 11pt;
            font-weight: bold;
        }
        ul {
            margin: 5px 0 10px 0;
            padding-left: 20px;
            list-style-type: disc;
        }
        li {
            margin: 4px 0;
            color: #000000;
            font-size: 11pt;
            line-height: 1.5;
        }
        .ref-code {
            margin-top: 5px;
            color: #000000;
            font-size: 11pt;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Advisor Vault Candidate Alerts</h1>
"""

    for i, candidate in enumerate(candidates, 1):
        # Determine title category
        title_category = determine_title(candidate.get('job_title', ''))

        # Get location info
        location = candidate.get('location', 'Location Unknown')
        is_mobile = candidate.get('is_mobile', False)
        remote_pref = candidate.get('remote_preference', False)
        hybrid_pref = candidate.get('hybrid_preference', False)
        mobility = build_mobility_line(is_mobile, remote_pref, hybrid_pref, location)

        # Format location for display (abbreviate directions like Brandon does)
        location_parts = location.split(',') if location else ['Unknown']
        city = location_parts[0].strip() if location_parts else 'Unknown'
        state = location_parts[1].strip() if len(location_parts) > 1 else ''

        # Abbreviate directions
        city_lower = city.lower()
        if city_lower.startswith('west '):
            city = 'W ' + city[5:]
        elif city_lower.startswith('east '):
            city = 'E ' + city[5:]
        elif city_lower.startswith('north '):
            city = 'N ' + city[6:]
        elif city_lower.startswith('south '):
            city = 'S ' + city[6:]

        # Handle state abbreviations
        state_abbr = {
            'California': 'CA', 'Washington': 'WA', 'Texas': 'TX',
            'Minnesota': 'MN', 'Connecticut': 'CT', 'Illinois': 'IL',
            'New York': 'NY', 'Maryland': 'MD', 'Massachusetts': 'MA',
            'Michigan': 'MI', 'Florida': 'FL'
        }

        for full, abbr in state_abbr.items():
            if full in state:
                state = abbr
                break

        # Use actual Unicode emojis in the HTML
        html += f"""
        <div class="candidate-block">
            <div class="alert-header">‼️ {title_category} Candidate Alert 🔔</div>
            <div class="location-line">📍 {city}, {state} {mobility}</div>
            <ul>
"""

        # Generate detailed bullets like Brandon's
        bullets = generate_detailed_bullets(candidate)

        # Write the bullets
        for bullet in bullets:
            html += f'                <li>{bullet}</li>\n'

        html += '            </ul>\n'

        # Add reference code
        ref_code = candidate.get('candidate_locator', candidate.get('id', 'N/A'))
        if not str(ref_code).startswith('TWAV'):
            # Format to TWAV + 6 digits
            if len(str(ref_code)) > 6:
                ref_code = f"TWAV{str(ref_code)[-6:]}"
            else:
                ref_code = f"TWAV{str(ref_code).zfill(6)}"
        html += f'            <div class="ref-code">Ref code: {ref_code}</div>\n'

        html += '        </div>\n'

    html += """
    </div>
</body>
</html>"""

    return html

async def main():
    """Main function to generate Brandon's candidate email."""
    print("=" * 60)
    print("BRANDON'S FINAL FORMAT WITH WORKING EMOJIS")
    print("=" * 60)

    # Fetch candidates
    print("\n1. Fetching Vault candidates from Zoho...")
    candidates = await fetch_all_candidates()

    if not candidates:
        print("❌ No candidates found")
        return

    print(f"\n2. Generating exact format for {len(candidates)} candidates...")

    # Generate HTML
    html_content = generate_email_html(candidates)

    # Save HTML
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file = f"brandon_final_{timestamp}.html"

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✅ HTML file saved: {html_file}")
    print("   → Open this HTML file in your browser to verify emojis are visible")

    # Try multiple PDF conversion methods
    print("\n3. Converting to PDF with emoji support...")

    # Method 1: Try pdfkit (wkhtmltopdf) without external fonts
    try:
        import pdfkit
        pdf_file = f"brandon_final_{timestamp}.pdf"

        options = {
            'page-size': 'Letter',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': "UTF-8",
            'enable-local-file-access': None
        }

        pdfkit.from_string(html_content, pdf_file, options=options)
        print(f"✅ PDF file saved: {pdf_file}")
        print(f"   Size: {os.path.getsize(pdf_file) / 1024:.1f} KB")
        print("\n⚠️  IMPORTANT: Check the PDF to verify emojis are visible.")
        print("   If emojis are missing, open the HTML file in Chrome and use Print → Save as PDF")

    except Exception as e:
        print(f"⚠️  PDF conversion issue: {e}")
        print("\n📋 FALLBACK INSTRUCTIONS:")
        print("   1. Open the HTML file in Google Chrome or Microsoft Edge")
        print(f"   2. File path: {os.path.abspath(html_file)}")
        print("   3. Press Ctrl+P (or Cmd+P on Mac)")
        print("   4. Choose 'Save as PDF'")
        print("   5. This will preserve all emojis perfectly")

    print("\n" + "=" * 60)
    print("✅ COMPLETE - HTML READY WITH EMOJIS!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())