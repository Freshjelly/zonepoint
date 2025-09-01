# path: bots/discord_report.py
import requests
import json
import logging
from datetime import datetime, timedelta
import pytz
import os
import sys
import yaml

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.schema import DatabaseManager
from etl.rollup import WeeklyRollup

logger = logging.getLogger(__name__)

class DiscordReporter:
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.getenv('DISCORD_WEBHOOK_URL')
        self.db = DatabaseManager()
        self.rollup = WeeklyRollup()
        self.jst = pytz.timezone('Asia/Tokyo')
        
        # Load config
        with open('config/app.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
    
    def send_weekly_digest(self, target_date: datetime = None):
        """Send weekly digest to Discord"""
        if not self.webhook_url:
            logger.warning("No Discord webhook URL configured. Skipping Discord report.")
            return {"status": "skipped", "message": "No webhook URL"}
        
        if target_date is None:
            target_date = datetime.now(self.jst)
        
        # Get week boundaries
        week_start, week_end = self.rollup._get_week_boundaries(target_date)
        
        logger.info(f"Preparing Discord report for week: {week_start} to {week_end}")
        
        try:
            # Get metrics data
            industry_metrics = self._get_industry_metrics(week_start)
            top_channels = self._get_top_channels(week_start, limit=5)
            top_videos = self._get_top_videos(week_start, limit=3)
            
            # Create embed
            embed = self._create_embed(
                week_start, week_end, 
                industry_metrics, top_channels, top_videos
            )
            
            # Send to Discord
            response = self._send_webhook(embed)
            
            if response.status_code == 204:
                logger.info("Discord report sent successfully")
                return {"status": "success", "message": "Report sent successfully"}
            else:
                logger.error(f"Discord webhook failed: {response.status_code} - {response.text}")
                return {"status": "error", "message": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error sending Discord report: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_industry_metrics(self, week_start):
        """Get industry-wide metrics"""
        with self.db.connect() as conn:
            industry_data = conn.execute("""
                SELECT 
                    views_delta_week,
                    delta_pct
                FROM weekly_metrics 
                WHERE scope = 'industry' AND entity_id = 'all' 
                AND week_start = ?
            """, [week_start]).fetchone()
            
            # Get previous week for comparison
            prev_week_start = week_start - timedelta(days=7)
            prev_industry = conn.execute("""
                SELECT 
                    views_delta_week,
                    delta_pct
                FROM weekly_metrics 
                WHERE scope = 'industry' AND entity_id = 'all' 
                AND week_start = ?
            """, [prev_week_start]).fetchone()
            
            # Get total video count
            video_count = conn.execute("""
                SELECT COUNT(*) FROM weekly_metrics 
                WHERE scope = 'video' AND week_start = ?
            """, [week_start]).fetchone()[0]
        
        if industry_data:
            return {
                'views_delta': industry_data[0],
                'delta_pct': industry_data[1],
                'prev_delta_pct': prev_industry[1] if prev_industry else 0,
                'video_count': video_count,
                'trend': 'up' if industry_data[1] > 0 else 'down'
            }
        else:
            return {
                'views_delta': 0,
                'delta_pct': 0,
                'prev_delta_pct': 0,
                'video_count': 0,
                'trend': 'flat'
            }
    
    def _get_top_channels(self, week_start, limit=5):
        """Get top performing channels"""
        with self.db.connect() as conn:
            import pandas as pd
            
            channels_data = pd.read_sql("""
                SELECT 
                    c.title,
                    wm.views_delta_week,
                    wm.delta_pct,
                    wm.zscore
                FROM weekly_metrics wm
                LEFT JOIN channels c ON wm.entity_id = c.channel_id
                WHERE wm.scope = 'channel' AND wm.week_start = ?
                ORDER BY wm.zscore DESC
                LIMIT ?
            """, conn, params=[week_start, limit])
        
        return [
            {
                'title': row['title'],
                'views_delta': row['views_delta_week'],
                'delta_pct': row['delta_pct'],
                'zscore': row['zscore'],
                'judgement': self._get_quick_judgement(row['zscore'], row['delta_pct'])
            }
            for _, row in channels_data.iterrows()
        ]
    
    def _get_top_videos(self, week_start, limit=3):
        """Get top performing videos"""
        with self.db.connect() as conn:
            import pandas as pd
            
            videos_data = pd.read_sql("""
                SELECT 
                    v.title,
                    c.title as channel_title,
                    wm.views_delta_week,
                    wm.delta_pct,
                    wm.entity_id as video_id
                FROM weekly_metrics wm
                LEFT JOIN videos v ON wm.entity_id = v.video_id
                LEFT JOIN channels c ON v.channel_id = c.channel_id
                WHERE wm.scope = 'video' AND wm.week_start = ?
                ORDER BY wm.views_delta_week DESC
                LIMIT ?
            """, conn, params=[week_start, limit])
        
        return [
            {
                'title': row['title'][:60] + ('...' if len(row['title']) > 60 else ''),
                'channel_title': row['channel_title'],
                'views_delta': row['views_delta_week'],
                'delta_pct': row['delta_pct'],
                'url': f"https://youtube.com/watch?v={row['video_id']}"
            }
            for _, row in videos_data.iterrows()
        ]
    
    def _get_quick_judgement(self, zscore, delta_pct):
        """Quick judgement based on Z-score"""
        if zscore > 1.0:
            return "🏆 勝ち"
        elif zscore < -1.0:
            return "📉 低迷"
        else:
            return "➖ 平均的"
    
    def _create_embed(self, week_start, week_end, industry, top_channels, top_videos):
        """Create Discord embed message"""
        # Determine overall trend emoji
        trend_emoji = {
            'up': '📈',
            'down': '📉',
            'flat': '➖'
        }.get(industry['trend'], '➖')
        
        # Color based on industry performance
        color = 0x28a745 if industry['delta_pct'] > 0 else 0xdc3545 if industry['delta_pct'] < -5 else 0xffc107
        
        embed = {
            "title": f"{trend_emoji} FX YouTube週次レポート",
            "description": f"**{week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')}の動向分析**",
            "color": color,
            "timestamp": datetime.now(self.jst).isoformat(),
            "fields": []
        }
        
        # Industry overview
        views_delta_formatted = self._format_large_number(industry['views_delta'])
        embed["fields"].append({
            "name": "🌐 業界全体",
            "value": f"**視聴増分**: {views_delta_formatted}\n**増減率**: {industry['delta_pct']:+.1f}%\n**分析動画数**: {industry['video_count']:,}本",
            "inline": True
        })
        
        # Previous week comparison
        week_trend = industry['delta_pct'] - industry['prev_delta_pct']
        trend_text = f"前週比 {week_trend:+.1f}%ポイント" if week_trend != 0 else "前週と同水準"
        embed["fields"].append({
            "name": "📊 前週対比",
            "value": trend_text,
            "inline": True
        })
        
        # Add empty field for line break
        embed["fields"].append({
            "name": "\u200b",
            "value": "\u200b",
            "inline": False
        })
        
        # Top channels
        if top_channels:
            channels_text = []
            for i, channel in enumerate(top_channels[:3], 1):
                channels_text.append(
                    f"{i}. **{channel['title'][:20]}**\n"
                    f"   {channel['delta_pct']:+.1f}% (Z: {channel['zscore']:.2f}) {channel['judgement']}"
                )
            
            embed["fields"].append({
                "name": "🏅 注目チャンネル TOP3",
                "value": "\n\n".join(channels_text),
                "inline": False
            })
        
        # Top videos
        if top_videos:
            videos_text = []
            for i, video in enumerate(top_videos, 1):
                views_formatted = self._format_large_number(video['views_delta'])
                videos_text.append(
                    f"{i}. [{video['title']}]({video['url']})\n"
                    f"   📺 {video['channel_title']} | 📈 +{views_formatted}"
                )
            
            embed["fields"].append({
                "name": "🎬 トップ動画",
                "value": "\n\n".join(videos_text),
                "inline": False
            })
        
        # Footer
        embed["footer"] = {
            "text": "FX YouTube Insights | Powered by Claude Code",
            "icon_url": "https://yt3.googleusercontent.com/584JjRp5QMuKbyduM_2k5RlXFqHJtQ0qLIPZpwbUjMJmgHp2aizXg8Inq-S7SrT7Bbt0Peimms0=s176-c-k-c0x00ffffff-no-rj"
        }
        
        return {"embeds": [embed]}
    
    def _format_large_number(self, number):
        """Format large numbers with appropriate units"""
        if abs(number) >= 100000000:  # 1億
            return f"{number/100000000:.1f}億回"
        elif abs(number) >= 10000:  # 1万
            return f"{number/10000:.1f}万回"
        else:
            return f"{number:,}回"
    
    def _send_webhook(self, embed_data):
        """Send message to Discord webhook"""
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            self.webhook_url,
            headers=headers,
            data=json.dumps(embed_data)
        )
        
        return response
    
    def test_webhook(self):
        """Send test message to Discord"""
        if not self.webhook_url:
            return {"status": "error", "message": "No webhook URL configured"}
        
        test_embed = {
            "embeds": [{
                "title": "🧪 テスト通知",
                "description": "FX YouTube Insights のテストメッセージです",
                "color": 0x007bff,
                "timestamp": datetime.now(self.jst).isoformat(),
                "footer": {
                    "text": "システム正常動作中"
                }
            }]
        }
        
        try:
            response = self._send_webhook(test_embed)
            
            if response.status_code == 204:
                return {"status": "success", "message": "Test message sent successfully"}
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

def main():
    """Main function for testing"""
    reporter = DiscordReporter()
    result = reporter.send_weekly_digest()
    print(f"Discord report result: {result}")

if __name__ == "__main__":
    main()