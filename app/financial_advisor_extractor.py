"""
Financial Advisor Data Extraction and Pattern Recognition

This module extends the existing email processing system with specialized
financial advisor pattern recognition, including AUM, production metrics,
licenses, and career trajectory analysis using pgvector similarity search.

Integrates with the database schema defined in add_financial_advisor_patterns.sql
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from decimal import Decimal, InvalidOperation
from datetime import datetime
import asyncio

from .models import ExtractedData, CompanyRecord, ContactRecord, DealRecord
from .database_enhancements import EnhancedPostgreSQLClient

logger = logging.getLogger(__name__)


class FinancialPatternExtractor:
    """Extract and normalize financial advisor patterns from email content"""

    def __init__(self, postgres_client: Optional[EnhancedPostgreSQLClient] = None):
        self.postgres_client = postgres_client

        # Financial metric regex patterns optimized for advisor emails
        self.aum_patterns = [
            r'\$([0-9,]+(?:\.[0-9]+)?)\s*(billion|billion|b|B)\s*(?:AUM|aum|in assets|under management|managed|book)',
            r'\$([0-9,]+(?:\.[0-9]+)?)\s*(million|million|m|M|MM)\s*(?:AUM|aum|in assets|under management|managed|book)',
            r'\$([0-9,]+(?:\.[0-9]+)?)\s*(thousand|thousand|k|K)\s*(?:AUM|aum|in assets|under management|managed|book)',
            r'(?:AUM|aum|assets under management|book size|manages?|managing)[:\s-]+\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?',
            r'(?:oversee[sn]?|responsible for)[\s\w]*\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?[\s\w]*(?:in assets|AUM)',
            r'(?:book|portfolio)[\s\w]*\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?'
        ]

        self.production_patterns = [
            r'\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)\s*(?:annual production|production|in production|revenue|gross)',
            r'(?:production|revenue|generated|produces?)[:\s-]+\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?',
            r'(?:generating|produced?)[\s\w]*\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?\s*(?:annually|per year|in production)?',
            r'(?:T12|trailing 12|last 12 months?)[\s\w]*\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?'
        ]

        self.compensation_patterns = [
            r'(?:salary|compensation|pay|seeking|looking for)[:\s]*\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?(?:\s*[-–—]\s*\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?)?',
            r'\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?\s*(?:[-–—]\s*\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?)?\s*(?:base|salary|compensation)',
            r'(?:base|salary|compensation)[:\s]*\$([0-9,]+(?:\.[0-9]+)?)\s*([BMKbmk]?)(?:illion|illion)?'
        ]

        self.license_patterns = {
            'series_7': [r'(?:series|sie)[\s\-]?7(?!\d)', r'\bs7\b'],
            'series_63': [r'(?:series)[\s\-]?63(?!\d)', r'\bs63\b'],
            'series_65': [r'(?:series)[\s\-]?65(?!\d)', r'\bs65\b'],
            'series_66': [r'(?:series)[\s\-]?66(?!\d)', r'\bs66\b'],
            'series_24': [r'(?:series)[\s\-]?24(?!\d)', r'\bs24\b'],
            'series_31': [r'(?:series)[\s\-]?31(?!\d)', r'\bs31\b']
        }

        self.designation_patterns = {
            'cfa': [r'\bCFA\b', r'Chartered Financial Analyst', r'C\.F\.A\.'],
            'cfp': [r'\bCFP®?\b', r'Certified Financial Planner', r'C\.F\.P\.'],
            'cpwa': [r'\bCPWA®?\b', r'Certified Private Wealth Advisor', r'C\.P\.W\.A\.'],
            'chfc': [r'\bChFC®?\b', r'Chartered Financial Consultant', r'Ch\.F\.C\.'],
            'clu': [r'\bCLU®?\b', r'Chartered Life Underwriter', r'C\.L\.U\.'],
            'mba': [r'\bMBA\b', r'Master[s]? of Business Administration', r'M\.B\.A\.']
        }

        self.achievement_patterns = [
            r'(?:#|top\s)?([0-9]+)(?:\s*[-–—]\s*[0-9]+)?\s*(?:%|percent|percentile)\s*(?:performer|producer|advisor|nationally|firm.?wide)',
            r'(?:#|ranked\s?)([0-9]+)(?:\s*[-–—]\s*[0-9]+)?\s*(?:nationally|in nation|across firm|company.?wide|out of [0-9,]+)',
            r'(?:president[\'']?s club|chairman[\'']?s club|circle of (?:excellence|champions)|top producer|leading producer)',
            r'(?:barron[\'']?s|forbes)\s*(?:top|best|leading)[\s\w]*(?:advisor|financial advisor)',
            r'(?:close rate|conversion rate|win rate)[:\s]+([0-9]+(?:\.[0-9]+)?)%'
        ]

        self.client_patterns = [
            r'([0-9,]+)\+?\s*(?:clients?|relationships?|households?|families)',
            r'(?:serve[sd]?|serving|manages?|managing)[\s\w]*([0-9,]+)\+?\s*(?:clients?|relationships?)',
            r'([0-9]+(?:\.[0-9]+)?)%\s*(?:retention|client retention|renewal rate)',
            r'([0-9,]+)\+?\s*(?:HNW|UHNW|high.?net.?worth|ultra.?high)\s*(?:clients?|individuals?|families)'
        ]

    def extract_financial_metrics(self, email_content: str) -> Dict[str, Any]:
        """Extract all financial metrics from email content"""
        content_lower = email_content.lower()
        metrics = {
            'aum_amount': None,
            'aum_range_low': None,
            'aum_range_high': None,
            'production_amount': None,
            'compensation_low': None,
            'compensation_high': None,
            'trailing_12_revenue': None,
            'years_experience': None,
            'team_size': None,
            'client_count': None,
            'has_series_7': False,
            'has_series_63': False,
            'has_series_65': False,
            'has_series_66': False,
            'has_series_24': False,
            'has_series_31': False,
            'has_cfa': False,
            'has_cfp': False,
            'has_cpwa': False,
            'has_chfc': False,
            'has_clu': False,
            'has_mba': False,
            'designations': [],
            'licenses': [],
            'achievements': [],
            'rankings': [],
            'performance_percentages': [],
            'raw_patterns': []
        }

        # Extract AUM amounts
        for pattern in self.aum_patterns:
            matches = re.finditer(pattern, email_content, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.group(1).replace(',', '')
                    unit = match.group(2).upper() if len(match.groups()) > 1 and match.group(2) else ''
                    amount = self._normalize_amount(amount_str, unit)
                    if amount and (not metrics['aum_amount'] or amount > metrics['aum_amount']):
                        metrics['aum_amount'] = float(amount)
                        metrics['raw_patterns'].append({
                            'type': 'aum',
                            'raw_text': match.group(0),
                            'amount': float(amount)
                        })
                except (ValueError, IndexError, InvalidOperation):
                    continue

        # Extract production amounts
        for pattern in self.production_patterns:
            matches = re.finditer(pattern, email_content, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.group(1).replace(',', '')
                    unit = match.group(2).upper() if len(match.groups()) > 1 and match.group(2) else ''
                    amount = self._normalize_amount(amount_str, unit)
                    if amount and (not metrics['production_amount'] or amount > metrics['production_amount']):
                        metrics['production_amount'] = float(amount)
                        metrics['raw_patterns'].append({
                            'type': 'production',
                            'raw_text': match.group(0),
                            'amount': float(amount)
                        })
                except (ValueError, IndexError, InvalidOperation):
                    continue

        # Extract compensation ranges
        for pattern in self.compensation_patterns:
            matches = re.finditer(pattern, email_content, re.IGNORECASE)
            for match in matches:
                try:
                    groups = match.groups()
                    # Handle single amount or range
                    amount1_str = groups[0].replace(',', '') if groups[0] else None
                    unit1 = groups[1].upper() if len(groups) > 1 and groups[1] else ''
                    amount2_str = groups[2].replace(',', '') if len(groups) > 2 and groups[2] else None
                    unit2 = groups[3].upper() if len(groups) > 3 and groups[3] else ''

                    if amount1_str:
                        amount1 = self._normalize_amount(amount1_str, unit1)
                        if amount1:
                            metrics['compensation_low'] = float(amount1)

                            if amount2_str:
                                amount2 = self._normalize_amount(amount2_str, unit2)
                                if amount2:
                                    metrics['compensation_high'] = float(amount2)
                            else:
                                metrics['compensation_high'] = float(amount1)

                            metrics['raw_patterns'].append({
                                'type': 'compensation',
                                'raw_text': match.group(0),
                                'amount_low': float(amount1),
                                'amount_high': float(amount2) if amount2_str else float(amount1)
                            })
                except (ValueError, IndexError, InvalidOperation):
                    continue

        # Extract licenses
        for license_key, patterns in self.license_patterns.items():
            for pattern in patterns:
                if re.search(pattern, email_content, re.IGNORECASE):
                    metrics[f'has_{license_key}'] = True
                    license_name = license_key.replace('_', ' ').title()
                    if license_name not in metrics['licenses']:
                        metrics['licenses'].append(license_name)
                    break

        # Extract designations
        for designation_key, patterns in self.designation_patterns.items():
            for pattern in patterns:
                if re.search(pattern, email_content, re.IGNORECASE):
                    metrics[f'has_{designation_key}'] = True
                    designation_name = designation_key.upper()
                    if designation_name not in metrics['designations']:
                        metrics['designations'].append(designation_name)
                    break

        # Extract achievements and rankings
        for pattern in self.achievement_patterns:
            matches = re.finditer(pattern, email_content, re.IGNORECASE)
            for match in matches:
                achievement_text = match.group(0)
                metrics['achievements'].append(achievement_text)
                metrics['raw_patterns'].append({
                    'type': 'achievement',
                    'raw_text': achievement_text
                })

        # Extract years of experience
        experience_patterns = [
            r'([0-9]+)\+?\s*years?\s*(?:of\s*)?(?:experience|in the industry|financial services)',
            r'(?:experience|industry experience)[:\s]+([0-9]+)\+?\s*years?',
            r'([0-9]+)\+?\s*year\s*(?:veteran|professional)'
        ]
        for pattern in experience_patterns:
            match = re.search(pattern, email_content, re.IGNORECASE)
            if match:
                try:
                    years = int(match.group(1))
                    if not metrics['years_experience'] or years > metrics['years_experience']:
                        metrics['years_experience'] = years
                except ValueError:
                    continue

        # Extract client counts
        for pattern in self.client_patterns:
            matches = re.finditer(pattern, email_content, re.IGNORECASE)
            for match in matches:
                try:
                    if '%' in match.group(0):
                        # Percentage metric
                        percentage = float(match.group(1))
                        metrics['performance_percentages'].append(percentage)
                    else:
                        # Client count
                        count_str = match.group(1).replace(',', '')
                        count = int(count_str)
                        if not metrics['client_count'] or count > metrics['client_count']:
                            metrics['client_count'] = count
                except (ValueError, IndexError):
                    continue

        return metrics

    def _normalize_amount(self, amount_str: str, unit: str) -> Optional[Decimal]:
        """Normalize amount string to decimal value"""
        try:
            amount = Decimal(amount_str)

            if unit in ['B', 'BILLION']:
                return amount * Decimal('1000000000')
            elif unit in ['M', 'MILLION', 'MM']:
                return amount * Decimal('1000000')
            elif unit in ['K', 'THOUSAND']:
                return amount * Decimal('1000')
            else:
                # If no unit and amount is small, assume thousands for financial context
                if amount < 1000 and amount > 100:
                    return amount * Decimal('1000')
                return amount
        except InvalidOperation:
            return None

    async def enhance_extracted_data(
        self,
        extracted_data: ExtractedData,
        email_content: str
    ) -> ExtractedData:
        """Enhance extracted data with financial advisor specific fields"""

        # Extract financial metrics
        metrics = self.extract_financial_metrics(email_content)

        # Update ExtractedData with financial advisor fields
        if metrics['aum_amount']:
            extracted_data.aum_managed = self._format_amount(metrics['aum_amount'])

        if metrics['production_amount']:
            extracted_data.production_annual = self._format_amount(metrics['production_amount'])

        if metrics['client_count']:
            extracted_data.client_count = f"{metrics['client_count']:,} clients"

        if metrics['licenses']:
            extracted_data.licenses_held = metrics['licenses']

        if metrics['designations']:
            extracted_data.designations = metrics['designations']

        if metrics['years_experience']:
            extracted_data.years_experience = f"{metrics['years_experience']} years"

        if metrics['compensation_low'] and metrics['compensation_high']:
            low = self._format_amount(metrics['compensation_low'])
            high = self._format_amount(metrics['compensation_high'])
            if low == high:
                extracted_data.compensation_range = low
            else:
                extracted_data.compensation_range = f"{low} - {high}"

        # Store raw metrics in deal_record description for database storage
        if extracted_data.deal_record is None:
            extracted_data.deal_record = DealRecord()

        # Append financial metrics to description
        financial_summary = []
        if metrics['aum_amount']:
            financial_summary.append(f"AUM: {self._format_amount(metrics['aum_amount'])}")
        if metrics['production_amount']:
            financial_summary.append(f"Production: {self._format_amount(metrics['production_amount'])}")
        if metrics['licenses']:
            financial_summary.append(f"Licenses: {', '.join(metrics['licenses'])}")
        if metrics['designations']:
            financial_summary.append(f"Designations: {', '.join(metrics['designations'])}")

        if financial_summary:
            current_desc = extracted_data.deal_record.description_of_reqs or ""
            if current_desc:
                current_desc += " | "
            current_desc += " | ".join(financial_summary)
            extracted_data.deal_record.description_of_reqs = current_desc

        return extracted_data

    def _format_amount(self, amount: float) -> str:
        """Format amount for display"""
        if amount >= 1_000_000_000:
            return f"${amount / 1_000_000_000:.1f}B"
        elif amount >= 1_000_000:
            return f"${amount / 1_000_000:.1f}M"
        elif amount >= 1_000:
            return f"${amount / 1_000:.0f}K"
        else:
            return f"${amount:,.0f}"

    async def store_financial_patterns(
        self,
        email_id: str,
        email_content: str,
        extracted_metrics: Dict[str, Any]
    ) -> List[str]:
        """Store extracted patterns in database for learning"""
        if not self.postgres_client:
            return []

        pattern_ids = []

        try:
            await self.postgres_client.init_pool()

            # Store each raw pattern
            for pattern in extracted_metrics.get('raw_patterns', []):
                async with self.postgres_client.pool.acquire() as conn:
                    pattern_id = await conn.fetchval("""
                        INSERT INTO financial_patterns (
                            pattern_type, raw_text, normalized_value, unit,
                            confidence_score, source_email_id
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING id
                    """,
                        pattern['type'],
                        pattern['raw_text'],
                        pattern.get('amount', pattern.get('amount_low', 0)),
                        self._extract_unit_from_text(pattern['raw_text']),
                        0.85,  # Default confidence
                        email_id
                    )
                    pattern_ids.append(str(pattern_id))

            logger.info(f"Stored {len(pattern_ids)} financial patterns for email {email_id}")

        except Exception as e:
            logger.error(f"Failed to store financial patterns: {e}")

        return pattern_ids

    def _extract_unit_from_text(self, text: str) -> str:
        """Extract unit from pattern text"""
        text_upper = text.upper()
        if 'B' in text_upper or 'BILLION' in text_upper:
            return 'B'
        elif 'M' in text_upper or 'MILLION' in text_upper or 'MM' in text_upper:
            return 'M'
        elif 'K' in text_upper or 'THOUSAND' in text_upper:
            return 'K'
        return ''

    async def find_similar_advisors(
        self,
        career_narrative: str,
        similarity_threshold: float = 0.8,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find advisors with similar career trajectories using vector search"""
        if not self.postgres_client:
            return []

        try:
            # This would require an embedding model integration
            # For now, return empty list as placeholder
            logger.info(f"Similar advisor search requested for narrative: {career_narrative[:100]}...")
            return []

        except Exception as e:
            logger.error(f"Failed to find similar advisors: {e}")
            return []

    async def analyze_market_data(
        self,
        aum_threshold: float = 100_000_000,
        production_threshold: float = 1_000_000
    ) -> Dict[str, Any]:
        """Analyze market data for high-value advisors"""
        if not self.postgres_client:
            return {}

        try:
            await self.postgres_client.init_pool()

            async with self.postgres_client.pool.acquire() as conn:
                # Get high-value advisor statistics
                stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_advisors,
                        COUNT(CASE WHEN aum_amount >= $1 THEN 1 END) as high_aum_count,
                        COUNT(CASE WHEN production_amount >= $2 THEN 1 END) as high_production_count,
                        AVG(aum_amount) as avg_aum,
                        AVG(production_amount) as avg_production,
                        AVG(years_experience) as avg_experience
                    FROM email_processing_history
                    WHERE processing_status = 'success'
                        AND (aum_amount IS NOT NULL OR production_amount IS NOT NULL)
                """, aum_threshold, production_threshold)

                # Get designation distribution
                designations = await conn.fetch("""
                    SELECT
                        unnest(designations) as designation,
                        COUNT(*) as count
                    FROM email_processing_history
                    WHERE designations IS NOT NULL
                        AND processing_status = 'success'
                    GROUP BY unnest(designations)
                    ORDER BY count DESC
                    LIMIT 10
                """)

                return {
                    'market_stats': dict(stats) if stats else {},
                    'top_designations': [dict(row) for row in designations],
                    'analysis_date': datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to analyze market data: {e}")
            return {}


class FinancialAdvisorProcessor:
    """Main processor for financial advisor email processing"""

    def __init__(self, postgres_client: Optional[EnhancedPostgreSQLClient] = None):
        self.extractor = FinancialPatternExtractor(postgres_client)
        self.postgres_client = postgres_client

    async def process_advisor_email(
        self,
        email_content: str,
        extracted_data: ExtractedData,
        email_id: Optional[str] = None
    ) -> Tuple[ExtractedData, Dict[str, Any]]:
        """Process financial advisor email with enhanced pattern extraction"""

        # Enhance extracted data with financial metrics
        enhanced_data = await self.extractor.enhance_extracted_data(
            extracted_data, email_content
        )

        # Extract raw financial metrics for database storage
        financial_metrics = self.extractor.extract_financial_metrics(email_content)

        # Store patterns in database if email_id provided
        pattern_ids = []
        if email_id and self.postgres_client:
            pattern_ids = await self.extractor.store_financial_patterns(
                email_id, email_content, financial_metrics
            )

        # Prepare metadata for response
        metadata = {
            'financial_metrics': financial_metrics,
            'pattern_ids': pattern_ids,
            'processing_timestamp': datetime.now().isoformat(),
            'patterns_extracted': len(financial_metrics.get('raw_patterns', []))
        }

        logger.info(f"Processed advisor email with {len(pattern_ids)} patterns stored")

        return enhanced_data, metadata

    async def update_database_record(
        self,
        email_id: str,
        financial_metrics: Dict[str, Any]
    ) -> bool:
        """Update database record with extracted financial metrics"""
        if not self.postgres_client:
            return False

        try:
            await self.postgres_client.init_pool()

            async with self.postgres_client.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE email_processing_history
                    SET
                        financial_metrics = $2,
                        aum_amount = $3,
                        production_amount = $4,
                        compensation_low = $5,
                        compensation_high = $6,
                        years_experience = $7,
                        has_series_7 = $8,
                        has_series_65 = $9,
                        has_series_66 = $10,
                        has_cfa = $11,
                        has_cfp = $12,
                        designations = $13,
                        licenses = $14,
                        achievements = $15,
                        performance_percentages = $16,
                        extracted_patterns = $17
                    WHERE id = $1
                """,
                    email_id,
                    json.dumps(financial_metrics),
                    financial_metrics.get('aum_amount'),
                    financial_metrics.get('production_amount'),
                    financial_metrics.get('compensation_low'),
                    financial_metrics.get('compensation_high'),
                    financial_metrics.get('years_experience'),
                    financial_metrics.get('has_series_7', False),
                    financial_metrics.get('has_series_65', False),
                    financial_metrics.get('has_series_66', False),
                    financial_metrics.get('has_cfa', False),
                    financial_metrics.get('has_cfp', False),
                    financial_metrics.get('designations', []),
                    financial_metrics.get('licenses', []),
                    financial_metrics.get('achievements', []),
                    financial_metrics.get('performance_percentages', []),
                    json.dumps(financial_metrics.get('raw_patterns', []))
                )

            logger.info(f"Updated database record {email_id} with financial metrics")
            return True

        except Exception as e:
            logger.error(f"Failed to update database record {email_id}: {e}")
            return False


# Export main classes
__all__ = [
    'FinancialPatternExtractor',
    'FinancialAdvisorProcessor'
]