"""CSP pre-execution screening and post-execution monitoring (Issue #2)."""

from __future__ import annotations

from datetime import date, datetime

from backend.config import (
    CSP_BREACH_PCT,
    CSP_EVENT_HORIZON_DAYS,
    CSP_IV_REALIZED_MIN_RATIO,
    CSP_OTM_PCT_GOOD,
    TTL_OPTIONS_MONITOR,
)
from backend.cache import ttl_cache
from backend.schemas.csp import CspMonitorResponse, CspScreenResponse, CspVerdict, SuggestedContract
from backend.services import options_chain_service, stock_service


def compute_unrealized_pnl_pct(initial_premium: float, current_mid: float | None) -> float | None:
    if current_mid is None or initial_premium <= 0:
        return None
    return round((initial_premium - current_mid) / initial_premium * 100, 2)


def compute_trigger_close_alert(initial_premium: float, current_mid: float | None) -> bool:
    return current_mid is not None and current_mid <= initial_premium * 0.50


def compute_breached(spot: float | None, strike_price: float, breach_pct: float = CSP_BREACH_PCT) -> bool:
    if spot is None:
        return False
    if spot <= strike_price:
        return True
    if strike_price > 0:
        distance_pct = (spot - strike_price) / strike_price * 100
        if distance_pct <= breach_pct:
            return True
    return False


def _build_markdown(pros: list[str], cons: list[str], verdict: CspVerdict, title: str = "CSP Analysis") -> str:
    lines = [f"## {title}", ""]
    lines.append("### Pros (Premium Efficiency and Safety Drivers)")
    for p in pros or ["None identified."]:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("### Cons (Capital Risks and Drag Factors)")
    for c in cons or ["None identified."]:
        lines.append(f"- {c}")
    lines.append("")
    lines.append("### Professional Verdict and Strike Suggestion")
    lines.append(f"- {verdict.summary}")
    if verdict.recommended_strike:
        lines.append(f"- Recommended strike: ${verdict.recommended_strike:.2f}")
    if verdict.margin_of_safety_pct is not None:
        lines.append(f"- Margin of safety (OTM): {verdict.margin_of_safety_pct:.1f}%")
    lines.append("")
    lines.append("*Not financial advice — for journaling and education only.*")
    return "\n".join(lines)


