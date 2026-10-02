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


class CspScanRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    min_bid: float = Field(default=0.40, ge=0)
    min_open_interest: int = Field(default=500, ge=0)
    delta_min: float = Field(default=0.12, ge=0, le=1)
    delta_max: float = Field(default=0.25, ge=0, le=1)
    min_iv_pct: float = Field(default=25, ge=0)
    min_otm_pct: float = Field(default=3, ge=0)
    min_score: float = Field(default=40, ge=0, le=100)
    min_dte: int = Field(default=21, ge=0)
    max_dte: int = Field(default=45, ge=0)


class CspScanContract(BaseModel):
    symbol: str
    expiration: str
    strike: float
    bid: float
    delta: float
    iv_pct: float
    open_interest: int
    dte: int
    otm_pct: float
    premium_per_contract: float
    return_on_capital_pct: float
    annualized_return_pct: float
    breakeven: float
    composite_score: float


class CspScanFiltersOut(BaseModel):
    min_bid: float
    min_open_interest: int
    delta_min: float
    delta_max: float
    min_iv_pct: float
    min_otm_pct: float
    min_score: float
    min_dte: int
    max_dte: int


class CspScanResponse(BaseModel):
    ticker: str
    spot: float
    scanned_at: str
    filters: CspScanFiltersOut
    contracts: list[CspScanContract]
    disclaimer: str


class CspRecentScan(BaseModel):
    ticker: str
    scanned_at: str
    spot: float
    match_count: int
    filters: CspScanFiltersOut
    contracts: list[CspScanContract]

