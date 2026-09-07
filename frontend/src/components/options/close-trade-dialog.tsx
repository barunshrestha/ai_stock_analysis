"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

export function CloseTradeDialog({
  tradeId,
  onClosed,
  defaultClosePrice,
}: {
  tradeId: number;
  onClosed?: () => void;
  defaultClosePrice?: string;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [closePrice, setClosePrice] = useState("");
  const [assigned, setAssigned] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (defaultClosePrice && open) {
      setClosePrice(defaultClosePrice);
    }
  }, [defaultClosePrice, open]);

  const mut = useMutation({
    mutationFn: () =>
      api.optionsCloseTrade(tradeId, {
        closed_at: new Date().toISOString(),
        close_net_per_contract: Number(closePrice),
        assigned,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["options-trades"] });
      qc.invalidateQueries({ queryKey: ["options-trade", tradeId] });
      setOpen(false);
      onClosed?.();
    },
    onError: (e: Error) => setError(e instanceof ApiError ? e.message : "Close failed"),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">Close trade</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Close position</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <label className="block space-y-1 text-sm">
            <span className="text-muted-foreground">Close net per contract (BTC/STC price)</span>
            <Input type="number" step="0.01" value={closePrice} onChange={(e) => setClosePrice(e.target.value)} />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={assigned} onChange={(e) => setAssigned(e.target.checked)} />
            Assigned (skip BTC — kept full opening premium)
          </label>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button onClick={() => mut.mutate()} disabled={mut.isPending || !closePrice}>
            {mut.isPending ? "Closing…" : "Confirm close"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
