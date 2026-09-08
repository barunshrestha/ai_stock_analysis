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


SYSTEM_PROMPT_VALUATION = """You are an investment-bank-style equity valuation analyst.
Write a clear valuation memo in simple language.

Hard rules:
- Use ONLY the metrics and facts provided in the user message (including any `dcf` block).
- Never invent DCF inputs, peer multiples, or industry averages not in the context.
- If `dcf` is null/missing, say a DCF estimate is unavailable and rely on multiples only.
- This is educational / journaling content, not personalized investment advice.

Cover these sections in order, using markdown headings:
1. P/E and multiples vs peers
2. Discounted cash flow (DCF) estimate
3. Industry / peer average valuation context
4. Undervalued, fair, or overvalued conclusion

After the markdown memo, end with a single fenced JSON block (and nothing after it) in this exact shape:
```json
{
  "verdict": "undervalued" | "fair" | "overvalued",
  "confidence": "low" | "medium" | "high",
  "pe_vs_peers": "cheap" | "inline" | "expensive" | "unknown",
  "summary": "one short sentence"
}
```
"""

_VALUATION_VERDICTS = frozenset({"undervalued", "fair", "overvalued"})
_PE_VS_PEERS = frozenset({"cheap", "inline", "expensive", "unknown"})


def parse_valuation_response(raw: str) -> tuple[str, dict | None]:
    """Split valuation markdown from trailing JSON; normalize verdict enums."""
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
                structured = _normalize_valuation_structured(parsed)
        except json.JSONDecodeError:
            structured = None
        markdown = (raw[: last.start()] + raw[last.end() :]).strip()

    return markdown, structured


def _normalize_valuation_structured(data: dict[str, Any]) -> dict:
    confidence = str(data.get("confidence") or "medium").lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "medium"
    verdict = str(data.get("verdict") or "fair").lower().strip()
    if verdict not in _VALUATION_VERDICTS:
        verdict = "fair"
    pe_vs = str(data.get("pe_vs_peers") or "unknown").lower().strip()
    if pe_vs not in _PE_VS_PEERS:
        pe_vs = "unknown"
    return {
        "verdict": verdict,
        "confidence": confidence,
        "pe_vs_peers": pe_vs,
        "summary": str(data.get("summary") or "").strip() or None,
    }


def generate_valuation_memo(metrics: dict) -> tuple[str | None, dict | None, str | None]:
    """Ground Gemini on metrics (+ optional dcf) for Issue #9. Returns (markdown, structured, error)."""
    symbol = (metrics.get("identity") or {}).get("symbol") or "UNKNOWN"
    user_prompt = (
        f"Perform a valuation analysis of {symbol} using ONLY this structured context JSON.\n\n"
        f"```json\n{json.dumps(metrics, default=str, indent=2)}\n```\n\n"
        "Produce the valuation memo and trailing JSON verdict as instructed."
    )
    content, error = call_gemini(SYSTEM_PROMPT_VALUATION, user_prompt)
    if error:
        return None, None, error
    markdown, structured = parse_valuation_response(content or "")
    if not markdown:
        return None, None, "Gemini returned no usable valuation memo."
    return markdown, structured, None


SYSTEM_PROMPT_RISK = """You are a senior equity risk analyst.
Write a clear investment-risk assessment in simple language with professional insights.

Hard rules:
- Use ONLY the metrics and facts provided in the user message.
- Never invent regulatory events, lawsuits, or debt figures not supported by the context.
- If data is missing, say so and discuss the risk qualitatively — do not guess numbers.
- Rank risks from most dangerous to least dangerous.
- This is educational / journaling content, not personalized investment advice.

Cover these sections in order, using markdown headings:
1. Economic risks
2. Industry disruption
3. Competition
4. Regulatory threats
5. Debt or financial risks
6. Ranked risk summary (most → least dangerous)

After the markdown memo, end with a single fenced JSON block (and nothing after it) in this exact shape:
```json
{
  "overall_risk": "low" | "medium" | "high",
  "confidence": "low" | "medium" | "high",
  "ranked_risks": [
    { "rank": 1, "category": "economic|disruption|competition|regulatory|financial|other", "title": "...", "severity": "low|medium|high" }
  ],
  "summary": "one short sentence"
}
```
Include up to 5 ranked_risks, ordered most → least dangerous.
"""

_RISK_LEVELS = frozenset({"low", "medium", "high"})
_RISK_CATEGORIES = frozenset({"economic", "disruption", "competition", "regulatory", "financial", "other"})
_DEFAULT_RISK_CATEGORIES = ("economic", "disruption", "competition", "regulatory", "financial")


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
    raw = str(value or "other").lower().strip()
    return raw if raw in _RISK_CATEGORIES else "other"


def _normalize_ranked_risks(raw_list: Any) -> list[dict]:
    items: list[dict] = []
    if isinstance(raw_list, list):
        for entry in raw_list:
            if not isinstance(entry, dict):
                continue
            try:
                rank = int(entry.get("rank") or 0)
            except (TypeError, ValueError):
                rank = 0
            title = str(entry.get("title") or "").strip() or "Unspecified risk"
            items.append(
                {
                    "rank": rank,
                    "category": _normalize_risk_category(entry.get("category")),
                    "title": title,
                    "severity": _normalize_risk_level(entry.get("severity"), "medium"),
                }
            )
    items.sort(key=lambda x: (x["rank"] if x["rank"] > 0 else 999, x["title"]))
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
    # re-number 1..n and cap at 5
    out = []
    for i, item in enumerate(items[:5], start=1):
        out.append({**item, "rank": i})
    # pad to 5 with defaults if short
    used = {x["category"] for x in out}
    for category in _DEFAULT_RISK_CATEGORIES:
        if len(out) >= 5:
            break
        if category not in used:
            out.append(
                {
                    "rank": len(out) + 1,
                    "category": category,
                    "title": f"{category.replace('_', ' ').title()} risk",
                    "severity": "medium",
                }
            )
            used.add(category)
    return out[:5]


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


SYSTEM_PROMPT_GROWTH = """You are a senior growth equity analyst.
Write a clear growth-potential assessment in simple language.

Hard rules:
- Use ONLY the metrics and facts provided in the user message.
- Never invent TAM/SAM/market-size figures. If unavailable, say so and reason from growth rates and industry labels only.
- This is educational / journaling content, not personalized investment advice.

Cover these sections in order, using markdown headings:
1. Market size context
2. Industry growth rate
3. Expansion opportunities
4. New products
5. AI or technology advantages
6. 5–10 year growth outlook

After the markdown memo, end with a single fenced JSON block (and nothing after it) in this exact shape:
```json
{
  "outlook_band": "low" | "moderate" | "high",
  "confidence": "low" | "medium" | "high",
  "primary_driver": "short phrase",
  "five_year_summary": "one short sentence",
  "ten_year_summary": "one short sentence"
}
```
"""

_OUTLOOK_BANDS = frozenset({"low", "moderate", "high"})


def parse_growth_response(raw: str) -> tuple[str, dict | None]:
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
                structured = _normalize_growth_structured(parsed)
        except json.JSONDecodeError:
            structured = None
        markdown = (raw[: last.start()] + raw[last.end() :]).strip()
    return markdown, structured


def _normalize_growth_structured(data: dict[str, Any]) -> dict:
    confidence = str(data.get("confidence") or "medium").lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "medium"
    band = str(data.get("outlook_band") or "moderate").lower().strip()
    if band not in _OUTLOOK_BANDS:
        band = "moderate"
    return {
        "outlook_band": band,
        "confidence": confidence,
        "primary_driver": str(data.get("primary_driver") or "").strip() or None,
        "five_year_summary": str(data.get("five_year_summary") or "").strip() or None,
        "ten_year_summary": str(data.get("ten_year_summary") or "").strip() or None,
    }


def generate_growth_memo(metrics: dict) -> tuple[str | None, dict | None, str | None]:
    symbol = (metrics.get("identity") or {}).get("symbol") or "UNKNOWN"
    user_prompt = (
        f"Analyze the future growth potential of {symbol} using ONLY this structured context JSON.\n\n"
        f"```json\n{json.dumps(metrics, default=str, indent=2)}\n```\n\n"
        "Produce the growth memo and trailing JSON outlook as instructed."
    )
    content, error = call_gemini(SYSTEM_PROMPT_GROWTH, user_prompt)
    if error:
        return None, None, error
    markdown, structured = parse_growth_response(content or "")
    if not markdown:
        return None, None, "Gemini returned no usable growth memo."
    return markdown, structured, None


SYSTEM_PROMPT_INSTITUTIONAL = """You are a hedge fund portfolio manager writing an educational journal note.
Evaluate whether the stock is a good long-term institutional holding.

Hard rules:
- Use ONLY the metrics and facts provided in the user message.
- Never invent catalysts, filings, or ownership figures not in the context.
- This is educational / journaling content, not personalized investment advice.

Cover these sections in order, using markdown headings:
1. Why institutions might buy
2. Why they might avoid
3. Key catalysts
4. Investment thesis

After the markdown memo, end with a single fenced JSON block (and nothing after it) in this exact shape:
```json
{
  "stance": "attractive" | "mixed" | "unattractive",
  "confidence": "low" | "medium" | "high",
  "buy_reasons": ["..."],
  "avoid_reasons": ["..."],
  "catalysts": ["..."],
  "thesis_one_liner": "..."
}
```
"""

_INST_STANCES = frozenset({"attractive", "mixed", "unattractive"})


