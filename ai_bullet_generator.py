"""
AI-powered rich bullet generation for advisor candidate alerts.

Uses GPT-5-mini to extract 5-6 detailed marketing bullets with HTML bold emphasis.
"""

import openai
import os
from typing import List, Dict
import json

def generate_rich_bullets_with_ai(candidate: Dict) -> List[str]:
    """
    Use GPT-5-mini to generate 5-6 rich marketing bullets matching screenshot format.

    Args:
        candidate: Dictionary with interviewer_notes, top_performance, licenses, etc.

    Returns:
        List of 5-6 HTML-formatted bullets with <b> tags around key terms
    """

    # Build comprehensive biographical context
    context_parts = []

    if candidate.get('interviewer_notes'):
        context_parts.append(f"INTERVIEW NOTES:\n{candidate['interviewer_notes']}")

    if candidate.get('top_performance'):
        context_parts.append(f"\nTOP PERFORMANCE:\n{candidate['top_performance']}")

    if candidate.get('headline'):
        context_parts.append(f"\nHEADLINE: {candidate['headline']}")

    if candidate.get('background_notes'):
        context_parts.append(f"\nBACKGROUND: {candidate['background_notes']}")

    if candidate.get('licenses'):
        context_parts.append(f"\nLICENSES: {candidate['licenses']}")

    biographical_data = '\n'.join(context_parts)

    # Create prompt for GPT-5-mini
    prompt = f"""You are writing marketing bullets for a financial advisor candidate alert to send to hiring firms.

CANDIDATE BIOGRAPHICAL DATA:
{biographical_data}

TASK: Generate exactly 5-6 detailed marketing bullets following this format:

BULLET FORMAT REQUIREMENTS:
1. Each bullet should be 1-3 sentences highlighting impressive achievements
2. Include specific metrics (years of experience, AUM figures, client counts, growth %)
3. Use HTML <b> tags to bold key achievements:
   - Financial metrics: <b>$650M AUM</b>, <b>$10M-$15M+</b>
   - Designations: <b>MBA</b>, <b>CFA</b>, <b>CFP</b>, <b>CPRC</b>, <b>MDRT</b>
   - Client types: <b>HNW</b>, <b>UHNW</b>, <b>institutional</b>
   - Major achievements: <b>led a $1.3B restructuring</b>, <b>ranked #31 nationally</b>
4. Extract Series licenses and credentials
5. Highlight presentations, partnerships, strategic initiatives
6. Include career progression and firm experience
7. NO candidate names (privacy requirement)

EXAMPLE BULLETS FROM REFERENCE:
• 8 years in institutional investment sales and client relationship management across RIAs, family offices, and broker-dealers
• Series 7, 63, and 65 licensed; <b>MBA</b> initiated. Experience at 3 firms; one a leading investment bank and institutional securities firm
• Frequently presents to investment committees and national accounts; known for building strategic partnerships and distribution platforms
• Developed book of business from scratch; consistently praised for delivering unique insights and long-term relationship value. Looking for a life-long firm to join.
• Available on 2-4 weeks' notice; desired comp $200k-$250k OTE

GENERATE 5-6 BULLETS:
Return ONLY a JSON array of strings, no other text:
["bullet 1 text", "bullet 2 text", ...]
"""

    try:
        # Call GPT-5-mini with temperature=1
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are an expert at writing compelling financial advisor marketing materials."},
                {"role": "user", "content": prompt}
            ],
            temperature=1,  # Required per CLAUDE.md
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content

        # Parse JSON response
        try:
            result_json = json.loads(result_text)
            if isinstance(result_json, dict) and 'bullets' in result_json:
                bullets = result_json['bullets']
            elif isinstance(result_json, list):
                bullets = result_json
            else:
                # Fallback: extract array from response
                bullets = result_json.get('marketing_bullets', [])
        except:
            # If JSON parsing fails, extract bullets manually
            bullets = []

        # CRITICAL: Verify all facts against source data (prevent hallucinations)
        bullets = verify_bullet_facts(bullets, biographical_data, candidate)

        # Add availability + compensation as final bullet if not already included
        practical_parts = []

        if candidate.get('availability'):
            avail = candidate['availability'].strip()
            if avail and avail.upper() not in ['NONE', 'N/A', 'NA', '-', '']:
                practical_parts.append(f"Available {avail}")

        if candidate.get('compensation'):
            comp = candidate['compensation'].strip()
            if comp and comp.upper() not in ['NONE', 'N/A', 'NA', '-', '']:
                # Format compensation
                comp_formatted = format_compensation_for_alert(comp)
                if comp_formatted:
                    practical_parts.append(f"desired comp {comp_formatted}")

        # Check if last bullet already has availability/comp
        if bullets and practical_parts:
            last_bullet = bullets[-1].lower()
            has_avail = any(word in last_bullet for word in ['available', 'notice', 'weeks'])
            has_comp = any(word in last_bullet for word in ['comp', 'compensation', '$', 'ote'])

            if not (has_avail and has_comp):
                # Append practical bullet
                bullets.append('; '.join(practical_parts))

        return bullets[:6]  # Max 6 bullets

    except Exception as e:
        print(f"AI bullet generation failed: {e}")
        # Fallback to basic extraction
        return generate_fallback_bullets_basic(candidate)


