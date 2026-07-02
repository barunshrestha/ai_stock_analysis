"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarDays } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function formatEventDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

export function EconomicCalendarStrip() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["news-calendar"],
    queryFn: () => api.newsCalendar(7),
    staleTime: 30 * 60_000,
  });

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <CalendarDays className="size-4 text-muted-foreground" />
        <h2 className="text-lg font-semibold tracking-tight">This Week</h2>
      </div>
      {isPending ? (
        <div className="flex gap-2 overflow-hidden">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-44 shrink-0" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-muted-foreground">Could not load economic calendar.</p>
      ) : !data.finnhub_configured ? (
        <p className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
          Add <code className="rounded bg-muted px-1">FINNHUB_API_KEY</code> to your{" "}
          <code className="rounded bg-muted px-1">.env</code> for the US economic release
          calendar (free at finnhub.io).
        </p>
      ) : data.events.length === 0 ? (
        <p className="text-sm text-muted-foreground">No US releases scheduled this week.</p>
      ) : (
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
          {data.events.map((ev) => (
            <Card key={ev.id} className="w-44 shrink-0 py-0">
              <CardContent className="space-y-1 px-3 py-2.5">
                <div className="flex items-center justify-between gap-1">
                  <span className="text-xs font-medium text-muted-foreground">
                    {formatEventDate(ev.date)}
                  </span>
                  <Badge
                    variant="outline"
                    className={cn(
                      "h-4 px-1 text-[9px] uppercase",
                      ev.impact === "high" && "border-positive text-positive",
                      ev.impact === "medium" && "border-amber-500 text-amber-600 dark:text-amber-400",
                    )}
                  >
                    {ev.impact}
                  </Badge>
                </div>
                <p className="line-clamp-3 text-xs font-medium leading-snug">{ev.event}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
