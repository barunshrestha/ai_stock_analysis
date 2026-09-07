"""Parse broker screenshot text (OCR) into a draft options trade."""

from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Any

from backend.schemas.options import Broker, LegInput, OptionType, TradeSide


def _extract_ticker(text: str) -> str | None:
    m = re.search(r"\b([A-Z]{1,5})\b(?=\s+\$?\d+\.?\d*\s+(?:Put|Call|put|call))", text)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Z]{1,5})\b\s+\d{1,2}/\d{1,2}", text)
    return m.group(1) if m else None


def _extract_strikes(text: str) -> list[float]:
    strikes = []
    for m in re.finditer(r"\$(\d+(?:\.\d{1,2})?)\s*(?:Put|Call|put|call)", text):
        strikes.append(float(m.group(1)))
    if not strikes:
        for m in re.finditer(r"(?:Strike|strike)[:\s]*\$?(\d+(?:\.\d{1,2})?)", text):
            strikes.append(float(m.group(1)))
    return strikes


def _extract_premium(text: str) -> float | None:
    patterns = [
        r"(?:Credit|credit|Premium|premium|Price|price)[:\s]*\$?(\d+\.\d{2})",
        r"\$(\d+\.\d{2})\s*(?:credit|Credit|per contract)",
        r"(?:Filled|filled)[^\$]*\$?(\d+\.\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return float(m.group(1))
    amounts = re.findall(r"\$(\d+\.\d{2})", text)
    return float(amounts[0]) if amounts else None


def _extract_contracts(text: str) -> int | None:
    m = re.search(r"(?:Qty|Quantity|Contracts|contracts)[:\s]*(\d+)", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d+)\s+contract", text, re.I)
    return int(m.group(1)) if m else None


def _extract_dates(text: str) -> tuple[date | None, date | None]:
    exp = None
    executed = None
    exp_m = re.search(r"(?:Exp(?:iration)?|Expires)[:\s]*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
    if exp_m:
        exp = _parse_date(exp_m.group(1))
    if not exp:
        dates = re.findall(r"(\d{1,2}/\d{1,2}/\d{2,4})", text)
        if dates:
            exp = _parse_date(dates[0])
    exec_m = re.search(
        r"(?:Filled|Executed|Order filled)[^\n]*(\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.I,
    )
    if exec_m:
        executed = _parse_date(exec_m.group(1))
    return exp, executed


def _parse_date(raw: str) -> date | None:
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _detect_option_type(text: str) -> str:
    lower = text.lower()
    if " put" in lower or lower.endswith("put"):
        return "put"
    if " call" in lower or lower.endswith("call"):
        return "call"
    return "put"


def _detect_side(text: str) -> str:
    lower = text.lower()
    if "sell to open" in lower or "sold" in lower and "open" in lower:
        return "sell_to_open"
    if "buy to close" in lower:
        return "buy_to_close"
    if "buy to open" in lower:
        return "buy_to_open"
    if "sell to close" in lower:
        return "sell_to_close"
    if "credit" in lower:
        return "sell_to_open"
    return "sell_to_open"


def _detect_broker(text: str) -> Broker:
    lower = text.lower()
    if "robinhood" in lower:
        return Broker.robinhood
    if "thinkorswim" in lower or "td ameritrade" in lower:
        return Broker.thinkorswim
    if "webull" in lower:
        return Broker.webull
    return Broker.unknown


def _detect_strategy(text: str, legs_count: int, option_type: str, side: str) -> tuple[str, float, list[dict]]:
    lower = text.lower()
    suggestions: list[dict] = []

    if legs_count >= 4 or "iron condor" in lower:
        strat = "iron_condor"
        conf = 0.75
        suggestions.append(
            {
                "strategy": strat,
                "reason": "Multiple strikes or iron condor language detected.",
                "impact": "Verify both put and call spread widths; max loss = wider wing minus credit.",
                "recommended_checks": ["max_loss", "annualized_roc", "otm_distance"],
            }
        )
    elif legs_count == 2:
        strat = "put_credit_spread" if option_type == "put" else "call_credit_spread"
        conf = 0.7
        suggestions.append(
            {
                "strategy": strat,
                "reason": "Two strikes detected — likely a vertical spread.",
                "impact": "Confirm net credit and spread width define max loss.",
                "recommended_checks": ["max_loss", "annualized_roc"],
            }
        )
    elif option_type == "put" and side == "sell_to_open":
        if "cash secured" in lower or "csp" in lower:
            strat = "cash_secured_put"
        else:
            strat = "cash_secured_put"
        conf = 0.85
        suggestions.append(
            {
                "strategy": "cash_secured_put",
                "reason": "Single short put / sell-to-open detected.",
                "impact": "Collateral ≈ strike × 100 × contracts; watch OTM distance and earnings.",
                "recommended_checks": ["annualized_roc", "otm_distance", "earnings_before_expiry"],
            }
        )
    elif option_type == "call" and side == "sell_to_open":
        strat = "covered_call"
        conf = 0.8
        suggestions.append(
            {
                "strategy": strat,
                "reason": "Single short call / sell-to-open detected.",
                "impact": "Caps upside at strike; watch ex-dividend dates.",
                "recommended_checks": ["otm_distance", "earnings_before_expiry"],
            }
        )
    elif side == "buy_to_open":
        strat = "long_call" if option_type == "call" else "long_put"
        conf = 0.75
        suggestions.append(
            {
                "strategy": strat,
                "reason": "Buy-to-open detected — debit strategy.",
                "impact": "Max loss is premium paid; define profit target and time stop.",
                "recommended_checks": ["dte", "max_loss"],
            }
        )
    else:
        strat = "custom"
        conf = 0.5
        suggestions.append(
            {
                "strategy": "custom",
                "reason": "Could not confidently classify — review legs manually.",
                "impact": "Enter collateral override if needed.",
                "recommended_checks": ["dte"],
            }
        )

    return strat, conf, suggestions


def parse_text_to_draft(text: str, broker: Broker | None = None) -> dict[str, Any]:
    text = text.strip()
    ticker = _extract_ticker(text)
    strikes = _extract_strikes(text)
    premium = _extract_premium(text)
    contracts = _extract_contracts(text) or 1
    exp_date, exec_date = _extract_dates(text)
    option_type = _detect_option_type(text)
    side = _detect_side(text)
    detected_broker = broker or _detect_broker(text)

    uncertain: list[str] = []
    if not ticker:
        uncertain.append("ticker")
    if not strikes:
        uncertain.append("strike")
    if premium is None:
        uncertain.append("premium_per_contract")
    if not exp_date:
        uncertain.append("expiration_date")

    legs: list[dict] = []
    for i, strike in enumerate(strikes[:4], start=1):
        legs.append(
            {
                "leg_index": i,
                "option_type": option_type if i == 1 else ("put" if option_type == "put" else "call"),
                "side": side,
                "strike": strike,
                "premium_per_contract": premium or 0,
                "expiration_date": exp_date.isoformat() if exp_date else None,
            }
        )
    if not legs and strikes:
        pass
    elif not legs and premium:
        legs.append(
            {
                "leg_index": 1,
                "option_type": option_type,
                "side": side,
                "strike": 0,
                "premium_per_contract": premium,
                "expiration_date": exp_date.isoformat() if exp_date else None,
            }
        )

    strategy, strat_conf, suggestions = _detect_strategy(text, len(strikes), option_type, side)

    confidence = 0.9 - 0.1 * len(uncertain)
    if not strikes or not ticker:
        confidence = min(confidence, 0.6)

    executed_at = datetime.combine(exec_date or date.today(), datetime.min.time()).isoformat()

    return {
        "draft": {
            "strategy_type": strategy,
            "ticker": ticker or "",
            "legs": legs,
            "contracts": contracts,
            "executed_at": executed_at,
            "expiration_date": exp_date.isoformat() if exp_date else None,
            "net_credit_debit": premium if side == "sell_to_open" else -(premium or 0),
            "broker": detected_broker.value,
            "notes": None,
        },
        "detected_strategy": strategy,
        "strategy_confidence": round(strat_conf, 2),
        "parse_confidence": round(max(confidence, 0), 2),
        "uncertain_fields": uncertain,
        "trade_type_suggestions": suggestions,
        "raw_text_preview": text[:500],
    }


def ocr_image_to_text(image_bytes: bytes) -> tuple[str | None, str | None]:
    """Run OCR on image bytes. Returns (text, error)."""
    try:
        from PIL import Image
    except ImportError:
        return None, "Pillow not installed. Use manual entry or paste text via parse-text."

    try:
        import pytesseract
    except ImportError:
        return None, "pytesseract not installed. pip install pytesseract and install Tesseract OCR, or use parse-text."

    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img)
        if not text.strip():
            return None, "OCR returned no text — try a clearer screenshot or manual entry."
        return text, None
    except Exception as exc:
        return None, f"OCR failed: {exc}"


def parse_image(image_bytes: bytes, broker: Broker | None = None) -> tuple[dict | None, str | None]:
    text, err = ocr_image_to_text(image_bytes)
    if err:
        return None, err
    return parse_text_to_draft(text, broker), None
