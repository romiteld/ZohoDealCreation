#!/usr/bin/env python3
"""
Test AI bullet generator on reference candidates from screenshot.
"""

import csv
import sys
import os
from dotenv import load_dotenv

# Load environment
load_dotenv('.env.local')

# Import AI generator
from ai_bullet_generator import generate_rich_bullets_with_ai

# Reference candidates from screenshot
REFERENCE_CANDIDATES = [
    'TWAV117805',  # Lead Advisor (Milwaukee, WI)
    'TWAV117795',  # COO / Lead Advisor (Des Moines, IA)
    'TWAV117812',  # COO / Lead Advisor (Houston, TX)
]

def main():
    print("=" * 80)
    print("Testing AI Bullet Generator on Reference Candidates")
    print("=" * 80)
    print()

    # Load candidates from CSV
    candidates = {}
    with open('Candidates_2025_10_09.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ref = row.get('Reference_Code', '').strip()
            if ref in REFERENCE_CANDIDATES:
                candidates[ref] = {
                    'name': row.get('Full_Name', ''),
                    'title': row.get('Title', ''),
                    'city': row.get('City', ''),
                    'state': row.get('State', ''),
                    'interviewer_notes': row.get('Interviewer Notes', ''),
                    'top_performance': row.get('Top Performance Result', ''),
                    'headline': row.get('Headline', ''),
                    'background_notes': row.get('Background Notes', ''),
                    'licenses': row.get('Licenses', ''),
                    'availability': row.get('Availability', ''),
                    'compensation': row.get('Desired Comp', ''),
                    'is_mobile': row.get('Mobile', '').lower() == 'yes'
                }

    # Test each candidate
    for ref in REFERENCE_CANDIDATES:
        if ref not in candidates:
            print(f"⚠️  {ref} not found in CSV")
            continue

        candidate = candidates[ref]
        print(f"{'=' * 80}")
        print(f"‼️ {candidate['title']} Candidate Alert 🔔")
        print(f"📍 {candidate['city']}, {candidate['state']} ({'Is Mobile' if candidate['is_mobile'] else 'Not mobile'})")
        print(f"{'=' * 80}")
        print()

        # Generate bullets
        print("Generating bullets with GPT-5-mini...\n")
        bullets = generate_rich_bullets_with_ai(candidate)

        print(f"Generated {len(bullets)} bullets:\n")
        for bullet in bullets:
            print(f"• {bullet}")

        print(f"\nRef code: {ref}")
        print("\n" * 2)

if __name__ == "__main__":
    main()