def analyze_stock_for_csp(ticker_symbol: str) -> CspScreenResponse:
    symbol = ticker_symbol.strip().upper()
    if not symbol:
        raise ValueError("Ticker is required.")

    hist = stock_service.get_history(symbol, "1y")
    if hist is None or hist.empty:
        raise LookupError(f"No market data for '{symbol}'")

    fundamentals = options_chain_service.get_fundamental_health(symbol)
    events = options_chain_service.get_upcoming_events(symbol, CSP_EVENT_HORIZON_DAYS)
    technicals = options_chain_service.get_ema_levels(hist)
    realized_vol = options_chain_service.realized_vol_30d(hist)

    exp_str, dte = options_chain_service.pick_expiration_in_dte_window(symbol)
    if not exp_str:
        raise LookupError(f"No options expiration found in {30}-{45} DTE window for '{symbol}'")

    exp_date = options_chain_service._parse_expiration(exp_str)
    if not exp_date:
        raise LookupError(f"Could not parse expiration '{exp_str}' for '{symbol}'")

    puts = options_chain_service.get_puts_chain(symbol, exp_str)
    spot = technicals["current_price"]
    suggested = options_chain_service.find_put_near_delta(puts, spot, exp_date)

    pros: list[str] = []
    cons: list[str] = []
    risk_score = 0

    dte_ratio = fundamentals.get("debt_to_equity")
    if dte_ratio is not None:
        if dte_ratio < 100:
            pros.append(f"Debt-to-equity ({dte_ratio:.1f}) is moderate — balance sheet risk acceptable.")
        else:
            cons.append(f"Elevated debt-to-equity ({dte_ratio:.1f}) increases assignment risk if stock falls.")
            risk_score += 1

    fcf = fundamentals.get("free_cash_flow")
    if fcf is not None:
        if fcf > 0:
            pros.append("Positive free cash flow supports fundamental health.")
        else:
            cons.append("Negative free cash flow — fundamental drag on long-term hold if assigned.")
            risk_score += 1

    if events["earnings_within_horizon"]:
        cons.append(f"Earnings scheduled within {CSP_EVENT_HORIZON_DAYS} days ({events['earnings_date']}) — gap risk.")
        risk_score += 2
    else:
        pros.append("No earnings conflict detected within the event horizon.")

    if events["ex_dividend_within_horizon"]:
        cons.append(f"Ex-dividend date within {CSP_EVENT_HORIZON_DAYS} days ({events['ex_dividend_date']}).")
        risk_score += 1
    else:
        pros.append("No ex-dividend conflict in the horizon window.")

    if technicals.get("above_ema_50"):
        pros.append(f"Price (${spot:.2f}) is above 50-day EMA (${technicals['ema_50']:.2f}) — supportive trend.")
    elif technicals.get("ema_50"):
        cons.append(f"Price below 50-day EMA (${technicals['ema_50']:.2f}) — weaker near-term support.")
        risk_score += 1

    if technicals.get("above_ema_200") is False and technicals.get("ema_200"):
        cons.append(f"Price below 200-day EMA (${technicals['ema_200']:.2f}) — longer-term downtrend.")
        risk_score += 1
    elif technicals.get("above_ema_200"):
        pros.append(f"Price above 200-day EMA (${technicals['ema_200']:.2f}).")

    iv = suggested.get("implied_volatility") if suggested else None
    iv_ratio = None
    if iv and realized_vol and realized_vol > 0:
        iv_pct = iv * 100 if iv < 3 else iv
        iv_ratio = iv_pct / realized_vol
        if iv_ratio >= CSP_IV_REALIZED_MIN_RATIO:
            pros.append(f"Implied vol ({iv_pct:.1f}%) vs 30d realized ({realized_vol:.1f}%) — premiums relatively rich.")
        else:
            cons.append(f"IV below realized vol (ratio {iv_ratio:.2f}) — premium may not compensate for risk.")
            risk_score += 1
    elif realized_vol:
        pros.append(f"30-day realized volatility: {realized_vol:.1f}% (IV unavailable for comparison).")

    suggested_contract: SuggestedContract | None = None
    margin_otm = None
    if suggested:
        suggested_contract = SuggestedContract(
            strike=suggested["strike"],
            expiration=exp_str,
            dte=dte or 0,
            premium_mid=suggested["premium_mid"],
            delta=suggested["delta"],
            implied_volatility=suggested.get("implied_volatility"),
            bid=suggested.get("bid"),
            ask=suggested.get("ask"),
            spread_pct=suggested.get("spread_pct"),
            open_interest=suggested.get("open_interest"),
            volume=suggested.get("volume"),
            otm_pct=suggested.get("otm_pct"),
            liquidity_ok=suggested.get("liquidity_ok", True),
        )
        otm = suggested.get("otm_pct") or 0
        margin_otm = otm if otm > 0 else 0
        if margin_otm >= CSP_OTM_PCT_GOOD:
            pros.append(f"Suggested ~0.30-delta put is {margin_otm:.1f}% OTM — reasonable margin of safety.")
        elif margin_otm > 0:
            cons.append(f"Suggested put only {margin_otm:.1f}% OTM — limited buffer.")
            risk_score += 1
        else:
            cons.append("Suggested put is at or in the money — high assignment risk.")
            risk_score += 2
        if not suggested.get("liquidity_ok"):
            cons.append("Wide bid-ask spread or low open interest on suggested contract.")
            risk_score += 1
        else:
            pros.append("Suggested contract has acceptable liquidity (spread/OI).")

    if risk_score >= 3:
        overall = "high_risk"
        color = "red"
        summary = "Multiple risk factors — consider skipping or adjusting strike/DTE."
    elif risk_score >= 1:
        overall = "mixed"
        color = "red" if risk_score >= 2 else "green"
        summary = "Mixed signals — review cons before entering."
    else:
        overall = "favorable"
        color = "green"
        summary = "Key metrics favor a cash-secured put at the suggested strike."

    verdict = CspVerdict(
        recommended_strike=suggested["strike"] if suggested else None,
        margin_of_safety_pct=margin_otm,
        summary=summary,
    )

    sections = {
        "fundamentals": {**fundamentals, **events},
        "technicals": technicals,
        "volatility": {
            "realized_vol_30d_pct": round(realized_vol, 2) if realized_vol else None,
            "implied_volatility": suggested.get("implied_volatility") if suggested else None,
            "iv_vs_realized_ratio": round(iv_ratio, 2) if iv_ratio else None,
            "expiration": exp_str,
            "dte": dte,
        },
        "suggested_contract": suggested,
    }

    md = _build_markdown(pros, cons, verdict, f"CSP Pre-Execution: {symbol}")

    return CspScreenResponse(
        ticker=symbol,
        overall_verdict=overall,
        recommendation_color=color,
        sections=sections,
        pros=pros,
        cons=cons,
        verdict=verdict,
        markdown=md,
        suggested_contract=suggested_contract,
    )


