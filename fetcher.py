import hashlib
import html
import json
import math
import os
import re
import sqlite3
import time
from calendar import timegm
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("NEWS_DB_PATH", PROJECT_DIR / "news.db"))
USER_AGENT = "personal-news-research-agent/1.0"


FEEDS = {
    "AI & Big Tech": [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
        "https://feeds.feedburner.com/venturebeat/SZYF",
        "https://openai.com/news/rss.xml",
        "https://blog.google/technology/ai/rss/",
        "https://www.wired.com/feed/tag/artificial-intelligence/rss",
    ],
    "Geopolitics & Military": [
        "https://feeds.reuters.com/reuters/worldNews",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.defensenews.com/arc/outboundfeeds/rss/",
        "https://warontherocks.com/feed/",
        "https://foreignpolicy.com/feed/",
    ],
    "India & Indian Politics": [
        "https://www.thehindu.com/news/national/feeder/default.rss",
        "https://indianexpress.com/feed/",
        "https://feeds.feedburner.com/ndtvnews-india-news",
        "https://www.livemint.com/rss/politics",
        "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",
        "https://www.thehindu.com/news/national/kerala/feeder/default.rss",
    ],
    "Social Media": [
        "https://techcrunch.com/category/social/feed/",
        "https://www.theverge.com/social-media/rss/index.xml",
        "https://www.wired.com/feed/tag/social-media/rss",
        "https://mashable.com/feeds/rss/tech",
    ],
    "Major Economy Events": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://www.ft.com/?format=rss",
        "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
    ],
}


