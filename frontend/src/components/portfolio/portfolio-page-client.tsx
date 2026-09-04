"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { PortfolioGrid } from "@/components/portfolio/portfolio-grid";
import {
  loadStoredSelection,
  PortfolioViewSelector,
  portfolioSelectionKey,
  selectionToView,
  storeSelection,
  type PortfolioViewSelection,
} from "@/components/portfolio/portfolio-view-selector";

export function PortfolioPageClient() {
  const { data: portfoliosData, isPending: portfoliosPending } = useQuery({
    queryKey: ["portfolios"],
    queryFn: () => api.listPortfolios(),
  });

  const portfolios = portfoliosData?.portfolios ?? [];
  const defaultId = portfolios[0]?.id ?? null;

  const [selection, setSelection] = React.useState<PortfolioViewSelection | null>(null);

  React.useEffect(() => {
    if (portfoliosPending) return;
    if (!selection) {
      setSelection(loadStoredSelection(defaultId) || (defaultId ? portfolioSelectionKey(defaultId) : ""));
    }
  }, [portfoliosPending, defaultId, selection]);

  React.useEffect(() => {
    if (!selection) return;
    storeSelection(selection);
  }, [selection]);

  const activeSelection =
    selection || (defaultId ? portfolioSelectionKey(defaultId) : "");
  const view = selectionToView(activeSelection, portfolios);
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

  if (portfoliosPending || !selection) {
    return <div className="h-40 animate-pulse rounded-lg bg-muted/40" />;
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {isPortfolio ? view.name : view.industry}
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
        <PortfolioViewSelector value={activeSelection} onChange={setSelection} />
      </div>
      <PortfolioGrid view={view} />
    </div>
  );
}
