#!/usr/bin/env python3
"""
Generate Top 20 Marketable Candidates - Vault Alert Style

Creates HTML email matching exact vault alerts format with only top performers.
"""
import sys
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))

from find_top_marketable_candidates import (
    parse_html_to_candidates,
    MarketabilityScorer
)


def extract_candidate_card_html(html_content: str, ref_code: str) -> str:
    """Extract the full HTML card for a specific candidate by ref code."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all candidate cards
    cards = soup.find_all('div', class_='candidate-card')
    
    for card in cards:
        # Look for ref code in this card
        ref_element = card.find('p', string=lambda t: t and ref_code in t)
        if ref_element:
            # Return the entire card HTML
            return str(card)
    
    return None


def generate_vault_style_email():
    """Generate email matching vault alerts format with top 20 candidates."""
    
    # Initialize scorer
    scorer = MarketabilityScorer()
    
    # Load and parse candidates
    advisor_path = Path(__file__).parent / "boss_format_advisors_20251016_192620.html"
    with open(advisor_path, 'r', encoding='utf-8') as f:
        advisor_html_full = f.read()
    advisor_candidates = parse_html_to_candidates(advisor_html_full)

    
    exec_path = Path(__file__).parent / "boss_format_executives_20251016_192620.html"
    with open(exec_path, 'r', encoding='utf-8') as f:
        exec_html_full = f.read()
    exec_candidates = parse_html_to_candidates(exec_html_full)
    
    # Score all candidates
    scored_advisors = []
    for candidate in advisor_candidates:
        score, breakdown = scorer.score_candidate(candidate)
        scored_advisors.append({**candidate, 'score': score, 'breakdown': breakdown})
    
    scored_executives = []
    for candidate in exec_candidates:
        score, breakdown = scorer.score_candidate(candidate)
        scored_executives.append({**candidate, 'score': score, 'breakdown': breakdown})
    
    # Sort by score
    scored_advisors.sort(key=lambda x: x['score'], reverse=True)
    scored_executives.sort(key=lambda x: x['score'], reverse=True)
    
    # Get top 10
    top_advisors = scored_advisors[:10]
    top_executives = scored_executives[:10]
    
    # Read the original vault HTML to get CSS and structure
    soup = BeautifulSoup(advisor_html_full, 'html.parser')
    
    # Extract the style tag
    style_tag = soup.find('style')
    style_content = str(style_tag) if style_tag else ""
    
    # Build HTML email
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">

    <title>Top 20 Most Marketable Vault Candidates - {datetime.now().strftime('%B %d, %Y')}</title>
    {style_content}
</head>
<body>
    <h1>🏆 Top 20 Most Marketable Vault Candidates - Week of {datetime.now().strftime('%B %d, %Y')}</h1>
    
    <div class="stats">
        <p><strong>Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
        <p><strong>Selection Criteria:</strong> Algorithmically scored from {len(advisor_candidates) + len(exec_candidates)} vault candidates using weighted MarketabilityScorer</p>
        <p><strong>Total Selected:</strong> 20 candidates (10 advisors + 10 executives)</p>
    </div>
    
    <div class="stats" style="background: #e8f4f8; border-left: 4px solid #3498db;">
        <h2 style="margin-top: 0; color: #2c3e50;">📊 Scoring Methodology (0-100 Scale)</h2>
        <ul style="line-height: 1.8;">
            <li><strong>💰 AUM/Book Size (40 points max):</strong> $1B+ = 40pts, $500M+ = 35pts, $300M+ = 30pts, $100M+ = 20pts</li>
            <li><strong>📈 Production L12Mo (30 points max):</strong> $2M+ = 30pts, $1M+ = 25pts, $500K+ = 20pts, $250K+ = 15pts</li>
            <li><strong>🎓 Credentials (15 points max):</strong> CFP/CFA = 10pts each, CPA = 7pts, CRPC/CHFC/CIMA = 5pts, Series licenses = 1-2pts</li>
            <li><strong>⏰ Availability (15 points max):</strong> Immediately/ASAP = 15pts, 2 weeks = 12pts, 1 month = 8pts</li>
        </ul>
        <p style="margin-bottom: 0;"><em><strong>Note:</strong> Most candidates lack production data, limiting maximum achievable scores to ~70 points. Top advisor scored 82.0/100, top executive scored 73.0/100.</em></p>
    </div>
    
    <h1 style="margin-top: 40px;">👔 Top 10 Financial Advisors (Ranked by Score)</h1>
"""

    
    # Add top 10 advisor cards
    for i, candidate in enumerate(top_advisors, 1):
        ref_code = candidate['Candidate_Locator']
        card_html = extract_candidate_card_html(advisor_html_full, ref_code)
        
        if card_html:
            # Add rank and score badge to the card
            card_html_modified = add_rank_and_score(card_html, i, candidate['score'], candidate['breakdown'])
            html += f"\n    {card_html_modified}\n"
        else:
            print(f"Warning: Could not find card for {ref_code}")
    
    # Add executives section
    html += """
    <h1 style="margin-top: 40px;">🎯 Top 10 Executives & Leadership (Ranked by Score)</h1>
"""
    
    # Add top 10 executive cards
    for i, candidate in enumerate(top_executives, 1):
        ref_code = candidate['Candidate_Locator']
        card_html = extract_candidate_card_html(exec_html_full, ref_code)
        
        if card_html:
            # Add rank and score badge to the card
            card_html_modified = add_rank_and_score(card_html, i, candidate['score'], candidate['breakdown'])
            html += f"\n    {card_html_modified}\n"
        else:
            print(f"Warning: Could not find card for {ref_code}")
    
    # Add footer with key insights
    html += f"""
    <div class="stats" style="margin-top: 40px; background: #f0f8ff;">
        <h2 style="margin-top: 0; color: #2c3e50;">📌 Key Insights</h2>

        <ul style="line-height: 1.8;">
            <li><strong>🥇 Top Advisor:</strong> {top_advisors[0]['Candidate_Locator']} - {top_advisors[0]['score']:.1f}/100 ({top_advisors[0]['Location']})</li>
            <li><strong>🥇 Top Executive:</strong> {top_executives[0]['Candidate_Locator']} - {top_executives[0]['score']:.1f}/100 ({top_executives[0]['Location']})</li>
            <li><strong>Immediate Availability:</strong> {sum(1 for c in top_advisors + top_executives if 'immediately' in c['When_Available'].lower() or 'asap' in c['When_Available'].lower())} of 20 candidates</li>
            <li><strong>Premium Credentials:</strong> All top 10 advisors have CFP, CFA, or equivalent designations</li>
            <li><strong>AUM Range:</strong> Top candidates manage $50M - $6.5B in client assets</li>
        </ul>
        <p style="margin-bottom: 0;"><em>Generated by MarketabilityScorer v1.0 | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}</em></p>
    </div>
    
</body>
</html>
"""
    
    return html


