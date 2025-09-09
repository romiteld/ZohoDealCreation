"""
Enhanced integrations module with PostgreSQL cluster integration
"""

import os
import time
import requests
import aiohttp
import asyncio
import base64
import uuid
import logging
import re
import json
from typing import Dict, Any, Optional, List, Tuple
from azure.storage.blob import BlobServiceClient
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from datetime import datetime, timezone

# Make asyncpg optional - PostgreSQL support is optional
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    asyncpg = None

# Import enhanced database features if available
try:
    from .database_enhancements import (
        EnhancedPostgreSQLClient,
        CostAwareVectorSearch,
        CONTEXT_WINDOWS
    )
    HAS_ENHANCED_DB = True
except ImportError:
    HAS_ENHANCED_DB = False
    EnhancedPostgreSQLClient = None
    CostAwareVectorSearch = None
    CONTEXT_WINDOWS = None

logger = logging.getLogger(__name__)

class PostgreSQLClient:
    """Client for Azure Cosmos DB for PostgreSQL with vector support."""
    
    def __init__(self, connection_string: str):
        if not HAS_ASYNCPG:
            raise ImportError("asyncpg is not installed. PostgreSQL features will be disabled.")
        self.connection_string = connection_string
        self.pool = None
        
        # Initialize enhanced client if available
        self.enhanced_client = None
        if HAS_ENHANCED_DB:
            try:
                self.enhanced_client = EnhancedPostgreSQLClient(connection_string)
                logger.info("Enhanced PostgreSQL client initialized with 400K context support")
            except Exception as e:
                logger.warning(f"Could not initialize enhanced client: {e}")
    
    async def init_pool(self):
        """Initialize connection pool."""
        if not self.pool:
            self.pool = await asyncpg.create_pool(self.connection_string, min_size=2, max_size=10)
    
    async def test_connection(self):
        """Test database connection."""
        await self.init_pool()
        async with self.pool.acquire() as conn:
            await conn.fetchval('SELECT 1')
    
    async def ensure_tables(self):
        """Create tables if they don't exist."""
        await self.init_pool()
        
        create_tables_sql = """
        -- Enable pgvector extension for vector similarity search
        CREATE EXTENSION IF NOT EXISTS vector;
        
        -- Email processing history
        CREATE TABLE IF NOT EXISTS email_processing_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            internet_message_id TEXT UNIQUE,
            sender_email TEXT NOT NULL,
            reply_to_email TEXT,
            primary_email TEXT NOT NULL,
            subject TEXT,
            processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            zoho_deal_id TEXT,
            zoho_account_id TEXT,
            zoho_contact_id TEXT,
            deal_name TEXT,
            company_name TEXT,
            contact_name TEXT,
            processing_status TEXT DEFAULT 'success',
            error_message TEXT,
            raw_extracted_data JSONB,
            email_body_hash TEXT -- For deduplication
        );
        
        -- Email vectors for similarity search
        CREATE TABLE IF NOT EXISTS email_vectors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email_id UUID REFERENCES email_processing_history(id),
            embedding vector(1536), -- OpenAI embedding dimension
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- Company enrichment cache
        CREATE TABLE IF NOT EXISTS company_enrichment_cache (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain TEXT UNIQUE NOT NULL,
            company_name TEXT,
            website TEXT,
            industry TEXT,
            description TEXT,
            enriched_data JSONB,
            enriched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            source TEXT DEFAULT 'firecrawl'
        );
        
        -- Zoho record mapping for deduplication
        CREATE TABLE IF NOT EXISTS zoho_record_mapping (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            record_type TEXT NOT NULL, -- 'account', 'contact', 'deal'
            zoho_id TEXT NOT NULL,
            lookup_key TEXT NOT NULL, -- email, domain, name
            lookup_value TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(record_type, lookup_key, lookup_value)
        );
        
        -- Batch processing status tracking
        CREATE TABLE IF NOT EXISTS batch_processing_status (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            batch_id TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL, -- 'pending', 'processing', 'completed', 'failed', 'partial'
            total_emails INTEGER NOT NULL,
            processed_emails INTEGER DEFAULT 0,
            failed_emails INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            processing_time_seconds NUMERIC,
            tokens_used INTEGER DEFAULT 0,
            estimated_cost NUMERIC DEFAULT 0.0,
            error_message TEXT,
            metadata JSONB DEFAULT '{}'::jsonb
        );
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_email_history_message_id ON email_processing_history(internet_message_id);
        CREATE INDEX IF NOT EXISTS idx_email_history_primary_email ON email_processing_history(primary_email);
        CREATE INDEX IF NOT EXISTS idx_email_history_processed_at ON email_processing_history(processed_at);
        CREATE INDEX IF NOT EXISTS idx_company_cache_domain ON company_enrichment_cache(domain);
        CREATE INDEX IF NOT EXISTS idx_zoho_mapping_lookup ON zoho_record_mapping(record_type, lookup_key, lookup_value);
        CREATE INDEX IF NOT EXISTS idx_batch_status_batch_id ON batch_processing_status(batch_id);
        CREATE INDEX IF NOT EXISTS idx_batch_status_created_at ON batch_processing_status(created_at);
        
        -- Vector similarity index
        CREATE INDEX IF NOT EXISTS idx_email_vectors_embedding ON email_vectors 
        USING hnsw (embedding vector_cosine_ops);
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(create_tables_sql)
        
        logger.info("PostgreSQL tables ensured")
    
    async def store_email_processing(self, processing_data: Dict[str, Any]) -> str:
        """Store email processing history."""
        await self.init_pool()
        
        insert_sql = """
        INSERT INTO email_processing_history (
            internet_message_id, sender_email, reply_to_email, primary_email,
            subject, zoho_deal_id, zoho_account_id, zoho_contact_id,
            deal_name, company_name, contact_name, processing_status,
            error_message, raw_extracted_data, email_body_hash
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        RETURNING id;
        """
        
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
            return str(row['id'])
    
    async def check_duplicate_email(self, internet_message_id: str = None, email_hash: str = None) -> Optional[Dict]:
        """Check if email was already processed."""
        await self.init_pool()
        
        if internet_message_id:
            query = "SELECT * FROM email_processing_history WHERE internet_message_id = $1"
            param = internet_message_id
        elif email_hash:
            query = "SELECT * FROM email_processing_history WHERE email_body_hash = $1"
            param = email_hash
        else:
            return None
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, param)
            return dict(row) if row else None
    
    async def check_duplicate(self, sender_email: str, candidate_name: str) -> bool:
        """Check if similar record already exists for this sender/candidate combo."""
        await self.init_pool()
        
        # More comprehensive duplicate check - tighten to 30 days and include sender email
        query = """
        SELECT COUNT(*) as count 
        FROM email_processing_history 
        WHERE contact_name = $1
          AND sender_email = $2
          AND processed_at > NOW() - INTERVAL '30 days'
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, candidate_name, sender_email)
            recent_count = row['count'] if row else 0
            
            if recent_count > 0:
                logger.warning(f"Found {recent_count} recent entries for candidate {candidate_name} from {sender_email} in last 30 days")
                return True
            
            # Also check if exact same email was processed recently (within 24 hours) by email hash
            email_query = """
            SELECT COUNT(*) as count
            FROM email_processing_history
            WHERE sender_email = $1
              AND processed_at > NOW() - INTERVAL '24 hours'
            """
            
            email_row = await conn.fetchrow(email_query, sender_email)
            email_count = email_row['count'] if email_row else 0
            
            if email_count > 0:
                logger.warning(f"Same email from {sender_email} processed within last hour")
                return True
                
            return False
    
    async def store_processed_email(self, sender_email: str, candidate_name: str, deal_id: str):
        """Store processed email record for deduplication."""
        await self.init_pool()
        
        insert_sql = """
        INSERT INTO email_processing_history (
            sender_email, primary_email, contact_name, zoho_deal_id, processing_status
        ) VALUES ($1, $1, $2, $3, 'success')
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(insert_sql, sender_email, candidate_name, deal_id)
    
    async def store_company_enrichment(self, domain: str, enrichment_data: Dict[str, Any]):
        """Cache company enrichment data."""
        await self.init_pool()
        
        upsert_sql = """
        INSERT INTO company_enrichment_cache (domain, company_name, website, industry, description, enriched_data)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (domain) 
        DO UPDATE SET 
            company_name = EXCLUDED.company_name,
            website = EXCLUDED.website,
            industry = EXCLUDED.industry,
            description = EXCLUDED.description,
            enriched_data = EXCLUDED.enriched_data,
            enriched_at = NOW();
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                upsert_sql,
                domain,
                enrichment_data.get('company_name'),
                enrichment_data.get('website'),
                enrichment_data.get('industry'),
                enrichment_data.get('description'),
                json.dumps(enrichment_data)
            )
    
    async def get_company_enrichment(self, domain: str) -> Optional[Dict]:
        """Get cached company enrichment data."""
        await self.init_pool()
        
        query = "SELECT * FROM company_enrichment_cache WHERE domain = $1"
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, domain)
            if row:
                data = dict(row)
                data['enriched_data'] = json.loads(data['enriched_data']) if data['enriched_data'] else {}
                return data
            return None
    
    async def store_zoho_mapping(self, record_type: str, zoho_id: str, lookup_key: str, lookup_value: str):
        """Store Zoho record mapping for deduplication."""
        await self.init_pool()
        
        upsert_sql = """
        INSERT INTO zoho_record_mapping (record_type, zoho_id, lookup_key, lookup_value)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (record_type, lookup_key, lookup_value)
        DO UPDATE SET zoho_id = EXCLUDED.zoho_id;
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(upsert_sql, record_type, zoho_id, lookup_key, lookup_value)
    
    async def get_zoho_mapping(self, record_type: str, lookup_key: str, lookup_value: str) -> Optional[str]:
        """Get existing Zoho record ID."""
        await self.init_pool()
        
        query = "SELECT zoho_id FROM zoho_record_mapping WHERE record_type = $1 AND lookup_key = $2 AND lookup_value = $3"
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, record_type, lookup_key, lookup_value)
            return row['zoho_id'] if row else None
    
    async def store_email_vector(self, email_id: str, embedding: List[float]):
        """Store email vector for similarity search."""
        await self.init_pool()
        
        insert_sql = "INSERT INTO email_vectors (email_id, embedding) VALUES ($1, $2)"
        
        async with self.pool.acquire() as conn:
            await conn.execute(insert_sql, email_id, embedding)
    
    async def search_similar_emails(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """Find similar emails using vector search."""
        # Use enhanced client if available for better performance
        if self.enhanced_client:
            return await self.enhanced_client.search_similar_contexts(
                query_embedding, limit=limit, threshold=0.7
            )
        
        await self.init_pool()
        
        search_sql = """
        SELECT 
            eh.*,
            ev.embedding <=> $1 as similarity_distance
        FROM email_vectors ev
        JOIN email_processing_history eh ON eh.id = ev.email_id
        ORDER BY ev.embedding <=> $1
        LIMIT $2;
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(search_sql, query_embedding, limit)
            return [dict(row) for row in rows]
    
    async def store_large_context(self, content: str, model_tier: str, total_tokens: int) -> Optional[str]:
        """Store large context using enhanced client if available."""
        if self.enhanced_client:
            return await self.enhanced_client.store_large_context(
                content, model_tier, total_tokens
            )
        return None
    
    async def track_cost(self, model_tier: str, input_tokens: int, output_tokens: int, 
                         cost: float, success: bool = True) -> Optional[str]:
        """Track model usage costs using enhanced client."""
        if self.enhanced_client:
            return await self.enhanced_client.track_model_cost(
                model_tier, input_tokens, output_tokens,
                total_cost=cost, success=success
            )
        return None
    
    async def store_enhanced_correction(self, field_name: str, original: str, 
                                       corrected: str, domain: str) -> Optional[str]:
        """Store correction pattern with enhanced features."""
        if self.enhanced_client:
            return await self.enhanced_client.store_correction_pattern(
                field_name, original, corrected, domain=domain
            )
        return None
    
    async def get_cost_analytics(self) -> Dict[str, Any]:
        """Get comprehensive cost analytics."""
        if self.enhanced_client:
            return await self.enhanced_client.get_cost_analytics()
        return {}
    
    # Batch processing status methods
    async def create_batch_status(self, batch_id: str, total_emails: int, metadata: Dict = None) -> str:
        """Create a new batch processing status record."""
        await self.init_pool()
        
        insert_sql = """
        INSERT INTO batch_processing_status (
            batch_id, status, total_emails, metadata
        ) VALUES ($1, $2, $3, $4)
        RETURNING id;
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                insert_sql,
                batch_id,
                'pending',
                total_emails,
                json.dumps(metadata or {})
            )
            return str(row['id'])
    
    async def update_batch_status(self, batch_id: str, status: str = None, processed_emails: int = None,
                                  failed_emails: int = None, processing_time_seconds: float = None,
                                  tokens_used: int = None, estimated_cost: float = None,
                                  error_message: str = None, metadata: Dict = None) -> bool:
        """Update batch processing status."""
        await self.init_pool()
        
        # Build dynamic update query
        updates = []
        values = []
        param_counter = 1
        
        if status is not None:
            updates.append(f"status = ${param_counter}")
            values.append(status)
            param_counter += 1
            
            # Set timestamps based on status
            if status == 'processing':
                updates.append(f"started_at = NOW()")
            elif status in ['completed', 'failed', 'partial']:
                updates.append(f"completed_at = NOW()")
        
        if processed_emails is not None:
            updates.append(f"processed_emails = ${param_counter}")
            values.append(processed_emails)
            param_counter += 1
        
        if failed_emails is not None:
            updates.append(f"failed_emails = ${param_counter}")
            values.append(failed_emails)
            param_counter += 1
            
        if processing_time_seconds is not None:
            updates.append(f"processing_time_seconds = ${param_counter}")
            values.append(processing_time_seconds)
            param_counter += 1
            
        if tokens_used is not None:
            updates.append(f"tokens_used = ${param_counter}")
            values.append(tokens_used)
            param_counter += 1
            
        if estimated_cost is not None:
            updates.append(f"estimated_cost = ${param_counter}")
            values.append(estimated_cost)
            param_counter += 1
            
        if error_message is not None:
            updates.append(f"error_message = ${param_counter}")
            values.append(error_message)
            param_counter += 1
            
        if metadata is not None:
            updates.append(f"metadata = ${param_counter}")
            values.append(json.dumps(metadata))
            param_counter += 1
        
        if not updates:
            return True  # No updates to make
        
        # Add batch_id as the last parameter
        values.append(batch_id)
        update_sql = f"""
        UPDATE batch_processing_status 
        SET {', '.join(updates)}
        WHERE batch_id = ${param_counter}
        """
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(update_sql, *values)
            return result == "UPDATE 1"
    
    async def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Get batch processing status."""
        await self.init_pool()
        
        query = "SELECT * FROM batch_processing_status WHERE batch_id = $1"
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, batch_id)
            if row:
                result = dict(row)
                # Parse JSON metadata
                if result.get('metadata'):
                    try:
                        result['metadata'] = json.loads(result['metadata'])
                    except json.JSONDecodeError:
                        result['metadata'] = {}
                return result
            return None
    
    async def list_batch_statuses(self, limit: int = 50, status_filter: str = None) -> List[Dict]:
        """List batch processing statuses."""
        await self.init_pool()
        
        base_query = "SELECT * FROM batch_processing_status"
        params = []
        
        if status_filter:
            base_query += " WHERE status = $1"
            params.append(status_filter)
            
        base_query += " ORDER BY created_at DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(base_query, *params)
            results = []
            for row in rows:
                result = dict(row)
                # Parse JSON metadata
                if result.get('metadata'):
                    try:
                        result['metadata'] = json.loads(result['metadata'])
                    except json.JSONDecodeError:
                        result['metadata'] = {}
                results.append(result)
            return results

