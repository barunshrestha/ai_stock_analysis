"""US economic release calendar sourced from Gemini with Google Search grounding."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, timedelta
from typing import Any

from backend.cache import ttl_cache
from backend.config import GEMINI_API_KEY, TTL_NEWS_CALENDAR
from backend.services import gemini_service

logger = logging.getLogger(__name__)

_MAX_EVENTS = 50
_MAX_EVENT_NAME = 120
_IMPACTS = ("high", "medium", "low")

SYSTEM_PROMPT = """You are a financial data assistant that compiles the US economic release calendar.

Hard rules:
- Use Google Search to find the officially scheduled US releases (BLS, BEA, Census, Federal Reserve,
  Department of Labor, ISM, Conference Board, University of Michigan, etc.) in the requested date range.
- Only include releases you found a scheduled date for. Never guess dates.
- If you cannot find any, return an empty array.

Respond with a single fenced JSON block and nothing else:
```json
[
  {
    "date": "YYYY-MM-DD",
    "time": "08:30 ET" | null,
    "event": "Consumer Price Index (CPI)",
    "impact": "high" | "medium" | "low",
    "estimate": "consensus as text" | null,
    "previous": "prior reading as text" | null
  }
]
```
"""

_JSON_ARRAY_RE = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.DOTALL | re.IGNORECASE)


class CalendarUnavailableError(Exception):
    """Gemini could not produce a usable calendar; raised so failures are not cached."""


def _impact_label(event: str) -> str:
    upper = event.upper()
    if any(k in upper for k in ("CPI", "FOMC", "NFP", "NONFARM", "GDP", "PCE", "FED")):
        return "high"
    if any(k in upper for k in ("PPI", "JOBLESS", "RETAIL", "PMI", "HOUSING")):
        return "medium"
    return "low"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:40] or None


def _extract_json_array(raw: str) -> list[Any]:
    match = _JSON_ARRAY_RE.search(raw or "")
    candidate = match.group(1) if match else (raw or "").strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise CalendarUnavailableError("Gemini returned an unreadable calendar.") from exc
    if not isinstance(parsed, list):
        raise CalendarUnavailableError("Gemini returned an unexpected calendar format.")
    return parsed


def parse_calendar_response(raw: str, start: date, end: date) -> list[dict]:
    """Validate model output: keep well-formed events dated inside [start, end], sorted by date."""
    events: list[dict] = []
    seen: set[str] = set()
    for row in _extract_json_array(raw):
        if not isinstance(row, dict):
            continue
        name = str(row.get("event") or "").strip()[:_MAX_EVENT_NAME]
        try:
            event_date = date.fromisoformat(str(row.get("date") or "")[:10])
        except ValueError:
            continue
        if not name or not (start <= event_date <= end):
            continue
        event_id = hashlib.sha256(f"{event_date}{name}".encode()).hexdigest()[:16]
        if event_id in seen:
            continue
        seen.add(event_id)
        impact = str(row.get("impact") or "").lower()
        events.append(
            {
                "id": event_id,
                "date": event_date.isoformat(),
                "time": _optional_text(row.get("time")),
                "event": name,
                "country": "US",
                "impact": impact if impact in _IMPACTS else _impact_label(name),
                "actual": None,
                "estimate": _optional_text(row.get("estimate")),
                "previous": _optional_text(row.get("previous")),
            }
        )
    events.sort(key=lambda e: e["date"])
    return events[:_MAX_EVENTS]


@ttl_cache(TTL_NEWS_CALENDAR)
def _fetch_calendar(start_iso: str, end_iso: str) -> list[dict]:
    start, end = date.fromisoformat(start_iso), date.fromisoformat(end_iso)
    user_prompt = (
        f"List every scheduled US economic data release from {start_iso} to {end_iso} inclusive "
        f"(today is {start_iso})."
    )
    raw, error = gemini_service.call_gemini(
        SYSTEM_PROMPT, user_prompt, temperature=0.1, max_output_tokens=4096, google_search=True
    )
    if error or raw is None:
        raise CalendarUnavailableError(error or "Gemini returned no calendar.")
    return parse_calendar_response(raw, start, end)


def get_economic_calendar(days: int = 7) -> dict:
    """Returns {"events", "configured", "error"}; successful lookups are cached per date range."""
    if not GEMINI_API_KEY:
        return {"events": [], "configured": False, "error": None}
    start = date.today()
    end = start + timedelta(days=max(1, min(days, 14)))
    try:
        events = _fetch_calendar(start.isoformat(), end.isoformat())
    except CalendarUnavailableError as exc:
        logger.warning("Economic calendar unavailable: %s", exc)
        return {"events": [], "configured": True, "error": "Economic calendar is temporarily unavailable."}
    return {"events": events, "configured": True, "error": None}
