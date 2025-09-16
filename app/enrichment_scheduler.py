"""
Scheduled Enrichment Job Manager

Handles periodic enrichment of records based on configurable schedules:
- Cron-based scheduling
- Priority-based enrichment
- Automatic retry for failed records
- Smart selection of records needing enrichment
"""

import os
import json
import logging
import asyncio
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum
from croniter import croniter
from uuid import uuid4

from app.bulk_enrichment_service import (
    BulkEnrichmentService,
    BulkEnrichmentRequest,
    EnrichmentPriority
)
from app.database_connection_manager import DatabaseConnectionManager

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Types of enrichment schedules"""
    HOURLY = "0 * * * *"           # Every hour
    DAILY = "0 0 * * *"            # Daily at midnight
    WEEKLY = "0 0 * * 0"           # Weekly on Sunday
    MONTHLY = "0 0 1 * *"          # Monthly on the 1st
    CUSTOM = "custom"              # Custom cron expression


@dataclass
class EnrichmentSchedule:
    """Configuration for a scheduled enrichment job"""
    schedule_id: str
    name: str
    cron_expression: str
    filters: Dict[str, Any]
    config: Dict[str, Any]
    is_active: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None

    def calculate_next_run(self, from_time: Optional[datetime] = None) -> datetime:
        """Calculate the next run time based on cron expression"""
        base_time = from_time or datetime.now(timezone.utc)
        cron = croniter(self.cron_expression, base_time)
        return cron.get_next(datetime)

    def should_run(self) -> bool:
        """Check if the schedule should run now"""
        if not self.is_active:
            return False

        now = datetime.now(timezone.utc)
        if self.next_run and now >= self.next_run:
            return True

        return False


class EnrichmentScheduler:
    """Manages scheduled enrichment jobs"""

    def __init__(
        self,
        db_manager: DatabaseConnectionManager,
        enrichment_service: BulkEnrichmentService
    ):
        self.db_manager = db_manager
        self.enrichment_service = enrichment_service
        self.schedules: Dict[str, EnrichmentSchedule] = {}
        self.scheduler_task = None
        self.check_interval = 60  # Check schedules every minute

    async def initialize(self):
        """Initialize the scheduler and load schedules"""
        await self._load_schedules()
        await self._start_scheduler()
        logger.info("Enrichment scheduler initialized")

    async def _load_schedules(self):
        """Load active schedules from database"""
        try:
            async with self.db_manager.get_connection() as conn:
                results = await conn.fetch("""
                    SELECT schedule_id, name, cron_expression, filters,
                           config, is_active, last_run, next_run
                    FROM enrichment_schedules
                    WHERE is_active = true
                """)

                for row in results:
                    schedule = EnrichmentSchedule(
                        schedule_id=row["schedule_id"],
                        name=row["name"],
                        cron_expression=row["cron_expression"],
                        filters=json.loads(row["filters"]) if row["filters"] else {},
                        config=json.loads(row["config"]) if row["config"] else {},
                        is_active=row["is_active"],
                        last_run=row["last_run"],
                        next_run=row["next_run"]
                    )

                    # Calculate next run if not set
                    if not schedule.next_run:
                        schedule.next_run = schedule.calculate_next_run()

                    self.schedules[schedule.schedule_id] = schedule

                logger.info(f"Loaded {len(self.schedules)} active schedules")

        except Exception as e:
            logger.error(f"Failed to load schedules: {str(e)}")

    async def _start_scheduler(self):
        """Start the scheduler background task"""
        if not self.scheduler_task or self.scheduler_task.done():
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())
            logger.info("Scheduler background task started")

    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while True:
            try:
                # Check each schedule
                for schedule_id, schedule in self.schedules.items():
                    if schedule.should_run():
                        await self._execute_schedule(schedule)

                # Wait before next check
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {str(e)}")
                await asyncio.sleep(self.check_interval)

    async def _execute_schedule(self, schedule: EnrichmentSchedule):
        """Execute a scheduled enrichment job"""
        try:
            logger.info(f"Executing schedule: {schedule.name}")

            # Build enrichment request from schedule config
            request = BulkEnrichmentRequest(
                filters=schedule.filters,
                priority=EnrichmentPriority[schedule.config.get("priority", "BACKGROUND")],
                batch_size=schedule.config.get("batch_size", 50),
                include_company=schedule.config.get("include_company", True),
                include_employees=schedule.config.get("include_employees", False),
                update_zoho=schedule.config.get("update_zoho", True)
            )

            # Create and execute job
            job_id = await self.enrichment_service.create_job(request)

            # Update schedule record
            schedule.last_run = datetime.now(timezone.utc)
            schedule.next_run = schedule.calculate_next_run()

            await self._update_schedule_in_db(schedule)

            # Store schedule execution history
            await self._record_schedule_execution(schedule.schedule_id, job_id)

            logger.info(f"Schedule {schedule.name} executed with job {job_id}")

        except Exception as e:
            logger.error(f"Failed to execute schedule {schedule.name}: {str(e)}")

    async def _update_schedule_in_db(self, schedule: EnrichmentSchedule):
        """Update schedule in database"""
        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE enrichment_schedules
                    SET last_run = $1, next_run = $2, updated_at = NOW()
                    WHERE schedule_id = $3
                """, schedule.last_run, schedule.next_run, schedule.schedule_id)

        except Exception as e:
            logger.error(f"Failed to update schedule in database: {str(e)}")

    async def _record_schedule_execution(self, schedule_id: str, job_id: str):
        """Record schedule execution history"""
        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO enrichment_schedule_history (
                        schedule_id, job_id, executed_at
                    ) VALUES ($1, $2, $3)
                """, schedule_id, job_id, datetime.now(timezone.utc))

        except Exception as e:
            logger.warning(f"Failed to record schedule execution: {str(e)}")

    async def create_schedule(
        self,
        name: str,
        schedule_type: ScheduleType,
        filters: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        custom_cron: Optional[str] = None
    ) -> str:
        """Create a new enrichment schedule"""
        schedule_id = str(uuid4())

        # Determine cron expression
        if schedule_type == ScheduleType.CUSTOM and custom_cron:
            cron_expression = custom_cron
        else:
            cron_expression = schedule_type.value

        # Validate cron expression
        try:
            croniter(cron_expression)
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {str(e)}")

        # Create schedule object
        schedule = EnrichmentSchedule(
            schedule_id=schedule_id,
            name=name,
            cron_expression=cron_expression,
            filters=filters or {},
            config=config or {},
            is_active=True,
            next_run=None
        )

        schedule.next_run = schedule.calculate_next_run()

        # Save to database
        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO enrichment_schedules (
                        schedule_id, name, cron_expression, filters,
                        config, is_active, next_run, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                    schedule_id,
                    name,
                    cron_expression,
                    json.dumps(filters or {}),
                    json.dumps(config or {}),
                    True,
                    schedule.next_run,
                    datetime.now(timezone.utc)
                )

            # Add to active schedules
            self.schedules[schedule_id] = schedule

            logger.info(f"Created schedule: {name} ({schedule_id})")
            return schedule_id

        except Exception as e:
            logger.error(f"Failed to create schedule: {str(e)}")
            raise

    async def update_schedule(
        self,
        schedule_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update an existing schedule"""
        if schedule_id not in self.schedules:
            logger.warning(f"Schedule {schedule_id} not found")
            return False

        schedule = self.schedules[schedule_id]

        # Update schedule object
        if "name" in updates:
            schedule.name = updates["name"]
        if "cron_expression" in updates:
            schedule.cron_expression = updates["cron_expression"]
            schedule.next_run = schedule.calculate_next_run()
        if "filters" in updates:
            schedule.filters = updates["filters"]
        if "config" in updates:
            schedule.config = updates["config"]
        if "is_active" in updates:
            schedule.is_active = updates["is_active"]

        # Save to database
        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE enrichment_schedules
                    SET name = $1, cron_expression = $2, filters = $3,
                        config = $4, is_active = $5, next_run = $6,
                        updated_at = NOW()
                    WHERE schedule_id = $7
                """,
                    schedule.name,
                    schedule.cron_expression,
                    json.dumps(schedule.filters),
                    json.dumps(schedule.config),
                    schedule.is_active,
                    schedule.next_run,
                    schedule_id
                )

            logger.info(f"Updated schedule: {schedule_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update schedule: {str(e)}")
            return False

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule"""
        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    DELETE FROM enrichment_schedules
                    WHERE schedule_id = $1
                """, schedule_id)

            # Remove from active schedules
            if schedule_id in self.schedules:
                del self.schedules[schedule_id]

            logger.info(f"Deleted schedule: {schedule_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete schedule: {str(e)}")
            return False

    async def get_schedules(self) -> List[Dict[str, Any]]:
        """Get all schedules"""
        result = []
        for schedule in self.schedules.values():
            result.append({
                "schedule_id": schedule.schedule_id,
                "name": schedule.name,
                "cron_expression": schedule.cron_expression,
                "filters": schedule.filters,
                "config": schedule.config,
                "is_active": schedule.is_active,
                "last_run": schedule.last_run.isoformat() if schedule.last_run else None,
                "next_run": schedule.next_run.isoformat() if schedule.next_run else None
            })
        return result

    async def cleanup(self):
        """Clean up scheduler resources"""
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("Enrichment scheduler cleaned up")


# Predefined schedule templates
SCHEDULE_TEMPLATES = {
    "daily_missing_data": {
        "name": "Daily Missing Data Enrichment",
        "schedule_type": ScheduleType.DAILY,
        "filters": {
            "missing_linkedin": True,
            "missing_phone": True,
            "created_after": "30_days_ago"  # Will be processed to actual date
        },
        "config": {
            "priority": "BACKGROUND",
            "batch_size": 50,
            "include_company": True,
            "include_employees": False,
            "update_zoho": True
        }
    },
    "weekly_new_contacts": {
        "name": "Weekly New Contact Enrichment",
        "schedule_type": ScheduleType.WEEKLY,
        "filters": {
            "created_after": "7_days_ago"
        },
        "config": {
            "priority": "LOW",
            "batch_size": 100,
            "include_company": True,
            "include_employees": True,
            "update_zoho": True
        }
    },
    "hourly_high_priority": {
        "name": "Hourly High Priority Enrichment",
        "schedule_type": ScheduleType.HOURLY,
        "filters": {
            "source": "Referral",
            "created_after": "1_hour_ago"
        },
        "config": {
            "priority": "HIGH",
            "batch_size": 25,
            "include_company": True,
            "include_employees": True,
            "update_zoho": True
        }
    }
}


async def create_default_schedules(
    db_manager: DatabaseConnectionManager,
    enrichment_service: BulkEnrichmentService
) -> EnrichmentScheduler:
    """Create scheduler with default schedules"""
    scheduler = EnrichmentScheduler(db_manager, enrichment_service)
    await scheduler.initialize()

    # Check if default schedules already exist
    existing_schedules = await scheduler.get_schedules()
    existing_names = {s["name"] for s in existing_schedules}

    # Create default schedules if they don't exist
    for template_key, template in SCHEDULE_TEMPLATES.items():
        if template["name"] not in existing_names:
            # Process date filters
            filters = template["filters"].copy()
            for key, value in filters.items():
                if isinstance(value, str) and value.endswith("_ago"):
                    # Convert relative date to actual date
                    parts = value.split("_")
                    if len(parts) >= 2:
                        amount = int(parts[0]) if parts[0].isdigit() else 1
                        unit = parts[1]
                        if unit == "days":
                            filters[key] = (datetime.now(timezone.utc) - timedelta(days=amount)).isoformat()
                        elif unit == "hours":
                            filters[key] = (datetime.now(timezone.utc) - timedelta(hours=amount)).isoformat()

            await scheduler.create_schedule(
                name=template["name"],
                schedule_type=template["schedule_type"],
                filters=filters,
                config=template["config"]
            )
            logger.info(f"Created default schedule: {template['name']}")

    return scheduler