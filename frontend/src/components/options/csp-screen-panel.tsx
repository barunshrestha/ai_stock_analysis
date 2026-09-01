"use client";

import type { CspScreenResult } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { statusColor } from "@/components/options/constants";

export function CspScreenPanel({
  screen,
  onApply,
}: {
  screen: CspScreenResult | null;
  onApply?: () => void;
}) {
  if (!screen) return null;

  const contract = screen.suggested_contract;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">CSP ticker screen — {screen.ticker}</CardTitle>
          <Badge variant="outline" className={cn("capitalize", statusColor(screen.overall_verdict))}>
            {screen.overall_verdict.replace("_", " ")}
          </Badge>
          {screen.recommendation_color === "red" && (
            <Badge variant="destructive">Review before entry</Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground">{screen.verdict.summary}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <h4 className="mb-2 text-sm font-medium text-positive">Pros</h4>
            <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
              {screen.pros.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="mb-2 text-sm font-medium text-destructive">Cons</h4>
            <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
              {screen.cons.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        </div>

        {contract && (
          <div className="rounded-lg border bg-muted/20 p-3 text-sm">
            <p className="font-medium">Suggested ~0.30-delta put</p>
            <div className="mt-2 grid gap-1 sm:grid-cols-2">
              <span>Strike: ${contract.strike.toFixed(2)}</span>
              <span>Expiration: {contract.expiration} ({contract.dte} DTE)</span>
              <span>Premium (mid): ${contract.premium_mid.toFixed(2)}</span>
              <span>Delta: {contract.delta.toFixed(2)}</span>
              {contract.otm_pct != null && <span>OTM: {contract.otm_pct.toFixed(1)}%</span>}
              {!contract.liquidity_ok && (
                <span className="text-amber-600 dark:text-amber-400">Low liquidity / wide spread</span>
              )}
            </div>
            {onApply && (
              <Button type="button" size="sm" className="mt-3" variant="secondary" onClick={onApply}>
                Apply to form
              </Button>
            )}
          </div>
        )}

        <p className="text-xs text-muted-foreground">{screen.disclaimer}</p>
      </CardContent>
    </Card>
  );
}
