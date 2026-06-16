"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SymbolSearchDialog } from "@/components/search/symbol-search-dialog";

/**
 * Landing-page symbol picker that routes to a section-specific page,
 * e.g. base="/ai" -> /ai/AAPL.
 */
export function SectionSymbolPicker({
  base,
  label,
}: {
  base: string;
  label: string;
}) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);

  return (
    <>
      <Button
        variant="outline"
        size="lg"
        className="w-full max-w-md justify-start gap-2 text-muted-foreground"
        onClick={() => setOpen(true)}
      >
        <Search className="size-4" />
        {label}
      </Button>
      <SymbolSearchDialog
        open={open}
        onOpenChange={setOpen}
        onSelect={(symbol) => {
          setOpen(false);
          router.push(`${base}/${symbol}`);
        }}
      />
    </>
  );
}
