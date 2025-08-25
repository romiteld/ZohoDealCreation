"""
Optimized integrations module with connection pooling and async operations
"""

import os
import time
import base64
import uuid
import logging
import json
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from functools import lru_cache
from datetime import datetime, timezone

import asyncpg
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

logger = logging.getLogger(__name__)

class PostgreSQLClient:
    """Optimized PostgreSQL client with connection pooling and async operations"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None
        self._pool_lock = asyncio.Lock()
        self._tables_initialized = False
    
    async def init_pool(self):
        """Initialize connection pool with optimized settings"""
        async with self._pool_lock:
            if not self.pool:
                try:
                    self.pool = await asyncpg.create_pool(
                        self.connection_string,
                        min_size=1,  # Start with minimal connections
                        max_size=10,
                        max_inactive_connection_lifetime=300,  # 5 minutes
                        command_timeout=10,
                        server_settings={
                            'jit': 'off'  # Disable JIT for faster queries
                        }
                    )
                    logger.info("PostgreSQL pool initialized")
                except Exception as e:
                    logger.error(f"Failed to create PostgreSQL pool: {e}")
                    raise
    
    async def ensure_tables(self):
        """Create tables if they don't exist (optimized with single check)"""
        if self._tables_initialized:
            return
        
        await self.init_pool()
        
        # Optimized table creation with IF NOT EXISTS
        create_tables_sql = """
        -- Create extension only if needed
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        
        -- Main processing history table (optimized indexes)
        CREATE TABLE IF NOT EXISTS email_processing_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            internet_message_id TEXT,
            sender_email TEXT NOT NULL,
            reply_to_email TEXT,
            primary_email TEXT NOT NULL,
            subject TEXT,
            processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            zoho_deal_id TEXT,
            zoho_account_id TEXT,
            zoho_contact_id TEXT,
            deal_name TEXT,
            company_name TEXT,
            contact_name TEXT,
            processing_status TEXT DEFAULT 'success',
            error_message TEXT,
            raw_extracted_data JSONB,
            email_body_hash TEXT
        );
        
        -- Company enrichment cache (simplified)
        CREATE TABLE IF NOT EXISTS company_enrichment_cache (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain TEXT UNIQUE NOT NULL,
            company_name TEXT,
            website TEXT,
            enriched_data JSONB,
            enriched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Zoho record mapping (simplified)
        CREATE TABLE IF NOT EXISTS zoho_record_mapping (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            record_type TEXT NOT NULL,
            zoho_id TEXT NOT NULL,
            lookup_key TEXT NOT NULL,
            lookup_value TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create indexes concurrently to avoid blocking
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_email_message_id 
            ON email_processing_history(internet_message_id) 
            WHERE internet_message_id IS NOT NULL;
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_email_hash 
            ON email_processing_history(email_body_hash) 
            WHERE email_body_hash IS NOT NULL;
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_email_primary 
            ON email_processing_history(primary_email);
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_company_domain 
            ON company_enrichment_cache(domain);
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_zoho_lookup 
            ON zoho_record_mapping(record_type, lookup_key, lookup_value);
        """
        
        try:
            async with self.pool.acquire() as conn:
                # Execute in transaction for atomicity
                async with conn.transaction():
                    # Split and execute statements separately for better error handling
                    statements = create_tables_sql.split(';')
                    for stmt in statements:
                        if stmt.strip():
                            try:
                                await conn.execute(stmt)
                            except asyncpg.exceptions.DuplicateTableError:
                                pass  # Table already exists
                            except asyncpg.exceptions.UndefinedObjectError as e:
                                if "CONCURRENTLY" in stmt:
                                    # Index might already exist, ignore
                                    pass
                                else:
                                    raise
            
            self._tables_initialized = True
            logger.info("PostgreSQL tables initialized")
        except Exception as e:
            logger.error(f"Failed to ensure tables: {e}")
            # Don't fail the app if table creation fails
            self._tables_initialized = True
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(asyncpg.exceptions.PostgresConnectionError)
    )
    async def store_email_processing(self, processing_data: Dict[str, Any]) -> Optional[str]:
        """Store email processing history with retry logic"""
        if not self.pool:
            await self.init_pool()
        
        insert_sql = """
        INSERT INTO email_processing_history (
            internet_message_id, sender_email, reply_to_email, primary_email,
            subject, zoho_deal_id, zoho_account_id, zoho_contact_id,
            deal_name, company_name, contact_name, processing_status,
            error_message, raw_extracted_data, email_body_hash
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        ON CONFLICT (internet_message_id) WHERE internet_message_id IS NOT NULL
        DO NOTHING
        RETURNING id;
        """
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    insert_sql,
                    processing_data.get('internet_message_id'),
                    processing_data.get('sender_email'),
                    processing_data.get('reply_to_email'),
                    processing_data.get('primary_email'),
                    processing_data.get('subject'),
                    processing_data.get('zoho_deal_id'),
                    processing_data.get('zoho_account_id'),
                    processing_data.get('zoho_contact_id'),
                    processing_data.get('deal_name'),
                    processing_data.get('company_name'),
                    processing_data.get('contact_name'),
                    processing_data.get('processing_status', 'success'),
                    processing_data.get('error_message'),
                    json.dumps(processing_data.get('raw_extracted_data', {})),
                    processing_data.get('email_body_hash')
                )
                return str(row['id']) if row else None
        except Exception as e:
            logger.error(f"Failed to store email processing: {e}")
            return None
    
    async def check_duplicate_email(self, internet_message_id: str = None, email_hash: str = None) -> Optional[Dict]:
        """Check for duplicate emails with optimized query"""
        if not self.pool:
            await self.init_pool()
        
        # Use prepared statement for better performance
        if internet_message_id:
            query = """
            SELECT zoho_deal_id, zoho_account_id, zoho_contact_id, 
                   deal_name, primary_email
            FROM email_processing_history 
            WHERE internet_message_id = $1
            LIMIT 1
            """
            param = internet_message_id
        elif email_hash:
            query = """
            SELECT zoho_deal_id, zoho_account_id, zoho_contact_id, 
                   deal_name, primary_email
            FROM email_processing_history 
            WHERE email_body_hash = $1
            LIMIT 1
            """
            param = email_hash
        else:
            return None
        
        try:
            async with self.pool.acquire() as conn:
                # Prepare statement for reuse
                stmt = await conn.prepare(query)
                row = await stmt.fetchrow(param)
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"Duplicate check failed: {e}")
            return None
    
    async def store_company_enrichment(self, domain: str, enrichment_data: Dict[str, Any]):
        """Cache company enrichment data with upsert"""
        if not self.pool:
            await self.init_pool()
        
        upsert_sql = """
        INSERT INTO company_enrichment_cache (domain, company_name, website, enriched_data)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (domain) 
        DO UPDATE SET 
            company_name = EXCLUDED.company_name,
            website = EXCLUDED.website,
            enriched_data = EXCLUDED.enriched_data,
            enriched_at = CURRENT_TIMESTAMP;
        """
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    upsert_sql,
                    domain,
                    enrichment_data.get('company_name'),
                    enrichment_data.get('website'),
                    json.dumps(enrichment_data)
                )
        except Exception as e:
            logger.error(f"Failed to store company enrichment: {e}")
    
    async def get_company_enrichment(self, domain: str) -> Optional[Dict]:
        """Get cached company enrichment data"""
        if not self.pool:
            await self.init_pool()
        
        query = """
        SELECT company_name, website, enriched_data
        FROM company_enrichment_cache 
        WHERE domain = $1
        AND enriched_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
        """
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, domain)
                if row:
                    result = dict(row)
                    if result.get('enriched_data'):
                        return json.loads(result['enriched_data'])
                    return result
        except Exception as e:
            logger.warning(f"Failed to get company enrichment: {e}")
        
        return None
    
    async def store_zoho_mapping(self, record_type: str, zoho_id: str, 
                                 lookup_key: str, lookup_value: str):
        """Store Zoho record mapping for deduplication"""
        if not self.pool:
            await self.init_pool()
        
        insert_sql = """
        INSERT INTO zoho_record_mapping (record_type, zoho_id, lookup_key, lookup_value)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (record_type, lookup_key, lookup_value) 
        DO UPDATE SET zoho_id = EXCLUDED.zoho_id;
        """
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(insert_sql, record_type, zoho_id, lookup_key, lookup_value)
        except Exception as e:
            logger.error(f"Failed to store Zoho mapping: {e}")
    
    async def get_zoho_mapping(self, record_type: str, lookup_key: str, 
                               lookup_value: str) -> Optional[str]:
        """Get Zoho ID from mapping cache"""
        if not self.pool:
            await self.init_pool()
        
        query = """
        SELECT zoho_id FROM zoho_record_mapping
        WHERE record_type = $1 AND lookup_key = $2 AND lookup_value = $3
        LIMIT 1
        """
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, record_type, lookup_key, lookup_value)
                return row['zoho_id'] if row else None
        except Exception as e:
            logger.warning(f"Failed to get Zoho mapping: {e}")
            return None


