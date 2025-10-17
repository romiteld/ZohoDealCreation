"""
Rich bullet extraction matching screenshot format.

Key differences from current approach:
1. Extract FULL SENTENCES/PARAGRAPHS from Interviewer Notes (not fragments)
2. Add <b>HTML bold tags</b> around key achievements (AUM, designations, company names, metrics)
3. Generate 5-6 detailed bullets (not 3-4)
4. Each bullet can be multiple sentences long
5. Preserve specific details like "3 firms", "$650M AUM", "MBA initiated"
"""

import re
from typing import List, Dict

def add_bold_emphasis(text: str) -> str:
    """
    Add HTML <b> tags around key achievement terms.

    Bold patterns:
    - Financial metrics: $XXM AUM, $XXB, $XXM-$XXM+
    - Designations: MBA, CFA, CFP, CPRC, MDRT, Executive MBA, Global MBA
    - Company types: HNW, UHNW, RIA, wirehouse, institutional
    - Achievement verbs: led a $X, grew from $X to $Y, ranked #X
    """

    # Bold financial metrics
    text = re.sub(r'(\$[\d.]+[BMK]\+?(?:\s*AUM)?)', r'<b>\1</b>', text, flags=re.IGNORECASE)
    text = re.sub(r'(\$[\d.]+[BMK]?[-–]\$[\d.]+[BMK]\+?)', r'<b>\1</b>', text)

    # Bold designations and credentials
    designations = ['MBA', 'CFA', 'CFP', 'CPRC', 'MDRT', 'CRPC', 'RICP', 'ChFC', 'CLU', 'CIMA', 'CIMC']
    for des in designations:
        text = re.sub(rf'\b({des})\b', r'<b>\1</b>', text)

    # Bold special MBA types
    text = re.sub(r'\b(Executive MBA|Global MBA)\b', r'<b>\1</b>', text, flags=re.IGNORECASE)

    # Bold client types
    client_types = ['HNW', 'UHNW', 'institutional', 'RIA', 'wirehouse', 'broker-dealer', 'family office']
    for ct in client_types:
        text = re.sub(rf'\b({ct})\b', r'<b>\1</b>', text, flags=re.IGNORECASE)

    # Bold major achievement phrases
    text = re.sub(r'\b(led a \$[\d.]+[BMK]? [\w\s]+)', r'<b>\1</b>', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(grew (?:from |AUM )?\$[\d.]+[BMK]? to \$[\d.]+[BMK]?)', r'<b>\1</b>', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(ranked #\d+)', r'<b>\1</b>', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(top \d+%)', r'<b>\1</b>', text, flags=re.IGNORECASE)

    return text


def extract_rich_bullets_from_notes(interviewer_notes: str, top_performance: str, candidate: Dict) -> List[str]:
    """
    Extract 5-6 rich, detailed bullets matching screenshot format.

    Strategy:
    1. Split notes into sentences
    2. Identify high-value sentences (achievements, metrics, experience)
    3. Combine related sentences into comprehensive bullets
    4. Add bold emphasis to key terms
    5. Append availability + comp as final bullet

    Returns: List of 5-6 HTML-formatted bullets
    """
    bullets = []

    combined_text = f"{interviewer_notes}\n\n{top_performance}"

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', combined_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    # BULLET 1: Years of experience + credentials + specialization
    # Pattern: "8 years in institutional investment sales and client relationship management across RIAs, family offices, and broker-dealers"
    experience_bullets = []

    for sent in sentences:
        # Look for year patterns with context
        if re.search(r'\d+\+?\s*years?', sent, re.IGNORECASE):
            # This is a rich experience sentence
            experience_bullets.append(sent)
            break

    if experience_bullets:
        bullet1 = ' '.join(experience_bullets)
        bullet1 = add_bold_emphasis(bullet1)
        bullets.append(bullet1)

    # BULLET 2: Licenses + credentials
    # Pattern: "Series 7, 63, and 65 licensed; MBA initiated. Experience at 3 firms; one a leading investment bank and institutional securities firm"
    license_parts = []

    # Find all Series licenses
    series_matches = re.findall(r'Series\s+\d{1,2}', combined_text, re.IGNORECASE)
    if series_matches:
        unique_series = list(dict.fromkeys(series_matches))  # Preserve order
        license_parts.append(', '.join(unique_series) + ' licensed')

    # Find other licenses (SIE, Life & Health)
    if re.search(r'\bSIE\b', combined_text):
        license_parts.append('SIE')
    if re.search(r'\bLife\s+(?:&|and)\s+Health', combined_text, re.IGNORECASE):
        license_parts.append('Life & Health')

    # Find MBA/designations sentences
    for sent in sentences:
        if re.search(r'\b(MBA|CFA|CFP|CPRC|MDRT)', sent):
            license_parts.append(sent)
            break

    # Find "experience at X firms" patterns
    for sent in sentences:
        if re.search(r'(?:experience|worked) at \d+ firms?', sent, re.IGNORECASE):
            license_parts.append(sent)
            break

    if license_parts:
        bullet2 = '; '.join(license_parts)
        bullet2 = add_bold_emphasis(bullet2)
        bullets.append(bullet2)

    # BULLET 3: Major achievement #1 (AUM growth, presentations, deal flow)
    # Pattern: "Frequently presents to investment committees and national accounts; known for building strategic partnerships and distribution platforms"
    achievement_sentences = []

    for sent in sentences:
        # Look for achievement keywords
        if any(keyword in sent.lower() for keyword in [
            'presents', 'frequently', 'known for', 'strategic', 'partnerships',
            'distribution', 'committees', 'national accounts', 'recognized'
        ]):
            achievement_sentences.append(sent)
            if len(achievement_sentences) >= 2:  # Max 2 sentences
                break

    if achievement_sentences:
        bullet3 = ' '.join(achievement_sentences)
        bullet3 = add_bold_emphasis(bullet3)
        bullets.append(bullet3)

    # BULLET 4: Major achievement #2 (book building, growth metrics)
    # Pattern: "Developed book of business from scratch; consistently praised for delivering unique insights and long-term relationship value. Looking for a life-long firm to join."
    growth_sentences = []

    for sent in sentences:
        if any(keyword in sent.lower() for keyword in [
            'developed', 'built', 'book', 'scratch', 'consistently', 'praised',
            'delivering', 'unique', 'insights', 'relationship value', 'looking for'
        ]):
            growth_sentences.append(sent)
            if len(growth_sentences) >= 2:
                break

    if growth_sentences:
        bullet4 = ' '.join(growth_sentences)
        bullet4 = add_bold_emphasis(bullet4)
        bullets.append(bullet4)

    # BULLET 5: Availability + Compensation
    # Pattern: "Available on 2-4 weeks' notice; desired comp $200k-$250k OTE"
    practical_parts = []

    if candidate.get('availability'):
        avail = candidate['availability'].strip()
        if avail and avail.upper() not in ['NONE', 'N/A', 'NA', '-']:
            practical_parts.append(f"Available {avail}")

    if candidate.get('compensation'):
        comp = candidate['compensation'].strip()
        if comp and comp.upper() not in ['NONE', 'N/A', 'NA', '-']:
            # Format compensation
            comp_formatted = format_compensation_rich(comp)
            practical_parts.append(f"desired comp {comp_formatted}")

    if practical_parts:
        bullet5 = '; '.join(practical_parts)
        bullets.append(bullet5)

    return bullets[:6]  # Max 6 bullets


def format_compensation_rich(comp_str: str) -> str:
    """Format compensation in screenshot style: $200k-$250k OTE"""
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

    return comp_str
