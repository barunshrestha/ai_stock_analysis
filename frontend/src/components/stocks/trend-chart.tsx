"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** 6-month closing-price area chart for the Comprehensive tab. */
export function TrendChart({ symbol }: { symbol: string }) {
  const { data, isPending, isError } = useQuery({
    queryKey: ["history", symbol, "6mo"],
    queryFn: () => api.stockHistory(symbol, "6mo"),
  });

  if (isPending) return <Skeleton className="h-72 w-full" />;
  if (isError || !data) return null;

  const points = data.candles
    .filter((c) => c.close != null)
    .map((c) => ({
      date: c.date.slice(0, 10),
      close: c.close as number,
    }));
  const first = points[0]?.close ?? 0;
  const last = points[points.length - 1]?.close ?? 0;
  const rising = last >= first;
  const color = rising ? "#22c55e" : "#ef4444";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">6-Month Price Trend</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={points} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
            <defs>
              <linearGradient id={`trend-${symbol}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              fontSize={11}
              minTickGap={48}
            />
            <YAxis
              domain={["auto", "auto"]}
              tickFormatter={(v: number) => v.toFixed(0)}
              tickLine={false}
              axisLine={false}
              fontSize={11}
              width={48}
            />
            <Tooltip
              formatter={(value) => [formatPrice(Number(value)), "Close"]}
              contentStyle={{
                backgroundColor: "var(--popover)",
                borderColor: "var(--border)",
                borderRadius: 8,
                color: "var(--popover-foreground)",
              }}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke={color}
              strokeWidth={2}
              fill={`url(#trend-${symbol})`}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
