"use client";

import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type CalendarDayCell,
  type CalendarMonth,
  formatSignedMoney,
} from "@/components/options/dashboard/aggregate";

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function DayCell({
  cell,
  selected,
  onSelect,
}: {
  cell: CalendarDayCell;
  selected: boolean;
  onSelect: (key: string) => void;
}) {
  const hasActivity = cell.inMonth && (cell.closedCount > 0 || cell.newCount > 0 || cell.pnl !== 0);
  return (
    <button
      type="button"
      disabled={!cell.inMonth}
      onClick={() => cell.inMonth && onSelect(cell.dateKey)}
      className={cn(
        "flex min-h-[72px] flex-col rounded-md border p-1.5 text-left transition-colors",
        !cell.inMonth && "border-transparent bg-transparent text-muted-foreground/40",
        cell.inMonth && "hover:bg-muted/40",
        hasActivity && cell.pnl >= 0 && "border-positive/30 bg-positive/5",
        hasActivity && cell.pnl < 0 && "border-destructive/30 bg-destructive/5",
        selected && "ring-2 ring-amber-500/70",
      )}
    >
      <span className="text-xs font-medium">{cell.dayOfMonth}</span>
      {cell.inMonth && hasActivity && (
        <>
          <span
            className={cn(
              "mt-0.5 text-xs font-semibold tabular-nums",
              cell.pnl > 0 && "text-positive",
              cell.pnl < 0 && "text-destructive",
            )}
          >
            {formatSignedMoney(cell.pnl)}
          </span>
          <span className="text-[10px] leading-tight text-muted-foreground">
            {cell.closedCount > 0 && `${cell.closedCount} closed`}
            {cell.closedCount > 0 && cell.newCount > 0 && " · "}
            {cell.newCount > 0 && `${cell.newCount} new`}
          </span>
        </>
      )}
    </button>
  );
}

export function PnlCalendar({
  calendar,
  selectedDateKey,
  onSelectDay,
  onPrevMonth,
  onNextMonth,
}: {
  calendar: CalendarMonth;
  selectedDateKey: string | null;
  onSelectDay: (dateKey: string) => void;
  onPrevMonth: () => void;
  onNextMonth: () => void;
}) {
  const title = new Date(calendar.year, calendar.month, 1).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 space-y-0">
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarDays className="size-4" />
          P&amp;L Calendar
        </CardTitle>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span
            className={cn(
              "font-semibold tabular-nums",
              calendar.monthPnl > 0 && "text-positive",
              calendar.monthPnl < 0 && "text-destructive",
            )}
          >
            {formatSignedMoney(calendar.monthPnl)}
          </span>
          <span className="text-xs text-muted-foreground">
            {calendar.upDays} up · {calendar.downDays} down
          </span>
          <div className="flex items-center gap-1">
            <Button type="button" variant="ghost" size="icon" className="size-8" onClick={onPrevMonth}>
              <ChevronLeft className="size-4" />
            </Button>
            <span className="min-w-[9rem] text-center text-sm font-medium">{title}</span>
            <Button type="button" variant="ghost" size="icon" className="size-8" onClick={onNextMonth}>
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-[repeat(7,minmax(0,1fr))_auto] gap-1">
          {DOW.map((d) => (
            <div key={d} className="px-1 text-center text-[11px] font-medium text-muted-foreground">
              {d}
            </div>
          ))}
          <div className="px-1 text-center text-[11px] font-medium text-muted-foreground">Week</div>

          {calendar.weeks.map((week, wi) => (
            <div key={wi} className="contents">
              {week.days.map((cell) => (
                <DayCell
                  key={cell.dateKey + String(cell.inMonth)}
                  cell={cell}
                  selected={selectedDateKey === cell.dateKey}
                  onSelect={onSelectDay}
                />
              ))}
              <div
                className={cn(
                  "flex min-h-[72px] items-center justify-center rounded-md border px-2 text-xs font-semibold tabular-nums",
                  week.weekPnl > 0 && "border-positive/30 bg-positive/5 text-positive",
                  week.weekPnl < 0 && "border-destructive/30 bg-destructive/5 text-destructive",
                  week.weekPnl === 0 && "text-muted-foreground",
                )}
              >
                {formatSignedMoney(week.weekPnl)}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
