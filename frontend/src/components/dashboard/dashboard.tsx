"use client";

import { useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EconomicCalendarStrip } from "@/components/news/economic-calendar-strip";
import { NewsFeed } from "@/components/news/news-feed";
import { PortfolioNews } from "@/components/news/portfolio-news";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export function Dashboard() {
  const queryClient = useQueryClient();
  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["news-feed"] });
    queryClient.invalidateQueries({ queryKey: ["news-portfolio"] });
    queryClient.invalidateQueries({ queryKey: ["news-calendar"] });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            {greeting()} · {today}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw className="size-4" />
          Refresh
        </Button>
      </div>

      <EconomicCalendarStrip />
      <PortfolioNews />
      <NewsFeed />
    </div>
  );
}
