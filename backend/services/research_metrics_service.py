"""Build a compact, JSON-serializable metrics pack from yFinance for LLM grounding."""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.services import stock_service

_SUMMARY_MAX = 700


def _clean(value: Any) -> Any:
    return stock_service._clean(value)


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
        "peer_note": None
        if peers
        else "Peer list not available from Yahoo for this symbol — do not invent competitor valuations.",
    }
