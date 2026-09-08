"""AI endpoints: Ollama summary/points and Gemini Wall Street memo (Issue #6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.config import GEMINI_MODEL
from backend.deps import get_db
from backend.services import (
    gemini_service,
    ollama_service,
    research_metrics_service,
    stock_service,
    valuation_dcf_service,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])

WALL_STREET_ANALYSIS_TYPE = "wall_street"
MOAT_ANALYSIS_TYPE = "moat"
VALUATION_ANALYSIS_TYPE = "valuation"
RISK_ANALYSIS_TYPE = "risk"
GROWTH_ANALYSIS_TYPE = "growth"
INSTITUTIONAL_ANALYSIS_TYPE = "institutional"
DEBATE_ANALYSIS_TYPE = "debate"
EARNINGS_ANALYSIS_TYPE = "earnings"
VERDICT_ANALYSIS_TYPE = "verdict"


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


class ValuationRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"
    force: bool = True


class RiskRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"
    force: bool = True


class GrowthRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"
    force: bool = True


class InstitutionalRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"
    force: bool = True


class DebateRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"
    force: bool = True


class EarningsRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    period: str = "1y"
    force: bool = True


class VerdictRequest(BaseModel):
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


@router.get("/valuation/{ticker}")
def get_valuation_cache(ticker: str, db=Depends(get_db)):
    """Return cached valuation memo if present (200 + cached:false when missing)."""
    symbol = ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=422, detail="Ticker is required.")
    row = db.get_ai_analysis_cache(symbol, VALUATION_ANALYSIS_TYPE)
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


@router.post("/valuation")
def valuation_analysis(req: ValuationRequest, db=Depends(get_db)):
    """Issue #9: valuation memo with deterministic DCF sketch + Gemini (upserts cache)."""
    symbol = req.symbol.strip().upper()
    try:
        metrics = research_metrics_service.build_research_metrics(symbol, req.period)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch data for {symbol}: {exc}")

    metrics = {**metrics, "dcf": valuation_dcf_service.compute_simple_dcf(metrics)}

    markdown, structured, error = gemini_service.generate_valuation_memo(metrics)
    if error:
        raise HTTPException(status_code=503, detail=error)

    saved = db.upsert_ai_analysis_cache(
        ticker=symbol,
        analysis_type=VALUATION_ANALYSIS_TYPE,
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


def _live_memo_route(
    *,
    symbol: str,
    period: str,
    analysis_type: str,
    generate_fn,
    db,
    enrich=None,
):
    try:
        metrics = research_metrics_service.build_research_metrics(symbol, period)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch data for {symbol}: {exc}")

    if enrich is not None:
        metrics = enrich(symbol, metrics)

    markdown, structured, error = generate_fn(metrics)
    if error:
        raise HTTPException(status_code=503, detail=error)

    saved = db.upsert_ai_analysis_cache(
        ticker=symbol,
        analysis_type=analysis_type,
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


def _cached_memo_route(ticker: str, analysis_type: str, db):
    symbol = ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=422, detail="Ticker is required.")
    row = db.get_ai_analysis_cache(symbol, analysis_type)
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


@router.get("/risk/{ticker}")
def get_risk_cache(ticker: str, db=Depends(get_db)):
    return _cached_memo_route(ticker, RISK_ANALYSIS_TYPE, db)


@router.post("/risk")
def risk_analysis(req: RiskRequest, db=Depends(get_db)):
    """Issue #10: ranked risk memo via Gemini (always live; upserts cache)."""
    return _live_memo_route(
        symbol=req.symbol.strip().upper(),
        period=req.period,
        analysis_type=RISK_ANALYSIS_TYPE,
        generate_fn=gemini_service.generate_risk_memo,
        db=db,
    )


@router.get("/growth/{ticker}")
def get_growth_cache(ticker: str, db=Depends(get_db)):
    return _cached_memo_route(ticker, GROWTH_ANALYSIS_TYPE, db)


@router.post("/growth")
def growth_analysis(req: GrowthRequest, db=Depends(get_db)):
    """Issue #11: growth potential memo via Gemini (always live; upserts cache)."""
    return _live_memo_route(
        symbol=req.symbol.strip().upper(),
        period=req.period,
        analysis_type=GROWTH_ANALYSIS_TYPE,
        generate_fn=gemini_service.generate_growth_memo,
        db=db,
    )


@router.get("/institutional/{ticker}")
def get_institutional_cache(ticker: str, db=Depends(get_db)):
    return _cached_memo_route(ticker, INSTITUTIONAL_ANALYSIS_TYPE, db)


@router.post("/institutional")
def institutional_analysis(req: InstitutionalRequest, db=Depends(get_db)):
    """Issue #12: institutional PM perspective via Gemini (always live; upserts cache)."""
    return _live_memo_route(
        symbol=req.symbol.strip().upper(),
        period=req.period,
        analysis_type=INSTITUTIONAL_ANALYSIS_TYPE,
        generate_fn=gemini_service.generate_institutional_memo,
        db=db,
    )


@router.get("/debate/{ticker}")
def get_debate_cache(ticker: str, db=Depends(get_db)):
    return _cached_memo_route(ticker, DEBATE_ANALYSIS_TYPE, db)


@router.post("/debate")
def debate_analysis(req: DebateRequest, db=Depends(get_db)):
    """Issue #13: bull vs bear debate via Gemini (always live; upserts cache)."""
    return _live_memo_route(
        symbol=req.symbol.strip().upper(),
        period=req.period,
        analysis_type=DEBATE_ANALYSIS_TYPE,
        generate_fn=gemini_service.generate_debate_memo,
        db=db,
    )


def _enrich_earnings(symbol: str, metrics: dict) -> dict:
    return {**metrics, "earnings_context": research_metrics_service.build_earnings_context(symbol)}


@router.get("/earnings/{ticker}")
def get_earnings_cache(ticker: str, db=Depends(get_db)):
    return _cached_memo_route(ticker, EARNINGS_ANALYSIS_TYPE, db)


@router.post("/earnings")
def earnings_analysis(req: EarningsRequest, db=Depends(get_db)):
    """Issue #14: earnings report breakdown via Gemini (always live; upserts cache)."""
    return _live_memo_route(
        symbol=req.symbol.strip().upper(),
        period=req.period,
        analysis_type=EARNINGS_ANALYSIS_TYPE,
        generate_fn=gemini_service.generate_earnings_memo,
        db=db,
        enrich=_enrich_earnings,
    )


@router.get("/verdict/{ticker}")
def get_verdict_cache(ticker: str, db=Depends(get_db)):
    return _cached_memo_route(ticker, VERDICT_ANALYSIS_TYPE, db)


@router.post("/verdict")
def verdict_analysis(req: VerdictRequest, db=Depends(get_db)):
    """Issue #15: Buy/Hold/Avoid journal verdict via Gemini (always live; upserts cache)."""
    return _live_memo_route(
        symbol=req.symbol.strip().upper(),
        period=req.period,
        analysis_type=VERDICT_ANALYSIS_TYPE,
        generate_fn=gemini_service.generate_verdict_memo,
        db=db,
    )

