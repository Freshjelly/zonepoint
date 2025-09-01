# src/utils/dedup.py
from pathlib import Path
import hashlib
import logging

logger = logging.getLogger(__name__)

class SentCache:
    """Cache for tracking sent items to prevent duplicates"""
    
    def __init__(self, path="data/sent_hashes.txt", keep=300):
        self.path = Path(path)
        self.keep = keep
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        """Load existing hashes from file"""
        self.items = []
        if self.path.exists():
            try:
                self.items = [line.strip() for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
                logger.info(f"Loaded {len(self.items)} cached hashes")
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
                self.items = []

    def _save(self):
        """Save hashes to file, keeping only the most recent"""
        try:
            to_save = self.items[-self.keep:]
            self.path.write_text("\n".join(to_save) + "\n", encoding="utf-8")
            logger.debug(f"Saved {len(to_save)} hashes to cache")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def seen(self, title: str, url: str) -> bool:
        """Check if an item has been seen before"""
        if not title and not url:
            return False
            
        key = hashlib.sha256((title + url).encode("utf-8")).hexdigest()
        
        if key in self.items:
            logger.debug(f"Found duplicate: {title[:50]}")
            return True
        
        self.items.append(key)
        self._save()
        return False