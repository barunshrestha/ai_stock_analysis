"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { PortfolioGrid } from "@/components/portfolio/portfolio-grid";
import {
  PORTFOLIO_VIEW_KEY,
  PortfolioViewSelector,
  selectionToView,
  type PortfolioViewSelection,
} from "@/components/portfolio/portfolio-view-selector";

export function PortfolioPageClient() {
  const [selection, setSelection] =
    React.useState<PortfolioViewSelection>(PORTFOLIO_VIEW_KEY);
  const view = selectionToView(selection);
  const isPortfolio = view.mode === "portfolio";

  const { data: industriesData } = useQuery({
    queryKey: ["admin-industries"],
    queryFn: () => api.adminIndustries(),
    enabled: !isPortfolio,
  });

  const industryStockCount =
    view.mode === "industry"
      ? (industriesData?.industries[view.industry]?.length ?? null)
      : null;

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {isPortfolio ? "My Portfolio" : view.industry}
          </h1>
          <p className="text-sm text-muted-foreground">
            {isPortfolio ? (
              <>
                Saved stocks with live metrics. Click a column to sort, a symbol
                to open its analysis.
              </>
            ) : industryStockCount !== null ? (
              <>
                {industryStockCount} stock{industryStockCount === 1 ? "" : "s"}{" "}
                in this industry. Click a column to sort, a symbol to open its
                analysis.
              </>
            ) : (
              <>
                Stocks assigned to this industry. Click a column to sort, a
                symbol to open its analysis.
              </>
            )}
          </p>
        </div>
        <PortfolioViewSelector value={selection} onChange={setSelection} />
      </div>
      <PortfolioGrid view={view} />
    </div>
  );
}
