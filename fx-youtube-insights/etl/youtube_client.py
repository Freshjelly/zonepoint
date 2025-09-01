# path: etl/youtube_client.py
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pytz
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import yaml

logger = logging.getLogger(__name__)

class YouTubeClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        self.youtube = None
        self.jst = pytz.timezone('Asia/Tokyo')
        
        # Load config
        with open('config/app.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        if self.api_key:
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        else:
            logger.warning("No YouTube API key provided. Running in dummy mode.")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpError)
    )
    def get_channel_info(self, channel_ids: List[str], etags: Dict[str, str] = None) -> List[Dict]:
        """Get channel information with ETag support"""
        if not self.youtube:
            return []
        
        etags = etags or {}
        results = []
        
        # Process in batches
        batch_size = self.config['youtube']['batch_size']
        for i in range(0, len(channel_ids), batch_size):
            batch = channel_ids[i:i + batch_size]
            
            try:
                request = self.youtube.channels().list(
                    part='snippet,statistics',
                    id=','.join(batch)
                )
                
                # Add ETag if available (for caching)
                # Note: YouTube API v3 doesn't support per-item ETags well
                # This is more for demonstration
                response = request.execute()
                
                for item in response.get('items', []):
                    channel_data = {
                        'channel_id': item['id'],
                        'title': item['snippet']['title'],
                        'description': item['snippet'].get('description', ''),
                        'custom_url': item['snippet'].get('customUrl'),
                        'published_at': self._parse_datetime(item['snippet']['publishedAt']),
                        'view_count': int(item['statistics'].get('viewCount', 0)),
                        'subscriber_count': int(item['statistics'].get('subscriberCount', 0)),
                        'video_count': int(item['statistics'].get('videoCount', 0)),
                        'etag': item.get('etag')
                    }
                    results.append(channel_data)
                    
            except HttpError as e:
                if e.resp.status == 429:
                    logger.error("YouTube API quota exceeded")
                    raise
                elif e.resp.status >= 500:
                    logger.error(f"YouTube API server error: {e}")
                    raise
                else:
                    logger.error(f"YouTube API error: {e}")
                    continue
        
        return results
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpError)
    )
    def search_videos(self, keyword: str, published_after: Optional[datetime] = None) -> List[Dict]:
        """Search for videos by keyword"""
        if not self.youtube:
            return []
        
        if not published_after:
            published_after = datetime.now(self.jst) - timedelta(
                days=self.config['youtube']['search_days']
            )
        
        results = []
        
        try:
            request = self.youtube.search().list(
                part='id,snippet',
                q=keyword,
                type='video',
                order='viewCount',
                publishedAfter=published_after.isoformat(),
                maxResults=self.config['youtube']['search_limit_per_run']
            )
            
            response = request.execute()
            
            for item in response.get('items', []):
                video_data = {
                    'video_id': item['id']['videoId'],
                    'channel_id': item['snippet']['channelId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet'].get('description', ''),
                    'published_at': self._parse_datetime(item['snippet']['publishedAt']),
                    'channel_title': item['snippet'].get('channelTitle')
                }
                results.append(video_data)
                
        except HttpError as e:
            if e.resp.status == 429:
                logger.error("YouTube API quota exceeded")
                raise
            else:
                logger.error(f"YouTube API error during search: {e}")
        
        return results
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpError)
    )
    def get_video_stats(self, video_ids: List[str], etags: Dict[str, str] = None) -> List[Dict]:
        """Get video statistics with ETag support"""
        if not self.youtube:
            return []
        
        etags = etags or {}
        results = []
        
        # Process in batches
        batch_size = self.config['youtube']['batch_size']
        for i in range(0, len(video_ids), batch_size):
            batch = video_ids[i:i + batch_size]
            
            try:
                request = self.youtube.videos().list(
                    part='statistics,contentDetails,snippet',
                    id=','.join(batch)
                )
                
                response = request.execute()
                
                for item in response.get('items', []):
                    video_data = {
                        'video_id': item['id'],
                        'channel_id': item['snippet']['channelId'],
                        'title': item['snippet']['title'],
                        'published_at': self._parse_datetime(item['snippet']['publishedAt']),
                        'duration': item['contentDetails']['duration'],
                        'view_count': int(item['statistics'].get('viewCount', 0)),
                        'like_count': int(item['statistics'].get('likeCount', 0)),
                        'comment_count': int(item['statistics'].get('commentCount', 0)),
                        'etag': item.get('etag')
                    }
                    results.append(video_data)
                    
            except HttpError as e:
                if e.resp.status == 429:
                    logger.error("YouTube API quota exceeded")
                    raise
                elif e.resp.status >= 500:
                    logger.error(f"YouTube API server error: {e}")
                    raise
                else:
                    logger.error(f"YouTube API error: {e}")
                    continue
        
        return results
    
    def _parse_datetime(self, datetime_str: str) -> datetime:
        """Parse YouTube datetime string to timezone-aware datetime"""
        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        return dt.astimezone(self.jst)
    
    def check_quota_status(self) -> Dict[str, Any]:
        """Check API quota status (simplified)"""
        # Note: YouTube API v3 doesn't provide direct quota status
        # This is a placeholder for quota tracking logic
        return {
            'status': 'ok' if self.youtube else 'no_api_key',
            'message': 'API key configured' if self.youtube else 'Running in dummy mode'
        }