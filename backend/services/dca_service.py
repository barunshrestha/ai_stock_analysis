"""DCA scoring and backtest, ported from the legacy Streamlit app.

The scoring model and score-weighted vs equal-weight backtest are unchanged
from app.py; only the I/O changed (returns JSON-serializable dicts instead
of rendering Streamlit widgets).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.services import stock_service

DCA_WEIGHTS = {
    "fundamentals": 25,
    "valuation": 15,
    "technical": 15,
    "analyst_institutional": 15,
    "earnings_forecast": 15,
    "news_social": 10,
    "macro": 5,
}


def normalize_percent(value, floor_pct=-100.0, cap_pct=200.0) -> float:
    if value is None or pd.isna(value):
        return 50.0
    v = max(floor_pct, min(cap_pct, value))
    return (v - floor_pct) / (cap_pct - floor_pct) * 100.0


def compute_total_score_from_components(components: dict) -> float:
    total = 0.0
    for key, weight in DCA_WEIGHTS.items():
        total += components.get(key, 50.0) * (weight / 100.0)
    return max(0.0, min(100.0, total))


def allocate_weights_from_scores(scores: dict) -> dict:
    eps = 1e-8
    tickers = list(scores.keys())
    vals = np.array([max(eps, scores[t]) for t in tickers], dtype=float)
    s = float(np.sum(vals))
    if s <= 0:
        n = len(tickers)
        return {t: 1.0 / n for t in tickers}
    return {t: float(v / s) for t, v in zip(tickers, vals)}


def calculate_stock_score(info: dict, hist_data: pd.DataFrame, earnings_data=None) -> tuple[float, dict]:
    """Score 0-100 from fundamentals, valuation, technicals, analyst views, earnings."""
    components: dict[str, float] = {}
    try:
        profit_margin = info.get("profitMargins", 0) * 100 if info.get("profitMargins") else None
        roe = info.get("returnOnEquity", 0) * 100 if info.get("returnOnEquity") else None
        current_ratio = info.get("currentRatio")
        debt_to_equity = info.get("debtToEquity")

        fund_score = 50.0
        if profit_margin:
            fund_score += normalize_percent(profit_margin, 0, 50) * 0.3
        if roe:
            fund_score += normalize_percent(roe, 0, 50) * 0.3
        if current_ratio:
            fund_score += normalize_percent((current_ratio - 1) * 50, -50, 50) * 0.2
        if debt_to_equity:
            fund_score += normalize_percent((2 - debt_to_equity) * 25, -50, 50) * 0.2
        components["fundamentals"] = max(0, min(100, fund_score))

        pe_ratio = info.get("trailingPE")
        val_score = 50.0
        if pe_ratio:
            if 10 <= pe_ratio <= 25:
                val_score = 70
            elif pe_ratio < 10:
                val_score = 60
            elif pe_ratio > 30:
                val_score = 30
            else:
                val_score = 50
        components["valuation"] = val_score

        if len(hist_data) >= 20:
            returns_20 = hist_data["Close"].pct_change(20).iloc[-1] * 100 if len(hist_data) > 20 else 0
            returns_50 = hist_data["Close"].pct_change(50).iloc[-1] * 100 if len(hist_data) > 50 else 0
            momentum = (returns_20 * 0.6 + returns_50 * 0.4) if len(hist_data) > 50 else returns_20
            components["technical"] = normalize_percent(momentum, -50, 100)
        else:
            components["technical"] = 50.0

        recommendation_mean = info.get("recommendationMean")
        if recommendation_mean:
            analyst_score = (5 - recommendation_mean) / 4 * 100
            components["analyst_institutional"] = max(0, min(100, analyst_score))
        else:
            components["analyst_institutional"] = 50.0

        if earnings_data is not None and not earnings_data.empty:
            earnings_values = earnings_data["Earnings"].values
            if len(earnings_values) >= 2:
                recent_avg = np.mean(earnings_values[-2:])
                older_avg = np.mean(earnings_values[:-2]) if len(earnings_values) > 2 else earnings_values[0]
                earnings_growth = ((recent_avg - older_avg) / abs(older_avg)) * 100 if older_avg != 0 else 0
                components["earnings_forecast"] = normalize_percent(earnings_growth, -50, 100)
            else:
                components["earnings_forecast"] = 50.0
        else:
            components["earnings_forecast"] = 50.0

        if len(hist_data) >= 5:
            recent_returns = hist_data["Close"].pct_change(5).iloc[-1] * 100
            components["news_social"] = normalize_percent(recent_returns, -20, 20)
        else:
            components["news_social"] = 50.0

        components["macro"] = 50.0

        return compute_total_score_from_components(components), components
    except Exception:
        return 50.0, {k: 50.0 for k in DCA_WEIGHTS}


def run_backtest(symbols: list[str], daily_invest: float, start_date: str, end_date: str) -> dict:
    """Score-weighted vs equal-weight DCA backtest.

    Returns a JSON payload with both equity curves and summary stats.
    Raises ValueError with a user-readable message on bad input/data.
    """
    all_data: dict[str, pd.DataFrame] = {}
    all_info: dict[str, dict] = {}
    all_earnings: dict[str, pd.DataFrame | None] = {}
    skipped: list[str] = []

    for symbol in symbols:
        try:
            hist = stock_service.get_history(symbol, "5y")
            info = stock_service.get_info(symbol)
            if hist is None or hist.empty or not info:
                skipped.append(symbol)
                continue
            all_data[symbol] = hist
            all_info[symbol] = info
            all_earnings[symbol] = stock_service.get_earnings(symbol)
        except Exception:
            skipped.append(symbol)

    if not all_data:
        raise ValueError("No data available for any of the requested symbols")

    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date)

    price_data: dict[str, pd.Series] = {}
    for symbol, hist in all_data.items():
        hist_copy = hist.copy()
        if hist_copy.index.tz is not None:
            hist_copy.index = hist_copy.index.tz_localize(None)
        filtered = hist_copy[(hist_copy.index >= start_dt) & (hist_copy.index <= end_dt)]
        if not filtered.empty:
            price_data[symbol] = filtered["Close"]

    if not price_data:
        raise ValueError("No data available in the specified date range")

    price_df = pd.DataFrame(price_data).dropna()
    if price_df.index.tz is not None:
        price_df.index = price_df.index.tz_localize(None)
    if price_df.empty:
        raise ValueError("No overlapping trading dates found for the selected stocks")

    # Pre-strip timezones once; the daily loop slices these repeatedly.
    naive_data = {}
    for symbol in price_df.columns:
        hist_full = all_data[symbol].copy()
        if hist_full.index.tz is not None:
            hist_full.index = hist_full.index.tz_localize(None)
        naive_data[symbol] = hist_full

    shares = {t: 0.0 for t in price_df.columns}
    invested = {t: 0.0 for t in price_df.columns}
    score_curve: list[dict] = []

    fallback_scores = {
        symbol: calculate_stock_score(all_info[symbol], naive_data[symbol], all_earnings.get(symbol))[0]
        for symbol in price_df.columns
    }

    for dt in price_df.index:
        prices = price_df.loc[dt]
        scores: dict[str, float] = {}
        for symbol in price_df.columns:
            hist_up_to_date = naive_data[symbol][naive_data[symbol].index <= dt]
            if len(hist_up_to_date) >= 20:
                score, _ = calculate_stock_score(all_info[symbol], hist_up_to_date, all_earnings.get(symbol))
                scores[symbol] = score
            else:
                scores[symbol] = fallback_scores.get(symbol, 50.0)

        weights = allocate_weights_from_scores(scores)
        for symbol in price_df.columns:
            price = prices[symbol]
            if pd.isna(price) or price <= 0:
                continue
            alloc = daily_invest * weights[symbol]
            shares[symbol] += alloc / price
            invested[symbol] += alloc

        score_curve.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "portfolio_value": float(sum(shares[s] * prices[s] for s in price_df.columns)),
                "total_invested": float(sum(invested.values())),
                "weights": {s: round(weights.get(s, 0.0), 4) for s in price_df.columns},
            }
        )

    shares_eq = {t: 0.0 for t in price_df.columns}
    invested_eq = {t: 0.0 for t in price_df.columns}
    equal_curve: list[dict] = []
    equal_weight = 1.0 / len(price_df.columns)

    for dt in price_df.index:
        prices = price_df.loc[dt]
        for symbol in price_df.columns:
            price = prices[symbol]
            if pd.isna(price) or price <= 0:
                continue
            alloc = daily_invest * equal_weight
            shares_eq[symbol] += alloc / price
            invested_eq[symbol] += alloc
        equal_curve.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "portfolio_value": float(sum(shares_eq[s] * prices[s] for s in price_df.columns)),
                "total_invested": float(sum(invested_eq.values())),
            }
        )

    def _summary(curve: list[dict]) -> dict:
        total_days = len(curve)
        total_invested = curve[-1]["total_invested"] if curve else 0.0
        final_value = curve[-1]["portfolio_value"] if curve else 0.0
        roi = (final_value - total_invested) / total_invested * 100 if total_invested > 0 else 0.0
        years = total_days / 252.0
        cagr = (
            ((final_value / total_invested) ** (1.0 / years) - 1.0) * 100
            if total_invested > 0 and years > 0
            else 0.0
        )
        return {
            "days": total_days,
            "total_invested": round(total_invested, 2),
            "final_value": round(final_value, 2),
            "roi_pct": round(roi, 2),
            "cagr_pct": round(cagr, 2),
        }

    return {
        "symbols": list(price_df.columns),
        "skipped": skipped,
        "score_weighted": {"summary": _summary(score_curve), "curve": score_curve},
        "equal_weight": {"summary": _summary(equal_curve), "curve": equal_curve},
        "final_shares": {s: round(shares[s], 4) for s in price_df.columns},
    }
