#!/usr/bin/env python3
import sys
import os
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.rollup import WeeklyRollup

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/rollup.log', mode='a', encoding='utf-8')
        ]
    )

def main():
    """Run weekly rollup calculation"""
    # Load environment variables
    load_dotenv()
    
    # Setup logging
    os.makedirs('logs', exist_ok=True)
    setup_logging()
    logger = logging.getLogger(__name__)
    
    jst = pytz.timezone('Asia/Tokyo')
    start_time = datetime.now(jst)
    
    logger.info(f"Starting weekly rollup at {start_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
    
    try:
        # Initialize rollup calculator
        rollup = WeeklyRollup()
        
        # Calculate weekly metrics
        results = rollup.calculate_weekly_metrics()
        
        end_time = datetime.now(jst)
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Weekly rollup completed in {duration:.1f} seconds")
        logger.info(f"Week analyzed: {results['week_start']} to {results['week_end']}")
        
        # Print summary
        print("=" * 50)
        print("WEEKLY ROLLUP SUMMARY")
        print("=" * 50)
        print(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
        print(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
        print(f"Duration: {duration:.1f} seconds")
        print(f"Week Period: {results['week_start']} to {results['week_end']}")
        
        # Industry metrics
        industry = results['industry']
        print("\nINDUSTRY METRICS:")
        print(f"  Total View Delta: {industry['views_delta_this_week']:,}")
        print(f"  Weekly Change: {industry['delta_pct']:+.2f}%")
        print(f"  Videos Analyzed: {industry['video_count']}")
        print(f"  Channels Analyzed: {industry['channel_count']}")
        
        # Channel metrics
        channels = results['channels']
        print(f"\nCHANNEL METRICS:")
        print(f"  Channels Processed: {len(channels)}")
        
        if not channels.empty:
            # Top performers
            top_channels = channels.nlargest(3, 'zscore')
            print("\n  Top Performers (by Z-score):")
            for i, (_, row) in enumerate(top_channels.iterrows(), 1):
                print(f"    {i}. {row['title'][:30]}: {row['delta_pct']:+.1f}% (Z: {row['zscore']:.2f})")
            
            # Bottom performers
            bottom_channels = channels.nsmallest(3, 'zscore')
            print("\n  Bottom Performers (by Z-score):")
            for i, (_, row) in enumerate(bottom_channels.iterrows(), 1):
                print(f"    {i}. {row['title'][:30]}: {row['delta_pct']:+.1f}% (Z: {row['zscore']:.2f})")
        
        # Top videos
        top_videos = results['top_videos'][:5]
        print(f"\nTOP VIDEOS:")
        for i, video in enumerate(top_videos, 1):
            print(f"  {i}. {video['title'][:50]}")
            print(f"     Views: +{video['views_delta']:,} ({video['delta_pct']:+.1f}%)")
        
        print("=" * 50)
        
        return 0
        
    except Exception as e:
        logger.error(f"Weekly rollup failed: {e}")
        print(f"ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit(main())