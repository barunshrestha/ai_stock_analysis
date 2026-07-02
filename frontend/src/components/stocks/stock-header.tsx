"use client";

import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import type { StockOverview } from "@/lib/api";
import { changeColor, formatPct, formatPrice } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function StockHeader({ overview }: { overview: StockOverview }) {
  const { metrics } = overview;
  const change = metrics.daily_change_pct;

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="truncate text-2xl font-bold tracking-tight sm:text-3xl">
            {overview.name}
          </h1>
          <span className="font-mono text-sm text-muted-foreground">
            {overview.symbol}
            {overview.exchange ? ` · ${overview.exchange}` : ""}
          </span>
        </div>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {overview.sector && <Badge variant="secondary">{overview.sector}</Badge>}
          {overview.industry && <Badge variant="outline">{overview.industry}</Badge>}
        </div>
      </div>
      <div className="shrink-0 text-left sm:text-right">
        <div className="text-3xl font-bold tabular-nums sm:text-4xl">
          {formatPrice(metrics.current_price, overview.currency ?? "USD")}
        </div>
        <div
          className={cn(
            "flex items-center gap-1 text-sm font-medium sm:justify-end",
            changeColor(change),
          )}
        >
          {change != null &&
            (change >= 0 ? (
              <ArrowUpRight className="size-4" />
            ) : (
              <ArrowDownRight className="size-4" />
            ))}
          {formatPct(change, { signed: true })} today
        </div>
      </div>
    </div>
  );
}
