"""Backend configuration sourced from environment variables (.env)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")
OLLAMA_ANALYSIS_MODEL = os.getenv("OLLAMA_ANALYSIS_MODEL", "deepseek-r1:latest")
# Keep context modest — default Ollama num_ctx can be huge and stalls CPU inference.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

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
TTL_MARKET_CONTEXT = 5 * 60
TTL_OPTIONS_CHAIN = 60
TTL_OPTIONS_MONITOR = 60

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# Gemini (Issue #6 Wall Street–style research memo)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Pre-trade analysis thresholds
PRETRADE_DTE_GOOD_MIN = int(os.getenv("PRETRADE_DTE_GOOD_MIN", "30"))
PRETRADE_DTE_GOOD_MAX = int(os.getenv("PRETRADE_DTE_GOOD_MAX", "45"))
PRETRADE_DTE_CAUTION = int(os.getenv("PRETRADE_DTE_CAUTION", "14"))
PRETRADE_ANNUALIZED_ROC_GOOD = float(os.getenv("PRETRADE_ANNUALIZED_ROC_GOOD", "20"))
PRETRADE_OTM_PCT_GOOD = float(os.getenv("PRETRADE_OTM_PCT_GOOD", "5"))
PRETRADE_OTM_PCT_CAUTION = float(os.getenv("PRETRADE_OTM_PCT_CAUTION", "2"))

# CSP screening (Issue #2)
CSP_DTE_MIN = int(os.getenv("CSP_DTE_MIN", "30"))
CSP_DTE_MAX = int(os.getenv("CSP_DTE_MAX", "45"))
CSP_TARGET_DELTA = float(os.getenv("CSP_TARGET_DELTA", "0.30"))
CSP_EVENT_HORIZON_DAYS = int(os.getenv("CSP_EVENT_HORIZON_DAYS", "45"))
CSP_OTM_PCT_GOOD = float(os.getenv("CSP_OTM_PCT_GOOD", "5"))
CSP_IV_REALIZED_MIN_RATIO = float(os.getenv("CSP_IV_REALIZED_MIN_RATIO", "1.0"))
CSP_SPREAD_PCT_MAX = float(os.getenv("CSP_SPREAD_PCT_MAX", "10"))
CSP_MIN_OPEN_INTEREST = int(os.getenv("CSP_MIN_OPEN_INTEREST", "50"))
CSP_BREACH_PCT = float(os.getenv("CSP_BREACH_PCT", "3"))
CSP_RISK_FREE_RATE = float(os.getenv("CSP_RISK_FREE_RATE", "0.05"))

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
