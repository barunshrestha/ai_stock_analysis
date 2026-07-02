"use client";

import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  BrainCircuit,
  ChevronDown,
  Loader2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendChart } from "@/components/stocks/trend-chart";

function ollamaErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 503) {
    return "Ollama is not running. Start it with `ollama serve` and try again.";
  }
  return error instanceof Error ? error.message : "Analysis failed.";
}

function TrendCard({ symbol }: { symbol: string }) {
  const { data, isPending, isError } = useQuery({
    queryKey: ["trend", symbol],
    queryFn: () => api.stockTrend(symbol),
  });

  if (isPending) return <Skeleton className="h-28 w-full" />;
  if (isError || !data) return null;

  const up = data.trend_label.toLowerCase().includes("up");

  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-3">
        <div className="flex items-center gap-2">
          {up ? (
            <TrendingUp className="size-5 text-positive" />
          ) : (
            <TrendingDown className="size-5 text-negative" />
          )}
          <div>
            <div className="text-xs text-muted-foreground">Trend</div>
            <div className={cn("font-semibold", up ? "text-positive" : "text-negative")}>
              {data.trend_label}
            </div>
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Latest Price</div>
          <div className="font-semibold tabular-nums">
            {formatPrice(data.latest_price)}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Support</div>
          <div className="font-semibold tabular-nums text-positive">
            {formatPrice(data.support)}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Resistance</div>
          <div className="font-semibold tabular-nums text-negative">
            {formatPrice(data.resistance)}
          </div>
        </div>
        <div className="min-w-0">
          <div className="text-xs text-muted-foreground">
            {data.bad_entry_label}
          </div>
          <div className="truncate text-sm font-medium">{data.bad_entry_zone}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function PointCard({
  symbol,
  point,
}: {
  symbol: string;
  point: { number: number; title: string; instruction: string };
}) {
  const [openContent, setOpenContent] = React.useState(true);
  const mutation = useMutation({
    mutationFn: () => api.aiPoint(symbol, point.number),
  });

  return (
    <Card className="py-4">
      <CardHeader className="flex flex-row items-center justify-between gap-2 px-4">
        <CardTitle className="flex min-w-0 items-center gap-2 text-sm">
          <Badge variant="outline" className="shrink-0 font-mono">
            {point.number}
          </Badge>
          <span className="truncate">{point.title}</span>
        </CardTitle>
        <div className="flex shrink-0 items-center gap-1">
          {mutation.data && (
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={() => setOpenContent((o) => !o)}
              aria-label="Toggle analysis"
            >
              <ChevronDown
                className={cn("size-4 transition-transform", openContent && "rotate-180")}
              />
            </Button>
          )}
          <Button
            size="sm"
            variant={mutation.data ? "ghost" : "outline"}
            className="h-7 text-xs"
            disabled={mutation.isPending}
            onClick={() => {
              setOpenContent(true);
              mutation.mutate();
            }}
          >
            {mutation.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : mutation.data ? (
              "Re-run"
            ) : (
              "Analyze"
            )}
          </Button>
        </div>
      </CardHeader>
      {(mutation.isPending || mutation.isError || (mutation.data && openContent)) && (
        <CardContent className="px-4">
          {mutation.isPending && (
            <p className="text-xs text-muted-foreground">
              Running local model — this can take 10–30 seconds…
            </p>
          )}
          {mutation.isError && (
            <p className="text-xs text-negative">{ollamaErrorMessage(mutation.error)}</p>
          )}
          {mutation.data && openContent && (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              {mutation.data.content}
            </p>
          )}
        </CardContent>
      )}
    </Card>
  );
}

export function AiAnalysis({ symbol }: { symbol: string }) {
  const points = useQuery({
    queryKey: ["ai-points"],
    queryFn: () => api.aiPoints(),
    staleTime: Infinity,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <BrainCircuit className="size-6 text-muted-foreground" />
        <h1 className="font-mono text-2xl font-bold tracking-tight sm:text-3xl">
          {symbol}
        </h1>
        <Badge variant="secondary">AI Analysis</Badge>
      </div>

      <TrendCard symbol={symbol} />
      <TrendChart symbol={symbol} />

      <div>
        <h2 className="mb-1 text-lg font-semibold">15-Point Analysis</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Each point runs on demand against your local Ollama model using live
          market data.
        </p>
        {points.isPending ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : points.isError ? (
          <p className="text-sm text-negative">Failed to load analysis points.</p>
        ) : (
          <div className="grid gap-2 lg:grid-cols-2">
            {points.data.points.map((p) => (
              <PointCard key={p.number} symbol={symbol} point={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
