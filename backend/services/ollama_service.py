"""Ollama integration, ported from the legacy Streamlit app.

Prompts are kept identical to preserve output quality; only the transport
moved from inside Streamlit to a plain service callable by FastAPI routes.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

from backend.config import OLLAMA_ANALYSIS_MODEL, OLLAMA_BASE_URL, OLLAMA_MODEL

ANALYSIS_POINTS = [
    (1, "What the company actually does", "Explain the core business, products/services, customers, and business model in simple terms."),
    (2, "How it makes money", "Break down primary revenue streams, pricing power, and key profit drivers."),
    (3, "Suitability for short-term trading", "Assess volatility, liquidity, catalysts, and whether short-term setup quality is favorable."),
    (4, "Fundamental summary", "Summarize revenue growth trend, profit/loss profile, debt condition, and cash-flow condition."),
    (5, "Recommendation", "Give a clear buy/sell/hold style view for short-term traders with brief reasoning."),
    (6, "Current market sentiment", "Describe sentiment (bullish/bearish/mixed), citing price behavior and recent context."),
    (7, "Sector impact on short-term move", "Explain how sector dynamics can influence near-term price movement."),
    (8, "Main trend", "Explain the current main trend using provided trend context and moving averages."),
    (9, "Resistance and support", "Interpret support/resistance levels and how traders may react around them."),
    (10, "Beginner bad-entry areas", "Highlight common poor entry zones for beginners and why they are risky."),
    (11, "Simple trading plan", "Provide entry rationale, buy area, stop-loss, and realistic target."),
    (12, "Entry logic that makes sense", "Explain a clear trigger/confirmation logic before entering."),
    (13, "Hidden risks", "Identify less obvious risks (event risk, gap risk, liquidity, guidance, macro spillover)."),
    (14, "What can be improved", "Suggest what conditions/data would improve confidence in the setup."),
    (15, "Risk management", "Provide position sizing, max loss, invalidation, and trade management rules."),
]


def call_ollama(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    model: str | None = None,
) -> tuple[str | None, str | None]:
    """Call the Ollama chat API. Returns (content, error_message)."""
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": model or OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            if data.get("error"):
                return None, f"Ollama error: {data.get('error')}"
            content = (data.get("message") or {}).get("content")
            if not content:
                return None, f"Ollama response missing message content: {str(data)[:300]}"
            return content, None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
        except Exception:
            body = str(e)
        return None, f"Ollama HTTP {e.code}: {body}"
    except urllib.error.URLError as e:
        return None, f"Cannot reach Ollama at {OLLAMA_BASE_URL}: {str(e.reason)}"
    except Exception as e:
        return None, f"Ollama request failed: {str(e)}"


def _earnings_trend(earnings_data: pd.DataFrame | None) -> str:
    if earnings_data is None or earnings_data.empty or "Earnings" not in earnings_data.columns:
        return "N/A"
    vals = earnings_data["Earnings"].dropna().values
    if len(vals) >= 3:
        return "Growing" if vals[-1] > vals[0] else "Declining" if vals[-1] < vals[0] else "Flat"
    if len(vals) == 2:
        return "Growing" if vals[-1] > vals[0] else "Declining" if vals[-1] < vals[0] else "Flat"
    return "N/A"


def build_data_context(
    symbol: str,
    info: dict,
    hist_data: pd.DataFrame,
    earnings_data: pd.DataFrame | None,
    trend_context: dict | None,
) -> str:
    company_name = info.get("longName") or symbol

    price_change_1m = 0.0
    price_change_6m = 0.0
    if hist_data is not None and not hist_data.empty:
        close = hist_data["Close"]
        if len(close) > 21:
            price_change_1m = ((close.iloc[-1] - close.iloc[-22]) / close.iloc[-22]) * 100
        if len(close) > 126:
            price_change_6m = ((close.iloc[-1] - close.iloc[-127]) / close.iloc[-127]) * 100

    profit_margin = info.get("profitMargins")
    return f"""
