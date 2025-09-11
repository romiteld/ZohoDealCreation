"""
Bulletproof CSV Import System v2
Handles CSV/XLSX imports with resilient column mapping, idempotent upserts, and comprehensive observability.
"""

import os
import io
import json
import hashlib
import logging
import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple, Union
from contextlib import asynccontextmanager
import chardet
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import aiofiles
from tempfile import NamedTemporaryFile
import shutil

# Import database client
from ..integrations import PostgreSQLClient

# Import monitoring
try:
    from ..monitoring import MonitoringService
    HAS_MONITORING = True
except ImportError:
    HAS_MONITORING = False
    MonitoringService = None

# Configure logging
logger = logging.getLogger(__name__)

# Constants
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
MAX_ROWS = 100000  # Prevent OOM
UPLOAD_DIR = Path("/mnt/data/uploads")
LOCAL_IMPORT_DIR = Path("app/admin/imports")
CLEANUP_HOURS = 24

# Column mapping aliases for resilient parsing
COLUMN_MAPPINGS = {
    "deals": {
        # Primary identifiers
        "record id": "deal_id",
        "deal id": "deal_id",
        "id": "deal_id",
        
        # Deal name
        "deal name": "deal_name",
        "subject": "deal_name",
        "name": "deal_name",
        "title": "deal_name",
        
        # Account/Company
        "account name": "account_name",
        "company name": "account_name",
        "client": "account_name",
        "company": "account_name",
        "organization": "account_name",
        
        # Owner
        "owner": "owner_name",
        "owner name": "owner_name",
        "assigned to": "owner_name",
        "deal owner": "owner_name",
        
        # Amount
        "amount": "amount_usd",
        "amount usd": "amount_usd",
        "deal amount": "amount_usd",
        "value": "amount_usd",
        
        # Stage
        "stage": "stage",
        "deal stage": "stage",
        "pipeline stage": "stage",
        "status": "stage",
        
        # Dates
        "created date": "created_date",
        "created time": "created_date",
        "created at": "created_date",
        "creation date": "created_date",
        
        "closing date": "closing_date",
        "close date": "closing_date",
        "expected close": "closing_date",
        
        # Source fields
        "source": "source",
        "lead source": "source",
        "source detail": "source_detail",
        "referrer name": "referrer_name",
        "referrer": "referrer_name",
        
        # Other fields
        "description": "description",
        "notes": "description",
        "details": "description",
    },
    
    "stages": {
        "deal id": "deal_id",
        "record id": "deal_id",
        "from stage": "from_stage",
        "previous stage": "from_stage",
        "to stage": "to_stage",
        "new stage": "to_stage",
        "current stage": "to_stage",
        "modified time": "moved_at",
        "moved at": "moved_at",
        "changed at": "moved_at",
        "stage changed": "moved_at",
        "modified by": "modified_by",
        "changed by": "modified_by",
    },
    
    "meetings": {
        "subject": "subject",
        "title": "subject",
        "meeting subject": "subject",
        "meeting title": "subject",
        "start time": "meeting_date",
        "meeting date": "meeting_date",
        "start date": "meeting_date",
        "scheduled for": "meeting_date",
        "opened": "opened",
        "opens": "opened",
        "email opened": "opened",
        "clicked": "clicked",
        "clicks": "clicked",
        "link clicked": "clicked",
        "deal id": "deal_id",
        "related to": "deal_id",
        "participants": "participants",
        "attendees": "participants",
    },
    
    "notes": {
        "deal id": "deal_id",
        "related to": "deal_id",
        "note content": "note_text",
        "note": "note_text",
        "content": "note_text",
        "text": "note_text",
        "description": "note_text",
        "created time": "created_at",
        "created at": "created_at",
        "note date": "created_at",
        "created by": "created_by",
        "author": "created_by",
        "note owner": "created_by",
    }
}


