"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Upload } from "lucide-react";

import { api, ApiError, type PortfolioImportResult } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

function statusVariant(status: string) {
  if (status === "added") return "default";
  if (status === "skipped") return "secondary";
  return "destructive";
}

export function ImportCsvDialog({ portfolioId }: { portfolioId?: number }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = React.useState(false);
  const [file, setFile] = React.useState<File | null>(null);
  const [result, setResult] = React.useState<PortfolioImportResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const importMut = useMutation({
    mutationFn: (f: File) => api.importPortfolioCsv(f, portfolioId),
    onSuccess: (data) => {
      setResult(data);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
    },
    onError: (e: Error) => {
      setResult(null);
      setError(e instanceof ApiError ? e.message : "Import failed");
    },
  });

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    importMut.reset();
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Upload className="size-4" />
          Import CSV
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Import stocks from CSV</DialogTitle>
          <DialogDescription>
            Add multiple tickers to your portfolio at once. Market data is fetched from Yahoo Finance
            for each symbol.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 text-sm">
          <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">Accepted formats</p>
            <pre className="mt-2 overflow-x-auto whitespace-pre">{`symbol\nAAPL\nMSFT\nGOOGL`}</pre>
            <p className="mt-2">Or with header: <code>symbol,ticker,...</code> — only the symbol column is used.</p>
          </div>

          <Input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setResult(null);
              setError(null);
            }}
          />

          {error && <p className="text-destructive">{error}</p>}

          {result && (
            <div className="space-y-2">
              <p>
                <span className="font-medium">{result.added} added</span>
                {result.skipped > 0 && ` · ${result.skipped} skipped`}
                {result.failed > 0 && ` · ${result.failed} failed`}
                {" "}of {result.total}
              </p>
              <ul className="max-h-48 space-y-1 overflow-y-auto rounded-md border p-2">
                {result.results.map((row) => (
                  <li key={row.symbol} className="flex items-start justify-between gap-2 text-xs">
                    <span className="font-mono font-medium">{row.symbol}</span>
                    <Badge variant={statusVariant(row.status)} className="shrink-0 capitalize">
                      {row.status}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {result ? "Done" : "Cancel"}
            </Button>
            {!result && (
              <Button
                type="button"
                onClick={() => file && importMut.mutate(file)}
                disabled={!file || importMut.isPending}
              >
                {importMut.isPending ? (
                  <>
                    <Loader2 className="mr-1 size-4 animate-spin" />
                    Importing…
                  </>
                ) : (
                  "Import"
                )}
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
