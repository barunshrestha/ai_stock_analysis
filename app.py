import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np
import time
import os
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from database import DatabaseManager
from formatting_utils import (
    format_number, format_percentage, format_volume, 
    format_price, format_ratio, format_change_percentage,
    format_financial_statement_value
)
from scanner import scan_stock, fetch_stock_data, calculate_technical_indicators, calculate_sma

# Load environment variables from .env file
load_dotenv()

# Ollama (local LLM) configuration - no API key required
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_ANALYSIS_MODEL = os.getenv("OLLAMA_ANALYSIS_MODEL", "gemma3:4b")
AI_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def call_ollama(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    model: str | None = None
) -> str | None:
    """Call Ollama chat API (e.g. Gemma3:4b). Returns assistant content or None on failure."""
    content, _ = call_ollama_with_error(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model
    )
    return content


def call_ollama_with_error(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    model: str | None = None
) -> tuple[str | None, str | None]:
    """Call Ollama chat API and return (content, error_message)."""
    import urllib.request
    import urllib.error
    import json
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


@st.cache_data(ttl=60)
def fetch_ollama_models() -> list[str]:
    """Fetch list of available Ollama model names from the API. Cached for 60s."""
    import urllib.request
    import urllib.error
    import json
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("models") or []
            names = [m.get("name") for m in models if m.get("name")]
            return names if names else [OLLAMA_MODEL]
    except Exception:
        return [OLLAMA_MODEL]


def get_current_ollama_model() -> str:
    """Return the user-selected LLM model from session state, or env default."""
    return st.session_state.get("selected_llm_model") or OLLAMA_MODEL


def create_grok_trend_chart(hist_data, symbol):
    """Create trend chart with support/resistance and beginner bad-entry zone."""
    if hist_data is None or hist_data.empty:
        return None, None

    chart_data = hist_data.copy().tail(min(len(hist_data), 180))
    close = chart_data['Close']
    low = chart_data['Low']
    high = chart_data['High']

    ma_20 = close.rolling(window=20).mean() if len(chart_data) >= 20 else None
    ma_50 = close.rolling(window=50).mean() if len(chart_data) >= 50 else None

    # Quantile-based levels are more stable than single-point min/max.
    support = float(low.quantile(0.15))
    resistance = float(high.quantile(0.85))
    latest_price = float(close.iloc[-1])

    trend_label = "Sideways"
    if ma_50 is not None and not ma_50.dropna().empty:
        ma_50_series = ma_50.dropna()
        if len(ma_50_series) >= 10:
            slope = float(ma_50_series.iloc[-1] - ma_50_series.iloc[-10])
        else:
            slope = float(ma_50_series.iloc[-1] - ma_50_series.iloc[0])
        if latest_price > ma_50_series.iloc[-1] and slope > 0:
            trend_label = "Uptrend"
        elif latest_price < ma_50_series.iloc[-1] and slope < 0:
            trend_label = "Downtrend"

    price_range = max(resistance - support, 0.01)
    if trend_label == "Uptrend":
        bad_entry_low = resistance - (0.15 * price_range)
        bad_entry_high = resistance + (0.05 * price_range)
        bad_entry_label = "Beginner bad-entry zone: chasing near resistance"
    elif trend_label == "Downtrend":
        bad_entry_low = support - (0.05 * price_range)
        bad_entry_high = support + (0.15 * price_range)
        bad_entry_label = "Beginner bad-entry zone: catching falling knife"
    else:
        midpoint = (support + resistance) / 2
        bad_entry_low = midpoint - (0.08 * price_range)
        bad_entry_high = midpoint + (0.08 * price_range)
        bad_entry_label = "Beginner bad-entry zone: random entries in noisy range"

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=chart_data.index,
        open=chart_data['Open'],
        high=chart_data['High'],
        low=chart_data['Low'],
        close=chart_data['Close'],
        name=f"{symbol} Price"
    ))

    if ma_20 is not None:
        fig.add_trace(go.Scatter(
            x=chart_data.index,
            y=ma_20,
            mode='lines',
            name='20-Day MA',
            line=dict(color='orange', width=1.5)
        ))

    if ma_50 is not None:
        fig.add_trace(go.Scatter(
            x=chart_data.index,
            y=ma_50,
            mode='lines',
            name='50-Day MA',
            line=dict(color='red', width=1.5)
        ))

    fig.add_hline(y=support, line_dash="dot", line_color="green", annotation_text=f"Support: {support:.2f}")
    fig.add_hline(y=resistance, line_dash="dot", line_color="purple", annotation_text=f"Resistance: {resistance:.2f}")
    fig.add_hrect(
        y0=bad_entry_low, y1=bad_entry_high,
        fillcolor="rgba(255, 0, 0, 0.12)", line_width=0,
        annotation_text=bad_entry_label, annotation_position="top left"
    )

    fig.update_layout(
        title=f"{symbol} Main Trend + Support/Resistance",
        xaxis_title="Date",
        yaxis_title="Price ($)",
        template="plotly_white",
        height=550,
        showlegend=True
    )

    trend_context = {
        "trend_label": trend_label,
        "support": support,
        "resistance": resistance,
        "latest_price": latest_price,
        "bad_entry_zone": f"{bad_entry_low:.2f} - {bad_entry_high:.2f}",
        "bad_entry_label": bad_entry_label
    }
    return fig, trend_context


def build_ollama_analysis_data_context(stock_symbol, company_name, info, hist_data, earnings_data, trend_context):
    """Build compact context block for per-point Ollama analysis prompts."""
    market_cap = info.get('marketCap')
    pe_ratio = info.get('trailingPE')
    revenue = info.get('totalRevenue')
    profit_margin = info.get('profitMargins')
    debt_to_equity = info.get('debtToEquity')
    current_ratio = info.get('currentRatio')
    beta = info.get('beta')
    free_cashflow = info.get('freeCashflow')

    price_change_1m = 0.0
    price_change_6m = 0.0
    if hist_data is not None and not hist_data.empty:
        close = hist_data['Close']
        if len(close) > 21:
            price_change_1m = ((close.iloc[-1] - close.iloc[-22]) / close.iloc[-22]) * 100
        if len(close) > 126:
            price_change_6m = ((close.iloc[-1] - close.iloc[-127]) / close.iloc[-127]) * 100

    earnings_trend = "N/A"
    if earnings_data is not None and not earnings_data.empty and 'Earnings' in earnings_data.columns:
        vals = earnings_data['Earnings'].dropna().values
        if len(vals) >= 3:
            earnings_trend = "Growing" if vals[-1] > vals[0] else "Declining" if vals[-1] < vals[0] else "Flat"

    data_context = f"""
Company: {company_name} ({stock_symbol})
Sector: {info.get('sector', 'N/A')} | Industry: {info.get('industry', 'N/A')}
Business Summary: {info.get('longBusinessSummary', 'N/A')[:700]}
Market Cap: {format_number(market_cap)}
P/E Ratio: {format_ratio(pe_ratio)}
Revenue: {format_number(revenue)}
Profit Margin: {format_percentage((profit_margin or 0) * 100) if profit_margin is not None else 'N/A'}
Debt-to-Equity: {format_ratio(debt_to_equity)}
Current Ratio: {format_ratio(current_ratio)}
Free Cash Flow: {format_number(free_cashflow)}
Beta: {format_ratio(beta)}
Earnings Trend: {earnings_trend}
Price Change 1M: {price_change_1m:.2f}%
Price Change 6M: {price_change_6m:.2f}%
Trend Context: {trend_context}
"""
    return data_context


def generate_ollama_point_analysis(stock_symbol, company_name, info, hist_data, earnings_data, trend_context, point_number, point_title, point_instruction):
    """Generate one Ollama answer for a single requested analysis point."""
    data_context = build_ollama_analysis_data_context(
        stock_symbol, company_name, info, hist_data, earnings_data, trend_context
    )

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
    content, ollama_error = call_ollama_with_error(
        system_prompt,
        user_prompt,
        temperature=0.35,
        max_tokens=2400,
        model=get_current_ollama_model()
    )
    if not content:
        if ollama_error:
            return None, ollama_error
        return None, "Ollama returned no content for this request."
    return content, None

# Page configuration
st.set_page_config(
    page_title="Stock Financial Analysis",
    page_icon="📈",
    layout="wide"
)

# Initialize database
@st.cache_resource
def init_database():
    try:
        db_instance = DatabaseManager()
        # Verify that the new portfolio methods exist
        if not hasattr(db_instance, 'add_to_portfolio'):
            st.warning("Database schema outdated. Please restart the application.")
        return db_instance
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None

db = init_database()

# Check for query parameters (for opening stock analysis from portfolio links)
query_params = st.query_params
symbol_from_url = query_params.get("symbol", None)
auto_analyze = query_params.get("analyze", None)

# Navigation
# Initialize page key in session state if not exists
page_key = "nav_page"
if page_key not in st.session_state:
    st.session_state[page_key] = "Stock Analysis"  # Default page

# If symbol is in URL, force page to Stock Analysis
if symbol_from_url:
    # Store symbol in session state for auto-analysis
    if 'url_symbol' not in st.session_state or st.session_state.url_symbol != symbol_from_url:
        st.session_state.url_symbol = symbol_from_url
        st.session_state.auto_analyze_from_url = True
    # Set the page to Stock Analysis when symbol comes from URL
    st.session_state[page_key] = "Stock Analysis"

# Determine page index
page_index = 0
if st.session_state[page_key] == "My Portfolio":
    page_index = 1
elif st.session_state[page_key] == "DCA":
    page_index = 2
elif st.session_state[page_key] == "Ollama Analysis":
    page_index = 3
elif st.session_state[page_key] == "Automation":
    page_index = 4
elif st.session_state[page_key] == "By Industry":
    page_index = 5

page = st.sidebar.radio(
    "Navigation",
    ["Stock Analysis", "My Portfolio", "DCA", "Ollama Analysis", "Automation", "By Industry"],
    index=page_index,
    key=page_key,
    label_visibility="visible"
)

# Title based on selected page
if page == "Stock Analysis":
    page_heading = ("📈 Stock Financial Analysis", "Enter a stock symbol to get comprehensive financial data, interactive charts, and download capabilities.")
elif page == "My Portfolio":
    page_heading = ("💼 My Portfolio", "View and manage your portfolio with comprehensive financial metrics and analysis.")
elif page == "DCA":
    page_heading = ("💰 DCA (Dollar Cost Averaging)", "Add stock symbols to track your dollar cost averaging strategy.")
elif page == "Ollama Analysis":
    page_heading = ("🧠 Ollama Analysis", "Use Ollama LLM for structured stock analysis, trading plan, and risk review.")
elif page == "By Industry":
    page_heading = ("🏭 Stocks by Industry (Admin)", "Add, edit, and delete stock–industry assignments. A stock can belong to multiple industries.")
else:  # Automation
    page_heading = ("🤖 Trading Automation", "Automated technical analysis with AI-powered market sentiment and trade setup generation.")

st.title(page_heading[0])
st.markdown(page_heading[1])

# Initialize session state for selected LLM model (app-wide default until changed)
if "selected_llm_model" not in st.session_state:
    st.session_state.selected_llm_model = OLLAMA_MODEL

# Initialize session state for DCA stocks
if 'dca_stocks' not in st.session_state:
    st.session_state.dca_stocks = []

# Initialize session state for DCA dollar amount
if 'dca_dollar_amount' not in st.session_state:
    st.session_state.dca_dollar_amount = 0.0

# Initialize session state for portfolio
if 'portfolio' not in st.session_state:
    # Try to load portfolio from database
    if db and hasattr(db, 'get_portfolio'):
        try:
            saved_portfolio = db.get_portfolio()
            if saved_portfolio:
                st.session_state.portfolio = saved_portfolio
            else:
                # Default portfolio if none exists in database
                default_portfolio = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META']
                st.session_state.portfolio = default_portfolio
                # Save default portfolio to database
                if hasattr(db, 'save_portfolio'):
                    try:
                        db.save_portfolio(default_portfolio)
                    except:
                        pass  # Fail silently, will warn user later
        except Exception as e:
            # Fallback to default if database operation fails
            st.session_state.portfolio = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META']
    else:
        # Fallback if database is not available
        st.session_state.portfolio = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META']

# Persist Stock Analysis selections across reruns (buttons, status refresh, etc.)
if 'stock_analysis_context' not in st.session_state:
    st.session_state.stock_analysis_context = None
if 'ollama_analysis_context' not in st.session_state:
    st.session_state.ollama_analysis_context = None

# Sidebar for inputs
# Initialize analyze_button to avoid undefined variable errors
analyze_button = False
stock_symbol = None
ollama_button = False
ollama_symbol = None

with st.sidebar:
    # LLM model selector (applies to all AI features app-wide)
    st.subheader("🤖 LLM Model")
    try:
        available_models = fetch_ollama_models()
    except Exception:
        available_models = [OLLAMA_MODEL]
    current_model = get_current_ollama_model()
    if current_model not in available_models:
        available_models = [current_model] + [m for m in available_models if m != current_model]
    selected = st.selectbox(
        "Model",
        options=available_models,
        index=available_models.index(current_model) if current_model in available_models else 0,
        key="llm_model_select",
        help="Selected model is used for all AI analysis across the app until you change it.",
    )
    st.session_state.selected_llm_model = selected
    st.caption(f"Using: **{get_current_ollama_model()}**")
    st.markdown("---")

    if page == "Stock Analysis":
        st.header("Stock Analysis Settings")
    elif page == "Ollama Analysis":
        st.header("Ollama Analysis Settings")
    elif page == "My Portfolio":
        st.header("Portfolio Settings")
    elif page == "Automation":
        st.header("Automation Settings")
    elif page == "By Industry":
        st.header("Industry Browse")
    else:  # DCA
        st.header("DCA Settings")

    if page == "Stock Analysis":
        # Stock symbol input - use URL parameter if available
        default_symbol = symbol_from_url if symbol_from_url else "AAPL"
        stock_symbol = st.text_input(
            "Enter Stock Symbol",
            value=default_symbol,
            help="Enter a valid stock ticker symbol (e.g., AAPL, GOOGL, MSFT)"
        ).upper()

        # Filter by industry: optional quick pick
        if db and hasattr(db, "get_all_industries"):
            ind_list = db.get_all_industries()
            if ind_list:
                st.selectbox("Filter by industry", ["(None)"] + sorted(ind_list), key="sa_industry_filter")
                sel_ind = st.session_state.get("sa_industry_filter") or "(None)"
                if sel_ind != "(None)" and hasattr(db, "get_stocks_by_industry"):
                    stocks_in_ind = db.get_stocks_by_industry(sel_ind)
                    sym_opts = [s["symbol"] for s in stocks_in_ind]
                    picked = st.selectbox("Pick symbol from industry", [""] + sym_opts, key="sa_industry_symbol")
                    if picked:
                        stock_symbol = picked
        
        # Analysis options
        show_fundamental_analysis = st.checkbox(
            "Fundamental Analysis",
            value=False,
            help="Show detailed financial statements including income statement, balance sheet, and cash flow"
        )
        
        # Auto-check Comprehensive Financial Overview when symbol comes from URL
        comprehensive_default = True if symbol_from_url else False
        show_comprehensive_table = st.checkbox(
            "Comprehensive Financial Overview",
            value=comprehensive_default,
            help="Show detailed tabular view with all key financial metrics organized by category"
        )
        
        # Data source options
        use_database = st.checkbox(
            "Use cached data from database",
            value=True,
            help="Check to use previously stored data from database, uncheck to fetch fresh data from Yahoo Finance"
        )
        
        # Analysis button - auto-trigger if symbol comes from URL
        analyze_button = st.button("Analyze Stock", type="primary")
        
        # Auto-trigger analysis if symbol comes from URL
        if symbol_from_url and st.session_state.get('auto_analyze_from_url', False):
            analyze_button = True
            # Clear the flag after using it
            st.session_state.auto_analyze_from_url = False

        if analyze_button and stock_symbol:
            st.session_state.stock_analysis_context = {
                "symbol": stock_symbol,
                "show_fundamental_analysis": show_fundamental_analysis,
                "show_comprehensive_table": show_comprehensive_table,
                "use_database": use_database
            }
    elif page == "Ollama Analysis":
        ollama_symbol = st.text_input(
            "Enter Stock Symbol",
            value="AAPL",
            help="Enter a valid stock ticker symbol for Ollama-based analysis"
        ).upper()
        if db and hasattr(db, "get_all_industries"):
            ind_list = db.get_all_industries()
            if ind_list:
                st.selectbox("Filter by industry", ["(None)"] + sorted(ind_list), key="ollama_industry_filter")
                sel_ind = st.session_state.get("ollama_industry_filter") or "(None)"
                if sel_ind != "(None)" and hasattr(db, "get_stocks_by_industry"):
                    stocks_in_ind = db.get_stocks_by_industry(sel_ind)
                    sym_opts = [s["symbol"] for s in stocks_in_ind]
                    picked = st.selectbox("Pick symbol from industry", [""] + sym_opts, key="ollama_industry_symbol")
                    if picked:
                        ollama_symbol = picked

        ollama_use_database = st.checkbox(
            "Use cached data from database",
            value=True,
            help="Use cached company/price data when available"
        )

        ollama_button = st.button("Analyze with Ollama", type="primary", key="ollama_analyze_button")
        if ollama_button and ollama_symbol:
            st.session_state.ollama_analysis_context = {
                "symbol": ollama_symbol,
                "period": "1 Year",
                "use_database": ollama_use_database
            }
    elif page == "DCA":
        # DCA page sidebar
        st.subheader("Add Stocks for DCA")
        
        # Input for comma-separated stock symbols
        dca_input = st.text_input(
            "Enter Stock Symbols (comma-separated)",
            value="",
            help="Enter stock symbols separated by commas (e.g., AAPL, GOOGL, MSFT)"
        )
        
        # Input for dollar amount
        dollar_amount = st.number_input(
            "Dollar Amount ($)",
            min_value=0.0,
            value=float(st.session_state.get('dca_dollar_amount', 0.0)),
            step=10.0,
            help="Enter the dollar amount you want to invest per DCA period"
        )
        
        # Store dollar amount in session state
        st.session_state.dca_dollar_amount = dollar_amount
        
        # Add stocks button
        if st.button("Add Stocks", type="primary", key="add_dca_stocks") and dca_input:
            # Parse comma-separated symbols
            symbols = [s.strip().upper() for s in dca_input.split(",") if s.strip()]
            
            if symbols:
                # Add new symbols to DCA list (avoid duplicates)
                new_symbols = []
                for symbol in symbols:
                    if symbol not in st.session_state.dca_stocks:
                        st.session_state.dca_stocks.append(symbol)
                        new_symbols.append(symbol)
                
                if new_symbols:
                    st.success(f"✅ Added {len(new_symbols)} stock(s): {', '.join(new_symbols)}")
                else:
                    st.info("All symbols are already in your DCA list")
                
                st.rerun()
        
        # Clear all button
        if st.button("Clear All Stocks", key="clear_dca_stocks", help="Remove all stocks from DCA list"):
            st.session_state.dca_stocks = []
            st.success("All DCA stocks cleared")
            st.rerun()
    elif page == "Automation":
        # Automation page sidebar
        automation_ticker = st.text_input(
            "Enter Stock Symbol",
            value="AAPL",
            help="Enter a stock ticker to analyze for automated trading setups"
        ).upper()
        if db and hasattr(db, "get_all_industries"):
            ind_list = db.get_all_industries()
            if ind_list:
                st.selectbox("Filter by industry", ["(None)"] + sorted(ind_list), key="automation_industry_filter")
                sel_ind = st.session_state.get("automation_industry_filter") or "(None)"
                if sel_ind != "(None)" and hasattr(db, "get_stocks_by_industry"):
                    stocks_in_ind = db.get_stocks_by_industry(sel_ind)
                    sym_opts = [s["symbol"] for s in stocks_in_ind]
                    picked = st.selectbox("Pick symbol from industry", [""] + sym_opts, key="automation_industry_symbol")
                    if picked:
                        automation_ticker = picked

        automation_button = st.button("🚀 Generate Trade Setups", type="primary", key="automation_analyze")
        
        st.markdown("---")
        st.info("💡 **How it works:**\n\n1. Scans last 60 days of price data\n2. Calculates technical indicators (SMA, RSI, ATR)\n3. Identifies trading setups\n4. Generates 5 trade parameters for different timeframes\n5. AI analyzes news and fundamentals\n6. Shows visual trade setup chart")
    else:  # My Portfolio page
        # Portfolio management
        st.subheader("Manage Portfolio")
        
        # Add stock to portfolio
        new_stock = st.text_input(
            "Add Stock Symbol",
            value="",
            help="Enter a stock ticker to add to your portfolio"
        ).upper()
        
        if st.button("Add to Portfolio") and new_stock:
            if new_stock not in st.session_state.portfolio:
                st.session_state.portfolio.append(new_stock)
                # Clear cached portfolio data since portfolio changed
                if 'cached_portfolio_data' in st.session_state:
                    del st.session_state.cached_portfolio_data
                st.session_state.portfolio_loaded = False
                
                # Save to database - try portfolio table first
                saved_to_db = False
                if db:
                    try:
                        # Try to use portfolio table
                        if hasattr(db, 'add_to_portfolio'):
                            if db.add_to_portfolio(new_stock):
                                saved_to_db = True
                        
                        # Also try to fetch and save basic stock info to ensure symbol is in database
                        try:
                            ticker = yf.Ticker(new_stock)
                            info = ticker.info
                            if info and info.get('symbol'):
                                db.save_stock_info(new_stock, info)
                                saved_to_db = True
                        except:
                            pass  # Continue even if stock info fetch fails
                        
                        if saved_to_db:
                            st.success(f"✅ Added {new_stock} to portfolio (saved to database)")
                        else:
                            st.warning(f"Added {new_stock} to portfolio (session only - restart app to enable database)")
                    except Exception as e:
                        st.warning(f"Added {new_stock} to portfolio (session only)")
                        with st.expander("🔧 Database Error Details"):
                            st.error(f"Error: {e}")
                            st.info("Click 'Refresh Database' in Database Management section or restart the app.")
                else:
                    st.success(f"Added {new_stock} to portfolio")
                st.session_state.portfolio_loaded = False
                st.rerun()
            else:
                st.warning(f"{new_stock} is already in your portfolio")
        
        # Data source options
        use_database = st.checkbox(
            "Use cached data from database",
            value=True,
            help="Check to use previously stored data from database, uncheck to fetch fresh data from Yahoo Finance"
        )
        
        # Refresh portfolio button
        analyze_button = st.button("Refresh Portfolio Data", type="primary")
        
        # Show database status
        if db and hasattr(db, 'get_portfolio'):
            with st.expander("📊 Portfolio Database Status"):
                try:
                    db_portfolio = db.get_portfolio()
                    if db_portfolio:
                        st.success(f"✅ {len(db_portfolio)} stocks saved in database")
                        st.write("**Database Portfolio:**", ", ".join(db_portfolio))
                        
                        # Check for sync issues
                        session_set = set(st.session_state.portfolio)
                        db_set = set(db_portfolio)
                        
                        if session_set != db_set:
                            st.warning("⚠️ Session and database are out of sync")
                            only_session = session_set - db_set
                            only_db = db_set - session_set
                            if only_session:
                                st.info(f"Only in session: {', '.join(only_session)}")
                            if only_db:
                                st.info(f"Only in database: {', '.join(only_db)}")
                            
                            if st.button("🔄 Sync Portfolio to Database"):
                                try:
                                    db.save_portfolio(list(st.session_state.portfolio))
                                    st.success("Portfolio synced successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Sync failed: {e}")
                        else:
                            st.success("✅ Session and database are in sync")
                    else:
                        st.warning("No portfolio found in database")
                        if st.button("💾 Save Current Portfolio to Database"):
                            try:
                                db.save_portfolio(list(st.session_state.portfolio))
                                st.success("Portfolio saved successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Save failed: {e}")
                except Exception as e:
                    st.error(f"Error checking database: {e}")
    
    # Database management section
    if db:
        st.subheader("Database Management")
        
        # Check if portfolio methods are available
        if not hasattr(db, 'add_to_portfolio'):
            st.error("⚠️ Database schema needs update!")
            st.info("Click the button below to refresh the database connection.")
            if st.button("🔄 Refresh Database", type="primary"):
                st.cache_resource.clear()
                st.rerun()
        
        # Portfolio statistics
        portfolio_count = len(st.session_state.portfolio)
        st.write(f"**Portfolio stocks:** {portfolio_count}")
        
        stored_symbols = db.get_all_symbols()
        if stored_symbols:
            st.write(f"**Cached symbols:** {', '.join(stored_symbols[:10])}")
            if len(stored_symbols) > 10:
                st.write(f"... and {len(stored_symbols) - 10} more")
            
            # Database statistics
            with st.expander("Database Statistics"):
                st.write("**Tables created:**")
                st.write("• Portfolio (saved stocks)")
                st.write("• Stock price data")
                st.write("• Company information")
                st.write("• Earnings data")
                st.write("• Income statements")
                st.write("• Balance sheets")
                st.write("• Cash flow statements")
                
                # Show caching status for a sample symbol if available
                if stored_symbols:
                    sample_symbol = stored_symbols[0]
                    st.write(f"\n**Cache Status for {sample_symbol}:**")
                    
                    # Check cached data availability
                    cached_data = {
                        'Stock Data': db.get_stock_data(sample_symbol) is not None,
                        'Company Info': db.get_stock_info(sample_symbol) is not None,
                        'Earnings': db.get_earnings_data(sample_symbol) is not None
                    }
                    
                    # Check financial statements
                    financials = db.get_financial_statements(sample_symbol)
                    if financials:
                        cached_data['Income Statement'] = financials.get('income_stmt') is not None and not financials.get('income_stmt').empty
                        cached_data['Balance Sheet'] = financials.get('balance_sheet') is not None and not financials.get('balance_sheet').empty
                        cached_data['Cash Flow'] = financials.get('cash_flow') is not None and not financials.get('cash_flow').empty
                    else:
                        cached_data['Income Statement'] = False
                        cached_data['Balance Sheet'] = False
                        cached_data['Cash Flow'] = False
                    
                    for data_type, is_cached in cached_data.items():
                        status = "✓ Cached" if is_cached else "✗ Not cached"
                        st.write(f"  {data_type}: {status}")
            
            # Clear data option
            symbol_to_delete = st.selectbox(
                "Delete data for symbol:",
                options=[""] + stored_symbols,
                help="Select a symbol to delete all its data from database"
            )
            
            if st.button("Delete Selected Data") and symbol_to_delete:
                if db.delete_stock_data(symbol_to_delete):
                    st.success(f"Deleted data for {symbol_to_delete}")
                    st.rerun()
                else:
                    st.error("Failed to delete data")
        else:
            st.write("No data stored in database yet")

