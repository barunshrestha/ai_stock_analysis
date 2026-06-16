"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Bot, CheckCircle2, ChevronDown, XCircle } from "lucide-react";

import { api } from "@/lib/api";
import {
  changeColor,
  formatCompact,
  formatNumber,
  formatPct,
  formatPrice,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PriceChart, type PriceLine } from "@/components/stocks/price-chart";

export function AutomationScan({ symbol }: { symbol: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["automation", symbol],
    queryFn: () => api.automationScan(symbol),
  });

  const priceLines: PriceLine[] = React.useMemo(() => {
    const params = data?.trade_params;
    if (!params) return [];
    const first = params.setups[0];
    return [
      { price: first?.entry ?? params.entry_price, title: "Entry", color: "#3b82f6" },
      { price: first?.stop_loss ?? 0, title: "Stop", color: "#ef4444" },
      { price: first?.target_1 ?? 0, title: "T1", color: "#22c55e" },
      { price: first?.target_2 ?? 0, title: "T2", color: "#16a34a" },
    ].filter((l) => l.price > 0);
  }, [data]);

  if (isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (isError) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        Scan failed: {error instanceof Error ? error.message : "unknown error"}
      </p>
    );
  }

  const setup = data.setup;
  const params = data.trade_params;
  const ind = setup?.indicators;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Bot className="size-6 text-muted-foreground" />
        <h1 className="font-mono text-2xl font-bold tracking-tight sm:text-3xl">
          {symbol}
        </h1>
        <Badge variant="secondary">Trade Setup Scan</Badge>
      </div>

      {data.warning && (
        <p className="rounded-md border border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          {data.warning}
        </p>
      )}

      {setup && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              {setup.setup_detected ? (
                <>
                  <CheckCircle2 className="size-5 text-positive" />
                  Setup detected
                </>
              ) : (
                <>
                  <XCircle className="size-5 text-muted-foreground" />
                  No setup right now
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {setup.details.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
            <details className="group text-sm">
              <summary className="flex cursor-pointer select-none items-center gap-1 text-muted-foreground hover:text-foreground">
                <ChevronDown className="size-4 transition-transform group-open:rotate-180" />
                What do these indicators mean?
              </summary>
              <dl className="mt-2 space-y-2 border-l pl-4">
                {Object.entries(setup.definitions).map(([term, def]) => (
                  <div key={term}>
                    <dt className="font-medium">{term}</dt>
                    <dd className="text-muted-foreground">{def}</dd>
                  </div>
                ))}
              </dl>
            </details>
          </CardContent>
        </Card>
      )}

      {ind && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
          {[
            { label: "Price", value: formatPrice(ind.current_price) },
            {
              label: "Day Change",
              value: formatPct(ind.price_change_pct, { signed: true }),
              colorClass: changeColor(ind.price_change_pct),
            },
            { label: "20-Day SMA", value: formatPrice(ind.sma_20) },
            { label: "RSI (14)", value: formatNumber(ind.rsi, 1) },
            { label: "ATR", value: formatNumber(ind.atr, 2) },
            { label: "Day High", value: formatPrice(ind.high) },
            { label: "Day Low", value: formatPrice(ind.low) },
            { label: "Volume", value: formatCompact(ind.volume) },
          ].map((item) => (
            <Card key={item.label} className="py-3">
              <CardContent className="px-3">
                <div className="text-xs text-muted-foreground">{item.label}</div>
                <div
                  className={cn(
                    "mt-0.5 truncate text-sm font-semibold tabular-nums",
                    "colorClass" in item ? item.colorClass : undefined,
                  )}
                >
                  {item.value}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Setup Visualization (entry, stop, targets)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <PriceChart symbol={symbol} defaultPeriod="3mo" priceLines={priceLines} />
        </CardContent>
      </Card>

      {params && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Trade Setups by Timeframe
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timeframe</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead className="text-right">Entry</TableHead>
                    <TableHead className="text-right">Stop Loss</TableHead>
                    <TableHead className="text-right">Target 1</TableHead>
                    <TableHead className="text-right">Target 2</TableHead>
                    <TableHead className="text-right">Risk/Share</TableHead>
                    <TableHead className="text-right">R:R (T1 / T2)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {params.setups.map((s) => (
                    <TableRow key={s.timeframe}>
                      <TableCell>
                        <div className="font-medium">{s.timeframe}</div>
                        <div className="max-w-56 truncate text-xs text-muted-foreground">
                          {s.description}
                        </div>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">
                        {s.duration}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatPrice(s.entry)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-negative">
                        {formatPrice(s.stop_loss)}
                        <div className="text-xs text-muted-foreground">
                          -{formatNumber(s.stop_loss_pct, 1)}%
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-positive">
                        {formatPrice(s.target_1)}
                        <div className="text-xs text-muted-foreground">
                          +{formatNumber(s.target_1_pct, 1)}%
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-positive">
                        {formatPrice(s.target_2)}
                        <div className="text-xs text-muted-foreground">
                          +{formatNumber(s.target_2_pct, 1)}%
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatPrice(s.risk_per_share)}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-right tabular-nums">
                        {s.risk_reward_1} / {s.risk_reward_2}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Stops and targets derived from ATR ({formatNumber(params.atr, 2)})
              × {params.atr_multiplier}. Generated{" "}
              {new Date(params.generated_at).toLocaleString()}. Not financial
              advice.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
