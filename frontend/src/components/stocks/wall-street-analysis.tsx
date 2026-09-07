"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { BrainCircuit, ChevronDown, Loader2, RefreshCw } from "lucide-react";

import { api, ApiError, type WallStreetAnalysis } from "@/lib/api";
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
  return error instanceof Error ? error.message : "Failed to generate Wall Street analysis.";
}

function stanceClass(stance: string) {
  switch (stance) {
    case "bullish":
      return "border-positive/50 bg-positive/5 text-positive";
    case "bearish":
      return "border-destructive/50 bg-destructive/5 text-destructive";
    default:
      return "border-border bg-muted/30";
  }
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

function ResultBody({ data }: { data: WallStreetAnalysis }) {
  const s = data.structured;
  return (
    <div className="space-y-4">
      {s && (
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className={cn("capitalize", stanceClass(s.overall_stance))}>
            {s.overall_stance}
          </Badge>
          <Badge variant="secondary" className="capitalize">
            Confidence: {s.confidence}
          </Badge>
        </div>
      )}
      {s && (s.base_case_summary || s.bull_case_summary || s.bear_case_summary) && (
        <div className="grid gap-2 text-sm sm:grid-cols-3">
          {s.bull_case_summary && (
            <div className="rounded-md border border-positive/30 bg-positive/5 p-2">
              <div className="text-xs font-medium text-positive">Bull</div>
              <p className="mt-1 text-muted-foreground">{s.bull_case_summary}</p>
            </div>
          )}
          {s.base_case_summary && (
            <div className="rounded-md border bg-muted/20 p-2">
              <div className="text-xs font-medium">Base</div>
              <p className="mt-1 text-muted-foreground">{s.base_case_summary}</p>
            </div>
          )}
          {s.bear_case_summary && (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 p-2">
              <div className="text-xs font-medium text-destructive">Bear</div>
              <p className="mt-1 text-muted-foreground">{s.bear_case_summary}</p>
            </div>
          )}
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
 * On-demand Gemini Wall Street memo grounded on yFinance metrics (Issue #6).
 */
export function WallStreetAnalysisPanel({ symbol }: { symbol: string }) {
  const mutation = useMutation({
    mutationFn: () => api.aiWallStreet(symbol),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <BrainCircuit className="size-4" />
          Wall Street–style analysis
        </CardTitle>
        <Button
          size="sm"
          variant={mutation.data ? "ghost" : "default"}
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Generating…
            </>
          ) : mutation.data ? (
            <>
              <RefreshCw className="size-4" />
              Regenerate
            </>
          ) : (
            "Generate"
          )}
        </Button>
      </CardHeader>
      <CardContent>
        {mutation.isIdle && (
          <p className="text-sm text-muted-foreground">
            Pull live yFinance metrics and ask Gemini for a grounded equity research memo
            (business, moat, risks, valuation, bull/base/bear, outlook).
          </p>
        )}
        {mutation.isPending && (
          <p className="text-sm text-muted-foreground">
            Fetching metrics and calling Gemini — this can take a short while…
          </p>
        )}
        {mutation.isError && (
          <p className="text-sm text-negative">{geminiErrorMessage(mutation.error)}</p>
        )}
        {mutation.data && <ResultBody data={mutation.data} />}
      </CardContent>
    </Card>
  );
}
