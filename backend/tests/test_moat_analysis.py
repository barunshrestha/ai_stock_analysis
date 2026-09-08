"""Unit tests for Issue #8 moat memo parsing and route shape."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_moat_response


class TestParseMoatResponse:
    def test_extracts_score_and_markdown(self):
        raw = """## Brand strength

Strong consumer franchise.

```json
{
  "moat_score": 8,
  "confidence": "high",
  "strongest_pillar": "brand",
  "summary": "Wide brand moat"
}
```
"""
        md, structured = parse_moat_response(raw)
        assert "Brand strength" in md
        assert "```json" not in md
        assert structured is not None
        assert structured["moat_score"] == 8
        assert structured["confidence"] == "high"
        assert structured["strongest_pillar"] == "brand"

    def test_clamps_score_high_and_low(self):
        high = 'x\n```json\n{"moat_score": 99, "confidence": "low", "strongest_pillar": "cost"}\n```'
        _, s_high = parse_moat_response(high)
        assert s_high is not None
        assert s_high["moat_score"] == 10

        low = 'x\n```json\n{"moat_score": -3, "confidence": "low", "strongest_pillar": "ip"}\n```'
        _, s_low = parse_moat_response(low)
        assert s_low is not None
        assert s_low["moat_score"] == 1

    def test_invalid_pillar_and_confidence(self):
        raw = 'memo\n```json\n{"moat_score": 5, "confidence": "maybe", "strongest_pillar": "magic"}\n```'
        _, structured = parse_moat_response(raw)
        assert structured is not None
        assert structured["confidence"] == "medium"
        assert structured["strongest_pillar"] == "none"

    def test_invalid_json_returns_null_structured(self):
        md, structured = parse_moat_response("Hello\n```json\n{bad}\n```")
        assert "Hello" in md
        assert structured is None


class TestMoatRoute:
    def test_post_upserts_and_get_returns_cache(self):
        client = TestClient(app)
        metrics = {
            "identity": {"symbol": "MOAT1"},
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
                "backend.routers.ai.gemini_service.generate_moat_memo",
                return_value=(
                    "## Moat\n\nWide.",
                    {
                        "moat_score": 7,
                        "confidence": "medium",
                        "strongest_pillar": "switching",
                        "summary": "Solid switching costs",
                    },
                    None,
                ),
            ),
        ):
            r = client.post("/api/ai/moat", json={"symbol": "MOAT1", "period": "1y", "force": True})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "live"
        assert body["structured"]["moat_score"] == 7

        g = client.get("/api/ai/moat/MOAT1")
        assert g.status_code == 200
        cached = g.json()
        assert cached["cached"] is True
        assert cached["markdown"].startswith("## Moat")
        assert cached["structured"]["strongest_pillar"] == "switching"

    def test_get_miss_returns_cached_false(self):
        client = TestClient(app)
        g = client.get("/api/ai/moat/NOMOATCACHEDXYZ")
        assert g.status_code == 200
        assert g.json() == {"cached": False, "symbol": "NOMOATCACHEDXYZ", "source": None}
