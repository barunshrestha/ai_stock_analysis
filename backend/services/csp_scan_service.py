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

# Points for each relative component. Parts are min-max scaled across the scan.
_LIQUIDITY_POINTS = 30.0
_PREMIUM_POINTS = 25.0
_POP_POINTS = 25.0
_IV_POINTS = 20.0


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


def filters_from_dict(raw: dict) -> ScanFilters:
    return ScanFilters(
        min_bid=float(raw["min_bid"]),
        min_open_interest=int(raw["min_open_interest"]),
        delta_min=float(raw["delta_min"]),
        delta_max=float(raw["delta_max"]),
        min_iv_pct=float(raw["min_iv_pct"]),
        min_otm_pct=float(raw["min_otm_pct"]),
        min_score=float(raw["min_score"]),
        min_dte=int(raw["min_dte"]),
        max_dte=int(raw["max_dte"]),
    )


# Shipped starting profiles. Maximum days stays 45 on each.
PRESET_PROFILES: tuple[tuple[str, ScanFilters], ...] = (
    (
        "Conservative",
        ScanFilters(
            min_bid=0.50,
            min_open_interest=1000,
            delta_min=0.10,
            delta_max=0.20,
            min_iv_pct=25,
            min_otm_pct=5,
            min_score=50,
            min_dte=30,
            max_dte=45,
        ),
    ),
    ("Balanced", ScanFilters()),
    (
        "Aggressive",
        ScanFilters(
            min_bid=0.25,
            min_open_interest=200,
            delta_min=0.15,
            delta_max=0.35,
            min_iv_pct=20,
            min_otm_pct=2,
            min_score=30,
            min_dte=14,
            max_dte=45,
        ),
    ),
)


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


def _minmax(values: list[float]) -> list[float]:
    """Scale values to 0–1 across this scan. A tie, including a single survivor, is full credit."""
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return [1.0 for _ in values]
    span = hi - lo
    return [(value - lo) / span for value in values]


def _tightness(bid: float, ask) -> float:
    """Bid divided by ask. A missing or unusable ask scores zero tightness."""
    if ask is None or (isinstance(ask, float) and pd.isna(ask)) or pd.isna(ask):
        return 0.0
    try:
        ask_f = float(ask)
    except (TypeError, ValueError):
        return 0.0
    if ask_f <= 0 or ask_f < bid:
        return 0.0
    return bid / ask_f


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


def contract_math(bid: float, strike: float, spot: float, dte: int) -> dict | None:
    """Return row math, or None when capital at risk is not positive."""
    premium = bid * 100
    capital = (strike * 100) - premium
    if capital <= 0 or strike <= 0 or spot <= 0 or dte <= 0:
        return None
    roc = (premium / capital) * 100
    annualized = roc * (365 / dte)
    otm_pct = ((spot - strike) / spot) * 100
    return {
        "premium_per_contract": round(premium, 2),
        "capital_at_risk": round(capital, 2),
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


def _public_contract(candidate: dict) -> dict:
    return {key: value for key, value in candidate.items() if not key.startswith("_")}


def apply_relative_scores(candidates: list[dict], min_score: float) -> list[dict]:
    """Score hard-filter survivors against each other, then drop scores under the minimum."""
    if not candidates:
        return []
    oi_norm = _minmax([float(row["_oi"]) for row in candidates])
    tight_norm = _minmax([float(row["_tightness"]) for row in candidates])
    premium_norm = _minmax([float(row["_annualized_raw"]) for row in candidates])
    pop_norm = _minmax([float(row["_pop_raw"]) for row in candidates])
    iv_norm = _minmax([float(row["_iv_raw"]) for row in candidates])

    scored: list[dict] = []
    for index, candidate in enumerate(candidates):
        liquidity = 0.5 * oi_norm[index] + 0.5 * tight_norm[index]
        parts = {
            "liquidity_points": round(_LIQUIDITY_POINTS * liquidity, 2),
            "premium_points": round(_PREMIUM_POINTS * premium_norm[index], 2),
            "pop_points": round(_POP_POINTS * pop_norm[index], 2),
            "iv_points": round(_IV_POINTS * iv_norm[index], 2),
        }
        score = round(sum(parts.values()), 2)
        if score < min_score:
            continue
        row = _public_contract(candidate)
        row.update(parts)
        row["composite_score"] = score
        scored.append(row)
    return scored


def candidates_from_chain(
    chain: pd.DataFrame,
    *,
    symbol: str,
    spot: float,
    expiration: str,
    dte: int,
    filters: ScanFilters,
) -> list[dict]:
    """Puts that pass every hard filter. Score is applied later across the whole scan."""
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
        if math is None or math["_otm_raw"] < filters.min_otm_pct:
            continue

        pop = 1.0 - delta
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
                "capital_at_risk": math["capital_at_risk"],
                "return_on_capital_pct": math["return_on_capital_pct"],
                "annualized_return_pct": math["annualized_return_pct"],
                "breakeven": math["breakeven"],
                "probability_of_profit": round(pop, 4),
                "_oi": float(oi),
                "_tightness": _tightness(bid, row.get("ask")),
                "_annualized_raw": math["_annualized_raw"],
                "_pop_raw": pop,
                "_iv_raw": iv_pct,
            }
        )
    return rows


def contracts_from_chain(
    chain: pd.DataFrame,
    *,
    symbol: str,
    spot: float,
    expiration: str,
    dte: int,
    filters: ScanFilters,
) -> list[dict]:
    """Hard-filter one chain, then score that chain against itself."""
    return apply_relative_scores(
        candidates_from_chain(
            chain,
            symbol=symbol,
            spot=spot,
            expiration=expiration,
            dte=dte,
            filters=filters,
        ),
        filters.min_score,
    )


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

    candidates: list[dict] = []
    for exp_str, dte in expirations_in_window(expirations, filters, as_of):
        chain = options_chain_service.get_puts_chain(symbol, exp_str)
        candidates.extend(
            candidates_from_chain(
                chain,
                symbol=symbol,
                spot=spot,
                expiration=exp_str,
                dte=dte,
                filters=filters,
            )
        )
    contracts = apply_relative_scores(candidates, filters.min_score)

    return {
        "ticker": symbol,
        "spot": round(spot, 2),
        "scanned_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "filters": filters_to_dict(filters),
        "contracts": sort_contracts(contracts),
        "disclaimer": DISCLAIMER,
    }
