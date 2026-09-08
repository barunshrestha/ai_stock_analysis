"use client";

import Link from "next/link";
import { CheckCircle2, Lock, PlusCircle, UserCheck } from "lucide-react";

import type { OptionTrade } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type ClosedEarlyRow,
  entryPremiumDollars,
  formatSignedMoney,
  primaryOptionType,
  primaryStrike,
} from "@/components/options/dashboard/aggregate";

function TradeMeta({ trade }: { trade: OptionTrade }) {
  const opt = primaryOptionType(trade).toUpperCase();
  const strike = primaryStrike(trade);
  return (
    <span className="text-xs text-muted-foreground">
      {opt}
      {strike != null ? ` ${strike}` : ""} · {trade.contracts}x
    </span>
  );
}

function Money({ value, className }: { value: number; className?: string }) {
  return (
    <span
      className={cn(
        "tabular-nums font-medium",
        value > 0 && "text-positive",
        value < 0 && "text-destructive",
        className,
      )}
    >
      {formatSignedMoney(value)}
    </span>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <p className="text-sm text-muted-foreground">{text}</p>;
}

export function StatusCards({
  closedEarly,
  expired,
  assigned,
  newPositions,
}: {
  closedEarly: ClosedEarlyRow[];
  expired: OptionTrade[];
  assigned: OptionTrade[];
  newPositions: OptionTrade[];
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Card className="min-h-[140px]">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Lock className="size-4 text-amber-600 dark:text-amber-400" />
            Closed Early
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {closedEarly.length === 0 ? (
            <EmptyLine text="None closed early" />
          ) : (
            closedEarly.map(({ trade, daysHeld, originalDte, progressPct, pnl }) => (
              <Link
                key={trade.id}
                href={`/options/${trade.id}`}
                className="flex items-start justify-between gap-2 rounded-md px-1 py-0.5 hover:bg-muted/50"
              >
                <div className="min-w-0">
                  <div className="font-mono text-sm font-semibold">{trade.ticker}</div>
                  <TradeMeta trade={trade} />
                  <div className="text-xs text-muted-foreground">
                    {daysHeld}d/{originalDte}d – {progressPct}%
                  </div>
                </div>
                <Money value={pnl} />
              </Link>
            ))
          )}
        </CardContent>
      </Card>

      <Card className="min-h-[140px]">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="size-4 text-positive" />
            Expired
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {expired.length === 0 ? (
            <EmptyLine text="None expired" />
          ) : (
            expired.map((trade) => (
              <Link
                key={trade.id}
                href={`/options/${trade.id}`}
                className="flex items-start justify-between gap-2 rounded-md px-1 py-0.5 hover:bg-muted/50"
              >
                <div className="min-w-0">
                  <div className="font-mono text-sm font-semibold">{trade.ticker}</div>
                  <TradeMeta trade={trade} />
                </div>
                <Money value={trade.realized_pnl ?? 0} />
              </Link>
            ))
          )}
        </CardContent>
      </Card>

      <Card className="min-h-[140px]">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <UserCheck className="size-4 text-blue-600 dark:text-blue-400" />
            Assigned
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {assigned.length === 0 ? (
            <EmptyLine text="None in this period" />
          ) : (
            assigned.map((trade) => (
              <Link
                key={trade.id}
                href={`/options/${trade.id}`}
                className="flex items-start justify-between gap-2 rounded-md px-1 py-0.5 hover:bg-muted/50"
              >
                <div className="min-w-0">
                  <div className="font-mono text-sm font-semibold">{trade.ticker}</div>
                  <TradeMeta trade={trade} />
                </div>
                <Money value={trade.realized_pnl ?? 0} />
              </Link>
            ))
          )}
        </CardContent>
      </Card>

      <Card className="min-h-[140px]">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <PlusCircle className="size-4 text-violet-600 dark:text-violet-400" />
            New Positions
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {newPositions.length === 0 ? (
            <EmptyLine text="No new positions" />
          ) : (
            newPositions.map((trade) => (
              <Link
                key={trade.id}
                href={`/options/${trade.id}`}
                className="flex items-start justify-between gap-2 rounded-md px-1 py-0.5 hover:bg-muted/50"
              >
                <div className="min-w-0">
                  <div className="font-mono text-sm font-semibold">{trade.ticker}</div>
                  <TradeMeta trade={trade} />
                </div>
                <Money value={entryPremiumDollars(trade)} />
              </Link>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
