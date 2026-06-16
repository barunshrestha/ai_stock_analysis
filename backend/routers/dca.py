"""DCA backtest endpoint."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import dca_service

router = APIRouter(prefix="/api/dca", tags=["dca"])


class BacktestRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=1, max_length=20)
    daily_invest: float = Field(..., gt=0)
    start_date: date
    end_date: date


@router.post("/backtest")
def run_backtest(req: BacktestRequest):
    if req.start_date >= req.end_date:
        raise HTTPException(status_code=422, detail="start_date must be before end_date")
    symbols = [s.strip().upper() for s in req.symbols if s.strip()]
    try:
        return dca_service.run_backtest(
            symbols,
            req.daily_invest,
            req.start_date.isoformat(),
            req.end_date.isoformat(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Backtest failed: {exc}")


@router.post("/score/{symbol}")
def stock_score(symbol: str):
    """Current DCA score breakdown for one symbol."""
    from backend.services import stock_service

    symbol = symbol.upper()
    try:
        hist = stock_service.get_history(symbol, "1y")
        if hist is None or hist.empty:
            raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
        info = stock_service.get_info(symbol)
        earnings = stock_service.get_earnings(symbol)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch data for {symbol}: {exc}")

    score, components = dca_service.calculate_stock_score(info, hist, earnings)
    return {
        "symbol": symbol,
        "score": round(score, 2),
        "components": {k: round(v, 2) for k, v in components.items()},
        "weights": dca_service.DCA_WEIGHTS,
    }
