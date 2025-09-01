"""Language detection utilities."""

from typing import Optional, Tuple
from langdetect import detect_langs, LangDetectException
from loguru import logger

def detect_language(text: str) -> Tuple[str, float]:
    """
    Detect language of text.
    Returns (language_code, confidence).
    """
    if not text or len(text) < 20:
        return ("unknown", 0.0)
    
    try:
        detections = detect_langs(text)
        if detections:
            best = detections[0]
            return (best.lang, best.prob)
    except LangDetectException as e:
        logger.debug(f"Language detection failed: {e}")
    
    return ("unknown", 0.0)

def is_japanese(text: str, threshold: float = 0.5) -> bool:
    """Check if text is Japanese."""
    lang, confidence = detect_language(text)
    return lang == "ja" and confidence >= threshold

def should_translate(text: str, target_lang: str = "ja") -> bool:
    """Check if text should be translated."""
    lang, confidence = detect_language(text)
    
    # Don't translate if already in target language
    if lang == target_lang:
        return False
    
    # Don't translate if detection confidence is too low
    if confidence < 0.7:
        return False
    
    return True