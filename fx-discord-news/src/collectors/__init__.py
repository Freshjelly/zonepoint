"""Data collection modules."""

from .rss import RSSCollector
from .economic_calendar import EconomicCalendarCollector

__all__ = ["RSSCollector", "EconomicCalendarCollector"]