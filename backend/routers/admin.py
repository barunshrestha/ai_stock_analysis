"""Admin endpoints for stock-industry assignments (existing stock_industry table)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.deps import get_db

router = APIRouter(prefix="/api/admin/industries", tags=["admin"])


class AssignRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    industries: list[str] = Field(..., min_length=1)


class SetIndustriesRequest(BaseModel):
    industries: list[str]


@router.get("")
def list_industries(db=Depends(get_db)):
    """All industries with their assigned stocks."""
    return {"industries": db.admin_get_industries_with_stocks() or {}}


@router.post("/assign", status_code=201)
def assign_stock(req: AssignRequest, db=Depends(get_db)):
    symbol = req.symbol.upper()
    results = {}
    for industry in req.industries:
        industry = industry.strip()
        if not industry:
            continue
        ok, err = db.admin_add_stock_to_industry(symbol, industry)
        results[industry] = "added" if ok else (err or "failed")
    if not any(v == "added" for v in results.values()):
        raise HTTPException(status_code=422, detail={"symbol": symbol, "results": results})
    return {"symbol": symbol, "results": results}


@router.put("/stock/{symbol}")
def set_stock_industries(symbol: str, req: SetIndustriesRequest, db=Depends(get_db)):
    """Replace all industry assignments for a symbol."""
    symbol = symbol.upper()
    industries = [i.strip() for i in req.industries if i.strip()]
    ok, err = db.admin_set_stock_industries(symbol, industries)
    if not ok:
        raise HTTPException(status_code=422, detail=err or "Failed to update industries")
    return {"symbol": symbol, "industries": industries}


@router.delete("/stock/{symbol}/{industry}")
def remove_assignment(symbol: str, industry: str, db=Depends(get_db)):
    symbol = symbol.upper()
    ok, err = db.admin_remove_stock_from_industry(symbol, industry)
    if not ok:
        raise HTTPException(status_code=404, detail=err or "Assignment not found")
    return {"symbol": symbol, "industry": industry, "removed": True}
