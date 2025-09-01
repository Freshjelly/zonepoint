#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from typing import List, Optional, Tuple

# Optional/External deps are imported lazily with fallbacks
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
    def detect(_text: str) -> str:  # fallback: unknown
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

DEFAULT_MODEL_NAME = "gpt-4o-mini"


def load_env():
    try:
        if _load_dotenv:
            _load_dotenv()
    except Exception:
        pass


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def init_db(db_path: str):
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
    conn.commit()
    return conn


def is_seen(conn: sqlite3.Connection, url: str) -> bool:
    try:
        h = sha1(url)
        cur = conn.execute("SELECT 1 FROM seen WHERE url_sha1=?", (h,))
        return cur.fetchone() is not None
    except Exception:
        return False


def mark_seen(conn: sqlite3.Connection, url: str):
    try:
        h = sha1(url)
        conn.execute(
            "INSERT OR IGNORE INTO seen(url_sha1, url, seen_at) VALUES (?, ?, ?)",
            (h, url, datetime.utcnow().isoformat(timespec="seconds") + "Z"),
        )
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
            # Minimal regex-based extraction as last resort
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
        # Remove scripts/styles
        html = _re.sub(r"<script[\s\S]*?</script>", " ", html, flags=_re.I)
        html = _re.sub(r"<style[\s\S]*?</style>", " ", html, flags=_re.I)
        # Replace block tags with newlines for readability
        html = _re.sub(r"</?(p|div|br|li|ul|ol|h\d)[^>]*>", "\n", html, flags=_re.I)
        # Strip remaining tags
        text = _re.sub(r"<[^>]+>", " ", html)
        # Collapse whitespace
        text = _re.sub(r"\s+", " ", text)
        return text.strip()
    except Exception:
        return ""


def extract_main_text(html: str) -> str:
    # readability + bs4 path
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
    # Fallback to meta description or basic text
    meta = _fallback_meta_description(html)
    if meta:
        return meta
    # As a last resort, strip tags from the whole page
    return _html_to_text_basic(html)


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


def re_search(pattern: str, text: str) -> bool:
    import re

    return re.search(pattern, text) is not None


def _split_sentences(text: str) -> List[str]:
    import re

    if not text:
        return []
    # Normalize whitespace
    t = re.sub(r"[\t\r]+", " ", text)
    # Japanese split by 。！？
    ja_parts = re.split(r"(?<=[。！？])\s+", t)
    # English-like split by .!? when followed by space and capital/lower
    en_parts = []
    for p in ja_parts:
        en_parts.extend(re.split(r"(?<=[\.!?])\s+", p))
    sents = [s.strip() for s in en_parts if s and len(s.strip()) > 0]
    return sents


def summarize_rule_based_ja(text: str) -> str:
    import re

    sents = _split_sentences(text)
    if not sents:
        return ""
    # Score sentences with finance-related keywords (JA + EN)
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
        # Prefer medium length sentences
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
    # Ensure 2-3 bullets
    if len(top) < 2:
        top = (top + sents)[:2]
    top = top[:3]

    bullets = []
    for s in top:
        s = re.sub(r"\s+", " ", s).strip()
        # Truncate to ~120 chars
        max_len = 120
        if len(s) > max_len:
            s = s[: max_len - 1] + "…"
        bullets.append("• " + s)
    return "\n".join(bullets)


def _openai_chat(api_key: str, model_name: str, text: str, timeout: int = 15) -> Optional[str]:
    if requests is None:
        print("OpenAI call skipped: missing 'requests' (pip install requests)")
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


def _deepl_translate(api_key: str, text: str, timeout: int = 15) -> Optional[str]:
    if requests is None:
        print("DeepL call skipped: missing 'requests' (pip install requests)")
        return None
    try:
        # Heuristic: free keys often end with ':fx' or '-free'
        host = "api.deepl.com"
        if api_key.endswith(":fx") or api_key.endswith("-free"):
            host = "api-free.deepl.com"
        url = f"https://{host}/v2/translate"
        data = {
            "auth_key": api_key,
            "text": text,
            "target_lang": "JA",
        }
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
    # Ensure 2-3 bullets
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
    # Truncate lines to ~140 to be safe
    trimmed = []
    for b in bullets:
        if len(b) > 140:
            trimmed.append(b[:139] + "…")
        else:
            trimmed.append(b)
    return "\n".join(trimmed)


