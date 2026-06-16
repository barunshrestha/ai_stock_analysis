"""Ollama AI endpoints: 4-section summary and 15-point analysis."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import ollama_service, stock_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


class SummaryRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"


class PointRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    point: int = Field(..., ge=1, le=15)
    period: str = "1y"


def _fetch_context(symbol: str, period: str):
    hist = stock_service.get_history(symbol, period)
    if hist is None or hist.empty:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
    info = stock_service.get_info(symbol)
    earnings = stock_service.get_earnings(symbol)
    return hist, info, earnings


@router.get("/points")
def list_points():
    """The 15 analysis point definitions (for rendering buttons in the UI)."""
    return {
        "points": [
            {"number": n, "title": t, "instruction": i}
            for n, t, i in ollama_service.ANALYSIS_POINTS
        ]
    }


@router.post("/summary")
def ai_summary(req: SummaryRequest):
    symbol = req.symbol.upper()
    try:
        hist, info, earnings = _fetch_context(symbol, req.period)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch data for {symbol}: {exc}")

    content, error = ollama_service.generate_summary(symbol, info, hist, earnings)
    if error:
        raise HTTPException(status_code=503, detail=error)
    return {"symbol": symbol, "summary": content}


@router.post("/point")
def ai_point(req: PointRequest):
    symbol = req.symbol.upper()
    try:
        hist, info, earnings = _fetch_context(symbol, req.period)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch data for {symbol}: {exc}")

    trend_context = stock_service.compute_trend_context(hist)
    content, error = ollama_service.generate_point_analysis(
        symbol, info, hist, earnings, trend_context, req.point
    )
    if error:
        raise HTTPException(status_code=503, detail=error)
    return {"symbol": symbol, "point": req.point, "content": content}
