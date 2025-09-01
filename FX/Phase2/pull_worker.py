#!/usr/bin/env python
"""
Pull-based Zoom recording ingestion worker
Periodically fetches recent recordings and processes unprocessed meetings
"""

import os
import sys
import json
import logging
import argparse
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Set, Optional
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

# Import shared utilities from app.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import (
    get_zoom_access_token,
    fetch_recording_files,
    get_transcript_text,
    summarize_and_extract_todos,
    create_minutes_doc,
    post_to_discord
)

load_dotenv()

# Pull-specific configuration
ZOOM_USER_ID = os.getenv("ZOOM_USER_ID", "me")
PULL_LOOKBACK_MINUTES = int(os.getenv("PULL_LOOKBACK_MINUTES", "360"))
PULL_INTERVAL_SECONDS = int(os.getenv("PULL_INTERVAL_SECONDS", "300"))
STATE_DIR = os.getenv("STATE_DIR", "./state")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tokyo")

# Ensure state directory exists
Path(STATE_DIR).mkdir(parents=True, exist_ok=True)
STATE_FILE = Path(STATE_DIR) / "processed.json"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProcessedState:
    """Manage processed meeting UUIDs"""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.data = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state file: {e}")
                return {"meetings": [], "emails": []}
        return {"meetings": [], "emails": []}
    
    def _save(self) -> None:
        """Save state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")
    
    def is_processed(self, meeting_uuid: str) -> bool:
        """Check if meeting has been processed"""
        return meeting_uuid in self.data.get("meetings", [])
    
    def mark_processed(self, meeting_uuid: str) -> None:
        """Mark meeting as processed"""
        if "meetings" not in self.data:
            self.data["meetings"] = []
        if meeting_uuid not in self.data["meetings"]:
            self.data["meetings"].append(meeting_uuid)
            # Keep only last 10000 UUIDs to prevent unbounded growth
            if len(self.data["meetings"]) > 10000:
                self.data["meetings"] = self.data["meetings"][-10000:]
            self._save()


async def get_user_recordings(
    token: str,
    user_id: str,
    from_date: str,
    to_date: str,
    page_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get recordings for a user within date range
    
    Args:
        token: Zoom access token
        user_id: User ID or email
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        page_token: Pagination token
    
    Returns:
        API response with recordings list
    """
    url = f"https://api.zoom.us/v2/users/{user_id}/recordings"
    
    params = {
        "from": from_date,
        "to": to_date,
        "page_size": 30,
        "trash_type": "meeting_recordings"
    }
    
    if page_token:
        params["next_page_token"] = page_token
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, params=params)
        
        # Handle 404 (user not found or no recordings)
        if response.status_code == 404:
            logger.warning(f"User {user_id} not found or has no recordings")
            return {"meetings": []}
        
        response.raise_for_status()
        return response.json()


async def fetch_recent_recordings(lookback_minutes: int) -> List[Dict[str, Any]]:
    """
    Fetch recordings from the past N minutes
    
    Args:
        lookback_minutes: How many minutes to look back
    
    Returns:
        List of recording objects
    """
    try:
        token = await get_zoom_access_token()
        
        # Calculate date range
        tz = ZoneInfo(TIMEZONE)
        now = datetime.now(tz)
        from_time = now - timedelta(minutes=lookback_minutes)
        
        # Handle multi-day spans
        from_date = from_time.strftime("%Y-%m-%d")
        to_date = now.strftime("%Y-%m-%d")
        
        logger.info(f"Fetching recordings from {from_date} to {to_date} for user {ZOOM_USER_ID}")
        
        all_meetings = []
        page_token = None
        
        while True:
            data = await get_user_recordings(
                token=token,
                user_id=ZOOM_USER_ID,
                from_date=from_date,
                to_date=to_date,
                page_token=page_token
            )
            
            meetings = data.get("meetings", [])
            all_meetings.extend(meetings)
            
            # Check for pagination
            page_token = data.get("next_page_token")
            if not page_token:
                break
            
            logger.info(f"Fetching next page...")
        
        # Filter by actual time (API returns full day)
        filtered_meetings = []
        for meeting in all_meetings:
            start_time_str = meeting.get("start_time")
            if start_time_str:
                try:
                    # Parse ISO format
                    start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    if start_time >= from_time.replace(tzinfo=start_time.tzinfo):
                        filtered_meetings.append(meeting)
                except Exception as e:
                    logger.warning(f"Failed to parse start_time: {start_time_str}, error: {e}")
                    filtered_meetings.append(meeting)  # Include if can't parse
            else:
                filtered_meetings.append(meeting)  # Include if no start_time
        
        logger.info(f"Found {len(filtered_meetings)} recordings in lookback period")
        return filtered_meetings
        
    except Exception as e:
        logger.error(f"Failed to fetch recordings: {e}")
        logger.error(traceback.format_exc())
        return []


