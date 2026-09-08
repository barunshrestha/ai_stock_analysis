"""Unit tests for Issue #14 earnings analysis."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_earnings_response
from backend.services.research_metrics_service import build_earnings_context


class TestParseEarnings:
    def test_happy(self):
        raw = 'e\n```json\n{"surprise": "beat", "confidence": "high", "summary": "Beat on EPS"}\n```'
        _, s = parse_earnings_response(raw)
        assert s["surprise"] == "beat"

    def test_invalid(self):
        raw = 'e\n```json\n{"surprise": "smash", "confidence": "x"}\n```'
        _, s = parse_earnings_response(raw)
        assert s["surprise"] == "unknown"


class TestEarningsContext:
    def test_shape_with_mocks(self):
        with (
            patch("backend.services.research_metrics_service.stock_service.get_info", return_value={"epsTrailingTwelveMonths": 2.0, "forwardEps": 1.8}),
            patch("backend.services.research_metrics_service.stock_service.get_history", return_value=None),
            patch("backend.services.research_metrics_service.stock_service.get_earnings_dates", return_value=None),
        ):
            ctx = build_earnings_context("EAR1")
        assert ctx["symbol"] == "EAR1"
        assert "eps_actual" in ctx
        assert ctx["note"]


class TestEarningsRoute:
    def test_post_get(self):
        client = TestClient(app)
        with (
            patch("backend.routers.ai.research_metrics_service.build_research_metrics", return_value={"identity": {"symbol": "EAR1"}}),
            patch("backend.routers.ai.research_metrics_service.build_earnings_context", return_value={"symbol": "EAR1", "surprise_pct": None}),
            patch("backend.routers.ai.gemini_service.generate_earnings_memo", return_value=("## E", {"surprise": "unknown", "confidence": "low", "summary": None}, None)),
        ):
            body = client.post("/api/ai/earnings", json={"symbol": "EAR1"}).json()
        assert body["source"] == "live"
        assert "earnings_context" in body["metrics"]
        assert client.get("/api/ai/earnings/EAR1").json()["cached"] is True

    def test_miss(self):
        assert TestClient(app).get("/api/ai/earnings/NOEARNXYZ").json()["cached"] is False