def get_realtime_price(symbol):
    """Get real-time price for a single stock"""
    try:
        ticker = yf.Ticker(symbol)
        # Use fast_info for quick price fetch
        info = ticker.fast_info
        current_price = info.get('lastPrice') or info.get('regularMarketPrice')
        if current_price:
            return current_price
        return None
    except:
        return None

def validate_stock_symbol(symbol):
    """Validate if the stock symbol exists and has data"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        # Check if we have basic company information
        if 'symbol' not in info or info.get('regularMarketPrice') is None:
            return False, "Invalid stock symbol or no market data available"
        return True, None
    except Exception as e:
        return False, f"Error validating symbol: {str(e)}"

def get_stock_data(symbol, period, use_database=True, include_financials=False):
    """Fetch comprehensive stock data from Yahoo Finance or database"""
    try:
        hist_data = None
        info = None
        earnings_5y = None
        financials = None
        
        # Use database data exclusively if checkbox is checked
        if use_database and db:
            hist_data = db.get_stock_data(symbol)
            info = db.get_stock_info(symbol)
            earnings_5y = db.get_earnings_data(symbol)
            financials = None
            
            if hist_data is not None and info is not None:
                st.info(f"Using cached data from database for {symbol}")
                # Get financials from database if requested
                if include_financials:
                    financials = db.get_financial_statements(symbol)
                    if financials and any(v is not None and not v.empty for v in financials.values()):
                        st.success("Financial statements loaded from database cache")
                    else:
                        st.warning("Financial statements not available in database. Uncheck 'Use cached data' to fetch fresh data.")
                        financials = None
                
                return hist_data, info, earnings_5y, financials, None
            else:
                st.warning(f"No cached data found for {symbol} in database. Uncheck 'Use cached data' to fetch fresh data from Yahoo Finance.")
                return None, None, None, None, "No cached data available in database"
        
        # Fetch fresh data from Yahoo Finance
        # st.info(f"Fetching fresh data from Yahoo Finance for {symbol}")
        ticker = yf.Ticker(symbol)
        
        # Get historical data
        hist_data = ticker.history(period=period)
        if hist_data.empty:
            return None, None, None, None, "No historical data available for this symbol"
        
        # Get additional 3-month volume data for detailed analysis
        volume_3m = ticker.history(period="3mo")
        if not volume_3m.empty:
            # Store 3-month data as an attribute using setattr to avoid pandas warning
            setattr(hist_data, 'volume_3m', volume_3m)
        
        # Get company info
        info = ticker.info
        
        # Get earnings data (last 5 years)
        try:
            earnings = ticker.earnings
            if earnings is not None and not earnings.empty:
                # Get last 5 years of earnings data
                earnings_5y = earnings.tail(5)
            else:
                earnings_5y = None
        except:
            earnings_5y = None
        
        # Get financial statements if requested
        if include_financials:
            financials = get_financial_statements(ticker)
        
        # Save to database if available
        # if db:
        #     db.save_stock_data(symbol, hist_data)
        #     db.save_stock_info(symbol, info)
        #     if earnings_5y is not None:
        #         db.save_earnings_data(symbol, earnings_5y)
        #     if financials:
        #         db.save_financial_statements(symbol, financials)
        #     st.success(f"Data saved to database for future use")
        
        return hist_data, info, earnings_5y, financials, None
    except Exception as e:
        return None, None, None, None, f"Error fetching data: {str(e)}"

def calculate_financial_metrics(hist_data, info):
    """Calculate key financial metrics"""
    try:
        latest_close = hist_data['Close'].iloc[-1]
        previous_close = hist_data['Close'].iloc[-2] if len(hist_data) > 1 else latest_close
        
        # Calculate percentage change
        pct_change = ((latest_close - previous_close) / previous_close) * 100
        
        # Calculate volatility (standard deviation of returns)
        returns = hist_data['Close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100  # Annualized volatility
        
        # Calculate moving averages
        ma_20 = hist_data['Close'].rolling(window=20).mean().iloc[-1] if len(hist_data) >= 20 else None
        ma_50 = hist_data['Close'].rolling(window=50).mean().iloc[-1] if len(hist_data) >= 50 else None
        
        # Create metrics dictionary using global formatting functions
        metrics = {
            'Current Price': format_price(latest_close),
            'Daily Change': format_change_percentage(pct_change),
            'Volume': format_volume(hist_data['Volume'].iloc[-1]),
            'Market Cap': format_number(info.get('marketCap')),
            'P/E Ratio': format_ratio(info.get('trailingPE')),
            'Dividend Yield': format_percentage(info.get('dividendYield', 0)*100) if info.get('dividendYield') else "N/A",
            'Volatility (Annual)': format_percentage(volatility),
            '20-Day MA': format_price(ma_20) if ma_20 else "N/A",
            '50-Day MA': format_price(ma_50) if ma_50 else "N/A",
            '52-Week High': format_price(info.get('fiftyTwoWeekHigh')) if info.get('fiftyTwoWeekHigh') else "N/A",
            '52-Week Low': format_price(info.get('fiftyTwoWeekLow')) if info.get('fiftyTwoWeekLow') else "N/A",
        }
        
        return metrics
    except Exception as e:
        st.error(f"Error calculating metrics: {str(e)}")
        return {}

def generate_ai_stock_summary(stock_symbol, company_name, info, metrics, hist_data, earnings_data, financials, model: str | None = None):
    """
    Generate AI-powered stock analysis summary including:
    1. Company health summary
    2. Key opportunities
    3. Major risks
    4. Buy/Sell/Hold logic explanation
    Uses the provided model (or env default) for Ollama; pass model when calling from background thread.
    """
    try:
        # Prepare data summary for AI
        current_price = hist_data['Close'].iloc[-1] if not hist_data.empty else None
        price_change_1d = ((hist_data['Close'].iloc[-1] - hist_data['Close'].iloc[-2]) / hist_data['Close'].iloc[-2] * 100) if len(hist_data) > 1 else 0
        price_change_1y = ((hist_data['Close'].iloc[-1] - hist_data['Close'].iloc[0]) / hist_data['Close'].iloc[0] * 100) if len(hist_data) > 0 else 0
        
        # Extract key financial data
        pe_ratio = info.get('trailingPE')
        market_cap = info.get('marketCap')
        revenue = info.get('totalRevenue')
        profit_margin = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else None
        roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else None
        debt_to_equity = info.get('debtToEquity')
        current_ratio = info.get('currentRatio')
        dividend_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
        beta = info.get('beta')
        volatility = metrics.get('Volatility (Annual)', 'N/A')
        
        # Prepare earnings trend
        earnings_trend = "N/A"
        if earnings_data is not None and not earnings_data.empty:
            earnings_values = earnings_data['Earnings'].values
            if len(earnings_values) >= 2:
                recent_avg = np.mean(earnings_values[-2:])
                older_avg = np.mean(earnings_values[:-2]) if len(earnings_values) > 2 else earnings_values[0]
                earnings_trend = "Growing" if recent_avg > older_avg else "Declining" if recent_avg < older_avg else "Stable"
        
        # Build data context for AI
        profit_margin_str = f"{profit_margin:.2f}%" if profit_margin else 'N/A'
        roe_str = f"{roe:.2f}%" if roe else 'N/A'
        market_cap_str = f"${market_cap/1e9:.2f}B" if market_cap else 'N/A'
        current_price_str = f"${current_price:.2f}" if current_price else 'N/A'
        
        data_context = f"""
Company: {company_name} ({stock_symbol})
Current Price: {current_price_str} (1-day change: {price_change_1d:.2f}%, 1-year change: {price_change_1y:.2f}%)
Market Cap: {market_cap_str}
P/E Ratio: {pe_ratio if pe_ratio else 'N/A'}
Profit Margin: {profit_margin_str}
ROE: {roe_str}
Debt-to-Equity: {debt_to_equity if debt_to_equity else 'N/A'}
Current Ratio: {current_ratio if current_ratio else 'N/A'}
Dividend Yield: {dividend_yield:.2f}%
Beta: {beta if beta else 'N/A'}
Volatility: {volatility}
Earnings Trend: {earnings_trend}
Sector: {info.get('sector', 'N/A')}
Industry: {info.get('industry', 'N/A')}
Business Summary: {info.get('longBusinessSummary', 'N/A')[:500]}
"""
        
        # Use Ollama (e.g. Gemma3:4b) for AI analysis
        system_prompt = "You are an expert financial analyst with deep knowledge of stock market analysis, financial metrics, and investment strategies."
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
        content = call_ollama(system_prompt, user_prompt, temperature=0.7, max_tokens=2000, model=model)
        if content:
            return content
        
        # Fallback: Template-based analysis when AI is not available
        return generate_template_summary(stock_symbol, company_name, info, metrics, hist_data, earnings_data, pe_ratio, market_cap, profit_margin, roe, debt_to_equity, current_ratio, dividend_yield, beta, volatility, earnings_trend, price_change_1d, price_change_1y)
        
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def generate_template_summary(stock_symbol, company_name, info, metrics, hist_data, earnings_data, pe_ratio, market_cap, profit_margin, roe, debt_to_equity, current_ratio, dividend_yield, beta, volatility, earnings_trend, price_change_1d, price_change_1y):
    """Generate a template-based summary when AI is not available"""
    
    # Determine health indicators
    health_score = 0
    health_notes = []
    
    if pe_ratio and 10 <= pe_ratio <= 25:
        health_score += 1
        health_notes.append("Reasonable P/E ratio")
    elif pe_ratio and pe_ratio > 25:
        health_notes.append("High P/E ratio - may be overvalued")
    elif pe_ratio and pe_ratio < 10:
        health_notes.append("Low P/E ratio - may indicate value or concerns")
    
    if profit_margin and profit_margin > 10:
        health_score += 1
        health_notes.append("Strong profit margins")
    elif profit_margin and profit_margin < 5:
        health_notes.append("Thin profit margins")
    
    if roe and roe > 15:
        health_score += 1
        health_notes.append("Strong return on equity")
    elif roe and roe < 10:
        health_notes.append("Weak return on equity")
    
    if current_ratio and 1.5 <= current_ratio <= 3:
        health_score += 1
        health_notes.append("Healthy liquidity position")
    elif current_ratio and current_ratio < 1:
        health_notes.append("Liquidity concerns")
    
    if debt_to_equity and debt_to_equity < 1:
        health_score += 1
        health_notes.append("Conservative debt levels")
    elif debt_to_equity and debt_to_equity > 2:
        health_notes.append("High debt levels")
    
    health_status = "Strong" if health_score >= 4 else "Moderate" if health_score >= 2 else "Weak"
    
    # Determine recommendation
    recommendation = "HOLD"
    recommendation_reason = []
    
    if pe_ratio and pe_ratio < 15 and profit_margin and profit_margin > 10 and roe and roe > 15:
        recommendation = "BUY"
        recommendation_reason.append("Attractive valuation with strong fundamentals")
    elif pe_ratio and pe_ratio > 30 or (profit_margin and profit_margin < 0) or (debt_to_equity and debt_to_equity > 3):
        recommendation = "SELL"
        recommendation_reason.append("Concerning fundamentals or overvaluation")
    else:
        recommendation = "HOLD"
        recommendation_reason.append("Mixed signals - monitor closely")
    
    # Build conditional strings for better readability
    health_desc = 'strong' if health_score >= 4 else 'moderate' if health_score >= 2 else 'weak'
    
    pe_valuation = ''
    if pe_ratio:
        if 10 <= pe_ratio <= 25:
            pe_valuation = 'suggests reasonable valuation'
        elif pe_ratio > 25:
            pe_valuation = 'may indicate overvaluation'
        elif pe_ratio < 10:
            pe_valuation = 'may indicate value opportunity'
    
    profit_desc = ''
    if profit_margin:
        if profit_margin > 10:
            profit_desc = 'demonstrates strong operational efficiency'
        elif profit_margin < 5:
            profit_desc = 'indicates thin margins'
    
    roe_desc = ''
    if roe:
        if roe > 15:
            roe_desc = 'shows effective capital utilization'
        elif roe < 10:
            roe_desc = 'suggests room for improvement'
    
    liquidity_desc = ''
    if current_ratio:
        if 1.5 <= current_ratio <= 3:
            liquidity_desc = 'indicates healthy short-term financial position'
        elif current_ratio < 1:
            liquidity_desc = 'may raise liquidity concerns'
    
    debt_desc = ''
    if debt_to_equity:
        if debt_to_equity < 1:
            debt_desc = 'shows conservative leverage'
        elif debt_to_equity > 2:
            debt_desc = 'indicates higher financial risk'
    
    summary = f"""## 1. Company Health Summary

**Overall Health Status: {health_status}**

{company_name} ({stock_symbol}) shows {health_desc} financial health indicators:

- **Valuation**: P/E Ratio of {pe_ratio if pe_ratio else 'N/A'} {pe_valuation}
- **Profitability**: Profit margin of {f"{profit_margin:.2f}% {profit_desc}" if profit_margin else 'N/A'}
- **Efficiency**: ROE of {f"{roe:.2f}% {roe_desc}" if roe else 'N/A'}
- **Liquidity**: Current ratio of {current_ratio if current_ratio else 'N/A'} {liquidity_desc}
- **Debt Management**: Debt-to-equity of {debt_to_equity if debt_to_equity else 'N/A'} {debt_desc}
- **Price Performance**: {price_change_1d:+.2f}% (1-day), {price_change_1y:+.2f}% (1-year)
- **Earnings Trend**: {earnings_trend}

## 2. Key Opportunities

- **Market Position**: Operating in the {info.get('sector', 'N/A')} sector with potential for {'growth' if price_change_1y > 0 else 'recovery'}
- **Dividend Income**: Dividend yield of {dividend_yield:.2f}% {'provides income component' if dividend_yield > 0 else 'focuses on growth'}
- **Valuation Potential**: {('Current metrics suggest potential upside' if pe_ratio and pe_ratio < 20 else 'Premium valuation may limit near-term gains' if pe_ratio and pe_ratio > 25 else 'Fair valuation with balanced risk-reward') if pe_ratio else 'Valuation data unavailable'}
- **Sector Trends**: {info.get('sector', 'N/A')} sector {'shows positive momentum' if price_change_1y > 0 else 'may be in transition'}

## 3. Major Risks

- **Valuation Risk**: {('High P/E ratio suggests overvaluation risk' if pe_ratio and pe_ratio > 25 else 'Low P/E may indicate underlying concerns' if pe_ratio and pe_ratio < 10 else 'Valuation appears reasonable') if pe_ratio else 'Valuation data unavailable'}
- **Financial Risk**: {('High debt levels increase financial risk' if debt_to_equity and debt_to_equity > 2 else 'Debt levels appear manageable' if debt_to_equity and debt_to_equity < 1 else 'Moderate debt levels') if debt_to_equity else 'Debt data unavailable'}
- **Liquidity Risk**: {'Current ratio below 1 indicates potential liquidity issues' if current_ratio and current_ratio < 1 else 'Liquidity position appears adequate' if current_ratio else 'Liquidity data unavailable'}
- **Market Risk**: Beta of {beta if beta else 'N/A'} {('indicates higher volatility' if beta and beta > 1.2 else 'suggests lower volatility' if beta and beta < 0.8 else 'moderate volatility') if beta else ''}
- **Profitability Risk**: {('Negative or low profit margins raise sustainability concerns' if profit_margin and profit_margin < 5 else 'Profitability appears stable' if profit_margin and profit_margin > 10 else 'Moderate profitability') if profit_margin else 'Profitability data unavailable'}
- **Price Volatility**: {f'High volatility ({volatility}) increases investment risk' if isinstance(volatility, str) and 'High' in str(volatility) else 'Volatility appears manageable'}

## 4. Buy/Sell/Hold Recommendation & Logic

**Recommendation: {recommendation}**

**Investment Thesis:**

{' '.join(recommendation_reason) if recommendation_reason else 'Based on available financial metrics'}

**Key Factors:**
- **Valuation**: {('Attractive' if pe_ratio and pe_ratio < 15 else 'Fair' if pe_ratio and 15 <= pe_ratio <= 25 else 'Expensive' if pe_ratio and pe_ratio > 25 else 'Unknown') if pe_ratio else 'Unknown'}
- **Fundamentals**: {'Strong' if health_score >= 4 else 'Moderate' if health_score >= 2 else 'Weak'}
- **Risk-Reward**: {'Favorable' if recommendation == 'BUY' else 'Unfavorable' if recommendation == 'SELL' else 'Balanced'}
- **Time Horizon**: {'Suitable for long-term investors' if recommendation == 'BUY' else 'Consider short-term exit' if recommendation == 'SELL' else 'Monitor for better entry/exit points'}

**What Would Change This Recommendation:**
- **To BUY**: Significant improvement in profit margins, debt reduction, or valuation becoming more attractive
- **To SELL**: Deteriorating fundamentals, increasing debt, or valuation becoming excessive
- **To HOLD**: Maintain current position while monitoring key metrics for changes