async def process_meeting(meeting: Dict[str, Any], state: ProcessedState) -> bool:
    """
    Process a single meeting recording
    
    Args:
        meeting: Meeting data from Zoom API
        state: Processed state manager
    
    Returns:
        True if successful, False otherwise
    """
    meeting_uuid = meeting.get("uuid", "")
    meeting_topic = meeting.get("topic", "Zoom Meeting")
    
    if not meeting_uuid:
        logger.warning("Meeting has no UUID, skipping")
        return False
    
    # Check if already processed
    if state.is_processed(meeting_uuid):
        logger.info(f"Meeting {meeting_topic} already processed, skipping")
        return True
    
    try:
        logger.info(f"Processing meeting: {meeting_topic} (UUID: {meeting_uuid})")
        
        # Get OAuth token
        token = await get_zoom_access_token()
        
        # Fetch recording files
        recording_data = await fetch_recording_files(meeting_uuid, token)
        
        # Check if recording files exist
        if not recording_data.get("recording_files"):
            logger.warning(f"No recording files for meeting {meeting_topic}")
            # Mark as processed to avoid retrying
            state.mark_processed(meeting_uuid)
            return False
        
        # Get transcript
        transcript_text = await get_transcript_text(recording_data, token)
        
        if transcript_text == "Transcript not available for this recording.":
            logger.warning(f"No transcript available for {meeting_topic}")
            # Still create minutes with basic info
        
        # Extract summary and todos
        minutes = await summarize_and_extract_todos(transcript_text)
        
        # Create document title with date
        tz = ZoneInfo(TIMEZONE)
        start_time_str = meeting.get("start_time", "")
        if start_time_str:
            try:
                meeting_date = datetime.fromisoformat(start_time_str.replace("Z", "+00:00")).astimezone(tz).strftime("%Y-%m-%d")
            except:
                meeting_date = datetime.now(tz).strftime("%Y-%m-%d")
        else:
            meeting_date = datetime.now(tz).strftime("%Y-%m-%d")
        
        doc_title = f"{meeting_topic} {meeting_date} 議事録"
        
        # Create Google Doc
        doc_url = await create_minutes_doc(doc_title, minutes)
        
        # Post to Discord
        discord_message = f"📄 {doc_title}\n{doc_url}\n*(Pull型で処理)*"
        await post_to_discord(discord_message)
        
        # Mark as processed
        state.mark_processed(meeting_uuid)
        
        logger.info(f"Successfully processed meeting: {meeting_topic}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to process meeting {meeting_topic}: {e}")
        logger.error(traceback.format_exc())
        return False


async def run_once() -> None:
    """Run pull process once"""
    logger.info("Starting pull process...")
    
    state = ProcessedState(STATE_FILE)
    recordings = await fetch_recent_recordings(PULL_LOOKBACK_MINUTES)
    
    if not recordings:
        logger.info("No recordings found in lookback period")
        return
    
    success_count = 0
    fail_count = 0
    
    for meeting in recordings:
        if await process_meeting(meeting, state):
            success_count += 1
        else:
            fail_count += 1
        
        # Small delay between processing to avoid rate limits
        await asyncio.sleep(1)
    
    logger.info(f"Pull process completed. Success: {success_count}, Failed: {fail_count}")


async def run_daemon() -> None:
    """Run pull process as daemon"""
    logger.info(f"Starting daemon mode, interval: {PULL_INTERVAL_SECONDS} seconds")
    
    while True:
        try:
            await run_once()
        except Exception as e:
            logger.error(f"Error in daemon loop: {e}")
            logger.error(traceback.format_exc())
        
        logger.info(f"Sleeping for {PULL_INTERVAL_SECONDS} seconds...")
        await asyncio.sleep(PULL_INTERVAL_SECONDS)


def main():
    parser = argparse.ArgumentParser(description='Zoom Recording Pull Worker')
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (for cron jobs)'
    )
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Run as daemon with periodic polling'
    )
    
    args = parser.parse_args()
    
    # Default to --once if no args
    if not args.once and not args.daemon:
        args.once = True
    
    if args.once:
        asyncio.run(run_once())
    elif args.daemon:
        try:
            asyncio.run(run_daemon())
        except KeyboardInterrupt:
            logger.info("Daemon stopped by user")


if __name__ == "__main__":
    main()