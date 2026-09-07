"""Parse portfolio CSV uploads and bulk-add symbols with Yahoo validation."""

from __future__ import annotations

import csv
import io
import re

from backend.services import stock_service

_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-^=]{1,10}$")
_MAX_SYMBOLS = 500


def parse_portfolio_csv(content: bytes) -> tuple[list[str], str | None]:
    """Return deduplicated symbols from CSV bytes. Error string if parse fails."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], "File must be UTF-8 encoded text."

    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if row and any(cell.strip() for cell in row)]
    if not rows:
        return [], "CSV file is empty."

    header = [cell.strip().lower() for cell in rows[0]]
    symbol_idx = 0
    data_rows = rows

    if "symbol" in header:
        symbol_idx = header.index("symbol")
        data_rows = rows[1:]
    elif "ticker" in header:
        symbol_idx = header.index("ticker")
        data_rows = rows[1:]
    elif header[0] in ("symbol", "ticker"):
        data_rows = rows[1:]

    symbols: list[str] = []
    seen: set[str] = set()
    for row in data_rows:
        if symbol_idx >= len(row):
            continue
        raw = row[symbol_idx].strip()
        if not raw or raw.startswith("#"):
            continue
        sym = raw.upper()
        if sym in seen:
            continue
        seen.add(sym)
        symbols.append(sym)

    if not symbols:
        return [], "No symbols found. Use a 'symbol' column or one ticker per row."
    if len(symbols) > _MAX_SYMBOLS:
        return [], f"Too many symbols ({len(symbols)}). Maximum is {_MAX_SYMBOLS} per upload."
    return symbols, None


def import_portfolio_symbols(symbols: list[str], db, portfolio_id: int | None = None) -> dict:
    """Validate and add symbols; cache company info from Yahoo when possible."""
    pid = portfolio_id or db.ensure_default_portfolio()
    existing = set(db.get_portfolio(pid) or [])
    results: list[dict] = []
    added = skipped = failed = 0

    for sym in symbols:
        if not _SYMBOL_RE.match(sym):
            failed += 1
            results.append({"symbol": sym, "status": "error", "message": "Invalid ticker format"})
            continue
        if sym in existing:
            skipped += 1
            results.append({"symbol": sym, "status": "skipped", "message": "Already in portfolio"})
            continue
        try:
            hist = stock_service.get_history(sym, "1mo")
            if hist is None or hist.empty:
                failed += 1
                results.append({"symbol": sym, "status": "error", "message": "Symbol not found on Yahoo Finance"})
                continue
        except Exception as exc:
            failed += 1
            results.append({"symbol": sym, "status": "error", "message": f"Validation failed: {exc}"})
            continue

        if not db.add_to_portfolio(sym, pid):
            failed += 1
            results.append({"symbol": sym, "status": "error", "message": "Could not save to portfolio"})
            continue

        existing.add(sym)
        added += 1
        info_saved = False
        try:
            info_saved = bool(db.save_stock_info(sym, stock_service.get_info(sym)))
        except Exception:
            pass
        msg = "Added and cached company data" if info_saved else "Added (company data cache skipped)"
        results.append({"symbol": sym, "status": "added", "message": msg})

    return {
        "total": len(symbols),
        "added": added,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }
