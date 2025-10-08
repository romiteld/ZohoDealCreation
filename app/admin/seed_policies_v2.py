#!/usr/bin/env python3
"""
Bulletproof Policy Seeding System v2
Generates and manages critical policy data for recruitment system
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.integrations import PostgreSQLClient
from well_shared.cache.redis_manager import RedisCacheManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PolicySeeder:
    """Manages policy generation and seeding for recruitment system."""
    
    # National firm indicators
    NATIONAL_FIRMS = {
        'lpl', 'lpl financial', 'raymond james', 'ameriprise', 'edward jones', 
        'wells fargo', 'morgan stanley', 'merrill lynch', 'ubs', 'charles schwab',
        'fidelity', 'vanguard', 'northwestern mutual', 'massmutual', 'prudential',
        'goldman sachs', 'jpmorgan', 'jp morgan', 'j.p. morgan', 'bank of america',
        'citigroup', 'deutsche bank', 'credit suisse', 'barclays', 'rbc',
        'td ameritrade', 'e*trade', 'etrade', 'franklin templeton'
    }
    
    # Major US metro area mappings
    METRO_MAPPINGS = {
        # NYC Metro
        'manhattan': 'NYC Metro', 'brooklyn': 'NYC Metro', 'queens': 'NYC Metro',
        'bronx': 'NYC Metro', 'staten island': 'NYC Metro', 'new york': 'NYC Metro',
        'new york city': 'NYC Metro', 'nyc': 'NYC Metro', 'newark': 'NYC Metro',
        'jersey city': 'NYC Metro', 'hoboken': 'NYC Metro', 'white plains': 'NYC Metro',
        'yonkers': 'NYC Metro', 'new rochelle': 'NYC Metro', 'stamford': 'NYC Metro',
        
        # LA Metro
        'los angeles': 'LA Metro', 'beverly hills': 'LA Metro', 'santa monica': 'LA Metro',
        'pasadena': 'LA Metro', 'long beach': 'LA Metro', 'glendale': 'LA Metro',
        'burbank': 'LA Metro', 'torrance': 'LA Metro', 'anaheim': 'LA Metro',
        'irvine': 'LA Metro', 'newport beach': 'LA Metro',
        
        # Chicago Metro
        'chicago': 'Chicago Metro', 'evanston': 'Chicago Metro', 'oak park': 'Chicago Metro',
        'schaumburg': 'Chicago Metro', 'naperville': 'Chicago Metro', 'aurora': 'Chicago Metro',
        'joliet': 'Chicago Metro', 'arlington heights': 'Chicago Metro',
        
        # SF Bay Area
        'san francisco': 'SF Bay Area', 'oakland': 'SF Bay Area', 'san jose': 'SF Bay Area',
        'berkeley': 'SF Bay Area', 'palo alto': 'SF Bay Area', 'mountain view': 'SF Bay Area',
        'sunnyvale': 'SF Bay Area', 'fremont': 'SF Bay Area', 'hayward': 'SF Bay Area',
        'san mateo': 'SF Bay Area', 'redwood city': 'SF Bay Area', 'menlo park': 'SF Bay Area',
        
        # Boston Metro
        'boston': 'Boston Metro', 'cambridge': 'Boston Metro', 'somerville': 'Boston Metro',
        'brookline': 'Boston Metro', 'newton': 'Boston Metro', 'quincy': 'Boston Metro',
        'waltham': 'Boston Metro', 'lexington': 'Boston Metro',
        
        # DC Metro
        'washington': 'DC Metro', 'washington dc': 'DC Metro', 'washington d.c.': 'DC Metro',
        'arlington': 'DC Metro', 'alexandria': 'DC Metro', 'bethesda': 'DC Metro',
        'silver spring': 'DC Metro', 'rockville': 'DC Metro', 'fairfax': 'DC Metro',
        'reston': 'DC Metro', 'mclean': 'DC Metro',
        
        # Miami Metro
        'miami': 'Miami Metro', 'miami beach': 'Miami Metro', 'coral gables': 'Miami Metro',
        'aventura': 'Miami Metro', 'fort lauderdale': 'Miami Metro', 'boca raton': 'Miami Metro',
        'west palm beach': 'Miami Metro', 'hollywood': 'Miami Metro',
        
        # Dallas Metro
        'dallas': 'Dallas Metro', 'fort worth': 'Dallas Metro', 'plano': 'Dallas Metro',
        'irving': 'Dallas Metro', 'richardson': 'Dallas Metro', 'frisco': 'Dallas Metro',
        'mckinney': 'Dallas Metro', 'arlington': 'Dallas Metro',
        
        # Houston Metro
        'houston': 'Houston Metro', 'the woodlands': 'Houston Metro', 'sugar land': 'Houston Metro',
        'katy': 'Houston Metro', 'pearland': 'Houston Metro', 'cypress': 'Houston Metro',
        
        # Atlanta Metro
        'atlanta': 'Atlanta Metro', 'decatur': 'Atlanta Metro', 'marietta': 'Atlanta Metro',
        'alpharetta': 'Atlanta Metro', 'sandy springs': 'Atlanta Metro', 'roswell': 'Atlanta Metro',
        
        # Phoenix Metro
        'phoenix': 'Phoenix Metro', 'scottsdale': 'Phoenix Metro', 'tempe': 'Phoenix Metro',
        'mesa': 'Phoenix Metro', 'chandler': 'Phoenix Metro', 'glendale': 'Phoenix Metro',
        
        # Seattle Metro
        'seattle': 'Seattle Metro', 'bellevue': 'Seattle Metro', 'redmond': 'Seattle Metro',
        'tacoma': 'Seattle Metro', 'kirkland': 'Seattle Metro', 'renton': 'Seattle Metro',
        
        # Philadelphia Metro
        'philadelphia': 'Philadelphia Metro', 'philly': 'Philadelphia Metro',
        'cherry hill': 'Philadelphia Metro', 'king of prussia': 'Philadelphia Metro',
        'wilmington': 'Philadelphia Metro',
        
        # Denver Metro
        'denver': 'Denver Metro', 'aurora': 'Denver Metro', 'lakewood': 'Denver Metro',
        'littleton': 'Denver Metro', 'boulder': 'Denver Metro',
        
        # Minneapolis Metro
        'minneapolis': 'Minneapolis Metro', 'st paul': 'Minneapolis Metro', 
        'saint paul': 'Minneapolis Metro', 'bloomington': 'Minneapolis Metro',
        'minnetonka': 'Minneapolis Metro', 'edina': 'Minneapolis Metro',
        
        # San Diego Metro
        'san diego': 'San Diego Metro', 'la jolla': 'San Diego Metro', 
        'carlsbad': 'San Diego Metro', 'oceanside': 'San Diego Metro',
        
        # Detroit Metro
        'detroit': 'Detroit Metro', 'dearborn': 'Detroit Metro', 'troy': 'Detroit Metro',
        'southfield': 'Detroit Metro', 'ann arbor': 'Detroit Metro',
        
        # Portland Metro
        'portland': 'Portland Metro', 'beaverton': 'Portland Metro', 'hillsboro': 'Portland Metro',
        'gresham': 'Portland Metro', 'lake oswego': 'Portland Metro',
        
        # Las Vegas Metro
        'las vegas': 'Las Vegas Metro', 'henderson': 'Las Vegas Metro', 
        'north las vegas': 'Las Vegas Metro', 'summerlin': 'Las Vegas Metro'
    }
    
    # Subject line variants with template strings
    SUBJECT_VARIANTS = {
        'v1': '🎯 Weekly Talent Update - {date}',
        'v2': 'Your Curated Candidates - {date}',
        'v3': '📊 TalentWell Weekly Digest',
        'v4': 'Steve - New Talent Matches Available',
        'v5': 'Weekly Recruiting Pipeline Update'
    }
    
    # Selector priors (tau_delta, alpha, beta)
    SELECTOR_PRIORS = {
        'mobility': (0.30, 5, 3),      # High volatility
        'compensation': (0.28, 5, 3),   # High volatility
        'location': (0.35, 4, 3),       # Very high volatility
        'licenses': (0.55, 2, 6),       # Low volatility
        'achievements': (0.40, 3, 4)    # Medium volatility
    }
    
    def __init__(self):
        """Initialize policy seeder with database and Redis connections."""
        self.pg_client = None
        self.redis_client = None
        self.initialized = False
        
    async def initialize(self):
        """Initialize database and Redis connections."""
        try:
            # Initialize PostgreSQL
            connection_string = os.getenv('DATABASE_URL')
            if not connection_string:
                raise ValueError("DATABASE_URL not found in environment")
            
            self.pg_client = PostgreSQLClient(connection_string)
            await self.pg_client.init_pool()
            await self.pg_client.ensure_tables()
            logger.info("PostgreSQL initialized")
            
            # Initialize Redis
            redis_connection_string = os.getenv('AZURE_REDIS_CONNECTION_STRING')
            if redis_connection_string:
                self.redis_client = RedisCacheManager(redis_connection_string)
                await self.redis_client.connect()
                if self.redis_client._connected:
                    logger.info("Redis initialized")
                else:
                    logger.warning("Redis connection failed, continuing without Redis")
                    self.redis_client = None
            else:
                logger.warning("AZURE_REDIS_CONNECTION_STRING not found, continuing without Redis")
                
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize connections: {e}")
            raise
            
    async def clear_redis_policies(self):
        """Clear existing policy keys from Redis."""
        if not self.redis_client or not self.redis_client._connected:
            logger.warning("Redis not available, skipping clear")
            return 0
            
        try:
            patterns = [
                'policy:employers:*',
                'geo:metro:*',
                'bandit:subjects:global:*',
                'c3:tau:*',
                'ttl:*'
            ]
            
            deleted_count = 0
            for pattern in patterns:
                cursor = 0
                while True:
                    cursor, keys = await self.redis_client.client.scan(
                        cursor, match=pattern, count=100
                    )
                    if keys:
                        await self.redis_client.client.delete(*keys)
                        deleted_count += len(keys)
                    if cursor == 0:
                        break
                        
            logger.info(f"Cleared {deleted_count} existing policy keys from Redis")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to clear Redis policies: {e}")
            return 0
            
    async def seed_employer_policies(self) -> int:
        """Seed employer normalization policies."""
        count = 0
        
        try:
            # Get existing deals from database to analyze employers
            query = """
            SELECT DISTINCT firm_name 
            FROM deals 
            WHERE firm_name IS NOT NULL 
            ORDER BY firm_name
            """
            
            async with self.pg_client.pool.acquire() as conn:
                rows = await conn.fetch(query)
                
                for row in rows:
                    firm_name = row['firm_name']
                    if not firm_name:
                        continue
                        
                    # Classify firm type
                    firm_lower = firm_name.lower().strip()
                    is_national = any(
                        national in firm_lower 
                        for national in self.NATIONAL_FIRMS
                    )
                    firm_type = 'National firm' if is_national else 'Independent firm'
                    
                    # Store in PostgreSQL
                    upsert_query = """
                    INSERT INTO policy_employers (company_name, firm_type)
                    VALUES ($1, $2)
                    ON CONFLICT (company_name) 
                    DO UPDATE SET firm_type = EXCLUDED.firm_type
                    RETURNING id
                    """
                    
                    await conn.execute(upsert_query, firm_name, firm_type)
                    
                    # Store in Redis (no TTL)
                    if self.redis_client and self.redis_client._connected:
                        redis_key = f'policy:employers:{firm_name.lower()}'
                        await self.redis_client.client.set(
                            redis_key, 
                            firm_type,
                            ex=None  # No expiration
                        )
                    
                    count += 1
                    
            # Add default national firms not in data
            for firm in self.NATIONAL_FIRMS:
                if ' ' in firm:  # Only add multi-word firm names
                    proper_name = firm.title()
                    
                    # Store in PostgreSQL
                    async with self.pg_client.pool.acquire() as conn:
                        upsert_query = """
                        INSERT INTO policy_employers (company_name, firm_type)
                        VALUES ($1, $2)
                        ON CONFLICT (company_name) 
                        DO UPDATE SET firm_type = EXCLUDED.firm_type
                        """
                        await conn.execute(upsert_query, proper_name, 'National firm')
                    
                    # Store in Redis
                    if self.redis_client and self.redis_client._connected:
                        redis_key = f'policy:employers:{firm.lower()}'
                        await self.redis_client.client.set(
                            redis_key,
                            'National firm',
                            ex=None
                        )
                    
                    count += 1
                    
            logger.info(f"Seeded {count} employer policies")
            return count
            
        except Exception as e:
            logger.error(f"Failed to seed employer policies: {e}")
            return count
            
    async def seed_city_policies(self) -> int:
        """Seed city to metro area mapping policies."""
        count = 0
        
        try:
            # Store all metro mappings
            for city, metro in self.METRO_MAPPINGS.items():
                # Store in PostgreSQL
                async with self.pg_client.pool.acquire() as conn:
                    upsert_query = """
                    INSERT INTO policy_city_context (city, metro_area)
                    VALUES ($1, $2)
                    ON CONFLICT (city) 
                    DO UPDATE SET metro_area = EXCLUDED.metro_area
                    """
                    await conn.execute(upsert_query, city.title(), metro)
                
                # Store in Redis (no TTL)
                if self.redis_client and self.redis_client._connected:
                    redis_key = f'geo:metro:{city.lower()}'
                    await self.redis_client.client.set(
                        redis_key,
                        metro,
                        ex=None
                    )
                
                count += 1
                
            # Also get unique locations from deals
            query = """
            SELECT DISTINCT location 
            FROM deals 
            WHERE location IS NOT NULL 
            ORDER BY location
            """
            
            async with self.pg_client.pool.acquire() as conn:
                rows = await conn.fetch(query)
                
                for row in rows:
                    location = row['location']
                    if not location:
                        continue
                    
                    # Check if already mapped
                    location_lower = location.lower().strip()
                    if location_lower not in self.METRO_MAPPINGS:
                        # Default to standalone metro
                        metro = f"{location} Metro"
                        
                        # Store in PostgreSQL
                        upsert_query = """
                        INSERT INTO policy_city_context (city, metro_area)
                        VALUES ($1, $2)
                        ON CONFLICT (city) 
                        DO UPDATE SET metro_area = EXCLUDED.metro_area
                        """
                        await conn.execute(upsert_query, location, metro)
                        
                        # Store in Redis
                        if self.redis_client and self.redis_client._connected:
                            redis_key = f'geo:metro:{location_lower}'
                            await self.redis_client.client.set(
                                redis_key,
                                metro,
                                ex=None
                            )
                        
                        count += 1
                        
            logger.info(f"Seeded {count} city context policies")
            return count
            
        except Exception as e:
            logger.error(f"Failed to seed city policies: {e}")
            return count
            
    async def seed_subject_priors(self) -> int:
        """Seed subject line bandit priors based on meeting engagement."""
        count = 0
        
        try:
            # Calculate engagement priors from meetings data
            query = """
            SELECT 
                COUNT(*) as total_meetings,
                SUM(CASE WHEN email_opened = true THEN 1 ELSE 0 END) as opened,
                SUM(CASE WHEN link_clicked = true THEN 1 ELSE 0 END) as clicked
            FROM meetings
            WHERE start_datetime >= NOW() - INTERVAL '90 days'
            """
            
            async with self.pg_client.pool.acquire() as conn:
                row = await conn.fetchrow(query)
                
                # Calculate base priors from engagement
                if row and row['total_meetings'] > 0:
                    # Base alpha/beta from actual engagement rates
                    open_rate = (row['opened'] or 0) / row['total_meetings']
                    click_rate = (row['clicked'] or 0) / row['total_meetings']
                    
                    # Convert to beta distribution parameters
                    # Higher alpha = more successes, higher beta = more failures
                    base_alpha = max(1, int(open_rate * 10))
                    base_beta = max(1, int((1 - open_rate) * 10))
                else:
                    # Default uninformed priors
                    base_alpha = 1
                    base_beta = 1
                    
                # Seed each subject variant
                for variant_id, template in self.SUBJECT_VARIANTS.items():
                    # Adjust priors based on variant characteristics
                    if 'Talent' in template:
                        # Professional variants get boost
                        alpha = base_alpha + 2
                        beta = base_beta
                    elif '🎯' in template or '📊' in template:
                        # Emoji variants are riskier
                        alpha = base_alpha
                        beta = base_beta + 1
                    elif 'Steve' in template:
                        # Personalized gets boost
                        alpha = base_alpha + 3
                        beta = base_beta
                    else:
                        # Neutral variants
                        alpha = base_alpha + 1
                        beta = base_beta
                        
                    # Store in PostgreSQL
                    upsert_query = """
                    INSERT INTO policy_subject_priors (
                        audience, variant_id, text_template, alpha, beta
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (audience, variant_id) 
                    DO UPDATE SET 
                        text_template = EXCLUDED.text_template,
                        alpha = EXCLUDED.alpha,
                        beta = EXCLUDED.beta
                    """
                    
                    await conn.execute(
                        upsert_query,
                        'global',  # Default to global audience
                        variant_id,
                        template,
                        alpha,
                        beta
                    )
                    
                    # Store in Redis (no TTL)
                    if self.redis_client and self.redis_client._connected:
                        redis_key = f'bandit:subjects:global:{variant_id}'
                        redis_value = json.dumps({
                            'template': template,
                            'alpha': alpha,
                            'beta': beta,
                            'last_updated': datetime.now(timezone.utc).isoformat()
                        })
                        await self.redis_client.client.set(
                            redis_key,
                            redis_value,
                            ex=None
                        )
                    
                    count += 1
                    
            logger.info(f"Seeded {count} subject line priors")
            return count
            
        except Exception as e:
            logger.error(f"Failed to seed subject priors: {e}")
            return count
            
    async def seed_selector_priors(self) -> int:
        """Seed selector TTL and C³ priors."""
        count = 0
        
        try:
            for selector, (tau_delta, alpha, beta) in self.SELECTOR_PRIORS.items():
                # Store in PostgreSQL
                async with self.pg_client.pool.acquire() as conn:
                    upsert_query = """
                    INSERT INTO policy_selector_priors (
                        selector, tau_delta, bdat_alpha, bdat_beta
                    )
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (selector) 
                    DO UPDATE SET 
                        tau_delta = EXCLUDED.tau_delta,
                        bdat_alpha = EXCLUDED.bdat_alpha,
                        bdat_beta = EXCLUDED.bdat_beta
                    """
                    
                    await conn.execute(
                        upsert_query,
                        selector,
                        tau_delta,
                        alpha,
                        beta
                    )
                
                # Store in Redis (no TTL)
                if self.redis_client and self.redis_client._connected:
                    # C³ tau parameter
                    tau_key = f'c3:tau:{selector}'
                    await self.redis_client.client.set(
                        tau_key,
                        str(tau_delta),
                        ex=None
                    )
                    
                    # TTL parameters
                    ttl_key = f'ttl:{selector}'
                    ttl_value = json.dumps({
                        'alpha': alpha,
                        'beta': beta
                    })
                    await self.redis_client.client.set(
                        ttl_key,
                        ttl_value,
                        ex=None
                    )
                
                count += 1
                
            logger.info(f"Seeded {count} selector priors")
            return count
            
        except Exception as e:
            logger.error(f"Failed to seed selector priors: {e}")
            return count
            
    async def reload_from_database(self) -> Dict[str, int]:
        """Reload all policies from database to Redis."""
        if not self.redis_client or not self.redis_client._connected:
            logger.warning("Redis not available for reload")
            return {'employers': 0, 'cities': 0, 'subjects': 0, 'selectors': 0}
            
        counts = {'employers': 0, 'cities': 0, 'subjects': 0, 'selectors': 0}
        
        try:
            # Clear existing Redis policies first
            await self.clear_redis_policies()
            
            # Reload employers
            query = "SELECT company_name, firm_type FROM policy_employers"
            async with self.pg_client.pool.acquire() as conn:
                rows = await conn.fetch(query)
                for row in rows:
                    redis_key = f"policy:employers:{row['company_name'].lower()}"
                    await self.redis_client.client.set(
                        redis_key,
                        row['firm_type'],
                        ex=None
                    )
                    counts['employers'] += 1
                    
            # Reload cities
            query = "SELECT city, metro_area FROM policy_city_context"
            async with self.pg_client.pool.acquire() as conn:
                rows = await conn.fetch(query)
                for row in rows:
                    redis_key = f"geo:metro:{row['city'].lower()}"
                    await self.redis_client.client.set(
                        redis_key,
                        row['metro_area'],
                        ex=None
                    )
                    counts['cities'] += 1
                    
            # Reload subject priors
            query = """
            SELECT audience, variant_id, text_template, alpha, beta 
            FROM policy_subject_priors
            """
            async with self.pg_client.pool.acquire() as conn:
                rows = await conn.fetch(query)
                for row in rows:
                    redis_key = f"bandit:subjects:{row['audience']}:{row['variant_id']}"
                    redis_value = json.dumps({
                        'template': row['text_template'],
                        'alpha': row['alpha'],
                        'beta': row['beta'],
                        'last_updated': datetime.now(timezone.utc).isoformat()
                    })
                    await self.redis_client.client.set(
                        redis_key,
                        redis_value,
                        ex=None
                    )
                    counts['subjects'] += 1
                    
            # Reload selector priors
            query = """
            SELECT selector, tau_delta, bdat_alpha, bdat_beta 
            FROM policy_selector_priors
            """
            async with self.pg_client.pool.acquire() as conn:
                rows = await conn.fetch(query)
                for row in rows:
                    # C³ tau
                    tau_key = f"c3:tau:{row['selector']}"
                    await self.redis_client.client.set(
                        tau_key,
                        str(row['tau_delta']),
                        ex=None
                    )
                    
                    # TTL parameters
                    ttl_key = f"ttl:{row['selector']}"
                    ttl_value = json.dumps({
                        'alpha': row['bdat_alpha'],
                        'beta': row['bdat_beta']
                    })
                    await self.redis_client.client.set(
                        ttl_key,
                        ttl_value,
                        ex=None
                    )
                    counts['selectors'] += 1
                    
            logger.info(f"Reloaded policies from database: {counts}")
            return counts
            
        except Exception as e:
            logger.error(f"Failed to reload from database: {e}")
            return counts
            
    async def seed_all(self) -> Dict[str, int]:
        """Seed all policies to database and Redis."""
        if not self.initialized:
            await self.initialize()
            
        results = {
            'employers': 0,
            'cities': 0,
            'subjects': 0,
            'selectors': 0
        }
        
        try:
            # Clear existing Redis policies
            await self.clear_redis_policies()
            
            # Seed each policy type
            results['employers'] = await self.seed_employer_policies()
            results['cities'] = await self.seed_city_policies()
            results['subjects'] = await self.seed_subject_priors()
            results['selectors'] = await self.seed_selector_priors()
            
            logger.info(f"Policy seeding complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to seed all policies: {e}")
            return results
            
    async def close(self):
        """Close database and Redis connections."""
        if self.pg_client and self.pg_client.pool:
            await self.pg_client.pool.close()
            
        if self.redis_client:
            await self.redis_client.disconnect()
            

async def main():
    """Main entry point for policy seeding."""
    seeder = PolicySeeder()
    
    try:
        # Initialize connections
        await seeder.initialize()
        
        # Check command line arguments
        import sys
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()
            
            if command == 'reload':
                # Reload from database to Redis
                results = await seeder.reload_from_database()
                print(f"Reloaded policies: {json.dumps(results, indent=2)}")
                
            elif command == 'clear':
                # Clear Redis policies only
                count = await seeder.clear_redis_policies()
                print(f"Cleared {count} Redis policy keys")
                
            else:
                print(f"Unknown command: {command}")
                print("Usage: seed_policies_v2.py [reload|clear]")
        else:
            # Default: seed all policies
            results = await seeder.seed_all()
            print(f"Seeding complete: {json.dumps(results, indent=2)}")
            
    except Exception as e:
        logger.error(f"Policy seeding failed: {e}")
        sys.exit(1)
        
    finally:
        await seeder.close()
        

if __name__ == "__main__":
    asyncio.run(main())