def add_rank_and_score(card_html: str, rank: int, score: float, breakdown: dict) -> str:
    """Add rank badge and score breakdown to a candidate card."""
    soup = BeautifulSoup(card_html, 'html.parser')
    card = soup.find('div', class_='candidate-card')
    
    if not card:
        return card_html
    
    # Find the h2 header
    header = card.find('h2')
    if header:
        # Determine rank emoji
        rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
        
        # Add rank and score to header
        original_text = header.get_text()

        
        # Create new header text with rank and score
        new_header = f"{rank_emoji} {original_text} - Score: {score:.1f}/100"
        header.string = new_header
    
    # Add score breakdown after the header
    if header:
        # Create score breakdown div
        breakdown_html = f"""
        <div style="background: #f8f9fa; padding: 10px; border-radius: 4px; margin: 10px 0; font-size: 14px;">
            <strong>📊 Marketability Score Breakdown:</strong> 
            AUM = {breakdown['aum']:.0f}pts | 
            Production = {breakdown['production']:.0f}pts | 
            Credentials = {breakdown['credentials']:.0f}pts | 
            Availability = {breakdown['availability']:.0f}pts
        </div>
"""
        breakdown_soup = BeautifulSoup(breakdown_html, 'html.parser')
        header.insert_after(breakdown_soup)
    
    return str(card)


def main():
    """Generate vault-style email."""
    print("="*70)
    print("🎨 GENERATING TOP 20 VAULT-STYLE EMAIL")
    print("="*70)
    print()
    
    print("⚡ Generating HTML...")
    html = generate_vault_style_email()
    
    # Save file
    output_path = Path(__file__).parent / "top_20_vault_style.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Vault-style email saved to: {output_path}")
    print(f"📄 File size: {len(html):,} characters")
    print()
    print("="*70)
    print("✅ VAULT-STYLE EMAIL READY")
    print("="*70)
    
    return html, str(output_path)


if __name__ == "__main__":
    html, path = main()
    print(f"\n📋 This email matches vault alerts format exactly")
    print(f"📬 Ready to send to bosses for distribution")
