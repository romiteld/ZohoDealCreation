"""
Test digest rendering and content validation against CSV source.
Verifies that rendered digest cards match actual Zoho data.
"""
import csv
import os
import sys
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv('.env.local')

async def test_digest_generation():
    """Generate a test digest and validate content"""
    from app.jobs.talentwell_curator import TalentWellCurator
    from app.integrations import ZohoApiClient

    print("=" * 80)
    print("DIGEST RENDERING TEST")
    print("=" * 80)

    # Initialize curator
    curator = TalentWellCurator()
    zoho_client = ZohoApiClient()

    # Fetch recent vault candidates (last 7 days)
    to_date = datetime.now()
    from_date = to_date - timedelta(days=7)

    print(f"\n📅 Fetching vault candidates: {from_date.date()} → {to_date.date()}")

    candidates = await zoho_client.query_candidates(
        from_date=from_date,
        to_date=to_date,
        published_to_vault=True
    )

    print(f"✅ Fetched {len(candidates)} candidates from API")

    if not candidates:
        print("⚠️  No candidates found in date range")
        return

    # Load CSV for comparison
    csv_data = {}
    with open('Candidates_2025_10_07.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            candidate_name = row['Candidate Name'].strip()
            csv_data[candidate_name] = row

    print(f"📊 Loaded {len(csv_data)} candidates from CSV")

    # Compare first 5 candidates
    print(f"\n🔍 Validating API data against CSV source:")
    print("=" * 80)

    for i, candidate in enumerate(candidates[:5], 1):
        api_name = candidate.get('Full_Name', 'Unknown')
        api_title = candidate.get('Title', 'No title')
        api_location = candidate.get('Current_Location', 'No location')
        api_pub_date = candidate.get('Date_Published_to_Vault', 'No date')

        print(f"\n{i}. API Data:")
        print(f"   Name: {api_name}")
        print(f"   Title: {api_title}")
        print(f"   Location: {api_location}")
        print(f"   Published: {api_pub_date}")

        # Find matching CSV row
        if api_name in csv_data:
            csv_row = csv_data[api_name]
            csv_title = csv_row.get('Title', '').strip()
            csv_location = csv_row.get('Current Location', '').strip()
            csv_pub_date = csv_row.get('Date Published to Vault', '').strip()

            print(f"\n   CSV Data:")
            print(f"   Title: {csv_title}")
            print(f"   Location: {csv_location}")
            print(f"   Published: {csv_pub_date}")

            # Validate matches
            title_match = api_title == csv_title
            location_match = api_location == csv_location
            date_match = api_pub_date.startswith(csv_pub_date) if csv_pub_date else True

            print(f"\n   Validation:")
            print(f"   Title match: {'✅' if title_match else '❌'}")
            print(f"   Location match: {'✅' if location_match else '❌'}")
            print(f"   Date match: {'✅' if date_match else '❌'}")
        else:
            print(f"   ⚠️  NOT FOUND in CSV export")

    # Generate digest HTML
    print(f"\n" + "=" * 80)
    print("GENERATING DIGEST HTML")
    print("=" * 80)

    digest_html = await curator.run_weekly_digest(
        audience='advisors',
        days=7,
        max_cards=5  # Limit to 5 for testing
    )

    if digest_html:
        print(f"✅ Generated digest HTML ({len(digest_html)} chars)")

        # Check for CSS inlining
        if 'style="' in digest_html:
            print(f"✅ CSS appears to be inlined (contains style attributes)")
        else:
            print(f"⚠️  CSS may not be inlined (no style attributes found)")

        # Save to file for inspection
        output_path = '/tmp/test_digest.html'
        with open(output_path, 'w') as f:
            f.write(digest_html)
        print(f"📄 Saved digest to: {output_path}")

        # Extract candidate names from HTML
        import re
        # Look for candidate names in the HTML (they should be in headers or bold text)
        names_in_html = set()
        for candidate in candidates[:5]:
            name = candidate.get('Full_Name', '')
            if name in digest_html:
                names_in_html.add(name)

        print(f"\n🔍 Content Validation:")
        print(f"   Candidates in digest: {len(names_in_html)}/5")
        if len(names_in_html) >= 3:
            print(f"   ✅ Majority of candidates rendered")
        else:
            print(f"   ⚠️  Missing candidate content in HTML")

    else:
        print(f"❌ Digest generation failed")

if __name__ == '__main__':
    asyncio.run(test_digest_generation())

    print(f"\n" + "=" * 80)
    print("✅ DIGEST RENDERING TEST COMPLETE")
    print("=" * 80)
