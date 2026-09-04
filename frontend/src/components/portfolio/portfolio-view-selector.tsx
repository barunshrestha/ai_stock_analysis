"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { api, type PortfolioView } from "@/lib/api";
import { cn } from "@/lib/utils";
import { NewPortfolioDialog } from "@/components/portfolio/new-portfolio-dialog";

export const PORTFOLIO_SELECTION_STORAGE = "portfolio-view-selection";
export const PORTFOLIO_KEY_PREFIX = "portfolio:";

export type PortfolioViewSelection = string;

export function portfolioSelectionKey(portfolioId: number) {
  return `${PORTFOLIO_KEY_PREFIX}${portfolioId}`;
}

export function parsePortfolioSelection(value: string): number | null {
  if (!value.startsWith(PORTFOLIO_KEY_PREFIX)) return null;
  const id = Number(value.slice(PORTFOLIO_KEY_PREFIX.length));
  return Number.isFinite(id) ? id : null;
}

interface PortfolioViewSelectorProps {
  value: PortfolioViewSelection;
  onChange: (value: PortfolioViewSelection) => void;
  className?: string;
}

export function PortfolioViewSelector({
  value,
  onChange,
  className,
}: PortfolioViewSelectorProps) {
  const { data: portfoliosData, isPending: portfoliosPending } = useQuery({
    queryKey: ["portfolios"],
    queryFn: () => api.listPortfolios(),
  });

  const { data: industriesData, isPending: industriesPending } = useQuery({
    queryKey: ["admin-industries"],
    queryFn: () => api.adminIndustries(),
  });

  const portfolios = portfoliosData?.portfolios ?? [];
  const industries = React.useMemo(
    () => Object.keys(industriesData?.industries ?? {}).sort((a, b) => a.localeCompare(b)),
    [industriesData],
  );

  React.useEffect(() => {
    if (portfolios.length === 0) return;
    const parsed = parsePortfolioSelection(value);
    if (parsed && portfolios.some((p) => p.id === parsed)) return;
    if (!value.startsWith(PORTFOLIO_KEY_PREFIX) && !industries.includes(value)) return;
    if (!value.startsWith(PORTFOLIO_KEY_PREFIX)) return;
    onChange(portfolioSelectionKey(portfolios[0].id));
  }, [portfolios, value, onChange, industries]);

  return (
    <div className={cn("flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3", className)}>
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
        <label htmlFor="portfolio-view" className="shrink-0 text-sm font-medium">
          View
        </label>
        <select
          id="portfolio-view"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={portfoliosPending || industriesPending}
          className="h-9 w-full max-w-xs rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50 sm:w-64"
        >
          {portfolios.length > 0 && (
            <optgroup label="Portfolios">
              {portfolios.map((p) => (
                <option key={p.id} value={portfolioSelectionKey(p.id)}>
                  {p.name}
                  {p.symbol_count > 0 ? ` (${p.symbol_count})` : ""}
                </option>
              ))}
            </optgroup>
          )}
          {industries.length > 0 && (
            <optgroup label="Industries">
              {industries.map((industry) => (
                <option key={industry} value={industry}>
                  {industry}
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </div>
      <NewPortfolioDialog
        onCreated={(id) => {
          onChange(portfolioSelectionKey(id));
        }}
      />
    </div>
  );
}

export function selectionToView(
  selection: PortfolioViewSelection,
  portfolios: { id: number; name: string }[] = [],
): PortfolioView {
  const portfolioId = parsePortfolioSelection(selection);
  if (portfolioId !== null) {
    const match = portfolios.find((p) => p.id === portfolioId);
    return {
      mode: "portfolio",
      portfolioId,
      name: match?.name ?? "Portfolio",
    };
  }
  return { mode: "industry", industry: selection };
}

export function loadStoredSelection(defaultPortfolioId: number | null): PortfolioViewSelection {
  if (typeof window === "undefined") {
    return defaultPortfolioId ? portfolioSelectionKey(defaultPortfolioId) : "";
  }
  const stored = window.localStorage.getItem(PORTFOLIO_SELECTION_STORAGE);
  if (stored) return stored;
  return defaultPortfolioId ? portfolioSelectionKey(defaultPortfolioId) : "";
}

export function storeSelection(selection: PortfolioViewSelection) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PORTFOLIO_SELECTION_STORAGE, selection);
}
