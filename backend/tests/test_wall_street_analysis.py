"""Unit tests for Wall Street metrics pack and Gemini memo parser (Issue #6)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pandas as pd

from backend.services.gemini_service import parse_memo_response
from backend.services.research_metrics_service import build_research_metrics


class TestParseMemoResponse:
    def test_extracts_json_and_markdown(self):
        raw = """## Business model

Widgets for everyone.

```json
{
  "overall_stance": "bullish",
  "confidence": "medium",
  "base_case_summary": "Steady growth",
  "bull_case_summary": "Upside on margins",
  "bear_case_summary": "Competition rises"
}
```
"""
        md, structured = parse_memo_response(raw)
        assert "Business model" in md
        assert "```json" not in md
        assert structured is not None
        assert structured["overall_stance"] == "bullish"
        assert structured["confidence"] == "medium"
        assert structured["base_case_summary"] == "Steady growth"

    def test_invalid_json_returns_null_structured(self):
        raw = "Hello\n```json\n{not valid}\n```"
        md, structured = parse_memo_response(raw)
        assert "Hello" in md
        assert structured is None

    def test_normalizes_bad_stance(self):
        raw = 'x\n```json\n{"overall_stance":"maybe","confidence":"nope"}\n```'
        _, structured = parse_memo_response(raw)
        assert structured is not None
        assert structured["overall_stance"] == "neutral"
        assert structured["confidence"] == "medium"


class TestBuildResearchMetrics:
    def test_builds_stable_shape_with_null_safe_fields(self):
        hist = pd.DataFrame(
            {
                "Open": [10.0] * 30,
                "High": [11.0] * 30,
                "Low": [9.0] * 30,
                "Close": [10.0 + i * 0.1 for i in range(30)],
                "Volume": [1_000_000] * 30,
            },
            index=pd.date_range("2025-01-01", periods=30, freq="B"),
        )
        info = {
            "longName": "Test Corp",
            "sector": "Technology",
            "industry": "Software",
            "longBusinessSummary": "A" * 900,
            "marketCap": 1e9,
            "trailingPE": 20.0,
            "profitMargins": 0.15,
            "debtToEquity": 40.0,
            "freeCashflow": 1e8,
            "peers": ["MSFT", "GOOG"],
        }
        earnings = pd.DataFrame(
            {"Earnings": [1.0, 1.2, 1.5]},
            index=[datetime(2023, 1, 1), datetime(2024, 1, 1), datetime(2025, 1, 1)],
        )
        income = pd.DataFrame(
            {
                datetime(2024, 12, 31): [100.0, 10.0],
                datetime(2023, 12, 31): [90.0, 8.0],
            },
            index=["Total Revenue", "Net Income"],
        )

        with (
            patch("backend.services.research_metrics_service.stock_service.get_history", return_value=hist),
            patch("backend.services.research_metrics_service.stock_service.get_info", return_value=info),
            patch("backend.services.research_metrics_service.stock_service.get_earnings", return_value=earnings),
            patch(
                "backend.services.research_metrics_service.stock_service.get_financial_statements",
                return_value={"income_stmt": income, "balance_sheet": None, "cash_flow": None},
            ),
        ):
            pack = build_research_metrics("test", "1y")

        assert pack["identity"]["symbol"] == "TEST"
        assert pack["identity"]["name"] == "Test Corp"
        assert pack["identity"]["business_summary"] is not None
        assert len(pack["identity"]["business_summary"]) <= 701
        assert pack["valuation"]["pe_ratio"] == 20.0
        assert pack["profitability"]["profit_margin_pct"] == 15.0
        assert pack["peers"] == ["MSFT", "GOOG"]
        assert pack["peer_note"] is None
        assert "market" in pack and "growth" in pack and "trend" in pack

    def test_missing_peers_sets_note(self):
        hist = pd.DataFrame(
            {
                "Open": [10.0] * 25,
                "High": [11.0] * 25,
                "Low": [9.0] * 25,
                "Close": [10.0] * 25,
                "Volume": [1000] * 25,
            },
            index=pd.date_range("2025-01-01", periods=25, freq="B"),
        )
        with (
            patch("backend.services.research_metrics_service.stock_service.get_history", return_value=hist),
            patch("backend.services.research_metrics_service.stock_service.get_info", return_value={"longName": "X"}),
            patch("backend.services.research_metrics_service.stock_service.get_earnings", return_value=None),
            patch(
                "backend.services.research_metrics_service.stock_service.get_financial_statements",
                return_value={"income_stmt": None, "balance_sheet": None, "cash_flow": None},
            ),
        ):
            pack = build_research_metrics("XYZ")
        assert pack["peers"] is None
        assert "Peer list not available" in (pack["peer_note"] or "")

    def test_empty_history_raises(self):
        with patch(
            "backend.services.research_metrics_service.stock_service.get_history",
            return_value=pd.DataFrame(),
        ):
            try:
                build_research_metrics("NOPE")
                assert False, "expected LookupError"
            except LookupError:
                pass
