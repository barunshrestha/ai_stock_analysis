"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Trash2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function DeleteTradeDialog({
  tradeId,
  ticker,
  redirectToJournal = false,
  onDeleted,
  trigger,
}: {
  tradeId: number;
  ticker: string;
  redirectToJournal?: boolean;
  onDeleted?: () => void;
  trigger?: ReactNode;
}) {
  const router = useRouter();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mut = useMutation({
    mutationFn: () => api.optionsDeleteTrade(tradeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["options-trades"] });
      qc.invalidateQueries({ queryKey: ["csp-monitoring-summary"] });
      qc.removeQueries({ queryKey: ["options-trade", tradeId] });
      setOpen(false);
      onDeleted?.();
      if (redirectToJournal) router.push("/options");
    },
    onError: (e: Error) => setError(e instanceof ApiError ? e.message : "Delete failed"),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 shrink-0 text-muted-foreground hover:text-destructive"
            aria-label={`Delete ${ticker} trade`}
          >
            <Trash2 className="size-4" />
          </Button>
        )}
      </DialogTrigger>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Delete trade?</DialogTitle>
          <DialogDescription>
            This permanently removes the {ticker} trade from your journal. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={mut.isPending}>
            Cancel
          </Button>
          <Button type="button" variant="destructive" onClick={() => mut.mutate()} disabled={mut.isPending}>
            {mut.isPending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
