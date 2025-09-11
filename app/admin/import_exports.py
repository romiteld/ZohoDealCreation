"""
TalentWell CSV import system for Zoho exports.
Imports and processes Steve Perry's deals from Jan 1 - Sep 8, 2025.
"""

import csv
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import re
import io

from app.integrations import PostgreSQLClient

logger = logging.getLogger(__name__)


class TalentWellImporter:
    """Import and process Zoho CSV exports for TalentWell digest system."""
    
    def __init__(self):
        self.owner_filter = "Steve Perry"
        self.start_date = datetime(2025, 1, 1)
        self.end_date = datetime(2025, 9, 8)
        self.postgres_client = PostgreSQLClient()
        
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats from CSV exports."""
        if not date_str or date_str.strip() == "":
            return None
        
        # Common Zoho date formats
        formats = [
            "%Y-%m-%d %H:%M:%S",  # 2025-01-15 10:30:00
            "%Y-%m-%d",           # 2025-01-15
            "%m/%d/%Y",           # 01/15/2025
            "%m/%d/%Y %I:%M %p",  # 01/15/2025 10:30 AM
            "%d-%b-%Y",           # 15-Jan-2025
            "%d-%b-%Y %H:%M",     # 15-Jan-2025 10:30
            "%m-%d-%Y",           # 01-15-2025
            "%Y/%m/%d",           # 2025/01/15
            "%m/%d/%y",           # 01/15/25
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: '{date_str}'")
        return None
    
    def filter_by_date_range(self, record: Dict[str, Any], date_fields: List[str]) -> bool:
        """Check if record falls within the target date range."""
        for field in date_fields:
            date_str = record.get(field, "")
            if date_str:
                parsed_date = self.parse_date(date_str)
                if parsed_date and self.start_date <= parsed_date <= self.end_date:
                    return True
        return False
    
    def process_deals_csv(self, csv_content: str) -> List[Dict[str, Any]]:
        """Process deals CSV content."""
        deals = []
        reader = csv.DictReader(io.StringIO(csv_content))
        
        for row in reader:
            # Filter by owner
            owner = row.get('Deal Owner', '').strip()
            if owner != self.owner_filter:
                continue
            
            # Filter by date range
            if not self.filter_by_date_range(row, ['Created Time', 'Closing Date', 'Modified Time']):
                continue
            
            # Process deal record
            deal = {
                'id': row.get('Deal Id', '').strip(),
                'candidate_name': row.get('Deal Name', '').strip(),
                'job_title': row.get('Job Title', '').strip(),
                'firm_name': row.get('Account Name', '').strip(),
                'location': row.get('Location', '').strip(),
                'owner': owner,
                'stage': row.get('Stage', '').strip(),
                'created_date': self.parse_date(row.get('Created Time', '')),
                'closing_date': self.parse_date(row.get('Closing Date', '')),
                'source': row.get('Lead Source', '').strip(),
                'source_detail': row.get('Source Detail', '').strip(),
                'referrer_name': row.get('Referrer Name', '').strip(),
                'description': row.get('Description', '').strip(),
                'amount': self.parse_numeric(row.get('Amount', '')),
                'raw_data': dict(row)  # Store original CSV data
            }
            
            if deal['id']:  # Only add deals with valid IDs
                deals.append(deal)
        
        logger.info(f"Processed {len(deals)} deals for {self.owner_filter}")
        return deals
    
    def process_stage_history_csv(self, csv_content: str) -> List[Dict[str, Any]]:
        """Process deal stage history CSV content."""
        history = []
        reader = csv.DictReader(io.StringIO(csv_content))
        
        for row in reader:
            # Filter by date range
            if not self.filter_by_date_range(row, ['Changed Time']):
                continue
            
            record = {
                'deal_id': row.get('Deal Id', '').strip(),
                'stage': row.get('Stage', '').strip(),
                'changed_time': self.parse_date(row.get('Changed Time', '')),
                'duration_days': self.parse_numeric(row.get('Duration', '')),
                'changed_by': row.get('Changed By', '').strip()
            }
            
            if record['deal_id']:
                history.append(record)
        
        logger.info(f"Processed {len(history)} stage history records")
        return history
    
    def process_meetings_csv(self, csv_content: str) -> List[Dict[str, Any]]:
        """Process meetings CSV content."""
        meetings = []
        reader = csv.DictReader(io.StringIO(csv_content))
        
        for row in reader:
            # Filter by date range
            if not self.filter_by_date_range(row, ['Start DateTime', 'Created Time']):
                continue
            
            record = {
                'deal_id': row.get('Deal Id', '').strip() or row.get('Related To', '').strip(),
                'title': row.get('Title', '').strip(),
                'start_datetime': self.parse_date(row.get('Start DateTime', '')),
                'participants': row.get('Participants', '').strip(),
                'email_opened': row.get('Email Opened', '').strip().lower() == 'yes',
                'link_clicked': row.get('Link Clicked', '').strip().lower() == 'yes',
                'raw_data': dict(row)
            }
            
            if record['deal_id']:
                meetings.append(record)
        
        logger.info(f"Processed {len(meetings)} meeting records")
        return meetings
    
    def process_notes_csv(self, csv_content: str) -> List[Dict[str, Any]]:
        """Process deal notes CSV content."""
        notes = []
        reader = csv.DictReader(io.StringIO(csv_content))
        
        for row in reader:
            # Filter by date range
            if not self.filter_by_date_range(row, ['Created Time', 'Modified Time']):
                continue
            
            record = {
                'deal_id': row.get('Deal Id', '').strip() or row.get('Parent Id', '').strip(),
                'note_content': row.get('Note Content', '').strip(),
                'created_at': self.parse_date(row.get('Created Time', '')),
                'created_by': row.get('Note Owner', '').strip() or row.get('Created By', '').strip()
            }
            
            if record['deal_id'] and record['note_content']:
                notes.append(record)
        
        logger.info(f"Processed {len(notes)} note records")
        return notes
    
    def parse_numeric(self, value: str) -> Optional[float]:
        """Parse numeric value from string."""
        if not value or value.strip() == "":
            return None
        
        # Remove currency symbols and commas
        cleaned = re.sub(r'[$,]', '', value.strip())
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    async def upsert_deals(self, deals: List[Dict[str, Any]]) -> int:
        """Upsert deals into the database."""
        if not deals:
            return 0
        
        await self.postgres_client.init_pool()
        
        upsert_sql = """
        INSERT INTO deals (
            id, candidate_name, job_title, firm_name, location, owner, stage,
            created_date, closing_date, source, source_detail, referrer_name,
            description, amount, raw_data
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        ON CONFLICT (id) DO UPDATE SET
            candidate_name = EXCLUDED.candidate_name,
            job_title = EXCLUDED.job_title,
            firm_name = EXCLUDED.firm_name,
            location = EXCLUDED.location,
            owner = EXCLUDED.owner,
            stage = EXCLUDED.stage,
            created_date = EXCLUDED.created_date,
            closing_date = EXCLUDED.closing_date,
            source = EXCLUDED.source,
            source_detail = EXCLUDED.source_detail,
            referrer_name = EXCLUDED.referrer_name,
            description = EXCLUDED.description,
            amount = EXCLUDED.amount,
            raw_data = EXCLUDED.raw_data,
            imported_at = NOW()
        """
        
        async with self.postgres_client.pool.acquire() as conn:
            for deal in deals:
                await conn.execute(
                    upsert_sql,
                    deal['id'], deal['candidate_name'], deal['job_title'],
                    deal['firm_name'], deal['location'], deal['owner'],
                    deal['stage'], deal['created_date'], deal['closing_date'],
                    deal['source'], deal['source_detail'], deal['referrer_name'],
                    deal['description'], deal['amount'], json.dumps(deal['raw_data'])
                )
        
        logger.info(f"Upserted {len(deals)} deals")
        return len(deals)
    
    async def upsert_stage_history(self, history: List[Dict[str, Any]]) -> int:
        """Upsert stage history into the database."""
        if not history:
            return 0
        
        await self.postgres_client.init_pool()
        
        # First, get existing deal IDs to validate references
        deal_ids = set()
        async with self.postgres_client.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM deals WHERE owner = $1", self.owner_filter)
            deal_ids = {row['id'] for row in rows}
        
        # Filter history to only include valid deal references
        valid_history = [h for h in history if h['deal_id'] in deal_ids]
        
        if not valid_history:
            logger.warning("No valid stage history records found with matching deal IDs")
            return 0
        
        upsert_sql = """
        INSERT INTO deal_stage_history (
            deal_id, stage, changed_time, duration_days, changed_by
        ) VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (deal_id, stage, changed_time) DO UPDATE SET
            duration_days = EXCLUDED.duration_days,
            changed_by = EXCLUDED.changed_by,
            imported_at = NOW()
        """
        
        async with self.postgres_client.pool.acquire() as conn:
            for record in valid_history:
                await conn.execute(
                    upsert_sql,
                    record['deal_id'], record['stage'], record['changed_time'],
                    record['duration_days'], record['changed_by']
                )
        
        logger.info(f"Upserted {len(valid_history)} stage history records")
        return len(valid_history)
    
    async def upsert_meetings(self, meetings: List[Dict[str, Any]]) -> int:
        """Upsert meetings into the database."""
        if not meetings:
            return 0
        
        await self.postgres_client.init_pool()
        
        # Get existing deal IDs
        deal_ids = set()
        async with self.postgres_client.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM deals WHERE owner = $1", self.owner_filter)
            deal_ids = {row['id'] for row in rows}
        
        # Filter meetings to only include valid deal references
        valid_meetings = [m for m in meetings if m['deal_id'] in deal_ids]
        
        if not valid_meetings:
            logger.warning("No valid meeting records found with matching deal IDs")
            return 0
        
        upsert_sql = """
        INSERT INTO meetings (
            deal_id, title, start_datetime, participants, email_opened, link_clicked, raw_data
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (deal_id, title, start_datetime) DO UPDATE SET
            participants = EXCLUDED.participants,
            email_opened = EXCLUDED.email_opened,
            link_clicked = EXCLUDED.link_clicked,
            raw_data = EXCLUDED.raw_data,
            imported_at = NOW()
        """
        
        async with self.postgres_client.pool.acquire() as conn:
            for meeting in valid_meetings:
                await conn.execute(
                    upsert_sql,
                    meeting['deal_id'], meeting['title'], meeting['start_datetime'],
                    meeting['participants'], meeting['email_opened'], meeting['link_clicked'],
                    json.dumps(meeting['raw_data'])
                )
        
        logger.info(f"Upserted {len(valid_meetings)} meeting records")
        return len(valid_meetings)
    
    async def upsert_notes(self, notes: List[Dict[str, Any]]) -> int:
        """Upsert notes into the database."""
        if not notes:
            return 0
        
        await self.postgres_client.init_pool()
        
        # Get existing deal IDs
        deal_ids = set()
        async with self.postgres_client.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM deals WHERE owner = $1", self.owner_filter)
            deal_ids = {row['id'] for row in rows}
        
        # Filter notes to only include valid deal references
        valid_notes = [n for n in notes if n['deal_id'] in deal_ids]
        
        if not valid_notes:
            logger.warning("No valid note records found with matching deal IDs")
            return 0
        
        upsert_sql = """
        INSERT INTO deal_notes (
            deal_id, note_content, created_at, created_by
        ) VALUES ($1, $2, $3, $4)
        ON CONFLICT (deal_id, note_content, created_at) DO UPDATE SET
            created_by = EXCLUDED.created_by,
            imported_at = NOW()
        """
        
        async with self.postgres_client.pool.acquire() as conn:
            for note in valid_notes:
                await conn.execute(
                    upsert_sql,
                    note['deal_id'], note['note_content'],
                    note['created_at'], note['created_by']
                )
        
        logger.info(f"Upserted {len(valid_notes)} note records")
        return len(valid_notes)
    
    async def import_csv_data(self, csv_data: Dict[str, str]) -> Dict[str, Any]:
        """Import all CSV data types and return summary."""
        summary = {
            'deals': 0,
            'stage_history': 0,
            'meetings': 0,
            'notes': 0,
            'owner': self.owner_filter,
            'date_range': f"{self.start_date.date()} to {self.end_date.date()}"
        }
        
        try:
            # Process deals first (required for foreign key references)
            if 'deals' in csv_data:
                deals = self.process_deals_csv(csv_data['deals'])
                summary['deals'] = await self.upsert_deals(deals)
            
            # Process stage history
            if 'stage_history' in csv_data:
                history = self.process_stage_history_csv(csv_data['stage_history'])
                summary['stage_history'] = await self.upsert_stage_history(history)
            
            # Process meetings
            if 'meetings' in csv_data:
                meetings = self.process_meetings_csv(csv_data['meetings'])
                summary['meetings'] = await self.upsert_meetings(meetings)
            
            # Process notes
            if 'notes' in csv_data:
                notes = self.process_notes_csv(csv_data['notes'])
                summary['notes'] = await self.upsert_notes(notes)
            
            logger.info(f"Import completed: {summary}")
            return {
                'status': 'success',
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'summary': summary
            }


# Create singleton instance
importer = TalentWellImporter()