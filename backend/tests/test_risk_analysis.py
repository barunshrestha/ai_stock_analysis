"""Unit tests for Issue #10 risk memo parsing and routes."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_risk_response


class TestParseRiskResponse:
    def test_extracts_ranked_risks(self):
        raw = """## Economic

Soft landing risk.

```json
{
  "overall_risk": "medium",
  "confidence": "high",
  "ranked_risks": [
    {"rank": 2, "category": "competition", "title": "Share loss", "severity": "high"},
    {"rank": 1, "category": "financial", "title": "Leverage", "severity": "medium"}
  ],
  "summary": "Manageable risks"
}
```
"""
        md, structured = parse_risk_response(raw)
        assert "Economic" in md
        assert structured is not None
        assert structured["overall_risk"] == "medium"
        assert structured["ranked_risks"][0]["category"] == "financial"
        assert structured["ranked_risks"][0]["rank"] == 1
        assert len(structured["ranked_risks"]) == 5

    def test_invalid_enums_default(self):
        raw = 'x\n```json\n{"overall_risk": "extreme", "confidence": "maybe", "ranked_risks": []}\n```'
        _, s = parse_risk_response(raw)
        assert s["overall_risk"] == "medium"
        assert s["confidence"] == "medium"
        assert len(s["ranked_risks"]) == 5


class TestRiskRoute:
    def test_post_and_get_cache(self):
        client = TestClient(app)
        metrics = {"identity": {"symbol": "RISK1"}, "market": {"price": 10}}
        with (
            patch("backend.routers.ai.research_metrics_service.build_research_metrics", return_value=metrics),
            patch(
                "backend.routers.ai.gemini_service.generate_risk_memo",
                return_value=("## Risk\n\nOk.", {"overall_risk": "low", "confidence": "medium", "ranked_risks": [
                    {"rank": 1, "category": "economic", "title": "E", "severity": "low"},
                    {"rank": 2, "category": "disruption", "title": "D", "severity": "low"},
                    {"rank": 3, "category": "competition", "title": "C", "severity": "low"},
                    {"rank": 4, "category": "regulatory", "title": "R", "severity": "low"},
                    {"rank": 5, "category": "financial", "title": "F", "severity": "low"},
                ], "summary": "Low"}, None),
            ),
        ):
            r = client.post("/api/ai/risk", json={"symbol": "RISK1", "period": "1y", "force": True})
        assert r.status_code == 200, r.text
        assert r.json()["source"] == "live"
        g = client.get("/api/ai/risk/RISK1")
        assert g.json()["cached"] is True

    def test_get_miss(self):
        client = TestClient(app)
        g = client.get("/api/ai/risk/NORISKCACHEDXYZ")
        assert g.json() == {"cached": False, "symbol": "NORISKCACHEDXYZ", "source": None}
