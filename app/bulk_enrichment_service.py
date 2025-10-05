"""
Bulk Apollo.io Enrichment Service for Existing Zoho Records

This module provides comprehensive bulk enrichment capabilities:
- Process existing records from PostgreSQL
- Batch enrichment through Apollo.io API
- Rate limiting and pagination support
- WebSocket progress updates
- Scheduled job management
- Metrics tracking and success rates
"""

import os
import json
import logging
import asyncio
from typing import Dict, Optional, List, Any, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, validator

# Apollo enricher import
from app.apollo_enricher import (
    apollo_unlimited_people_search,
    apollo_unlimited_company_search,
    apollo_deep_enrichment
)

# Database connection
from app.database_connection_manager import DatabaseConnectionManager

# WebSocket manager for progress updates
try:
    from app.signalr_manager import SignalRManager
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False
    SignalRManager = None

logger = logging.getLogger(__name__)


class EnrichmentStatus(Enum):
    """Status of enrichment job"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class EnrichmentPriority(Enum):
    """Priority levels for enrichment"""
    HIGH = 1      # Critical records (deals in progress)
    MEDIUM = 2    # Active contacts
    LOW = 3       # Historical records
    BACKGROUND = 4 # Bulk background jobs


@dataclass
class EnrichmentMetrics:
    """Metrics for tracking enrichment performance"""
    total_records: int = 0
    enriched_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    linkedin_found: int = 0
    phone_found: int = 0
    website_found: int = 0
    location_found: int = 0
    company_data_found: int = 0
    key_employees_found: int = 0
    success_rate: float = 0.0
    avg_data_completeness: float = 0.0
    processing_time_ms: int = 0
    api_calls_made: int = 0
    cache_hits: int = 0

    def calculate_success_rate(self):
        """Calculate success rate percentage"""
        if self.total_records > 0:
            self.success_rate = (self.enriched_count / self.total_records) * 100
        return self.success_rate

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return asdict(self)


class BulkEnrichmentRequest(BaseModel):
    """Request model for bulk enrichment"""
    record_ids: Optional[List[str]] = Field(None, description="List of record IDs to enrich")
    emails: Optional[List[str]] = Field(None, description="List of emails to enrich")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters for selecting records")
    priority: EnrichmentPriority = Field(EnrichmentPriority.MEDIUM, description="Job priority")
    batch_size: int = Field(50, description="Number of records per batch", ge=1, le=100)
    include_company: bool = Field(True, description="Include company enrichment")
    include_employees: bool = Field(False, description="Include key employees data")
    update_zoho: bool = Field(True, description="Update Zoho CRM records")
    webhook_url: Optional[str] = Field(None, description="Webhook for job completion")

    @validator("batch_size")
    def validate_batch_size(cls, v):
        """Ensure batch size is reasonable for API rate limits"""
        if v > 100:
            raise ValueError("Batch size cannot exceed 100 for rate limiting")
        return v


class EnrichmentJob:
    """Manages a bulk enrichment job"""

    def __init__(
        self,
        job_id: str,
        request: BulkEnrichmentRequest,
        db_manager: DatabaseConnectionManager,
        websocket_manager: Optional[SignalRManager] = None
    ):
        self.job_id = job_id
        self.request = request
        self.db_manager = db_manager
        self.websocket_manager = websocket_manager

        self.status = EnrichmentStatus.PENDING
        self.metrics = EnrichmentMetrics()
        self.start_time = None
        self.end_time = None
        self.current_batch = 0
        self.total_batches = 0
        self.errors = []

        # Rate limiting
        self.api_calls_per_minute = 60  # Apollo.io rate limit
        self.last_api_call = None
        self.api_call_delay = 1.0  # Minimum seconds between calls

    async def execute(self) -> Dict[str, Any]:
        """Execute the enrichment job"""
        self.start_time = datetime.now(timezone.utc)
        self.status = EnrichmentStatus.IN_PROGRESS

        try:
            # Step 1: Load records to enrich
            records = await self._load_records()
            self.metrics.total_records = len(records)

            if not records:
                self.status = EnrichmentStatus.COMPLETED
                self.metrics.skipped_count = self.metrics.total_records
                return self._generate_report()

            # Step 2: Calculate batches
            self.total_batches = (len(records) + self.request.batch_size - 1) // self.request.batch_size

            # Step 3: Process in batches
            for batch_num in range(self.total_batches):
                self.current_batch = batch_num + 1
                start_idx = batch_num * self.request.batch_size
                end_idx = min(start_idx + self.request.batch_size, len(records))
                batch_records = records[start_idx:end_idx]

                await self._process_batch(batch_records)
                await self._send_progress_update()

                # Rate limiting between batches
                if batch_num < self.total_batches - 1:
                    await asyncio.sleep(self.api_call_delay)

            # Step 4: Calculate final metrics
            self.metrics.calculate_success_rate()
            self.status = EnrichmentStatus.COMPLETED if self.metrics.failed_count == 0 else EnrichmentStatus.PARTIAL

        except Exception as e:
            logger.error(f"Enrichment job {self.job_id} failed: {str(e)}")
            self.status = EnrichmentStatus.FAILED
            self.errors.append(str(e))

        finally:
            self.end_time = datetime.now(timezone.utc)
            self.metrics.processing_time_ms = int((self.end_time - self.start_time).total_seconds() * 1000)

            # Save job results to database
            await self._save_job_results()

            # Send webhook if configured
            if self.request.webhook_url:
                await self._send_webhook()

        return self._generate_report()

    async def _load_records(self) -> List[Dict[str, Any]]:
        """Load records from database based on request criteria"""
        records = []

        try:
            async with self.db_manager.get_connection() as conn:
                # Build query based on request
                if self.request.record_ids:
                    # Load specific records by ID
                    query = """
                        SELECT id, deal_id, deal_name, contact_email, contact_name,
                               account_name, metadata, candidate_name, company_name,
                               email, job_title, created_at
                        FROM deals
                        WHERE id = ANY($1)
                        ORDER BY created_at DESC
                    """
                    records = await conn.fetch(query, self.request.record_ids)

                elif self.request.emails:
                    # Load records by email
                    query = """
                        SELECT id, deal_id, deal_name, contact_email, contact_name,
                               account_name, metadata, candidate_name, company_name,
                               email, job_title, created_at
                        FROM deals
                        WHERE email = ANY($1) OR contact_email = ANY($1)
                        ORDER BY created_at DESC
                    """
                    records = await conn.fetch(query, self.request.emails)

                elif self.request.filters:
                    # Build dynamic query based on filters
                    where_clauses = []
                    params = []
                    param_count = 0

                    if "created_after" in self.request.filters:
                        param_count += 1
                        where_clauses.append(f"created_at >= ${param_count}")
                        params.append(self.request.filters["created_after"])

                    if "created_before" in self.request.filters:
                        param_count += 1
                        where_clauses.append(f"created_at <= ${param_count}")
                        params.append(self.request.filters["created_before"])

                    if "source" in self.request.filters:
                        param_count += 1
                        where_clauses.append(f"source = ${param_count}")
                        params.append(self.request.filters["source"])

                    if "has_email" in self.request.filters and self.request.filters["has_email"]:
                        where_clauses.append("(email IS NOT NULL OR contact_email IS NOT NULL)")

                    if "missing_linkedin" in self.request.filters and self.request.filters["missing_linkedin"]:
                        where_clauses.append("(metadata->>'linkedin_url' IS NULL OR metadata->>'linkedin_url' = '')")

                    if "missing_phone" in self.request.filters and self.request.filters["missing_phone"]:
                        where_clauses.append("(metadata->>'phone' IS NULL OR metadata->>'phone' = '')")

                    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

                    query = f"""
                        SELECT id, deal_id, deal_name, contact_email, contact_name,
                               account_name, metadata, candidate_name, company_name,
                               email, job_title, created_at
                        FROM deals
                        WHERE {where_clause}
                        ORDER BY created_at DESC
                        LIMIT 1000
                    """
                    records = await conn.fetch(query, *params)

                else:
                    # Default: load recent records without enrichment
                    query = """
                        SELECT id, deal_id, deal_name, contact_email, contact_name,
                               account_name, metadata, candidate_name, company_name,
                               email, job_title, created_at
                        FROM deals
                        WHERE (metadata->>'apollo_enriched' IS NULL OR metadata->>'apollo_enriched' = 'false')
                        AND (email IS NOT NULL OR contact_email IS NOT NULL)
                        ORDER BY created_at DESC
                        LIMIT 500
                    """
                    records = await conn.fetch(query)

                # Convert to list of dicts
                records = [dict(record) for record in records]
                logger.info(f"Loaded {len(records)} records for enrichment")

        except Exception as e:
            logger.error(f"Failed to load records: {str(e)}")
            raise

        return records

    async def _process_batch(self, batch_records: List[Dict[str, Any]]):
        """Process a batch of records through Apollo enrichment"""
        for record in batch_records:
            try:
                # Apply rate limiting
                await self._apply_rate_limit()

                # Determine email to use for enrichment
                email = record.get("email") or record.get("contact_email")
                name = record.get("candidate_name") or record.get("contact_name")
                company = record.get("company_name") or record.get("account_name")

                if not email and not name:
                    logger.warning(f"Skipping record {record.get('id')} - no email or name")
                    self.metrics.skipped_count += 1
                    continue

                # Perform Apollo enrichment
                enrichment_result = await apollo_deep_enrichment(
                    email=email,
                    name=name,
                    company=company,
                    extract_all=self.request.include_employees
                )

                self.metrics.api_calls_made += 1

                # Process enrichment result
                if enrichment_result and (enrichment_result.get("person") or enrichment_result.get("company")):
                    await self._save_enrichment(record, enrichment_result)
                    self.metrics.enriched_count += 1

                    # Track specific data points found
                    if enrichment_result.get("person"):
                        person = enrichment_result["person"]
                        if person.get("linkedin_url"):
                            self.metrics.linkedin_found += 1
                        if person.get("phone"):
                            self.metrics.phone_found += 1
                        if person.get("location"):
                            self.metrics.location_found += 1

                    if enrichment_result.get("company"):
                        company_data = enrichment_result["company"]
                        self.metrics.company_data_found += 1
                        if company_data.get("website"):
                            self.metrics.website_found += 1
                        if company_data.get("key_employees"):
                            self.metrics.key_employees_found += 1

                    # Update average data completeness
                    self.metrics.avg_data_completeness = (
                        (self.metrics.avg_data_completeness * (self.metrics.enriched_count - 1) +
                         enrichment_result.get("data_completeness", 0)) / self.metrics.enriched_count
                    )
                else:
                    logger.warning(f"No enrichment data found for record {record.get('id')}")
                    self.metrics.skipped_count += 1

            except Exception as e:
                logger.error(f"Failed to enrich record {record.get('id')}: {str(e)}")
                self.metrics.failed_count += 1
                self.errors.append({
                    "record_id": record.get("id"),
                    "error": str(e)
                })

    async def _save_enrichment(self, record: Dict[str, Any], enrichment_data: Dict[str, Any]):
        """Save enrichment data to database and optionally update Zoho"""
        try:
            async with self.db_manager.get_connection() as conn:
                # Prepare updated metadata
                existing_metadata = record.get("metadata") or {}
                if isinstance(existing_metadata, str):
                    existing_metadata = json.loads(existing_metadata)

                # Merge enrichment data into metadata
                updated_metadata = {
                    **existing_metadata,
                    "apollo_enriched": True,
                    "apollo_enrichment_date": datetime.now(timezone.utc).isoformat(),
                    "apollo_data": enrichment_data,
                    "enrichment_job_id": self.job_id
                }

                # Extract key fields for direct columns
                person_data = enrichment_data.get("person", {})
                company_data = enrichment_data.get("company", {})

                # Update deals table
                await conn.execute("""
                    UPDATE deals
                    SET metadata = $1,
                        modified_at = NOW()
                    WHERE id = $2
                """, json.dumps(updated_metadata), record["id"])

                # Store in apollo_enrichments table
                await conn.execute("""
                    INSERT INTO apollo_enrichments (
                        record_id, email, enriched_data,
                        data_completeness, job_id, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (record_id) DO UPDATE
                    SET enriched_data = $3,
                        data_completeness = $4,
                        job_id = $5,
                        updated_at = $6
                """,
                    record["id"],
                    record.get("email") or record.get("contact_email"),
                    json.dumps(enrichment_data),
                    enrichment_data.get("data_completeness", 0),
                    self.job_id,
                    datetime.now(timezone.utc)
                )

                # Update Zoho if enabled
                if self.request.update_zoho and record.get("deal_id"):
                    await self._update_zoho_record(record["deal_id"], enrichment_data)

                logger.info(f"Saved enrichment for record {record['id']}")

        except Exception as e:
            logger.error(f"Failed to save enrichment for record {record['id']}: {str(e)}")
            raise

    async def _update_zoho_record(self, deal_id: str, enrichment_data: Dict[str, Any]):
        """Update Zoho CRM record with enrichment data"""
        # This would integrate with your existing Zoho API service
        # For now, we'll log the intention
        logger.info(f"Would update Zoho deal {deal_id} with enrichment data")
        # TODO: Implement actual Zoho update logic

    async def _apply_rate_limit(self):
        """Apply rate limiting between API calls"""
        if self.last_api_call:
            elapsed = (datetime.now(timezone.utc) - self.last_api_call).total_seconds()
            if elapsed < self.api_call_delay:
                await asyncio.sleep(self.api_call_delay - elapsed)

        self.last_api_call = datetime.now(timezone.utc)

    async def _send_progress_update(self):
        """Send progress update via WebSocket if available"""
        if self.websocket_manager and HAS_WEBSOCKET:
            progress = {
                "job_id": self.job_id,
                "status": self.status.value,
                "current_batch": self.current_batch,
                "total_batches": self.total_batches,
                "records_processed": self.metrics.enriched_count + self.metrics.failed_count + self.metrics.skipped_count,
                "total_records": self.metrics.total_records,
                "success_rate": self.metrics.calculate_success_rate(),
                "metrics": self.metrics.to_dict()
            }

            try:
                await self.websocket_manager.send_message(
                    f"enrichment.progress.{self.job_id}",
                    progress
                )
            except Exception as e:
                logger.warning(f"Failed to send WebSocket progress update: {str(e)}")

    async def _save_job_results(self):
        """Save job results to database"""
        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO enrichment_jobs (
                        job_id, request_data, status, metrics,
                        start_time, end_time, errors, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (job_id) DO UPDATE
                    SET status = $3,
                        metrics = $4,
                        end_time = $6,
                        errors = $7,
                        updated_at = $8
                """,
                    self.job_id,
                    json.dumps(self.request.dict()),
                    self.status.value,
                    json.dumps(self.metrics.to_dict()),
                    self.start_time,
                    self.end_time,
                    json.dumps(self.errors),
                    datetime.now(timezone.utc)
                )

                logger.info(f"Saved job results for {self.job_id}")

        except Exception as e:
            logger.error(f"Failed to save job results: {str(e)}")

    async def _send_webhook(self):
        """Send webhook notification on job completion"""
        if not self.request.webhook_url:
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                webhook_data = {
                    "job_id": self.job_id,
                    "status": self.status.value,
                    "metrics": self.metrics.to_dict(),
                    "processing_time_ms": self.metrics.processing_time_ms,
                    "errors": self.errors[:10]  # Limit errors in webhook
                }

                response = await client.post(
                    self.request.webhook_url,
                    json=webhook_data,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(f"Webhook sent successfully for job {self.job_id}")
                else:
                    logger.warning(f"Webhook failed with status {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to send webhook: {str(e)}")

    def _generate_report(self) -> Dict[str, Any]:
        """Generate final job report"""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "metrics": self.metrics.to_dict(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "processing_time_ms": self.metrics.processing_time_ms,
            "errors": self.errors[:100],  # Limit errors in response
            "summary": {
                "total_records": self.metrics.total_records,
                "enriched": self.metrics.enriched_count,
                "failed": self.metrics.failed_count,
                "skipped": self.metrics.skipped_count,
                "success_rate": f"{self.metrics.success_rate:.1f}%",
                "data_completeness": f"{self.metrics.avg_data_completeness:.1f}%",
                "linkedin_found": self.metrics.linkedin_found,
                "phone_found": self.metrics.phone_found,
                "website_found": self.metrics.website_found,
                "company_data_found": self.metrics.company_data_found
            }
        }


class BulkEnrichmentService:
    """Service for managing bulk enrichment operations"""

    def __init__(self, db_manager: DatabaseConnectionManager, websocket_manager: Optional[SignalRManager] = None):
        self.db_manager = db_manager
        self.websocket_manager = websocket_manager
        self.active_jobs = {}
        self.job_queue = asyncio.Queue()
        self.worker_task = None
        self.max_concurrent_jobs = 3

    async def initialize(self):
        """Initialize the service and ensure required tables exist"""
        await self._ensure_enrichment_tables()

        # Start background worker
        if not self.worker_task or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._job_worker())
            logger.info("Bulk enrichment service initialized")

    async def _ensure_enrichment_tables(self):
        """Ensure enrichment-specific tables exist"""
        enrichment_tables_sql = """
        -- Apollo enrichments table
        CREATE TABLE IF NOT EXISTS apollo_enrichments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            record_id VARCHAR(255) UNIQUE,
            email VARCHAR(255),
            enriched_data JSONB NOT NULL,
            data_completeness DECIMAL(5,2),
            job_id VARCHAR(255),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Enrichment jobs table
        CREATE TABLE IF NOT EXISTS enrichment_jobs (
            job_id VARCHAR(255) PRIMARY KEY,
            request_data JSONB NOT NULL,
            status VARCHAR(50) NOT NULL,
            priority INTEGER DEFAULT 2,
            metrics JSONB,
            start_time TIMESTAMPTZ,
            end_time TIMESTAMPTZ,
            errors JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Enrichment schedule table
        CREATE TABLE IF NOT EXISTS enrichment_schedules (
            schedule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            cron_expression VARCHAR(100),
            filters JSONB,
            config JSONB NOT NULL,
            is_active BOOLEAN DEFAULT true,
            last_run TIMESTAMPTZ,
            next_run TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Enrichment schedule history table
        CREATE TABLE IF NOT EXISTS enrichment_schedule_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            schedule_id VARCHAR(255) NOT NULL,
            job_id VARCHAR(255) NOT NULL,
            executed_at TIMESTAMPTZ DEFAULT NOW(),
            success BOOLEAN DEFAULT true,
            error_message TEXT
        );

        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_apollo_enrichments_email ON apollo_enrichments(email);
        CREATE INDEX IF NOT EXISTS idx_apollo_enrichments_record_id ON apollo_enrichments(record_id);
        CREATE INDEX IF NOT EXISTS idx_apollo_enrichments_job_id ON apollo_enrichments(job_id);
        CREATE INDEX IF NOT EXISTS idx_enrichment_jobs_status ON enrichment_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_enrichment_jobs_priority ON enrichment_jobs(priority);
        CREATE INDEX IF NOT EXISTS idx_enrichment_schedules_active ON enrichment_schedules(is_active);
        CREATE INDEX IF NOT EXISTS idx_enrichment_schedules_next_run ON enrichment_schedules(next_run);
        CREATE INDEX IF NOT EXISTS idx_schedule_history_schedule_id ON enrichment_schedule_history(schedule_id);
        CREATE INDEX IF NOT EXISTS idx_schedule_history_executed_at ON enrichment_schedule_history(executed_at DESC);
        """

        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute(enrichment_tables_sql)
            logger.info("Enrichment tables ensured")
        except Exception as e:
            logger.error(f"Failed to create enrichment tables: {str(e)}")
            raise

    async def create_job(self, request: BulkEnrichmentRequest) -> str:
        """Create a new enrichment job"""
        job_id = f"enrich_{uuid4().hex[:12]}"

        # Create job instance
        job = EnrichmentJob(
            job_id=job_id,
            request=request,
            db_manager=self.db_manager,
            websocket_manager=self.websocket_manager
        )

        # Add to queue based on priority
        await self.job_queue.put((request.priority.value, job_id, job))

        # Store job in active jobs
        self.active_jobs[job_id] = job

        logger.info(f"Created enrichment job {job_id} with priority {request.priority.name}")

        return job_id

    async def _job_worker(self):
        """Background worker to process enrichment jobs"""
        while True:
            try:
                # Get next job from queue (prioritized)
                priority, job_id, job = await self.job_queue.get()

                # Check concurrent job limit
                active_count = sum(1 for j in self.active_jobs.values()
                                   if j.status == EnrichmentStatus.IN_PROGRESS)

                if active_count >= self.max_concurrent_jobs:
                    # Re-queue the job
                    await self.job_queue.put((priority, job_id, job))
                    await asyncio.sleep(5)  # Wait before checking again
                    continue

                # Execute the job
                logger.info(f"Starting job {job_id}")
                asyncio.create_task(self._execute_job(job))

            except asyncio.CancelledError:
                logger.info("Job worker cancelled")
                break
            except Exception as e:
                logger.error(f"Job worker error: {str(e)}")
                await asyncio.sleep(5)

    async def _execute_job(self, job: EnrichmentJob):
        """Execute a job and clean up"""
        try:
            await job.execute()
        finally:
            # Remove from active jobs after completion
            if job.job_id in self.active_jobs:
                del self.active_jobs[job.job_id]

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job"""
        # Check active jobs first
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            return {
                "job_id": job_id,
                "status": job.status.value,
                "metrics": job.metrics.to_dict(),
                "current_batch": job.current_batch,
                "total_batches": job.total_batches,
                "errors": job.errors[:10]
            }

        # Check database for completed jobs
        try:
            async with self.db_manager.get_connection() as conn:
                result = await conn.fetchrow("""
                    SELECT job_id, status, metrics, start_time, end_time, errors
                    FROM enrichment_jobs
                    WHERE job_id = $1
                """, job_id)

                if result:
                    return {
                        "job_id": result["job_id"],
                        "status": result["status"],
                        "metrics": json.loads(result["metrics"]) if result["metrics"] else {},
                        "start_time": result["start_time"].isoformat() if result["start_time"] else None,
                        "end_time": result["end_time"].isoformat() if result["end_time"] else None,
                        "errors": json.loads(result["errors"]) if result["errors"] else []
                    }
        except Exception as e:
            logger.error(f"Failed to get job status from database: {str(e)}")

        return None

    async def get_enrichment_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get enrichment statistics for the specified period"""
        try:
            async with self.db_manager.get_connection() as conn:
                since_date = datetime.now(timezone.utc) - timedelta(days=days)

                # Get overall stats
                stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_enrichments,
                        AVG(data_completeness) as avg_completeness,
                        COUNT(DISTINCT job_id) as total_jobs,
                        COUNT(DISTINCT email) as unique_emails
                    FROM apollo_enrichments
                    WHERE created_at >= $1
                """, since_date)

                # Get job stats
                job_stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_jobs,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_jobs,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_jobs,
                        AVG((metrics->>'processing_time_ms')::int) as avg_processing_time
                    FROM enrichment_jobs
                    WHERE created_at >= $1
                """, since_date)

                return {
                    "period_days": days,
                    "total_enrichments": stats["total_enrichments"],
                    "avg_data_completeness": float(stats["avg_completeness"]) if stats["avg_completeness"] else 0,
                    "unique_emails_enriched": stats["unique_emails"],
                    "total_jobs": job_stats["total_jobs"],
                    "completed_jobs": job_stats["completed_jobs"],
                    "failed_jobs": job_stats["failed_jobs"],
                    "avg_processing_time_ms": job_stats["avg_processing_time"],
                    "active_jobs": len(self.active_jobs)
                }

        except Exception as e:
            logger.error(f"Failed to get enrichment stats: {str(e)}")
            return {}

    async def cleanup(self):
        """Clean up resources"""
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        logger.info("Bulk enrichment service cleaned up")