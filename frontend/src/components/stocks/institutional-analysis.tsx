"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Landmark, ChevronDown, Loader2, RefreshCw } from "lucide-react";

import {
  api,
  ApiError,
  type InstitutionalAnalysis,
  type InstitutionalCacheLookup,
} from "@/lib/api";
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
  return error instanceof Error
    ? error.message
    : "Failed to generate institutional analysis.";
}

function formatCachedAt(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function stanceClass(stance: string) {
  if (stance === "attractive") return "border-positive/50 bg-positive/5 text-positive";
  if (stance === "unattractive")
    return "border-destructive/50 bg-destructive/5 text-destructive";
  return "border-amber-500/50 bg-amber-500/5 text-amber-700 dark:text-amber-400";
}

function cacheLookupToAnalysis(
  data: InstitutionalCacheLookup,
): InstitutionalAnalysis | null {
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

function ResultBody({ data }: { data: InstitutionalAnalysis }) {
  const s = data.structured;
  const source = data.source ?? (data.cached ? "cache" : "live");
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={source === "cache" ? "secondary" : "outline"}>
          {source === "cache" ? "Cached" : "Live"}
        </Badge>
        {s?.stance && (
          <Badge variant="outline" className={cn("capitalize", stanceClass(s.stance))}>
            {s.stance}
          </Badge>
        )}
        {s?.confidence && (
          <Badge variant="secondary" className="capitalize">
            Confidence: {s.confidence}
          </Badge>
        )}
        {data.updated_at && (
          <span className="text-xs text-muted-foreground">
            {source === "cache" ? "Cached at" : "Generated at"} {formatCachedAt(data.updated_at)}
          </span>
        )}
      </div>
      {s?.thesis_one_liner && (
        <p className="text-sm text-muted-foreground">{s.thesis_one_liner}</p>
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
 * Issue #12 — institutional investor perspective with DB cache (Use cached vs Regenerate).
 */
export function InstitutionalAnalysisPanel({ symbol }: { symbol: string }) {
  const queryClient = useQueryClient();
  const [displayed, setDisplayed] = useState<InstitutionalAnalysis | null>(null);

  useEffect(() => {
    setDisplayed(null);
  }, [symbol]);

  const cacheQuery = useQuery({
    queryKey: ["ai-institutional-cache", symbol],
    queryFn: () => api.aiInstitutionalCache(symbol),
  });

  const generateMut = useMutation({
    mutationFn: () => api.aiInstitutional(symbol, "1y", true),
    onSuccess: (data) => {
      setDisplayed(data);
      void queryClient.invalidateQueries({ queryKey: ["ai-institutional-cache", symbol] });
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
          <Landmark className="size-4" />
          Institutional investor perspective
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
              Hedge-fund-style view: why institutions might buy or avoid, key catalysts, and a
              long-term investment thesis grounded on yFinance metrics.
            </p>
            {cacheQuery.isPending && <p>Checking for a saved institutional memo…</p>}
            {hasCache && (
              <p>
                A saved institutional memo is available
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
