import os
import sys
import logging
from dotenv import load_dotenv

# Setup logging first
try:
    from .utils.logging_setup import setup_logging
except ImportError:
    # Fallback if utils doesn't exist yet
    logging.basicConfig(level=logging.INFO)
    setup_logging = None

from .ingest import pull_latest
from .classify import detect_currencies, classify_event
from .scoring import pairs_from_ccy, sentiment_score, impact_score
from .summarizer import make_summary
from .publish import post_webhook

logger = logging.getLogger(__name__)

def run(mode="alerts"):
    """Main execution function for alerts or digest mode"""
    try:
        logger.info(f"Starting run in {mode} mode")
        
        # Load config path from environment
        config_path = os.getenv("CONFIG_PATH", "config/rules.yml")
        logger.info(f"Using config: {config_path}")
        
        items = pull_latest(max_items=60)
        th = float(os.getenv("ALERT_IMPACT_THRESHOLD","3.0"))
        
        # Import dedup utility if available
        try:
            from .utils.dedup import SentCache
            cache = SentCache()
        except ImportError:
            logger.warning("Deduplication not available")
            cache = None
        
        digest = []
        for it in items:
            text = f"{it['title']} {it['summary']}"
            
            # Check for duplicates
            if cache and cache.seen(it.get('title', ''), it.get('url', '')):
                logger.info(f"Skipping duplicate: {it.get('title', '')[:50]}")
                continue
            
            ccys = detect_currencies(text)
            labels = classify_event(text)
            pairs = pairs_from_ccy(ccys)
            senti = sentiment_score(text)
            impact = impact_score(labels)
            msg = make_summary(it, ccys, pairs, labels, senti, impact)
            
            if mode=="alerts":
                if impact >= th:
                    logger.info(f"Sending alert for impact {impact}: {it.get('title', '')[:50]}")
                    post_webhook("【速報】\n" + msg)
            else:
                digest.append(msg)
        
        if mode=="digest" and digest:
            head = "【朝ダイジェスト】主要トピック"
            body = "\n---\n".join(digest[:int(os.getenv("DIGEST_MAX_ITEMS","10"))])
            logger.info(f"Sending digest with {len(digest)} items")
            post_webhook(head + "\n" + body)
        
        logger.info(f"Run completed successfully in {mode} mode")
        return 0
        
    except Exception as e:
        logger.error(f"Error in run: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    load_dotenv()
    
    # Setup structured logging if available
    if setup_logging:
        setup_logging(os.getenv("LOG_LEVEL", "INFO"))
    
    # Get mode from environment
    mode = os.getenv("MODE", "alerts")
    
    # Run and exit with appropriate code
    exit_code = run(mode)
    sys.exit(exit_code)