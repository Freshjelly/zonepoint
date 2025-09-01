"""Scheduler jobs module."""

import pytz
from datetime import datetime, timedelta
from typing import List, Optional
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from src.config import config, settings
from src.collectors import RSSCollector
from src.nlp import EntityExtractor, ImpactScorer, LLMAdapter
from src.nlp.prompts import SUMMARY_PROMPT, ACTION_PROMPT
from src.filters import NewsFilter
from src.filters.rules import Enriched
from src.delivery import DiscordDelivery
from src.utils import DuplicateChecker, clean_text, normalize_japanese, detect_language

class NewsScheduler:
    """News collection and delivery scheduler."""
    
    def __init__(self):
        self.scheduler = BlockingScheduler(timezone=pytz.timezone(settings.tz))
        self.duplicate_checker = DuplicateChecker(ttl_hours=config.cache.ttl_hours)
        
        # Initialize components
        self.collector = RSSCollector(feeds=config.feeds)
        self.extractor = EntityExtractor()
        self.scorer = ImpactScorer()
        self.llm = LLMAdapter(
            provider=config.llm.provider,
            model=config.llm.model.get(config.llm.provider)
        )
        self.filter = NewsFilter(
            pairs_allowlist=config.pairs_allowlist,
            impact_threshold_breaking=config.impact_thresholds.breaking,
            impact_threshold_digest=config.impact_thresholds.digest,
            pair_score_threshold=config.pair_score_threshold
        )
        self.delivery = DiscordDelivery(
            webhook_beginner=settings.discord_webhook_beginner,
            webhook_pro=settings.discord_webhook_pro,
            disclaimer=config.disclaimer
        )
    
    def _enrich_article(self, article) -> Optional[Enriched]:
        """Enrich article with NLP analysis."""
        try:
            # Clean text
            text = f"{article.title} {article.body}"
            text = clean_text(text)
            
            # Detect language
            lang, _ = detect_language(text)
            article.lang = lang
            
            # Extract entities
            currencies = self.extractor.extract_currencies(text)
            central_banks = self.extractor.extract_central_banks(text)
            category = self.extractor.categorize_event(text)
            pairs = self.extractor.extract_currency_pairs(currencies)
            
            # Calculate scores
            impact_score = self.scorer.calculate_impact_score(
                text, category, currencies, central_banks
            )
            pair_scores = self.scorer.calculate_pair_scores(
                text, pairs, currencies, central_banks
            )
            
            return Enriched(
                article=article,
                currencies=currencies,
                central_banks=central_banks,
                category=category,
                impact_score=impact_score,
                pair_scores=pair_scores
            )
            
        except Exception as e:
            logger.error(f"Failed to enrich article: {e}")
            return None
    
    def _generate_summary_and_guide(self, enriched: Enriched) -> tuple[str, str]:
        """Generate summary and action guide."""
        try:
            # Generate summary
            summary = self.llm.summarize(
                SUMMARY_PROMPT,
                title=enriched.article.title,
                body=enriched.article.body[:1000],
                source=enriched.article.source,
                currencies=", ".join(enriched.currencies),
                category=enriched.category,
                impact_score=enriched.impact_score
            )
            summary = normalize_japanese(summary)
            
            # Generate action guide
            action_guide = self.llm.generate_action_guide(
                ACTION_PROMPT,
                summary=summary,
                currencies=", ".join(enriched.currencies),
                category=enriched.category,
                impact_score=enriched.impact_score
            )
            action_guide = normalize_japanese(action_guide)
            
            return summary, action_guide
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            # Fallback
            summary = f"要約生成に失敗しました。元記事をご確認ください: {enriched.article.title}"
            action_guide = "詳細は元記事をご確認ください。"
            return summary, action_guide
    
    def check_breaking_news(self):
        """Check for breaking news and send immediately."""
        logger.info("Checking for breaking news...")
        
        try:
            # Collect recent articles
            articles = self.collector.collect(limit_per_feed=5)
            
            # Process each article
            for article in articles:
                # Check duplicate
                if self.duplicate_checker.is_duplicate(article.url, article.title):
                    continue
                
                # Enrich article
                enriched = self._enrich_article(article)
                if not enriched:
                    continue
                
                # Check if breaking news
                if self.filter.is_breaking_news(enriched):
                    logger.info(f"Breaking news detected: {article.title[:50]}...")
                    
                    # Generate summary and guide
                    summary, action_guide = self._generate_summary_and_guide(enriched)
                    
                    # Determine confidence
                    if enriched.impact_score >= 80:
                        confidence = "高"
                    elif enriched.impact_score >= 60:
                        confidence = "中"
                    else:
                        confidence = "低"
                    
                    # Send to Discord
                    self.delivery.send_news(
                        title=article.title,
                        summary=summary,
                        action_guide=action_guide,
                        source=article.source,
                        url=str(article.url),
                        currencies=enriched.currencies,
                        confidence=confidence,
                        original_excerpt=article.body[:200]
                    )
                    
                    # Mark as sent
                    self.duplicate_checker.add(article.url, article.title)
        
        except Exception as e:
            logger.error(f"Breaking news check failed: {e}")
    
    def send_morning_digest(self):
        """Send morning digest at 6:00 JST."""
        logger.info("Sending morning digest...")
        self._send_digest("朝のダイジェスト", hours_back=12)
    
    def send_night_digest(self):
        """Send night digest at 22:00 JST."""
        logger.info("Sending night digest...")
        self._send_digest("夜のダイジェスト", hours_back=16)
    
    def _send_digest(self, title: str, hours_back: int = 24):
        """Send digest with top articles."""
        try:
            # Collect articles
            articles = self.collector.collect(limit_per_feed=20)
            
            # Filter by time
            cutoff = datetime.now() - timedelta(hours=hours_back)
            recent_articles = [
                a for a in articles
                if a.ts.replace(tzinfo=None) > cutoff
            ]
            
            # Enrich and filter
            enriched_articles = []
            for article in recent_articles:
                if self.duplicate_checker.is_duplicate(article.url, article.title):
                    continue
                
                enriched = self._enrich_article(article)
                if enriched and self.filter.is_digest_worthy(enriched):
                    enriched_articles.append(enriched)
            
            # Sort by impact score
            enriched_articles.sort(key=lambda x: x.impact_score, reverse=True)
            
            # Take top articles
            top_articles = enriched_articles[:10]
            
            if not top_articles:
                logger.info("No digest-worthy articles found")
                return
            
            # Prepare digest data
            digest_data = []
            for enriched in top_articles:
                # Generate short summary
                summary, _ = self._generate_summary_and_guide(enriched)
                
                # Determine confidence
                if enriched.impact_score >= 80:
                    confidence = "高"
                elif enriched.impact_score >= 60:
                    confidence = "中"
                else:
                    confidence = "低"
                
                digest_data.append({
                    "title": enriched.article.title,
                    "summary_short": summary[:200],
                    "currencies_str": ", ".join(enriched.currencies[:3]),
                    "confidence": confidence,
                    "url": str(enriched.article.url)
                })
                
                # Mark as sent
                self.duplicate_checker.add(enriched.article.url, enriched.article.title)
            
            # Send digest
            self.delivery.send_digest(
                title=f"📊 {title}",
                articles=digest_data,
                period="本日"
            )
            
            logger.info(f"Digest sent with {len(digest_data)} articles")
        
        except Exception as e:
            logger.error(f"Failed to send digest: {e}")
    
    def setup_jobs(self):
        """Setup scheduled jobs."""
        # Morning digest (6:00 JST)
        morning_time = config.schedule.morning_digest_jst.split(":")
        self.scheduler.add_job(
            self.send_morning_digest,
            CronTrigger(hour=int(morning_time[0]), minute=int(morning_time[1])),
            id="morning_digest",
            name="Morning Digest"
        )
        
        # Night digest (22:00 JST)
        night_time = config.schedule.night_digest_jst.split(":")
        self.scheduler.add_job(
            self.send_night_digest,
            CronTrigger(hour=int(night_time[0]), minute=int(night_time[1])),
            id="night_digest",
            name="Night Digest"
        )
        
        # Breaking news check (every 5 minutes)
        self.scheduler.add_job(
            self.check_breaking_news,
            IntervalTrigger(minutes=config.schedule.breaking_check_interval_minutes),
            id="breaking_news",
            name="Breaking News Check"
        )
        
        logger.info("Scheduler jobs configured")
    
    def start(self):
        """Start scheduler."""
        try:
            self.setup_jobs()
            logger.info("Starting scheduler...")
            self.scheduler.start()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            self.scheduler.shutdown()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            self.scheduler.shutdown()