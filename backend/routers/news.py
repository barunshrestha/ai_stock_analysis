"""News feed endpoints for the Dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.auth import CurrentUser, get_current_user
from backend.deps import get_db
from backend.services import economic_calendar_service, news_service

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/feed")
def news_feed(
    category: str = Query("top", pattern="^(top|markets|economy|fed|policy|earnings)$"),
    limit: int = Query(40, ge=1, le=100),
):
    items = news_service.get_news_by_category(category, limit)
    return {"category": category, "items": items}


@router.get("/portfolio")
def portfolio_news(db=Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    symbols = db.get_all_portfolio_symbols(user.id)
    items = news_service.get_portfolio_news(symbols)
    return {"symbols": symbols, "items": items}


@router.get("/calendar")
def economic_calendar(days: int = Query(7, ge=1, le=14)):
    calendar = economic_calendar_service.get_economic_calendar(days)
    return {
        "days": days,
        "calendar_configured": calendar["configured"],
        "calendar_error": calendar["error"],
        "events": calendar["events"],
    }
