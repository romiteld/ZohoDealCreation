"""
Zoom API integration for transcript fetching.
Uses Server-to-Server OAuth for authentication.
"""
import os
import base64
import json
import logging
import re
import asyncio
import random
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import httpx
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

class ZoomClient:
    """Zoom API client for fetching meeting recordings and transcripts."""
    
    def __init__(self):
        self.account_id = os.getenv("ZOOM_ACCOUNT_ID")
        self.client_id = os.getenv("ZOOM_CLIENT_ID")
        self.client_secret = os.getenv("ZOOM_CLIENT_SECRET")
        self.secret_token = os.getenv("ZOOM_SECRET_TOKEN")
        self.verification_token = os.getenv("ZOOM_VERIFICATION_TOKEN")
        
        # Validate required credentials
        if not all([self.account_id, self.client_id, self.client_secret]):
            raise ValueError("Missing required Zoom API credentials. Please set ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, and ZOOM_CLIENT_SECRET environment variables.")
        
        self.base_url = "https://api.zoom.us/v2"
        self.oauth_url = "https://zoom.us/oauth/token"
        self._access_token = None
        self._token_expiry = None

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        timeout: int = 10,
        **kwargs
    ) -> httpx.Response:
        """
        Exponential backoff with jitter for Zoom API requests.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            max_retries: Maximum retry attempts (default: 3)
            timeout: Request timeout in seconds (default: 10)
            **kwargs: Additional httpx request parameters

        Returns:
            httpx.Response object

        Raises:
            Exception: After max retries exceeded
        """
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(method, url, **kwargs)
                    if response.status_code < 500:
                        return response
                    logger.warning(f"Zoom 5xx (attempt {attempt+1}/{max_retries}): {response.status_code}")
            except httpx.TimeoutException as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Zoom timeout (attempt {attempt+1}/{max_retries}): {e}")
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.error(f"Zoom error (attempt {attempt+1}/{max_retries}): {e}")

            # Exponential backoff with jitter
            delay = (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)

        raise Exception(f"Zoom API failed after {max_retries} retries: {url}")

    async def get_access_token(self) -> str:
        """
        Get access token using Server-to-Server OAuth.
        Uses account_credentials grant type.
        """
        try:
            # Check if we have a valid cached token
            if self._access_token and self._token_expiry:
                if datetime.now() < self._token_expiry:
                    return self._access_token
            
            # Create Basic auth header
            credentials = f"{self.client_id}:{self.client_secret}"
            auth_header = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Request body for Server-to-Server OAuth
            data = {
                "grant_type": "account_credentials",
                "account_id": self.account_id
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.oauth_url,
                    headers=headers,
                    data=data
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    self._access_token = token_data["access_token"]
                    # Token expires in 1 hour, refresh 5 minutes early
                    expires_in = token_data.get("expires_in", 3600)
                    self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)
                    logger.info("Successfully obtained Zoom access token")
                    return self._access_token
                else:
                    logger.error(f"Failed to get Zoom access token: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting Zoom access token: {e}")
            return None
    
    async def fetch_meeting_recording(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch recording details for a specific meeting.
        Returns recording metadata including download URLs.
        """
        try:
            token = await self.get_access_token()
            if not token:
                return None

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            url = f"{self.base_url}/meetings/{meeting_id}/recordings"

            # CRITICAL FIX: Use retry helper instead of direct AsyncClient
            response = await self._request_with_retry("GET", url, headers=headers)

            if response.status_code == 200:
                recording_data = response.json()
                logger.info(f"Successfully fetched recording for meeting {meeting_id}")
                return recording_data
            elif response.status_code == 404:
                logger.info(f"No recording found for meeting {meeting_id}")
                return None
            else:
                logger.error(f"Failed to fetch recording: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error fetching recording for meeting {meeting_id}: {e}")
            return None
    
    async def download_transcript(self, download_url: str, access_token: Optional[str] = None) -> Optional[str]:
        """
        Download transcript file from Zoom.
        Returns the transcript content as string.
        """
        try:
            if not access_token:
                access_token = await self.get_access_token()
                if not access_token:
                    return None

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # CRITICAL FIX: Use retry helper instead of direct AsyncClient
            # Note: httpx follow_redirects handled internally by request method
            response = await self._request_with_retry("GET", download_url, headers=headers, follow_redirects=True)

            if response.status_code == 200:
                # Zoom transcripts are typically in VTT format
                transcript_content = response.text
                logger.info(f"Successfully downloaded transcript")
                return transcript_content
            else:
                logger.error(f"Failed to download transcript: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error downloading transcript: {e}")
            return None
    
    def parse_vtt_to_text(self, vtt_content: str) -> str:
        """
        Parse VTT transcript format to plain text.
        Removes timestamps and formatting, preserves speaker names.
        """
        lines = vtt_content.split('\n')
        text_lines = []
        
        # Skip WebVTT header
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip WebVTT header, timestamps, and empty lines
            if (line.startswith('WEBVTT') or 
                '-->' in line or 
                line == '' or 
                re.match(r'^\d{2}:\d{2}:\d{2}', line)):
                i += 1
                continue
            
            # This is actual transcript text
            text_lines.append(line)
            i += 1
        
        # Join and clean up
        transcript = ' '.join(text_lines)
        # Remove multiple spaces
        transcript = re.sub(r'\s+', ' ', transcript)
        
        return transcript.strip()
    
    async def fetch_zoom_transcript_for_meeting(self, meeting_id_or_url: str) -> Optional[str]:
        """
        Main method to fetch and parse transcript for a meeting.
        Accepts either a meeting ID or a Zoom URL.
        Returns parsed transcript text or None if unavailable.
        """
        # Extract meeting ID if URL provided
        meeting_id = self._extract_meeting_id(meeting_id_or_url)
        if not meeting_id:
            logger.error(f"Could not extract meeting ID from: {meeting_id_or_url}")
            return None
        
        # Fetch recording metadata
        recording_data = await self.fetch_meeting_recording(meeting_id)
        if not recording_data:
            logger.info(f"No recording data for meeting: {meeting_id}")
            return None
        
        # Look for transcript file in recording files
        recording_files = recording_data.get("recording_files", [])
        transcript_file = None
        
        for file in recording_files:
            if file.get("file_type") == "TRANSCRIPT" or file.get("file_extension") == "VTT":
                transcript_file = file
                break
        
        if not transcript_file:
            # Try to find any audio transcript
            for file in recording_files:
                if "transcript" in file.get("recording_type", "").lower():
                    transcript_file = file
                    break
        
        if not transcript_file:
            logger.info(f"No transcript file found for meeting: {meeting_id}")
            return None
        
        # Download and parse transcript
        download_url = transcript_file.get("download_url")
        if not download_url:
            logger.error(f"No download URL for transcript")
            return None
        
        transcript_content = await self.download_transcript(download_url)
        if not transcript_content:
            return None
        
        # Parse VTT to text
        parsed_transcript = self.parse_vtt_to_text(transcript_content)
        
        logger.info(f"Successfully fetched and parsed transcript for meeting {meeting_id}")
        return parsed_transcript
    
    def _extract_meeting_id(self, meeting_input: str) -> Optional[str]:
        """
        Extract meeting ID from various Zoom URL formats or return as-is if already an ID.
        
        Handles:
        - Direct meeting ID: "85725475967"
        - Recording share URL: "https://us02web.zoom.us/rec/share/..."
        - Recording play URL: "https://zoom.us/rec/play/85725475967"
        """
        # If it's already just numbers, assume it's a meeting ID
        if meeting_input.isdigit():
            return meeting_input
        
        # Try to parse as URL
        try:
            parsed = urlparse(meeting_input)
            
            # Check for /rec/play/ format
            if '/rec/play/' in parsed.path:
                # Extract ID after /rec/play/
                parts = parsed.path.split('/rec/play/')
                if len(parts) > 1:
                    meeting_id = parts[1].split('/')[0].split('?')[0]
                    if meeting_id:
                        return meeting_id
            
            # Check for /rec/share/ format (share ID, not meeting ID directly)
            if '/rec/share/' in parsed.path:
                # For share URLs, we'd need to use a different API endpoint
                # For now, extract the share ID
                parts = parsed.path.split('/rec/share/')
                if len(parts) > 1:
                    share_id = parts[1].split('/')[0].split('?')[0]
                    # Note: This would need additional API call to convert share ID to meeting ID
                    logger.warning(f"Share URL detected. Share ID: {share_id}. May need additional processing.")
                    return share_id
            
            # Check query parameters for meeting_id
            query_params = parse_qs(parsed.query)
            if 'meeting_id' in query_params:
                return query_params['meeting_id'][0]
            
        except Exception as e:
            logger.error(f"Error parsing meeting URL: {e}")
        
        # If no pattern matched, return the input as-is (might be a direct ID)
        return meeting_input
    
    async def list_recordings(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: int = 30
    ) -> List[Dict[str, Any]]:
        """
        List all cloud recordings for the account within a date range.

        Args:
            from_date: Start date in YYYY-MM-DD format (defaults to 30 days ago)
            to_date: End date in YYYY-MM-DD format (defaults to today)
            page_size: Number of records per page (max 300)

        Returns:
            List of recording metadata
        """
        try:
            # CRITICAL FIX: Default to last 30 days if None
            if not from_date:
                from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            if not to_date:
                to_date = datetime.now().strftime("%Y-%m-%d")

            token = await self.get_access_token()
            if not token:
                return []

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            params = {
                "from": from_date,
                "to": to_date,
                "page_size": min(page_size, 300)
            }

            url = f"{self.base_url}/accounts/{self.account_id}/recordings"

            # Use retry helper
            response = await self._request_with_retry("GET", url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                meetings = data.get("meetings", [])
                logger.info(f"Found {len(meetings)} recordings from {from_date} to {to_date}")
                return meetings
            else:
                logger.error(f"Failed to list recordings: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error listing recordings: {e}")
            return []

    async def search_recordings_by_participant(
        self,
        participant_name: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Search for recordings by participant name.

        Args:
            participant_name: Name to search for (case-insensitive)
            from_date: Start date (YYYY-MM-DD), defaults to 30 days ago
            to_date: End date (YYYY-MM-DD), defaults to today
            page_size: Number of results per page (max 300)

        Returns:
            List of recording metadata dictionaries matching participant
        """
        try:
            # Get all recordings in date range
            all_recordings = await self.list_recordings(from_date, to_date, page_size)

            # Filter by participant name (case-insensitive)
            search_lower = participant_name.lower()
            matching_recordings = []

            for meeting in all_recordings:
                # Check topic/host name
                topic = meeting.get("topic", "").lower()
                host_name = meeting.get("host_email", "").lower()

                # Also check participant list if available
                participants = meeting.get("participant_list", [])
                participant_names = [p.get("name", "").lower() for p in participants]

                if (search_lower in topic or
                    search_lower in host_name or
                    any(search_lower in name for name in participant_names)):
                    matching_recordings.append(meeting)

            logger.info(f"Found {len(matching_recordings)} recordings matching participant: {participant_name}")
            return matching_recordings

        except Exception as e:
            logger.error(f"Error searching recordings by participant: {e}")
            return []

    async def search_recordings_by_topic(
        self,
        topic_keywords: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Search for recordings by topic keywords.

        Args:
            topic_keywords: Keywords to search for in meeting topic
            from_date: Start date (YYYY-MM-DD), defaults to 30 days ago
            to_date: End date (YYYY-MM-DD), defaults to today
            page_size: Number of results per page (max 300)

        Returns:
            List of recording metadata dictionaries matching keywords
        """
        try:
            # Get all recordings in date range
            all_recordings = await self.list_recordings(from_date, to_date, page_size)

            # Filter by keywords (case-insensitive)
            keywords_lower = topic_keywords.lower().split()
            matching_recordings = []

            for meeting in all_recordings:
                topic = meeting.get("topic", "").lower()

                # Check if any keyword matches
                if any(keyword in topic for keyword in keywords_lower):
                    matching_recordings.append(meeting)

            logger.info(f"Found {len(matching_recordings)} recordings matching topic: {topic_keywords}")
            return matching_recordings

        except Exception as e:
            logger.error(f"Error searching recordings by topic: {e}")
            return []

    async def get_recording_with_transcript(
        self,
        meeting_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get recording metadata and transcript content for a meeting.

        Args:
            meeting_id: Zoom meeting ID

        Returns:
            Dictionary with recording metadata and transcript text, or None if not found
        """
        try:
            # Fetch recording metadata
            recording = await self.fetch_meeting_recording(meeting_id)
            if not recording:
                return None

            # Fetch transcript
            transcript_text = await self.fetch_zoom_transcript_for_meeting(meeting_id)

            return {
                "meeting_id": meeting_id,
                "topic": recording.get("topic"),
                "start_time": recording.get("start_time"),
                "duration": recording.get("duration"),
                "host_email": recording.get("host_email"),
                "recording_count": recording.get("recording_count", 0),
                "transcript_text": transcript_text,
                "recording_files": recording.get("recording_files", [])
            }

        except Exception as e:
            logger.error(f"Error getting recording with transcript: {e}")
            return None