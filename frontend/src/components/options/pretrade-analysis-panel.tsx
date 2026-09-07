"use client";

import type { PreTradeAnalysis } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { statusColor } from "@/components/options/constants";

export function PreTradeAnalysisPanel({ analysis }: { analysis: PreTradeAnalysis | null }) {
  if (!analysis) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">Pre-trade analysis</CardTitle>
          <Badge variant="outline" className={cn("capitalize", statusColor(analysis.overall_score))}>
            {analysis.overall_score.replace("_", " ")}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">{analysis.summary}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-2">
          {analysis.indicators.map((ind) => (
            <div
              key={ind.id}
              className={cn("rounded-lg border p-3 text-sm", statusColor(ind.status))}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium">{ind.label}</span>
                <span className="shrink-0 font-mono text-xs">{ind.value}</span>
              </div>
              <p className="mt-1 text-xs opacity-90">{ind.impact}</p>
            </div>
          ))}
        </div>
        {analysis.recommendations.length > 0 && (
          <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
            {analysis.recommendations.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
