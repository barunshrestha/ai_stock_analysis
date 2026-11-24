"""One-symbol covered-call screener.

Filters a Yahoo call chain and ranks surviving contracts. Quotes are delayed.
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

CLASSIC = "classic"
PRE_EARNINGS = "pre_earnings"
MODES = (CLASSIC, PRE_EARNINGS)

_LIQUIDITY_POINTS = 30.0
_RETURN_POINTS = 25.0
_KEEP_POINTS = 25.0
_IV_POINTS = 20.0


@dataclass(frozen=True)
class ScanFilters:
    min_annualized_return_pct: float = 8.0
    delta_min: float = 0.15
    delta_max: float = 0.30
    min_otm_pct: float = 2.0
    max_otm_pct: float = 5.0
    min_dte: int = 30
    max_dte: int = 45
    min_iv_pct: float = 40.0
    min_open_interest: int = 500
    min_downside_protection_pct: float = 2.0
    min_score: float = 40.0


def filters_from_dict(raw: dict) -> ScanFilters:
    return ScanFilters(
        min_annualized_return_pct=float(raw["min_annualized_return_pct"]),
        delta_min=float(raw["delta_min"]),
        delta_max=float(raw["delta_max"]),
        min_otm_pct=float(raw["min_otm_pct"]),
        max_otm_pct=float(raw["max_otm_pct"]),
        min_dte=int(raw["min_dte"]),
        max_dte=int(raw["max_dte"]),
        min_iv_pct=float(raw["min_iv_pct"]),
        min_open_interest=int(raw["min_open_interest"]),
        min_downside_protection_pct=float(raw["min_downside_protection_pct"]),
        min_score=float(raw["min_score"]),
    )


def filters_to_dict(filters: ScanFilters) -> dict:
    return asdict(filters)


PRESET_PROFILES: tuple[tuple[str, ScanFilters], ...] = (
    (
        "Conservative",
        ScanFilters(
            min_annualized_return_pct=10,
            delta_min=0.10,
            delta_max=0.20,
            min_otm_pct=3,
            max_otm_pct=7,
            min_dte=30,
            max_dte=45,
            min_iv_pct=40,
            min_open_interest=1000,
            min_downside_protection_pct=3,
            min_score=50,
        ),
    ),
    ("Balanced", ScanFilters()),
    (
        "Aggressive",
        ScanFilters(
            min_annualized_return_pct=6,
            delta_min=0.20,
            delta_max=0.40,
            min_otm_pct=1,
            max_otm_pct=3,
            min_dte=21,
            max_dte=45,
            min_iv_pct=40,
            min_open_interest=200,
            min_downside_protection_pct=1,
            min_score=30,
        ),
    ),
)


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
    if filters.max_otm_pct < filters.min_otm_pct:
        raise ValueError("Maximum strike distance must be at least the minimum.")
    if filters.min_otm_pct < 0 or filters.max_otm_pct < 0:
        raise ValueError("Strike distance cannot be negative.")
    if filters.min_iv_pct < 0:
        raise ValueError("Minimum implied volatility cannot be negative.")
    if filters.min_downside_protection_pct < 0:
        raise ValueError("Minimum downside protection cannot be negative.")
    if filters.min_annualized_return_pct < 0:
        raise ValueError("Minimum annualized return cannot be negative.")
    if filters.min_score < 0 or filters.min_score > 100:
        raise ValueError("Minimum composite score must be between 0 and 100.")


def validate_mode(mode: str) -> str:
    cleaned = (mode or "").strip().lower()
    if cleaned not in MODES:
        raise ValueError("Mode must be classic or pre_earnings.")
    return cleaned


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


def _call_delta(row: pd.Series, spot: float, tte_years: float, iv_pct: float | None) -> float | None:
    if "delta" in row.index and row.get("delta") is not None and not pd.isna(row.get("delta")):
        return abs(float(row["delta"]))
    if iv_pct is None:
        return None
    iv = _iv_decimal(iv_pct)
    if iv <= 0:
        return None
    strike = float(row.get("strike") or 0)
    value = abs(options_chain_service.estimate_call_delta(strike, spot, tte_years, iv))
    return value if value > 0 else None


def contract_math(bid: float, strike: float, spot: float, dte: int) -> dict | None:
    """Return row math, or None when the inputs cannot price one covered call."""
    if bid <= 0 or strike <= 0 or spot <= 0 or dte <= 0:
        return None
    premium = bid * 100
    above_pct = ((strike - spot) / spot) * 100
    downside_pct = (bid / spot) * 100
    max_profit = ((strike - spot) * 100) + premium
    capital = spot * 100
    roc = (max_profit / capital) * 100
    annualized = roc * (365 / dte)
    return {
        "premium_per_contract": round(premium, 2),
        "otm_pct": round(above_pct, 2),
        "downside_protection_pct": round(downside_pct, 2),
        "max_profit_if_called": round(max_profit, 2),
        "return_on_capital_pct": round(roc, 3),
        "annualized_return_pct": round(annualized, 2),
        "breakeven": round(spot - bid, 2),
        "_annualized_raw": annualized,
        "_otm_raw": above_pct,
        "_downside_raw": downside_pct,
    }


def expiration_allowed(
    mode: str,
    expiration: date,
    dte: int,
    earnings_date: date | None,
    filters: ScanFilters,
    as_of: date,
) -> bool:
    """Classic drops calls that live through earnings. Pre-earnings keeps only those."""
    if mode == CLASSIC:
        if earnings_date is None:
            return True
        return expiration < earnings_date
    if earnings_date is None:
        return False
    earnings_dte = (earnings_date - as_of).days
    covers_report = earnings_date <= expiration
    in_window = filters.min_dte <= earnings_dte <= filters.max_dte
    return covers_report and in_window and filters.min_dte <= dte <= filters.max_dte


def expirations_in_window(
    expirations: list[str],
    filters: ScanFilters,
    as_of: date | None = None,
) -> list[tuple[str, date, int]]:
    ref = as_of or date.today()
    selected: list[tuple[str, date, int]] = []
    for exp_str in expirations:
        exp_date = options_chain_service._parse_expiration(exp_str)
        if not exp_date:
            continue
        days = options_chain_service._dte(exp_date, ref)
        if filters.min_dte <= days <= filters.max_dte:
            selected.append((exp_str, exp_date, days))
    return selected


def _public_contract(candidate: dict) -> dict:
    return {key: value for key, value in candidate.items() if not key.startswith("_")}


def apply_relative_scores(candidates: list[dict], min_score: float) -> list[dict]:
    """Score hard-filter survivors against each other, then drop scores under the minimum."""
    if not candidates:
        return []
    oi_norm = _minmax([float(row["_oi"]) for row in candidates])
    tight_norm = _minmax([float(row["_tightness"]) for row in candidates])
    return_norm = _minmax([float(row["_annualized_raw"]) for row in candidates])
    keep_norm = _minmax([float(row["_keep_raw"]) for row in candidates])
    iv_norm = _minmax([float(row["_iv_raw"]) for row in candidates])

    scored: list[dict] = []
    for index, candidate in enumerate(candidates):
        liquidity = 0.5 * oi_norm[index] + 0.5 * tight_norm[index]
        parts = {
            "liquidity_points": round(_LIQUIDITY_POINTS * liquidity, 2),
            "return_points": round(_RETURN_POINTS * return_norm[index], 2),
            "keep_points": round(_KEEP_POINTS * keep_norm[index], 2),
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
    expiration_date: date,
    dte: int,
    filters: ScanFilters,
    mode: str,
    earnings_date: date | None,
    as_of: date,
) -> list[dict]:
    """Calls that pass every hard filter. Score is applied later across the whole scan."""
    if chain is None or chain.empty or spot <= 0 or dte <= 0:
        return []
    if not expiration_allowed(mode, expiration_date, dte, earnings_date, filters, as_of):
        return []

    earnings_iso = earnings_date.isoformat() if earnings_date else None
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
        if bid <= 0:
            continue

        oi = options_chain_service._safe_int(row.get("openInterest"))
        if oi < filters.min_open_interest:
            continue

        iv_pct = _iv_pct(row.get("impliedVolatility"))
        if iv_pct is None or iv_pct < filters.min_iv_pct:
            continue

        delta = _call_delta(row, spot, tte_years, iv_pct)
        if delta is None or delta < filters.delta_min or delta > filters.delta_max:
            continue

        math = contract_math(bid, strike, spot, dte)
        if math is None:
            continue
        if math["_otm_raw"] < filters.min_otm_pct or math["_otm_raw"] > filters.max_otm_pct:
            continue
        if math["_downside_raw"] < filters.min_downside_protection_pct:
            continue
        if math["_annualized_raw"] < filters.min_annualized_return_pct:
            continue

        keep = 1.0 - delta
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
                "downside_protection_pct": math["downside_protection_pct"],
                "max_profit_if_called": math["max_profit_if_called"],
                "return_on_capital_pct": math["return_on_capital_pct"],
                "annualized_return_pct": math["annualized_return_pct"],
                "breakeven": math["breakeven"],
                "earnings_date": earnings_iso,
                "probability_of_keeping_premium": round(keep, 4),
                "_oi": float(oi),
                "_tightness": _tightness(bid, row.get("ask")),
                "_annualized_raw": math["_annualized_raw"],
                "_keep_raw": keep,
                "_iv_raw": iv_pct,
            }
        )
    return rows


def sort_contracts(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda c: (-c["composite_score"], c["expiration"], c["strike"]))


def _parse_earnings_date(events: dict) -> date | None:
    raw = events.get("earnings_date") if events else None
    if not raw:
        return None
    return options_chain_service._parse_expiration(str(raw)[:10])


def scan_calls(
    symbol: str,
    filters: ScanFilters | None = None,
    mode: str = CLASSIC,
    *,
    as_of: date | None = None,
) -> dict:
    filters = filters or ScanFilters()
    validate_scan_filters(filters)
    mode = validate_mode(mode)
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Ticker is required.")

    hist = stock_service.get_history(symbol, "5d")
    if hist is None or hist.empty:
        raise LookupError(f"No market data for '{symbol}'")
    spot = float(hist["Close"].iloc[-1])
    if spot <= 0 or pd.isna(spot):
        raise LookupError(f"No market data for '{symbol}'")

    ref = as_of or date.today()
    earnings_date = _parse_earnings_date(options_chain_service.get_upcoming_events(symbol))
    if mode == PRE_EARNINGS and earnings_date is None:
        raise ValueError("Yahoo has no earnings date for this ticker.")

    expirations = options_chain_service.get_expirations(symbol)
    if not expirations:
        raise LookupError(f"No options chain for '{symbol}'")

    candidates: list[dict] = []
    for exp_str, exp_date, dte in expirations_in_window(expirations, filters, ref):
        chain = options_chain_service.get_calls_chain(symbol, exp_str)
        candidates.extend(
            candidates_from_chain(
                chain,
                symbol=symbol,
                spot=spot,
                expiration=exp_str,
                expiration_date=exp_date,
                dte=dte,
                filters=filters,
                mode=mode,
                earnings_date=earnings_date,
                as_of=ref,
            )
        )

    return {
        "ticker": symbol,
        "spot": round(spot, 2),
        "scanned_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": mode,
        "earnings_date": earnings_date.isoformat() if earnings_date else None,
        "filters": filters_to_dict(filters),
        "contracts": sort_contracts(apply_relative_scores(candidates, filters.min_score)),
        "disclaimer": DISCLAIMER,
    }
