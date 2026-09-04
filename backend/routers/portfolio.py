"""Portfolio endpoints backed by named portfolio buckets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from backend.deps import get_db
from backend.services import stock_service
from backend.services.grid_service import build_grid_rows
from backend.services.portfolio_import_service import import_portfolio_symbols, parse_portfolio_csv

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class PortfolioCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


def _resolve_portfolio_id(db, portfolio_id: int | None) -> int:
    pid = portfolio_id or db.ensure_default_portfolio()
    if not db.get_portfolio_bucket(pid):
        raise HTTPException(status_code=404, detail="Portfolio not found.")
    return pid


@router.get("/portfolios")
def list_portfolios(db=Depends(get_db)):
    db.ensure_default_portfolio()
    return {"portfolios": db.list_portfolio_buckets()}


@router.post("/portfolios", status_code=201)
def create_portfolio(body: PortfolioCreateRequest, db=Depends(get_db)):
    created = db.create_portfolio_bucket(body.name.strip())
    if not created:
        raise HTTPException(status_code=409, detail=f"Portfolio '{body.name.strip()}' already exists.")
    return created


@router.get("")
def get_portfolio(db=Depends(get_db), portfolio_id: int | None = Query(None)):
    pid = _resolve_portfolio_id(db, portfolio_id)
    bucket = db.get_portfolio_bucket(pid)
    return {
        "portfolio_id": pid,
        "name": bucket["name"] if bucket else "Portfolio",
        "symbols": db.get_portfolio(pid) or [],
    }


@router.get("/grid")
def portfolio_grid(db=Depends(get_db), period: str = Query("1y"), portfolio_id: int | None = Query(None)):
    """Comprehensive grid data for every symbol in a portfolio bucket."""
    pid = _resolve_portfolio_id(db, portfolio_id)
    symbols = db.get_portfolio(pid) or []
    rows, errors = build_grid_rows(symbols, period)
    bucket = db.get_portfolio_bucket(pid)
    return {
        "portfolio_id": pid,
        "name": bucket["name"] if bucket else "Portfolio",
        "rows": rows,
        "errors": errors,
    }


@router.post("/import-csv")
async def import_portfolio_csv(
    file: UploadFile = File(...),
    db=Depends(get_db),
    portfolio_id: int | None = Query(None),
):
    """Bulk-add symbols to a portfolio bucket from CSV."""
    pid = _resolve_portfolio_id(db, portfolio_id)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Upload must be a .csv file.")
    data = await file.read()
    if len(data) > 1024 * 1024:
        raise HTTPException(status_code=422, detail="CSV must be under 1 MB.")
    if not data.strip():
        raise HTTPException(status_code=422, detail="CSV file is empty.")

    symbols, parse_err = parse_portfolio_csv(data)
    if parse_err:
        raise HTTPException(status_code=422, detail=parse_err)

    summary = import_portfolio_symbols(symbols, db, pid)
    summary["portfolio_id"] = pid
    return summary


@router.post("/{symbol}", status_code=201)
def add_to_portfolio(
    symbol: str,
    db=Depends(get_db),
    portfolio_id: int | None = Query(None),
):
    pid = _resolve_portfolio_id(db, portfolio_id)
    symbol = symbol.upper()
    try:
        hist = stock_service.get_history(symbol, "1mo")
        if hist is None or hist.empty:
            raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not validate '{symbol}': {exc}")

    existing = db.get_portfolio(pid) or []
    if symbol in existing:
        raise HTTPException(status_code=409, detail=f"'{symbol}' is already in this portfolio")

    if not db.add_to_portfolio(symbol, pid):
        raise HTTPException(status_code=500, detail=f"Could not add '{symbol}'")

    try:
        db.save_stock_info(symbol, stock_service.get_info(symbol))
    except Exception:
        pass
    return {"symbol": symbol, "portfolio_id": pid, "added": True}


@router.delete("/{symbol}")
def remove_from_portfolio(
    symbol: str,
    db=Depends(get_db),
    portfolio_id: int | None = Query(None),
):
    pid = _resolve_portfolio_id(db, portfolio_id)
    symbol = symbol.upper()
    if not db.remove_from_portfolio(symbol, pid):
        raise HTTPException(status_code=404, detail=f"'{symbol}' is not in this portfolio")
    return {"symbol": symbol, "portfolio_id": pid, "removed": True}
