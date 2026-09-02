"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TradeForm } from "@/components/options/trade-form";

export function TradeEditClient({ id }: { id: number }) {
  const { data: trade, isPending, isError } = useQuery({
    queryKey: ["options-trade", id],
    queryFn: () => api.optionsTrade(id),
  });

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (isError || !trade) {
    return <p className="text-destructive">Trade not found.</p>;
  }
  if (trade.status !== "open") {
    return (
      <div className="space-y-4">
        <p className="text-muted-foreground">Only open trades can be edited.</p>
        <Button variant="outline" asChild>
          <Link href={`/options/${id}`}>Back to trade</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild>
        <Link href={`/options/${id}`}>
          <ArrowLeft className="mr-1 size-4" />
          Back to trade
        </Link>
      </Button>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Edit trade — {trade.ticker}</h1>
        <p className="text-sm text-muted-foreground">Update contracts, premium, legs, or notes.</p>
      </div>
      <TradeForm tradeId={id} initialTrade={trade} />
    </div>
  );
}
