"""Pydantic schemas for CSP pre/post analysis (Issue #2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CspScreenRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    strategy: str | None = Field(
        default="cash_secured_put",
        description="Option strategy to screen for (defaults to CSP).",
    )


class SuggestedContract(BaseModel):
    strike: float
    expiration: str
    dte: int
    premium_mid: float
    delta: float
    option_type: Literal["put", "call"] = "put"
    side: Literal["sell_to_open", "buy_to_open"] = "sell_to_open"
    target_delta: float | None = None
    implied_volatility: float | None = None
    bid: float | None = None
    ask: float | None = None
    spread_pct: float | None = None
    open_interest: int | None = None
    volume: int | None = None
    otm_pct: float | None = None
    liquidity_ok: bool = True
    note: str | None = None


class CspVerdict(BaseModel):
    recommended_strike: float | None = None
    margin_of_safety_pct: float | None = None
    summary: str


class CspScreenResponse(BaseModel):
    ticker: str
    strategy: str = "cash_secured_put"
    strategy_label: str = "Cash-Secured Put"
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
    bid: float | None = None
    ask: float | None = None
    spread_pct: float | None = None
    open_interest: int | None = None
    liquidity_ok: bool | None = None
    disclaimer: str = "Not financial advice — for journaling and education only."


class TickerNoteUpsert(BaseModel):
    content: str = Field(default="", max_length=8000)


class TickerNoteResponse(BaseModel):
    ticker: str
    note_key: str
    content: str
    updated_at: str | None = None

