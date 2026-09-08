"""Unit tests for Issue #15 buy-verdict memo parsing and route shape."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_verdict_response


class TestParseVerdictResponse:
    def test_extracts_verdict_and_markdown(self):
        raw = """## Short-term outlook (1 year)

Cautious near term.

## Final verdict (Buy, Hold, or Avoid)

Hold for now.

```json
{
  "verdict": "hold",
  "confidence": "high",
  "horizon_fit": "long",
  "summary": "Better as a long-term compounder"
}
```
"""
        md, structured = parse_verdict_response(raw)
        assert "Short-term outlook" in md
        assert "```json" not in md
        assert structured is not None
        assert structured["verdict"] == "hold"
        assert structured["confidence"] == "high"
        assert structured["horizon_fit"] == "long"
        assert structured["summary"] == "Better as a long-term compounder"

    def test_maps_sell_to_avoid(self):
        raw = 'memo\n```json\n{"verdict": "sell", "confidence": "low", "horizon_fit": "neither"}\n```'
        _, structured = parse_verdict_response(raw)
        assert structured is not None
        assert structured["verdict"] == "avoid"

    def test_invalid_verdict_confidence_horizon(self):
        raw = (
            'memo\n```json\n'
            '{"verdict": "maybe", "confidence": "sure", "horizon_fit": "forever"}\n'
            "```"
        )
        _, structured = parse_verdict_response(raw)
        assert structured is not None
        assert structured["verdict"] == "hold"
        assert structured["confidence"] == "medium"
        assert structured["horizon_fit"] == "neither"

    def test_invalid_json_returns_null_structured(self):
        md, structured = parse_verdict_response("Hello\n```json\n{bad}\n```")
        assert "Hello" in md
        assert structured is None


class TestVerdictRoute:
    def test_post_upserts_and_get_returns_cache(self):
        client = TestClient(app)
        metrics = {
            "identity": {"symbol": "BUY1"},
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
                "backend.routers.ai.gemini_service.generate_verdict_memo",
                return_value=(
                    "## Short-term outlook (1 year)\n\nMixed.\n\n## Final verdict\n\nAvoid.",
                    {
                        "verdict": "avoid",
                        "confidence": "medium",
                        "horizon_fit": "neither",
                        "summary": "Risk/reward unattractive today",
                    },
                    None,
                ),
            ),
        ):
            r = client.post("/api/ai/verdict", json={"symbol": "BUY1", "period": "1y", "force": True})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "live"
        assert body["structured"]["verdict"] == "avoid"
        assert "disclaimer" in body

        g = client.get("/api/ai/verdict/BUY1")
        assert g.status_code == 200
        cached = g.json()
        assert cached["cached"] is True
        assert "Short-term outlook" in cached["markdown"]
        assert cached["structured"]["horizon_fit"] == "neither"

    def test_get_miss_returns_cached_false(self):
        client = TestClient(app)
        g = client.get("/api/ai/verdict/NOVERDICTCACHEDXYZ")
        assert g.status_code == 200
        assert g.json() == {"cached": False, "symbol": "NOVERDICTCACHEDXYZ", "source": None}
