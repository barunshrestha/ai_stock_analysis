"""Collateral, ROC, and P&L calculations for options trades."""

from __future__ import annotations

from datetime import date, datetime

from backend.schemas.options import LegInput, OptionTradeCreate, STRATEGY_META


def _short_legs(legs: list[LegInput]) -> list[LegInput]:
    return [l for l in legs if l.side.value in ("sell_to_open", "sell_to_close")]


def _long_legs(legs: list[LegInput]) -> list[LegInput]:
    return [l for l in legs if l.side.value in ("buy_to_open", "buy_to_close")]


def compute_collateral(
    strategy_type: str,
    legs: list[LegInput],
    contracts: int,
    net_credit_debit: float,
    override: float | None = None,
) -> float:
    if override is not None:
        return round(override, 2)

    st = strategy_type
    puts = [l for l in legs if l.option_type.value == "put"]
    calls = [l for l in legs if l.option_type.value == "call"]

    if st == "cash_secured_put" and puts:
        return round(puts[0].strike * 100 * contracts, 2)
    if st == "covered_call" and calls:
        return round(calls[0].strike * 100 * contracts, 2)
    if st in ("put_credit_spread", "put_debit_spread") and len(puts) >= 2:
        strikes = sorted([p.strike for p in puts], reverse=True)
        width = abs(strikes[0] - strikes[1])
        return round(width * 100 * contracts, 2)
    if st in ("call_credit_spread", "call_debit_spread") and len(calls) >= 2:
        strikes = sorted([c.strike for c in calls])
        width = abs(strikes[-1] - strikes[0])
        return round(width * 100 * contracts, 2)
    if st == "iron_condor" and len(legs) >= 4:
        put_strikes = sorted([l.strike for l in puts])
        call_strikes = sorted([l.strike for l in calls])
        put_width = abs(put_strikes[-1] - put_strikes[0]) if len(put_strikes) >= 2 else 0
        call_width = abs(call_strikes[-1] - call_strikes[0]) if len(call_strikes) >= 2 else 0
        width = max(put_width, call_width)
        return round(width * 100 * contracts, 2)
    if st in ("long_call", "long_put"):
        return round(abs(net_credit_debit) * 100 * contracts, 2)
    if st in ("short_put", "short_call", "custom"):
        short = _short_legs(legs)
        if short:
            return round(short[0].strike * 100 * contracts, 2)
    return round(max(abs(net_credit_debit) * 100 * contracts, 1), 2)


def compute_metrics(trade: OptionTradeCreate) -> dict:
    collateral = compute_collateral(
        trade.strategy_type.value,
        trade.legs,
        trade.contracts,
        trade.net_credit_debit,
        trade.collateral_override,
    )
    total_premium = trade.net_credit_debit * 100 * trade.contracts
    dte = max((trade.expiration_date - trade.executed_at.date()).days, 1)
    roc = (total_premium / collateral * 100) if collateral else 0
    annualized_roc = roc * (365 / dte)

    meta = STRATEGY_META.get(trade.strategy_type.value, {})
    short_premium = meta.get("short_premium")

    short_strike = None
    short_puts = [l for l in trade.legs if l.option_type.value == "put" and l.side.value == "sell_to_open"]
    short_calls = [l for l in trade.legs if l.option_type.value == "call" and l.side.value == "sell_to_open"]
    if short_puts:
        short_strike = short_puts[0].strike
    elif short_calls:
        short_strike = short_calls[0].strike

    breach_price = None
    assignment_basis = None
    if short_premium and short_strike is not None:
        if short_puts:
            breach_price = round(short_strike - trade.net_credit_debit, 2)
            assignment_basis = breach_price
        elif short_calls:
            breach_price = round(short_strike + trade.net_credit_debit, 2)
            assignment_basis = breach_price

    max_profit = total_premium if (short_premium or trade.net_credit_debit > 0) else None
    max_loss = None
    if trade.strategy_type.value in ("put_credit_spread", "call_credit_spread", "iron_condor"):
        max_loss = round(collateral - abs(total_premium), 2) if total_premium > 0 else collateral
    elif not short_premium and trade.net_credit_debit < 0:
        max_loss = round(abs(total_premium), 2)

    return {
        "collateral_required": collateral,
        "total_premium_dollars": round(total_premium, 2),
        "days_to_expiration": dte,
        "return_on_capital_pct": round(roc, 3),
        "annualized_roc_pct": round(annualized_roc, 2),
        "premium_pct_of_strike": round(
            (trade.net_credit_debit / short_strike * 100) if short_strike else 0, 3
        ),
        "breach_price": breach_price,
        "assignment_cost_basis": assignment_basis,
        "btc_50pct_target_per_contract": round(trade.net_credit_debit * 0.5, 2)
        if short_premium and trade.net_credit_debit > 0
        else None,
        "max_profit_dollars": round(max_profit, 2) if max_profit is not None else None,
        "max_loss_dollars": max_loss,
        "short_strike": short_strike,
        "is_short_premium": bool(short_premium),
    }


def compute_close_pnl(
    net_credit_debit: float,
    close_net_per_contract: float,
    contracts: int,
    is_short_premium: bool,
    assigned: bool = False,
) -> float:
    if assigned:
        return round(net_credit_debit * 100 * contracts, 2)
    if is_short_premium:
        return round((net_credit_debit - close_net_per_contract) * 100 * contracts, 2)
    return round((close_net_per_contract - abs(net_credit_debit)) * 100 * contracts, 2)


def trade_to_db_payload(trade: OptionTradeCreate, metrics: dict, advisory: dict) -> tuple[dict, list[dict]]:
    import json

    trade_row = {
        "status": "open",
        "strategy_type": trade.strategy_type.value,
        "ticker": trade.ticker,
        "broker": trade.broker.value if trade.broker else None,
        "executed_at": trade.executed_at,
        "expiration_date": datetime.combine(trade.expiration_date, datetime.min.time()),
        "contracts": trade.contracts,
        "net_credit_debit": trade.net_credit_debit,
        "collateral_required": metrics["collateral_required"],
        "collateral_override": trade.collateral_override,
        "notes": trade.notes,
        "metrics_json": json.dumps(metrics),
        "advisory_json": json.dumps(advisory),
    }
    leg_rows = []
    for leg in trade.legs:
        exp = leg.expiration_date or trade.expiration_date
        leg_rows.append(
            {
                "leg_index": leg.leg_index,
                "option_type": leg.option_type.value,
                "side": leg.side.value,
                "strike": leg.strike,
                "premium_per_contract": leg.premium_per_contract,
                "expiration_date": datetime.combine(exp, datetime.min.time()),
            }
        )
    return trade_row, leg_rows
