#!/usr/bin/env python3
import sys
import os
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots.discord_report import DiscordReporter

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/discord.log', mode='a', encoding='utf-8')
        ]
    )

def main():
    """Post weekly digest to Discord"""
    # Load environment variables
    load_dotenv()
    
    # Setup logging
    os.makedirs('logs', exist_ok=True)
    setup_logging()
    logger = logging.getLogger(__name__)
    
    jst = pytz.timezone('Asia/Tokyo')
    start_time = datetime.now(jst)
    
    logger.info(f"Starting Discord weekly digest at {start_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
    
    try:
        # Initialize Discord reporter
        reporter = DiscordReporter()
        
        # Check if webhook URL is configured
        if not reporter.webhook_url:
            print("WARNING: No Discord webhook URL configured.")
            print("Set DISCORD_WEBHOOK_URL in .env file to enable Discord notifications.")
            return 0
        
        # Send weekly digest
        result = reporter.send_weekly_digest()
        
        end_time = datetime.now(jst)
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Discord report completed in {duration:.1f} seconds")
        logger.info(f"Result: {result}")
        
        # Print summary
        print("=" * 50)
        print("DISCORD WEEKLY DIGEST SUMMARY")
        print("=" * 50)
        print(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
        print(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
        print(f"Duration: {duration:.1f} seconds")
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
        print("=" * 50)
        
        if result['status'] == 'success':
            return 0
        else:
            return 1
        
    except Exception as e:
        logger.error(f"Discord report failed: {e}")
        print(f"ERROR: {e}")
        return 1

def test_webhook():
    """Test Discord webhook connection"""
    load_dotenv()
    
    reporter = DiscordReporter()
    
    if not reporter.webhook_url:
        print("ERROR: No Discord webhook URL configured.")
        return 1
    
    print("Testing Discord webhook...")
    result = reporter.test_webhook()
    
    print(f"Test result: {result['status']}")
    print(f"Message: {result['message']}")
    
    return 0 if result['status'] == 'success' else 1

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Discord Weekly Digest')
    parser.add_argument('--test', action='store_true', help='Test webhook connection')
    args = parser.parse_args()
    
    if args.test:
        exit(test_webhook())
    else:
        exit(main())