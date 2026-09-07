/** Typed client for the FastAPI backend (see PRD.md section 7). */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export interface SearchResult {
  symbol: string;
  name: string | null;
  exchange: string | null;
  type: string | null;
}

export interface WallStreetStructured {
  overall_stance: "bullish" | "neutral" | "bearish";
  confidence: "low" | "medium" | "high";
  base_case_summary: string | null;
  bull_case_summary: string | null;
  bear_case_summary: string | null;
}

export interface WallStreetAnalysis {
  symbol: string;
  metrics: Record<string, unknown>;
  markdown: string;
  structured: WallStreetStructured | null;
  model: string;
  disclaimer: string;
  cached?: boolean;
  source?: "cache" | "live" | null;
  updated_at?: string | null;
}

export interface WallStreetCacheLookup {
  cached: boolean;
  symbol: string;
  source?: "cache" | "live" | null;
  metrics?: Record<string, unknown>;
  markdown?: string;
  structured?: WallStreetStructured | null;
  model?: string;
  disclaimer?: string;
  updated_at?: string | null;
}

export interface StockMetrics {
  current_price: number | null;
  daily_change_pct: number | null;
  weekly_change_pct: number | null;
  monthly_change_pct: number | null;
  yearly_change_pct: number | null;
  volume: number | null;
  market_cap: number | null;
  pe_ratio: number | null;
  forward_pe: number | null;
  pb_ratio: number | null;
  ps_ratio: number | null;
  peg_ratio: number | null;
  dividend_yield_pct: number | null;
  volatility_annual_pct: number | null;
  ma_20: number | null;
  ma_50: number | null;
  week_52_high: number | null;
  week_52_low: number | null;
  beta: number | null;
  profit_margin_pct: number | null;
  operating_margin_pct: number | null;
  gross_margin_pct: number | null;
  roe_pct: number | null;
  roa_pct: number | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  revenue: number | null;
  revenue_growth_pct: number | null;
  eps: number | null;
  free_cash_flow: number | null;
  operating_cash_flow: number | null;
  book_value_per_share: number | null;
}

export interface StockOverview {
  symbol: string;
  name: string;
  sector: string | null;
  industry: string | null;
  exchange: string | null;
  currency: string | null;
  website: string | null;
  business_summary: string | null;
  metrics: StockMetrics;
}

