import Link from "next/link";
import { ExternalLink } from "lucide-react";

import type { NewsItem } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

const CATEGORY_LABELS: Record<string, string> = {
  markets: "Markets",
  economy: "Economy",
  fed: "Fed",
  policy: "Policy",
  earnings: "Earnings",
};

export function NewsCard({ item }: { item: NewsItem }) {
  return (
    <Card className="py-0 transition-colors hover:bg-muted/40">
      <CardContent className="px-4 py-3 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{item.source}</span>
          {item.category !== "markets" && (
            <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
              {CATEGORY_LABELS[item.category] ?? item.category}
            </Badge>
          )}
          {item.symbols.map((s) => (
            <Link
              key={s}
              href={`/stocks/${s}`}
              className="font-mono text-positive hover:underline"
            >
              {s}
            </Link>
          ))}
          {item.published_at && (
            <span className="ml-auto">{formatRelativeTime(item.published_at)}</span>
          )}
        </div>
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="group flex items-start gap-1.5"
        >
          <span className="text-sm font-medium leading-snug group-hover:text-primary">
            {item.title}
          </span>
          <ExternalLink className="mt-0.5 size-3 shrink-0 opacity-40" />
        </a>
        {item.summary && (
          <p className="line-clamp-2 text-xs text-muted-foreground">{item.summary}</p>
        )}
      </CardContent>
    </Card>
  );
}
