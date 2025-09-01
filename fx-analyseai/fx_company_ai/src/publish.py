import os
import requests
import time
import random
import logging
import json

logger = logging.getLogger(__name__)

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

def post_webhook(text: str, max_retries: int = 3):
    """Post message to Discord webhook with retry logic"""
    
    # Prepare the payload
    payload = {"content": text[:1900]}
    
    # DRY_RUN mode: log payload instead of sending
    if DRY_RUN:
        logger.info(f"[DRY_RUN] Would send to Discord: message={text[:100]}...")
        logger.info(f"[DRY_RUN] Full payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        return
    
    if not WEBHOOK:
        logger.warning("Discord webhook URL not configured")
        return
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                WEBHOOK, 
                json=payload, 
                timeout=10
            )
            
            if response.status_code == 204:
                logger.info("Message sent successfully to Discord")
                return
            elif response.status_code == 429:
                # Rate limited - use retry-after header if available
                retry_after = float(response.headers.get("Retry-After", 1))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
            elif response.status_code >= 500:
                # Server error - use exponential backoff
                wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                logger.warning(f"Server error {response.status_code}, retrying in {wait_time:.1f}s")
                time.sleep(wait_time)
            else:
                logger.error(f"Discord webhook failed with status {response.status_code}: {response.text}")
                break
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    logger.error(f"Failed to send message after {max_retries} attempts")