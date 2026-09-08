"""Unit tests for Issue #9 valuation DCF helper, parser, and routes."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_valuation_response
from backend.services.valuation_dcf_service import compute_simple_dcf


def _base_metrics(**overrides):
    m = {
        "identity": {"symbol": "VAL1"},
        "market": {"price": 100.0, "beta": 1.0},
        "valuation": {"market_cap": 1_000_000.0, "pe_ratio": 20},
        "growth": {"revenue_growth_pct": 10.0},
        "balance_sheet_cash": {"free_cash_flow": 50_000.0},
        "peers": [],
        "peer_comps": [],
    }
    m.update(overrides)
    return m


class TestComputeSimpleDcf:
    def test_returns_none_without_fcf(self):
        metrics = _base_metrics(balance_sheet_cash={"free_cash_flow": None})
        assert compute_simple_dcf(metrics) is None

    def test_returns_none_for_non_positive_fcf(self):
        metrics = _base_metrics(balance_sheet_cash={"free_cash_flow": -1})
        assert compute_simple_dcf(metrics) is None

    def test_clamps_negative_growth_and_computes_vs_price(self):
        metrics = _base_metrics(growth={"revenue_growth_pct": -50.0})
        dcf = compute_simple_dcf(metrics)
        assert dcf is not None
        assert dcf["growth_pct"] == -5.0
        assert dcf["discount_pct"] == 8.0
        assert "vs_price_pct" in dcf
        assert dcf["implied_value_per_share"] > 0


class TestParseValuationResponse:
    def test_extracts_verdict(self):
        raw = """## P/E

Cheap vs peers.

```json
{
  "verdict": "undervalued",
  "confidence": "high",
  "pe_vs_peers": "cheap",
  "summary": "Discount to peers"
}
```
"""
        md, structured = parse_valuation_response(raw)
        assert "P/E" in md
        assert structured is not None
        assert structured["verdict"] == "undervalued"
        assert structured["pe_vs_peers"] == "cheap"

    def test_invalid_verdict_defaults_fair(self):
        raw = 'memo\n```json\n{"verdict": "bargain", "confidence": "maybe", "pe_vs_peers": "x"}\n```'
        _, structured = parse_valuation_response(raw)
        assert structured is not None
        assert structured["verdict"] == "fair"
        assert structured["confidence"] == "medium"
        assert structured["pe_vs_peers"] == "unknown"


class TestValuationRoute:
    def test_post_upserts_and_get_returns_cache(self):
        client = TestClient(app)
        metrics = _base_metrics()
        with (
            patch(
                "backend.routers.ai.research_metrics_service.build_research_metrics",
                return_value=metrics,
            ),
            patch(
                "backend.routers.ai.gemini_service.generate_valuation_memo",
                return_value=(
                    "## Valuation\n\nFair.",
                    {
                        "verdict": "fair",
                        "confidence": "medium",
                        "pe_vs_peers": "inline",
                        "summary": "In line",
                    },
                    None,
                ),
            ),
        ):
            r = client.post(
                "/api/ai/valuation", json={"symbol": "VAL1", "period": "1y", "force": True}
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "live"
        assert body["structured"]["verdict"] == "fair"
        assert "dcf" in body["metrics"]

        g = client.get("/api/ai/valuation/VAL1")
        assert g.status_code == 200
        cached = g.json()
        assert cached["cached"] is True
        assert cached["markdown"].startswith("## Valuation")

    def test_get_miss_returns_cached_false(self):
        client = TestClient(app)
        g = client.get("/api/ai/valuation/NOVALCACHEDXYZ")
        assert g.status_code == 200
        assert g.json() == {"cached": False, "symbol": "NOVALCACHEDXYZ", "source": None}
