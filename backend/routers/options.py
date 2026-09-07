"""Options trade journal, pre-trade analysis, OCR parse, and market context."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from backend.deps import get_db
from backend.schemas.options import (
    STRATEGY_META,
    LegInput,
    OptionTradeClose,
    OptionTradeCreate,
    OptionTradeUpdate,
    ParseTextRequest,
    StrategyType,
)
from backend.schemas.csp import CspScreenRequest, TickerNoteUpsert
from backend.services import (
    csp_analysis_service,
    market_context_service,
    options_advisory_service,
    options_image_parser_service,
    options_metrics_service,
    options_pretrade_service,
)

router = APIRouter(prefix="/api/options", tags=["options"])


@router.get("/strategies")
def list_strategies():
    return {
        "strategies": [
            {"id": k, **v}
            for k, v in STRATEGY_META.items()
        ]
    }


@router.get("/market/context")
def market_context():
    return market_context_service.get_market_context()


@router.get("/ticker-notes/{ticker}")
def get_ticker_note(
    ticker: str,
    note_key: str = Query("liquidity", min_length=1, max_length=40),
    db=Depends(get_db),
):
    note = db.get_ticker_analysis_note(ticker, note_key)
    if not note:
        return {"ticker": ticker.strip().upper(), "note_key": note_key, "content": "", "updated_at": None}
    return note


@router.put("/ticker-notes/{ticker}")
def upsert_ticker_note(
    ticker: str,
    body: TickerNoteUpsert,
    note_key: str = Query("liquidity", min_length=1, max_length=40),
    db=Depends(get_db),
):
    saved = db.upsert_ticker_analysis_note(ticker, note_key, body.content)
    if not saved:
        raise HTTPException(status_code=500, detail="Could not save note.")
    return saved


@router.post("/csp/screen")
def csp_screen(req: CspScreenRequest):
    try:
        return csp_analysis_service.analyze_stock_for_strategy(
            req.ticker, req.strategy or "cash_secured_put"
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/trades/{trade_id}/monitor")
def monitor_trade(trade_id: int, db=Depends(get_db)):
    trade = db.get_options_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")
    if trade["status"] != "open":
        raise HTTPException(status_code=422, detail="Monitoring is only for open trades.")
    if trade["strategy_type"] not in ("cash_secured_put", "short_put"):
        raise HTTPException(status_code=422, detail="Monitoring supports CSP / short put trades only.")

    from datetime import date as date_cls

    strike = trade["legs"][0]["strike"] if trade.get("legs") else trade["metrics"].get("short_strike")
    if not strike:
        raise HTTPException(status_code=422, detail="Trade has no strike on file.")
    exp = date_cls.fromisoformat(trade["expiration_date"])
    try:
        result = csp_analysis_service.monitor_active_csp(
            trade["ticker"],
            float(strike),
            exp,
            float(trade["net_credit_debit"]),
        )
        return result.model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/monitoring/summary")
def monitoring_summary(db=Depends(get_db)):
    """Alert badges for open CSP trades in the journal."""
    trades = db.list_options_trades(status="open")
    alerts = []
    from datetime import date as date_cls

    for t in trades:
        if t["strategy_type"] not in ("cash_secured_put", "short_put"):
            continue
        strike = t["legs"][0]["strike"] if t.get("legs") else None
        if not strike:
            continue
        try:
            mon = csp_analysis_service.monitor_active_csp(
                t["ticker"],
                float(strike),
                date_cls.fromisoformat(t["expiration_date"]),
                float(t["net_credit_debit"]),
            )
            if mon.trigger_close_alert or mon.breached:
                alerts.append(
                    {
                        "trade_id": t["id"],
                        "ticker": t["ticker"],
                        "trigger_close_alert": mon.trigger_close_alert,
                        "breached": mon.breached,
                        "unrealized_pnl_pct": mon.unrealized_pnl_pct,
                    }
                )
        except Exception:
            continue
    return {"alerts": alerts}


@router.post("/pre-trade/analyze")
def pre_trade_analyze(trade: OptionTradeCreate):
    try:
        return options_pretrade_service.analyze_pretrade(trade).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/parse-text")
def parse_text(req: ParseTextRequest):
    return options_image_parser_service.parse_text_to_draft(req.text, req.broker)


@router.post("/parse-image")
async def parse_image(
    file: UploadFile = File(...),
    broker: str | None = Form(None),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="Upload must be an image file.")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Image must be under 10 MB.")
    from backend.schemas.options import Broker

    b = Broker(broker) if broker else None
    result, err = options_image_parser_service.parse_image(data, b)
    if err:
        raise HTTPException(status_code=422, detail=err)
    return result


@router.post("/trades")
def create_trade(trade: OptionTradeCreate, db=Depends(get_db)):
    metrics = options_metrics_service.compute_metrics(trade)
    advisory = options_advisory_service.build_advisory(
        trade.strategy_type.value, metrics, trade.ticker
    )
    trade_row, leg_rows = options_metrics_service.trade_to_db_payload(trade, metrics, advisory)
    saved = db.create_options_trade(trade_row, leg_rows)
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to save trade.")
    return saved


@router.get("/trades")
def list_trades(
    status: str | None = Query(None, pattern="^(open|closed|assigned|expired)$"),
    ticker: str | None = None,
    db=Depends(get_db),
):
    return {"trades": db.list_options_trades(status=status, ticker=ticker)}


@router.get("/trades/{trade_id}")
def get_trade(trade_id: int, db=Depends(get_db)):
    trade = db.get_options_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")
    return trade


@router.patch("/trades/{trade_id}")
def update_trade(trade_id: int, body: OptionTradeUpdate, db=Depends(get_db)):
    existing = db.get_options_trade(trade_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Trade not found.")
    if existing["status"] != "open":
        raise HTTPException(status_code=422, detail="Only open trades can be edited.")

    merged = OptionTradeCreate(
        strategy_type=body.strategy_type or StrategyType(existing["strategy_type"]),
        ticker=existing["ticker"],
        legs=body.legs
        or [LegInput(**leg) for leg in existing["legs"]],
        contracts=body.contracts or existing["contracts"],
        executed_at=body.executed_at or datetime.fromisoformat(existing["executed_at"]),
        expiration_date=body.expiration_date
        or datetime.fromisoformat(existing["expiration_date"]).date(),
        net_credit_debit=body.net_credit_debit if body.net_credit_debit is not None else existing["net_credit_debit"],
        collateral_override=body.collateral_override if body.collateral_override is not None else existing.get("collateral_override"),
        broker=body.broker,
        notes=body.notes if body.notes is not None else existing.get("notes"),
    )
    metrics = options_metrics_service.compute_metrics(merged)
    advisory = options_advisory_service.build_advisory(
        merged.strategy_type.value, metrics, merged.ticker
    )
    trade_row, leg_rows = options_metrics_service.trade_to_db_payload(merged, metrics, advisory)
    trade_row.pop("status", None)
    updated = db.update_options_trade(trade_id, trade_row, leg_rows)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update trade.")
    return updated


@router.patch("/trades/{trade_id}/close")
def close_trade(trade_id: int, body: OptionTradeClose, db=Depends(get_db)):
    existing = db.get_options_trade(trade_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Trade not found.")
    if existing["status"] != "open":
        raise HTTPException(status_code=422, detail="Trade is not open.")

    is_short = existing.get("metrics", {}).get("is_short_premium", existing["net_credit_debit"] > 0)
    pnl = options_metrics_service.compute_close_pnl(
        existing["net_credit_debit"],
        body.close_net_per_contract,
        existing["contracts"],
        is_short,
        body.assigned,
    )
    close_data = {
        "status": "assigned" if body.assigned else "closed",
        "closed_at": body.closed_at,
        "close_net_per_contract": body.close_net_per_contract,
        "realized_pnl": pnl,
    }
    updated = db.close_options_trade(trade_id, close_data)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to close trade.")
    return updated


@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: int, db=Depends(get_db)):
    if not db.delete_options_trade(trade_id):
        raise HTTPException(status_code=404, detail="Trade not found.")
    return {"deleted": True, "id": trade_id}