def parse_institutional_response(raw: str) -> tuple[str, dict | None]:
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
                structured = _normalize_institutional_structured(parsed)
        except json.JSONDecodeError:
            structured = None
        markdown = (raw[: last.start()] + raw[last.end() :]).strip()
    return markdown, structured


def _string_list(value: Any, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        s = str(item or "").strip()
        if s:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def _normalize_institutional_structured(data: dict[str, Any]) -> dict:
    confidence = str(data.get("confidence") or "medium").lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "medium"
    stance = str(data.get("stance") or "mixed").lower().strip()
    if stance not in _INST_STANCES:
        stance = "mixed"
    return {
        "stance": stance,
        "confidence": confidence,
        "buy_reasons": _string_list(data.get("buy_reasons")),
        "avoid_reasons": _string_list(data.get("avoid_reasons")),
        "catalysts": _string_list(data.get("catalysts")),
        "thesis_one_liner": str(data.get("thesis_one_liner") or "").strip() or None,
    }


def generate_institutional_memo(metrics: dict) -> tuple[str | None, dict | None, str | None]:
    symbol = (metrics.get("identity") or {}).get("symbol") or "UNKNOWN"
    user_prompt = (
        f"Act like a hedge fund PM and evaluate whether {symbol} is a good long-term investment "
        f"using ONLY this structured context JSON.\n\n"
        f"```json\n{json.dumps(metrics, default=str, indent=2)}\n```\n\n"
        "Produce the institutional memo and trailing JSON as instructed."
    )
    content, error = call_gemini(SYSTEM_PROMPT_INSTITUTIONAL, user_prompt)
    if error:
        return None, None, error
    markdown, structured = parse_institutional_response(content or "")
    if not markdown:
        return None, None, "Gemini returned no usable institutional memo."
    return markdown, structured, None


SYSTEM_PROMPT_DEBATE = """You are moderating a debate between two equity analysts.
Write a clear bull vs bear debate in simple language.

Hard rules:
- Use ONLY the metrics and facts provided in the user message.
- Both sides must be data-backed from the context; never invent catalysts.
- This is educational / journaling content, not personalized investment advice.

Cover these sections in order, using markdown headings:
1. Bull case
2. Bear case
3. Balanced conclusion

After the markdown memo, end with a single fenced JSON block (and nothing after it) in this exact shape:
```json
{
  "bull_score": 1-10,
  "bear_score": 1-10,
  "winner": "bull" | "bear" | "draw",
  "confidence": "low" | "medium" | "high",
  "conclusion_one_liner": "..."
}
```
"""

_DEBATE_WINNERS = frozenset({"bull", "bear", "draw"})


def parse_debate_response(raw: str) -> tuple[str, dict | None]:
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
                structured = _normalize_debate_structured(parsed)
        except json.JSONDecodeError:
            structured = None
        markdown = (raw[: last.start()] + raw[last.end() :]).strip()
    return markdown, structured


def _clamp_score(value: Any, default: int = 5) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        score = default
    return max(1, min(10, score))


def _normalize_debate_structured(data: dict[str, Any]) -> dict:
    confidence = str(data.get("confidence") or "medium").lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "medium"
    winner = str(data.get("winner") or "draw").lower().strip()
    if winner not in _DEBATE_WINNERS:
        winner = "draw"
    return {
        "bull_score": _clamp_score(data.get("bull_score")),
        "bear_score": _clamp_score(data.get("bear_score")),
        "winner": winner,
        "confidence": confidence,
        "conclusion_one_liner": str(data.get("conclusion_one_liner") or "").strip() or None,
    }


def generate_debate_memo(metrics: dict) -> tuple[str | None, dict | None, str | None]:
    symbol = (metrics.get("identity") or {}).get("symbol") or "UNKNOWN"
    user_prompt = (
        f"Create a bull vs bear debate about {symbol} using ONLY this structured context JSON.\n\n"
        f"```json\n{json.dumps(metrics, default=str, indent=2)}\n```\n\n"
        "Produce the debate memo and trailing JSON scores as instructed."
    )
    content, error = call_gemini(SYSTEM_PROMPT_DEBATE, user_prompt)
    if error:
        return None, None, error
    markdown, structured = parse_debate_response(content or "")
    if not markdown:
        return None, None, "Gemini returned no usable debate memo."
    return markdown, structured, None


SYSTEM_PROMPT_EARNINGS = """You are an equity analyst explaining the latest earnings report.
Write a clear earnings breakdown in simple language.

Hard rules:
- Use ONLY the metrics and facts provided (including any `earnings_context` block).
- Never invent beats, misses, guidance, or market reactions not in the context.
- If expectations or reaction data are missing, say so explicitly.
- This is educational / journaling content, not personalized investment advice.

Cover these sections in order, using markdown headings:
1. Revenue vs expectations
2. Profit vs expectations
3. Key metrics investors watch
4. Management guidance
5. Market reaction

After the markdown memo, end with a single fenced JSON block (and nothing after it) in this exact shape:
```json
{
  "surprise": "beat" | "miss" | "inline" | "unknown",
  "confidence": "low" | "medium" | "high",
  "summary": "one short sentence"
}
```
"""

_EARNINGS_SURPRISES = frozenset({"beat", "miss", "inline", "unknown"})


def parse_earnings_response(raw: str) -> tuple[str, dict | None]:
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
                structured = _normalize_earnings_structured(parsed)
        except json.JSONDecodeError:
            structured = None
        markdown = (raw[: last.start()] + raw[last.end() :]).strip()
    return markdown, structured


def _normalize_earnings_structured(data: dict[str, Any]) -> dict:
    confidence = str(data.get("confidence") or "medium").lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "medium"
    surprise = str(data.get("surprise") or "unknown").lower().strip()
    if surprise not in _EARNINGS_SURPRISES:
        surprise = "unknown"
    return {
        "surprise": surprise,
        "confidence": confidence,
        "summary": str(data.get("summary") or "").strip() or None,
    }


def generate_earnings_memo(metrics: dict) -> tuple[str | None, dict | None, str | None]:
    symbol = (metrics.get("identity") or {}).get("symbol") or "UNKNOWN"
    user_prompt = (
        f"Explain the latest earnings report of {symbol} using ONLY this structured context JSON.\n\n"
        f"```json\n{json.dumps(metrics, default=str, indent=2)}\n```\n\n"
        "Produce the earnings breakdown and trailing JSON as instructed."
    )
    content, error = call_gemini(SYSTEM_PROMPT_EARNINGS, user_prompt)
    if error:
        return None, None, error
    markdown, structured = parse_earnings_response(content or "")
    if not markdown:
        return None, None, "Gemini returned no usable earnings memo."
    return markdown, structured, None


SYSTEM_PROMPT_VERDICT = """You are writing an educational stock journal verdict — NOT personalized financial advice.
Evaluate whether the ticker looks like a Buy, Hold, or Avoid for journaling purposes only.

Hard rules:
- Use ONLY the metrics and facts provided in the user message.
- Never invent catalysts or risks not supported by the context.
- Always remind the reader this is educational journaling, not advice.
- Verdict must be Buy, Hold, or Avoid (use Avoid instead of Sell).

Cover these sections in order, using markdown headings:
1. Short-term outlook (1 year)
2. Long-term outlook (5+ years)
3. Key catalysts
4. Major risks
5. Final verdict: Buy / Hold / Avoid with rationale

After the markdown memo, end with a single fenced JSON block (and nothing after it) in this exact shape:
```json
{
  "verdict": "buy" | "hold" | "avoid",
  "confidence": "low" | "medium" | "high",
  "horizon_fit": "short" | "long" | "both" | "neither",
  "summary": "one short sentence"
}
```
"""

_VERDICTS = frozenset({"buy", "hold", "avoid"})
_HORIZONS = frozenset({"short", "long", "both", "neither"})


def parse_verdict_response(raw: str) -> tuple[str, dict | None]:
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
                structured = _normalize_verdict_structured(parsed)
        except json.JSONDecodeError:
            structured = None
        markdown = (raw[: last.start()] + raw[last.end() :]).strip()
    return markdown, structured


def _normalize_verdict_structured(data: dict[str, Any]) -> dict:
    confidence = str(data.get("confidence") or "medium").lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "medium"
    verdict = str(data.get("verdict") or "hold").lower().strip()
    if verdict == "sell":
        verdict = "avoid"
    if verdict not in _VERDICTS:
        verdict = "hold"
    horizon = str(data.get("horizon_fit") or "both").lower().strip()
    if horizon not in _HORIZONS:
        horizon = "both"
    return {
        "verdict": verdict,
        "confidence": confidence,
        "horizon_fit": horizon,
        "summary": str(data.get("summary") or "").strip() or None,
    }


def generate_verdict_memo(metrics: dict) -> tuple[str | None, dict | None, str | None]:
    symbol = (metrics.get("identity") or {}).get("symbol") or "UNKNOWN"
    user_prompt = (
        f"Evaluate whether {symbol} is a good investment today for an educational journal "
        f"using ONLY this structured context JSON.\n\n"
        f"```json\n{json.dumps(metrics, default=str, indent=2)}\n```\n\n"
        "Produce the verdict memo and trailing JSON as instructed."
    )
    content, error = call_gemini(SYSTEM_PROMPT_VERDICT, user_prompt)
    if error:
        return None, None, error
    markdown, structured = parse_verdict_response(content or "")
    if not markdown:
        return None, None, "Gemini returned no usable verdict memo."
    return markdown, structured, None
