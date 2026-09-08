import type { OptionTrade } from "@/lib/api";

export type TimeframePreset = "1d" | "7d" | "30d";

export type DashboardCloseKind = "closed_early" | "expired" | "assigned";

export interface TimeWindow {
  start: Date;
  end: Date;
  label: string;
  preset: TimeframePreset;
}

export interface ClosedEarlyRow {
  trade: OptionTrade;
  daysHeld: number;
  originalDte: number;
  progressPct: number;
  pnl: number;
}

export interface DashboardAggregate {
  window: TimeWindow;
  tradeCountInWindow: number;
  closedEarly: ClosedEarlyRow[];
  expired: OptionTrade[];
  assigned: OptionTrade[];
  newPositions: OptionTrade[];
  premiumRealized: number;
  newPremiumOpened: number;
  avgRoiClosed: number | null;
  closedEarlyCount: number;
  expiredCount: number;
  assignedCount: number;
  spreadPremiumInRealized: number;
  spreadCloseCount: number;
}

export interface CalendarDayCell {
  dateKey: string; // YYYY-MM-DD
  dayOfMonth: number;
  inMonth: boolean;
  pnl: number;
  closedCount: number;
  newCount: number;
}

export interface CalendarWeek {
  days: CalendarDayCell[];
  weekPnl: number;
}

export interface CalendarMonth {
  year: number;
  month: number; // 0-11
  weeks: CalendarWeek[];
  monthPnl: number;
  upDays: number;
  downDays: number;
}

function startOfLocalDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0, 0);
}

function endOfLocalDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 999);
}