Company: {company_name} ({symbol})
Sector: {info.get('sector', 'N/A')} | Industry: {info.get('industry', 'N/A')}
Business Summary: {(info.get('longBusinessSummary') or 'N/A')[:700]}
Market Cap: {info.get('marketCap', 'N/A')}
P/E Ratio: {info.get('trailingPE', 'N/A')}
Revenue: {info.get('totalRevenue', 'N/A')}
Profit Margin: {f"{profit_margin * 100:.2f}%" if profit_margin is not None else 'N/A'}
Debt-to-Equity: {info.get('debtToEquity', 'N/A')}
Current Ratio: {info.get('currentRatio', 'N/A')}
Free Cash Flow: {info.get('freeCashflow', 'N/A')}
Beta: {info.get('beta', 'N/A')}
Earnings Trend: {_earnings_trend(earnings_data)}
Price Change 1M: {price_change_1m:.2f}%
Price Change 6M: {price_change_6m:.2f}%
Trend Context: {trend_context or 'N/A'}
"""


def generate_summary(
    symbol: str,
    info: dict,
    hist_data: pd.DataFrame,
    earnings_data: pd.DataFrame | None,
) -> tuple[str | None, str | None]:
    """4-section AI stock summary (health, opportunities, risks, recommendation)."""
    company_name = info.get("longName") or symbol
    close = hist_data["Close"]
    current_price = float(close.iloc[-1])
    price_change_1d = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) > 1 else 0
    price_change_1y = ((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100) if len(close) > 0 else 0

    returns = close.pct_change().dropna()
    volatility = float(returns.std() * np.sqrt(252) * 100) if len(returns) > 1 else None

    pe_ratio = info.get("trailingPE")
    market_cap = info.get("marketCap")
    profit_margin = info.get("profitMargins", 0) * 100 if info.get("profitMargins") else None
    roe = info.get("returnOnEquity", 0) * 100 if info.get("returnOnEquity") else None
    dividend_yield = info.get("dividendYield", 0) * 100 if info.get("dividendYield") else 0

    data_context = f"""
Company: {company_name} ({symbol})
Current Price: ${current_price:.2f} (1-day change: {price_change_1d:.2f}%, 1-year change: {price_change_1y:.2f}%)
Market Cap: {f"${market_cap / 1e9:.2f}B" if market_cap else 'N/A'}
P/E Ratio: {pe_ratio if pe_ratio else 'N/A'}
Profit Margin: {f"{profit_margin:.2f}%" if profit_margin else 'N/A'}
ROE: {f"{roe:.2f}%" if roe else 'N/A'}
Debt-to-Equity: {info.get('debtToEquity', 'N/A')}
Current Ratio: {info.get('currentRatio', 'N/A')}
Dividend Yield: {dividend_yield:.2f}%
Beta: {info.get('beta', 'N/A')}
Volatility: {f"{volatility:.2f}%" if volatility is not None else 'N/A'}
Earnings Trend: {_earnings_trend(earnings_data)}
Sector: {info.get('sector', 'N/A')}
Industry: {info.get('industry', 'N/A')}
Business Summary: {(info.get('longBusinessSummary') or 'N/A')[:500]}
"""

    system_prompt = (
        "You are an expert financial analyst with deep knowledge of stock market "
        "analysis, financial metrics, and investment strategies."
    )
    user_prompt = f"""You are a financial analyst providing a comprehensive stock analysis. Analyze the following stock data and provide a detailed summary in exactly 4 sections:

{data_context}

Provide your analysis in the following format:

## 1. Company Health Summary
[Provide a comprehensive assessment of the company's financial health, including profitability, liquidity, solvency, and operational efficiency. Be specific with metrics and data points.]

## 2. Key Opportunities
[Identify and explain the main growth opportunities, competitive advantages, market position, and positive catalysts for this stock. Be specific and data-driven.]

## 3. Major Risks
[Identify and explain the primary risks facing this company, including financial risks, market risks, competitive threats, and operational challenges. Be specific and data-driven.]

## 4. Buy/Sell/Hold Recommendation & Logic
[Provide a clear Buy, Sell, or Hold recommendation with detailed reasoning. Explain the investment thesis, valuation considerations, risk-reward profile, and time horizon. Be specific about what would change your recommendation.]

Format your response using clear markdown sections. Be professional, analytical, and data-driven. Use specific numbers and metrics from the data provided."""

    return call_ollama(system_prompt, user_prompt, temperature=0.7, max_tokens=2000)


def generate_point_analysis(
    symbol: str,
    info: dict,
    hist_data: pd.DataFrame,
    earnings_data: pd.DataFrame | None,
    trend_context: dict | None,
    point_number: int,
) -> tuple[str | None, str | None]:
    """One of the 15 structured analysis points (Ollama Analysis page)."""
    point = next((p for p in ANALYSIS_POINTS if p[0] == point_number), None)
    if point is None:
        return None, f"Unknown analysis point: {point_number}"
    _, point_title, point_instruction = point

    data_context = build_data_context(symbol, info, hist_data, earnings_data, trend_context)
    system_prompt = (
        "You are a practical stock analyst and trading coach. "
        "Write clearly for beginners, but keep analysis data-driven and realistic."
    )
    user_prompt = f"""
Using the stock data below, answer ONLY one point.
Keep the answer concise, actionable, and specific to this company.

{data_context}

Requested point:
{point_number}. {point_title}
Instruction: {point_instruction}

Formatting requirements:
- Use exactly one markdown heading in this format:
  ## {point_number}. {point_title}
- Do not include other numbered sections.
- Add a short "Not financial advice" line at the end.
"""
    return call_ollama(
        system_prompt,
        user_prompt,
        temperature=0.35,
        max_tokens=2400,
        model=OLLAMA_ANALYSIS_MODEL,
    )
