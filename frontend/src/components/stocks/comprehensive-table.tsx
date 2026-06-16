"use client";

import type { StockMetrics } from "@/lib/api";
import {
  changeColor,
  formatCompact,
  formatNumber,
  formatPct,
  formatPrice,
} from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface Row {
  label: string;
  value: string;
  colorClass?: string;
}

interface Group {
  title: string;
  rows: Row[];
}

function buildGroups(m: StockMetrics): Group[] {
  return [
    {
      title: "Price & Volume",
      rows: [
        { label: "Current Price", value: formatPrice(m.current_price) },
        {
          label: "Daily Change",
          value: formatPct(m.daily_change_pct, { signed: true }),
          colorClass: changeColor(m.daily_change_pct),
        },
        {
          label: "Weekly Change",
          value: formatPct(m.weekly_change_pct, { signed: true }),
          colorClass: changeColor(m.weekly_change_pct),
        },
        {
          label: "Monthly Change",
          value: formatPct(m.monthly_change_pct, { signed: true }),
          colorClass: changeColor(m.monthly_change_pct),
        },
        {
          label: "Yearly Change",
          value: formatPct(m.yearly_change_pct, { signed: true }),
          colorClass: changeColor(m.yearly_change_pct),
        },
        { label: "Volume", value: formatCompact(m.volume) },
        { label: "20-Day MA", value: formatPrice(m.ma_20) },
        { label: "50-Day MA", value: formatPrice(m.ma_50) },
        { label: "52-Week High", value: formatPrice(m.week_52_high) },
        { label: "52-Week Low", value: formatPrice(m.week_52_low) },
        { label: "Annual Volatility", value: formatPct(m.volatility_annual_pct) },
        { label: "Beta", value: formatNumber(m.beta) },
      ],
    },
    {
      title: "Valuation",
      rows: [
        { label: "Market Cap", value: formatCompact(m.market_cap) },
        { label: "P/E (TTM)", value: formatNumber(m.pe_ratio) },
        { label: "Forward P/E", value: formatNumber(m.forward_pe) },
        { label: "P/B Ratio", value: formatNumber(m.pb_ratio) },
        { label: "P/S Ratio", value: formatNumber(m.ps_ratio) },
        { label: "PEG Ratio", value: formatNumber(m.peg_ratio) },
        { label: "EPS", value: formatNumber(m.eps) },
        { label: "Book Value / Share", value: formatNumber(m.book_value_per_share) },
        { label: "Dividend Yield", value: formatPct(m.dividend_yield_pct) },
      ],
    },
    {
      title: "Profitability",
      rows: [
        { label: "Revenue", value: formatCompact(m.revenue) },
        {
          label: "Revenue Growth",
          value: formatPct(m.revenue_growth_pct, { signed: true }),
          colorClass: changeColor(m.revenue_growth_pct),
        },
        { label: "Gross Margin", value: formatPct(m.gross_margin_pct) },
        { label: "Operating Margin", value: formatPct(m.operating_margin_pct) },
        { label: "Profit Margin", value: formatPct(m.profit_margin_pct) },
        { label: "ROE", value: formatPct(m.roe_pct) },
        { label: "ROA", value: formatPct(m.roa_pct) },
      ],
    },
    {
      title: "Financial Health",
      rows: [
        { label: "Debt / Equity", value: formatNumber(m.debt_to_equity) },
        { label: "Current Ratio", value: formatNumber(m.current_ratio) },
        { label: "Operating Cash Flow", value: formatCompact(m.operating_cash_flow) },
        { label: "Free Cash Flow", value: formatCompact(m.free_cash_flow) },
      ],
    },
  ];
}

/** Full metric breakdown for the Comprehensive tab. */
export function ComprehensiveTable({ metrics }: { metrics: StockMetrics }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {buildGroups(metrics).map((group) => (
        <Card key={group.title}>
          <CardHeader>
            <CardTitle className="text-base">{group.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableBody>
                {group.rows.map((row) => (
                  <TableRow key={row.label}>
                    <TableCell className="text-muted-foreground">
                      {row.label}
                    </TableCell>
                    <TableCell
                      className={cn(
                        "text-right font-medium tabular-nums",
                        row.colorClass,
                      )}
                    >
                      {row.value}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