**Note**: This is a template-based analysis. For AI-powered insights, ensure Ollama is running and select your preferred model in the sidebar (currently using the selected LLM model).
"""
    
    return summary

def calculate_volume_metrics(hist_data):
    """Calculate volume-specific metrics for the last 3 months"""
    try:
        # Use 3-month data if available
        if hasattr(hist_data, 'volume_3m') and hist_data.volume_3m is not None:
            volume_data = hist_data.volume_3m
        else:
            volume_data = hist_data
        
        if volume_data.empty:
            return {}
        
        # Calculate volume metrics
        current_volume = volume_data['Volume'].iloc[-1]
        avg_volume = volume_data['Volume'].mean()
        max_volume = volume_data['Volume'].max()
        min_volume = volume_data['Volume'].min()
        
        # Volume trend (comparing recent vs earlier periods)
        half_point = len(volume_data) // 2
        if half_point > 0:
            recent_avg = volume_data['Volume'].iloc[half_point:].mean()
            earlier_avg = volume_data['Volume'].iloc[:half_point].mean()
            volume_trend = ((recent_avg - earlier_avg) / earlier_avg) * 100 if earlier_avg > 0 else 0
        else:
            volume_trend = 0
        
        # Volume relative to average
        volume_vs_avg = ((current_volume - avg_volume) / avg_volume) * 100 if avg_volume > 0 else 0
        
        volume_metrics = {
            'Current Volume': format_volume(current_volume),
            'Avg Volume (3M)': format_volume(avg_volume),
            'Max Volume (3M)': format_volume(max_volume),
            'Min Volume (3M)': format_volume(min_volume),
            'Volume vs Avg': format_change_percentage(volume_vs_avg, 1),
            'Volume Trend': format_change_percentage(volume_trend, 1)
        }
        
        return volume_metrics
    except Exception as e:
        st.error(f"Error calculating volume metrics: {str(e)}")
        return {}

def create_price_chart(hist_data, symbol):
    """Create an interactive price chart using Plotly"""
    fig = go.Figure()
    
    # Add candlestick chart
    fig.add_trace(go.Candlestick(
        x=hist_data.index,
        open=hist_data['Open'],
        high=hist_data['High'],
        low=hist_data['Low'],
        close=hist_data['Close'],
        name=f"{symbol} Price"
    ))
    
    # Add moving averages if enough data
    if len(hist_data) >= 20:
        ma_20 = hist_data['Close'].rolling(window=20).mean()
        fig.add_trace(go.Scatter(
            x=hist_data.index,
            y=ma_20,
            mode='lines',
            name='20-Day MA',
            line=dict(color='orange', width=1)
        ))
    
    if len(hist_data) >= 50:
        ma_50 = hist_data['Close'].rolling(window=50).mean()
        fig.add_trace(go.Scatter(
            x=hist_data.index,
            y=ma_50,
            mode='lines',
            name='50-Day MA',
            line=dict(color='red', width=1)
        ))
    
    fig.update_layout(
        title=f"{symbol} Stock Price Chart",
        xaxis_title="Date",
        yaxis_title="Price ($)",
        template="plotly_white",
        height=500,
        showlegend=True
    )
    
    return fig

def create_volume_chart(hist_data, symbol):
    """Create a volume chart with 3-month focus"""
    fig = go.Figure()
    
    # Use 3-month data if available, otherwise use all available data
    if hasattr(hist_data, 'volume_3m') and hist_data.volume_3m is not None:
        volume_data = hist_data.volume_3m
        title_suffix = " (Last 3 Months)"
    else:
        volume_data = hist_data
        title_suffix = ""
    
    # Calculate volume moving average
    volume_ma = volume_data['Volume'].rolling(window=20).mean()
    
    # Add volume bars
    fig.add_trace(go.Bar(
        x=volume_data.index,
        y=volume_data['Volume'],
        name='Daily Volume',
        marker_color='lightblue',
        opacity=0.7
    ))
    
    # Add volume moving average
    fig.add_trace(go.Scatter(
        x=volume_data.index,
        y=volume_ma,
        mode='lines',
        name='20-Day Volume MA',
        line=dict(color='red', width=2)
    ))
    
    fig.update_layout(
        title=f"{symbol} Trading Volume{title_suffix}",
        xaxis_title="Date",
        yaxis_title="Volume",
        template="plotly_white",
        height=400,
        showlegend=True
    )
    
    return fig

def create_earnings_chart(earnings_data, symbol):
    """Create an earnings per share chart for the last 5 years"""
    if earnings_data is None or earnings_data.empty:
        return None
    
    fig = go.Figure()
    
    # Create bar chart for earnings
    fig.add_trace(go.Bar(
        x=earnings_data.index,
        y=earnings_data['Earnings'],
        name='Earnings Per Share',
        marker_color='green',
        text=[f"${val:.2f}" for val in earnings_data['Earnings']],
        textposition='outside'
    ))
    
    fig.update_layout(
        title=f"{symbol} Earnings Per Share (Last 5 Years)",
        xaxis_title="Year",
        yaxis_title="Earnings Per Share ($)",
        template="plotly_white",
        height=400,
        showlegend=False
    )
    
    return fig

def get_financial_statements(ticker):
    """Get financial statements from Yahoo Finance"""
    try:
        financials = {
            'income_stmt': None,
            'balance_sheet': None,
            'cash_flow': None
        }
        
        # Get income statement
        try:
            financials['income_stmt'] = ticker.income_stmt
        except:
            pass
            
        # Get balance sheet
        try:
            financials['balance_sheet'] = ticker.balance_sheet
        except:
            pass
            
        # Get cash flow
        try:
            financials['cash_flow'] = ticker.cash_flow
        except:
            pass
            
        return financials
    except Exception as e:
        st.error(f"Error fetching financial statements: {e}")
        return None

def display_financial_statement(statement_df, title, symbol):
    """Display a financial statement in a formatted table with proper number formatting"""
    if statement_df is None or statement_df.empty:
        st.warning(f"{title} data not available for {symbol}")
        return
    
    st.subheader(f"📊 {title}")
    
    # Create a copy for formatting
    display_df = statement_df.copy()
    
    # Reset index to make row names accessible
    display_df = display_df.reset_index()
    
    # Format all numeric columns consistently
    for col in display_df.columns:
        if col != 'index':  # Skip the index column
            # Check if column contains numeric data
            try:
                # Convert to numeric, handling any string values
                numeric_col = pd.to_numeric(display_df[col], errors='coerce')
                if not numeric_col.isna().all():  # If column has numeric data
                    # Apply financial formatting to numeric values
                    display_df[col] = numeric_col.apply(lambda x: format_financial_statement_value(x) if pd.notna(x) else 'N/A')
            except:
                # If conversion fails, keep original values
                pass
    
    # Format column names (dates) for better readability
    new_columns = []
    for col in display_df.columns:
        if col == 'index':
            new_columns.append('Item')
        elif hasattr(col, 'strftime'):
            new_columns.append(col.strftime('%Y-%m-%d'))
        else:
            new_columns.append(str(col))
    display_df.columns = new_columns
    
    # Display the formatted table
    st.dataframe(display_df, use_container_width=True)
    
    return display_df

def create_comprehensive_metrics_table(symbol, info, hist_data, financials):
    """Create a comprehensive metrics table matching the image structure"""
    
    # Helper function to safely get values
    def safe_get(data, key, default='N/A'):
        try:
            value = data.get(key)
            if value is None or value == '':
                return default
            return value
        except:
            return default
    
    # Helper function to format ratios
    def format_ratio_safe(value):
        try:
            if value is None or value == '' or pd.isna(value):
                return 'N/A'
            if isinstance(value, (int, float)):
                return f"{value:.2f}"
            return str(value)
        except:
            return 'N/A'
    
    # Helper function to format percentages
    def format_percentage_safe(value):
        try:
            if value is None or value == '' or pd.isna(value):
                return 'N/A'
            if isinstance(value, (int, float)):
                return f"{value:.2f}%"
            return str(value)
        except:
            return 'N/A'
    
    # Helper function to format currency
    def format_currency_safe(value):
        try:
            if value is None or value == '' or pd.isna(value):
                return 'N/A'
            if isinstance(value, (int, float)):
                if abs(value) >= 1e9:
                    return f"${value/1e9:.1f}B"
                elif abs(value) >= 1e6:
                    return f"${value/1e6:.1f}M"
                elif abs(value) >= 1e3:
                    return f"${value/1e3:.1f}K"
                else:
                    return f"${value:.2f}"
            return str(value)
        except:
            return 'N/A'
    
    # Calculate price change percentages
    def calculate_price_changes(hist_data):
        """Calculate hourly, daily, weekly, monthly, and 52-week price changes"""
        changes = {
            'hourly_change': 'N/A',
            'hourly_change_value': 'N/A',
            'daily_change': 'N/A',
            'daily_change_value': 'N/A',
            'weekly_change': 'N/A',
            'weekly_change_value': 'N/A',
            'monthly_change': 'N/A',
            'monthly_change_value': 'N/A',
            'yearly_change': 'N/A'
        }
        
        try:
            if hist_data is None or hist_data.empty or len(hist_data) < 2:
                return changes
            
            current_price = hist_data['Close'].iloc[-1]
            
            # Hourly change (use intraday data if available, otherwise N/A)
            # Since we typically have daily data, hourly might not be available
            if len(hist_data) >= 2:
                # For daily data, we can calculate the change within the last day
                # Using Open to Close of the most recent day as a proxy for intraday
                last_day = hist_data.iloc[-1]
                if 'Open' in hist_data.columns and pd.notna(last_day['Open']) and last_day['Open'] > 0:
                    hourly_change_value = current_price - last_day['Open']
                    hourly_pct = (hourly_change_value / last_day['Open']) * 100
                    changes['hourly_change'] = format_percentage_safe(hourly_pct)
                    changes['hourly_change_value'] = format_currency_safe(hourly_change_value)
            
            # Daily change (1 day ago)
            if len(hist_data) >= 2:
                prev_close = hist_data['Close'].iloc[-2]
                if pd.notna(prev_close) and prev_close > 0:
                    daily_change_value = current_price - prev_close
                    daily_pct = (daily_change_value / prev_close) * 100
                    changes['daily_change'] = format_percentage_safe(daily_pct)
                    changes['daily_change_value'] = format_currency_safe(daily_change_value)
            
            # Weekly change (5-7 trading days ago)
            if len(hist_data) >= 7:
                week_ago_price = hist_data['Close'].iloc[-7]
                if pd.notna(week_ago_price) and week_ago_price > 0:
                    weekly_change_value = current_price - week_ago_price
                    weekly_pct = (weekly_change_value / week_ago_price) * 100
                    changes['weekly_change'] = format_percentage_safe(weekly_pct)
                    changes['weekly_change_value'] = format_currency_safe(weekly_change_value)
            elif len(hist_data) >= 5:
                week_ago_price = hist_data['Close'].iloc[-5]
                if pd.notna(week_ago_price) and week_ago_price > 0:
                    weekly_change_value = current_price - week_ago_price
                    weekly_pct = (weekly_change_value / week_ago_price) * 100
                    changes['weekly_change'] = format_percentage_safe(weekly_pct)
                    changes['weekly_change_value'] = format_currency_safe(weekly_change_value)
            
            # Monthly change (approximately 21 trading days ago)
            if len(hist_data) >= 21:
                month_ago_price = hist_data['Close'].iloc[-21]
                if pd.notna(month_ago_price) and month_ago_price > 0:
                    monthly_change_value = current_price - month_ago_price
                    monthly_pct = (monthly_change_value / month_ago_price) * 100
                    changes['monthly_change'] = format_percentage_safe(monthly_pct)
                    changes['monthly_change_value'] = format_currency_safe(monthly_change_value)
            
            # 52-week change (approximately 252 trading days ago, or earliest available)
            if len(hist_data) >= 252:
                year_ago_price = hist_data['Close'].iloc[-252]
                if pd.notna(year_ago_price) and year_ago_price > 0:
                    yearly_change_value = current_price - year_ago_price
                    yearly_pct = (yearly_change_value / year_ago_price) * 100
                    changes['yearly_change'] = format_percentage_safe(yearly_pct)
                    changes['yearly_change_value'] = format_currency_safe(yearly_change_value)
            elif len(hist_data) >= 2:
                # Use earliest available price if less than a year of data
                earliest_price = hist_data['Close'].iloc[0]
                if pd.notna(earliest_price) and earliest_price > 0:
                    yearly_change_value = current_price - earliest_price
                    yearly_pct = (yearly_change_value / earliest_price) * 100
                    changes['yearly_change'] = format_percentage_safe(yearly_pct)
                    changes['yearly_change_value'] = format_currency_safe(yearly_change_value)
        
        except Exception as e:
            pass
        
        return changes
    
    # Calculate price changes
    price_changes = calculate_price_changes(hist_data)
    
    # Get financial statement data
    income_stmt = financials.get('income_stmt') if financials else None
    balance_sheet = financials.get('balance_sheet') if financials else None
    cash_flow = financials.get('cash_flow') if financials else None
    
    # Calculate current price and market cap
    current_price = hist_data['Close'].iloc[-1] if not hist_data.empty else 0
    market_cap = info.get('marketCap', 0)
    shares_outstanding = info.get('sharesOutstanding', 0)
    
    # Get industry/sector info
    industry = safe_get(info, 'industry', 'N/A')
    sector = safe_get(info, 'sector', 'N/A')
    
    # Add price changes to metrics
    hourly_change = price_changes['hourly_change']
    daily_change = price_changes['daily_change']
    weekly_change = price_changes['weekly_change']
    monthly_change = price_changes['monthly_change']
    yearly_change = price_changes['yearly_change']
    
    # Calculate PEG Ratio
    # PEG Ratio = P/E Ratio / Earnings Growth Rate
    pe_ratio = info.get('trailingPE')
    earnings_growth = info.get('earningsQuarterlyGrowth')
    peg_ratio = 'N/A'
    
    if pe_ratio and earnings_growth and pe_ratio > 0 and earnings_growth > 0:
        try:
            # Convert growth rate to percentage (0.15 = 15%)
            growth_rate = earnings_growth * 100
            peg_ratio_value = pe_ratio / growth_rate
            peg_ratio = format_ratio_safe(peg_ratio_value)
        except:
            peg_ratio = 'N/A'
    
    # Create comprehensive metrics dictionary
    metrics = {
        # Company Overview
        'Industry': industry,
        'Sector': sector,
        'Ticker': symbol,
        'Current Price': format_currency_safe(current_price),
        'Market Cap': format_currency_safe(market_cap),
        
        # Price Changes
        'Hourly Change': hourly_change,
        'Hourly Change Value': price_changes.get('hourly_change_value', 'N/A'),
        'Daily Change': daily_change,
        'Daily Change Value': price_changes.get('daily_change_value', 'N/A'),
        'Weekly Change': weekly_change,
        'Weekly Change Value': price_changes.get('weekly_change_value', 'N/A'),
        'Monthly Change': monthly_change,
        'Monthly Change Value': price_changes.get('monthly_change_value', 'N/A'),
        '52 Week Change': yearly_change,
        
        # Valuation Ratios
        'P/E Ratio': format_ratio_safe(info.get('trailingPE')),
        'PEG Ratio': peg_ratio,
        'Forward P/E': format_ratio_safe(info.get('forwardPE')),
        'P/B Ratio': format_ratio_safe(info.get('priceToBook')),
        'P/S Ratio': format_ratio_safe(info.get('priceToSalesTrailing12Months')),
        'Dividend Yield': format_percentage_safe(info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0),
        'Dividend Coverage': 'N/A',  # Would need additional calculation
        
        # Income Statement - Profitability Metrics
        'Revenue': 'N/A',
        'Revenue YoY': 'N/A',
        'Revenue per Share': 'N/A',
        'EPS': format_currency_safe(info.get('trailingEps')),
        'Cash Flow per Share': 'N/A',
        'Gross Profit Margin': 'N/A',
        'Operating Margin': format_percentage_safe(info.get('operatingMargin', 0) * 100 if info.get('operatingMargin') else 0),
        'Net Profit Margin': format_percentage_safe(info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0),
        'ROE': format_percentage_safe(info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0),
        'ROA': format_percentage_safe(info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0),
        
        # Balance Sheet
        'Asset Turnover': 'N/A',
        'D/E Ratio': format_ratio_safe(info.get('debtToEquity')),
        'Current Ratio': format_ratio_safe(info.get('currentRatio')),
        'Book Value per Share': format_currency_safe(info.get('bookValue')),
        
        # Cash Flow Statement
        'Operating Cash Flow': 'N/A',
        'Operating Cash Flow Margin': 'N/A',
        'Investing Cash Flow': 'N/A',
        'Financing Cash Flow': 'N/A',
        'Free Cash Flow': format_currency_safe(info.get('freeCashflow')),
    }
    
    # Try to extract data from financial statements if available
    if income_stmt is not None and not income_stmt.empty:
        try:
            # Get the most recent year's data (first column)
            latest_year = income_stmt.columns[0]
            
            # Revenue
            if 'Total Revenue' in income_stmt.index:
                revenue = income_stmt.loc['Total Revenue', latest_year]
                metrics['Revenue'] = format_currency_safe(revenue)
                
                # Revenue per share
                if shares_outstanding and revenue:
                    rps = revenue / shares_outstanding
                    metrics['Revenue per Share'] = format_currency_safe(rps)
            
            # Try to calculate YoY growth if we have previous year data
            if len(income_stmt.columns) > 1:
                try:
                    current_revenue = income_stmt.loc['Total Revenue', latest_year] if 'Total Revenue' in income_stmt.index else 0
                    previous_revenue = income_stmt.loc['Total Revenue', income_stmt.columns[1]] if 'Total Revenue' in income_stmt.index else 0
                    if previous_revenue and current_revenue:
                        yoy_growth = ((current_revenue - previous_revenue) / previous_revenue) * 100
                        metrics['Revenue YoY'] = format_percentage_safe(yoy_growth)
                except:
                    pass
            
            # Net Income and EPS
            if 'Net Income' in income_stmt.index:
                net_income = income_stmt.loc['Net Income', latest_year]
                if shares_outstanding and net_income:
                    eps = net_income / shares_outstanding
                    metrics['EPS'] = format_currency_safe(eps)
            
            # Operating Income and margins
            if 'Operating Income' in income_stmt.index:
                operating_income = income_stmt.loc['Operating Income', latest_year]
                if 'Total Revenue' in income_stmt.index:
                    total_revenue = income_stmt.loc['Total Revenue', latest_year]
                    if total_revenue and operating_income:
                        op_margin = (operating_income / total_revenue) * 100
                        metrics['Operating Margin'] = format_percentage_safe(op_margin)
        
        except Exception as e:
            pass  # Continue with default values
    
    if balance_sheet is not None and not balance_sheet.empty:
        try:
            latest_year = balance_sheet.columns[0]
            
            # Total Assets and Revenue for Asset Turnover
            if 'Total Assets' in balance_sheet.index and 'Total Revenue' in income_stmt.index:
                total_assets = balance_sheet.loc['Total Assets', latest_year]
                total_revenue = income_stmt.loc['Total Revenue', latest_year] if income_stmt is not None else 0
                if total_assets and total_revenue:
                    asset_turnover = total_revenue / total_assets
                    metrics['Asset Turnover'] = format_ratio_safe(asset_turnover)
        
        except Exception as e:
            pass
    
    if cash_flow is not None and not cash_flow.empty:
        try:
            latest_year = cash_flow.columns[0]
            
            # Operating Cash Flow
            if 'Total Cash From Operating Activities' in cash_flow.index:
                ocf = cash_flow.loc['Total Cash From Operating Activities', latest_year]
                metrics['Operating Cash Flow'] = format_currency_safe(ocf)
                
                # Operating Cash Flow Margin
                if 'Total Revenue' in income_stmt.index:
                    total_revenue = income_stmt.loc['Total Revenue', latest_year]
                    if total_revenue and ocf:
                        ocf_margin = (ocf / total_revenue) * 100
                        metrics['Operating Cash Flow Margin'] = format_percentage_safe(ocf_margin)
            
            # Investing Cash Flow
            if 'Total Cashflows From Investing Activities' in cash_flow.index:
                icf = cash_flow.loc['Total Cashflows From Investing Activities', latest_year]
                metrics['Investing Cash Flow'] = format_currency_safe(icf)
            
            # Financing Cash Flow
            if 'Total Cash From Financing Activities' in cash_flow.index:
                fcf = cash_flow.loc['Total Cash From Financing Activities', latest_year]
                metrics['Financing Cash Flow'] = format_currency_safe(fcf)
        
        except Exception as e:
            pass
    
    return metrics

# DCA Backtest Functions (based on notebook)
def normalize_percent(value, floor_pct=-100.0, cap_pct=200.0):
    """Normalize a percentage value to 0-100 range"""
    if pd.isna(value):
        return 50.0
    v = max(floor_pct, min(cap_pct, value))
    return (v - floor_pct) / (cap_pct - floor_pct) * 100.0

# Scoring weights (from notebook)
DCA_WEIGHTS = {
    "fundamentals": 25,
    "valuation": 15,
    "technical": 15,
    "analyst_institutional": 15,
    "earnings_forecast": 15,
    "news_social": 10,
    "macro": 5
}

def compute_total_score_from_components(components: dict) -> float:
    """Compute total score from component scores (0-100)"""
    total = 0.0
    for k, w in DCA_WEIGHTS.items():
        comp = components.get(k, 50.0)  # Default to neutral (50) if missing
        total += comp * (w / 100.0)
    # Ensure within 0..100
    return max(0.0, min(100.0, total))

def allocate_weights_from_scores(scores: dict) -> dict:
    """Allocate weights from scores (score-weighted allocation)"""
    eps = 1e-8
    tickers = list(scores.keys())
    vals = np.array([max(eps, scores[t]) for t in tickers], dtype=float)
    s = np.sum(vals)
    if s <= 0:
        # Equal weight fallback
        n = len(tickers)
        return {t: 1.0/n for t in tickers}
    ws = vals / s
    return {t: float(w) for t, w in zip(tickers, ws)}

def calculate_stock_score(info, hist_data, earnings_data=None):
    """Calculate stock score based on fundamentals, valuation, and technical indicators"""
    components = {}
    
    try:
        # Fundamentals component (25%)
        profit_margin = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else None
        roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else None
        current_ratio = info.get('currentRatio')
        debt_to_equity = info.get('debtToEquity')
        
        fund_score = 50.0  # Neutral baseline
        if profit_margin:
            fund_score += normalize_percent(profit_margin, 0, 50) * 0.3
        if roe:
            fund_score += normalize_percent(roe, 0, 50) * 0.3
        if current_ratio:
            fund_score += normalize_percent((current_ratio - 1) * 50, -50, 50) * 0.2
        if debt_to_equity:
            # Lower debt is better
            fund_score += normalize_percent((2 - debt_to_equity) * 25, -50, 50) * 0.2
        
        components["fundamentals"] = max(0, min(100, fund_score))
        
        # Valuation component (15%)
        pe_ratio = info.get('trailingPE')
        pb_ratio = info.get('priceToBook')
        ps_ratio = info.get('priceToSalesTrailing12Months')
        
        val_score = 50.0
        if pe_ratio:
            # Lower P/E is generally better (value), but too low might indicate problems
            # Normalize: 10-25 is good range
            if 10 <= pe_ratio <= 25:
                val_score = 70
            elif pe_ratio < 10:
                val_score = 60  # Might be value or concern
            elif pe_ratio > 30:
                val_score = 30  # Overvalued
            else:
                val_score = 50
        
        components["valuation"] = val_score
        
        # Technical component (15%) - momentum based
        if len(hist_data) >= 20:
            returns_20 = hist_data['Close'].pct_change(20).iloc[-1] * 100 if len(hist_data) > 20 else 0
            returns_50 = hist_data['Close'].pct_change(50).iloc[-1] * 100 if len(hist_data) > 50 else 0
            momentum = (returns_20 * 0.6 + returns_50 * 0.4) if len(hist_data) > 50 else returns_20
            components["technical"] = normalize_percent(momentum, -50, 100)
        else:
            components["technical"] = 50.0
        
        # Analyst/Institutional component (15%)
        # Use recommendation mean if available
        recommendation_mean = info.get('recommendationMean')
        if recommendation_mean:
            # Map recommendation: 1=Strong Buy, 5=Strong Sell
            # Convert to 0-100 scale (inverted)
            analyst_score = (5 - recommendation_mean) / 4 * 100
            components["analyst_institutional"] = max(0, min(100, analyst_score))
        else:
            components["analyst_institutional"] = 50.0
        
        # Earnings forecast component (15%)
        if earnings_data is not None and not earnings_data.empty:
            # Check earnings trend
            earnings_values = earnings_data['Earnings'].values
            if len(earnings_values) >= 2:
                recent_avg = np.mean(earnings_values[-2:])
                older_avg = np.mean(earnings_values[:-2]) if len(earnings_values) > 2 else earnings_values[0]
                earnings_growth = ((recent_avg - older_avg) / abs(older_avg)) * 100 if older_avg != 0 else 0
                components["earnings_forecast"] = normalize_percent(earnings_growth, -50, 100)
            else:
                components["earnings_forecast"] = 50.0
        else:
            components["earnings_forecast"] = 50.0
        
        # News/Social component (10%) - use price momentum as proxy
        if len(hist_data) >= 5:
            recent_returns = hist_data['Close'].pct_change(5).iloc[-1] * 100
            components["news_social"] = normalize_percent(recent_returns, -20, 20)
        else:
            components["news_social"] = 50.0
        
        # Macro component (5%) - neutral for now
        components["macro"] = 50.0
        
        # Compute total score
        total_score = compute_total_score_from_components(components)
        return total_score, components
        
    except Exception as e:
        # Return neutral score on error
        return 50.0, {k: 50.0 for k in DCA_WEIGHTS.keys()}

def backtest_dca(symbols, daily_invest, start_date, end_date, use_database=True):
    """Backtest DCA strategy with score-weighted allocation"""
    try:
        # Fetch historical data for all symbols
        all_data = {}
        all_info = {}
        all_earnings = {}
        
        progress = st.progress(0)
        status = st.empty()
        
        for i, symbol in enumerate(symbols):
            status.text(f"Fetching data for {symbol}... ({i+1}/{len(symbols)})")
            hist_data, info, earnings_data, _, error = get_stock_data(symbol, "5y", use_database, False)
            
            if error or hist_data is None or info is None:
                st.warning(f"Could not fetch data for {symbol}: {error}")
                continue
            
            all_data[symbol] = hist_data
            all_info[symbol] = info
            all_earnings[symbol] = earnings_data
            progress.progress((i + 1) / len(symbols))
        
        progress.empty()
        status.empty()
        
        if not all_data:
            return None, None, "No data available for any symbols"
        
        # Filter data to date range
        # Convert dates to timezone-naive Timestamps
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)
        
        # Create aligned price dataframe
        price_data = {}
        for symbol, hist in all_data.items():
            # Remove timezone from index if present to avoid comparison issues
            hist_copy = hist.copy()
            if hist_copy.index.tz is not None:
                hist_copy.index = hist_copy.index.tz_localize(None)
            
            # Filter by date range
            filtered = hist_copy[(hist_copy.index >= start_dt) & (hist_copy.index <= end_dt)]
            if not filtered.empty:
                price_data[symbol] = filtered['Close']
        
        if not price_data:
            return None, None, "No data available in the specified date range"
        
        # Align all price series to common dates
        price_df = pd.DataFrame(price_data)
        price_df = price_df.dropna()  # Remove dates where any stock is missing
        
        # Ensure index is timezone-naive
        if price_df.index.tz is not None:
            price_df.index = price_df.index.tz_localize(None)
        
        if price_df.empty:
            return None, None, "No overlapping dates found for the stocks"
        
        # Calculate daily scores and run backtest
        shares = {t: 0.0 for t in price_df.columns}
        invested = {t: 0.0 for t in price_df.columns}
        history = []
        
        # Pre-calculate scores for efficiency (using full historical data)
        # In a real implementation, you'd recalculate daily, but for performance we'll use current scores
        daily_scores = {}
        for symbol in price_df.columns:
            hist_full = all_data[symbol]
            earnings = all_earnings.get(symbol)
            score, _ = calculate_stock_score(all_info[symbol], hist_full, earnings)
            # Use same score for all days (or could recalculate periodically)
            daily_scores[symbol] = score
        
        # Calculate scores for each day (using latest available data up to that point)
        for dt in price_df.index:
            prices = price_df.loc[dt]
            scores = {}
            
            # For performance, use pre-calculated scores, but could recalculate daily
            # Calculate current scores based on data up to this date
            for symbol in price_df.columns:
                # Use historical data up to current date for technical indicators
                # Handle timezone-aware indices
                hist_full = all_data[symbol].copy()
                if hist_full.index.tz is not None:
                    hist_full.index = hist_full.index.tz_localize(None)
                
                # Convert dt to timezone-naive if needed
                dt_naive = dt.tz_localize(None) if hasattr(dt, 'tz') and dt.tz is not None else dt
                
                hist_up_to_date = hist_full[hist_full.index <= dt_naive]
                if len(hist_up_to_date) >= 20:  # Need enough data for technical analysis
                    earnings = all_earnings.get(symbol)
                    score, _ = calculate_stock_score(all_info[symbol], hist_up_to_date, earnings)
                    scores[symbol] = score
                else:
                    # Use pre-calculated score if not enough data
                    scores[symbol] = daily_scores.get(symbol, 50.0)
            
            # Allocate weights from scores
            weights = allocate_weights_from_scores(scores)
            
            # Make purchases at closing price
            for symbol in price_df.columns:
                w = weights[symbol]
                alloc = daily_invest * w
                price = prices[symbol]
                
                if pd.isna(price) or price <= 0:
                    continue
                
                qty = alloc / price
                shares[symbol] += qty
                invested[symbol] += alloc
            
            # Record portfolio value
            current_value = sum(shares[s] * prices[s] for s in price_df.columns)
            history.append({
                "Date": dt,
                "PortfolioValue": current_value,
                "TotalInvested": sum(invested.values()),
                **{f"Shares_{s}": shares[s] for s in price_df.columns},
                **{f"Invested_{s}": invested[s] for s in price_df.columns},
                **{f"Score_{s}": scores.get(s, 50.0) for s in price_df.columns},
                **{f"Weight_{s}": weights.get(s, 0.0) for s in price_df.columns}
            })
        
        hist_df = pd.DataFrame(history).set_index("Date")
        
        # Calculate equal-weight baseline
        shares_eq = {t: 0.0 for t in price_df.columns}
        invested_eq = {t: 0.0 for t in price_df.columns}
        history_eq = []
        equal_weight = 1.0 / len(price_df.columns)
        
        for dt in price_df.index:
            prices = price_df.loc[dt]
            
            for symbol in price_df.columns:
                alloc = daily_invest * equal_weight
                price = prices[symbol]
                
                if pd.isna(price) or price <= 0:
                    continue
                
                qty = alloc / price
                shares_eq[symbol] += qty
                invested_eq[symbol] += alloc
            
            current_value = sum(shares_eq[s] * prices[s] for s in price_df.columns)
            history_eq.append({
                "Date": dt,
                "PortfolioValue": current_value,
                "TotalInvested": sum(invested_eq.values())
            })
        
        hist_eq_df = pd.DataFrame(history_eq).set_index("Date")
        
        return hist_df, hist_eq_df, None
        
    except Exception as e:
        return None, None, f"Error in backtest: {str(e)}"

def fetch_portfolio_data(symbols, use_database=True):
    """Fetch comprehensive data for multiple stocks in portfolio"""
    portfolio_data = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, symbol in enumerate(symbols):
        try:
            status_text.text(f"Fetching data for {symbol}... ({i+1}/{len(symbols)})")
            
            # Fetch data with financials - use 1 year to get 52-week change
            hist_data, info, _, financials, error = get_stock_data(symbol, "1y", use_database, include_financials=True)
            
            if error or hist_data is None or info is None:
                st.warning(f"Could not fetch data for {symbol}")
                continue
            
            # Get comprehensive metrics
            metrics = create_comprehensive_metrics_table(symbol, info, hist_data, financials)
            metrics['symbol'] = symbol
            metrics['hist_data'] = hist_data  # Store for mini charts
            
            portfolio_data.append(metrics)
            # end a for loop iteration
            # break   
        except Exception as e:
            st.warning(f"Error fetching data for {symbol}: {str(e)}")
            continue
        
        progress_bar.progress((i + 1) / len(symbols))
    
    status_text.empty()
    progress_bar.empty()
    
    return portfolio_data

def create_mini_chart(hist_data):
    """Create a mini sparkline chart for 6-month performance"""
    try:
        if hist_data is None or hist_data.empty:
            return None
        
        # Use last 6 months of data (approximately 126 trading days)
        chart_data = hist_data.tail(126) if len(hist_data) > 126 else hist_data
        
        # Determine color based on performance
        first_price = chart_data['Close'].iloc[0]
        last_price = chart_data['Close'].iloc[-1]
        color = 'green' if last_price >= first_price else 'red'
        
        # Create a small line chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=chart_data.index,
            y=chart_data['Close'],
            mode='lines',
            line=dict(color=color, width=1.5),
            showlegend=False,
            hovertemplate='%{y:.2f}<extra></extra>'
        ))
        
        fig.update_layout(
            height=50,
            width=150,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
        )
        
        return fig
    except:
        return None

def style_value(value, is_percentage=False, reverse_colors=False):
    """Apply color styling to values based on positive/negative"""
    try:
        # Extract numeric value from string
        if isinstance(value, str):
            # Remove currency symbols, commas, percentages
            clean_value = value.replace('$', '').replace(',', '').replace('%', '').replace('B', '').replace('M', '').replace('K', '')
            if clean_value == 'N/A' or clean_value == '' or clean_value == '#DIV/0!' or clean_value == '#N/A':
                return value
            
            try:
                numeric_value = float(clean_value)
            except:
                return value
        elif isinstance(value, (int, float)):
            numeric_value = value
        else:
            return value
        
        # Apply color based on value
        if numeric_value > 0:
            color = 'red' if reverse_colors else 'green'
        elif numeric_value < 0:
            color = 'green' if reverse_colors else 'red'
        else:
            return value
        
        return f'<span style="color: {color};">{value}</span>'
    except:
        return value

def display_portfolio_grid(portfolio_data):
    """Display the comprehensive portfolio grid with all financial metrics"""
    if not portfolio_data:
        st.warning("No portfolio data available")
        return
    
    # Create DataFrame from portfolio data
    grid_data = []
    
    def format_currency_value(value):
        try:
            if value is None or pd.isna(value):
                return 'N/A'
            return format_price(value)
        except:
            return 'N/A'

    def compute_change_value(hist_data, periods, use_open=False):
        try:
            if hist_data is None or hist_data.empty:
                return None

            hist_df = hist_data
            current_price = hist_df['Close'].iloc[-1]

            if use_open:
                last_row = hist_df.iloc[-1]
                if 'Open' not in hist_df.columns:
                    return None
                open_price = last_row['Open']
                if pd.isna(open_price):
                    return None
                return current_price - open_price

            for period in periods:
                if len(hist_df) >= period:
                    past_price = hist_df['Close'].iloc[-period]
                    if pd.notna(past_price):
                        return current_price - past_price
            return None
        except:
            return None

    for stock_metrics in portfolio_data:
        row = {
            'Sector': stock_metrics.get('Sector', 'N/A'),
            'Security': stock_metrics.get('symbol', 'N/A'),
            'Price': stock_metrics.get('Current Price', 'N/A'),
            'MCAP': stock_metrics.get('Market Cap', 'N/A'),
            
            # Price Changes
            'Hourly %': stock_metrics.get('Hourly Change', 'N/A'),
            'Hourly $': stock_metrics.get('Hourly Change Value', 'N/A'),
            'Daily %': stock_metrics.get('Daily Change', 'N/A'),
            'Daily $': stock_metrics.get('Daily Change Value', 'N/A'),
            'Weekly %': stock_metrics.get('Weekly Change', 'N/A'),
            'Weekly $': stock_metrics.get('Weekly Change Value', 'N/A'),
            'Monthly %': stock_metrics.get('Monthly Change', 'N/A'),
            'Monthly $': stock_metrics.get('Monthly Change Value', 'N/A'),
            '52W %': stock_metrics.get('52 Week Change', 'N/A'),
            
            # Valuation Ratios
            'P/E Ratio': stock_metrics.get('P/E Ratio', 'N/A'),
            'P/B Ratio': stock_metrics.get('P/B Ratio', 'N/A'),
            'P/S Ratio': stock_metrics.get('P/S Ratio', 'N/A'),
            'PEG Ratio': stock_metrics.get('PEG Ratio', 'N/A'),
            'Forward PE': stock_metrics.get('Forward P/E', 'N/A'),
            'Div Yield': stock_metrics.get('Dividend Yield', 'N/A'),
            'Div Coverage': stock_metrics.get('Dividend Coverage', 'N/A'),
            
            # Income Statement
            'Revenue': stock_metrics.get('Revenue', 'N/A'),
            'Revenue YoY': stock_metrics.get('Revenue YoY', 'N/A'),
            'RPS': stock_metrics.get('Revenue per Share', 'N/A'),
            'EPS': stock_metrics.get('EPS', 'N/A'),
            'CF per Share': stock_metrics.get('Cash Flow per Share', 'N/A'),
            'Gross Margin': stock_metrics.get('Gross Profit Margin', 'N/A'),
            'Op Margin': stock_metrics.get('Operating Margin', 'N/A'),
            'Net Margin': stock_metrics.get('Net Profit Margin', 'N/A'),
            
            # Balance Sheet
            'ROE': stock_metrics.get('ROE', 'N/A'),
            'ROA': stock_metrics.get('ROA', 'N/A'),
            'Asset Turnover': stock_metrics.get('Asset Turnover', 'N/A'),
            'D/E Ratio': stock_metrics.get('D/E Ratio', 'N/A'),
            'Current Ratio': stock_metrics.get('Current Ratio', 'N/A'),
            'Book Value/Share': stock_metrics.get('Book Value per Share', 'N/A'),
            
            # Cash Flow
            'OCF': stock_metrics.get('Operating Cash Flow', 'N/A'),
            'OCF Margin': stock_metrics.get('Operating Cash Flow Margin', 'N/A'),
            'ICF': stock_metrics.get('Investing Cash Flow', 'N/A'),
            'FCF': stock_metrics.get('Financing Cash Flow', 'N/A'),
            'Free Cash Flow': stock_metrics.get('Free Cash Flow', 'N/A'),
            
            # Store hist_data for chart (not displayed in grid)
            '_hist_data': stock_metrics.get('hist_data')
        }
        
        hist_data = stock_metrics.get('hist_data')

        if row['Hourly $'] == 'N/A':
            delta = compute_change_value(hist_data, periods=[], use_open=True)
            if delta is not None:
                row['Hourly $'] = format_currency_value(delta)

        if row['Weekly $'] == 'N/A':
            delta = compute_change_value(hist_data, periods=[7, 5])
            if delta is not None:
                row['Weekly $'] = format_currency_value(delta)

        if row['Monthly $'] == 'N/A':
            delta = compute_change_value(hist_data, periods=[21, 14])
            if delta is not None:
                row['Monthly $'] = format_currency_value(delta)
        
        grid_data.append(row)
    
    df = pd.DataFrame(grid_data)
    
    # Filtering options
    st.subheader("🔍 Filters")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        sector_filter = st.multiselect(
            "Filter by Sector",
            options=['All'] + sorted(df['Sector'].unique().tolist()),
            default=['All']
        )
    
    with col2:
        min_price = st.number_input("Min Price ($)", value=0.0, min_value=0.0)
    
    with col3:
        max_price = st.number_input("Max Price ($)", value=10000.0, min_value=0.0)
    
    with col4:
        search_term = st.text_input("Search Symbol", value="")
    
    # Apply filters
    filtered_df = df.copy()
    
    if 'All' not in sector_filter and sector_filter:
        filtered_df = filtered_df[filtered_df['Sector'].isin(sector_filter)]
    
    if search_term:
        filtered_df = filtered_df[filtered_df['Security'].str.contains(search_term, case=False, na=False)]
    
    # Price filtering (extract numeric value)
    def extract_numeric_price(price_str):
        try:
            if isinstance(price_str, str):
                clean = price_str.replace('$', '').replace(',', '')
                return float(clean)
            return float(price_str)
        except:
            return 0.0
    
    filtered_df['_numeric_price'] = filtered_df['Price'].apply(extract_numeric_price)
    filtered_df = filtered_df[(filtered_df['_numeric_price'] >= min_price) & (filtered_df['_numeric_price'] <= max_price)]
    filtered_df = filtered_df.drop('_numeric_price', axis=1)
    
    st.write(f"**Showing {len(filtered_df)} of {len(df)} stocks**")
    
    # Display comprehensive grid with tabs for different sections
    st.subheader("📊 Portfolio Overview")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview", 
        "Valuation Ratios", 
        "Income Statement", 
        "Balance Sheet", 
        "Cash Flow"
    ])
    
    # Remove hist_data from display
    display_df = filtered_df.drop('_hist_data', axis=1, errors='ignore')
    
    # Helper function to color percentage values
    def color_percentages(val):
        """Color positive percentages green and negative percentages red"""
        if isinstance(val, str):
            # Extract numeric value from percentage string
            try:
                if val == 'N/A' or val == '' or '%' not in val:
                    return ''
                numeric_val = float(val.replace('%', '').replace(',', ''))
                if numeric_val > 0:
                    return 'color: green; font-weight: bold'
                elif numeric_val < 0:
                    return 'color: red; font-weight: bold'
                else:
                    return ''
            except:
                return ''
        return ''
    
    # Helper function to extract numeric value from percentage strings for sorting
    def extract_numeric_from_percent(val):
        """Extract numeric value from percentage string"""
        try:
            if isinstance(val, str) and '%' in val:
                return float(val.replace('%', '').replace(',', ''))
            elif isinstance(val, (int, float)):
                return float(val)
            else:
                return float('-inf')  # Put N/A at the bottom
        except:
            return float('-inf')
    
    # Helper function to extract numeric value from currency strings for sorting
    def extract_numeric_from_currency(val):
        """Extract numeric value from currency-formatted string"""
        try:
            if isinstance(val, str):
                value = val.strip()
                if value in ('', 'N/A'):
                    return float('-inf')
                # Remove currency symbols and commas
                value = value.replace('$', '').replace(',', '').replace('+', '')
                multiplier = 1.0
                if value.endswith('B'):
                    multiplier = 1e9
                    value = value[:-1]
                elif value.endswith('M'):
                    multiplier = 1e6
                    value = value[:-1]
                elif value.endswith('K'):
                    multiplier = 1e3
                    value = value[:-1]
                # Handle parentheses for negatives
                value = value.strip()
                negative = value.startswith('(') and value.endswith(')')
                if negative:
                    value = value[1:-1]
                numeric = float(value)
                if negative:
                    numeric = -numeric
                return numeric * multiplier
            elif isinstance(val, (int, float)):
                return float(val)
            return float('-inf')
        except:
            return float('-inf')
    
    # Initialize sort state in session state
    if 'sort_states' not in st.session_state:
        st.session_state.sort_states = {}
    
    with tab1:
        # Overview columns with price changes
        overview_cols = ['Sector', 'Security', 'Price', 'MCAP', 'Hourly %', 'Hourly $', 'Daily %', 'Daily $', 'Weekly %', 'Weekly $', 'Monthly %', 'Monthly $', '52W %']
        percentage_cols_overview = ['Hourly %', 'Daily %', 'Weekly %', 'Monthly %', '52W %']
        
        # Enable real-time price updates toggle
        enable_realtime_prices = st.checkbox(
            "🔴 Enable Real-Time Price Updates (5 min refresh)",
            value=False,
            key="enable_realtime_overview"
        )
        
        # Sorting controls
        col_sort1, col_sort2 = st.columns([3, 1])
        with col_sort1:
            sort_col_overview = st.selectbox("Sort by", overview_cols, key="sort_overview")
        with col_sort2:
            if sort_col_overview in percentage_cols_overview:
                # For percentage columns, use toggle button
                sort_key = f'overview_{sort_col_overview}'
                if sort_key not in st.session_state.sort_states:
                    st.session_state.sort_states[sort_key] = 'desc'  # Start with positive high
                
                button_label = "↓ Positive High" if st.session_state.sort_states[sort_key] == 'desc' else "↑ Negative High"
                if st.button(button_label, key=f"toggle_{sort_key}"):
                    st.session_state.sort_states[sort_key] = 'asc' if st.session_state.sort_states[sort_key] == 'desc' else 'desc'
                    st.rerun()
                
                ascending = st.session_state.sort_states[sort_key] == 'asc'
            else:
                # For non-percentage columns, use standard ascending/descending
                sort_order = st.radio("Order", ["↓ Descending", "↑ Ascending"], key="order_overview", horizontal=True)
                ascending = sort_order == "↑ Ascending"
        
        # Ensure all overview columns exist before slicing
        for col in overview_cols:
            if col not in display_df.columns:
                display_df[col] = 'N/A'
        
        # Prepare overview dataframe
        sorted_df_overview = display_df[overview_cols].copy()
        
        # Initialize real-time price update tracking
        if enable_realtime_prices:
            # Initialize tracking variables in session state
            if 'last_price_update_time' not in st.session_state:
                st.session_state.last_price_update_time = 0
            if 'realtime_enabled_time' not in st.session_state:
                st.session_state.realtime_enabled_time = time.time()
            
            # Track when real-time was enabled/disabled
            current_time = time.time()
            REFRESH_INTERVAL = 300  # 5 minutes in seconds
            CHECK_INTERVAL = 30  # Check every 30 seconds to see if it's time to update
            
            # Calculate time since last update
            # If last_update_time is 0, it means prices haven't been updated yet, so update immediately
            if st.session_state.last_price_update_time > 0:
                time_since_last_update = current_time - st.session_state.last_price_update_time
            else:
                # First time enabling real-time or no previous update - update immediately
                time_since_last_update = REFRESH_INTERVAL + 1
            
            # Check if real-time was just enabled (within last 10 seconds)
            # This handles the case where user just enabled real-time
            time_since_enabled = current_time - st.session_state.realtime_enabled_time
            just_enabled = time_since_enabled < 10
            
            # Update prices if 5 minutes have passed OR if real-time was just enabled (first time)
            should_update_prices = (time_since_last_update >= REFRESH_INTERVAL) or (just_enabled and st.session_state.last_price_update_time == 0)
            
            if should_update_prices:
                # Update prices with real-time data
                st.caption("🔴 Fetching live prices...")
                prices_updated = False
                # Create a mapping of symbol to updated price
                price_updates = {}
                for _, row in sorted_df_overview.iterrows():
                    symbol = row['Security']
                    realtime_price = get_realtime_price(symbol)
                    if realtime_price:
                        # Format the price
                        if realtime_price >= 1e9:
                            price_str = f"${realtime_price/1e9:.1f}B"
                        elif realtime_price >= 1e6:
                            price_str = f"${realtime_price/1e6:.1f}M"
                        elif realtime_price >= 1e3:
                            price_str = f"${realtime_price/1e3:.1f}K"
                        else:
                            price_str = f"${realtime_price:.2f}"
                        price_updates[symbol] = price_str
                        prices_updated = True
                
                # Apply price updates to the dataframe
                if price_updates:
                    for idx, row in sorted_df_overview.iterrows():
                        symbol = row['Security']
                        if symbol in price_updates:
                            sorted_df_overview.at[idx, 'Price'] = price_updates[symbol]
                
                # Update the last update time
                if prices_updated:
                    st.session_state.last_price_update_time = current_time
                    # Note: We keep realtime_enabled_time as is - it's used to detect if real-time was just enabled
                    # The condition (just_enabled and last_price_update_time == 0) ensures we only update
                    # immediately on first enable, not on subsequent checks
            else:
                # Show countdown until next update
                remaining_time = max(0, REFRESH_INTERVAL - time_since_last_update)
                minutes_remaining = int(remaining_time // 60)
                seconds_remaining = int(remaining_time % 60)
                if remaining_time > 0:
                    st.caption(f"⏱️ Next refresh in {minutes_remaining}m {seconds_remaining}s...")
                else:
                    st.caption("⏱️ Refreshing prices...")
        else:
            # Reset tracking when real-time is disabled
            if 'last_price_update_time' in st.session_state:
                # Keep the last update time, but clear the enabled time
                if 'realtime_enabled_time' in st.session_state:
                    del st.session_state.realtime_enabled_time
        
        # Sort the dataframe
        if sort_col_overview in percentage_cols_overview:
            # Extract numeric values for sorting
            sorted_df_overview[f'_sort_{sort_col_overview}'] = sorted_df_overview[sort_col_overview].apply(extract_numeric_from_percent)
            sorted_df_overview = sorted_df_overview.sort_values(by=f'_sort_{sort_col_overview}', ascending=ascending)
            sorted_df_overview = sorted_df_overview.drop(f'_sort_{sort_col_overview}', axis=1)
        else:
            try:
                if sort_col_overview in ['Price', 'MCAP', 'Hourly $', 'Daily $', 'Weekly $', 'Monthly $']:
                    sorted_df_overview[f'_sort_{sort_col_overview}'] = sorted_df_overview[sort_col_overview].apply(extract_numeric_from_currency)
                    sorted_df_overview = sorted_df_overview.sort_values(by=f'_sort_{sort_col_overview}', ascending=ascending)
                    sorted_df_overview = sorted_df_overview.drop(f'_sort_{sort_col_overview}', axis=1)
                else:
                    sorted_df_overview = sorted_df_overview.sort_values(by=sort_col_overview, ascending=ascending)
            except:
                pass
        
        # Apply styling to percentage columns
        styled_overview = sorted_df_overview.style.applymap(
            color_percentages,
            subset=percentage_cols_overview
        )
        
        st.dataframe(
            styled_overview,
            use_container_width=True,
            height=600
        )
        
        # Auto-refresh using JavaScript (non-blocking) - placed after dataframe to avoid interrupting rendering
        if enable_realtime_prices:
            # Use JavaScript to auto-refresh the page periodically (non-blocking)
            # This allows the page to update without blocking user interaction
            # The page will reload every CHECK_INTERVAL seconds to check if it's time to update prices
            CHECK_INTERVAL = 30  # Check every 30 seconds
            
            # Inject JavaScript for auto-refresh (non-blocking on server side)
            # This runs in the browser, not blocking the server
            # The page will auto-reload every 30 seconds to check if prices need updating
            CHECK_INTERVAL_MS = CHECK_INTERVAL * 1000
            auto_refresh_js = f"""
            <script>
                if (!window.autoRefreshTimer) {{
                    window.autoRefreshTimer = setTimeout(function() {{
                        window.autoRefreshTimer = null;
                        window.location.reload();
                    }}, {CHECK_INTERVAL_MS});
                }}
            </script>
            """
            # Use components.html for reliable JavaScript execution in Streamlit
            try:
                import streamlit.components.v1 as components
                components.html(auto_refresh_js, height=0)
            except ImportError:
                # Fallback to markdown if components.html is not available
                st.markdown(auto_refresh_js, unsafe_allow_html=True)
        
        # Add helpful information
        st.info("📊 **Price Changes**: Hourly (Open to Close today), Daily (vs yesterday), Weekly (vs 1 week ago), Monthly (vs 1 month ago), 52W (vs 1 year ago)")
        
        # Add mini charts
        st.subheader("6-Month Performance Charts")
        num_cols = 4
        cols = st.columns(num_cols)
        
        for idx, (_, stock) in enumerate(filtered_df.iterrows()):
            with cols[idx % num_cols]:
                st.write(f"**{stock['Security']}**")
                hist_data = stock.get('_hist_data')
                if hist_data is not None:
                    mini_chart = create_mini_chart(hist_data)
                    if mini_chart:
                        st.plotly_chart(mini_chart, use_container_width=True, key=f"chart_{idx}")
    
    with tab2:
        # Valuation Ratios columns
        valuation_cols = ['Security', 'P/E Ratio', 'P/B Ratio', 'P/S Ratio', 'PEG Ratio', 
                         'Forward PE', 'Div Yield', 'Div Coverage']
        
        # Column descriptions for tooltips
        valuation_tooltips = {
            'P/E Ratio': """
