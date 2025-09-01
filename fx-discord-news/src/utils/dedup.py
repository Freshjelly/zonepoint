"""Duplicate detection utilities."""

import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
from rapidfuzz import fuzz
from loguru import logger

class DuplicateChecker:
    """Check for duplicate articles."""
    
    def __init__(self, ttl_hours: int = 24, similarity_threshold: float = 85.0):
        self.ttl_hours = ttl_hours
        self.similarity_threshold = similarity_threshold
        self._cache: Dict[str, datetime] = {}
        self._title_cache: Dict[str, str] = {}
    
    def _clean_cache(self):
        """Remove expired entries from cache."""
        now = datetime.now()
        expired = []
        
        for key, timestamp in self._cache.items():
            if now - timestamp > timedelta(hours=self.ttl_hours):
                expired.append(key)
        
        for key in expired:
            del self._cache[key]
            if key in self._title_cache:
                del self._title_cache[key]
    
    def _get_url_hash(self, url: str) -> str:
        """Get hash of URL."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def is_duplicate_url(self, url: str) -> bool:
        """Check if URL is duplicate."""
        self._clean_cache()
        url_hash = self._get_url_hash(url)
        
        if url_hash in self._cache:
            logger.debug(f"Duplicate URL found: {url}")
            return True
        
        return False
    
    def is_similar_title(self, title: str) -> bool:
        """Check if title is similar to cached titles."""
        if not title:
            return False
        
        for cached_title in self._title_cache.values():
            similarity = fuzz.ratio(title.lower(), cached_title.lower())
            if similarity >= self.similarity_threshold:
                logger.debug(f"Similar title found: {title} (similarity: {similarity}%)")
                return True
        
        return False
    
    def add(self, url: str, title: str):
        """Add URL and title to cache."""
        url_hash = self._get_url_hash(url)
        self._cache[url_hash] = datetime.now()
        self._title_cache[url_hash] = title
        logger.debug(f"Added to cache: {url[:50]}...")
    
    def is_duplicate(self, url: str, title: str) -> bool:
        """Check if article is duplicate (URL or title)."""
        return self.is_duplicate_url(url) or self.is_similar_title(title)