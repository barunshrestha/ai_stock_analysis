"""Trading automation endpoint — wraps the existing scanner module."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from scanner import scan_stock

router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.get("/{symbol}")
def automation_scan(symbol: str, days: int = Query(60, ge=30, le=365)):
    symbol = symbol.upper()
    setup_info, trade_params, error = scan_stock(symbol, days=days)
    if error and not setup_info:
        raise HTTPException(status_code=502, detail=error)
    return {
        "symbol": symbol,
        "setup": setup_info if isinstance(setup_info, dict) else None,
        "trade_params": trade_params,
        "warning": error,
    }
