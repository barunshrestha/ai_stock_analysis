"""Stock data endpoints: overview, history, financials, earnings."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.services import stock_service

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


def _validate_period(period: str) -> str:
    if period not in stock_service.VALID_PERIODS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid period '{period}'. Valid: {sorted(stock_service.VALID_PERIODS)}",
        )
    return period


@router.get("/{symbol}")
def stock_overview(symbol: str, period: str = Query("1y")):
    _validate_period(period)
    try:
        return stock_service.stock_overview(symbol, period)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch data for {symbol}: {exc}")


@router.get("/{symbol}/history")
def stock_history(symbol: str, period: str = Query("1y")):
    _validate_period(period)
    try:
        hist = stock_service.get_history(symbol, period)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch history for {symbol}: {exc}")
    if hist is None or hist.empty:
        raise HTTPException(status_code=404, detail=f"No historical data for '{symbol}'")
    return {
        "symbol": symbol.upper(),
        "period": period,
        "candles": stock_service.history_to_records(hist),
    }


@router.get("/{symbol}/financials")
def stock_financials(symbol: str):
    try:
        statements = stock_service.get_financial_statements(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch financials for {symbol}: {exc}")
    payload = {
        key: stock_service.statement_to_payload(df) for key, df in statements.items()
    }
    if all(v is None for v in payload.values()):
        raise HTTPException(status_code=404, detail=f"No financial statements for '{symbol}'")
    return {"symbol": symbol.upper(), **payload}


@router.get("/{symbol}/earnings")
def stock_earnings(symbol: str, years: int = Query(5, ge=1, le=10)):
    try:
        earnings = stock_service.get_earnings(symbol, years)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch earnings for {symbol}: {exc}")
    if earnings is None or earnings.empty:
        raise HTTPException(status_code=404, detail=f"No earnings data for '{symbol}'")
    return {
        "symbol": symbol.upper(),
        "earnings": [
            {"year": int(year), "net_income": float(row["Earnings"])}
            for year, row in earnings.iterrows()
        ],
    }


@router.get("/{symbol}/trend")
def stock_trend(symbol: str, period: str = Query("1y")):
    """Trend context (support/resistance/bad-entry zone) for the AI Analysis page."""
    _validate_period(period)
    try:
        hist = stock_service.get_history(symbol, period)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch history for {symbol}: {exc}")
    trend = stock_service.compute_trend_context(hist)
    if trend is None:
        raise HTTPException(status_code=404, detail=f"Not enough data to compute trend for '{symbol}'")
    return {"symbol": symbol.upper(), **trend}
