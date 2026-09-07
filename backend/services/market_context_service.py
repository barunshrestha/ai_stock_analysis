"""Aggregated macro market context for the options sidebar."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.cache import ttl_cache
from backend.config import TTL_MARKET_CONTEXT
from backend.services import news_service, stock_service


def _index_change(symbol: str) -> tuple[float | None, float | None]:
    try:
        hist = stock_service.get_history(symbol, "5d")
        if hist is None or hist.empty or len(hist) < 2:
            return None, None
        close = hist["Close"]
        latest = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        if prev == 0:
            return latest, None
        return latest, (latest - prev) / prev * 100
    except Exception:
        return None, None


def _sentiment_label(spy_chg: float | None, qqq_chg: float | None, vix: float | None, vix_chg: float | None) -> tuple[str, str, str]:
    if vix is not None and vix > 25:
        return "high_volatility", "High volatility", "Elevated VIX — wider swings; size short premium carefully."
    if vix_chg is not None and vix_chg > 10:
        return "high_volatility", "High volatility", "VIX spiking — intraday reversals more likely."
    if spy_chg is not None and qqq_chg is not None and spy_chg < -1 and qqq_chg < -1:
        return "risk_off", "Risk-off", "Broad market selling — caution on bullish short premium."
    if spy_chg is not None and vix is not None and spy_chg > 0.5 and vix < 15:
        return "risk_on", "Risk-on", "Calm, positive tape — generally supportive for defined-risk premium selling."
    return "neutral", "Neutral", "Mixed macro — rely on trade-specific pre-trade checks."


@ttl_cache(TTL_MARKET_CONTEXT)
def get_market_context() -> dict:
    spy_level, spy_chg = _index_change("SPY")
    qqq_level, qqq_chg = _index_change("QQQ")
    vix_level, vix_chg = _index_change("^VIX")

    label_key, label_display, impact = _sentiment_label(spy_chg, qqq_chg, vix_level, vix_chg)

    events, finnhub_ok = news_service.get_economic_calendar(7)
    high_events = [e for e in events if e.get("impact") == "high"][:8]
    all_events = events[:12]

    earnings_headlines = news_service.get_news_by_category("earnings", 6)
    market_headlines = news_service.get_news_by_category("markets", 5)
    economy_headlines = news_service.get_news_by_category("economy", 3)

    alerts: list[dict] = []
    for ev in high_events[:3]:
        alerts.append({"level": "high", "text": f"{ev.get('event')} — {ev.get('date', '')[:10]}"})
    if vix_chg is not None and vix_chg > 5:
        alerts.append({"level": "medium", "text": f"VIX up {vix_chg:.1f}% — elevated intraday swings"})
    if spy_chg is not None and spy_chg < -1:
        alerts.append({"level": "medium", "text": f"SPY down {spy_chg:.1f}% today"})

    footer = impact
    if high_events:
        footer = f"Next macro: {high_events[0].get('event')} on {high_events[0].get('date', '')[:10]}. {impact}"

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "sentiment": {
            "label": label_key,
            "display": label_display,
            "vix": round(vix_level, 2) if vix_level else None,
            "vix_change_pct": round(vix_chg, 2) if vix_chg is not None else None,
            "spy_change_pct": round(spy_chg, 2) if spy_chg is not None else None,
            "qqq_change_pct": round(qqq_chg, 2) if qqq_chg is not None else None,
            "impact": impact,
        },
        "economic_events": all_events,
        "finnhub_configured": finnhub_ok,
        "catalysts": {
            "earnings_headlines": earnings_headlines,
            "market_headlines": market_headlines,
            "economy_headlines": economy_headlines,
        },
        "alerts": alerts,
        "footer_note": footer,
        "disclaimer": "Macro context is generic — not ticker-specific. Not financial advice.",
    }
