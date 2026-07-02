"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, Download, Trash2 } from "lucide-react";

import { api, type StockMetrics } from "@/lib/api";
import {
  changeColor,
  formatCompact,
  formatNumber,
  formatPct,
  formatPrice,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AddStockDialog } from "@/components/portfolio/add-stock-dialog";
import { Sparkline } from "@/components/portfolio/sparkline";

interface GridRow {
  symbol: string;
  name: string;
  sector: string | null;
  metrics: StockMetrics;
  sparkline: number[];
}

type Formatter = "price" | "pct" | "signedPct" | "compact" | "number";

interface MetricCol {
  key: keyof StockMetrics;
  label: string;
  fmt: Formatter;
}

const TAB_COLUMNS: Record<string, MetricCol[]> = {
  performance: [
    { key: "current_price", label: "Price", fmt: "price" },
    { key: "daily_change_pct", label: "1D %", fmt: "signedPct" },
    { key: "weekly_change_pct", label: "1W %", fmt: "signedPct" },
    { key: "monthly_change_pct", label: "1M %", fmt: "signedPct" },
    { key: "yearly_change_pct", label: "1Y %", fmt: "signedPct" },
    { key: "volatility_annual_pct", label: "Volatility", fmt: "pct" },
  ],
  valuation: [
    { key: "market_cap", label: "Mkt Cap", fmt: "compact" },
    { key: "pe_ratio", label: "P/E", fmt: "number" },
    { key: "forward_pe", label: "Fwd P/E", fmt: "number" },
    { key: "pb_ratio", label: "P/B", fmt: "number" },
    { key: "ps_ratio", label: "P/S", fmt: "number" },
    { key: "peg_ratio", label: "PEG", fmt: "number" },
    { key: "eps", label: "EPS", fmt: "number" },
    { key: "dividend_yield_pct", label: "Div Yield", fmt: "pct" },
  ],
  profitability: [
    { key: "revenue", label: "Revenue", fmt: "compact" },
    { key: "revenue_growth_pct", label: "Rev Growth", fmt: "signedPct" },
    { key: "gross_margin_pct", label: "Gross Mgn", fmt: "pct" },
    { key: "operating_margin_pct", label: "Op Mgn", fmt: "pct" },
    { key: "profit_margin_pct", label: "Net Mgn", fmt: "pct" },
    { key: "roe_pct", label: "ROE", fmt: "pct" },
    { key: "roa_pct", label: "ROA", fmt: "pct" },
  ],
  health: [
    { key: "debt_to_equity", label: "D/E", fmt: "number" },
    { key: "current_ratio", label: "Current Ratio", fmt: "number" },
    { key: "operating_cash_flow", label: "Op CF", fmt: "compact" },
    { key: "free_cash_flow", label: "FCF", fmt: "compact" },
    { key: "book_value_per_share", label: "BV/Share", fmt: "number" },
    { key: "beta", label: "Beta", fmt: "number" },
  ],
  price: [
    { key: "current_price", label: "Price", fmt: "price" },
    { key: "ma_20", label: "MA 20", fmt: "price" },
    { key: "ma_50", label: "MA 50", fmt: "price" },
    { key: "week_52_high", label: "52W High", fmt: "price" },
    { key: "week_52_low", label: "52W Low", fmt: "price" },
    { key: "volume", label: "Volume", fmt: "compact" },
  ],
};

function formatValue(value: number | null, fmt: Formatter): string {
  switch (fmt) {
    case "price":
      return formatPrice(value);
    case "pct":
      return formatPct(value);
    case "signedPct":
      return formatPct(value, { signed: true });
    case "compact":
      return formatCompact(value);
    case "number":
      return formatNumber(value);
  }
}

