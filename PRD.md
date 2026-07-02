# PRD: AI Stock Analysis — Professional Redesign

**Version:** 1.0
**Date:** June 12, 2026
**Status:** Approved for implementation

---

## 1. Problem Statement

The current application is a single 4,700-line Streamlit script with significant UX problems:

1. Left navigation uses a radio button group — confusing and unprofessional.
2. Stock symbol input lives in the sidebar instead of within each page.
3. No autosuggest — users must know exact ticker symbols.
4. Analysis options (Fundamental Analysis, Comprehensive Overview) are sidebar
   checkboxes instead of in-page tabs/sections.
5. "Use cached data" checkbox exposes an implementation detail to users.
6. An explicit "Analyze Stock" button gates every interaction.
7. The sidebar is cluttered with per-page settings, DB management, and status panels.
8. Streamlit's layout is desktop-only; unusable on phones and tablets.

## 2. Goals

- Professional, modern financial-app UI comparable to Google Finance / Yahoo Finance.
- Clean sidebar navigation with real links (no radio buttons).
- Google-Finance-style search with live autosuggest on every page.
- Auto-load analysis on symbol selection (no Analyze button).
- Per-stock analysis sections as in-page tabs (Overview, Fundamentals, Comprehensive).
- Caching handled transparently server-side (no user-facing cache toggle).
- Fully responsive: desktop, tablet (iPad), and phone.

## 3. Non-Goals

- Changing data sources (Yahoo Finance via yfinance + curl_cffi stays).
- Changing the database schema (PostgreSQL tables stay as-is).
- Changing AI provider (local Ollama stays).
- Authentication / multi-user support (future phase).

## 4. Tech Stack Decision

| Layer     | Choice                                    | Rationale                                                  |
|-----------|-------------------------------------------|------------------------------------------------------------|
| Frontend  | Next.js 14+ (App Router) + TypeScript     | Industry standard, file-based routing, SSR                 |
| Styling   | Tailwind CSS + shadcn/ui                  | User-selected; professional component library              |
| Charts    | TradingView Lightweight Charts + Recharts | Financial-grade candlesticks; simple charts for metrics    |
| Backend   | FastAPI (Python)                          | Reuses existing yahoo_session.py, scanner.py, database.py  |
| Database  | Existing PostgreSQL + SQLAlchemy          | No schema change                                           |
| AI        | Existing Ollama integration               | Proxied through FastAPI                                    |

## 5. Information Architecture

    Sidebar (collapsible, icons + labels)
    ├── 📈 Stocks            /stocks and /stocks/[symbol]
    ├── 💼 Portfolio         /portfolio
    ├── 💰 DCA               /dca
    ├── 🧠 AI Analysis       /ai/[symbol]        (Ollama 15-point)
    ├── 🤖 Automation        /automation/[symbol] (trade setups)
    └── ⚙️ Admin > Industries /admin/industries

    Top bar (persistent on every page)
    └── Global stock search with autosuggest (Yahoo search API, debounced 300 ms)

### Stock detail page (/stocks/[symbol]) — in-page tabs replace sidebar checkboxes:

- **Overview**: price header, key metrics, candlestick chart, volume, AI summary
- **Fundamentals**: income statement, balance sheet, cash flow tables
- **Comprehensive**: full metric table + 6-month chart
- **Earnings**: 5-year Net Income chart

## 6. Key Behavior Changes

| Current (Streamlit)                  | New (Next.js)                                      |
|--------------------------------------|-----------------------------------------------------|
| Sidebar radio navigation             | Sidebar nav links; active route highlighted        |
| Sidebar text input for symbol        | Top-bar global search, autosuggest, on every page  |
| "Analyze Stock" button               | Navigating to /stocks/AAPL auto-loads everything   |
| "Use cached data" checkbox           | Server-side cache: DB-first with TTL, then Yahoo   |
| Filter-by-industry dropdowns         | Removed (industry admin stays under /admin)        |
| Fundamental/Comprehensive checkboxes | Tabs within stock detail page                      |
| Fixed desktop layout                 | Responsive: sidebar → bottom tab bar on mobile     |

## 7. API Surface (FastAPI)

    GET  /api/search?q=...                 → Yahoo autosuggest proxy
    GET  /api/stocks/{symbol}              → quote + info + metrics
    GET  /api/stocks/{symbol}/history      → OHLCV (period param)
    GET  /api/stocks/{symbol}/financials   → 3 statements
    GET  /api/stocks/{symbol}/earnings     → 5y Net Income
    GET  /api/portfolio                    → saved symbols + grid data
    POST/DELETE /api/portfolio/{symbol}    → manage portfolio
    GET/POST /api/dca/...                  → DCA list + backtest
    POST /api/ai/summary                   → Ollama summary
    POST /api/ai/point                     → Ollama 15-point analysis
    GET  /api/automation/{symbol}          → scanner trade setups
    CRUD /api/admin/industries             → industry assignments

Caching policy: quotes 1 min TTL; history 15 min; financials/earnings 24 h
(backed by in-process TTL cache + existing PostgreSQL tables; transparent to users).

## 8. Responsive Design Requirements

- Desktop (≥1024px): persistent sidebar, multi-column dashboards.
- Tablet (768–1023px): collapsible sidebar, 2-column grids.
- Phone (<768px): bottom tab bar (5 items), single column, horizontally
  scrollable tables, touch-friendly charts.

## 9. Implementation Phases

### Phase 1 — Backend API (FastAPI)

1. Scaffold FastAPI app; mount existing modules (yahoo_session, scanner, database).
2. Implement /api/search proxy to Yahoo autosuggest.
3. Implement stock endpoints (quote, history, financials, earnings).
4. Implement portfolio, DCA, admin endpoints over existing DatabaseManager.
5. Implement Ollama proxy endpoints (summary + 15-point).
6. Add transparent caching layer (TTL).
7. CORS config for the Next.js dev origin.

### Phase 2 — Frontend foundation (Next.js)

1. Scaffold Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui.
2. Build app shell: sidebar nav, top bar, mobile bottom tabs, dark/light theme.
3. Build global search component with debounced autosuggest.
4. Set up TanStack Query for API data fetching/caching.

### Phase 3 — Stock detail page

1. /stocks/[symbol] route with Overview, Fundamentals, Comprehensive, Earnings tabs.
2. TradingView Lightweight Charts candlestick + volume.
3. Metric cards, financial statement tables (responsive).
4. AI summary panel with streaming Ollama output.

### Phase 4 — Portfolio & DCA pages

1. Portfolio grid (5 metric tabs) using TanStack Table; sorting; CSV export.
2. DCA list management + backtest runner with results charts.

### Phase 5 — AI Analysis & Automation pages

1. /ai/[symbol]: trend chart + 15-point on-demand analysis.
2. /automation/[symbol]: indicators, setup detection, 5-timeframe trade table,
   setup visualization chart.

### Phase 6 — Admin, polish, deployment

1. /admin/industries CRUD.
2. Responsive QA pass on phone/tablet breakpoints.
3. Loading/error/empty states everywhere.
4. Deployment: docker-compose (FastAPI + Next.js + Postgres) or
   Vercel (frontend) + local/VPS (backend).
5. Decommission Streamlit app once parity confirmed.

## 10. Success Criteria

- All 6 current pages reachable via clean sidebar nav.
- Typing "app" in search suggests Apple (AAPL) within 500 ms.
- Selecting a suggestion loads full analysis with no extra clicks.
- No cache/database controls visible to end users.
- Lighthouse mobile usability score ≥ 90.
- Existing PostgreSQL data fully reused; zero data migration.
