"""Unit tests for Issue #10 risk memo parsing and route shape."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_risk_response


class TestParseRiskResponse:
    def test_extracts_ranked_risks_and_markdown(self):
        raw = """## Economic risks

Rates and demand softness.

```json
{
  "overall_risk": "high",
  "confidence": "medium",
  "ranked_risks": [
    {"rank": 2, "category": "competition", "title": "Peers gaining share", "severity": "medium"},
    {"rank": 1, "category": "economic", "title": "Macro slowdown", "severity": "high"},
    {"rank": 3, "category": "regulatory", "title": "Policy overhang", "severity": "low"}
  ],
  "summary": "Macro and competition lead the risk stack"
}
```
"""
        md, structured = parse_risk_response(raw)
        assert "Economic risks" in md
        assert "```json" not in md
        assert structured is not None
        assert structured["overall_risk"] == "high"
        assert structured["confidence"] == "medium"
        ranks = [r["rank"] for r in structured["ranked_risks"]]
        assert ranks == sorted(ranks)
        assert structured["ranked_risks"][0]["category"] == "economic"
        assert structured["ranked_risks"][0]["title"] == "Macro slowdown"

    def test_normalizes_enums_sorts_and_caps_to_five(self):
        raw = """memo
```json
{
  "overall_risk": "scary",
  "confidence": "maybe",
  "ranked_risks": [
    {"rank": 9, "category": "debt", "title": "Leverage", "severity": "HIGH"},
    {"rank": 1, "category": "magic", "title": "Unknown", "severity": "nope"},
    {"rank": 3, "category": "industry disruption", "title": "Tech shift", "severity": "low"},
    {"rank": 2, "category": "competition", "title": "Share loss", "severity": "medium"},
    {"rank": 4, "category": "regulatory", "title": "Rules", "severity": "medium"},
    {"rank": 5, "category": "economic", "title": "Cycle", "severity": "high"},
    {"rank": 6, "category": "other", "title": "Extra", "severity": "low"}
  ],
  "summary": "Crowded risk list"
}
```"""
        _, structured = parse_risk_response(raw)
        assert structured is not None
        assert structured["overall_risk"] == "medium"
        assert structured["confidence"] == "medium"
        risks = structured["ranked_risks"]
        assert len(risks) == 5
        assert [r["rank"] for r in risks] == [1, 2, 3, 4, 5]
        assert risks[0]["category"] == "other"  # invalid "magic" → other
        assert risks[1]["category"] == "competition"
        assert risks[2]["category"] == "disruption"  # alias
        assert risks[3]["category"] == "regulatory"
        assert risks[4]["category"] == "economic"
        # debt→financial was rank 9 and dropped by the cap-to-5 rule
        assert all(r["severity"] in ("low", "medium", "high") for r in risks)

    def test_defaults_missing_categories(self):
        raw = 'x\n```json\n{"overall_risk": "low", "confidence": "high", "ranked_risks": [], "summary": "Thin"}\n```'
        _, structured = parse_risk_response(raw)
        assert structured is not None
        cats = {r["category"] for r in structured["ranked_risks"]}
        assert cats >= {"economic", "disruption", "competition", "regulatory", "financial"}
        assert len(structured["ranked_risks"]) == 5

    def test_invalid_json_returns_null_structured(self):
        md, structured = parse_risk_response("Hello\n```json\n{bad}\n```")
        assert "Hello" in md
        assert structured is None


class TestRiskRoute:
    def test_post_upserts_and_get_returns_cache(self):
        client = TestClient(app)
        metrics = {
            "identity": {"symbol": "RISK1"},
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
                "backend.routers.ai.gemini_service.generate_risk_memo",
                return_value=(
                    "## Risk\n\nElevated.",
                    {
                        "overall_risk": "medium",
                        "confidence": "high",
                        "ranked_risks": [
                            {
                                "rank": 1,
                                "category": "financial",
                                "title": "Debt load",
                                "severity": "high",
                            }
                        ],
                        "summary": "Balance sheet leads risks",
                    },
                    None,
                ),
            ),
        ):
            r = client.post("/api/ai/risk", json={"symbol": "RISK1", "period": "1y", "force": True})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "live"
        assert body["structured"]["overall_risk"] == "medium"

        g = client.get("/api/ai/risk/RISK1")
        assert g.status_code == 200
        cached = g.json()
        assert cached["cached"] is True
        assert cached["markdown"].startswith("## Risk")
        assert cached["structured"]["ranked_risks"][0]["category"] == "financial"

    def test_get_miss_returns_cached_false(self):
        client = TestClient(app)
        g = client.get("/api/ai/risk/NORISKCACHEDXYZ")
        assert g.status_code == 200
        assert g.json() == {"cached": False, "symbol": "NORISKCACHEDXYZ", "source": None}
