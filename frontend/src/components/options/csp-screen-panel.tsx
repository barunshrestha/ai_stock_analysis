"use client";

import type { CspScreenResult } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { statusColor } from "@/components/options/constants";
import { LiquidityWarningPopover } from "@/components/options/liquidity-warning-popover";

export function CspScreenPanel({
  screen,
  onApply,
}: {
  screen: CspScreenResult | null;
  onApply?: () => void;
}) {
  if (!screen) return null;

  const contract = screen.suggested_contract;
  const strategyLabel = screen.strategy_label ?? "Stock";
  const optionType = contract?.option_type ?? "put";
  const targetDelta = contract?.target_delta ?? 0.3;
  const contractTitle = contract
    ? `Suggested ~${targetDelta.toFixed(2)}-delta ${optionType}`
    : null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">
            Stock screen — {screen.ticker}
            <span className="font-normal text-muted-foreground"> ({strategyLabel})</span>
          </CardTitle>
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
            <p className="font-medium">{contractTitle}</p>
            {contract.note && <p className="mt-1 text-xs text-muted-foreground">{contract.note}</p>}
            <div className="mt-2 grid gap-1 sm:grid-cols-2">
              <span>Strike: ${contract.strike.toFixed(2)}</span>
              <span>
                Expiration: {contract.expiration} ({contract.dte} DTE)
              </span>
              <span>Premium (mid): ${contract.premium_mid.toFixed(2)}</span>
              <span>Delta: {contract.delta.toFixed(2)}</span>
              {contract.otm_pct != null && <span>OTM: {contract.otm_pct.toFixed(1)}%</span>}
              {!contract.liquidity_ok && (
                <LiquidityWarningPopover
                  ticker={screen.ticker}
                  storageMode="browser"
                  metrics={{
                    bid: contract.bid,
                    ask: contract.ask,
                    premium_mid: contract.premium_mid,
                    spread_pct: contract.spread_pct,
                    open_interest: contract.open_interest,
                    volume: contract.volume,
                  }}
                />
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
