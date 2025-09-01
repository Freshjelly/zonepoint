#!/usr/bin/env python3
"""
FX News fetcher with alert and digest modes.
Python 3.11 compatible.
"""

import argparse
import atexit
import fcntl
import hashlib
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

# External deps (lazy import with fallbacks where possible)
try:
    import feedparser  # type: ignore
except Exception:
    feedparser = None  # type: ignore

try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore

try:
    import tldextract  # type: ignore
except Exception:
    tldextract = None  # type: ignore

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    BeautifulSoup = None  # type: ignore

try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore
except Exception:
    _load_dotenv = None

try:
    from langdetect import detect  # type: ignore
except Exception:
    def detect(_text: str) -> str:  # fallback: unknown language
        return ""

try:
    from readability import Document  # type: ignore
except Exception:
    Document = None  # type: ignore


DEFAULT_FEEDS = [
    "https://www.fxstreet.com/rss/news",
    "https://www.boj.or.jp/en/rss/whatsnew.xml",
    "https://www.federalreserve.gov/feeds/press_all.xml",
]

MODEL_NAME = "gpt-4o-mini"
DISCORD_LIMIT = 1900  # keep some headroom from 2000


def load_env():
    try:
        if _load_dotenv:
            _load_dotenv()
    except Exception:
        pass


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_sha1 TEXT UNIQUE,
            url TEXT,
            seen_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            url TEXT,
            host TEXT,
            title_hint TEXT,
            summary_hint TEXT,
            body_excerpt TEXT,
            ja_bullets TEXT,
            tags TEXT,
            score INTEGER,
            created_at TEXT,
            alert_posted_at TEXT,
            digest_date_jst TEXT
        )
        """
    )
    conn.commit()
    return conn


def is_seen(conn: sqlite3.Connection, url: str) -> bool:
    try:
        h = sha1(url)
        cur = conn.execute("SELECT 1 FROM seen WHERE url_sha1=?", (h,))
        return cur.fetchone() is not None
    except Exception:
        return False


def ensure_seen(conn: sqlite3.Connection, url: str) -> None:
    try:
        h = sha1(url)
        conn.execute(
            "INSERT OR IGNORE INTO seen(url_sha1, url, seen_at) VALUES (?, ?, ?)",
            (h, url, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.commit()
    except Exception:
        pass


def upsert_article(
    conn: sqlite3.Connection,
    url: str,
    host: str,
    title_hint: str,
    summary_hint: str,
    body_excerpt: str,
    ja_bullets: str,
    tags: str,
    score: int,
) -> None:
    try:
        _id = sha1(url)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            """
            INSERT INTO articles(id, url, host, title_hint, summary_hint, body_excerpt, ja_bullets, tags, score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                host=excluded.host,
                title_hint=COALESCE(excluded.title_hint, articles.title_hint),
                summary_hint=COALESCE(excluded.summary_hint, articles.summary_hint),
                body_excerpt=COALESCE(excluded.body_excerpt, articles.body_excerpt),
                ja_bullets=COALESCE(excluded.ja_bullets, articles.ja_bullets),
                tags=COALESCE(excluded.tags, articles.tags),
                score=COALESCE(excluded.score, articles.score)
            """,
            (
                _id,
                url,
                host,
                title_hint,
                summary_hint,
                body_excerpt,
                ja_bullets,
                tags,
                int(score),
                now,
            ),
        )
        conn.commit()
    except Exception as e:
        print(f"upsert_article error: {e}")


def mark_alert_posted(conn: sqlite3.Connection, url: str) -> None:
    try:
        _id = sha1(url)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute("UPDATE articles SET alert_posted_at=? WHERE id=?", (now, _id))
        conn.commit()
    except Exception:
        pass


def mark_digest_date(conn: sqlite3.Connection, url: str, date_jst: str) -> None:
    try:
        _id = sha1(url)
        conn.execute("UPDATE articles SET digest_date_jst=? WHERE id=?", (date_jst, _id))
        conn.commit()
    except Exception:
        pass


def fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    if requests is None:
        print("Missing dependency 'requests'. Install with: pip install requests")
        return None
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code >= 400:
            print(f"HTTP {r.status_code} for {url}")
            return None
        return r.text
    except Exception as e:
        print(f"fetch_url error for {url}: {e}")
        return None


def _fallback_meta_description(html: str) -> str:
    if not html:
        return ""
    try:
        if BeautifulSoup is None:
            import re as _re

            m = _re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html, _re.I)
            if m:
                return m.group(1).strip()
            m = _re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, _re.I)
            if m:
                return m.group(1).strip()
            return ""
        soup = BeautifulSoup(html, "html.parser")
        og = soup.find("meta", attrs={"property": "og:description"})
        if og and og.get("content"):
            return og.get("content").strip()
        desc = soup.find("meta", attrs={"name": "description"})
        if desc and desc.get("content"):
            return desc.get("content").strip()
    except Exception:
        pass
    return ""


def _html_to_text_basic(html: str) -> str:
    try:
        import re as _re
        html = _re.sub(r"<script[\s\S]*?</script>", " ", html, flags=_re.I)
        html = _re.sub(r"<style[\s\S]*?</style>", " ", html, flags=_re.I)
        html = _re.sub(r"</?(p|div|br|li|ul|ol|h\d)[^>]*>", "\n", html, flags=_re.I)
        text = _re.sub(r"<[^>]+>", " ", html)
        text = _re.sub(r"\s+", " ", text)
        return text.strip()
    except Exception:
        return ""


def extract_main_text(html: str) -> str:
    try:
        if Document is not None:
            doc = Document(html)
            content_html = doc.summary(html_partial=True)
            if BeautifulSoup is not None:
                soup = BeautifulSoup(content_html, "html.parser")
                for tag in soup(["script", "style", "nav", "aside", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text("\n")
                lines = [l.strip() for l in text.splitlines()]
                text = "\n".join([l for l in lines if l])
                if text:
                    return text
            else:
                text = _html_to_text_basic(content_html)
                if text:
                    return text
    except Exception:
        pass
    meta = _fallback_meta_description(html)
    if meta:
        return meta
    return _html_to_text_basic(html)


def _split_sentences(text: str) -> List[str]:
    import re

    if not text:
        return []
    t = re.sub(r"[\t\r]+", " ", text)
    ja_parts = re.split(r"(?<=[。！？])\s+", t)
    en_parts: List[str] = []
    for p in ja_parts:
        en_parts.extend(re.split(r"(?<=[\.!?])\s+", p))
    sents = [s.strip() for s in en_parts if s and len(s.strip()) > 0]
    return sents


def summarize_rule_based_ja(text: str) -> str:
    import re

    sents = _split_sentences(text)
    if not sents:
        return ""
    keywords = [
        "利上げ",
        "利下げ",
        "インフレ",
        "CPI",
        "雇用",
        "PMI",
        "中銀",
        "金利",
        "政策金利",
        "声明",
        "発言",
        "景気",
        "ドル",
        "円",
        "ユーロ",
        "債券",
        "住宅",
        "指標",
        "予想",
        "前月比",
        "前年比",
        "上昇",
        "低下",
        "伸び",
        "減速",
        "Fed",
        "FOMC",
        "BoJ",
        "ECB",
        "rate",
        "inflation",
        "employment",
        "policy",
        "statement",
        "yoy",
        "mom",
    ]
    scored: List[Tuple[int, str]] = []
    for s in sents:
        score = 0
        for kw in keywords:
            if kw.lower() in s.lower():
                score += 1
        l = len(s)
        if 40 <= l <= 160:
            score += 1
        if any(x in s for x in ["%", "億", "兆", "万人", "bp", "ポイント", "basis"]):
            score += 1
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for _, s in scored[:3] if len(s.strip()) > 0]
    if not top:
        top = sents[:2]
    if len(top) < 2:
        top = (top + sents)[:2]
    top = top[:3]

    bullets = []
    for s in top:
        s = re.sub(r"\s+", " ", s).strip()
        max_len = 120
        if len(s) > max_len:
            s = s[: max_len - 1] + "…"
        bullets.append("• " + s)
    return "\n".join(bullets)


def _openai_chat(api_key: str, model_name: str, text: str, timeout: int = 15) -> Optional[str]:
    if requests is None:
        print("OpenAI call skipped: missing 'requests'")
        return None
    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        system_prompt = (
            "金融ニュースの熟練エディター。与える本文だけから日本語で2〜3行の箇条書き要約(各60〜120字)。"
            "固有名詞/数値は保持。前置き/補足禁止。タイトルを使わない。"
        )
        payload = {
            "model": model_name,
            "temperature": 0.2,
            "max_tokens": 512,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text[:12000]},
            ],
        }
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
        if r.status_code >= 400:
            print(f"OpenAI API error {r.status_code}: {r.text[:200]}")
            return None
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip()
    except Exception as e:
        print(f"OpenAI call error: {e}")
        return None


def _normalize_llm_output(text: str) -> List[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    bullets = []
    for l in lines:
        if l.startswith("• "):
            bullets.append(l)
        elif l.startswith("-") or l.startswith("・"):
            bullets.append("• " + l.lstrip("-・ "))
        else:
            bullets.append("• " + l)
        if len(bullets) >= 3:
            break
    if len(bullets) < 2 and lines:
        for l in lines[len(bullets) :]:
            bullets.append("• " + l)
            if len(bullets) >= 2:
                break
    return bullets[:3]


def summarize_llm_ja(text: str, model_name: str, api_key: str, timeout: int = 15) -> str:
    out = _openai_chat(api_key, model_name, text, timeout=timeout)
    if not out:
        return ""
    bullets = _normalize_llm_output(out)
    if len(bullets) < 2:
        return ""
    trimmed = []
    for b in bullets:
        if len(b) > 140:
            trimmed.append(b[:139] + "…")
        else:
            trimmed.append(b)
    return "\n".join(trimmed)


def _deepl_translate(api_key: str, text: str, timeout: int = 15) -> Optional[str]:
    if requests is None:
        print("DeepL call skipped: missing 'requests'")
        return None
    try:
        host = "api.deepl.com"
        if api_key.endswith(":fx") or api_key.endswith("-free"):
            host = "api-free.deepl.com"
        url = f"https://{host}/v2/translate"
        data = {"auth_key": api_key, "text": text, "target_lang": "JA"}
        r = requests.post(url, data=data, timeout=timeout)
        if r.status_code >= 400:
            print(f"DeepL API error {r.status_code}: {r.text[:200]}")
            return None
        res = r.json()
        tr = res.get("translations", [{}])[0].get("text", "")
        return tr.strip()
    except Exception as e:
        print(f"DeepL call error: {e}")
        return None


def summarize_to_ja(text: str, model_name: str, openai_key: Optional[str], deepl_key: Optional[str], timeout: int = 15) -> str:
    if openai_key:
        s = summarize_llm_ja(text, model_name, openai_key, timeout=timeout)
        if s:
            return s
    rb = summarize_rule_based_ja(text)
    if not rb:
        return ""
    lang = ""
    try:
        lang = detect(text)
    except Exception:
        lang = ""
    if lang != "ja" and deepl_key:
        tr = _deepl_translate(deepl_key, rb, timeout=timeout)
        if tr:
            return tr
    return rb


def re_search(pattern: str, text: str) -> bool:
    import re

    return re.search(pattern, text) is not None


def detect_pairs(text: str) -> List[str]:
    patterns = [
        ("USDJPY", r"(?i)(USD\s*/?\s*JPY|ドル\s*/?\s*円|米?ドル.*?円|円.*?米?ドル)"),
        ("EURJPY", r"(?i)(EUR\s*/?\s*JPY|ユーロ.*?円|円.*?ユーロ)"),
        ("EURUSD", r"(?i)(EUR\s*/?\s*USD|ユーロ.*?ドル|ドル.*?ユーロ)"),
        ("GBPUSD", r"(?i)(GBP\s*/?\s*USD|ポンド.*?ドル|ドル.*?ポンド)"),
        ("AUDJPY", r"(?i)(AUD\s*/?\s*JPY|豪.*?円|円.*?豪)"),
    ]
    tags = []
    for name, pat in patterns:
        try:
            if re_search(pat, text):
                tags.append(f"[{name}]")
        except Exception:
            continue
        if len(tags) >= 4:
            break
    return tags


def _get_host(url: str) -> str:
    if tldextract is not None:
        try:
            ext = tldextract.extract(url)
            return ".".join([p for p in [ext.domain, ext.suffix] if p]) or ext.fqdn or url
        except Exception:
            pass
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        if host.startswith("www."):
            host = host[4:]
        return host or url
    except Exception:
        return url


def build_digest_block(summary: str, url: str, tags: List[str]) -> str:
    host = _get_host(url)
    tag_str = " ".join(tags) if tags else ""
    line2 = f"{url}  (source: {host})"
    if tag_str:
        line2 += f"  {tag_str}"
    return f"{summary}\n{line2}"


def post_to_discord(message: str, webhook: str, timeout: int = 15, retries: int = 3) -> bool:
    if requests is None:
        print("Discord post skipped: missing 'requests'")
        return False
    headers = {"Content-Type": "application/json"}
    payload = {"content": message}
    delay = 1.0
    for i in range(retries):
        try:
            r = requests.post(webhook, headers=headers, data=json.dumps(payload), timeout=timeout)
            if r.status_code < 400:
                return True
            print(f"Discord error {r.status_code}: {r.text[:500]}")
        except Exception as e:
            print(f"Discord post error (try {i+1}/{retries}): {e}")
        if i < retries - 1:
            time.sleep(delay)
            delay *= 2
    return False


def _pack_blocks_to_limit(header: str, blocks: List[str], limit: int = DISCORD_LIMIT) -> Tuple[str, int]:
    message = header
    used = 0
    for blk in blocks:
        candidate = message + "\n\n" + blk
        if len(candidate) <= limit:
            message = candidate
            used += 1
            continue
        if used == 0:
            available = limit - len(header) - 2
            if available > 10:
                short = blk[: available - 9] + "…（続く可能性）"
                message = header + "\n\n" + short
                used = 1
        break
    if len(message) > limit:
        # as safety, hard cut with marker
        message = message[: limit - 9] + "…（続く可能性）"
    return message, used


def _collect_feed_items(feed_url: str, timeout: int = 15) -> List[dict]:
    items: List[dict] = []
    if feedparser is not None:
        try:
            f = feedparser.parse(feed_url)
            for e in getattr(f, 'entries', []) or []:
                link = e.get("link")
                if not link:
                    continue
                summary = e.get("summary") or e.get("description") or ""
                title = e.get("title") or ""
                items.append({"url": link, "summary": summary, "title": title})
            return items
        except Exception as e:
            print(f"Feed parse error (feedparser) {feed_url}: {e}")
    try:
        xml_text = fetch_url(feed_url, timeout=timeout)
        if not xml_text:
            return items
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_text)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        for it in root.findall('.//item'):
            link = it.findtext('link') or ''
            summary = it.findtext('description') or ''
            title = it.findtext('title') or ''
            if link:
                items.append({"url": link, "summary": summary, "title": title})
        for it in root.findall('.//atom:entry', ns):
            link_el = it.find('atom:link', ns)
            link = ''
            if link_el is not None:
                link = link_el.attrib.get('href', '')
            if not link:
                t = it.findtext('atom:id', namespaces=ns)
                link = t or ''
            summary = (it.findtext('atom:summary', namespaces=ns) or it.findtext('atom:content', namespaces=ns) or '')
            title = it.findtext('atom:title', namespaces=ns) or ''
            if link:
                items.append({"url": link, "summary": summary, "title": title})
    except Exception as e:
        print(f"Feed parse error (fallback) {feed_url}: {e}")
    return items


def _get_env_webhooks(args) -> Tuple[str, str, str]:
    base = args.webhook or os.getenv("DISCORD_WEBHOOK")
    alerts = args.webhook_alerts or os.getenv("DISCORD_WEBHOOK_ALERTS") or base
    digest = args.webhook_digest or os.getenv("DISCORD_WEBHOOK_DIGEST") or base
    return base or "", alerts or "", digest or ""


def compute_score(text: str, bullets: str, tags: List[str]) -> int:
    import re

    strong = r"(?i)(利上げ|利下げ|policy rate|rate hike|rate cut|介入|為替介入|緊急会合|emergency meeting|声明|statement|関税|tariff|制裁|sanction|辞任|解任|resign|fired|解雇|国債買入|YCC|サプライズ|surprise)"
    medium = r"(?i)(インフレ|inflation|CPI|雇用|NFP|失業|unemployment|PMI|要人発言|remarks|guidance|見通し|outlook)"
    score = 0
    combined = (text or "") + "\n" + (bullets or "")
    if re.search(strong, combined):
        # May appear multiple times; count occurrences for additive +2 per match?
        # Spec implies keyword category adds points when present; we'll add once.
        score += 2
    if re.search(medium, combined):
        score += 1
    if any(t in tags for t in ["[USDJPY]", "[EURUSD]", "[EURJPY]"]):
        score += 1
    return score


@dataclass
class PreparedArticle:
    url: str
    host: str
    bullets: str
    tags: List[str]
    score: int


def process_candidate(
    url: str,
    summary_hint: str,
    model_name: str,
    openai_key: Optional[str],
    deepl_key: Optional[str],
    timeout: int = 15,
) -> Optional[PreparedArticle]:
    html = fetch_url(url, timeout=timeout)
    body_text = ""
    if html:
        body_text = extract_main_text(html)
    if not body_text:
        body_text = summary_hint or ""
    if not body_text:
        if html:
            body_text = _fallback_meta_description(html)
    if not body_text:
        return None
    try:
        bullets = summarize_to_ja(body_text, model_name, openai_key, deepl_key, timeout=timeout)
    except Exception as e:
        print(f"Summarization error for {url}: {e}")
        bullets = ""
    if not bullets:
        return None
    tags = detect_pairs(body_text)
    score = compute_score(body_text, bullets, tags)
    host = _get_host(url)
    return PreparedArticle(url=url, host=host, bullets=bullets, tags=tags, score=score)


def mode_fetch_alert(
    conn: sqlite3.Connection,
    feeds: List[str],
    direct_urls: List[str],
    max_items: int,
    model_name: str,
    openai_key: Optional[str],
    deepl_key: Optional[str],
    webhook_alerts: str,
    timeout: int,
    dry_run: bool = False,
) -> None:
    if not webhook_alerts:
        print("Missing DISCORD_WEBHOOK_ALERTS (or DISCORD_WEBHOOK). Skipping alerts.")
    candidates: List[dict] = []
    for fu in feeds:
        items = _collect_feed_items(fu, timeout=timeout)
        candidates.extend(items)
    for u in direct_urls:
        candidates.append({"url": u, "summary": "", "title": ""})

    # dedupe by URL, preserve order
    seen_urls: set[str] = set()
    uniq = []
    for it in candidates:
        u = (it.get("url") or "").strip()
        if not u or u in seen_urls:
            continue
        seen_urls.add(u)
        uniq.append(it)

    prepared_new: List[PreparedArticle] = []
    count_processed = 0
    for it in uniq:
        if count_processed >= max_items:
            break
        url = it.get("url", "")
        summary_hint = it.get("summary", "")
        title_hint = it.get("title", "")
        if not url:
            continue

        already = is_seen(conn, url)
        pa = process_candidate(url, summary_hint, model_name, openai_key, deepl_key, timeout=timeout)
        if not pa:
            continue

        body_excerpt = pa.bullets.replace("\n", " ")
        upsert_article(
            conn,
            url=url,
            host=pa.host,
            title_hint=title_hint,
            summary_hint=summary_hint,
            body_excerpt=body_excerpt[:400],
            ja_bullets=pa.bullets,
            tags=" ".join(pa.tags),
            score=pa.score,
        )
        ensure_seen(conn, url)

        if not already and pa.score >= 3:
            prepared_new.append(pa)
        count_processed += 1

    if not prepared_new:
        print("No alerts to post.")
        return

    # spam guard: max 3 alerts per last hour
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    try:
        cur = conn.execute(
            "SELECT COUNT(1) FROM articles WHERE alert_posted_at IS NOT NULL AND alert_posted_at >= ?",
            (one_hour_ago.isoformat(timespec="seconds"),),
        )
        recent_count = int(cur.fetchone()[0])
    except Exception:
        recent_count = 0

    remaining_slots = max(0, 3 - recent_count)
    individual = prepared_new[:remaining_slots]
    batched = prepared_new[remaining_slots:]

    # Post individual alerts
    for pa in individual:
        header = "【速報】本文要約（日本語)"
        block = build_digest_block(pa.bullets, pa.url, pa.tags)
        msg, _ = _pack_blocks_to_limit(header, [block], limit=DISCORD_LIMIT)
        if dry_run:
            print(f"[DRY-RUN] アラート投稿:\n{msg}")
        elif webhook_alerts:
            ok = post_to_discord(msg, webhook_alerts, timeout=timeout)
            if ok:
                mark_alert_posted(conn, pa.url)
        else:
            print(msg)

    # Post batched alert if needed
    if batched:
        header = "【速報】本文要約（日本語)"
        blocks = [build_digest_block(pa.bullets, pa.url, pa.tags) for pa in batched]
        msg, used = _pack_blocks_to_limit(header, blocks, limit=DISCORD_LIMIT)
        if used > 0:
            if dry_run:
                print(f"[DRY-RUN] バッチアラート投稿:\n{msg}")
            elif webhook_alerts:
                ok = post_to_discord(msg, webhook_alerts, timeout=timeout)
                if ok:
                    for pa in batched[:used]:
                        mark_alert_posted(conn, pa.url)


def jst_window(now_utc: datetime, tz_name: str, kind: str = "morning") -> Tuple[datetime, datetime, str]:
    """
    時間窓計算
    kind='morning': 前日6:00→当日6:00
    kind='day': 当日0:00→現在
    """
    tz = ZoneInfo(tz_name) if ZoneInfo else timezone(timedelta(hours=9))
    now_local = now_utc.astimezone(tz)
    
    if kind == "day":
        # 当日0:00→現在
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = now_local
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        range_str = f"{start_local.strftime('%Y-%m-%d %H:%M')}〜{end_local.strftime('%Y-%m-%d %H:%M')} {tz_name}"
        date_jst = end_local.strftime('%Y-%m-%d')
        return start_utc, end_utc, f"{range_str}|{date_jst}"
    
    else:  # kind == "morning" (デフォルト)
        # 前日6:00→当日6:00
        pivot = now_local.replace(hour=6, minute=0, second=0, microsecond=0)
        if now_local < pivot:
            pivot = pivot - timedelta(days=0)  # running exactly at 6:00 works
        # find most recent 6:00 <= now; if running after 6:00, pivot is today 6; if before, pivot is today 6 as well (cron at 6:00)
        start_local = pivot - timedelta(days=1)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = pivot.astimezone(timezone.utc)
        range_str = f"{start_local.strftime('%Y-%m-%d %H:%M')}〜{pivot.strftime('%Y-%m-%d %H:%M')} {tz_name}"
        date_jst = pivot.strftime('%Y-%m-%d')
        return start_utc, end_utc, f"{range_str}|{date_jst}"


def mode_digest(
    conn: sqlite3.Connection,
    max_digest_items: int,
    webhook_digest: str,
    tz_name: str,
    timeout: int,
    digest_kind: str = "morning",
    dry_run: bool = False,
) -> None:
    if not webhook_digest:
        print("Missing DISCORD_WEBHOOK_DIGEST (or DISCORD_WEBHOOK). Skipping digest.")
        return
    start_utc, end_utc, range_and_date = jst_window(datetime.now(timezone.utc), tz_name, digest_kind)
    range_str, date_jst = range_and_date.split("|")
    try:
        cur = conn.execute(
            """
            SELECT url, host, ja_bullets, tags FROM articles
            WHERE created_at >= ? AND created_at < ?
              AND (digest_date_jst IS NULL OR digest_date_jst = '')
            ORDER BY created_at ASC
            """,
            (
                start_utc.isoformat(timespec="seconds"),
                end_utc.isoformat(timespec="seconds"),
            ),
        )
        rows = cur.fetchall()
    except Exception as e:
        print(f"DB query error for digest: {e}")
        rows = []

    if not rows:
        print("No digest items.")
        return

    blocks = []
    urls = []
    for r in rows[:max_digest_items]:
        url, host, bullets, tags_s = r
        tags = tags_s.split() if tags_s else []
        blocks.append(build_digest_block(bullets, url, tags))
        urls.append(url)

    header = f"【FXニュースまとめ】本文要約（日本語） / {range_str}"
    msg, used = _pack_blocks_to_limit(header, blocks, limit=DISCORD_LIMIT)
    if used <= 0:
        print("No digest items.")
        return

    if dry_run:
        print(f"[DRY-RUN] ダイジェスト投稿:\n{msg}")
    else:
        ok = post_to_discord(msg, webhook_digest, timeout=timeout)
        if ok:
            for u in urls[:used]:
                mark_digest_date(conn, u, date_jst)


def mode_once(
    conn: sqlite3.Connection,
    feeds: List[str],
    direct_urls: List[str],
    max_items: int,
    model_name: str,
    openai_key: Optional[str],
    deepl_key: Optional[str],
    webhook_default: str,
    timeout: int,
    dry_run: bool = False,
) -> None:
    candidates: List[dict] = []
    for fu in feeds:
        items = _collect_feed_items(fu, timeout=timeout)
        candidates.extend(items)
    for u in direct_urls:
        candidates.append({"url": u, "summary": "", "title": ""})

    seen_urls: set[str] = set()
    uniq = []
    for it in candidates:
        u = (it.get("url") or "").strip()
        if not u or u in seen_urls:
            continue
        seen_urls.add(u)
        uniq.append(it)

    prepared: List[str] = []
    used_urls: List[str] = []
    count = 0
    for it in uniq:
        if count >= max_items:
            break
        url = it.get("url", "")
        summary_hint = it.get("summary", "")
        title_hint = it.get("title", "")
        if not url or is_seen(conn, url):
            continue
        pa = process_candidate(url, summary_hint, model_name, openai_key, deepl_key, timeout=timeout)
        if not pa:
            continue
        block = build_digest_block(pa.bullets, pa.url, pa.tags)
        prepared.append(block)
        used_urls.append(url)
        upsert_article(
            conn,
            url=url,
            host=pa.host,
            title_hint=title_hint,
            summary_hint=summary_hint,
            body_excerpt=pa.bullets.replace("\n", " ")[:400],
            ja_bullets=pa.bullets,
            tags=" ".join(pa.tags),
            score=pa.score,
        )
        ensure_seen(conn, url)
        count += 1

    if not prepared:
        print("No new items.")
        return
    header = "【FXニュースまとめ】本文要約（日本語）"
    msg, used = _pack_blocks_to_limit(header, prepared, limit=DISCORD_LIMIT)
    if used <= 0:
        print("No new items.")
        return
    if dry_run:
        print(f"[DRY-RUN] ワンス投稿:\n{msg}")
    elif webhook_default:
        ok = post_to_discord(msg, webhook_default, timeout=timeout)
        if not ok:
            print("Failed to post to Discord.")
    else:
        print(msg)


def main():
    load_env()
    parser = argparse.ArgumentParser(description="FX news fetcher: alert and digest modes")
    parser.add_argument("--mode", choices=["fetch-alert", "digest", "once"], default="fetch-alert")
    parser.add_argument("--max-items", type=int, default=20, help="Max items to process in fetch/once")
    parser.add_argument("--max-digest-items", type=int, default=20)
    parser.add_argument("--digest-kind", choices=["morning", "day"], default="morning", 
                        help="Digest time window: morning (prev 6:00-today 6:00) or day (today 0:00-now)")
    parser.add_argument("--feed", action="append")
    parser.add_argument("--feeds-file", help="File containing RSS feeds (one per line)")
    parser.add_argument("--url", action="append")
    parser.add_argument("--urls")
    parser.add_argument("--db", default="seen_news.db")
    parser.add_argument("--webhook")
    parser.add_argument("--webhook-alerts")
    parser.add_argument("--webhook-digest")
    parser.add_argument("--model-name", default=MODEL_NAME)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--tz", default=os.getenv("TIMEZONE", "Asia/Tokyo"))
    parser.add_argument("--dry-run", action="store_true", help="Show output without posting to Discord")
    parser.add_argument("--lock", help="Lock file path to prevent concurrent execution")

    args = parser.parse_args()

    # ファイルロック処理（重複起動防止）
    lock_file = None
    if args.lock:
        try:
            lock_file = open(args.lock, 'w')
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            def cleanup_lock():
                if lock_file:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                    try:
                        os.remove(args.lock)
                    except:
                        pass
            
            atexit.register(cleanup_lock)
            lock_file.write(str(os.getpid()))
            lock_file.flush()
        except (IOError, OSError) as e:
            print(f"❌ ロック取得失敗: {e}")
            print(f"   別のプロセスが実行中の可能性があります: {args.lock}")
            sys.exit(1)

    if requests is None:
        print("Missing required dependency: requests. Install via: python3 -m pip install --user -r requirements.txt")
        sys.exit(1)
    if feedparser is None:
        print("Notice: 'feedparser' not installed. Falling back to basic XML parsing.")
    if BeautifulSoup is None:
        print("Notice: 'beautifulsoup4' not installed. Basic HTML text extraction will be used.")
    if Document is None:
        print("Notice: 'readability-lxml' not installed. Main content extraction quality may be reduced.")
    if tldextract is None:
        print("Notice: 'tldextract' not installed. Host extraction will be basic.")

    # フィード収集: --feed, --feeds-file, DEFAULT_FEEDS から合算・重複排除
    feeds = []
    if args.feed:
        feeds.extend(args.feed)
    
    # feeds.txtからの読み込み
    if args.feeds_file:
        try:
            with open(args.feeds_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # 空行と # から始まる行は無視
                    if line and not line.startswith("#"):
                        feeds.append(line)
        except Exception as e:
            print(f"Failed to read feeds file {args.feeds_file}: {e}")
    
    # デフォルトフィードを追加（何も指定されていない場合）
    if not feeds:
        feeds = DEFAULT_FEEDS
    
    # 重複排除
    feeds = list(dict.fromkeys(feeds))
    direct_urls = args.url or []
    if args.urls:
        try:
            with open(args.urls, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u:
                        direct_urls.append(u)
        except Exception as e:
            print(f"Failed to read urls file {args.urls}: {e}")

    base, alerts, digest = _get_env_webhooks(args)
    conn = init_db(args.db)
    openai_key = os.getenv("OPENAI_API_KEY")
    deepl_key = os.getenv("DEEPL_API_KEY")

    try:
        if args.mode == "fetch-alert":
            mode_fetch_alert(
                conn,
                feeds=feeds,
                direct_urls=direct_urls,
                max_items=args.max_items,
                model_name=args.model_name,
                openai_key=openai_key,
                deepl_key=deepl_key,
                webhook_alerts=alerts or base,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
        elif args.mode == "digest":
            mode_digest(
                conn,
                max_digest_items=args.max_digest_items,
                webhook_digest=digest or base,
                tz_name=args.tz,
                timeout=args.timeout,
                digest_kind=args.digest_kind,
                dry_run=args.dry_run,
            )
        else:  # once
            mode_once(
                conn,
                feeds=feeds,
                direct_urls=direct_urls,
                max_items=args.max_items,
                model_name=args.model_name,
                openai_key=openai_key,
                deepl_key=deepl_key,
                webhook_default=base,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
    except Exception as e:
        print(f"Fatal error: {e}")


if __name__ == "__main__":
    main()

