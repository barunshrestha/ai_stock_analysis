"""Backend configuration sourced from environment variables (.env)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_ANALYSIS_MODEL = os.getenv("OLLAMA_ANALYSIS_MODEL", "gemma3:4b")

# Next.js dev servers; extend via CORS_ORIGINS env (comma-separated) for prod.
# 3002 is the pinned frontend dev port (3000/3001 are taken on this machine).
_default_origins = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:3002,http://127.0.0.1:3002"
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

# Cache TTLs in seconds (PRD section 7).
TTL_QUOTE = 60
TTL_HISTORY = 15 * 60
TTL_FUNDAMENTALS = 24 * 60 * 60
TTL_SEARCH = 60 * 60
TTL_NEWS = 15 * 60
TTL_NEWS_PORTFOLIO = 5 * 60
TTL_NEWS_CALENDAR = 60 * 60

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# RSS feeds grouped by dashboard category. Add URLs here without code changes.
NEWS_RSS_FEEDS: dict[str, list[tuple[str, str]]] = {
    # (source_label, feed_url)
    "markets": [
        ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
        ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
        ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/marketpulse/"),
    ],
    "economy": [
        ("AP News", "https://feeds.apnews.com/apf-business"),
        ("BEA", "https://www.bea.gov/news/rss.xml"),
    ],
    "fed": [
        ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
        ("BLS", "https://www.bls.gov/feed/bls_latest.rss"),
    ],
    "policy": [
        ("Politico", "https://rss.politico.com/economy.xml"),
    ],
}

EARNINGS_KEYWORDS = (
    "earnings",
    "ipo",
    "s-1",
    "guidance",
    "quarterly results",
    "beats estimates",
    "misses estimates",
    "initial public offering",
)
