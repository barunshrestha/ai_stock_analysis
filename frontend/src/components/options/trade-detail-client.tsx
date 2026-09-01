"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AdvisoryPanel } from "@/components/options/advisory-panel";
import { CloseTradeDialog } from "@/components/options/close-trade-dialog";
import { STRATEGY_LABELS } from "@/components/options/constants";

export function TradeDetailClient({ id }: { id: number }) {
  const { data: trade, isPending, isError, refetch } = useQuery({
    queryKey: ["options-trade", id],
    queryFn: () => api.optionsTrade(id),
  });

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (isError || !trade) {
    return <p className="text-destructive">Trade not found.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/options">
            <ArrowLeft className="mr-1 size-4" />
            Journal
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold">
          {trade.ticker}{" "}
          <span className="text-base font-normal text-muted-foreground">
            {STRATEGY_LABELS[trade.strategy_type]}
          </span>
        </h1>
        <span className="rounded-full border px-2 py-0.5 text-xs uppercase">{trade.status}</span>
        {trade.status === "open" && <CloseTradeDialog tradeId={trade.id} onClosed={() => refetch()} />}
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/stocks/${trade.ticker}`}>View stock</Link>
        </Button>
      </div>

      {trade.realized_pnl != null && (
        <p className="text-lg font-medium">
          Realized P&L: ${trade.realized_pnl.toFixed(2)}
          {trade.close_net_per_contract != null && (
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              (closed @ ${trade.close_net_per_contract.toFixed(2)})
            </span>
          )}
        </p>
      )}

      <AdvisoryPanel trade={trade} />
    </div>
  );
}
