"""Tests for news filtering."""

import pytest
from datetime import datetime
from src.filters import NewsFilter
from src.filters.rules import Enriched
from src.collectors.rss import Article

class TestNewsFilter:
    """Test news filtering functionality."""
    
    @pytest.fixture
    def filter(self):
        """Create filter instance."""
        return NewsFilter(
            pairs_allowlist=["USDJPY", "EURUSD", "GBPUSD"],
            impact_threshold_breaking=60,
            impact_threshold_digest=40,
            pair_score_threshold=50
        )
    
    @pytest.fixture
    def sample_article(self):
        """Create sample article."""
        return Article(
            id="test123",
            source="Test Source",
            url="https://example.com/test",
            ts=datetime.now(),
            title="Test Article",
            body="Test body content",
            lang="en"
        )
    
    def test_breaking_news_high_impact(self, filter, sample_article):
        """Test breaking news detection with high impact."""
        enriched = Enriched(
            article=sample_article,
            currencies=["USD", "JPY"],
            central_banks=["FED"],
            category="policy_rate",
            impact_score=75,
            pair_scores={"USDJPY": 60, "EURUSD": 30}
        )
        
        assert filter.is_breaking_news(enriched) is True
    
    def test_breaking_news_low_impact(self, filter, sample_article):
        """Test breaking news rejection with low impact."""
        enriched = Enriched(
            article=sample_article,
            currencies=["USD", "JPY"],
            central_banks=["FED"],
            category="other",
            impact_score=50,  # Below breaking threshold
            pair_scores={"USDJPY": 60, "EURUSD": 30}
        )
        
        assert filter.is_breaking_news(enriched) is False
    
    def test_breaking_news_low_pair_score(self, filter, sample_article):
        """Test breaking news rejection with low pair score."""
        enriched = Enriched(
            article=sample_article,
            currencies=["USD", "JPY"],
            central_banks=["FED"],
            category="policy_rate",
            impact_score=75,
            pair_scores={"USDJPY": 40, "EURUSD": 30}  # Below pair threshold
        )
        
        assert filter.is_breaking_news(enriched) is False
    
    def test_digest_worthy(self, filter, sample_article):
        """Test digest worthiness."""
        enriched = Enriched(
            article=sample_article,
            currencies=["USD", "EUR"],
            central_banks=["ECB"],
            category="inflation",
            impact_score=45,  # Above digest threshold
            pair_scores={"EURUSD": 40}
        )
        
        assert filter.is_digest_worthy(enriched) is True
    
    def test_digest_not_worthy(self, filter, sample_article):
        """Test digest rejection."""
        enriched = Enriched(
            article=sample_article,
            currencies=["USD", "EUR"],
            central_banks=["ECB"],
            category="other",
            impact_score=35,  # Below digest threshold
            pair_scores={"EURUSD": 30}
        )
        
        assert filter.is_digest_worthy(enriched) is False
    
    def test_exclude_minor_currencies(self, filter, sample_article):
        """Test exclusion of minor currencies."""
        enriched = Enriched(
            article=sample_article,
            currencies=["TRY", "ZAR"],  # Minor currencies only
            central_banks=[],
            category="other",
            impact_score=50,
            pair_scores={}
        )
        
        assert filter.should_exclude(enriched) is True
    
    def test_exclude_low_impact(self, filter, sample_article):
        """Test exclusion of low impact articles."""
        enriched = Enriched(
            article=sample_article,
            currencies=["USD"],
            central_banks=[],
            category="other",
            impact_score=15,  # Very low impact
            pair_scores={"USDJPY": 20}
        )
        
        assert filter.should_exclude(enriched) is True
    
    def test_filter_for_breaking(self, filter, sample_article):
        """Test filtering multiple articles for breaking news."""
        articles = [
            Enriched(
                article=sample_article,
                currencies=["USD", "JPY"],
                central_banks=["FED"],
                category="policy_rate",
                impact_score=80,
                pair_scores={"USDJPY": 70}
            ),
            Enriched(
                article=sample_article,
                currencies=["EUR"],
                central_banks=["ECB"],
                category="inflation",
                impact_score=45,
                pair_scores={"EURUSD": 40}
            ),
            Enriched(
                article=sample_article,
                currencies=["TRY"],
                central_banks=[],
                category="other",
                impact_score=30,
                pair_scores={}
            )
        ]
        
        breaking = filter.filter_for_breaking(articles)
        assert len(breaking) == 1
        assert breaking[0].impact_score == 80
    
    def test_filter_for_digest_with_limit(self, filter, sample_article):
        """Test filtering for digest with limit."""
        articles = []
        for i in range(15):
            articles.append(Enriched(
                article=sample_article,
                currencies=["USD"],
                central_banks=[],
                category="inflation",
                impact_score=45 + i,  # Varying impact scores
                pair_scores={"USDJPY": 50}
            ))
        
        digest = filter.filter_for_digest(articles, limit=10)
        assert len(digest) == 10
        # Should be sorted by impact score (highest first)
        assert digest[0].impact_score > digest[-1].impact_score
    
    def test_non_allowed_pair_rejection(self, filter, sample_article):
        """Test rejection of non-allowed currency pairs."""
        enriched = Enriched(
            article=sample_article,
            currencies=["NZD", "CAD"],
            central_banks=[],
            category="policy_rate",
            impact_score=70,
            pair_scores={"NZDCAD": 80}  # Not in allowlist
        )
        
        assert filter.is_breaking_news(enriched) is False
        assert filter.is_digest_worthy(enriched) is False