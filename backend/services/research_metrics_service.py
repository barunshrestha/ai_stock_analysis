"""Build a compact, JSON-serializable metrics pack from yFinance for LLM grounding."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from backend.services import stock_service

_SUMMARY_MAX = 700


def _clean(value: Any) -> Any:
    return stock_service._clean(value)


def _to_date(value: Any) -> date | None:
    """Best-effort parse of timestamps / date-like values to a calendar date."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        try:
            return value.to_pydatetime().date()
        except Exception:
            return None
    if isinstance(value, (int, float)):
        # Yahoo unix seconds (or ms)
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    if hasattr(value, "date") and callable(value.date):
        try:
            d = value.date()
            return d if isinstance(d, date) else None
        except Exception:
            return None
    return None


def _col(df: pd.DataFrame, *candidates: str) -> str | None:
    lower = {str(c).strip().lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    for key, orig in lower.items():
        for name in candidates:
            if name.lower() in key:
                return orig
    return None


def _price_reaction_pct(hist: pd.DataFrame | None, report_date: date | None, sessions: int = 2) -> float | None:
    """Close change from 1 session before report to ~1–2 sessions after. Null if unknown."""
    if hist is None or hist.empty or report_date is None or "Close" not in hist.columns:
        return None
    try:
        closes = hist["Close"].dropna()
    except Exception:
        return None
    if closes.empty:
        return None

    session_dates: list[date] = []
    for ts in closes.index:
        d = _to_date(ts)
        if d is not None:
            session_dates.append(d)
    if len(session_dates) < 3:
        return None

    # First trading session on or after the report date (falls back to last on/before).
    on_or_after = [i for i, d in enumerate(session_dates) if d >= report_date]
    if on_or_after:
        report_idx = on_or_after[0]
    else:
        on_or_before = [i for i, d in enumerate(session_dates) if d <= report_date]
        if not on_or_before:
            return None
        report_idx = on_or_before[-1]

    pre_idx = report_idx - 1
    post_idx = min(report_idx + max(1, sessions), len(closes) - 1)
    if pre_idx < 0 or post_idx <= pre_idx:
        return None
    pre = float(closes.iloc[pre_idx])
    post = float(closes.iloc[post_idx])
    if not pre:
        return None
    return round((post - pre) / abs(pre) * 100, 2)


def build_earnings_context(symbol: str) -> dict:
    """
    Compact earnings pack for Issue #14 grounding.

    Never invents beats/misses — EPS fields stay null when Yahoo has no figures.
    """
    sym = symbol.strip().upper()
    if not sym:
        raise ValueError("Ticker is required.")

    info = stock_service.get_info(sym) or {}
    earnings_dates = stock_service.get_earnings_dates(sym)
    today = date.today()

    last_report_date: str | None = None
    next_earnings_date: str | None = None
    eps_actual = None
    eps_estimate = None
    surprise_pct = None

    if earnings_dates is not None and not earnings_dates.empty:
        reported_col = _col(earnings_dates, "Reported EPS", "EPS Actual", "Actual")
        estimate_col = _col(earnings_dates, "EPS Estimate", "Estimate")
        surprise_col = _col(earnings_dates, "Surprise(%)", "Surprise %", "Surprise")

        rows: list[dict] = []
        for ts, row in earnings_dates.iterrows():
            d = _to_date(ts)
            if d is None:
                continue
            reported = _clean(row.get(reported_col)) if reported_col else None
            estimate = _clean(row.get(estimate_col)) if estimate_col else None
            surprise = _clean(row.get(surprise_col)) if surprise_col else None
            rows.append(
                {
                    "date": d,
                    "reported": reported,
                    "estimate": estimate,
                    "surprise": surprise,
                }
            )

        # Last report: most recent row with a reported EPS (prefer on/before today).
        reported_rows = [r for r in rows if isinstance(r["reported"], (int, float))]
        past_reported = [r for r in reported_rows if r["date"] <= today]
        last = (past_reported or reported_rows)
        if last:
            last = max(last, key=lambda r: r["date"])
            last_report_date = last["date"].isoformat()
            eps_actual = last["reported"]
            eps_estimate = last["estimate"] if isinstance(last["estimate"], (int, float)) else None
            surprise_pct = last["surprise"] if isinstance(last["surprise"], (int, float)) else None
            # Derive surprise only when both sides exist — never invent a beat/miss label here.
            if surprise_pct is None and eps_actual is not None and eps_estimate not in (None, 0):
                try:
                    surprise_pct = round(
                        (float(eps_actual) - float(eps_estimate)) / abs(float(eps_estimate)) * 100, 2
                    )
                except (TypeError, ValueError, ZeroDivisionError):
                    surprise_pct = None

        # Next date: earliest future calendar row (with or without estimate).
        future = [r for r in rows if r["date"] > today]
        if future:
            nxt = min(future, key=lambda r: r["date"])
            next_earnings_date = nxt["date"].isoformat()

    # Fallback next date from info / calendar-style timestamps when table has none.
    if next_earnings_date is None:
        for key in (
            "earningsTimestampStart",
            "earningsTimestamp",
            "earningsDate",
            "earningsCallTimestampStart",
        ):
            d = _to_date(info.get(key))
            if d is not None and d > today:
                next_earnings_date = d.isoformat()
                break

    # Slim revenue history from existing statement builder.
    statements = stock_service.get_financial_statements(sym)
    income = statements.get("income_stmt") if statements else None
    revenue_row = _row_by_label(income, ("Total Revenue", "Operating Revenue", "Revenue"))
    revenue_history = _pct_series_yoy(revenue_row) if revenue_row is not None else []

    hist = None
    try:
        hist = stock_service.get_history(sym, "2y")
    except Exception:
        hist = None
    report_d = date.fromisoformat(last_report_date) if last_report_date else None
    price_reaction_pct = _price_reaction_pct(hist, report_d, sessions=2)

    return {
        "last_report_date": last_report_date,
        "next_earnings_date": next_earnings_date,
        "eps_actual": eps_actual,
        "eps_estimate": eps_estimate,
        "surprise_pct": surprise_pct,
        "revenue_history": revenue_history,
        "price_reaction_pct": price_reaction_pct,
    }


def _pct_series_yoy(series: pd.Series) -> list[dict]:
    """Compact year-over-year points from a statement row (newest columns first)."""
    points: list[dict] = []
    vals = [(str(c)[:10], _clean(v)) for c, v in series.items() if _clean(v) is not None]
    # yfinance statements are typically newest-first columns
    for i, (label, val) in enumerate(vals[:5]):
        yoy = None
        if i + 1 < len(vals) and isinstance(val, (int, float)) and isinstance(vals[i + 1][1], (int, float)):
            prev = vals[i + 1][1]
            if prev:
                yoy = round((float(val) - float(prev)) / abs(float(prev)) * 100, 2)
        points.append({"period": label, "value": val, "yoy_pct": yoy})
    return points


def _row_by_label(df: pd.DataFrame | None, candidates: tuple[str, ...]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    lower_map = {str(idx).strip().lower(): idx for idx in df.index}
    for name in candidates:
        key = name.lower()
        if key in lower_map:
            return df.loc[lower_map[key]]
        for idx_l, idx in lower_map.items():
            if key in idx_l:
                return df.loc[idx]
    return None


def _earnings_compact(earnings: pd.DataFrame | None) -> list[dict]:
    if earnings is None or earnings.empty or "Earnings" not in earnings.columns:
        return []
    out: list[dict] = []
    for ts, row in earnings.tail(5).iterrows():
        label = ts.strftime("%Y") if hasattr(ts, "strftime") else str(ts)[:10]
        out.append({"year": label, "net_income": _clean(row.get("Earnings"))})
    return out


def _peer_symbols(info: dict) -> list[str] | None:
    raw = (
        info.get("peerGroup")
        or info.get("peers")
        or info.get("similar")
        or info.get("recommendedSymbols")
        or info.get("peerSymbols")
        or info.get("peer_symbols")
    )
    if isinstance(raw, str) and raw.strip():
        return [s.strip().upper() for s in raw.split(",") if s.strip()][:12]
    if isinstance(raw, list):
        symbols = []
        for item in raw:
            if isinstance(item, str):
                symbols.append(item.upper())
            elif isinstance(item, dict) and item.get("symbol"):
                symbols.append(str(item["symbol"]).upper())
        return symbols[:12] or None
    return None


def _peer_snapshots(peer_symbols: list[str] | None, exclude: str, limit: int = 3) -> list[dict]:
    """Fetch compact margin/valuation snapshots for a few peer tickers (best-effort)."""
    if not peer_symbols:
        return []
    out: list[dict] = []
    for sym in peer_symbols:
        s = str(sym).upper().strip()
        if not s or s == exclude or len(out) >= limit:
            continue
        try:
            info = stock_service.get_info(s) or {}
            out.append(
                {
                    "symbol": s,
                    "name": info.get("longName") or info.get("shortName") or s,
                    "market_cap": _clean(info.get("marketCap")),
                    "gross_margin_pct": _clean(
                        info.get("grossMargins") * 100 if info.get("grossMargins") is not None else None
                    ),
                    "operating_margin_pct": _clean(
                        info.get("operatingMargins") * 100 if info.get("operatingMargins") is not None else None
                    ),
                    "profit_margin_pct": _clean(
                        info.get("profitMargins") * 100 if info.get("profitMargins") is not None else None
                    ),
                    "pe_ratio": _clean(info.get("trailingPE")),
                }
            )
        except Exception:
            continue
    return out


def build_research_metrics(symbol: str, period: str = "1y") -> dict:
    """Fetch market data and return a stable metrics dict for Gemini grounding."""
    sym = symbol.strip().upper()
    if not sym:
        raise ValueError("Ticker is required.")

    hist = stock_service.get_history(sym, period)
    if hist is None or hist.empty:
        raise LookupError(f"No market data found for symbol '{sym}'")

    info = stock_service.get_info(sym) or {}
    earnings = stock_service.get_earnings(sym)
    metrics = stock_service.compute_metrics(hist, info)
    trend = stock_service.compute_trend_context(hist)
    statements = stock_service.get_financial_statements(sym)

    income = statements.get("income_stmt")
    revenue_row = _row_by_label(income, ("Total Revenue", "Operating Revenue", "Revenue"))
    net_income_row = _row_by_label(income, ("Net Income", "Net Income Common Stockholders"))

    summary = info.get("longBusinessSummary") or ""
    if len(summary) > _SUMMARY_MAX:
        summary = summary[:_SUMMARY_MAX].rstrip() + "…"

    close = hist["Close"]
    change_6m = None
    if len(close) > 126:
        past = float(close.iloc[-127])
        if past:
            change_6m = round((float(close.iloc[-1]) - past) / past * 100, 2)

    peers = _peer_symbols(info)
    peer_comps = _peer_snapshots(peers, exclude=sym, limit=3)

    return {
        "identity": {
            "symbol": sym,
            "name": info.get("longName") or info.get("shortName") or sym,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "exchange": info.get("fullExchangeName") or info.get("exchange"),
            "currency": info.get("currency"),
            "website": info.get("website"),
            "business_summary": summary or None,
        },
        "market": {
            "price": metrics.get("current_price"),
            "change_1d_pct": metrics.get("daily_change_pct"),
            "change_1m_pct": metrics.get("monthly_change_pct"),
            "change_6m_pct": change_6m,
            "change_1y_pct": metrics.get("yearly_change_pct"),
            "week_52_high": metrics.get("week_52_high"),
            "week_52_low": metrics.get("week_52_low"),
            "beta": metrics.get("beta"),
            "volume": metrics.get("volume"),
            "volatility_annual_pct": metrics.get("volatility_annual_pct"),
            "ma_20": metrics.get("ma_20"),
            "ma_50": metrics.get("ma_50"),
        },
        "valuation": {
            "market_cap": metrics.get("market_cap"),
            "pe_ratio": metrics.get("pe_ratio"),
            "forward_pe": metrics.get("forward_pe"),
            "peg_ratio": metrics.get("peg_ratio"),
            "pb_ratio": metrics.get("pb_ratio"),
            "ps_ratio": metrics.get("ps_ratio"),
            "dividend_yield_pct": metrics.get("dividend_yield_pct"),
            "eps": metrics.get("eps"),
            "book_value_per_share": metrics.get("book_value_per_share"),
        },
        "profitability": {
            "gross_margin_pct": metrics.get("gross_margin_pct"),
            "operating_margin_pct": metrics.get("operating_margin_pct"),
            "profit_margin_pct": metrics.get("profit_margin_pct"),
            "roe_pct": metrics.get("roe_pct"),
            "roa_pct": metrics.get("roa_pct"),
        },
        "balance_sheet_cash": {
            "debt_to_equity": metrics.get("debt_to_equity"),
            "current_ratio": metrics.get("current_ratio"),
            "free_cash_flow": metrics.get("free_cash_flow"),
            "operating_cash_flow": metrics.get("operating_cash_flow"),
            "total_cash": _clean(info.get("totalCash")),
            "total_debt": _clean(info.get("totalDebt")),
        },
        "growth": {
            "revenue_growth_pct": metrics.get("revenue_growth_pct"),
            "revenue": metrics.get("revenue"),
            "revenue_history": _pct_series_yoy(revenue_row) if revenue_row is not None else [],
            "net_income_history": _pct_series_yoy(net_income_row) if net_income_row is not None else [],
            "earnings_annual": _earnings_compact(earnings),
        },
        "trend": trend,
        "peers": peers,
        "peer_comps": peer_comps,
        "peer_note": None
        if peers
        else "Peer list not available from Yahoo for this symbol — do not invent competitor valuations.",
    }