def summarize_to_ja(text: str, model_name: str, openai_key: Optional[str], deepl_key: Optional[str], timeout: int = 15) -> str:
    if openai_key:
        s = summarize_llm_ja(text, model_name, openai_key, timeout=timeout)
        if s:
            return s
    # Rule-based summary then optional translation
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


def build_digest_block(summary: str, url: str, tags: List[str]) -> str:
    host = _get_host(url)
    tag_str = " ".join(tags) if tags else ""
    line2 = f"{url}  (source: {host})"
    if tag_str:
        line2 += f"  {tag_str}"
    return f"{summary}\n{line2}"


def _pack_blocks_to_limit(header: str, blocks: List[str], limit: int = 2000) -> Tuple[str, int]:
    message = header
    used = 0
    for blk in blocks:
        candidate = message + "\n\n" + blk
        if len(candidate) <= limit:
            message = candidate
            used += 1
            continue
        # If nothing added yet, try to truncate first block to fit
        if used == 0:
            available = limit - len(header) - 2
            if available > 10:  # ensure minimal room
                short = blk[: available - 1] + "…"
                message = header + "\n\n" + short
                used = 1
        break
    return message, used


def post_to_discord(message: str, webhook: str, timeout: int = 15) -> bool:
    if requests is None:
        print("Discord post skipped: missing 'requests' (pip install requests)")
        return False
    try:
        headers = {"Content-Type": "application/json"}
        payload = {"content": message}
        r = requests.post(webhook, headers=headers, data=json.dumps(payload), timeout=timeout)
        if r.status_code >= 400:
            print(f"Discord error {r.status_code}: {r.text[:500]}")
            return False
        return True
    except Exception as e:
        print(f"Discord post error: {e}")
        return False


def _read_urls_file(path: str) -> List[str]:
    urls = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                u = line.strip()
                if u:
                    urls.append(u)
    except Exception as e:
        print(f"Failed to read urls file {path}: {e}")
    return urls


def _collect_feed_items(feed_url: str, timeout: int = 15) -> List[dict]:
    items: List[dict] = []
    # Preferred: feedparser
    if feedparser is not None:
        try:
            f = feedparser.parse(feed_url)
            for e in getattr(f, 'entries', []) or []:
                link = e.get("link")
                if not link:
                    continue
                summary = e.get("summary") or e.get("description") or ""
                items.append({"url": link, "summary": summary})
            return items
        except Exception as e:
            print(f"Feed parse error (feedparser) {feed_url}: {e}")
    # Fallback: basic XML parsing
    try:
        xml_text = fetch_url(feed_url, timeout=timeout)
        if not xml_text:
            return items
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_text)
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        }
        # RSS 2.0
        for it in root.findall('.//item'):
            link = it.findtext('link') or ''
            summary = it.findtext('description') or ''
            if link:
                items.append({"url": link, "summary": summary})
        # Atom
        for it in root.findall('.//atom:entry', ns):
            link_el = it.find('atom:link', ns)
            link = ''
            if link_el is not None:
                link = link_el.attrib.get('href', '')
            if not link:
                t = it.findtext('atom:id', namespaces=ns)
                link = t or ''
            summary = (it.findtext('atom:summary', namespaces=ns) or it.findtext('atom:content', namespaces=ns) or '')
            if link:
                items.append({"url": link, "summary": summary})
    except Exception as e:
        print(f"Feed parse error (fallback) {feed_url}: {e}")
    return items


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
        if host.startswith('www.'):
            host = host[4:]
        return host or url
    except Exception:
        return url


