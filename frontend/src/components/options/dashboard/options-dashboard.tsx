"use client";

import { useMemo, useState } from "react";

import type { OptionTrade } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  aggregateDashboard,
  buildCalendarMonth,
  tradesForDay,
  type TimeframePreset,
} from "@/components/options/dashboard/aggregate";
import { StatusCards } from "@/components/options/dashboard/status-cards";
import { StatsRow } from "@/components/options/dashboard/stats-row";
import { PnlCalendar } from "@/components/options/dashboard/pnl-calendar";
import { DayDetailSheet } from "@/components/options/dashboard/day-detail-sheet";
import { cn } from "@/lib/utils";

const PRESETS: { id: TimeframePreset; label: string }[] = [
  { id: "1d", label: "1D" },
  { id: "7d", label: "7D" },
  { id: "30d", label: "30D" },
];

export function OptionsDashboard({
  trades,
  isLoading,
  isError,
}: {
  trades: OptionTrade[];
  isLoading?: boolean;
  isError?: boolean;
}) {
  const [preset, setPreset] = useState<TimeframePreset>("7d");
  const now = useMemo(() => new Date(), []);
  const [calCursor, setCalCursor] = useState(() => ({
    year: now.getFullYear(),
    month: now.getMonth(),
  }));
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const agg = useMemo(() => aggregateDashboard(trades, preset, now), [trades, preset, now]);
  const calendar = useMemo(
    () => buildCalendarMonth(calCursor.year, calCursor.month, trades),
    [calCursor, trades],
  );
  const dayTrades = useMemo(
    () => (selectedDay ? tradesForDay(trades, selectedDay) : { closed: [], opened: [] }),
    [trades, selectedDay],
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full max-w-md" />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-36 w-full" />
          ))}
        </div>
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  if (isError) {
    return <p className="text-sm text-destructive">Failed to load trades for the dashboard.</p>;
  }

  const periodTitle =
    preset === "1d" ? "LAST 1 DAY" : preset === "7d" ? "LAST 7 DAYS" : "LAST 30 DAYS";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold tracking-wide">{periodTitle}</h2>
          <span className="text-sm text-muted-foreground">{agg.window.label}</span>
          <Badge variant="secondary">{agg.tradeCountInWindow} trades</Badge>
        </div>
        <div className="inline-flex rounded-md border p-0.5">
          {PRESETS.map((p) => (
            <Button
              key={p.id}
              type="button"
              size="sm"
              variant={preset === p.id ? "default" : "ghost"}
              className={cn("h-8 px-3", preset === p.id && "shadow-sm")}
              onClick={() => setPreset(p.id)}
            >
              {p.label}
            </Button>
          ))}
        </div>
      </div>

      <StatusCards
        closedEarly={agg.closedEarly}
        expired={agg.expired}
        assigned={agg.assigned}
        newPositions={agg.newPositions}
      />

      <StatsRow agg={agg} />

      <PnlCalendar
        calendar={calendar}
        selectedDateKey={selectedDay}
        onSelectDay={setSelectedDay}
        onPrevMonth={() =>
          setCalCursor((c) => {
            const d = new Date(c.year, c.month - 1, 1);
            return { year: d.getFullYear(), month: d.getMonth() };
          })
        }
        onNextMonth={() =>
          setCalCursor((c) => {
            const d = new Date(c.year, c.month + 1, 1);
            return { year: d.getFullYear(), month: d.getMonth() };
          })
        }
      />

      <DayDetailSheet
        open={Boolean(selectedDay)}
        dateKey={selectedDay}
        closed={dayTrades.closed}
        opened={dayTrades.opened}
        onOpenChange={(open) => {
          if (!open) setSelectedDay(null);
        }}
      />
    </div>
  );
}
