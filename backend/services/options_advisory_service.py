"""Post-trade management advisory for options positions."""

from __future__ import annotations

from backend.schemas.options import STRATEGY_META


DISCLAIMER = "Not financial advice — for journaling and education only."


def build_advisory(strategy_type: str, metrics: dict, ticker: str) -> dict:
    meta = STRATEGY_META.get(strategy_type, {})
    short_premium = metrics.get("is_short_premium", False)
    dte = metrics.get("days_to_expiration", 0)
    advisory: dict = {"disclaimer": DISCLAIMER, "strategy_label": meta.get("label", strategy_type)}

    if short_premium and metrics.get("btc_50pct_target_per_contract") is not None:
        target = metrics["btc_50pct_target_per_contract"]
        max_profit = metrics.get("max_profit_dollars") or metrics.get("total_premium_dollars", 0)
        advisory["profit_taking"] = {
            "rule": "50pct_max_profit",
            "btc_target_per_contract": target,
            "target_profit_dollars": round(max_profit * 0.5, 2),
            "recommendation": f"Set alert to buy back when option mark <= ${target:.2f} per contract.",
        }

    if metrics.get("breach_price") is not None:
        breach = metrics["breach_price"]
        advisory["defensive"] = {
            "trigger_price": breach,
            "roll_playbook": [
                f"Monitor {ticker} approaching ${breach:.2f} (breach zone).",
                "Quote a roll: lower strike (puts) or higher strike (calls) + later expiration.",
                "Execute roll only if net credit > $0 after closing the current leg.",
                "If no net credit is available, close for a defined loss or prepare for assignment.",
            ],
        }

    if metrics.get("assignment_cost_basis") is not None:
        basis = metrics["assignment_cost_basis"]
        collateral = metrics.get("collateral_required", 0)
        advisory["assignment"] = {
            "net_cost_basis_per_share": basis,
            "cash_required": collateral,
            "shares_if_assigned": None,
            "note": f"If assigned, effective stock price is approximately ${basis:.2f} per share.",
        }

    advisory["risk_management"] = {
        "annualized_roc_pct": metrics.get("annualized_roc_pct"),
        "return_on_capital_pct": metrics.get("return_on_capital_pct"),
        "dte_reminder": "Consider closing or rolling before 21 DTE to reduce gamma risk."
        if dte <= 21
        else "Manage position size relative to total buying power.",
    }

    if not short_premium:
        advisory["debit_strategy"] = {
            "max_loss_dollars": metrics.get("max_loss_dollars"),
            "recommendation": "Define exit at 50% loss or 21 DTE if thesis is invalidated.",
        }

    return advisory
