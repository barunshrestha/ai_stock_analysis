"""Unit tests for Issue #15 buy verdict analysis."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_verdict_response


class TestParseVerdict:
    def test_maps_sell_to_avoid(self):
        raw = 'v\n```json\n{"verdict": "sell", "confidence": "high", "horizon_fit": "short", "summary": "Exit"}\n```'
        _, s = parse_verdict_response(raw)
        assert s["verdict"] == "avoid"

    def test_invalid_defaults_hold(self):
        raw = 'v\n```json\n{"verdict": "maybe", "confidence": "x", "horizon_fit": "forever"}\n```'
        _, s = parse_verdict_response(raw)
        assert s["verdict"] == "hold"
        assert s["horizon_fit"] == "both"


class TestVerdictRoute:
    def test_post_get(self):
        client = TestClient(app)
        structured = {"verdict": "hold", "confidence": "medium", "horizon_fit": "both", "summary": "Wait"}
        with (
            patch("backend.routers.ai.research_metrics_service.build_research_metrics", return_value={"identity": {"symbol": "VER1"}}),
            patch("backend.routers.ai.gemini_service.generate_verdict_memo", return_value=("## V", structured, None)),
        ):
            assert client.post("/api/ai/verdict", json={"symbol": "VER1"}).status_code == 200
        assert client.get("/api/ai/verdict/VER1").json()["cached"] is True

    def test_miss(self):
        assert TestClient(app).get("/api/ai/verdict/NOVERDICTXYZ").json()["cached"] is False
