"""Options pre-execution screening and CSP post-execution monitoring (Issue #2)."""

from __future__ import annotations

from datetime import date

from backend.config import (
    CSP_BREACH_PCT,
    CSP_EVENT_HORIZON_DAYS,
    CSP_IV_REALIZED_MIN_RATIO,
    CSP_OTM_PCT_GOOD,
    CSP_TARGET_DELTA,
    TTL_OPTIONS_MONITOR,
)
from backend.cache import ttl_cache
from backend.schemas.csp import CspMonitorResponse, CspScreenResponse, CspVerdict, SuggestedContract
from backend.schemas.options import STRATEGY_META
from backend.services import options_chain_service, stock_service

# Contract suggestion rules per strategy. None = stock fundamentals only (no auto-fill leg).
_SCREEN_CONTRACT: dict[str, dict | None] = {
    "cash_secured_put": {
        "option_type": "put",
        "side": "sell_to_open",
        "target_delta": CSP_TARGET_DELTA,
        "note": "Primary short put (~0.30Δ).",
    },
    "short_put": {
        "option_type": "put",
        "side": "sell_to_open",
        "target_delta": CSP_TARGET_DELTA,
        "note": "Short put (~0.30Δ).",
    },
    "covered_call": {
        "option_type": "call",
        "side": "sell_to_open",
        "target_delta": CSP_TARGET_DELTA,
        "note": "Covered call (~0.30Δ). Assumes you already own 100 shares per contract.",
    },
    "short_call": {
        "option_type": "call",
        "side": "sell_to_open",
        "target_delta": CSP_TARGET_DELTA,
        "note": "Short call (~0.30Δ).",
    },
    "long_call": {
        "option_type": "call",
        "side": "buy_to_open",
        "target_delta": 0.50,
        "note": "Near-ATM long call (~0.50Δ).",
    },
    "long_put": {
        "option_type": "put",
        "side": "buy_to_open",
        "target_delta": 0.50,
        "note": "Near-ATM long put (~0.50Δ).",
    },
    "put_credit_spread": {
        "option_type": "put",
        "side": "sell_to_open",
        "target_delta": CSP_TARGET_DELTA,
        "note": "Short put leg only (~0.30Δ) — add the long put yourself.",
    },
    "call_credit_spread": {
        "option_type": "call",
        "side": "sell_to_open",
        "target_delta": CSP_TARGET_DELTA,
        "note": "Short call leg only (~0.30Δ) — add the long call yourself.",
    },
    "put_debit_spread": {
        "option_type": "put",
        "side": "buy_to_open",
        "target_delta": 0.50,
        "note": "Long put leg only (~0.50Δ) — add the short put yourself.",
    },
    "call_debit_spread": {
        "option_type": "call",
        "side": "buy_to_open",
        "target_delta": 0.50,
        "note": "Long call leg only (~0.50Δ) — add the short call yourself.",
    },
    "iron_condor": {
        "option_type": "put",
        "side": "sell_to_open",
        "target_delta": CSP_TARGET_DELTA,
        "note": "Short put wing only (~0.30Δ) — fill remaining legs yourself.",
    },
    "custom": None,
}


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


def _strategy_label(strategy: str) -> str:
    meta = STRATEGY_META.get(strategy) or {}
    return str(meta.get("label") or strategy.replace("_", " ").title())


def _build_markdown(pros: list[str], cons: list[str], verdict: CspVerdict, title: str) -> str:
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
    return analyze_stock_for_strategy(ticker_symbol, "cash_secured_put")


