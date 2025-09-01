"""
Zoom → Auto Minutes (Summary/ToDo/Delivery) MVP
Python + FastAPI implementation
"""

import os
import hashlib
import hmac
import json
import logging
import base64
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI

from utils_vtt import vtt_to_text

load_dotenv()

# Configuration
INGESTION_MODE = os.getenv("INGESTION_MODE", "webhook")  # webhook|pull|gmail
ZOOM_WEBHOOK_SECRET_TOKEN = os.getenv("ZOOM_WEBHOOK_SECRET_TOKEN", "")
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID", "")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID", "")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "./service-account.json")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
MINUTES_SHARE_ANYONE = os.getenv("MINUTES_SHARE_ANYONE", "true").lower() == "true"
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tokyo")
REPLAY_WINDOW_SECONDS = int(os.getenv("REPLAY_WINDOW_SECONDS", "300"))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Zoom Minutes MVP")


class ValidationResponse(BaseModel):
    plainToken: str
    encryptedToken: str


def verify_zoom_signature(raw_body: bytes, signature: str, timestamp: str) -> bool:
    """
    Verify Zoom webhook signature
    Returns True if valid, False otherwise
    """
    try:
        # Check replay attack protection
        current_time = time.time()
        request_time = int(timestamp)
        if abs(current_time - request_time) > REPLAY_WINDOW_SECONDS:
            logger.warning(f"Timestamp out of replay window: {abs(current_time - request_time)} seconds")
            return False

        # Create signature
        message = f"v0:{timestamp}:{raw_body.decode('utf-8', errors='ignore')}"
        expected_signature = hmac.new(
            ZOOM_WEBHOOK_SECRET_TOKEN.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Handle both v0=<hex> and <hex> formats
        received_signature = signature
        if signature.startswith("v0="):
            received_signature = signature[3:]
        
        # Constant time comparison
        return hmac.compare_digest(expected_signature, received_signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


async def get_zoom_access_token() -> str:
    """
    Get Zoom Server-to-Server OAuth access token
    """
    url = "https://zoom.us/oauth/token"
    params = {
        "grant_type": "account_credentials",
        "account_id": ZOOM_ACCOUNT_ID
    }
    
    # Basic auth
    credentials = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()["access_token"]


async def fetch_recording_files(meeting_uuid: str, token: str) -> Dict[str, Any]:
    """
    Fetch recording files from Zoom API
    Note: meeting_uuid needs double encoding if it contains slashes
    """
    # Double encode UUID if it contains slashes
    encoded_uuid = quote(quote(meeting_uuid, safe=''), safe='')
    
    url = f"https://api.zoom.us/v2/meetings/{encoded_uuid}/recordings"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


async def download_with_oauth(download_url: str, token: str) -> bytes:
    """
    Download file from Zoom with OAuth token
    """
    # Add access_token to URL
    separator = "&" if "?" in download_url else "?"
    url_with_token = f"{download_url}{separator}access_token={token}"
    
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url_with_token)
        response.raise_for_status()
        return response.content


async def get_transcript_text(recording_data: Dict[str, Any], token: str) -> str:
    """
    Extract transcript from recording files
    Priority: VTT transcript > Audio with Whisper (if available)
    """
    recording_files = recording_data.get("recording_files", [])
    
    # First try to get VTT transcript
    for file_info in recording_files:
        file_type = file_info.get("file_type", "")
        if file_type in ["TRANSCRIPT", "TIMELINE_TRANSCRIPT", "CC"]:
            try:
                logger.info(f"Downloading VTT transcript: {file_type}")
                vtt_content = await download_with_oauth(file_info["download_url"], token)
                return vtt_to_text(vtt_content)
            except Exception as e:
                logger.warning(f"Failed to process VTT: {e}")
                continue
    
    # Fallback to audio transcription with Whisper (if available)
    if OPENAI_API_KEY:
        for file_info in recording_files:
            file_type = file_info.get("file_type", "")
            if file_type in ["AUDIO_ONLY", "M4A"]:
                try:
                    logger.info("No VTT found, attempting Whisper transcription")
                    # Note: Whisper integration would require additional setup
                    # This is a placeholder for the actual implementation
                    logger.warning("Whisper transcription not implemented in MVP")
                    break
                except Exception as e:
                    logger.warning(f"Failed to transcribe audio: {e}")
                    break
    
    # If no transcript available, return placeholder
    return "Transcript not available for this recording."


async def summarize_and_extract_todos(text: str) -> Dict[str, Any]:
    """
    Use LLM to extract summary, decisions, and todos
    Falls back to simple extraction if LLM unavailable
    """
    if OPENAI_API_KEY:
        try:
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            
            prompt = f"""
            以下の会議記録から、次の3つを抽出してください：
            1. 要点サマリー（箇条書き）
            2. 決定事項（箇条書き）
            3. ToDo項目（タスク、担当者、期限）

            出力は以下のJSON形式で返してください：
            {{
                "summary": ["項目1", "項目2", ...],
                "decisions": ["決定1", "決定2", ...],
                "todos": [
                    {{"task": "タスク内容", "owner": "担当者名", "due": "YYYY-MM-DD or 空"}},
                    ...
                ]
            }}

            会議記録：
            {text}
            """
            
            resp = await client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "あなたは会議の議事録を作成するアシスタントです。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            content = resp.choices[0].message.content
            result = json.loads(content)
            return result
            
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}")
    
    # Fallback: Simple extraction
    lines = text.split('\n')
    summary_lines = lines[:5] if len(lines) > 5 else lines
    
    return {
        "summary": [line.strip() for line in summary_lines if line.strip()],
        "decisions": ["会議内容から決定事項を抽出できませんでした"],
        "todos": [
            {"task": "議事録の詳細確認", "owner": "参加者", "due": ""}
        ]
    }


