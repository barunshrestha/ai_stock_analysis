"""News feed endpoints for the Dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.deps import get_db
from backend.services import news_service

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/feed")
def news_feed(
    category: str = Query("top", pattern="^(top|markets|economy|fed|policy|earnings)$"),
    limit: int = Query(40, ge=1, le=100),
):
    items = news_service.get_news_by_category(category, limit)
    return {"category": category, "items": items}


@router.get("/portfolio")
def portfolio_news(db=Depends(get_db)):
    symbols = db.get_portfolio() or []
    items = news_service.get_portfolio_news(symbols)
    return {"symbols": symbols, "items": items}


@router.get("/calendar")
def economic_calendar(days: int = Query(7, ge=1, le=14)):
    events, finnhub_configured = news_service.get_economic_calendar(days)
    return {
        "days": days,
        "finnhub_configured": finnhub_configured,
        "events": events,
    }
