#!/usr/bin/env python
"""
Gmail-triggered Zoom recording ingestion
Monitors Gmail for Zoom recording completion emails and triggers pull processing
"""

import os
import sys
import json
import logging
import argparse
import asyncio
import traceback
import pickle
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import pull worker functionality
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from pull_worker import ProcessedState, process_meeting, fetch_recent_recordings

load_dotenv()

# Gmail-specific configuration
GMAIL_CREDENTIALS_JSON = os.getenv("GMAIL_CREDENTIALS_JSON", "./gmail_credentials.json")
GMAIL_TOKEN_JSON = os.getenv("GMAIL_TOKEN_JSON", "./gmail_token.json")
GMAIL_QUERY = os.getenv("GMAIL_QUERY", 'from:no-reply@zoom.us subject:"Cloud Recording" newer_than:7d')
GMAIL_POLL_INTERVAL_SECONDS = int(os.getenv("GMAIL_POLL_INTERVAL_SECONDS", "300"))
STATE_DIR = os.getenv("STATE_DIR", "./state")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tokyo")

# Gmail API scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Ensure state directory exists
Path(STATE_DIR).mkdir(parents=True, exist_ok=True)
STATE_FILE = Path(STATE_DIR) / "processed.json"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GmailMonitor:
    """Monitor Gmail for Zoom recording emails"""
    
    def __init__(self):
        self.service = self._build_service()
        self.state = ProcessedState(STATE_FILE)
    
    def _build_service(self):
        """Build Gmail API service with authentication"""
        creds = None
        
        # Load existing token
        token_path = Path(GMAIL_TOKEN_JSON)
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(GMAIL_CREDENTIALS_JSON).exists():
                    raise FileNotFoundError(
                        f"Gmail credentials file not found: {GMAIL_CREDENTIALS_JSON}\n"
                        "Please download OAuth2 credentials from Google Cloud Console"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    GMAIL_CREDENTIALS_JSON, SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        return build('gmail', 'v1', credentials=creds)
    
    def _is_email_processed(self, email_id: str) -> bool:
        """Check if email has been processed"""
        return email_id in self.state.data.get("emails", [])
    
    def _mark_email_processed(self, email_id: str) -> None:
        """Mark email as processed"""
        if "emails" not in self.state.data:
            self.state.data["emails"] = []
        if email_id not in self.state.data["emails"]:
            self.state.data["emails"].append(email_id)
            # Keep only last 1000 email IDs
            if len(self.state.data["emails"]) > 1000:
                self.state.data["emails"] = self.state.data["emails"][-1000:]
            self.state._save()
    
    def search_recording_emails(self) -> List[Dict[str, Any]]:
        """
        Search for Zoom recording completion emails
        
        Returns:
            List of email messages
        """
        try:
            logger.info(f"Searching Gmail with query: {GMAIL_QUERY}")
            
            results = self.service.users().messages().list(
                userId='me',
                q=GMAIL_QUERY,
                maxResults=50
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} matching emails")
            
            return messages
            
        except HttpError as error:
            logger.error(f"Gmail API error: {error}")
            return []
        except Exception as e:
            logger.error(f"Failed to search emails: {e}")
            logger.error(traceback.format_exc())
            return []
    
    def get_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get email details including headers and body
        
        Args:
            message_id: Gmail message ID
        
        Returns:
            Email details or None
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='metadata',
                metadataHeaders=['Date', 'Subject', 'From']
            ).execute()
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to get email details: {e}")
            return None
    
    def extract_meeting_info(self, email: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Extract meeting information from email
        
        Args:
            email: Email message data
        
        Returns:
            Dict with meeting_topic and approximate_time
        """
        try:
            headers = email.get('payload', {}).get('headers', [])
            
            subject = None
            date_str = None
            
            for header in headers:
                name = header.get('name', '')
                value = header.get('value', '')
                
                if name == 'Subject':
                    subject = value
                elif name == 'Date':
                    date_str = value
            
            if not date_str:
                return None
            
            # Parse email date
            # Example: "Mon, 25 Nov 2024 10:30:45 +0000"
            from email.utils import parsedate_to_datetime
            email_date = parsedate_to_datetime(date_str)
            
            # Extract meeting topic from subject if possible
            # Example: "Cloud Recording - Meeting Topic is now available"
            meeting_topic = "Unknown Meeting"
            if subject and "Cloud Recording" in subject:
                # Try to extract topic between "Recording - " and " is now"
                parts = subject.split(" - ", 1)
                if len(parts) > 1:
                    topic_part = parts[1].replace(" is now available", "").strip()
                    if topic_part:
                        meeting_topic = topic_part
            
            return {
                "meeting_topic": meeting_topic,
                "email_time": email_date.isoformat(),
                "lookback_hint": email_date
            }
            
        except Exception as e:
            logger.error(f"Failed to extract meeting info: {e}")
            return None


async def process_email_trigger(monitor: GmailMonitor, email_id: str) -> bool:
    """
    Process a Gmail trigger email
    
    Args:
        monitor: Gmail monitor instance
        email_id: Gmail message ID
    
    Returns:
        True if processed successfully
    """
    try:
        # Get email details
        email = monitor.get_email_details(email_id)
        if not email:
            return False
        
        # Extract meeting information
        info = monitor.extract_meeting_info(email)
        if not info:
            logger.warning(f"Could not extract meeting info from email {email_id}")
            return False
        
        logger.info(f"Processing trigger for: {info['meeting_topic']}")
        
        # Calculate focused lookback period (±24 hours from email time)
        lookback_hint = info.get("lookback_hint")
        if lookback_hint:
            # Use a 48-hour window centered on email time
            lookback_minutes = 24 * 60  # 24 hours before and after
        else:
            # Fall back to default lookback
            lookback_minutes = int(os.getenv("PULL_LOOKBACK_MINUTES", "360"))
        
        # Fetch recent recordings with focused search
        recordings = await fetch_recent_recordings(lookback_minutes)
        
        if not recordings:
            logger.info("No recordings found for trigger email")
            return True  # Still mark as processed
        
        # Process unprocessed meetings
        state = ProcessedState(STATE_FILE)
        processed_count = 0
        
        for meeting in recordings:
            meeting_topic = meeting.get("topic", "")
            
            # Try to match by topic similarity if available
            if info["meeting_topic"] != "Unknown Meeting":
                if info["meeting_topic"].lower() not in meeting_topic.lower():
                    continue  # Skip non-matching meetings
            
            if await process_meeting(meeting, state):
                processed_count += 1
        
        logger.info(f"Processed {processed_count} meetings from email trigger")
        return True
        
    except Exception as e:
        logger.error(f"Failed to process email trigger: {e}")
        logger.error(traceback.format_exc())
        return False


async def run_gmail_monitor() -> None:
    """Run Gmail monitoring once"""
    logger.info("Checking Gmail for new recording notifications...")
    
    try:
        monitor = GmailMonitor()
        emails = monitor.search_recording_emails()
        
        if not emails:
            logger.info("No new recording emails found")
            return
        
        new_count = 0
        processed_count = 0
        
        for message in emails:
            email_id = message.get('id')
            if not email_id:
                continue
            
            # Check if already processed
            if monitor._is_email_processed(email_id):
                continue
            
            new_count += 1
            logger.info(f"Processing new email trigger: {email_id}")
            
            # Process this email trigger
            if await process_email_trigger(monitor, email_id):
                monitor._mark_email_processed(email_id)
                processed_count += 1
            
            # Small delay between processing
            await asyncio.sleep(2)
        
        logger.info(f"Gmail check completed. New: {new_count}, Processed: {processed_count}")
        
    except Exception as e:
        logger.error(f"Gmail monitor error: {e}")
        logger.error(traceback.format_exc())


async def run_daemon() -> None:
    """Run Gmail monitor as daemon"""
    logger.info(f"Starting Gmail daemon mode, interval: {GMAIL_POLL_INTERVAL_SECONDS} seconds")
    
    while True:
        try:
            await run_gmail_monitor()
        except Exception as e:
            logger.error(f"Error in daemon loop: {e}")
            logger.error(traceback.format_exc())
        
        logger.info(f"Sleeping for {GMAIL_POLL_INTERVAL_SECONDS} seconds...")
        await asyncio.sleep(GMAIL_POLL_INTERVAL_SECONDS)


def main():
    parser = argparse.ArgumentParser(description='Gmail-triggered Zoom Recording Ingestion')
    parser.add_argument(
        '--auth',
        action='store_true',
        help='Run OAuth authentication flow only'
    )
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Run as daemon with periodic polling'
    )
    
    args = parser.parse_args()
    
    if args.auth:
        # Just authenticate and exit
        logger.info("Running Gmail OAuth authentication...")
        monitor = GmailMonitor()
        logger.info("Authentication successful!")
        logger.info(f"Token saved to: {GMAIL_TOKEN_JSON}")
    elif args.daemon:
        try:
            asyncio.run(run_daemon())
        except KeyboardInterrupt:
            logger.info("Daemon stopped by user")
    else:
        # Default: run once
        asyncio.run(run_gmail_monitor())


if __name__ == "__main__":
    main()