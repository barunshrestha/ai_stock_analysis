"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Scale, ChevronDown, Loader2, RefreshCw } from "lucide-react";

import {
  api,
  ApiError,
  type VerdictAnalysis,
  type VerdictCacheLookup,
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
  return error instanceof Error ? error.message : "Failed to generate analysis.";
}

function formatCachedAt(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function cacheLookupToAnalysis(data: VerdictCacheLookup): VerdictAnalysis | null {
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

function ResultBody({ data }: { data: VerdictAnalysis }) {
  const s = data.structured;
  const source = data.source ?? (data.cached ? "cache" : "live");
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={source === "cache" ? "secondary" : "outline"}>
          {source === "cache" ? "Cached" : "Live"}
        </Badge>
        {s?.verdict && (
          <Badge variant="outline" className={cn("capitalize",
            s.verdict === "buy" && "border-positive/50 text-positive",
            s.verdict === "avoid" && "border-destructive/50 text-destructive",
            s.verdict === "hold" && "border-amber-500/50 text-amber-700 dark:text-amber-400"
          )}>{s.verdict}</Badge>
        )}
        {s?.horizon_fit && (
          <Badge variant="outline" className="capitalize">Horizon: {s.horizon_fit}</Badge>
        )}
        {s?.confidence && (
          <Badge variant="secondary" className="capitalize">Confidence: {s.confidence}</Badge>
        )}
        {data.updated_at && (
          <span className="text-xs text-muted-foreground">
            {source === "cache" ? "Cached at" : "Generated at"} {formatCachedAt(data.updated_at)}
          </span>
        )}
      </div>
      {(s?.summary) && <p className="text-sm text-muted-foreground">{s?.summary}</p>}
      <div className="whitespace-pre-wrap text-sm leading-relaxed">{data.markdown}</div>
      <MetricsPreview metrics={data.metrics} />
      <p className="text-xs text-muted-foreground">
        {data.disclaimer} · Model: {data.model}
      </p>
    </div>
  );
}

export function BuyVerdictPanel({ symbol }: { symbol: string }) {
  const queryClient = useQueryClient();
  const [displayed, setDisplayed] = useState<VerdictAnalysis | null>(null);

  useEffect(() => {
    setDisplayed(null);
  }, [symbol]);

  const cacheQuery = useQuery({
    queryKey: ["ai-verdict-cache", symbol],
    queryFn: () => api.aiVerdictCache(symbol),
  });

  const generateMut = useMutation({
    mutationFn: () => api.aiVerdict(symbol, "1y", true),
    onSuccess: (data) => {
      setDisplayed(data);
      void queryClient.invalidateQueries({ queryKey: ["ai-verdict-cache", symbol] });
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
          <Scale className="size-4" />
          Should I buy this stock?
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
            
            <p className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
              Educational journaling only — not personalized investment advice.
            </p>
            <p>Educational journal verdict only — not financial advice. Short- and long-term outlook, catalysts, risks, Buy/Hold/Avoid.</p>
            {cacheQuery.isPending && <p>Checking for a saved memo…</p>}
            {hasCache && (
              <p>
                A saved memo is available
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
