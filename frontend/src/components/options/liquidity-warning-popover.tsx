"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HelpCircle, Loader2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const SPREAD_MAX_PCT = 10;
const MIN_OPEN_INTEREST = 50;
const NOTE_KEY = "liquidity";
const LOCAL_PREFIX = "csp-note:liquidity:";

export type LiquidityMetrics = {
  bid?: number | null;
  ask?: number | null;
  premium_mid?: number | null;
  spread_pct?: number | null;
  open_interest?: number | null;
  volume?: number | null;
};

function localKey(ticker: string) {
  return `${LOCAL_PREFIX}${ticker.toUpperCase()}`;
}

function readLocalNote(ticker: string): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(localKey(ticker)) ?? "";
  } catch {
    return "";
  }
}

function writeLocalNote(ticker: string, content: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(localKey(ticker), content);
}

function buildReasons(m: LiquidityMetrics): string[] {
  const reasons: string[] = [];
  if (m.spread_pct != null && m.spread_pct > SPREAD_MAX_PCT) {
    reasons.push(
      `Bid–ask spread is ${m.spread_pct.toFixed(1)}% of mid (threshold ${SPREAD_MAX_PCT}%).`,
    );
  }
  if (m.open_interest != null && m.open_interest < MIN_OPEN_INTEREST) {
    reasons.push(
      `Open interest is ${m.open_interest} contracts (threshold ${MIN_OPEN_INTEREST}).`,
    );
  }
  if (reasons.length === 0) {
    reasons.push("Liquidity checks failed for this contract (spread and/or open interest).");
  }
  return reasons;
}

/**
 * Clickable "Low liquidity / wide spread" label with explanation + per-ticker notes.
 * storageMode "browser" = pre-analysis localStorage; "server" = DB for saved trades.
 */
export function LiquidityWarningPopover({
  ticker,
  metrics,
  storageMode,
}: {
  ticker: string;
  metrics: LiquidityMetrics;
  storageMode: "browser" | "server";
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = React.useState(false);
  const [draft, setDraft] = React.useState("");
  const [savedFlash, setSavedFlash] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const serverQ = useQuery({
    queryKey: ["ticker-note", ticker, NOTE_KEY],
    queryFn: () => api.getTickerNote(ticker, NOTE_KEY),
    enabled: open && storageMode === "server",
  });

  React.useEffect(() => {
    if (!open) return;
    setError(null);
    setSavedFlash(false);
    if (storageMode === "browser") {
      setDraft(readLocalNote(ticker));
    } else if (serverQ.data) {
      setDraft(serverQ.data.content ?? "");
    }
  }, [open, storageMode, ticker, serverQ.data]);

  const saveMut = useMutation({
    mutationFn: async () => {
      if (storageMode === "browser") {
        writeLocalNote(ticker, draft);
        return { content: draft };
      }
      return api.putTickerNote(ticker, draft, NOTE_KEY);
    },
    onSuccess: () => {
      setSavedFlash(true);
      setError(null);
      if (storageMode === "server") {
        queryClient.invalidateQueries({ queryKey: ["ticker-note", ticker, NOTE_KEY] });
      }
    },
    onError: (e: Error) => {
      setError(e instanceof ApiError ? e.message : "Could not save note");
    },
  });

  const reasons = buildReasons(metrics);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1 text-left text-amber-600 underline decoration-dotted underline-offset-2 hover:text-amber-500 dark:text-amber-400"
        >
          Low liquidity / wide spread
          <HelpCircle className="size-3.5 shrink-0 opacity-80" aria-hidden />
        </button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Low liquidity / wide spread</DialogTitle>
          <DialogDescription>
            Plain-English explanation for {ticker.toUpperCase()} — why this flag appeared and what to
            do next.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 text-sm">
          <section className="space-y-1">
            <h4 className="font-medium">What this means</h4>
            <p className="text-muted-foreground">
              The option is harder or more expensive to trade cleanly. Either few traders are in this
              contract (low open interest), or the gap between what buyers bid and sellers ask is
              large relative to the option&apos;s mid price. That gap can eat a big chunk of the
              premium you expect to collect when you open or close a short put.
            </p>
          </section>

          <section className="space-y-1">
            <h4 className="font-medium">Why it flagged this trade</h4>
            <ul className="list-inside list-disc space-y-1 text-muted-foreground">
              {reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
            <div className="mt-2 grid grid-cols-2 gap-2 rounded-md border bg-muted/30 p-2 text-xs">
              <span>Bid: {metrics.bid != null ? `$${metrics.bid.toFixed(2)}` : "N/A"}</span>
              <span>Ask: {metrics.ask != null ? `$${metrics.ask.toFixed(2)}` : "N/A"}</span>
              <span>
                Mid:{" "}
                {metrics.premium_mid != null ? `$${metrics.premium_mid.toFixed(2)}` : "N/A"}
              </span>
              <span>
                Spread:{" "}
                {metrics.spread_pct != null ? `${metrics.spread_pct.toFixed(1)}%` : "N/A"}
              </span>
              <span>
                Open interest: {metrics.open_interest != null ? metrics.open_interest : "N/A"}
              </span>
              <span>Volume: {metrics.volume != null ? metrics.volume : "N/A"}</span>
            </div>
          </section>

          <section className="space-y-1">
            <h4 className="font-medium">What to do</h4>
            <ul className="list-inside list-disc space-y-1 text-muted-foreground">
              <li>Prefer a strike/expiration with tighter bid–ask and higher open interest.</li>
              <li>Use limit orders near mid — avoid market orders that fill at the ask/bid extremes.</li>
              <li>Size smaller if you still take the trade; exits can be costly.</li>
              <li>Re-check liquidity near market open when option markets are more active.</li>
            </ul>
          </section>

          <section className="space-y-2">
            <h4 className="font-medium">Your analysis notes ({ticker.toUpperCase()})</h4>
            <p className="text-xs text-muted-foreground">
              {storageMode === "browser"
                ? "Saved in this browser for pre-trade screening of this ticker."
                : "Saved on the server for this ticker (shared across saved trades)."}
            </p>
            {storageMode === "server" && serverQ.isPending ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" /> Loading notes…
              </div>
            ) : (
              <textarea
                className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
                placeholder="e.g. Spread widened after earnings — wait for OI to rebuild before selling puts…"
                value={draft}
                onChange={(e) => {
                  setDraft(e.target.value);
                  setSavedFlash(false);
                }}
              />
            )}
            {error && <p className="text-xs text-destructive">{error}</p>}
            {savedFlash && <p className="text-xs text-positive">Saved.</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setOpen(false)}>
                Close
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => saveMut.mutate()}
                disabled={saveMut.isPending || (storageMode === "server" && serverQ.isPending)}
              >
                {saveMut.isPending ? "Saving…" : "Save notes"}
              </Button>
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
