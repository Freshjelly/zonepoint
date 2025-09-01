"""RSS feed collector."""

import hashlib
import time
from datetime import datetime, timezone
from typing import List, Optional
import feedparser
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, HttpUrl
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

class Article(BaseModel):
    """Article data model."""
    id: str
    source: str
    url: HttpUrl
    ts: datetime
    title: str
    body: str
    lang: str = Field(default="en")

class RSSCollector:
    """Collect articles from RSS feeds."""
    
    def __init__(self, feeds: List[str], timeout: int = 30):
        self.feeds = feeds
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
    
    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _fetch_feed(self, feed_url: str) -> Optional[feedparser.FeedParserDict]:
        """Fetch and parse RSS feed."""
        try:
            response = self.client.get(feed_url)
            response.raise_for_status()
            return feedparser.parse(response.text)
        except Exception as e:
            logger.error(f"Failed to fetch feed {feed_url}: {e}")
            return None
    
    def _extract_body(self, entry: dict) -> str:
        """Extract body text from feed entry."""
        body = ""
        
        # Try different fields
        if "content" in entry:
            content = entry.content[0] if isinstance(entry.content, list) else entry.content
            body = content.get("value", "")
        elif "summary" in entry:
            body = entry.summary
        elif "description" in entry:
            body = entry.description
        
        # Clean HTML if present
        if body and "<" in body:
            soup = BeautifulSoup(body, "html.parser")
            body = soup.get_text(separator=" ", strip=True)
        
        return body
    
    def _parse_timestamp(self, entry: dict) -> datetime:
        """Parse timestamp from feed entry."""
        # Try different date fields
        for field in ["published_parsed", "updated_parsed", "created_parsed"]:
            if hasattr(entry, field):
                time_struct = getattr(entry, field)
                if time_struct and time_struct is not None:
                    try:
                        # Convert time.struct_time to datetime
                        timestamp = time.mktime(time_struct)
                        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    except (ValueError, TypeError, OverflowError):
                        continue
        
        # Try string date fields as fallback
        for field in ["published", "updated", "created"]:
            if hasattr(entry, field):
                date_str = getattr(entry, field)
                if date_str:
                    try:
                        # Try to parse common date formats
                        from dateutil import parser
                        parsed_date = parser.parse(date_str)
                        # Convert to UTC if timezone naive
                        if parsed_date.tzinfo is None:
                            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                        return parsed_date.astimezone(timezone.utc)
                    except Exception:
                        continue
        
        # Default to now
        return datetime.now(timezone.utc)
    
    def _generate_id(self, url: str) -> str:
        """Generate unique ID for article."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def collect(self, limit_per_feed: int = 10) -> List[Article]:
        """Collect articles from all feeds."""
        all_articles = []
        
        for feed_url in self.feeds:
            logger.info(f"Collecting from {feed_url}")
            feed = self._fetch_feed(feed_url)
            
            if not feed or not feed.entries:
                continue
            
            # Extract source name
            source = feed.feed.get("title", feed_url.split("/")[2])
            
            # Process entries
            for entry in feed.entries[:limit_per_feed]:
                try:
                    # Skip if no link
                    if not hasattr(entry, "link"):
                        continue
                    
                    article = Article(
                        id=self._generate_id(entry.link),
                        source=source,
                        url=entry.link,
                        ts=self._parse_timestamp(entry),
                        title=entry.get("title", "No title"),
                        body=self._extract_body(entry),
                        lang="en"  # Will be detected later
                    )
                    
                    all_articles.append(article)
                    
                except Exception as e:
                    logger.error(f"Failed to parse entry: {e}")
                    continue
        
        # Sort by timestamp (newest first)
        all_articles.sort(key=lambda x: x.ts, reverse=True)
        
        logger.info(f"Collected {len(all_articles)} articles")
        return all_articles