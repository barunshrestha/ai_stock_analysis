"use client";

import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Briefcase, Loader2, Play, X } from "lucide-react";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { DcaResults } from "@/components/dca/dca-results";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

const MAX_SYMBOLS = 20;

export function DcaBacktest() {
  const [symbols, setSymbols] = React.useState<string[]>([]);
  const [symbolInput, setSymbolInput] = React.useState("");
  const [dailyInvest, setDailyInvest] = React.useState("100");
  const [startDate, setStartDate] = React.useState(isoDaysAgo(182));
  const [endDate, setEndDate] = React.useState(isoDaysAgo(0));

  const portfolio = useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.portfolio(),
  });

  const backtest = useMutation({
    mutationFn: () =>
      api.dcaBacktest({
        symbols,
        daily_invest: Number(dailyInvest),
        start_date: startDate,
        end_date: endDate,
      }),
  });

  const addSymbol = (raw: string) => {
    const symbol = raw.trim().toUpperCase();
    if (!symbol || symbols.includes(symbol) || symbols.length >= MAX_SYMBOLS)
      return;
    setSymbols((prev) => [...prev, symbol]);
    setSymbolInput("");
  };

  const amountValid = Number(dailyInvest) > 0;
  const datesValid = startDate < endDate;
  const canRun =
    symbols.length > 0 && amountValid && datesValid && !backtest.isPending;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Backtest Setup</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">
              Stocks ({symbols.length}/{MAX_SYMBOLS})
            </label>
            <div className="flex flex-wrap gap-1.5">
              {symbols.map((s) => (
                <Badge key={s} variant="secondary" className="gap-1 font-mono">
                  {s}
                  <button
                    onClick={() =>
                      setSymbols((prev) => prev.filter((x) => x !== s))
                    }
                    aria-label={`Remove ${s}`}
                    className="rounded-full hover:text-negative"
                  >
                    <X className="size-3" />
                  </button>
                </Badge>
              ))}
              {symbols.length === 0 && (
                <span className="text-sm text-muted-foreground">
                  No stocks selected yet.
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Input
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addSymbol(symbolInput);
                  }
                }}
                placeholder="Add ticker (e.g. AAPL) and press Enter"
                className="h-9 w-64"
              />
              <Button
                variant="outline"
                size="sm"
                className="h-9"
                onClick={() => addSymbol(symbolInput)}
                disabled={!symbolInput.trim()}
              >
                Add
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-9"
                disabled={!portfolio.data || portfolio.data.symbols.length === 0}
                onClick={() =>
                  setSymbols(
                    (portfolio.data?.symbols ?? []).slice(0, MAX_SYMBOLS),
                  )
                }
              >
                <Briefcase className="size-4" />
                Use my portfolio
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <label htmlFor="dca-amount" className="text-sm font-medium">
                Daily investment ($)
              </label>
              <Input
                id="dca-amount"
                type="number"
                min="1"
                step="10"
                value={dailyInvest}
                onChange={(e) => setDailyInvest(e.target.value)}
                className="h-9"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="dca-start" className="text-sm font-medium">
                Start date
              </label>
              <Input
                id="dca-start"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="h-9"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="dca-end" className="text-sm font-medium">
                End date
              </label>
              <Input
                id="dca-end"
                type="date"
                value={endDate}
                max={isoDaysAgo(0)}
                onChange={(e) => setEndDate(e.target.value)}
                className="h-9"
              />
            </div>
          </div>
          {!datesValid && (
            <p className="text-xs text-negative">
              Start date must be before end date.
            </p>
          )}

          <Button onClick={() => backtest.mutate()} disabled={!canRun}>
            {backtest.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Running backtest… this can take a minute
              </>
            ) : (
              <>
                <Play className="size-4" />
                Run Backtest
              </>
            )}
          </Button>
          {backtest.isError && (
            <p className="text-sm text-negative">
              {backtest.error instanceof Error
                ? backtest.error.message
                : "Backtest failed."}
            </p>
          )}
        </CardContent>
      </Card>

      {backtest.data && <DcaResults result={backtest.data} />}
    </div>
  );
}
