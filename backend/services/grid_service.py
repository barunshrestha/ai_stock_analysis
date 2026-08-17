"""Build portfolio-style grid rows for a list of symbols."""

from __future__ import annotations

from backend.services import stock_service


def build_grid_rows(
    symbols: list[str], period: str = "1y"
) -> tuple[list[dict], dict[str, str]]:
    """Fetch history, metrics, and sparkline for each symbol."""
    rows: list[dict] = []
    errors: dict[str, str] = {}
    for symbol in symbols:
        try:
            hist = stock_service.get_history(symbol, period)
            if hist is None or hist.empty:
                errors[symbol] = "no history"
                continue
            info = stock_service.get_info(symbol)
            metrics = stock_service.compute_metrics(hist, info)
            spark = hist["Close"].tail(126)
            step = max(1, len(spark) // 60)
            rows.append(
                {
                    "symbol": symbol,
                    "name": info.get("longName") or info.get("shortName") or symbol,
                    "sector": info.get("sector"),
                    "metrics": metrics,
                    "sparkline": [round(float(v), 2) for v in spark.iloc[::step]],
                }
            )
        except Exception as exc:
            errors[symbol] = str(exc)
    return rows, errors
