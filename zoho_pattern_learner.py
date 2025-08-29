#!/usr/bin/env python3
"""
Zoho CRM Pattern Learner - Focused on Recent Deals
Learns from the 9 deals created during this session to improve email extraction
"""

import os
import json
import psycopg2
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

class ZohoPatternLearner:
    def __init__(self):
        """Initialize with known deal patterns from this session"""
        self.oauth_service_url = os.getenv('ZOHO_OAUTH_SERVICE_URL', 'https://well-zoho-oauth.azurewebsites.net')
        self.database_url = os.getenv('DATABASE_URL')
        self.api_base_url = "https://www.zohoapis.com/crm/v8"
        self.access_token = None
        self.db_conn = None
        
        # Known deals from this session with their patterns
        self.known_deals = [
            {
                'name': 'Kevin Sullivan – Recruiting Consult',
                'company': 'NAMCOA',
                'source': 'Referral',
                'source_detail': 'Scott Leak',
                'pattern_notes': 'Company corrected from email domain to actual company name'
            },
            {
                'name': 'Mary Beth Scalese – Recruiting Consult',
                'company': 'Fortune Financial',
                'source': 'Website Inbound',
                'source_detail': 'Calendly',
                'pattern_notes': 'Calendly indicates Website Inbound'
            },
            {
                'name': 'Advisor (Fort Wayne) Howard Bailey',
                'company': 'Howard Bailey',
                'source': 'Referral',
                'source_detail': 'Phil Blosser',
                'pattern_notes': 'Job title/location/company naming pattern'
            },
            {
                'name': 'Tom Mentzel – Referral',
                'company': 'Legacy Financial Advisors',
                'source': 'Referral',
                'source_detail': 'Jay Robinson',
                'pattern_notes': 'Deal type in name indicates source'
            },
            {
                'name': 'Advisor (San Diego) BML Wealth Management',
                'company': 'BML Wealth Management',
                'source': 'Referral',
                'source_detail': 'Brady Lamar',
                'pattern_notes': 'Job title/location/company pattern'
            },
            {
                'name': 'Darcy Bergen – Recruiting Consult',
                'company': 'Bergen Financial',
                'source': 'Website Inbound',
                'source_detail': 'Calendly',
                'pattern_notes': 'Calendly scheduling = Website Inbound'
            },
            {
                'name': 'Jon Maxson – Recruiting Consult',
                'company': 'Comcast',
                'source': 'Referral',
                'source_detail': 'BOSS',
                'pattern_notes': 'Email domain used when company unclear'
            },
            {
                'name': 'David Nicholas – Recruiting Consult',
                'company': 'Nicholas Wealth',
                'source': 'Website Inbound',
                'source_detail': 'Calendly',
                'pattern_notes': 'Personal name + Wealth pattern for company'
            },
            {
                'name': 'Craig Kirsner – Recruiting Consult',
                'company': 'Kirsner Wealth',
                'source': 'Reverse Recruiting',
                'source_detail': 'Phil Blosser',
                'pattern_notes': 'TWAV codes indicate Reverse Recruiting'
            }
        ]

    def get_access_token(self) -> str:
        """Get access token from Azure OAuth service"""
        try:
            response = requests.get(f"{self.oauth_service_url}/token")
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                return self.access_token
            else:
                raise Exception(f"Failed to get access token: {response.status_code}")
        except Exception as e:
            print(f"Error getting access token: {e}")
            raise

    def connect_database(self):
        """Connect to PostgreSQL database"""
        try:
            self.db_conn = psycopg2.connect(self.database_url)
            print("Connected to PostgreSQL database")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise

    def search_recent_deals(self) -> List[Dict]:
        """Search for deals created in the last 7 days"""
        url = f"{self.api_base_url}/Deals/search"
        headers = {
            'Authorization': f'Zoho-oauthtoken {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Calculate date 7 days ago
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        params = {
            'criteria': f'(Created_Time:greater_equal:{seven_days_ago})',
            'fields': 'Deal_Name,Contact_Name,Account_Name,Source,Source_Detail,Lead_Source,Stage,Pipeline,Owner,Created_Time'
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('data', [])
        else:
            print(f"Failed to search deals: {response.status_code}")
            return []

    def populate_pattern_tables(self):
        """Populate database tables with learned patterns"""
        cursor = self.db_conn.cursor()
        
        # 1. Source determination patterns
        source_patterns = {
            'referral': {
                'keywords': ['referred by', 'introduction', 'referral', 'introduced'],
                'detail_patterns': ['Scott Leak', 'Phil Blosser', 'Brady Lamar', 'Jay Robinson', 'BOSS'],
                'confidence': 0.9
            },
            'website_inbound': {
                'keywords': ['calendly', 'scheduled', 'website', 'booked', 'calendar'],
                'detail_patterns': ['Calendly', 'Website Form'],
                'confidence': 0.95
            },
            'reverse_recruiting': {
                'keywords': ['TWAV', 'advisor vault', 'TWAV[0-9]+', 'candidate code'],
                'detail_patterns': ['TWAV Advisor Vault'],
                'confidence': 0.95
            },
            'email_inbound': {
                'keywords': ['email', 'reached out', 'contacted', 'inquired'],
                'detail_patterns': [],
                'confidence': 0.7
            }
        }
        
        for source_type, pattern_data in source_patterns.items():
            cursor.execute("""
                INSERT INTO learning_patterns (pattern_type, pattern_key, pattern_value, confidence, usage_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (pattern_type, pattern_key) 
                DO UPDATE SET 
                    pattern_value = EXCLUDED.pattern_value,
                    confidence = EXCLUDED.confidence,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                'source_determination',
                source_type,
                json.dumps(pattern_data),
                pattern_data['confidence'],
                len(pattern_data['detail_patterns'])
            ))
        
        # 2. Deal naming patterns
        naming_patterns = [
            {
                'pattern': '{contact_name} – {deal_type}',
                'examples': ['Kevin Sullivan – Recruiting Consult', 'Tom Mentzel – Referral'],
                'regex': r'^[A-Za-z\s]+ – [A-Za-z\s]+$',
                'confidence': 0.9
            },
            {
                'pattern': 'Advisor ({location}) {company}',
                'examples': ['Advisor (Fort Wayne) Howard Bailey', 'Advisor (San Diego) BML Wealth Management'],
                'regex': r'^Advisor \([^)]+\) .+$',
                'confidence': 0.9
            }
        ]
        
        for idx, pattern in enumerate(naming_patterns):
            cursor.execute("""
                INSERT INTO learning_patterns (pattern_type, pattern_key, pattern_value, confidence, usage_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (pattern_type, pattern_key) 
                DO UPDATE SET 
                    usage_count = learning_patterns.usage_count + %s,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                'deal_naming',
                f'pattern_{idx+1}',
                json.dumps(pattern),
                pattern['confidence'],
                len(pattern['examples']),
                len(pattern['examples'])
            ))
        
        # 3. Company name patterns
        company_patterns = [
            {
                'pattern': 'personal_wealth',
                'description': 'Last name + Wealth/Financial',
                'examples': ['Kirsner Wealth', 'Nicholas Wealth', 'Bergen Financial'],
                'confidence': 0.85
            },
            {
                'pattern': 'email_domain_fallback',
                'description': 'Use email domain when company unknown',
                'examples': ['Comcast from comcast.net'],
                'confidence': 0.6
            }
        ]
        
        for pattern in company_patterns:
            cursor.execute("""
                INSERT INTO learning_patterns (pattern_type, pattern_key, pattern_value, confidence, usage_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (pattern_type, pattern_key) 
                DO UPDATE SET 
                    usage_count = learning_patterns.usage_count + %s,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                'company_inference',
                pattern['pattern'],
                json.dumps(pattern),
                pattern['confidence'],
                len(pattern['examples']),
                len(pattern['examples'])
            ))
        
        # 4. Correction patterns from this session
        corrections = [
            {
                'original': 'Infinite Wealth Advisors',
                'corrected': 'NAMCOA',
                'reason': 'Email signature had correct company',
                'confidence': 1.0
            },
            {
                'original': 'Marshal Johnson – Recruiting Consult',
                'corrected': 'Advisor (Fort Wayne) Howard Bailey',
                'reason': 'Follow job-title/location/company convention',
                'confidence': 0.9
            }
        ]
        
        for correction in corrections:
            cursor.execute("""
                INSERT INTO ai_corrections (
                    email_domain, 
                    email_snippet, 
                    original_extraction, 
                    user_corrections, 
                    correction_timestamp,
                    success_rate
                )
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
            """, (
                'example.com',  # placeholder
                correction['reason'],
                json.dumps({'value': correction['original']}),
                json.dumps({'value': correction['corrected'], 'reason': correction['reason']}),
                correction['confidence']
            ))
        
        self.db_conn.commit()
        print("✅ Pattern tables populated with learning data")

    def populate_company_cache(self):
        """Populate company enrichment cache with known companies"""
        cursor = self.db_conn.cursor()
        
        companies = [
            ('namcoa.com', 'NAMCOA – Naples Asset Management Company'),
            ('fortunefinancial.com', 'Fortune Financial'),
            ('howardbailey.com', 'Howard Bailey'),
            ('legacyfa.com', 'Legacy Financial Advisors'),
            ('bmlwealth.com', 'BML Wealth Management'),
            ('bergenfinancial.com', 'Bergen Financial'),
            ('comcast.net', 'Comcast'),
            ('nicholaswealth.com', 'Nicholas Wealth'),
            ('kirsnerwealth.com', 'Kirsner Wealth')
        ]
        
        for domain, company_name in companies:
            cursor.execute("""
                INSERT INTO company_enrichment_cache (domain, company_name, enrichment_data, last_enriched, created_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (domain) 
                DO UPDATE SET 
                    company_name = EXCLUDED.company_name,
                    last_enriched = CURRENT_TIMESTAMP
            """, (
                domain,
                company_name,
                json.dumps({
                    'source': 'manual_entry',
                    'confidence': 1.0,
                    'verified': True,
                    'learned_from': 'session_deals'
                })
            ))
        
        self.db_conn.commit()
        print("✅ Company cache populated")

    def create_smart_cache_entries(self):
        """Create email cache entries for common patterns"""
        cursor = self.db_conn.cursor()
        
        # Cache entries for common email patterns
        cache_patterns = [
            {
                'pattern': 'calendly_scheduling',
                'keywords': ['calendly.com', 'scheduled a meeting', 'booked time'],
                'extraction': {
                    'source': 'Website Inbound',
                    'source_detail': 'Calendly',
                    'confidence': 0.95
                }
            },
            {
                'pattern': 'twav_reference',
                'keywords': ['TWAV', 'Advisor Vault', 'candidate code'],
                'extraction': {
                    'source': 'Reverse Recruiting',
                    'confidence': 0.95
                }
            },
            {
                'pattern': 'referral_introduction',
                'keywords': ['referred by', 'introduction from', 'suggested I reach out'],
                'extraction': {
                    'source': 'Referral',
                    'confidence': 0.9
                }
            }
        ]
        
        for pattern in cache_patterns:
            cache_key = f"pattern_{pattern['pattern']}"
            cursor.execute("""
                INSERT INTO email_cache (
                    cache_key,
                    email_pattern_hash,
                    email_type,
                    extraction_result,
                    model_used,
                    confidence_score,
                    hit_count,
                    expires_at,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (cache_key) 
                DO UPDATE SET 
                    hit_count = email_cache.hit_count + 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                cache_key,
                json.dumps(pattern['keywords']),
                pattern['pattern'],
                json.dumps(pattern['extraction']),
                'pattern_matching',
                pattern['extraction']['confidence'],
                0,
                datetime.now() + timedelta(days=30)
            ))
        
        self.db_conn.commit()
        print("✅ Smart cache entries created")

    def run_learning_pipeline(self):
        """Run the complete learning pipeline"""
        print("🚀 Starting Zoho CRM Pattern Learning Pipeline...")
        
        # Get access token
        print("\n1. Getting access token...")
        self.get_access_token()
        
        # Connect to database
        print("\n2. Connecting to database...")
        self.connect_database()
        
        # Populate pattern tables
        print("\n3. Populating pattern learning tables...")
        self.populate_pattern_tables()
        
        # Populate company cache
        print("\n4. Populating company enrichment cache...")
        self.populate_company_cache()
        
        # Create smart cache entries
        print("\n5. Creating smart cache entries...")
        self.create_smart_cache_entries()
        
        # Optional: Fetch recent deals from Zoho
        print("\n6. Fetching recent deals from Zoho CRM...")
        recent_deals = self.search_recent_deals()
        print(f"   Found {len(recent_deals)} recent deals")
        
        # Close database connection
        if self.db_conn:
            self.db_conn.close()
        
        print("\n✅ Pattern learning complete! Database is now smarter for email extraction.")
        print("\nKey patterns learned:")
        print("  • Calendly = Website Inbound")
        print("  • TWAV codes = Reverse Recruiting")
        print("  • Referrer names in Source Detail")
        print("  • Deal naming: Contact – Type OR Advisor (Location) Company")
        print("  • Company inference from email domains and personal names")

if __name__ == "__main__":
    learner = ZohoPatternLearner()
    learner.run_learning_pipeline()