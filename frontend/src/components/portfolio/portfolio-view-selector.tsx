"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { api, type PortfolioView } from "@/lib/api";
import { cn } from "@/lib/utils";

export const PORTFOLIO_VIEW_KEY = "My Portfolio";

export type PortfolioViewSelection = typeof PORTFOLIO_VIEW_KEY | string;

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
  const { data, isPending } = useQuery({
    queryKey: ["admin-industries"],
    queryFn: () => api.adminIndustries(),
  });

  const industries = React.useMemo(
    () => Object.keys(data?.industries ?? {}).sort((a, b) => a.localeCompare(b)),
    [data],
  );

  return (
    <div className={cn("flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3", className)}>
      <label htmlFor="portfolio-view" className="shrink-0 text-sm font-medium">
        View
      </label>
      <select
        id="portfolio-view"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isPending}
        className="h-9 w-full max-w-xs rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50 sm:w-64"
      >
        <option value={PORTFOLIO_VIEW_KEY}>My Portfolio</option>
        {industries.map((industry) => (
          <option key={industry} value={industry}>
            {industry}
          </option>
        ))}
      </select>
    </div>
  );
}

export function selectionToView(selection: PortfolioViewSelection): PortfolioView {
  if (selection === PORTFOLIO_VIEW_KEY) {
    return { mode: "portfolio" };
  }
  return { mode: "industry", industry: selection };
}
