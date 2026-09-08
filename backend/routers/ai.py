"""AI endpoints: Ollama summary/points and Gemini Wall Street memo (Issue #6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.config import GEMINI_MODEL
from backend.deps import get_db
from backend.services import gemini_service, ollama_service, research_metrics_service, stock_service

router = APIRouter(prefix="/api/ai", tags=["ai"])

WALL_STREET_ANALYSIS_TYPE = "wall_street"
MOAT_ANALYSIS_TYPE = "moat"
GROWTH_ANALYSIS_TYPE = "growth"


class SummaryRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"


class PointRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    point: int = Field(..., ge=1, le=15)
    period: str = "1y"


class WallStreetRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"
    force: bool = True


class MoatRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"
    force: bool = True


class GrowthRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"
    force: bool = True


def _fetch_context(symbol: str, period: str):
    hist = stock_service.get_history(symbol, period)
    if hist is None or hist.empty:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
    info = stock_service.get_info(symbol)
    earnings = stock_service.get_earnings(symbol)
    return hist, info, earnings


def _ai_memo_payload(
    *,
    symbol: str,
    markdown: str,
    structured: dict | None,
    metrics: dict | None,
    model: str | None,
    source: str,
    updated_at: str | None,
    cached: bool,
) -> dict:
    return {
        "cached": cached,
        "symbol": symbol,
        "metrics": metrics or {},
        "markdown": markdown,
        "structured": structured,
        "model": model or GEMINI_MODEL,
        "disclaimer": gemini_service.DISCLAIMER,
        "updated_at": updated_at,
        "source": source,
    }


def _wall_street_payload(**kwargs) -> dict:
    return _ai_memo_payload(**kwargs)


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


@router.get("/wall-street/{ticker}")
def get_wall_street_cache(ticker: str, db=Depends(get_db)):
    """Return cached Wall Street memo if present (200 + cached:false when missing)."""
    symbol = ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=422, detail="Ticker is required.")
    row = db.get_ai_analysis_cache(symbol, WALL_STREET_ANALYSIS_TYPE)
    if not row:
        return {"cached": False, "symbol": symbol, "source": None}
    return _wall_street_payload(
        symbol=symbol,
        markdown=row.get("markdown") or "",
        structured=row.get("structured"),
        metrics=row.get("metrics"),
        model=row.get("model"),
        source="cache",
        updated_at=row.get("updated_at"),
        cached=True,
    )


@router.post("/wall-street")
def wall_street_analysis(req: WallStreetRequest, db=Depends(get_db)):
    """Issue #6: yFinance metrics pack + Gemini research memo (always live; upserts cache)."""
    symbol = req.symbol.strip().upper()
    try:
        metrics = research_metrics_service.build_research_metrics(symbol, req.period)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch data for {symbol}: {exc}")

    markdown, structured, error = gemini_service.generate_wall_street_memo(metrics)
    if error:
        raise HTTPException(status_code=503, detail=error)

    saved = db.upsert_ai_analysis_cache(
        ticker=symbol,
        analysis_type=WALL_STREET_ANALYSIS_TYPE,
        markdown=markdown or "",
        model=GEMINI_MODEL,
        structured=structured,
        metrics=metrics,
    )
    updated_at = saved.get("updated_at") if saved else None

    return _wall_street_payload(
        symbol=symbol,
        markdown=markdown or "",
        structured=structured,
        metrics=metrics,
        model=GEMINI_MODEL,
        source="live",
        updated_at=updated_at,
        cached=False,
    )


@router.get("/moat/{ticker}")
def get_moat_cache(ticker: str, db=Depends(get_db)):
    """Return cached moat memo if present (200 + cached:false when missing)."""
    symbol = ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=422, detail="Ticker is required.")
    row = db.get_ai_analysis_cache(symbol, MOAT_ANALYSIS_TYPE)
    if not row:
        return {"cached": False, "symbol": symbol, "source": None}
    return _ai_memo_payload(
        symbol=symbol,
        markdown=row.get("markdown") or "",
        structured=row.get("structured"),
        metrics=row.get("metrics"),
        model=row.get("model"),
        source="cache",
        updated_at=row.get("updated_at"),
        cached=True,
    )


@router.post("/moat")
def moat_analysis(req: MoatRequest, db=Depends(get_db)):
    """Issue #8: competitive moat memo via Gemini (always live; upserts cache)."""
    symbol = req.symbol.strip().upper()
    try:
        metrics = research_metrics_service.build_research_metrics(symbol, req.period)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch data for {symbol}: {exc}")

    markdown, structured, error = gemini_service.generate_moat_memo(metrics)
    if error:
        raise HTTPException(status_code=503, detail=error)

    saved = db.upsert_ai_analysis_cache(
        ticker=symbol,
        analysis_type=MOAT_ANALYSIS_TYPE,
        markdown=markdown or "",
        model=GEMINI_MODEL,
        structured=structured,
        metrics=metrics,
    )
    updated_at = saved.get("updated_at") if saved else None

    return _ai_memo_payload(
        symbol=symbol,
        markdown=markdown or "",
        structured=structured,
        metrics=metrics,
        model=GEMINI_MODEL,
        source="live",
        updated_at=updated_at,
        cached=False,
    )


@router.get("/growth/{ticker}")
def get_growth_cache(ticker: str, db=Depends(get_db)):
    """Return cached growth memo if present (200 + cached:false when missing)."""
    symbol = ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=422, detail="Ticker is required.")
    row = db.get_ai_analysis_cache(symbol, GROWTH_ANALYSIS_TYPE)
    if not row:
        return {"cached": False, "symbol": symbol, "source": None}
    return _ai_memo_payload(
        symbol=symbol,
        markdown=row.get("markdown") or "",
        structured=row.get("structured"),
        metrics=row.get("metrics"),
        model=row.get("model"),
        source="cache",
        updated_at=row.get("updated_at"),
        cached=True,
    )


@router.post("/growth")
def growth_analysis(req: GrowthRequest, db=Depends(get_db)):
    """Issue #11: growth potential memo via Gemini (always live; upserts cache)."""
    symbol = req.symbol.strip().upper()
    try:
        metrics = research_metrics_service.build_research_metrics(symbol, req.period)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch data for {symbol}: {exc}")

    markdown, structured, error = gemini_service.generate_growth_memo(metrics)
    if error:
        raise HTTPException(status_code=503, detail=error)

    saved = db.upsert_ai_analysis_cache(
        ticker=symbol,
        analysis_type=GROWTH_ANALYSIS_TYPE,
        markdown=markdown or "",
        model=GEMINI_MODEL,
        structured=structured,
        metrics=metrics,
    )
    updated_at = saved.get("updated_at") if saved else None

    return _ai_memo_payload(
        symbol=symbol,
        markdown=markdown or "",
        structured=structured,
        metrics=metrics,
        model=GEMINI_MODEL,
        source="live",
        updated_at=updated_at,
        cached=False,
    )
