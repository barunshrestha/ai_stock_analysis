"""Pydantic schemas for the options trade journal."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class StrategyType(str, Enum):
    cash_secured_put = "cash_secured_put"
    covered_call = "covered_call"
    short_put = "short_put"
    short_call = "short_call"
    long_call = "long_call"
    long_put = "long_put"
    put_credit_spread = "put_credit_spread"
    call_credit_spread = "call_credit_spread"
    put_debit_spread = "put_debit_spread"
    call_debit_spread = "call_debit_spread"
    iron_condor = "iron_condor"
    custom = "custom"


class OptionType(str, Enum):
    put = "put"
    call = "call"


class TradeSide(str, Enum):
    sell_to_open = "sell_to_open"
    buy_to_close = "buy_to_close"
    buy_to_open = "buy_to_open"
    sell_to_close = "sell_to_close"


class TradeStatus(str, Enum):
    open = "open"
    closed = "closed"
    assigned = "assigned"
    expired = "expired"


class Broker(str, Enum):
    robinhood = "robinhood"
    thinkorswim = "thinkorswim"
    webull = "webull"
    unknown = "unknown"


class LegInput(BaseModel):
    leg_index: int = Field(..., ge=1, le=4)
    option_type: OptionType
    side: TradeSide
    strike: float = Field(..., gt=0)
    premium_per_contract: float = Field(..., gt=0)
    expiration_date: date | None = None


class OptionTradeCreate(BaseModel):
    strategy_type: StrategyType
    ticker: str = Field(..., min_length=1, max_length=10)
    legs: list[LegInput] = Field(..., min_length=1, max_length=4)
    contracts: int = Field(..., ge=1)
    executed_at: datetime
    expiration_date: date
    net_credit_debit: float = Field(..., description="Net credit (+) or debit (-) per contract")
    collateral_override: float | None = Field(None, gt=0)
    broker: Broker | None = None
    notes: str | None = None

    @field_validator("ticker")
    @classmethod
    def upper_ticker(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def dates_valid(self) -> OptionTradeCreate:
        if self.expiration_date < self.executed_at.date():
            raise ValueError("expiration_date must be on or after execution date")
        return self


class OptionTradeClose(BaseModel):
    closed_at: datetime
    close_net_per_contract: float = Field(..., ge=0)
    assigned: bool = False


class OptionTradeUpdate(BaseModel):
    strategy_type: StrategyType | None = None
    legs: list[LegInput] | None = None
    contracts: int | None = Field(None, ge=1)
    executed_at: datetime | None = None
    expiration_date: date | None = None
    net_credit_debit: float | None = None
    collateral_override: float | None = None
    broker: Broker | None = None
    notes: str | None = None


STRATEGY_META: dict[str, dict] = {
    "cash_secured_put": {"label": "Cash-Secured Put", "legs": 1, "short_premium": True},
    "covered_call": {"label": "Covered Call", "legs": 1, "short_premium": True},
    "short_put": {"label": "Short Put (Naked)", "legs": 1, "short_premium": True},
    "short_call": {"label": "Short Call (Naked)", "legs": 1, "short_premium": True},
    "long_call": {"label": "Long Call", "legs": 1, "short_premium": False},
    "long_put": {"label": "Long Put", "legs": 1, "short_premium": False},
    "put_credit_spread": {"label": "Put Credit Spread", "legs": 2, "short_premium": True},
    "call_credit_spread": {"label": "Call Credit Spread", "legs": 2, "short_premium": True},
    "put_debit_spread": {"label": "Put Debit Spread", "legs": 2, "short_premium": False},
    "call_debit_spread": {"label": "Call Debit Spread", "legs": 2, "short_premium": False},
    "iron_condor": {"label": "Iron Condor", "legs": 4, "short_premium": True},
    "custom": {"label": "Custom", "legs": 1, "short_premium": None},
}


class IndicatorStatus(str, Enum):
    good = "good"
    neutral = "neutral"
    caution = "caution"
    bad = "bad"


class PreTradeIndicator(BaseModel):
    id: str
    label: str
    value: str
    status: IndicatorStatus
    impact: str
    annualized: str | None = None


class PreTradeAnalysis(BaseModel):
    overall_score: Literal["favorable", "mixed", "high_risk"]
    summary: str
    indicators: list[PreTradeIndicator]
    recommendations: list[str]


class ParseTextRequest(BaseModel):
    text: str = Field(..., min_length=10)
    broker: Broker | None = None
