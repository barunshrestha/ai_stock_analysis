"use client";

import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type DashboardAggregate,
  formatSignedMoney,
} from "@/components/options/dashboard/aggregate";

function StatValue({
  value,
  className,
}: {
  value: string;
  className?: string;
}) {
  return <p className={cn("text-2xl font-semibold tabular-nums tracking-tight", className)}>{value}</p>;
}

export function StatsRow({ agg }: { agg: DashboardAggregate }) {
  const periodLabel =
    agg.window.preset === "1d" ? "1D" : agg.window.preset === "7d" ? "7D" : "30D";

  return (
    <div className="space-y-2">
      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Premium Realized ({periodLabel})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <StatValue
              value={formatSignedMoney(agg.premiumRealized)}
              className={cn(
                agg.premiumRealized > 0 && "text-positive",
                agg.premiumRealized < 0 && "text-destructive",
              )}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              {agg.closedEarlyCount} early · {agg.expiredCount} expired · {agg.assignedCount}{" "}
              assigned
              {agg.spreadCloseCount > 0 && (
                <>
                  {" "}
                  · incl. {formatSignedMoney(agg.spreadPremiumInRealized)} from{" "}
                  {agg.spreadCloseCount} spread
                  {agg.spreadCloseCount === 1 ? "" : "s"}
                </>
              )}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              New Premium Opened ({periodLabel})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <StatValue
              value={formatSignedMoney(agg.newPremiumOpened)}
              className="text-blue-600 dark:text-blue-400"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              {agg.newPositions.length} new position
              {agg.newPositions.length === 1 ? "" : "s"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg ROI / Trade ({periodLabel})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <StatValue
              value={
                agg.avgRoiClosed == null
                  ? "—"
                  : `${agg.avgRoiClosed >= 0 ? "+" : ""}${agg.avgRoiClosed.toFixed(2)}%`
              }
              className={cn(
                agg.avgRoiClosed != null && agg.avgRoiClosed > 0 && "text-positive",
                agg.avgRoiClosed != null && agg.avgRoiClosed < 0 && "text-destructive",
              )}
            />
            <p className="mt-1 text-xs text-muted-foreground">on closed trades</p>
          </CardContent>
        </Card>
      </div>
      <p className="text-xs text-muted-foreground">
        Selling stats use journal entry credit and realized P&amp;L only (no live marks).
      </p>
    </div>
  );
}
