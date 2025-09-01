"""Filtering rules module."""

from typing import Dict, List, Optional
from pydantic import BaseModel
from loguru import logger

class Enriched(BaseModel):
    """Enriched article model."""
    article: "Article"  # Forward reference
    currencies: List[str]
    central_banks: List[str]
    category: str
    impact_score: int
    pair_scores: Dict[str, int]

class NewsFilter:
    """Filter news based on rules."""
    
    def __init__(
        self,
        pairs_allowlist: List[str],
        impact_threshold_breaking: int = 60,
        impact_threshold_digest: int = 40,
        pair_score_threshold: int = 50
    ):
        self.pairs_allowlist = set(pairs_allowlist)
        self.impact_threshold_breaking = impact_threshold_breaking
        self.impact_threshold_digest = impact_threshold_digest
        self.pair_score_threshold = pair_score_threshold
        
        # Minor currencies to exclude
        self.excluded_currencies = {
            "TRY", "ZAR", "BRL", "RUB", "INR", "KRW", "MXN"
        }
    
    def is_breaking_news(self, enriched: Enriched) -> bool:
        """Check if article qualifies as breaking news."""
        # Impact score check
        if enriched.impact_score < self.impact_threshold_breaking:
            return False
        
        # Check if any allowed pair has high score
        for pair, score in enriched.pair_scores.items():
            if pair in self.pairs_allowlist and score >= self.pair_score_threshold:
                logger.info(
                    f"Breaking news: {enriched.article.title[:50]}... "
                    f"(impact: {enriched.impact_score}, {pair}: {score})"
                )
                return True
        
        return False
    
    def is_digest_worthy(self, enriched: Enriched) -> bool:
        """Check if article qualifies for digest."""
        # Impact score check
        if enriched.impact_score < self.impact_threshold_digest:
            return False
        
        # Check if it involves allowed pairs
        has_allowed_pair = any(
            pair in self.pairs_allowlist
            for pair in enriched.pair_scores.keys()
        )
        
        if has_allowed_pair:
            logger.debug(f"Digest worthy: {enriched.article.title[:50]}...")
            return True
        
        return False
    
    def should_exclude(self, enriched: Enriched) -> bool:
        """Check if article should be excluded."""
        # Exclude if only minor currencies
        if enriched.currencies:
            major_currencies = set(enriched.currencies) - self.excluded_currencies
            if not major_currencies:
                logger.debug(f"Excluded (minor currencies only): {enriched.article.title[:50]}...")
                return True
        
        # Exclude if impact too low
        if enriched.impact_score < 20:
            logger.debug(f"Excluded (low impact): {enriched.article.title[:50]}...")
            return True
        
        return False
    
    def filter_for_breaking(self, articles: List[Enriched]) -> List[Enriched]:
        """Filter articles for breaking news."""
        breaking = []
        
        for article in articles:
            if self.should_exclude(article):
                continue
            
            if self.is_breaking_news(article):
                breaking.append(article)
        
        return breaking
    
    def filter_for_digest(
        self,
        articles: List[Enriched],
        limit: int = 10
    ) -> List[Enriched]:
        """Filter articles for digest."""
        digest = []
        
        for article in articles:
            if self.should_exclude(article):
                continue
            
            if self.is_digest_worthy(article):
                digest.append(article)
        
        # Sort by impact score and limit
        digest.sort(key=lambda x: x.impact_score, reverse=True)
        
        return digest[:limit]