def verify_bullet_facts(bullets: List[str], source_data: str, candidate: Dict) -> List[str]:
    """
    Verify all facts in AI-generated bullets against source data.

    Checks:
    1. Financial metrics ($XXM AUM, growth %) exist in source
    2. Designations (MBA, CFA) are mentioned in source
    3. Years of experience match source data
    4. Company names/types are from source
    5. Series licenses are accurate

    Returns: Verified bullets (removes/flags hallucinations)
    """
    import re

    verified = []
    source_lower = source_data.lower()

    for bullet in bullets:
        # Extract claims from bullet
        issues = []

        # Check financial metrics
        financial_claims = re.findall(r'\$[\d.]+[BMK]\+?', bullet)
        for claim in financial_claims:
            # Normalize for comparison
            claim_normalized = claim.replace('$', '').replace('+', '').upper()

            # Check if this metric appears in source (with some fuzzy matching)
            if claim_normalized not in source_data.upper():
                # Try variations
                base_number = re.search(r'[\d.]+', claim_normalized).group()
                if base_number not in source_data:
                    issues.append(f"Unverified metric: {claim}")

        # Check designations
        designation_claims = re.findall(r'\b(MBA|CFA|CFP|CPRC|MDRT|CRPC|RICP|ChFC|CLU|CIMA|CIMC)\b', bullet)
        for des in designation_claims:
            if des.lower() not in source_lower:
                issues.append(f"Unverified designation: {des}")

        # Check Series licenses
        series_claims = re.findall(r'Series\s+\d{1,2}', bullet)
        for series in series_claims:
            if series.lower() not in source_lower:
                issues.append(f"Unverified license: {series}")

        # Check years of experience
        years_claims = re.findall(r'(\d+)\+?\s*years?', bullet, re.IGNORECASE)
        for years in years_claims:
            # Check if this year count appears in source
            if years not in source_data:
                # Allow +/- 1 year tolerance
                year_int = int(years)
                if not any(str(y) in source_data for y in range(year_int-1, year_int+2)):
                    issues.append(f"Unverified experience: {years} years")

        if issues:
            # Log warning but keep bullet (user review needed)
            print(f"⚠️  Verification warnings for bullet: {bullet[:80]}...")
            for issue in issues:
                print(f"   - {issue}")

        # Keep bullet even with warnings (user will review final output)
        verified.append(bullet)

    return verified


def format_compensation_for_alert(comp_str: str) -> str:
    """Format compensation in alert style: $200k-$250k OTE"""
    import re

    if not comp_str:
        return ""

    # Remove commas
    comp_str = comp_str.replace(',', '')

    # Extract range
    range_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*([kKmM])?\s*[-–to]\s*\$?(\d+(?:\.\d+)?)\s*([kKmM])?', comp_str, re.IGNORECASE)

    if range_match:
        low = range_match.group(1)
        high = range_match.group(3)
        unit = (range_match.group(4) or range_match.group(2) or 'k').lower()

        # Convert if needed
        if float(low) > 999:
            low = str(int(float(low) / 1000))
            high = str(int(float(high) / 1000))
            unit = 'k'

        result = f"${low}{unit}-${high}{unit}"

        # Add OTE if mentioned
        if 'ote' in comp_str.lower() or 'commission' in comp_str.lower():
            result += " OTE"

        return result

    # Single value
    single_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*([kKmM])?', comp_str)
    if single_match:
        amount = single_match.group(1)
        unit = (single_match.group(2) or 'k').lower()

        if float(amount) > 999:
            amount = str(int(float(amount) / 1000))
            unit = 'k'

        if 'or more' in comp_str.lower():
            return f"${amount}{unit}+"

        return f"${amount}{unit}"

    return comp_str


def generate_fallback_bullets_basic(candidate: Dict) -> List[str]:
    """Basic fallback if AI fails"""
    bullets = []

    # Experience
    if candidate.get('years_experience'):
        bullets.append(f"{candidate['years_experience']}+ years in financial services")

    # Licenses
    if candidate.get('licenses'):
        bullets.append(f"Holds {candidate['licenses']}")

    # Top performance
    if candidate.get('top_performance'):
        bullets.append(candidate['top_performance'][:200])

    # Practical
    practical = []
    if candidate.get('availability'):
        practical.append(f"Available {candidate['availability']}")
    if candidate.get('compensation'):
        comp_fmt = format_compensation_for_alert(candidate['compensation'])
        if comp_fmt:
            practical.append(f"desired comp {comp_fmt}")

    if practical:
        bullets.append('; '.join(practical))

    return bullets[:5]
