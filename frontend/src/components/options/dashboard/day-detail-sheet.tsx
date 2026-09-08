"use client";

import type { ReactNode } from "react";
import Link from "next/link";

import type { OptionTrade } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { STRATEGY_LABELS } from "@/components/options/constants";
import {
  entryPremiumDollars,
  formatSignedMoney,
} from "@/components/options/dashboard/aggregate";
import { cn } from "@/lib/utils";

function TradeLine({
  trade,
  trailing,
}: {
  trade: OptionTrade;
  trailing: ReactNode;
}) {
  return (
    <Link
      href={`/options/${trade.id}`}
      className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 hover:bg-muted/40"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono font-semibold">{trade.ticker}</span>
          <Badge variant="outline">{STRATEGY_LABELS[trade.strategy_type]}</Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          {trade.contracts}× · exp {trade.expiration_date}
        </p>
      </div>
      {trailing}
    </Link>
  );
}

export function DayDetailSheet({
  open,
  dateKey,
  closed,
  opened,
  onOpenChange,
}: {
  open: boolean;
  dateKey: string | null;
  closed: OptionTrade[];
  opened: OptionTrade[];
  onOpenChange: (open: boolean) => void;
}) {
  const label = dateKey
    ? new Date(dateKey + "T12:00:00").toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{label || "Day detail"}</SheetTitle>
          <SheetDescription>Closed and newly opened trades for this day.</SheetDescription>
        </SheetHeader>
        <div className="mt-4 space-y-6 px-1">
          <section className="space-y-2">
            <h3 className="text-sm font-medium">Closed ({closed.length})</h3>
            {closed.length === 0 ? (
              <p className="text-sm text-muted-foreground">No closes.</p>
            ) : (
              closed.map((t) => (
                <TradeLine
                  key={`c-${t.id}`}
                  trade={t}
                  trailing={
                    <span
                      className={cn(
                        "text-sm font-medium tabular-nums",
                        (t.realized_pnl ?? 0) > 0 && "text-positive",
                        (t.realized_pnl ?? 0) < 0 && "text-destructive",
                      )}
                    >
                      {formatSignedMoney(t.realized_pnl ?? 0)}
                    </span>
                  }
                />
              ))
            )}
          </section>
          <section className="space-y-2">
            <h3 className="text-sm font-medium">Opened ({opened.length})</h3>
            {opened.length === 0 ? (
              <p className="text-sm text-muted-foreground">No new opens.</p>
            ) : (
              opened.map((t) => (
                <TradeLine
                  key={`o-${t.id}`}
                  trade={t}
                  trailing={
                    <span className="text-sm font-medium tabular-nums text-blue-600 dark:text-blue-400">
                      {formatSignedMoney(entryPremiumDollars(t))}
                    </span>
                  }
                />
              ))
            )}
          </section>
        </div>
      </SheetContent>
    </Sheet>
  );
}
