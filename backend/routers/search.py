"""GET /api/search — Yahoo autosuggest proxy for the global search box."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.services import stock_service

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search(q: str = Query(..., min_length=1, max_length=50), limit: int = Query(8, ge=1, le=20)):
    try:
        return {"query": q, "results": stock_service.search_symbols(q, limit)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Yahoo search unavailable: {exc}")
