#!/usr/bin/env python3
"""
Find Top 10 Most Marketable Candidates

Parses cached vault alert HTML files and scores candidates using
the MarketabilityScorer to identify top advisors and executives.
"""
import re
import sys
from pathlib import Path
from typing import List, Dict, Any
from bs4 import BeautifulSoup

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.jobs.marketability_scorer import MarketabilityScorer


def parse_html_to_candidates(html_content: str) -> List[Dict[str, Any]]:
    """Parse HTML vault alerts to extract candidate data."""
    soup = BeautifulSoup(html_content, 'html.parser')
    candidates = []
    
    cards = soup.find_all('div', class_='candidate-card')
    
    for card in cards:
        try:
            # Extract ref code
            ref_element = card.find('p', string=re.compile(r'Ref code:'))
            ref_code = 'Unknown'
            if ref_element:
                match = re.search(r'Ref code:\s*(TWAV\d+)', ref_element.text)
                if match:
                    ref_code = match.group(1)
            
            # Extract location
            location_element = card.find('strong', string=re.compile(r'📍 Location:'))
            location = 'Unknown'
            if location_element:
                location_text = location_element.parent.text
                match = re.search(r'📍 Location:\s*([^(]+)', location_text)
                if match:
                    location = match.group(1).strip()
            
            # Extract header (role/position info)
            header = card.find('h2')
            role = header.text if header else 'Unknown'
            
            # Extract bullets - combine all to search for data
            bullets = []
            for li in card.find_all('li'):
                bullets.append(li.text.strip())
            
            combined_text = ' '.join(bullets)
            
            # Extract AUM/Book Size
            aum = extract_aum(combined_text)
            
            # Extract Production
            production = extract_production(combined_text)
            
            # Extract Licenses
            licenses = extract_licenses(combined_text)

            
            # Extract Availability
            availability = extract_availability(combined_text)
            
            candidate = {
                'Candidate_Locator': ref_code,
                'Location': location,
                'Role': role,
                'Book_Size_AUM': aum,
                'Production_L12Mo': production,
                'Licenses_and_Exams': licenses,
                'When_Available': availability,
                'Bullets': bullets[:3]  # Top 3 bullets
            }
            
            candidates.append(candidate)
            
        except Exception as e:
            print(f"Error parsing card: {e}")
            continue
    
    return candidates


def extract_aum(text: str) -> str:
    """Extract AUM/Book Size from text."""
    # Patterns: "$300M", "$1.5B", "$100M+ AUM"
    patterns = [
        r'\$[\d.]+[BMK]\+?\s*(?:AUM|book|assets|in client assets)',
        r'(?:Manages?|Managing)\s+\$[\d.]+[BMK]\+?',
        r'\$[\d.]+[BMK]\+?\s+in\s+(?:AUM|assets)',
    ]

    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Extract just the dollar amount
            dollar_match = re.search(r'\$[\d.]+[BMK]\+?', match.group(0))
            if dollar_match:
                return dollar_match.group(0)
    
    return ''


