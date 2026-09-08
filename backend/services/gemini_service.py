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


SYSTEM_PROMPT_MOAT = """You are a senior equity strategist specializing in competitive moats.
Write a clear moat assessment in simple language with professional insights.

Hard rules:
- Use ONLY the metrics and facts provided in the user message.
- Never invent patents, brand rankings, market shares, or competitor facts not supported by the context.
- If peer comps are missing, compare qualitatively using sector/industry labels and state that competitor data is unavailable.
- This is educational / journaling content, not personalized investment advice.

Cover these sections in order, using markdown headings:
1. Brand strength
2. Network effects
3. Switching costs
4. Cost advantage
5. Patents or proprietary tech
6. Competitor comparison
7. Overall moat rating (1–10) with rationale

After the markdown memo, end with a single fenced JSON block (and nothing after it) in this exact shape:
```json
{
  "moat_score": 1-10,
  "confidence": "low" | "medium" | "high",
  "strongest_pillar": "brand" | "network" | "switching" | "cost" | "ip" | "none",
  "summary": "one short sentence"
}
```
"""

_MOAT_PILLARS = frozenset({"brand", "network", "switching", "cost", "ip", "none"})


def parse_moat_response(raw: str) -> tuple[str, dict | None]:
    """Split moat markdown from trailing JSON; clamp moat_score to 1–10."""
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
                structured = _normalize_moat_structured(parsed)
        except json.JSONDecodeError:
            structured = None
        markdown = (raw[: last.start()] + raw[last.end() :]).strip()

    return markdown, structured


def _normalize_moat_structured(data: dict[str, Any]) -> dict:
    confidence = str(data.get("confidence") or "medium").lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "medium"
    pillar = str(data.get("strongest_pillar") or "none").lower().strip()
    if pillar not in _MOAT_PILLARS:
        pillar = "none"
    score_raw = data.get("moat_score")
    try:
        score = int(round(float(score_raw)))
    except (TypeError, ValueError):
        score = 5
    score = max(1, min(10, score))
    return {
        "moat_score": score,
        "confidence": confidence,
        "strongest_pillar": pillar,
        "summary": str(data.get("summary") or "").strip() or None,
    }


def generate_moat_memo(metrics: dict) -> tuple[str | None, dict | None, str | None]:
    """Ground Gemini on metrics for Issue #8 moat analysis. Returns (markdown, structured, error)."""
    symbol = (metrics.get("identity") or {}).get("symbol") or "UNKNOWN"
    user_prompt = (
        f"Evaluate the competitive moat of {symbol} using ONLY this structured context JSON.\n\n"
        f"```json\n{json.dumps(metrics, default=str, indent=2)}\n```\n\n"
        "Produce the moat memo and trailing JSON score as instructed."
    )
    content, error = call_gemini(SYSTEM_PROMPT_MOAT, user_prompt)
    if error:
        return None, None, error
    markdown, structured = parse_moat_response(content or "")
    if not markdown:
        return None, None, "Gemini returned no usable moat memo."
    return markdown, structured, None


SYSTEM_PROMPT_RISK = """You are a senior equity risk analyst.
Write a clear investment-risk assessment in simple language with professional insights.

Hard rules:
- Use ONLY the metrics and facts provided in the user message.
- Never invent macro events, regulatory actions, debt figures, or competitor threats not supported by the context.
- If data is missing, say so and discuss the risk qualitatively — do not guess numbers.
- Rank risks from most dangerous to least dangerous.
- This is educational / journaling content, not personalized investment advice.

Cover these sections in order, using markdown headings:
1. Economic risks
2. Industry disruption
3. Competition
4. Regulatory threats
5. Debt or financial risks

After the markdown memo, end with a single fenced JSON block (and nothing after it) in this exact shape:
```json
{
  "overall_risk": "low" | "medium" | "high",
  "confidence": "low" | "medium" | "high",
  "ranked_risks": [
    {
      "rank": 1,
      "category": "economic" | "disruption" | "competition" | "regulatory" | "financial" | "other",
      "title": "short label",
      "severity": "low" | "medium" | "high"
    }
  ],
  "summary": "one short sentence"
}
```
Include up to 5 ranked_risks, ordered most → least dangerous.
"""

