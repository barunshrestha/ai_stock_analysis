"""yfinance options chain helpers for CSP screening and monitoring."""

from __future__ import annotations

import math
from datetime import date, datetime

import numpy as np
import pandas as pd

from backend.cache import ttl_cache
from backend.config import (
    CSP_DTE_MAX,
    CSP_DTE_MIN,
    CSP_MIN_OPEN_INTEREST,
    CSP_RISK_FREE_RATE,
    CSP_SPREAD_PCT_MAX,
    CSP_TARGET_DELTA,
    TTL_OPTIONS_CHAIN,
)
from backend.services import stock_service
from yahoo_session import get_ticker, with_retry


def _parse_expiration(exp_str: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(exp_str, fmt).date()
        except ValueError:
            continue
    return None


def _dte(expiration: date, as_of: date | None = None) -> int:
    ref = as_of or date.today()
    return max((expiration - ref).days, 0)


@ttl_cache(TTL_OPTIONS_CHAIN)
def get_expirations(symbol: str) -> list[str]:
    ticker = get_ticker(symbol.upper())
    opts = with_retry(lambda: ticker.options, attempts=2)
    return list(opts or [])


def get_puts_chain(symbol: str, expiration: str) -> pd.DataFrame:
    ticker = get_ticker(symbol.upper())

    def _fetch():
        chain = ticker.option_chain(expiration)
        puts = chain.puts
        if puts is None or puts.empty:
            return pd.DataFrame()
        return puts.copy()

    return with_retry(_fetch, attempts=2)


def pick_expiration_in_dte_window(
    symbol: str,
    min_dte: int = CSP_DTE_MIN,
    max_dte: int = CSP_DTE_MAX,
    as_of: date | None = None,
) -> tuple[str | None, int | None]:
    ref = as_of or date.today()
    best_exp: str | None = None
    best_dte: int | None = None
    for exp_str in get_expirations(symbol):
        exp_date = _parse_expiration(exp_str)
        if not exp_date:
            continue
        days = _dte(exp_date, ref)
        if min_dte <= days <= max_dte:
            if best_dte is None or abs(days - (min_dte + max_dte) / 2) < abs(best_dte - (min_dte + max_dte) / 2):
                best_exp = exp_str
                best_dte = days
    return best_exp, best_dte


def _safe_int(val) -> int:
    if val is None or (isinstance(val, float) and (pd.isna(val) or np.isnan(val))):
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def option_mid_price(row: pd.Series) -> float | None:
    bid = row.get("bid")
    ask = row.get("ask")
    last = row.get("lastPrice")
    if bid is not None and ask is not None and not (pd.isna(bid) or pd.isna(ask)):
        if bid > 0 or ask > 0:
            return float((bid + ask) / 2)
    if last is not None and not pd.isna(last) and last > 0:
        return float(last)
    return None


def estimate_put_delta(strike: float, spot: float, tte_years: float, iv: float, rate: float = CSP_RISK_FREE_RATE) -> float:
    if tte_years <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    try:
        from py_vollib.black_scholes.greeks.analytical import delta

        return float(delta("p", spot, strike, tte_years, rate, iv))
    except Exception:
        return 0.0


def _row_delta(row: pd.Series, spot: float, tte_years: float) -> float:
    if "delta" in row.index and row.get("delta") is not None and not pd.isna(row.get("delta")):
        return abs(float(row["delta"]))
    iv = row.get("impliedVolatility")
    strike = float(row.get("strike", 0))
    if iv is None or pd.isna(iv) or iv <= 0:
        iv = 0.25
    return abs(estimate_put_delta(strike, spot, tte_years, float(iv)))


def find_put_near_delta(
    chain: pd.DataFrame,
    spot: float,
    expiration_date: date,
    target_delta: float = CSP_TARGET_DELTA,
    as_of: date | None = None,
) -> dict | None:
    if chain is None or chain.empty or spot <= 0:
        return None
    ref = as_of or date.today()
    tte_years = max(_dte(expiration_date, ref), 1) / 365.0
    best: dict | None = None
    best_diff = float("inf")

    for _, row in chain.iterrows():
        strike = float(row.get("strike", 0))
        if strike <= 0:
            continue
        d = _row_delta(row, spot, tte_years)
        diff = abs(d - target_delta)
        mid = option_mid_price(row)
        if mid is None:
            continue
        bid = float(row.get("bid") or 0)
        ask = float(row.get("ask") or 0)
        spread_pct = ((ask - bid) / mid * 100) if mid > 0 and ask > 0 and bid >= 0 else None
        oi = _safe_int(row.get("openInterest"))
        vol = _safe_int(row.get("volume"))
        iv = row.get("impliedVolatility")
        iv_f = float(iv) if iv is not None and not pd.isna(iv) else None

        candidate = {
            "strike": strike,
            "delta": round(d, 4),
            "premium_mid": round(mid, 2),
            "bid": round(bid, 2),
            "ask": round(ask, 2),
            "spread_pct": round(spread_pct, 2) if spread_pct is not None else None,
            "open_interest": oi,
            "volume": vol,
            "implied_volatility": round(iv_f, 4) if iv_f else None,
            "otm_pct": round((spot - strike) / spot * 100, 2) if spot > strike else round((spot - strike) / spot * 100, 2),
            "liquidity_ok": (spread_pct is None or spread_pct <= CSP_SPREAD_PCT_MAX) and oi >= CSP_MIN_OPEN_INTEREST,
        }
        if diff < best_diff:
            best_diff = diff
            best = candidate
    return best


def realized_vol_30d(hist: pd.DataFrame) -> float | None:
    if hist is None or hist.empty or len(hist) < 22:
        return None
    close = hist["Close"].tail(31)
    returns = close.pct_change().dropna()
    if len(returns) < 5:
        return None
    return float(returns.std() * np.sqrt(252) * 100)


def get_ema_levels(hist: pd.DataFrame) -> dict:
    close = hist["Close"]
    latest = float(close.iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1]) if len(close) >= 50 else None
    ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1]) if len(close) >= 200 else None
    return {
        "current_price": round(latest, 2),
        "ema_50": round(ema50, 2) if ema50 else None,
        "ema_200": round(ema200, 2) if ema200 else None,
        "above_ema_50": ema50 is not None and latest > ema50,
        "above_ema_200": ema200 is not None and latest > ema200,
    }


