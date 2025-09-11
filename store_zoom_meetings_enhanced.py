#!/usr/bin/env python3
"""
Enhanced Zoom meeting storage with participant names and comprehensive metadata.
Stores everything useful for searching and analysis.
"""

import asyncio
import base64
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import aiohttp
import asyncpg
import json
import re

load_dotenv('.env.local')

async def create_enhanced_zoom_table(conn):
    """Create enhanced table with participant info and searchable metadata."""
    
    # Drop old table if migrating
    await conn.execute("""
        DROP TABLE IF EXISTS zoom_meetings_enhanced CASCADE
    """)
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS zoom_meetings_enhanced (
            id SERIAL PRIMARY KEY,
            meeting_id BIGINT UNIQUE NOT NULL,
            
            -- Basic meeting info
            topic TEXT,
            agenda TEXT,
            host_id TEXT,
            host_email TEXT,
            host_name TEXT,
            
            -- Timing
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration INTEGER,
            timezone TEXT,
            
            -- Participants
            participant_count INTEGER DEFAULT 0,
            participant_names TEXT[], -- Array of participant names
            participant_emails TEXT[], -- Array of participant emails
            participant_details JSONB, -- Full participant data
            
            -- Recording info
            has_transcript BOOLEAN DEFAULT FALSE,
            has_video BOOLEAN DEFAULT FALSE,
            has_audio BOOLEAN DEFAULT FALSE,
            has_chat BOOLEAN DEFAULT FALSE,
            recording_count INTEGER DEFAULT 0,
            total_size BIGINT DEFAULT 0, -- Total size in bytes
            
            -- Content indicators
            is_interview BOOLEAN DEFAULT FALSE,
            is_internal_meeting BOOLEAN DEFAULT FALSE,
            is_client_meeting BOOLEAN DEFAULT FALSE,
            is_candidate_meeting BOOLEAN DEFAULT FALSE,
            
            -- Searchable text fields
            transcript_preview TEXT, -- First 1000 chars of transcript
            chat_messages TEXT, -- Concatenated chat messages
            keywords TEXT[], -- Extracted keywords for search
            
            -- URLs
            share_url TEXT,
            recording_play_url TEXT,
            download_urls JSONB,
            
            -- Full metadata
            recording_files JSONB,
            metadata JSONB,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP,
            
            -- Processing status
            processed BOOLEAN DEFAULT FALSE,
            processing_notes TEXT
        )
    """)
    
    # Create comprehensive indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_enhanced_meeting_id 
        ON zoom_meetings_enhanced(meeting_id)
    """)
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_enhanced_has_transcript 
        ON zoom_meetings_enhanced(has_transcript)
    """)
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_enhanced_participant_names 
        ON zoom_meetings_enhanced USING GIN(participant_names)
    """)
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_enhanced_participant_emails 
        ON zoom_meetings_enhanced USING GIN(participant_emails)
    """)
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_enhanced_keywords
        ON zoom_meetings_enhanced USING GIN(keywords)
    """)
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_enhanced_start_time 
        ON zoom_meetings_enhanced(start_time DESC)
    """)
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_enhanced_host_email 
        ON zoom_meetings_enhanced(host_email)
    """)
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_enhanced_meeting_types
        ON zoom_meetings_enhanced(is_interview, is_candidate_meeting, is_client_meeting)
    """)
    
    # Create full-text search
    await conn.execute("""
        ALTER TABLE zoom_meetings_enhanced 
        ADD COLUMN IF NOT EXISTS search_vector tsvector
    """)
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoom_enhanced_search 
        ON zoom_meetings_enhanced USING GIN(search_vector)
    """)
    
    print("✓ Enhanced database table 'zoom_meetings_enhanced' ready with comprehensive indexes")

