#!/usr/bin/env python3
"""
Zoho CRM Data Export for Email Extraction Intelligence
Exports minimal essential data from Zoho CRM to populate PostgreSQL database
Works with existing ZohoCRMClient from integrations module
"""

import os
import sys
import json
import time
import csv
import psycopg2
import asyncio
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Import the existing integration modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.integrations import ZohoClient, PostgreSQLClient

class ZohoDataExporter:
    def __init__(self):
        """
        Initialize with existing ZohoCRMClient
        This script only READS data to learn patterns - it never modifies ownership
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
        self.api_base_url = self.zoho_client.base_url
        
        # Essential fields for email extraction intelligence
        self.deal_fields = [
            'Deal_Name',
            'Contact_Name',
            'Owner',
            'Source',
            'Source_Detail',
            'Lead_Source',  # Alternative source field
            'Stage',
            'Pipeline',
            'Account_Name',
            'Amount',
            'Closing_Date',
            'Created_Time',
            'Modified_Time'
        ]
        
        self.contact_fields = [
            'First_Name',
            'Last_Name',
            'Email',
            'Phone',
            'Mobile',
            'Account_Name',
            'Title',
            'Created_Time',
            'Modified_Time'
        ]
        
        self.account_fields = [
            'Account_Name',
            'Website',
            'Phone',
            'Industry',
            'Account_Type',
            'Created_Time',
            'Modified_Time'
        ]

    def get_access_token(self) -> str:
        """Get access token using existing ZohoCRMClient method"""
        try:
            # Use the existing client's method
            self.access_token = self.zoho_client._get_access_token()
            return self.access_token
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

    def create_bulk_read_job(self, module: str, fields: List[str]) -> str:
        """Create a bulk read job for a specific module"""
        # Bulk Read API uses a different endpoint
        url = f"https://www.zohoapis.{self.zoho_client.dc}/crm/bulk/v8/read"
        headers = {
            'Authorization': f'Zoho-oauthtoken {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Request body for bulk read
        data = {
            "query": {
                "module": {
                    "api_name": module
                },
                "fields": fields,
                "page": 1
            }
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 201:
            result = response.json()
            job_id = result['data'][0]['details']['id']
            print(f"Created bulk read job for {module}: {job_id}")
            return job_id
        else:
            print(f"Failed to create bulk read job: {response.status_code}")
            print(response.text)
            return None

    def check_job_status(self, job_id: str) -> Dict:
        """Check the status of a bulk read job"""
        url = f"https://www.zohoapis.{self.zoho_client.dc}/crm/bulk/v8/read/{job_id}"
        headers = {
            'Authorization': f'Zoho-oauthtoken {self.access_token}'
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            return result['data'][0]
        else:
            print(f"Failed to check job status: {response.status_code}")
            return None

    def download_result(self, job_id: str, output_file: str) -> bool:
        """Download the CSV result from a completed bulk read job"""
        url = f"https://www.zohoapis.{self.zoho_client.dc}/crm/bulk/v8/read/{job_id}/result"
        headers = {
            'Authorization': f'Zoho-oauthtoken {self.access_token}'
        }
        
        response = requests.get(url, headers=headers, stream=True)
        
        if response.status_code == 200:
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Downloaded result to {output_file}")
            return True
        else:
            print(f"Failed to download result: {response.status_code}")
            return False

    def wait_for_job_completion(self, job_id: str, max_wait: int = 300) -> bool:
        """Wait for a bulk read job to complete"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = self.check_job_status(job_id)
            if status:
                state = status.get('state')
                print(f"Job {job_id} state: {state}")
                
                if state == 'COMPLETED':
                    return True
                elif state == 'FAILED':
                    print(f"Job failed: {status.get('result', {}).get('error_message')}")
                    return False
            
            time.sleep(5)  # Wait 5 seconds before checking again
        
        print(f"Job {job_id} timed out")
        return False

    def process_deals_csv(self, csv_file: str):
        """
        Process exported Deals CSV and populate pattern learning database
        NOTE: This only READS data to learn patterns - never modifies Zoho records
        All deals are processed regardless of owner to maximize learning
        """
        cursor = self.db_conn.cursor()
        
        # Create pattern learning entries
        patterns_inserted = 0
        mappings_inserted = 0
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Extract essential fields (read-only, keeping all owner data intact)
                deal_name = row.get('Deal_Name', '')
                contact_name = row.get('Contact_Name', '')
                owner = row.get('Owner', '')  # Read owner for learning, never modify
                source = row.get('Source', '') or row.get('Lead_Source', '')
                source_detail = row.get('Source_Detail', '')
                stage = row.get('Stage', '')
                pipeline = row.get('Pipeline', '')
                account_name = row.get('Account_Name', '')
                
                # Learn source patterns
                if source and source_detail:
                    # Store source pattern for learning
                    pattern_key = f"source_{source.lower().replace(' ', '_')}"
                    pattern_value = json.dumps({
                        'source': source,
                        'detail_example': source_detail,
                        'keywords': self.extract_source_keywords(source, source_detail)
                    })
                    
                    cursor.execute("""
                        INSERT INTO learning_patterns (pattern_type, pattern_key, pattern_value, confidence, usage_count)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (pattern_type, pattern_key) 
                        DO UPDATE SET 
                            usage_count = learning_patterns.usage_count + 1,
                            confidence = LEAST(1.0, learning_patterns.confidence + 0.01)
                    """, ('source_determination', pattern_key, pattern_value, 0.8, 1))
                    patterns_inserted += 1
                
                # Learn deal naming patterns
                if deal_name:
                    # Extract pattern from deal name
                    naming_pattern = self.extract_naming_pattern(deal_name)
                    if naming_pattern:
                        cursor.execute("""
                            INSERT INTO learning_patterns (pattern_type, pattern_key, pattern_value, confidence, usage_count)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (pattern_type, pattern_key) 
                            DO UPDATE SET 
                                usage_count = learning_patterns.usage_count + 1,
                                confidence = LEAST(1.0, learning_patterns.confidence + 0.01)
                        """, ('deal_naming', naming_pattern['key'], json.dumps(naming_pattern), 0.8, 1))
                        patterns_inserted += 1
                
                # Store company mapping if we have account info
                if account_name and contact_name:
                    # Extract domain from account if possible
                    domain = self.extract_domain_from_account(account_name)
                    if domain:
                        cursor.execute("""
                            INSERT INTO company_templates (company_domain, template_patterns, field_mappings, confidence_scores, usage_count, success_rate)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (company_domain) 
                            DO UPDATE SET 
                                usage_count = company_templates.usage_count + 1,
                                success_rate = LEAST(1.0, company_templates.success_rate + 0.01),
                                updated_at = CURRENT_TIMESTAMP
                        """, (
                            domain,
                            json.dumps({'account_name': account_name, 'common_sources': [source]}),
                            json.dumps({'Deal_Name': deal_name, 'Source': source}),
                            json.dumps({'source': 0.8, 'naming': 0.8}),
                            1,
                            0.8
                        ))
                        mappings_inserted += 1
        
        self.db_conn.commit()
        print(f"Processed deals: {patterns_inserted} patterns learned, {mappings_inserted} company mappings created")

    def process_contacts_csv(self, csv_file: str):
        """Process exported Contacts CSV and populate database"""
        cursor = self.db_conn.cursor()
        
        contacts_processed = 0
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get('Email', '').lower()
                if not email:
                    continue
                
                first_name = row.get('First_Name', '')
                last_name = row.get('Last_Name', '')
                account_name = row.get('Account_Name', '')
                
                # Extract domain from email
                domain = email.split('@')[-1] if '@' in email else ''
                
                if domain and account_name:
                    # Store email domain to company mapping
                    cursor.execute("""
                        INSERT INTO company_enrichment_cache (domain, company_name, enrichment_data, last_enriched, created_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (domain) 
                        DO UPDATE SET 
                            company_name = EXCLUDED.company_name,
                            last_enriched = CURRENT_TIMESTAMP
                    """, (
                        domain,
                        account_name,
                        json.dumps({
                            'source': 'zoho_export',
                            'confidence': 1.0,
                            'verified': True
                        })
                    ))
                    contacts_processed += 1
        
        self.db_conn.commit()
        print(f"Processed {contacts_processed} contacts for domain mappings")

    def extract_source_keywords(self, source: str, source_detail: str) -> List[str]:
        """Extract keywords that indicate a specific source"""
        keywords = []
        
        if source == "Referral":
            keywords = ["referred", "referral", "introduction", "introduced by"]
        elif source == "Website Inbound":
            keywords = ["calendly", "scheduled", "website", "online", "form"]
        elif source == "Reverse Recruiting":
            keywords = ["TWAV", "advisor vault", "candidate", "recruiting"]
        elif source == "Email Inbound":
            keywords = ["email", "reached out", "contacted"]
        
        # Add source detail keywords if present
        if source_detail:
            keywords.extend(source_detail.lower().split())
        
        return keywords

    def extract_naming_pattern(self, deal_name: str) -> Optional[Dict]:
        """Extract naming pattern from deal name"""
        # Check for different patterns
        if " – " in deal_name:
            parts = deal_name.split(" – ")
            if len(parts) == 2:
                return {
                    'key': 'name_type',
                    'pattern': '{contact_name} – {deal_type}',
                    'example': deal_name
                }
        
        # Check for Advisor (Location) Company pattern
        if deal_name.startswith("Advisor (") and ")" in deal_name:
            return {
                'key': 'advisor_location_company',
                'pattern': 'Advisor ({location}) {company}',
                'example': deal_name
            }
        
        return None

    def extract_domain_from_account(self, account_name: str) -> Optional[str]:
        """Try to extract a domain from account name"""
        # This is a simplified version - in reality you might want to
        # look up the actual website from the Account record
        # For now, create a simplified domain
        if account_name:
            # Remove common suffixes
            clean_name = account_name.lower()
            for suffix in [' llc', ' inc', ' corp', ' company', ' financial', ' advisors', ' wealth', ' management']:
                clean_name = clean_name.replace(suffix, '')
            
            # Create a likely domain
            domain = clean_name.replace(' ', '').replace('-', '') + '.com'
            return domain
        return None

    def export_all_data(self):
        """Main export function"""
        print("Starting Zoho CRM data export for email intelligence...")
        
        # Get access token
        self.get_access_token()
        
        # Connect to database
        self.connect_database()
        
        # Export Deals
        print("\n1. Exporting Deals...")
        deal_job_id = self.create_bulk_read_job("Deals", self.deal_fields)
        if deal_job_id and self.wait_for_job_completion(deal_job_id):
            deals_file = "/tmp/zoho_deals_export.csv"
            if self.download_result(deal_job_id, deals_file):
                self.process_deals_csv(deals_file)
        
        # Export Contacts
        print("\n2. Exporting Contacts...")
        contact_job_id = self.create_bulk_read_job("Contacts", self.contact_fields)
        if contact_job_id and self.wait_for_job_completion(contact_job_id):
            contacts_file = "/tmp/zoho_contacts_export.csv"
            if self.download_result(contact_job_id, contacts_file):
                self.process_contacts_csv(contacts_file)
        
        # Export Accounts
        print("\n3. Exporting Accounts...")
        account_job_id = self.create_bulk_read_job("Accounts", self.account_fields)
        if account_job_id and self.wait_for_job_completion(account_job_id):
            accounts_file = "/tmp/zoho_accounts_export.csv"
            if self.download_result(account_job_id, accounts_file):
                self.process_accounts_csv(accounts_file)
        
        # Close database connection
        if self.db_conn:
            self.db_conn.close()
        
        print("\n✅ Export complete! Database populated with pattern learning data.")

    def process_accounts_csv(self, csv_file: str):
        """Process exported Accounts CSV and populate database"""
        cursor = self.db_conn.cursor()
        
        accounts_processed = 0
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                account_name = row.get('Account_Name', '')
                website = row.get('Website', '')
                
                if not account_name:
                    continue
                
                # Extract domain from website or create from name
                if website:
                    domain = urlparse(website).netloc.replace('www.', '')
                else:
                    domain = self.extract_domain_from_account(account_name)
                
                if domain:
                    cursor.execute("""
                        INSERT INTO company_enrichment_cache (domain, company_name, enrichment_data, last_enriched, created_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (domain) 
                        DO UPDATE SET 
                            company_name = EXCLUDED.company_name,
                            enrichment_data = EXCLUDED.enrichment_data,
                            last_enriched = CURRENT_TIMESTAMP
                    """, (
                        domain,
                        account_name,
                        json.dumps({
                            'source': 'zoho_export',
                            'website': website,
                            'industry': row.get('Industry', ''),
                            'confidence': 1.0,
                            'verified': True
                        })
                    ))
                    accounts_processed += 1
        
        self.db_conn.commit()
        print(f"Processed {accounts_processed} accounts for domain mappings")

if __name__ == "__main__":
    exporter = ZohoDataExporter()
    exporter.export_all_data()