SEARCH_LOCALES = {
    "global": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "india": {"hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
    "uk": {"hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
    "europe": {"hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
    "middle_east": {"hl": "en-AE", "gl": "AE", "ceid": "AE:en"},
    "asia": {"hl": "en-SG", "gl": "SG", "ceid": "SG:en"},
}


SEARCH_PROFILES = {
    "AI & Big Tech": [
        '"artificial intelligence" OR "AI model" OR OpenAI OR Anthropic OR DeepMind',
        '"AI regulation" OR "AI safety" OR "frontier model"',
        '"Microsoft AI" OR "Google AI" OR "Meta AI" OR "Apple AI"',
    ],
    "Geopolitics & Military": [
        'war OR conflict OR sanctions OR ceasefire OR "peace talks"',
        '"defense deal" OR missile OR drone OR military OR navy',
        '"United Nations" OR NATO OR "South China Sea" OR "Middle East"',
    ],
    "India & Indian Politics": [
        'India government OR parliament OR "Supreme Court" OR election',
        '"Modi government" OR BJP OR Congress OR "foreign policy"',
        '"Reserve Bank of India" OR RBI OR "Indian economy"',
    ],
    "Social Media": [
        '"social media" OR TikTok OR Instagram OR YouTube OR "X platform"',
        '"content moderation" OR "online safety" OR "platform regulation"',
        '"creator economy" OR "short video" OR "viral trend"',
    ],
    "Major Economy Events": [
        '"interest rates" OR inflation OR recession OR "central bank"',
        '"stock market" OR "bond yields" OR "oil prices" OR "trade war"',
        '"Federal Reserve" OR ECB OR RBI OR "Bank of Japan"',
    ],
}


IMPACT_KEYWORDS = {
    "AI & Big Tech": [
        "launch",
        "release",
        "model",
        "benchmark",
        "safety",
        "regulation",
        "lawsuit",
        "partnership",
        "chips",
        "data center",
    ],
    "Geopolitics & Military": [
        "war",
        "attack",
        "ceasefire",
        "sanctions",
        "missile",
        "drone",
        "nato",
        "treaty",
        "border",
        "defense",
    ],
    "India & Indian Politics": [
        "election",
        "parliament",
        "supreme court",
        "cabinet",
        "policy",
        "rbi",
        "budget",
        "state",
        "modi",
        "opposition",
    ],
    "Social Media": [
        "ban",
        "regulation",
        "algorithm",
        "creator",
        "advertising",
        "privacy",
        "lawsuit",
        "moderation",
        "users",
        "platform",
    ],
    "Major Economy Events": [
        "inflation",
        "rates",
        "central bank",
        "recession",
        "market",
        "crash",
        "rally",
        "tariff",
        "oil",
        "currency",
    ],
}


HIGH_SIGNAL_SOURCES = [
    "reuters",
    "associated press",
    "ap news",
    "bbc",
    "financial times",
    "bloomberg",
    "wall street journal",
    "new york times",
    "the hindu",
    "indian express",
    "the verge",
    "techcrunch",
    "wired",
]


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                summary TEXT,
                category TEXT NOT NULL,
                source TEXT,
                published_at TEXT,
                fetched_at TEXT NOT NULL,
                discovery_method TEXT DEFAULT 'rss',
                search_query TEXT,
                region TEXT,
                research_score REAL DEFAULT 0,
                used INTEGER DEFAULT 0
            )
            """
        )
        ensure_column(conn, "articles", "published_at", "TEXT")
        ensure_column(conn, "articles", "discovery_method", "TEXT DEFAULT 'rss'")
        ensure_column(conn, "articles", "search_query", "TEXT")
        ensure_column(conn, "articles", "region", "TEXT")
        ensure_column(conn, "articles", "research_score", "REAL DEFAULT 0")


def ensure_column(conn, table, column, column_type):
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def article_hash(url):
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def clean_text(value, max_len=500):
    if not value:
        return ""
    text = re.sub(r"<[^<]+?>", "", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def score_article(title, summary, category, source, published_at=None, discovery_method="rss"):
    text = f"{title} {summary}".lower()
    source_text = (source or "").lower()
    score = 10.0

    keyword_hits = sum(1 for keyword in IMPACT_KEYWORDS.get(category, []) if keyword in text)
    score += min(keyword_hits * 4, 28)

    if any(source_name in source_text for source_name in HIGH_SIGNAL_SOURCES):
        score += 14

    if discovery_method == "gdelt":
        score += 8
    elif discovery_method == "google_news":
        score += 5

    published = parse_iso_datetime(published_at)
    if published:
        age_hours = max((datetime.utcnow() - published).total_seconds() / 3600, 0)
        if age_hours <= 6:
            score += 18
        elif age_hours <= 24:
            score += 12
        elif age_hours <= 72:
            score += 6

    global_terms = [
        "breaking",
        "exclusive",
        "announces",
        "confirmed",
        "global",
        "international",
        "investigation",
        "emergency",
        "crisis",
        "record",
    ]
    score += min(sum(1 for term in global_terms if term in text) * 2, 10)

    return round(score, 2)


def entry_datetime(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.utcfromtimestamp(timegm(parsed)).isoformat()


def save_article(
    title,
    url,
    summary,
    category,
    source,
    published_at=None,
    discovery_method="rss",
    search_query=None,
    region=None,
):
    init_db()
    aid = article_hash(url)
    cleaned_title = clean_text(title, max_len=300)
    cleaned_summary = clean_text(summary)
    research_score = score_article(
        cleaned_title,
        cleaned_summary,
        category,
        source,
        published_at=published_at,
        discovery_method=discovery_method,
    )
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO articles
                (
                    id, title, url, summary, category, source, published_at, fetched_at,
                    discovery_method, search_query, region, research_score
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                aid,
                cleaned_title,
                url.strip(),
                cleaned_summary,
                category,
                source,
                published_at,
                datetime.now().isoformat(),
                discovery_method,
                search_query,
                region,
                research_score,
            ),
        )
        return cursor.rowcount == 1


def get_articles(hours=24, category=None, unused_only=False, limit=None, order_by="score"):
    init_db()
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    filters = ["fetched_at > ?"]
    params = [since]

    if category:
        filters.append("category = ?")
        params.append(category)
    if unused_only:
        filters.append("used = 0")

    query = f"""
        SELECT
            title, url, summary, category, source, published_at, fetched_at,
            discovery_method, search_query, region, research_score, used
        FROM articles
        WHERE {" AND ".join(filters)}
    """
    if order_by == "recent":
        query += " ORDER BY COALESCE(published_at, fetched_at) DESC"
    else:
        query += " ORDER BY research_score DESC, COALESCE(published_at, fetched_at) DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def get_todays_articles():
    rows = get_articles(hours=24, unused_only=True)
    return [
        (row["title"], row["url"], row["summary"], row["category"], row["source"])
        for row in rows
    ]


def mark_used(urls):
    init_db()
    with get_connection() as conn:
        conn.executemany("UPDATE articles SET used = 1 WHERE url = ?", [(url,) for url in urls])


def get_stats():
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                category,
                COUNT(*) AS total,
                SUM(CASE WHEN used = 0 THEN 1 ELSE 0 END) AS unused,
                ROUND(AVG(research_score), 1) AS avg_score
            FROM articles
            GROUP BY category
            ORDER BY category
            """
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS count FROM articles").fetchone()["count"]
    return total, rows


def fetch_feed(category, feed_url, max_per_feed=10):
    try:
        import feedparser
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'feedparser'. Install dependencies with: pip install -r requirements.txt"
        ) from exc

    feed = feedparser.parse(feed_url)
    source = feed.feed.get("title", feed_url)
    inserted = 0

    for entry in feed.entries[:max_per_feed]:
        title = entry.get("title", "").strip()
        url = entry.get("link", "").strip()
        summary = entry.get("summary", entry.get("description", "")).strip()
        if not title or not url:
            continue

        if save_article(title, url, summary, category, source, entry_datetime(entry)):
            inserted += 1

    return inserted, len(feed.entries[:max_per_feed]), source


def google_news_url(query, region="global"):
    locale = SEARCH_LOCALES.get(region, SEARCH_LOCALES["global"])
    encoded_query = quote_plus(query)
    return (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}&hl={locale['hl']}&gl={locale['gl']}&ceid={locale['ceid']}"
    )


