"""Tests for impact scoring."""

import pytest
from src.nlp.score import ImpactScorer

class TestImpactScorer:
    """Test impact scoring functionality."""
    
    @pytest.fixture
    def scorer(self):
        """Create scorer instance."""
        return ImpactScorer()
    
    def test_high_impact_policy_rate(self, scorer):
        """Test high impact score for policy rate decision."""
        text = "Fed surprises with emergency rate hike"
        score = scorer.calculate_impact_score(
            text=text,
            category="policy_rate",
            currencies=["USD"],
            central_banks=["FED"]
        )
        assert score >= 80
    
    def test_medium_impact_inflation(self, scorer):
        """Test medium impact score for inflation data."""
        text = "CPI data comes in as expected"
        score = scorer.calculate_impact_score(
            text=text,
            category="inflation",
            currencies=["USD"],
            central_banks=[]
        )
        assert 40 <= score <= 70
    
    def test_low_impact_other(self, scorer):
        """Test low impact score for other category."""
        text = "Market remains stable with minor fluctuations"
        score = scorer.calculate_impact_score(
            text=text,
            category="other",
            currencies=["USD"],
            central_banks=[]
        )
        assert score <= 40
    
    def test_impact_boost_multiple_currencies(self, scorer):
        """Test impact boost for multiple currencies."""
        text = "Global market shock"
        score_single = scorer.calculate_impact_score(
            text=text,
            category="other",
            currencies=["USD"],
            central_banks=[]
        )
        score_multiple = scorer.calculate_impact_score(
            text=text,
            category="other",
            currencies=["USD", "EUR", "JPY", "GBP"],
            central_banks=[]
        )
        assert score_multiple > score_single
    
    def test_impact_boost_central_banks(self, scorer):
        """Test impact boost for multiple central banks."""
        text = "Central bank coordination"
        score_single = scorer.calculate_impact_score(
            text=text,
            category="official_comment",
            currencies=["USD"],
            central_banks=["FED"]
        )
        score_multiple = scorer.calculate_impact_score(
            text=text,
            category="official_comment",
            currencies=["USD", "EUR"],
            central_banks=["FED", "ECB"]
        )
        assert score_multiple > score_single
    
    def test_high_impact_keywords(self, scorer):
        """Test high impact keywords boost score."""
        text_normal = "Fed announces rate decision"
        text_high = "Fed surprises with unprecedented emergency rate decision"
        
        score_normal = scorer.calculate_impact_score(
            text=text_normal,
            category="policy_rate",
            currencies=["USD"],
            central_banks=["FED"]
        )
        score_high = scorer.calculate_impact_score(
            text=text_high,
            category="policy_rate",
            currencies=["USD"],
            central_banks=["FED"]
        )
        assert score_high > score_normal
    
    def test_low_impact_keywords(self, scorer):
        """Test low impact keywords reduce score."""
        text_normal = "Fed announces rate decision"
        text_low = "Fed announces expected unchanged rate decision as predicted"
        
        score_normal = scorer.calculate_impact_score(
            text=text_normal,
            category="policy_rate",
            currencies=["USD"],
            central_banks=["FED"]
        )
        score_low = scorer.calculate_impact_score(
            text=text_low,
            category="policy_rate",
            currencies=["USD"],
            central_banks=["FED"]
        )
        assert score_low < score_normal
    
    def test_pair_scores(self, scorer):
        """Test currency pair scoring."""
        text = "USDJPY surges as USD strengthens against JPY"
        scores = scorer.calculate_pair_scores(
            text=text,
            pairs=["USDJPY", "EURUSD", "GBPUSD"],
            currencies=["USD", "JPY"],
            central_banks=[]
        )
        
        assert "USDJPY" in scores
        assert scores["USDJPY"] > scores.get("EURUSD", 0)
        assert all(0 <= score <= 100 for score in scores.values())
    
    def test_score_reproducibility(self, scorer):
        """Test that same input produces same score."""
        text = "Fed raises rates by 25 basis points"
        kwargs = {
            "text": text,
            "category": "policy_rate",
            "currencies": ["USD"],
            "central_banks": ["FED"]
        }
        
        score1 = scorer.calculate_impact_score(**kwargs)
        score2 = scorer.calculate_impact_score(**kwargs)
        assert score1 == score2
    
    def test_score_clamping(self, scorer):
        """Test that scores are clamped to 0-100 range."""
        # Test maximum score
        text = "BREAKING: Unprecedented emergency crisis surge shock in markets"
        score = scorer.calculate_impact_score(
            text=text,
            category="policy_rate",
            currencies=["USD", "EUR", "JPY", "GBP"],
            central_banks=["FED", "ECB", "BOJ", "BOE"]
        )
        assert score <= 100
        
        # Test minimum score
        text = "Expected unchanged stable steady minor adjustments"
        score = scorer.calculate_impact_score(
            text=text,
            category="other",
            currencies=[],
            central_banks=[]
        )
        assert score >= 0