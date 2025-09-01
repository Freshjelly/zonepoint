"""Text processing utilities."""

import re
import unicodedata
from typing import List, Optional

def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Normalize unicode
    text = unicodedata.normalize('NFKC', text)
    
    # Remove multiple spaces/newlines
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    
    # Remove zero-width characters
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    
    return text.strip()

def normalize_japanese(text: str) -> str:
    """Normalize Japanese punctuation."""
    if not text:
        return ""
    
    replacements = {
        '､': '、',
        '｡': '。',
        '･': '・',
        '｢': '「',
        '｣': '」',
        '！': '!',
        '？': '?',
        '（': '(',
        '）': ')',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Ensure proper spacing around punctuation
    text = re.sub(r'([。！？])\s*', r'\1 ', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def extract_sentences(text: str, limit: int = 3) -> List[str]:
    """Extract first N sentences from text."""
    if not text:
        return []
    
    # Split by sentence endings
    sentences = re.split(r'[.!?。！？]\s+', text)
    
    # Filter empty sentences and limit
    sentences = [s.strip() for s in sentences if s.strip()]
    
    return sentences[:limit]

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length."""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def count_japanese_chars(text: str) -> int:
    """Count Japanese characters in text."""
    japanese_chars = re.findall(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', text)
    return len(japanese_chars)

def is_mostly_japanese(text: str, threshold: float = 0.3) -> bool:
    """Check if text is mostly Japanese."""
    if not text:
        return False
    
    japanese_count = count_japanese_chars(text)
    total_chars = len(re.sub(r'\s', '', text))
    
    if total_chars == 0:
        return False
    
    return (japanese_count / total_chars) >= threshold