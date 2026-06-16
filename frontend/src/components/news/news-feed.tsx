"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { api, type NewsCategory } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NewsCard } from "@/components/news/news-card";

const TABS: { value: NewsCategory; label: string }[] = [
  { value: "top", label: "Top Stories" },
  { value: "markets", label: "Markets" },
  { value: "economy", label: "US Economy" },
  { value: "fed", label: "Fed & Inflation" },
  { value: "policy", label: "Policy" },
  { value: "earnings", label: "Earnings & IPOs" },
];

function FeedList({ category }: { category: NewsCategory }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["news-feed", category],
    queryFn: () => api.newsFeed(category, 30),
    staleTime: 5 * 60_000,
  });

  if (isPending) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  }
  if (isError) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Failed to load news:{" "}
        {error instanceof Error ? error.message : "unknown error"}
      </p>
    );
  }
  if (!data.items.length) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No headlines in this category right now.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {data.items.map((item) => (
        <NewsCard key={item.id} item={item} />
      ))}
    </div>
  );
}

export function NewsFeed() {
  const [tab, setTab] = React.useState<NewsCategory>("top");

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold tracking-tight">Market News</h2>
      <Tabs value={tab} onValueChange={(v) => setTab(v as NewsCategory)}>
        <div className="overflow-x-auto">
          <TabsList className="h-auto w-max flex-wrap">
            {TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value} className="text-xs sm:text-sm">
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
        {TABS.map((t) => (
          <TabsContent key={t.value} value={t.value} className="mt-3">
            <FeedList category={t.value} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
