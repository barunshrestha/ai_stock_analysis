"""Simple educational FCF DCF sketch for Issue #9 (not a full IB model)."""

from __future__ import annotations

from typing import Any


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_simple_dcf(metrics: dict) -> dict | None:
    """
    5-year FCF DCF with terminal growth.
    Returns None when free cash flow or shares/price inputs are unusable.
    """
    cash = metrics.get("balance_sheet_cash") or {}
    growth = metrics.get("growth") or {}
    market = metrics.get("market") or {}
    valuation = metrics.get("valuation") or {}

    fcf = _f(cash.get("free_cash_flow"))
    if fcf is None or fcf <= 0:
        return None

    price = _f(market.get("price"))
    market_cap = _f(valuation.get("market_cap"))
    if price is None or price <= 0 or market_cap is None or market_cap <= 0:
        return None

    shares = market_cap / price
    if shares <= 0:
        return None

    g_raw = _f(growth.get("revenue_growth_pct"))
    # revenue_growth_pct is already percent; fall back to 5%
    if g_raw is None:
        growth_pct = 5.0
    else:
        growth_pct = max(-5.0, min(25.0, g_raw))

    beta = _f(market.get("beta")) or 1.0
    discount_pct = max(8.0, min(14.0, 8.0 + 2.0 * max(beta - 1.0, 0.0)))
    terminal_growth_pct = 2.5

    g = growth_pct / 100.0
    r = discount_pct / 100.0
    tg = terminal_growth_pct / 100.0
    if r <= tg:
        return None

    pv = 0.0
    last_fcf = fcf
    for year in range(1, 6):
        last_fcf = last_fcf * (1.0 + g)
        pv += last_fcf / ((1.0 + r) ** year)

    terminal_value = last_fcf * (1.0 + tg) / (r - tg)
    pv += terminal_value / ((1.0 + r) ** 5)

    implied = pv / shares
    vs_price_pct = round((implied - price) / price * 100.0, 2)

    return {
        "fcf": round(fcf, 2),
        "shares_outstanding_est": round(shares, 2),
        "growth_pct": round(growth_pct, 2),
        "discount_pct": round(discount_pct, 2),
        "terminal_growth_pct": terminal_growth_pct,
        "implied_value_per_share": round(implied, 2),
        "price": round(price, 2),
        "vs_price_pct": vs_price_pct,
        "assumptions": (
            "5-year FCF projection; growth from revenue_growth_pct clamped −5%…25% "
            "(default 5%); terminal growth 2.5%; discount 8%+2%×max(beta−1,0) capped 8–14%. "
            "Educational sketch only — not a full DCF."
        ),
    }
