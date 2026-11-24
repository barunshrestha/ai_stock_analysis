"""Covered-call math, earnings modes, and relative score. No live Yahoo calls."""

from datetime import date

import pandas as pd
import pytest

from backend.services import cc_scan_service, options_chain_service, stock_service
from backend.services.cc_scan_service import (
    ScanFilters,
    candidates_from_chain,
    contract_math,
    expiration_allowed,
    scan_calls,
)


AS_OF = date(2026, 1, 10)
BEFORE = date(2026, 2, 1)
ON_EARNINGS = date(2026, 2, 10)
AFTER = date(2026, 2, 20)
EARNINGS = date(2026, 2, 10)


def _filters(**overrides) -> ScanFilters:
    base = dict(
        min_annualized_return_pct=8,
        delta_min=0.15,
        delta_max=0.30,
        min_otm_pct=2,
        max_otm_pct=5,
        min_dte=21,
        max_dte=45,
        min_iv_pct=40,
        min_open_interest=500,
        min_downside_protection_pct=2,
        min_score=40,
    )
    base.update(overrides)
    return ScanFilters(**base)


def _row(**overrides) -> dict:
    row = {
        "strike": 103,
        "bid": 2.0,
        "ask": 2.1,
        "openInterest": 2000,
        "impliedVolatility": 0.50,
        "delta": 0.16,
    }
    row.update(overrides)
    return row


def _chain(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows) or [_row()])


def test_contract_math_spot_100_strike_103_bid_2():
    math = contract_math(2, 103, 100, 30)
    assert math is not None
    assert math["premium_per_contract"] == 200
    assert math["downside_protection_pct"] == 2
    assert math["max_profit_if_called"] == 500
    assert math["return_on_capital_pct"] == 5
    assert math["breakeven"] == 98


def test_classic_drops_expiration_on_the_earnings_date():
    filters = _filters()
    assert expiration_allowed("classic", ON_EARNINGS, 31, EARNINGS, filters, AS_OF) is False
    assert expiration_allowed("classic", BEFORE, 22, EARNINGS, filters, AS_OF) is True

    dropped = candidates_from_chain(
        _chain(),
        symbol="TEST",
        spot=100,
        expiration="2026-02-10",
        expiration_date=ON_EARNINGS,
        dte=31,
        filters=filters,
        mode="classic",
        earnings_date=EARNINGS,
        as_of=AS_OF,
    )
    kept = candidates_from_chain(
        _chain(),
        symbol="TEST",
        spot=100,
        expiration="2026-02-01",
        expiration_date=BEFORE,
        dte=22,
        filters=filters,
        mode="classic",
        earnings_date=EARNINGS,
        as_of=AS_OF,
    )
    assert dropped == []
    assert len(kept) == 1


def test_classic_keeps_the_chain_when_earnings_are_missing():
    filters = _filters()
    assert expiration_allowed("classic", ON_EARNINGS, 31, None, filters, AS_OF) is True
    rows = candidates_from_chain(
        _chain(),
        symbol="TEST",
        spot=100,
        expiration="2026-02-10",
        expiration_date=ON_EARNINGS,
        dte=31,
        filters=filters,
        mode="classic",
        earnings_date=None,
        as_of=AS_OF,
    )
    assert len(rows) == 1
    assert rows[0]["earnings_date"] is None


def test_pre_earnings_rejects_a_missing_earnings_date(monkeypatch):
    hist = pd.DataFrame({"Close": [100.0]})
    monkeypatch.setattr(stock_service, "get_history", lambda *_a, **_k: hist)
    monkeypatch.setattr(options_chain_service, "get_upcoming_events", lambda _symbol: {})

    with pytest.raises(ValueError, match="no earnings date"):
        scan_calls("TEST", _filters(), "pre_earnings", as_of=AS_OF)


def test_pre_earnings_keeps_only_the_expiration_that_covers_an_in_window_report():
    filters = _filters(min_dte=30, max_dte=45)
    assert expiration_allowed("pre_earnings", BEFORE, 22, EARNINGS, filters, AS_OF) is False
    assert expiration_allowed("pre_earnings", AFTER, 41, EARNINGS, filters, AS_OF) is True

    far_earnings = date(2026, 4, 1)
    assert expiration_allowed("pre_earnings", date(2026, 4, 10), 90, far_earnings, filters, AS_OF) is False

    before = candidates_from_chain(
        _chain(),
        symbol="TEST",
        spot=100,
        expiration="2026-02-01",
        expiration_date=BEFORE,
        dte=22,
        filters=filters,
        mode="pre_earnings",
        earnings_date=EARNINGS,
        as_of=AS_OF,
    )
    covering = candidates_from_chain(
        _chain(),
        symbol="TEST",
        spot=100,
        expiration="2026-02-20",
        expiration_date=AFTER,
        dte=41,
        filters=filters,
        mode="pre_earnings",
        earnings_date=EARNINGS,
        as_of=AS_OF,
    )
    assert before == []
    assert len(covering) == 1
    assert covering[0]["earnings_date"] == "2026-02-10"


def test_single_survivor_scores_100():
    rows = candidates_from_chain(
        _chain(),
        symbol="TEST",
        spot=100,
        expiration="2026-02-20",
        expiration_date=AFTER,
        dte=30,
        filters=_filters(min_score=0),
        mode="classic",
        earnings_date=None,
        as_of=AS_OF,
    )
    scored = cc_scan_service.apply_relative_scores(rows, min_score=0)
    assert len(scored) == 1
    assert scored[0]["composite_score"] == 100
    assert scored[0]["liquidity_points"] == 30
    assert scored[0]["return_points"] == 25
    assert scored[0]["keep_points"] == 25
    assert scored[0]["iv_points"] == 20


def test_minimum_score_drops_a_contract_only_when_a_peer_scores_higher():
    winner = _row(strike=103, bid=2.0, ask=2.1, openInterest=2000, impliedVolatility=0.50, delta=0.16)
    loser = _row(strike=102, bid=2.0, ask=4.0, openInterest=500, impliedVolatility=0.40, delta=0.28)
    rows = candidates_from_chain(
        _chain(winner, loser),
        symbol="TEST",
        spot=100,
        expiration="2026-02-20",
        expiration_date=AFTER,
        dte=30,
        filters=_filters(min_score=0),
        mode="classic",
        earnings_date=None,
        as_of=AS_OF,
    )
    assert len(rows) == 2
    kept = cc_scan_service.apply_relative_scores(rows, min_score=40)
    assert [row["strike"] for row in kept] == [103]
    assert kept[0]["composite_score"] == 100

    alone = cc_scan_service.apply_relative_scores([rows[1]], min_score=40)
    assert len(alone) == 1
    assert alone[0]["strike"] == 102
    assert alone[0]["composite_score"] == 100
