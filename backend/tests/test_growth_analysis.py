"""Unit tests for Issue #11 growth analysis."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_growth_response


class TestParseGrowthResponse:
    def test_happy(self):
        raw = '## Growth\n\n```json\n{"outlook_band": "high", "confidence": "medium", "primary_driver": "AI", "five_year_summary": "Strong", "ten_year_summary": "Solid"}\n```'
        md, s = parse_growth_response(raw)
        assert "Growth" in md
        assert s["outlook_band"] == "high"
        assert s["primary_driver"] == "AI"

    def test_invalid_band(self):
        raw = 'x\n```json\n{"outlook_band": "insane", "confidence": "nope"}\n```'
        _, s = parse_growth_response(raw)
        assert s["outlook_band"] == "moderate"
        assert s["confidence"] == "medium"


class TestGrowthRoute:
    def test_post_get(self):
        client = TestClient(app)
        with (
            patch("backend.routers.ai.research_metrics_service.build_research_metrics", return_value={"identity": {"symbol": "GRW1"}}),
            patch("backend.routers.ai.gemini_service.generate_growth_memo", return_value=("## G", {"outlook_band": "moderate", "confidence": "low", "primary_driver": None, "five_year_summary": None, "ten_year_summary": None}, None)),
        ):
            assert client.post("/api/ai/growth", json={"symbol": "GRW1"}).status_code == 200
        assert client.get("/api/ai/growth/GRW1").json()["cached"] is True

    def test_miss(self):
        assert TestClient(app).get("/api/ai/growth/NOGROWTHXYZ").json()["cached"] is False