def extract_production(text: str) -> str:
    """Extract Production L12Mo from text."""
    # Patterns: "$1.2M annually", "$500K in production"
    patterns = [
        r'\$[\d.]+[MK]\+?\s+(?:annually|in production|quarterly)',
        r'Generated\s+\$[\d.]+[MK]\+?',
        r'\$[\d.]+[MK]\+?\s+(?:production|revenue)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            dollar_match = re.search(r'\$[\d.]+[MK]\+?', match.group(0))
            if dollar_match:
                return dollar_match.group(0)
    
    return ''



def extract_licenses(text: str) -> str:
    """Extract licenses and credentials from text."""
    # Look for common designations and licenses
    credentials = []
    
    # Premium designations
    premium = ['CFP', 'CFA', 'CPA', 'CRPC', 'RICP', 'CHFC', 'CIMA', 'CPWA', 'CTFA']
    for cred in premium:
        if re.search(rf'\b{cred}\b', text, re.IGNORECASE):
            credentials.append(cred)
    
    # Series licenses
    series = re.findall(r'Series\s+\d+', text, re.IGNORECASE)
    credentials.extend(series)
    
    return ', '.join(credentials) if credentials else ''


def extract_availability(text: str) -> str:
    """Extract availability from text."""
    # Look for "Available:" pattern
    match = re.search(r'Available[:\s]+([^;•]+)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Look for common patterns
    if re.search(r'\bimmediately\b|\basap\b', text, re.IGNORECASE):
        return 'Immediately'
    if re.search(r'\d+\s+weeks?\s+notice', text, re.IGNORECASE):
        match = re.search(r'(\d+\s+weeks?\s+notice)', text, re.IGNORECASE)
        return match.group(1) if match else '2 weeks notice'
    
    return 'TBD'



def main():
    """Main execution."""
    print("="*70)
    print("🎯 FINDING TOP 10 MOST MARKETABLE CANDIDATES")
    print("="*70)
    print()
    
    # Initialize scorer
    scorer = MarketabilityScorer()
    
    # Load advisor HTML
    print("📂 Loading advisor HTML...")
    advisor_path = Path(__file__).parent / "boss_format_advisors_20251016_192620.html"
    with open(advisor_path, 'r', encoding='utf-8') as f:
        advisor_html = f.read()
    
    advisor_candidates = parse_html_to_candidates(advisor_html)
    print(f"   ✅ Parsed {len(advisor_candidates)} advisor candidates")
    
    # Load executive HTML
    print("\n📂 Loading executive HTML...")
    exec_path = Path(__file__).parent / "boss_format_executives_20251016_192620.html"
    with open(exec_path, 'r', encoding='utf-8') as f:
        exec_html = f.read()
    
    exec_candidates = parse_html_to_candidates(exec_html)
    print(f"   ✅ Parsed {len(exec_candidates)} executive candidates")
    
    # Score advisors
    print("\n⚡ Scoring advisor candidates...")
    scored_advisors = []
    for candidate in advisor_candidates:
        score, breakdown = scorer.score_candidate(candidate)
        scored_advisors.append({
            **candidate,
            'score': score,
            'breakdown': breakdown
        })

    
    # Score executives
    print("⚡ Scoring executive candidates...")
    scored_executives = []
    for candidate in exec_candidates:
        score, breakdown = scorer.score_candidate(candidate)
        scored_executives.append({
            **candidate,
            'score': score,
            'breakdown': breakdown
        })
    
    # Sort by score
    scored_advisors.sort(key=lambda x: x['score'], reverse=True)
    scored_executives.sort(key=lambda x: x['score'], reverse=True)
    
    # Print Top 10 Advisors
    print("\n" + "="*70)
    print("🏆 TOP 10 MOST MARKETABLE ADVISORS")
    print("="*70)
    print()
    
    for i, candidate in enumerate(scored_advisors[:10], 1):
        print(f"\n{i}. {candidate['Candidate_Locator']} - Score: {candidate['score']:.1f}/100")
        print(f"   📍 {candidate['Location']}")
        print(f"   💼 {candidate['Role']}")
        print(f"   💰 AUM: {candidate['Book_Size_AUM'] or 'Not disclosed'}")
        print(f"   📈 Production: {candidate['Production_L12Mo'] or 'Not disclosed'}")
        print(f"   🎓 {candidate['Licenses_and_Exams'] or 'No credentials listed'}")
        print(f"   ⏰ Available: {candidate['When_Available']}")
        print(f"   📊 Breakdown: AUM={candidate['breakdown']['aum']:.0f}, "
              f"Prod={candidate['breakdown']['production']:.0f}, "
              f"Creds={candidate['breakdown']['credentials']:.0f}, "
              f"Avail={candidate['breakdown']['availability']:.0f}")

    
    # Print Top 10 Executives
    print("\n" + "="*70)
    print("🏆 TOP 10 MOST MARKETABLE EXECUTIVES")
    print("="*70)
    print()
    
    for i, candidate in enumerate(scored_executives[:10], 1):
        print(f"\n{i}. {candidate['Candidate_Locator']} - Score: {candidate['score']:.1f}/100")
        print(f"   📍 {candidate['Location']}")
        print(f"   💼 {candidate['Role']}")
        print(f"   💰 AUM: {candidate['Book_Size_AUM'] or 'Not disclosed'}")
        print(f"   📈 Production: {candidate['Production_L12Mo'] or 'Not disclosed'}")
        print(f"   🎓 {candidate['Licenses_and_Exams'] or 'No credentials listed'}")
        print(f"   ⏰ Available: {candidate['When_Available']}")
        print(f"   📊 Breakdown: AUM={candidate['breakdown']['aum']:.0f}, "
              f"Prod={candidate['breakdown']['production']:.0f}, "
              f"Creds={candidate['breakdown']['credentials']:.0f}, "
              f"Avail={candidate['breakdown']['availability']:.0f}")
    
    print("\n" + "="*70)
    print("✅ ANALYSIS COMPLETE")
    print("="*70)
    print(f"\n📊 Total candidates analyzed: {len(advisor_candidates) + len(exec_candidates)}")
    print(f"   • Advisors: {len(advisor_candidates)}")
    print(f"   • Executives: {len(exec_candidates)}")


if __name__ == "__main__":
    main()
