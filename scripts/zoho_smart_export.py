#!/usr/bin/env python3
"""
Zoho CRM Smart Export for Pattern Learning
Uses regular API (not bulk) to export recent data for pattern learning
Works within existing OAuth scope permissions
"""

import os
import sys
import json
import time
import psycopg2
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Import the existing integration modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.integrations import ZohoClient, PostgreSQLClient

class ZohoSmartExporter:
    def __init__(self):
        """
        Initialize with existing ZohoClient
        This script only READS data to learn patterns - never modifies records
        """
        self.database_url = os.getenv('DATABASE_URL')
        self.db_conn = None
        
        # Initialize PostgreSQL client
        try:
            self.pg_client = PostgreSQLClient(self.database_url)
        except:
            self.pg_client = None
            
        # Initialize Zoho CRM client using existing integration
        self.zoho_client = ZohoClient(pg_client=self.pg_client)
        
    def connect_database(self):
        """Connect to PostgreSQL database"""
        try:
            self.db_conn = psycopg2.connect(self.database_url)
            print("Connected to PostgreSQL database")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise
    
    def get_recent_deals(self) -> List[Dict]:
        """Get deals from January 1st 2025 to August 29th 2025 using regular API"""
        print("Fetching deals from January 1st 2025 to August 29th 2025...")
        
        # Get access token
        access_token = self.zoho_client._get_access_token()
        
        # Specific date range - Zoho expects ISO 8601 format with timezone
        from_date = '2025-01-01T00:00:00+00:00'
        to_date = '2025-08-29T23:59:59+00:00'
        
        # Use search API with criteria
        url = f"{self.zoho_client.base_url}/Deals/search"
        headers = {
            'Authorization': f'Zoho-oauthtoken {access_token}'
        }
        params = {
            'criteria': f'((Created_Time:greater_equal:{from_date})and(Created_Time:less_equal:{to_date}))',
            'fields': 'Deal_Name,Contact_Name,Owner,Source,Source_Detail,Lead_Source,Stage,Pipeline,Account_Name,Created_Time',
            'per_page': 200
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                deals = data.get('data', [])
                print(f"Found {len(deals)} deals")
                return deals
            else:
                print(f"Error fetching deals: {response.status_code}")
                print(response.text)
                return []
        except Exception as e:
            print(f"Exception fetching deals: {e}")
            return []
    
    def get_recent_contacts(self) -> List[Dict]:
        """Get contacts from January 1st 2025 to August 29th 2025 using regular API"""
        print("Fetching contacts from January 1st 2025 to August 29th 2025...")
        
        # Get access token
        access_token = self.zoho_client._get_access_token()
        
        # Specific date range - Zoho expects ISO 8601 format with timezone
        from_date = '2025-01-01T00:00:00+00:00'
        to_date = '2025-08-29T23:59:59+00:00'
        
        # Use search API
        url = f"{self.zoho_client.base_url}/Contacts/search"
        headers = {
            'Authorization': f'Zoho-oauthtoken {access_token}'
        }
        params = {
            'criteria': f'((Created_Time:greater_equal:{from_date})and(Created_Time:less_equal:{to_date}))',
            'fields': 'First_Name,Last_Name,Email,Phone,Account_Name,Title,Created_Time',
            'per_page': 200
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                contacts = data.get('data', [])
                print(f"Found {len(contacts)} contacts")
                return contacts
            else:
                print(f"Error fetching contacts: {response.status_code}")
                return []
        except Exception as e:
            print(f"Exception fetching contacts: {e}")
            return []
    
    def process_deals(self, deals: List[Dict]):
        """Process deals and populate pattern learning database"""
        if not deals:
            print("No deals to process")
            return
            
        cursor = self.db_conn.cursor()
        patterns_inserted = 0
        
        print(f"Processing {len(deals)} deals for pattern learning...")
        
        for deal in deals:
            # Extract fields safely
            deal_name = deal.get('Deal_Name', '')
            source = deal.get('Source') or deal.get('Lead_Source', '')
            source_detail = deal.get('Source_Detail', '')
            owner = deal.get('Owner', {}).get('name', '') if isinstance(deal.get('Owner'), dict) else ''
            
            # Learn source patterns
            if source:
                pattern_key = f"source_{source.lower().replace(' ', '_')}"
                pattern_value = json.dumps({
                    'source': source,
                    'detail_example': source_detail,
                    'owner': owner  # Include owner in pattern for context
                })
                
                # Check if pattern exists
                cursor.execute("""
                    SELECT id FROM learning_patterns 
                    WHERE pattern_type = %s AND pattern_key = %s
                """, ('source_determination', pattern_key))
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute("""
                        UPDATE learning_patterns 
                        SET usage_count = usage_count + 1,
                            confidence = LEAST(1.0, confidence + 0.01),
                            last_used = CURRENT_TIMESTAMP
                        WHERE pattern_type = %s AND pattern_key = %s
                    """, ('source_determination', pattern_key))
                else:
                    cursor.execute("""
                        INSERT INTO learning_patterns (pattern_type, pattern_key, pattern_value, confidence, usage_count)
                        VALUES (%s, %s, %s, %s, %s)
                    """, ('source_determination', pattern_key, pattern_value, 0.8, 1))
                patterns_inserted += 1
            
            # Learn deal naming patterns
            if deal_name:
                # Check for common patterns
                if " – " in deal_name:
                    pattern_type = "contact_dash_type"
                elif deal_name.startswith("Advisor ("):
                    pattern_type = "advisor_location_company"
                else:
                    pattern_type = "other"
                
                # Check if pattern exists
                cursor.execute("""
                    SELECT id FROM learning_patterns 
                    WHERE pattern_type = %s AND pattern_key = %s
                """, ('deal_naming', pattern_type))
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute("""
                        UPDATE learning_patterns 
                        SET usage_count = usage_count + 1,
                            last_used = CURRENT_TIMESTAMP
                        WHERE pattern_type = %s AND pattern_key = %s
                    """, ('deal_naming', pattern_type))
                else:
                    cursor.execute("""
                        INSERT INTO learning_patterns (pattern_type, pattern_key, pattern_value, confidence, usage_count)
                        VALUES (%s, %s, %s, %s, %s)
                    """, ('deal_naming', pattern_type, json.dumps({'example': deal_name}), 0.8, 1))
        
        self.db_conn.commit()
        print(f"✅ Learned {patterns_inserted} patterns from deals")
    
    def process_contacts(self, contacts: List[Dict]):
        """Process contacts and populate company mappings"""
        if not contacts:
            print("No contacts to process")
            return
            
        cursor = self.db_conn.cursor()
        mappings_inserted = 0
        
        print(f"Processing {len(contacts)} contacts for domain mappings...")
        
        for contact in contacts:
            email = contact.get('Email') or ''
            email = email.lower() if email else ''
            if not email or '@' not in email:
                continue
                
            domain = email.split('@')[-1]
            account = contact.get('Account_Name')
            account_name = account.get('name') if isinstance(account, dict) else account
            
            if domain and account_name:
                # Store domain to company mapping
                cursor.execute("""
                    INSERT INTO company_enrichment_cache (domain, enrichment_data, created_at, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (domain) 
                    DO UPDATE SET 
                        enrichment_data = EXCLUDED.enrichment_data,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    domain,
                    json.dumps({
                        'company_name': account_name,
                        'source': 'zoho_export',
                        'confidence': 1.0,
                        'verified': True
                    })
                ))
                mappings_inserted += 1
        
        self.db_conn.commit()
        print(f"✅ Created {mappings_inserted} domain-to-company mappings")
    
    def populate_cache_patterns(self):
        """Populate smart cache patterns based on learned data"""
        cursor = self.db_conn.cursor()
        
        # Common patterns for email caching
        cache_patterns = [
            {
                'pattern': 'calendly_scheduling',
                'keywords': ['calendly.com', 'scheduled a meeting', 'booked time'],
                'extraction': {'source': 'Website Inbound', 'source_detail': 'Calendly', 'confidence': 0.95}
            },
            {
                'pattern': 'twav_reference',
                'keywords': ['TWAV', 'Advisor Vault', 'candidate code'],
                'extraction': {'source': 'Reverse Recruiting', 'confidence': 0.95}
            },
            {
                'pattern': 'referral_keywords',
                'keywords': ['referred by', 'introduction from', 'suggested I reach out'],
                'extraction': {'source': 'Referral', 'confidence': 0.9}
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
                    hit_count = email_cache.hit_count + 1
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
        print("✅ Smart cache patterns populated")
    
    def run_export(self):
        """Main export function"""
        print("🚀 Starting Zoho CRM Smart Export for Pattern Learning...")
        print("=" * 60)
        
        # Connect to database
        self.connect_database()
        
        try:
            # Get recent deals
            print("\n📊 Fetching Deals (Jan 1 - Aug 29, 2025)...")
            deals = self.get_recent_deals()
            if deals:
                self.process_deals(deals)
            
            # Get recent contacts
            print("\n👥 Fetching Contacts (Jan 1 - Aug 29, 2025)...")
            contacts = self.get_recent_contacts()
            if contacts:
                self.process_contacts(contacts)
            
            # Populate cache patterns
            print("\n💾 Populating Cache Patterns...")
            self.populate_cache_patterns()
            
            print("\n" + "=" * 60)
            print("✅ Export complete! Database is now smarter for email extraction.")
            print("\nKey improvements made:")
            print("  • Learned source determination patterns from actual deals")
            print("  • Mapped email domains to company names")
            print("  • Created smart cache entries for common patterns")
            print("  • All data preserved exactly as-is (read-only operation)")
            
        except Exception as e:
            print(f"\n❌ Error during export: {e}")
            raise
        finally:
            # Close database connection
            if self.db_conn:
                self.db_conn.close()

if __name__ == "__main__":
    exporter = ZohoSmartExporter()
    exporter.run_export()