def classify_meeting_type(topic, participant_names, participant_emails):
    """Classify meeting type based on topic and participants."""
    
    topic_lower = (topic or "").lower()
    all_names = " ".join(participant_names or []).lower()
    all_emails = " ".join(participant_emails or []).lower()
    
    # Interview indicators
    interview_keywords = ["interview", "candidate", "screening", "assessment", "hiring"]
    is_interview = any(keyword in topic_lower for keyword in interview_keywords)
    
    # Candidate meeting indicators
    candidate_keywords = ["candidate", "applicant", "recruit", "talent"]
    is_candidate = any(keyword in topic_lower or keyword in all_names for keyword in candidate_keywords)
    
    # Client meeting indicators
    client_keywords = ["client", "customer", "prospect", "demo", "sales"]
    is_client = any(keyword in topic_lower for keyword in client_keywords)
    
    # Internal meeting check (all participants from same domain)
    if participant_emails:
        domains = [email.split('@')[-1] for email in participant_emails if '@' in email]
        is_internal = len(set(domains)) <= 1 if domains else False
    else:
        is_internal = False
    
    return {
        'is_interview': is_interview,
        'is_candidate_meeting': is_candidate or is_interview,
        'is_client_meeting': is_client,
        'is_internal_meeting': is_internal
    }

def extract_keywords(topic, transcript_preview, participant_names):
    """Extract searchable keywords from meeting content."""
    
    keywords = []
    
    # Extract from topic
    if topic:
        # Remove common words and split
        words = re.findall(r'\b[A-Za-z]{3,}\b', topic)
        keywords.extend([w.lower() for w in words if len(w) > 3])
    
    # Extract names (first and last names separately)
    for name in participant_names or []:
        parts = name.split()
        keywords.extend([p.lower() for p in parts if len(p) > 2])
    
    # Extract from transcript preview
    if transcript_preview:
        # Find capitalized words (likely names or important terms)
        important_words = re.findall(r'\b[A-Z][a-z]{2,}\b', transcript_preview[:500])
        keywords.extend([w.lower() for w in important_words[:20]])  # Limit to 20
    
    # Remove duplicates and return
    return list(set(keywords))