function buildColumns(
  tab: string,
  onRemove: (symbol: string) => void,
): ColumnDef<GridRow>[] {
  const metricCols: ColumnDef<GridRow>[] = TAB_COLUMNS[tab].map((col) => ({
    id: col.key,
    accessorFn: (row) => row.metrics[col.key] ?? undefined,
    sortUndefined: "last",
    header: col.label,
    cell: ({ row }) => {
      const value = row.original.metrics[col.key];
      return (
        <span
          className={cn(
            "tabular-nums",
            col.fmt === "signedPct" && changeColor(value),
          )}
        >
          {formatValue(value, col.fmt)}
        </span>
      );
    },
  }));

  return [
    {
      id: "symbol",
      accessorKey: "symbol",
      header: "Symbol",
      cell: ({ row }) => (
        <Link
          href={`/stocks/${row.original.symbol}`}
          className="font-mono font-semibold hover:underline"
        >
          {row.original.symbol}
        </Link>
      ),
    },
    {
      id: "name",
      accessorKey: "name",
      header: "Company",
      cell: ({ row }) => (
        <div className="max-w-44 truncate">
          <div className="truncate font-medium">{row.original.name}</div>
          <div className="truncate text-xs text-muted-foreground">
            {row.original.sector ?? ""}
          </div>
        </div>
      ),
    },
    {
      id: "trend",
      header: "6M Trend",
      enableSorting: false,
      cell: ({ row }) => <Sparkline values={row.original.sparkline} />,
    },
    ...metricCols,
    {
      id: "actions",
      header: "",
      enableSorting: false,
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon"
          className="size-7 text-muted-foreground hover:text-negative"
          onClick={() => onRemove(row.original.symbol)}
          aria-label={`Remove ${row.original.symbol}`}
        >
          <Trash2 className="size-4" />
        </Button>
      ),
    },
  ];
}

function exportCsv(rows: GridRow[], tab: string) {
  const cols = TAB_COLUMNS[tab];
  const header = ["Symbol", "Company", "Sector", ...cols.map((c) => c.label)];
  const lines = rows.map((row) =>
    [
      row.symbol,
      `"${row.name.replaceAll('"', '""')}"`,
      `"${(row.sector ?? "").replaceAll('"', '""')}"`,
      ...cols.map((c) => row.metrics[c.key] ?? ""),
    ].join(","),
  );
  const csv = [header.join(","), ...lines].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `portfolio-${tab}-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function PortfolioGrid() {
  const queryClient = useQueryClient();
  const [tab, setTab] = React.useState("performance");
  const [sorting, setSorting] = React.useState<SortingState>([]);

  const { data, isPending, isError, error } = useQuery({
    queryKey: ["portfolio", "grid"],
    queryFn: () => api.portfolioGrid(),
  });

  const removeMutation = useMutation({
    mutationFn: (symbol: string) => api.removeFromPortfolio(symbol),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["portfolio"] }),
  });

  const onRemove = React.useCallback(
    (symbol: string) => removeMutation.mutate(symbol),
    [removeMutation],
  );

  const columns = React.useMemo(() => buildColumns(tab, onRemove), [tab, onRemove]);
  const rows = React.useMemo(() => data?.rows ?? [], [data]);

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-9 w-full max-w-lg" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (isError) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        Failed to load portfolio:{" "}
        {error instanceof Error ? error.message : "unknown error"}
      </p>
    );
  }

  const fetchErrors = Object.entries(data.errors);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Tabs value={tab} onValueChange={setTab}>
          <div className="overflow-x-auto">
            <TabsList>
              <TabsTrigger value="performance">Performance</TabsTrigger>
              <TabsTrigger value="valuation">Valuation</TabsTrigger>
              <TabsTrigger value="profitability">Profitability</TabsTrigger>
              <TabsTrigger value="health">Health</TabsTrigger>
              <TabsTrigger value="price">Price</TabsTrigger>
            </TabsList>
          </div>
        </Tabs>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => exportCsv(rows, tab)}
            disabled={rows.length === 0}
          >
            <Download className="size-4" />
            CSV
          </Button>
          <AddStockDialog />
        </div>
      </div>

      {fetchErrors.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Could not load: {fetchErrors.map(([s]) => s).join(", ")}
        </p>
      )}

      {rows.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-20 text-center">
          <p className="text-sm text-muted-foreground">
            Your portfolio is empty. Add a stock to start tracking it.
          </p>
          <AddStockDialog />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((hg) => (
                <TableRow key={hg.id}>
                  {hg.headers.map((header) => {
                    const canSort = header.column.getCanSort();
                    const dir = header.column.getIsSorted();
                    return (
                      <TableHead
                        key={header.id}
                        className={cn(
                          "whitespace-nowrap",
                          canSort && "cursor-pointer select-none",
                        )}
                        onClick={
                          canSort
                            ? header.column.getToggleSortingHandler()
                            : undefined
                        }
                      >
                        <span className="inline-flex items-center gap-1">
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                          {canSort &&
                            (dir === "asc" ? (
                              <ArrowUp className="size-3" />
                            ) : dir === "desc" ? (
                              <ArrowDown className="size-3" />
                            ) : (
                              <ArrowUpDown className="size-3 opacity-40" />
                            ))}
                        </span>
                      </TableHead>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="whitespace-nowrap">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
