"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function CspMonitorPanel({
  tradeId,
  open,
  onCloseAlert,
}: {
  tradeId: number;
  open: boolean;
  onCloseAlert?: (suggestedClosePrice: number) => void;
}) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["csp-monitor", tradeId],
    queryFn: () => api.cspMonitorTrade(tradeId),
    enabled: open,
    refetchInterval: open ? 60_000 : false,
  });

  if (!open) return null;
  if (isPending) return <Skeleton className="h-48 w-full" />;
  if (isError || !data) {
    return (
      <Card>
        <CardContent className="py-4 text-sm text-destructive">
          Live monitor unavailable: {error instanceof Error ? error.message : "Unknown error"}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn(data.recommendation_color === "red" && "border-destructive/40")}>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">Live CSP monitor</CardTitle>
          <Badge variant="outline" className="text-xs">
            Refreshes every 60s
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {data.trigger_close_alert && (
          <div
            className="rounded-md border border-positive/50 bg-positive/10 p-3 text-positive"
            role="alert"
          >
            <p className="font-medium">50% max profit alert</p>
            <p className="mt-1 text-xs opacity-90">
              Current mark ${data.current_mid?.toFixed(2)} — consider buying to close.
            </p>
            {onCloseAlert && data.current_mid != null && (
              <button
                type="button"
                className="mt-2 text-xs underline"
                onClick={() => onCloseAlert(data.current_mid!)}
              >
                Pre-fill close dialog
              </button>
            )}
          </div>
        )}
        {data.breached && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-destructive" role="alert">
            <p className="font-medium">Strike zone breach</p>
            <p className="mt-1 text-xs opacity-90">
              Spot ${data.current_spot?.toFixed(2)} is at or within 3% of strike ${data.strike_price.toFixed(2)}.
            </p>
          </div>
        )}

        <div className="grid gap-2 sm:grid-cols-2">
          <Metric label="Current spot" value={data.current_spot != null ? `$${data.current_spot.toFixed(2)}` : "N/A"} />
          <Metric label="Option mark (mid)" value={data.current_mid != null ? `$${data.current_mid.toFixed(2)}` : "N/A"} />
          <Metric
            label="Unrealized P&L"
            value={data.unrealized_pnl_pct != null ? `${data.unrealized_pnl_pct.toFixed(1)}%` : "N/A"}
          />
          <Metric label="Net cost basis" value={`$${data.net_cost_basis.toFixed(2)}`} />
        </div>

        <p className="text-muted-foreground">{data.recommendation}</p>
        <p className="text-xs text-muted-foreground">{data.disclaimer}</p>
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-mono font-medium">{value}</p>
    </div>
  );
}
