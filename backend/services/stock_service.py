"""Stock data service.

Wraps yahoo_session (curl_cffi impersonation + retry) and returns raw,
JSON-serializable values. Formatting is the frontend's job — unlike the
legacy Streamlit app, no pre-formatted strings are produced here.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from backend.cache import ttl_cache
from backend.config import TTL_FUNDAMENTALS, TTL_HISTORY, TTL_QUOTE, TTL_SEARCH
from yahoo_session import get_earnings_history, get_ticker, get_yahoo_session, with_retry

_YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}


def _clean(value: Any) -> Any:
    """Convert NaN/inf to None so the value is JSON-safe."""
    if value is None:
        return None
    if isinstance(value, (np.floating, np.integer)):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


@ttl_cache(TTL_SEARCH)
def search_symbols(query: str, limit: int = 8) -> list[dict]:
    """Proxy Yahoo's autosuggest endpoint through the impersonation session."""
    session = get_yahoo_session()
    resp = with_retry(
        lambda: session.get(
            _YAHOO_SEARCH_URL,
            params={
                "q": query,
                "quotesCount": limit,
                "newsCount": 0,
                "listsCount": 0,
                "enableFuzzyQuery": "false",
            },
            timeout=10,
        )
    )
    data = resp.json()
    results = []
    for quote in data.get("quotes", [])[:limit]:
        if not quote.get("symbol"):
            continue
        results.append(
            {
                "symbol": quote.get("symbol"),
                "name": quote.get("longname") or quote.get("shortname"),
                "exchange": quote.get("exchDisp") or quote.get("exchange"),
                "type": quote.get("quoteType"),
            }
        )
    return results


@ttl_cache(TTL_HISTORY)
def get_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    ticker = get_ticker(symbol)
    return with_retry(lambda: ticker.history(period=period))


@ttl_cache(TTL_QUOTE)
def get_info(symbol: str) -> dict:
    ticker = get_ticker(symbol)
    return with_retry(lambda: ticker.info)


@ttl_cache(TTL_FUNDAMENTALS)
def get_financial_statements(symbol: str) -> dict[str, pd.DataFrame | None]:
    ticker = get_ticker(symbol)
    statements: dict[str, pd.DataFrame | None] = {}
    for key, attr in (
        ("income_stmt", "income_stmt"),
        ("balance_sheet", "balance_sheet"),
        ("cash_flow", "cash_flow"),
    ):
        try:
            statements[key] = with_retry(lambda attr=attr: getattr(ticker, attr))
        except Exception:
            statements[key] = None
    return statements


@ttl_cache(TTL_FUNDAMENTALS)
def get_earnings(symbol: str, years: int = 5) -> pd.DataFrame | None:
    ticker = get_ticker(symbol)
    return with_retry(lambda: get_earnings_history(ticker, years=years))


def history_to_records(hist: pd.DataFrame) -> list[dict]:
    records = []
    for ts, row in hist.iterrows():
        records.append(
            {
                "date": ts.strftime("%Y-%m-%d"),
                "open": _clean(row.get("Open")),
                "high": _clean(row.get("High")),
                "low": _clean(row.get("Low")),
                "close": _clean(row.get("Close")),
                "volume": _clean(row.get("Volume")),
            }
        )
    return records


def statement_to_payload(df: pd.DataFrame | None) -> dict | None:
    if df is None or df.empty:
        return None
    columns = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c) for c in df.columns]
    rows = []
    for item, values in df.iterrows():
        rows.append({"item": str(item), "values": [_clean(v) for v in values]})
    return {"columns": columns, "rows": rows}


def _pct_change(close: pd.Series, periods_back: int) -> float | None:
    if len(close) <= periods_back:
        return None
    past = close.iloc[-(periods_back + 1)]
    if pd.isna(past) or past == 0:
        return None
    return float((close.iloc[-1] - past) / past * 100)


