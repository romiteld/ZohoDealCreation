"""
TalentWell policy seed generation system.
Generates global policy seeds from imported Steve Perry data.
"""

import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

from app.integrations import PostgreSQLClient
from app.redis_cache_manager import get_cache_manager

logger = logging.getLogger(__name__)


class TalentWellPolicySeeder:
    """Generate and load policy seeds for TalentWell digest system."""
    
    def __init__(self):
        self.postgres_client = PostgreSQLClient()
        self.cache_manager = None
        self.seed_dir = Path("app/policy/seed")
        
    async def initialize(self):
        """Initialize async components."""
        self.cache_manager = await get_cache_manager()
        
    async def generate_employer_normalization(self) -> Dict[str, str]:
        """Generate employer classification from deal data."""
        await self.postgres_client.init_pool()
        
        # Get all unique company names from deals
        async with self.postgres_client.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT firm_name 
                FROM deals 
                WHERE firm_name IS NOT NULL AND firm_name != ''
                ORDER BY firm_name
            """)
        
        employers = {}
        
        # National firm indicators (major brands)
        national_indicators = [
            'LPL', 'Raymond James', 'Ameriprise', 'Edward Jones',
            'Wells Fargo', 'Morgan Stanley', 'Merrill Lynch', 'Merrill',
            'UBS', 'Charles Schwab', 'Schwab', 'Fidelity', 'Vanguard',
            'Northwestern Mutual', 'MassMutual', 'Prudential',
            'Goldman Sachs', 'JPMorgan', 'Bank of America', 'Citigroup',
            'Deutsche Bank', 'Credit Suisse', 'Barclays', 'RBC',
            'TD Ameritrade', 'E*Trade', 'Franklin Templeton'
        ]
        
        for row in rows:
            company = row['firm_name'].strip()
            if not company:
                continue
                
            # Check if company matches national firm indicators
            is_national = False
            company_lower = company.lower()
            
            for indicator in national_indicators:
                if indicator.lower() in company_lower:
                    is_national = True
                    break
            
            employers[company] = "National firm" if is_national else "Independent firm"
        
        logger.info(f"Generated employer classifications for {len(employers)} companies")
        return employers
    
    async def generate_city_context(self) -> Dict[str, str]:
        """Generate city to metro area mappings from deal locations."""
        await self.postgres_client.init_pool()
        
        # Get all unique locations from deals
        async with self.postgres_client.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT location 
                FROM deals 
                WHERE location IS NOT NULL AND location != ''
                ORDER BY location
            """)
        
        city_context = {}
        
        # Major metro area mappings
        metro_mappings = {
            # Northeast
            'New York': 'NYC Metro', 'Manhattan': 'NYC Metro', 'Brooklyn': 'NYC Metro',
            'Queens': 'NYC Metro', 'Bronx': 'NYC Metro', 'Staten Island': 'NYC Metro',
            'Newark': 'NYC Metro', 'Jersey City': 'NYC Metro', 'Stamford': 'NYC Metro',
            'White Plains': 'NYC Metro', 'Westchester': 'NYC Metro',
            
            'Boston': 'Boston Metro', 'Cambridge': 'Boston Metro', 'Worcester': 'Boston Metro',
            'Newton': 'Boston Metro', 'Quincy': 'Boston Metro', 'Lowell': 'Boston Metro',
            
            'Philadelphia': 'Philadelphia Metro', 'Camden': 'Philadelphia Metro',
            'Wilmington': 'Philadelphia Metro', 'Trenton': 'Philadelphia Metro',
            
            'Washington': 'DC Metro', 'Arlington': 'DC Metro', 'Alexandria': 'DC Metro',
            'Bethesda': 'DC Metro', 'Silver Spring': 'DC Metro', 'Rockville': 'DC Metro',
            'Fairfax': 'DC Metro', 'Vienna': 'DC Metro', 'McLean': 'DC Metro',
            
            # Southeast
            'Atlanta': 'Atlanta Metro', 'Marietta': 'Atlanta Metro', 'Sandy Springs': 'Atlanta Metro',
            'Roswell': 'Atlanta Metro', 'Alpharetta': 'Atlanta Metro', 'Decatur': 'Atlanta Metro',
            
            'Miami': 'Miami Metro', 'Fort Lauderdale': 'Miami Metro', 'Hollywood': 'Miami Metro',
            'Coral Gables': 'Miami Metro', 'Aventura': 'Miami Metro', 'Boca Raton': 'Miami Metro',
            
            'Charlotte': 'Charlotte Metro', 'Raleigh': 'Raleigh Metro', 'Durham': 'Raleigh Metro',
            'Cary': 'Raleigh Metro', 'Chapel Hill': 'Raleigh Metro',
            
            'Nashville': 'Nashville Metro', 'Franklin': 'Nashville Metro', 'Brentwood': 'Nashville Metro',
            'Jacksonville': 'Jacksonville Metro', 'Tampa': 'Tampa Metro', 'St. Petersburg': 'Tampa Metro',
            'Orlando': 'Orlando Metro', 'Lakeland': 'Tampa Metro',
            
            # Midwest
            'Chicago': 'Chicago Metro', 'Evanston': 'Chicago Metro', 'Oak Park': 'Chicago Metro',
            'Schaumburg': 'Chicago Metro', 'Naperville': 'Chicago Metro', 'Aurora': 'Chicago Metro',
            'Joliet': 'Chicago Metro', 'Elgin': 'Chicago Metro', 'Waukegan': 'Chicago Metro',
            
            'Detroit': 'Detroit Metro', 'Ann Arbor': 'Detroit Metro', 'Dearborn': 'Detroit Metro',
            'Troy': 'Detroit Metro', 'Warren': 'Detroit Metro', 'Sterling Heights': 'Detroit Metro',
            
            'Cleveland': 'Cleveland Metro', 'Akron': 'Cleveland Metro', 'Columbus': 'Columbus Metro',
            'Toledo': 'Toledo Metro', 'Youngstown': 'Youngstown Metro',
            
            'Milwaukee': 'Milwaukee Metro', 'Madison': 'Madison Metro', 'Green Bay': 'Green Bay Metro',
            'Minneapolis': 'Minneapolis Metro', 'St. Paul': 'Minneapolis Metro', 'Bloomington': 'Minneapolis Metro',
            
            'Indianapolis': 'Indianapolis Metro', 'Kansas City': 'Kansas City Metro',
            'St. Louis': 'St. Louis Metro', 'Cincinnati': 'Cincinnati Metro',
            
            # West
            'Los Angeles': 'LA Metro', 'Beverly Hills': 'LA Metro', 'Santa Monica': 'LA Metro',
            'Pasadena': 'LA Metro', 'Glendale': 'LA Metro', 'Burbank': 'LA Metro',
            'Long Beach': 'LA Metro', 'Anaheim': 'LA Metro', 'Irvine': 'LA Metro',
            'Newport Beach': 'LA Metro', 'Huntington Beach': 'LA Metro',
            
            'San Francisco': 'Bay Area', 'San Jose': 'Bay Area', 'Oakland': 'Bay Area',
            'Berkeley': 'Bay Area', 'Palo Alto': 'Bay Area', 'Mountain View': 'Bay Area',
            'Cupertino': 'Bay Area', 'Fremont': 'Bay Area', 'Hayward': 'Bay Area',
            'San Mateo': 'Bay Area', 'Redwood City': 'Bay Area', 'Santa Clara': 'Bay Area',
            
            'San Diego': 'San Diego Metro', 'La Jolla': 'San Diego Metro', 'Chula Vista': 'San Diego Metro',
            'Carlsbad': 'San Diego Metro', 'Oceanside': 'San Diego Metro',
            
            'Seattle': 'Seattle Metro', 'Bellevue': 'Seattle Metro', 'Redmond': 'Seattle Metro',
            'Tacoma': 'Seattle Metro', 'Everett': 'Seattle Metro', 'Spokane': 'Spokane Metro',
            
            'Portland': 'Portland Metro', 'Beaverton': 'Portland Metro', 'Hillsboro': 'Portland Metro',
            'Gresham': 'Portland Metro', 'Lake Oswego': 'Portland Metro',
            
            'Denver': 'Denver Metro', 'Aurora': 'Denver Metro', 'Lakewood': 'Denver Metro',
            'Thornton': 'Denver Metro', 'Westminster': 'Denver Metro', 'Arvada': 'Denver Metro',
            'Boulder': 'Denver Metro', 'Fort Collins': 'Fort Collins Metro',
            
            'Phoenix': 'Phoenix Metro', 'Scottsdale': 'Phoenix Metro', 'Tempe': 'Phoenix Metro',
            'Mesa': 'Phoenix Metro', 'Chandler': 'Phoenix Metro', 'Glendale': 'Phoenix Metro',
            
            'Las Vegas': 'Las Vegas Metro', 'Henderson': 'Las Vegas Metro', 'North Las Vegas': 'Las Vegas Metro',
            'Salt Lake City': 'Salt Lake Metro', 'West Valley': 'Salt Lake Metro', 'Provo': 'Salt Lake Metro',
            
            # Southwest
            'Dallas': 'DFW Metro', 'Fort Worth': 'DFW Metro', 'Plano': 'DFW Metro',
            'Arlington': 'DFW Metro', 'Irving': 'DFW Metro', 'Garland': 'DFW Metro',
            'Grand Prairie': 'DFW Metro', 'McKinney': 'DFW Metro', 'Frisco': 'DFW Metro',
            
            'Houston': 'Houston Metro', 'Pasadena': 'Houston Metro', 'Pearland': 'Houston Metro',
            'Sugar Land': 'Houston Metro', 'Baytown': 'Houston Metro', 'Conroe': 'Houston Metro',
            'The Woodlands': 'Houston Metro', 'Katy': 'Houston Metro',
            
            'San Antonio': 'San Antonio Metro', 'Austin': 'Austin Metro', 'Round Rock': 'Austin Metro',
            'Cedar Park': 'Austin Metro', 'Pflugerville': 'Austin Metro',
            
            'Oklahoma City': 'Oklahoma City Metro', 'Tulsa': 'Tulsa Metro',
            'Little Rock': 'Little Rock Metro', 'Memphis': 'Memphis Metro',
            'New Orleans': 'New Orleans Metro', 'Baton Rouge': 'Baton Rouge Metro'
        }
        
        for row in rows:
            location = row['location'].strip()
            if not location:
                continue
            
            # Extract city from location (usually first part before comma)
            location_parts = location.split(',')
            city = location_parts[0].strip()
            
            # Find metro mapping
            metro = None
            for key, metro_area in metro_mappings.items():
                if key.lower() in city.lower():
                    metro = metro_area
                    break
            
            # Default to city name if no metro mapping found
            if not metro:
                metro = city if city else location
            
            city_context[city] = metro
        
        logger.info(f"Generated city context mappings for {len(city_context)} cities")
        return city_context
    
    async def generate_subject_bandit_priors(self) -> List[Dict[str, Any]]:
        """Generate subject line bandit priors from meeting engagement data."""
        await self.postgres_client.init_pool()
        
        # Get meeting engagement data
        async with self.postgres_client.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT title, email_opened, link_clicked
                FROM meetings
                WHERE title IS NOT NULL AND title != ''
            """)
        
        # Analyze engagement patterns
        keyword_stats = defaultdict(lambda: {'total': 0, 'opens': 0, 'clicks': 0})
        
        for row in rows:
            title = row['title'].lower()
            opened = row['email_opened']
            clicked = row['link_clicked']
            
            # Extract keywords for analysis
            keywords = []
            if 'talent' in title:
                keywords.append('talent')
            if 'candidate' in title or 'candidates' in title:
                keywords.append('candidate')
            if 'weekly' in title:
                keywords.append('weekly')
            if 'digest' in title:
                keywords.append('digest')
            if 'update' in title:
                keywords.append('update')
            if 'match' in title or 'matches' in title:
                keywords.append('match')
            
            # Update stats for each keyword
            for keyword in keywords:
                keyword_stats[keyword]['total'] += 1
                if opened:
                    keyword_stats[keyword]['opens'] += 1
                if clicked:
                    keyword_stats[keyword]['clicks'] += 1
        
        # Define subject line variants with engagement-based priors
        subjects = [
            {
                'id': 'v1',
                'text': '🎯 Weekly Talent Update - {date}',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v2', 
                'text': 'Your Curated Candidates - {date}',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v3',
                'text': '📊 TalentWell Weekly Digest',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v4',
                'text': 'Steve - New Talent Matches Available',
                'alpha': 1,
                'beta': 1
            },
            {
                'id': 'v5',
                'text': 'Weekly Recruiting Pipeline Update',
                'alpha': 1,
                'beta': 1
            }
        ]
        
        # Update priors based on historical performance
        for subject in subjects:
            text_lower = subject['text'].lower()
            
            # Boost alpha/beta based on keyword performance
            for keyword, stats in keyword_stats.items():
                if keyword in text_lower and stats['total'] > 0:
                    # Calculate engagement rate
                    open_rate = stats['opens'] / stats['total'] if stats['total'] > 0 else 0
                    click_rate = stats['clicks'] / stats['total'] if stats['total'] > 0 else 0
                    
                    # Boost alpha for good performance, beta for poor performance
                    if open_rate > 0.3:  # Good open rate
                        subject['alpha'] += int(stats['opens'] * 0.5)
                    if click_rate > 0.1:  # Good click rate
                        subject['alpha'] += int(stats['clicks'] * 1.0)
                    
                    # Add some beta for non-engaging sends
                    non_opens = stats['total'] - stats['opens']
                    subject['beta'] += int(non_opens * 0.3)
        
        logger.info(f"Generated {len(subjects)} subject line variants with engagement priors")
        return subjects
    
    async def generate_selector_priors(self) -> Dict[str, Dict[str, Any]]:
        """Generate C³ and BDAT selector priors based on edit frequency patterns."""
        await self.postgres_client.init_pool()
        
        # Get stage change frequency data as proxy for edit patterns
        async with self.postgres_client.pool.acquire() as conn:
            deal_changes = await conn.fetch("""
                SELECT deal_id, COUNT(*) as change_count
                FROM deal_stage_history
                GROUP BY deal_id
            """)
            
            total_deals = await conn.fetchval("SELECT COUNT(*) FROM deals")
        
        # Calculate average change frequency
        if total_deals == 0:
            total_deals = 1
        
        change_counts = [row['change_count'] for row in deal_changes]
        avg_changes = sum(change_counts) / len(change_counts) if change_counts else 2.0
        
        # Define selector-specific thresholds based on expected volatility
        # Higher volatility = looser tau_delta, shorter TTL
        selector_priors = {
            'mobility': {
                'tau_delta': 0.30,  # High volatility - location preferences change
                'bdat_alpha': 5,    # Moderate TTL
                'bdat_beta': 3
            },
            'compensation': {
                'tau_delta': 0.28,  # High volatility - comp expectations fluctuate
                'bdat_alpha': 5,
                'bdat_beta': 3
            },
            'location': {
                'tau_delta': 0.35,  # Very high volatility - location is fluid
                'bdat_alpha': 4,    # Shorter TTL
                'bdat_beta': 3
            },
            'licenses': {
                'tau_delta': 0.55,  # Low volatility - licenses don't change often
                'bdat_alpha': 2,    # Longer TTL
                'bdat_beta': 6
            },
            'achievements': {
                'tau_delta': 0.40,  # Medium volatility - achievements accumulate slowly
                'bdat_alpha': 3,
                'bdat_beta': 4
            }
        }
        
        # Adjust based on actual change patterns if we have data
        if change_counts and avg_changes > 3:
            # High change frequency - make all selectors more lenient
            for selector in selector_priors:
                selector_priors[selector]['tau_delta'] *= 0.8
                selector_priors[selector]['bdat_alpha'] = max(2, selector_priors[selector]['bdat_alpha'] - 1)
        
        logger.info(f"Generated selector priors for {len(selector_priors)} selectors")
        return selector_priors
    
    async def save_policy_seeds_to_files(self, policies: Dict[str, Any]):
        """Save policy seeds to JSON files."""
        self.seed_dir.mkdir(parents=True, exist_ok=True)
        
        for name, data in policies.items():
            file_path = self.seed_dir / f"{name}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Saved {name}.json with {len(data) if isinstance(data, (dict, list)) else 1} entries")
    
    async def save_policies_to_database(self, policies: Dict[str, Any]):
        """Save policy seeds to database tables."""
        await self.postgres_client.init_pool()
        
        async with self.postgres_client.pool.acquire() as conn:
            # Save employer classifications
            if 'employers' in policies:
                await conn.execute("DELETE FROM policy_employers")
                for company, firm_type in policies['employers'].items():
                    await conn.execute(
                        "INSERT INTO policy_employers (company_name, firm_type) VALUES ($1, $2)",
                        company, firm_type
                    )
                logger.info(f"Saved {len(policies['employers'])} employer policies to database")
            
            # Save city context
            if 'city_context' in policies:
                await conn.execute("DELETE FROM policy_city_context")
                for city, metro in policies['city_context'].items():
                    await conn.execute(
                        "INSERT INTO policy_city_context (city, metro_area) VALUES ($1, $2)",
                        city, metro
                    )
                logger.info(f"Saved {len(policies['city_context'])} city mappings to database")
            
            # Save subject priors
            if 'subjects' in policies:
                await conn.execute("DELETE FROM policy_subject_priors WHERE audience = 'global'")
                for subject in policies['subjects']:
                    await conn.execute(
                        """INSERT INTO policy_subject_priors 
                           (audience, variant_id, text_template, alpha, beta) 
                           VALUES ($1, $2, $3, $4, $5)""",
                        'global', subject['id'], subject['text'],
                        subject['alpha'], subject['beta']
                    )
                logger.info(f"Saved {len(policies['subjects'])} subject variants to database")
            
            # Save selector priors
            if 'selector_priors' in policies:
                await conn.execute("DELETE FROM policy_selector_priors")
                for selector, params in policies['selector_priors'].items():
                    await conn.execute(
                        """INSERT INTO policy_selector_priors 
                           (selector, tau_delta, bdat_alpha, bdat_beta) 
                           VALUES ($1, $2, $3, $4)""",
                        selector, params['tau_delta'],
                        params['bdat_alpha'], params['bdat_beta']
                    )
                logger.info(f"Saved {len(policies['selector_priors'])} selector configs to database")
    
    async def load_policies_to_redis(self, policies: Dict[str, Any]):
        """Load policy seeds into Redis with appropriate TTLs."""
        if not self.cache_manager or not self.cache_manager.client:
            logger.warning("Redis not available, skipping policy load to cache")
            return
        
        redis_client = self.cache_manager.client
        
        # Load employer policies
        if 'employers' in policies:
            for company, firm_type in policies['employers'].items():
                key = f"policy:employers:{company.lower().replace(' ', '_')}"
                await redis_client.setex(key, 86400 * 30, firm_type)  # 30-day TTL
        
        # Load city context
        if 'city_context' in policies:
            for city, metro in policies['city_context'].items():
                key = f"geo:metro:{city.lower().replace(' ', '_')}"
                await redis_client.setex(key, 86400 * 30, metro)  # 30-day TTL
        
        # Load subject bandit priors
        if 'subjects' in policies:
            for subject in policies['subjects']:
                key = f"bandit:subjects:global:{subject['id']}"
                value = json.dumps({
                    'text': subject['text'],
                    'alpha': subject['alpha'],
                    'beta': subject['beta']
                })
                await redis_client.setex(key, 86400 * 7, value)  # 7-day TTL
            
            # Store variant list
            variant_ids = [s['id'] for s in policies['subjects']]
            await redis_client.setex(
                "bandit:subjects:global:variants",
                86400 * 7,
                json.dumps(variant_ids)
            )
        
        # Load selector priors
        if 'selector_priors' in policies:
            for selector, params in policies['selector_priors'].items():
                # C³ tau values
                tau_key = f"c3:tau:{selector}"
                await redis_client.setex(tau_key, 86400 * 30, str(params['tau_delta']))
                
                # BDAT TTL parameters
                ttl_key = f"ttl:{selector}"
                ttl_value = json.dumps({
                    'alpha': params['bdat_alpha'],
                    'beta': params['bdat_beta']
                })
                await redis_client.setex(ttl_key, 86400 * 30, ttl_value)
        
        logger.info("Policy seeds loaded to Redis with appropriate TTLs")
    
    async def generate_all_policies(self) -> Dict[str, Any]:
        """Generate all policy seeds from database data."""
        await self.initialize()
        
        logger.info("Generating policy seeds from imported data...")
        
        # Generate all policy types
        employers = await self.generate_employer_normalization()
        city_context = await self.generate_city_context()
        subjects = await self.generate_subject_bandit_priors()
        selector_priors = await self.generate_selector_priors()
        
        policies = {
            'employers': employers,
            'city_context': city_context,
            'subjects': subjects,
            'selector_priors': selector_priors
        }
        
        # Save to all storage locations
        await self.save_policy_seeds_to_files(policies)
        await self.save_policies_to_database(policies)
        await self.load_policies_to_redis(policies)
        
        summary = {
            'employers': len(employers),
            'city_context': len(city_context),
            'subjects': len(subjects),
            'selector_priors': len(selector_priors),
            'generated_at': datetime.now().isoformat()
        }
        
        logger.info(f"Policy generation completed: {summary}")
        return {
            'status': 'success',
            'summary': summary,
            'policies': policies
        }


# Create singleton instance
policy_seeder = TalentWellPolicySeeder()