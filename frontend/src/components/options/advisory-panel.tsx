"use client";

import type { OptionTrade } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { STRATEGY_LABELS } from "@/components/options/constants";

export function AdvisoryPanel({ trade }: { trade: OptionTrade }) {
  const adv = trade.advisory as Record<string, Record<string, unknown>>;
  const m = trade.metrics;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Trade metrics</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
          <Metric label="Strategy" value={STRATEGY_LABELS[trade.strategy_type]} />
          <Metric label="Collateral" value={`$${m.collateral_required.toLocaleString()}`} />
          <Metric label="Total premium" value={`$${m.total_premium_dollars.toLocaleString()}`} />
          <Metric label="ROC" value={`${m.return_on_capital_pct.toFixed(2)}%`} />
          <Metric label="Annualized ROC" value={`${m.annualized_roc_pct.toFixed(1)}%`} />
          <Metric label="DTE" value={String(m.days_to_expiration)} />
          {m.breach_price != null && (
            <Metric label="Breach zone" value={`$${m.breach_price.toFixed(2)}`} />
          )}
          {m.btc_50pct_target_per_contract != null && (
            <Metric label="50% BTC target" value={`$${m.btc_50pct_target_per_contract.toFixed(2)}`} />
          )}
        </CardContent>
      </Card>

      {adv.profit_taking && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Profit taking (50% rule)</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <p>{String(adv.profit_taking.recommendation)}</p>
            <p className="mt-1">
              Target profit: ${Number(adv.profit_taking.target_profit_dollars).toLocaleString()}
            </p>
          </CardContent>
        </Card>
      )}

      {adv.defensive && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Defensive roll playbook</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-2 text-sm text-muted-foreground">
              Trigger near ${Number(adv.defensive.trigger_price).toFixed(2)}
            </p>
            <ol className="list-inside list-decimal space-y-1 text-sm">
              {(adv.defensive.roll_playbook as string[]).map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {adv.assignment && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Assignment preparedness</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <p>{String(adv.assignment.note)}</p>
            <p className="mt-1">
              Cash if assigned: ${Number(adv.assignment.cash_required).toLocaleString()}
            </p>
          </CardContent>
        </Card>
      )}

      <p className="text-xs text-muted-foreground">
        {String(adv.disclaimer ?? "Not financial advice.")}
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 border-b border-border/50 py-1">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
