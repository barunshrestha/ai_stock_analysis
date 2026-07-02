"""Portfolio endpoints backed by the existing DatabaseManager portfolio table."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.deps import get_db
from backend.services import stock_service

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
def get_portfolio(db=Depends(get_db)):
    return {"symbols": db.get_portfolio() or []}


@router.get("/grid")
def portfolio_grid(db=Depends(get_db), period: str = Query("1y")):
    """Comprehensive grid data for every portfolio symbol (raw values)."""
    symbols = db.get_portfolio() or []
    rows = []
    errors = {}
    for symbol in symbols:
        try:
            hist = stock_service.get_history(symbol, period)
            if hist is None or hist.empty:
                errors[symbol] = "no history"
                continue
            info = stock_service.get_info(symbol)
            metrics = stock_service.compute_metrics(hist, info)
            # 6-month sparkline (~126 trading days), downsampled to keep payload small.
            spark = hist["Close"].tail(126)
            step = max(1, len(spark) // 60)
            rows.append(
                {
                    "symbol": symbol,
                    "name": info.get("longName") or info.get("shortName") or symbol,
                    "sector": info.get("sector"),
                    "metrics": metrics,
                    "sparkline": [round(float(v), 2) for v in spark.iloc[::step]],
                }
            )
        except Exception as exc:
            errors[symbol] = str(exc)
    return {"rows": rows, "errors": errors}


@router.post("/{symbol}", status_code=201)
def add_to_portfolio(symbol: str, db=Depends(get_db)):
    symbol = symbol.upper()
    # Validate the symbol exists on Yahoo before persisting.
    try:
        hist = stock_service.get_history(symbol, "1mo")
        if hist is None or hist.empty:
            raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not validate '{symbol}': {exc}")

    if not db.add_to_portfolio(symbol):
        raise HTTPException(status_code=409, detail=f"'{symbol}' is already in the portfolio")

    # Best-effort: cache company info for industry/sector lookups.
    try:
        db.save_stock_info(symbol, stock_service.get_info(symbol))
    except Exception:
        pass
    return {"symbol": symbol, "added": True}


@router.delete("/{symbol}")
def remove_from_portfolio(symbol: str, db=Depends(get_db)):
    symbol = symbol.upper()
    if not db.remove_from_portfolio(symbol):
        raise HTTPException(status_code=404, detail=f"'{symbol}' is not in the portfolio")
    return {"symbol": symbol, "removed": True}
