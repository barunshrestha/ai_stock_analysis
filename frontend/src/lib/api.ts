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

export interface PortfolioGridResponse {
  rows: PortfolioGridRow[];
  errors: Record<string, string>;
}

export interface IndustryGridResponse extends PortfolioGridResponse {
  industry: string;
}

export type PortfolioView =
  | { mode: "portfolio" }
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
  portfolio: () => request<{ symbols: string[] }>(`/api/portfolio`),
  portfolioGrid: () => request<PortfolioGridResponse>(`/api/portfolio/grid`),
  industryGrid: (industry: string) =>
    request<IndustryGridResponse>(
      `/api/admin/industries/${encodeURIComponent(industry)}/grid`,
    ),
  addToPortfolio: (symbol: string) =>
    request(`/api/portfolio/${symbol}`, { method: "POST" }),
  removeFromPortfolio: (symbol: string) =>
    request(`/api/portfolio/${symbol}`, { method: "DELETE" }),
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
};
