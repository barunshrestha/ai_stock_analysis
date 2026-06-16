"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/lib/api";
import { formatCompact } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** 5-year Net Income bar chart (Earnings tab). */
export function EarningsChart({ symbol }: { symbol: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["earnings", symbol],
    queryFn: () => api.stockEarnings(symbol),
  });

  if (isPending) return <Skeleton className="h-80 w-full" />;
  if (isError) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Failed to load earnings:{" "}
        {error instanceof Error ? error.message : "unknown error"}
      </p>
    );
  }
  if (data.earnings.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No earnings history available.
      </p>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Net Income by Year</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data.earnings} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="year" tickLine={false} axisLine={false} fontSize={12} />
            <YAxis
              tickFormatter={(v: number) => formatCompact(v)}
              tickLine={false}
              axisLine={false}
              fontSize={12}
              width={64}
            />
            <Tooltip
              formatter={(value) => [formatCompact(Number(value)), "Net Income"]}
              cursor={{ fill: "var(--muted)", opacity: 0.4 }}
              contentStyle={{
                backgroundColor: "var(--popover)",
                borderColor: "var(--border)",
                borderRadius: 8,
                color: "var(--popover-foreground)",
              }}
            />
            <Bar dataKey="net_income" radius={[4, 4, 0, 0]}>
              {data.earnings.map((entry) => (
                <Cell
                  key={entry.year}
                  fill={entry.net_income >= 0 ? "#22c55e" : "#ef4444"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