**P/E Ratio (Price-to-Earnings)**

**Formula:** Share Price / Earnings Per Share (EPS)

**What it means:** 
- Shows how much investors are willing to pay for each dollar of a company's earnings
- Example: If P/E = 18, investors pay $18 for the company to earn $1 per year

**How to use:**
- Lower P/E often suggests undervaluation (but compare to industry peers)
- Higher P/E may indicate growth expectations or overvaluation
- Compare with competitors in the same industry
""",
            'P/B Ratio': """
**P/B Ratio (Price-to-Book)**

**Formula:** Share Price / Book Value Per Share

**What it means:**
- Compares company's market value to its book value (net asset value)
- Book value = Total Assets - Total Liabilities

**How to use:**
- P/B < 1 might suggest undervaluation (but understand why first)
- P/B > 1 means market values company above its accounting value
- Useful for asset-heavy companies (banks, real estate)
""",
            'P/S Ratio': """
**P/S Ratio (Price-to-Sales)**

**Formula:** Market Cap / Total Revenue (or Share Price / Revenue Per Share)

**What it means:**
- Compares company's market value to its total revenue
- Useful for companies with no earnings yet

**How to use:**
- Lower P/S is generally better
- Consider the company's growth potential
- Good for comparing companies in same industry
""",
            'PEG Ratio': """
