"""Pydantic schemas for CSP pre/post analysis (Issue #2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CspScreenRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)


class SuggestedContract(BaseModel):
    strike: float
    expiration: str
    dte: int
    premium_mid: float
    delta: float
    implied_volatility: float | None = None
    bid: float | None = None
    ask: float | None = None
    spread_pct: float | None = None
    open_interest: int | None = None
    volume: int | None = None
    otm_pct: float | None = None
    liquidity_ok: bool = True


class CspVerdict(BaseModel):
    recommended_strike: float | None = None
    margin_of_safety_pct: float | None = None
    summary: str


class CspScreenResponse(BaseModel):
    ticker: str
    overall_verdict: Literal["favorable", "mixed", "high_risk"]
    recommendation_color: Literal["green", "red"]
    sections: dict
    pros: list[str]
    cons: list[str]
    verdict: CspVerdict
    markdown: str
    suggested_contract: SuggestedContract | None = None
    disclaimer: str = "Not financial advice — for journaling and education only."


class CspMonitorResponse(BaseModel):
    ticker: str
    strike_price: float
    expiration_date: str
    initial_premium: float
    current_spot: float | None = None
    current_mid: float | None = None
    unrealized_pnl_pct: float | None = None
    trigger_close_alert: bool = False
    breached: bool = False
    net_cost_basis: float
    recommendation_color: Literal["green", "red"]
    recommendation: str
    markdown: str
    disclaimer: str = "Not financial advice — for journaling and education only."
