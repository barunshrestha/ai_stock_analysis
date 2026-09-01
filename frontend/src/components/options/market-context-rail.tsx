"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarDays, TrendingDown, TrendingUp } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function pct(v: number | null | undefined) {
  if (v == null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function sentimentColor(label: string) {
  if (label === "risk_on") return "text-positive";
  if (label === "risk_off" || label === "high_volatility") return "text-destructive";
  return "text-muted-foreground";
}

/** Merge headline feeds without duplicate ids (same story can appear in multiple categories). */
function uniqueHeadlines<T extends { id: string }>(lists: T[][], limit: number): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const list of lists) {
    for (const item of list) {
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      out.push(item);
      if (out.length >= limit) return out;
    }
  }
  return out;
}

export function MarketContextRail() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["market-context"],
    queryFn: () => api.marketContext(),
    staleTime: 5 * 60_000,
  });

  if (isPending) {
    return (
      <aside className="hidden w-80 shrink-0 space-y-3 xl:block">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </aside>
    );
  }

  if (isError || !data) {
    return (
      <aside className="hidden w-80 shrink-0 xl:block">
        <Card>
          <CardContent className="py-4 text-sm text-muted-foreground">
            Could not load market context.
          </CardContent>
        </Card>
      </aside>
    );
  }

  const s = data.sentiment;

  return (
    <aside className="hidden w-80 shrink-0 space-y-3 xl:block">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">Market mood</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className={cn("text-lg font-semibold", sentimentColor(s.label))}>{s.display}</p>
          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <span>SPY {pct(s.spy_change_pct)}</span>
            <span>QQQ {pct(s.qqq_change_pct)}</span>
            <span>VIX {s.vix?.toFixed(1) ?? "—"}</span>
            <span>VIX chg {pct(s.vix_change_pct)}</span>
          </div>
          <p className="text-xs leading-snug text-muted-foreground">{s.impact}</p>
        </CardContent>
      </Card>

      {data.alerts.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm font-semibold">
              <AlertTriangle className="size-4" />
              Alerts
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {data.alerts.map((a, i) => (
              <p key={i} className="text-xs text-muted-foreground">
                <Badge variant="outline" className="mr-1 h-4 text-[9px] uppercase">
                  {a.level}
                </Badge>
                {a.text}
              </p>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-1.5 text-sm font-semibold">
            <CalendarDays className="size-4" />
            Economic calendar
          </CardTitle>
        </CardHeader>
        <CardContent className="max-h-48 space-y-2 overflow-y-auto">
          {!data.finnhub_configured ? (
            <p className="text-xs text-muted-foreground">
              Add FINNHUB_API_KEY for US economic releases.
            </p>
          ) : data.economic_events.length === 0 ? (
            <p className="text-xs text-muted-foreground">No events this week.</p>
          ) : (
            data.economic_events.slice(0, 8).map((ev) => (
              <div key={ev.id} className="flex gap-2 text-xs">
                <Badge
                  variant="outline"
                  className={cn(
                    "h-4 shrink-0 text-[9px] uppercase",
                    ev.impact === "high" && "border-positive text-positive",
                  )}
                >
                  {ev.impact}
                </Badge>
                <div>
                  <p className="font-medium leading-snug">{ev.event}</p>
                  <p className="text-muted-foreground">{ev.date.slice(0, 10)}</p>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">Catalysts</CardTitle>
        </CardHeader>
        <CardContent className="max-h-56 space-y-2 overflow-y-auto">
          {uniqueHeadlines(
            [data.catalysts.earnings_headlines, data.catalysts.market_headlines],
            8,
          ).map((item) => (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block text-xs hover:text-primary"
              >
                <span className="font-medium leading-snug line-clamp-2">{item.title}</span>
                <span className="text-muted-foreground">{item.source}</span>
              </a>
            ))}
        </CardContent>
      </Card>

      <p className="px-1 text-[10px] leading-snug text-muted-foreground">{data.footer_note}</p>
      <p className="px-1 text-[10px] text-muted-foreground">{data.disclaimer}</p>
    </aside>
  );
}

/** Compact market mood for mobile sheet trigger */
export function MarketContextBadge() {
  const { data } = useQuery({
    queryKey: ["market-context"],
    queryFn: () => api.marketContext(),
    staleTime: 5 * 60_000,
  });
  if (!data) return null;
  const up = (data.sentiment.spy_change_pct ?? 0) >= 0;
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground xl:hidden">
      {up ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
      {data.sentiment.display}
    </span>
  );
}
