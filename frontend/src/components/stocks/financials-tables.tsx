"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type StatementPayload } from "@/lib/api";
import { formatCompact } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function StatementTable({ statement }: { statement: StatementPayload | null }) {
  if (!statement || statement.rows.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No data available for this statement.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="min-w-48 bg-background sticky left-0">
              Line Item
            </TableHead>
            {statement.columns.map((col) => (
              <TableHead key={col} className="text-right whitespace-nowrap">
                {col}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {statement.rows.map((row) => (
            <TableRow key={row.item}>
              <TableCell className="min-w-48 bg-background sticky left-0 font-medium">
                {row.item}
              </TableCell>
              {row.values.map((v, i) => (
                <TableCell key={i} className="text-right tabular-nums">
                  {formatCompact(v)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function FinancialsTables({ symbol }: { symbol: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["financials", symbol],
    queryFn: () => api.stockFinancials(symbol),
  });

  if (isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-9 w-72" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (isError) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Failed to load financials:{" "}
        {error instanceof Error ? error.message : "unknown error"}
      </p>
    );
  }

  return (
    <Tabs defaultValue="income" className="space-y-3">
      <TabsList>
        <TabsTrigger value="income">Income Statement</TabsTrigger>
        <TabsTrigger value="balance">Balance Sheet</TabsTrigger>
        <TabsTrigger value="cashflow">Cash Flow</TabsTrigger>
      </TabsList>
      <TabsContent value="income">
        <StatementTable statement={data.income_stmt} />
      </TabsContent>
      <TabsContent value="balance">
        <StatementTable statement={data.balance_sheet} />
      </TabsContent>
      <TabsContent value="cashflow">
        <StatementTable statement={data.cash_flow} />
      </TabsContent>
    </Tabs>
  );
}
