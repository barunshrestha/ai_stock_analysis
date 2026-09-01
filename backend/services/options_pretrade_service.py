"""Pre-trade indicator checklist before committing an options trade."""

from __future__ import annotations

from datetime import date

from backend.config import (
    PRETRADE_ANNUALIZED_ROC_GOOD,
    PRETRADE_DTE_CAUTION,
    PRETRADE_DTE_GOOD_MAX,
    PRETRADE_DTE_GOOD_MIN,
    PRETRADE_OTM_PCT_CAUTION,
    PRETRADE_OTM_PCT_GOOD,
)
from backend.schemas.options import (
    IndicatorStatus,
    OptionTradeCreate,
    PreTradeAnalysis,
    PreTradeIndicator,
)
from backend.services import options_metrics_service, stock_service


def _status_score(status: IndicatorStatus) -> int:
    return {"good": 0, "neutral": 1, "caution": 2, "bad": 3}[status.value]


def _overall_score(indicators: list[PreTradeIndicator]) -> str:
    if not indicators:
        return "mixed"
    worst = max(_status_score(i.status) for i in indicators)
    if worst >= 3:
        return "high_risk"
    if worst >= 2:
        return "mixed"
    return "favorable"


def _earnings_before_expiry(ticker: str, exp: date) -> tuple[bool, str | None]:
    try:
        info = stock_service.get_info(ticker)
        raw = info.get("earningsTimestamp") or info.get("earningsDate")
        if not raw:
            return False, None
        if isinstance(raw, (list, tuple)) and raw:
            raw = raw[0]
        if hasattr(raw, "date"):
            earn_date = raw.date() if callable(getattr(raw, "date", None)) else raw
        elif isinstance(raw, (int, float)):
            from datetime import datetime

            earn_date = datetime.fromtimestamp(raw).date()
        else:
            return False, None
        if earn_date <= exp:
            return True, earn_date.isoformat()
    except Exception:
        pass
    return False, None


def analyze_pretrade(trade: OptionTradeCreate) -> PreTradeAnalysis:
    metrics = options_metrics_service.compute_metrics(trade)
    indicators: list[PreTradeIndicator] = []
    recommendations: list[str] = []

    dte = metrics["days_to_expiration"]
    if PRETRADE_DTE_GOOD_MIN <= dte <= PRETRADE_DTE_GOOD_MAX:
        dte_status = IndicatorStatus.good
        dte_impact = "30–45 DTE is a common theta-efficiency window for short premium."
    elif dte < PRETRADE_DTE_CAUTION:
        dte_status = IndicatorStatus.bad if dte < 7 else IndicatorStatus.caution
        dte_impact = "Short DTE increases gamma risk; rolls and assignment happen faster."
        recommendations.append("Consider 30+ DTE unless intentionally trading weekly premium.")
    else:
        dte_status = IndicatorStatus.neutral
        dte_impact = "Longer DTE reduces gamma but ties up capital longer."

    indicators.append(
        PreTradeIndicator(
            id="dte",
            label="Days to expiration",
            value=str(dte),
            status=dte_status,
            impact=dte_impact,
        )
    )

    ann_roc = metrics.get("annualized_roc_pct") or 0
    if ann_roc >= PRETRADE_ANNUALIZED_ROC_GOOD:
        roc_status = IndicatorStatus.good
    elif ann_roc >= PRETRADE_ANNUALIZED_ROC_GOOD * 0.5:
        roc_status = IndicatorStatus.neutral
    else:
        roc_status = IndicatorStatus.caution
    indicators.append(
        PreTradeIndicator(
            id="annualized_roc",
            label="Annualized return on capital",
            value=f"{ann_roc:.1f}%",
            status=roc_status,
            impact="Higher ROC improves return if the trade succeeds; verify it justifies defined risk.",
            annualized=f"{ann_roc:.1f}%",
        )
    )

    try:
        hist = stock_service.get_history(trade.ticker, "6mo")
        info = stock_service.get_info(trade.ticker)
        spot = metrics.get("short_strike") and hist["Close"].iloc[-1] if not hist.empty else None
        short_strike = metrics.get("short_strike")
        if spot and short_strike:
            if trade.strategy_type.value in ("cash_secured_put", "short_put", "put_credit_spread"):
                otm_pct = (short_strike - spot) / spot * 100
            elif trade.strategy_type.value in ("covered_call", "short_call", "call_credit_spread"):
                otm_pct = (spot - short_strike) / spot * 100
            else:
                otm_pct = abs(short_strike - spot) / spot * 100

            if otm_pct >= PRETRADE_OTM_PCT_GOOD:
                otm_status = IndicatorStatus.good
            elif otm_pct >= PRETRADE_OTM_PCT_CAUTION:
                otm_status = IndicatorStatus.neutral
            else:
                otm_status = IndicatorStatus.caution
            indicators.append(
                PreTradeIndicator(
                    id="otm_distance",
                    label="Short strike distance from spot",
                    value=f"{otm_pct:.1f}% OTM",
                    status=otm_status,
                    impact="Further OTM short strikes generally reduce assignment probability.",
                )
            )

        trend = stock_service.compute_trend_context(hist) if not hist.empty else None
        if trend:
            indicators.append(
                PreTradeIndicator(
                    id="trend",
                    label="Underlying trend",
                    value=trend["trend_label"],
                    status=IndicatorStatus.neutral,
                    impact=f"Price ${trend['latest_price']:.2f}; support ${trend['support']:.2f}, resistance ${trend['resistance']:.2f}.",
                )
            )

        vol = info.get("averageVolume") or info.get("averageDailyVolume10Day")
        if vol and vol < 500_000:
            indicators.append(
                PreTradeIndicator(
                    id="liquidity",
                    label="Underlying liquidity",
                    value=f"Avg vol {vol:,.0f}",
                    status=IndicatorStatus.caution,
                    impact="Lower volume can mean wider option spreads and harder exits.",
                )
            )
    except Exception:
        recommendations.append("Could not fetch live quote — verify strike distance manually.")

    has_earn, earn_date = _earnings_before_expiry(trade.ticker, trade.expiration_date)
    if has_earn:
        indicators.append(
            PreTradeIndicator(
                id="earnings_before_expiry",
                label="Earnings before expiration",
                value=f"Yes — {earn_date}",
                status=IndicatorStatus.bad,
                impact="Gap and IV risk can move the stock through your strike quickly.",
            )
        )
        recommendations.append("Consider expiring after earnings or using a wider strike.")
    else:
        indicators.append(
            PreTradeIndicator(
                id="earnings_before_expiry",
                label="Earnings before expiration",
                value="None detected",
                status=IndicatorStatus.good,
                impact="No known earnings conflict before expiration.",
            )
        )

    if metrics.get("max_loss_dollars") is not None:
        indicators.append(
            PreTradeIndicator(
                id="max_loss",
                label="Defined max loss",
                value=f"${metrics['max_loss_dollars']:,.2f}",
                status=IndicatorStatus.neutral,
                impact="Ensure max loss fits your portfolio risk budget.",
            )
        )

    overall = _overall_score(indicators)
    bad_labels = [i.label for i in indicators if i.status == IndicatorStatus.bad]
    if bad_labels:
        summary = f"Review carefully: {', '.join(bad_labels)} flagged."
    elif overall == "favorable":
        summary = "Key metrics look reasonable for this strategy — confirm sizing and macro context."
    else:
        summary = "Mixed signals — adjust strike, DTE, or size before entering."

    return PreTradeAnalysis(
        overall_score=overall,
        summary=summary,
        indicators=indicators,
        recommendations=recommendations,
    )
