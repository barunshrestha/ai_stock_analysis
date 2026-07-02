"use client";

import type { StockMetrics } from "@/lib/api";
import {
  changeColor,
  formatCompact,
  formatNumber,
  formatPct,
  formatPrice,
} from "@/lib/format";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MetricItem {
  label: string;
  value: string;
  colorClass?: string;
}

/** Key at-a-glance metrics shown on the Overview tab. */
export function MetricCards({ metrics }: { metrics: StockMetrics }) {
  const items: MetricItem[] = [
    { label: "Market Cap", value: formatCompact(metrics.market_cap) },
    { label: "P/E (TTM)", value: formatNumber(metrics.pe_ratio) },
    { label: "EPS", value: formatNumber(metrics.eps) },
    {
      label: "Dividend Yield",
      value: formatPct(metrics.dividend_yield_pct),
    },
    { label: "Volume", value: formatCompact(metrics.volume) },
    { label: "Beta", value: formatNumber(metrics.beta) },
    { label: "52W High", value: formatPrice(metrics.week_52_high) },
    { label: "52W Low", value: formatPrice(metrics.week_52_low) },
    {
      label: "1W Change",
      value: formatPct(metrics.weekly_change_pct, { signed: true }),
      colorClass: changeColor(metrics.weekly_change_pct),
    },
    {
      label: "1M Change",
      value: formatPct(metrics.monthly_change_pct, { signed: true }),
      colorClass: changeColor(metrics.monthly_change_pct),
    },
    {
      label: "1Y Change",
      value: formatPct(metrics.yearly_change_pct, { signed: true }),
      colorClass: changeColor(metrics.yearly_change_pct),
    },
    {
      label: "Volatility (1Y)",
      value: formatPct(metrics.volatility_annual_pct),
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {items.map((item) => (
        <Card key={item.label} className="py-3">
          <CardContent className="px-3">
            <div className="text-xs text-muted-foreground">{item.label}</div>
            <div
              className={cn(
                "mt-0.5 truncate text-sm font-semibold tabular-nums",
                item.colorClass,
              )}
            >
              {item.value}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
