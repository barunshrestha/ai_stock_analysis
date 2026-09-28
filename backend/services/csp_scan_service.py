"""One-symbol cash-secured put scanner (story #32).

Filters a Yahoo put chain and ranks surviving contracts. Quotes are delayed.
Delta is a model estimate from implied volatility, not an exchange greek.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

import pandas as pd

from backend.services import options_chain_service, stock_service

DISCLAIMER = (
    "Bids are delayed Yahoo Finance quotes. Delta is a model estimate, not an exchange greek. "
    "Not financial advice — for journaling and education only."
)

# Annualized return, IV, open interest, and distance at which each score slice is full.
_ANN_RETURN_FULL = 40.0
_IV_FULL_PCT = 50.0
_OI_FULL = 2000
_OTM_FULL_PCT = 15.0


@dataclass(frozen=True)
class ScanFilters:
    min_bid: float = 0.40
    min_open_interest: int = 500
    delta_min: float = 0.12
    delta_max: float = 0.25
    min_iv_pct: float = 25.0
    min_otm_pct: float = 3.0
    min_score: float = 40.0
    min_dte: int = 21
    max_dte: int = 45


def filters_to_dict(filters: ScanFilters) -> dict:
    return asdict(filters)


def validate_scan_filters(filters: ScanFilters) -> None:
    """Reject impossible ranges before any market-data call."""
    if filters.delta_min > filters.delta_max:
        raise ValueError("Minimum delta must be less than or equal to maximum delta.")
    if not (0 <= filters.delta_min <= 1 and 0 <= filters.delta_max <= 1):
        raise ValueError("Delta must be between 0 and 1.")
    if filters.max_dte < filters.min_dte:
        raise ValueError("Maximum days to expiration must be at least the minimum.")
    _require_whole(filters.min_dte, "Minimum days to expiration")
    _require_whole(filters.max_dte, "Maximum days to expiration")
    _require_whole(filters.min_open_interest, "Minimum open interest")
    if filters.min_bid < 0:
        raise ValueError("Minimum bid cannot be negative.")
    if filters.min_iv_pct < 0:
        raise ValueError("Minimum implied volatility cannot be negative.")
    if filters.min_otm_pct < 0:
        raise ValueError("Strike distance cannot be negative.")
    if filters.min_score < 0 or filters.min_score > 100:
        raise ValueError("Minimum composite score must be between 0 and 100.")


def _require_whole(value: int | float, label: str) -> None:
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{label} must be a whole number zero or greater.")
    if value < 0:
        raise ValueError(f"{label} must be a whole number zero or greater.")


def _portion(value: float, floor: float, full: float, points: float) -> float:
    """Points for how far `value` sits between the filter floor and the full-credit level."""
    if full <= floor:
        return points
    if value <= floor:
        return 0.0
    return points * min((value - floor) / (full - floor), 1.0)


def composite_score(
    annualized_return_pct: float,
    iv_pct: float,
    open_interest: int,
    otm_pct: float,
    filters: ScanFilters,
) -> float:
    ann_pts = _ANN_RETURN_FULL * min(max(annualized_return_pct, 0.0) / _ANN_RETURN_FULL, 1.0)
    iv_pts = _portion(iv_pct, filters.min_iv_pct, _IV_FULL_PCT, 20)
    oi_pts = _portion(float(open_interest), float(filters.min_open_interest), _OI_FULL, 20)
    otm_pts = _portion(otm_pct, filters.min_otm_pct, _OTM_FULL_PCT, 20)
    return round(ann_pts + iv_pts + oi_pts + otm_pts, 2)


def _iv_pct(raw) -> float | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)) or pd.isna(raw):
        return None
    try:
        iv = float(raw)
    except (TypeError, ValueError):
        return None
    if iv <= 0:
        return None
    return iv * 100 if iv < 3 else iv


def _iv_decimal(iv_pct: float) -> float:
    return iv_pct / 100 if iv_pct >= 3 else iv_pct


def _abs_delta(row: pd.Series, spot: float, tte_years: float, iv_pct: float | None) -> float | None:
    if "delta" in row.index and row.get("delta") is not None and not pd.isna(row.get("delta")):
        return abs(float(row["delta"]))
    if iv_pct is None:
        return None
    iv = _iv_decimal(iv_pct)
    if iv <= 0:
        return None
    strike = float(row.get("strike") or 0)
    return abs(options_chain_service.estimate_put_delta(strike, spot, tte_years, iv))


def contract_math(bid: float, strike: float, spot: float, dte: int) -> dict:
    roc = (bid / strike) * 100 if strike else 0.0
    annualized = roc * (365 / dte) if dte else 0.0
    otm_pct = ((spot - strike) / spot) * 100 if spot else 0.0
    return {
        "premium_per_contract": round(bid * 100, 2),
        "return_on_capital_pct": round(roc, 3),
        "annualized_return_pct": round(annualized, 2),
        "breakeven": round(strike - bid, 2),
        "otm_pct": round(otm_pct, 2),
        "_annualized_raw": annualized,
        "_otm_raw": otm_pct,
    }


def expirations_in_window(
    expirations: list[str],
    filters: ScanFilters,
    as_of: date | None = None,
) -> list[tuple[str, int]]:
    ref = as_of or date.today()
    selected: list[tuple[str, int]] = []
    for exp_str in expirations:
        exp_date = options_chain_service._parse_expiration(exp_str)
        if not exp_date:
            continue
        days = options_chain_service._dte(exp_date, ref)
        if filters.min_dte <= days <= filters.max_dte:
            selected.append((exp_str, days))
    return selected


def contracts_from_chain(
    chain: pd.DataFrame,
    *,
    symbol: str,
    spot: float,
    expiration: str,
    dte: int,
    filters: ScanFilters,
) -> list[dict]:
    """Keep puts that pass every filter. Callers sort the combined list."""
    if chain is None or chain.empty or spot <= 0 or dte <= 0:
        return []
    if dte < filters.min_dte or dte > filters.max_dte:
        return []

    tte_years = max(dte, 1) / 365.0
    rows: list[dict] = []
    for _, row in chain.iterrows():
        strike = float(row.get("strike") or 0)
        if strike <= 0:
            continue
        bid_raw = row.get("bid")
        if bid_raw is None or pd.isna(bid_raw):
            continue
        bid = float(bid_raw)
        if bid <= 0 or bid < filters.min_bid:
            continue

        oi = options_chain_service._safe_int(row.get("openInterest"))
        if oi < filters.min_open_interest:
            continue

        iv_pct = _iv_pct(row.get("impliedVolatility"))
        if iv_pct is None or iv_pct < filters.min_iv_pct:
            continue

        delta = _abs_delta(row, spot, tte_years, iv_pct)
        if delta is None or delta < filters.delta_min or delta > filters.delta_max:
            continue

        math = contract_math(bid, strike, spot, dte)
        if math["_otm_raw"] < filters.min_otm_pct:
            continue

        score = composite_score(math["_annualized_raw"], iv_pct, oi, math["_otm_raw"], filters)
        if score < filters.min_score:
            continue

        rows.append(
            {
                "symbol": symbol,
                "expiration": expiration,
                "strike": round(strike, 2),
                "bid": round(bid, 2),
                "delta": round(delta, 4),
                "iv_pct": round(iv_pct, 2),
                "open_interest": oi,
                "dte": dte,
                "otm_pct": math["otm_pct"],
                "premium_per_contract": math["premium_per_contract"],
                "return_on_capital_pct": math["return_on_capital_pct"],
                "annualized_return_pct": math["annualized_return_pct"],
                "breakeven": math["breakeven"],
                "composite_score": score,
            }
        )
    return rows


def sort_contracts(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda c: (-c["composite_score"], c["expiration"], c["strike"]))


def scan_puts(symbol: str, filters: ScanFilters | None = None, *, as_of: date | None = None) -> dict:
    filters = filters or ScanFilters()
    validate_scan_filters(filters)
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Ticker is required.")

    hist = stock_service.get_history(symbol, "5d")
    if hist is None or hist.empty:
        raise LookupError(f"No market data for '{symbol}'")
    spot = float(hist["Close"].iloc[-1])
    if spot <= 0 or pd.isna(spot):
        raise LookupError(f"No market data for '{symbol}'")

    expirations = options_chain_service.get_expirations(symbol)
    if not expirations:
        raise LookupError(f"No options chain for '{symbol}'")

    contracts: list[dict] = []
    for exp_str, dte in expirations_in_window(expirations, filters, as_of):
        chain = options_chain_service.get_puts_chain(symbol, exp_str)
        contracts.extend(
            contracts_from_chain(
                chain,
                symbol=symbol,
                spot=spot,
                expiration=exp_str,
                dte=dte,
                filters=filters,
            )
        )

    return {
        "ticker": symbol,
        "spot": round(spot, 2),
        "scanned_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "filters": filters_to_dict(filters),
        "contracts": sort_contracts(contracts),
        "disclaimer": DISCLAIMER,
    }
