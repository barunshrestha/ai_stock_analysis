"""Unit tests for Issue #12 institutional memo parsing and route shape."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_institutional_response


class TestParseInstitutionalResponse:
    def test_extracts_stance_and_markdown(self):
        raw = """## Why institutions might buy it

Scale and cash generation.

```json
{
  "stance": "attractive",
  "confidence": "high",
  "buy_reasons": ["Durable cash flows", "Wide distribution"],
  "avoid_reasons": ["Valuation stretch"],
  "catalysts": ["New product cycle"],
  "thesis_one_liner": "Quality compounder at a fair price"
}
```
"""
        md, structured = parse_institutional_response(raw)
        assert "Why institutions might buy" in md
        assert "```json" not in md
        assert structured is not None
        assert structured["stance"] == "attractive"
        assert structured["confidence"] == "high"
        assert structured["buy_reasons"] == ["Durable cash flows", "Wide distribution"]
        assert structured["thesis_one_liner"] == "Quality compounder at a fair price"

    def test_caps_lists_to_five(self):
        raw = (
            'memo\n```json\n{"stance": "mixed", "confidence": "low", '
            '"buy_reasons": ["a","b","c","d","e","f","g"], '
            '"avoid_reasons": ["1","2","3","4","5","6"], '
            '"catalysts": ["x","y","z","w","v","u"], '
            '"thesis_one_liner": "Mixed"}\n```'
        )
        _, structured = parse_institutional_response(raw)
        assert structured is not None
        assert structured["buy_reasons"] == ["a", "b", "c", "d", "e"]
        assert structured["avoid_reasons"] == ["1", "2", "3", "4", "5"]
        assert structured["catalysts"] == ["x", "y", "z", "w", "v"]

    def test_invalid_stance_and_confidence(self):
        raw = 'memo\n```json\n{"stance": "buy", "confidence": "maybe", "buy_reasons": []}\n```'
        _, structured = parse_institutional_response(raw)
        assert structured is not None
        assert structured["stance"] == "mixed"
        assert structured["confidence"] == "medium"
        assert structured["buy_reasons"] == []
        assert structured["avoid_reasons"] == []
        assert structured["catalysts"] == []

    def test_invalid_json_returns_null_structured(self):
        md, structured = parse_institutional_response("Hello\n```json\n{bad}\n```")
        assert "Hello" in md
        assert structured is None


class TestInstitutionalRoute:
    def test_post_upserts_and_get_returns_cache(self):
        client = TestClient(app)
        metrics = {
            "identity": {"symbol": "INST1"},
            "market": {"price": 10},
            "peers": ["AAA"],
            "peer_comps": [],
            "peer_note": None,
            "ownership": {
                "held_percent_institutions": 0.72,
                "held_percent_insiders": 0.05,
            },
        }
        with (
            patch(
                "backend.routers.ai.research_metrics_service.build_research_metrics",
                return_value=metrics,
            ),
            patch(
                "backend.routers.ai.gemini_service.generate_institutional_memo",
                return_value=(
                    "## Thesis\n\nAttractive.",
                    {
                        "stance": "attractive",
                        "confidence": "medium",
                        "buy_reasons": ["Scale"],
                        "avoid_reasons": ["Competition"],
                        "catalysts": ["Earnings beat"],
                        "thesis_one_liner": "Institutional-quality compounder",
                    },
                    None,
                ),
            ),
        ):
            r = client.post(
                "/api/ai/institutional",
                json={"symbol": "INST1", "period": "1y", "force": True},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "live"
        assert body["structured"]["stance"] == "attractive"

        g = client.get("/api/ai/institutional/INST1")
        assert g.status_code == 200
        cached = g.json()
        assert cached["cached"] is True
        assert cached["markdown"].startswith("## Thesis")
        assert cached["structured"]["thesis_one_liner"] == "Institutional-quality compounder"

    def test_get_miss_returns_cached_false(self):
        client = TestClient(app)
        g = client.get("/api/ai/institutional/NOINSTCACHEDXYZ")
        assert g.status_code == 200
        assert g.json() == {"cached": False, "symbol": "NOINSTCACHEDXYZ", "source": None}