class AzureBlobStorageClient:
    """Handles uploading files to Azure Blob Storage."""
    
    def __init__(self, connection_string: str, container_name: str = "email-attachments"):
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_name = container_name
        self._ensure_container_exists()

    def _ensure_container_exists(self):
        """Create container if it doesn't exist."""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container()
        except Exception as e:
            logger.warning(f"Container check/create warning: {e}")
    
    def test_connection(self):
        """Test blob storage connection."""
        container_client = self.blob_service_client.get_container_client(self.container_name)
        return container_client.exists()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def upload_file(self, filename: str, content_base64: str) -> str:
        """Uploads a base64 encoded file to Azure Blob Storage."""
        file_content = base64.b64decode(content_base64)
        unique_filename = f"{uuid.uuid4()}-{filename}"
        
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=unique_filename)
        blob_client.upload_blob(file_content, overwrite=True)
        return blob_client.url

class ZohoClient:
    """Client for Zoho CRM v8 API with PostgreSQL integration."""
    
    def __init__(self, pg_client: PostgreSQLClient = None):
        self.dc = os.getenv("ZOHO_DC", "com")
        self.base_url = f"https://www.zohoapis.{self.dc}/crm/v8"
        self.token_url = f"https://accounts.zoho.{self.dc}/oauth/v2/token"
        
        self.client_id = os.environ["ZOHO_CLIENT_ID"]
        self.client_secret = os.environ["ZOHO_CLIENT_SECRET"]
        self.refresh_token = os.environ["ZOHO_REFRESH_TOKEN"]
        self.access_token = None
        self.expires_at = 0
        
        # Owner configuration - should be set via environment variables
        # For production, this will be dynamically determined based on authorized users
        self.default_owner_id = os.getenv("ZOHO_DEFAULT_OWNER_ID")
        self.default_owner_email = os.getenv("ZOHO_DEFAULT_OWNER_EMAIL")
        self.pg_client = pg_client

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _get_access_token(self) -> str:
        """Get fresh access token using refresh token."""
        if self.access_token and time.time() < self.expires_at:
            return self.access_token
            
        payload = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token"
        }
        
        response = requests.post(self.token_url, data=payload)
        response.raise_for_status()
        
        data = response.json()
        self.access_token = data["access_token"]
        self.expires_at = time.time() + data.get("expires_in", 3600) - 60
        
        return self.access_token

    def strip_salutation(self, name: str) -> str:
        """Strip common salutations from names per Steve's feedback."""
        if not name:
            return ""
        
        salutations = ["Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Miss", "Sir", "Madam"]
        clean_name = name
        
        for salutation in salutations:
            clean_name = re.sub(rf'\b{re.escape(salutation)}\b', '', clean_name, flags=re.IGNORECASE)
        
        return ' '.join(clean_name.split())

    def extract_names(self, full_name: str) -> Dict[str, str]:
        """Extract first/last name ensuring First Name is always present for templates."""
        clean_name = self.strip_salutation(full_name)
        
        if not clean_name:
            return {"First_Name": "Unknown", "Last_Name": "Contact"}
        
        parts = clean_name.split()
        
        if len(parts) == 1:
            return {"First_Name": parts[0], "Last_Name": ""}
        else:
            return {"First_Name": parts[0], "Last_Name": " ".join(parts[1:])}

    def determine_email_address(self, from_email: str, reply_to_email: Optional[str] = None) -> str:
        """Always pick Reply-To if present, else From per Steve's feedback."""
        return reply_to_email if reply_to_email else from_email

    def infer_company_from_domain(self, email: str) -> str:
        """Infer company name from email domain."""
        if '@' not in email:
            return "Unknown Company"
        
        domain = email.split('@')[1].lower()
        
        if domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com']:
            return "Unknown Company"
        
        company = domain.replace('.com', '').replace('.org', '').replace('.net', '')
        company = company.replace('.', ' ').title()
        
        return company

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make authenticated request to Zoho API v8."""
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        response = requests.request(method, url, json=data, headers=headers)
        
        if response.status_code == 401:
            self.access_token = None
            headers["Authorization"] = f"Zoho-oauthtoken {self._get_access_token()}"
            response = requests.request(method, url, json=data, headers=headers)
        
        if response.status_code not in [200, 201, 204]:
            error_msg = f"Zoho API error - Status: {response.status_code}, URL: {url}, Response: {response.text}"
            logger.error(error_msg)
            try:
                error_json = response.json()
                if 'data' in error_json and isinstance(error_json['data'], list) and error_json['data']:
                    if 'details' in error_json['data'][0]:
                        logger.error(f"Zoho error details: {error_json['data'][0]['details']}")
                    if 'message' in error_json['data'][0]:
                        logger.error(f"Zoho error message: {error_json['data'][0]['message']}")
            except:
                pass
        response.raise_for_status()
        return response.json()

    async def upsert_account(self, company_name: str, website: str = None, enriched_data: Dict = None) -> str:
        """Create or update Account with PostgreSQL caching."""
        
        # Check PostgreSQL cache first
        if self.pg_client and website:
            domain = website.replace('http://', '').replace('https://', '').replace('www.', '')
            cached_id = await self.pg_client.get_zoho_mapping('account', 'domain', domain)
            if cached_id:
                logger.info(f"Found cached account ID: {cached_id}")
                return cached_id
        
        # Search Zoho
        account_id = None
        if website:
            account_id = self.search_account_by_website(website)
        
        if not account_id:
            account_id = self.search_account_by_name(company_name)
        
        account_data = {"Account_Name": company_name}
        
        if website:
            account_data["Website"] = website
        
        if enriched_data:
            if enriched_data.get("description"):
                account_data["Description"] = enriched_data["description"]
            if enriched_data.get("industry"):
                account_data["Industry"] = enriched_data["industry"]
        
        if account_id:
            payload = {"data": [{"id": account_id, **account_data}]}
            response = self._make_request("PUT", "Accounts", payload)
        else:
            payload = {"data": [account_data]}
            response = self._make_request("POST", "Accounts", payload)
        
        if response.get("data") and len(response["data"]) > 0:
            account_id = response["data"][0]["details"]["id"]
            
            # Cache in PostgreSQL
            if self.pg_client:
                if website:
                    domain = website.replace('http://', '').replace('https://', '').replace('www.', '')
                    await self.pg_client.store_zoho_mapping('account', account_id, 'domain', domain)
                await self.pg_client.store_zoho_mapping('account', account_id, 'name', company_name)
            
            return account_id
        
        raise ValueError(f"Failed to upsert account: {response}")

    async def upsert_contact(self, full_name: str, email: str, account_id: str) -> str:
        """Create or update Contact with PostgreSQL caching."""
        
        # Check PostgreSQL cache first
        if self.pg_client:
            cached_id = await self.pg_client.get_zoho_mapping('contact', 'email', email)
            if cached_id:
                logger.info(f"Found cached contact ID: {cached_id}")
                return cached_id
        
        # Search Zoho
        contact_id = self.search_contact_by_email(email)
        
        names = self.extract_names(full_name)
        
        contact_data = {
            "First_Name": names["First_Name"],
            "Email": email,
            "Account_Name": {"id": account_id}
        }
        
        if names["Last_Name"]:
            contact_data["Last_Name"] = names["Last_Name"]
        
        if contact_id:
            payload = {"data": [{"id": contact_id, **contact_data}]}
            response = self._make_request("PUT", "Contacts", payload)
        else:
            payload = {"data": [contact_data]}
            response = self._make_request("POST", "Contacts", payload)
        
        if response.get("data") and len(response["data"]) > 0:
            contact_id = response["data"][0]["details"]["id"]
            
            # Cache in PostgreSQL
            if self.pg_client:
                await self.pg_client.store_zoho_mapping('contact', contact_id, 'email', email)
            
            return contact_id
        
        raise ValueError(f"Failed to upsert contact: {response}")

    def search_account_by_website(self, website: str) -> Optional[str]:
        """Search for existing account by website."""
        try:
            clean_website = website.lower().replace('http://', '').replace('https://', '').replace('www.', '')
            response = self._make_request("GET", f"Accounts/search?criteria=Website:equals:{clean_website}")
            
            if response.get("data") and len(response["data"]) > 0:
                return response["data"][0]["id"]
        except Exception as e:
            logger.warning(f"Account website search failed: {e}")
        
        return None

    def search_account_by_name(self, company_name: str) -> Optional[str]:
        """Search for existing account by name."""
        try:
            response = self._make_request("GET", f"Accounts/search?criteria=Account_Name:equals:{company_name}")
            
            if response.get("data") and len(response["data"]) > 0:
                return response["data"][0]["id"]
        except Exception as e:
            logger.warning(f"Account name search failed: {e}")
        
        return None

    def search_contact_by_email(self, email: str) -> Optional[str]:
        """Search for existing contact by email."""
        try:
            response = self._make_request("GET", f"Contacts/search?criteria=Email:equals:{email}")
            
            if response.get("data") and len(response["data"]) > 0:
                return response["data"][0]["id"]
        except Exception as e:
            logger.warning(f"Contact search failed: {e}")
        
        return None

    def create_deal(self, deal_data: Dict[str, Any], internet_message_id: str = None) -> str:
        """Create Deal with exact Zoho field mapping."""
        
        # Owner field - skip if not configured (Zoho will use default)
        # In production, this will be set based on the authorized user making the request
        owner_field = None
        if self.default_owner_id:
            owner_field = {"id": self.default_owner_id}
        elif self.default_owner_email:
            owner_field = {"email": self.default_owner_email}
        
        # Build Deal data with correct Zoho field names
        zoho_deal = {
            "Deal_Name": deal_data.get("deal_name", "Unknown Deal"),
            "Contact_Name": {"id": deal_data["contact_id"]},
            "Account_Name": {"id": deal_data["account_id"]},
            "Stage": "Lead",  # Using "Lead" as the initial stage
            "Pipeline": deal_data.get("pipeline", "Sales Pipeline"),
            "Source": deal_data.get("source", "Email Inbound"),  # Using proper source value
            "Description": deal_data.get("description", "")
        }
        
        # Add optional fields only if they have values
        if deal_data.get("closing_date"):
            zoho_deal["Closing_Date"] = deal_data["closing_date"]
        
        if deal_data.get("next_activity_date"):
            zoho_deal["Next_Activity_Date"] = deal_data["next_activity_date"]
            
        if deal_data.get("next_activity_description"):
            zoho_deal["Next_Activity_Description"] = deal_data["next_activity_description"]
        
        # Only add Owner if configured
        if owner_field:
            zoho_deal["Owner"] = owner_field
        
        # Handle Source_Detail field
        if deal_data.get("source_detail"):
            zoho_deal["Source_Detail"] = deal_data["source_detail"]
        elif internet_message_id:
            zoho_deal["Source_Detail"] = f"Email ID: {internet_message_id}"
        
        # Remove None values
        zoho_deal = {k: v for k, v in zoho_deal.items() if v is not None and v != ""}
        
        payload = {"data": [zoho_deal]}
        logger.info(f"Creating Deal with payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = self._make_request("POST", "Deals", payload)
            
            if response.get("data") and len(response["data"]) > 0:
                deal_id = response["data"][0]["details"]["id"]
                logger.info(f"Successfully created Deal with ID: {deal_id}")
                return deal_id
            else:
                logger.error(f"Unexpected response structure when creating deal: {response}")
                raise ValueError(f"Failed to create deal - unexpected response: {response}")
                
        except Exception as e:
            logger.error(f"Error creating deal: {str(e)}")
            logger.error(f"Deal data was: {json.dumps(zoho_deal, indent=2)}")
            raise

    def attach_file_to_deal(self, deal_id: str, file_url: str, filename: str):
        """Add file URL as a note to the Deal record."""
        note_data = {
            "Note_Title": f"Attachment: {filename}",
            "Note_Content": f"File URL from Azure Storage:\n{file_url}",
            "$se_module": "Deals",
            "Parent_Id": deal_id
        }
        
        payload = {"data": [note_data]}
        
        try:
            self._make_request("POST", "Notes", payload)
            logger.info(f"Added attachment note for {filename} to Deal {deal_id}")
        except Exception as e:
            logger.warning(f"Could not attach file as note to deal {deal_id}: {e}")

# Legacy compatibility
class ZohoApiClient(ZohoClient):
    """Legacy compatibility wrapper."""
    
    def __init__(self, oauth_service_url: str = None):
        super().__init__()
    
    async def create_or_update_records(self, extracted_data, sender_email: str, attachment_urls: list = None, is_duplicate: bool = False) -> dict:
        """
        Create or update Zoho records (Account -> Contact -> Deal) based on extracted data.
        This is the main orchestration method called by the API.
        Returns dict with all created record IDs and details.
        """
        try:
            # Extract data with defaults
            candidate_name = extracted_data.candidate_name or "Unknown Contact"
            company_name = extracted_data.company_name or self.infer_company_from_domain(sender_email)
            job_title = extracted_data.job_title or "Financial Advisor"
            location = extracted_data.location or "Unknown Location"
            
            # Format deal name using business rules format
            deal_name = f"{job_title} ({location}) - {company_name}"
            
            # Determine primary email (Reply-To or From)
            primary_email = sender_email
            
            # Check for existing records in Zoho CRM first
            existing_contact = await self.check_zoho_contact_duplicate(primary_email)
            existing_account = await self.check_zoho_account_duplicate(company_name)
            
            # Log duplicate status
            if existing_contact:
                logger.info(f"Found existing contact in Zoho: {existing_contact.get('id')}")
            if existing_account:
                logger.info(f"Found existing account in Zoho: {existing_account.get('id')}")
            
            # Determine source based on referrer
            if extracted_data.referrer_name and extracted_data.referrer_name != "Unknown":
                source = "Referral"
                source_detail = extracted_data.referrer_name
            else:
                source = "Email Inbound"
                source_detail = "Direct email contact"
            
            # 1. Create/update Account
            logger.info(f"Creating/updating account for: {company_name}")
            account_id = await self.upsert_account(
                company_name=company_name,
                website=None,  # Could be enriched later
                enriched_data=None
            )
            logger.info(f"Account ID: {account_id}")
            
            # 2. Create/update Contact
            logger.info(f"Creating/updating contact for: {candidate_name} ({primary_email})")
            contact_id = await self.upsert_contact(
                full_name=candidate_name,
                email=primary_email,
                account_id=account_id
            )
            logger.info(f"Contact ID: {contact_id}")
            
            # 3. Create Deal (avoid duplicates if an identical deal already exists)
            # Check for an existing deal with the same name first
            try:
                existing_deal = await self.check_zoho_deal_duplicate(deal_name)
            except Exception:
                existing_deal = None
            if existing_deal and existing_deal.get("id"):
                logger.info(f"Found existing deal in Zoho with same name: {existing_deal['id']} - skipping create")
                deal_id = existing_deal["id"]
                # Return comprehensive result without re-creating
                return {
                    "deal_id": deal_id,
                    "account_id": account_id,
                    "contact_id": contact_id,
                    "deal_name": deal_name,
                    "primary_email": primary_email,
                    "was_duplicate": True,
                    "existing_contact_id": existing_contact.get('id') if existing_contact else None,
                    "existing_account_id": existing_account.get('id') if existing_account else None
                }
            logger.info(f"Creating deal: {deal_name}")
            deal_data = {
                "deal_name": deal_name,
                "contact_id": contact_id,
                "account_id": account_id,
                "source": source,
                "source_detail": source_detail,
                "description": f"Email intake from {primary_email}"
            }
            
            deal_id = self.create_deal(deal_data)
            logger.info(f"Deal ID: {deal_id}")
            
            # 4. Attach files if any
            if attachment_urls:
                for i, url in enumerate(attachment_urls):
                    filename = f"attachment_{i+1}"
                    try:
                        self.attach_file_to_deal(deal_id, url, filename)
                    except Exception as e:
                        logger.warning(f"Failed to attach file {filename}: {e}")
            
            # Return comprehensive result
            return {
                "deal_id": deal_id,
                "account_id": account_id,
                "contact_id": contact_id,
                "deal_name": deal_name,
                "primary_email": primary_email,
                "was_duplicate": bool(existing_contact or existing_account),
                "existing_contact_id": existing_contact.get('id') if existing_contact else None,
                "existing_account_id": existing_account.get('id') if existing_account else None
            }
            
        except Exception as e:
            logger.error(f"Error in create_or_update_records: {str(e)}")
            raise
    
    async def check_zoho_deal_duplicate(self, deal_name: str) -> dict:
        """Check if a deal with this exact name already exists in Zoho CRM.
        Uses Zoho search API on Deal_Name for exact match.
        """
        try:
            if not deal_name:
                return None
            # Exact match on Deal_Name
            search_query = f"(Deal_Name:equals:{deal_name})"
            response = self._make_request("GET", f"Deals/search?criteria={search_query}")
            if response.get("data") and len(response["data"]) > 0:
                deal = response["data"][0]
                logger.info(f"Found existing deal in Zoho: {deal.get('Deal_Name')} ({deal.get('id')})")
                return {
                    "id": deal.get("id"),
                    "name": deal.get("Deal_Name"),
                    "stage": deal.get("Stage")
                }
            return None
        except Exception as e:
            logger.warning(f"Error checking Zoho deal duplicate: {e}")
            return None

    async def check_zoho_contact_duplicate(self, email: str) -> dict:
        """Check if a contact with this email already exists in Zoho CRM"""
        try:
            # Search for contacts by email
            search_query = f"(Email:equals:{email})"
            response = self._make_request("GET", f"Contacts/search?criteria={search_query}")
            
            if response.get("data") and len(response["data"]) > 0:
                contact = response["data"][0]
                logger.info(f"Found existing contact in Zoho: {contact['Full_Name']} ({contact['Email']})")
                return {
                    "id": contact["id"],
                    "name": contact["Full_Name"],
                    "email": contact["Email"],
                    "account_name": contact.get("Account_Name", {}).get("name") if contact.get("Account_Name") else None
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking Zoho contact duplicate: {e}")
            return None
    
    async def check_zoho_account_duplicate(self, company_name: str) -> dict:
        """Check if an account with this company name already exists in Zoho CRM"""
        try:
            if not company_name or company_name == "Unknown":
                return None
                
            # Search for accounts by name (case-insensitive)
            search_query = f"(Account_Name:equals:{company_name})"
            response = self._make_request("GET", f"Accounts/search?criteria={search_query}")
            
            if response.get("data") and len(response["data"]) > 0:
                account = response["data"][0]
                logger.info(f"Found existing account in Zoho: {account['Account_Name']}")
                return {
                    "id": account["id"],
                    "name": account["Account_Name"],
                    "website": account.get("Website"),
                    "industry": account.get("Industry")
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking Zoho account duplicate: {e}")
            return None