class AzureBlobStorageClient:
    """Optimized Azure Blob Storage client with lazy initialization"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._client = None
        self._container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "email-attachments")
    
    @property
    def client(self):
        """Lazy initialize blob service client"""
        if not self._client:
            from azure.storage.blob import BlobServiceClient
            self._client = BlobServiceClient.from_connection_string(self.connection_string)
            logger.info("Azure Blob Storage client initialized")
        return self._client
    
    def upload_file(self, filename: str, content_base64: str) -> str:
        """Upload file to Azure Blob Storage"""
        try:
            # Generate unique blob name
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            blob_name = f"{timestamp}_{uuid.uuid4().hex[:8]}_{filename}"
            
            # Decode base64 content
            content = base64.b64decode(content_base64)
            
            # Get container client
            container_client = self.client.get_container_client(self._container_name)
            
            # Upload blob
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(content, overwrite=True)
            
            # Return URL
            return blob_client.url
        except Exception as e:
            logger.error(f"Failed to upload file {filename}: {e}")
            raise


class ZohoClient:
    """Optimized Zoho CRM client with caching and async support"""
    
    def __init__(self, pg_client: Optional[PostgreSQLClient] = None):
        self.pg_client = pg_client
        self._access_token = None
        self._token_expiry = 0
        self.oauth_service_url = os.getenv("ZOHO_OAUTH_SERVICE_URL", "https://well-zoho-oauth.azurewebsites.net")
        self.api_domain = os.getenv("ZOHO_API_DOMAIN", "https://www.zohoapis.com")
        
        # Cache for Zoho lookups
        self._account_cache = {}
        self._contact_cache = {}
        
    @lru_cache(maxsize=1)
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with cached access token"""
        if time.time() >= self._token_expiry:
            self._refresh_access_token()
        
        return {
            "Authorization": f"Zoho-oauthtoken {self._access_token}",
            "Content-Type": "application/json"
        }
    
    def _refresh_access_token(self):
        """Refresh access token using refresh token directly"""
        import requests
        
        # First try using refresh token directly if available
        refresh_token = os.getenv("ZOHO_REFRESH_TOKEN")
        client_id = os.getenv("ZOHO_CLIENT_ID")
        client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        
        if refresh_token and client_id and client_secret:
            # Use refresh token directly to get new access token
            token_url = "https://accounts.zoho.com/oauth/v2/token"
            token_data = {
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token"
            }
            
            try:
                response = requests.post(token_url, data=token_data, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self._access_token = data['access_token']
                    # Set expiry to 50 minutes (tokens last 60 minutes)
                    self._token_expiry = time.time() + 3000
                    logger.info("Zoho access token refreshed using refresh token")
                    return
                else:
                    logger.warning(f"Failed to refresh with token: {response.status_code} - {response.text}")
            except Exception as e:
                logger.warning(f"Failed to refresh using refresh token: {e}")
        
        # Fallback to OAuth service if refresh token not available or failed
        try:
            response = requests.get(f"{self.oauth_service_url}/get-token", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self._access_token = data['access_token']
                # Set expiry to 50 minutes (tokens last 60 minutes)
                self._token_expiry = time.time() + 3000
                logger.info("Zoho access token refreshed from OAuth service")
            else:
                raise Exception(f"Failed to get access token: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to refresh Zoho access token: {e}")
            raise
    
    def infer_company_from_domain(self, email: str) -> str:
        """Infer company name from email domain"""
        if '@' not in email:
            return "Unknown Company"
        
        domain = email.split('@')[1].lower()
        
        # Remove common email providers
        generic_domains = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'aol.com', 'icloud.com', 'mail.com', 'protonmail.com'
        }
        
        if domain in generic_domains:
            return "Independent"
        
        # Extract company name from domain
        company_part = domain.split('.')[0]
        
        # Capitalize and clean
        company_name = company_part.replace('-', ' ').replace('_', ' ')
        company_name = ' '.join(word.capitalize() for word in company_name.split())
        
        return company_name or "Unknown Company"
    
    async def upsert_account(self, company_name: str, website: str = None, 
                            enriched_data: Dict = None) -> str:
        """Create or update account with caching"""
        import requests
        
        # Check cache first
        if company_name in self._account_cache:
            return self._account_cache[company_name]
        
        # Check PostgreSQL cache if available
        if self.pg_client:
            cached_id = await self.pg_client.get_zoho_mapping("account", "name", company_name)
            if cached_id:
                self._account_cache[company_name] = cached_id
                return cached_id
        
        # Search for existing account
        search_url = f"{self.api_domain}/crm/v8/Accounts/search"
        params = {"criteria": f"Account_Name:equals:{company_name}"}
        
        try:
            response = requests.get(search_url, params=params, headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    account_id = data["data"][0]["id"]
                    self._account_cache[company_name] = account_id
                    
                    # Store in PostgreSQL cache
                    if self.pg_client:
                        await self.pg_client.store_zoho_mapping("account", account_id, "name", company_name)
                    
                    return account_id
        except Exception as e:
            logger.warning(f"Account search failed: {e}")
        
        # Create new account
        create_url = f"{self.api_domain}/crm/v8/Accounts"
        account_data = {
            "data": [{
                "Account_Name": company_name,
                "Website": website
            }]
        }
        
        if enriched_data:
            account_data["data"][0].update({
                "Industry": enriched_data.get("industry"),
                "Description": enriched_data.get("description")
            })
        
        try:
            response = requests.post(create_url, json=account_data, headers=self._get_headers(), timeout=10)
            if response.status_code == 201:
                data = response.json()
                account_id = data["data"][0]["details"]["id"]
                self._account_cache[company_name] = account_id
                
                # Store in PostgreSQL cache
                if self.pg_client:
                    await self.pg_client.store_zoho_mapping("account", account_id, "name", company_name)
                
                logger.info(f"Created account: {company_name} ({account_id})")
                return account_id
        except Exception as e:
            logger.error(f"Failed to create account: {e}")
            raise
        
        raise Exception(f"Failed to create account: {company_name}")
    
    async def upsert_contact(self, full_name: str, email: str, account_id: str) -> str:
        """Create or update contact with caching"""
        import requests
        
        # Check cache first
        if email in self._contact_cache:
            return self._contact_cache[email]
        
        # Check PostgreSQL cache if available
        if self.pg_client:
            cached_id = await self.pg_client.get_zoho_mapping("contact", "email", email)
            if cached_id:
                self._contact_cache[email] = cached_id
                return cached_id
        
        # Search for existing contact
        search_url = f"{self.api_domain}/crm/v8/Contacts/search"
        params = {"criteria": f"Email:equals:{email}"}
        
        try:
            response = requests.get(search_url, params=params, headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    contact_id = data["data"][0]["id"]
                    self._contact_cache[email] = contact_id
                    
                    # Store in PostgreSQL cache
                    if self.pg_client:
                        await self.pg_client.store_zoho_mapping("contact", contact_id, "email", email)
                    
                    return contact_id
        except Exception as e:
            logger.warning(f"Contact search failed: {e}")
        
        # Parse name
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else "Unknown"
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Contact"
        
        # Create new contact
        create_url = f"{self.api_domain}/crm/v8/Contacts"
        contact_data = {
            "data": [{
                "First_Name": first_name,
                "Last_Name": last_name,
                "Email": email,
                "Account_Name": {"id": account_id}
            }]
        }
        
        try:
            response = requests.post(create_url, json=contact_data, headers=self._get_headers(), timeout=10)
            if response.status_code == 201:
                data = response.json()
                contact_id = data["data"][0]["details"]["id"]
                self._contact_cache[email] = contact_id
                
                # Store in PostgreSQL cache
                if self.pg_client:
                    await self.pg_client.store_zoho_mapping("contact", contact_id, "email", email)
                
                logger.info(f"Created contact: {full_name} ({contact_id})")
                return contact_id
        except Exception as e:
            logger.error(f"Failed to create contact: {e}")
            raise
        
        raise Exception(f"Failed to create contact: {full_name}")
    
    def create_deal(self, deal_data: Dict[str, Any], internet_message_id: str = None) -> str:
        """Create deal in Zoho CRM"""
        import requests
        
        create_url = f"{self.api_domain}/crm/v8/Deals"
        
        # Prepare deal payload
        zoho_deal = {
            "data": [{
                "Deal_Name": deal_data["deal_name"],
                "Account_Name": {"id": deal_data["account_id"]},
                "Contact_Name": {"id": deal_data["contact_id"]},
                "Stage": "Qualification",
                "Pipeline": deal_data.get("pipeline", "Sales Pipeline"),
                "Lead_Source": deal_data.get("source", "Email"),
                "Description": deal_data.get("description", "")
            }]
        }
        
        # Add custom fields if available
        if deal_data.get("source_detail"):
            zoho_deal["data"][0]["Lead_Source_Detail"] = deal_data["source_detail"]
        
        if internet_message_id:
            zoho_deal["data"][0]["Email_Message_ID"] = internet_message_id
        
        try:
            response = requests.post(create_url, json=zoho_deal, headers=self._get_headers(), timeout=10)
            if response.status_code == 201:
                data = response.json()
                deal_id = data["data"][0]["details"]["id"]
                logger.info(f"Created deal: {deal_data['deal_name']} ({deal_id})")
                return deal_id
        except Exception as e:
            logger.error(f"Failed to create deal: {e}")
            raise
        
        raise Exception(f"Failed to create deal: {deal_data['deal_name']}")
    
    def attach_file_to_deal(self, deal_id: str, file_url: str, filename: str):
        """Attach file to deal (simplified)"""
        # This would require downloading from Azure and uploading to Zoho
        # For now, we'll just log it
        logger.info(f"Would attach {filename} to deal {deal_id}")
        # Implementation depends on Zoho's attachment API requirements