"""Pydantic schemas for the covered-call screener."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CcScanFiltersIn(BaseModel):
    min_annualized_return_pct: float = Field(..., ge=0)
    delta_min: float = Field(..., ge=0, le=1)
    delta_max: float = Field(..., ge=0, le=1)
    min_otm_pct: float = Field(..., ge=0)
    max_otm_pct: float = Field(..., ge=0)
    min_dte: int = Field(..., ge=0)
    max_dte: int = Field(..., ge=0)
    min_iv_pct: float = Field(..., ge=0)
    min_open_interest: int = Field(..., ge=0)
    min_downside_protection_pct: float = Field(..., ge=0)
    min_score: float = Field(..., ge=0, le=100)


class CcScanFiltersOut(BaseModel):
    min_annualized_return_pct: float
    delta_min: float
    delta_max: float
    min_otm_pct: float
    max_otm_pct: float
    min_dte: int
    max_dte: int
    min_iv_pct: float
    min_open_interest: int
    min_downside_protection_pct: float
    min_score: float


class CcScanRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    mode: Literal["classic", "pre_earnings"] = "classic"
    filters: CcScanFiltersIn


class CcScanContract(BaseModel):
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
    downside_protection_pct: float
    max_profit_if_called: float
    return_on_capital_pct: float
    annualized_return_pct: float
    breakeven: float
    earnings_date: str | None = None
    probability_of_keeping_premium: float
    liquidity_points: float
    return_points: float
    keep_points: float
    iv_points: float
    composite_score: float


class CcScanResponse(BaseModel):
    ticker: str
    spot: float
    scanned_at: str
    mode: Literal["classic", "pre_earnings"]
    earnings_date: str | None = None
    filters: CcScanFiltersOut
    contracts: list[CcScanContract]
    disclaimer: str


class CcRecentScan(BaseModel):
    ticker: str
    scanned_at: str
    spot: float
    mode: Literal["classic", "pre_earnings"]
    earnings_date: str | None = None
    match_count: int
    filters: CcScanFiltersOut
    contracts: list[CcScanContract]


class CcProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)
    filters: CcScanFiltersIn


class CcProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    filters: CcScanFiltersIn | None = None


class CcRiskProfile(BaseModel):
    id: int
    name: str
    filters: CcScanFiltersOut
