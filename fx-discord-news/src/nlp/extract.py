"""Entity extraction module."""

import re
from typing import Dict, List, Set
from loguru import logger

class EntityExtractor:
    """Extract entities from text."""
    
    # Currency codes
    CURRENCIES = {
        "USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "NZD",
        "CNY", "HKD", "SGD", "SEK", "NOK", "MXN", "ZAR", "TRY",
        "BRL", "RUB", "INR", "KRW"
    }
    
    # Central banks
    CENTRAL_BANKS = {
        "FED": ["USD"],
        "FRB": ["USD"],
        "FOMC": ["USD"],
        "ECB": ["EUR"],
        "BOJ": ["JPY"],
        "日銀": ["JPY"],
        "BOE": ["GBP"],
        "RBA": ["AUD"],
        "BOC": ["CAD"],
        "SNB": ["CHF"],
        "RBNZ": ["NZD"],
        "PBOC": ["CNY"],
    }
    
    # Event categories with keywords
    EVENT_CATEGORIES = {
        "policy_rate": [
            "rate decision", "policy rate", "interest rate",
            "金利決定", "政策金利", "利上げ", "利下げ",
            "hawkish", "dovish", "tightening", "easing"
        ],
        "official_comment": [
            "fed chair", "ecb president", "governor",
            "speech", "testimony", "press conference",
            "議長", "総裁", "発言", "会見"
        ],
        "inflation": [
            "cpi", "pce", "inflation", "consumer price",
            "消費者物価", "インフレ", "物価"
        ],
        "employment": [
            "nfp", "non-farm", "unemployment", "jobless",
            "雇用統計", "失業率", "新規雇用"
        ],
        "gdp": [
            "gdp", "gross domestic", "growth",
            "GDP", "国内総生産", "成長率"
        ],
        "pmi": [
            "pmi", "purchasing managers", "manufacturing",
            "PMI", "製造業", "サービス業"
        ],
        "retail": [
            "retail sales", "consumer spending",
            "小売売上", "消費支出"
        ],
        "trade": [
            "trade balance", "current account", "exports",
            "貿易収支", "経常収支", "輸出"
        ]
    }
    
    def extract_currencies(self, text: str) -> List[str]:
        """Extract currency codes from text."""
        if not text:
            return []
        
        currencies = set()
        text_upper = text.upper()
        
        # Direct currency code matches
        for currency in self.CURRENCIES:
            if currency in text_upper:
                # Check it's not part of another word
                pattern = r'\b' + currency + r'\b'
                if re.search(pattern, text_upper):
                    currencies.add(currency)
        
        # Check central banks
        for bank, bank_currencies in self.CENTRAL_BANKS.items():
            if bank in text_upper:
                currencies.update(bank_currencies)
        
        return sorted(list(currencies))
    
    def extract_central_banks(self, text: str) -> List[str]:
        """Extract central bank mentions from text."""
        if not text:
            return []
        
        banks = set()
        text_upper = text.upper()
        
        for bank in self.CENTRAL_BANKS.keys():
            if bank in text_upper:
                banks.add(bank)
        
        return sorted(list(banks))
    
    def categorize_event(self, text: str) -> str:
        """Categorize event type from text."""
        if not text:
            return "other"
        
        text_lower = text.lower()
        scores = {}
        
        for category, keywords in self.EVENT_CATEGORIES.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[category] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return "other"
    
    def extract_currency_pairs(self, currencies: List[str]) -> List[str]:
        """Generate currency pairs from extracted currencies."""
        if not currencies:
            return []
        
        # Major pairs (with USD)
        major_bases = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF"]
        pairs = []
        
        for currency in currencies:
            if currency == "USD":
                # USD as quote currency
                for base in major_bases:
                    if base != "USD" and base in currencies:
                        pairs.append(f"{base}USD")
            elif currency in major_bases:
                # USD as base currency
                pairs.append(f"USD{currency}")
            
            # JPY crosses
            if currency == "JPY":
                for base in ["EUR", "GBP", "AUD", "NZD", "CAD", "CHF"]:
                    if base in currencies:
                        pairs.append(f"{base}JPY")
        
        # Remove duplicates and sort
        return sorted(list(set(pairs)))