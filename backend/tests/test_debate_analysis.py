"""Unit tests for Issue #13 debate analysis."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_debate_response


class TestParseDebate:
    def test_clamps_scores(self):
        raw = 'd\n```json\n{"bull_score": 99, "bear_score": -2, "winner": "bull", "confidence": "high", "conclusion_one_liner": "Bullish lean"}\n```'
        _, s = parse_debate_response(raw)
        assert s["bull_score"] == 10
        assert s["bear_score"] == 1
        assert s["winner"] == "bull"

    def test_invalid_winner(self):
        raw = 'd\n```json\n{"bull_score": 5, "bear_score": 5, "winner": "tie", "confidence": "x"}\n```'
        _, s = parse_debate_response(raw)
        assert s["winner"] == "draw"
        assert s["confidence"] == "medium"


class TestDebateRoute:
    def test_post_get(self):
        client = TestClient(app)
        structured = {"bull_score": 7, "bear_score": 6, "winner": "bull", "confidence": "medium", "conclusion_one_liner": "Lean bull"}
        with (
            patch("backend.routers.ai.research_metrics_service.build_research_metrics", return_value={"identity": {"symbol": "DEB1"}}),
            patch("backend.routers.ai.gemini_service.generate_debate_memo", return_value=("## Debate", structured, None)),
        ):
            assert client.post("/api/ai/debate", json={"symbol": "DEB1"}).status_code == 200
        assert client.get("/api/ai/debate/DEB1").json()["cached"] is True

    def test_miss(self):
        assert TestClient(app).get("/api/ai/debate/NODEBATEXYZ").json()["cached"] is False
