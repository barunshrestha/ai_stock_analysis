"""NaN/Infinity from market data must serialize as null instead of crashing the response."""

from __future__ import annotations

import math
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.json_response import to_json_safe
from backend.main import app


def test_to_json_safe_replaces_nan_and_inf_recursively():
    payload = {"a": math.nan, "b": [1.5, math.inf, {"c": -math.inf}], "d": "x", "e": 3}
    assert to_json_safe(payload) == {"a": None, "b": [1.5, None, {"c": None}], "d": "x", "e": 3}


def test_ai_route_with_nan_metrics_returns_200():
    structured = {"bull_score": 6, "bear_score": 5, "winner": "bull", "confidence": "medium"}
    metrics = {"identity": {"symbol": "NANX"}, "market": {"change_6m_pct": math.nan}}
    with (
        patch("backend.routers.ai.research_metrics_service.build_research_metrics", return_value=metrics),
        patch("backend.routers.ai.gemini_service.generate_debate_memo", return_value=("## d", structured, None)),
    ):
        res = TestClient(app).post("/api/ai/debate", json={"symbol": "NANX"})
    assert res.status_code == 200
    assert res.json()["metrics"]["market"]["change_6m_pct"] is None
