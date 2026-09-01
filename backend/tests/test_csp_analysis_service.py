"""Unit tests for CSP analysis helpers (Issue #2)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from backend.services.csp_analysis_service import (
    compute_breached,
    compute_trigger_close_alert,
    compute_unrealized_pnl_pct,
)
from backend.services.options_chain_service import find_put_near_delta


class TestMonitorMath:
    def test_unrealized_pnl_short_put_profit(self):
        assert compute_unrealized_pnl_pct(2.0, 1.0) == 50.0

    def test_unrealized_pnl_none_when_no_mark(self):
        assert compute_unrealized_pnl_pct(2.0, None) is None

    def test_trigger_close_at_half_premium(self):
        assert compute_trigger_close_alert(2.0, 1.0) is True
        assert compute_trigger_close_alert(2.0, 1.01) is False

    def test_breach_at_or_below_strike(self):
        assert compute_breached(100.0, 100.0) is True
        assert compute_breached(95.0, 100.0) is True

    def test_breach_within_three_percent(self):
        assert compute_breached(102.0, 100.0, breach_pct=3.0) is True
        assert compute_breached(104.0, 100.0, breach_pct=3.0) is False

    def test_no_breach_without_spot(self):
        assert compute_breached(None, 100.0) is False


class TestDeltaPicker:
    def test_picks_closest_delta_strike(self):
        chain = pd.DataFrame(
            [
                {"strike": 90.0, "bid": 1.0, "ask": 1.2, "impliedVolatility": 0.3},
                {"strike": 95.0, "bid": 2.0, "ask": 2.2, "impliedVolatility": 0.3},
                {"strike": 100.0, "bid": 4.0, "ask": 4.2, "impliedVolatility": 0.3},
            ]
        )
        exp = date.today() + timedelta(days=35)
        result = find_put_near_delta(chain, spot=100.0, expiration_date=exp, target_delta=0.30)
        assert result is not None
        assert result["strike"] in (90.0, 95.0, 100.0)
        assert 0.0 < result["delta"] < 1.0

    def test_empty_chain_returns_none(self):
        assert find_put_near_delta(pd.DataFrame(), spot=100.0, expiration_date=date.today()) is None
