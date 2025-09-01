"""Tests for entity extraction."""

import pytest
from src.nlp.extract import EntityExtractor

class TestEntityExtractor:
    """Test entity extraction functionality."""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        return EntityExtractor()
    
    def test_extract_currencies(self, extractor):
        """Test currency extraction."""
        text = "The USD/JPY pair rose after the Fed decision, while EUR declined."
        currencies = extractor.extract_currencies(text)
        
        assert "USD" in currencies
        assert "JPY" in currencies
        assert "EUR" in currencies
        assert len(currencies) == 3
    
    def test_extract_central_banks(self, extractor):
        """Test central bank extraction."""
        text = "The FED raised rates while the ECB kept them unchanged. BOJ intervened."
        banks = extractor.extract_central_banks(text)
        
        assert "FED" in banks
        assert "ECB" in banks
        assert "BOJ" in banks
    
    def test_categorize_policy_rate(self, extractor):
        """Test policy rate categorization."""
        text = "Fed announces interest rate decision with hawkish tone"
        category = extractor.categorize_event(text)
        assert category == "policy_rate"
    
    def test_categorize_inflation(self, extractor):
        """Test inflation categorization."""
        text = "US CPI comes in higher than expected, inflation concerns rise"
        category = extractor.categorize_event(text)
        assert category == "inflation"
    
    def test_categorize_employment(self, extractor):
        """Test employment categorization."""
        text = "Non-farm payrolls surge, unemployment rate drops to new low"
        category = extractor.categorize_event(text)
        assert category == "employment"
    
    def test_extract_currency_pairs(self, extractor):
        """Test currency pair generation."""
        currencies = ["USD", "JPY", "EUR"]
        pairs = extractor.extract_currency_pairs(currencies)
        
        assert "USDJPY" in pairs
        assert "EURUSD" in pairs
        assert "EURJPY" in pairs
    
    def test_japanese_text_extraction(self, extractor):
        """Test extraction from Japanese text."""
        text = "日銀が金利据え置きを決定、ドル円は150円を突破"
        
        currencies = extractor.extract_currencies(text)
        assert "JPY" in currencies  # From 日銀
        
        banks = extractor.extract_central_banks(text)
        assert "BOJ" in banks or "日銀" in banks
    
    def test_empty_text(self, extractor):
        """Test handling of empty text."""
        assert extractor.extract_currencies("") == []
        assert extractor.extract_central_banks("") == []
        assert extractor.categorize_event("") == "other"
        assert extractor.extract_currency_pairs([]) == []
    
    def test_multiple_category_keywords(self, extractor):
        """Test text with multiple category keywords."""
        text = "Fed rate decision impacts inflation expectations and employment outlook"
        category = extractor.categorize_event(text)
        # Should return the category with highest score
        assert category in ["policy_rate", "inflation", "employment"]