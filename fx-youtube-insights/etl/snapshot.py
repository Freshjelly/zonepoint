# path: etl/snapshot.py
import logging
import csv
from datetime import datetime
from typing import List, Dict, Set
import pytz
import yaml
from .youtube_client import YouTubeClient
from .schema import DatabaseManager

logger = logging.getLogger(__name__)

class SnapshotCollector:
    def __init__(self, db_path: str = "data/analytics.duckdb"):
        self.db = DatabaseManager(db_path)
        self.youtube = YouTubeClient()
        self.jst = pytz.timezone('Asia/Tokyo')
        
        # Load config
        with open('config/app.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
    
    def run_snapshot(self):
        """Run complete snapshot collection"""
        logger.info("Starting snapshot collection...")
        snapshot_date = datetime.now(self.jst).date()
        
        # Initialize database schema
        self.db.initialize_schema()
        
        # Check if we have API key
        if not self.youtube.api_key:
            logger.warning("No API key found. Inserting dummy data...")
            self.db.insert_dummy_data()
            return {
                'status': 'dummy_data',
                'message': 'Dummy data inserted for testing',
                'snapshot_date': snapshot_date
            }
        
        results = {
            'channels_processed': 0,
            'videos_processed': 0,
            'new_videos_found': 0,
            'errors': []
        }
        
        # 1. Collect seed channels
        channel_ids = self._load_seed_channels()
        results['channels_processed'] = self._collect_channels(channel_ids, snapshot_date)
        
        # 2. Search for videos by keywords
        video_ids = self._search_videos_by_keywords(snapshot_date)
        results['new_videos_found'] = len(video_ids)
        
        # 3. Collect video statistics
        results['videos_processed'] = self._collect_videos(video_ids, snapshot_date)
        
        # 4. Collect stats for existing videos
        existing_video_ids = self._get_existing_video_ids()
        results['videos_processed'] += self._collect_videos(existing_video_ids, snapshot_date)
        
        logger.info(f"Snapshot collection completed: {results}")
        return results
    
    def _load_seed_channels(self) -> List[str]:
        """Load channel IDs from seed file"""
        channel_ids = []
        with open('config/seed_channels.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row['channel_id'].startswith('#'):
                    channel_ids.append(row['channel_id'])
        return channel_ids
    
    def _load_keywords(self) -> List[str]:
        """Load search keywords"""
        with open('config/keywords_ja.txt', 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    
    def _collect_channels(self, channel_ids: List[str], snapshot_date) -> int:
        """Collect channel information and statistics"""
        if not channel_ids:
            return 0
        
        # Get ETags for caching
        etags = {}
        for channel_id in channel_ids:
            etag = self.db.get_latest_etag('channel', channel_id)
            if etag:
                etags[channel_id] = etag
        
        # Fetch channel data
        channels = self.youtube.get_channel_info(channel_ids, etags)
        
        # Store in database
        for channel in channels:
            # Update channel info
            self.db.upsert_channel({
                'channel_id': channel['channel_id'],
                'title': channel['title'],
                'custom_url': channel.get('custom_url'),
                'published_at': channel['published_at']
            })
            
            # Store statistics snapshot
            self.db.upsert_channel_stats({
                'channel_id': channel['channel_id'],
                'snapshot_date': snapshot_date,
                'view_count': channel['view_count'],
                'subscriber_count': channel['subscriber_count'],
                'video_count': channel['video_count'],
                'etag': channel.get('etag')
            })
        
        return len(channels)
    
    def _search_videos_by_keywords(self, snapshot_date) -> Set[str]:
        """Search for videos using keywords"""
        keywords = self._load_keywords()
        all_video_ids = set()
        
        for keyword in keywords:
            logger.info(f"Searching for keyword: {keyword}")
            videos = self.youtube.search_videos(keyword)
            
            for video in videos:
                all_video_ids.add(video['video_id'])
                
                # Store video basic info
                self.db.upsert_video({
                    'video_id': video['video_id'],
                    'channel_id': video['channel_id'],
                    'title': video['title'],
                    'description': video.get('description'),
                    'published_at': video['published_at'],
                    'duration': None  # Will be updated when fetching stats
                })
                
                # Also add the channel if not in seed
                self.db.upsert_channel({
                    'channel_id': video['channel_id'],
                    'title': video.get('channel_title'),
                    'custom_url': None,
                    'published_at': None
                })
            
            # Record search history
            with self.db.connect() as conn:
                conn.execute("""
                    INSERT INTO search_history (keyword, search_date, results_count)
                    VALUES (?, ?, ?)
                    ON CONFLICT (keyword, search_date) DO UPDATE SET
                        results_count = EXCLUDED.results_count
                """, [keyword, snapshot_date, len(videos)])
        
        return all_video_ids
    
    def _collect_videos(self, video_ids: Set[str], snapshot_date) -> int:
        """Collect video statistics"""
        if not video_ids:
            return 0
        
        video_ids_list = list(video_ids)
        
        # Get ETags for caching
        etags = {}
        for video_id in video_ids_list:
            etag = self.db.get_latest_etag('video', video_id)
            if etag:
                etags[video_id] = etag
        
        # Fetch video statistics
        videos = self.youtube.get_video_stats(video_ids_list, etags)
        
        # Store in database
        for video in videos:
            # Update video info
            self.db.upsert_video({
                'video_id': video['video_id'],
                'channel_id': video['channel_id'],
                'title': video['title'],
                'description': None,  # Not updating description here
                'published_at': video['published_at'],
                'duration': video['duration']
            })
            
            # Store statistics snapshot
            self.db.upsert_video_stats({
                'video_id': video['video_id'],
                'snapshot_date': snapshot_date,
                'view_count': video['view_count'],
                'like_count': video['like_count'],
                'comment_count': video['comment_count'],
                'etag': video.get('etag')
            })
        
        return len(videos)
    
    def _get_existing_video_ids(self) -> Set[str]:
        """Get all existing video IDs from database"""
        with self.db.connect() as conn:
            result = conn.execute("""
                SELECT DISTINCT video_id 
                FROM videos 
                WHERE published_at >= CURRENT_DATE - INTERVAL '30 days'
            """).fetchall()
            
            return {row[0] for row in result}