async def create_minutes_doc(title: str, minutes: Dict[str, Any]) -> str:
    """
    Create Google Document with meeting minutes
    Returns the document URL
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        # Load service account credentials
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_JSON,
            scopes=[
                'https://www.googleapis.com/auth/documents',
                'https://www.googleapis.com/auth/drive'
            ]
        )
        
        # Create services
        docs_service = build('docs', 'v1', credentials=credentials)
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # Create document
        doc = docs_service.documents().create(body={'title': title}).execute()
        doc_id = doc['documentId']
        
        # Build content
        requests = []
        content = []
        
        # Add summary section
        content.append("## 要点サマリー\n")
        for item in minutes.get("summary", []):
            content.append(f"• {item}\n")
        content.append("\n")
        
        # Add decisions section
        content.append("## 決定事項\n")
        for item in minutes.get("decisions", []):
            content.append(f"• {item}\n")
        content.append("\n")
        
        # Add todos section
        content.append("## ToDo\n")
        for todo in minutes.get("todos", []):
            task = todo.get("task", "")
            owner = todo.get("owner", "未定")
            due = todo.get("due", "未定")
            content.append(f"• {task} (担当: {owner}, 期限: {due})\n")
        
        # Insert content
        full_content = "".join(content)
        requests.append({
            'insertText': {
                'location': {'index': 1},
                'text': full_content
            }
        })
        
        # Update document
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        
        # Set sharing permissions if configured
        if MINUTES_SHARE_ANYONE:
            drive_service.permissions().create(
                fileId=doc_id,
                body={
                    'type': 'anyone',
                    'role': 'reader'
                }
            ).execute()
        
        # Return document URL
        return f"https://docs.google.com/document/d/{doc_id}/edit"
        
    except Exception as e:
        logger.error(f"Failed to create Google Doc: {e}")
        logger.error(traceback.format_exc())
        raise


async def post_to_discord(message: str):
    """
    Post message to Discord webhook
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL not configured")
        return
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message}
        )
        response.raise_for_status()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"ok": True}


@app.post("/zoom/webhook")
async def zoom_webhook(request: Request):
    """
    Zoom webhook endpoint
    Handles URL validation and recording.completed events
    """
    raw_body = await request.body()
    
    try:
        body = json.loads(raw_body)
        event_type = body.get("event", "")
        
        # Handle URL validation
        if event_type == "endpoint.url_validation":
            plain_token = body.get("payload", {}).get("plainToken", "")
            
            # Generate encrypted token
            encrypted_token = hmac.new(
                ZOOM_WEBHOOK_SECRET_TOKEN.encode(),
                plain_token.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return ValidationResponse(
                plainToken=plain_token,
                encryptedToken=encrypted_token
            )
        
        # Verify signature for other events
        signature = request.headers.get("x-zm-signature", "")
        timestamp = request.headers.get("x-zm-request-timestamp", "")
        
        if not verify_zoom_signature(raw_body, signature, timestamp):
            logger.warning(f"Invalid signature for event: {event_type}")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Handle recording.completed event
        if event_type == "recording.completed":
            logger.info("Processing recording.completed event")
            
            payload = body.get("payload", {})
            object_data = payload.get("object", {})
            
            meeting_uuid = object_data.get("uuid", "")
            meeting_topic = object_data.get("topic", "Zoom Meeting")
            
            # Get OAuth token once for reuse
            token = await get_zoom_access_token()
            
            # Fetch recording files
            recording_data = await fetch_recording_files(meeting_uuid, token)
            
            # Get transcript
            transcript_text = await get_transcript_text(recording_data, token)
            
            # Extract summary and todos
            minutes = await summarize_and_extract_todos(transcript_text)
            
            # Create document title with date
            tz = ZoneInfo(TIMEZONE)
            meeting_date = datetime.now(tz).strftime("%Y-%m-%d")
            doc_title = f"{meeting_topic} {meeting_date} 議事録"
            
            # Create Google Doc
            doc_url = await create_minutes_doc(doc_title, minutes)
            
            # Post to Discord
            discord_message = f"📄 {doc_title}\n{doc_url}"
            await post_to_discord(discord_message)
            
            logger.info(f"Successfully processed meeting: {meeting_topic}")
            return {"status": "success", "doc_url": doc_url}
        
        # Return success for other events
        return {"status": "success"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )


if __name__ == "__main__":
    import uvicorn
    
    # Check ingestion mode
    if INGESTION_MODE in ["pull", "gmail"]:
        logger.info(f"INGESTION_MODE is '{INGESTION_MODE}'. Web server will only provide health endpoint.")
        logger.info(f"To run {INGESTION_MODE} ingestion:")
        if INGESTION_MODE == "pull":
            logger.info("  python pull_worker.py --once   # Run once")
            logger.info("  python pull_worker.py --daemon # Run as daemon")
        elif INGESTION_MODE == "gmail":
            logger.info("  python gmail_ingest.py --auth   # Initial OAuth setup")
            logger.info("  python gmail_ingest.py          # Run once")
            logger.info("  python gmail_ingest.py --daemon # Run as daemon")
    elif INGESTION_MODE == "webhook":
        logger.info("Running in webhook mode. Server will listen for Zoom webhooks.")
    else:
        logger.warning(f"Unknown INGESTION_MODE: {INGESTION_MODE}. Defaulting to webhook mode.")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)