class ImportRequest(BaseModel):
    """Request model for CSV imports"""
    paths: Optional[Dict[str, str]] = Field(
        None,
        description="Custom file paths for each entity type"
    )
    
    @validator('paths')
    def validate_paths(cls, v):
        if v:
            for entity_type, path in v.items():
                if entity_type not in ['deals', 'stages', 'meetings', 'notes']:
                    raise ValueError(f"Unknown entity type: {entity_type}")
                if not Path(path).exists():
                    raise ValueError(f"File not found: {path}")
        return v


class ImportService:
    """Service for handling CSV/XLSX imports with resilient processing"""
    
    def __init__(self):
        connection_string = os.getenv('DATABASE_URL')
        if not connection_string:
            raise ValueError("DATABASE_URL environment variable is required")
        self.db_client = PostgreSQLClient(connection_string)
        self.monitoring = MonitoringService() if HAS_MONITORING else None
        
        # Ensure upload directory exists (graceful failure for permissions)
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not create upload directory {UPLOAD_DIR}: {e}")
        
        try:
            LOCAL_IMPORT_DIR.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not create local import directory {LOCAL_IMPORT_DIR}: {e}")
    
    async def cleanup_old_uploads(self):
        """Remove uploaded files older than CLEANUP_HOURS"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=CLEANUP_HOURS)
            
            for file_path in UPLOAD_DIR.glob("*"):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_time:
                        file_path.unlink()
                        logger.info(f"Cleaned up old upload: {file_path.name}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # Read first 10KB
                result = chardet.detect(raw_data)
                return result['encoding'] or 'utf-8'
        except Exception:
            return 'utf-8'
    
    def normalize_column_name(self, column: str, entity_type: str) -> str:
        """Normalize column names using mapping aliases"""
        column_lower = column.lower().strip()
        
        # Check if we have mappings for this entity type
        if entity_type in COLUMN_MAPPINGS:
            mappings = COLUMN_MAPPINGS[entity_type]
            if column_lower in mappings:
                return mappings[column_lower]
        
        # Return cleaned version if no mapping found
        return column_lower.replace(' ', '_').replace('-', '_')
    
    def read_file(self, file_path: Path, entity_type: str) -> Tuple[pd.DataFrame, List[str]]:
        """Read CSV or XLSX file with encoding detection and column normalization"""
        unknown_headers = []
        
        try:
            # Determine file type
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, engine='openpyxl')
            else:
                # Try different encodings
                encodings = ['utf-8', 'latin-1', 'cp1252']
                detected_encoding = self.detect_encoding(file_path)
                if detected_encoding and detected_encoding not in encodings:
                    encodings.insert(0, detected_encoding)
                
                df = None
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if df is None:
                    raise ValueError(f"Could not read file with any encoding: {file_path}")
            
            # Remove empty rows
            df = df.dropna(how='all')
            
            # Check row limit
            if len(df) > MAX_ROWS:
                raise ValueError(f"File exceeds maximum rows ({MAX_ROWS}): {len(df)} rows")
            
            # Normalize column names
            original_columns = df.columns.tolist()
            new_columns = {}
            
            for col in original_columns:
                normalized = self.normalize_column_name(col, entity_type)
                new_columns[col] = normalized
                
                # Track unknown headers (but don't log PII)
                if entity_type in COLUMN_MAPPINGS:
                    if col.lower().strip() not in COLUMN_MAPPINGS[entity_type]:
                        unknown_headers.append(col)
            
            df = df.rename(columns=new_columns)
            
            return df, unknown_headers
            
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    
    def generate_note_hash(self, deal_id: str, note_text: str, created_at: str) -> str:
        """Generate hash for note uniqueness"""
        content = f"{deal_id}:{note_text[:100]}:{created_at}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def import_deals(self, df: pd.DataFrame) -> int:
        """Import deals with idempotent upserts"""
        if df.empty:
            return 0
        
        count = 0
        await self.db_client.init_pool()
        
        async with self.db_client.pool.acquire() as conn:
            for _, row in df.iterrows():
                try:
                    # Extract fields with defaults
                    deal_data = {
                        'deal_id': str(row.get('deal_id', '')),
                        'deal_name': str(row.get('deal_name', 'Unknown')),
                        'account_name': str(row.get('account_name', 'Unknown')),
                        'owner_name': str(row.get('owner_name', 'Unknown')),
                        'amount_usd': float(row.get('amount_usd', 0)) if pd.notna(row.get('amount_usd')) else 0,
                        'stage': str(row.get('stage', 'Unknown')),
                        'created_date': pd.to_datetime(row.get('created_date')) if pd.notna(row.get('created_date')) else None,
                        'closing_date': pd.to_datetime(row.get('closing_date')) if pd.notna(row.get('closing_date')) else None,
                        'source': str(row.get('source', 'Unknown')),
                        'source_detail': str(row.get('source_detail', '')) if pd.notna(row.get('source_detail')) else None,
                        'referrer_name': str(row.get('referrer_name', '')) if pd.notna(row.get('referrer_name')) else None,
                        'description': str(row.get('description', '')) if pd.notna(row.get('description')) else None,
                        'raw_data': row.to_dict()
                    }
                    
                    # Skip if no deal_id
                    if not deal_data['deal_id']:
                        continue
                    
                    # Upsert deal
                    await conn.execute("""
                        INSERT INTO deals (
                            deal_id, deal_name, account_name, owner, 
                            amount_usd, stage, created_date, closing_date,
                            source, source_detail, referrer_name, description,
                            raw_json
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT (deal_id) DO UPDATE SET
                            deal_name = EXCLUDED.deal_name,
                            account_name = EXCLUDED.account_name,
                            owner = EXCLUDED.owner,
                            amount_usd = EXCLUDED.amount_usd,
                            stage = EXCLUDED.stage,
                            created_date = EXCLUDED.created_date,
                            closing_date = EXCLUDED.closing_date,
                            source = EXCLUDED.source,
                            source_detail = EXCLUDED.source_detail,
                            referrer_name = EXCLUDED.referrer_name,
                            description = EXCLUDED.description,
                            raw_json = EXCLUDED.raw_json,
                            imported_at = NOW()
                    """, 
                        deal_data['deal_id'],
                        deal_data['deal_name'],
                        deal_data['account_name'],
                        deal_data['owner_name'],
                        deal_data['amount_usd'],
                        deal_data['stage'],
                        deal_data['created_date'],
                        deal_data['closing_date'],
                        deal_data['source'],
                        deal_data['source_detail'],
                        deal_data['referrer_name'],
                        deal_data['description'],
                        json.dumps(deal_data['raw_data'])
                    )
                    count += 1
                    
                except Exception as e:
                    logger.error(f"Error importing deal row: {e}")
                    continue
        
        return count
    
    async def import_stages(self, df: pd.DataFrame) -> int:
        """Import deal stage history with idempotent upserts"""
        if df.empty:
            return 0
        
        count = 0
        await self.db_client.init_pool()
        
        async with self.db_client.pool.acquire() as conn:
            for _, row in df.iterrows():
                try:
                    # Extract fields
                    stage_data = {
                        'deal_id': str(row.get('deal_id', '')),
                        'from_stage': str(row.get('from_stage', '')) if pd.notna(row.get('from_stage')) else None,
                        'to_stage': str(row.get('to_stage', '')),
                        'moved_at': pd.to_datetime(row.get('moved_at')) if pd.notna(row.get('moved_at')) else datetime.now(timezone.utc),
                        'modified_by': str(row.get('modified_by', '')) if pd.notna(row.get('modified_by')) else None
                    }
                    
                    # Skip if no deal_id or to_stage
                    if not stage_data['deal_id'] or not stage_data['to_stage']:
                        continue
                    
                    # Calculate duration if from_stage exists
                    duration_days = None
                    if stage_data['from_stage'] and stage_data['moved_at']:
                        # Try to find previous stage entry to calculate duration
                        prev_stage = await conn.fetchrow("""
                            SELECT moved_at FROM deal_stage_history 
                            WHERE deal_id = $1 AND to_stage = $2
                            ORDER BY moved_at DESC LIMIT 1
                        """, stage_data['deal_id'], stage_data['from_stage'])
                        
                        if prev_stage and prev_stage['moved_at']:
                            duration = stage_data['moved_at'] - prev_stage['moved_at']
                            duration_days = duration.days
                    
                    # Upsert stage history
                    await conn.execute("""
                        INSERT INTO deal_stage_history (
                            deal_id, from_stage, to_stage, moved_at, 
                            modified_by, duration_days
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (deal_id, to_stage, moved_at) DO UPDATE SET
                            from_stage = EXCLUDED.from_stage,
                            modified_by = EXCLUDED.modified_by,
                            duration_days = EXCLUDED.duration_days,
                            imported_at = NOW()
                    """,
                        stage_data['deal_id'],
                        stage_data['from_stage'],
                        stage_data['to_stage'],
                        stage_data['moved_at'],
                        stage_data['modified_by'],
                        duration_days
                    )
                    count += 1
                    
                except Exception as e:
                    logger.error(f"Error importing stage row: {e}")
                    continue
        
        return count
    
    async def import_meetings(self, df: pd.DataFrame) -> int:
        """Import meetings with idempotent upserts"""
        if df.empty:
            return 0
        
        count = 0
        await self.db_client.init_pool()
        
        async with self.db_client.pool.acquire() as conn:
            for _, row in df.iterrows():
                try:
                    # Extract fields
                    meeting_data = {
                        'deal_id': str(row.get('deal_id', '')),
                        'subject': str(row.get('subject', 'Unknown')),
                        'meeting_date': pd.to_datetime(row.get('meeting_date')) if pd.notna(row.get('meeting_date')) else None,
                        'participants': str(row.get('participants', '')) if pd.notna(row.get('participants')) else None,
                        'opened': bool(row.get('opened', False)),
                        'clicked': bool(row.get('clicked', False)),
                        'raw_data': row.to_dict()
                    }
                    
                    # Skip if no deal_id or subject
                    if not meeting_data['deal_id'] or not meeting_data['subject']:
                        continue
                    
                    # Upsert meeting
                    await conn.execute("""
                        INSERT INTO meetings (
                            deal_id, title, start_datetime, participants,
                            email_opened, link_clicked, raw_data
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (deal_id, title, start_datetime) DO UPDATE SET
                            participants = EXCLUDED.participants,
                            email_opened = EXCLUDED.email_opened,
                            link_clicked = EXCLUDED.link_clicked,
                            raw_data = EXCLUDED.raw_data,
                            imported_at = NOW()
                    """,
                        meeting_data['deal_id'],
                        meeting_data['subject'],
                        meeting_data['meeting_date'],
                        meeting_data['participants'],
                        meeting_data['opened'],
                        meeting_data['clicked'],
                        json.dumps(meeting_data['raw_data'])
                    )
                    count += 1
                    
                except Exception as e:
                    logger.error(f"Error importing meeting row: {e}")
                    continue
        
        return count
    
    async def import_notes(self, df: pd.DataFrame) -> int:
        """Import deal notes with idempotent upserts"""
        if df.empty:
            return 0
        
        count = 0
        await self.db_client.init_pool()
        
        async with self.db_client.pool.acquire() as conn:
            for _, row in df.iterrows():
                try:
                    # Extract fields
                    note_data = {
                        'deal_id': str(row.get('deal_id', '')),
                        'note_text': str(row.get('note_text', '')),
                        'created_at': pd.to_datetime(row.get('created_at')) if pd.notna(row.get('created_at')) else datetime.now(timezone.utc),
                        'created_by': str(row.get('created_by', '')) if pd.notna(row.get('created_by')) else None
                    }
                    
                    # Skip if no deal_id or note_text
                    if not note_data['deal_id'] or not note_data['note_text']:
                        continue
                    
                    # Generate note hash for uniqueness
                    note_hash = self.generate_note_hash(
                        note_data['deal_id'],
                        note_data['note_text'],
                        str(note_data['created_at'])
                    )
                    
                    # Upsert note
                    await conn.execute("""
                        INSERT INTO deal_notes (
                            deal_id, note_content, created_at, created_by, note_hash
                        ) VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (deal_id, created_at, note_hash) DO UPDATE SET
                            note_content = EXCLUDED.note_content,
                            created_by = EXCLUDED.created_by,
                            imported_at = NOW()
                    """,
                        note_data['deal_id'],
                        note_data['note_text'],
                        note_data['created_at'],
                        note_data['created_by'],
                        note_hash
                    )
                    count += 1
                    
                except Exception as e:
                    logger.error(f"Error importing note row: {e}")
                    continue
        
        return count
    
    async def process_import(
        self, 
        paths: Optional[Dict[str, str]] = None,
        uploaded_files: Optional[Dict[str, UploadFile]] = None
    ) -> Dict[str, Any]:
        """Main import processing method"""
        
        # Clean up old uploads first
        await self.cleanup_old_uploads()
        
        import_start = datetime.now()
        results = {
            "deals": 0,
            "stages": 0,
            "meetings": 0,
            "notes": 0,
            "unknown_headers": []
        }
        
        try:
            # Determine file paths
            file_paths = {}
            
            if uploaded_files:
                # Save uploaded files
                for entity_type, upload_file in uploaded_files.items():
                    if upload_file.size > MAX_UPLOAD_SIZE:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File {upload_file.filename} exceeds maximum size of {MAX_UPLOAD_SIZE/1024/1024:.1f}MB"
                        )
                    
                    # Save to upload directory
                    file_extension = Path(upload_file.filename).suffix
                    temp_path = UPLOAD_DIR / f"{entity_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_extension}"
                    
                    async with aiofiles.open(temp_path, 'wb') as f:
                        content = await upload_file.read()
                        await f.write(content)
                    
                    file_paths[entity_type] = temp_path
            
            elif paths:
                # Use provided paths
                for entity_type, path in paths.items():
                    file_paths[entity_type] = Path(path)
            
            else:
                # Use default locations
                # Check container location first, then local
                for entity_type in ['deals', 'stages', 'meetings', 'notes']:
                    container_path = UPLOAD_DIR / f"{entity_type}.csv"
                    local_path = LOCAL_IMPORT_DIR / f"{entity_type}.csv"
                    
                    if container_path.exists():
                        file_paths[entity_type] = container_path
                    elif local_path.exists():
                        file_paths[entity_type] = local_path
            
            # Process each file
            for entity_type, file_path in file_paths.items():
                if not file_path.exists():
                    logger.info(f"Skipping {entity_type}: file not found")
                    continue
                
                logger.info(f"Processing {entity_type} from {file_path}")
                
                # Read file with column normalization
                df, unknown_headers = self.read_file(file_path, entity_type)
                results["unknown_headers"].extend(unknown_headers)
                
                # Import based on entity type
                if entity_type == 'deals':
                    results['deals'] = await self.import_deals(df)
                elif entity_type == 'stages':
                    results['stages'] = await self.import_stages(df)
                elif entity_type == 'meetings':
                    results['meetings'] = await self.import_meetings(df)
                elif entity_type == 'notes':
                    results['notes'] = await self.import_notes(df)
            
            # Log to Application Insights if available
            if self.monitoring:
                import_duration = (datetime.now() - import_start).total_seconds()
                try:
                    # Track custom metric
                    self.monitoring.track_custom_metric(
                        "csv_import_completed",
                        {
                            "deals_count": results['deals'],
                            "stages_count": results['stages'],
                            "meetings_count": results['meetings'],
                            "notes_count": results['notes'],
                            "duration_seconds": import_duration
                        }
                    )
                except Exception as e:
                    logger.warning(f"Could not track metrics: {e}")
            
            # Remove duplicate unknown headers
            results["unknown_headers"] = list(set(results["unknown_headers"]))
            
            return results
            
        except Exception as e:
            logger.error(f"Import error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# Create router
router = APIRouter(prefix="/api/admin/import/v2", tags=["admin", "import"])

# Initialize service
import_service = ImportService()


@router.post("/", response_model=Dict[str, Any])
async def import_data(
    request: Optional[ImportRequest] = Body(None),
    deals_file: Optional[UploadFile] = File(None),
    stages_file: Optional[UploadFile] = File(None),
    meetings_file: Optional[UploadFile] = File(None),
    notes_file: Optional[UploadFile] = File(None)
):
    """
    Bulletproof CSV/XLSX import endpoint with three input methods:
    
    1. No body → use default folders (app/admin/imports/ for local, /mnt/data/ for container)
    2. JSON body with paths: {"paths": {"deals": "/path/to/deals.csv", ...}}
    3. Multipart file uploads → store in /mnt/data/uploads/
    
    Features:
    - Handles CSV and XLSX files
    - Auto-detects encoding (utf-8, latin-1, cp1252)
    - Resilient column mapping with common aliases
    - Idempotent upserts to prevent duplicates
    - Size limits: 50MB per file, 100k rows max
    - Auto-cleanup of uploads older than 24 hours
    - Comprehensive logging to Application Insights
    
    Returns:
    - Count of imported records for each entity type
    - List of unknown column headers encountered
    """
    
    # Collect uploaded files if any
    uploaded_files = {}
    if deals_file:
        uploaded_files['deals'] = deals_file
    if stages_file:
        uploaded_files['stages'] = stages_file
    if meetings_file:
        uploaded_files['meetings'] = meetings_file
    if notes_file:
        uploaded_files['notes'] = notes_file
    
    # Process import
    paths = request.paths if request else None
    results = await import_service.process_import(paths=paths, uploaded_files=uploaded_files)
    
    return results


@router.get("/status")
async def get_import_status():
    """
    Get import system status and configuration
    """
    await import_service.db_client.init_pool()
    
    async with import_service.db_client.pool.acquire() as conn:
        # Get record counts
        deals_count = await conn.fetchval("SELECT COUNT(*) FROM deals")
        stages_count = await conn.fetchval("SELECT COUNT(*) FROM deal_stage_history")
        meetings_count = await conn.fetchval("SELECT COUNT(*) FROM meetings")
        notes_count = await conn.fetchval("SELECT COUNT(*) FROM deal_notes")
        
        # Get last import times
        last_deal = await conn.fetchrow("SELECT MAX(imported_at) as last_import FROM deals")
        last_stage = await conn.fetchrow("SELECT MAX(imported_at) as last_import FROM deal_stage_history")
        last_meeting = await conn.fetchrow("SELECT MAX(imported_at) as last_import FROM meetings")
        last_note = await conn.fetchrow("SELECT MAX(imported_at) as last_import FROM deal_notes")
    
    return {
        "configuration": {
            "max_upload_size_mb": MAX_UPLOAD_SIZE / (1024 * 1024),
            "max_rows": MAX_ROWS,
            "cleanup_hours": CLEANUP_HOURS,
            "upload_directory": str(UPLOAD_DIR),
            "local_import_directory": str(LOCAL_IMPORT_DIR)
        },
        "database_counts": {
            "deals": deals_count,
            "stages": stages_count,
            "meetings": meetings_count,
            "notes": notes_count
        },
        "last_imports": {
            "deals": last_deal['last_import'].isoformat() if last_deal['last_import'] else None,
            "stages": last_stage['last_import'].isoformat() if last_stage['last_import'] else None,
            "meetings": last_meeting['last_import'].isoformat() if last_meeting['last_import'] else None,
            "notes": last_note['last_import'].isoformat() if last_note['last_import'] else None
        },
        "column_mappings": COLUMN_MAPPINGS
    }


@router.post("/cleanup")
async def trigger_cleanup():
    """
    Manually trigger cleanup of old upload files
    """
    await import_service.cleanup_old_uploads()
    return {"status": "cleanup completed"}


# Add router to main app in your main.py:
# from app.admin.import_exports_v2 import router as import_v2_router
# app.include_router(import_v2_router)