function parseDateOnly(iso: string): Date {
  const datePart = iso.slice(0, 10);
  const [y, m, d] = datePart.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function toDateKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function daysBetween(a: Date, b: Date): number {
  const ms = startOfLocalDay(b).getTime() - startOfLocalDay(a).getTime();
  return Math.round(ms / 86_400_000);
}

function formatRangeLabel(start: Date, end: Date): string {
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  return `${start.toLocaleDateString(undefined, opts)} – ${end.toLocaleDateString(undefined, opts)}`;
}

export function getTimeWindow(preset: TimeframePreset, now: Date = new Date()): TimeWindow {
  const end = endOfLocalDay(now);
  const startBase = startOfLocalDay(now);
  const daysBack = preset === "1d" ? 0 : preset === "7d" ? 6 : 29;
  const start = new Date(startBase);
  start.setDate(start.getDate() - daysBack);
  return {
    start,
    end,
    label: formatRangeLabel(start, end),
    preset,
  };
}

export function entryPremiumDollars(trade: OptionTrade): number {
  const fromMetrics = trade.metrics?.total_premium_dollars;
  if (typeof fromMetrics === "number" && Number.isFinite(fromMetrics)) {
    return fromMetrics;
  }
  return trade.net_credit_debit * 100 * trade.contracts;
}

export function primaryOptionType(trade: OptionTrade): "put" | "call" {
  const shortLeg = trade.legs.find((l) => l.side === "sell_to_open");
  if (shortLeg) return shortLeg.option_type;
  return trade.legs[0]?.option_type ?? "put";
}

export function primaryStrike(trade: OptionTrade): number | null {
  const shortLeg = trade.legs.find((l) => l.side === "sell_to_open");
  if (shortLeg) return shortLeg.strike;
  return trade.legs[0]?.strike ?? trade.metrics?.short_strike ?? null;
}

function inWindow(ts: string | null | undefined, window: TimeWindow): boolean {
  if (!ts) return false;
  const t = new Date(ts);
  if (Number.isNaN(t.getTime())) return false;
  return t >= window.start && t <= window.end;
}

export function classifyCloseKind(trade: OptionTrade): DashboardCloseKind | null {
  if (trade.status === "assigned") return "assigned";
  if (trade.status === "expired") return "expired";
  if (trade.status !== "closed" || !trade.closed_at) return null;
  const closed = parseDateOnly(trade.closed_at);
  const exp = parseDateOnly(trade.expiration_date);
  if (closed >= exp) return "expired";
  return "closed_early";
}

export function closedEarlyProgress(trade: OptionTrade): Omit<ClosedEarlyRow, "trade" | "pnl"> | null {
  if (!trade.closed_at) return null;
  const executed = parseDateOnly(trade.executed_at);
  const closed = parseDateOnly(trade.closed_at);
  const exp = parseDateOnly(trade.expiration_date);
  const originalDte = Math.max(1, daysBetween(executed, exp));
  const daysHeld = Math.max(0, daysBetween(executed, closed));
  const progressPct = Math.min(100, Math.round((100 * daysHeld) / originalDte));
  return { daysHeld, originalDte, progressPct };
}

function isSpreadStrategy(trade: OptionTrade): boolean {
  return (
    trade.strategy_type.includes("spread") || trade.strategy_type === "iron_condor"
  );
}

export function aggregateDashboard(
  trades: OptionTrade[],
  preset: TimeframePreset,
  now: Date = new Date(),
): DashboardAggregate {
  const window = getTimeWindow(preset, now);

  const closedEarly: ClosedEarlyRow[] = [];
  const expired: OptionTrade[] = [];
  const assigned: OptionTrade[] = [];
  const newPositions: OptionTrade[] = [];

  let premiumRealized = 0;
  let newPremiumOpened = 0;
  let spreadPremiumInRealized = 0;
  let spreadCloseCount = 0;
  const roiSamples: number[] = [];
  const idsInWindow = new Set<number>();

  for (const trade of trades) {
    if (inWindow(trade.executed_at, window)) {
      newPositions.push(trade);
      newPremiumOpened += entryPremiumDollars(trade);
      idsInWindow.add(trade.id);
    }

    if (!inWindow(trade.closed_at, window)) continue;
    idsInWindow.add(trade.id);

    const kind = classifyCloseKind(trade);
    if (!kind) continue;

    const pnl = trade.realized_pnl ?? 0;
    premiumRealized += pnl;

    if (kind === "closed_early") {
      const progress = closedEarlyProgress(trade);
      if (progress) {
        closedEarly.push({ trade, pnl, ...progress });
      }
    } else if (kind === "expired") {
      expired.push(trade);
    } else {
      assigned.push(trade);
    }

    if (isSpreadStrategy(trade)) {
      spreadPremiumInRealized += pnl;
      spreadCloseCount += 1;
    }

    const entry = Math.abs(entryPremiumDollars(trade));
    if (entry > 0 && trade.realized_pnl != null) {
      roiSamples.push(trade.realized_pnl / entry);
    }
  }

  closedEarly.sort((a, b) => (b.trade.closed_at ?? "").localeCompare(a.trade.closed_at ?? ""));
  expired.sort((a, b) => (b.closed_at ?? "").localeCompare(a.closed_at ?? ""));
  assigned.sort((a, b) => (b.closed_at ?? "").localeCompare(a.closed_at ?? ""));
  newPositions.sort((a, b) => b.executed_at.localeCompare(a.executed_at));

  const avgRoiClosed =
    roiSamples.length === 0
      ? null
      : (roiSamples.reduce((s, v) => s + v, 0) / roiSamples.length) * 100;

  return {
    window,
    tradeCountInWindow: idsInWindow.size,
    closedEarly,
    expired,
    assigned,
    newPositions,
    premiumRealized,
    newPremiumOpened,
    avgRoiClosed,
    closedEarlyCount: closedEarly.length,
    expiredCount: expired.length,
    assignedCount: assigned.length,
    spreadPremiumInRealized,
    spreadCloseCount,
  };
}

export function buildCalendarMonth(
  year: number,
  month: number,
  trades: OptionTrade[],
): CalendarMonth {
  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  const startPad = first.getDay(); // Sun=0

  const pnlByDay = new Map<string, number>();
  const closedByDay = new Map<string, number>();
  const newByDay = new Map<string, number>();

  for (const trade of trades) {
    if (trade.closed_at) {
      const key = trade.closed_at.slice(0, 10);
      const d = parseDateOnly(key);
      if (d.getFullYear() === year && d.getMonth() === month) {
        pnlByDay.set(key, (pnlByDay.get(key) ?? 0) + (trade.realized_pnl ?? 0));
        closedByDay.set(key, (closedByDay.get(key) ?? 0) + 1);
      }
    }
    const openKey = trade.executed_at.slice(0, 10);
    const od = parseDateOnly(openKey);
    if (od.getFullYear() === year && od.getMonth() === month) {
      newByDay.set(openKey, (newByDay.get(openKey) ?? 0) + 1);
    }
  }

  const cells: CalendarDayCell[] = [];
  for (let i = 0; i < startPad; i++) {
    const d = new Date(year, month, 1 - (startPad - i));
    cells.push({
      dateKey: toDateKey(d),
      dayOfMonth: d.getDate(),
      inMonth: false,
      pnl: 0,
      closedCount: 0,
      newCount: 0,
    });
  }
  for (let day = 1; day <= last.getDate(); day++) {
    const d = new Date(year, month, day);
    const key = toDateKey(d);
    cells.push({
      dateKey: key,
      dayOfMonth: day,
      inMonth: true,
      pnl: pnlByDay.get(key) ?? 0,
      closedCount: closedByDay.get(key) ?? 0,
      newCount: newByDay.get(key) ?? 0,
    });
  }
  while (cells.length % 7 !== 0) {
    const lastCell = cells[cells.length - 1];
    const d = parseDateOnly(lastCell.dateKey);
    d.setDate(d.getDate() + 1);
    cells.push({
      dateKey: toDateKey(d),
      dayOfMonth: d.getDate(),
      inMonth: false,
      pnl: 0,
      closedCount: 0,
      newCount: 0,
    });
  }

  const weeks: CalendarWeek[] = [];
  for (let i = 0; i < cells.length; i += 7) {
    const days = cells.slice(i, i + 7);
    const weekPnl = days.filter((c) => c.inMonth).reduce((s, c) => s + c.pnl, 0);
    weeks.push({ days, weekPnl });
  }

  let monthPnl = 0;
  let upDays = 0;
  let downDays = 0;
  for (const c of cells) {
    if (!c.inMonth) continue;
    monthPnl += c.pnl;
    if (c.closedCount > 0 || c.pnl !== 0) {
      if (c.pnl > 0) upDays += 1;
      else if (c.pnl < 0) downDays += 1;
    }
  }

  return { year, month, weeks, monthPnl, upDays, downDays };
}

export function tradesForDay(trades: OptionTrade[], dateKey: string) {
  const closed = trades.filter((t) => t.closed_at?.slice(0, 10) === dateKey);
  const opened = trades.filter((t) => t.executed_at.slice(0, 10) === dateKey);
  return { closed, opened };
}

export function formatSignedMoney(n: number): string {
  const abs = Math.abs(n).toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
  });
  if (n > 0) return `+${abs}`;
  if (n < 0) return `-${abs.replace("-", "")}`;
  return abs;
}
