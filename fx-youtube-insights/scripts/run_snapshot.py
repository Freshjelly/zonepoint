#!/usr/bin/env python3
import sys
import os
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.snapshot import SnapshotCollector

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/snapshot.log', mode='a', encoding='utf-8')
        ]
    )

def main():
    """Run snapshot collection"""
    # Load environment variables
    load_dotenv()
    
    # Setup logging
    os.makedirs('logs', exist_ok=True)
    setup_logging()
    logger = logging.getLogger(__name__)
    
    jst = pytz.timezone('Asia/Tokyo')
    start_time = datetime.now(jst)
    
    logger.info(f"Starting snapshot collection at {start_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
    
    try:
        # Initialize collector
        collector = SnapshotCollector()
        
        # Run snapshot
        results = collector.run_snapshot()
        
        end_time = datetime.now(jst)
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Snapshot collection completed in {duration:.1f} seconds")
        logger.info(f"Results: {results}")
        
        # Print summary
        print("=" * 50)
        print("SNAPSHOT COLLECTION SUMMARY")
        print("=" * 50)
        print(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
        print(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
        print(f"Duration: {duration:.1f} seconds")
        print(f"Status: {results.get('status', 'completed')}")
        
        if 'channels_processed' in results:
            print(f"Channels Processed: {results['channels_processed']}")
        if 'videos_processed' in results:
            print(f"Videos Processed: {results['videos_processed']}")
        if 'new_videos_found' in results:
            print(f"New Videos Found: {results['new_videos_found']}")
        
        if results.get('errors'):
            print(f"Errors: {len(results['errors'])}")
            for error in results['errors']:
                print(f"  - {error}")
        
        print("=" * 50)
        
        return 0
        
    except Exception as e:
        logger.error(f"Snapshot collection failed: {e}")
        print(f"ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit(main())