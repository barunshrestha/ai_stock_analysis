"""News aggregation: RSS feeds and Yahoo portfolio news."""

from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
from curl_cffi import requests as cf_requests

from backend.cache import ttl_cache
from backend.config import (
    EARNINGS_KEYWORDS,
    NEWS_RSS_FEEDS,
    TTL_NEWS,
    TTL_NEWS_PORTFOLIO,
)
from yahoo_session import get_ticker, with_retry

_SESSION = cf_requests.Session(impersonate="chrome")

VALID_CATEGORIES = ("top", "markets", "economy", "fed", "policy", "earnings")


def _parse_published(entry: Any) -> str | None:
    """Return ISO-8601 UTC string from an RSS entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except (TypeError, ValueError):
                pass
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError):
                pass
    return None


def _item_id(url: str, title: str) -> str:
    key = url or title
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _normalize_entry(
    entry: Any,
    *,
    source: str,
    category: str,
    symbols: list[str] | None = None,
) -> dict | None:
    title = (getattr(entry, "title", None) or "").strip()
    if not title:
        return None
    url = getattr(entry, "link", None) or ""
    if not url and getattr(entry, "links", None):
        url = entry.links[0].get("href", "")
    summary = getattr(entry, "summary", None) or getattr(entry, "description", None) or ""
    summary = re.sub(r"<[^>]+>", "", summary).strip()
    if len(summary) > 280:
        summary = summary[:277] + "..."
    return {
        "id": _item_id(url, title),
        "title": title,
        "url": url,
        "source": source,
        "category": category,
        "published_at": _parse_published(entry),
        "summary": summary or None,
        "symbols": symbols or [],
    }


def _fetch_rss(url: str, source: str, category: str) -> list[dict]:
    try:
        resp = _SESSION.get(url, timeout=15)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception:
        return []
    items: list[dict] = []
    for entry in parsed.entries[:30]:
        item = _normalize_entry(entry, source=source, category=category)
        if item and item["url"]:
            items.append(item)
    return items


def _dedupe_sort(items: list[dict], limit: int) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for item in sorted(
        items,
        key=lambda x: x.get("published_at") or "",
        reverse=True,
    ):
        key = item.get("url") or item.get("title", "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def _matches_earnings(item: dict) -> bool:
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    return any(kw in text for kw in EARNINGS_KEYWORDS)


@ttl_cache(TTL_NEWS)
def _fetch_all_rss() -> list[dict]:
    items: list[dict] = []
    for category, feeds in NEWS_RSS_FEEDS.items():
        for source, url in feeds:
            items.extend(_fetch_rss(url, source, category))
    return items


def get_news_by_category(category: str, limit: int = 40) -> list[dict]:
    if category not in VALID_CATEGORIES:
        category = "top"
    all_items = _fetch_all_rss()
    if category == "top":
        return _dedupe_sort(all_items, limit)
    if category == "earnings":
        earnings = [i for i in all_items if _matches_earnings(i)]
        return _dedupe_sort(earnings, limit)
    filtered = [i for i in all_items if i["category"] == category]
    return _dedupe_sort(filtered, limit)


def _yahoo_news_for_symbol(symbol: str, limit: int = 3) -> list[dict]:
    try:
        ticker = get_ticker(symbol)
        raw = with_retry(lambda: getattr(ticker, "news", None) or [], attempts=2)
    except Exception:
        return []
    items: list[dict] = []
    for article in raw[:limit]:
        # yfinance 1.x nests fields under content; older shape is flat.
        content = article.get("content") if isinstance(article.get("content"), dict) else article
        title = (content.get("title") or "").strip()
        if not title:
            continue
        url = ""
        for key in ("clickThroughUrl", "canonicalUrl"):
            link_obj = content.get(key)
            if isinstance(link_obj, dict) and link_obj.get("url"):
                url = link_obj["url"]
                break
        if not url:
            url = content.get("link") or content.get("url") or article.get("link") or ""
        published = content.get("pubDate") or content.get("displayTime")
        if not published:
            ts = content.get("providerPublishTime") or article.get("providerPublishTime")
            if ts:
                published = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        provider = content.get("provider") or {}
        publisher = (
            provider.get("displayName")
            if isinstance(provider, dict)
            else None
        ) or content.get("publisher") or "Yahoo Finance"
        summary = content.get("summary") or content.get("description") or None
        items.append(
            {
                "id": _item_id(url, title),
                "title": title,
                "url": url,
                "source": publisher,
                "category": "earnings" if _matches_earnings({"title": title}) else "markets",
                "published_at": published,
                "summary": summary,
                "symbols": [symbol],
            }
        )
    return items


@ttl_cache(TTL_NEWS_PORTFOLIO)
def _get_portfolio_news_cached(symbols_key: tuple[str, ...]) -> list[dict]:
    if not symbols_key:
        return []
    items: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(8, len(symbols_key))) as pool:
        futures = {
            pool.submit(_yahoo_news_for_symbol, s): s for s in symbols_key[:20]
        }
        for fut in as_completed(futures):
            try:
                items.extend(fut.result())
            except Exception:
                pass
    return _dedupe_sort(items, limit=60)


def get_portfolio_news(symbols: list[str]) -> list[dict]:
    key = tuple(sorted(s.upper() for s in symbols if s.strip()))
    return _get_portfolio_news_cached(key)
