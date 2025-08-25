"""
Cosmos DB for PostgreSQL vector storage using pgvector
Replaces Chroma/SQLite to avoid compatibility issues on Azure
"""

import os
import json
import asyncio
import asyncpg
import logging
from typing import List, Dict, Tuple, Optional, Any
from functools import lru_cache
import hashlib

logger = logging.getLogger(__name__)

class CosmosVectorStore:
    """Vector storage using Cosmos DB for PostgreSQL with pgvector extension"""
    
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string or os.getenv("DATABASE_URL")
        self._pool = None
        
    async def initialize(self):
        """Initialize connection pool and setup vector tables"""
        try:
            # Create connection pool
            self._pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=1,
                max_size=5,
                command_timeout=30
            )
            
            # Setup vector extension and tables
            async with self._pool.acquire() as conn:
                # Create pgvector extension
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Create embeddings table for CrewAI context
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS crewai_embeddings (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        metadata JSONB DEFAULT '{}',
                        embedding VECTOR(1536),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index for similarity search
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_crewai_embeddings_vector 
                    ON crewai_embeddings USING ivfflat (embedding vector_cosine_ops) 
                    WITH (lists = 50)
                """)
                
                # Create cache table for processed emails
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS email_cache (
                        email_hash TEXT PRIMARY KEY,
                        extracted_data JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 hour')
                    )
                """)
                
                logger.info("Cosmos DB vector store initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            # Continue without vector store - CrewAI will work without it
            self._pool = None
    
    async def close(self):
        """Close connection pool"""
        if self._pool:
            await self._pool.close()
    
    async def store_embedding(self, doc_id: str, content: str, embedding: List[float], metadata: Dict = None):
        """Store document with embedding in Cosmos DB"""
        if not self._pool:
            return
            
        try:
            # Convert embedding to pgvector format
            embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
            
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO crewai_embeddings (id, content, metadata, embedding)
                    VALUES ($1, $2, $3, $4::vector)
                    ON CONFLICT (id) DO UPDATE
                    SET content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding,
                        created_at = CURRENT_TIMESTAMP
                """, doc_id, content, json.dumps(metadata or {}), embedding_str)
                
        except Exception as e:
            logger.warning(f"Failed to store embedding: {e}")
    
    async def search_similar(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents using cosine similarity"""
        if not self._pool:
            return []
            
        try:
            # Convert embedding to pgvector format
            embedding_str = "[" + ",".join(f"{x:.8f}" for x in query_embedding) + "]"
            
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, content, metadata, 
                           1 - (embedding <=> $1::vector) AS similarity
                    FROM crewai_embeddings
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                """, embedding_str, top_k)
                
                return [
                    {
                        "id": row["id"],
                        "content": row["content"],
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                        "similarity": float(row["similarity"])
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.warning(f"Failed to search similar: {e}")
            return []
    
    async def cache_email_result(self, email_content: str, extracted_data: Dict):
        """Cache email processing results for fast retrieval"""
        if not self._pool:
            return
            
        try:
            # Create hash of email content
            email_hash = hashlib.md5(email_content.encode()).hexdigest()
            
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO email_cache (email_hash, extracted_data)
                    VALUES ($1, $2)
                    ON CONFLICT (email_hash) DO UPDATE
                    SET extracted_data = EXCLUDED.extracted_data,
                        created_at = CURRENT_TIMESTAMP,
                        expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour'
                """, email_hash, json.dumps(extracted_data))
                
        except Exception as e:
            logger.warning(f"Failed to cache email result: {e}")
    
    async def get_cached_result(self, email_content: str) -> Optional[Dict]:
        """Retrieve cached email result if available"""
        if not self._pool:
            return None
            
        try:
            # Create hash of email content
            email_hash = hashlib.md5(email_content.encode()).hexdigest()
            
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT extracted_data 
                    FROM email_cache 
                    WHERE email_hash = $1 
                    AND expires_at > CURRENT_TIMESTAMP
                """, email_hash)
                
                if row:
                    return json.loads(row["extracted_data"])
                    
        except Exception as e:
            logger.warning(f"Failed to get cached result: {e}")
            
        return None
    
    async def cleanup_expired_cache(self):
        """Remove expired cache entries"""
        if not self._pool:
            return
            
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM email_cache 
                    WHERE expires_at < CURRENT_TIMESTAMP
                """)
        except Exception as e:
            logger.warning(f"Failed to cleanup cache: {e}")


# Singleton instance
_vector_store = None

async def get_vector_store() -> CosmosVectorStore:
    """Get or create singleton vector store instance"""
    global _vector_store
    if not _vector_store:
        _vector_store = CosmosVectorStore()
        await _vector_store.initialize()
    return _vector_store

async def cleanup_vector_store():
    """Cleanup vector store connections"""
    global _vector_store
    if _vector_store:
        await _vector_store.close()
        _vector_store = None