def monitor_active_csp(
    ticker_symbol: str,
    strike_price: float,
    expiration_date: date,
    initial_premium: float,
) -> CspMonitorResponse:
    return _monitor_active_csp_cached(
        ticker_symbol.strip().upper(),
        strike_price,
        expiration_date.isoformat(),
        initial_premium,
    )


@ttl_cache(TTL_OPTIONS_MONITOR)
def _monitor_active_csp_cached(
    symbol: str,
    strike_price: float,
    exp_str: str,
    initial_premium: float,
) -> CspMonitorResponse:
    expiration_date = options_chain_service._parse_expiration(exp_str) or date.today()

    hist = stock_service.get_history(symbol, "5d")
    spot = float(hist["Close"].iloc[-1]) if hist is not None and not hist.empty else None

    contract = options_chain_service.find_put_at_strike(symbol, exp_str, strike_price)
    current_mid = contract.get("premium_mid") if contract else None

    unrealized_pct = compute_unrealized_pnl_pct(initial_premium, current_mid)
    trigger_close = compute_trigger_close_alert(initial_premium, current_mid)
    breached = compute_breached(spot, strike_price)

    net_basis = round(strike_price - initial_premium, 2)
    profitable = unrealized_pct is not None and unrealized_pct > 0
    color: str = "green" if profitable and not breached else "red"

    if trigger_close:
        rec = "50% max profit reached — consider buying to close (professional BTC rule)."
    elif breached:
        rec = f"Stock testing strike zone — prepare to roll for net credit or accept assignment at ~${net_basis:.2f} basis."
    elif profitable:
        rec = f"Position profitable ({unrealized_pct:.1f}% of max premium captured)."
    else:
        rec = "Position underwater — monitor closely; review defensive roll rules."

    md_lines = [
        f"## CSP Monitor: {symbol}",
        "",
        f"- Strike: ${strike_price:.2f} | Exp: {exp_str}",
        f"- Initial premium: ${initial_premium:.2f} | Current mid: ${current_mid:.2f}" if current_mid else f"- Initial premium: ${initial_premium:.2f}",
        f"- Unrealized P&L: {unrealized_pct:.1f}%" if unrealized_pct is not None else "- Unrealized P&L: N/A",
        f"- 50% close alert: {'YES' if trigger_close else 'No'}",
        f"- Breach alert: {'YES' if breached else 'No'}",
        f"- Net cost basis if assigned: ${net_basis:.2f}",
        "",
        f"**Recommendation:** {rec}",
        "",
        "*Not financial advice — for journaling and education only.*",
    ]

    return CspMonitorResponse(
        ticker=symbol,
        strike_price=strike_price,
        expiration_date=exp_str,
        initial_premium=initial_premium,
        current_spot=round(spot, 2) if spot else None,
        current_mid=current_mid,
        unrealized_pnl_pct=unrealized_pct,
        trigger_close_alert=trigger_close,
        breached=breached,
        net_cost_basis=net_basis,
        recommendation_color=color,
        recommendation=rec,
        markdown="\n".join(md_lines),
    )
