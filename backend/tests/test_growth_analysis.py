"""Unit tests for Issue #11 growth memo parsing and route shape."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_growth_response


class TestParseGrowthResponse:
    def test_extracts_outlook_and_markdown(self):
        raw = """## Market size

Large addressable opportunity when data is present.

```json
{
  "outlook_band": "high",
  "confidence": "medium",
  "primary_driver": "cloud expansion",
  "five_year_summary": "Steady double-digit growth likely",
  "ten_year_summary": "Platform scale could compound further"
}
```
"""
        md, structured = parse_growth_response(raw)
        assert "Market size" in md
        assert "```json" not in md
        assert structured is not None
        assert structured["outlook_band"] == "high"
        assert structured["confidence"] == "medium"
        assert structured["primary_driver"] == "cloud expansion"
        assert structured["five_year_summary"] == "Steady double-digit growth likely"
        assert structured["ten_year_summary"] == "Platform scale could compound further"

    def test_invalid_outlook_and_confidence(self):
        raw = (
            'memo\n```json\n{"outlook_band": "huge", "confidence": "maybe", '
            '"primary_driver": "AI", "five_year_summary": "Up", "ten_year_summary": "Up more"}\n```'
        )
        _, structured = parse_growth_response(raw)
        assert structured is not None
        assert structured["outlook_band"] == "moderate"
        assert structured["confidence"] == "medium"
        assert structured["primary_driver"] == "AI"

    def test_empty_driver_and_summaries_become_none(self):
        raw = 'x\n```json\n{"outlook_band": "low", "confidence": "high", "primary_driver": "  ", "five_year_summary": "", "ten_year_summary": null}\n```'
        _, structured = parse_growth_response(raw)
        assert structured is not None
        assert structured["outlook_band"] == "low"
        assert structured["primary_driver"] is None
        assert structured["five_year_summary"] is None
        assert structured["ten_year_summary"] is None

    def test_invalid_json_returns_null_structured(self):
        md, structured = parse_growth_response("Hello\n```json\n{bad}\n```")
        assert "Hello" in md
        assert structured is None


class TestGrowthRoute:
    def test_post_upserts_and_get_returns_cache(self):
        client = TestClient(app)
        metrics = {
            "identity": {"symbol": "GROW1"},
            "market": {"price": 10},
            "peers": ["AAA"],
            "peer_comps": [],
            "peer_note": None,
        }
        with (
            patch(
                "backend.routers.ai.research_metrics_service.build_research_metrics",
                return_value=metrics,
            ),
            patch(
                "backend.routers.ai.gemini_service.generate_growth_memo",
                return_value=(
                    "## Growth\n\nSolid runway.",
                    {
                        "outlook_band": "moderate",
                        "confidence": "high",
                        "primary_driver": "new markets",
                        "five_year_summary": "Expansion-led growth",
                        "ten_year_summary": "Mature but still compounding",
                    },
                    None,
                ),
            ),
        ):
            r = client.post("/api/ai/growth", json={"symbol": "GROW1", "period": "1y", "force": True})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "live"
        assert body["structured"]["outlook_band"] == "moderate"
        assert body["structured"]["primary_driver"] == "new markets"

        g = client.get("/api/ai/growth/GROW1")
        assert g.status_code == 200
        cached = g.json()
        assert cached["cached"] is True
        assert cached["markdown"].startswith("## Growth")
        assert cached["structured"]["five_year_summary"] == "Expansion-led growth"

    def test_get_miss_returns_cached_false(self):
        client = TestClient(app)
        g = client.get("/api/ai/growth/NOGROWTHCACHEDXYZ")
        assert g.status_code == 200
        assert g.json() == {"cached": False, "symbol": "NOGROWTHCACHEDXYZ", "source": None}
