"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";

export function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

interface SymbolSearchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (symbol: string) => void;
  title?: string;
  groupHeading?: string;
}

/** Shared Yahoo-autosuggest dialog used by global search and section pickers. */
export function SymbolSearchDialog({
  open,
  onOpenChange,
  onSelect,
  title = "Search stocks",
  groupHeading = "Stocks",
}: SymbolSearchDialogProps) {
  const [query, setQuery] = React.useState("");
  const debouncedQuery = useDebounced(query.trim(), 300);

  const { data, isFetching } = useQuery({
    queryKey: ["search", debouncedQuery],
    queryFn: () => api.search(debouncedQuery),
    enabled: open && debouncedQuery.length >= 1,
    staleTime: 5 * 60_000,
  });

  return (
    <CommandDialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) setQuery("");
      }}
      shouldFilter={false}
      title={title}
    >
      <CommandInput
        placeholder="Search by company name or ticker…"
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {debouncedQuery.length === 0
            ? "Type to search — e.g. “apple” or “AAPL”"
            : isFetching
              ? "Searching…"
              : "No matches found."}
        </CommandEmpty>
        {data && data.results.length > 0 && (
          <CommandGroup heading={groupHeading}>
            {data.results.map((r) => (
              <CommandItem
                key={r.symbol}
                value={r.symbol}
                onSelect={() => {
                  onSelect(r.symbol);
                  setQuery("");
                }}
                className="flex items-center gap-3"
              >
                <span className="w-16 shrink-0 font-mono font-semibold">
                  {r.symbol}
                </span>
                <span className="flex-1 truncate text-muted-foreground">
                  {r.name ?? "—"}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {r.exchange ?? ""}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
