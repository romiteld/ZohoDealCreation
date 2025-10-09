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

# Import feature flags
try:
    from app.config import FEATURE_ASYNC_ZOHO
except ImportError:
    FEATURE_ASYNC_ZOHO = False  # Default to sync if config not available

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

# Zoho API configuration
ZOHO_BASE_URL = "https://www.zohoapis.com/crm"


async def get_zoho_headers(access_token: Optional[str] = None) -> Dict[str, str]:
    """Get Zoho API headers with authentication - async version"""
    if not access_token:
        # Get token from OAuth service
        oauth_url = f"{os.getenv('ZOHO_OAUTH_SERVICE_URL', '')}/api/token"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(oauth_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        access_token = data.get('access_token')
        except Exception as e:
            logger.error(f"Failed to get Zoho token: {e}")

    return {
        "Authorization": f"Bearer {access_token}" if access_token else "",
        "Content-Type": "application/json"
    }

def get_zoho_headers_sync(access_token: Optional[str] = None) -> Dict[str, str]:
    """Get Zoho API headers with authentication - synchronous version for backwards compatibility"""
    if not access_token:
        # Get token from OAuth service
        oauth_url = f"{os.getenv('ZOHO_OAUTH_SERVICE_URL', '')}/api/token"
        try:
            response = requests.get(oauth_url)
            if response.status_code == 200:
                access_token = response.json().get('access_token')
        except Exception as e:
            logger.error(f"Failed to get Zoho token: {e}")

    return {
        "Authorization": f"Bearer {access_token}" if access_token else "",
        "Content-Type": "application/json"
    }


async def fetch_deal_from_zoho(deal_id: str) -> Optional[Dict[str, Any]]:
    """Fetch deal details from Zoho - async version using aiohttp"""
    headers = await get_zoho_headers()
    url = f"{ZOHO_BASE_URL}/v8/Deals/{deal_id}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [{}])[0] if 'data' in data else None
    except Exception as e:
        logger.error(f"Failed to fetch deal {deal_id}: {e}")

    return None

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

    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
        if self.enhanced_client and hasattr(self.enhanced_client, 'close'):
            await self.enhanced_client.close()
    
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
        
        -- TalentWell tables for digest system
        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY,
            candidate_name TEXT,
            job_title TEXT,
            firm_name TEXT,
            location TEXT,
            owner TEXT,
            stage TEXT,
            created_date TIMESTAMP WITH TIME ZONE,
            closing_date TIMESTAMP WITH TIME ZONE,
            source TEXT,
            source_detail TEXT,
            referrer_name TEXT,
            description TEXT,
            amount NUMERIC,
            raw_data JSONB,
            imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Add missing columns from main.py INSERT statement
        ALTER TABLE deals ADD COLUMN IF NOT EXISTS deal_id VARCHAR;
        ALTER TABLE deals ADD COLUMN IF NOT EXISTS deal_name TEXT;
        ALTER TABLE deals ADD COLUMN IF NOT EXISTS owner_email TEXT;
        ALTER TABLE deals ADD COLUMN IF NOT EXISTS owner_name TEXT;
        ALTER TABLE deals ADD COLUMN IF NOT EXISTS contact_name TEXT;
        ALTER TABLE deals ADD COLUMN IF NOT EXISTS contact_email TEXT;
        ALTER TABLE deals ADD COLUMN IF NOT EXISTS account_name TEXT;
        ALTER TABLE deals ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        ALTER TABLE deals ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
        ALTER TABLE deals ADD COLUMN IF NOT EXISTS modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

        -- Ensure PRIMARY KEY exists on id column (required for ON CONFLICT)
        DO $$
        BEGIN
            -- Check if primary key constraint exists
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE contype = 'p'
                AND conrelid = 'deals'::regclass
            ) THEN
                -- Add primary key if it doesn't exist
                ALTER TABLE deals ADD PRIMARY KEY (id);
            END IF;
        END $$;
        
        CREATE TABLE IF NOT EXISTS deal_stage_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            deal_id TEXT REFERENCES deals(id),
            stage TEXT,
            changed_time TIMESTAMP WITH TIME ZONE,
            duration_days INTEGER,
            changed_by TEXT,
            imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS meetings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            deal_id TEXT REFERENCES deals(id),
            title TEXT,
            start_datetime TIMESTAMP WITH TIME ZONE,
            participants TEXT,
            email_opened BOOLEAN DEFAULT FALSE,
            link_clicked BOOLEAN DEFAULT FALSE,
            raw_data JSONB,
            imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS deal_notes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            deal_id TEXT REFERENCES deals(id),
            note_content TEXT,
            created_at TIMESTAMP WITH TIME ZONE,
            created_by TEXT,
            imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- Policy storage tables
        CREATE TABLE IF NOT EXISTS policy_employers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_name TEXT UNIQUE NOT NULL,
            firm_type TEXT NOT NULL, -- 'National firm' or 'Independent firm'
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS policy_city_context (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            city TEXT UNIQUE NOT NULL,
            metro_area TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS policy_subject_priors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            audience TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            text_template TEXT NOT NULL,
            alpha INTEGER DEFAULT 1,
            beta INTEGER DEFAULT 1,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(audience, variant_id)
        );
        
        CREATE TABLE IF NOT EXISTS policy_selector_priors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            selector TEXT UNIQUE NOT NULL,
            tau_delta NUMERIC NOT NULL,
            bdat_alpha INTEGER NOT NULL,
            bdat_beta INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Apollo enrichments table for storing LinkedIn and social media URLs
        CREATE TABLE IF NOT EXISTS apollo_enrichments (
            email TEXT PRIMARY KEY,
            linkedin_url TEXT,
            twitter_url TEXT,
            facebook_url TEXT,
            github_url TEXT,
            company_linkedin_url TEXT,
            company_twitter_url TEXT,
            company_facebook_url TEXT,
            phone TEXT,
            mobile_phone TEXT,
            work_phone TEXT,
            enriched_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_email_history_message_id ON email_processing_history(internet_message_id);
        CREATE INDEX IF NOT EXISTS idx_email_history_primary_email ON email_processing_history(primary_email);
        CREATE INDEX IF NOT EXISTS idx_apollo_enrichments_linkedin
            ON apollo_enrichments(linkedin_url) WHERE linkedin_url IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_apollo_enrichments_company
            ON apollo_enrichments((enriched_data->>'firm_company')) WHERE enriched_data IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_email_history_processed_at ON email_processing_history(processed_at);
        CREATE INDEX IF NOT EXISTS idx_company_cache_domain ON company_enrichment_cache(domain);
        CREATE INDEX IF NOT EXISTS idx_zoho_mapping_lookup ON zoho_record_mapping(record_type, lookup_key, lookup_value);
        CREATE INDEX IF NOT EXISTS idx_batch_status_batch_id ON batch_processing_status(batch_id);
        CREATE INDEX IF NOT EXISTS idx_batch_status_created_at ON batch_processing_status(created_at);
        
        -- TalentWell indexes
        CREATE INDEX IF NOT EXISTS idx_deals_owner ON deals(owner);
        CREATE INDEX IF NOT EXISTS idx_deals_created_date ON deals(created_date);
        CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals(stage);
        CREATE INDEX IF NOT EXISTS idx_deal_stage_history_deal_id ON deal_stage_history(deal_id);
        CREATE INDEX IF NOT EXISTS idx_meetings_deal_id ON meetings(deal_id);
        CREATE INDEX IF NOT EXISTS idx_meetings_start_datetime ON meetings(start_datetime);
        CREATE INDEX IF NOT EXISTS idx_deal_notes_deal_id ON deal_notes(deal_id);
        CREATE INDEX IF NOT EXISTS idx_policy_employers_company ON policy_employers(company_name);
        CREATE INDEX IF NOT EXISTS idx_policy_city_context_city ON policy_city_context(city);
        CREATE INDEX IF NOT EXISTS idx_policy_subject_priors_audience ON policy_subject_priors(audience);
        CREATE INDEX IF NOT EXISTS idx_policy_selector_priors_selector ON policy_selector_priors(selector);
        
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
            
            # Also check if exact same email was processed recently (within 5 minutes) to prevent rapid duplicates
            email_query = """
            SELECT COUNT(*) as count
            FROM email_processing_history
            WHERE sender_email = $1
              AND contact_name = $2
              AND processed_at > NOW() - INTERVAL '5 minutes'
            """

            email_row = await conn.fetchrow(email_query, sender_email, candidate_name)
            email_count = email_row['count'] if email_row else 0

            if email_count > 0:
                logger.warning(f"Same candidate {candidate_name} from {sender_email} processed within last 5 minutes - likely duplicate click")
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

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("PostgreSQL connection pool closed")

        if self.enhanced_client and hasattr(self.enhanced_client, 'close'):
            try:
                await self.enhanced_client.close()
            except Exception as e:
                logger.warning(f"Could not close enhanced client: {e}")

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

    async def upload_attachment(self, filename: str, content_base64: str, content_type: str = None) -> str:
        """Uploads an attachment to Azure Blob Storage (async wrapper for compatibility)."""
        try:
            return self.upload_file(filename, content_base64)
        except Exception as e:
            logger.error(f"Error uploading attachment {filename}: {e}")
            return None

class ZohoClient:
    """Client for Zoho CRM v8 API with PostgreSQL integration."""
    
    def __init__(self, pg_client: PostgreSQLClient = None):
        self.dc = os.getenv("ZOHO_DC", "com")
        self.base_url = f"https://www.zohoapis.{self.dc}/crm/v8"
        self.token_url = f"https://accounts.zoho.{self.dc}/oauth/v2/token"

        # OAuth credentials - optional if using OAuth proxy
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.refresh_token = os.getenv("ZOHO_REFRESH_TOKEN")
        self.access_token = None
        self.expires_at = 0

        # OAuth proxy URL for token retrieval (alternative to direct credentials)
        self.use_oauth_proxy = bool(os.getenv("ZOHO_OAUTH_SERVICE_URL") and not self.client_id)
        self.oauth_proxy_url = os.getenv("ZOHO_OAUTH_SERVICE_URL")
        
        # Owner configuration - should be set via environment variables
        # For production, this will be dynamically determined based on authorized users
        self.default_owner_id = os.getenv("ZOHO_DEFAULT_OWNER_ID")
        self.default_owner_email = os.getenv("ZOHO_DEFAULT_OWNER_EMAIL")
        self.pg_client = pg_client

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _get_access_token(self) -> str:
        """Get fresh access token using refresh token or OAuth proxy."""
        if self.access_token and time.time() < self.expires_at:
            return self.access_token

        # Use OAuth proxy if configured and no direct credentials
        if self.use_oauth_proxy and self.oauth_proxy_url:
            try:
                proxy_url = f"{self.oauth_proxy_url}/api/token"
                response = requests.get(proxy_url, timeout=10)
                response.raise_for_status()
                data = response.json()
                self.access_token = data.get("access_token")
                # Proxy tokens typically have 55min cache, set expires slightly earlier
                self.expires_at = time.time() + 3000  # 50 minutes
                logger.info("Retrieved access token from OAuth proxy")
                return self.access_token
            except Exception as e:
                logger.error(f"Failed to get token from OAuth proxy: {e}")
                raise

        # Fall back to direct OAuth refresh token flow
        if not self.refresh_token:
            raise ValueError("No OAuth credentials or proxy URL configured")

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
    def _make_request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        """
        Make authenticated request to Zoho API v8 (synchronous).

        NOTE: Async implementation disabled until call sites are updated.
        Feature flag FEATURE_ASYNC_ZOHO currently has no effect.
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self._get_access_token()}",
            "Content-Type": "application/json"
        }

        response = requests.request(method, url, json=data, headers=headers, params=params)

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

    async def upsert_account(self, company_name: str, website: str = None,
                           phone: str = None, enriched_data: Dict = None) -> str:
        """Create or update Account with PostgreSQL caching and Steve's template fields."""

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

        # Build account data with all fields from Steve's Company Record template
        account_data = {"Account_Name": company_name}

        if website:
            account_data["Website"] = website

        if phone:
            account_data["Phone"] = phone

        # Add enriched data and Steve's template fields
        if enriched_data:
            if enriched_data.get("description"):
                account_data["Description"] = enriched_data["description"]
            if enriched_data.get("industry"):
                account_data["Industry"] = enriched_data["industry"]
            # Steve's template fields
            if enriched_data.get("source"):
                account_data["Account_Source"] = enriched_data["source"]
            if enriched_data.get("source_detail"):
                account_data["Source_Detail"] = enriched_data["source_detail"]
            if enriched_data.get("who_gets_credit"):
                account_data["Who_Gets_Credit"] = enriched_data["who_gets_credit"]
            if enriched_data.get("credit_detail"):
                account_data["Credit_Detail"] = enriched_data["credit_detail"]

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

    async def upsert_contact(self, full_name: str, email: str, account_id: str,
                           phone: str = None, city: str = None, state: str = None,
                           source: str = None) -> str:
        """Create or update Contact with PostgreSQL caching and enhanced fields."""

        # Check PostgreSQL cache first
        if self.pg_client:
            cached_id = await self.pg_client.get_zoho_mapping('contact', 'email', email)
            if cached_id:
                logger.info(f"Found cached contact ID: {cached_id}")
                return cached_id

        # Search Zoho
        contact_id = self.search_contact_by_email(email)

        names = self.extract_names(full_name)

        # Build contact data with all fields from Steve's template
        contact_data = {
            "First_Name": names["First_Name"],
            "Email": email,
            "Account_Name": {"id": account_id}
        }

        if names["Last_Name"]:
            contact_data["Last_Name"] = names["Last_Name"]

        # Add optional fields from Steve's Contact Record template
        if phone:
            contact_data["Phone"] = phone

        if city:
            contact_data["Mailing_City"] = city

        if state:
            contact_data["Mailing_State"] = state

        if source:
            contact_data["Lead_Source"] = source

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
            response = self._make_request("GET", f"Accounts/search?criteria=(Website:equals:{clean_website})")
            
            if response.get("data") and len(response["data"]) > 0:
                return response["data"][0]["id"]
        except Exception as e:
            logger.warning(f"Account website search failed: {e}")
        
        return None

    def search_account_by_name(self, company_name: str) -> Optional[str]:
        """Search for existing account by name."""
        try:
            response = self._make_request("GET", f"Accounts/search?criteria=(Account_Name:equals:{company_name})")
            
            if response.get("data") and len(response["data"]) > 0:
                return response["data"][0]["id"]
        except Exception as e:
            logger.warning(f"Account name search failed: {e}")
        
        return None

    def search_contact_by_email(self, email: str) -> Optional[str]:
        """Search for existing contact by email."""
        try:
            response = self._make_request("GET", f"Contacts/search?criteria=(Email:equals:{email})")
            
            if response.get("data") and len(response["data"]) > 0:
                return response["data"][0]["id"]
        except Exception as e:
            logger.warning(f"Contact search failed: {e}")
        
        return None

    def create_deal(self, deal_data: Dict[str, Any], internet_message_id: str = None) -> str:
        """Create Deal with Steve's template field mapping."""

        # Owner field - skip if not configured (Zoho will use default)
        # In production, this will be set based on the authorized user making the request
        owner_field = None
        if self.default_owner_id:
            owner_field = {"id": self.default_owner_id}
        elif self.default_owner_email:
            owner_field = {"email": self.default_owner_email}

        # Build Deal data with correct Zoho field names from Steve's template
        zoho_deal = {
            "Deal_Name": deal_data.get("deal_name", "Unknown Deal"),
            "Contact_Name": {"id": deal_data["contact_id"]},
            "Account_Name": {"id": deal_data["account_id"]},
            "Stage": "Lead",  # Using "Lead" as the initial stage
            "Pipeline": deal_data.get("pipeline", "Sales Pipeline"),
            "Source": deal_data.get("source", "Email Inbound"),
            "Description": deal_data.get("description", "")
        }

        # Add all optional fields from Steve's Deal Record template
        if deal_data.get("closing_date"):
            zoho_deal["Closing_Date"] = deal_data["closing_date"]

        if deal_data.get("next_activity_date"):
            zoho_deal["Next_Activity_Date"] = deal_data["next_activity_date"]

        if deal_data.get("next_activity_description"):
            zoho_deal["Next_Activity_Description"] = deal_data["next_activity_description"]

        # Company-level credit tracking from Steve's template
        if deal_data.get("who_gets_credit"):
            zoho_deal["Who_Gets_Credit"] = deal_data["who_gets_credit"]

        if deal_data.get("credit_detail"):
            zoho_deal["Credit_Detail"] = deal_data["credit_detail"]

        # Only add Owner if configured
        if owner_field:
            zoho_deal["Owner"] = owner_field

        # Handle Source_Detail field from Steve's template
        if deal_data.get("source_detail"):
            zoho_deal["Source_Detail"] = deal_data["source_detail"]
        elif internet_message_id:
            zoho_deal["Source_Detail"] = f"Email ID: {internet_message_id}"

        # Remove None values
        zoho_deal = {k: v for k, v in zoho_deal.items() if v is not None and v != ""}

        payload = {"data": [zoho_deal]}
        logger.info(f"Creating Deal with Steve's template mapping: {json.dumps(payload, indent=2)}")

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

    def get_access_token(self) -> str:
        """Public method for health checks."""
        return self._get_access_token()
    
    async def create_or_update_records(self, extracted_data, sender_email: str, attachment_urls: list = None, is_duplicate: bool = False, attachment_metadata: list = None) -> dict:
        """
        Create or update Zoho records (Account -> Contact -> Deal) based on extracted data.
        This is the main orchestration method called by the API.
        Uses Steve's 3-record template structure for comprehensive field mapping.
        Returns dict with all created record IDs and details.

        Args:
            attachment_metadata: List of dicts with 'url' and 'filename' keys for proper attachment naming
        """
        try:
            # Extract structured data from Steve's template format
            company_record = extracted_data.company_record if hasattr(extracted_data, 'company_record') else None
            contact_record = extracted_data.contact_record if hasattr(extracted_data, 'contact_record') else None
            deal_record = extracted_data.deal_record if hasattr(extracted_data, 'deal_record') else None

            # Fallback to legacy fields for backward compatibility
            if not company_record:
                company_name = extracted_data.company_name or self.infer_company_from_domain(sender_email)
                company_phone = getattr(extracted_data, 'phone', None)
                company_website = getattr(extracted_data, 'website', None)
            else:
                company_name = company_record.company_name or self.infer_company_from_domain(sender_email)
                company_phone = company_record.phone
                company_website = company_record.website

            if not contact_record:
                contact_name = extracted_data.candidate_name or "Unknown Contact"
                contact_email = sender_email
                contact_phone = getattr(extracted_data, 'phone', None)
                contact_city = None
                contact_state = None
                if hasattr(extracted_data, 'location') and extracted_data.location:
                    location_parts = extracted_data.location.split(',')
                    contact_city = location_parts[0].strip() if location_parts else None
                    contact_state = location_parts[1].strip() if len(location_parts) > 1 else None
            else:
                contact_name = f"{contact_record.first_name or ''} {contact_record.last_name or ''}".strip() or "Unknown Contact"
                contact_email = contact_record.email or sender_email
                contact_phone = contact_record.phone
                contact_city = contact_record.city
                contact_state = contact_record.state

            if not deal_record:
                job_title = extracted_data.job_title or "Financial Advisor"
                location = getattr(extracted_data, 'location', None)
                # Use legacy format for backward compatibility
                from .business_rules import format_deal_name
                deal_name = format_deal_name(job_title, location, company_name, use_steve_format=False)
                pipeline = "Sales Pipeline"
                closing_date = None
                description = getattr(extracted_data, 'notes', None)
            else:
                # Steve's template provides the deal name directly
                deal_name = deal_record.deal_name
                # If deal name is not provided, format using Steve's format
                if not deal_name:
                    from .business_rules import format_deal_name
                    # Extract components for formatting with Steve's format
                    job_title = getattr(extracted_data, 'job_title', None)
                    location = getattr(extracted_data, 'location', None)
                    deal_name = format_deal_name(job_title, location, company_name, use_steve_format=True)
                pipeline = "Sales Pipeline"  # ALWAYS use Sales Pipeline as the only pipeline
                closing_date = deal_record.closing_date
                description = deal_record.description_of_reqs

            # Determine primary email (Reply-To or From)
            primary_email = contact_email or sender_email
            
            # Check for existing records in Zoho CRM first
            existing_contact = await self.check_zoho_contact_duplicate(primary_email)
            existing_account = await self.check_zoho_account_duplicate(company_name)
            
            # Log duplicate status
            if existing_contact:
                logger.info(f"Found existing contact in Zoho: {existing_contact.get('id')}")
            if existing_account:
                logger.info(f"Found existing account in Zoho: {existing_account.get('id')}")
            
            # Determine source based on Steve's template structure
            if company_record and company_record.company_source:
                source = company_record.company_source
                source_detail = company_record.source_detail or company_record.detail
            elif deal_record and deal_record.source:
                source = deal_record.source
                source_detail = deal_record.source_detail
            elif extracted_data.referrer_name and extracted_data.referrer_name != "Unknown":
                source = "Referral"
                source_detail = extracted_data.referrer_name
            else:
                source = "Email Inbound"
                source_detail = "Direct email contact"

            # 1. Create/update Account with comprehensive company data
            logger.info(f"Creating/updating account for: {company_name}")
            # Prepare enriched data from company record
            enriched_data = {}
            if company_record:
                if company_record.company_source:
                    enriched_data['source'] = company_record.company_source
                if company_record.source_detail:
                    enriched_data['source_detail'] = company_record.source_detail
                if company_record.who_gets_credit:
                    enriched_data['who_gets_credit'] = company_record.who_gets_credit
                if company_record.detail:
                    enriched_data['credit_detail'] = company_record.detail

            account_id = await self.upsert_account(
                company_name=company_name,
                website=company_website,
                phone=company_phone,
                enriched_data=enriched_data if enriched_data else None
            )
            logger.info(f"Account ID: {account_id}")

            # 2. Create/update Contact with enhanced contact data
            logger.info(f"Creating/updating contact for: {contact_name} ({primary_email})")
            contact_id = await self.upsert_contact(
                full_name=contact_name,
                email=primary_email,
                account_id=account_id,
                phone=contact_phone,
                city=contact_city,
                state=contact_state,
                source=contact_record.source if contact_record else source
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
            # Build comprehensive deal data using Steve's template structure
            deal_data = {
                "deal_name": deal_name,
                "contact_id": contact_id,
                "account_id": account_id,
                "source": source,
                "source_detail": source_detail,
                "pipeline": pipeline,
                "description": description or f"Email intake from {primary_email}"
            }

            # Add all fields from Steve's Deal Record template
            if deal_record:
                if deal_record.closing_date:
                    deal_data["closing_date"] = deal_record.closing_date
                if deal_record.description_of_reqs:
                    deal_data["description"] = deal_record.description_of_reqs

            # Add company-level source information if available
            if company_record:
                if company_record.who_gets_credit:
                    deal_data["who_gets_credit"] = company_record.who_gets_credit
                if company_record.detail:
                    deal_data["credit_detail"] = company_record.detail
            
            deal_id = self.create_deal(deal_data)
            logger.info(f"Deal ID: {deal_id}")
            
            # 4. Attach files if any
            # Prefer attachment_metadata for proper filenames, fallback to URLs with generic names
            if attachment_metadata:
                for attachment in attachment_metadata:
                    try:
                        self.attach_file_to_deal(deal_id, attachment['url'], attachment['filename'])
                    except Exception as e:
                        logger.warning(f"Failed to attach file {attachment.get('filename', 'unknown')}: {e}")
            elif attachment_urls:
                # Fallback for backwards compatibility
                for i, url in enumerate(attachment_urls):
                    filename = f"attachment_{i+1}"
                    try:
                        self.attach_file_to_deal(deal_id, url, filename)
                    except Exception as e:
                        logger.warning(f"Failed to attach file {filename}: {e}")
            
            # Cache enrichment data for TalentWell integration
            await self._cache_enrichment_data(
                primary_email=primary_email,
                company_name=company_name,
                job_title=job_title,
                location=location,
                phone=contact_phone or company_phone,
                company_website=company_website
            )

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
    
    async def _cache_enrichment_data(
        self,
        primary_email: str,
        company_name: Optional[str] = None,
        job_title: Optional[str] = None,
        location: Optional[str] = None,
        phone: Optional[str] = None,
        company_website: Optional[str] = None
    ) -> None:
        """Cache enrichment data for TalentWell integration with 7-day TTL."""
        try:
            # Import Redis client
            from well_shared.cache.redis_manager import get_cache_manager

            cache_manager = await get_cache_manager()
            if not cache_manager:
                logger.warning("Redis cache not available, skipping enrichment cache")
                return

            # Build cache key
            cache_key = f"enrichment:contact:{primary_email.lower()}"

            # Build enrichment data
            enrichment_data = {
                "email": primary_email,
                "company": company_name,
                "job_title": job_title,
                "location": location,
                "phone": phone,
                "company_website": company_website,
                "enriched_at": datetime.now(timezone.utc).isoformat(),
                "source": "outlook_intake"
            }

            # Remove None values to save space
            enrichment_data = {k: v for k, v in enrichment_data.items() if v is not None}

            # Store in Redis with 7-day TTL
            await cache_manager.client.setex(
                cache_key,
                86400 * 7,  # 7 days in seconds
                json.dumps(enrichment_data)
            )

            logger.info(f"Cached enrichment data for {primary_email} with 7-day TTL")

        except Exception as e:
            logger.error(f"Failed to cache enrichment data: {e}")
            # Don't raise - caching failure shouldn't break the main flow

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
    
    async def query_deals(self,
                         limit: int = 100,
                         page: int = 1,
                         from_date: Optional[datetime] = None,
                         to_date: Optional[datetime] = None,
                         owner_email: Optional[str] = None,
                         stage: Optional[str] = None,
                         contact_name: Optional[str] = None,
                         account_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query deals from Zoho CRM for Teams Bot queries.
        Normalizes Zoho's PascalCase field names to snake_case for query engine compatibility.

        Args:
            limit: Maximum number of deals to return
            page: Page number for pagination
            from_date: Filter deals created after this date
            to_date: Filter deals created before this date
            owner_email: Filter by owner email address
            stage: Filter by deal stage
            contact_name: Filter by contact name
            account_name: Filter by account/company name

        Returns:
            List of normalized deal dictionaries with snake_case field names
        """
        try:
            # Build search criteria
            criteria_parts = []

            # Date filters
            if from_date:
                date_str = from_date.strftime("%Y-%m-%d")
                criteria_parts.append(f"(Created_Time:greater_equal:{date_str})")

            if to_date:
                date_str = to_date.strftime("%Y-%m-%d")
                criteria_parts.append(f"(Created_Time:less_equal:{date_str})")

            # Owner filter (by email)
            if owner_email:
                criteria_parts.append(f"(Owner.email:equals:{owner_email})")

            # Stage filter
            if stage:
                criteria_parts.append(f"(Stage:equals:{stage})")

            # Contact name filter
            if contact_name:
                criteria_parts.append(f"(Contact_Name.name:contains:{contact_name})")

            # Account name filter
            if account_name:
                criteria_parts.append(f"(Account_Name.name:contains:{account_name})")

            # Make API request
            if criteria_parts:
                # Combine criteria with AND (spaces are critical!)
                search_criteria = " and ".join(criteria_parts)
                params = {
                    "criteria": search_criteria,
                    "fields": "id,Deal_Name,Stage,Contact_Name,Account_Name,Owner,Created_Time,Modified_Time,Closing_Date,Amount,Description,Source,Source_Detail",
                    "page": page,
                    "per_page": min(limit, 200)
                }
                logger.info(f"Querying Deals with search criteria: {search_criteria}")
                response = self._make_request("GET", "Deals/search", data=None, params=params)
            else:
                # No filters - get all deals
                params = {
                    "fields": "id,Deal_Name,Stage,Contact_Name,Account_Name,Owner,Created_Time,Modified_Time,Closing_Date,Amount,Description,Source,Source_Detail",
                    "page": page,
                    "per_page": min(limit, 200)
                }
                logger.info("Querying all Deals (no filters)")
                response = self._make_request("GET", "Deals", data=None, params=params)

            deals = response.get("data", [])
            logger.info(f"Fetched {len(deals)} deals from Zoho (response status: {response.get('status', 'unknown')})")

            # Normalize field names from PascalCase to snake_case
            processed_deals = []
            for deal in deals:
                # Extract owner email from Owner object
                owner = deal.get("Owner", {})
                owner_email_value = owner.get("email") if isinstance(owner, dict) else None
                owner_name_value = owner.get("name") if isinstance(owner, dict) else None

                # Extract contact name from Contact_Name object
                contact = deal.get("Contact_Name", {})
                contact_name_value = contact.get("name") if isinstance(contact, dict) else None

                # Extract account name from Account_Name object
                account = deal.get("Account_Name", {})
                account_name_value = account.get("name") if isinstance(account, dict) else None

                # Parse datetime strings to datetime objects for query engine compatibility
                created_at_str = deal.get("Created_Time")
                modified_at_str = deal.get("Modified_Time")
                closing_date_str = deal.get("Closing_Date")

                created_at = None
                modified_at = None
                closing_date = None

                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid Created_Time format: {created_at_str}")

                if modified_at_str:
                    try:
                        modified_at = datetime.fromisoformat(modified_at_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid Modified_Time format: {modified_at_str}")

                if closing_date_str:
                    try:
                        # Closing_Date may be just a date (YYYY-MM-DD) without time
                        if 'T' in closing_date_str:
                            closing_date = datetime.fromisoformat(closing_date_str.replace('Z', '+00:00'))
                        else:
                            closing_date = datetime.strptime(closing_date_str, "%Y-%m-%d")
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid Closing_Date format: {closing_date_str}")

                processed = {
                    "id": deal.get("id"),
                    "deal_name": deal.get("Deal_Name"),
                    "stage": deal.get("Stage"),
                    "contact_name": contact_name_value,
                    "account_name": account_name_value,
                    "owner_email": owner_email_value,
                    "owner_name": owner_name_value,
                    "created_at": created_at,
                    "modified_at": modified_at,
                    "closing_date": closing_date,
                    "amount": deal.get("Amount"),
                    "description": deal.get("Description"),
                    "source": deal.get("Source"),
                    "source_detail": deal.get("Source_Detail")
                }
                processed_deals.append(processed)

            logger.info(f"Normalized {len(processed_deals)} deals to snake_case format")
            return processed_deals

        except Exception as e:
            logger.error(f"Error querying deals from Zoho: {e}")
            return []

    async def query_meetings(self,
                            limit: int = 100,
                            page: int = 1,
                            from_date: Optional[datetime] = None,
                            to_date: Optional[datetime] = None,
                            owner_email: Optional[str] = None,
                            event_title: Optional[str] = None,
                            related_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query events/meetings from Zoho CRM Events module.
        Normalizes Zoho's PascalCase field names to snake_case for query engine compatibility.

        Args:
            limit: Maximum number of events to return
            page: Page number for pagination
            from_date: Filter events starting after this date
            to_date: Filter events starting before this date
            owner_email: Filter by owner email address
            event_title: Filter by event title (contains search)
            related_to: Filter by related record name (What_Id lookup)

        Returns:
            List of normalized event dictionaries with snake_case field names
        """
        try:
            # Build search criteria
            criteria_parts = []

            # Date filters (use Start_DateTime for event start time)
            if from_date:
                date_str = from_date.strftime("%Y-%m-%d")
                criteria_parts.append(f"(Start_DateTime:greater_equal:{date_str})")

            if to_date:
                date_str = to_date.strftime("%Y-%m-%d")
                criteria_parts.append(f"(Start_DateTime:less_equal:{date_str})")

            # Owner filter (by email)
            if owner_email:
                criteria_parts.append(f"(Owner.email:equals:{owner_email})")

            # Event title filter (contains search)
            if event_title:
                criteria_parts.append(f"(Event_Title:contains:{event_title})")

            # Related record filter (What_Id lookup - searches related record name)
            if related_to:
                criteria_parts.append(f"(What_Id.name:contains:{related_to})")

            # Make API request
            if criteria_parts:
                # Combine criteria with AND (spaces are critical!)
                search_criteria = " and ".join(criteria_parts)
                params = {
                    "criteria": search_criteria,
                    "fields": "id,Event_Title,Start_DateTime,End_DateTime,Participants,Owner,What_Id,se_module,Description,Location,Created_Time,Modified_Time",
                    "page": page,
                    "per_page": min(limit, 200)
                }
                logger.info(f"Querying Events with search criteria: {search_criteria}")
                response = self._make_request("GET", "Events/search", data=None, params=params)
            else:
                # No filters - get all events
                params = {
                    "fields": "id,Event_Title,Start_DateTime,End_DateTime,Participants,Owner,What_Id,se_module,Description,Location,Created_Time,Modified_Time",
                    "page": page,
                    "per_page": min(limit, 200)
                }
                logger.info("Querying all Events (no filters)")
                response = self._make_request("GET", "Events", data=None, params=params)

            events = response.get("data", [])
            logger.info(f"Fetched {len(events)} events from Zoho (response status: {response.get('status', 'unknown')})")

            # Normalize field names from PascalCase to snake_case
            processed_events = []
            for event in events:
                # Extract owner email from Owner object
                owner = event.get("Owner", {})
                owner_email_value = owner.get("email") if isinstance(owner, dict) else None
                owner_name_value = owner.get("name") if isinstance(owner, dict) else None

                # Extract related record info from What_Id lookup
                what_id = event.get("What_Id", {})
                related_record_name = what_id.get("name") if isinstance(what_id, dict) else None
                related_record_id = what_id.get("id") if isinstance(what_id, dict) else None

                # Extract participants list
                participants = event.get("Participants", [])
                attendee_names = []
                if isinstance(participants, list):
                    for participant in participants:
                        if isinstance(participant, dict):
                            attendee_names.append(participant.get("name", "Unknown"))

                # Parse datetime strings to datetime objects
                start_datetime_str = event.get("Start_DateTime")
                end_datetime_str = event.get("End_DateTime")
                created_at_str = event.get("Created_Time")
                modified_at_str = event.get("Modified_Time")

                start_datetime = None
                end_datetime = None
                created_at = None
                modified_at = None

                if start_datetime_str:
                    try:
                        start_datetime = datetime.fromisoformat(start_datetime_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid Start_DateTime format: {start_datetime_str}")

                if end_datetime_str:
                    try:
                        end_datetime = datetime.fromisoformat(end_datetime_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid End_DateTime format: {end_datetime_str}")

                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid Created_Time format: {created_at_str}")

                if modified_at_str:
                    try:
                        modified_at = datetime.fromisoformat(modified_at_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid Modified_Time format: {modified_at_str}")

                processed = {
                    "id": event.get("id"),
                    "subject": event.get("Event_Title"),  # Map to 'subject' for consistency
                    "event_title": event.get("Event_Title"),
                    "start_datetime": start_datetime,
                    "end_datetime": end_datetime,
                    "meeting_date": start_datetime,  # Alias for query engine compatibility
                    "attendees": attendee_names,
                    "owner_email": owner_email_value,
                    "owner_name": owner_name_value,
                    "related_to": related_record_name,
                    "related_to_id": related_record_id,
                    "related_module": event.get("se_module"),  # Module type (Deals, Contacts, etc.)
                    "description": event.get("Description"),
                    "location": event.get("Location"),
                    "created_at": created_at,
                    "modified_at": modified_at
                }
                processed_events.append(processed)

            logger.info(f"Normalized {len(processed_events)} events to snake_case format")
            return processed_events

        except Exception as e:
            logger.error(f"Error querying events from Zoho: {e}")
            return []

    async def query_candidates(self,
                              limit: int = 100,
                              page: int = 1,
                              from_date: Optional[datetime] = None,
                              to_date: Optional[datetime] = None,
                              owner: Optional[str] = None,
                              published_to_vault: bool = None,
                              candidate_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query candidates from Zoho CRM for TalentWell digest.
        Fetches all Leads (displayed as Candidates in Zoho) that are not Placed or Hired.
        The "Vault Candidates" view shows all available candidates.
        Applies optional date range and candidate type filters.

        Args:
            candidate_type: Filter by "advisors" or "c_suite". None = all candidates.
        """
        try:
            # Build search criteria - simplified since Candidate_Status is not searchable
            criteria_parts = []

            # Note: Publish_to_Vault is not searchable via API, will filter locally
            # Don't add it to search criteria

            # NOTE: Owner filter removed - now filtering by candidate type instead

            # If we have search criteria (but NOT for published_to_vault), use search endpoint
            if criteria_parts:
                # Combine all criteria with AND
                search_criteria = "and".join(criteria_parts)

                # Make API request with search - include fields to avoid N+1 queries
                params = {
                    "criteria": search_criteria,
                    "fields": "id,Full_Name,Email,Employer,Designation,Current_Location,Candidate_Locator,Is_Mobile,Remote,Open_to_Hybrid,Professional_Designations,Book_Size_AUM,Production_L12Mo,Desired_Comp,When_Available,Lead_Source,Candidate_Source_Details,Next_Interview_Scheduled,Interview_Recording_Link,Full_Interview_URL,Phone,Sourced_By,Publish_to_Vault,Date_Published_to_Vault",
                    "page": page,
                    "per_page": limit
                }

                # Use Leads module (displayed as Candidates in Zoho)
                module_name = os.getenv("ZCAND_MODULE", "Leads")
                response = self._make_request("GET", f"{module_name}/search", data=None, params=params)
                candidates = response.get("data", [])
                logger.info(f"Fetched {len(candidates)} candidates from search query")
            else:
                # No search criteria - use custom view for Vault Candidates
                # Custom view ID for "_Vault Candidates" (filters to Publish_to_Vault=True server-side)
                # This avoids the 2000 record pagination limit by using a filtered view

                # Use Leads module (displayed as Candidates in Zoho)
                module_name = os.getenv("ZCAND_MODULE", "Leads")
                vault_view_id = os.getenv("ZOHO_VAULT_VIEW_ID", "6221978000090941003")

                # Fetch using custom view (supports up to 2000 records with simple pagination)
                params = {
                    "fields": "id,Full_Name,Email,Employer,Designation,Current_Location,Candidate_Locator,Is_Mobile,Remote,Open_to_Hybrid,Professional_Designations,Book_Size_AUM,Production_L12Mo,Desired_Comp,When_Available,Lead_Source,Candidate_Source_Details,Next_Interview_Scheduled,Interview_Recording_Link,Full_Interview_URL,Phone,Sourced_By,Publish_to_Vault,Date_Published_to_Vault",
                    "cvid": vault_view_id,  # Use custom view to filter server-side
                    "page": page,
                    "per_page": limit if limit <= 200 else 200
                }

                response = self._make_request("GET", module_name, data=None, params=params)
                candidates = response.get("data", [])
                logger.info(f"Fetched {len(candidates)} candidates from Vault Candidates view (cvid={vault_view_id})")

            if candidates:
                # Normalize date bounds ONCE before loop for inclusive comparison
                # CRITICAL: Use UTC-aware datetimes to match Zoho's offset-aware timestamps
                normalized_from_date = None
                normalized_to_date = None

                if from_date or to_date:
                    from datetime import time, timezone

                    # Normalize from_date to start of day (00:00:00 UTC)
                    if from_date:
                        if isinstance(from_date, str):
                            parsed_from = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                            # Strip offset and make UTC-aware
                            normalized_from_date = datetime.combine(
                                parsed_from.date(), time.min, tzinfo=timezone.utc
                            )
                        elif isinstance(from_date, datetime):
                            # Strip offset and make UTC-aware
                            normalized_from_date = datetime.combine(
                                from_date.date(), time.min, tzinfo=timezone.utc
                            )
                        else:  # date object
                            normalized_from_date = datetime.combine(
                                from_date, time.min, tzinfo=timezone.utc
                            )

                    # Normalize to_date to END of day (23:59:59 UTC) for inclusive comparison
                    if to_date:
                        if isinstance(to_date, str):
                            parsed_to = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
                            # If parsed time is midnight (00:00:00), push to end of day
                            if parsed_to.time() == time.min:
                                normalized_to_date = datetime.combine(
                                    parsed_to.date(), time.max, tzinfo=timezone.utc
                                )
                            else:
                                # Keep original time but ensure UTC-aware
                                normalized_to_date = parsed_to.astimezone(timezone.utc)
                        elif isinstance(to_date, datetime):
                            # If time is midnight (00:00:00), push to end of day
                            if to_date.time() == time.min:
                                normalized_to_date = datetime.combine(
                                    to_date.date(), time.max, tzinfo=timezone.utc
                                )
                            else:
                                # Ensure UTC-aware
                                normalized_to_date = to_date.astimezone(timezone.utc) if to_date.tzinfo else to_date.replace(tzinfo=timezone.utc)
                        else:  # date object
                            normalized_to_date = datetime.combine(
                                to_date, time.max, tzinfo=timezone.utc
                            )

                    logger.debug(f"Date filter normalized: from={normalized_from_date}, to={normalized_to_date}")

                # Extract relevant fields for each candidate
                processed_candidates = []
                for candidate in candidates:
                    # Filter by Publish_to_Vault field if specified
                    if published_to_vault is not None:
                        if candidate.get("Publish_to_Vault", False) != published_to_vault:
                            continue

                    # Filter by Date_Published_to_Vault if date range specified
                    if normalized_from_date or normalized_to_date:
                        date_published_str = candidate.get("Date_Published_to_Vault")
                        if not date_published_str:
                            # Skip candidates without publish date when date filtering is active
                            continue

                        try:
                            # Parse Zoho ISO date string: "2025-10-06T14:00:00" or "2025-10-06T14:00:00+00:00"
                            date_published = datetime.fromisoformat(date_published_str.replace('Z', '+00:00'))

                            # Ensure UTC-aware for safe comparison with normalized bounds
                            if date_published.tzinfo is None:
                                date_published = date_published.replace(tzinfo=timezone.utc)
                            else:
                                date_published = date_published.astimezone(timezone.utc)

                            # Apply inclusive date range
                            if normalized_from_date and date_published < normalized_from_date:
                                continue
                            if normalized_to_date and date_published > normalized_to_date:
                                continue

                        except (ValueError, AttributeError) as e:
                            logger.warning(f"Invalid Date_Published_to_Vault '{date_published_str}' for candidate {candidate.get('Full_Name')}: {e}")
                            continue

                    # Filter by candidate type based on job title keywords
                    if candidate_type:
                        job_title = (candidate.get("Designation") or candidate.get("Title") or "").lower()

                        if candidate_type == "advisors":
                            # Advisor keywords
                            advisor_keywords = ["advisor", "financial advisor", "wealth advisor", "investment advisor", "wealth management"]
                            if not any(keyword in job_title for keyword in advisor_keywords):
                                continue
                        elif candidate_type == "c_suite":
                            # C-Suite/Executive keywords
                            exec_keywords = ["ceo", "cfo", "coo", "cto", "president", "vp", "vice president",
                                           "chief", "director", "managing director", "executive", "head of"]
                            if not any(keyword in job_title for keyword in exec_keywords):
                                continue

                    processed = {
                        "id": candidate.get("id"),
                        "candidate_locator": candidate.get("Candidate_Locator") or candidate.get("id"),
                        "candidate_name": candidate.get("Full_Name"),
                        "job_title": candidate.get("Designation"),
                        "company_name": candidate.get("Employer"),
                        "location": candidate.get("Current_Location"),
                        "is_mobile": candidate.get("Is_Mobile", False),
                        "remote_preference": candidate.get("Remote"),
                        "hybrid_preference": candidate.get("Open_to_Hybrid"),
                        "professional_designations": candidate.get("Professional_Designations"),
                        "book_size_aum": candidate.get("Book_Size_AUM"),
                        "production_12mo": candidate.get("Production_L12Mo"),
                        "desired_comp": candidate.get("Desired_Comp"),
                        "when_available": candidate.get("When_Available"),
                        "source": candidate.get("Lead_Source"),
                        "source_detail": candidate.get("Candidate_Source_Details"),
                        "date_published": candidate.get("Date_Published_to_Vault"),
                        "meeting_date": candidate.get("Next_Interview_Scheduled"),
                        "meeting_id": None,  # Field does not exist in Zoho - extract from Interview_Recording_Link if needed
                        "transcript_url": candidate.get("Interview_Recording_Link") or candidate.get("Full_Interview_URL"),
                        "email": candidate.get("Email"),
                        "phone": candidate.get("Phone"),
                        "referrer_name": candidate.get("Sourced_By"),
                        "published_to_vault": candidate.get("Publish_to_Vault", False)
                    }
                    processed_candidates.append(processed)

                # Sort by Date_Published_to_Vault ascending (oldest first = deterministic ranking)
                processed_candidates.sort(
                    key=lambda x: x.get("date_published") or "9999-12-31",
                    reverse=False
                )
                logger.debug(f"Sorted {len(processed_candidates)} vault candidates by Date_Published_to_Vault (oldest first)")

                # Log filtered count if filtering was applied
                filters_applied = []
                if published_to_vault is not None:
                    filters_applied.append("Vault")
                if candidate_type:
                    filters_applied.append(f"Type={candidate_type}")

                if filters_applied:
                    logger.info(f"Filtered to {len(processed_candidates)} candidates from {len(candidates)} total (filters: {', '.join(filters_applied)})")

                return processed_candidates
            else:
                logger.info("No candidates found matching criteria")
                return []
                
        except Exception as e:
            logger.error(f"Error querying candidates from Zoho: {e}")
            return []

    async def get_candidates(self,
                            cvid: str,
                            fields: List[str],
                            page: int = 1,
                            per_page: int = 200) -> Dict[str, Any]:
        """
        Fetch candidates from Zoho API using custom view ID.

        Args:
            cvid: Custom view ID (e.g., "_Vault Candidates" view)
            fields: List of field names to fetch
            page: Page number (default: 1)
            per_page: Records per page (max: 200)

        Returns:
            Dict with 'data' (list of records), 'info' (pagination), 'headers' (rate limits)
        """
        try:
            # Build query parameters
            params = {
                'cvid': cvid,
                'fields': ','.join(fields),
                'page': page,
                'per_page': per_page
            }

            # Make request (using synchronous _make_request)
            response = self._make_request("GET", "Leads", params=params)

            # Extract rate limit headers (if available)
            # Note: _make_request doesn't return headers, so we'll return empty dict
            headers = {}

            return {
                'data': response.get('data', []),
                'info': response.get('info', {}),
                'headers': headers
            }

        except Exception as e:
            logger.error(f"Error fetching candidates from Zoho API: {e}")
            raise
