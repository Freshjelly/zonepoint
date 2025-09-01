import feedparser, hashlib, time, sqlite3, os
from urllib.parse import urlparse
from typing import List, Dict

FEEDS = [
  "https://www.boj.or.jp/en/rss/whatsnew.xml",
  "https://www.federalreserve.gov/feeds/press_all.xml",
  "https://www.ecb.europa.eu/rss/press.html",
  "https://www.fxstreet.com/rss/news",
  "https://www.dailyforex.com/rss",
]

DB_PATH = "data/seen_urls.sqlite"

def _db():
    os.makedirs("data", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY, ts INTEGER)")
    return con

def _fp(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def pull_latest(max_items=100) -> List[Dict]:
    items = []
    for f in FEEDS:
        d = feedparser.parse(f)
        for e in d.entries[:max_items]:
            link = getattr(e, "link", "") or ""
            title = getattr(e, "title", "") or ""
            summ  = getattr(e, "summary", "") or ""
            published = getattr(e, "published", "") or ""
            items.append({
                "id": _fp(link or title),
                "source": urlparse(f).netloc,
                "title": title,
                "summary": summ,
                "link": link,
                "published": published
            })
    con = _db()
    fresh = []
    with con:
        for it in items:
            try:
                con.execute("INSERT INTO seen(id, ts) VALUES(?,?)", (it["id"], int(time.time())))
                fresh.append(it)
            except sqlite3.IntegrityError:
                pass
    return fresh