def main():
    load_env()

    parser = argparse.ArgumentParser(description="Fetch FX news, summarize body in JA, and post to Discord.")
    parser.add_argument("--max-items", type=int, default=8)
    parser.add_argument("--feed", action="append", help="RSS/Atom feed URL (multi)")
    parser.add_argument("--url", action="append", help="Direct article URL (multi)")
    parser.add_argument("--urls", help="File with 1 URL per line")
    parser.add_argument("--db", default="seen_news.db")
    parser.add_argument("--webhook", help="Discord webhook (overrides .env)")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--timeout", type=int, default=15)

    args = parser.parse_args()

    # Dependency notices
    if requests is None:
        print("Missing required dependency: requests. Install via: python3 -m pip install --user -r requirements.txt")
        sys.exit(1)

    if feedparser is None:
        print("Notice: 'feedparser' not installed. Falling back to basic XML parsing for feeds.")
    if BeautifulSoup is None:
        print("Notice: 'beautifulsoup4' not installed. Falling back to basic HTML text extraction.")
    if Document is None:
        print("Notice: 'readability-lxml' not installed. Main content extraction quality may be reduced.")
    if tldextract is None:
        print("Notice: 'tldextract' not installed. Host name extraction will be basic.")

    webhook = args.webhook or os.getenv("DISCORD_WEBHOOK")
    if not webhook:
        print("Missing DISCORD_WEBHOOK. Set via --webhook or .env")
        sys.exit(1)

    openai_key = os.getenv("OPENAI_API_KEY")
    deepl_key = os.getenv("DEEPL_API_KEY")

    feeds = args.feed if args.feed else DEFAULT_FEEDS
    direct_urls = args.url or []
    if args.urls:
        direct_urls.extend(_read_urls_file(args.urls))

    conn = init_db(args.db)

    candidates = []
    for fu in feeds:
        items = _collect_feed_items(fu, timeout=args.timeout)
        for it in items:
            url = it["url"].strip()
            if url:
                candidates.append({"url": url, "summary": it.get("summary", "")})

    for u in direct_urls:
        u = u.strip()
        if u:
            candidates.append({"url": u, "summary": ""})

    # Deduplicate by URL
    seen_urls = set()
    uniq_candidates = []
    for it in candidates:
        u = it["url"]
        if u in seen_urls:
            continue
        seen_urls.add(u)
        uniq_candidates.append(it)

    prepared = []
    for it in uniq_candidates:
        if len(prepared) >= args.max_items:
            break
        url = it["url"]
        if is_seen(conn, url):
            continue
        html = fetch_url(url, timeout=args.timeout)
        body_text = ""
        if html:
            body_text = extract_main_text(html)
        if not body_text:
            # Fallback to RSS summary if available
            body_text = it.get("summary", "")
        if not body_text:
            # Last resort: try meta description again if html was fetched
            if html:
                body_text = _fallback_meta_description(html)
        if not body_text or len(body_text.strip()) == 0:
            continue
        try:
            summary = summarize_to_ja(
                body_text, args.model_name, openai_key, deepl_key, timeout=args.timeout
            )
        except Exception as e:
            print(f"Summarization error for {url}: {e}")
            summary = ""
        if not summary:
            continue
        try:
            tags = detect_pairs(body_text)
        except Exception:
            tags = []
        block = build_digest_block(summary, url, tags)
        prepared.append({"url": url, "block": block})

    if not prepared:
        print("No new items.")
        return

    header = "【FXニュースまとめ】本文要約（日本語）"
    blocks = [x["block"] for x in prepared]
    message, used_count = _pack_blocks_to_limit(header, blocks, limit=2000)
    if used_count <= 0:
        print("No new items.")
        return

    ok = post_to_discord(message, webhook, timeout=args.timeout)
    if not ok:
        print("Failed to post to Discord.")
        return

    # Mark only posted items as seen
    try:
        for x in prepared[:used_count]:
            mark_seen(conn, x["url"])
    except Exception:
        pass


if __name__ == "__main__":
    main()
