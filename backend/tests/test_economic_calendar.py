"""Gemini-backed economic calendar: output validation, failure handling, and caching.

Assumption: Gemini output is untrusted, so anything malformed or dated outside the
requested window is dropped rather than shown to users.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import economic_calendar_service as svc

START, END = date(2026, 9, 24), date(2026, 10, 1)

VALID_RESPONSE = """Here you go:
```json
[
  {"date": "2026-09-30", "time": "10:00 ET", "event": "Consumer Confidence", "impact": "medium",
   "estimate": "103.0", "previous": "104.2"},
  {"date": "2026-09-25", "time": "08:30 ET", "event": "GDP (Q2 Final)", "impact": "bogus",
   "estimate": null, "previous": "3.0%"}
]
```"""


@pytest.fixture(autouse=True)
def _gemini_configured():
    with patch.object(svc, "GEMINI_API_KEY", "test-key"):
        yield


def test_parse_sorts_and_normalizes_events():
    events = svc.parse_calendar_response(VALID_RESPONSE, START, END)
    assert [e["event"] for e in events] == ["GDP (Q2 Final)", "Consumer Confidence"]
    assert events[0]["impact"] == "high"  # invalid impact falls back to keyword label
    assert events[1]["impact"] == "medium"
    assert events[1]["estimate"] == "103.0"
    assert all(e["country"] == "US" and e["id"] for e in events)


def test_parse_drops_out_of_range_malformed_and_duplicate_rows():
    raw = """```json
[
  {"date": "2026-08-01", "event": "Stale CPI"},
  {"date": "not-a-date", "event": "Broken"},
  {"date": "2026-09-26", "event": ""},
  "junk",
  {"date": "2026-09-26", "event": "PCE"},
  {"date": "2026-09-26", "event": "PCE"}
]
```"""
    events = svc.parse_calendar_response(raw, START, END)
    assert [e["event"] for e in events] == ["PCE"]


def test_parse_empty_array_is_valid():
    assert svc.parse_calendar_response("```json\n[]\n```", START, END) == []


@pytest.mark.parametrize("raw", ["no json here", '```json\n{"not": "a list"}\n```'])
def test_parse_rejects_unusable_output(raw):
    with pytest.raises(svc.CalendarUnavailableError):
        svc.parse_calendar_response(raw, START, END)


def test_not_configured_without_gemini_key():
    with patch.object(svc, "GEMINI_API_KEY", ""):
        assert svc.get_economic_calendar(7) == {"events": [], "configured": False, "error": None}


def test_gemini_failure_returns_generic_error_and_is_not_cached():
    with patch.object(svc.gemini_service, "call_gemini", return_value=(None, "quota exceeded: secret")) as call:
        first = svc.get_economic_calendar(3)
        second = svc.get_economic_calendar(3)
    assert first["configured"] is True and first["events"] == []
    assert "secret" not in first["error"]
    assert second == first
    assert call.call_count == 2


def test_success_uses_google_search_and_is_cached():
    raw = '```json\n[{"date": "%s", "event": "Initial Jobless Claims"}]\n```' % date.today().isoformat()
    with patch.object(svc.gemini_service, "call_gemini", return_value=(raw, None)) as call:
        first = svc.get_economic_calendar(5)
        second = svc.get_economic_calendar(5)
    assert first["error"] is None and first["events"][0]["impact"] == "medium"
    assert second == first
    assert call.call_count == 1
    assert call.call_args.kwargs["google_search"] is True


def test_calendar_endpoint_shape():
    payload = {"events": [], "configured": True, "error": None}
    with patch.object(svc, "get_economic_calendar", return_value=payload):
        res = TestClient(app).get("/api/news/calendar?days=7")
    assert res.status_code == 200
    assert res.json() == {"days": 7, "calendar_configured": True, "calendar_error": None, "events": []}
