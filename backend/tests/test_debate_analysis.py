"""Unit tests for Issue #13 bull vs bear debate parsing and route shape."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_debate_response


class TestParseDebateResponse:
    def test_extracts_scores_and_markdown(self):
        raw = """## Bull case

Growth and margins look strong.

## Bear case

Valuation is stretched.

## Balanced conclusion

Mixed picture with a slight bull lean.

```json
{
  "bull_score": 8,
  "bear_score": 6,
  "winner": "bull",
  "confidence": "high",
  "conclusion_one_liner": "Bulls have the edge on fundamentals"
}
```
"""
        md, structured = parse_debate_response(raw)
        assert "Bull case" in md
        assert "Bear case" in md
        assert "Balanced conclusion" in md
        assert "```json" not in md
        assert structured is not None
        assert structured["bull_score"] == 8
        assert structured["bear_score"] == 6
        assert structured["winner"] == "bull"
        assert structured["confidence"] == "high"
        assert "Bulls have the edge" in (structured["conclusion_one_liner"] or "")

    def test_clamps_scores_high_and_low(self):
        high = (
            'x\n```json\n{"bull_score": 99, "bear_score": -2, '
            '"winner": "draw", "confidence": "low"}\n```'
        )
        _, s = parse_debate_response(high)
        assert s is not None
        assert s["bull_score"] == 10
        assert s["bear_score"] == 1

    def test_invalid_winner_derived_from_scores(self):
        raw = (
            'memo\n```json\n{"bull_score": 4, "bear_score": 9, '
            '"winner": "maybe", "confidence": "weird"}\n```'
        )
        _, structured = parse_debate_response(raw)
        assert structured is not None
        assert structured["winner"] == "bear"
        assert structured["confidence"] == "medium"

    def test_draw_when_scores_equal_and_winner_invalid(self):
        raw = 'memo\n```json\n{"bull_score": 5, "bear_score": 5, "winner": "???"}\n```'
        _, structured = parse_debate_response(raw)
        assert structured is not None
        assert structured["winner"] == "draw"

    def test_invalid_json_returns_null_structured(self):
        md, structured = parse_debate_response("Hello\n```json\n{bad}\n```")
        assert "Hello" in md
        assert structured is None


class TestDebateRoute:
    def test_post_upserts_and_get_returns_cache(self):
        client = TestClient(app)
        metrics = {
            "identity": {"symbol": "DEB1"},
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
                "backend.routers.ai.gemini_service.generate_debate_memo",
                return_value=(
                    "## Bull case\n\nUp.\n\n## Bear case\n\nDown.\n\n## Balanced conclusion\n\nTie.",
                    {
                        "bull_score": 7,
                        "bear_score": 7,
                        "winner": "draw",
                        "confidence": "medium",
                        "conclusion_one_liner": "Evenly matched",
                    },
                    None,
                ),
            ),
        ):
            r = client.post("/api/ai/debate", json={"symbol": "DEB1", "period": "1y", "force": True})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "live"
        assert body["structured"]["winner"] == "draw"
        assert body["structured"]["bull_score"] == 7

        g = client.get("/api/ai/debate/DEB1")
        assert g.status_code == 200
        cached = g.json()
        assert cached["cached"] is True
        assert "Bull case" in cached["markdown"]
        assert cached["structured"]["conclusion_one_liner"] == "Evenly matched"

    def test_get_miss_returns_cached_false(self):
        client = TestClient(app)
        g = client.get("/api/ai/debate/NODEBATECACHEDXYZ")
        assert g.status_code == 200
        assert g.json() == {"cached": False, "symbol": "NODEBATECACHEDXYZ", "source": None}
