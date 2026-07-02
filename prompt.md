# Implementation Prompt: AI Stock Analysis Professional Redesign

You are implementing a full UI redesign of an existing Python stock-analysis
app. Read PRD.md in the repo root first — it is the source of truth.
Work phase by phase, in order. Do not skip validation steps.

## Context

Existing code to REUSE (do not rewrite the logic):

- yahoo_session.py — curl_cffi Chrome-impersonation session, get_ticker(),
  with_retry(), get_earnings_history(). All Yahoo access MUST go through this.
- scanner.py — SMA/RSI/ATR indicators, setup detection, trade params.
- database.py — DatabaseManager with PostgreSQL tables for prices, info,
  earnings, financial statements, portfolio, stock_industry.
- formatting_utils.py — number formatting helpers.
- app.py — the legacy 4,700-line Streamlit app. Port its business logic
  (metric calculations, DCA scoring/backtest, Ollama prompts) into the new
  backend; do NOT port its UI patterns.

Environment: .env contains DATABASE_URL and optional OLLAMA_* vars.
yfinance>=1.3.0 — Ticker.earnings is removed; use get_earnings_history().
pandas>=3.0 — applymap is removed; use .map on Styler/DataFrame.

## Target architecture

- backend/ — FastAPI app exposing the API in PRD section 7.
- frontend/ — Next.js 14 App Router + TypeScript + Tailwind CSS + shadcn/ui.
- Charts: TradingView Lightweight Charts (candlesticks), Recharts (misc).
- Data fetching: TanStack Query. Tables: TanStack Table.

## Hard requirements (from user)

1. Sidebar must be real navigation links — NO radio buttons.
2. Stock search lives in the top bar on EVERY page, with Google-Finance-style
   autosuggest backed by GET /api/search (Yahoo search API proxy, debounced).
3. NO "Filter by Industry" controls on analysis pages.
4. Fundamental Analysis and Comprehensive Overview are TABS inside
   /stocks/[symbol] — not sidebar options.
5. NO user-facing cache toggle. Backend caches transparently (TTL).
6. NO "Analyze Stock" button. Selecting a search suggestion navigates to
   /stocks/[symbol] which auto-loads all data.
7. Sidebar contains ONLY navigation (+ theme toggle). No settings, no DB
   management panels.
8. Fully responsive: persistent sidebar on desktop, collapsible on tablet,
   bottom tab bar on phones. Tables scroll horizontally on small screens.

## Phase order and validation

Implement phases 1-6 exactly as defined in PRD.md section 9.
After each phase, validate:

- Phase 1: curl every endpoint; confirm AAPL returns history (252 rows for 1y),
  info, 3 financial statements, and 4-5 earnings rows. Confirm /api/search?q=app
  returns AAPL among suggestions.
- Phase 2: app shell renders at all three breakpoints; search box debounces
  and shows suggestions.
- Phase 3: /stocks/AAPL loads everything with zero clicks; all 4 tabs work;
  candlestick chart renders.
- Phase 4: portfolio grid sorts; CSV downloads; DCA backtest completes and
  charts results.
- Phase 5: 15-point AI analysis streams per point; automation shows 5 trade
  setups with chart.
- Phase 6: mobile Lighthouse usability >= 90; docker-compose up brings up the
  full stack.

## Conventions

- TypeScript strict mode; functional components; no class components.
- Use shadcn/ui primitives (Card, Tabs, Table, Command for search palette).
- Color tokens: green for positive change, red for negative, monospace for
  ticker symbols and prices.
- Keep the Streamlit app untouched and runnable until Phase 6 sign-off.
- Commit at the end of each phase with a descriptive message.
