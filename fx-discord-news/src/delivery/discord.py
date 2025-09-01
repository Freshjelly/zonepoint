"""Discord delivery module."""

from datetime import datetime
from typing import Dict, List, Optional
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

class DiscordEmbed:
    """Discord embed builder."""
    
    # Color codes
    COLORS = {
        "high": 0x00FF00,    # Green
        "medium": 0xFFFF00,   # Yellow
        "low": 0x808080,      # Gray
        "error": 0xFF0000,    # Red
    }
    
    @classmethod
    def create_news_embed(
        cls,
        title: str,
        summary: str,
        action_guide: str,
        source: str,
        url: str,
        currencies: List[str],
        confidence: str,
        disclaimer: str
    ) -> Dict:
        """Create news embed."""
        # Parse summary sections
        sections = cls._parse_summary(summary)
        
        # Determine color based on confidence
        color = cls.COLORS.get(confidence.lower(), cls.COLORS["medium"])
        
        # Build embed
        embed = {
            "title": title[:256],  # Discord limit
            "url": url,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": f"出所: {source}"
            },
            "fields": []
        }
        
        # Add summary fields
        if sections.get("要点"):
            embed["fields"].append({
                "name": "📌 要点",
                "value": sections["要点"][:1024],
                "inline": False
            })
        
        if sections.get("なぜ重要か"):
            embed["fields"].append({
                "name": "⚡ なぜ重要か",
                "value": sections["なぜ重要か"][:1024],
                "inline": False
            })
        
        if sections.get("関連ペア"):
            embed["fields"].append({
                "name": "💱 関連ペア",
                "value": sections["関連ペア"][:1024],
                "inline": True
            })
        
        embed["fields"].append({
            "name": "📊 確度",
            "value": confidence,
            "inline": True
        })
        
        # Add action guide
        if action_guide:
            embed["fields"].append({
                "name": "🎯 次の一手（考え方）",
                "value": action_guide[:1024],
                "inline": False
            })
        
        # Add checklist
        checklist = (
            "□ 経済指標カレンダーを確認\n"
            "□ 直近の高値・安値を確認\n"
            "□ スプレッドを確認\n"
            "□ ポジションサイズを計算"
        )
        embed["fields"].append({
            "name": "✅ チェックリスト",
            "value": checklist,
            "inline": False
        })
        
        # Add disclaimer
        if disclaimer:
            embed["fields"].append({
                "name": "⚠️ 免責事項",
                "value": disclaimer[:1024],
                "inline": False
            })
        
        return embed
    
    @staticmethod
    def _parse_summary(summary: str) -> Dict[str, str]:
        """Parse summary into sections."""
        sections = {}
        current_section = None
        current_content = []
        
        for line in summary.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Check for section headers
            if line.startswith("要点：") or line.startswith("要点:"):
                if current_section:
                    sections[current_section] = "\n".join(current_content)
                current_section = "要点"
                current_content = [line.split("：", 1)[-1].strip()]
            elif line.startswith("なぜ重要か：") or line.startswith("なぜ重要か:"):
                if current_section:
                    sections[current_section] = "\n".join(current_content)
                current_section = "なぜ重要か"
                current_content = [line.split("：", 1)[-1].strip()]
            elif line.startswith("関連ペア：") or line.startswith("関連ペア:"):
                if current_section:
                    sections[current_section] = "\n".join(current_content)
                current_section = "関連ペア"
                current_content = [line.split("：", 1)[-1].strip()]
            elif line.startswith("確度：") or line.startswith("確度:"):
                if current_section:
                    sections[current_section] = "\n".join(current_content)
                current_section = "確度"
                current_content = [line.split("：", 1)[-1].strip()]
            elif current_section:
                current_content.append(line)
        
        # Add last section
        if current_section:
            sections[current_section] = "\n".join(current_content)
        
        return sections

class DiscordDelivery:
    """Discord webhook delivery."""
    
    def __init__(
        self,
        webhook_beginner: str,
        webhook_pro: str,
        disclaimer: str = ""
    ):
        self.webhook_beginner = webhook_beginner
        self.webhook_pro = webhook_pro
        self.disclaimer = disclaimer
        self.client = httpx.Client(timeout=30)
    
    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10)
    )
    def _send_webhook(self, webhook_url: str, payload: Dict) -> bool:
        """Send webhook request."""
        if not webhook_url:
            logger.warning("Webhook URL not configured")
            return False
        
        try:
            response = self.client.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info("Discord webhook sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            raise
    
    def send_news(
        self,
        title: str,
        summary: str,
        action_guide: str,
        source: str,
        url: str,
        currencies: List[str],
        confidence: str = "中",
        original_excerpt: Optional[str] = None
    ) -> bool:
        """Send news to Discord."""
        # Create embed
        embed = DiscordEmbed.create_news_embed(
            title=title,
            summary=summary,
            action_guide=action_guide,
            source=source,
            url=url,
            currencies=currencies,
            confidence=confidence,
            disclaimer=self.disclaimer
        )
        
        # Prepare payloads
        beginner_payload = {
            "embeds": [embed]
        }
        
        # Pro version with original excerpt
        pro_payload = {
            "embeds": [embed.copy()]
        }
        
        if original_excerpt and self.webhook_pro:
            pro_payload["embeds"][0]["fields"].insert(1, {
                "name": "📄 原文抜粋",
                "value": original_excerpt[:1024],
                "inline": False
            })
        
        # Send to both webhooks
        success = True
        
        if self.webhook_beginner:
            try:
                self._send_webhook(self.webhook_beginner, beginner_payload)
            except Exception:
                success = False
        
        if self.webhook_pro:
            try:
                self._send_webhook(self.webhook_pro, pro_payload)
            except Exception:
                success = False
        
        return success
    
    def send_digest(
        self,
        title: str,
        articles: List[Dict],
        period: str = "today"
    ) -> bool:
        """Send digest to Discord."""
        # Create digest embed
        embed = {
            "title": title,
            "color": DiscordEmbed.COLORS["medium"],
            "timestamp": datetime.utcnow().isoformat(),
            "description": f"📰 {period}の重要ニュースまとめ",
            "fields": []
        }
        
        # Add article summaries
        for i, article in enumerate(articles[:10], 1):
            field_value = (
                f"**{article.get('confidence', '中')}** | "
                f"{article.get('currencies_str', 'N/A')}\n"
                f"{article.get('summary_short', '')[:200]}..."
            )
            
            embed["fields"].append({
                "name": f"{i}. {article['title'][:100]}",
                "value": field_value,
                "inline": False
            })
        
        # Add disclaimer
        if self.disclaimer:
            embed["fields"].append({
                "name": "⚠️ 免責事項",
                "value": self.disclaimer[:1024],
                "inline": False
            })
        
        # Send to both webhooks
        payload = {"embeds": [embed]}
        
        success = True
        if self.webhook_beginner:
            try:
                self._send_webhook(self.webhook_beginner, payload)
            except Exception:
                success = False
        
        if self.webhook_pro:
            try:
                self._send_webhook(self.webhook_pro, payload)
            except Exception:
                success = False
        
        return success