**PEG Ratio (Price/Earnings-to-Growth)**

**Formula:** P/E Ratio / Earnings Growth Rate

**What it means:**
- P/E ratio adjusted for earnings growth
- Accounts for future growth expectations

**How to use:**
- PEG ≤ 1 is often considered favorable
- Suggests reasonable price for expected growth
- PEG > 2 may indicate overvaluation
""",
            'Forward PE': """
**Forward P/E Ratio**

**Formula:** Current Share Price / Projected EPS (next 12 months)

**What it means:**
- Estimated future P/E based on projected earnings
- Forward-looking valuation metric

**How to use:**
- Lower Forward P/E is generally better
- Compare with current P/E to see growth expectations
- Useful for predicting future value
""",
            'Div Yield': """
**Dividend Yield**

**Formula:** Annual Dividend / Stock Price

**What it means:**
- Annual return on stock from dividends alone
- Expressed as a percentage

**How to use:**
- Higher yield is better (but ensure sustainability)
- Compare with industry averages
- Check dividend history for consistency
- Very high yields may signal trouble
""",
            'Div Coverage': """
**Dividend Coverage Ratio**

**Formula:** Net Income / Total Dividends Paid

**What it means:**
- How many times a company can pay dividends from earnings
- Measures dividend sustainability

**How to use:**
- Ratio > 2 is generally healthy
- Ratio < 1 means paying dividends from reserves (unsustainable)
- Higher ratio = more sustainable dividends
"""
        }
        
        # Display tooltips in an expander
        with st.expander("ℹ️ **Column Descriptions** - Click to view metric explanations"):
            # Create tabs for each metric
            metric_tabs = st.tabs(['P/E Ratio', 'P/B Ratio', 'P/S Ratio', 'PEG Ratio', 'Forward PE', 'Div Yield', 'Div Coverage'])
            
            for idx, (tab, metric) in enumerate(zip(metric_tabs, ['P/E Ratio', 'P/B Ratio', 'P/S Ratio', 'PEG Ratio', 'Forward PE', 'Div Yield', 'Div Coverage'])):
                with tab:
                    st.markdown(valuation_tooltips[metric])
        
        # Add sorting functionality
        sort_col_val = st.selectbox("Sort by", valuation_cols, key="sort_valuation")
        sort_order_val = st.radio("Order", ["Ascending", "Descending"], key="order_valuation", horizontal=True)
        
        sorted_df_val = display_df[valuation_cols].copy()
        try:
            # Try to sort numerically if possible
            ascending = sort_order_val == "Ascending"
            sorted_df_val = sorted_df_val.sort_values(by=sort_col_val, ascending=ascending)
        except:
            pass
        
        st.dataframe(
            sorted_df_val,
            use_container_width=True,
            height=600
        )
    
    with tab3:
        # Income Statement columns
        income_cols = ['Security', 'Revenue', 'Revenue YoY', 'RPS', 'EPS', 'CF per Share',
                      'Gross Margin', 'Op Margin', 'Net Margin']
        percentage_cols_income = ['Revenue YoY', 'Gross Margin', 'Op Margin', 'Net Margin']
        
        # Column descriptions for tooltips
        income_tooltips = {
            'Revenue': """
**Revenue (Total Revenue)**

**What it means:**
- Total amount of money generated from core operations
- Before deducting any expenses
- Also called "top line" or "sales"

**How to use:**
- Look for consistent growth over time
- Compare with competitors in same industry
- Rising revenue indicates business expansion
""",
            'Revenue YoY': """
**Revenue Year-over-Year Growth**

**Formula:** ((Current Year Revenue - Previous Year Revenue) / Previous Year Revenue) × 100

**What it means:**
- Percentage change in revenue compared to previous year
- Indicates business growth rate

**How to use:**
- Positive YoY = Growing business ✅
- Negative YoY = Declining sales ⚠️
- Compare with industry average
- Look for consistent positive growth over 5 years
""",
            'RPS': """
**RPS (Revenue Per Share)**

**Formula:** Total Revenue / Shares Outstanding

**What it means:**
- How much revenue company generates per share
- Normalizes revenue across different company sizes

**How to use:**
- Rising RPS over time = Good growth indicator ✅
- Rising RPS + Rising EPS = Strong business growth
- Rising RPS + Falling EPS = Revenue growth without profit
- Flat RPS over years = Market saturation
- Declining RPS = Losing market share
""",
            'EPS': """
**EPS (Earnings Per Share)**

**Formula:** (Net Income - Preferred Dividends) / Shares Outstanding

**What it means:**
- Company's profit allocated to each share
- Key profitability metric

**How to use:**
- Higher EPS is better
- Look for consistent growth over time
- Compare with cash flow per share
- If EPS < Cash Flow per Share over long term, investigate why
- Growing EPS = Increasing profitability ✅
""",
            'CF per Share': """
**Cash Flow Per Share**

**Formula:** (Operating Cash Flow - Preferred Dividends) / Shares Outstanding

**What it means:**
- Actual cash generated per share
- More reliable than EPS (harder to manipulate)

**How to use:**
- Should be close to or higher than EPS
- If CF per Share < EPS over long term, be cautious ⚠️
- Higher values indicate strong cash generation
- Look for consistent growth
""",
            'Gross Margin': """
**Gross Profit Margin**

**Formula:** (Gross Profit / Revenue) × 100
**Where:** Gross Profit = Revenue - Cost of Goods Sold

**What it means:**
- Percentage of revenue left after direct production costs
- Shows pricing power and production efficiency

**How to use:**
- Higher is better (more profit per sale)
- Compare with industry peers
- Declining margin = Increasing costs or pricing pressure ⚠️
- 40%+ is excellent for most industries
""",
            'Op Margin': """
**Operating Margin**

**Formula:** (Operating Income / Revenue) × 100

**What it means:**
- Percentage of revenue left after operating expenses
- Shows operational efficiency

**How to use:**
- Higher is better
- Declining margin over time = Warning sign ⚠️
- Compare with competitors
- 15-20%+ is generally healthy
- Shows how well company controls costs
""",
            'Net Margin': """
**Net Profit Margin**

**Formula:** (Net Income / Revenue) × 100

**What it means:**
- Percentage of revenue that becomes profit
- "Bottom line" profitability

**How to use:**
- Higher is better
- Declining margin = Deteriorating profitability ⚠️
- Compare with industry average
- 10%+ is generally good
- Shows overall profitability after all expenses
"""
        }
        
        # Display tooltips in an expander
        with st.expander("ℹ️ **Column Descriptions** - Click to view metric explanations"):
            # Create tabs for each metric
            metric_tabs = st.tabs(['Revenue', 'Revenue YoY', 'RPS', 'EPS', 'CF per Share', 'Gross Margin', 'Op Margin', 'Net Margin'])
            
            for idx, (tab, metric) in enumerate(zip(metric_tabs, ['Revenue', 'Revenue YoY', 'RPS', 'EPS', 'CF per Share', 'Gross Margin', 'Op Margin', 'Net Margin'])):
                with tab:
                    st.markdown(income_tooltips[metric])
        
        # Sorting controls
        col_sort1, col_sort2 = st.columns([3, 1])
        with col_sort1:
            sort_col_inc = st.selectbox("Sort by", income_cols, key="sort_income")
        with col_sort2:
            if sort_col_inc in percentage_cols_income:
                # For percentage columns, use toggle button
                sort_key = f'income_{sort_col_inc}'
                if sort_key not in st.session_state.sort_states:
                    st.session_state.sort_states[sort_key] = 'desc'
                
                button_label = "↓ Positive High" if st.session_state.sort_states[sort_key] == 'desc' else "↑ Negative High"
                if st.button(button_label, key=f"toggle_{sort_key}"):
                    st.session_state.sort_states[sort_key] = 'asc' if st.session_state.sort_states[sort_key] == 'desc' else 'desc'
                    st.rerun()
                
                ascending = st.session_state.sort_states[sort_key] == 'asc'
            else:
                sort_order = st.radio("Order", ["↓ Descending", "↑ Ascending"], key="order_income", horizontal=True)
                ascending = sort_order == "↑ Ascending"
        
        # Sort the dataframe
        sorted_df_inc = display_df[income_cols].copy()
        if sort_col_inc in percentage_cols_income:
            sorted_df_inc[f'_sort_{sort_col_inc}'] = sorted_df_inc[sort_col_inc].apply(extract_numeric_from_percent)
            sorted_df_inc = sorted_df_inc.sort_values(by=f'_sort_{sort_col_inc}', ascending=ascending)
            sorted_df_inc = sorted_df_inc.drop(f'_sort_{sort_col_inc}', axis=1)
        else:
            try:
                sorted_df_inc = sorted_df_inc.sort_values(by=sort_col_inc, ascending=ascending)
            except:
                pass
        
        # Apply styling to percentage columns
        styled_income = sorted_df_inc.style.applymap(
            color_percentages,
            subset=percentage_cols_income
        )
        
        st.dataframe(
            styled_income,
            use_container_width=True,
            height=600
        )
        
        # Add color-coded insights
        st.info("💡 **Tip**: Green percentages indicate positive growth, red indicates negative. Look for consistent positive Revenue YoY and EPS growth.")
    
    with tab4:
        # Balance Sheet columns
        balance_cols = ['Security', 'ROE', 'ROA', 'Asset Turnover', 'D/E Ratio', 
                       'Current Ratio', 'Book Value/Share']
        percentage_cols_balance = ['ROE', 'ROA']
        
        # Column descriptions for tooltips
        balance_tooltips = {
            'ROE': """
**ROE (Return on Equity)**

