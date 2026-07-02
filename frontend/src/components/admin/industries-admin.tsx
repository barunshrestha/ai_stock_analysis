"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Search, X } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { SymbolSearchDialog } from "@/components/search/symbol-search-dialog";

function AssignForm({ existingIndustries }: { existingIndustries: string[] }) {
  const queryClient = useQueryClient();
  const [pickerOpen, setPickerOpen] = React.useState(false);
  const [symbol, setSymbol] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<string[]>([]);
  const [newIndustry, setNewIndustry] = React.useState("");

  const assign = useMutation({
    mutationFn: () => api.assignIndustries(symbol!, selected),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-industries"] });
      setSymbol(null);
      setSelected([]);
      setNewIndustry("");
    },
  });

  const toggle = (industry: string) =>
    setSelected((prev) =>
      prev.includes(industry)
        ? prev.filter((i) => i !== industry)
        : [...prev, industry],
    );

  const addNew = () => {
    const name = newIndustry.trim();
    if (!name) return;
    if (!selected.includes(name)) setSelected((prev) => [...prev, name]);
    setNewIndustry("");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Assign a Stock to Industries</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setPickerOpen(true)}>
            <Search className="size-4" />
            {symbol ?? "Pick a stock…"}
          </Button>
          <SymbolSearchDialog
            open={pickerOpen}
            onOpenChange={setPickerOpen}
            onSelect={(s) => {
              setSymbol(s);
              setPickerOpen(false);
            }}
            title="Pick a stock"
          />
        </div>

        <div className="space-y-2">
          <div className="text-sm font-medium">Industries</div>
          <div className="flex flex-wrap gap-1.5">
            {existingIndustries.map((industry) => (
              <button key={industry} onClick={() => toggle(industry)}>
                <Badge
                  variant={selected.includes(industry) ? "default" : "outline"}
                  className="cursor-pointer"
                >
                  {industry}
                </Badge>
              </button>
            ))}
            {selected
              .filter((i) => !existingIndustries.includes(i))
              .map((industry) => (
                <button key={industry} onClick={() => toggle(industry)}>
                  <Badge className="cursor-pointer gap-1">
                    {industry}
                    <X className="size-3" />
                  </Badge>
                </button>
              ))}
          </div>
          <div className="flex gap-2">
            <Input
              value={newIndustry}
              onChange={(e) => setNewIndustry(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addNew();
                }
              }}
              placeholder="New industry name…"
              className="h-9 w-56"
            />
            <Button
              variant="outline"
              size="sm"
              className="h-9"
              onClick={addNew}
              disabled={!newIndustry.trim()}
            >
              <Plus className="size-4" />
              Add
            </Button>
          </div>
        </div>

        <Button
          size="sm"
          disabled={!symbol || selected.length === 0 || assign.isPending}
          onClick={() => assign.mutate()}
        >
          {assign.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Assigning…
            </>
          ) : (
            <>Assign {symbol ?? ""} to {selected.length || "…"} industr{selected.length === 1 ? "y" : "ies"}</>
          )}
        </Button>
        {assign.isError && (
          <p className="text-sm text-negative">
            {assign.error instanceof Error
              ? assign.error.message
              : "Failed to assign."}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function IndustriesAdmin() {
  const queryClient = useQueryClient();
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["admin-industries"],
    queryFn: () => api.adminIndustries(),
  });

  const remove = useMutation({
    mutationFn: ({ symbol, industry }: { symbol: string; industry: string }) =>
      api.removeIndustryAssignment(symbol, industry),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["admin-industries"] }),
  });

  if (isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (isError) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        Failed to load industries:{" "}
        {error instanceof Error ? error.message : "unknown error"}
      </p>
    );
  }

  const industries = Object.entries(data.industries).sort(([a], [b]) =>
    a.localeCompare(b),
  );

  return (
    <div className="space-y-4">
      <AssignForm existingIndustries={industries.map(([name]) => name)} />

      {industries.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">
          No industries yet. Assign a stock above to create the first one.
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {industries.map(([industry, stocks]) => (
            <Card key={industry} className="py-4">
              <CardHeader className="px-4">
                <CardTitle className="flex items-center justify-between text-sm">
                  {industry}
                  <span className="text-xs font-normal text-muted-foreground">
                    {stocks.length} stock{stocks.length === 1 ? "" : "s"}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="px-4">
                <div className="flex flex-wrap gap-1.5">
                  {stocks.map((s) => (
                    <Badge
                      key={s.symbol}
                      variant="secondary"
                      className={cn(
                        "gap-1 font-mono",
                        remove.isPending && "opacity-60",
                      )}
                    >
                      <Link
                        href={`/stocks/${s.symbol}`}
                        className="hover:underline"
                        title={s.company_name ?? undefined}
                      >
                        {s.symbol}
                      </Link>
                      <button
                        onClick={() =>
                          remove.mutate({ symbol: s.symbol, industry })
                        }
                        aria-label={`Remove ${s.symbol} from ${industry}`}
                        className="rounded-full hover:text-negative"
                      >
                        <X className="size-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
