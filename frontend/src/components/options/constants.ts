import type { StrategyType } from "@/lib/api";

export const STRATEGY_LABELS: Record<StrategyType, string> = {
  cash_secured_put: "Cash-Secured Put",
  covered_call: "Covered Call",
  short_put: "Short Put",
  short_call: "Short Call",
  long_call: "Long Call",
  long_put: "Long Put",
  put_credit_spread: "Put Credit Spread",
  call_credit_spread: "Call Credit Spread",
  put_debit_spread: "Put Debit Spread",
  call_debit_spread: "Call Debit Spread",
  iron_condor: "Iron Condor",
  custom: "Custom",
};

export const LEG_COUNTS: Record<StrategyType, number> = {
  cash_secured_put: 1,
  covered_call: 1,
  short_put: 1,
  short_call: 1,
  long_call: 1,
  long_put: 1,
  put_credit_spread: 2,
  call_credit_spread: 2,
  put_debit_spread: 2,
  call_debit_spread: 2,
  iron_condor: 4,
  custom: 1,
};

export function statusColor(status: string) {
  switch (status) {
    case "good":
    case "favorable":
      return "border-positive/50 bg-positive/5 text-positive";
    case "caution":
    case "mixed":
      return "border-amber-500/50 bg-amber-500/5 text-amber-700 dark:text-amber-400";
    case "bad":
    case "high_risk":
      return "border-destructive/50 bg-destructive/5 text-destructive";
    default:
      return "border-border bg-muted/30";
  }
}