_RISK_LEVELS = frozenset({"low", "medium", "high"})
_RISK_CATEGORIES = frozenset(
    {"economic", "disruption", "competition", "regulatory", "financial", "other"}
)
_DEFAULT_RISK_CATEGORIES = (
    "economic",
    "disruption",
    "competition",
    "regulatory",
    "financial",
)
_CATEGORY_ALIASES = {
    "economy": "economic",
    "macro": "economic",
    "industry": "disruption",
    "industry_disruption": "disruption",
    "industry disruption": "disruption",
    "tech": "disruption",
    "competitive": "competition",
    "competitors": "competition",
    "regulation": "regulatory",
    "legal": "regulatory",
    "debt": "financial",
    "leverage": "financial",
    "balance_sheet": "financial",
    "balance sheet": "financial",
    "finance": "financial",
}


def parse_risk_response(raw: str) -> tuple[str, dict | None]:
    """Split risk markdown from trailing JSON; normalize enums and rank list."""
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
                structured = _normalize_risk_structured(parsed)
        except json.JSONDecodeError:
            structured = None
        markdown = (raw[: last.start()] + raw[last.end() :]).strip()

    return markdown, structured


def _normalize_risk_level(value: Any, default: str = "medium") -> str:
    level = str(value or default).lower().strip()
    return level if level in _RISK_LEVELS else default


def _normalize_risk_category(value: Any) -> str:
    raw = str(value or "").lower().strip().replace("-", "_")
    if raw in _RISK_CATEGORIES:
        return raw
    aliased = _CATEGORY_ALIASES.get(raw) or _CATEGORY_ALIASES.get(raw.replace("_", " "))
    if aliased:
        return aliased
    return "other"


def _normalize_ranked_risks(raw_list: Any) -> list[dict]:
    items: list[dict] = []
    if isinstance(raw_list, list):
        for idx, entry in enumerate(raw_list):
            if not isinstance(entry, dict):
                continue
            try:
                rank = int(entry.get("rank", idx + 1))
            except (TypeError, ValueError):
                rank = idx + 1
            title = str(entry.get("title") or "").strip() or "Unspecified risk"
            items.append(
                {
                    "rank": rank,
                    "category": _normalize_risk_category(entry.get("category")),
                    "title": title,
                    "severity": _normalize_risk_level(entry.get("severity"), "medium"),
                }
            )

    items.sort(key=lambda r: (r["rank"], r["title"]))
    items = items[:5]

    present = {r["category"] for r in items}
    for category in _DEFAULT_RISK_CATEGORIES:
        if len(items) >= 5:
            break
        if category not in present:
            items.append(
                {
                    "rank": len(items) + 1,
                    "category": category,
                    "title": f"{category.replace('_', ' ').title()} risk",
                    "severity": "medium",
                }
            )
            present.add(category)

    if not items:
        for i, category in enumerate(_DEFAULT_RISK_CATEGORIES, start=1):
            items.append(
                {
                    "rank": i,
                    "category": category,
                    "title": f"{category.replace('_', ' ').title()} risk",
                    "severity": "medium",
                }
            )

    for i, item in enumerate(items, start=1):
        item["rank"] = i
    return items


def _normalize_risk_structured(data: dict[str, Any]) -> dict:
    return {
        "overall_risk": _normalize_risk_level(data.get("overall_risk"), "medium"),
        "confidence": _normalize_risk_level(data.get("confidence"), "medium"),
        "ranked_risks": _normalize_ranked_risks(data.get("ranked_risks")),
        "summary": str(data.get("summary") or "").strip() or None,
    }


def generate_risk_memo(metrics: dict) -> tuple[str | None, dict | None, str | None]:
    """Ground Gemini on metrics for Issue #10 risk analysis. Returns (markdown, structured, error)."""
    symbol = (metrics.get("identity") or {}).get("symbol") or "UNKNOWN"
    user_prompt = (
        f"Identify the biggest risks of investing in {symbol} using ONLY this structured context JSON.\n\n"
        f"```json\n{json.dumps(metrics, default=str, indent=2)}\n```\n\n"
        "Produce the risk memo and trailing JSON ranking as instructed."
    )
    content, error = call_gemini(SYSTEM_PROMPT_RISK, user_prompt)
    if error:
        return None, None, error
    markdown, structured = parse_risk_response(content or "")
    if not markdown:
        return None, None, "Gemini returned no usable risk memo."
    return markdown, structured, None
