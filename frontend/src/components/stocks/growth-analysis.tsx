"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { TrendingUp, ChevronDown, Loader2, RefreshCw } from "lucide-react";

import { api, ApiError, type GrowthAnalysis, type GrowthCacheLookup } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function geminiErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 503) {
    return error.message.includes("GEMINI_API_KEY")
      ? "Gemini is not configured. Add GEMINI_API_KEY to your .env and restart the API."
      : error.message;
  }
  return error instanceof Error ? error.message : "Failed to generate growth analysis.";
}

function formatCachedAt(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function outlookClass(band: string) {
  if (band === "high") return "border-positive/50 bg-positive/5 text-positive";
  if (band === "moderate") return "border-amber-500/50 bg-amber-500/5 text-amber-700 dark:text-amber-400";
  return "border-destructive/50 bg-destructive/5 text-destructive";
}

function cacheLookupToAnalysis(data: GrowthCacheLookup): GrowthAnalysis | null {
  if (!data.cached || !data.markdown) return null;
  return {
    symbol: data.symbol,
    metrics: data.metrics ?? {},
    markdown: data.markdown,
    structured: data.structured ?? null,
    model: data.model ?? "unknown",
    disclaimer: data.disclaimer ?? "Not financial advice — for journaling and education only.",
    cached: true,
    source: "cache",
    updated_at: data.updated_at ?? null,
  };
}

function MetricsPreview({ metrics }: { metrics: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border bg-muted/20">
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium"
        onClick={() => setOpen((v) => !v)}
      >
        Metrics used (yFinance context)
        <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <pre className="max-h-64 overflow-auto border-t px-3 py-2 text-xs text-muted-foreground">
          {JSON.stringify(metrics, null, 2)}
        </pre>
      )}
    </div>
  );
}

function ResultBody({ data }: { data: GrowthAnalysis }) {
  const s = data.structured;
  const source = data.source ?? (data.cached ? "cache" : "live");
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={source === "cache" ? "secondary" : "outline"}>
          {source === "cache" ? "Cached" : "Live"}
        </Badge>
        {s?.outlook_band && (
          <Badge variant="outline" className={cn("capitalize", outlookClass(s.outlook_band))}>
            Outlook: {s.outlook_band}
          </Badge>
        )}
        {s?.confidence && (
          <Badge variant="secondary" className="capitalize">
            Confidence: {s.confidence}
          </Badge>
        )}
        {s?.primary_driver && (
          <Badge variant="outline">Driver: {s.primary_driver}</Badge>
        )}
        {data.updated_at && (
          <span className="text-xs text-muted-foreground">
            {source === "cache" ? "Cached at" : "Generated at"} {formatCachedAt(data.updated_at)}
          </span>
        )}
      </div>
      {(s?.five_year_summary || s?.ten_year_summary) && (
        <div className="space-y-1 text-sm text-muted-foreground">
          {s.five_year_summary && <p>5y: {s.five_year_summary}</p>}
          {s.ten_year_summary && <p>10y: {s.ten_year_summary}</p>}
        </div>
      )}
      <div className="whitespace-pre-wrap text-sm leading-relaxed">{data.markdown}</div>
      <MetricsPreview metrics={data.metrics} />
      <p className="text-xs text-muted-foreground">
        {data.disclaimer} · Model: {data.model}
      </p>
    </div>
  );
}

/**
 * Issue #11 — growth potential memo with DB cache (Use cached vs Regenerate).
 */
export function GrowthAnalysisPanel({ symbol }: { symbol: string }) {
  const queryClient = useQueryClient();
  const [displayed, setDisplayed] = useState<GrowthAnalysis | null>(null);

  useEffect(() => {
    setDisplayed(null);
  }, [symbol]);

  const cacheQuery = useQuery({
    queryKey: ["ai-growth-cache", symbol],
    queryFn: () => api.aiGrowthCache(symbol),
  });

  const generateMut = useMutation({
    mutationFn: () => api.aiGrowth(symbol, "1y", true),
    onSuccess: (data) => {
      setDisplayed(data);
      void queryClient.invalidateQueries({ queryKey: ["ai-growth-cache", symbol] });
    },
  });

  const hasCache = Boolean(cacheQuery.data?.cached);
  const cachedAt = formatCachedAt(cacheQuery.data?.updated_at);
  const busy = generateMut.isPending || cacheQuery.isPending;

  const useCached = () => {
    if (!cacheQuery.data) return;
    const analysis = cacheLookupToAnalysis(cacheQuery.data);
    if (analysis) setDisplayed(analysis);
  };

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <TrendingUp className="size-4" />
          Growth potential analysis
        </CardTitle>
        <div className="flex flex-wrap gap-2">
          {hasCache && (
            <Button size="sm" variant="secondary" disabled={busy} onClick={useCached}>
              Use cached
            </Button>
          )}
          <Button
            size="sm"
            variant={displayed || hasCache ? "outline" : "default"}
            disabled={busy}
            onClick={() => generateMut.mutate()}
          >
            {generateMut.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Generating…
              </>
            ) : hasCache || displayed ? (
              <>
                <RefreshCw className="size-4" />
                Regenerate
              </>
            ) : (
              "Generate"
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {!displayed && !generateMut.isPending && !generateMut.isError && (
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>
              Assess market size, industry growth, expansion, new products, and AI/tech
              advantages — then outline a 5–10 year outlook using grounded yFinance metrics.
            </p>
            {cacheQuery.isPending && <p>Checking for a saved growth memo…</p>}
            {hasCache && (
              <p>
                A saved growth memo is available
                {cachedAt ? ` (cached ${cachedAt})` : ""}. Use cached for an instant view, or
                regenerate to call Gemini again.
              </p>
            )}
          </div>
        )}
        {generateMut.isPending && (
          <p className="text-sm text-muted-foreground">
            Fetching metrics and calling Gemini — this can take a short while…
          </p>
        )}
        {generateMut.isError && (
          <p className="text-sm text-negative">{geminiErrorMessage(generateMut.error)}</p>
        )}
        {displayed && <ResultBody data={displayed} />}
      </CardContent>
    </Card>
  );
}
