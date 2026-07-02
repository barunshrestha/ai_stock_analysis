"use client";

import * as React from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { BacktestResult, BacktestSummary } from "@/lib/api";
import { changeColor, formatCompact, formatNumber, formatPct, formatPrice } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

const SCORE_COLOR = "#3b82f6";
const EQUAL_COLOR = "#a855f7";
const INVESTED_COLOR = "#9ca3af";

function SummaryCard({
  title,
  summary,
  accent,
}: {
  title: string;
  summary: BacktestSummary;
  accent: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <span
            className="inline-block size-2.5 rounded-full"
            style={{ backgroundColor: accent }}
          />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <div className="text-xs text-muted-foreground">Invested</div>
            <div className="font-semibold tabular-nums">
              {formatPrice(summary.total_invested)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Final Value</div>
            <div className="font-semibold tabular-nums">
              {formatPrice(summary.final_value)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">ROI</div>
            <div
              className={cn(
                "font-semibold tabular-nums",
                changeColor(summary.roi_pct),
              )}
            >
              {formatPct(summary.roi_pct, { signed: true })}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">CAGR</div>
            <div
              className={cn(
                "font-semibold tabular-nums",
                changeColor(summary.cagr_pct),
              )}
            >
              {formatPct(summary.cagr_pct, { signed: true })}
            </div>
          </div>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          {summary.days} trading days
        </p>
      </CardContent>
    </Card>
  );
}

export function DcaResults({ result }: { result: BacktestResult }) {
  const chartData = React.useMemo(() => {
    const equalByDate = new Map(
      result.equal_weight.curve.map((p) => [p.date, p.portfolio_value]),
    );
    return result.score_weighted.curve.map((p) => ({
      date: p.date,
      score_weighted: Math.round(p.portfolio_value * 100) / 100,
      equal_weight:
        Math.round((equalByDate.get(p.date) ?? 0) * 100) / 100,
      invested: Math.round(p.total_invested * 100) / 100,
    }));
  }, [result]);

  const latestWeights =
    result.score_weighted.curve.at(-1)?.weights ?? {};

  return (
    <div className="space-y-4">
      {result.skipped.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Skipped (no data): {result.skipped.join(", ")}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <SummaryCard
          title="Score-Weighted DCA"
          summary={result.score_weighted.summary}
          accent={SCORE_COLOR}
        />
        <SummaryCard
          title="Equal-Weight DCA"
          summary={result.equal_weight.summary}
          accent={EQUAL_COLOR}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Portfolio Value Over Time</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                fontSize={11}
                minTickGap={48}
              />
              <YAxis
                tickFormatter={(v: number) => formatCompact(v)}
                tickLine={false}
                axisLine={false}
                fontSize={11}
                width={56}
              />
              <Tooltip
                formatter={(value, name) => [
                  formatPrice(Number(value)),
                  name === "score_weighted"
                    ? "Score-Weighted"
                    : name === "equal_weight"
                      ? "Equal-Weight"
                      : "Invested",
                ]}
                contentStyle={{
                  backgroundColor: "var(--popover)",
                  borderColor: "var(--border)",
                  borderRadius: 8,
                  color: "var(--popover-foreground)",
                }}
              />
              <Legend
                formatter={(value: string) =>
                  value === "score_weighted"
                    ? "Score-Weighted"
                    : value === "equal_weight"
                      ? "Equal-Weight"
                      : "Total Invested"
                }
              />
              <Line
                type="monotone"
                dataKey="score_weighted"
                stroke={SCORE_COLOR}
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="equal_weight"
                stroke={EQUAL_COLOR}
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="invested"
                stroke={INVESTED_COLOR}
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Final Position (Score-Weighted)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead className="text-right">Shares Accumulated</TableHead>
                  <TableHead className="text-right">Latest Allocation</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.symbols.map((s) => (
                  <TableRow key={s}>
                    <TableCell className="font-mono font-semibold">{s}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatNumber(result.final_shares[s] ?? null, 4)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {latestWeights[s] != null
                        ? formatPct(latestWeights[s] * 100)
                        : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