def analyze_stock_for_strategy(ticker_symbol: str, strategy: str | None = None) -> CspScreenResponse:
    symbol = ticker_symbol.strip().upper()
    if not symbol:
        raise ValueError("Ticker is required.")

    strategy_key = (strategy or "cash_secured_put").strip().lower()
    if strategy_key not in _SCREEN_CONTRACT:
        raise ValueError(f"Unsupported strategy for screening: {strategy_key}")
    label = _strategy_label(strategy_key)
    contract_cfg = _SCREEN_CONTRACT[strategy_key]

    hist = stock_service.get_history(symbol, "1y")
    if hist is None or hist.empty:
        raise LookupError(f"No market data for '{symbol}'")

    fundamentals = options_chain_service.get_fundamental_health(symbol)
    events = options_chain_service.get_upcoming_events(symbol, CSP_EVENT_HORIZON_DAYS)
    technicals = options_chain_service.get_ema_levels(hist)
    realized_vol = options_chain_service.realized_vol_30d(hist)
    spot = technicals["current_price"]

    pros: list[str] = []
    cons: list[str] = []
    risk_score = 0

    dte_ratio = fundamentals.get("debt_to_equity")
    if dte_ratio is not None:
        if dte_ratio < 100:
            pros.append(f"Debt-to-equity ({dte_ratio:.1f}) is moderate — balance sheet risk acceptable.")
        else:
            cons.append(f"Elevated debt-to-equity ({dte_ratio:.1f}) increases downside risk if stock falls.")
            risk_score += 1

    fcf = fundamentals.get("free_cash_flow")
    if fcf is not None:
        if fcf > 0:
            pros.append("Positive free cash flow supports fundamental health.")
        else:
            cons.append("Negative free cash flow — fundamental drag if you hold or get assigned shares.")
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

    exp_str: str | None = None
    dte: int | None = None
    suggested: dict | None = None
    suggested_contract: SuggestedContract | None = None
    margin_otm = None
    iv_ratio = None

    if contract_cfg is not None:
        exp_str, dte = options_chain_service.pick_expiration_in_dte_window(symbol)
        if not exp_str:
            raise LookupError(f"No options expiration found in {30}-{45} DTE window for '{symbol}'")

        exp_date = options_chain_service._parse_expiration(exp_str)
        if not exp_date:
            raise LookupError(f"Could not parse expiration '{exp_str}' for '{symbol}'")

        option_type = contract_cfg["option_type"]
        target_delta = float(contract_cfg["target_delta"])
        side = contract_cfg["side"]
        chain = (
            options_chain_service.get_calls_chain(symbol, exp_str)
            if option_type == "call"
            else options_chain_service.get_puts_chain(symbol, exp_str)
        )
        suggested = options_chain_service.find_option_near_delta(
            chain, spot, exp_date, option_type=option_type, target_delta=target_delta
        )

        if suggested:
            suggested_contract = SuggestedContract(
                strike=suggested["strike"],
                expiration=exp_str,
                dte=dte or 0,
                premium_mid=suggested["premium_mid"],
                delta=suggested["delta"],
                option_type=option_type,
                side=side,
                target_delta=target_delta,
                implied_volatility=suggested.get("implied_volatility"),
                bid=suggested.get("bid"),
                ask=suggested.get("ask"),
                spread_pct=suggested.get("spread_pct"),
                open_interest=suggested.get("open_interest"),
                volume=suggested.get("volume"),
                otm_pct=suggested.get("otm_pct"),
                liquidity_ok=suggested.get("liquidity_ok", True),
                note=contract_cfg.get("note"),
            )
            otm = suggested.get("otm_pct") or 0
            margin_otm = otm if otm > 0 else 0
            opt_label = "call" if option_type == "call" else "put"
            delta_label = f"~{target_delta:.2f}-delta"
            is_short = side == "sell_to_open"

            if is_short:
                if margin_otm >= CSP_OTM_PCT_GOOD:
                    pros.append(
                        f"Suggested {delta_label} {opt_label} is {margin_otm:.1f}% OTM — reasonable margin of safety."
                    )
                elif margin_otm > 0:
                    cons.append(f"Suggested {opt_label} only {margin_otm:.1f}% OTM — limited buffer.")
                    risk_score += 1
                else:
                    cons.append(f"Suggested {opt_label} is at or in the money — elevated assignment risk.")
                    risk_score += 2
            else:
                if abs(otm) <= 3:
                    pros.append(f"Suggested {delta_label} {opt_label} is near ATM — typical for long premium.")
                elif otm > 0:
                    pros.append(f"Suggested long {opt_label} is {otm:.1f}% OTM.")
                else:
                    cons.append(f"Suggested long {opt_label} is ITM ({abs(otm):.1f}%) — higher cost / less leverage.")
                    risk_score += 1

            if not suggested.get("liquidity_ok"):
                cons.append("Wide bid-ask spread or low open interest on suggested contract.")
                risk_score += 1
            else:
                pros.append("Suggested contract has acceptable liquidity (spread/OI).")
    else:
        pros.append("Custom strategy — stock suitability only; pick legs manually.")

    iv = suggested.get("implied_volatility") if suggested else None
    if iv and realized_vol and realized_vol > 0:
        iv_pct = iv * 100 if iv < 3 else iv
        iv_ratio = iv_pct / realized_vol
        if contract_cfg and contract_cfg.get("side") == "buy_to_open":
            if iv_ratio >= CSP_IV_REALIZED_MIN_RATIO:
                cons.append(f"IV rich vs realized (ratio {iv_ratio:.2f}) — long premium may be expensive.")
                risk_score += 1
            else:
                pros.append(f"IV vs 30d realized looks reasonable for buying premium (ratio {iv_ratio:.2f}).")
        else:
            if iv_ratio >= CSP_IV_REALIZED_MIN_RATIO:
                pros.append(
                    f"Implied vol ({iv_pct:.1f}%) vs 30d realized ({realized_vol:.1f}%) — premiums relatively rich."
                )
            else:
                cons.append(f"IV below realized vol (ratio {iv_ratio:.2f}) — premium may not compensate for risk.")
                risk_score += 1
    elif realized_vol:
        pros.append(f"30-day realized volatility: {realized_vol:.1f}% (IV unavailable for comparison).")

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
        if suggested_contract:
            summary = f"Key metrics favor a {label.lower()} near the suggested strike."
        else:
            summary = f"Key metrics look favorable for {label.lower()} on this ticker (no auto contract)."

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

    md = _build_markdown(pros, cons, verdict, f"{label} Pre-Execution: {symbol}")

    return CspScreenResponse(
        ticker=symbol,
        strategy=strategy_key,
        strategy_label=label,
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
        bid=contract.get("bid") if contract else None,
        ask=contract.get("ask") if contract else None,
        spread_pct=contract.get("spread_pct") if contract else None,
        open_interest=contract.get("open_interest") if contract else None,
        liquidity_ok=contract.get("liquidity_ok") if contract else None,
    )
