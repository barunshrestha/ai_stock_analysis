"""Gemini client for Wall Street–style equity research memos (Issue #6)."""

from __future__ import annotations

import json
import re
from typing import Any

from backend.config import GEMINI_API_KEY, GEMINI_MODEL

DISCLAIMER = "Not financial advice — for journaling and education only."

SYSTEM_PROMPT = """You are a senior Wall Street equity research analyst.
Write a clear research memo in simple language with professional insights.

Hard rules:
- Use ONLY the metrics and facts provided in the user message.
- Never invent numbers, peer valuations, or catalysts that are not in the context.
- If a field is null/missing, say the data is not available — do not guess.
- If peers are missing, discuss valuation using the provided multiples only and note that competitor comps are unavailable.
- This is educational / journaling content, not personalized investment advice.

Cover these sections in order, using markdown headings:
1. Business model and revenue streams
2. Competitive advantages (moat)
3. Industry trends
4. Financial health (revenue growth, margins, debt)
5. Key risks
6. Valuation vs competitors
7. Bull, bear, and base case scenarios
8. 12–24 month outlook

After the markdown memo, end with a single fenced JSON block (and nothing after it) in this exact shape:
```json
{
  "overall_stance": "bullish" | "neutral" | "bearish",
  "confidence": "low" | "medium" | "high",
  "base_case_summary": "one short sentence",
  "bull_case_summary": "one short sentence",
  "bear_case_summary": "one short sentence"
}
```
"""

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def call_gemini(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.4,
    max_output_tokens: int = 4096,
    model: str | None = None,
) -> tuple[str | None, str | None]:
    """Call Gemini. Returns (content, error_message)."""
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY is not configured. Add it to your .env and restart the API."

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None, "google-genai is not installed. Run: pip install google-genai"

    model_name = model or GEMINI_MODEL
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            return None, f"Gemini returned empty content for model {model_name}."
        return text, None
    except Exception as exc:
        return None, f"Gemini request failed: {exc}"


def parse_memo_response(raw: str) -> tuple[str, dict | None]:
    """Split markdown body from trailing JSON fence. structured is None if parse fails."""
    if not raw or not raw.strip():
        return "", None

    matches = list(_JSON_FENCE_RE.finditer(raw))
    structured: dict | None = None
    markdown = raw.strip()

    if matches:
        last = matches[-1]
        try:
            parsed = json.loads(last.group(1))
            if isinstance(parsed, dict):
                structured = _normalize_structured(parsed)
        except json.JSONDecodeError:
            structured = None
        markdown = (raw[: last.start()] + raw[last.end() :]).strip()

    return markdown, structured


def _normalize_structured(data: dict[str, Any]) -> dict:
    stance = str(data.get("overall_stance") or "neutral").lower()
    if stance not in ("bullish", "neutral", "bearish"):
        stance = "neutral"
    confidence = str(data.get("confidence") or "medium").lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "medium"
    return {
        "overall_stance": stance,
        "confidence": confidence,
        "base_case_summary": str(data.get("base_case_summary") or "").strip() or None,
        "bull_case_summary": str(data.get("bull_case_summary") or "").strip() or None,
        "bear_case_summary": str(data.get("bear_case_summary") or "").strip() or None,
    }


def generate_wall_street_memo(metrics: dict) -> tuple[str | None, dict | None, str | None]:
    """
    Ground Gemini on metrics pack.
    Returns (markdown, structured, error).
    """
    symbol = (metrics.get("identity") or {}).get("symbol") or "UNKNOWN"
    user_prompt = (
        f"Analyze {symbol} using ONLY this structured market context JSON.\n\n"
        f"```json\n{json.dumps(metrics, default=str, indent=2)}\n```\n\n"
        "Produce the research memo and trailing JSON verdict as instructed."
    )
    content, error = call_gemini(SYSTEM_PROMPT, user_prompt)
    if error:
        return None, None, error
    markdown, structured = parse_memo_response(content or "")
    if not markdown:
        return None, None, "Gemini returned no usable markdown memo."
    return markdown, structured, None
