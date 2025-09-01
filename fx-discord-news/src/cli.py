"""Command-line interface for FX Discord News."""

import sys
from datetime import datetime
import click
from loguru import logger
from typing import Optional

from src.config import config, settings
from src.collectors import RSSCollector
from src.nlp import EntityExtractor, ImpactScorer, LLMAdapter
from src.nlp.prompts import SUMMARY_PROMPT, ACTION_PROMPT
from src.filters import NewsFilter
from src.filters.rules import Enriched
from src.delivery import DiscordDelivery
from src.scheduler import NewsScheduler
from src.utils import clean_text, normalize_japanese, DuplicateChecker
from src.collectors.rss import Article

@click.group()
def cli():
    """FX Discord News - Automated FX news collection and delivery."""
    pass

@cli.command()
@click.option('--when', type=click.Choice(['morning', 'night']), required=True, help='Digest type')
def digest(when: str):
    """Send digest (morning or night)."""
    logger.info(f"Sending {when} digest...")
    
    scheduler = NewsScheduler()
    
    if when == 'morning':
        scheduler.send_morning_digest()
    else:
        scheduler.send_night_digest()
    
    logger.info("Digest sent successfully")

@cli.command()
@click.option('--url', required=True, help='News article URL to summarize')
def summary(url: str):
    """Summarize a specific news article."""
    logger.info(f"Summarizing article: {url}")
    
    try:
        # Create dummy article
        import httpx
        from bs4 import BeautifulSoup
        
        # Fetch article
        with httpx.Client() as client:
            response = client.get(url)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = soup.find('title')
            title = title.text if title else "No title"
            
            # Extract body
            body = soup.get_text(separator=' ', strip=True)[:2000]
        
        # Create article object
        article = Article(
            id="test",
            source="Manual",
            url=url,
            ts=datetime.now(),
            title=title,
            body=body,
            lang="en"
        )
        
        # Process article
        extractor = EntityExtractor()
        scorer = ImpactScorer()
        
        text = f"{article.title} {article.body}"
        text = clean_text(text)
        
        currencies = extractor.extract_currencies(text)
        central_banks = extractor.extract_central_banks(text)
        category = extractor.categorize_event(text)
        pairs = extractor.extract_currency_pairs(currencies)
        
        impact_score = scorer.calculate_impact_score(
            text, category, currencies, central_banks
        )
        pair_scores = scorer.calculate_pair_scores(
            text, pairs, currencies, central_banks
        )
        
        # Generate summary
        llm = LLMAdapter(
            provider=config.llm.provider,
            model=config.llm.model.get(config.llm.provider)
        )
        
        summary_text = llm.summarize(
            SUMMARY_PROMPT,
            title=article.title,
            body=article.body[:1000],
            source=article.source,
            currencies=", ".join(currencies),
            category=category,
            impact_score=impact_score
        )
        
        action_guide = llm.generate_action_guide(
            ACTION_PROMPT,
            summary=summary_text,
            currencies=", ".join(currencies),
            category=category,
            impact_score=impact_score
        )
        
        # Print results
        click.echo("\n" + "="*50)
        click.echo("📰 ARTICLE SUMMARY")
        click.echo("="*50)
        click.echo(f"\n📌 Title: {title}")
        click.echo(f"🌐 URL: {url}")
        click.echo(f"💱 Currencies: {', '.join(currencies)}")
        click.echo(f"🏦 Central Banks: {', '.join(central_banks)}")
        click.echo(f"📊 Category: {category}")
        click.echo(f"⚡ Impact Score: {impact_score}/100")
        click.echo(f"\n📝 Summary:\n{normalize_japanese(summary_text)}")
        click.echo(f"\n🎯 Action Guide:\n{normalize_japanese(action_guide)}")
        click.echo("\n" + "="*50)
        
    except Exception as e:
        logger.error(f"Failed to summarize article: {e}")
        sys.exit(1)

@cli.command()
def test_news():
    """Send test news to Discord."""
    logger.info("Sending test news to Discord...")
    
    # Create test article
    test_article = {
        "title": "【テスト】FRBが予想外の利上げを発表 - ドル急騰",
        "summary": """要点：
・FRB（米連邦準備制度理事会）が0.25%の利上げを決定
・市場予想は据え置きだったため、サプライズとなった
・ドルが主要通貨に対して全面高の展開

なぜ重要か：金利差拡大でドル買い圧力が強まる可能性

関連ペア：USDJPY, EURUSD, GBPUSD

確度：高（公式発表に基づく）""",
        "action_guide": """想定シナリオA（ドル高継続）：USDJPY上昇継続の可能性。150円のレジスタンスラインに注目。

想定シナリオB（利益確定売り）：急騰後の調整で一時的な下落。148円のサポートラインを確認。

注意：FOMC後はボラティリティが高く、スプレッドも拡大傾向。ポジションサイズは通常の半分程度に抑えることを推奨。""",
        "source": "テストソース",
        "url": "https://example.com/test-article",
        "currencies": ["USD", "JPY", "EUR"],
        "confidence": "高"
    }
    
    # Send to Discord
    delivery = DiscordDelivery(
        webhook_beginner=settings.discord_webhook_beginner,
        webhook_pro=settings.discord_webhook_pro,
        disclaimer=config.disclaimer
    )
    
    success = delivery.send_news(
        title=test_article["title"],
        summary=test_article["summary"],
        action_guide=test_article["action_guide"],
        source=test_article["source"],
        url=test_article["url"],
        currencies=test_article["currencies"],
        confidence=test_article["confidence"],
        original_excerpt="これはテスト記事の原文抜粋です。実際のニュースではありません。"
    )
    
    if success:
        logger.info("Test news sent successfully!")
        click.echo("✅ Test news sent successfully to Discord!")
    else:
        logger.error("Failed to send test news")
        click.echo("❌ Failed to send test news. Check your webhook configuration.")
        sys.exit(1)

@cli.command(name='run-scheduler')
def run_scheduler():
    """Run the news scheduler (daemon mode)."""
    click.echo("Starting FX News Scheduler...")
    click.echo(f"Timezone: {settings.tz}")
    click.echo(f"Morning digest: {config.schedule.morning_digest_jst} JST")
    click.echo(f"Night digest: {config.schedule.night_digest_jst} JST")
    click.echo(f"Breaking news check: every {config.schedule.breaking_check_interval_minutes} minutes")
    click.echo("\nPress Ctrl+C to stop\n")
    
    scheduler = NewsScheduler()
    scheduler.start()

@cli.command(name='check-breaking')
def check_breaking():
    """Check for breaking news once."""
    logger.info("Checking for breaking news...")
    
    scheduler = NewsScheduler()
    scheduler.check_breaking_news()
    
    logger.info("Breaking news check completed")

def main():
    """Main entry point."""
    cli()

if __name__ == '__main__':
    main()