def compute_metrics(hist: pd.DataFrame, info: dict) -> dict:
    """Raw-value port of the legacy calculate_financial_metrics."""
    close = hist["Close"]
    latest_close = float(close.iloc[-1])

    returns = close.pct_change().dropna()
    volatility = float(returns.std() * np.sqrt(252) * 100) if len(returns) > 1 else None

    ma_20 = float(close.rolling(20).mean().iloc[-1]) if len(hist) >= 20 else None
    ma_50 = float(close.rolling(50).mean().iloc[-1]) if len(hist) >= 50 else None

    dividend_yield = info.get("dividendYield")

    return {
        "current_price": _clean(latest_close),
        "daily_change_pct": _clean(_pct_change(close, 1)),
        "weekly_change_pct": _clean(_pct_change(close, 5)),
        "monthly_change_pct": _clean(_pct_change(close, 21)),
        "yearly_change_pct": _clean(_pct_change(close, 251)),
        "volume": _clean(hist["Volume"].iloc[-1]),
        "market_cap": _clean(info.get("marketCap")),
        "pe_ratio": _clean(info.get("trailingPE")),
        "forward_pe": _clean(info.get("forwardPE")),
        "pb_ratio": _clean(info.get("priceToBook")),
        "ps_ratio": _clean(info.get("priceToSalesTrailing12Months")),
        "peg_ratio": _clean(info.get("pegRatio") or info.get("trailingPegRatio")),
        "dividend_yield_pct": _clean(dividend_yield * 100 if dividend_yield else None),
        "volatility_annual_pct": _clean(volatility),
        "ma_20": _clean(ma_20),
        "ma_50": _clean(ma_50),
        "week_52_high": _clean(info.get("fiftyTwoWeekHigh")),
        "week_52_low": _clean(info.get("fiftyTwoWeekLow")),
        "beta": _clean(info.get("beta")),
        "profit_margin_pct": _clean(
            info.get("profitMargins") * 100 if info.get("profitMargins") is not None else None
        ),
        "operating_margin_pct": _clean(
            info.get("operatingMargins") * 100 if info.get("operatingMargins") is not None else None
        ),
        "gross_margin_pct": _clean(
            info.get("grossMargins") * 100 if info.get("grossMargins") is not None else None
        ),
        "roe_pct": _clean(
            info.get("returnOnEquity") * 100 if info.get("returnOnEquity") is not None else None
        ),
        "roa_pct": _clean(
            info.get("returnOnAssets") * 100 if info.get("returnOnAssets") is not None else None
        ),
        "debt_to_equity": _clean(info.get("debtToEquity")),
        "current_ratio": _clean(info.get("currentRatio")),
        "revenue": _clean(info.get("totalRevenue")),
        "revenue_growth_pct": _clean(
            info.get("revenueGrowth") * 100 if info.get("revenueGrowth") is not None else None
        ),
        "eps": _clean(info.get("trailingEps")),
        "free_cash_flow": _clean(info.get("freeCashflow")),
        "operating_cash_flow": _clean(info.get("operatingCashflow")),
        "book_value_per_share": _clean(info.get("bookValue")),
    }


def stock_overview(symbol: str, period: str = "1y") -> dict:
    """Full payload for GET /api/stocks/{symbol}."""
    hist = get_history(symbol, period)
    if hist is None or hist.empty:
        raise LookupError(f"No market data found for symbol '{symbol}'")
    info = get_info(symbol)
    return {
        "symbol": symbol.upper(),
        "name": info.get("longName") or info.get("shortName") or symbol.upper(),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "exchange": info.get("fullExchangeName") or info.get("exchange"),
        "currency": info.get("currency"),
        "website": info.get("website"),
        "business_summary": info.get("longBusinessSummary"),
        "metrics": compute_metrics(hist, info),
    }


def compute_trend_context(hist: pd.DataFrame) -> dict | None:
    """Port of the legacy trend/support/resistance calculation (data only, no chart)."""
    if hist is None or hist.empty:
        return None
    chart_data = hist.tail(min(len(hist), 180))
    close = chart_data["Close"]
    low = chart_data["Low"]
    high = chart_data["High"]

    support = float(low.quantile(0.15))
    resistance = float(high.quantile(0.85))
    latest_price = float(close.iloc[-1])

    ma_50 = close.rolling(50).mean() if len(chart_data) >= 50 else None
    trend_label = "Sideways"
    if ma_50 is not None and not ma_50.dropna().empty:
        ma_50_series = ma_50.dropna()
        if len(ma_50_series) >= 10:
            slope = float(ma_50_series.iloc[-1] - ma_50_series.iloc[-10])
        else:
            slope = float(ma_50_series.iloc[-1] - ma_50_series.iloc[0])
        if latest_price > ma_50_series.iloc[-1] and slope > 0:
            trend_label = "Uptrend"
        elif latest_price < ma_50_series.iloc[-1] and slope < 0:
            trend_label = "Downtrend"

    price_range = max(resistance - support, 0.01)
    if trend_label == "Uptrend":
        bad_entry_low = resistance - (0.15 * price_range)
        bad_entry_high = resistance + (0.05 * price_range)
        bad_entry_label = "Beginner bad-entry zone: chasing near resistance"
    elif trend_label == "Downtrend":
        bad_entry_low = support - (0.05 * price_range)
        bad_entry_high = support + (0.15 * price_range)
        bad_entry_label = "Beginner bad-entry zone: catching falling knife"
    else:
        midpoint = (support + resistance) / 2
        bad_entry_low = midpoint - (0.08 * price_range)
        bad_entry_high = midpoint + (0.08 * price_range)
        bad_entry_label = "Beginner bad-entry zone: random entries in noisy range"

    return {
        "trend_label": trend_label,
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "latest_price": round(latest_price, 2),
        "bad_entry_zone": f"{bad_entry_low:.2f} - {bad_entry_high:.2f}",
        "bad_entry_label": bad_entry_label,
    }
