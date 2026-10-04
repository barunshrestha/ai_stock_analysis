"""Unit tests for the cash-secured put scanner (story #32). No live Yahoo calls."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from backend.services.csp_scan_service import (
    ScanFilters,
    contracts_from_chain,
    expirations_in_window,
    scan_puts,
    sort_contracts,
    validate_scan_filters,
)


def _row(**overrides) -> dict:
    base = {
        "strike": 90.0,
        "bid": 2.0,
        "openInterest": 1500,
        "impliedVolatility": 0.40,
        "delta": 0.20,
    }
    base.update(overrides)
    return base


def _chain(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def _kept(**overrides) -> list[dict]:
    filters = overrides.pop("filters", ScanFilters())
    dte = overrides.pop("dte", 30)
    spot = overrides.pop("spot", 100.0)
    row = _row(**overrides)
    return contracts_from_chain(
        _chain(row),
        symbol="AAPL",
        spot=spot,
        expiration="2026-10-16",
        dte=dte,
        filters=filters,
    )


class TestFilters:
    def test_drops_bid_under_minimum(self):
        assert _kept(bid=0.30) == []

    def test_drops_open_interest_under_minimum(self):
        assert _kept(openInterest=499) == []

    def test_drops_delta_above_range(self):
        assert _kept(delta=0.30) == []

    def test_drops_low_iv(self):
        assert _kept(impliedVolatility=0.20) == []

    def test_drops_strike_too_close_to_spot(self):
        assert _kept(strike=98.0) == []

    def test_drops_dte_outside_window(self):
        assert _kept(dte=14) == []
        assert _kept(dte=60) == []

    def test_drops_when_capital_at_risk_is_not_positive(self):
        assert _kept(bid=90.0, strike=90.0) == []

    def test_drops_score_under_minimum_only_when_a_peer_scores_higher(self):
        filters = ScanFilters(min_score=80)
        chain = _chain(
            _row(ask=2.2, openInterest=2000),
            _row(ask=4.0, openInterest=600),
        )
        rows = contracts_from_chain(
            chain,
            symbol="AAPL",
            spot=100.0,
            expiration="2026-10-16",
            dte=30,
            filters=filters,
        )
        assert len(rows) == 1
        assert rows[0]["open_interest"] == 2000
        assert rows[0]["composite_score"] == 100.0

    def test_expiration_window_keeps_only_in_range_dates(self):
        ref = date(2026, 9, 26)
        expirations = [
            (ref + timedelta(days=14)).isoformat(),
            (ref + timedelta(days=30)).isoformat(),
            (ref + timedelta(days=60)).isoformat(),
        ]
        selected = expirations_in_window(expirations, ScanFilters(), ref)
        assert [days for _, days in selected] == [30]


class TestValidation:
    def test_min_delta_above_max(self):
        filters = ScanFilters(delta_min=0.30, delta_max=0.12)
        with pytest.raises(ValueError, match="Minimum delta must be less than or equal to maximum delta"):
            validate_scan_filters(filters)

    def test_max_dte_below_min(self):
        filters = ScanFilters(min_dte=45, max_dte=21)
        with pytest.raises(ValueError, match="Maximum days to expiration must be at least the minimum"):
            validate_scan_filters(filters)


class TestMath:
    def test_premium_roc_and_breakeven(self):
        rows = _kept()
        assert len(rows) == 1
        row = rows[0]
        assert row["premium_per_contract"] == 200.0
        assert row["capital_at_risk"] == 8800.0
        assert row["return_on_capital_pct"] == 2.273
        assert row["annualized_return_pct"] == 27.65
        assert row["breakeven"] == 88.0
        assert row["otm_pct"] == 10.0
        assert row["probability_of_profit"] == 0.8
        assert row["composite_score"] == 100.0

    def test_single_survivor_scores_100(self):
        rows = _kept(bid=0.40, strike=97.0, impliedVolatility=0.25, openInterest=500, delta=0.25, dte=45)
        assert len(rows) == 1
        assert rows[0]["composite_score"] == 100.0

    def test_tighter_spread_and_higher_open_interest_ranks_first(self):
        chain = _chain(
            _row(ask=2.2, openInterest=2000),
            _row(ask=4.0, openInterest=600),
        )
        rows = sort_contracts(
            contracts_from_chain(
                chain,
                symbol="AAPL",
                spot=100.0,
                expiration="2026-10-16",
                dte=30,
                filters=ScanFilters(min_score=0),
            )
        )
        assert [row["open_interest"] for row in rows] == [2000, 600]
        assert rows[0]["liquidity_points"] == 30.0
        assert rows[1]["liquidity_points"] == 0.0
        assert rows[0]["composite_score"] == 100.0
        assert rows[1]["composite_score"] == 70.0

    def test_sorts_highest_score_first(self):
        chain = _chain(
            _row(strike=90.0, bid=2.0, delta=0.20),
            _row(strike=85.0, bid=3.0, delta=0.18, openInterest=2000, impliedVolatility=0.55),
        )
        rows = sort_contracts(
            contracts_from_chain(
                chain,
                symbol="AAPL",
                spot=100.0,
                expiration="2026-10-16",
                dte=30,
                filters=ScanFilters(min_score=0),
            )
        )
        assert [r["strike"] for r in rows] == [85.0, 90.0]
        assert rows[0]["composite_score"] > rows[1]["composite_score"]


class TestScanOrchestration:
    def test_fetches_only_expirations_inside_the_window(self, monkeypatch):
        ref = date(2026, 9, 26)
        near = (ref + timedelta(days=14)).isoformat()
        mid = (ref + timedelta(days=30)).isoformat()
        far = (ref + timedelta(days=60)).isoformat()
        fetched: list[str] = []

        monkeypatch.setattr(
            "backend.services.csp_scan_service.stock_service.get_history",
            lambda symbol, period: pd.DataFrame({"Close": [100.0]}),
        )
        monkeypatch.setattr(
            "backend.services.csp_scan_service.options_chain_service.get_expirations",
            lambda symbol: [near, mid, far],
        )

        def _chain(symbol, expiration):
            fetched.append(expiration)
            return _chain_frame()

        monkeypatch.setattr(
            "backend.services.csp_scan_service.options_chain_service.get_puts_chain",
            _chain,
        )

        result = scan_puts("aapl", ScanFilters(), as_of=ref)
        assert fetched == [mid]
        assert result["ticker"] == "AAPL"
        assert result["spot"] == 100.0
        assert len(result["contracts"]) == 1
        assert result["contracts"][0]["symbol"] == "AAPL"


def _chain_frame() -> pd.DataFrame:
    return _chain(_row())
