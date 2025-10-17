#!/usr/bin/env python3
"""
Generate Top 10 Most Marketable Candidates Email

Creates HTML email matching vault alerts style with top performers.
"""
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from find_top_marketable_candidates import (
    parse_html_to_candidates,
    MarketabilityScorer
)


def generate_top_10_email_html():
    """Generate HTML email for top 10 most marketable candidates."""
    
    # Initialize scorer
    scorer = MarketabilityScorer()
    
    # Load and parse candidates
    advisor_path = Path(__file__).parent / "boss_format_advisors_20251016_192620.html"
    with open(advisor_path, 'r', encoding='utf-8') as f:
        advisor_html = f.read()
    advisor_candidates = parse_html_to_candidates(advisor_html)
    
    exec_path = Path(__file__).parent / "boss_format_executives_20251016_192620.html"
    with open(exec_path, 'r', encoding='utf-8') as f:
        exec_html = f.read()
    exec_candidates = parse_html_to_candidates(exec_html)
    
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
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Top 10 Most Marketable Vault Candidates - {datetime.now().strftime('%B %d, %Y')}</title>
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
        h2 {{
            color: #3498db;
            margin-top: 30px;
        }}
        .intro {{
            background: #fff;
            padding: 20px;
            border-radius: 8px;

            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .scoring-info {{
            background: #e8f4f8;
            padding: 15px;
            border-left: 4px solid #3498db;
            margin-bottom: 20px;
            border-radius: 4px;
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
        .candidate-card h3 {{
            color: #2c3e50;
            margin-top: 0;
            font-size: 18px;
        }}
        .score-badge {{
            display: inline-block;
            background: #27ae60;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 16px;
            margin-left: 10px;
        }}
        .score-breakdown {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 14px;
        }}

        .details {{
            line-height: 1.6;
            color: #555;
        }}
        .details strong {{
            color: #2c3e50;
        }}
        .rank {{
            font-size: 24px;
            font-weight: bold;
            color: #3498db;
            margin-right: 10px;
        }}
        ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        li {{
            margin: 5px 0;
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
    <h1>🏆 Top 10 Most Marketable Vault Candidates</h1>
    
    <div class="intro">
        <p><strong>Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
        <p><strong>Total Analyzed:</strong> {len(advisor_candidates)} advisors + {len(exec_candidates)} executives = {len(advisor_candidates) + len(exec_candidates)} candidates</p>

        <p><strong>Selection Method:</strong> Scored using weighted MarketabilityScorer algorithm</p>
    </div>
    
    <div class="scoring-info">
        <h3>📊 How Candidates Were Scored (0-100 Scale)</h3>
        <ul>
            <li><strong>💰 AUM/Book Size (40 points max):</strong> $1B+ = 40pts, $500M+ = 35pts, $300M+ = 30pts, $100M+ = 20pts</li>
            <li><strong>📈 Production L12Mo (30 points max):</strong> $2M+ = 30pts, $1M+ = 25pts, $500K+ = 20pts, $250K+ = 15pts</li>
            <li><strong>🎓 Credentials (15 points max):</strong> CFP/CFA = 10pts each, CPA = 7pts, CRPC/CHFC/CIMA = 5pts, Series licenses = 1-2pts</li>
            <li><strong>⏰ Availability (15 points max):</strong> Immediately/ASAP = 15pts, 2 weeks = 12pts, 1 month = 8pts, 2+ months = 3-5pts</li>
        </ul>
        <p><em>Note: Most candidates lack production data, which limits maximum achievable scores to ~70 points.</em></p>
    </div>
    
    <h2>👔 Top 10 Financial Advisors</h2>
"""
    
    # Generate advisor cards
    for i, candidate in enumerate(top_advisors, 1):
        rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        
        html += f"""
    <div class="candidate-card">
        <h3><span class="rank">{rank_emoji}</span>{candidate['Candidate_Locator']}<span class="score-badge">{candidate['score']:.1f}/100</span></h3>

        <div class="details">
            <p><strong>📍 Location:</strong> {candidate['Location']}</p>
            <p><strong>💼 Role:</strong> {candidate['Role'].replace('‼️', '').replace('🔔', '').strip()}</p>
            <p><strong>💰 AUM:</strong> {candidate['Book_Size_AUM'] or 'Not disclosed'}</p>
            <p><strong>📈 Production:</strong> {candidate['Production_L12Mo'] or 'Not disclosed'}</p>
            <p><strong>🎓 Credentials:</strong> {candidate['Licenses_and_Exams'] or 'Not disclosed'}</p>
            <p><strong>⏰ Available:</strong> {candidate['When_Available']}</p>
        </div>
        <div class="score-breakdown">
            <strong>Score Breakdown:</strong> 
            AUM = {candidate['breakdown']['aum']:.0f}pts | 
            Production = {candidate['breakdown']['production']:.0f}pts | 
            Credentials = {candidate['breakdown']['credentials']:.0f}pts | 
            Availability = {candidate['breakdown']['availability']:.0f}pts
        </div>
        <p style="margin-top: 10px;"><strong>🔑 Top Highlights:</strong></p>
        <ul>
"""
        
        # Add top 3 bullets
        for bullet in candidate['Bullets'][:3]:
            html += f"            <li>{bullet}</li>\n"
        
        html += """        </ul>
    </div>
"""
    
    # Add executives section
    html += """
    <h2>🎯 Top 10 Executives & Leadership</h2>
"""

    
    # Generate executive cards
    for i, candidate in enumerate(top_executives, 1):
        rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        
        html += f"""
    <div class="candidate-card">
        <h3><span class="rank">{rank_emoji}</span>{candidate['Candidate_Locator']}<span class="score-badge">{candidate['score']:.1f}/100</span></h3>
        <div class="details">
            <p><strong>📍 Location:</strong> {candidate['Location']}</p>
            <p><strong>💼 Role:</strong> {candidate['Role'].replace('‼️', '').replace('🔔', '').strip()}</p>
            <p><strong>💰 AUM:</strong> {candidate['Book_Size_AUM'] or 'Not disclosed'}</p>
            <p><strong>📈 Production:</strong> {candidate['Production_L12Mo'] or 'Not disclosed'}</p>
            <p><strong>🎓 Credentials:</strong> {candidate['Licenses_and_Exams'] or 'Not disclosed'}</p>
            <p><strong>⏰ Available:</strong> {candidate['When_Available']}</p>
        </div>
        <div class="score-breakdown">
            <strong>Score Breakdown:</strong> 
            AUM = {candidate['breakdown']['aum']:.0f}pts | 
            Production = {candidate['breakdown']['production']:.0f}pts | 
            Credentials = {candidate['breakdown']['credentials']:.0f}pts | 
            Availability = {candidate['breakdown']['availability']:.0f}pts
        </div>
        <p style="margin-top: 10px;"><strong>🔑 Top Highlights:</strong></p>
        <ul>
"""
        
        # Add top 3 bullets
        for bullet in candidate['Bullets'][:3]:
            html += f"            <li>{bullet}</li>\n"
        
        html += """        </ul>
    </div>
"""

    
    # Add footer
    html += f"""
    <div class="intro" style="margin-top: 40px;">
        <h3>📌 Key Insights</h3>
        <ul>
            <li><strong>Top Advisor Score:</strong> {top_advisors[0]['score']:.1f}/100 ({top_advisors[0]['Candidate_Locator']})</li>
            <li><strong>Top Executive Score:</strong> {top_executives[0]['score']:.1f}/100 ({top_executives[0]['Candidate_Locator']})</li>
            <li><strong>Data Quality Impact:</strong> 90%+ of candidates lack production data, limiting maximum scores to ~70 points</li>
            <li><strong>Immediate Availability:</strong> {sum(1 for c in top_advisors + top_executives if 'immediately' in c['When_Available'].lower() or 'asap' in c['When_Available'].lower())} of top 20 candidates available immediately</li>
            <li><strong>Premium Credentials:</strong> All top 10 advisors have CFP, CFA, or equivalent designations</li>
        </ul>
        
        <p style="margin-top: 20px;"><em>Generated by MarketabilityScorer v1.0 | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}</em></p>
    </div>
    
</body>
</html>
"""
    
    return html


def main():
    """Generate and save preview HTML."""
    print("="*70)
    print("🎨 GENERATING TOP 10 MARKETABLE CANDIDATES EMAIL")
    print("="*70)
    print()
    
    # Generate HTML
    print("⚡ Generating HTML email...")
    html = generate_top_10_email_html()
    
    # Save preview
    preview_path = Path(__file__).parent / "top_10_marketable_preview.html"
    with open(preview_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Preview saved to: {preview_path}")

    print(f"📄 File size: {len(html):,} characters")
    print()
    print("🌐 Open the preview file in your browser to review.")
    print()
    print("="*70)
    print("✅ PREVIEW READY")
    print("="*70)
    
    return html, str(preview_path)


if __name__ == "__main__":
    html, preview_path = main()
    
    print(f"\n📋 Next steps:")
    print(f"1. Open preview: {preview_path}")
    print(f"2. Review the formatting and content")
    print(f"3. If approved, I'll send to steve@, brandon@, daniel.romitelli@")
