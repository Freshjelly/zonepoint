# path: etl/schema.py
import duckdb
import os
from datetime import datetime
import pytz
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "data/analytics.duckdb"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn: Optional[duckdb.DuckDBPyConnection] = None
        
    def connect(self):
        """Connect to DuckDB database"""
        self.conn = duckdb.connect(self.db_path)
        self.conn.execute("SET TimeZone = 'Asia/Tokyo'")
        return self.conn
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def initialize_schema(self):
        """Create tables if they don't exist"""
        with self.connect() as conn:
            # Channels table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id VARCHAR PRIMARY KEY,
                    title VARCHAR,
                    custom_url VARCHAR,
                    published_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Channel statistics snapshots
            conn.execute("""
                CREATE TABLE IF NOT EXISTS channel_stats (
                    channel_id VARCHAR,
                    snapshot_date DATE,
                    view_count BIGINT,
                    subscriber_count BIGINT,
                    video_count INTEGER,
                    etag VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (channel_id, snapshot_date),
                    FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
                )
            """)
            
            # Videos table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    video_id VARCHAR PRIMARY KEY,
                    channel_id VARCHAR,
                    title VARCHAR,
                    description TEXT,
                    published_at TIMESTAMP,
                    duration VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
                )
            """)
            
            # Video statistics snapshots
            conn.execute("""
                CREATE TABLE IF NOT EXISTS video_stats (
                    video_id VARCHAR,
                    snapshot_date DATE,
                    view_count BIGINT,
                    like_count INTEGER,
                    comment_count INTEGER,
                    etag VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (video_id, snapshot_date),
                    FOREIGN KEY (video_id) REFERENCES videos(video_id)
                )
            """)
            
            # Weekly metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS weekly_metrics (
                    scope VARCHAR,  -- 'industry', 'channel', 'video'
                    entity_id VARCHAR,  -- channel_id or video_id or 'all' for industry
                    week_start DATE,
                    week_end DATE,
                    views_delta_week BIGINT,
                    views_total BIGINT,
                    delta_pct DOUBLE,
                    zscore DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (scope, entity_id, week_start)
                )
            """)
            
            # Search history table (to track what we've searched)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_history (
                    keyword VARCHAR,
                    search_date DATE,
                    results_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (keyword, search_date)
                )
            """)
            
            logger.info("Database schema initialized successfully")
    
    def upsert_channel(self, channel_data: dict):
        """Insert or update channel data"""
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO channels (channel_id, title, custom_url, published_at, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (channel_id) 
                DO UPDATE SET 
                    title = EXCLUDED.title,
                    custom_url = EXCLUDED.custom_url,
                    updated_at = CURRENT_TIMESTAMP
            """, [
                channel_data['channel_id'],
                channel_data.get('title'),
                channel_data.get('custom_url'),
                channel_data.get('published_at')
            ])
    
    def upsert_channel_stats(self, stats_data: dict):
        """Insert or update channel statistics"""
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO channel_stats (
                    channel_id, snapshot_date, view_count, 
                    subscriber_count, video_count, etag
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (channel_id, snapshot_date)
                DO UPDATE SET
                    view_count = EXCLUDED.view_count,
                    subscriber_count = EXCLUDED.subscriber_count,
                    video_count = EXCLUDED.video_count,
                    etag = EXCLUDED.etag
            """, [
                stats_data['channel_id'],
                stats_data['snapshot_date'],
                stats_data.get('view_count', 0),
                stats_data.get('subscriber_count', 0),
                stats_data.get('video_count', 0),
                stats_data.get('etag')
            ])
    
    def upsert_video(self, video_data: dict):
        """Insert or update video data"""
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO videos (
                    video_id, channel_id, title, description, 
                    published_at, duration, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (video_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    updated_at = CURRENT_TIMESTAMP
            """, [
                video_data['video_id'],
                video_data['channel_id'],
                video_data.get('title'),
                video_data.get('description'),
                video_data.get('published_at'),
                video_data.get('duration')
            ])
    
    def upsert_video_stats(self, stats_data: dict):
        """Insert or update video statistics"""
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO video_stats (
                    video_id, snapshot_date, view_count,
                    like_count, comment_count, etag
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (video_id, snapshot_date)
                DO UPDATE SET
                    view_count = EXCLUDED.view_count,
                    like_count = EXCLUDED.like_count,
                    comment_count = EXCLUDED.comment_count,
                    etag = EXCLUDED.etag
            """, [
                stats_data['video_id'],
                stats_data['snapshot_date'],
                stats_data.get('view_count', 0),
                stats_data.get('like_count', 0),
                stats_data.get('comment_count', 0),
                stats_data.get('etag')
            ])
    
    def upsert_weekly_metrics(self, metrics_data: dict):
        """Insert or update weekly metrics"""
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO weekly_metrics (
                    scope, entity_id, week_start, week_end,
                    views_delta_week, views_total, delta_pct, zscore
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (scope, entity_id, week_start)
                DO UPDATE SET
                    week_end = EXCLUDED.week_end,
                    views_delta_week = EXCLUDED.views_delta_week,
                    views_total = EXCLUDED.views_total,
                    delta_pct = EXCLUDED.delta_pct,
                    zscore = EXCLUDED.zscore
            """, [
                metrics_data['scope'],
                metrics_data['entity_id'],
                metrics_data['week_start'],
                metrics_data['week_end'],
                metrics_data['views_delta_week'],
                metrics_data['views_total'],
                metrics_data['delta_pct'],
                metrics_data.get('zscore')
            ])
    
    def get_latest_etag(self, resource_type: str, resource_id: str) -> Optional[str]:
        """Get latest ETag for a resource"""
        with self.connect() as conn:
            if resource_type == 'channel':
                result = conn.execute("""
                    SELECT etag FROM channel_stats
                    WHERE channel_id = ?
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """, [resource_id]).fetchone()
            else:  # video
                result = conn.execute("""
                    SELECT etag FROM video_stats
                    WHERE video_id = ?
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """, [resource_id]).fetchone()
            
            return result[0] if result else None
    
    def insert_dummy_data(self):
        """Insert dummy data for testing"""
        import random
        from datetime import timedelta
        
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        
        # Insert dummy channels
        dummy_channels = [
            ('UCdummy001fx', 'FXトレーダー太郎'),
            ('UCdummy002fx', '為替予想チャンネル'),
            ('UCdummy003fx', 'ドル円分析ラボ'),
            ('UCdummy004fx', 'FX初心者講座'),
            ('UCdummy005fx', 'テクニカル分析マスター')
        ]
        
        with self.connect() as conn:
            for channel_id, title in dummy_channels:
                self.upsert_channel({
                    'channel_id': channel_id,
                    'title': title,
                    'custom_url': f'@{title.replace(" ", "")}',
                    'published_at': now - timedelta(days=random.randint(100, 1000))
                })
                
                # Add channel stats for last 14 days
                for days_ago in range(14):
                    snapshot_date = (now - timedelta(days=days_ago)).date()
                    self.upsert_channel_stats({
                        'channel_id': channel_id,
                        'snapshot_date': snapshot_date,
                        'view_count': random.randint(100000, 10000000),
                        'subscriber_count': random.randint(1000, 100000),
                        'video_count': random.randint(50, 500),
                        'etag': f'dummy_etag_{days_ago}'
                    })
                
                # Add dummy videos
                for video_num in range(10):
                    video_id = f'{channel_id}_video_{video_num}'
                    self.upsert_video({
                        'video_id': video_id,
                        'channel_id': channel_id,
                        'title': f'動画タイトル {video_num}: ドル円分析',
                        'description': 'テスト動画の説明文',
                        'published_at': now - timedelta(days=random.randint(1, 30)),
                        'duration': 'PT10M30S'
                    })
                    
                    # Add video stats
                    base_views = random.randint(1000, 100000)
                    for days_ago in range(14):
                        snapshot_date = (now - timedelta(days=days_ago)).date()
                        self.upsert_video_stats({
                            'video_id': video_id,
                            'snapshot_date': snapshot_date,
                            'view_count': base_views + random.randint(0, 1000) * (14 - days_ago),
                            'like_count': random.randint(10, 1000),
                            'comment_count': random.randint(1, 100),
                            'etag': f'dummy_video_etag_{days_ago}'
                        })
        
        logger.info("Dummy data inserted successfully")