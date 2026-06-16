"""
Shared Yahoo Finance session helpers.

Yahoo started blocking the default `requests`/`urllib` user agent that
`yfinance` ships with on cloud and many residential IPs (HTTP 401/429,
empty `info` payloads, etc.). Routing every request through a
`curl_cffi` session that impersonates a real Chrome browser (TLS
fingerprint + headers) bypasses that block.

Centralizing the session and Ticker factory here avoids duplicating
setup at every call site and ensures a single shared connection pool /
cookie jar per process.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Callable, TypeVar

import pandas as pd
import yfinance as yf
from curl_cffi import requests as cf_requests

T = TypeVar("T")

# Browser fingerprints supported by curl_cffi. We try them in order if
# Yahoo starts rejecting one of them; "chrome" is the moving alias for
# the latest stable Chrome impersonation profile.
_DEFAULT_IMPERSONATE = "chrome"


@lru_cache(maxsize=1)
def get_yahoo_session():
    """Return a process-wide curl_cffi session impersonating Chrome.

    Cached so the cookie jar and HTTP connection pool are reused across
    every Ticker call, which both improves latency and reduces the
    chance of being flagged as a bot.
    """
    return cf_requests.Session(impersonate=_DEFAULT_IMPERSONATE)


def get_ticker(symbol: str) -> yf.Ticker:
    """Return a `yf.Ticker` bound to the shared impersonation session."""
    return yf.Ticker(symbol, session=get_yahoo_session())


def with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
) -> T:
    """Run `fn` with exponential backoff for transient Yahoo errors.

    Only retries on errors that look transient (rate limiting, timeouts,
    connection issues, 5xx). Non-transient errors (e.g. invalid symbol)
    are re-raised immediately so callers see them on the first try.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            msg = str(exc).lower()
            transient = any(
                marker in msg
                for marker in ("429", "rate", "timeout", "timed out", "connection", "5xx", "503", "502", "500")
            )
            if attempt == attempts - 1 or not transient:
                raise
            time.sleep(base_delay * (2 ** attempt))
    # Defensive: loop above either returns or raises. This line is
    # unreachable but keeps type checkers happy.
    assert last_exc is not None
    raise last_exc


# Preferred Net Income row labels, ordered from most specific to most
# generic. yfinance 1.x exposes several variants; we take the first that
# exists in `income_stmt`.
_NET_INCOME_ROWS: tuple[str, ...] = (
    "Net Income",
    "Net Income Common Stockholders",
    "Net Income Continuous Operations",
    "Net Income From Continuing Operation Net Minority Interest",
    "Net Income Including Noncontrolling Interests",
)


def get_earnings_history(ticker: yf.Ticker, years: int = 5) -> pd.DataFrame | None:
    """Return the last `years` of Net Income as an `'Earnings'`-shaped DataFrame.

    yfinance 1.x deprecated and removed `Ticker.earnings`. To preserve
    the downstream chart contract (`index=year, columns=['Earnings']`),
    we pull the "Net Income" row from `ticker.income_stmt` and reshape
    it. Returns None if the income statement is unavailable.
    """
    try:
        income_stmt = ticker.income_stmt
    except Exception:
        return None
    if income_stmt is None or income_stmt.empty:
        return None

    # Find the first available Net Income row by preference order.
    row: pd.Series | None = None
    for label in _NET_INCOME_ROWS:
        if label in income_stmt.index:
            candidate = income_stmt.loc[label]
            if isinstance(candidate, pd.Series) and candidate.notna().any():
                row = candidate
                break
    if row is None:
        return None

    # Columns are pandas Timestamps (most recent first). Reindex by
    # calendar year so the downstream chart can label bars correctly.
    earnings = pd.DataFrame({"Earnings": row.values}, index=[ts.year for ts in row.index])
    earnings = earnings.dropna(subset=["Earnings"]).sort_index()
    if earnings.empty:
        return None
    return earnings.tail(years)