**Formula:** (Net Income / Shareholders' Equity) × 100

**What it means:**
- How much profit company generates from shareholders' investment
- Measures efficiency of using equity to generate profits
- Shows how well management uses investors' money

**How to use:**
- Higher ROE is better (15%+ is good)
- Declining ROE over time = Warning sign ⚠️
- Compare with industry peers
- ROE > 20% = Excellent ✅
- Consistent high ROE = Competitive advantage
""",
            'ROA': """
**ROA (Return on Assets)**

**Formula:** (Net Income / Total Assets) × 100

**What it means:**
- How efficiently company uses its assets to generate profit
- Shows asset productivity

**How to use:**
- Higher ROA is better
- Declining ROA = Less efficient asset use ⚠️
- Compare with competitors in same industry
- 5%+ is generally good
- Useful for comparing companies of different sizes
""",
            'Asset Turnover': """
**Asset Turnover Ratio**

**Formula:** Total Revenue / Total Assets

**What it means:**
- How efficiently company uses assets to generate revenue
- Higher = More sales per dollar of assets

**How to use:**
- Higher is better (more efficient)
- Declining ratio = Assets not being used effectively ⚠️
- Compare with industry average
- Varies significantly by industry
- Retail: 2-3x, Manufacturing: 0.5-1x
""",
            'D/E Ratio': """
**D/E Ratio (Debt-to-Equity)**

**Formula:** Total Liabilities / Shareholders' Equity

**What it means:**
- How much debt company uses to finance operations
- Measures financial leverage

**How to use:**
- Lower is generally safer (less debt risk)
- D/E < 1 is favorable for most industries
- Rising D/E = Increasing financial risk ⚠️
- High D/E in recession = Dangerous
- Compare with industry norms (utilities naturally higher)
- Moderate debt can amplify returns ✅
""",
            'Current Ratio': """
**Current Ratio**

**Formula:** Current Assets / Current Liabilities

**What it means:**
- Company's ability to pay short-term obligations
- Liquidity measure

**How to use:**
- Ratio > 1.0 = Can cover short-term debts ✅
- Ratio < 1.0 = Potential liquidity issues ⚠️
- 1.5 - 2.0 = Healthy range
- Declining ratio = Weakening liquidity
- Too high (>3) = Inefficient use of assets
""",
            'Book Value/Share': """
**Book Value Per Share**

**Formula:** Total Equity / Total Outstanding Shares

**What it means:**
- Company's net worth per share
- Accounting value (not market value)

**How to use:**
- Higher is better
- Declining book value = Eroding equity ⚠️
- Compare with stock price (P/B Ratio)
- Growing book value = Building shareholder value ✅
- Useful for asset-heavy companies
"""
        }
        
        # Display tooltips in an expander
        with st.expander("ℹ️ **Column Descriptions** - Click to view metric explanations"):
            # Create tabs for each metric
            metric_tabs_balance = st.tabs(['ROE', 'ROA', 'Asset Turnover', 'D/E Ratio', 'Current Ratio', 'Book Value/Share'])
            
            for idx, (tab, metric) in enumerate(zip(metric_tabs_balance, ['ROE', 'ROA', 'Asset Turnover', 'D/E Ratio', 'Current Ratio', 'Book Value/Share'])):
                with tab:
                    st.markdown(balance_tooltips[metric])
        
        # Sorting controls
        col_sort1, col_sort2 = st.columns([3, 1])
        with col_sort1:
            sort_col_bal = st.selectbox("Sort by", balance_cols, key="sort_balance")
        with col_sort2:
            if sort_col_bal in percentage_cols_balance:
                # For percentage columns, use toggle button
                sort_key = f'balance_{sort_col_bal}'
                if sort_key not in st.session_state.sort_states:
                    st.session_state.sort_states[sort_key] = 'desc'
                
                button_label = "↓ Positive High" if st.session_state.sort_states[sort_key] == 'desc' else "↑ Negative High"
                if st.button(button_label, key=f"toggle_{sort_key}"):
                    st.session_state.sort_states[sort_key] = 'asc' if st.session_state.sort_states[sort_key] == 'desc' else 'desc'
                    st.rerun()
                
                ascending = st.session_state.sort_states[sort_key] == 'asc'
            else:
                sort_order = st.radio("Order", ["↓ Descending", "↑ Ascending"], key="order_balance", horizontal=True)
                ascending = sort_order == "↑ Ascending"
        
        # Sort the dataframe
        sorted_df_bal = display_df[balance_cols].copy()
        if sort_col_bal in percentage_cols_balance:
            sorted_df_bal[f'_sort_{sort_col_bal}'] = sorted_df_bal[sort_col_bal].apply(extract_numeric_from_percent)
            sorted_df_bal = sorted_df_bal.sort_values(by=f'_sort_{sort_col_bal}', ascending=ascending)
            sorted_df_bal = sorted_df_bal.drop(f'_sort_{sort_col_bal}', axis=1)
        else:
            try:
                sorted_df_bal = sorted_df_bal.sort_values(by=sort_col_bal, ascending=ascending)
            except:
                pass
        
        # Apply styling to percentage columns
        styled_balance = sorted_df_bal.style.applymap(
            color_percentages,
            subset=percentage_cols_balance
        )
        
        st.dataframe(
            styled_balance,
            use_container_width=True,
            height=600
        )
        
        st.info("💡 **Tip**: Higher ROE and ROA are better. Lower D/E ratio indicates less debt. Current Ratio above 1.0 is generally healthy.")
    
    with tab5:
        # Cash Flow columns
        cashflow_cols = ['Security', 'OCF', 'OCF Margin', 'ICF', 'FCF', 'Free Cash Flow']
        percentage_cols_cashflow = ['OCF Margin']
        
        # Column descriptions for tooltips
        cashflow_tooltips = {
            'OCF': """
**OCF (Operating Cash Flow)**

**Formula:** Net Income + Depreciation & Amortization - Changes in Working Capital

**What it means:**
- Actual cash generated from core business operations
- Most important cash flow metric
- Shows real cash-generating ability

**How to use:**
- Positive OCF = Company generates cash ✅
- Declining OCF = Warning sign ⚠️
- Should grow with revenue over time
- Compare with net income (should be close)
- More reliable than net income (harder to manipulate)
""",
            'OCF Margin': """
**Operating Cash Flow Margin**

**Formula:** (Operating Cash Flow / Revenue) × 100

**What it means:**
- Percentage of revenue converted to cash
- Shows cash generation efficiency

**How to use:**
- Higher is better (20%+ is excellent)
- Declining margin = Less efficient cash generation ⚠️
- Compare with net profit margin
- Should be higher than net margin (ideal)
- 15%+ is generally healthy ✅
""",
            'ICF': """
**ICF (Investing Cash Flow)**

**What it means:**
- Cash used for investments in assets
- Includes: Equipment purchases, acquisitions, investments

**How to use:**
- Usually negative (company investing in growth) ✅
- Large negative = Heavy investment phase
- Positive = Selling assets (may indicate trouble) ⚠️
- Compare with operating cash flow
- Should be funded by operating cash flow ideally
""",
            'FCF': """
**FCF (Financing Cash Flow)**

**What it means:**
- Cash from/to shareholders and creditors
- Includes: Debt issued/repaid, dividends, share buybacks

**How to use:**
- Negative = Paying dividends/debt (can be good) ✅
- Positive = Raising debt/equity (dilution risk) ⚠️
- Look at the components to understand full story
- Consistent dividend payments = Strong ✅
- Frequent equity raises = Potential red flag
""",
            'Free Cash Flow': """
**Free Cash Flow**

**Formula:** Operating Cash Flow - Capital Expenditures

**What it means:**
- Cash available after maintaining/expanding operations
- Most important metric for valuation
- Cash available for dividends, buybacks, debt reduction

**How to use:**
- Positive FCF is crucial ✅ ✅ ✅
- Growing FCF = Strong business
- Negative FCF = Unsustainable (unless growth phase) ⚠️
- Use for DCF valuation
- Companies with strong FCF can:
  • Pay dividends
  • Buy back shares
  • Reduce debt
  • Invest in growth
"""
        }
        
        # Display tooltips in an expander
        with st.expander("ℹ️ **Column Descriptions** - Click to view metric explanations"):
            # Create tabs for each metric
            metric_tabs = st.tabs(['OCF', 'OCF Margin', 'ICF', 'FCF', 'Free Cash Flow'])
            
            for idx, (tab, metric) in enumerate(zip(metric_tabs, ['OCF', 'OCF Margin', 'ICF', 'FCF', 'Free Cash Flow'])):
                with tab:
                    st.markdown(cashflow_tooltips[metric])
        
        # Sorting controls
        col_sort1, col_sort2 = st.columns([3, 1])
        with col_sort1:
            sort_col_cf = st.selectbox("Sort by", cashflow_cols, key="sort_cashflow")
        with col_sort2:
            if sort_col_cf in percentage_cols_cashflow:
                # For percentage columns, use toggle button
                sort_key = f'cashflow_{sort_col_cf}'
                if sort_key not in st.session_state.sort_states:
                    st.session_state.sort_states[sort_key] = 'desc'
                
                button_label = "↓ Positive High" if st.session_state.sort_states[sort_key] == 'desc' else "↑ Negative High"
                if st.button(button_label, key=f"toggle_{sort_key}"):
                    st.session_state.sort_states[sort_key] = 'asc' if st.session_state.sort_states[sort_key] == 'desc' else 'desc'
                    st.rerun()
                
                ascending = st.session_state.sort_states[sort_key] == 'asc'
            else:
                sort_order = st.radio("Order", ["↓ Descending", "↑ Ascending"], key="order_cashflow", horizontal=True)
                ascending = sort_order == "↑ Ascending"
        
        # Sort the dataframe
        sorted_df_cf = display_df[cashflow_cols].copy()
        if sort_col_cf in percentage_cols_cashflow:
            sorted_df_cf[f'_sort_{sort_col_cf}'] = sorted_df_cf[sort_col_cf].apply(extract_numeric_from_percent)
            sorted_df_cf = sorted_df_cf.sort_values(by=f'_sort_{sort_col_cf}', ascending=ascending)
            sorted_df_cf = sorted_df_cf.drop(f'_sort_{sort_col_cf}', axis=1)
        else:
            try:
                sorted_df_cf = sorted_df_cf.sort_values(by=sort_col_cf, ascending=ascending)
            except:
                pass
        
        # Apply styling to percentage columns
        styled_cashflow = sorted_df_cf.style.applymap(
            color_percentages,
            subset=percentage_cols_cashflow
        )
        
        st.dataframe(
            styled_cashflow,
            use_container_width=True,
            height=600
        )
        
        st.info("💡 **Tip**: Positive Free Cash Flow is crucial. It indicates the company generates enough cash to invest, pay dividends, or reduce debt.")
    
    # Export portfolio data
    st.subheader("💾 Export Portfolio")
    csv_data = display_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Portfolio as CSV",
        data=csv_data,
        file_name=f"portfolio_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

def display_comprehensive_table(symbol, info, hist_data, financials):
    """Display the comprehensive metrics table"""
    st.subheader("📊 Comprehensive Financial Overview")
    
    # Create the metrics
    metrics = create_comprehensive_metrics_table(symbol, info, hist_data, financials)
    
    # Company Overview Section
    st.markdown("### Company Overview")
    overview_data = {
        'Industry': [metrics['Industry']],
        'Ticker': [metrics['Ticker']],
        'Current Price': [metrics['Current Price']],
        'Market Cap': [metrics['Market Cap']]
    }
    st.dataframe(pd.DataFrame(overview_data), use_container_width=True)
    
    # Valuation Ratios Section
    st.markdown("### Valuation Ratios")
    
    # Help information for valuation metrics
    with st.expander("ℹ️ Metric Explanations"):
        st.markdown("""
        **P/E Ratio**: Share Price / Earnings Per Share (EPS). 
        Indicates how much investors are willing to pay for each dollar of a company's earnings. 
        For example, if AAPL's P/E ratio is 18, investors are willing to pay $18 for the company to earn $1 per year.
        A lower P/E often suggests undervaluation, but always compare it to industry peers.
        
        **P/B Ratio**: Share Price / Book Value Per Share. 
        Compares a company's market value to its book value (net asset value).
        A P/B ratio less than 1 might suggest undervaluation, but it's crucial to understand why.
        
        **P/S Ratio**: Share Price / Revenue Per Share. 
        Compares a company's market value to its total revenue.
        A lower P/S is generally better but consider the company's growth potential.

        **PEG Ratio**: P/E Ratio / Earnings Growth Rate. 
        Considers the P/E ratio in relation to the company's expected earnings growth.
        A PEG ratio of 1 or less is often considered favorable, suggesting a reasonable price for the expected growth.
        
        **Forward P/E**: Estimated future P/E ratio based on projected earnings. 
        Useful for predicting future earnings potential.
        A lower Forward P/E is generally better, but consider the company's growth potential.
        
        **Dividend Yield**: Measures the annual return on a stock from dividends.
        Dividend Yield = Annual Dividend/Stock price
        A higher yield is better, but ensure the company can sustain its dividend.
        
        **Dividend Coverage**: Net Income / Total Dividends Paid.
        Indicates how many times a company can pay its dividends from its earnings.
        """)
    
    valuation_data = {
        'P/E Ratio': [metrics['P/E Ratio']],
        'PEG Ratio': [metrics['PEG Ratio']],
        'P/B Ratio': [metrics['P/B Ratio']],
        'P/S Ratio': [metrics['P/S Ratio']],
        'Forward P/E': [metrics['Forward P/E']],
        'Dividend Yield': [metrics['Dividend Yield']],
        'Dividend Coverage': [metrics['Dividend Coverage']]
    }
    st.dataframe(pd.DataFrame(valuation_data), use_container_width=True)
    
    # Income Statement - Profitability Metrics
    st.markdown("### Income Statement - Profitability Metrics")

    # Help information for profitability metrics
    with st.expander("ℹ️ Metric Explanations"):
            st.markdown("""
            **REVENUE**: The total amount of money a company generates from its core operations (selling goods or services) before deducting any expenses.
            Metrics to Look For:
                Revenue Growth: Consistent year-over-year or quarter-over-quarter growth indicates a growing business. Look for trends over several periods.
                Revenue per Share: Total revenue divided by the number of outstanding shares. Helps contextualize revenue on a per-share basis.
            
            **Revenue YoY**: Year-over-Year Growth: 
            Compares current year's revenue to the previous year's revenue. 
            How much revenue a company has generated from its core operations from the past years.
            A positive YoY growth suggests expansion.
            
            **RPS**: Total revenue divided by the number of outstanding shares. 
            How much revenue a company has generated from its core operations per share.
            Growth Indicator: Rising RPS over time(5 years) indicates growing sales and potential market dominance.
                📉 Rising RPS + Rising EPS = Strong business growth, efficient operations
                📉 Rising RPS + Falling EPS = Revenue growth without profit – may be due to cost pressures
                📉 Flat RPS over years = Market saturation, declining competitiveness
                📉 Declining RPS = Losing market share or product weakness.

            **EPS*: (Net Income -	Preferred Dividends)/Shares Outstanding (Basic Average)
            If a company's earnings per share is less than cash flow per share over long term, investors need to be cautious and find out why.
            
            **Cash flow per share**: Cash Flow per Share =	(Net Cash Flow from Operating Activities - Preferred Dividends)/Shares Outstanding (Basic Average)
            If a company's cash flow per share is less than earnings per share over long term, investors need to be cautious and find out why.
            
            **Operating Margin**: Operating Margin = Operating Income / Total Revenue
            A higher operating margin indicates better efficiency in converting sales into profits.
            Be aware of declining Operating Margin from the past years.
            
            **Net Profit Margin**: Net Profit Margin = Net Income / Total Revenue
            A higher net profit margin indicates better efficiency in converting sales into profits.
            Be aware of declining Net Profit Margin from the past years.
            
            **Net Profit Margin**: Net Profit Margin = Net Income / Total Revenue
            A higher net profit margin indicates better efficiency in converting sales into profits.
            Be aware of declining Net Profit Margin from the past years.
            
            **ROE**: Return on Equity = Net Income / Shareholders' Equity
            A higher ROE indicates better efficiency in using shareholders' equity to generate profits.
            Be aware of declining ROE from the past years.
            How much profit a company generates from shareholder's investment
            It determines how effectively investors money are managed.
            
            **ROA**: Return on Assets = Net Income / Total Assets
            A higher ROA indicates better efficiency in using assets to generate profits.
            Be aware of declining ROA from the past years.
            How well a company uses its assets to generate profit.
            Useful for comparing how efficiently companies uses their assets to generate profits.
            """)

    
    income_data = {
        'Revenue': [metrics['Revenue']],
        'Revenue YoY': [metrics['Revenue YoY']],
        'Revenue per Share': [metrics['Revenue per Share']],
        'EPS': [metrics['EPS']],
        'Cash Flow per Share': [metrics['Cash Flow per Share']],
        'Gross Profit Margin': [metrics['Gross Profit Margin']],
        'Operating Margin': [metrics['Operating Margin']],
        'Net Profit Margin': [metrics['Net Profit Margin']],
        'ROE': [metrics['ROE']],
        'ROA': [metrics['ROA']]
    }
    st.dataframe(pd.DataFrame(income_data), use_container_width=True)
    
    # Balance Sheet
    st.markdown("### Balance Sheet")

    # Help information for profitability metrics
    with st.expander("ℹ️ Metric Explanations"):
            st.markdown("""
            **Asset Turnover Ratio**: Asset Turnover = Total Revenue / Total Assets
            A higher asset turnover ratio indicates better efficiency in using assets to generate revenue.
            Be aware of declining Asset Turnover Ratio from the past years.
            Useful for comparing how efficiently companies uses their assets to generate revenue.
            
            **D/E Ratio**: Debt-to-Equity Ratio = Total Liabilities / Total Equity
            A higher D/E ratio indicates more debt relative to equity, which can increase financial risk.
            Be aware of rising D/E ratio from the past years.
            Useful for comparing how much debt a company has relative to its equity.
            Total Liabilities / Total Equity. Measures the proportion of a company's financing that comes from debt versus equity. A higher ratio indicates higher financial leverage.
            Total Liabilities / Shareholders' Equity. Measures the proportion of debt a company uses to finance its assets relative to the value of shareholders' equity. 
            A high D/E ratio can indicate higher financial risk. 
            Generally, a ratio below 1 is favorable, but it varies by industry.

            **Current Ratio**: Current Ratio = Current Assets / Current Liabilities
            A higher current ratio indicates more liquidity and the ability to meet short-term obligations.
            Be aware of declining Current Ratio from the past years.
            How much liquidity a company has relative to its current liabilities.
            Useful for comparing how much liquidity a company has relative to its current liabilities.
            Current Assets / Current Liabilities. Measures the ability of a company to meet its short-term obligations with its current assets. A higher ratio indicates better liquidity.

            **Book Value per Share**: Book Value per Share = Total Equity / Total Outstanding Shares
            A higher book value per share indicates more equity per share, which can be a sign of financial strength.
            Be aware of declining Book Value per Share from the past years.
            How much equity a company has per share.
            Useful for comparing how much equity a company has per share.
            Total Equity / Total Outstanding Shares. Measures the value of a company's equity per share. A higher ratio indicates more equity per share.
          """)
    
    
    balance_data = {
        'Asset Turnover': [metrics['Asset Turnover']],
        'D/E Ratio': [metrics['D/E Ratio']],
        'Current Ratio': [metrics['Current Ratio']],
        'Book Value per Share': [metrics['Book Value per Share']]
    }
    st.dataframe(pd.DataFrame(balance_data), use_container_width=True)
    
    # Cash Flow Statement
    st.markdown("### Cash Flow Statement")
    
    # Help information for balance sheet metrics
    with st.expander("ℹ️ Metric Explanations"):
            st.markdown("""  
            **Free Cash Flow**: Free Cash Flow = Operating Cash Flow - Capital Expenditures
            A positive free cash flow indicates that a company has enough cash to invest in growth, pay dividends, or reduce debt.
            Be aware of declining Free Cash Flow from the past years.
            Useful for comparing how much cash a company has after paying for its operating expenses and capital expenditures.
            Operating Cash Flow - Capital Expenditures. Measures the cash flow a company has after paying for its operating expenses and capital expenditures. A positive ratio indicates that a company has enough cash to invest in growth, pay dividends, or reduce debt.

            **Free Cash Flow Margin**: Free Cash Flow Margin = Free Cash Flow / Total Revenue
            A higher free cash flow margin indicates better efficiency in generating cash from operations.
            Be aware of declining Free Cash Flow Margin from the past years.
            Useful for comparing how much cash a company has after paying for its operating expenses and capital expenditures relative to its total revenue.
            Free Cash Flow / Total Revenue. Measures the cash flow a company has after paying for its operating expenses and capital expenditures relative to its total revenue. A higher ratio indicates better efficiency in generating cash from operations.

            **Operating Cash Flow**: Operating Cash Flow = Net Income + Depreciation & Amortization - Changes in Working Capital
            A positive operating cash flow indicates that a company is generating cash from its operations.
            Be aware of declining Operating Cash Flow from the past years.
            Useful for comparing how much cash a company has from its operations.
            Net Income + Depreciation & Amortization - Changes in Working Capital. Measures the cash flow a company has from its operations. A positive ratio indicates that a company is generating cash from its operations.

            **Operating Cash Flow Margin**: Operating Cash Flow Margin = Operating Cash Flow / Total Revenue
            A higher operating cash flow margin indicates better efficiency in generating cash from operations.
            Be aware of declining Operating Cash Flow Margin from the past years.
            Useful for comparing how much cash a company has from its operations relative to its total revenue.
            Operating Cash Flow / Total Revenue. Measures the cash flow a company has from its operations relative to its total revenue. A higher ratio indicates better efficiency in generating cash from operations.

            **Investing Cash Flow**: Investing Cash Flow = Capital Expenditures - Depreciation & Amortization
            A positive investing cash flow indicates that a company is investing in its future growth.
            Be aware of declining Investing Cash Flow from the past years.
            Useful for comparing how much cash a company is investing in its future growth.
            Capital Expenditures - Depreciation & Amortization. Measures the cash flow a company is investing in its future growth. A positive ratio indicates that a company is investing in its future growth.
            
            **Financing Cash Flow**: Financing Cash Flow = Dividends Paid + Share Repurchases - Issuance of New Debt
            A positive financing cash flow indicates that a company is raising capital.
            Be aware of declining Financing Cash Flow from the past years.
            Useful for comparing how much cash a company is raising capital.
            Dividends Paid + Share Repurchases - Issuance of New Debt. Measures the cash flow a company is raising capital. A positive ratio indicates that a company is raising capital.

            **Free Cash Flow**: Free Cash Flow = Operating Cash Flow - Capital Expenditures
            A positive free cash flow indicates that a company has enough cash to invest in growth, pay dividends, or reduce debt.
            Be aware of declining Free Cash Flow from the past years.
            Useful for comparing how much cash a company has after paying for its operating expenses and capital expenditures.
            Operating Cash Flow - Capital Expenditures. Measures the cash flow a company has after paying for its operating expenses and capital expenditures. A positive ratio indicates that a company has enough cash to invest in growth, pay dividends, or reduce debt.
            """)
    
    
    cashflow_data = {
        'Operating Cash Flow': [metrics['Operating Cash Flow']],
        'Operating Cash Flow Margin': [metrics['Operating Cash Flow Margin']],
        'Investing Cash Flow': [metrics['Investing Cash Flow']],
        'Financing Cash Flow': [metrics['Financing Cash Flow']],
        'Free Cash Flow': [metrics['Free Cash Flow']]
    }
    st.dataframe(pd.DataFrame(cashflow_data), use_container_width=True)
    
    return metrics

# Main application logic
if page == "My Portfolio":
    # Industry selector: My Portfolio (default) or industries from admin stock_industry table
    admin_industries = []
    if db and hasattr(db, "admin_get_all_industries"):
        admin_industries = db.admin_get_all_industries()
    view_options = ["My Portfolio"] + (admin_industries if admin_industries else [])
    selected_view = st.selectbox(
        "View",
        options=view_options,
        key="portfolio_view_select",
        help="Select 'My Portfolio' for your portfolio stocks, or an industry to see all stocks in that industry."
    )

    if selected_view != "My Portfolio":
        # Show stocks by industry (from admin stock_industry table)
        st.subheader(f"📋 {selected_view}")
        industry_stocks = db.admin_get_stocks_by_industry(selected_view) if db and hasattr(db, "admin_get_stocks_by_industry") else []
        if not industry_stocks:
            st.info(f"No stocks assigned to **{selected_view}** yet. Use the 'By Industry' page to add stocks to industries.")
        else:
            st.write(f"**{len(industry_stocks)} stocks** in this industry")
            st.markdown("""
            <style>
            .stock-link { color: inherit; font-weight: bold; text-decoration: none; cursor: pointer; }
            .stock-link:hover { color: #1f77b4; text-decoration: underline; }
            </style>
            """, unsafe_allow_html=True)
            num_cols = 10
            symbols_only = [item["symbol"] for item in industry_stocks]
            for row_start in range(0, len(symbols_only), num_cols):
                cols = st.columns(num_cols)
                row_symbols = symbols_only[row_start:row_start + num_cols]
                for col, symbol in zip(cols, row_symbols):
                    with col:
                        st.markdown(
                            f'<a href="?symbol={symbol}&analyze=true" target="_blank" class="stock-link" title="Analyze {symbol}">{symbol}</a>',
                            unsafe_allow_html=True
                        )

            if st.button("Load portfolio data for this industry", key=f"industry_load_{selected_view}"):
                with st.spinner(f"Fetching data for {len(symbols_only)} stocks in {selected_view}..."):
                    industry_portfolio_data = fetch_portfolio_data(symbols_only, use_database)
                if industry_portfolio_data:
                    st.session_state["industry_portfolio_data"] = industry_portfolio_data
                    st.session_state["industry_portfolio_loaded_for"] = selected_view
                    st.rerun()
                else:
                    st.error("Could not load portfolio data. Please check stock symbols and try again.")

            if st.session_state.get("industry_portfolio_loaded_for") == selected_view and st.session_state.get("industry_portfolio_data"):
                st.markdown("---")
                st.subheader(f"Portfolio data: {selected_view}")
                display_portfolio_grid(st.session_state["industry_portfolio_data"])
    else:
        pass  # My Portfolio: no portfolio display (use View selector + industry / refresh sections)

    # Portfolio page logic (overview/charts) — only when viewing My Portfolio
    if selected_view == "My Portfolio" and (analyze_button or st.session_state.get('portfolio_loaded', False)):
        if st.session_state.portfolio:
            # Check if real-time updates are enabled (from previous render)
            # If real-time is enabled and data is cached, skip full refetch to avoid updating financial statements
            enable_realtime = st.session_state.get('enable_realtime_overview', False)
            cached_portfolio_data = st.session_state.get('cached_portfolio_data', None)
            portfolio_symbols_match = (
                cached_portfolio_data is not None and 
                len(cached_portfolio_data) == len(st.session_state.portfolio) and
                all(item.get('symbol') in st.session_state.portfolio for item in cached_portfolio_data)
            )
            
            # Only use cached data if:
            # 1. Real-time is enabled (auto-refresh, not manual refresh)
            # 2. Manual refresh button was NOT clicked (analyze_button is False)
            # 3. Cached data exists and matches current portfolio
            should_use_cache = enable_realtime and not analyze_button and portfolio_symbols_match
            
            if should_use_cache:
                # Use cached data when real-time is enabled to avoid refetching financial statements
                portfolio_data = cached_portfolio_data
            else:
                # Fetch fresh data (first load, manual refresh, or when cache is invalid)
                with st.spinner(f"Loading portfolio data for {len(st.session_state.portfolio)} stocks..."):
                    portfolio_data = fetch_portfolio_data(st.session_state.portfolio, use_database)
                    # Cache the portfolio data in session state
                    st.session_state.cached_portfolio_data = portfolio_data
                    st.session_state.portfolio_loaded = True
            
            if portfolio_data:
                display_portfolio_grid(portfolio_data)
            else:
                st.error("Could not load portfolio data. Please check your stock symbols.")
        else:
            st.info("👈 Add stocks to your portfolio using the sidebar")
    elif selected_view == "My Portfolio":
        if st.session_state.portfolio:
            st.info("👈 Click 'Refresh Portfolio Data' to load your portfolio analysis")
        else:
            st.info("👈 Add stocks to your portfolio using the sidebar")

elif page == "DCA":
    # DCA page - Display recently added stocks
    st.subheader("💰 DCA Stocks")
    
    # Display dollar amount if set
    if st.session_state.get('dca_dollar_amount', 0.0) > 0:
        st.info(f"💵 **DCA Amount**: ${st.session_state.dca_dollar_amount:,.2f} per period")
    
    if st.session_state.dca_stocks:
        # Industry filter for DCA list
        dca_industry_map = {}
        if db and hasattr(db, "get_stock_info"):
            for sym in st.session_state.dca_stocks:
                info = db.get_stock_info(sym)
                if info and info.get("industry"):
                    dca_industry_map[sym] = info["industry"]
        dca_industries = sorted(set(dca_industry_map.values()))
        dca_industry_filter = st.selectbox(
            "Filter by industry",
            options=["All"] + dca_industries,
            key="dca_industry_filter",
        )
        if dca_industry_filter != "All":
            dca_display = [s for s in st.session_state.dca_stocks if dca_industry_map.get(s) == dca_industry_filter]
        else:
            dca_display = st.session_state.dca_stocks
        st.write(f"**{len(st.session_state.dca_stocks)} stock(s) in your DCA list**" + (f" — showing {len(dca_display)} in selected industry" if dca_industry_filter != "All" else ""))
        
        # Display stocks in a nice grid format
        st.markdown("""
        <style>
        .dca-stock-item {
            display: inline-block;
            padding: 10px 15px;
            margin: 5px;
            border-radius: 8px;
            background-color: rgba(0, 0, 0, 0.05);
            border: 1px solid rgba(0, 0, 0, 0.1);
        }
        .dca-stock-item:hover {
            background-color: rgba(0, 0, 0, 0.1);
            border-color: #1f77b4;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Display stocks in columns (use dca_display for industry-filtered view)
        num_cols = 6
        for row_start in range(0, len(dca_display), num_cols):
            cols = st.columns(num_cols)
            row_symbols = dca_display[row_start:row_start + num_cols]
            
            for col, symbol in zip(cols, row_symbols):
                with col:
                    # Create a container for each stock with remove button
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        # Make stock symbol clickable link
                        st.markdown(
                            f'<a href="?symbol={symbol}&analyze=true" target="_blank" class="stock-link" title="Click to analyze {symbol}">{symbol}</a>',
                            unsafe_allow_html=True
                        )
                    with col2:
                        if st.button("×", key=f"remove_dca_{symbol}", help=f"Remove {symbol}"):
                            st.session_state.dca_stocks.remove(symbol)
                            st.rerun()
        
        st.markdown("---")
        
        # DCA Backtest Section
        if st.session_state.get('dca_dollar_amount', 0.0) > 0 and len(st.session_state.dca_stocks) > 0:
            st.subheader("📊 DCA Backtest")
            
            # Date range selection
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "Start Date",
                    value=datetime.now().date() - timedelta(days=365*2),  # Default: 2 years ago
                    max_value=datetime.now().date()
                )
            with col2:
                end_date = st.date_input(
                    "End Date",
                    value=datetime.now().date(),
                    max_value=datetime.now().date()
                )
            
            # Run backtest button
            if st.button("🚀 Run DCA Backtest", type="primary", key="run_dca_backtest"):
                with st.spinner("Running backtest... This may take a moment."):
                    hist_score, hist_equal, error = backtest_dca(
                        st.session_state.dca_stocks,
                        st.session_state.dca_dollar_amount,
                        start_date,
                        end_date,
                        use_database=False  # Use fresh data for backtest
                    )
                    
                    if error:
                        st.error(f"Backtest error: {error}")
                    elif hist_score is not None and hist_equal is not None:
                        st.session_state.dca_backtest_results = {
                            'score_weighted': hist_score,
                            'equal_weight': hist_equal,
                            'start_date': start_date,
                            'end_date': end_date
                        }
                        st.success("✅ Backtest completed!")
                        st.rerun()
            
            # Display backtest results if available
            if 'dca_backtest_results' in st.session_state:
                results = st.session_state.dca_backtest_results
                hist_score = results['score_weighted']
                hist_equal = results['equal_weight']
                
                # Summary metrics
                total_days = len(hist_score)
                daily_invest = st.session_state.dca_dollar_amount
                total_invested = daily_invest * total_days
                final_value_score = hist_score['PortfolioValue'].iloc[-1]
                final_value_equal = hist_equal['PortfolioValue'].iloc[-1]
                
                roi_score = (final_value_score - total_invested) / total_invested * 100 if total_invested > 0 else 0
                roi_equal = (final_value_equal - total_invested) / total_invested * 100 if total_invested > 0 else 0
                
                years = total_days / 252.0
                cagr_score = ((final_value_score / total_invested) ** (1.0/years) - 1.0) * 100 if total_invested > 0 and years > 0 else 0
                cagr_equal = ((final_value_equal / total_invested) ** (1.0/years) - 1.0) * 100 if total_invested > 0 and years > 0 else 0
                
                # Display metrics
                st.markdown("### 📈 Backtest Results")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Invested", f"${total_invested:,.2f}")
                    st.metric("Days", total_days)
                
                with col2:
                    st.metric("Score-Weighted Final Value", f"${final_value_score:,.2f}", 
                             f"{roi_score:+.2f}% ROI")
                    st.metric("CAGR", f"{cagr_score:.2f}%")
                
                with col3:
                    st.metric("Equal-Weight Final Value", f"${final_value_equal:,.2f}",
                             f"{roi_equal:+.2f}% ROI")
                    st.metric("CAGR", f"{cagr_equal:.2f}%")
                
                with col4:
                    outperformance = final_value_score - final_value_equal
                    outperformance_pct = (outperformance / final_value_equal) * 100 if final_value_equal > 0 else 0
                    st.metric("Outperformance", f"${outperformance:,.2f}", f"{outperformance_pct:+.2f}%")
                
                # Portfolio value chart
                st.markdown("### 📊 Portfolio Value Over Time")
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=hist_score.index,
                    y=hist_score['PortfolioValue'],
                    mode='lines',
                    name='Score-Weighted DCA',
                    line=dict(color='#1f77b4', width=2)
                ))
                
                fig.add_trace(go.Scatter(
                    x=hist_equal.index,
                    y=hist_equal['PortfolioValue'],
                    mode='lines',
                    name='Equal-Weight DCA',
                    line=dict(color='#ff7f0e', width=2, dash='dash')
                ))
                
                # Add total invested line
                invested_line = [total_invested] * len(hist_score)
                fig.add_trace(go.Scatter(
                    x=hist_score.index,
                    y=invested_line,
                    mode='lines',
                    name='Total Invested',
                    line=dict(color='gray', width=1, dash='dot')
                ))
                
                fig.update_layout(
                    title="Portfolio Value Over Time (Score-weighted vs Equal-weight DCA)",
                    xaxis_title="Date",
                    yaxis_title="Portfolio Value (USD)",
                    hovermode='x unified',
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Allocation weights over time
                st.markdown("### 🎯 Allocation Weights Over Time")
                
                # Sample dates for weight visualization
                sample_dates = hist_score.index[::max(1, len(hist_score)//10)]
                weight_data = []
                
                for dt in sample_dates:
                    row = {'Date': dt}
                    for symbol in st.session_state.dca_stocks:
                        weight_col = f'Weight_{symbol}'
                        if weight_col in hist_score.columns:
                            row[symbol] = hist_score.loc[dt, weight_col] * 100  # Convert to percentage
                    weight_data.append(row)
                
                if weight_data:
                    weight_df = pd.DataFrame(weight_data).set_index('Date')
                    
                    fig_weights = go.Figure()
                    for symbol in st.session_state.dca_stocks:
                        if symbol in weight_df.columns:
                            fig_weights.add_trace(go.Scatter(
                                x=weight_df.index,
                                y=weight_df[symbol],
                                mode='lines+markers',
                                name=symbol,
                                stackgroup='one'
                            ))
                    
                    fig_weights.update_layout(
                        title="Allocation Weights Over Time (Stacked)",
                        xaxis_title="Date",
                        yaxis_title="Weight (%)",
                        hovermode='x unified',
                        height=400
                    )
                    
                    st.plotly_chart(fig_weights, use_container_width=True)
                
                # Final portfolio breakdown
                st.markdown("### 💼 Final Portfolio Breakdown (Score-Weighted)")
                
                final_shares = {}
                final_prices = {}
                final_values = {}
                
                for symbol in st.session_state.dca_stocks:
                    shares_col = f'Shares_{symbol}'
                    if shares_col in hist_score.columns:
                        final_shares[symbol] = hist_score[shares_col].iloc[-1]
                        # Get final price
                        try:
                            ticker = yf.Ticker(symbol)
                            hist = ticker.history(period="1d")
                            if not hist.empty:
                                final_prices[symbol] = hist['Close'].iloc[-1]
                                final_values[symbol] = final_shares[symbol] * final_prices[symbol]
                        except:
                            pass
                
                if final_values:
                    breakdown_df = pd.DataFrame({
                        'Symbol': list(final_values.keys()),
                        'Shares': [final_shares.get(s, 0) for s in final_values.keys()],
                        'Price': [final_prices.get(s, 0) for s in final_values.keys()],
                        'Value': list(final_values.values())
                    })
                    breakdown_df['Weight %'] = (breakdown_df['Value'] / breakdown_df['Value'].sum() * 100).round(2)
                    breakdown_df = breakdown_df.sort_values('Value', ascending=False)
                    
                    st.dataframe(breakdown_df, use_container_width=True)
                    
                    # Pie chart
                    fig_pie = go.Figure(data=[go.Pie(
                        labels=breakdown_df['Symbol'],
                        values=breakdown_df['Value'],
                        hole=0.3,
                        textinfo='label+percent',
                        textposition='outside'
                    )])
                    fig_pie.update_layout(
                        title="Final Portfolio Value Breakdown",
                        height=400
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
        
        # Show recent additions info
        if len(st.session_state.dca_stocks) > 0:
            st.info(f"💡 **Tip**: Click on any stock symbol to analyze it in a new tab. Use the sidebar to add more stocks.")
    else:
        st.info("👈 Add stock symbols in the sidebar to get started with your DCA strategy!")
        st.markdown("""
        ### How to use DCA:
        1. Enter stock symbols separated by commas in the sidebar (e.g., `AAPL, GOOGL, MSFT`)
        2. Click "Add Stocks" to add them to your DCA list
        3. View all your DCA stocks on this page
        4. Click on any stock symbol to analyze it
        5. Use "Clear All Stocks" to reset your list
        """)

elif page == "Automation" and automation_button and automation_ticker:
    # Automation page logic
    st.header(f"🤖 Automated Trading Analysis: {automation_ticker}")
    
    # Validate ticker
    is_valid, error_msg = validate_stock_symbol(automation_ticker)
    
    if not is_valid:
        st.error(error_msg)
    else:
        with st.spinner(f"Scanning {automation_ticker} and analyzing technical indicators..."):
            # Run scanner
            setup_info, trade_params, error = scan_stock(automation_ticker, days=60)
            
            if error:
                st.error(f"Error: {error}")
            else:
                # Display setup information
                if setup_info and isinstance(setup_info, dict):
                    indicators = setup_info.get('indicators', {})
                    setup_detected = setup_info.get('setup_detected', False)
                    setup_details = setup_info.get('details', [])
                    definitions = setup_info.get('definitions', {})
                    
                    # Technical Indicators Summary
                    st.subheader("📊 Technical Indicators")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Current Price", f"${indicators.get('current_price', 0):.2f}")
                    with col2:
                        st.metric("20-day SMA", f"${indicators.get('sma_20', 0):.2f}" if indicators.get('sma_20') else "N/A")
                    with col3:
                        rsi_value = indicators.get('rsi', 0)
                        st.metric("RSI (14)", f"{rsi_value:.2f}" if rsi_value else "N/A")
                    with col4:
                        st.metric("ATR", f"${indicators.get('atr', 0):.2f}" if indicators.get('atr') else "N/A")
                    
                    # Setup Detection
                    st.subheader("🔍 Setup Detection")
                    if setup_detected:
                        st.success("✅ Trading Setup Detected!")
                        for detail in setup_details:
                            st.write(f"• {detail}")
                    else:
                        st.warning("⚠️ Setup conditions not fully met")
                        for detail in setup_details:
                            st.write(f"• {detail}")
                    
                    # Definitions
                    with st.expander("📚 Indicator Definitions"):
                        for term, definition in definitions.items():
                            st.markdown(f"**{term}:** {definition}")
                    
                    # Display Trade Parameters
                    if trade_params:
                        st.subheader("🎯 Trade Setups (5 Timeframes)")
                        
                        # Convert setups to DataFrame for display
                        setups_list = trade_params.get('setups', [])
                        if setups_list:
                            # Prepare DataFrame
                            df_data = []
                            for setup in setups_list:
                                df_data.append({
                                    'Timeframe': setup['timeframe'],
                                    'Duration': setup['duration'],
                                    'Entry': f"${setup['entry']:.2f}",
                                    'Stop Loss': f"${setup['stop_loss']:.2f} ({setup['stop_loss_pct']:.2f}%)",
                                    'Target 1 (1:1)': f"${setup['target_1']:.2f} (+{setup['target_1_pct']:.2f}%)",
                                    'Target 2 (2:1)': f"${setup['target_2']:.2f} (+{setup['target_2_pct']:.2f}%)",
                                    'Risk/Reward': f"{setup['risk_reward_1']} / {setup['risk_reward_2']}"
                                })
                            
                            setups_df = pd.DataFrame(df_data)
                            st.dataframe(setups_df, use_container_width=True, hide_index=True)
                            
                            # AI Analysis for each setup
                            st.subheader("🤖 AI-Powered Market Sentiment Analysis")
                            
                            # Get news and fundamentals
                            try:
                                ticker = yf.Ticker(automation_ticker)
                                info = ticker.info
                                company_name = info.get('longName', automation_ticker)
                                
                                # Get news (last 5 articles)
                                try:
                                    news_items = ticker.news[:5] if hasattr(ticker, 'news') and ticker.news else []
                                except:
                                    news_items = []
                                
                                # Prepare news summary
                                news_summary = ""
                                if news_items:
                                    news_summary = "\n".join([
                                        f"- {item.get('title', 'N/A')} ({item.get('provider', 'Unknown')})"
                                        for item in news_items[:5]
                                    ])
                                else:
                                    news_summary = "No recent news available"
                                
                                # Fundamental data
                                pe_ratio = info.get('trailingPE')
                                market_cap = info.get('marketCap')
                                revenue = info.get('totalRevenue')
                                profit_margin = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else None
                                
                                # Generate AI analysis for each timeframe (Ollama)
                                for i, setup in enumerate(setups_list):
                                    with st.expander(f"🧠 AI Analysis: {setup['timeframe']}", expanded=(i==0)):
                                        with st.spinner(f"Analyzing {setup['timeframe']} setup..."):
                                            try:
                                                user_prompt = f"""As a financial analyst, analyze the following trading setup for {company_name} ({automation_ticker}).

**Technical Setup:**
- Timeframe: {setup['timeframe']}
- Entry Price: ${setup['entry']:.2f}
- Stop Loss: ${setup['stop_loss']:.2f} ({setup['stop_loss_pct']:.2f}% below entry)
- Target 1: ${setup['target_1']:.2f} (1:1 Risk-to-Reward)
- Target 2: ${setup['target_2']:.2f} (2:1 Risk-to-Reward)
- Current Price: ${indicators.get('current_price', 0):.2f}
- RSI: {indicators.get('rsi', 'N/A')}
- Price near 20-day SMA: {'Yes' if setup_detected else 'No'}

**Company Fundamentals:**
- Market Cap: ${market_cap/1e9:.2f}B if market_cap else 'N/A'
- P/E Ratio: {pe_ratio if pe_ratio else 'N/A'}
- Profit Margin: {f"{profit_margin:.2f}%" if profit_margin else 'N/A'}
- Revenue: ${revenue/1e9:.2f}B if revenue else 'N/A'
- Sector: {info.get('sector', 'N/A')}
- Industry: {info.get('industry', 'N/A')}

**Recent News:**
{news_summary}

**Task:** Explain why this technical setup aligns (or doesn't align) with current market sentiment, fundamental trends, and recent news. Consider factors like:
1. Recent earnings growth or AI infrastructure deals
2. Market sentiment and news impact
3. Fundamental strength vs. technical setup
4. Risk factors specific to this timeframe
5. Whether the entry price and targets are realistic given current fundamentals

Provide a concise, actionable analysis (2-3 paragraphs) that helps a trader understand if this setup makes sense from both technical and fundamental perspectives."""
                                                system_prompt = "You are an expert financial analyst specializing in technical analysis and market sentiment. Provide clear, actionable insights."
                                                ai_analysis = call_ollama(system_prompt, user_prompt, temperature=0.7, max_tokens=500, model=get_current_ollama_model())
                                                if ai_analysis:
                                                    st.markdown(ai_analysis)
                                                else:
                                                    st.warning(f"AI analysis unavailable. Ensure Ollama is running (e.g. at {OLLAMA_BASE_URL}) with model {get_current_ollama_model()}.")
                                                    st.markdown(f"""
                                                    **Setup Summary:**
                                                    - Entry at ${setup['entry']:.2f} with stop-loss at ${setup['stop_loss']:.2f}
                                                    - Target 1 (1:1 R:R) at ${setup['target_1']:.2f}
                                                    - Target 2 (2:1 R:R) at ${setup['target_2']:.2f}
                                                    
                                                    **Considerations:**
                                                    - Check recent earnings and company news
                                                    - Verify fundamental strength aligns with technical setup
                                                    - Monitor market sentiment and sector trends
                                                    - Review risk factors specific to {setup['duration']} timeframe
                                                    """)
                                            except Exception as e:
                                                st.warning(f"AI analysis error: {str(e)}")
                                                st.info("**Manual Analysis:** This setup appears based on technical indicators. Consider checking recent earnings, news, and fundamental trends before trading.")
                            except Exception as e:
                                st.warning(f"Error fetching news/fundamentals: {str(e)}")
                                company_name = automation_ticker
                            
                            # Fetch historical data for chart
                            hist_data, _ = fetch_stock_data(automation_ticker, days=60)
                            if hist_data is not None and not hist_data.empty and trade_params:
                                st.subheader("📈 Trade Setup Chart")
                                
                                # Get the first setup (Intraday) for chart visualization
                                chart_setup = setups_list[0] if setups_list else None
                                
                                if chart_setup:
                                    # Create candlestick chart
                                    fig = go.Figure()
                                    
                                    # Add candlesticks
                                    fig.add_trace(go.Candlestick(
                                        x=hist_data.index,
                                        open=hist_data['Open'],
                                        high=hist_data['High'],
                                        low=hist_data['Low'],
                                        close=hist_data['Close'],
                                        name='Price'
                                    ))
                                    
                                    # Add 20-day SMA
                                    if indicators.get('sma_20'):
                                        sma_20_values = calculate_sma(hist_data['Close'], window=20)
                                        fig.add_trace(go.Scatter(
                                            x=hist_data.index,
                                            y=sma_20_values,
                                            mode='lines',
                                            name='20-day SMA',
                                            line=dict(color='blue', width=2)
                                        ))
                                    
                                    # Add entry line
                                    entry_price = chart_setup['entry']
                                    fig.add_hline(
                                        y=entry_price,
                                        line_dash="dash",
                                        line_color="green",
                                        annotation_text=f"Entry: ${entry_price:.2f}",
                                        annotation_position="right"
                                    )
                                    
                                    # Add stop loss line
                                    stop_loss = chart_setup['stop_loss']
                                    fig.add_hline(
                                        y=stop_loss,
                                        line_dash="dash",
                                        line_color="red",
                                        annotation_text=f"Stop Loss: ${stop_loss:.2f}",
                                        annotation_position="right"
                                    )
                                    
                                    # Add target lines
                                    target1 = chart_setup['target_1']
                                    fig.add_hline(
                                        y=target1,
                                        line_dash="dot",
                                        line_color="orange",
                                        annotation_text=f"Target 1 (1:1): ${target1:.2f}",
                                        annotation_position="right"
                                    )
                                    
                                    target2 = chart_setup['target_2']
                                    fig.add_hline(
                                        y=target2,
                                        line_dash="dot",
                                        line_color="purple",
                                        annotation_text=f"Target 2 (2:1): ${target2:.2f}",
                                        annotation_position="right"
                                    )
                                    
                                    fig.update_layout(
                                        title=f"{automation_ticker} - Trade Setup Visualization",
                                        xaxis_title="Date",
                                        yaxis_title="Price (USD)",
                                        height=600,
                                        xaxis_rangeslider_visible=False,
                                        hovermode='x unified'
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning("No trade setups generated.")
                else:
                    st.error("Could not retrieve setup information.")

elif page == "Automation" and (not automation_button or not automation_ticker):
    # Show instructions when button hasn't been clicked
    st.info("👈 Enter a stock symbol in the sidebar and click 'Generate Trade Setups' to begin automated analysis.")

elif page == "Stock Analysis" and st.session_state.get('stock_analysis_context'):
    # Stock Analysis page logic
    analysis_context = st.session_state.stock_analysis_context
    stock_symbol = analysis_context["symbol"]
    show_fundamental_analysis = analysis_context["show_fundamental_analysis"]
    show_comprehensive_table = analysis_context["show_comprehensive_table"]
    use_database = analysis_context["use_database"]

    # Validate stock symbol
    is_valid, error_msg = validate_stock_symbol(stock_symbol)
    
    if not is_valid:
        st.error(error_msg)
    else:
        # Show loading spinner
        with st.spinner(f"Fetching data for {stock_symbol}..."):
            # Always fetch financials if comprehensive table is requested
            fetch_financials = show_fundamental_analysis or show_comprehensive_table
            hist_data, info, earnings_data, financials, error = get_stock_data(stock_symbol, "1y", use_database, fetch_financials)
        
        if error:
            st.error(error)
        else:
            # Display company information
            company_name = info.get('longName', stock_symbol)
            st.header(f"{company_name} ({stock_symbol})")

            # Show a clear top banner while Ollama summary is being generated.
            ai_context_key = f"{stock_symbol}:1y:{get_current_ollama_model()}"
            ai_future_for_banner = st.session_state.get("ai_summary_future")
            is_ai_loading = (
                st.session_state.get("ai_summary_context") == ai_context_key and
                ai_future_for_banner is not None and
                not ai_future_for_banner.done()
            )
            if is_ai_loading:
                st.info("⏳ Loading data from Ollama in the background. You can continue using the page.")
            
            # Display business summary if available
            if info.get('longBusinessSummary'):
                with st.expander("Company Overview"):
                    st.write(info['longBusinessSummary'])
            
            # Calculate and display key metrics
            metrics = calculate_financial_metrics(hist_data, info)
            
            # AI-Generated Stock Analysis Summary
            st.subheader("🤖 AI Stock Analysis Summary")
            ai_summary_container = st.container()
            ai_context_key = f"{stock_symbol}:1y:{get_current_ollama_model()}"

            if "ai_summary_future" not in st.session_state:
                st.session_state.ai_summary_future = None
            if "ai_summary_context" not in st.session_state:
                st.session_state.ai_summary_context = None
            if "ai_summary_result" not in st.session_state:
                st.session_state.ai_summary_result = None
            if "ai_summary_error" not in st.session_state:
                st.session_state.ai_summary_error = None

            # Reset AI summary state when user switches to a different symbol/period context.
            if st.session_state.ai_summary_context != ai_context_key:
                running_future = st.session_state.ai_summary_future
                if running_future is not None and not running_future.done():
                    running_future.cancel()
                st.session_state.ai_summary_future = None
                st.session_state.ai_summary_context = ai_context_key
                st.session_state.ai_summary_result = None
                st.session_state.ai_summary_error = None

            action_col1, action_col2 = st.columns([1, 1])
            with action_col1:
                if st.button("Generate / Regenerate AI Summary", key=f"ai_generate_{ai_context_key}"):
                    st.session_state.ai_summary_result = None
                    st.session_state.ai_summary_error = None
                    st.session_state.ai_summary_future = AI_EXECUTOR.submit(
                        generate_ai_stock_summary,
                        stock_symbol,
                        company_name,
                        info,
                        metrics,
                        hist_data,
                        earnings_data,
                        financials,
                        get_current_ollama_model(),
                    )
                    st.rerun()
            with action_col2:
                if st.button("Refresh AI Status", key=f"ai_refresh_{ai_context_key}"):
                    st.rerun()

            current_future = st.session_state.ai_summary_future
            if current_future is not None and current_future.done():
                try:
                    st.session_state.ai_summary_result = current_future.result()
                    st.session_state.ai_summary_error = None
                except Exception as e:
                    st.session_state.ai_summary_error = str(e)
                finally:
                    st.session_state.ai_summary_future = None

            with ai_summary_container:
                if st.session_state.ai_summary_result:
                    st.markdown(st.session_state.ai_summary_result)
                    st.caption(f"🤖 Using AI model: {get_current_ollama_model()}")
                elif st.session_state.ai_summary_future is not None:
                    st.info("AI summary is generating in background. You can continue using the page and click 'Refresh AI Status'.")
                elif st.session_state.ai_summary_error:
                    st.warning(f"AI analysis unavailable: {st.session_state.ai_summary_error}")
                else:
                    st.info("Click 'Generate / Regenerate AI Summary' to run AI analysis in the background.")
            
            st.markdown("---")
            
            # Create columns for metrics display
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Current Price", metrics.get('Current Price', 'N/A'))
                st.metric("Market Cap", metrics.get('Market Cap', 'N/A'))
                st.metric("Volume", metrics.get('Volume', 'N/A'))
            
            with col2:
                st.metric("Daily Change", metrics.get('Daily Change', 'N/A'))
                st.metric("P/E Ratio", metrics.get('P/E Ratio', 'N/A'))
                st.metric("Dividend Yield", metrics.get('Dividend Yield', 'N/A'))
            
            with col3:
                st.metric("52-Week High", metrics.get('52-Week High', 'N/A'))
                st.metric("52-Week Low", metrics.get('52-Week Low', 'N/A'))
                st.metric("Volatility", metrics.get('Volatility (Annual)', 'N/A'))
            
            with col4:
                st.metric("20-Day MA", metrics.get('20-Day MA', 'N/A'))
                st.metric("50-Day MA", metrics.get('50-Day MA', 'N/A'))
            
            # Display charts
            st.subheader("📊 Price Chart")
            price_fig = create_price_chart(hist_data, stock_symbol)
            st.plotly_chart(price_fig, use_container_width=True)
            
            # Volume analysis section
            st.subheader("📈 Trading Volume Analysis")
            
            # Calculate volume metrics
            volume_metrics = calculate_volume_metrics(hist_data)
            
            # Display volume metrics in columns
            if volume_metrics:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Current Volume", volume_metrics.get('Current Volume', 'N/A'))
                    st.metric("Max Volume (3M)", volume_metrics.get('Max Volume (3M)', 'N/A'))
                
                with col2:
                    st.metric("Avg Volume (3M)", volume_metrics.get('Avg Volume (3M)', 'N/A'))
                    st.metric("Min Volume (3M)", volume_metrics.get('Min Volume (3M)', 'N/A'))
                
                with col3:
                    st.metric("Volume vs Avg", volume_metrics.get('Volume vs Avg', 'N/A'))
                    st.metric("Volume Trend", volume_metrics.get('Volume Trend', 'N/A'))
            
            # Volume chart
            volume_fig = create_volume_chart(hist_data, stock_symbol)
            st.plotly_chart(volume_fig, use_container_width=True)
            
            # Earnings Per Share Chart
            if earnings_data is not None and not earnings_data.empty:
                st.subheader("💰 Earnings Per Share (Last 5 Years)")
                earnings_fig = create_earnings_chart(earnings_data, stock_symbol)
                if earnings_fig:
                    st.plotly_chart(earnings_fig, use_container_width=True)
                    
                    # Display earnings data table
                    st.write("**Earnings Data:**")
                    earnings_display = earnings_data.copy()
                    earnings_display['Earnings'] = earnings_display['Earnings'].apply(format_price)
                    earnings_display.columns = ['Earnings Per Share ($)']
                    st.dataframe(earnings_display, use_container_width=True)
            else:
                st.subheader("💰 Earnings Per Share")
                st.info("Earnings data not available for this stock symbol.")
            
            # Comprehensive Financial Overview Section
            if show_comprehensive_table:
                display_comprehensive_table(stock_symbol, info, hist_data, financials)
            
            # Fundamental Analysis Section
            if show_fundamental_analysis and financials:
                st.subheader("📋 Fundamental Analysis")
                
                # Create tabs for different financial statements
                tab1, tab2, tab3 = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])
                
                with tab1:
                    if financials.get('income_stmt') is not None:
                        display_financial_statement(financials['income_stmt'], "Income Statement", stock_symbol)
                    else:
                        st.warning("Income Statement data not available")
                
                with tab2:
                    if financials.get('balance_sheet') is not None:
                        display_financial_statement(financials['balance_sheet'], "Balance Sheet", stock_symbol)
                    else:
                        st.warning("Balance Sheet data not available")
                
                with tab3:
                    if financials.get('cash_flow') is not None:
                        display_financial_statement(financials['cash_flow'], "Cash Flow Statement", stock_symbol)
                    else:
                        st.warning("Cash Flow Statement data not available")
            
            # Data table
            st.subheader("📋 Historical Data")
            
            # Prepare data for display
            display_data = hist_data.copy()
            display_data.index = display_data.index.strftime('%Y-%m-%d')
            display_data = display_data.round(2)
            
            # Show data table
            st.dataframe(display_data, use_container_width=True)
            
            # CSV Download
            st.subheader("💾 Download Data")
            
            # Prepare CSV data
            csv_data = display_data.copy()
            csv_data.insert(0, 'Date', csv_data.index)
            csv_data.reset_index(drop=True, inplace=True)
            
            # Add metadata to CSV
            metadata_df = pd.DataFrame({
                'Metric': list(metrics.keys()),
                'Value': list(metrics.values())
            })
            
            # Create download button
            csv_string = f"# {company_name} ({stock_symbol}) Financial Data\n"
            csv_string += f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            csv_string += "# Period: 1 Year\n\n"
            csv_string += "# Key Metrics\n"
            csv_string += metadata_df.to_csv(index=False)
            
            # Add volume metrics to CSV
            if volume_metrics:
                csv_string += "\n# Volume Analysis (Last 3 Months)\n"
                volume_df = pd.DataFrame({
                    'Metric': list(volume_metrics.keys()),
                    'Value': list(volume_metrics.values())
                })
                csv_string += volume_df.to_csv(index=False)
            
            # Add 3-month volume data to CSV if available
            if hasattr(hist_data, 'volume_3m') and hist_data.volume_3m is not None:
                csv_string += "\n# 3-Month Volume Data\n"
                volume_3m_csv = hist_data.volume_3m.copy()
                volume_3m_csv.insert(0, 'Date', volume_3m_csv.index.strftime('%Y-%m-%d'))
                volume_3m_csv.reset_index(drop=True, inplace=True)
                csv_string += volume_3m_csv.to_csv(index=False)
            
            # Add earnings data to CSV if available
            if earnings_data is not None and not earnings_data.empty:
                csv_string += "\n# Earnings Per Share (Last 5 Years)\n"
                earnings_csv = earnings_data.copy()
                earnings_csv.insert(0, 'Year', earnings_csv.index)
                earnings_csv.reset_index(drop=True, inplace=True)
                csv_string += earnings_csv.to_csv(index=False)
            
            # Add fundamental analysis data to CSV if available
            if show_fundamental_analysis and financials:
                # Helper function to format financial statement for CSV
                def format_statement_for_csv(statement_df, statement_name):
                    if statement_df is None or statement_df.empty:
                        return f"\n# {statement_name} - No data available\n"
                    
                    csv_string_part = f"\n# {statement_name} (formatted)\n"
                    formatted_df = statement_df.copy().reset_index()
                    
                    # Format all numeric columns
                    for col in formatted_df.columns:
                        if col != 'index':
                            try:
                                numeric_col = pd.to_numeric(formatted_df[col], errors='coerce')
                                if not numeric_col.isna().all():
                                    formatted_df[col] = numeric_col.apply(lambda x: format_financial_statement_value(x) if pd.notna(x) else 'N/A')
                            except:
                                pass
                    
                    # Format column names
                    new_columns = []
                    for col in formatted_df.columns:
                        if col == 'index':
                            new_columns.append('Item')
                        elif hasattr(col, 'strftime'):
                            new_columns.append(col.strftime('%Y-%m-%d'))
                        else:
                            new_columns.append(str(col))
                    formatted_df.columns = new_columns
                    
                    csv_string_part += formatted_df.to_csv(index=False)
                    return csv_string_part
                
                # Add formatted financial statements to CSV
                if financials.get('income_stmt') is not None:
                    csv_string += format_statement_for_csv(financials['income_stmt'], "Income Statement")
                
                if financials.get('balance_sheet') is not None:
                    csv_string += format_statement_for_csv(financials['balance_sheet'], "Balance Sheet")
                
                if financials.get('cash_flow') is not None:
                    csv_string += format_statement_for_csv(financials['cash_flow'], "Cash Flow Statement")
            
            csv_string += "\n# Historical Price Data\n"
            csv_string += csv_data.to_csv(index=False)
            
            st.download_button(
                label=f"📥 Download {stock_symbol} Data as CSV",
                data=csv_string,
                file_name=f"{stock_symbol}_financial_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                help="Download complete financial data including metrics and historical prices"
            )
            
            # Display additional information
            with st.expander("📈 Additional Information"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Sector:** ", info.get('sector', 'N/A'))
                    st.write("**Industry:** ", info.get('industry', 'N/A'))
                    st.write("**Country:** ", info.get('country', 'N/A'))
                    st.write("**Currency:** ", info.get('currency', 'N/A'))
                
                with col2:
                    employees = info.get('fullTimeEmployees')
                    employees_formatted = format_number(employees, currency=False, decimal_places=0) if employees else 'N/A'
                    st.write("**Employees:** ", employees_formatted)
                    st.write("**Exchange:** ", info.get('exchange', 'N/A'))
                    st.write("**Website:** ", info.get('website', 'N/A'))

elif page == "Ollama Analysis" and st.session_state.get('ollama_analysis_context'):
    ollama_context = st.session_state.ollama_analysis_context
    ollama_symbol = ollama_context["symbol"]
    ollama_period = ollama_context["period"]
    ollama_use_database = ollama_context["use_database"]

    ollama_period_map = {
        "6 Months": "6mo",
        "1 Year": "1y",
        "2 Years": "2y",
        "5 Years": "5y"
    }

    is_valid, error_msg = validate_stock_symbol(ollama_symbol)
    if not is_valid:
        st.error(error_msg)
    else:
        with st.spinner(f"Fetching data for {ollama_symbol}..."):
            hist_data, info, earnings_data, financials, error = get_stock_data(
                ollama_symbol,
                ollama_period_map[ollama_period],
                ollama_use_database,
                include_financials=True
            )

        if error:
            st.error(error)
        else:
            company_name = info.get('longName', ollama_symbol)
            st.header(f"{company_name} ({ollama_symbol})")

            st.subheader("📉 Main Trend, Support, Resistance, Bad-Entry Zone")
            trend_fig, trend_context = create_grok_trend_chart(hist_data, ollama_symbol)
            if trend_fig is not None:
                st.plotly_chart(trend_fig, use_container_width=True)
                st.caption(
                    f"Trend: {trend_context['trend_label']} | "
                    f"Support: {trend_context['support']:.2f} | "
                    f"Resistance: {trend_context['resistance']:.2f} | "
                    f"Bad-entry zone: {trend_context['bad_entry_zone']}"
                )
            else:
                st.warning("Not enough chart data to compute trend/support/resistance.")
                trend_context = {
                    "trend_label": "N/A",
                    "support": "N/A",
                    "resistance": "N/A",
                    "latest_price": "N/A",
                    "bad_entry_zone": "N/A",
                    "bad_entry_label": "N/A"
                }

            st.subheader("🧠 Ollama Analysis (On-demand per point)")
            st.caption(f"Model: {get_current_ollama_model()}")

            point_definitions = [
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
                (15, "Risk management", "Provide position sizing, max loss, invalidation, and trade management rules.")
            ]

            analysis_context_key = f"{ollama_symbol}:{ollama_period}:{get_current_ollama_model()}"
            if "ollama_point_cache" not in st.session_state:
                st.session_state.ollama_point_cache = {}
            if "ollama_point_error" not in st.session_state:
                st.session_state.ollama_point_error = {}

            point_cache = st.session_state.ollama_point_cache.setdefault(analysis_context_key, {})
            point_errors = st.session_state.ollama_point_error.setdefault(analysis_context_key, {})
            key_suffix = f"{ollama_symbol}_{ollama_period}".replace(" ", "_")

            for point_number, point_title, point_instruction in point_definitions:
                st.markdown(f"### {point_number}. {point_title}")
                button_label = "Regenerate" if point_number in point_cache else "Generate"
                if st.button(f"{button_label} Point {point_number}", key=f"ollama_point_{point_number}_{key_suffix}"):
                    with st.spinner(f"Loading point {point_number} from Ollama..."):
                        point_text, ollama_error = generate_ollama_point_analysis(
                            ollama_symbol,
                            company_name,
                            info,
                            hist_data,
                            earnings_data,
                            trend_context,
                            point_number,
                            point_title,
                            point_instruction
                        )
                    if ollama_error:
                        point_errors[point_number] = ollama_error
                    elif point_text:
                        point_cache[point_number] = point_text
                        if point_number in point_errors:
                            del point_errors[point_number]
                    else:
                        point_errors[point_number] = "Ollama returned no content for this point."

                if point_number in point_errors:
                    st.error(point_errors[point_number])
                elif point_number in point_cache:
                    st.markdown(point_cache[point_number])
                else:
                    st.caption("Click the button to generate this point with Ollama.")

elif page == "Ollama Analysis":
    st.info("👈 Enter a stock symbol in the sidebar and click 'Analyze with Ollama' to begin.")

elif page == "By Industry":
    # Admin panel: manage stocks and industry assignments (add, edit, delete)
    if not db or not hasattr(db, "admin_get_industries_with_stocks"):
        st.warning("Database is required for the Industry admin panel.")
    else:
        st.subheader("Admin: Manage stocks by industry")
        st.caption("Add stocks to industries, assign the same stock to multiple industries, or remove assignments.")

        # ----- Add stock to industry -----
        with st.expander("➕ Add stock to industry", expanded=True):
            add_symbol_input = st.text_input("Stock symbol(s)", value="", key="industry_add_symbol", placeholder="e.g. AAPL or AAPL, GOOGL, MSFT (comma-separated)").strip().upper()
            add_symbols = [s.strip() for s in add_symbol_input.split(",") if s.strip()]
            admin_industries = db.admin_get_all_industries()
            add_industry_new = st.text_input("New industry name (optional)", value="", key="industry_add_new", placeholder="Type to create new industry")
            add_industry_existing = st.multiselect(
                "Existing industries (or use new name above)",
                options=admin_industries,
                default=[],
                key="industry_add_existing",
            )
            add_industries = list(add_industry_existing)
            if add_industry_new.strip():
                add_industries.append(add_industry_new.strip())
            add_industries = list(dict.fromkeys(add_industries))  # unique, order preserved
            if st.button("Add to selected industries", key="industry_add_btn") and add_symbols:
                if not add_industries:
                    st.error("Select or enter at least one industry.")
                else:
                    total_ok = 0
                    for add_symbol in add_symbols:
                        for ind in add_industries:
                            ok, err = db.admin_add_stock_to_industry(add_symbol, ind)
                            if ok:
                                total_ok += 1
                            else:
                                st.error(f"Failed to add **{add_symbol}** to '{ind}': {err}")
                    if total_ok:
                        syms_str = ", ".join(add_symbols)
                        st.success(f"Added **{syms_str}** to {total_ok} industry assignment(s).")
                        for add_symbol in add_symbols:
                            try:
                                ticker = yf.Ticker(add_symbol)
                                info = ticker.info
                                if info and info.get("symbol"):
                                    db.save_stock_info(add_symbol, info)
                            except Exception:
                                pass
                        st.rerun()

        # ----- Filter and list industries -----
        industries_data = db.admin_get_industries_with_stocks()
        industry_names = sorted(industries_data.keys()) if industries_data else []
        selected_filter = st.selectbox(
            "Filter industries",
            options=["All industries"] + industry_names,
            key="industry_page_filter",
        )
        if selected_filter and selected_filter != "All industries":
            display_industries = {selected_filter: industries_data.get(selected_filter, [])}
        else:
            display_industries = industries_data or {}

        if not display_industries:
            st.info("No industries yet. Use **Add stock to industry** above to create industries and assign stocks.")
        else:
            for industry_name in sorted(display_industries.keys()):
                stocks = display_industries[industry_name]
                with st.expander(f"**{industry_name}** ({len(stocks)} stocks)", expanded=True):
                    for item in stocks:
                        sym = item["symbol"]
                        name = (item.get("company_name") or sym)[:40]
                        c1, c2, c3 = st.columns([3, 1, 1])
                        with c1:
                            st.markdown(
                                f'<a href="?symbol={sym}&analyze=true" target="_blank" class="stock-link" title="Analyze {sym}">{sym}</a> — {name}',
                                unsafe_allow_html=True,
                            )
                        with c2:
                            if st.button("Edit", key=f"industry_edit_{industry_name}_{sym}"):
                                st.session_state["industry_edit_symbol"] = sym
                                st.session_state["industry_edit_from"] = industry_name
                                st.rerun()
                        with c3:
                            if st.button("Delete", key=f"industry_del_{industry_name}_{sym}"):
                                ok, err = db.admin_remove_stock_from_industry(sym, industry_name)
                                if ok:
                                    st.success(f"Removed {sym} from **{industry_name}**.")
                                    st.rerun()
                                else:
                                    st.error(err)

        # ----- Edit flow: change industries for a symbol -----
        if st.session_state.get("industry_edit_symbol"):
            edit_sym = st.session_state["industry_edit_symbol"]
            from_industry = st.session_state.get("industry_edit_from", "")
            st.markdown("---")
            st.subheader(f"Edit industries for **{edit_sym}**")
            current = db.admin_get_industries_for_stock(edit_sym)
            st.write("Currently in:", ", ".join(current) if current else "—")
            add_to_ind = st.selectbox("Add to industry", options=["(Select)"] + (industry_names or ["(No industries yet)"]) + ["(New industry)"], key="edit_add_industry")
            new_ind_name = st.text_input("New industry name (if selected above)", key="edit_new_industry_name")
            col_a, col_b = st.columns(2)
            with col_a:
                if add_to_ind and add_to_ind not in ("(Select)", "(No industries yet)"):
                    target = new_ind_name.strip() if add_to_ind == "(New industry)" else add_to_ind
                    if target and st.button("Add to this industry", key="edit_add_btn"):
                        ok, err = db.admin_add_stock_to_industry(edit_sym, target)
                        if ok:
                            st.success(f"Added {edit_sym} to **{target}**.")
                            st.rerun()
                        else:
                            st.error(err)
            with col_b:
                remove_from = st.selectbox("Remove from industry", options=["(Select)"] + current, key="edit_remove_industry")
                if remove_from and remove_from != "(Select)" and st.button("Remove from this industry", key="edit_remove_btn"):
                    ok, err = db.admin_remove_stock_from_industry(edit_sym, remove_from)
                    if ok:
                        st.success(f"Removed {edit_sym} from **{remove_from}**.")
                        st.rerun()
                    else:
                        st.error(err)
            if st.button("Remove from all industries (delete this stock from admin)", key="edit_remove_all_btn"):
                ok, err = db.admin_remove_stock_from_all_industries(edit_sym)
                if ok:
                    st.success(f"Removed {edit_sym} from all industries.")
                    st.session_state.pop("industry_edit_symbol", None)
                    st.session_state.pop("industry_edit_from", None)
                    st.rerun()
                else:
                    st.error(err)
            if st.button("Done editing", key="edit_done_btn"):
                st.session_state.pop("industry_edit_symbol", None)
                st.session_state.pop("industry_edit_from", None)
                st.rerun()

elif page == "Stock Analysis":
    # Initial page state for Stock Analysis
    st.info("👈 Enter a stock symbol in the sidebar and click 'Analyze Stock' to get started!")
    
    # Show sample information
    st.subheader("🌟 Features")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**📊 Interactive Charts**")
        st.write("• Candlestick price charts")
        st.write("• Moving averages overlay")
        st.write("• Volume analysis")
    
    with col2:
        st.write("**📈 Key Metrics**")
        st.write("• Real-time price data")
        st.write("• Financial ratios")
        st.write("• Market statistics")
    
    with col3:
        st.write("**💾 Data Export**")
        st.write("• CSV download")
        st.write("• Historical data")
        st.write("• Complete metrics")
    
    st.subheader("🔍 Supported Stock Symbols")
    st.write("Enter any valid stock ticker symbol from major exchanges:")
    st.write("• **US Markets:** AAPL, GOOGL, MSFT, TSLA, AMZN")
    st.write("• **International:** NESN.SW, ASML.AS, SAP.DE")
    st.write("• **Indices:** ^GSPC (S&P 500), ^DJI (Dow Jones)")

# Footer
st.markdown("---")
st.markdown("📊 **Stock Financial Analysis** | Powered by Yahoo Finance | Built with Streamlit")
