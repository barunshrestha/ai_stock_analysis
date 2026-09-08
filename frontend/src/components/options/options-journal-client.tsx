"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";

import { api, type OptionTrade } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DeleteTradeDialog } from "@/components/options/delete-trade-dialog";
import { STRATEGY_LABELS } from "@/components/options/constants";
import { OptionsDashboard } from "@/components/options/dashboard/options-dashboard";

function mergeTrades(...lists: OptionTrade[][]): OptionTrade[] {
  const byId = new Map<number, OptionTrade>();
  for (const list of lists) {
    for (const t of list) byId.set(t.id, t);
  }
  return Array.from(byId.values()).sort((a, b) => b.executed_at.localeCompare(a.executed_at));
}

export function OptionsJournalClient() {
  const openQ = useQuery({ queryKey: ["options-trades", "open"], queryFn: () => api.optionsTrades({ status: "open" }) });
  const closedQ = useQuery({ queryKey: ["options-trades", "closed"], queryFn: () => api.optionsTrades({ status: "closed" }) });
  const assignedQ = useQuery({ queryKey: ["options-trades", "assigned"], queryFn: () => api.optionsTrades({ status: "assigned" }) });
  const expiredQ = useQuery({
    queryKey: ["options-trades", "expired"],
    queryFn: () => api.optionsTrades({ status: "expired" }),
  });
  const alertsQ = useQuery({
    queryKey: ["csp-monitoring-summary"],
    queryFn: () => api.cspMonitoringSummary(),
    refetchInterval: 60_000,
  });

  const alertByTrade = new Map((alertsQ.data?.alerts ?? []).map((a) => [a.trade_id, a]));

  const allTrades = useMemo(
    () =>
      mergeTrades(
        openQ.data?.trades ?? [],
        closedQ.data?.trades ?? [],
        assignedQ.data?.trades ?? [],
        expiredQ.data?.trades ?? [],
      ),
    [openQ.data, closedQ.data, assignedQ.data, expiredQ.data],
  );

  const dashboardLoading =
    openQ.isPending || closedQ.isPending || assignedQ.isPending || expiredQ.isPending;
  const dashboardError = openQ.isError || closedQ.isError || assignedQ.isError || expiredQ.isError;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Options journal</h1>
          <p className="text-sm text-muted-foreground">
            Track trades, pre-trade checks, and management rules.
          </p>
        </div>
        <Button asChild>
          <Link href="/options/new">
            <Plus className="mr-1 size-4" />
            New trade
          </Link>
        </Button>
      </div>

      <Tabs defaultValue="dashboard">
        <TabsList>
          <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="open">Open</TabsTrigger>
          <TabsTrigger value="closed">Closed</TabsTrigger>
          <TabsTrigger value="assigned">Assigned</TabsTrigger>
        </TabsList>
        <TabsContent value="dashboard" className="mt-4">
          <OptionsDashboard
            trades={allTrades}
            isLoading={dashboardLoading}
            isError={dashboardError}
          />
        </TabsContent>
        <TabsContent value="open" className="mt-4">
          <TradeList query={openQ} empty="No open trades." alertByTrade={alertByTrade} />
        </TabsContent>
        <TabsContent value="closed" className="mt-4">
          <TradeList query={closedQ} empty="No closed trades." />
        </TabsContent>
        <TabsContent value="assigned" className="mt-4">
          <TradeList query={assignedQ} empty="No assigned trades." />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function TradeList({
  query,
  empty,
  alertByTrade,
}: {
  query: ReturnType<typeof useQuery<{ trades: OptionTrade[] }>>;
  empty: string;
  alertByTrade?: Map<number, import("@/lib/api").CspMonitoringAlert>;
}) {
  if (query.isPending) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  }
  if (query.isError) {
    return <p className="text-sm text-destructive">Failed to load trades.</p>;
  }
  const trades = query.data?.trades ?? [];
  if (trades.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }
  return (
    <div className="space-y-2">
      {trades.map((t) => {
        const alert = alertByTrade?.get(t.id);
        return (
          <Card key={t.id} className="py-0 transition-colors hover:bg-muted/40">
            <CardContent className="flex items-center gap-2 px-4 py-3">
              <Link href={`/options/${t.id}`} className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
                <span className="font-mono text-lg font-semibold">{t.ticker}</span>
                <Badge variant="outline">{STRATEGY_LABELS[t.strategy_type]}</Badge>
                <span className="text-sm text-muted-foreground">
                  {t.contracts}× · ${t.net_credit_debit.toFixed(2)} · exp {t.expiration_date}
                </span>
                {alert?.trigger_close_alert && (
                  <Badge className="bg-positive/15 text-positive hover:bg-positive/20">50% profit</Badge>
                )}
                {alert?.breached && (
                  <Badge variant="destructive">Near strike</Badge>
                )}
                <span className="ml-auto text-sm sm:ml-0">
                  Ann. ROC {t.metrics.annualized_roc_pct.toFixed(1)}%
                </span>
                {t.realized_pnl != null && (
                  <span className="text-sm font-medium">P&L ${t.realized_pnl.toFixed(2)}</span>
                )}
              </Link>
              <div className="flex shrink-0 items-center gap-0.5">
                {t.status === "open" && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-8 shrink-0"
                    asChild
                    aria-label={`Edit ${t.ticker} trade`}
                  >
                    <Link href={`/options/${t.id}/edit`}>
                      <Pencil className="size-4" />
                    </Link>
                  </Button>
                )}
                <DeleteTradeDialog tradeId={t.id} ticker={t.ticker} />
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