export interface Candle {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface StatementPayload {
  columns: string[];
  rows: { item: string; values: (number | null)[] }[];
}

export interface TradeSetup {
  timeframe: string;
  duration: string;
  description: string;
  entry: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  risk_per_share: number;
  reward_1: number;
  reward_2: number;
  risk_reward_1: string;
  risk_reward_2: string;
  stop_loss_pct: number;
  target_1_pct: number;
  target_2_pct: number;
}

export interface ScanIndicators {
  current_price: number;
  sma_20: number;
  rsi: number;
  atr: number;
  high: number;
  low: number;
  volume: number;
  price_change_pct: number;
}

export interface AutomationResponse {
  symbol: string;
  setup: {
    setup_detected: boolean;
    details: string[];
    definitions: Record<string, string>;
    indicators: ScanIndicators;
  } | null;
  trade_params: {
    ticker: string;
    generated_at: string;
    entry_price: number;
    atr: number;
    atr_multiplier: number;
    setups: TradeSetup[];
  } | null;
  warning: string | null;
}

export interface PortfolioGridRow {
  symbol: string;
  name: string;
  sector: string | null;
  metrics: StockMetrics;
  sparkline: number[];
}

export interface PortfolioBucket {
  id: number;
  name: string;
  symbol_count: number;
  created_at?: string | null;
}

export interface PortfolioGridResponse {
  portfolio_id?: number;
  name?: string;
  rows: PortfolioGridRow[];
  errors: Record<string, string>;
}

export interface PortfolioImportRow {
  symbol: string;
  status: "added" | "skipped" | "error";
  message: string;
}

export interface PortfolioImportResult {
  total: number;
  added: number;
  skipped: number;
  failed: number;
  results: PortfolioImportRow[];
}

export interface IndustryGridResponse extends PortfolioGridResponse {
  industry: string;
}

export type PortfolioView =
  | { mode: "portfolio"; portfolioId: number; name: string }
  | { mode: "industry"; industry: string };

export interface TrendContext {
  symbol: string;
  trend_label: string;
  support: number;
  resistance: number;
  latest_price: number;
  bad_entry_zone: string;
  bad_entry_label: string;
}

export interface BacktestCurvePoint {
  date: string;
  portfolio_value: number;
  total_invested: number;
  weights?: Record<string, number>;
}

export interface BacktestSummary {
  days: number;
  total_invested: number;
  final_value: number;
  roi_pct: number;
  cagr_pct: number;
}

export interface BacktestResult {
  symbols: string[];
  skipped: string[];
  score_weighted: { summary: BacktestSummary; curve: BacktestCurvePoint[] };
  equal_weight: { summary: BacktestSummary; curve: BacktestCurvePoint[] };
  final_shares: Record<string, number>;
}

export type NewsCategory =
  | "top"
  | "markets"
  | "economy"
  | "fed"
  | "policy"
  | "earnings";

export interface NewsItem {
  id: string;
  title: string;
  url: string;
  source: string;
  category: string;
  published_at: string | null;
  summary: string | null;
  symbols: string[];
}

export interface EconomicEvent {
  id: string;
  date: string;
  time: string | null;
  event: string;
  country: string;
  impact: "high" | "medium" | "low";
  actual: number | null;
  estimate: number | null;
  previous: number | null;
}

export type StrategyType =
  | "cash_secured_put"
  | "covered_call"
  | "short_put"
  | "short_call"
  | "long_call"
  | "long_put"
  | "put_credit_spread"
  | "call_credit_spread"
  | "put_debit_spread"
  | "call_debit_spread"
  | "iron_condor"
  | "custom";

export interface OptionLeg {
  leg_index: number;
  option_type: "put" | "call";
  side: "sell_to_open" | "buy_to_close" | "buy_to_open" | "sell_to_close";
  strike: number;
  premium_per_contract: number;
  expiration_date?: string | null;
}

export interface OptionTradeCreatePayload {
  strategy_type: StrategyType;
  ticker: string;
  legs: OptionLeg[];
  contracts: number;
  executed_at: string;
  expiration_date: string;
  net_credit_debit: number;
  collateral_override?: number | null;
  broker?: string | null;
  notes?: string | null;
}

export interface OptionTradeMetrics {
  collateral_required: number;
  total_premium_dollars: number;
  days_to_expiration: number;
  return_on_capital_pct: number;
  annualized_roc_pct: number;
  premium_pct_of_strike?: number;
  breach_price?: number | null;
  assignment_cost_basis?: number | null;
  btc_50pct_target_per_contract?: number | null;
  max_profit_dollars?: number | null;
  max_loss_dollars?: number | null;
  short_strike?: number | null;
  is_short_premium?: boolean;
}

export type OptionTradeUpdatePayload = Partial<Omit<OptionTradeCreatePayload, "ticker">>;

export interface OptionTrade {
  id: number;
  status: "open" | "closed" | "assigned" | "expired";
  strategy_type: StrategyType;
  ticker: string;
  broker: string | null;
  executed_at: string;
  expiration_date: string;
  contracts: number;
  net_credit_debit: number;
  collateral_required: number;
  collateral_override: number | null;
  notes: string | null;
  metrics: OptionTradeMetrics;
  advisory: Record<string, unknown>;
  closed_at: string | null;
  close_net_per_contract: number | null;
  realized_pnl: number | null;
  legs: OptionLeg[];
  created_at: string;
  updated_at: string;
}

export interface PreTradeIndicator {
  id: string;
  label: string;
  value: string;
  status: "good" | "neutral" | "caution" | "bad";
  impact: string;
  annualized?: string | null;
}

export interface PreTradeAnalysis {
  overall_score: "favorable" | "mixed" | "high_risk";
  summary: string;
  indicators: PreTradeIndicator[];
  recommendations: string[];
}

export interface MarketContext {
  as_of: string;
  sentiment: {
    label: string;
    display: string;
    vix: number | null;
    vix_change_pct: number | null;
    spy_change_pct: number | null;
    qqq_change_pct: number | null;
    impact: string;
  };
  economic_events: EconomicEvent[];
  finnhub_configured: boolean;
  catalysts: {
    earnings_headlines: NewsItem[];
    market_headlines: NewsItem[];
    economy_headlines: NewsItem[];
  };
  alerts: { level: string; text: string }[];
  footer_note: string;
  disclaimer: string;
}

export interface ParseImageResult {
  draft: Partial<OptionTradeCreatePayload> & { broker?: string };
  detected_strategy: string;
  strategy_confidence: number;
  parse_confidence: number;
  uncertain_fields: string[];
  trade_type_suggestions: {
    strategy: string;
    reason: string;
    impact: string;
    recommended_checks: string[];
  }[];
  raw_text_preview?: string;
}

export interface CspSuggestedContract {
  strike: number;
  expiration: string;
  dte: number;
  premium_mid: number;
  delta: number;
  option_type?: "put" | "call";
  side?: "sell_to_open" | "buy_to_open";
  target_delta?: number | null;
  implied_volatility: number | null;
  bid: number | null;
  ask: number | null;
  spread_pct: number | null;
  open_interest: number | null;
  volume: number | null;
  otm_pct: number | null;
  liquidity_ok: boolean;
  note?: string | null;
}

export interface CspScreenResult {
  ticker: string;
  strategy?: string;
  strategy_label?: string;
  overall_verdict: "favorable" | "mixed" | "high_risk";
  recommendation_color: "green" | "red";
  sections: Record<string, unknown>;
  pros: string[];
  cons: string[];
  verdict: {
    recommended_strike: number | null;
    margin_of_safety_pct: number | null;
    summary: string;
  };
  markdown: string;
  suggested_contract: CspSuggestedContract | null;
  disclaimer: string;
}

export interface CspMonitorResult {
  ticker: string;
  strike_price: number;
  expiration_date: string;
  initial_premium: number;
  current_spot: number | null;
  current_mid: number | null;
  unrealized_pnl_pct: number | null;
  trigger_close_alert: boolean;
  breached: boolean;
  net_cost_basis: number;
  recommendation_color: "green" | "red";
  recommendation: string;
  markdown: string;
  bid?: number | null;
  ask?: number | null;
  spread_pct?: number | null;
  open_interest?: number | null;
  liquidity_ok?: boolean | null;
  disclaimer: string;
}

export interface TickerAnalysisNote {
  ticker: string;
  note_key: string;
  content: string;
  updated_at: string | null;
}

export interface CspMonitoringAlert {
  trade_id: number;
  ticker: string;
  trigger_close_alert: boolean;
  breached: boolean;
  unrealized_pnl_pct: number | null;
}

export const api = {
  search: (q: string) =>
    request<{ query: string; results: SearchResult[] }>(
      `/api/search?q=${encodeURIComponent(q)}`,
    ),
  stockOverview: (symbol: string, period = "1y") =>
    request<StockOverview>(`/api/stocks/${symbol}?period=${period}`),
  stockHistory: (symbol: string, period = "1y") =>
    request<{ symbol: string; period: string; candles: Candle[] }>(
      `/api/stocks/${symbol}/history?period=${period}`,
    ),
  stockFinancials: (symbol: string) =>
    request<{
      symbol: string;
      income_stmt: StatementPayload | null;
      balance_sheet: StatementPayload | null;
      cash_flow: StatementPayload | null;
    }>(`/api/stocks/${symbol}/financials`),
  stockEarnings: (symbol: string) =>
    request<{ symbol: string; earnings: { year: number; net_income: number }[] }>(
      `/api/stocks/${symbol}/earnings`,
    ),
  stockTrend: (symbol: string) =>
    request<TrendContext>(`/api/stocks/${symbol}/trend`),
  portfolio: (portfolioId?: number) => {
    const qs = portfolioId ? `?portfolio_id=${portfolioId}` : "";
    return request<{ portfolio_id: number; name: string; symbols: string[] }>(`/api/portfolio${qs}`);
  },
  listPortfolios: () =>
    request<{ portfolios: PortfolioBucket[] }>(`/api/portfolio/portfolios`),
  createPortfolio: (name: string) =>
    request<PortfolioBucket>(`/api/portfolio/portfolios`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  portfolioGrid: (portfolioId?: number) => {
    const qs = portfolioId ? `?portfolio_id=${portfolioId}` : "";
    return request<PortfolioGridResponse>(`/api/portfolio/grid${qs}`);
  },
  industryGrid: (industry: string) =>
    request<IndustryGridResponse>(
      `/api/admin/industries/${encodeURIComponent(industry)}/grid`,
    ),
  addToPortfolio: (symbol: string, portfolioId?: number) =>
    request(`/api/portfolio/${symbol}${portfolioId ? `?portfolio_id=${portfolioId}` : ""}`, {
      method: "POST",
    }),
  importPortfolioCsv: async (file: File, portfolioId?: number) => {
    const form = new FormData();
    form.append("file", file);
    const qs = portfolioId ? `?portfolio_id=${portfolioId}` : "";
    const res = await fetch(`${API_BASE}/api/portfolio/import-csv${qs}`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      } catch {
        /* keep statusText */
      }
      throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<PortfolioImportResult>;
  },
  removeFromPortfolio: (symbol: string, portfolioId?: number) =>
    request(`/api/portfolio/${symbol}${portfolioId ? `?portfolio_id=${portfolioId}` : ""}`, {
      method: "DELETE",
    }),
  automationScan: (symbol: string) =>
    request<AutomationResponse>(`/api/automation/${symbol}`),
  aiPoints: () =>
    request<{ points: { number: number; title: string; instruction: string }[] }>(
      `/api/ai/points`,
    ),
  aiSummary: (symbol: string) =>
    request<{ symbol: string; summary: string }>(`/api/ai/summary`, {
      method: "POST",
      body: JSON.stringify({ symbol }),
    }),
  aiPoint: (symbol: string, point: number) =>
    request<{ symbol: string; point: number; content: string }>(`/api/ai/point`, {
      method: "POST",
      body: JSON.stringify({ symbol, point }),
    }),
  aiWallStreet: (symbol: string, period = "1y", force = true) =>
    request<WallStreetAnalysis>(`/api/ai/wall-street`, {
      method: "POST",
      body: JSON.stringify({ symbol, period, force }),
    }),
  aiWallStreetCache: (symbol: string) =>
    request<WallStreetCacheLookup>(`/api/ai/wall-street/${encodeURIComponent(symbol)}`),
  adminIndustries: () =>
    request<{
      industries: Record<string, { symbol: string; company_name: string | null }[]>;
    }>(`/api/admin/industries`),
  assignIndustries: (symbol: string, industries: string[]) =>
    request<{ symbol: string; results: Record<string, string> }>(
      `/api/admin/industries/assign`,
      { method: "POST", body: JSON.stringify({ symbol, industries }) },
    ),
  removeIndustryAssignment: (symbol: string, industry: string) =>
    request<{ symbol: string; industry: string; removed: boolean }>(
      `/api/admin/industries/stock/${symbol}/${encodeURIComponent(industry)}`,
      { method: "DELETE" },
    ),
  dcaBacktest: (body: {
    symbols: string[];
    daily_invest: number;
    start_date: string;
    end_date: string;
  }) =>
    request<BacktestResult>(`/api/dca/backtest`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  newsFeed: (category: NewsCategory = "top", limit = 40) =>
    request<{ category: string; items: NewsItem[] }>(
      `/api/news/feed?category=${category}&limit=${limit}`,
    ),
  newsPortfolio: () =>
    request<{ symbols: string[]; items: NewsItem[] }>(`/api/news/portfolio`),
  newsCalendar: (days = 7) =>
    request<{
      days: number;
      finnhub_configured: boolean;
      events: EconomicEvent[];
    }>(`/api/news/calendar?days=${days}`),

  // Options journal
  optionsStrategies: () =>
    request<{ strategies: { id: string; label: string; legs: number; short_premium: boolean | null }[] }>(
      `/api/options/strategies`,
    ),
  marketContext: () => request<MarketContext>(`/api/options/market/context`),
  optionsPreTradeAnalyze: (body: OptionTradeCreatePayload) =>
    request<PreTradeAnalysis>(`/api/options/pre-trade/analyze`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cspScreen: (ticker: string, strategy?: StrategyType) =>
    request<CspScreenResult>(`/api/options/csp/screen`, {
      method: "POST",
      body: JSON.stringify({ ticker, strategy: strategy ?? "cash_secured_put" }),
    }),
  getTickerNote: (ticker: string, noteKey = "liquidity") =>
    request<TickerAnalysisNote>(
      `/api/options/ticker-notes/${encodeURIComponent(ticker)}?note_key=${encodeURIComponent(noteKey)}`,
    ),
  putTickerNote: (ticker: string, content: string, noteKey = "liquidity") =>
    request<TickerAnalysisNote>(
      `/api/options/ticker-notes/${encodeURIComponent(ticker)}?note_key=${encodeURIComponent(noteKey)}`,
      { method: "PUT", body: JSON.stringify({ content }) },
    ),
  cspMonitorTrade: (id: number) => request<CspMonitorResult>(`/api/options/trades/${id}/monitor`),
  cspMonitoringSummary: () =>
    request<{ alerts: CspMonitoringAlert[] }>(`/api/options/monitoring/summary`),
  optionsParseText: (text: string, broker?: string) =>
    request<ParseImageResult>(`/api/options/parse-text`, {
      method: "POST",
      body: JSON.stringify({ text, broker }),
    }),
  optionsParseImage: async (file: File, broker?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (broker) form.append("broker", broker);
    const res = await fetch(`${API_BASE}/api/options/parse-image`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      } catch {
        /* keep statusText */
      }
      throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<ParseImageResult>;
  },
  optionsTrades: (params?: { status?: string; ticker?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.ticker) q.set("ticker", params.ticker);
    const qs = q.toString();
    return request<{ trades: OptionTrade[] }>(`/api/options/trades${qs ? `?${qs}` : ""}`);
  },
  optionsTrade: (id: number) => request<OptionTrade>(`/api/options/trades/${id}`),
  optionsCreateTrade: (body: OptionTradeCreatePayload) =>
    request<OptionTrade>(`/api/options/trades`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  optionsUpdateTrade: (id: number, body: OptionTradeUpdatePayload) =>
    request<OptionTrade>(`/api/options/trades/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  optionsCloseTrade: (id: number, body: { closed_at: string; close_net_per_contract: number; assigned?: boolean }) =>
    request<OptionTrade>(`/api/options/trades/${id}/close`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  optionsDeleteTrade: (id: number) =>
    request<{ deleted: boolean; id: number }>(`/api/options/trades/${id}`, { method: "DELETE" }),
};