def search_google_news(category, query, region="global", max_records=20):
    try:
        import feedparser
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'feedparser'. Install dependencies with: pip install -r requirements.txt"
        ) from exc

    feed_url = google_news_url(query, region=region)
    feed = feedparser.parse(feed_url)
    inserted = 0

    for entry in feed.entries[:max_records]:
        title = entry.get("title", "").strip()
        url = entry.get("link", "").strip()
        summary = entry.get("summary", entry.get("description", "")).strip()
        if not title or not url:
            continue
        source = entry.get("source", {}).get("title") or "Google News"
        if save_article(
            title,
            url,
            summary,
            category,
            source,
            entry_datetime(entry),
            discovery_method="google_news",
            search_query=query,
            region=region,
        ):
            inserted += 1

    return inserted, len(feed.entries[:max_records]), f"Google News ({region})"


def gdelt_timespan(hours):
    days = max(1, math.ceil(hours / 24))
    return f"{days}d"


def search_gdelt(category, query, hours=24, max_records=50):
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'requests'. Install dependencies with: pip install -r requirements.txt"
        ) from exc

    response = requests.get(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        params={
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": max_records,
            "sort": "HybridRel",
            "timespan": gdelt_timespan(hours),
        },
        headers={"User-Agent": USER_AGENT},
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    articles = payload.get("articles", [])
    inserted = 0

    for article in articles:
        title = article.get("title", "").strip()
        url = article.get("url", "").strip()
        if not title or not url:
            continue
        summary = article.get("seendate", "")
        source = article.get("sourceCommonName") or article.get("domain") or "GDELT"
        published_at = gdelt_seen_date(article.get("seendate"))
        region = article.get("sourceCountry") or article.get("language") or "global"
        if save_article(
            title,
            url,
            summary,
            category,
            source,
            published_at,
            discovery_method="gdelt",
            search_query=query,
            region=region,
        ):
            inserted += 1

    return inserted, len(articles), "GDELT"


def gdelt_seen_date(value):
    if not value:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).isoformat()
        except ValueError:
            continue
    return None


def search_global(
    categories=None,
    providers=None,
    regions=None,
    hours=24,
    max_records=20,
    pause_seconds=0.5,
):
    init_db()
    categories = categories or list(SEARCH_PROFILES.keys())
    providers = providers or ["gdelt", "google_news"]
    regions = regions or ["global", "india", "uk", "asia"]
    total_inserted = 0

    for category in categories:
        print(f"\n{category}")
        for query in SEARCH_PROFILES.get(category, []):
            if "gdelt" in providers:
                try:
                    inserted, seen, source = search_gdelt(
                        category,
                        query,
                        hours=hours,
                        max_records=max_records,
                    )
                    total_inserted += inserted
                    print(f"  + {inserted:02d} new / {seen:02d} checked - {source}: {query}")
                    time.sleep(pause_seconds)
                except Exception as exc:
                    print(f"  ! GDELT failed for {query}: {exc}")

            if "google_news" in providers:
                for region in regions:
                    try:
                        inserted, seen, source = search_google_news(
                            category,
                            query,
                            region=region,
                            max_records=max_records,
                        )
                        total_inserted += inserted
                        print(f"  + {inserted:02d} new / {seen:02d} checked - {source}: {query}")
                        time.sleep(pause_seconds)
                    except Exception as exc:
                        print(f"  ! Google News failed for {query} [{region}]: {exc}")

    print(f"\nDiscovered {total_inserted} new global-search articles into {DB_PATH}")
    return total_inserted


def fetch_all(max_per_feed=10, pause_seconds=0.5):
    init_db()
    total_inserted = 0

    for category, feeds in FEEDS.items():
        category_inserted = 0
        print(f"\n{category}")
        for feed_url in feeds:
            try:
                inserted, seen, source = fetch_feed(category, feed_url, max_per_feed=max_per_feed)
                category_inserted += inserted
                total_inserted += inserted
                print(f"  + {inserted:02d} new / {seen:02d} checked - {source}")
                time.sleep(pause_seconds)
            except Exception as exc:
                print(f"  ! Failed {feed_url}: {exc}")
        print(f"  = {category_inserted} new articles")

    print(f"\nFetched {total_inserted} new articles into {DB_PATH}")
    return total_inserted


if __name__ == "__main__":
    fetch_all()
