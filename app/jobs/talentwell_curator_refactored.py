"""
Refactored TalentWell Curator with Score-Based Bullet Ranking System

This file shows the refactored _score_bullet and _generate_hard_skill_bullets methods
that implement intelligent bullet prioritization based on business value.
"""

from typing import Dict, List, Any, Optional
from app.extract.evidence import BulletPoint
import re
import logging

logger = logging.getLogger(__name__)


class TalentWellCuratorRefactored:
    """Refactored methods for score-based bullet ranking."""

    def _score_bullet(self, bullet: BulletPoint, deal: Dict[str, Any]) -> float:
        """
        Score a bullet point based on business value priority.

        Priority hierarchy:
        - AUM/Book Size: 10 (highest value indicator)
        - Growth Metrics: 9 (shows trajectory and success)
        - Production: 8.5 (revenue generation)
        - Rankings/Achievements: 8 (competitive positioning)
        - Client Metrics: 7.5 (relationship management)
        - Licenses/Designations: 7 (professional qualifications)
        - Team/Management: 6 (leadership capabilities)
        - Experience: 5 (baseline qualification)
        - Education: 4 (educational background)
        - Availability: 3 (logistics)
        - Compensation: 2 (expectations)
        - Location: 0 (redundant with header)
        - Company: 0 (redundant with header)
        """
        text_lower = bullet.text.lower()

        # Check for duplicates of header information (score 0)
        candidate_name = (deal.get('candidate_name', '') or '').lower()
        company_name = (deal.get('company_name', '') or '').lower()
        location = (deal.get('location', '') or '').lower()

        # Filter out redundant information
        if any([
            candidate_name and candidate_name in text_lower,
            company_name and company_name in text_lower,
            location and text_lower.startswith('location:'),
            text_lower.startswith('company:'),
            text_lower.startswith('firm:'),
        ]):
            return 0.0

        # AUM/Book Size (10)
        if any(keyword in text_lower for keyword in ['aum:', 'book size:', 'assets under management', 'manages $']):
            # Extra boost for large AUM
            if any(unit in text_lower for unit in ['billion', 'b ', 'b)', '$5b+', '$1b–']):
                return 10.0
            elif any(unit in text_lower for unit in ['million', 'm ', 'm)', '$500m']):
                return 9.8
            return 9.5

        # Growth Metrics (9)
        if any(keyword in text_lower for keyword in ['grew', 'growth', 'increased', 'expanded', 'doubled', 'tripled']):
            # Extra boost for percentage growth
            if '%' in text_lower:
                return 9.0
            return 8.8

        # Production (8.5)
        if 'production:' in text_lower or 'annual production' in text_lower or 'revenue' in text_lower:
            return 8.5

        # Rankings/Achievements (8)
        if any(keyword in text_lower for keyword in [
            'top', 'ranking', 'president', 'club', 'award', 'recognition',
            'best', 'leader', '#1', 'number one', 'first place', 'top producer'
        ]):
            return 8.0

        # Client Metrics (7.5)
        if any(keyword in text_lower for keyword in ['client', 'household', 'relationship', 'retention']):
            # Higher score for client count
            if any(char.isdigit() for char in text_lower):
                return 7.5
            return 7.2

        # Licenses/Designations (7)
        if any(keyword in text_lower for keyword in [
            'series', 'license', 'designation', 'cfa', 'cfp', 'cpa', 'chfc',
            'clu', 'cima', 'cpwa', 'certified', 'chartered'
        ]):
            # Higher score for multiple designations
            if ',' in text_lower or 'and' in text_lower:
                return 7.0
            return 6.8

        # Team/Management (6)
        if any(keyword in text_lower for keyword in ['team', 'manage', 'lead', 'supervise', 'oversee']):
            return 6.0

        # Experience (5)
        if 'experience:' in text_lower or 'years' in text_lower:
            # Higher score for more years
            years_match = re.search(r'(\d+)\+?\s*years?', text_lower)
            if years_match:
                years = int(years_match.group(1))
                if years >= 20:
                    return 5.5
                elif years >= 10:
                    return 5.2
            return 5.0

        # Education (4)
        if 'education:' in text_lower or any(keyword in text_lower for keyword in ['degree', 'mba', 'bachelor', 'master']):
            return 4.0

        # Specialties/Focus (3.5)
        if any(keyword in text_lower for keyword in ['specialt', 'focus', 'expertise', 'specialized']):
            return 3.5

        # Availability (3)
        if 'available:' in text_lower or 'available in' in text_lower or 'start date' in text_lower:
            return 3.0

        # Compensation (2)
        if 'compensation:' in text_lower or 'target comp:' in text_lower or 'salary' in text_lower:
            return 2.0

        # Default score for unclassified bullets
        return 1.0

    async def _generate_hard_skill_bullets(
        self,
        deal: Dict[str, Any],
        enhanced_data: Dict[str, Any],
        transcript: Optional[str]
    ) -> List[BulletPoint]:
        """
        Generate 3-5 hard skill bullets using score-based ranking.
        Collects ALL bullets from ALL sources, scores them, and returns top 5.
        """
        all_bullets = []

        # === PHASE 1: Collect ALL bullets from ALL sources ===

        # 1. CRM Data - Primary source with privacy handling
        if deal.get('book_size_aum'):
            # Parse and apply privacy rounding if available
            if hasattr(self, '_parse_aum') and hasattr(self, '_round_aum_for_privacy'):
                aum_value = self._parse_aum(deal['book_size_aum'])
                if aum_value > 0:
                    aum_rounded = self._round_aum_for_privacy(aum_value)
                    if aum_rounded and (not hasattr(self, '_is_internal_note') or not self._is_internal_note(deal['book_size_aum'])):
                        all_bullets.append(BulletPoint(
                            text=f"AUM: {aum_rounded}",
                            confidence=0.95,
                            source="CRM"
                        ))
            else:
                # Fallback if helper methods not available
                all_bullets.append(BulletPoint(
                    text=f"AUM: {deal['book_size_aum']}",
                    confidence=0.95,
                    source="CRM"
                ))

        if deal.get('production_12mo'):
            all_bullets.append(BulletPoint(
                text=f"Production: {deal['production_12mo']}",
                confidence=0.95,
                source="CRM"
            ))

        if deal.get('professional_designations'):
            all_bullets.append(BulletPoint(
                text=f"Licenses/Designations: {deal['professional_designations']}",
                confidence=0.95,
                source="CRM"
            ))

        years_exp = deal.get('years_experience')
        if years_exp:
            all_bullets.append(BulletPoint(
                text=f"Experience: {years_exp}",
                confidence=0.95,
                source="CRM"
            ))

        if deal.get('when_available'):
            # Format availability if helper available
            if hasattr(self, '_format_availability'):
                formatted = self._format_availability(deal['when_available'])
                if formatted:
                    all_bullets.append(BulletPoint(
                        text=formatted,
                        confidence=0.9,
                        source="CRM"
                    ))
            else:
                all_bullets.append(BulletPoint(
                    text=f"Available: {deal['when_available']}",
                    confidence=0.9,
                    source="CRM"
                ))

        if deal.get('desired_comp'):
            # Standardize compensation if helper available
            if hasattr(self, '_standardize_compensation'):
                standardized = self._standardize_compensation(deal['desired_comp'])
                if standardized:
                    all_bullets.append(BulletPoint(
                        text=standardized,
                        confidence=0.9,
                        source="CRM"
                    ))
            else:
                all_bullets.append(BulletPoint(
                    text=f"Compensation: {deal['desired_comp']}",
                    confidence=0.9,
                    source="CRM"
                ))

        # 2. Enhanced Data - Secondary source
        if enhanced_data.get('aum_managed') and not deal.get('book_size_aum'):
            if hasattr(self, '_parse_aum') and hasattr(self, '_round_aum_for_privacy'):
                aum_value = self._parse_aum(enhanced_data['aum_managed'])
                if aum_value > 0:
                    aum_rounded = self._round_aum_for_privacy(aum_value)
                    if aum_rounded:
                        all_bullets.append(BulletPoint(
                            text=f"AUM: {aum_rounded}",
                            confidence=0.9,
                            source="Extraction"
                        ))
            else:
                all_bullets.append(BulletPoint(
                    text=f"AUM: {enhanced_data['aum_managed']}",
                    confidence=0.9,
                    source="Extraction"
                ))

        if enhanced_data.get('production_annual') and not deal.get('production_12mo'):
            all_bullets.append(BulletPoint(
                text=f"Production: {enhanced_data['production_annual']}",
                confidence=0.9,
                source="Extraction"
            ))

        if enhanced_data.get('client_count'):
            all_bullets.append(BulletPoint(
                text=f"Clients: {enhanced_data['client_count']}",
                confidence=0.85,
                source="Extraction"
            ))

        licenses = enhanced_data.get('licenses_held', []) or []
        designations = enhanced_data.get('designations', []) or []
        prof_creds = licenses + designations
        if prof_creds and not deal.get('professional_designations'):
            all_bullets.append(BulletPoint(
                text=f"Licenses/Designations: {', '.join(prof_creds[:4])}",
                confidence=0.9,
                source="Extraction"
            ))

        if enhanced_data.get('years_experience') and not deal.get('years_experience'):
            all_bullets.append(BulletPoint(
                text=f"Experience: {enhanced_data['years_experience']}",
                confidence=0.9,
                source="Extraction"
            ))

        if enhanced_data.get('availability_timeframe') and not deal.get('when_available'):
            all_bullets.append(BulletPoint(
                text=f"Available: {enhanced_data['availability_timeframe']}",
                confidence=0.85,
                source="Extraction"
            ))

        if enhanced_data.get('compensation_range') and not deal.get('desired_comp'):
            all_bullets.append(BulletPoint(
                text=f"Compensation: {enhanced_data['compensation_range']}",
                confidence=0.85,
                source="Extraction"
            ))

        # 3. Transcript Mining - Tertiary source
        if transcript:
            # Use evidence extractor if available
            if hasattr(self, 'evidence_extractor'):
                transcript_bullets = self.evidence_extractor.generate_bullets_with_evidence(
                    {"transcript": transcript},
                    transcript=transcript
                )
                # Add all transcript bullets (will be scored later)
                for bullet in transcript_bullets:
                    all_bullets.append(bullet)

            # Direct transcript mining for specific patterns
            if hasattr(self, '_mine_transcript_directly'):
                direct_bullets = await self._mine_transcript_directly(transcript, enhanced_data)
                for bullet in direct_bullets:
                    # Check if not duplicate
                    if not any(b.text == bullet.text for b in all_bullets):
                        all_bullets.append(bullet)
            else:
                # Fallback direct mining if method not available
                # AUM/Book size patterns
                aum_patterns = [
                    r'\$(\d+(?:\.\d+)?)\s*([BMK])\s*(?:AUM|aum|under management|book)',
                    r'manage[sd]?\s*\$(\d+(?:\.\d+)?)\s*([BMK])',
                ]
                for pattern in aum_patterns:
                    matches = re.findall(pattern, transcript, re.IGNORECASE)
                    if matches:
                        amount, unit = matches[0]
                        unit_map = {'B': 'billion', 'M': 'million', 'K': 'thousand'}
                        text = f"AUM: ${amount}{unit_map.get(unit.upper(), unit)}"
                        if not any(b.text == text for b in all_bullets):
                            all_bullets.append(BulletPoint(
                                text=text,
                                confidence=0.9,
                                source="Transcript"
                            ))
                        break

                # Growth patterns
                growth_pattern = r'grew\s*(?:book|assets|aum)?\s*(?:by\s*)?(\d+)%'
                growth_matches = re.findall(growth_pattern, transcript, re.IGNORECASE)
                if growth_matches:
                    text = f"Grew book by {growth_matches[0]}%"
                    if not any(b.text == text for b in all_bullets):
                        all_bullets.append(BulletPoint(
                            text=text,
                            confidence=0.85,
                            source="Transcript"
                        ))

        # 4. Additional CRM fields that might have value
        if deal.get('education'):
            all_bullets.append(BulletPoint(
                text=f"Education: {deal['education']}",
                confidence=0.8,
                source="CRM"
            ))

        if deal.get('industry_focus'):
            all_bullets.append(BulletPoint(
                text=f"Industry Focus: {deal['industry_focus']}",
                confidence=0.8,
                source="CRM"
            ))

        # 5. Add any achievements or rankings from enhanced data
        if enhanced_data.get('achievements'):
            for achievement in enhanced_data.get('achievements', [])[:2]:
                all_bullets.append(BulletPoint(
                    text=achievement,
                    confidence=0.85,
                    source="Extraction"
                ))

        # === PHASE 2: Score ALL bullets ===
        scored_bullets = []
        for bullet in all_bullets:
            score = self._score_bullet(bullet, deal)
            if score > 0:  # Only include non-zero scored bullets
                scored_bullets.append((bullet, score))

        # === PHASE 3: Sort by score descending ===
        scored_bullets.sort(key=lambda x: x[1], reverse=True)

        # === PHASE 4: Return top 5 bullets ===
        top_bullets = [bullet for bullet, score in scored_bullets[:5]]

        # Log scoring results for debugging
        if scored_bullets:
            logger.info(f"Bullet scoring for {deal.get('candidate_name', 'Unknown')}:")
            for i, (bullet, score) in enumerate(scored_bullets[:10]):  # Log top 10
                logger.info(f"  #{i+1} (score={score:.1f}): {bullet.text[:50]}...")

        # Ensure minimum of 3 bullets if possible (but never fake data)
        if len(top_bullets) < 3:
            logger.warning(f"Only {len(top_bullets)} bullets for candidate {deal.get('candidate_name')}")

        return top_bullets