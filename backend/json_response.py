"""JSON response that tolerates NaN/Infinity from market data.

yfinance/pandas values leak NaN into payloads (and into cached memos); the stock JSONResponse
raises on them, which surfaces in the browser as a misleading CORS error on a 500.
"""

from __future__ import annotations

import math
from typing import Any

from fastapi.responses import JSONResponse


def to_json_safe(value: Any) -> Any:
    """Recursively replace NaN/Infinity floats with None."""
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, dict):
        return {k: to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_safe(v) for v in value]
    return value


class SafeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return super().render(to_json_safe(content))