async def fetch_participant_details(session, headers, meeting_id):
    """Fetch detailed participant information for a meeting."""
    
    try:
        participants_url = f"https://api.zoom.us/v2/report/meetings/{meeting_id}/participants"
        
        async with session.get(participants_url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                participants = data.get("participants", [])
                
                names = []
                emails = []
                details = []
                
                for p in participants:
                    name = p.get("name", "Unknown")
                    email = p.get("user_email", "")
                    
                    if name and name != "Unknown":
                        names.append(name)
                    if email:
                        emails.append(email)
                    
                    details.append({
                        "name": name,
                        "email": email,
                        "join_time": p.get("join_time"),
                        "leave_time": p.get("leave_time"),
                        "duration": p.get("duration", 0),
                        "user_id": p.get("user_id")
                    })
                
                return {
                    "names": names,
                    "emails": emails,
                    "details": details,
                    "count": len(participants)
                }
    except Exception as e:
        print(f"  Could not fetch participants for {meeting_id}: {e}")
    
    return {"names": [], "emails": [], "details": [], "count": 0}

async def fetch_and_store_enhanced():
    """Fetch all Zoom recordings with enhanced metadata."""
    
    # Get credentials
    account_id = os.getenv("ZOOM_ACCOUNT_ID")
    client_id = os.getenv("ZOOM_CLIENT_ID")
    client_secret = os.getenv("ZOOM_CLIENT_SECRET")
    database_url = os.getenv("DATABASE_URL")
    
    # Connect to PostgreSQL
    conn = await asyncpg.connect(database_url)
    
    try:
        # Create enhanced table
        await create_enhanced_zoom_table(conn)
        
        # Get Zoom access token
        auth_url = "https://zoom.us/oauth/token"
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "account_credentials",
            "account_id": account_id
        }
        
        async with aiohttp.ClientSession() as session:
            # Get token
            async with session.post(auth_url, headers=headers, data=data) as response:
                if response.status != 200:
                    print("Failed to authenticate with Zoom")
                    return
                    
                token_data = await response.json()
                access_token = token_data.get("access_token")
                print("✓ Zoom authentication successful")
            
            # Prepare date range (last 90 days)
            to_date = datetime.now()
            from_date = to_date - timedelta(days=90)
            
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Fetch recordings
            print("\nFetching enhanced meeting data...")
            recordings_url = "https://api.zoom.us/v2/accounts/me/recordings"
            
            page_count = 0
            total_meetings = 0
            next_page_token = ""
            
            while True:
                params = {
                    "from": from_date.strftime("%Y-%m-%d"),
                    "to": to_date.strftime("%Y-%m-%d"),
                    "page_size": 300,
                }
                
                if next_page_token:
                    params["next_page_token"] = next_page_token
                
                async with session.get(recordings_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        meetings = data.get("meetings", [])
                        
                        page_count += 1
                        print(f"  Page {page_count}: Found {len(meetings)} meetings")
                        
                        for meeting in meetings:
                            meeting_id = int(meeting.get("id", 0))
                            if not meeting_id:
                                continue
                            
                            # Basic info
                            topic = meeting.get("topic", "")
                            agenda = meeting.get("agenda", "")
                            host_id = meeting.get("host_id", "")
                            host_email = meeting.get("user_email", "")
                            host_name = meeting.get("user_name", "") or host_email.split('@')[0]
                            
                            # Timing
                            start_time = meeting.get("start_time")
                            duration = meeting.get("duration", 0)
                            timezone = meeting.get("timezone", "")
                            
                            if start_time:
                                try:
                                    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
                                    end_dt = start_dt + timedelta(minutes=duration) if duration else start_dt
                                except:
                                    start_dt = None
                                    end_dt = None
                            else:
                                start_dt = None
                                end_dt = None
                            
                            # Recording files analysis
                            recording_files = meeting.get("recording_files", [])
                            has_transcript = False
                            has_video = False
                            has_audio = False
                            has_chat = False
                            total_size = meeting.get("total_size", 0)
                            download_urls = {}
                            
                            for f in recording_files:
                                file_type = f.get("file_type", "")
                                if file_type == "TRANSCRIPT" or f.get("file_extension") == "VTT":
                                    has_transcript = True
                                    download_urls["transcript"] = f.get("download_url")
                                elif file_type == "MP4":
                                    has_video = True
                                    download_urls["video"] = f.get("download_url")
                                elif file_type == "M4A":
                                    has_audio = True
                                    download_urls["audio"] = f.get("download_url")
                                elif file_type == "CHAT":
                                    has_chat = True
                                    download_urls["chat"] = f.get("download_url")
                            
                            # Fetch participant details
                            participant_data = await fetch_participant_details(session, headers, meeting_id)
                            
                            # Classify meeting type
                            meeting_types = classify_meeting_type(
                                topic, 
                                participant_data["names"], 
                                participant_data["emails"]
                            )
                            
                            # Extract keywords
                            keywords = extract_keywords(topic, None, participant_data["names"])
                            
                            # Build searchable text
                            search_text = f"{topic} {agenda} {' '.join(participant_data['names'])} {host_name}"
                            
                            # Complete metadata
                            metadata = {
                                "uuid": meeting.get("uuid"),
                                "host_id": host_id,
                                "recording_files_count": len(recording_files),
                                "share_url": meeting.get("share_url"),
                                "recording_play_passcode": meeting.get("recording_play_passcode"),
                                "password": meeting.get("password"),
                                "type": meeting.get("type"),
                                "account_id": meeting.get("account_id")
                            }
                            
                            # Insert into enhanced table
                            await conn.execute("""
                                INSERT INTO zoom_meetings_enhanced (
                                    meeting_id, topic, agenda, host_id, host_email, host_name,
                                    start_time, end_time, duration, timezone,
                                    participant_count, participant_names, participant_emails, participant_details,
                                    has_transcript, has_video, has_audio, has_chat,
                                    recording_count, total_size,
                                    is_interview, is_internal_meeting, is_client_meeting, is_candidate_meeting,
                                    keywords, share_url, recording_play_url, download_urls,
                                    recording_files, metadata, search_vector
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                                         $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27,
                                         $28, $29, $30, to_tsvector('english', $31))
                                ON CONFLICT (meeting_id) 
                                DO UPDATE SET 
                                    participant_names = EXCLUDED.participant_names,
                                    participant_emails = EXCLUDED.participant_emails,
                                    participant_details = EXCLUDED.participant_details,
                                    keywords = EXCLUDED.keywords,
                                    download_urls = EXCLUDED.download_urls,
                                    updated_at = CURRENT_TIMESTAMP
                            """, 
                                meeting_id, topic, agenda, host_id, host_email, host_name,
                                start_dt, end_dt, duration, timezone,
                                participant_data["count"], participant_data["names"], 
                                participant_data["emails"], json.dumps(participant_data["details"]),
                                has_transcript, has_video, has_audio, has_chat,
                                len(recording_files), total_size,
                                meeting_types["is_interview"], meeting_types["is_internal_meeting"],
                                meeting_types["is_client_meeting"], meeting_types["is_candidate_meeting"],
                                keywords, meeting.get("share_url"), meeting.get("recording_play_url"),
                                json.dumps(download_urls), json.dumps(recording_files),
                                json.dumps(metadata), search_text
                            )
                            
                            total_meetings += 1
                            
                            # Show progress for meetings with participants
                            if participant_data["count"] > 0:
                                print(f"    Meeting {meeting_id}: {len(participant_data['names'])} participants")
                        
                        # Check for more pages
                        next_page_token = data.get("next_page_token", "")
                        if not next_page_token:
                            break
                    else:
                        break
        
        # Display comprehensive summary
        print(f"\n✓ Stored {total_meetings} meetings with enhanced metadata")
        
        # Get statistics
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE has_transcript = true) as with_transcript,
                COUNT(*) FILTER (WHERE has_video = true) as with_video,
                COUNT(*) FILTER (WHERE array_length(participant_names, 1) > 0) as with_participants,
                COUNT(*) FILTER (WHERE is_interview = true) as interviews,
                COUNT(*) FILTER (WHERE is_candidate_meeting = true) as candidate_meetings,
                COUNT(*) FILTER (WHERE is_client_meeting = true) as client_meetings,
                COUNT(*) FILTER (WHERE is_internal_meeting = true) as internal_meetings
            FROM zoom_meetings_enhanced
        """)
        
        print(f"\nEnhanced Database Summary:")
        print(f"  Total meetings: {stats['total']}")
        print(f"  With transcripts: {stats['with_transcript']}")
        print(f"  With video: {stats['with_video']}")
        print(f"  With participant names: {stats['with_participants']}")
        print(f"\nMeeting Types:")
        print(f"  Interviews: {stats['interviews']}")
        print(f"  Candidate meetings: {stats['candidate_meetings']}")
        print(f"  Client meetings: {stats['client_meetings']}")
        print(f"  Internal meetings: {stats['internal_meetings']}")
        
        # Show sample meetings with participants
        samples = await conn.fetch("""
            SELECT meeting_id, topic, participant_names, has_transcript
            FROM zoom_meetings_enhanced
            WHERE array_length(participant_names, 1) > 0
                AND has_transcript = true
            ORDER BY start_time DESC
            LIMIT 5
        """)
        
        if samples:
            print(f"\nSample meetings with participants and transcripts:")
            for row in samples:
                print(f"\n  Meeting ID: {row['meeting_id']}")
                print(f"    Topic: {row['topic'][:60]}")
                print(f"    Participants: {', '.join(row['participant_names'][:3])}")
                if len(row['participant_names']) > 3:
                    print(f"                  (+{len(row['participant_names']) - 3} more)")
        
    finally:
        await conn.close()

async def search_meetings(query):
    """Search for meetings using full-text search."""
    
    database_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(database_url)
    
    try:
        results = await conn.fetch("""
            SELECT meeting_id, topic, participant_names, start_time, has_transcript
            FROM zoom_meetings_enhanced
            WHERE search_vector @@ plainto_tsquery('english', $1)
                OR $1 = ANY(participant_names)
                OR $1 = ANY(keywords)
            ORDER BY start_time DESC
            LIMIT 10
        """, query)
        
        print(f"\nSearch results for '{query}':")
        for row in results:
            print(f"\n  Meeting ID: {row['meeting_id']}")
            print(f"    Topic: {row['topic']}")
            print(f"    Date: {row['start_time']}")
            print(f"    Participants: {', '.join(row['participant_names'][:3]) if row['participant_names'] else 'N/A'}")
            print(f"    Has transcript: {'Yes' if row['has_transcript'] else 'No'}")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        if query:
            asyncio.run(search_meetings(query))
        else:
            print("Usage: python store_zoom_meetings_enhanced.py search <query>")
    else:
        print("Fetching and storing enhanced Zoom meeting data...")
        asyncio.run(fetch_and_store_enhanced())
        
        print("\n" + "="*60)
        print("You can now search meetings:")
        print("  python store_zoom_meetings_enhanced.py search Brandon")
        print("  python store_zoom_meetings_enhanced.py search interview")
        print("  python store_zoom_meetings_enhanced.py search candidate")