"""Unit tests for Issue #14 earnings context, parser, and routes."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.gemini_service import parse_earnings_response
from backend.services.research_metrics_service import build_earnings_context


class TestParseEarningsResponse:
    def test_extracts_surprise_and_markdown(self):
        raw = """## Revenue vs expectations

Beat on top line.

```json
{
  "surprise": "beat",
  "confidence": "high",
  "summary": "EPS beat with modest price reaction"
}
```
"""
        md, structured = parse_earnings_response(raw)
        assert "Revenue vs expectations" in md
        assert "```json" not in md
        assert structured is not None
        assert structured["surprise"] == "beat"
        assert structured["confidence"] == "high"
        assert structured["summary"] == "EPS beat with modest price reaction"

    def test_invalid_surprise_defaults_unknown(self):
        raw = 'memo\n```json\n{"surprise": "crush", "confidence": "maybe", "summary": "x"}\n```'
        _, structured = parse_earnings_response(raw)
        assert structured is not None
        assert structured["surprise"] == "unknown"
        assert structured["confidence"] == "medium"

    def test_invalid_json_returns_null_structured(self):
        md, structured = parse_earnings_response("Hello\n```json\n{bad}\n```")
        assert "Hello" in md
        assert structured is None


class TestBuildEarningsContext:
    def test_shape_with_mocked_yahoo(self):
        today = date.today()
        last = today - timedelta(days=40)
        nxt = today + timedelta(days=50)
        earnings_dates = pd.DataFrame(
            {
                "EPS Estimate": [2.0, 1.5],
                "Reported EPS": [float("nan"), 1.65],
                "Surprise(%)": [float("nan"), 10.0],
            },
            index=pd.to_datetime([nxt.isoformat(), last.isoformat()]),
        )
        # Newest-first income columns (yfinance style)
        income = pd.DataFrame(
            {
                pd.Timestamp("2025-12-31"): [100.0],
                pd.Timestamp("2024-12-31"): [80.0],
            },
            index=["Total Revenue"],
        )
        hist_idx = pd.bdate_range(end=today, periods=80)
        # Put a clear jump around last report date
        closes = [100.0] * len(hist_idx)
        for i, d in enumerate(hist_idx):
            if d.date() >= last:
                closes[i] = 110.0
        hist = pd.DataFrame({"Close": closes, "Volume": [1_000_000] * len(hist_idx)}, index=hist_idx)

        with (
            patch("backend.services.research_metrics_service.stock_service.get_info", return_value={}),
            patch(
                "backend.services.research_metrics_service.stock_service.get_earnings_dates",
                return_value=earnings_dates,
            ),
            patch(
                "backend.services.research_metrics_service.stock_service.get_financial_statements",
                return_value={"income_stmt": income},
            ),
            patch(
                "backend.services.research_metrics_service.stock_service.get_history",
                return_value=hist,
            ),
        ):
            ctx = build_earnings_context("EARN1")

        assert set(ctx.keys()) == {
            "last_report_date",
            "next_earnings_date",
            "eps_actual",
            "eps_estimate",
            "surprise_pct",
            "revenue_history",
            "price_reaction_pct",
        }
        assert ctx["last_report_date"] == last.isoformat()
        assert ctx["next_earnings_date"] == nxt.isoformat()
        assert ctx["eps_actual"] == 1.65
        assert ctx["eps_estimate"] == 1.5
        assert ctx["surprise_pct"] == 10.0
        assert isinstance(ctx["revenue_history"], list)
        assert len(ctx["revenue_history"]) >= 1
        assert ctx["price_reaction_pct"] is not None

    def test_missing_data_stays_null_no_invented_surprise(self):
        with (
            patch("backend.services.research_metrics_service.stock_service.get_info", return_value={}),
            patch(
                "backend.services.research_metrics_service.stock_service.get_earnings_dates",
                return_value=None,
            ),
            patch(
                "backend.services.research_metrics_service.stock_service.get_financial_statements",
                return_value={"income_stmt": None},
            ),
            patch(
                "backend.services.research_metrics_service.stock_service.get_history",
                return_value=None,
            ),
        ):
            ctx = build_earnings_context("NODATA")

        assert ctx["last_report_date"] is None
        assert ctx["next_earnings_date"] is None
        assert ctx["eps_actual"] is None
        assert ctx["eps_estimate"] is None
        assert ctx["surprise_pct"] is None
        assert ctx["revenue_history"] == []
        assert ctx["price_reaction_pct"] is None


class TestEarningsRoute:
    def test_post_upserts_and_get_returns_cache(self):
        client = TestClient(app)
        metrics = {
            "identity": {"symbol": "EARN1"},
            "market": {"price": 10},
            "growth": {"revenue_history": []},
            "peers": [],
            "peer_comps": [],
        }
        earnings_ctx = {
            "last_report_date": "2026-07-30",
            "next_earnings_date": "2026-10-29",
            "eps_actual": 2.02,
            "eps_estimate": 1.89,
            "surprise_pct": 6.74,
            "revenue_history": [],
            "price_reaction_pct": 1.2,
        }
        with (
            patch(
                "backend.routers.ai.research_metrics_service.build_research_metrics",
                return_value=metrics,
            ),
            patch(
                "backend.routers.ai.research_metrics_service.build_earnings_context",
                return_value=earnings_ctx,
            ),
            patch(
                "backend.routers.ai.gemini_service.generate_earnings_memo",
                return_value=(
                    "## Revenue vs expectations\n\nBeat.",
                    {
                        "surprise": "beat",
                        "confidence": "medium",
                        "summary": "EPS beat",
                    },
                    None,
                ),
            ),
        ):
            r = client.post(
                "/api/ai/earnings", json={"symbol": "EARN1", "period": "1y", "force": True}
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "live"
        assert body["structured"]["surprise"] == "beat"
        assert body["metrics"]["earnings_context"]["eps_actual"] == 2.02

        g = client.get("/api/ai/earnings/EARN1")
        assert g.status_code == 200
        cached = g.json()
        assert cached["cached"] is True
        assert cached["markdown"].startswith("## Revenue")
        assert cached["structured"]["surprise"] == "beat"

    def test_get_miss_returns_cached_false(self):
        client = TestClient(app)
        g = client.get("/api/ai/earnings/NOEARNCACHEDXYZ")
        assert g.status_code == 200
        assert g.json() == {"cached": False, "symbol": "NOEARNCACHEDXYZ", "source": None}