def get_fundamental_health(symbol: str) -> dict:
    info = stock_service.get_info(symbol.upper())
    dte = info.get("debtToEquity")
    fcf = info.get("freeCashflow")
    return {
        "debt_to_equity": round(float(dte), 2) if dte is not None and not (isinstance(dte, float) and math.isnan(dte)) else None,
        "free_cash_flow": float(fcf) if fcf is not None and not (isinstance(fcf, float) and math.isnan(fcf)) else None,
    }


def _parse_event_date(raw) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and raw:
        raw = raw[0]
    if hasattr(raw, "date"):
        try:
            return raw.date() if callable(getattr(raw, "date", None)) else raw
        except Exception:
            pass
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw).date()
    if isinstance(raw, str):
        return _parse_expiration(raw[:10]) if len(raw) >= 10 else None
    return None


def get_upcoming_events(symbol: str, horizon_days: int = 45) -> dict:
    symbol = symbol.upper()
    info = stock_service.get_info(symbol)
    today = date.today()
    horizon = today.toordinal() + horizon_days

    earnings_date = _parse_event_date(info.get("earningsTimestamp") or info.get("earningsDate"))
    ex_div_date = _parse_event_date(info.get("exDividendDate"))

    try:
        ticker = get_ticker(symbol)
        cal = with_retry(lambda: ticker.calendar, attempts=2)
        if cal is not None and not (isinstance(cal, pd.DataFrame) and cal.empty):
            if isinstance(cal, pd.DataFrame):
                if "Earnings Date" in cal.index:
                    val = cal.loc["Earnings Date"]
                    if hasattr(val, "iloc"):
                        earnings_date = earnings_date or _parse_event_date(val.iloc[0])
                    else:
                        earnings_date = earnings_date or _parse_event_date(val)
                if "Ex-Dividend Date" in cal.index:
                    val = cal.loc["Ex-Dividend Date"]
                    if hasattr(val, "iloc"):
                        ex_div_date = ex_div_date or _parse_event_date(val.iloc[0])
                    else:
                        ex_div_date = ex_div_date or _parse_event_date(val)
    except Exception:
        pass

    def _within(d: date | None) -> bool:
        return d is not None and today <= d <= date.fromordinal(horizon)

    return {
        "earnings_date": earnings_date.isoformat() if earnings_date else None,
        "earnings_within_horizon": _within(earnings_date),
        "ex_dividend_date": ex_div_date.isoformat() if ex_div_date else None,
        "ex_dividend_within_horizon": _within(ex_div_date),
        "horizon_days": horizon_days,
    }


def find_put_at_strike(symbol: str, expiration: str, strike: float) -> dict | None:
    exp_key = expiration
    for e in get_expirations(symbol):
        parsed = _parse_expiration(e)
        if parsed and parsed.isoformat() == expiration[:10]:
            exp_key = e
            break
    chain = get_puts_chain(symbol, exp_key)
    if chain.empty:
        return None
    row = chain.loc[(chain["strike"] - strike).abs().idxmin()]
    mid = option_mid_price(row)
    if mid is None:
        return None
    exp_date = _parse_expiration(expiration)
    hist = stock_service.get_history(symbol, "5d")
    spot = float(hist["Close"].iloc[-1]) if not hist.empty else 0
    tte = max(_dte(exp_date, date.today()), 1) / 365.0 if exp_date else 30 / 365.0
    return {
        "strike": float(row["strike"]),
        "premium_mid": round(mid, 2),
        "bid": round(float(row.get("bid") or 0), 2),
        "ask": round(float(row.get("ask") or 0), 2),
        "delta": round(_row_delta(row, spot, tte), 4),
        "implied_volatility": float(row["impliedVolatility"]) if row.get("impliedVolatility") is not None and not pd.isna(row.get("impliedVolatility")) else None,
        "current_spot": round(spot, 2),
    }
