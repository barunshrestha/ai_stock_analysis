"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Briefcase } from "lucide-react";

import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function PortfolioNews() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["news-portfolio"],
    queryFn: () => api.newsPortfolio(),
    staleTime: 5 * 60_000,
  });

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Briefcase className="size-4 text-muted-foreground" />
        <h2 className="text-lg font-semibold tracking-tight">Your Portfolio News</h2>
      </div>
      {isPending ? (
        <div className="flex gap-2 overflow-hidden">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-72 shrink-0" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-muted-foreground">Could not load portfolio news.</p>
      ) : !data?.symbols.length ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-dashed px-4 py-3">
          <p className="text-sm text-muted-foreground">
            Add stocks to your portfolio to see ticker-specific headlines here.
          </p>
          <Button asChild size="sm" variant="outline">
            <Link href="/portfolio">Go to Portfolio</Link>
          </Button>
        </div>
      ) : !data.items.length ? (
        <p className="text-sm text-muted-foreground">
          No recent news for your portfolio symbols.
        </p>
      ) : (
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
          {data.items.map((item) => (
            <Card key={item.id} className="w-72 shrink-0 py-0">
              <CardContent className="space-y-1 px-3 py-2.5">
                <div className="flex items-center gap-2 text-xs">
                  {item.symbols[0] && (
                    <Link
                      href={`/stocks/${item.symbols[0]}`}
                      className="font-mono font-semibold text-positive hover:underline"
                    >
                      {item.symbols[0]}
                    </Link>
                  )}
                  <span className="truncate text-muted-foreground">{item.source}</span>
                  {item.published_at && (
                    <span className="ml-auto shrink-0 text-muted-foreground">
                      {formatRelativeTime(item.published_at)}
                    </span>
                  )}
                </div>
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="line-clamp-3 text-sm font-medium leading-snug hover:text-primary"
                >
                  {item.title}
                </a>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
