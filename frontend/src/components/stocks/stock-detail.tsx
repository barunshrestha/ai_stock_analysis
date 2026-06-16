"use client";

import { useQuery } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StockHeader } from "@/components/stocks/stock-header";
import { MetricCards } from "@/components/stocks/metric-cards";
import { PriceChart } from "@/components/stocks/price-chart";
import { FinancialsTables } from "@/components/stocks/financials-tables";
import { ComprehensiveTable } from "@/components/stocks/comprehensive-table";
import { TrendChart } from "@/components/stocks/trend-chart";
import { EarningsChart } from "@/components/stocks/earnings-chart";
import { AiSummary } from "@/components/stocks/ai-summary";

function LoadingState() {
  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-5 w-40" />
        </div>
        <Skeleton className="h-10 w-32" />
      </div>
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  );
}

/** Everything loads automatically on navigation — no Analyze button (PRD req 6). */
export function StockDetail({ symbol }: { symbol: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["overview", symbol],
    queryFn: () => api.stockOverview(symbol),
  });

  if (isPending) return <LoadingState />;

  if (isError) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="flex flex-col items-center gap-2 py-24 text-center">
        <h1 className="text-xl font-semibold">
          {notFound ? `“${symbol}” not found` : "Failed to load stock data"}
        </h1>
        <p className="max-w-md text-sm text-muted-foreground">
          {notFound
            ? "Check the ticker symbol or use the search bar above to find the right one."
            : error instanceof Error
              ? error.message
              : "Unknown error."}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <StockHeader overview={data} />

      <Tabs defaultValue="overview" className="space-y-4">
        <div className="overflow-x-auto">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="fundamentals">Fundamentals</TabsTrigger>
            <TabsTrigger value="comprehensive">Comprehensive</TabsTrigger>
            <TabsTrigger value="earnings">Earnings</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="overview" className="space-y-4">
          <MetricCards metrics={data.metrics} />
          <PriceChart symbol={symbol} />
          <AiSummary symbol={symbol} />
          {data.business_summary && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  About {data.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {data.business_summary}
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="fundamentals">
          <FinancialsTables symbol={symbol} />
        </TabsContent>

        <TabsContent value="comprehensive" className="space-y-4">
          <TrendChart symbol={symbol} />
          <ComprehensiveTable metrics={data.metrics} />
        </TabsContent>

        <TabsContent value="earnings">
          <EarningsChart symbol={symbol} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
