"""NLP processing modules."""

from .extract import EntityExtractor
from .score import ImpactScorer
from .llm import LLMAdapter
from .prompts import SUMMARY_PROMPT, ACTION_PROMPT

__all__ = [
    "EntityExtractor",
    "ImpactScorer", 
    "LLMAdapter",
    "SUMMARY_PROMPT",
    "ACTION_PROMPT",
]