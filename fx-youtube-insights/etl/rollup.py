# path: etl/rollup.py
import logging
from datetime import datetime, timedelta
import pytz
import pandas as pd
import numpy as np
from scipy import stats
from .schema import DatabaseManager

logger = logging.getLogger(__name__)

class WeeklyRollup:
    def __init__(self, db_path: str = "data/analytics.duckdb"):
        self.db = DatabaseManager(db_path)
        self.jst = pytz.timezone('Asia/Tokyo')
    
    def calculate_weekly_metrics(self, target_date: datetime = None):
        """Calculate weekly metrics for industry and channels"""
        if target_date is None:
            target_date = datetime.now(self.jst)
        
        # Get week boundaries (Monday to Sunday)
        week_start, week_end = self._get_week_boundaries(target_date)
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_end - timedelta(days=7)
        
        logger.info(f"Calculating metrics for week: {week_start} to {week_end}")
        
        results = {
            'week_start': week_start,
            'week_end': week_end,
            'industry': {},
            'channels': {},
            'top_videos': []
        }
        
        # Calculate video-level metrics
        video_metrics = self._calculate_video_metrics(
            week_start, week_end, prev_week_start, prev_week_end
        )
        
        # Calculate channel-level metrics
        channel_metrics = self._calculate_channel_metrics(video_metrics)
        
        # Calculate industry-level metrics
        industry_metrics = self._calculate_industry_metrics(video_metrics)
        
        # Calculate Z-scores
        self._calculate_zscores(channel_metrics, industry_metrics)
        
        # Store metrics in database
        self._store_weekly_metrics(week_start, week_end, industry_metrics, channel_metrics, video_metrics)
        
        # Prepare results
        results['industry'] = industry_metrics
        results['channels'] = channel_metrics
        results['top_videos'] = self._get_top_videos(video_metrics)
        
        return results
    
    def _get_week_boundaries(self, date: datetime):
        """Get Monday-Sunday boundaries for the week containing the date"""
        # Convert to date in JST
        date_jst = date.astimezone(self.jst).date()
        
        # Find Monday (weekday 0)
        days_since_monday = date_jst.weekday()
        week_start = date_jst - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)
        
        return week_start, week_end
    
    def _calculate_video_metrics(self, week_start, week_end, prev_week_start, prev_week_end):
        """Calculate weekly view deltas for all videos"""
        with self.db.connect() as conn:
            # Get view counts at week boundaries
            query = """
                WITH week_boundaries AS (
                    SELECT 
                        video_id,
                        MAX(CASE WHEN snapshot_date <= ? THEN view_count END) as views_week_end,
                        MAX(CASE WHEN snapshot_date <= ? THEN view_count END) as views_week_start,
                        MAX(CASE WHEN snapshot_date <= ? THEN view_count END) as views_prev_week_end,
                        MAX(CASE WHEN snapshot_date <= ? THEN view_count END) as views_prev_week_start
                    FROM video_stats
                    WHERE snapshot_date <= ?
                    GROUP BY video_id
                ),
                video_info AS (
                    SELECT 
                        v.video_id,
                        v.channel_id,
                        v.title,
                        v.published_at
                    FROM videos v
                )
                SELECT 
                    vi.*,
                    wb.views_week_end,
                    wb.views_week_start,
                    wb.views_prev_week_end,
                    wb.views_prev_week_start,
                    COALESCE(wb.views_week_end, 0) - COALESCE(wb.views_week_start, 0) as delta_this_week,
                    COALESCE(wb.views_prev_week_end, 0) - COALESCE(wb.views_prev_week_start, 0) as delta_last_week
                FROM video_info vi
                LEFT JOIN week_boundaries wb ON vi.video_id = wb.video_id
                WHERE wb.views_week_end IS NOT NULL OR wb.views_prev_week_end IS NOT NULL
            """
            
            df = pd.read_sql(query, conn, params=[
                week_end, week_start - timedelta(days=1),
                prev_week_end, prev_week_start - timedelta(days=1),
                week_end
            ])
        
        # Calculate percentage change
        df['delta_pct'] = df.apply(
            lambda row: self._calculate_percentage_change(
                row['delta_this_week'], 
                row['delta_last_week']
            ), axis=1
        )
        
        return df
    
    def _calculate_channel_metrics(self, video_metrics: pd.DataFrame):
        """Aggregate video metrics to channel level"""
        channel_metrics = video_metrics.groupby('channel_id').agg({
            'delta_this_week': 'sum',
            'delta_last_week': 'sum'
        }).reset_index()
        
        # Calculate percentage change
        channel_metrics['delta_pct'] = channel_metrics.apply(
            lambda row: self._calculate_percentage_change(
                row['delta_this_week'],
                row['delta_last_week']
            ), axis=1
        )
        
        # Get channel names
        with self.db.connect() as conn:
            channels_df = pd.read_sql(
                "SELECT channel_id, title FROM channels",
                conn
            )
        
        channel_metrics = channel_metrics.merge(channels_df, on='channel_id', how='left')
        
        return channel_metrics
    
    def _calculate_industry_metrics(self, video_metrics: pd.DataFrame):
        """Calculate industry-wide metrics"""
        total_this_week = video_metrics['delta_this_week'].sum()
        total_last_week = video_metrics['delta_last_week'].sum()
        
        return {
            'views_delta_this_week': int(total_this_week),
            'views_delta_last_week': int(total_last_week),
            'delta_pct': self._calculate_percentage_change(total_this_week, total_last_week),
            'video_count': len(video_metrics),
            'channel_count': video_metrics['channel_id'].nunique()
        }
    
    def _calculate_zscores(self, channel_metrics: pd.DataFrame, industry_metrics: dict):
        """Calculate Z-scores for channels relative to industry"""
        if len(channel_metrics) < 2:
            channel_metrics['zscore'] = 0
            return
        
        # Get distribution statistics
        delta_pcts = channel_metrics['delta_pct'].values
        median_pct = np.median(delta_pcts)
        std_pct = np.std(delta_pcts)
        
        # Calculate Z-scores
        if std_pct > 0:
            channel_metrics['zscore'] = (channel_metrics['delta_pct'] - median_pct) / std_pct
        else:
            channel_metrics['zscore'] = 0
        
        # Store median and std in industry metrics
        industry_metrics['median_delta_pct'] = median_pct
        industry_metrics['std_delta_pct'] = std_pct
    
    def _calculate_percentage_change(self, current, previous):
        """Calculate percentage change with safe division"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / abs(previous)) * 100
    
    def _store_weekly_metrics(self, week_start, week_end, industry_metrics, 
                              channel_metrics, video_metrics):
        """Store calculated metrics in database"""
        # Store industry metrics
        self.db.upsert_weekly_metrics({
            'scope': 'industry',
            'entity_id': 'all',
            'week_start': week_start,
            'week_end': week_end,
            'views_delta_week': industry_metrics['views_delta_this_week'],
            'views_total': industry_metrics['views_delta_this_week'],
            'delta_pct': industry_metrics['delta_pct'],
            'zscore': None
        })
        
        # Store channel metrics
        for _, row in channel_metrics.iterrows():
            self.db.upsert_weekly_metrics({
                'scope': 'channel',
                'entity_id': row['channel_id'],
                'week_start': week_start,
                'week_end': week_end,
                'views_delta_week': int(row['delta_this_week']),
                'views_total': int(row['delta_this_week']),
                'delta_pct': row['delta_pct'],
                'zscore': row.get('zscore', 0)
            })
        
        # Store top video metrics
        top_videos = video_metrics.nlargest(100, 'delta_this_week')
        for _, row in top_videos.iterrows():
            self.db.upsert_weekly_metrics({
                'scope': 'video',
                'entity_id': row['video_id'],
                'week_start': week_start,
                'week_end': week_end,
                'views_delta_week': int(row['delta_this_week']),
                'views_total': int(row.get('views_week_end', 0)),
                'delta_pct': row['delta_pct'],
                'zscore': None
            })
    
    def _get_top_videos(self, video_metrics: pd.DataFrame, n: int = 20):
        """Get top performing videos of the week"""
        top_videos = video_metrics.nlargest(n, 'delta_this_week')
        
        return [
            {
                'video_id': row['video_id'],
                'title': row['title'],
                'channel_id': row['channel_id'],
                'published_at': row['published_at'],
                'views_delta': int(row['delta_this_week']),
                'delta_pct': row['delta_pct']
            }
            for _, row in top_videos.iterrows()
        ]
    
    def get_channel_judgement(self, channel_id: str, week_start: datetime = None):
        """Judge whether channel performance is due to industry or content factors"""
        if week_start is None:
            week_start, _ = self._get_week_boundaries(datetime.now(self.jst))
        
        with self.db.connect() as conn:
            # Get industry metrics
            industry = conn.execute("""
                SELECT delta_pct, views_delta_week
                FROM weekly_metrics
                WHERE scope = 'industry' AND entity_id = 'all' AND week_start = ?
            """, [week_start]).fetchone()
            
            if not industry:
                return {'judgement': 'no_data', 'message': 'No industry data available'}
            
            # Get channel metrics
            channel = conn.execute("""
                SELECT delta_pct, zscore, views_delta_week
                FROM weekly_metrics
                WHERE scope = 'channel' AND entity_id = ? AND week_start = ?
            """, [channel_id, week_start]).fetchone()
            
            if not channel:
                return {'judgement': 'no_data', 'message': 'No channel data available'}
        
        industry_delta = industry[0]
        channel_zscore = channel[1]
        
        # Apply judgement logic
        if industry_delta < -10 and channel_zscore > -1.0:
            return {
                'judgement': 'industry_factor',
                'message': '業界全体の要因による変動',
                'industry_delta': industry_delta,
                'channel_zscore': channel_zscore
            }
        elif -5 <= industry_delta <= 5 and channel_zscore < -1.0:
            return {
                'judgement': 'content_factor',
                'message': 'コンテンツ要因による変動',
                'industry_delta': industry_delta,
                'channel_zscore': channel_zscore
            }
        elif channel_zscore > 1.0:
            return {
                'judgement': 'winning',
                'message': '業界平均を上回るパフォーマンス',
                'industry_delta': industry_delta,
                'channel_zscore': channel_zscore
            }
        else:
            return {
                'judgement': 'mixed',
                'message': '複合的な要因による変動',
                'industry_delta': industry_delta,
                'channel_zscore': channel_zscore
            }