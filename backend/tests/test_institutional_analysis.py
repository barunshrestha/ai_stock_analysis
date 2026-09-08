"""Unit tests for Issue #12 institutional analysis."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_institutional_response


class TestParseInstitutional:
    def test_caps_lists(self):
        raw = 'm\n```json\n{"stance": "attractive", "confidence": "high", "buy_reasons": ["a","b","c","d","e","f"], "avoid_reasons": ["x"], "catalysts": [], "thesis_one_liner": "Buy quality"}\n```'
        _, s = parse_institutional_response(raw)
        assert s["stance"] == "attractive"
        assert len(s["buy_reasons"]) == 5
        assert s["thesis_one_liner"] == "Buy quality"

    def test_invalid_stance(self):
        raw = 'm\n```json\n{"stance": "meh", "confidence": "x"}\n```'
        _, s = parse_institutional_response(raw)
        assert s["stance"] == "mixed"


class TestInstitutionalRoute:
    def test_post_get(self):
        client = TestClient(app)
        structured = {"stance": "mixed", "confidence": "medium", "buy_reasons": [], "avoid_reasons": [], "catalysts": [], "thesis_one_liner": None}
        with (
            patch("backend.routers.ai.research_metrics_service.build_research_metrics", return_value={"identity": {"symbol": "INS1"}, "ownership": {}}),
            patch("backend.routers.ai.gemini_service.generate_institutional_memo", return_value=("## I", structured, None)),
        ):
            assert client.post("/api/ai/institutional", json={"symbol": "INS1"}).status_code == 200
        assert client.get("/api/ai/institutional/INS1").json()["cached"] is True

    def test_miss(self):
        assert TestClient(app).get("/api/ai/institutional/NOINSTXYZ").json()["cached"] is False
