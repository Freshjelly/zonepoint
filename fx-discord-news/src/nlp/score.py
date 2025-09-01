"""Impact scoring module."""

from typing import Dict, List
from loguru import logger

class ImpactScorer:
    """Calculate impact scores for articles."""
    
    # Impact weights by category
    CATEGORY_WEIGHTS = {
        "policy_rate": 90,
        "official_comment": 70,
        "inflation": 65,
        "employment": 60,
        "gdp": 55,
        "pmi": 45,
        "retail": 40,
        "trade": 35,
        "other": 20
    }
    
    # Keywords that increase impact
    HIGH_IMPACT_KEYWORDS = [
        "surprise", "unexpected", "shock", "emergency",
        "crisis", "crash", "surge", "plunge", "soar",
        "record", "historic", "unprecedented",
        "サプライズ", "予想外", "急騰", "急落", "過去最",
        "breaking", "alert", "urgent"
    ]
    
    # Keywords that decrease impact
    LOW_IMPACT_KEYWORDS = [
        "expected", "forecast", "predicted", "inline",
        "unchanged", "steady", "stable", "minor",
        "予想通り", "変化なし", "安定", "小幅"
    ]
    
    def calculate_impact_score(
        self,
        text: str,
        category: str,
        currencies: List[str],
        central_banks: List[str]
    ) -> int:
        """
        Calculate impact score (0-100).
        """
        # Base score from category
        base_score = self.CATEGORY_WEIGHTS.get(category, 20)
        
        # Adjust for keyword presence
        text_lower = text.lower()
        
        # High impact keywords
        high_impact_count = sum(
            1 for keyword in self.HIGH_IMPACT_KEYWORDS
            if keyword in text_lower
        )
        
        # Low impact keywords
        low_impact_count = sum(
            1 for keyword in self.LOW_IMPACT_KEYWORDS
            if keyword in text_lower
        )
        
        # Adjust score
        score = base_score
        score += high_impact_count * 10
        score -= low_impact_count * 5
        
        # Boost for multiple currencies or central banks
        if len(currencies) >= 3:
            score += 10
        if len(central_banks) >= 2:
            score += 15
        
        # Clamp to 0-100
        score = max(0, min(100, score))
        
        logger.debug(f"Impact score: {score} (category: {category})")
        return score
    
    def calculate_pair_scores(
        self,
        text: str,
        pairs: List[str],
        currencies: List[str],
        central_banks: List[str]
    ) -> Dict[str, int]:
        """
        Calculate scores for each currency pair.
        """
        if not pairs:
            return {}
        
        scores = {}
        text_upper = text.upper()
        
        for pair in pairs:
            score = 0
            
            # Check direct pair mention
            if pair in text_upper:
                score += 50
            
            # Check individual currency mentions
            base = pair[:3]
            quote = pair[3:]
            
            base_count = text_upper.count(base)
            quote_count = text_upper.count(quote)
            
            score += min(base_count * 10, 30)
            score += min(quote_count * 10, 30)
            
            # Check central bank relevance
            for bank, bank_currencies in [
                ("FED", ["USD"]), ("FRB", ["USD"]), ("FOMC", ["USD"]),
                ("ECB", ["EUR"]), ("BOJ", ["JPY"]), ("BOE", ["GBP"]),
                ("RBA", ["AUD"]), ("BOC", ["CAD"]), ("SNB", ["CHF"]),
                ("RBNZ", ["NZD"])
            ]:
                if bank in central_banks:
                    if base in bank_currencies:
                        score += 20
                    if quote in bank_currencies:
                        score += 20
            
            # Clamp to 0-100
            scores[pair] = max(0, min(100, score))
        
        return scores