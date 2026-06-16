"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SymbolSearchDialog } from "@/components/search/symbol-search-dialog";

/**
 * Google-Finance-style global stock search.
 * Lives in the top bar on every page; selecting a suggestion navigates
 * straight to /stocks/[symbol] (no Analyze button — PRD req 6).
 */
export function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);

  // Cmd+K / Ctrl+K opens search from anywhere.
  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  return (
    <>
      <Button
        variant="outline"
        className="h-9 w-full max-w-xs justify-start gap-2 text-muted-foreground sm:max-w-sm md:max-w-md"
        onClick={() => setOpen(true)}
      >
        <Search className="size-4" />
        <span className="truncate">Search stocks…</span>
        <kbd className="pointer-events-none ml-auto hidden rounded border bg-muted px-1.5 font-mono text-[10px] font-medium sm:inline-block">
          ⌘K
        </kbd>
      </Button>
      <SymbolSearchDialog
        open={open}
        onOpenChange={setOpen}
        onSelect={(symbol) => {
          setOpen(false);
          router.push(`/stocks/${symbol}`);
        }}
      />
    </>
  );
}
